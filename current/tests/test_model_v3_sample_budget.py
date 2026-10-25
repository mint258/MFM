"""Actual original trainer resume plus synthetic event/receipt fault injection.

The single real512 H0 test opens only its synthetic training checkpoint and a
three-atom geometry. Synthetic SDK/terminal receipts below are unit fixtures,
never evidence of a persistent real run, final targets or a D5 population.
"""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import resource

import pytest
import torch
from torch_geometric.data import Data

from test_model_v3_trainer import make_trainer, UnitTracker
from test_model_v3_training import assert_tree_equal
from test_model_v3_architecture_training import architecture_trainer
from phychem_mfm.phase1.v3_sample_budget_experiment import SampleBudgetPlan, SampleBudgetExperiment, SegmentPause
from phychem_mfm.phase1.v3_sample_budget_events import (PanelEventController, TASKS, binding, read_bound,
    canonical, verify_checkpoint_record, write_once)
from phychem_mfm.phase1.v3_training import capture_rng_state
from phychem_mfm.phase1.v3_encoder_bridge import load_encoder_pair


@pytest.fixture(autouse=True)
def cpu_numerics():
    old = torch.get_num_threads(); torch.set_num_threads(1)
    try:
        yield
    finally:
        torch.set_num_threads(old)


def plan(budget=5, panel=(2, 4, 5), **changes):
    value = SampleBudgetPlan(sample_budget=budget, panel_samples=panel, validation_samples=(), validation_roles=(),
        recovery_interval_samples=budget, max_batch_samples=3, max_checkpoints_per_segment=8, max_total_checkpoints=32,
        max_segment_seconds=600, checkpoint_reserve_seconds=30, checkpoint_reserve_bytes=2*1024**2,
        max_segment_bytes=2*1024**3)
    return replace(value, **changes)


def experiment(root, p=None, *, tracker=None, groups=("P",), lineage="unit-sample"):
    p = p or plan()
    trainer = make_trainer(budget=p.sample_budget, groups=groups, milestones=tuple(n for n in (2, 4) if n <= p.sample_budget), tracker=tracker)
    return SampleBudgetExperiment(trainer, p, output_root=root, lineage=lineage, input_scope="synthetic_fixture")


def completion_directory(ref):
    return Path(ref["path"]).parent


def test_nonmilestone_final_budget_is_saved_with_all_original_milestones_and_outbox(tmp_path):
    exp = experiment(tmp_path / "experiment")
    limit = resource.getrlimit(resource.RLIMIT_FSIZE)
    result = exp.run(segment_id="one", until_samples=5)
    assert resource.getrlimit(resource.RLIMIT_FSIZE) == limit
    assert result["status"] == "BUDGET_REACHED_PENDING_EVALUATION"
    points = [body for _, body in exp.controller.events()]
    assert sorted(body["samples_consumed"] for body in points) == [2, 4, 5]
    assert all(body["status"] == "BLOCKED_UNSUPPORTED_ENCODER" for body in points)
    assert exp.trainer.clock.saved_milestones == [2, 4]
    assert exp.trainer.sampler.samples_consumed == exp.trainer.clock.samples_consumed == exp.trainer.scheduler.samples_consumed == 5
    _, state = verify_checkpoint_record(result["last_checkpoint"])
    assert state["samples_consumed"] == 5 and not result["data_authority_asserted"] and not result["scientific_acceptance"]


def test_three_views_and_no_label_batches_count_base_draws_not_atoms_views_or_updates(tmp_path):
    exp = experiment(tmp_path / "experiment", plan(3, (2, 3)), groups=("S",))
    exp.trainer.provider.missing_all = True
    before = deepcopy(exp.trainer.model.state_dict())
    result = exp.run(segment_id="no_labels", until_samples=3)
    assert result["samples_consumed"] == 3 and result["optimizer_updates"] == 0
    assert [ordinal for row in exp.trainer.tracker.records for ordinal in row.get("sample_ordinals", ())] == [0, 1, 2]
    assert exp.trainer.scheduler.samples_consumed == 3
    assert_tree_equal(before, exp.trainer.model.state_dict())


