"""Independent integral, true-gradient, and genuine tiny-trainer draft oracles.

These synthetic tests require the actual Stage50 test fixtures and an immutable
52c reference trainer file. They have not been executed by this draft author.
"""
from copy import deepcopy
from fractions import Fraction
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
import torch

from test_phase1_full_corpus_training import fixture, OfflineSpy, assert_same_tree
from phychem_mfm.phase1.downstream_training import checkpoint_content_sha256
from phychem_mfm.phase1.dynamic_loss import DynamicLossConfig, EMAGradientBalancer
from phychem_mfm.phase1.full_corpus_training import FullCorpusTrainer, FullCorpusTrainingError
from phychem_mfm.phase1.objectives import GROUP_TASKS, PHASE1_VARIANTS
from phychem_mfm.phase1.positive_strategy import (
    JOINT, POSITIVE, PositiveExposureStrategy, PositiveStrategyError, strategy_from_protocol)
from phychem_mfm.training.losses import LossResult


def _strategy(n=10, variant="SDP", name=POSITIVE):
    return PositiveExposureStrategy(name, variant, n)


def _protocol(n=5):
    return {"state": "frozen", "variants": list(PHASE1_VARIANTS), "seeds": [0, 1, 2],
            "strategies": {
                JOINT: {"variants": list(PHASE1_VARIANTS), "seeds": [0, 1, 2],
                        "config": _strategy(n, "SDP", JOINT).config_dict()},
                POSITIVE: {"variants": ["SDP"], "seeds": [0, 1, 2],
                           "config": _strategy(n).config_dict()}}}


@pytest.mark.parametrize("n", (1, 2, 3, 5, 10, 11))
def test_nominal_odd_even_fullpass_equal_integrals_and_positive_segments(n):
    recipe = _strategy(n).recipe_dict()
    early, late = n // 2, n - n // 2
    # Independent rational arithmetic, including the one-record/zero-early case.
    first = (Fraction(3, 2), Fraction(3, 4), Fraction(3, 4))
    last = tuple((n - early * value) / late for value in first)
    assert sum(first) == sum(last) == 3
    for group, a, b in zip(("S", "D", "P"), first, last):
        assert a > 0 and b > 0 and early * a + late * b == n
        assert recipe["early_nominal_factors"][group] == pytest.approx(float(a))
        assert recipe["late_nominal_factors"][group] == pytest.approx(float(b))


def test_crossing_batch_normalizes_each_side_before_actual_exposure_integral():
    result = _strategy().factors(4, 4, {"S": 2., "D": .5, "P": .5})
    # One early record: outer=(6/5,3/5,3/5); three late: (2/3,5/3,5/3).
    expected = {"S": float(Fraction(4, 5)), "D": float(Fraction(7, 5)), "P": float(Fraction(7, 5))}
    assert result["early_base_records"] == 1 and result["late_base_records"] == 3
    assert result["phase"] == "crossing" and result["effective_outer_factors"] == pytest.approx(expected)
    assert 2 * expected["S"] + .5 * expected["D"] + .5 * expected["P"] == pytest.approx(3.)
    # Averaging nominal factors first would yield 6/7 and 9/7: a different algorithm.
    assert expected["S"] != pytest.approx(float(Fraction(6, 7)))


def test_true_postscheduled_gradient_and_group_norms_are_not_a_sum_of_norms():
    h0 = torch.nn.Parameter(torch.zeros(3))
    names = tuple(name for group in GROUP_TASKS.values() for name in group)
    weighted = {name: h0.new_zeros(()) for name in names}
    weighted[GROUP_TASKS["S"][0]], weighted[GROUP_TASKS["D"][0]], weighted["energy"] = h0[0], 2*h0[1], 3*h0[2]
    balanced = SimpleNamespace(total=torch.stack(tuple(weighted.values())).sum(), weighted=weighted,
                              coefficients={name: .1 for name in names},
                              metrics={"measured_group_gradient_norms": {"S": 1., "D": 2., "P": 3.}})
    result = _strategy().apply(balanced, start=0, count=2, group_budget={"S": 1., "D": 1., "P": 1.})
    gradient, = torch.autograd.grad(result.total, (h0,))
    assert torch.equal(gradient, torch.tensor([1.5, 1.5, 2.25]))
    assert result.metrics["measured_postscheduled_group_gradient_norms"] == {"S": 1.5, "D": 1.5, "P": 2.25}
    assert float(gradient.norm()) == pytest.approx(math.sqrt(9.5625))
    assert float(gradient.norm()) != pytest.approx(5.25)
    assert result.metrics["measured_postscheduled_shared_total_gradient_norm"] is None
    assert result.coefficients["energy"] == pytest.approx(.075)


