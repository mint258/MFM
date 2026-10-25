"""Synthetic consumed-sample, safe-resume and raw-validation tests."""
from copy import deepcopy
from itertools import islice
import math
import random

import numpy as np
import pytest
import torch

from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_losses import compute_v3_loss
from phychem_mfm.phase1.v3_sampling import ConformerRef, InMemorySamplingIndex, MoleculeEntry, UniformMoleculeSampler
from phychem_mfm.phase1.v3_training import (SampleClock, ValidationAccumulator, capture_rng_state,
    commit_consumed_batch, load_checkpoint, save_new_checkpoint, shared_backbone_gradient_norms)


def index():
    return InMemorySamplingIndex(tuple(MoleculeEntry(str(i),
        (ConformerRef(str(i) + "c", 0, 2, (("PM7", str(i)),)),),
        (("S", True), ("D", True), ("P", True)), (("physics", True),)) for i in range(4)), "synthetic-v1")


def bindings():
    return {"code_sha": "a" * 40, "configuration_sha256": "b" * 64,
            "registry_sha256": "c" * 64, "normalization_sha256": "d" * 64, "data_version": "synthetic-v1"}


def assert_tree_equal(first, second):
    if isinstance(first, torch.Tensor):
        assert torch.equal(first, second)
    elif isinstance(first, dict):
        assert set(first) == set(second)
        for key in first:
            assert_tree_equal(first[key], second[key])
    elif isinstance(first, (list, tuple)):
        assert len(first) == len(second)
        for a, b in zip(first, second):
            assert_tree_equal(a, b)
    else:
        assert first == second


def test_sample_clock_uses_consumed_samples_and_splits_named_endpoints():
    clock = SampleClock(64000000)
    assert clock.milestones == (1000000, 2000000, 4000000, 8000000, 16000000, 32000000, 64000000)
    clock.advance(999999)
    assert clock.max_next_samples(500) == 1
    with pytest.raises(ValueError, match="crosses"):
        clock.advance(2)
    clock.advance(1, optimizer_updated=False)
    assert clock.samples_consumed == 1000000 and clock.optimizer_updates == 1
    assert clock.max_next_samples(500) == 500
    with pytest.raises(ValueError, match="clock contract"):
        SampleClock(100).load_state_dict(clock.state_dict())


def test_combined_commit_rejects_invalid_samples_without_moving_either_clock():
    sampler, clock = UniformMoleculeSampler(index(), seed=4, sample_budget=10), SampleClock(10, (3, 6))
    draws = list(islice(sampler, 4))
    with pytest.raises(ValueError, match="boundary"):
        commit_consumed_batch(sampler, clock, draws)
    assert sampler.samples_consumed == clock.samples_consumed == 0
    with pytest.raises(ValueError, match="next committed"):
        commit_consumed_batch(sampler, clock, draws[1:3])
    assert sampler.samples_consumed == clock.samples_consumed == 0
    commit_consumed_batch(sampler, clock, draws[:3])
    assert sampler.samples_consumed == clock.samples_consumed == 3


def build_model():
    return torch.nn.Sequential(torch.nn.Linear(4, 8), torch.nn.SiLU(),
                               torch.nn.Dropout(.3), torch.nn.Linear(8, 1))


def update(model, optimizer, sampler, clock):
    choices = list(islice(sampler, 3))
    base = torch.tensor([[choice.molecule_index, choice.ordinal / 10., 1., .5] for choice in choices])
    # Exercise all three ambient RNGs plus the model's dropout stream.
    x = base + torch.randn_like(base) * .01 + float(np.random.normal()) * .01 + random.random() * .01
    target = x.sum(-1, keepdim=True)
    optimizer.zero_grad(set_to_none=True)
    loss = (model(x) - target).square().mean()
    loss.backward(); optimizer.step()
    commit_consumed_batch(sampler, clock, choices)
    return float(loss.detach()), x.clone()


def test_weights_only_checkpoint_restores_optimizer_rng_and_unconsumed_prefetch_bitwise(tmp_path):
    torch.manual_seed(10); np.random.seed(10); random.seed(10)
    model = build_model()
    optimizer = torch.optim.AdamW(model.parameters(), lr=.01, foreach=False)
    sampler, clock = UniformMoleculeSampler(index(), seed=40, sample_budget=12), SampleClock(12, (3, 6, 9))
    update(model, optimizer, sampler, clock)
    prefetched = list(islice(sampler, 8))
    marker = save_new_checkpoint(tmp_path / "seen3", output_root=tmp_path, model=model,
                                 optimizer=optimizer, sampler=sampler, clock=clock, bindings=bindings(),
                                 extra_state={"validation_pending": False, "field_counts": {"f": 3}})
    assert marker["samples_consumed"] == 3 and clock.saved_milestones == [3]
    assert sampler.samples_consumed == 3
    expected_steps = [update(model, optimizer, sampler, clock) for _ in range(2)]
    expected_model, expected_optimizer = deepcopy(model.state_dict()), deepcopy(optimizer.state_dict())
    expected_rng = capture_rng_state()
    # Fresh initialization and unrelated random use must be fully undone by load.
    restored = build_model()
    restored_optimizer = torch.optim.AdamW(restored.parameters(), lr=.5, foreach=False)
    restored_sampler = UniformMoleculeSampler(index(), seed=40, sample_budget=12)
    restored_clock = SampleClock(12, (3, 6, 9))
    np.random.random(20); random.random(); torch.rand(20)
    extra = load_checkpoint(tmp_path / "seen3", output_root=tmp_path, model=restored,
                            optimizer=restored_optimizer, sampler=restored_sampler, clock=restored_clock,
                            expected_bindings=bindings())
    assert extra == {"validation_pending": False, "field_counts": {"f": 3}}
    assert list(islice(restored_sampler, 8)) == prefetched
    actual_steps = [update(restored, restored_optimizer, restored_sampler, restored_clock) for _ in range(2)]
    for expected, actual in zip(expected_steps, actual_steps):
        assert expected[0] == actual[0]
        assert torch.equal(expected[1], actual[1])
    assert_tree_equal(expected_model, restored.state_dict())
    assert_tree_equal(expected_optimizer, restored_optimizer.state_dict())
    assert_tree_equal(expected_rng, capture_rng_state())
    with pytest.raises(FileExistsError):
        save_new_checkpoint(tmp_path / "seen3", output_root=tmp_path, model=restored,
                            optimizer=restored_optimizer, sampler=restored_sampler, clock=restored_clock,
                            bindings=bindings())


