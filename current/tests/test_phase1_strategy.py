"""Synthetic preparation recipe tests; no formal runner or real target access."""
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest
import torch

from phychem_mfm.phase1.objectives import GROUP_TASKS, Phase1LossPolicy
from phychem_mfm.phase1.strategy import PositivePiecewiseJoint, PositiveWeightStage, RECIPE_NAME
from phychem_mfm.training.optim import build_adamw
from test_phase1_training import _batch, _model, _result


def recipe_dict(variant="SDP"):
    return {"name": RECIPE_NAME, "index_unit": "optimizer_update_step", "variant": variant,
            "max_updates": 6, "stages": [
                {"end_update_exclusive": 2, "group_weight_multipliers": {"S": 2., "D": 1., "P": 1.}},
                {"end_update_exclusive": 4, "group_weight_multipliers": {"S": 1., "D": 2., "P": 1.}},
                {"end_update_exclusive": 6, "group_weight_multipliers": {"S": 1., "D": 1., "P": 2.}},
            ]}


def test_boundaries_roundtrip_and_restore_reconstruction_have_no_cursor():
    values = recipe_dict()
    schedule = PositivePiecewiseJoint.from_dict(values)
    assert schedule.to_dict() == values
    assert PositivePiecewiseJoint.from_dict(schedule.to_dict()).sha256 == schedule.sha256
    base = Phase1LossPolicy()
    for u, expected_stage in ((0, 0), (1, 0), (2, 1), (3, 1), (4, 2), (5, 2), (2, 1), (0, 0)):
        selected = schedule.policy_at_update(base, u)
        restored = PositivePiecewiseJoint.from_dict(values).policy_at_update(base, u)
        assert selected.to_dict() == restored.to_dict()
        assert selected.stage_id == expected_stage
        assert selected.begin_update_inclusive == expected_stage * 2
        assert selected.end_update_exclusive == (expected_stage + 1) * 2
        assert selected.optimizer_update_step == u
        assert selected.schedule_sha256 == schedule.sha256
        assert selected.policy.task_weights == base.task_weights
        assert sum(selected.effective_group_coefficients.values()) == pytest.approx(1.)
    changed = deepcopy(values)
    changed["stages"][1]["group_weight_multipliers"]["D"] = 3.
    assert PositivePiecewiseJoint.from_dict(changed).sha256 != schedule.sha256
    moved = deepcopy(values)
    moved["stages"][0]["end_update_exclusive"] = 1
    assert PositivePiecewiseJoint.from_dict(moved).sha256 != schedule.sha256
    # Equal-duration rotating emphasis retains equal integrated group weight;
    # it does not assert isolation of supervision order from optimizer history.
    for group in GROUP_TASKS:
        mean = sum(schedule.policy_at_update(base, u).effective_group_coefficients[group]
                   for u in range(schedule.max_updates)) / schedule.max_updates
        assert mean == pytest.approx(1. / 3.)


def test_caller_maps_and_returned_dicts_cannot_drift_schedule_or_selected_policy():
    source = recipe_dict()
    schedule = PositivePiecewiseJoint.from_dict(source)
    original, digest = schedule.to_dict(), schedule.sha256
    source["stages"][0]["group_weight_multipliers"]["S"] = 0.
    source["stages"].clear()
    exported = schedule.to_dict()
    exported["stages"][0]["group_weight_multipliers"]["D"] = 90.
    assert schedule.to_dict() == original and schedule.sha256 == digest
    with pytest.raises(TypeError):
        schedule.stages[0].group_weight_multipliers["S"] = 0.
    with pytest.raises(FrozenInstanceError):
        schedule.max_updates = 100
    base = Phase1LossPolicy.from_mapping({"task_weights": {"energy": 2.}})
    selected = schedule.policy_at_update(base, 0)
    saved = selected.to_dict()
    base.group_weights["S"] = 50.
    base.task_weights["energy"] = 50.
    selected.to_dict()["loss_policy"]["task_weights"]["energy"] = 0.
    assert selected.to_dict() == saved
    for weights in (selected.policy.group_weights, selected.policy.task_weights,
                    selected.effective_group_coefficients):
        with pytest.raises(TypeError):
            weights[next(iter(weights))] = 0.


@pytest.mark.parametrize("variant", ("S", "D", "P"))
def test_single_group_multipliers_cancel_and_do_not_supply_an_order_contrast(variant):
    schedule = PositivePiecewiseJoint.from_dict(recipe_dict(variant))
    base = Phase1LossPolicy.from_mapping({"group_weights": {"S": 2., "D": 3., "P": 5.}})
    for u in (0, 2, 4):
        selected = schedule.policy_at_update(base, u)
        assert dict(selected.effective_group_coefficients) == {variant: 1.}
        assert selected.policy.task_weights == base.task_weights


