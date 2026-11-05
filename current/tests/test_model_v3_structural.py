"""Canonical S compatibility, independent masks and single-pass clean PD routing."""
from dataclasses import replace
import random

import numpy as np
import pytest
import torch
from torch_geometric.data import Batch, Data

from phychem_mfm.factory import build_model
from phychem_mfm.model.v3_heads import V3HeadBank
from phychem_mfm.model.v3_multiview import V3MultiViewModel
from phychem_mfm.phase1.objectives import Phase1JointSchedule, Phase1LossPolicy, compute_phase1_loss
from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_structural import (StructuralFieldBinding, StructuralViewConfig,
                                             build_structural_views, structural_raw_losses)
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.losses import LossWeights


def setup_model():
    torch.manual_seed(818)
    generator = torch.Generator().manual_seed(111)
    records = []
    for i in range(2):
        records.append(Data(x=torch.full((12, 1), 5, dtype=torch.long),
            pos=torch.randn(12, 3, generator=generator) * .4 + i,
            rdkit_bond_index=torch.stack((torch.arange(11), torch.arange(1, 12))),
            rdkit_bond_order=(torch.arange(11) % 5 + 1).long(), rdkit_bond_status="ok"))
    base = Batch.from_data_list(records)
    encoder = build_model({"architecture": {"preset": "shared_light"},
        "backbone": {"dim": 512, "layers": 1, "heads": 8, "ff_mult": 1, "n_atom_types": 119},
        "head": {"profile": "phase1", "geometry_head": "equivariant_noise",
                 "geometry_hidden_dim": 64, "geometry_message_layers": 0, "geometry_pair_chunk_size": 8192}})
    fields = (FieldSpec("s_element", "S", "structural", "atom", kind="classification", classes=119),
              FieldSpec("s_noise", "S", "structural", "atom", kind="denoise_eps_mse", representation="vector"),
              FieldSpec("s_bond", "S", "structural", "pair", kind="classification", classes=5),
              FieldSpec("new_energy", "P", "physics", "graph"),
              FieldSpec("new_atom", "D", "descriptor", "atom"))
    reg = LabelRegistry(fields, "synthetic-S-bridge-v1", "a" * 64)
    binding = StructuralFieldBinding("s_element", "s_noise", "s_bond")
    pd_registry = replace(reg, fields=tuple(field for field in fields if field.group != "S"))
    heads = V3HeadBank(pd_registry, forms="H2")
    model = V3MultiViewModel(encoder, heads, reg, binding)
    norms = {name: TrainNormalization((0.,), (1.,), "b" * 64, "synthetic-S-bridge-v1")
             for name in ("new_energy", "new_atom")}
    targets = {"new_energy": FieldTarget(torch.tensor([[1.], [2.]]), torch.ones(2, dtype=torch.bool)),
               "new_atom": FieldTarget(torch.arange(24, dtype=torch.float32)[:, None] / 24,
                                        torch.ones(24, dtype=torch.bool))}
    return model, base, reg, binding, norms, targets


def legacy_loss(outputs, batch):
    return compute_phase1_loss(outputs, batch, None, SupervisionConfig.from_variant("S"), LossWeights(),
        Phase1JointSchedule(), 0, policy=Phase1LossPolicy.from_mapping({"geometry_task": "denoise_eps_mse"}))


@pytest.fixture
def single_intraop_thread():
    # Actual diagnostic 4520338: even the identical source loss has non-bitwise
    # noise->embedding gradients at 8 threads. At 1 thread, source repeats,
    # duplicate source loss and bridge are all bitwise. Fix the test environment
    # rather than relax torch.equal; do not attribute a specific operator.
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(previous)