def test_true_original_model_optimizer_provider_scheduler_rng_and_validation_resume(tmp_path):
    p = plan(3, (2, 3), validation_samples=(2,), validation_roles=("VAL", "TRAIN_UNSEEN_CONFORMATION"))
    original = experiment(tmp_path / "experiment", p)
    first = original.run(segment_id="first", until_samples=2)
    # Compute the uninterrupted numerical reference without publishing a future
    # branch into this lineage's outbox. This is a genuine original trainer step.
    original.trainer.next_step(1)
    expected = (deepcopy(original.trainer.model.state_dict()), deepcopy(original.trainer.optimizer.state_dict()),
        deepcopy(original.trainer.scheduler.state_dict()), deepcopy(original.trainer.clock.state_dict()),
        deepcopy(original.trainer.provider.state_dict()), capture_rng_state(), deepcopy(original.trainer.validation_state))
    resumed = experiment(tmp_path / "experiment", p, tracker=UnitTracker("fresh-resume"))
    resumed.resume(completion_directory(first["last_checkpoint"]))
    # The original point is republished idempotently; no new training event.
    assert len(resumed.controller.events()) == 1
    resumed.run(segment_id="resumed", until_samples=3)
    actual = (resumed.trainer.model.state_dict(), resumed.trainer.optimizer.state_dict(), resumed.trainer.scheduler.state_dict(),
        resumed.trainer.clock.state_dict(), resumed.trainer.provider.state_dict(), capture_rng_state(), resumed.trainer.validation_state)
    for a, b in zip(expected, actual):
        assert_tree_equal(a, b)
    assert resumed.trainer.resume_parent["id"] == original.trainer.tracker.id
    curve = resumed.controller.curve()
    at_two = next(row for row in curve["points"] if row["samples_consumed"] == 2)
    assert {row["role"] for row in at_two["validation"]} == {"VAL", "TRAIN_UNSEEN_CONFORMATION"}
    assert at_two["segment_runtime_before_this_save"]["samples_consumed"] == 2


def test_explicit_segment_checkpoint_cap_pauses_only_after_safe_save_and_can_resume(tmp_path):
    p = plan(max_checkpoints_per_segment=1)
    exp = experiment(tmp_path / "experiment", p)
    first = exp.run(segment_id="first", until_samples=5)
    assert first["status"] == "SEGMENT_PAUSED" and first["samples_consumed"] == 2 and first["new_checkpoint_count"] == 1
    exp.resume(completion_directory(first["last_checkpoint"]))
    second = exp.run(segment_id="second", until_samples=5)
    assert second["status"] == "SEGMENT_PAUSED" and second["samples_consumed"] == 4
    final = exp.run(segment_id="third", until_samples=5)
    assert final["status"] == "BUDGET_REACHED_PENDING_EVALUATION" and final["samples_consumed"] == 5


def test_cooperative_preflight_pause_saves_committed_cursor_without_changing_recipe(tmp_path):
    exp = experiment(tmp_path / "experiment")
    contract = deepcopy(exp.trainer.contract)
    def preflight(action, context):
        assert context["payload_capacity_proven"] is False
        if action == "STEP" and context["samples_consumed"] == 2:
            raise SegmentPause("unit supervisor checkpoint reserve")
    result = exp.run(segment_id="pause", until_samples=5, preflight=preflight)
    assert result["status"] == "SEGMENT_PAUSED" and result["samples_consumed"] == 2
    assert read_bound(read_bound(result["last_checkpoint"])["trainer_marker"])["samples_consumed"] == 2
    assert exp.trainer.contract == contract


def test_bare_trainer_cannot_fake_encoder_extension_and_required_panel_rejects_before_output(tmp_path):
    trainer = make_trainer(budget=3, groups=("P",), milestones=(2,))
    destination = tmp_path / "not_created"
    with pytest.raises(ValueError, match="BLOCKED_UNSUPPORTED_ENCODER"):
        SampleBudgetExperiment(trainer, plan(3, (2, 3)), output_root=destination, lineage="unit", input_scope="synthetic_fixture", panel_required=True)
    assert not destination.exists() and "architecture_extension" not in trainer.contract


def test_complete_checkpoint_then_publish_failure_recovers_same_immutable_event(tmp_path, monkeypatch):
    exp = experiment(tmp_path / "experiment", plan(3, (2, 3)))
    publish = exp.controller.publish
    def fail(_):
        raise RuntimeError("synthetic publication interruption")
    monkeypatch.setattr(exp.controller, "publish", fail)
    with pytest.raises(RuntimeError, match="publication"):
        exp.run(segment_id="failed", until_samples=2)
    assert exp.last_checkpoint and not list((exp.controller.root / "events").iterdir())
    _, saved = verify_checkpoint_record(exp.last_checkpoint)
    expected_id = saved["event"]["event_id"]
    monkeypatch.setattr(exp.controller, "publish", publish)
    exp.resume(completion_directory(exp.last_checkpoint))
    exp.resume(completion_directory(exp.last_checkpoint))
    assert [body["event_id"] for _, body in exp.controller.events()] == [expected_id]
    assert (exp.segment / "FAILURE.json").exists()


