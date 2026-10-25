"""CPU integration only: injected synthetic adapter and explicit unit tracker."""
from copy import deepcopy
from dataclasses import replace
import random
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from torch_geometric.data import Batch

from test_model_v3_structural import setup_model
from test_model_v3_training import assert_tree_equal
from phychem_mfm.phase1.v3_contract import FieldTarget
from phychem_mfm.phase1.v3_sampling import ConformerRef, InMemorySamplingIndex, MoleculeEntry, UniformMoleculeSampler
from phychem_mfm.phase1.v3_structural import build_structural_views, eligibility_from_choices
from phychem_mfm.phase1.v3_trainer import PreparedV3Batch, SampleLRScheduler, V3StepTrainer
from phychem_mfm.phase1.v3_training import SampleClock, capture_rng_state
from phychem_mfm.training.losses import LossWeights


@pytest.fixture(autouse=True)
def fixed_cpu_numerical_environment():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(previous)


class UnitTracker:
    model_v3_unit_test_tracker = True

    def __init__(self, run_id="unit-original"):
        self.id, self.path, self.settings = run_id, "unit/" + run_id, SimpleNamespace(mode="offline")
        self.disabled, self.step, self.fail_next = False, 0, False
        self.records = []

    def log(self, row, *, step, commit):
        assert commit is True and step >= self.step
        if self.fail_next:
            self.fail_next = False
            raise RuntimeError("synthetic pre-write tracker failure")
        self.records.append(deepcopy(row))
        self.step = step + 1


class BoundSyntheticProvider:
    read_only, node_local = True, True
    source_sha256, data_version = "d" * 64, "synthetic-S-bridge-v1"

    def __init__(self, base, registry, binding, index):
        self.records, self.registry, self.binding, self.index = base.to_data_list(), registry, binding, index
        self.missing_all, self.calls, self.trace = False, 0, []
        self.generator = torch.Generator().manual_seed(919)

    def state_dict(self):
        return {"committed_calls": self.calls, "generator": self.generator.get_state().clone()}

    def load_state_dict(self, state):
        self.calls = state["committed_calls"]
        self.generator.set_state(state["generator"])

    def prepare(self, choices, *, role, view_config, enabled_groups, enabled_fields):
        self.calls += 1
        records = []
        for choice in choices:
            record = self.records[choice.molecule_index].clone()
            jitter = (float(torch.rand(())) + float(np.random.random()) + random.random()
                      + float(torch.rand((), generator=self.generator))) * .001
            record.pos = record.pos + jitter
            records.append(record)
        base = Batch.from_data_list(records)
        graph_masks = eligibility_from_choices(choices, self.registry, self.binding, enabled_fields=enabled_fields)
        if self.missing_all:
            graph_masks = {name: torch.zeros_like(value) for name, value in graph_masks.items()}
        views = build_structural_views(base, ordinals=tuple(choice.ordinal for choice in choices), config=view_config,
            include_structural="S" in enabled_groups, graph_eligibility=graph_masks)
        n = len(choices)
        labels = {"new_energy": FieldTarget(torch.tensor([[1. + choice.molecule_index + .01 * choice.ordinal] for choice in choices]),
                                             torch.full((n,), not self.missing_all, dtype=torch.bool)),
                  "new_atom": FieldTarget(torch.cat([torch.arange(12, dtype=torch.float32)[:, None] / 12
                                                     + choice.molecule_index * .1 for choice in choices]),
                                           torch.full((n * 12,), not self.missing_all, dtype=torch.bool))}
        self.trace.append({"role": role, "ordinals": [choice.ordinal for choice in choices],
                           "molecules": [choice.molecule_id for choice in choices],
                           "conformers": [choice.conformer_id for choice in choices], "pos": base.pos.clone()})
        return PreparedV3Batch(tuple(choices), views, labels, self.source_sha256, self.data_version, role)

    def validation_batches(self, *, role, view_config, enabled_groups, enabled_fields):
        raw = UniformMoleculeSampler(self.index, seed=7, sample_budget=2)
        choices = tuple(raw.choice(i) for i in range(2))
        if role == "VAL":
            choices = tuple(replace(choice, ordinal=100 + i, molecule_id="unseen-" + choice.molecule_id,
                                    conformer_id="val-" + choice.conformer_id) for i, choice in enumerate(choices))
        else:
            choices = tuple(replace(choice, ordinal=200 + i, conformer_id="unseen-conf-" + choice.conformer_id)
                            for i, choice in enumerate(choices))
        # Deliberately prepare before returning, to test preservation of provider
        # construction RNG as well as iterator/forward RNG.
        batch = self.prepare(choices, role=role, view_config=view_config,
                             enabled_groups=enabled_groups, enabled_fields=enabled_fields)
        return 1, iter((batch,))