def test_dynamic_enabled_denominator_matches_current_loss_and_excludes_disabled_groups():
    values = recipe_dict("SD")
    values["stages"][0]["group_weight_multipliers"] = {"S": 3., "D": 2., "P": 1e100}
    schedule = PositivePiecewiseJoint.from_dict(values)
    base = Phase1LossPolicy.from_mapping({"group_weights": {"S": 2., "D": 3., "P": 5.}})
    model, batch = _model(), _batch()
    for u, expected in ((0, {"S": .5, "D": .5}), (2, {"S": .25, "D": .75})):
        selected = schedule.policy_at_update(base, u)
        assert dict(selected.effective_group_coefficients) == pytest.approx(expected)
        _, result = _result(model, batch, "SD", policy=selected.policy)
        assert set(result.groups) == {"S", "D"}
        for group, coefficient in expected.items():
            assert sum(result.task_weights[name] for name in GROUP_TASKS[group]) == pytest.approx(coefficient)
        expected_loss = sum(result.groups[group] * expected[group] for group in expected)
        torch.testing.assert_close(result.total, expected_loss)
        assert result.descriptor_scale == result.stage1_scale == 1.


@pytest.mark.parametrize("variant", ("D", "SDP"))
def test_every_enabled_target_has_positive_step_zero_weight_and_h0_gradient(variant):
    schedule = PositivePiecewiseJoint.from_dict(recipe_dict(variant))
    selected = schedule.policy_at_update(Phase1LossPolicy(), 0)
    outputs, result = _result(_model(), _batch(), variant, policy=selected.policy)
    expected = {task for group in selected.effective_group_coefficients for task in GROUP_TASKS[group]}
    assert set(result.raw) == expected and result.missing_tasks == ()
    for name in expected:
        assert result.counts[name] > 0 and result.task_weights[name] > 0.
        gradient = torch.autograd.grad(result.weighted[name], outputs.atom_repr, retain_graph=True)[0]
        assert torch.isfinite(gradient).all() and bool(gradient.abs().sum() > 0), name


def test_missing_labels_keep_fixed_denominator_and_head_has_no_optimizer_drift():
    selected = PositivePiecewiseJoint.from_dict(recipe_dict()).policy_at_update(Phase1LossPolicy(), 0)
    batch, model = _batch(), _model()
    batch.energy_mask.zero_()
    before = {name: parameter.detach().clone() for name, parameter in model.energy_head.named_parameters()}
    optimizer = build_adamw(model, lr=1e-3, weight_decay=.1)
    optimizer.zero_grad(set_to_none=True)
    _, result = _result(model, batch, "SDP", policy=selected.policy)
    assert result.counts["energy"] == 0 and "energy" in result.missing_tasks
    assert result.counts["charge"] > 0
    assert result.task_weights["energy"] == result.task_weights["charge"] == pytest.approx(.125)
    assert result.raw["energy"].item() == 0. and not result.raw["energy"].requires_grad
    result.total.backward()
    assert all(parameter.grad is None for parameter in model.energy_head.parameters())
    optimizer.step()
    for name, parameter in model.energy_head.named_parameters():
        torch.testing.assert_close(parameter, before[name], rtol=0, atol=0)


def test_disabled_heads_have_no_gradient_or_weight_decay_update():
    selected = PositivePiecewiseJoint.from_dict(recipe_dict("SD")).policy_at_update(Phase1LossPolicy(), 0)
    model = _model()
    heads = {"energy": model.energy_head, "charge": model.charge_head}
    before = {key: {name: parameter.detach().clone() for name, parameter in head.named_parameters()}
              for key, head in heads.items()}
    optimizer = build_adamw(model, lr=1e-3, weight_decay=.1)
    optimizer.zero_grad(set_to_none=True)
    _, result = _result(model, _batch(), "SD", policy=selected.policy)
    assert "energy" not in result.raw and "charge" not in result.raw
    result.total.backward()
    optimizer.step()
    for key, head in heads.items():
        for name, parameter in head.named_parameters():
            assert parameter.grad is None
            torch.testing.assert_close(parameter, before[key][name], rtol=0, atol=0)


