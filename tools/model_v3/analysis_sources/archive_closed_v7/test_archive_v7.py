"""Bounded native-reader, exact mirror and recovery/index regression tests."""
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import bounded_history_v7 as reader
from archive_closed_runs_v7 import merge_entries, validate_lineage


def native_records(rows=None, *, run_id="unitrun0", exit_code=0, ancillary=0):
    from wandb.proto import wandb_internal_pb2 as pb
    first = pb.Record(); first.run.run_id = run_id
    yield first
    for _ in range(ancillary):
        metric = pb.Record(); metric.metric.name = "unit_metric"
        yield metric
    for row in (sample_rows() if rows is None else rows):
        record = pb.Record()
        for key, value in {"_step": row["step"], **row["row"]}.items():
            item = record.history.item.add(); item.key = key; item.value_json = json.dumps(value)
        yield record
    if exit_code is not None:
        final = pb.Record(); final.exit.exit_code = exit_code
        yield final


def sample_rows():
    return [{"step": 6, "commit": True, "row": {"event": "VALIDATION", "fields": {"noise": {"loss": .125, "count": 2, "valid": True, "R2": None}}, "lr": [.0003]}},
            {"step": 7, "commit": True, "row": {"event": "TRAIN_STEP", "loss/total": .25, "samples": 8}}]


def compare(records=None, mirrors=None, **kwargs):
    from wandb.proto import wandb_internal_pb2 as pb
    class Stream:
        def __init__(self):
            self.rows = iter(native_records() if records is None else records)
        def scan_data(self):
            item = next(self.rows, None)
            return None if item is None else item.SerializeToString()
    output = io.BytesIO()
    rows = sample_rows() if mirrors is None else mirrors
    source = io.BytesIO(b"".join(reader.encoded(row) for row in rows))
    defaults = dict(expected_run_id="unitrun0", expected_exit=0, expected_rows=len(rows),
                    mirror_factory=lambda config: reader.mirror_rows(source, "precision"))
    defaults.update(kwargs)
    return reader.verify_stream(Stream(), pb.Record, output, **defaults)


def test_nested_native_keys_and_exact_source_numeric_types():
    records = list(native_records())
    history = records[1]
    field = history.history.item[2]
    assert field.key == "fields"
    del history.history.item[2]
    for name, value in {"loss": .125, "count": 2., "valid": True, "R2": None}.items():
        item = history.history.item.add(); item.nested_key.extend(("fields", "noise", name)); item.value_json = json.dumps(value)
    result = compare(records)
    assert result["native_closed"] is True and result["history_rows"] == 2
    assert result["first_explicit_step"] == 6 and result["last_explicit_step"] == 7


@pytest.mark.parametrize("corruption", ("missing", "extra", "duplicate", "step", "boolean", "NaN", "overflow", "uncommitted", "run", "exit"))
def test_rejects_scientific_payload_step_identity_and_commit_corruption(corruption):
    records, mirrors = list(native_records()), sample_rows()
    history = records[1].history
    if corruption == "missing":
        del history.item[-1]
    elif corruption == "extra":
        item = history.item.add(); item.key = "undeclared_scientific"; item.value_json = "1"
    elif corruption == "duplicate":
        duplicate = deepcopy(history.item[-1])
        history.item.add().CopyFrom(duplicate)
    elif corruption == "step":
        history.item[0].value_json = "5"
    elif corruption == "boolean":
        history.item[2].value_json = '{"noise":{"loss":0.125,"count":2,"valid":1,"R2":null}}'
    elif corruption in ("NaN", "overflow"):
        history.item[-1].value_json = "NaN" if corruption == "NaN" else "1e309"
    elif corruption == "uncommitted":
        mirrors[0]["commit"] = False
    elif corruption == "run":
        records[0].run.run_id = "other_id"
    else:
        records[-1].exit.exit_code = 1
    with pytest.raises(ValueError):
        compare(records, mirrors)