def make_trainer(*, budget=6, groups=("S", "D", "P"), tracker=None, probe_interval=500,
                 milestones=(2, 4, 6), warmup=0, max_native_atoms=65536, optimizer_parameter_swap=None):
    model, base, registry, binding, norms, targets = setup_model()
    model.encoder.backbone.layers[0].ffn.net[2] = torch.nn.Dropout(.2)
    model.encoder.backbone.activation_checkpointing = True
    model.encoder.v3_performance_options = {"precision": "fp32", "backbone_checkpointing": None,
                                             "distance_implementation": "dense"}
    index = InMemorySamplingIndex(tuple(MoleculeEntry(f"m{i}",
        (ConformerRef(f"c{i}", 0, 12, (("PM7", f"unit:{i}"),)),),
        (("S", True), ("D", True), ("P", True)),
        (("structural", True), ("physics", True), ("descriptor", True))) for i in range(2)),
        BoundSyntheticProvider.data_version)
    sampler = UniformMoleculeSampler(index, seed=101, sample_budget=budget)
    clock = SampleClock(budget, tuple(value for value in milestones if value <= budget))
    provider = BoundSyntheticProvider(base, registry, binding, index)
    ordered = list(model.parameters())
    if optimizer_parameter_swap is not None:
        name_by_id = {id(parameter): name for name, parameter in model.named_parameters()}
        positions = {name_by_id[id(parameter)]: i for i, parameter in enumerate(ordered)}
        first, second = (positions[name] for name in optimizer_parameter_swap)
        assert ordered[first].shape == ordered[second].shape
        ordered[first], ordered[second] = ordered[second], ordered[first]
    optimizer = torch.optim.AdamW(ordered, lr=.003, betas=(.9, .95), weight_decay=0., foreach=False)
    scheduler = SampleLRScheduler(optimizer, sample_budget=budget, warmup_samples=warmup)
    bindings = {"code_sha": "c" * 40, "configuration_sha256": "e" * 64, "registry_sha256": registry.source_sha256,
                "normalization_sha256": "b" * 64, "data_version": provider.data_version}
    return V3StepTrainer(model, optimizer, scheduler, sampler, clock, provider, norms, LossWeights(),
                         tracker or UnitTracker(), bindings, enabled_groups=groups,
                         gradient_probe_interval=probe_interval, probe_samples=1, allow_unit_tracker=True,
                         max_native_atoms=max_native_atoms)


def scientific_record(row):
    return {key: value for key, value in row.items() if not key.startswith("runtime/") and key != "resume_parent_run_id"}


