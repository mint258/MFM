"""Meaningful Phase 1 contracts, independent of the large LMDB fixture."""

from copy import deepcopy

import pytest
import torch
from torch_geometric.data import Batch, Data
from torch_geometric.utils import to_dense_batch

from conftest import small_config
from phychem_mfm.data.descriptor_schema import (
    BOND_INDEX_FIELD,
    BOND_NEGATIVE_COUNT_FIELD,
    BOND_NEGATIVE_UPPER_IDS_FIELD,
    BOND_ORDER_FIELD,
    BOND_STATUS_FIELD,
    GRAPH_DESCRIPTOR_NAMES,
    SAMPLE_TYPE_ID_FIELD,
)
from phychem_mfm.factory import build_model
from phychem_mfm.model.phase1_specs import PHASE1_GRAPH_DESCRIPTOR_NAMES
from phychem_mfm.supervision import Objective


def phase1_config(route="light", geometry="legacy"):
    config = small_config(route)
    config["head"].update(profile="phase1", geometry_head=geometry)
    return config


def graph(large=False, *, sample_type=0, status="ok"):
    coordinates = (
        [[0.2, 0.0, 0.0], [1.3, 0.1, 0.0], [0.1, 1.5, 0.2], [0.4, 0.3, 1.7], [1.1, 1.2, 0.9]]
        if large else [[0.0, 0.0, 0.0], [1.2, 0.1, 0.0], [0.2, 1.4, 0.3]]
    )
    n = len(coordinates)
    result = Data(x=torch.arange(1, n + 1).view(-1, 1), pos=torch.tensor(coordinates))
    setattr(result, BOND_INDEX_FIELD, torch.tensor([[0, 1, 0], [1, 2, 2]]))
    setattr(result, BOND_ORDER_FIELD, torch.tensor([1, 4, 0]))
    setattr(result, BOND_STATUS_FIELD, status)
    setattr(result, SAMPLE_TYPE_ID_FIELD, torch.tensor([sample_type]))
    # These legacy nonedge fields must not influence Phase 1 selection.
    setattr(result, BOND_NEGATIVE_COUNT_FIELD, torch.tensor([100]))
    setattr(result, BOND_NEGATIVE_UPPER_IDS_FIELD, torch.tensor([0, 1, 2]))
    return result


def mixed_batch():
    return Batch.from_data_list([graph(), graph(large=True)])


@pytest.mark.parametrize("route", ("light", "expert"))
def test_phase1_heads_match_manifest_and_legacy_remains_available(route):
    model = build_model(phase1_config(route), preset=route)
    assert model.graph_descriptor_names == PHASE1_GRAPH_DESCRIPTOR_NAMES
    assert len(model.graph_descriptor_heads) == 23
    assert tuple(GRAPH_DESCRIPTOR_NAMES[i] for i in model.graph_descriptor_target_indices) == PHASE1_GRAPH_DESCRIPTOR_NAMES
    assert set(model.charge_descriptor_heads) == {"donor", "acceptor", "estate_index"}
    assert set(model.element_descriptor_heads) == {"is_aromatic", "is_in_ring", "min_ring_size"}
    assert not hasattr(model.bond_head, "existence")
    assert model.bond_head.order.out_features == 5
    assert model.bond_negative_ratio == 0
    assert model.bond_order_class_names == ("single", "double", "triple", "aromatic", "other")
    forbidden = ("formal_charge", "chiral_tag", "cip_code", "estate_type", "hybridization", "total_degree", "total_valence", "total_num_Hs")
    assert not any(name in key for key in model.state_dict() for name in forbidden)

    legacy = build_model(small_config(route), preset=route)
    assert len(legacy.graph_descriptor_heads) == 31
    assert "formal_charge" in legacy.charge_descriptor_heads
    assert "chiral_tag" in legacy.element_descriptor_heads
    assert hasattr(legacy.bond_head, "existence")
    assert legacy.bond_head.order.out_features == 6


