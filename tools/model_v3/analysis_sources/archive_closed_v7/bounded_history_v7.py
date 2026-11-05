"""Bounded native SDK/mirror comparison. No network, model or target access."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import time

MAX_NATIVE_RECORDS = 500000
MAX_HISTORY_ROWS = 100000
MAX_RECORD_BYTES = 4 << 20
MAX_LINE_BYTES = 65536
MAX_EXPORT_BYTES = 64 << 20


def require(condition, message):
    if not condition:
        raise ValueError(message)


class BudgetError(ValueError):
    pass


def strict_json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    def nonfinite(value):
        raise ValueError("Illegal nonfinite JSON constant: " + value)
    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    def finite(item):
        if type(item) is float:
            require(math.isfinite(item), "Illegal nonfinite JSON number")
        elif type(item) is dict:
            for child in item.values():
                finite(child)
        elif type(item) is list:
            for child in item:
                finite(child)
    finite(value)
    return value


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def flatten(value, *, prefix="", destination=None):
    result = {} if destination is None else destination
    if type(value) is dict and value:
        for key, item in value.items():
            require(type(key) is str and key, "Empty/non-string scientific key")
            flatten(item, prefix=(prefix + "/" if prefix else "") + key, destination=result)
    else:
        require(prefix and prefix not in result and not any(key.startswith(prefix + "/") or prefix.startswith(key + "/") for key in result),
                "Duplicate or overlapping flattened scientific key")
        result[prefix] = value
    return result


def native_items(items):
    result = {}
    for item in items:
        require(not (item.key and item.nested_key), "Ambiguous native key/nested_key")
        key = item.key or "/".join(item.nested_key)
        require(key, "Empty native history key")
        flatten(strict_json(item.value_json), prefix=key, destination=result)
    return result


def typed_like(native, expected):
    """Restore source JSON numeric types without any numerical tolerance."""
    if type(expected) is bool:
        require(type(native) is bool and native is expected, "Boolean scientific value differs")
    elif type(expected) is int:
        require(type(native) in (int, float) and math.isfinite(native) and native == expected
                and (type(native) is int or abs(native) <= 2**53), "Integer scientific value differs")
        return int(native)
    elif type(expected) is float:
        require(type(native) in (int, float) and math.isfinite(native) and float(native) == expected,
                "Floating scientific value differs")
        return float(native)
    elif type(expected) is list:
        require(type(native) is list and len(native) == len(expected), "Scientific list shape differs")
        return [typed_like(a, b) for a, b in zip(native, expected)]
    elif type(expected) is dict:
        require(type(native) is dict and set(native) == set(expected), "Scientific object keys differ")
        return {key: typed_like(native[key], value) for key, value in expected.items()}
    else:
        require(type(native) is type(expected) and native == expected, "Scientific value/type differs")
    return expected


def mirror_rows(stream, kind, *, max_rows=MAX_HISTORY_ROWS):
    previous = None
    for ordinal in range(max_rows + 1):
        raw = stream.readline(MAX_LINE_BYTES + 1)
        if not raw:
            return
        if ordinal == max_rows:
            raise BudgetError("Mirror history-row budget exhausted")
        require(raw.endswith(b"\n") and len(raw) <= MAX_LINE_BYTES, "Truncated/oversized mirror line")
        row = strict_json(raw)
        if kind == "A_plain":
            step, payload = row.get("optimizer_updates"), row
        else:
            require(type(row) is dict and set(row) <= {"step", "row", "commit"} and {"step", "row"} <= set(row),
                    "Malformed mirror envelope")
            require(row.get("commit", kind == "optimizer") is True, "Uncommitted mirror row")
            step, payload = row["step"], row["row"]
        require(type(step) is int and step >= 0 and (previous is None or step == previous + 1),
                "Duplicate, missing or unordered explicit mirror step")
        require(type(payload) is dict and payload and not any(key.startswith("_") for key in payload), "Scientific mirror payload required")
        previous = step
        yield {"step": step, "row": flatten(payload)}


def _apply_config(destination, update):
    for item in update.update:
        key = item.key or "/".join(item.nested_key)
        if key == "paired_role":
            destination[key] = strict_json(item.value_json)
    for item in update.remove:
        destination.pop(item.key or "/".join(item.nested_key), None)


def verify_stream(data, record_class, destination, *, expected_run_id, expected_exit, expected_rows,
                  mirror_factory, allow_incomplete=False, deadline=None, max_native_records=MAX_NATIVE_RECORDS,
                  max_history_rows=MAX_HISTORY_ROWS, max_record_bytes=MAX_RECORD_BYTES, max_export_bytes=MAX_EXPORT_BYTES):
    """Consume to clean EOF; packet budget and committed-history budget differ."""
    from google.protobuf.message import DecodeError
    deadline = time.monotonic() + 180 if deadline is None else deadline
    packets, rows, output_bytes, first_step, last_step = 0, 0, 0, None, None
    kinds, config, run_ids, exits, digest = Counter(), {}, [], [], hashlib.sha256()
    journal, clean_eof, decode_error, partial = None, False, None, 0
    try:
        while True:
            if time.monotonic() > deadline:
                raise BudgetError("Native reader wall budget exhausted")
            raw = data.scan_data()
            if raw is None:
                clean_eof = True
                break
            if packets >= max_native_records:
                raise BudgetError("Native packet budget exhausted before EOF")
            if len(raw) > max_record_bytes:
                raise BudgetError("Native record byte budget exhausted")
            packets += 1
            record = record_class(); record.ParseFromString(raw)
            kind = record.WhichOneof("record_type")
            kinds[kind or "none"] += 1
            if kind == "run":
                run_ids.append(record.run.run_id)
                _apply_config(config, record.run.config)
            elif kind == "config":
                previous_role = config.get("paired_role")
                _apply_config(config, record.config)
                require(journal is None or config.get("paired_role") == previous_role, "Native paired role changed during history")
            elif kind == "exit":
                exits.append(int(record.exit.exit_code))
            elif kind == "request" and "partial_history" in record.request.DESCRIPTOR.fields_by_name and record.request.HasField("partial_history"):
                partial += 1
                require(allow_incomplete, "Uncommitted native partial_history request")
            if kind != "history":
                continue
            if rows >= max_history_rows:
                raise BudgetError("Native committed-history budget exhausted")
            if journal is None:
                journal = iter(mirror_factory(config))
            expected = next(journal, None)
            require(expected is not None, "Extra committed native scientific row")
            values = native_items(record.history.item)
            require("_step" in values, "Native history lacks explicit _step")
            step = values.pop("_step")
            require(type(step) is int and step == expected["step"], "Native/mirror explicit step differs")
            for key in tuple(values):
                if key.startswith("_"):
                    require(key in {"_timestamp", "_runtime", "_wandb"} or key.startswith("_wandb/"), "Unexpected private SDK history field")
                    values.pop(key)
            require(set(values) == set(expected["row"]), "Missing or extra native scientific metric")
            normalized = {key: typed_like(values[key], value) for key, value in expected["row"].items()}
            out = encoded({"step": step, "row": normalized})
            output_bytes += len(out)
            if output_bytes > max_export_bytes:
                raise BudgetError("Normalized export byte budget exhausted")
            destination.write(out); digest.update(out)
            first_step = step if first_step is None else first_step
            last_step, rows = step, rows + 1
    except (EOFError, OSError, AssertionError, DecodeError) as exc:
        require(allow_incomplete, "Unexpected native SDK decode failure")
        decode_error = type(exc).__name__ + ": " + str(exc)[:200]
    if journal is None:
        journal = iter(mirror_factory(config))
    require(next(journal, None) is None and rows == expected_rows, "Native/mirror committed history counts differ")
    require(len(run_ids) <= 1 and all(value == expected_run_id for value in run_ids), "Native run identity differs")
    require(len(exits) <= 1, "Duplicate native exit records")
    if expected_exit is not None:
        require(run_ids == [expected_run_id] and exits == [expected_exit] and clean_eof and partial == 0,
                "Native clean EOF/runID/exit does not match the closed segment")
    elif not allow_incomplete:
        require(False, "Explicit native exit expectation required")
    closed = clean_eof and run_ids == [expected_run_id] and len(exits) == 1 and partial == 0
    return {"schema": "model_v3_native_mirror_verification_v7", "native_packets": packets, "record_types": dict(kinds),
        "history_rows": rows, "first_explicit_step": first_step, "last_explicit_step": last_step,
        "sdk_run_ids": run_ids, "sdk_exit_codes": exits, "clean_eof": clean_eof, "native_closed": closed,
        "uncommitted_native_requests": partial, "decode_error": decode_error,
        "status": "VERIFIED_COMMITTED_HISTORY" if closed else "FAILED_RAW_SDK_PRESERVED_INCOMPLETE",
        "normalized_history_bytes": output_bytes, "normalized_history_sha256": digest.hexdigest(),
        "paired_role": config.get("paired_role"), "scientific_acceptance": False, "online_sync_performed": False}


def verify_file(sdk_file, destination, **kwargs):
    from wandb.sdk.internal.datastore import DataStore
    from wandb.proto import wandb_internal_pb2
    require(Path(sdk_file).stat().st_size <= 128 << 20, "Native SDK source exceeds128MiB")
    data = DataStore()
    try:
        data.open_for_scan(str(sdk_file))
        return verify_stream(data, wandb_internal_pb2.Record, destination, **kwargs)
    finally:
        data.close()
