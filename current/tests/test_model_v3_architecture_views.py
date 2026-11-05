"""C3 clean/both routing, original S losses and independent eligibility."""
from dataclasses import replace
import random

import numpy as np
import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.factory import build_model
from phychem_mfm.model.v3_heads import V3HeadBank
from phychem_mfm.phase1.v3_architecture_views import (V3TwoViewModel, build_two_structural_views,
    combined_degrade_config, two_view_structural_raw_losses)
from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_structural import (StructuralFieldBinding, StructuralViewConfig, build_structural_views)
from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule, Phase1LossPolicy
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.degrade_molecules import degrade_once
from phychem_mfm.training.losses import LossWeights


@pytest.fixture
def setup():
    previous = torch.get_num_threads(); torch.set_num_threads(1)
    torch.manual_seed(713)
    records = [Data(x=torch.full((12, 1), 5, dtype=torch.long), pos=torch.randn(12, 3) * .4,
        rdkit_bond_index=torch.stack((torch.arange(11), torch.arange(1, 12))),
        rdkit_bond_order=(torch.arange(11) % 5 + 1).long(), rdkit_bond_status="ok") for _ in range(2)]
    base = Batch.from_data_list(records)
    encoder = build_model({"architecture": {"preset": "shared_light"},
        "backbone": {"dim": 512, "layers": 1, "heads": 8, "ff_mult": 1, "n_atom_types": 119},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise", "geometry_hidden_dim": 64}})
    fields = (FieldSpec("element", "S", "structural", "atom", kind="classification", classes=119),
        FieldSpec("noise", "S", "structural", "atom", kind="denoise_eps_mse", representation="vector"),
        FieldSpec("bond", "S", "structural", "pair", kind="classification", classes=5),
        FieldSpec("energy", "P", "physics", "graph"), FieldSpec("atom", "D", "descriptor", "atom"))
    registry = LabelRegistry(fields, "synthetic-C3-test-v1", "a" * 64)
    binding = StructuralFieldBinding("element", "noise", "bond")
    pd_registry = replace(registry, fields=tuple(field for field in fields if field.group != "S"))
    heads = V3HeadBank(pd_registry, forms="H2")
    model = V3TwoViewModel(encoder, heads, registry, binding)
    normalizations = {name: TrainNormalization((0.,), (1.,), "b" * 64, "synthetic-C3-test-v1")
                      for name in ("energy", "atom")}
    targets = {"energy": FieldTarget(torch.tensor([[1.], [2.]]), torch.ones(2, dtype=torch.bool)),
               "atom": FieldTarget(torch.ones(24, 1), torch.ones(24, dtype=torch.bool))}
    try:
        yield model, base, registry, binding, normalizations, targets
    finally:
        torch.set_num_threads(previous)


def source_loss(output, batch):
    return compute_phase1_loss(output, batch, None, SupervisionConfig.from_variant("S"), LossWeights(),
        Phase1JointSchedule(), 0, policy=Phase1LossPolicy.from_mapping({"geometry_task": "denoise_eps_mse"}))


def test_both_reuses_original_degradation_with_separate_levels_masks_and_native_order(setup):
    model, base, registry, binding, norms, targets = setup
    config = StructuralViewConfig(seed=13, epoch=4, topology_level=.3, geometry_level=.2)
    rng = torch.get_rng_state().clone(), random.getstate(), np.random.get_state()
    views = build_two_structural_views(base, ordinals=(100, 101), config=config)
    again = build_two_structural_views(base, ordinals=(100, 101), config=config)
    assert views.batch.sample_type_id.tolist() == [0, 3, 0, 3]
    assert views.base_graph_index.tolist() == [0, 0, 1, 1]
    assert torch.equal(views.batch.x[views.clean_atom_rows], base.x)
    assert torch.equal(views.batch.pos[views.clean_atom_rows], base.pos)
    assert torch.equal(views.batch.x, again.batch.x) and torch.equal(views.batch.pos, again.batch.pos)
    assert torch.equal(torch.get_rng_state(), rng[0]) and random.getstate() == rng[1]
    state = np.random.get_state()
    assert state[0] == rng[2][0] and np.array_equal(state[1], rng[2][1]) and state[2:] == rng[2][2:]
    cfg = combined_degrade_config(config)
    assert cfg.topo_replace_frac == .09 and cfg.topo_delete_frac == 0. and cfg.geom_noise_std == .1
    for i, record in enumerate(base.to_data_list()):
        expected = degrade_once(record.clone(), cfg, torch.Generator().manual_seed(config.noise_seed(100+i)))
        actual = views.batch.to_data_list()[2*i+1]
        assert torch.equal(actual.x, expected.x) and torch.equal(actual.pos, expected.pos)
        assert torch.equal(actual.target_x, record.x) and torch.equal(actual.target_pos, record.pos)
        assert torch.equal(actual.element_corrupt_mask.view(-1), actual.x.ne(record.x).any(-1))
    changed = build_two_structural_views(base, ordinals=(100, 101), config=replace(config, epoch=5))
    assert not torch.equal(views.batch.pos, changed.batch.pos)
    moved = views.to("cpu")
    assert moved.batch.sample_type_id.tolist() == [0, 3, 0, 3]


def test_two_view_bridge_matches_each_original_source_task_value_count_and_gradient(setup):
    model, base, registry, binding, norms, targets = setup
    views = build_two_structural_views(base, ordinals=(20, 21))
    prediction = model.forward_pretrain(views, enabled_groups=("S",))
    original = source_loss(prediction.source_outputs, views.batch)
    result = model.compute_loss(prediction, views, {}, norms, enabled_groups=("S",), weights=LossWeights())
    parameters = (model.encoder.element_head.weight, model.encoder.geometry_head.pair_mlp[-1].weight,
                  model.encoder.bond_head.order.weight, model.encoder.backbone.atom_emb.weight)
    for field, original_name in (("element", "element"), ("noise", "denoise_eps_mse"), ("bond", "bond_order")):
        assert torch.equal(result.fields[field], original.raw[original_name])
        assert result.counts[field] == original.counts[original_name] > 0
        left = torch.autograd.grad(result.fields[field], parameters, retain_graph=True, allow_unused=True)
        right = torch.autograd.grad(original.raw[original_name], parameters, retain_graph=True, allow_unused=True)
        for a, b in zip(left, right):
            assert (a is None and b is None) or torch.equal(a, b)
    assert original.counts["view/both"] == original.counts["view/clean"] == 2
    assert original.counts["view/geom"] == original.counts["view/topo"] == 0


def test_clean_bond_and_pd_use_same_single_forward_and_original_native_clean_rows(setup):
    model, base, registry, binding, norms, targets = setup
    views = build_two_structural_views(base, ordinals=(30, 31))
    calls, pd_inputs = [], []
    hook = model.encoder.backbone.register_forward_hook(lambda *args: calls.append(1))
    pd_hook = model.pd_heads.register_forward_pre_hook(lambda module, args: pd_inputs.append(args))
    try:
        result = model.forward_pretrain(views, enabled_groups=("S", "D", "P"))
    finally:
        hook.remove(); pd_hook.remove()
    assert calls == [1] and len(pd_inputs) == 1
    assert torch.equal(pd_inputs[0][0], result.clean_h0)
    assert torch.equal(pd_inputs[0][1], base.batch) and torch.equal(pd_inputs[0][2], base.pos)
    bond = result.source_outputs.bond
    # The existing source head retains only clean positive bond pairs.
    assert views.batch.sample_type_id[bond.pair_graph_index].eq(0).all()
    source = source_loss(result.source_outputs, views.batch)
    assert source.counts["bond_order"] == 22
    loss = model.compute_loss(result, views, targets, norms, enabled_groups=("S", "D", "P"), weights=LossWeights())
    assert loss.counts["energy"] == 2 and loss.counts["atom"] == 24
    loss.total.backward()
    assert model.pd_heads.group_projectors["P"][0].weight.grad is not None


def test_independent_role_graph_atom_pair_masks_filter_both_supervisions_separately(setup):
    model, base, registry, binding, norms, targets = setup
    eligibility = {"element": torch.tensor([True, False]), "noise": torch.tensor([False, True]),
                   "bond": torch.tensor([True, True])}
    views = build_two_structural_views(base, ordinals=(40, 41), graph_eligibility=eligibility)
    types, corruption = views.batch.sample_type_id.clone(), views.batch.element_corrupt_mask.clone()
    prediction = model.forward_pretrain(views, enabled_groups=("S",))
    raw, counts = two_view_structural_raw_losses(prediction.source_outputs, views, registry, binding, LossWeights())
    assert counts == {"element": 1, "noise": 12, "bond": 22}
    atomic = torch.zeros(24, dtype=torch.bool); atomic[12:15] = True
    pairs = torch.zeros(22, dtype=torch.bool); pairs[0] = True
    masked_raw, masked_counts = two_view_structural_raw_losses(prediction.source_outputs, views,
        registry, binding, LossWeights(), atom_eligibility={"noise": atomic}, bond_pair_eligibility=pairs)
    assert masked_counts == {"element": 1, "noise": 3, "bond": 1}
    assert torch.equal(raw["element"], masked_raw["element"])
    assert torch.equal(views.batch.sample_type_id, types) and torch.equal(views.batch.element_corrupt_mask, corruption)


def test_disabled_field_has_no_parameter_gradient_and_pd_only_has_one_clean_view(setup):
    model, base, registry, binding, norms, targets = setup
    views = build_two_structural_views(base, ordinals=(50, 51))
    prediction = model.forward_pretrain(views, enabled_groups=("S",), enabled_fields=("noise",))
    loss = model.compute_loss(prediction, views, {}, norms, enabled_groups=("S",), enabled_fields=("noise",),
                              weights=LossWeights())
    assert set(loss.fields) == {"noise"} and loss.counts["noise"] == 24
    loss.total.backward()
    assert model.encoder.element_head.weight.grad is None and model.encoder.bond_head.order.weight.grad is None
    clean = build_two_structural_views(base, ordinals=(50, 51), include_structural=False)
    assert clean.batch.sample_type_id.tolist() == [0, 0]
    result = model.forward_pretrain(clean, enabled_groups=("D", "P"))
    assert not result.structural_active
    pd = model.compute_loss(result, clean, targets, norms, enabled_groups=("D", "P"), weights=LossWeights())
    assert set(pd.fields) == {"energy", "atom"}
    with pytest.raises(ValueError, match="clean/both"):
        model.forward_pretrain(build_structural_views(base, ordinals=(50, 51)), enabled_groups=("S",))


def test_no_actual_element_changes_means_no_false_element_supervision(setup):
    model, base, registry, binding, norms, targets = setup
    views = build_two_structural_views(base, ordinals=(60, 61), config=StructuralViewConfig(topology_level=0.))
    assert views.batch.element_corrupt_mask.sum() == 0
    output = model.forward_pretrain(views, enabled_groups=("S",))
    result = model.compute_loss(output, views, {}, norms, enabled_groups=("S",), weights=LossWeights())
    assert result.counts["element"] == 0 and result.observed_fields["S"] == 2