def test_view_building_keeps_original_targets_corruption_facts_and_rng_streams():
    model, base, reg, binding, norms, targets = setup_model()
    before_x, before_pos = base.x.clone(), base.pos.clone()
    rng = torch.get_rng_state().clone(), random.getstate(), np.random.get_state()
    config = StructuralViewConfig(seed=7, epoch=2)
    views = build_structural_views(base, ordinals=(100, 101), config=config)
    repeated = build_structural_views(base, ordinals=(100, 101), config=config)
    assert torch.equal(views.batch.x, repeated.batch.x) and torch.equal(views.batch.pos, repeated.batch.pos)
    assert torch.equal(torch.get_rng_state(), rng[0]) and random.getstate() == rng[1]
    actual_np = np.random.get_state()
    assert rng[2][0] == actual_np[0] and np.array_equal(rng[2][1], actual_np[1]) and rng[2][2:] == actual_np[2:]
    assert torch.equal(base.x, before_x) and torch.equal(base.pos, before_pos)
    assert torch.equal(views.batch.x[views.clean_atom_rows], base.x)
    assert torch.equal(views.batch.pos[views.clean_atom_rows], base.pos)
    assert views.batch.sample_type_id.tolist() == [0, 1, 2, 0, 1, 2]
    assert views.base_graph_index.tolist() == [0, 0, 0, 1, 1, 1]
    for i, record in enumerate(views.batch.to_data_list()):
        source = base.to_data_list()[i // 3]
        assert torch.equal(record.target_x, source.x) and torch.equal(record.target_pos, source.pos)
        assert torch.equal(record.element_corrupt_mask.view(-1), record.x.ne(source.x).any(-1))
    next_epoch = build_structural_views(base, ordinals=(100, 101), config=replace(config, epoch=3))
    assert not torch.equal(views.batch.pos, next_epoch.batch.pos)


def test_source_s_heads_raw_losses_counts_and_parameter_gradients_are_retained(single_intraop_thread):
    model, base, reg, binding, norms, targets = setup_model()
    assert model.encoder.element_head is dict(model.encoder.named_children())["element_head"]
    assert model.encoder.bond_head.__class__.__name__ == "BondPairHead"
    assert model.encoder.geometry_head.__class__.__name__ == "EquivariantDenoisingHead"
    views = build_structural_views(base, ordinals=(10, 11))
    output = model.forward_pretrain(views, enabled_groups=("S",))
    source = legacy_loss(output.source_outputs, views.batch)
    result = model.compute_loss(output, views, {}, norms, enabled_groups=("S",), weights=LossWeights())
    parameters = (model.encoder.element_head.weight, model.encoder.bond_head.order.weight,
                  model.encoder.geometry_head.pair_mlp[-1].weight, model.encoder.backbone.atom_emb.weight)
    for field, name in (("s_element", "element"), ("s_noise", "denoise_eps_mse"), ("s_bond", "bond_order")):
        assert torch.equal(result.fields[field], source.raw[name])
        assert result.counts[field] == source.counts[name] > 0
        actual = torch.autograd.grad(result.fields[field], parameters, retain_graph=True, allow_unused=True)
        expected = torch.autograd.grad(source.raw[name], parameters, retain_graph=True, allow_unused=True)
        for a, b in zip(actual, expected):
            assert (a is None and b is None) or torch.equal(a, b)


def test_pd_receives_only_clean_h0_from_the_same_single_encoder_pass():
    model, base, reg, binding, norms, targets = setup_model()
    views = build_structural_views(base, ordinals=(20, 21))
    calls, pd_inputs = [], []
    encoder_hook = model.encoder.backbone.register_forward_hook(lambda module, args, output: calls.append(tuple(output.shape)))
    pd_hook = model.pd_heads.register_forward_pre_hook(lambda module, args: pd_inputs.append(tuple(value.detach().clone() for value in args)))
    try:
        output = model.forward_pretrain(views, enabled_groups=("S", "D", "P"))
    finally:
        encoder_hook.remove(); pd_hook.remove()
    assert calls == [(72, 512)] and len(pd_inputs) == 1
    assert torch.equal(pd_inputs[0][0], output.source_outputs.atom_repr[views.clean_atom_rows])
    assert torch.equal(pd_inputs[0][1], base.batch) and torch.equal(pd_inputs[0][2], base.pos)
    assert set(output.pd_predictions) == {"new_energy", "new_atom"}
    assert output.pd_predictions["new_energy"].shape == (2, 1)
    assert output.pd_predictions["new_atom"].shape == (24, 1)
    loss = model.compute_loss(output, views, targets, norms, enabled_groups=("S", "D", "P"), weights=LossWeights())
    assert loss.counts["new_energy"] == 2 and loss.counts["new_atom"] == 24
    assert loss.total.requires_grad


def test_pd_only_uses_clean_view_and_does_not_execute_or_update_structural_heads():
    model, base, reg, binding, norms, targets = setup_model()
    views = build_structural_views(base, ordinals=(20, 21), include_structural=False)
    calls = []
    hooks = [module.register_forward_hook(lambda *args: calls.append(1)) for module in
             (model.encoder.element_head, model.encoder.geometry_head, model.encoder.bond_head)]
    try:
        output = model.forward_pretrain(views, enabled_groups=("P", "D"))
        loss = model.compute_loss(output, views, targets, norms, enabled_groups=("P", "D"), weights=LossWeights())
        loss.total.backward()
    finally:
        for hook in hooks:
            hook.remove()
    assert not calls and len(views.batch.x) == 24
    assert all(parameter.grad is None for module in (model.encoder.element_head, model.encoder.geometry_head,
                                                    model.encoder.bond_head) for parameter in module.parameters())
    assert any(parameter.grad is not None for parameter in model.encoder.backbone.parameters())
    with pytest.raises(ValueError, match="PD-only"):
        model.forward_pretrain(views, enabled_groups=("S", "P"))


def test_distinct_role_and_atom_pair_masks_do_not_change_other_s_tasks_or_corruption():
    model, base, reg, binding, norms, targets = setup_model()
    eligibility = {"element": torch.tensor([True, False]), "noise": torch.tensor([False, True]),
                   "bond": torch.tensor([True, True])}
    views = build_structural_views(base, ordinals=(40, 41), graph_eligibility=eligibility)
    original_corruption = views.batch.element_corrupt_mask.clone()
    original_x, original_pos = views.batch.x.clone(), views.batch.pos.clone()
    output = model.forward_pretrain(views, enabled_groups=("S",))
    raw, counts = structural_raw_losses(output.source_outputs, views, reg, binding, LossWeights())
    assert counts == {"s_element": 1, "s_noise": 12, "s_bond": 22}
    atomic = torch.zeros(24, dtype=torch.bool); atomic[12:15] = True
    pair_mask = torch.zeros(22, dtype=torch.bool); pair_mask[0] = True
    masked_raw, masked_counts = structural_raw_losses(output.source_outputs, views, reg, binding, LossWeights(),
        atom_eligibility={"noise": atomic}, bond_pair_eligibility=pair_mask)
    assert masked_counts == {"s_element": 1, "s_noise": 3, "s_bond": 1}
    assert torch.equal(masked_raw["s_element"], raw["s_element"])
    assert torch.equal(views.batch.element_corrupt_mask, original_corruption)
    assert torch.equal(views.batch.x, original_x) and torch.equal(views.batch.pos, original_pos)
    assert int(views.batch.element_corrupt_mask.sum()) == 2


def test_disabled_structural_field_has_no_gradient_and_is_absent_from_s_mean():
    model, base, reg, binding, norms, targets = setup_model()
    views = build_structural_views(base, ordinals=(10, 11))
    enabled = ("s_noise", "s_bond")
    output = model.forward_pretrain(views, enabled_groups=("S",), enabled_fields=enabled)
    result = model.compute_loss(output, views, {}, norms, enabled_groups=("S",), weights=LossWeights(), enabled_fields=enabled)
    assert set(result.fields) == set(enabled) and result.observed_fields["S"] == 2
    torch.testing.assert_close(result.groups["S"], (result.fields["s_noise"] + result.fields["s_bond"]) / 2)
    result.total.backward()
    assert all(parameter.grad is None for parameter in model.encoder.element_head.parameters())


def test_structural_binding_sigma_and_pd_bank_are_explicit_and_checked():
    model, base, reg, binding, norms, targets = setup_model()
    with pytest.raises(ValueError, match="distinct explicit"):
        StructuralFieldBinding("s_noise", "s_noise", "s_bond").validate(reg)
    with pytest.raises(ValueError, match="exactly the P/D"):
        V3MultiViewModel(model.encoder, V3HeadBank(reg), reg, binding)
    views = build_structural_views(base, ordinals=(1, 2))
    output = model.forward_pretrain(views, enabled_groups=("S",))
    with pytest.raises(ValueError, match="sigma"):
        model.compute_loss(output, views, {}, norms, enabled_groups=("S",), weights=replace(LossWeights(), denoise_sigma=.2))


def test_unknown_field_and_forward_loss_group_field_drift_are_rejected():
    model, base, reg, binding, norms, targets = setup_model()
    views = build_structural_views(base, ordinals=(1, 2))
    with pytest.raises(ValueError, match="Unknown or duplicate"):
        model.forward_pretrain(views, enabled_groups=("S", "P"), enabled_fields=("typo_missing_field",))
    output = model.forward_pretrain(views, enabled_groups=("S", "P"), enabled_fields=("s_noise", "new_energy"))
    with pytest.raises(ValueError, match="group or field switches"):
        model.compute_loss(output, views, targets, norms, enabled_groups=("S", "P"), weights=LossWeights())
    with pytest.raises(ValueError, match="group or field switches"):
        model.compute_loss(output, views, targets, norms, enabled_groups=("S", "D"), weights=LossWeights(),
                           enabled_fields=("s_noise", "new_atom"))
    with pytest.raises(ValueError, match="Unknown or duplicate"):
        model.compute_loss(output, views, targets, norms, enabled_groups=("S", "P"), weights=LossWeights(),
                           enabled_fields=("mistyped",))