@pytest.mark.parametrize("u", (-1, 6, 7, 0., True, "0"))
def test_update_index_is_actual_integer_within_frozen_budget(u):
    with pytest.raises(ValueError, match="actual optimizer update"):
        PositivePiecewiseJoint.from_dict(recipe_dict()).policy_at_update(Phase1LossPolicy(), u)


@pytest.mark.parametrize("problem", ("none", "zero_budget", "bool_budget", "missing_group", "extra_group",
                                    "zero_weight", "negative_weight", "nan_weight", "inf_weight", "bool_weight",
                                    "string_weight", "empty", "nonincreasing", "incomplete", "past_budget",
                                    "bool_end", "wrong_index", "wrong_name", "extra_field", "extra_stage_field"))
def test_invalid_or_zero_supervision_recipe_is_rejected(problem):
    values = recipe_dict()
    if problem == "none":
        values["variant"] = "none"
    elif problem in ("zero_budget", "bool_budget"):
        values["max_updates"] = 0 if problem == "zero_budget" else True
    elif problem == "missing_group":
        values["stages"][0]["group_weight_multipliers"].pop("D")
    elif problem == "extra_group":
        values["stages"][0]["group_weight_multipliers"]["other"] = 1.
    elif problem.endswith("weight"):
        values["stages"][0]["group_weight_multipliers"]["D"] = {
            "zero_weight": 0., "negative_weight": -1., "nan_weight": float("nan"),
            "inf_weight": float("inf"), "bool_weight": True, "string_weight": "1"}[problem]
    elif problem == "empty":
        values["stages"] = []
    elif problem == "nonincreasing":
        values["stages"][1]["end_update_exclusive"] = 2
    elif problem == "incomplete":
        values["stages"][-1]["end_update_exclusive"] = 5
    elif problem == "past_budget":
        values["stages"][-1]["end_update_exclusive"] = 7
    elif problem == "bool_end":
        values["stages"][0]["end_update_exclusive"] = True
    elif problem == "wrong_index":
        values["index_unit"] = "structure_exposure"
    elif problem == "wrong_name":
        values["name"] = "staged"
    elif problem == "extra_field":
        values["mutable_cursor"] = 0
    else:
        values["stages"][0]["active_groups"] = ["S"]
    with pytest.raises(ValueError):
        PositivePiecewiseJoint.from_dict(values)


def test_legacy_variant_canonicalization_and_direct_constructor_defensive_copy():
    stage_values = {"S": 2., "D": 1., "P": 1.}
    stages = [PositiveWeightStage(1, stage_values)]
    schedule = PositivePiecewiseJoint("SPD", 1, stages)
    stage_values["D"] = 0.
    stages.clear()
    assert schedule.variant == "SDP" and len(schedule.stages) == 1
    assert schedule.policy_at_update(Phase1LossPolicy(), 0).effective_group_coefficients["D"] == pytest.approx(.25)


def test_arithmetic_cannot_silently_turn_positive_weights_into_zero_or_infinity():
    schedule = PositivePiecewiseJoint.from_dict(recipe_dict())
    for base in (Phase1LossPolicy.from_mapping({"group_weights": {"S": 1e308}}),
                 Phase1LossPolicy.from_mapping({"task_weights": {"energy": 1e308, "charge": 1e308}}),
                 Phase1LossPolicy.from_mapping({"group_weights": {"S": 5e-324, "D": 5e-324, "P": 5e-324}})):
        with pytest.raises(ValueError):
            schedule.policy_at_update(base, 0)
    values = recipe_dict()
    values["stages"][0]["group_weight_multipliers"]["D"] = 1e-300
    with pytest.raises(ValueError):
        PositivePiecewiseJoint.from_dict(values).policy_at_update(
            Phase1LossPolicy.from_mapping({"group_weights": {"D": 1e-300}}), 0)
    values["stages"][0]["group_weight_multipliers"]["D"] = 1e-100
    with pytest.raises(ValueError, match="positive in the float32 loss"):
        PositivePiecewiseJoint.from_dict(values).policy_at_update(Phase1LossPolicy(), 0)


@pytest.mark.parametrize("change", ("missing_group", "extra_group", "missing_task", "zero_task"))
def test_caller_mutation_cannot_bypass_base_policy_validation(change):
    base = Phase1LossPolicy()
    if change == "missing_group":
        base.group_weights.pop("D")
    elif change == "extra_group":
        base.group_weights["other"] = 1.
    elif change == "missing_task":
        base.task_weights.pop("energy")
    else:
        base.task_weights["energy"] = 0.
    with pytest.raises(ValueError):
        PositivePiecewiseJoint.from_dict(recipe_dict()).policy_at_update(base, 0)