def test_packet_and_committed_history_budgets_are_independent_and_never_truncate():
    result = compare(native_records(ancillary=50001), max_native_records=50005, max_history_rows=2)
    assert result["native_packets"] == 50005 and result["history_rows"] == 2 and result["clean_eof"]
    with pytest.raises(reader.BudgetError, match="packet budget"):
        compare(native_records(ancillary=7), max_native_records=7)
    with pytest.raises(reader.BudgetError, match="committed-history"):
        compare(max_history_rows=1)
    with pytest.raises(reader.BudgetError, match="export byte"):
        compare(max_export_bytes=10)
    with pytest.raises(reader.BudgetError, match="wall budget"):
        compare(deadline=time.monotonic()-1)
    with pytest.raises(reader.BudgetError, match="record byte"):
        compare(max_record_bytes=1)


def test_failed_zero_history_preserves_missing_exit_without_claiming_completion():
    from wandb.proto import wandb_internal_pb2 as pb
    first = pb.Record(); first.run.run_id = "unitrun0"
    result = compare([first], [], expected_exit=None, allow_incomplete=True)
    assert result["history_rows"] == 0 and result["sdk_exit_codes"] == []
    assert result["native_closed"] is False and result["status"] == "FAILED_RAW_SDK_PRESERVED_INCOMPLETE"
    with pytest.raises(ValueError, match="clean EOF/runID/exit"):
        compare([first], [], expected_exit=0)


def test_failed_decode_is_preserved_but_budget_exhaustion_never_becomes_clean_eof():
    from wandb.proto import wandb_internal_pb2 as pb
    first = pb.Record(); first.run.run_id = "unitrun0"
    class Broken:
        calls = 0
        def scan_data(self):
            self.calls += 1
            if self.calls == 1:
                return first.SerializeToString()
            raise EOFError("unit incomplete SDK tail")
    result = reader.verify_stream(Broken(), pb.Record, io.BytesIO(), expected_run_id="unitrun0", expected_exit=None,
        expected_rows=0, mirror_factory=lambda config: iter(()), allow_incomplete=True)
    assert result["clean_eof"] is False and result["native_closed"] is False and result["decode_error"].startswith("EOFError")
    with pytest.raises(reader.BudgetError, match="packet budget"):
        compare(native_records(ancillary=7), max_native_records=1, allow_incomplete=True, expected_exit=None)


def test_framing_duplicate_json_and_overlapping_native_keys_rejected():
    with pytest.raises(ValueError, match="Duplicate JSON"):
        reader.strict_json('{"step":0,"step":1}')
    with pytest.raises(ValueError, match="Truncated"):
        list(reader.mirror_rows(io.BytesIO(b'{"step":0,"row":{"x":1},"commit":true}'), "precision"))
    rows = sample_rows(); rows[1]["step"] = 6
    with pytest.raises(ValueError, match="Duplicate, missing"):
        compare(mirrors=rows)
    records = list(native_records())
    duplicate = records[1].history.item.add()
    duplicate.key = "fields/noise/loss"; duplicate.value_json = "0.125"
    with pytest.raises(ValueError, match="Duplicate or overlapping"):
        compare(records)


def test_native_uncommitted_partial_history_is_not_a_committed_row():
    from wandb.proto import wandb_internal_pb2 as pb
    partial = pb.Record()
    item = partial.request.partial_history.item.add(); item.key = "loss"; item.value_json = "1"
    records = list(native_records()); records.insert(1, partial)
    with pytest.raises(ValueError, match="Uncommitted native"):
        compare(records)