def test_missing_group_stays_in_budget_and_unscheduled_controller_state_is_not_changed_by_apply():
    h0 = torch.nn.Parameter(torch.zeros(2))
    names = tuple(name for group in GROUP_TASKS.values() for name in group)
    raw = {name: h0.new_zeros(()) for name in names}
    raw["element"], raw["energy"] = 1 + h0[0], 1 + h0[1]
    counts = {name: int(name in ("element", "energy")) for name in names}
    loss = LossResult(total=torch.stack(tuple(raw.values())).sum(), selection=h0.sum(), raw=raw, counts=counts)
    controller = EMAGradientBalancer("SDP", ("h0",), config=DynamicLossConfig(
        calibration_observations=1, scale_floor=1., scale_ceiling=1., weight_beta=0.))
    balanced = controller.balance(loss, (h0,), update=0)
    before, grad, rng = deepcopy(controller.state_dict()), h0.grad, torch.get_rng_state().clone()
    result = _strategy().apply(balanced, start=0, count=2,
                  group_budget=balanced.metrics["group_multipliers"].copy())
    assert result.metrics["complete_group_budget"].keys() == {"S", "D", "P"}
    assert all(result.weighted[name].item() == 0 for name in GROUP_TASKS["D"])
    assert controller.state_dict() == before and h0.grad is grad and torch.equal(torch.get_rng_state(), rng)
    assert all(before["task_state"][name]["observations"] == 0 for name in GROUP_TASKS["D"])


@pytest.mark.parametrize("variant", PHASE1_VARIANTS)
def test_joint_returns_original_objective_and_leaf_objects_without_tensor_recomputation(variant):
    total = torch.tensor(3., requires_grad=True)
    weighted, coefficients = {"sentinel": total}, {"sentinel": 1.}
    balanced = SimpleNamespace(total=total, weighted=weighted, coefficients=coefficients)
    strategy = _strategy(5, variant, JOINT)
    result = strategy.apply(balanced, start=1, count=2, group_budget={g: .5 for g in strategy.groups})
    assert result.total is total and result.weighted is weighted and result.coefficients is coefficients


@pytest.mark.parametrize("change", ("variant", "none", "seed", "recipe", "horizon", "source", "other_horizon", "typed_recipe"))
def test_frozen_strategy_allowlist_recipe_source_and_actual_length_reject_drift(change):
    protocol, variant, seed, actual_n = _protocol(), "SDP", 0, 5
    if change == "variant": variant = "SD"
    elif change == "none": variant = "none"
    elif change == "seed": seed = 3
    elif change == "horizon": actual_n = 6
    elif change == "other_horizon": protocol["strategies"][JOINT]["config"] = _strategy(6, "SDP", JOINT).config_dict()
    elif change == "source": protocol["strategies"][POSITIVE]["config"]["implementation_sha256"] = "0" * 64
    elif change == "typed_recipe":
        # False == 0 in Python, but cannot inherit a typed canonical recipe seal.
        protocol["strategies"][POSITIVE]["config"]["recipe"]["missing_groups_removed_from_denominator"] = 0
    else:
        protocol["strategies"][POSITIVE]["config"]["recipe"]["early_nominal_factors"]["S"] = 0.
    with pytest.raises(PositiveStrategyError):
            strategy_from_protocol(protocol, POSITIVE, variant, seed, total_base_exposures=actual_n)


@pytest.mark.parametrize("variant,seed,name", (("SDP", 0, POSITIVE), ("SDP", 1, POSITIVE),
                                               ("SDP", 2, POSITIVE), ("none", 2, JOINT)))