def test_partial_original_checkpoint_is_preserved_rejected_and_never_published(tmp_path, monkeypatch):
    exp = experiment(tmp_path / "experiment", plan(3, (2, 3)))
    def partial(directory, *, output_root):
        directory.mkdir(); (directory / "payload.pt").write_bytes(b"synthetic incomplete payload")
        raise OSError("synthetic failed serialization")
    monkeypatch.setattr(exp.trainer, "save", partial)
    with pytest.raises(OSError):
        exp.run(segment_id="failed", until_samples=2)
    directory = next(exp.segment.glob("checkpoint_*"))
    assert (directory / "trainer/payload.pt").read_bytes() == b"synthetic incomplete payload"
    assert not (directory / "EXPERIMENT_COMPLETE.json").exists() and not exp.controller.events()
    fresh = experiment(tmp_path / "experiment", plan(3, (2, 3)))
    before = deepcopy(fresh.trainer.model.state_dict())
    with pytest.raises(FileNotFoundError):
        fresh.resume(directory)
    assert_tree_equal(before, fresh.trainer.model.state_dict())


def test_tracking_failure_saves_only_committed_state_and_flushes_on_fresh_resume(tmp_path):
    tracker = UnitTracker(); tracker.fail_next = True
    p = plan(3, (2, 3))
    exp = experiment(tmp_path / "experiment", p, tracker=tracker)
    with pytest.raises(RuntimeError, match="tracker failure"):
        exp.run(segment_id="failed", until_samples=3)
    assert exp.trainer.clock.samples_consumed == 2 and exp.last_checkpoint and not exp.controller.events()
    restored = experiment(tmp_path / "experiment", p, tracker=UnitTracker("new-sdk-lineage"))
    restored.resume(completion_directory(exp.last_checkpoint))
    assert restored.trainer.pending_log is not None
    result = restored.run(segment_id="restored", until_samples=3)
    assert result["samples_consumed"] == 3 and restored.trainer.pending_log is None
    assert [row["samples_consumed"] for row in restored.trainer.tracker.records] == [2, 3]


def test_partial_optimizer_failure_cannot_be_promoted_to_committed_recovery(tmp_path, monkeypatch):
    exp = experiment(tmp_path / "experiment", plan(3, (2, 3)))
    def unsafe_step(*args, **kwargs):
        with torch.no_grad():
            next(exp.trainer.model.parameters()).add_(1.)
        raise RuntimeError("synthetic optimizer partial failure")
    monkeypatch.setattr(exp.trainer.optimizer, "step", unsafe_step)
    with pytest.raises(RuntimeError, match="optimizer partial"):
        exp.run(segment_id="failed", until_samples=3)
    assert exp.trainer.clock.samples_consumed == 0 and exp.last_checkpoint is None
    assert not list(exp.segment.glob("checkpoint_*")) and not exp.controller.events()


def test_changed_plan_budget_source_and_partial_metadata_are_not_implicitly_repaired(tmp_path):
    p = plan(3, (2, 3)); exp = experiment(tmp_path / "experiment", p)
    first = exp.run(segment_id="first", until_samples=2)
    with pytest.raises(ValueError, match="Existing/partial metadata"):
        experiment(tmp_path / "experiment", replace(p, max_batch_samples=1))
    directory = completion_directory(first["last_checkpoint"])
    state_path = directory / "experiment_state.json"
    original = state_path.read_bytes(); state_path.write_bytes(b"partial")
    with pytest.raises(ValueError):
        exp.resume(directory)
    assert state_path.read_bytes() == b"partial"
    state_path.write_bytes(original)  # Restore only this explicitly corrupted unit fixture.


def panel_bindings():
    return {"panel_sha256": "a"*64, "training_store_sha256": "b"*64,
        "membership_sha256": {name: "c"*64 for name in ("cyp_isoform", "expansionrx", "qm9")},
        "preregistration_sha": "d"*40, "code_sha": "e"*40}


@pytest.fixture(scope="module")
def ready512(tmp_path_factory):
    root = tmp_path_factory.mktemp("sample_budget_real512")
    old = torch.get_num_threads(); torch.set_num_threads(1)
    try:
        trainer, configuration = architecture_trainer(kind="C1-0", views="three", budget=1, layers=6)
        configuration_ref = write_once(root / "configuration.json", configuration)
        trainer.bindings["configuration_sha256"] = configuration_ref["sha256"]
        exp = SampleBudgetExperiment(trainer, plan(1, (1,)), output_root=root / "experiment", lineage="unit-real512",
            input_scope="synthetic_fixture", model_configuration=configuration_ref, panel_binding=panel_bindings(), panel_required=True)
        result = exp.run(segment_id="one", until_samples=1)
        return exp, result
    finally:
        torch.set_num_threads(old)