def test_phase1_rejects_target_manifest_drift():
    config = phase1_config()
    config["head"]["graph_descriptor_names"] = ["MolLogP", "RadiusOfGyration"]
    with pytest.raises(ValueError, match="23-target"):
        build_model(config)
    config = phase1_config()
    config["head"]["profile"] = "misspelled"
    with pytest.raises(ValueError, match="profile"):
        build_model(config)


@pytest.mark.parametrize("radius_mask", (False, True))
def test_h0_is_rigid_invariant_and_padding_isolated(radius_mask):
    config = phase1_config()
    config["backbone"].update(use_radius_mask=radius_mask, radius=1.6)
    torch.manual_seed(112)
    model = build_model(config).eval()
    batch = mixed_batch()
    rotation = torch.tensor([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    moved = batch.clone()
    moved.pos = batch.pos @ rotation.T + torch.tensor([4.0, -2.0, 1.0])
    reflected = batch.clone()
    reflected.pos = batch.pos * torch.tensor([-1.0, 1.0, 1.0])
    with torch.no_grad():
        reference = model.encode_atoms(batch)
        torch.testing.assert_close(model.encode_atoms(moved), reference, rtol=2e-5, atol=3e-6)
        torch.testing.assert_close(model.encode_atoms(reflected), reference, rtol=2e-5, atol=3e-6)
        # The short graph gains padding when batched with the long graph.
        singleton = Batch.from_data_list([graph()])
        torch.testing.assert_close(model.encode_atoms(singleton), reference[:3], rtol=2e-5, atol=3e-6)
        graph_repr = model.encode_graph(batch)
        outputs = model.forward_pretrain(batch, [])
        assert outputs.atom_repr.shape == reference.shape
        torch.testing.assert_close(outputs.atom_repr, reference, rtol=0, atol=0)
        torch.testing.assert_close(outputs.graph_repr, graph_repr, rtol=0, atol=0)


def test_phase1_bond_pairs_exclude_non_edges_unlabeled_and_nonclean_graphs():
    model = build_model(phase1_config()).eval()
    batch = Batch.from_data_list([graph(), graph(large=True, sample_type=1)])
    rng_before = torch.random.get_rng_state().clone()
    sampled = model._sample_bond_pairs(batch, batch.batch)
    assert torch.equal(torch.random.get_rng_state(), rng_before)
    assert sampled.pair_index.tolist() == [[0, 1], [1, 2]]
    assert sampled.pair_graph_index.tolist() == [0, 0]
    assert sampled.order_target.tolist() == [0, 3]
    assert sampled.positive_pair_count == sampled.sampled_pair_count == 2
    assert sampled.existence.numel() == 0
    assert sampled.existence_target.shape == (2, 1)
    assert sampled.existence_target.eq(1).all()
    with torch.no_grad():
        outputs = model.forward_pretrain(batch, [Objective.BOND])
    assert outputs.bond.order.shape == (2, 5)
    assert outputs.bond.existence.shape == (2, 0)
    assert outputs.bond.order_target.tolist() == [0, 3]


def test_phase1_invalid_bond_graph_has_no_predictions_or_labels():
    model = build_model(phase1_config())
    batch = Batch.from_data_list([graph(status="failed")])
    outputs = model.forward_pretrain(batch, [Objective.BOND])
    assert outputs.bond.order.shape == (0, 5)
    assert outputs.bond.existence.shape == (0, 0)
    assert outputs.bond.order_target.numel() == 0


@pytest.mark.parametrize("route", ("light", "expert"))
def test_residual_geometry_covariance_target_independence_and_first_step_gradient(route):
    torch.manual_seed(212)
    model = build_model(phase1_config(route, geometry="residual"), preset=route).eval()
    batch = mixed_batch()
    batch.target_pos = batch.pos + torch.linspace(-0.15, 0.2, batch.pos.numel()).view_as(batch.pos)
    rotation = torch.tensor([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    translation = torch.tensor([3.0, -4.0, 2.0])
    transformed = batch.clone()
    transformed.pos = batch.pos @ rotation.T + translation
    reflected = batch.clone()
    reflection = torch.tensor([-1.0, 1.0, 1.0])
    reflected.pos = batch.pos * reflection
    changed_labels = batch.clone()
    changed_labels.target_pos = torch.full_like(batch.target_pos, 12345.0)
    with torch.no_grad():
        base = model.forward_pretrain(batch, [Objective.GEOMETRY])
        moved = model.forward_pretrain(transformed, [Objective.GEOMETRY])
        mirror = model.forward_pretrain(reflected, [Objective.GEOMETRY])
        no_targets = model.forward_pretrain(changed_labels, [Objective.GEOMETRY])
        mask = base.node_mask.squeeze(-1)
        expected = base.coordinate_pred[mask] @ rotation.T + translation
        torch.testing.assert_close(moved.coordinate_pred[mask], expected, rtol=2e-5, atol=3e-6)
        torch.testing.assert_close(mirror.coordinate_pred[mask], base.coordinate_pred[mask] * reflection, rtol=2e-5, atol=3e-6)
        assert moved.coordinate_pred[~mask].eq(0).all()
        torch.testing.assert_close(no_targets.coordinate_pred, base.coordinate_pred, rtol=0, atol=0)
        torch.testing.assert_close(moved.atom_repr, base.atom_repr, rtol=2e-5, atol=3e-6)
        singleton = Batch.from_data_list([graph()])
        single_output = model.forward_pretrain(singleton, [Objective.GEOMETRY])
        torch.testing.assert_close(single_output.coordinate_pred[0], base.coordinate_pred[0, :3], rtol=2e-5, atol=3e-6)

    model.train()
    outputs = model.forward_pretrain(batch, [Objective.GEOMETRY])
    outputs.atom_repr.retain_grad()
    target, _ = to_dense_batch(batch.target_pos, batch.batch)
    mask = outputs.node_mask.squeeze(-1)
    pair_mask = mask[:, :, None] & mask[:, None, :]
    predicted_distance = torch.cdist(outputs.coordinate_pred, outputs.coordinate_pred)
    target_distance = torch.cdist(target, target)
    loss = (predicted_distance[pair_mask] - target_distance[pair_mask]).square().mean()
    loss.backward()
    assert outputs.atom_repr.grad is not None
    assert torch.isfinite(outputs.atom_repr.grad).all()
    assert outputs.atom_repr.grad.abs().sum() > 0
    assert any(parameter.grad is not None and parameter.grad.abs().sum() > 0 for parameter in model.backbone.parameters())
    if route == "expert":
        assert any(parameter.grad is not None and parameter.grad.abs().sum() > 0 for parameter in model.task_adapters["geometry"].parameters())


@pytest.mark.parametrize("route", ("light", "expert"))
def test_geometry_candidate_keeps_all_common_initialization_and_h0_export(route):
    legacy_config = phase1_config(route, geometry="legacy")
    residual_config = deepcopy(legacy_config)
    residual_config["head"]["geometry_head"] = "residual"
    torch.manual_seed(319)
    original = build_model(legacy_config, preset=route).eval()
    original_rng = torch.random.get_rng_state().clone()
    torch.manual_seed(319)
    candidate = build_model(residual_config, preset=route).eval()
    assert torch.equal(torch.random.get_rng_state(), original_rng)
    original_common = {name: tensor for name, tensor in original.state_dict().items()
                       if not name.startswith("geometry_head.")}
    candidate_common = {name: tensor for name, tensor in candidate.state_dict().items()
                        if not name.startswith("geometry_head.")}
    assert original_common.keys() == candidate_common.keys()
    for name, tensor in original_common.items():
        torch.testing.assert_close(candidate_common[name], tensor, rtol=0, atol=0, msg=name)
    with torch.no_grad():
        batch = mixed_batch()
        torch.testing.assert_close(candidate.encode_atoms(batch), original.encode_atoms(batch), rtol=0, atol=0)
        torch.testing.assert_close(candidate.encode_graph(batch), original.encode_graph(batch), rtol=0, atol=0)
