"""Phase 1 contracts: step-zero supervision, fixed weighting, valid targets."""

from copy import deepcopy

import pytest
import torch
from torch_geometric.data import Data

from conftest import small_config
from phychem_mfm.data.descriptor_schema import (
    BOND_INDEX_FIELD, BOND_ORDER_FIELD, BOND_STATUS_FIELD, ELEMENT_CORRUPT_MASK_FIELD,
    GRAPH_DESCRIPTOR_NAMES, GRAPH_FIELD, GRAPH_MASK_FIELD, NODE_MASK_FIELD,
)
from phychem_mfm.factory import build_model
from phychem_mfm.model.phase1_specs import PHASE1_CHARGE_DESCRIPTOR_SPECS, PHASE1_ELEMENT_DESCRIPTOR_SPECS
from phychem_mfm.phase1.objectives import (
    GROUP_TASKS, PHASE1_VARIANTS, Phase1JointSchedule, Phase1LossPolicy,
    canonical_variant, step_runtime_metrics,
)
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.data import SAMPLE_TYPE_TO_ID, fast_collate
from phychem_mfm.training.losses import LossWeights, StageSchedule, compute_pretrain_loss, objectives_for_step
from phychem_mfm.training.optim import build_adamw, build_warmup_cosine_scheduler


def _model(route="light"):
    config = small_config(route)
    config["head"]["profile"] = "phase1"
    torch.manual_seed(718)
    return build_model(config, preset=route)


def _graph(view: str, *, atom_count=3):
    base_pos = torch.tensor([[0.0, 0.0, 0.0], [1.4, 0.2, 0.0], [0.2, 1.6, 0.3], [0.3, 0.2, 1.8]])[:atom_count]
    target_x = torch.tensor([[6], [8], [1], [6]])[:atom_count]
    x = target_x.clone()
    pos = base_pos.clone()
    corrupted = torch.zeros((atom_count, 1))
    if view in ("topo", "both"):
        x[0, 0] = 7
        corrupted[0, 0] = 1
    if view in ("geom", "both"):
        pos[1] += torch.tensor([0.2, -0.1, 0.15])
    result = Data(x=x, pos=pos, target_x=target_x, target_pos=base_pos, energy=torch.tensor([12.3]),
                  energy_mask=torch.ones(1, dtype=torch.bool),
                  y=torch.linspace(-0.3, 0.4, atom_count).view(-1, 1),
                  charge_mask=torch.ones((atom_count, 1)), sample_type_id=torch.tensor([SAMPLE_TYPE_TO_ID[view]]))
    setattr(result, ELEMENT_CORRUPT_MASK_FIELD, corrupted)
    setattr(result, BOND_INDEX_FIELD, torch.tensor([[0, 1], [1, 2]]))
    setattr(result, BOND_ORDER_FIELD, torch.tensor([1, 4]))
    setattr(result, BOND_STATUS_FIELD, "ok")
    setattr(result, GRAPH_FIELD, torch.linspace(0.25, 2.0, len(GRAPH_DESCRIPTOR_NAMES)).view(1, -1))
    setattr(result, GRAPH_MASK_FIELD, torch.ones((1, len(GRAPH_DESCRIPTOR_NAMES))))
    setattr(result, NODE_MASK_FIELD, torch.ones((atom_count, 1)))
    for spec in PHASE1_CHARGE_DESCRIPTOR_SPECS + PHASE1_ELEMENT_DESCRIPTOR_SPECS:
        if spec.task_type == "regression":
            target = torch.linspace(0.4, 1.3, atom_count).view(-1, 1)
        elif spec.task_type == "binary":
            target = (torch.arange(atom_count) % 2).view(-1, 1).float()
        else:
            target = (torch.arange(atom_count) % int(spec.num_classes)).view(-1, 1)
        setattr(result, spec.field_name, target)
    return result


def _batch():
    return fast_collate([_graph("clean"), _graph("topo", atom_count=4), _graph("geom")])


