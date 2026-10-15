"""Independent synthetic gradient/EMA oracles; no data files or GPU execution."""
from copy import deepcopy
import hashlib
import json
import math

import pytest
import torch

from phychem_mfm.phase1.dynamic_loss import (
    DynamicLossConfig, DynamicLossError, EMAGradientBalancer,
)
from phychem_mfm.phase1.objectives import GROUP_TASKS, Phase1LossPolicy
from phychem_mfm.training.losses import LossResult


def _config(**changes):
    values = dict(calibration_observations=1, scale_beta=0., gradient_beta=0., weight_beta=0.,
                  balance_interval=1, scale_floor=1., scale_ceiling=1., gradient_floor=1e-12,
                  min_multiplier=.1, max_multiplier=10.)
    values.update(changes)
    return DynamicLossConfig(**values)


def _controller(variant="P", *, names=("shared.h0",), config=None, policy=None):
    return EMAGradientBalancer(variant, names, config=config or _config(), base_policy=policy)


def _loss(h0, values, *, variant="P", counts=None):
    names = [name for group in GROUP_TASKS if group in variant for name in GROUP_TASKS[group]]
    raw = {name: values.get(name, h0.new_zeros(())) for name in names}
    counts = {name: (counts[name] if counts and name in counts else int(name in values)) for name in names}
    total = torch.stack(list(raw.values())).sum()
    return LossResult(total=total, selection=total, raw=raw, counts=counts)


def _pair(h0, e=1., q=1., ge=1., gq=9.):
    return _loss(h0, {"energy": e + ge*h0[0], "charge": q + gq*h0[1]})


