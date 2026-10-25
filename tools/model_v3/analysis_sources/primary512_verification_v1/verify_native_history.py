"""Read-only native W&B scan; compare every declared panel scalar to its journal.

No model, source store, targets, predictions or network API is opened. The SDK
reader is independent of the evaluator/journal writer. Originals are retained.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import inspect
import json
import math
import os
from pathlib import Path
import re
import stat
import time
from primary512_scope import (EVALUATOR_CODE, RUN_NAME, MAX_CHECKPOINT_BYTES, read_source_chain, timing_observation)

PREREGISTRATION = "39cf4929299cd227a3c361183a4b26c8b1405900"
TASKS = frozenset(("cyp.3A4", "cyp.2D6", "exp.LogD", "exp.LogS",
    "exp.Log_HLM_CLint", "qm9.U0", "qm9.homo", "qm9.lumo", "qm9.alpha"))
READOUTS = frozenset(("ridge", "linear64_relu"))
MAX_SOURCE_BYTES = 128 << 20
MAX_JOURNAL_BYTES = 32 << 20
MAX_OUTPUT_BYTES = 64 << 20
MAX_NATIVE_RECORDS = 500000
MAX_HISTORY_ROWS = 100000
MAX_RECORD_BYTES = 4 << 20
MAX_JSON_LINE_BYTES = 32768
MAX_WALL_SECONDS = 180
METRIC = re.compile(r"(candidate|reference)/([^/@]+)@(ridge|linear64_relu)/(validation_error|readout/(?:loss|epoch|observed_labels|update))\Z")


class CompactHistorySink:
    """Compare/hash the complete stream without exporting per-update rows."""
    def write(self, raw):
        return len(raw)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("Non-finite JSON constant")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)+"\n").encode()


def ordinary(path, limit):
    path = Path(path).absolute()
    require(".." not in path.parts, "Parent traversal is not allowed")
    for ancestor in (path, *path.parents):
        require(not ancestor.is_symlink(), "Input/output ancestors must be physical paths")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
            "An ordinary, singly linked immutable input is required")
    require(info.st_size <= limit, "Input exceeds its declared byte bound")
    if hasattr(os, "getuid"):
        require(info.st_uid == os.getuid(), "Input belongs to another account")
    return path


def binding(path, limit=MAX_SOURCE_BYTES):
    path = ordinary(path, limit)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "Input changed during hashing")
    return {"path": str(path), "bytes": before.st_size, "sha256": digest.hexdigest()}


def bound_json(path, expected_sha, limit=8 << 20):
    require(re.fullmatch(r"[a-f0-9]{64}", expected_sha or ""), "A machine-computed SHA256 is required")
    item = binding(path, limit)
    require(item["sha256"] == expected_sha, "Bound input bytes differ")
    raw = Path(item["path"]).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == expected_sha, "Input changed before JSON decode")
    return strict_json(raw), item


def check_admission(receipt, result):
    require(receipt.get("schema") == "model_v3_primary512_metadata_admission_v1", "Root primary512 metadata admission receipt required")
    job = receipt["evaluation_job"]
    require(str(job["job_id"]) == str(result["job_id"]) and job["state"] == "COMPLETED"
        and job["exit_code"] == "0:0", "Successful terminal evaluation receipt required")
    require(type(job["elapsed_seconds"]) is int and job["elapsed_seconds"] >= 0, "Observed Slurm ElapsedRaw integer required")
    require("evaluation_supervisor" in receipt and "launch_spec" in receipt, "Actual supervisor/spec admission bindings required")
    admission = receipt["verification_admission"]
    require(admission["network_access"] is False and admission["gpu_requested"] is False,
            "This tool is CPU-only and offline")
    require(admission["max_output_bytes"] == MAX_OUTPUT_BYTES
        and admission["max_source_bytes"] == MAX_SOURCE_BYTES
        and admission["max_native_records"] == MAX_NATIVE_RECORDS
        and admission["max_history_rows"] == MAX_HISTORY_ROWS
        and admission["max_wall_seconds"] == MAX_WALL_SECONDS, "Reviewed metadata bounds differ")
    quota = admission["quota"]
    for field in ("free_bytes", "active_job_reserved_bytes", "reserved_headroom_bytes"):
        require(type(quota[field]) is int and quota[field] >= 0, "Invalid quota receipt")
    require(quota["reserved_headroom_bytes"] >= 32 << 30
        and quota["free_bytes"]-quota["active_job_reserved_bytes"]-quota["reserved_headroom_bytes"] >= MAX_OUTPUT_BYTES,
        "Quota headroom does not cover this bounded new export")
    observed = datetime.fromisoformat(quota["observed_at_utc"].replace("Z", "+00:00"))
    require(observed.utcoffset() is not None, "Quota timestamp must include its UTC offset")
    age = (datetime.now(timezone.utc)-observed).total_seconds()
    require(-60 <= age <= 3600, "Quota receipt must be at most one hour old")


def scalar(key, value):
    match = METRIC.fullmatch(key)
    require(match is not None and match[2] in TASKS, "Undeclared SDK/journal scientific history key")
    require(not (match[3] == "ridge" and match[4] != "validation_error"), "Ridge history schema differs")
    require(not (match[3] == "linear64_relu" and match[4] == "validation_error"), "Linear readout history schema differs")
    require(type(value) in (int, float) and math.isfinite(value), "Finite numeric panel scalar required")
    if match[4] in ("readout/epoch", "readout/observed_labels", "readout/update"):
        require(value >= 0 and int(value) == value, "Readout counters must be nonnegative integers")
        return int(value)
    require(value >= 0, "Panel loss/error must be nonnegative")
    return float(value)


def normalized(row, expected_step):
    require(type(row) is dict and type(row.get("step")) is int and row["step"] == expected_step,
        "History step is missing, duplicated or out of order")
    metrics = {key: scalar(key, value) for key, value in row.items() if key != "step"}
    require(len(metrics) in (1, 4), "Unexpected number of history scalars")
    prefixes = {key.rsplit("/readout/", 1)[0] if "/readout/" in key else key.rsplit("/", 1)[0] for key in metrics}
    require(len(prefixes) == 1, "A history row spans multiple scopes")
    if len(metrics) == 1:
        require(next(iter(metrics)).endswith("/validation_error"), "Expected one ridge validation scalar")
    else:
        require({key.rsplit("/", 1)[1] for key in metrics} == {"loss", "epoch", "observed_labels", "update"},
            "Incomplete readout update")
    return {"step": expected_step, **metrics}


def journal_rows(stream):
    for step in range(MAX_HISTORY_ROWS):
        raw = stream.readline(MAX_JSON_LINE_BYTES+1)
        if not raw:
            return
        require(raw.endswith(b"\n") and len(raw) <= MAX_JSON_LINE_BYTES, "Truncated/oversized journal line")
        yield normalized(strict_json(raw), step)
    require(not stream.read(1), "Journal exceeds the record budget")


def keyed_items(items):
    result = {}
    for item in items:
        key = item.key or "/".join(item.nested_key)
        require(key and key not in result, "Duplicate or empty native SDK key")
        result[key] = item.value_json
    return result


def apply_items(destination, record):
    destination.update(keyed_items(record.update))
    for item in getattr(record, "remove", ()):
        key = item.key or "/".join(item.nested_key)
        destination.pop(key, None)


def scan_records(data, record_class, *, deadline):
    for ordinal in range(MAX_NATIVE_RECORDS+1):
        require(time.monotonic() <= deadline, "Native SDK verification wall budget exhausted")
        raw = data.scan_data()
        if raw is None:
            return
        require(ordinal < MAX_NATIVE_RECORDS, "Native SDK total-record budget exhausted before EOF")
        require(len(raw) <= MAX_RECORD_BYTES, "Native SDK record is too large")
        record = record_class()
        record.ParseFromString(raw)
        yield record


def compare_records(records, journal, destination, *, expected_run_id, expected_config,
                    expected_summary, expected_rows, expected_display_name=None, budget_bytes=MAX_OUTPUT_BYTES):
    """Pure streamed comparison; tests also exercise a real SDK DataStore reader."""
    journal = iter(journal)
    counts, types, series = Counter(), Counter(), {}
    config, summary, run_ids, run_names, exits = {}, {}, [], [], []
    digest = hashlib.sha256()
    output_bytes, history_rows = 0, 0
    for record in records:
        counts["native_records"] += 1
        kind = record.WhichOneof("record_type")
        types[kind or "none"] += 1
        if kind == "run":
            run_ids.append(record.run.run_id)
            run_names.append(record.run.display_name)
            apply_items(config, record.run.config)
        if kind == "config":
            apply_items(config, record.config)
        if kind == "summary":
            apply_items(summary, record.summary)
        if kind == "exit":
            exits.append(int(record.exit.exit_code))
        if kind != "history":
            continue
        require(history_rows < MAX_HISTORY_ROWS, "Native SDK history-row budget exhausted")
        values = keyed_items(record.history.item)
        require("_step" in values, "Native SDK history lacks explicit _step")
        sdk_step = strict_json(values.pop("_step"))
        require(type(sdk_step) is int, "Native SDK _step must be an integer")
        for key in tuple(values):
            if key.startswith("_"):
                require(key in {"_timestamp", "_runtime", "_wandb"}, "Unexpected SDK internal history field")
                values.pop(key)
        native = normalized({"step": sdk_step, **{key: strict_json(raw) for key, raw in values.items()}}, history_rows)
        expected = next(journal, None)
        require(expected is not None and native == expected, "Native SDK and journal scientific payload/step differ")
        raw = encoded(native)
        output_bytes += len(raw)
        require(output_bytes <= budget_bytes, "Bounded history export exhausted its byte budget")
        destination.write(raw)
        digest.update(raw)
        for key, value in native.items():
            if key == "step":
                continue
            item = series.setdefault(key, {"count": 0, "first_step": sdk_step, "first": value,
                                          "minimum": value, "maximum": value})
            item.update(count=item["count"]+1, last_step=sdk_step, last=value,
                        minimum=min(item["minimum"], value), maximum=max(item["maximum"], value))
        history_rows += 1
    require(next(journal, None) is None and history_rows == expected_rows,
        "Native SDK/journal/result history counts differ")
    require(run_ids == [expected_run_id] and exits == [0], "SDK run identity or successful native exit differs")
    require(expected_display_name is None or run_names == [expected_display_name], "SDK declared run name differs")
    for key, value in expected_config.items():
        require(key in config and strict_json(config[key]) == value, "SDK initial config binding differs: "+key)
    for key, value in expected_summary.items():
        require(key in summary and strict_json(summary[key]) == value, "SDK final summary differs: "+key)
    return {"native_records": counts["native_records"], "record_types": dict(types),
        "history_rows": history_rows, "normalized_history_bytes": output_bytes,
        "normalized_history_sha256": digest.hexdigest(), "series": series,
        "sdk_run_id": expected_run_id, "sdk_exit_code": 0, "clean_eof": True}


def check_result_guard(result, guard, request, result_ref, request_ref):
    require(result["schema"] == "model_v3_dev_evaluation_result_v1" and result["status"] == "COMPLETED"
        and guard["status"] == "COMPLETED" and guard["child_returncode"] == 0,
        "Successful panel and external guard required")
    require(result["reference_kind"] == request["reference_kind"] == "primary"
        and result["encoder_pair"]["H0_dimension"] == 512 and request["run_id"] == RUN_NAME
        and result["code_sha"] == request["code_sha"] == EVALUATOR_CODE,
        "This certificate is restricted to the frozen A00 short500 primary512 panel")
    require(result["preregistration_sha"] == guard["preregistration_sha"] == request["preregistration_sha"] == PREREGISTRATION,
        "Published panel preregistration differs")
    require(guard["result"] == result_ref, "Guard's result raw-byte binding differs")
    require(result["request_sha256"] == guard["request_sha256"] == request_ref["sha256"], "Actual request binding differs")
    for key in ("code_sha", "job_id", "gpu_uuid"):
        require(result[key] == guard[key], "Core/guard identity differs: "+key)
    for key in ("code_sha", "data_version", "architecture_sha256", "pretraining_seed"):
        require(result[key] == request[key], "Core/request identity differs: "+key)
    require(type(result["journal_records"]) is int and 0 < result["journal_records"] < MAX_HISTORY_ROWS,
        "Result history count exceeds verification bounds")
    require(guard["child_runtime"]["policy_unchanged"] is True, "Execution precision policy drifted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("result", "guard", "request", "admission", "launch_spec"):
        parser.add_argument("--"+name.replace("_", "-"), type=Path, required=True)
        parser.add_argument("--"+name.replace("_", "-")+"-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True, help="Fresh model-owned external directory")
    args = parser.parse_args()
    started = time.monotonic()
    inputs = {}
    refs = {}
    for name in ("result", "guard", "request", "admission", "launch_spec"):
        inputs[name], refs[name] = bound_json(getattr(args, name), getattr(args, name+"_sha256"))
    refs["scope_implementation"] = binding(Path(__file__).with_name("primary512_scope.py"), 2 << 20)
    result, guard, request = (inputs[name] for name in ("result", "guard", "request"))
    check_result_guard(result, guard, request, refs["result"], refs["request"])
    check_admission(inputs["admission"], result)
    source_scope = read_source_chain(result, guard, request, inputs["launch_spec"], inputs["admission"], refs,
        binding=binding, bound_json=bound_json)
    output = args.output.absolute()
    require(not output.exists() and ".." not in output.parts, "A fresh output directory is required")
    require(output.is_relative_to(Path(__file__).absolute().parent), "Keep exports in this new model-owned verification directory")
    for ancestor in output.parents:
        require(not ancestor.is_symlink(), "Output ancestors must be physical")
    evaluation = Path(refs["result"]["path"]).parent
    require(not output.is_relative_to(evaluation), "Verification must not write into SDK/evaluation originals")
    require(len(guard["SDK_files"]) == 1, "Exactly one native SDK stream is expected")
    sdk_ref = guard["SDK_files"][0]
    sdk_path = Path(sdk_ref["path"]).absolute()
    require(sdk_path.is_relative_to(evaluation / "wandb") and sdk_path.name == "run-"+result["wandb_run_id"]+".wandb",
        "Guard SDK file is outside the declared evaluation run")
    require(binding(sdk_path) == sdk_ref, "Native SDK bytes differ from terminal guard")
    refs["sdk"] = sdk_ref
    refs["journal"] = binding(evaluation / "history.jsonl", MAX_JOURNAL_BYTES)
    # No wandb.init/API/login/sync is called. DataStore opens its file for scan.
    from wandb.proto import wandb_internal_pb2
    from wandb.sdk.internal.datastore import DataStore
    reader_source = Path(inspect.getsourcefile(DataStore))
    reader_binding = binding(reader_source, 2 << 20)
    output.mkdir(parents=True, exist_ok=False)
    expected_config = {key: request[key] for key in ("code_sha", "preregistration_sha", "data_version",
        "architecture_sha256", "pretraining_seed")}
    expected_config.update(request_sha256=refs["request"]["sha256"], job_id=result["job_id"],
        gpu_uuid=result["gpu_uuid"], panel_sha256=result["panel_sha256"],
        random_reference_initialization_seed=result["random_reference_initialization_seed"], readout_seed=result["readout_seed"])
    expected_summary = {"evaluation_status": "COMPLETED",
        "dev_primary_score": result["summaries"]["primary_18_cells"]["mean_normalized_improvement"]}
    data = DataStore()
    try:
        data.open_for_scan(str(sdk_path))
        with Path(refs["journal"]["path"]).open("rb") as journal:
            details = compare_records(scan_records(data, wandb_internal_pb2.Record,
                deadline=started+MAX_WALL_SECONDS), journal_rows(journal), CompactHistorySink(),
                expected_run_id=result["wandb_run_id"], expected_config=expected_config,
                expected_summary=expected_summary, expected_rows=result["journal_records"], expected_display_name=request["run_id"],
                budget_bytes=MAX_OUTPUT_BYTES-(2 << 20))
    finally:
        data.close()
    for name, ref in refs.items():
        limit = MAX_CHECKPOINT_BYTES if name == "export_checkpoint" else MAX_JOURNAL_BYTES if name == "journal" else MAX_SOURCE_BYTES
        require(binding(ref["path"], limit) == ref,
            "Read-only source changed during independent verification: "+name)
    require(binding(reader_source, 2 << 20) == reader_binding, "SDK reader source changed while scanning")
    require(time.monotonic()-started <= MAX_WALL_SECONDS, "Verification wall budget exhausted")
    certificate = {"schema": "model_v3_primary512_native_history_verification_v1", "status": "VERIFIED",
        "wandb_history_independently_verified": True, "original_result_was_not_modified": True,
        "original_core_verification_flag": result["wandb_history_independently_verified"],
        "comparison": "every declared scientific scalar and explicit global step; clean native SDK EOF, run/config/summary/exit",
        "reference_kind": "primary", "H0_dimension": 512, "layers": 6, "run_name": RUN_NAME,
        "source_scope": source_scope, "formal_pretraining_complete": False, "architecture_selection_claimed": False,
        **timing_observation(guard, inputs["admission"]),
        "evaluation_job_id": result["job_id"], "inputs": refs,
        "verifier_implementation": binding(__file__, 2 << 20),
        "sdk_reader": {"version": importlib.metadata.version("wandb"), "DataStore": reader_binding,
            "protobuf_version": importlib.metadata.version("protobuf"),
            "Record_schema_sha256": hashlib.sha256(wandb_internal_pb2.Record.DESCRIPTOR.file.serialized_pb).hexdigest()},
        "elapsed_seconds": time.monotonic()-started, "budget": {
            "max_native_records": MAX_NATIVE_RECORDS, "max_history_rows": MAX_HISTORY_ROWS,
            "max_sdk_bytes": MAX_SOURCE_BYTES,
            "max_output_bytes": MAX_OUTPUT_BYTES, "max_wall_seconds": MAX_WALL_SECONDS},
        "downstream_target_records_opened": 0, "member_ids_or_predictions_exported": False,
        "full_history_exported": False, "history_payload_scope": "all rows compared and canonical stream hashed; compact series statistics only",
        **details}
    raw = encoded(certificate)
    require(len(raw)+details["normalized_history_bytes"] <= MAX_OUTPUT_BYTES, "Certificate exceeds export budget")
    with (output / "verification.json").open("xb") as stream:
        stream.write(raw); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps({"status": "VERIFIED", "history_rows": details["history_rows"],
        "native_records": details["native_records"], "output": str(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