def _std():
    return {"stdE": 2.0, "stdQ": 0.4, "estate_index_std": 1.7,
            "graph_desc_std": torch.ones(len(GRAPH_DESCRIPTOR_NAMES))}


def _result(model, batch, variant, *, policy=None, schedule=None):
    supervision = SupervisionConfig.from_variant(variant)
    schedule = schedule or Phase1JointSchedule()
    outputs = model.forward_pretrain(batch, objectives_for_step(supervision, schedule, 0))
    result = compute_pretrain_loss(outputs, batch, _std(), supervision, LossWeights(), schedule, 0,
                                   graph_descriptor_indices=model.graph_descriptor_target_indices,
                                   phase1_mode=True, phase1_policy=policy)
    return outputs, result


@pytest.mark.parametrize("variant", PHASE1_VARIANTS)
def test_phase1_eight_condition_mapping_and_legacy_alias(variant):
    supervision = SupervisionConfig.from_variant(variant)
    token = "" if variant == "none" else variant
    assert supervision.structural == ("S" in token)
    assert supervision.descriptor == ("D" in token)
    assert supervision.physics == ("P" in token)
    assert canonical_variant(variant) == variant
    assert SupervisionConfig.from_variant("SPD").variant.value == "SPD"
    assert canonical_variant("SPD") == "SDP"
    assert SupervisionConfig.from_variant("SPD").objectives == SupervisionConfig.from_variant("SDP").objectives


@pytest.mark.parametrize("route", ("light", "expert"))
@pytest.mark.parametrize("variant", PHASE1_VARIANTS)
def test_step_zero_supervision_encoder_update_and_inactive_drift(route, variant):
    model = _model(route)
    batch = _batch()
    optimizer = build_adamw(model, lr=1e-3, weight_decay=0.1)
    scheduler = build_warmup_cosine_scheduler(optimizer, total_steps=100, warmup_steps=20)
    before = {name: parameter.detach().clone() for name, parameter in model.named_parameters()}
    optimizer.zero_grad(set_to_none=True)
    outputs, result = _result(model, batch, variant)
    assert outputs.atom_repr.shape == (10, 32)
    assert result.descriptor_scale == result.stage1_scale == 1.0
    assert result.missing_tasks == ()
    if variant == "none":
        assert not result.total.requires_grad
        assert result.total.item() == 0
        assert result.raw == result.weighted == result.groups == {}
        assert all(parameter.grad is None for parameter in model.parameters())
        return
    assert result.total.requires_grad and torch.isfinite(result.total)
    assert all(result.counts[name] > 0 for name in result.raw)
    result.total.backward()
    assert any(parameter.grad is not None and parameter.grad.abs().sum() > 0 for parameter in model.backbone.parameters())
    lr_used = optimizer.param_groups[0]["lr"]
    assert lr_used > 0
    optimizer.step()
    scheduler.step()
    runtime = step_runtime_metrics(optimizer, lr_used=lr_used, exposure_step=1, optimizer_update_step=1)
    assert runtime["train/lr_used"] == lr_used
    assert runtime["train/lr_next"] > lr_used
    assert any(not torch.equal(parameter, before[name]) for name, parameter in model.named_parameters() if name.startswith("backbone."))
    active_tasks = {"energy": "P" in variant, "charge": "P" in variant, "element": "S" in variant,
                    "geometry": "S" in variant, "bond": "S" in variant}
    for name, parameter in model.named_parameters():
        inactive = any(name.startswith(f"{task}_head.") or name.startswith(f"task_adapters.{task}.")
                       for task, active in active_tasks.items() if not active)
        inactive |= "D" not in variant and "descriptor_heads." in name
        if inactive:
            assert parameter.grad is None, name
            torch.testing.assert_close(parameter, before[name], rtol=0, atol=0, msg=name)