def test_frozen_declared_paired_auxiliary_seeds_and_none_joint_select_the_exact_recipe(variant, seed, name):
    result = strategy_from_protocol(_protocol(), name, variant, seed, total_base_exposures=5)
    assert result.name == name and result.variant == variant and result.total_base_exposures == 5


@pytest.mark.parametrize("field,subset", (("variants", ["SDP"]), ("seeds", [0])))
def test_joint_rejects_a_subset_allowlist_even_when_the_requested_cell_is_present(field, subset):
    protocol = _protocol()
    protocol["strategies"][JOINT][field] = subset
    # SDP/seed0 remains present in either subset. A membership-only guard would
    # accept it while silently removing the rest of the declared main matrix.
    with pytest.raises(PositiveStrategyError, match="complete ordered main"):
        strategy_from_protocol(protocol, JOINT, "SDP", 0, total_base_exposures=5)


@pytest.mark.parametrize("change", ("missing_budget", "zero_budget", "overflow", "interval", "bool_cursor", "underflow"))
def test_invalid_budgets_intervals_and_actual_dtype_underflow_fail_closed(change):
    strategy, budget, start, count = _strategy(), {"S": 1., "D": 1., "P": 1.}, 0, 2
    if change == "missing_budget": del budget["D"]
    elif change == "zero_budget": budget["P"] = 0.
    elif change == "overflow": budget = {g: 1e308 for g in budget}
    elif change == "interval": start = 9
    elif change == "bool_cursor": start = True
    if change != "underflow":
        with pytest.raises(PositiveStrategyError): strategy.factors(start, count, budget)
    else:
        tensor = torch.tensor(1., dtype=torch.float32, requires_grad=True)
        names = tuple(name for group in GROUP_TASKS.values() for name in group)
        balanced = SimpleNamespace(total=tensor, weighted={n: tensor for n in names},
                   coefficients={n: 1e-100 for n in names}, metrics={})
        with pytest.raises(PositiveStrategyError, match="representable"):
            strategy.apply(balanced, start=start, count=count, group_budget=budget)


def _trainer(tmp_path, *, name, data=None, strategy=POSITIVE):
    base, batches, _, data = fixture(tmp_path, name=name, shared_manifest=data)
    config = deepcopy(base.config)
    config["variant"] = "SDP"
    config["strategy"] = _strategy(len(base.sampler.index), "SDP", strategy).config_dict()
    tracker = OfflineSpy(name)
    trainer = FullCorpusTrainer(base.model, base.sampler, config, tracker=tracker)
    return trainer, batches, tracker, data


def test_real_tiny_sdp_adamw_dropout_restore_is_bitexact_across_actual_exposure_boundary(tmp_path):
    with torch.random.fork_rng(devices=[]):
        reference, batches, _, data = _trainer(tmp_path / "source", name="reference")
        rng = torch.get_rng_state().clone()
        for batch in batches: reference._consume(batch)
        expected_rng = torch.get_rng_state().clone()
        interrupted, same, _, _ = _trainer(tmp_path / "unused", name="interrupted", data=data)
        torch.set_rng_state(rng)
        interrupted._consume(same[0])
        payload = interrupted.checkpoint()
        receiver, _, tracker, _ = _trainer(tmp_path / "unused2", name="receiver", data=data)
        receiver.load_checkpoint(payload, checkpoint_file_sha256="f" * 64)
        for batch in same[1:]: receiver._consume(batch)
        for left, right in ((reference.model.state_dict(), receiver.model.state_dict()),
                            (reference.optimizer.state_dict(), receiver.optimizer.state_dict()),
                            (reference.controller.state_dict(), receiver.controller.state_dict()),
                            (reference.sampler.state_dict(), receiver.sampler.state_dict())):
            assert_same_tree(left, right)
        assert torch.equal(torch.get_rng_state(), expected_rng)
        assert receiver.counters["consumed_base_exposures"] == len(receiver.sampler.index) == 5
        assert tracker.rows[0]["strategy/exposure_start"] == len(same[0].logical_indices)
        assert all(row["strategy/name"] == POSITIVE for row in tracker.rows)