def _reseal(payload):
    payload["state_sha256"] = hashlib.sha256(json.dumps(
        {key: value for key, value in payload.items() if key != "state_sha256"},
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return payload


def _fixed_sums(controller, state=None):
    state = controller.state_dict() if state is None else state
    for group in controller.groups:
        base = controller.base_policy.task_weights
        assert sum(base[name]*state["task_state"][name]["multiplier"] for name in GROUP_TASKS[group]) == pytest.approx(
            sum(base[name] for name in GROUP_TASKS[group]), rel=1e-12, abs=1e-12)
    base = controller.base_policy.group_weights
    assert sum(base[group]*state["group_state"][group]["multiplier"] for group in controller.groups) == pytest.approx(
        sum(base[group] for group in controller.groups), rel=1e-12, abs=1e-12)


def test_equal_loss_different_gradients_hand_oracle_is_not_inverse_loss_weighting():
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller()
    result = controller.balance(_pair(h0), (h0,), update=0)
    # Raw losses are both one, yet derivatives are independent vectors (1,0)/(0,9).
    # Geometric targets + fixed-sum projection give multipliers 1.8/0.2.
    assert result.metrics["tasks"]["energy"]["raw_loss"] == result.metrics["tasks"]["charge"]["raw_loss"] == 1.
    assert result.metrics["tasks"]["energy"]["multiplier"] == pytest.approx(1.8)
    assert result.metrics["tasks"]["charge"]["multiplier"] == pytest.approx(.2)
    assert result.coefficients == pytest.approx({"energy": .9, "charge": .1})
    assert result.metrics["measured_raw_gradient_norms"] == pytest.approx({"energy": 1., "charge": 9.})
    assert result.metrics["measured_fixed_task_gradient_norms"] == pytest.approx({"energy": .5, "charge": 4.5})
    assert result.metrics["measured_weighted_gradient_norms"] == pytest.approx({"energy": .9, "charge": .9})
    assert result.metrics["measured_total_gradient_norm"] == pytest.approx(.9*math.sqrt(2))
    result.total.backward()
    torch.testing.assert_close(h0.grad, torch.tensor([.9, .9]))
    _fixed_sums(controller)


def test_group_vector_balancing_has_independent_hand_oracle_and_complete_task_denominators():
    h0 = torch.nn.Parameter(torch.zeros(2))
    values = {name: 1+h0[0] for name in GROUP_TASKS["S"]}
    values.update({name: 1+9*h0[1] for name in GROUP_TASKS["P"]})
    controller = _controller("SP")
    result = controller.balance(_loss(h0, values, variant="SP"), (h0,), update=0)
    assert result.metrics["denominators"] == {"groups": 2., "tasks": {"S": 3., "P": 2.}}
    assert result.metrics["group_multipliers"] == pytest.approx({"S": 1.8, "P": .2})
    assert all(result.metrics["tasks"][name]["multiplier"] == pytest.approx(1.) for name in values)
    assert [result.coefficients[name] for name in GROUP_TASKS["S"]] == pytest.approx([.3]*3)
    assert [result.coefficients[name] for name in GROUP_TASKS["P"]] == pytest.approx([.05]*2)
    assert result.metrics["measured_group_gradient_norms"] == pytest.approx({"S": .9, "P": .9})
    gradient = torch.autograd.grad(result.total, h0)[0]
    torch.testing.assert_close(gradient, torch.tensor([.9, .9]))
    _fixed_sums(controller)


def test_declared_bounds_can_prevent_equalization_and_never_claim_to_remove_conflict():
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller(config=_config(min_multiplier=.25, max_multiplier=4.))
    result = controller.balance(_pair(h0, gq=100.), (h0,), update=0)
    assert result.metrics["tasks"]["energy"]["multiplier"] == pytest.approx(1.75)
    assert result.metrics["tasks"]["charge"]["multiplier"] == pytest.approx(.25)
    contributions = result.metrics["measured_weighted_gradient_norms"]
    assert contributions == pytest.approx({"energy": .875, "charge": 12.5})
    assert contributions["charge"] > contributions["energy"]
    _fixed_sums(controller)


def test_roundoff_at_saturated_projection_boundary_preserves_frozen_missing_task_and_returns():
    h0 = torch.nn.Parameter(torch.zeros(2))
    base = Phase1LossPolicy()
    base.task_weights.update(energy=1., charge=28.)
    controller = _controller(policy=base, config=_config(min_multiplier=.25, max_multiplier=4.))
    controller.balance(_pair(h0, gq=1.), (h0,), update=0)
    payload = controller.state_dict()
    payload["task_state"]["energy"]["multiplier"] = 4.
    payload["task_state"]["charge"]["multiplier"] = 25/28
    controller.load_state_dict(_reseal(payload))
    missing_before = deepcopy(controller.task_state["charge"])
    # 29 - 28*(25/28) is slightly >4 in binary64; an accepted fixed-sum state
    # must not make the clipped projector search forever for an impossible >4.
    result = controller.balance(_loss(h0, {"energy": 1+h0[0]}), (h0,), update=1)
    assert result.metrics["tasks"]["energy"]["multiplier"] == pytest.approx(4.)
    assert controller.task_state["charge"] == missing_before
    assert result.metrics["denominators"]["tasks"]["P"] == 29.
    assert controller.next_update == 2
    _fixed_sums(controller)


def test_actual_total_and_group_norms_use_vector_sum_not_sum_of_task_norms():
    h0 = torch.nn.Parameter(torch.zeros(1))
    controller = _controller()
    result = controller.balance(_loss(h0, {"energy": 1+h0[0], "charge": 1-h0[0]}), (h0,), update=0)
    assert result.metrics["measured_weighted_gradient_norms"] == pytest.approx({"energy": .5, "charge": .5})
    assert result.metrics["measured_group_gradient_norms"] == {"P": 0.}
    assert result.metrics["measured_total_gradient_norm"] == 0.
    assert result.metrics["measured_fixed_total_gradient_norm"] == 0.
    result.total.backward()
    assert h0.grad is not None and torch.equal(h0.grad, torch.zeros_like(h0))


def test_finite_zero_shared_gradients_are_legal_and_do_not_explode_inverse_weights():
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller()
    result = controller.balance(_pair(h0, ge=0., gq=0.), (h0,), update=0)
    assert result.metrics["measured_total_gradient_norm"] == 0.
    assert result.metrics["group_multipliers"] == {"P": 1.}
    assert all(row["multiplier"] == 1. for row in result.metrics["tasks"].values())
    result.total.backward()
    assert h0.grad is not None and torch.equal(h0.grad, torch.zeros_like(h0))
    assert controller.next_update == 1


def test_stationary_zero_losses_stay_finite_connected_with_defined_scale_and_no_relative_loss_ratio():
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller()
    result = controller.balance(_loss(h0, {"energy": h0[0]*0, "charge": h0[1]*0}), (h0,), update=0)
    assert result.total.item() == 0. and result.total.requires_grad
    assert result.metrics["measured_total_gradient_norm"] == 0.
    assert all(row["scale"] == 1. and row["relative_loss_ema"] is None for row in result.metrics["tasks"].values())
    result.total.backward()
    assert h0.grad is not None and torch.equal(h0.grad, torch.zeros_like(h0))
    json.dumps(result.metrics, allow_nan=False)


def test_gradient_ema_smoothing_has_hand_calculated_memory_not_current_gradient_equalization():
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller(config=_config(gradient_beta=.5))
    controller.balance(_pair(h0), (h0,), update=0)
    result = controller.balance(_pair(h0, ge=3., gq=3.), (h0,), update=1)
    # Fixed task coefficients 1/2: EMA(.5,1.5)=1; EMA(4.5,1.5)=3.
    assert controller.task_state["energy"]["gradient_ema"] == pytest.approx(1.)
    assert controller.task_state["charge"]["gradient_ema"] == pytest.approx(3.)
    assert result.metrics["tasks"]["energy"]["multiplier"] == pytest.approx(1.5)
    assert result.metrics["tasks"]["charge"]["multiplier"] == pytest.approx(.5)
    assert result.metrics["measured_weighted_gradient_norms"] == pytest.approx({"energy": 2.25, "charge": .75})
    _fixed_sums(controller)


def test_nonuniform_base_weights_use_complete_weight_sums_and_exclude_disabled_group_only():
    h0 = torch.nn.Parameter(torch.zeros(2))
    policy = Phase1LossPolicy()
    policy.group_weights.update(S=2., D=3., P=5.)
    for name, value in zip(GROUP_TASKS["S"], (2., 3., 5.)):
        policy.task_weights[name] = value
    policy.task_weights.update(energy=7., charge=11.)
    controller = _controller("SP", policy=policy, config=_config(min_multiplier=1., max_multiplier=1.))
    values = {"element": 1+h0[0], "charge": 1+h0[1]}
    result = controller.balance(_loss(h0, values, variant="SP"), (h0,), update=0)
    assert result.metrics["denominators"] == {"groups": 7., "tasks": {"S": 10., "P": 18.}}
    assert result.coefficients["element"] == pytest.approx(2/10*2/7)
    assert result.coefficients["charge"] == pytest.approx(11/18*5/7)
    assert result.total.item() == pytest.approx(2/10*2/7+11/18*5/7)
    assert result.metrics["tasks"]["energy"]["valid_labels"] == 0
    _fixed_sums(controller)


def test_observed_loss_scale_calibrates_then_freezes_without_dividing_current_loss_to_one():
    h0 = torch.nn.Parameter(torch.zeros(2))
    config = _config(calibration_observations=2, scale_beta=.5, scale_floor=1e-6,
                     scale_ceiling=1e6, min_multiplier=1., max_multiplier=1.)
    controller = _controller(config=config)
    first = controller.balance(_pair(h0, e=1., q=4., gq=1.), (h0,), update=0)
    assert first.metrics["tasks"]["energy"]["scale"] == 1.
    second = controller.balance(_pair(h0, e=3., q=4., gq=1.), (h0,), update=1)
    assert second.metrics["tasks"]["energy"]["scale"] == 2.
    assert second.metrics["tasks"]["energy"]["scale_frozen"] is True
    third = controller.balance(_pair(h0, e=100., q=4., gq=1.), (h0,), update=2)
    assert third.metrics["tasks"]["energy"]["scale"] == 2.
    assert third.normalized["energy"].item() == 50.
    assert third.metrics["tasks"]["energy"]["relative_loss_ema"] == 51.
    assert third.coefficients == pytest.approx({"energy": .25, "charge": .125})
    torch.testing.assert_close(torch.autograd.grad(third.total, h0)[0], torch.tensor([.25, .125]))


def test_scale_freeze_counts_observed_training_labels_not_optimizer_updates_or_missing_rows():
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller(config=_config(calibration_observations=2, scale_beta=.5,
                                            scale_floor=1e-6, scale_ceiling=100.))
    controller.balance(_pair(h0, e=2., q=1., ge=1., gq=1.), (h0,), update=0)
    before = deepcopy(controller.task_state["energy"])
    for update in (1, 2):
        controller.balance(_loss(h0, {"charge": 1+h0[1]}), (h0,), update=update)
        assert controller.task_state["energy"] == before
    result = controller.balance(_pair(h0, e=6., q=1., ge=1., gq=1.), (h0,), update=3)
    assert result.metrics["tasks"]["energy"]["observations"] == 2
    assert result.metrics["tasks"]["energy"]["scale"] == 4.
    assert result.metrics["tasks"]["energy"]["scale_frozen"] is True


def test_missing_task_keeps_detached_zero_full_denominator_and_entire_prior_task_state():
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller()
    controller.balance(_pair(h0), (h0,), update=0)
    before = deepcopy(controller.task_state["energy"])
    raw = _loss(h0, {"charge": 4+9*h0[1]})
    result = controller.balance(raw, (h0,), update=1)
    assert controller.task_state["energy"] == before
    assert result.metrics["denominators"]["tasks"]["P"] == 2.
    assert not result.normalized["energy"].requires_grad and result.normalized["energy"].item() == 0.
    assert not result.weighted["energy"].requires_grad and result.weighted["energy"].item() == 0.
    assert result.metrics["tasks"]["charge"]["multiplier"] == pytest.approx(.2)
    assert result.total.item() == pytest.approx(.4)
    torch.testing.assert_close(torch.autograd.grad(result.total, h0)[0], torch.tensor([0., .9]))
    _fixed_sums(controller)


def test_unobserved_descriptor_group_and_tasks_are_not_removed_from_enabled_hierarchy():
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller("DP")
    before = controller.state_dict()
    result = controller.balance(_loss(h0, {"energy": 1+h0[0], "charge": 1+h0[1]}, variant="DP"), (h0,), update=0)
    after = controller.state_dict()
    for name in GROUP_TASKS["D"]:
        assert after["task_state"][name] == before["task_state"][name]
        assert result.metrics["tasks"][name]["valid_labels"] == 0
    assert after["group_state"]["D"] == before["group_state"]["D"]
    assert result.metrics["denominators"]["groups"] == 2.
    assert result.metrics["denominators"]["tasks"]["D"] == len(GROUP_TASKS["D"])
    assert result.total.item() == pytest.approx(.5)
    _fixed_sums(controller)


def test_nonprobe_updates_do_not_measure_gradients_or_change_gradient_ema_and_weights(monkeypatch):
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller(config=_config(balance_interval=4))
    controller.balance(_pair(h0), (h0,), update=0)
    before = controller.state_dict()
    def forbidden(*args, **kwargs):
        raise AssertionError("Nonprobe update must not call autograd.grad")
    monkeypatch.setattr(torch.autograd, "grad", forbidden)
    result = controller.balance(_pair(h0, e=2., q=2.), (h0,), update=1)
    assert result.metrics["probe_performed"] is False
    assert all(value is None for key, value in result.metrics.items() if key.startswith("measured_"))
    for name in controller.tasks:
        for key in ("gradient_ema", "multiplier", "last_probe_update"):
            assert controller.task_state[name][key] == before["task_state"][name][key]
    assert controller.group_state == before["group_state"]
    result.total.backward()
    assert h0.grad is not None


def test_probe_preserves_existing_grad_buffers_none_grad_and_caller_torch_rng():
    h0 = torch.nn.Parameter(torch.zeros(2))
    unused = torch.nn.Parameter(torch.ones(3))
    h0.grad = torch.tensor([11., 13.])
    grad_object = h0.grad
    grad_before = h0.grad.clone()
    rng = torch.get_rng_state().clone()
    controller = _controller(names=("shared.h0", "shared.unused"))
    result = controller.balance(_pair(h0), (h0, unused), update=0)
    assert h0.grad is grad_object and torch.equal(h0.grad, grad_before)
    assert unused.grad is None and torch.equal(torch.get_rng_state(), rng)
    assert result.metrics["shared_probe_numel"] == 5
    assert all(type(row["coefficient"]) is float for row in result.metrics["tasks"].values())
    json.dumps(result.metrics, allow_nan=False)


def test_same_controller_checkpoint_rebuilds_exact_ema_weights_and_following_gradient():
    h0 = torch.nn.Parameter(torch.zeros(2))
    config = _config(calibration_observations=2, scale_beta=.5, gradient_beta=.5,
                     weight_beta=.5, scale_floor=1e-6, scale_ceiling=100., balance_interval=3)
    first, restored = _controller(config=config), _controller(config=config)
    first.balance(_pair(h0, e=1., q=4.), (h0,), update=0)
    first.balance(_pair(h0, e=3., q=8.), (h0,), update=1)
    payload = json.loads(json.dumps(first.state_dict(), allow_nan=False))
    original_payload = deepcopy(payload)
    restored.load_state_dict(payload)
    assert restored.state_dict() == first.state_dict() and payload == original_payload
    for update in (2, 3, 4):
        a = first.balance(_pair(h0, e=5., q=10.), (h0,), update=update)
        b = restored.balance(_pair(h0, e=5., q=10.), (h0,), update=update)
        torch.testing.assert_close(a.total, b.total, rtol=0, atol=0)
        assert a.coefficients == b.coefficients and a.metrics == b.metrics
        torch.testing.assert_close(torch.autograd.grad(a.total, h0)[0], torch.autograd.grad(b.total, h0)[0], rtol=0, atol=0)
        assert restored.state_dict() == first.state_dict()
    assert payload == original_payload


def test_state_and_base_policy_are_owned_copies_not_mutable_caller_aliases():
    policy = Phase1LossPolicy()
    controller = _controller(policy=policy)
    original = controller.state_dict()
    policy.group_weights["P"] = 100.
    policy.task_weights["energy"] = 100.
    assert controller.state_dict() == original
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller.balance(_pair(h0), (h0,), update=0)
    payload = controller.state_dict()
    other = _controller()
    other.load_state_dict(payload)
    actual = other.state_dict()
    payload["task_state"]["energy"]["scale"] = 99.
    assert other.state_dict() == actual
    exported = other.state_dict()
    exported["group_state"]["P"]["multiplier"] = 9.
    assert other.state_dict() == actual


@pytest.mark.parametrize("mutation", ("missing_task", "missing_group", "cursor_rewind", "observation_overrun",
    "future_observation", "unscheduled_probe", "freeze_drift", "scale_negative", "task_sum_drift",
    "group_sum_drift", "base_drift", "names_drift", "config_drift"))
def test_resealed_checkpoint_semantic_tampering_rejects_atomically(mutation):
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller(config=_config(balance_interval=4))
    controller.balance(_pair(h0), (h0,), update=0)
    controller.balance(_pair(h0), (h0,), update=1)
    before = controller.state_dict()
    payload = deepcopy(before)
    row = payload["task_state"]["energy"]
    if mutation == "missing_task": del payload["task_state"]["charge"]
    elif mutation == "missing_group": del payload["group_state"]["P"]
    elif mutation == "cursor_rewind": payload["next_update"] = 0
    elif mutation == "observation_overrun": row["observations"] = 3
    elif mutation == "future_observation": row["last_observed_update"] = 2
    elif mutation == "unscheduled_probe": row["last_probe_update"] = 1
    elif mutation == "freeze_drift": row["scale_frozen"] = False
    elif mutation == "scale_negative": row["scale"] = -1.
    elif mutation == "task_sum_drift": row["multiplier"] = .5
    elif mutation == "group_sum_drift": payload["group_state"]["P"]["multiplier"] = 2.
    elif mutation == "base_drift": payload["base_policy"]["task_weights"]["energy"] = 2.
    elif mutation == "names_drift": payload["shared_parameter_names"] = ["other.h0"]
    elif mutation == "config_drift": payload["config"]["gradient_beta"] = .5
    _reseal(payload)
    rng = torch.get_rng_state().clone()
    with pytest.raises(DynamicLossError):
        controller.load_state_dict(payload)
    assert controller.state_dict() == before and torch.equal(torch.get_rng_state(), rng)


def test_checkpoint_bad_seal_and_nonfinite_json_fail_without_any_partial_assignment():
    controller = _controller()
    before = controller.state_dict()
    for bad in ("seal", "nonfinite"):
        payload = deepcopy(before)
        if bad == "seal": payload["state_sha256"] = "0"*64
        else: payload["task_state"]["energy"]["scale"] = float("nan")
        with pytest.raises(DynamicLossError):
            controller.load_state_dict(payload)
        assert controller.state_dict() == before


@pytest.mark.parametrize("case", ("all_missing", "missing_connected", "missing_nonzero", "observed_detached",
    "observed_unconnected", "nan_loss", "vector_loss", "bool_count", "negative_count", "missing_raw", "extra_raw"))
def test_invalid_training_loss_rejects_before_controller_state_or_existing_grads_change(case):
    h0 = torch.nn.Parameter(torch.zeros(2))
    h0.grad = torch.tensor([3., 5.])
    controller = _controller()
    result = _pair(h0)
    if case == "all_missing": result = _loss(h0, {})
    elif case == "missing_connected": result.counts["energy"] = 0; result.raw["energy"] = h0[0]*0
    elif case == "missing_nonzero": result.counts["energy"] = 0; result.raw["energy"] = h0.new_tensor(1.)
    elif case == "observed_detached": result.raw["energy"] = result.raw["energy"].detach()
    elif case == "observed_unconnected": result.raw["energy"] = torch.nn.Parameter(torch.tensor(1.))*2
    elif case == "nan_loss": result.raw["energy"] = h0[0]+float("nan")
    elif case == "vector_loss": result.raw["energy"] = h0+1
    elif case == "bool_count": result.counts["energy"] = True
    elif case == "negative_count": result.counts["energy"] = -1
    elif case == "missing_raw": del result.raw["energy"]
    elif case == "extra_raw": result.raw["not_declared"] = h0[0]+1
    before, grad = controller.state_dict(), h0.grad.clone()
    with pytest.raises(DynamicLossError):
        controller.balance(result, (h0,), update=0)
    assert controller.state_dict() == before and torch.equal(h0.grad, grad)


@pytest.mark.parametrize("update", (True, -1, 1, 1.5))
def test_optimizer_update_cursor_cannot_skip_replay_or_accept_bool(update):
    h0 = torch.nn.Parameter(torch.zeros(2))
    controller = _controller()
    before = controller.state_dict()
    with pytest.raises(DynamicLossError):
        controller.balance(_pair(h0), (h0,), update=update)
    assert controller.state_dict() == before
    controller.balance(_pair(h0), (h0,), update=0)
    after = controller.state_dict()
    with pytest.raises(DynamicLossError):
        controller.balance(_pair(h0), (h0,), update=0)
    assert controller.state_dict() == after


@pytest.mark.parametrize("changes", ({"calibration_observations": True}, {"calibration_observations": 0},
    {"balance_interval": 0}, {"scale_beta": 1.}, {"gradient_beta": -1.}, {"weight_beta": float("nan")},
    {"scale_floor": 0.}, {"scale_floor": 2., "scale_ceiling": 1.}, {"min_multiplier": 2.}, {"max_multiplier": .5}))
def test_invalid_bounded_config_rejects(changes):
    with pytest.raises(DynamicLossError):
        _config(**changes)


def test_effective_positive_weight_cannot_silently_underflow_to_zero_in_actual_float32_loss():
    h0 = torch.nn.Parameter(torch.zeros(2, dtype=torch.float32))
    base = Phase1LossPolicy()
    base.task_weights["energy"] = 5e-324
    controller = _controller(policy=base)
    before = controller.state_dict()
    with pytest.raises(DynamicLossError):
        controller.balance(_pair(h0, gq=1.), (h0,), update=0)
    assert controller.state_dict() == before


def test_real_shared_backbone_all_enabled_tasks_produce_a_backwardable_balanced_gradient():
    from test_phase1_training import _model, _batch, _result
    with torch.random.fork_rng(devices=[]):
        model, batch = _model(), _batch()
        _, raw = _result(model, batch, "SDP")
        names, parameters = zip(*model.backbone.named_parameters())
        controller = _controller("SDP", names=tuple("backbone."+name for name in names),
                                 config=_config(min_multiplier=.25, max_multiplier=4.))
        rng = torch.get_rng_state().clone()
        result = controller.balance(raw, tuple(parameters), update=0)
        assert torch.equal(torch.get_rng_state(), rng)
        assert all(parameter.grad is None for parameter in model.parameters())
        actual = torch.autograd.grad(result.total, tuple(parameters), retain_graph=True, allow_unused=True)
        norm = math.sqrt(sum(float(value.detach().double().square().sum()) for value in actual if value is not None))
        assert result.metrics["measured_total_gradient_norm"] == pytest.approx(norm, rel=1e-6)
        result.total.backward()
        assert all(parameter.grad is None or torch.isfinite(parameter.grad).all() for parameter in model.parameters())
        assert any(parameter.grad is not None and parameter.grad.abs().sum() > 0 for parameter in parameters)
        assert set(result.coefficients) == {name for tasks in GROUP_TASKS.values() for name in tasks}
        assert all(value > 0 and math.isfinite(value) for value in result.coefficients.values())
        _fixed_sums(controller)