@pytest.mark.parametrize("route", ("light", "expert"))
def test_each_retained_target_has_a_nonzero_step_zero_path_to_h0(route):
    outputs, result = _result(_model(route), _batch(), "SDP")
    expected = {task for tasks in GROUP_TASKS.values() for task in tasks}
    assert set(result.raw) == expected
    for name, loss in result.raw.items():
        gradient = torch.autograd.grad(loss, outputs.atom_repr, retain_graph=True)[0]
        assert torch.isfinite(gradient).all(), name
        assert gradient.abs().sum() > 0, name


def test_fixed_task_and_enabled_group_means_and_custom_policy():
    model = _model()
    batch = _batch()
    policy = Phase1LossPolicy.from_mapping({"group_weights": {"S": 2.0, "D": 3.0, "P": 5.0},
                                          "task_weights": {"energy": 4.0}})
    _, result = _result(model, batch, "SDP", policy=policy)
    for group, tasks in GROUP_TASKS.items():
        denominator = sum(policy.task_weights[name] for name in tasks)
        expected = sum(result.raw[name] * policy.task_weights[name] for name in tasks) / denominator
        torch.testing.assert_close(result.groups[group], expected)
    expected_total = sum(result.groups[group] * policy.group_weights[group] for group in GROUP_TASKS) / 10.0
    torch.testing.assert_close(result.total, expected_total)
    torch.testing.assert_close(result.total, sum(result.weighted.values()))
    assert sum(result.task_weights.values()) == pytest.approx(1.0)
    assert "bond_existence" not in result.raw
    assert not any("formal_charge" in name or "chiral" in name or "NPR" in name for name in result.raw)


def test_missing_labels_do_not_renormalize_groups_or_create_false_updates():
    model = _model()
    optimizer = build_adamw(model, lr=1e-3, weight_decay=0.1)
    missing_parameters = tuple(model.graph_descriptor_heads["MolLogP"].parameters()) + tuple(
        model.charge_descriptor_heads["estate_index"].parameters())
    before_missing = [parameter.detach().clone() for parameter in missing_parameters]
    batch = _batch()
    getattr(batch, GRAPH_MASK_FIELD)[:, GRAPH_DESCRIPTOR_NAMES.index("MolLogP")] = 0
    setattr(batch, "rdkit_node_estate_index", torch.full((batch.x.size(0), 1), float("nan")))
    _, result = _result(model, batch, "D")
    assert result.counts["graph_descriptor/MolLogP"] == 0
    assert result.counts["node_descriptor/estate_index"] == 0
    assert set(result.missing_tasks) == {"graph_descriptor/MolLogP", "node_descriptor/estate_index"}
    assert not result.raw["graph_descriptor/MolLogP"].requires_grad
    assert not result.raw["node_descriptor/estate_index"].requires_grad
    assert result.task_weights["graph_descriptor/MolLogP"] == pytest.approx(1 / 29)
    result.total.backward()
    assert all(parameter.grad is None for parameter in model.graph_descriptor_heads["MolLogP"].parameters())
    assert all(parameter.grad is None for parameter in model.charge_descriptor_heads["estate_index"].parameters())
    optimizer.step()
    for parameter, before in zip(missing_parameters, before_missing):
        torch.testing.assert_close(parameter, before, rtol=0, atol=0)

    batch = fast_collate([_graph("topo")])
    _, result = _result(_model(), batch, "D")
    assert not result.total.requires_grad
    assert result.total.item() == 0
    assert len(result.missing_tasks) == 29
    assert result.counts["valid_tasks/D"] == 0


def test_nan_targets_are_excluded_before_regression_arithmetic():
    batch = _batch()
    batch.energy[0] = float("nan")
    batch.y[0] = float("nan")
    _, result = _result(_model(), batch, "P")
    assert torch.isfinite(result.total)
    assert result.counts["energy"] == 0
    assert result.counts["charge"] == 2
    assert result.missing_tasks == ("energy",)