def test_fullzero_batch_consumes_exposure_without_model_decay_controller_or_resampling(tmp_path):
    with torch.random.fork_rng(devices=[]):
        trainer, batches, tracker, _ = _trainer(tmp_path / "source", name="zero")
        state, controller = deepcopy(trainer.model.state_dict()), trainer.controller.state_dict()
        # Explicit detached all-missing LossResult tests the producer's zero-label path.
        def no_observations(batch):
            raw = {name: torch.zeros(()) for name in trainer.enabled_tasks}
            return LossResult(total=torch.zeros(()), selection=torch.zeros(()), raw=raw,
                              counts={name: 0 for name in raw})
        trainer._loss = no_observations
        for batch in batches: trainer._consume(batch)
        assert_same_tree(state, trainer.model.state_dict())
        assert trainer.controller.state_dict() == controller and trainer.optimizer.state_dict()["state"] == {}
        assert trainer.counters["zero_label_batches"] == len(batches)
        assert trainer.sampler.samples_consumed == trainer.counters["consumed_base_exposures"] == 5
        assert tracker.rows[-1]["strategy/exposure_stop"] == 5
        assert tracker.rows[-1]["train/loss_postscheduled"] == 0.


@pytest.mark.parametrize("change", ("main_to_aux", "aux_to_main", "cursor", "recipe_source"))
def test_resealed_restore_strategy_and_cursor_drift_reject_before_live_state_or_rng_changes(tmp_path, change):
    with torch.random.fork_rng(devices=[]):
        old_name = JOINT if change == "main_to_aux" else POSITIVE
        trained, batches, _, data = _trainer(tmp_path / "source", name="trained", strategy=old_name)
        trained._consume(batches[0])
        payload = trained.checkpoint()
        new_name = JOINT if change == "aux_to_main" else POSITIVE
        receiver, _, _, _ = _trainer(tmp_path / "unused", name="receiver", data=data, strategy=new_name)
        if change == "cursor": payload["counters"]["consumed_base_exposures"] += 1
        elif change == "recipe_source": payload["config"]["strategy"]["implementation_sha256"] = "0" * 64
        payload["checkpoint_content_sha256"] = checkpoint_content_sha256(payload)
        model, optimizer, control = deepcopy(receiver.model.state_dict()), deepcopy(receiver.optimizer.state_dict()), receiver.controller.state_dict()
        rng, sampler, counters = torch.get_rng_state().clone(), receiver.sampler.state_dict(), deepcopy(receiver.counters)
        with pytest.raises((FullCorpusTrainingError, ValueError)):
            receiver.load_checkpoint(payload, checkpoint_file_sha256="f" * 64)
        assert_same_tree(model, receiver.model.state_dict())
        assert_same_tree(optimizer, receiver.optimizer.state_dict())
        assert receiver.controller.state_dict() == control and receiver.sampler.state_dict() == sampler
        assert receiver.counters == counters and torch.equal(torch.get_rng_state(), rng)


def test_joint_genuine_adamw_matches_immutable_52c_reference_weights_moments_controller_rng(tmp_path):
    path = Path(os.environ["PHASE1_JOINT_REFERENCE_PATH"])
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == "c1c011fcd9f435802089f814f7a3e2ab096e325ae53aa03e337f5dadc17c0ac1"
    module_name = "phychem_mfm.phase1._stage52_immutable_joint_reference"
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        with torch.random.fork_rng(devices=[]):
            current, batches, _, data = fixture(tmp_path / "source", name="current")
            rng = torch.get_rng_state().clone()
            for batch in batches: current._consume(batch)
            expected_rng = torch.get_rng_state().clone()
            base, same, _, _ = fixture(tmp_path / "unused", name="base", shared_manifest=data)
            reference = module.FullCorpusTrainer(base.model, base.sampler, deepcopy(base.config), tracker=OfflineSpy("reference"))
            torch.set_rng_state(rng)
            for batch in same: reference._consume(batch)
            assert_same_tree(current.model.state_dict(), reference.model.state_dict())
            assert_same_tree(current.optimizer.state_dict(), reference.optimizer.state_dict())
            assert current.controller.state_dict() == reference.controller.state_dict()
            assert current.sampler.state_dict() == reference.sampler.state_dict()
            assert torch.equal(torch.get_rng_state(), expected_rng)
    finally:
        sys.modules.pop(module_name, None)