def test_complete_step_resume_preserves_inputs_model_optimizer_scheduler_rng_and_history_cursor(tmp_path):
    np.random.seed(17); random.seed(17)
    original = make_trainer(probe_interval=2)
    original.next_step(2)
    original.validate("VAL")
    before_save = capture_rng_state()
    original.save(tmp_path / "resume2", output_root=tmp_path)
    assert_tree_equal(before_save, capture_rng_state())
    provider_at_save = deepcopy(original.provider.state_dict())
    trace_start, history_start = len(original.provider.trace), len(original.tracker.records)
    original.run(max_batch_samples=3, checkpoint_root=tmp_path)
    expected_rng = capture_rng_state()
    expected_model, expected_optimizer = deepcopy(original.model.state_dict()), deepcopy(original.optimizer.state_dict())
    expected_scheduler, expected_clock = original.scheduler.state_dict(), original.clock.state_dict()
    expected_provider = deepcopy(original.provider.state_dict())
    continued_records = original.tracker.records[history_start:]
    continued_inputs = original.provider.trace[trace_start:]

    restored = make_trainer(tracker=UnitTracker("unit-resumed"), probe_interval=2)
    restored.model.encoder.backbone.activation_checkpointing = False
    restored.load(tmp_path / "resume2", output_root=tmp_path)
    assert_tree_equal(before_save, capture_rng_state())
    assert_tree_equal(provider_at_save, restored.provider.state_dict())
    assert restored.model.encoder.backbone.activation_checkpointing is True
    assert restored.model.encoder.v3_performance_options["precision"] == "fp32"
    assert restored.validation_state["VAL"]["completed_runs"] == 1
    assert restored.log_cursor == history_start
    second_root = tmp_path / "continued"; second_root.mkdir()
    restored.run(max_batch_samples=3, checkpoint_root=second_root)
    assert_tree_equal(expected_model, restored.model.state_dict())
    assert_tree_equal(expected_optimizer, restored.optimizer.state_dict())
    assert_tree_equal(expected_scheduler, restored.scheduler.state_dict())
    assert_tree_equal(expected_clock, restored.clock.state_dict())
    assert_tree_equal(expected_provider, restored.provider.state_dict())
    assert_tree_equal(expected_rng, capture_rng_state())
    assert_tree_equal(continued_inputs, restored.provider.trace)
    assert [scientific_record(row) for row in continued_records] == [scientific_record(row) for row in restored.tracker.records]
    assert restored.log_cursor == original.log_cursor
    assert any("shared_gradient_norm/S" in row for row in restored.tracker.records)


def test_draw_adapter_and_clock_mismatch_are_rejected_before_numerical_or_rng_mutation():
    trainer = make_trainer(groups=("P",))
    draws = tuple(trainer.sampler.choice(i) for i in range(2))
    batch = trainer.provider.prepare(draws, role="TRAIN", view_config=trainer.view_config,
        enabled_groups=trainer.groups, enabled_fields=trainer.fields)
    initial = deepcopy(trainer.model.state_dict()), deepcopy(trainer.optimizer.state_dict()), capture_rng_state()
    wrong_draw = replace(batch, choices=(replace(draws[0], molecule_id="wrong"), draws[1]))
    for value, match in ((wrong_draw, "before optimization"), (replace(batch, adapter_sha256="f" * 64), "binding differs")):
        with pytest.raises(ValueError, match=match):
            trainer.step(value)
        assert_tree_equal(initial[0], trainer.model.state_dict())
        assert_tree_equal(initial[1], trainer.optimizer.state_dict())
        assert_tree_equal(initial[2], capture_rng_state())
        assert trainer.clock.samples_consumed == trainer.sampler.samples_consumed == 0
    trainer.scheduler.samples_consumed = 1
    calls = trainer.provider.calls
    with pytest.raises(ValueError, match="clocks diverged"):
        trainer.next_step(2)
    assert trainer.provider.calls == calls


def test_all_missing_labels_advance_seen_scheduler_without_adam_update_and_log_inactive_fields():
    trainer = make_trainer(groups=("P",))
    trainer.provider.missing_all = True
    initial = deepcopy(trainer.model.state_dict())
    row = trainer.next_step(2)
    assert row["optimizer_updated"] is False and row["optimizer_updates"] == 0
    assert trainer.clock.samples_consumed == trainer.sampler.samples_consumed == trainer.scheduler.samples_consumed == 2
    assert not trainer.optimizer.state and row["lr_used"] != row["lr_next"]
    assert_tree_equal(initial, trainer.model.state_dict())
    assert row["field_enabled/new_energy"] is True and row["valid_count/new_energy"] == 0
    assert row["loss/new_energy"] is None
    for name in ("s_element", "s_noise", "s_bond", "new_atom"):
        assert row["field_enabled/" + name] is False and row["valid_count/" + name] == 0
        assert "loss/" + name not in row and row["accuracy/" + name] is None