@pytest.mark.parametrize("energy_case", ("absent_mask", "masked_placeholder", "missing_target", "masked_nan"))
def test_energy_requires_explicit_valid_mask_and_never_supervises_placeholders(energy_case):
    batch = _batch()
    if energy_case == "absent_mask":
        del batch.energy_mask
    elif energy_case == "missing_target":
        del batch.energy
    else:
        batch.energy_mask[0] = False
        batch.energy[0] = 0.0 if energy_case == "masked_placeholder" else float("nan")
    model = _model()
    _, result = _result(model, batch, "P")
    assert result.counts["energy"] == 0
    assert result.raw["energy"].item() == 0.0 and not result.raw["energy"].requires_grad
    assert "energy" in result.missing_tasks
    assert result.task_weights["energy"] == pytest.approx(0.5)
    result.total.backward()
    assert all(parameter.grad is None for parameter in model.energy_head.parameters())


def test_geometry_excludes_clean_and_topology_views_and_retains_morse_distance():
    batch = _batch()
    _, result = _result(_model(), batch, "S")
    assert result.counts["distance"] == 3
    assert result.counts["distance_pairs"] == 3
    clean_only = fast_collate([_graph("clean")])
    _, clean_result = _result(_model(), clean_only, "S")
    assert clean_result.counts["distance"] == clean_result.counts["element"] == 0
    assert clean_result.counts["bond_order"] == 2


def test_phase1_rejects_delayed_descriptor_schedule_and_nonpositive_weights():
    model = _model()
    batch = _batch()
    with pytest.raises(ValueError, match="positive supervision"):
        _result(model, batch, "D", schedule=StageSchedule())
    decayed = StageSchedule(stage1_max_steps=0, descriptor_ramp_steps=0, stage1_decay_steps=1)
    supervision = SupervisionConfig.from_variant("SDP")
    outputs = model.forward_pretrain(batch, supervision.objectives)
    with pytest.raises(ValueError, match="fixed full-strength"):
        compute_pretrain_loss(outputs, batch, _std(), supervision, LossWeights(), decayed, 2,
                              phase1_mode=True, graph_descriptor_indices=model.graph_descriptor_target_indices)
    with pytest.raises(ValueError, match="strictly positive"):
        Phase1LossPolicy.from_mapping({"group_weights": {"D": 0.0}})
    with pytest.raises(ValueError, match="retained tasks"):
        Phase1LossPolicy.from_mapping({"task_weights": {"bond_existence": 1.0}})


def test_invalid_classification_labels_and_view_identifiers_are_not_coerced():
    batch = _batch()
    setattr(batch, "rdkit_node_donor", torch.full((batch.x.size(0), 1), 0.5))
    setattr(batch, "rdkit_node_min_ring_size", torch.full((batch.x.size(0), 1), -1))
    _, result = _result(_model(), batch, "D")
    assert result.counts["node_descriptor/donor"] == result.counts["node_descriptor/min_ring_size"] == 0
    assert not result.raw["node_descriptor/donor"].requires_grad
    assert not result.raw["node_descriptor/min_ring_size"].requires_grad
    batch.sample_type_id = batch.sample_type_id.float()
    batch.sample_type_id[0] = 0.5
    with pytest.raises(ValueError, match="finite integer"):
        _result(_model(), batch, "D")


def test_spd_remains_legacy_metadata_and_joint_does_not_depend_on_exposure():
    legacy = SupervisionConfig.from_variant("SPD").to_dict()
    assert legacy["variant"] == "SPD"
    schedule = Phase1JointSchedule()
    for step in (0, 1, 15000, 420000):
        assert schedule.descriptor_scale(step) == schedule.stage1_scale(step) == 1.0
    torch.manual_seed(818)
    state = deepcopy(_model().backbone.state_dict())
    for variant in PHASE1_VARIANTS:
        # Supervision choices do not mutate or select a different encoder.
        SupervisionConfig.from_variant(variant)
        for name, tensor in _model().backbone.state_dict().items():
            torch.testing.assert_close(tensor, state[name], rtol=0, atol=0)