def test_real_offline_sdk_nested_mirror_roundtrip(tmp_path, monkeypatch):
    import wandb
    monkeypatch.setenv("WANDB_MODE", "offline")
    monkeypatch.setenv("WANDB_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("WANDB_DATA_DIR", str(tmp_path / "wandb_data"))
    run = wandb.init(project="model_v3_archive_v7_unit", mode="offline", dir=str(tmp_path))
    run_id = run.id
    for row in sample_rows():
        run.log(row["row"], step=row["step"], commit=True)
    run.finish(exit_code=0)
    paths = list((tmp_path / "wandb").glob("offline-run-*/run-*.wandb"))
    assert len(paths) == 1
    source = io.BytesIO(b"".join(reader.encoded(row) for row in sample_rows()))
    result = reader.verify_file(paths[0], io.BytesIO(), expected_run_id=run_id, expected_exit=0, expected_rows=2,
        mirror_factory=lambda config: reader.mirror_rows(source, "precision"))
    assert result["history_rows"] == 2 and result["native_packets"] > 2 and result["clean_eof"] and result["native_closed"]


def test_existing_index_entries_preserved_and_identity_dedup_is_strict():
    old = [{"job_id": "old", "run_id": "oldid", "path": "legacy/path", "unknown": {"keep": True}}]
    new = {"job_id": "new", "run_id": "newid", "path": "new/path"}
    result = merge_entries(old, [new, new])
    assert result == [*old, new] and old[0]["unknown"] == {"keep": True}
    with pytest.raises(ValueError, match="different target"):
        merge_entries(result, [{**new, "path": "wrong/path"}])


def lineage_fixture():
    tracker = {"id": "parent", "mode": "offline"}
    parent = {"input_kind": "synthetic", "scientific_acceptance": False, "contract": {"bound": "same"},
        "tracker": tracker, "optimizer_updates": 2, "samples_consumed": 4, "validation": {"0": {"bound": 0}, "2": {"bound": 2}}}
    child = {**deepcopy(parent), "tracker": {"id": "child", "mode": "offline"}, "resume_parent_tracker": tracker,
        "parent_checkpoint": {"sha256": "a"*64}, "optimizer_updates": 4, "samples_consumed": 8,
        "validation": {**parent["validation"], "4": {"bound": 4}}}
    first, second = [], []
    for step, update, event, samples in ((0,0,"VALIDATION",0),(1,0,"VALIDATION",0),(2,1,"TRAIN_STEP",2),(3,2,"TRAIN_STEP",4),(4,2,"VALIDATION",4),(5,2,"VALIDATION",4),
                                       (6,3,"TRAIN_STEP",6),(7,4,"TRAIN_STEP",8),(8,4,"VALIDATION",8),(9,4,"VALIDATION",8)):
        row = {"step": step, "commit": True, "row": {"log_cursor": step, "event": event, "optimizer_updates": update,
            "samples_consumed": samples, "sample_ordinals": list(range(samples-2,samples)) if event == "TRAIN_STEP" else []}}
        if step >= 6:
            row["row"]["resume_parent_run_id"] = "parent"
        (first if step < 6 else second).append(row)
    state = {"optimizer_updates":2,"samples_consumed":4,"log_cursor":6,"points":parent["validation"]}
    return parent, child, first, second, state, {"optimizer_updates":2,"samples_consumed":4}


@pytest.mark.parametrize("corruption", (None, "parent", "cursor", "sample", "zero_replay", "uncommitted"))
def test_lineage_certificate_rejects_clock_parent_sample_and_replay_errors(corruption):
    values = lineage_fixture()
    if corruption == "parent":
        values[1]["resume_parent_tracker"]["id"] = "wrong"
        # deepcopy prevents a shared fixture object from changing both sides.
        values[0]["tracker"] = {"id":"parent", "mode":"offline"}
    elif corruption == "cursor":
        values[3][0]["step"] = 5
    elif corruption == "sample":
        values[3][0]["row"]["sample_ordinals"] = [3, 5]
    elif corruption == "zero_replay":
        values[3][-1]["row"]["optimizer_updates"] = 0
    elif corruption == "uncommitted":
        values[3][0]["commit"] = False
    if corruption is None:
        result = validate_lineage(*values)
        assert result["sample_ordinals"] == list(range(8)) and result["saved_zero_validation_not_replayed"]
    else:
        with pytest.raises(ValueError):
            validate_lineage(*values)