def test_actual_architecture_trainer_checkpoint_to_generic512_h0_is_target_free(ready512):
    exp, result = ready512
    event = exp.controller.events()[0][1]
    assert event["status"] == "READY" and event["samples_consumed"] == 1
    before = capture_rng_state()
    pair = load_encoder_pair(event["checkpoint"], event["model_configuration"],
        architecture_sha256=event["architecture_sha256"], pretraining_seed=event["pretraining_seed"],
        training_completion=event["training_completion"], enable_architecture_candidates=True)
    assert_tree_equal(before, capture_rng_state())
    assert pair.provenance["H0_dimension"] == 512 and pair.provenance["downstream_target_records_read"] == 0
    assert pair.candidate.config_dict() == pair.random_reference.config_dict() == exp.trainer.model.encoder.config_dict()
    assert_tree_equal(pair.candidate.state_dict(), exp.trainer.model.encoder.state_dict())
    graph = Data(x=torch.tensor([[5], [0], [7]]), pos=torch.tensor([[0., 0., 0.], [1., 0., 0.], [0., 1., 0.]]))
    exp.trainer.model.eval()
    with torch.no_grad():
        expected = exp.trainer.model.encoder.encode_atoms(graph)
        actual = pair.candidate.encode_atoms(graph)
        random = pair.random_reference.encode_atoms(graph)
    assert actual.shape == random.shape == (3, 512) and torch.equal(expected, actual)
    assert not torch.equal(actual, random)


def fake_result_and_evidence(tmp_path, event):
    # Deliberately synthetic receipts: prove collector binding/rejection only.
    task_rows = {task+"@"+method: {"error": .8, "reference_error": 1., "normalized_improvement": 1.-.8,
        "bootstrap_ci": [.1, .3], "observed_labels": 10, "observed_molecules": 2}
        for task in TASKS for method in ("ridge", "linear64_relu")}
    summaries = {}
    for name in ("primary_18_cells", "ridge", "linear64_relu"):
        selected = {key: row for key, row in task_rows.items() if name == "primary_18_cells" or key.endswith("@"+name)}
        summaries[name] = {"complete": True, "tasks": selected, "bootstrap_samples": 1000, "bootstrap_defined": 1000,
            "mean_normalized_improvement": 1.-.8, "bootstrap_ci": [.1, .3]}
    result = {"status": "COMPLETED", "reference_kind": "primary", **event["panel_binding"],
        "encoder_pair": {"checkpoint": event["checkpoint"], "original_configuration": event["model_configuration"],
            "H0_dimension": 512, "pretraining_seed": event["pretraining_seed"], "random_reference_seed": 20261025,
            "checkpoint_schema": "model_v3_immutable_sample_checkpoint", "training_completion": event["training_completion"],
            "checkpoint_encoder_state_sha256": "1"*64, "random_encoder_state_sha256": "2"*64},
        "architecture_sha256": event["architecture_sha256"], "random_reference_initialization_seed": 20261025,
        "readout_seed": 0, "summaries": summaries, "job_id": "synthetic", "wandb_run_id": "synthetic", "journal_records": 2,
        "h0_caches": {}}
    for dataset in ("cyp_isoform", "expansionrx", "qm9"):
        for label in ("candidate", "reference"):
            result["h0_caches"][label+"/"+dataset] = {"targets_cached": False, "binding": {
                "architecture_sha256": event["architecture_sha256"], "membership_sha256": "c"*64,
                "geometry_sha256": "3"*64, "dimension": 512, "packing_plan_sha256": "4"*64,
                "packing_budget_sha256": "5"*64, "effective_runtime_sha256": "6"*64,
                "encoder_sha256": "1"*64 if label == "candidate" else "2"*64}}
    result_ref = write_once(tmp_path / "result.json", result)
    outer_ref = write_once(tmp_path / "outer.json", {"status": "COMPLETED", "exit_code": 0, "job_id": "synthetic"})
    sdk_ref = write_once(tmp_path / "sdk.json", {"status": "VERIFIED", "wandb_history_independently_verified": True,
        "inputs": {"result": result_ref}, "sdk_run_id": "synthetic", "clean_eof": True, "sdk_exit_code": 0, "history_rows": 2})
    evidence_ref = write_once(tmp_path / "evidence.json", {"schema": "model_v3_sample_panel_evidence_v1", "result": result_ref,
        "outer_terminal": outer_ref, "sdk_verification": sdk_ref})
    return result_ref, evidence_ref


