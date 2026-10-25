"""Synthetic safety tests plus one real, tiny, offline W&B SDK round-trip."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import io
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_native_history as verify
import make_b3_report as report


def sample_rows():
    return [
        {"step": 0, "reference/cyp.3A4@ridge/validation_error": .5},
        {"step": 1, "candidate/qm9.U0@linear64_relu/readout/loss": .75,
         "candidate/qm9.U0@linear64_relu/readout/epoch": 0,
         "candidate/qm9.U0@linear64_relu/readout/observed_labels": 2,
         "candidate/qm9.U0@linear64_relu/readout/update": 0},
    ]


def records(rows=None, *, exit_code=0):
    from wandb.proto import wandb_internal_pb2 as pb
    first = pb.Record()
    first.run.run_id = "sa3audit"
    first.run.config.update.add(key="readout_seed", value_json="0")
    items = [first]
    for row in (sample_rows() if rows is None else rows):
        item = pb.Record()
        for key, value in row.items():
            item.history.item.add(key="_step" if key == "step" else key, value_json=json.dumps(value))
        item.history.item.add(key="_runtime", value_json="0.125")
        items.append(item)
    item = pb.Record()
    item.summary.update.add(key="evaluation_status", value_json='"COMPLETED"')
    items.append(item)
    item = pb.Record()
    item.exit.exit_code = exit_code
    items.append(item)
    return items


def compare(native, *, destination=None, rows=None, **kwargs):
    return verify.compare_records(native, sample_rows() if rows is None else rows,
        destination or io.BytesIO(), expected_run_id="sa3audit", expected_config={"readout_seed": 0},
        expected_summary={"evaluation_status": "COMPLETED"}, expected_rows=2, **kwargs)


def test_real_offline_sdk_round_trip(tmp_path, monkeypatch):
    # This is the actual installed SDK, not a fake DataStore/log method.
    monkeypatch.setenv("WANDB_MODE", "offline")
    monkeypatch.setenv("WANDB_DIR", str(tmp_path))
    monkeypatch.setenv("WANDB_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WANDB_DATA_DIR", str(tmp_path / "wandb_data"))
    import wandb
    from wandb.proto import wandb_internal_pb2 as pb
    from wandb.sdk.internal.datastore import DataStore
    run = wandb.init(project="model-v3-readonly-verifier-unit", id="sa3audit", mode="offline",
        dir=str(tmp_path), config={"readout_seed": 0})
    try:
        for row in sample_rows():
            run.log({key: value for key, value in row.items() if key != "step"}, step=row["step"], commit=True)
        run.summary["evaluation_status"] = "COMPLETED"
    finally:
        run.finish(exit_code=0)
    paths = list((tmp_path / "wandb").glob("offline-run-*/run-sa3audit.wandb"))
    assert len(paths) == 1
    before = verify.binding(paths[0])
    data = DataStore()
    destination = io.BytesIO()
    try:
        data.open_for_scan(str(paths[0]))
        result = compare(verify.scan_records(data, pb.Record, deadline=time.monotonic()+30), destination=destination)
    finally:
        data.close()
    assert result["clean_eof"] and result["history_rows"] == 2 and result["sdk_exit_code"] == 0
    assert verify.binding(paths[0]) == before
    assert [json.loads(line) for line in destination.getvalue().splitlines()] == sample_rows()


@pytest.mark.parametrize("corruption", ("loss", "step", "extra_key", "missing_row", "exit", "config", "run"))
def test_independent_comparison_rejects_drift(corruption):
    native = records()
    if corruption == "loss":
        native[2].history.item[1].value_json = "0.8"
    elif corruption == "step":
        native[2].history.item[0].value_json = "2"
    elif corruption == "extra_key":
        native[2].history.item.add(key="member_predictions", value_json="[0.1,0.2]")
    elif corruption == "missing_row":
        native.pop(2)
    elif corruption == "exit":
        native[-1].exit.exit_code = 1
    elif corruption == "config":
        native[0].run.config.update[0].value_json = "99"
    elif corruption == "run":
        native[0].run.run_id = "otherid0"
    with pytest.raises(ValueError):
        compare(native)


def test_export_budget_and_journal_framing():
    with pytest.raises(ValueError, match="byte budget"):
        compare(records(), budget_bytes=10)
    with pytest.raises(ValueError, match="Truncated"):
        list(verify.journal_rows(io.BytesIO(json.dumps(sample_rows()[0]).encode())))
    with pytest.raises(ValueError, match="Duplicate JSON"):
        verify.strict_json('{"step":0,"step":1}')
    bad = deepcopy(sample_rows()[1]); bad["candidate/qm9.U0@linear64_relu/readout/update"] = 1.5
    with pytest.raises(ValueError, match="integers"):
        verify.normalized(bad, 1)


def test_native_record_cap_rejects_stream_without_eof(monkeypatch):
    from wandb.proto import wandb_internal_pb2 as pb
    monkeypatch.setattr(verify, "MAX_NATIVE_RECORDS", 1)
    class NotAtEof:
        def scan_data(self):
            return records()[0].SerializeToString()
    with pytest.raises(ValueError, match="total-record budget"):
        list(verify.scan_records(NotAtEof(), pb.Record, deadline=time.monotonic()+1))


@pytest.mark.parametrize("native_limit", (8, 7))
def test_native_metric_ancillary_records_do_not_consume_history_quota_but_obey_total_cap(monkeypatch, native_limit):
    from wandb.proto import wandb_internal_pb2 as pb
    metric = pb.Record()
    metric.metric.name = "candidate/qm9.U0@linear64_relu/readout/loss"
    base = records()
    # Eight native records, with exactly two scientific history rows. Metric
    # definitions remain native ancillary records; they are not journal rows.
    native = [base[0], metric, base[1], metric, base[2], metric, *base[3:]]
    assert len(native) == 8
    monkeypatch.setattr(verify, "MAX_NATIVE_RECORDS", native_limit)
    monkeypatch.setattr(verify, "MAX_HISTORY_ROWS", 2)
    class SerializedStream:
        def __init__(self):
            self.rows = iter(row.SerializeToString() for row in native)
        def scan_data(self):
            return next(self.rows, None)
    stream = verify.scan_records(SerializedStream(), pb.Record, deadline=time.monotonic()+2)
    source = io.BytesIO(b"".join(verify.encoded(row) for row in sample_rows()))
    if native_limit == 7:
        with pytest.raises(ValueError, match="total-record budget"):
            compare(stream, rows=verify.journal_rows(source))
    else:
        result = compare(stream, rows=verify.journal_rows(source))
        assert result["native_records"] == 8 and result["record_types"]["metric"] == 3
        assert result["history_rows"] == 2 and result["clean_eof"]


def test_history_cap_still_rejects_extra_history_with_room_in_native_budget(monkeypatch):
    monkeypatch.setattr(verify, "MAX_HISTORY_ROWS", 1)
    assert verify.MAX_NATIVE_RECORDS == 500000
    with pytest.raises(ValueError, match="history-row budget"):
        compare(records())


def test_readonly_binding_rejects_symlink_and_raw_sha_drift(tmp_path):
    original = tmp_path / "original.json"
    original.write_text('{"status":"ok"}')
    with pytest.raises(ValueError, match="bytes differ"):
        verify.bound_json(original, "0"*64)
    link = tmp_path / "link.json"
    link.symlink_to(original)
    with pytest.raises(ValueError, match="physical"):
        verify.binding(link)


def test_admission_requires_successful_terminal_receipt_and_quota():
    admission = {"schema": "model_v3_bounded_metadata_admission_v2",
        "evaluation_job": {"job_id": "4520437", "state": "COMPLETED", "exit_code": "0:0"},
        "verification_admission": {"network_access": False, "gpu_requested": False,
            "max_output_bytes": verify.MAX_OUTPUT_BYTES, "max_source_bytes": verify.MAX_SOURCE_BYTES,
            "max_native_records": verify.MAX_NATIVE_RECORDS, "max_history_rows": verify.MAX_HISTORY_ROWS,
            "max_wall_seconds": verify.MAX_WALL_SECONDS,
            "quota": {"free_bytes": 40 << 30, "reserved_headroom_bytes": 32 << 30,
                "active_job_reserved_bytes": 0, "observed_at_utc": datetime.now(timezone.utc).isoformat()}}}
    verify.check_admission(admission, {"job_id": "4520437"})
    admission["evaluation_job"]["state"] = "RUNNING"
    with pytest.raises(ValueError, match="terminal"):
        verify.check_admission(admission, {"job_id": "4520437"})
    admission["evaluation_job"]["state"] = "COMPLETED"
    admission["verification_admission"]["quota"]["free_bytes"] = 32 << 30
    with pytest.raises(ValueError, match="Quota headroom"):
        verify.check_admission(admission, {"job_id": "4520437"})


def panel_fixture():
    architecture, state, random_state = "a"*64, "b"*64, "c"*64
    tasks = [{"task_id": task, "error_metric": "one_minus_hit1" if task.startswith("cyp.") else "mae",
        "unit": "binary" if task.startswith("cyp.") else "source_unit"} for task in sorted(verify.TASKS)]
    panel = {"tasks": tasks, "uncertainty": {"bootstrap_samples": 1000, "confidence": .95,
        "paired": True, "same_draw_across_tasks_and_readouts_within_dataset": True, "seed": 20261025},
        "readouts": {"linear64_relu": {"epochs": 20, "batch_graphs": 32, "seed": 0}}}
    checkpoint = {"path": "/fixture/model.pt", "sha256": "d"*64, "state_key": "model"}
    request = {"reference_kind": "historical_sanity_only", "architecture_sha256": architecture,
        "preregistration_sha": verify.PREREGISTRATION, "checkpoint": checkpoint, "pretraining_seed": 0,
        "model_configuration": {"path": "/fixture/B3.json", "sha256": "f"*64}}
    result = {"status": "COMPLETED", "reference_kind": "historical_sanity_only", "architecture_sha256": architecture,
        "preregistration_sha": verify.PREREGISTRATION, "random_reference_initialization_seed": 20261025,
        "pretraining_seed": 0, "readout_seed": 0, "membership_sha256": {d: "m"*64 for d in report.DATASETS},
        "h0_packing_plan_sha256": {d: "p"*64 for d in report.DATASETS}, "h0_packing_budget_sha256": "q"*64,
        "h0_effective_runtime_sha256": "r"*64, "h0_caches": {}, "summaries": {},
        "encoder_pair": {"reference_kind": "historical_sanity_only", "H0_dimension": 384,
            "architecture_sha256": architecture, "checkpoint": checkpoint, "random_reference_seed": 20261025,
            "original_configuration": request["model_configuration"],
            "pretraining_seed": 0, "checkpoint_encoder_state_sha256": state, "random_encoder_state_sha256": random_state,
            "historical_memory_implementation": {"candidate_and_random_use_identical_builder": True}},
        "job_id": "fixture", "elapsed_seconds": 123., "gpu_peak_allocated_bytes": 200000,
        "wandb_history_independently_verified": False, "code_sha": "e"*40}
    for label in ("candidate", "reference"):
        for dataset in report.DATASETS:
            result["h0_caches"][label+"/"+dataset] = {"targets_cached": False, "molecules": 2, "atoms": 10,
                "DO_NOT_EXPORT_MEMBER_ID": "PRIVATE_NATIVE_UID", "binding": {"dimension": 384,
                    "architecture_sha256": architecture, "membership_sha256": "m"*64, "geometry_sha256": "g"*64,
                    "packing_budget_sha256": "q"*64, "packing_plan_sha256": "p"*64,
                    "effective_runtime_sha256": "r"*64, "encoder_sha256": state if label == "candidate" else random_state}}
    all_tasks = {}
    for method in sorted(verify.READOUTS):
        cells = {}
        for task in sorted(verify.TASKS):
            error = 1.2 if task in ("cyp.2D6", "qm9.U0", "qm9.alpha") and method == "ridge" else .8
            score = 1-error
            cells[task+"@"+method] = {"error": error, "reference_error": 1., "normalized_improvement": score,
                "bootstrap_ci": [score-.1, score+.1], "bootstrap_defined": 1000,
                "observed_labels": 50, "observed_molecules": 2}
        result["summaries"][method] = {"architecture_sha256": architecture, "complete": True,
            "bootstrap_samples": 1000, "bootstrap_defined": 1000, "bootstrap_unit": "molecule",
            "bootstrap_seed": 20261025, "bootstrap_ci": [-.1, .3], "tasks": cells,
            "mean_normalized_improvement": sum(c["normalized_improvement"] for c in cells.values())/9}
        all_tasks.update(cells)
    result["summaries"]["primary_18_cells"] = {**deepcopy(result["summaries"]["ridge"]), "tasks": deepcopy(all_tasks),
        "mean_normalized_improvement": sum(c["normalized_improvement"] for c in all_tasks.values())/18}
    guard = {"status": "COMPLETED", "child_returncode": 0, "preregistration_sha": verify.PREREGISTRATION,
        "inclusive_panel_wall_seconds": 124., "inclusive_one_GPU_hour_target_met": True}
    return result, guard, request, panel


def test_report_keeps_eighteen_cells_negative_ridge_and_memory_scope():
    result, guard, request, panel = panel_fixture()
    rows = report.validate_panel(result, guard, request, panel)
    assert len(rows) == 18
    assert len([row for row in rows if row["normalized_improvement"] < 0]) == 3
    text = report.make_markdown(result, guard, rows, {"status": "PENDING"})
    assert "qm9.U0@ridge" in text and "qm9.alpha@ridge" in text and "cyp.2D6@ridge" in text
    assert "not device-global" in text and "512-dimensional" in text and "single pretraining seed" in text
    assert "PRIVATE_NATIVE_UID" not in text and "PRIVATE_NATIVE_UID" not in json.dumps(rows)
    assert result["wandb_history_independently_verified"] is False


def test_single_run_csv_passes_existing_typed_summary_checker(tmp_path):
    result, guard, request, _ = panel_fixture()
    request["run_id"] = "B3_fixture"
    result.update(data_version="selectedTRAIN-fixture", gpu_model="NVIDIA RTX 5090",
        gpu_uuid="GPU-12345678-1234-1234-1234-123456789abc")
    row = report.run_summary(result, guard, request, {"sha256": "f"*64}, {"independently_verified": False})
    destination = tmp_path / "run_summary.csv"
    report.write_csv(destination, [row])
    checker = Path(os.environ.get("SA3_REPOSITORY_CHECKER", str(Path(__file__).resolve().parents[3]
        / "MFM_model_v3_sa3/tools/check_repository.py")))
    spec = importlib.util.spec_from_file_location("readonly_existing_typed_csv_checker", checker)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert module.model_summary_csv("docs/model_v3/results/B3_fixture.csv", destination.read_bytes())
    assert "member" not in destination.read_text().lower()


@pytest.mark.parametrize("drift", ("random_membership", "random_geometry", "random_state", "dimension", "bootstrap", "cell"))
def test_report_rejects_unmatched_or_incomplete_panel(drift):
    result, guard, request, panel = panel_fixture()
    cache = result["h0_caches"]["reference/qm9"]["binding"]
    if drift == "random_membership": cache["membership_sha256"] = "other"
    elif drift == "random_geometry": cache["geometry_sha256"] = "other"
    elif drift == "random_state": cache["encoder_sha256"] = "other"
    elif drift == "dimension": result["encoder_pair"]["H0_dimension"] = 512
    elif drift == "bootstrap": result["summaries"]["ridge"]["bootstrap_samples"] = 999
    elif drift == "cell": result["summaries"]["ridge"]["tasks"].pop("qm9.U0@ridge")
    with pytest.raises(ValueError):
        report.validate_panel(result, guard, request, panel)


def test_core_false_flag_needs_separate_successful_matching_certificate():
    result = {"wandb_history_independently_verified": False, "wandb_run_id": "fixture", "journal_records": 2}
    refs = {key: {"path": "/fixture/"+key, "sha256": key} for key in ("result", "guard", "request")}
    assert report.verification_state(None, None, refs, result)["independently_verified"] is False
    cert = {"schema": "model_v3_B3_native_history_verification_v2", "status": "VERIFIED",
        "wandb_history_independently_verified": True, "inputs": refs, "sdk_run_id": "fixture",
        "history_rows": 2, "native_records": 10, "sdk_exit_code": 0, "clean_eof": True}
    state = report.verification_state(cert, {"path": "/fixture/certificate"}, refs, result)
    assert state["independently_verified"] is True and result["wandb_history_independently_verified"] is False
    cert["inputs"] = deepcopy(refs); cert["inputs"]["request"]["sha256"] = "wrong"
    with pytest.raises(ValueError, match="another input"):
        report.verification_state(cert, {}, refs, result)