def test_checkpoint_rejects_wrong_bindings_and_incomplete_directory(tmp_path):
    model = torch.nn.Linear(2, 1)
    optimizer = torch.optim.AdamW(model.parameters())
    sampler, clock = UniformMoleculeSampler(index(), seed=4, sample_budget=12), SampleClock(12)
    save_new_checkpoint(tmp_path / "recovery", output_root=tmp_path, model=model, optimizer=optimizer,
                        sampler=sampler, clock=clock, bindings=bindings())
    initial = deepcopy(model.state_dict())
    wrong = {**bindings(), "configuration_sha256": "e" * 64}
    with pytest.raises(ValueError, match="binding"):
        load_checkpoint(tmp_path / "recovery", output_root=tmp_path, model=model, optimizer=optimizer,
                        sampler=sampler, clock=clock, expected_bindings=wrong)
    assert_tree_equal(initial, model.state_dict())
    (tmp_path / "partial").mkdir()
    with pytest.raises(ValueError, match="Incomplete"):
        load_checkpoint(tmp_path / "partial", output_root=tmp_path, model=model, optimizer=optimizer,
                        sampler=sampler, clock=clock, expected_bindings=bindings())


def test_group_gradient_probe_occurs_each_500_updates_without_mutating_parameter_grads():
    parameter = torch.nn.Parameter(torch.tensor([1., 2.]))
    s = parameter.sum().square()
    groups = {"S": s, "D": s * 2, "P": torch.tensor(0.)}
    assert shared_backbone_gradient_norms(groups, (parameter,), optimizer_update=499) == {}
    result = shared_backbone_gradient_norms(groups, (parameter,), optimizer_update=500)
    assert result == pytest.approx({"S": math.sqrt(72), "D": math.sqrt(288), "P": 0.})
    assert parameter.grad is None
    (groups["S"] + groups["D"]).backward()
    assert torch.equal(parameter.grad, torch.tensor([18., 18.]))


def test_two_validation_populations_have_separate_raw_unit_metrics():
    reg = LabelRegistry((FieldSpec("energy", "P", "physics", "graph"),), "fixture", "f" * 64)
    norms = {"energy": TrainNormalization((100.,), (2.,), "a" * 64, "synthetic-v1")}
    prediction = {"energy": torch.tensor([[0.], [2.], [999.]])}
    labels = {"energy": FieldTarget(torch.tensor([[0.], [4.], [float("nan")]]), torch.tensor([True, True, False]))}
    loss = compute_v3_loss(prediction, labels, reg, norms, enabled_groups=("P",))
    val = ValidationAccumulator(reg, role="VAL", enabled_groups=("P",))
    seen = ValidationAccumulator(reg, role="TRAIN_UNSEEN_CONFORMATION", enabled_groups=("P",))
    val.add(prediction, labels, loss)
    row = val.result()["fields"]["energy"]
    assert row["valid_labels"] == 2 and row["MAE"] == pytest.approx(1.)
    assert row["R2"] == pytest.approx(.5)
    assert row["loss"] == pytest.approx(.25)
    assert seen.result()["fields"]["energy"]["valid_labels"] == 0
    with pytest.raises(ValueError, match="validation role"):
        ValidationAccumulator(reg, role="arbitrary_external_role", enabled_groups=("P",))


def test_constant_fields_report_unavailable_r2_instead_of_fabricating_zero():
    reg = LabelRegistry((FieldSpec("a", "D", "physics", "graph"),), "fixture", "a" * 64)
    predictions = {"a": torch.ones(2, 1)}
    targets = {"a": FieldTarget(torch.ones(2, 1), torch.ones(2, dtype=torch.bool))}
    loss = compute_v3_loss(predictions, targets, reg, {"a": TrainNormalization((0.,), (1.,), "b" * 64, "v1")}, enabled_groups=("D",))
    metric = ValidationAccumulator(reg, role="VAL", enabled_groups=("D",))
    metric.add(predictions, targets, loss)
    row = metric.result()["fields"]["a"]
    assert row["R2"] is None and row["MAE"] == 0.
    assert row["R2_unavailable_reason"] == "insufficient_or_constant_labels"