def test_ack_after_checkpoint_persists_across_true_resume_without_replay(ready512, tmp_path):
    exp, result = ready512
    event_ref, event = exp.controller.pending()[0]
    result_ref, evidence_ref = fake_result_and_evidence(tmp_path, event)
    receipt = exp.controller.acknowledge(event_ref, result_ref, evidence_ref)
    assert not exp.controller.pending()
    exp.resume(completion_directory(result["last_checkpoint"]))
    assert not exp.controller.pending()
    assert exp.controller.acknowledge(event_ref, result_ref, evidence_ref) == receipt
    curve = exp.controller.curve()
    assert curve["points"][0]["status"] == "ACKNOWLEDGED" and curve["points"][0]["samples_consumed"] == 1
    assert curve["platform_or_architecture_decision"] is None and not curve["scientific_acceptance"]


@pytest.mark.parametrize("drift", ("checkpoint", "panel", "sdk", "terminal"))
def test_collector_rejects_foreign_result_or_unclosed_tracking_and_keeps_pending(ready512, tmp_path, drift):
    exp, complete = ready512
    controller = PanelEventController(tmp_path / "peer_ledger", contract=exp.contract, max_records=8)
    event_ref = controller.publish(complete["last_checkpoint"]); event = read_bound(event_ref)["body"]
    folder = tmp_path / "receipts"; folder.mkdir()
    result_ref, evidence_ref = fake_result_and_evidence(folder, event)
    if drift in ("checkpoint", "panel"):
        value = read_bound(result_ref)
        if drift == "checkpoint": value["encoder_pair"]["checkpoint"] = {"sha256": "f"*64}
        else: value["panel_sha256"] = "f"*64
        bad = write_once(folder / "wrong_result.json", value)
        with pytest.raises(ValueError): controller.acknowledge(event_ref, bad, evidence_ref)
    else:
        evidence = read_bound(evidence_ref)
        key = "sdk_verification" if drift == "sdk" else "outer_terminal"
        value = read_bound(evidence[key]); value["status"] = "FAILED"
        evidence[key] = write_once(folder / "wrong_receipt.json", value)
        bad = write_once(folder / "wrong_evidence.json", evidence)
        with pytest.raises(ValueError): controller.acknowledge(event_ref, result_ref, bad)
    assert len(controller.pending()) == 1 and not list((controller.root / "acks").iterdir())


def test_partial_ack_attempt_is_preserved_and_does_not_hide_pending_event(ready512, tmp_path):
    exp, complete = ready512
    controller = PanelEventController(tmp_path / "ledger", contract=exp.contract, max_records=8)
    controller.publish(complete["last_checkpoint"])
    partial = controller.root / "acks" / "partial_attempt"; partial.mkdir()
    (partial / "receipt.json").write_bytes(b"partial")
    assert len(controller.pending()) == 1 and (partial / "receipt.json").read_bytes() == b"partial"


def test_acknowledged_sample_point_cannot_be_reassigned_to_an_alternative_event(ready512, tmp_path):
    exp, complete = ready512
    controller = PanelEventController(tmp_path / "ledger", contract=exp.contract, max_records=8)
    event_ref = controller.publish(complete["last_checkpoint"])
    receipts = tmp_path / "receipts"; receipts.mkdir()
    result_ref, evidence_ref = fake_result_and_evidence(receipts, read_bound(event_ref)["body"])
    controller.acknowledge(event_ref, result_ref, evidence_ref)
    original = read_bound(complete["last_checkpoint"])
    state = read_bound(original["state"]); intent = read_bound(original["intent"])
    state["reason"] = intent["state"]["reason"] = "synthetic_alternative_attempt"
    state["event"]["reason"] = state["reason"]
    state["event"]["event_id"] = canonical({key: value for key, value in state["event"].items() if key != "event_id"})
    replacement = {**original, "state": write_once(tmp_path / "alternative_state.json", state),
        "intent": write_once(tmp_path / "alternative_intent.json", intent)}
    alternative_ref = write_once(tmp_path / "alternative_complete.json", replacement)
    with pytest.raises(ValueError, match="implicit lineage fork"):
        controller.publish(alternative_ref)
    assert not controller.pending() and len(controller.events()) == 1


@pytest.mark.parametrize("field,value", (("recovery_interval_samples", 0), ("max_total_checkpoints", 0),
    ("max_segment_seconds", 7201), ("max_segment_bytes", 2*1024**3+1)))
def test_explicit_frequency_count_wall_and_storage_limits_are_mandatory(field, value):
    with pytest.raises(ValueError):
        plan(**{field: value})