def test_fixed_budget_splits_milestones_and_never_overruns_or_retains_history(tmp_path):
    trainer = make_trainer(budget=5, groups=("P",), milestones=(2, 4))
    with pytest.raises(ValueError, match="output root"):
        trainer.run(max_batch_samples=3)
    assert trainer.clock.samples_consumed == 0 and not trainer.provider.trace
    summary = trainer.run(max_batch_samples=3, checkpoint_root=tmp_path)
    assert summary["steps"] == 3 and summary["samples_consumed"] == 5
    assert len(summary["checkpoints"]) == 2 and "history" not in summary
    assert [ordinal for row in trainer.tracker.records for ordinal in row["sample_ordinals"]] == list(range(5))
    with pytest.raises(ValueError, match="exhausted"):
        trainer.next_step(1)
    assert trainer.clock.samples_consumed == 5


def test_validation_populations_are_separate_and_preserve_training_rng_provider_and_clocks():
    trainer = make_trainer()
    before_rng, before_provider = capture_rng_state(), deepcopy(trainer.provider.state_dict())
    before_clock, before_schedule = trainer.clock.state_dict(), trainer.scheduler.state_dict()
    before_model, before_optimizer = deepcopy(trainer.model.state_dict()), deepcopy(trainer.optimizer.state_dict())
    val = trainer.validate("VAL")
    seen = trainer.validate("TRAIN_UNSEEN_CONFORMATION")
    assert val["role"] == "VAL" and seen["role"] == "TRAIN_UNSEEN_CONFORMATION"
    assert trainer.validation_state["VAL"]["completed_runs"] == trainer.validation_state["TRAIN_UNSEEN_CONFORMATION"]["completed_runs"] == 1
    assert trainer.provider.trace[0]["molecules"][0].startswith("unseen-")
    assert trainer.provider.trace[1]["conformers"][0].startswith("unseen-conf-")
    assert val["fields"]["s_element"]["R2"] is None and val["fields"]["s_element"]["accuracy"] is not None
    for a, b in ((before_rng, capture_rng_state()), (before_provider, trainer.provider.state_dict()),
                 (before_clock, trainer.clock.state_dict()), (before_schedule, trainer.scheduler.state_dict()),
                 (before_model, trainer.model.state_dict()), (before_optimizer, trainer.optimizer.state_dict())):
        assert_tree_equal(a, b)
    calls = trainer.provider.calls
    with pytest.raises(ValueError, match="Only VAL"):
        trainer.validate("UNAUTHORIZED_EXTERNAL_ROLE")
    assert trainer.provider.calls == calls


def test_performance_options_and_scheduler_mismatch_reject_before_restoring_weights(tmp_path):
    trainer = make_trainer(groups=("P",))
    trainer.next_step(2)
    trainer.save(tmp_path / "execution", output_root=tmp_path)
    changed = make_trainer(groups=("P",))
    changed.model.encoder.v3_performance_options["precision"] = "bf16"
    initial = deepcopy(changed.model.state_dict())
    with pytest.raises(ValueError, match="Performance options changed"):
        changed.load(tmp_path / "execution", output_root=tmp_path)
    assert_tree_equal(initial, changed.model.state_dict())
    wrong_schedule = make_trainer(groups=("P",), warmup=1)
    initial = deepcopy(wrong_schedule.model.state_dict())
    with pytest.raises(ValueError, match="binding/digest"):
        wrong_schedule.load(tmp_path / "execution", output_root=tmp_path)
    assert_tree_equal(initial, wrong_schedule.model.state_dict())


def test_tracking_failure_keeps_committed_state_and_replays_pending_record_after_resume(tmp_path):
    tracker = UnitTracker(); tracker.fail_next = True
    trainer = make_trainer(groups=("P",), tracker=tracker)
    with pytest.raises(RuntimeError, match="pre-write tracker failure"):
        trainer.next_step(2)
    assert trainer.clock.samples_consumed == 2 and trainer.clock.optimizer_updates == 1
    assert trainer.log_cursor == 0 and trainer.pending_log is not None
    before_rng, calls = capture_rng_state(), trainer.provider.calls
    with pytest.raises(ValueError, match="Unacknowledged"):
        trainer.next_step(2)
    assert calls == trainer.provider.calls
    assert_tree_equal(before_rng, capture_rng_state())
    trainer.save(tmp_path / "pending", output_root=tmp_path)
    resumed = make_trainer(groups=("P",), tracker=UnitTracker("fresh-lineage"))
    resumed.load(tmp_path / "pending", output_root=tmp_path)
    resumed.flush_pending_log()
    assert resumed.log_cursor == 1 and resumed.pending_log is None
    assert resumed.tracker.records[0]["samples_consumed"] == 2
    resumed.next_step(2)
    assert resumed.clock.samples_consumed == 4 and resumed.clock.optimizer_updates == 2
    assert resumed.tracker.records[1]["resume_parent_run_id"] == tracker.id


def test_sample_scheduler_wsd_and_safe_state_restore():
    parameter = torch.nn.Parameter(torch.ones(1))
    optimizer = torch.optim.AdamW((parameter,), lr=.01)
    schedule = SampleLRScheduler(optimizer, sample_budget=100, warmup_samples=10, mode="wsd", decay_start_samples=80)
    assert optimizer.param_groups[0]["lr"] == 0.
    schedule.set_consumed(40)
    assert optimizer.param_groups[0]["lr"] == .01
    saved = schedule.state_dict()
    schedule.set_consumed(100)
    assert optimizer.param_groups[0]["lr"] == 0.
    schedule.load_state_dict(saved)
    assert schedule.samples_consumed == 40 and optimizer.param_groups[0]["lr"] == .01


def test_atom_limits_split_only_the_next_prefix_and_keep_sample_order():
    trainer = make_trainer(budget=3, groups=("P",), milestones=(), max_native_atoms=12)
    first = trainer.next_step(3)
    second = trainer.next_step(3)
    third = trainer.next_step(3)
    assert [first["sample_ordinals"], second["sample_ordinals"], third["sample_ordinals"]] == [[0], [1], [2]]
    assert trainer.clock.samples_consumed == 3


def test_same_shape_optimizer_parameter_swap_rejects_resume_before_any_state_mutation(tmp_path):
    original = make_trainer()
    original.next_step(2)
    names = {id(parameter): name for name, parameter in original.model.named_parameters()}
    by_shape, swap = {}, None
    for group in original.optimizer.param_groups:
        for parameter in group["params"]:
            if parameter.grad is None or parameter.ndim != 2:
                continue
            shape = tuple(parameter.shape)
            if shape in by_shape:
                swap = (by_shape[shape], parameter)
                break
            by_shape[shape] = parameter
        if swap is not None:
            break
    assert swap is not None
    assert not torch.equal(original.optimizer.state[swap[0]]["exp_avg"], original.optimizer.state[swap[1]]["exp_avg"])
    swapped_names = tuple(names[id(parameter)] for parameter in swap)
    original.save(tmp_path / "ordered", output_root=tmp_path)
    wrong = make_trainer(optimizer_parameter_swap=swapped_names)
    assert original.contract["optimizer_options"] == wrong.contract["optimizer_options"]
    assert original.contract["optimizer_parameter_groups"] != wrong.contract["optimizer_parameter_groups"]
    before = (deepcopy(wrong.model.state_dict()), deepcopy(wrong.optimizer.state_dict()),
              wrong.scheduler.state_dict(), wrong.sampler.state_dict(), wrong.clock.state_dict(), capture_rng_state())
    with pytest.raises(ValueError, match="binding/digest"):
        wrong.load(tmp_path / "ordered", output_root=tmp_path)
    after = (wrong.model.state_dict(), wrong.optimizer.state_dict(), wrong.scheduler.state_dict(),
             wrong.sampler.state_dict(), wrong.clock.state_dict(), capture_rng_state())
    assert_tree_equal(before, after)
