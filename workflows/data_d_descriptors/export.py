"""Target-free downstream D export using only frozen TRAIN fields/parameters.

Config: input_rows, membership_reference, train_manifest, output, peak_bytes,
workers and chunk_rows (256/512); reuse_main_raw defaults true. Membership is
only referenced, never read or repartitioned here. No statistics are fitted.
Optional libraries selects whole frozen L1/L2 families without changing fields.
include_D20 plus native_D20_parameters also supports native D20-only export
without a wide TRAIN manifest, descriptor initialization or worker pool.
"""
import argparse
import copy
from contextlib import nullcontext
import concurrent.futures as cf
import importlib.metadata
import json
import multiprocessing as mp
import os
from pathlib import Path
import platform
import time

import numpy as np

from . import pilot
from .produce import (check_checkpoint, encode_status, guard, read_json, reference,
                      require_cpu, rows, sync_arrays)
from workflows.data_v1_final.labels.common import D20_NAMES


SCHEMA = "D_DOWNSTREAM_DESCRIPTOR_EXPORT_V1"
DISABLED_D20 = frozenset(("NumBridgeheadAtoms", "NumSpiroAtoms", "MolMR"))


def source_binding(row):
    if "source_binding" in row:
        binding = row["source_binding"]
    elif "split" in row and "molecule_index" in row:
        binding = {"split": row["split"], "molecule_index": row["molecule_index"]}
    else:
        raise ValueError("Explicit existing source binding required")
    if not isinstance(binding, dict) or not binding:
        raise ValueError("Nonempty existing source binding required")
    return binding


def validate_source(row, *, need_d20):
    if not isinstance(row.get("molecule_id"), str) or not row["molecule_id"]:
        raise ValueError("Existing molecule_id required")
    if "smiles" not in row:
        raise ValueError("Explicit source smiles field required")
    if not (isinstance(row.get("smiles"), str) and row["smiles"]):
        if (row.get("smiles") is not None or not isinstance(row.get("source_error"), str)
                or not row["source_error"]):
            raise ValueError("Source graph or explicit source_error required")
    source_binding(row)
    if need_d20:
        existing = row.get("existing_D20")
        if not isinstance(existing, dict) or set(existing) != set(D20_NAMES):
            raise ValueError("All 20 canonical D20 fields, including explicit None, required")
        for value in existing.values():
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or np.isnan(value)):
                raise ValueError("Canonical D20 values must be numeric or missing None")


def signature(row, *, include_d20=False):
    value = {"smiles": row["smiles"], "source_binding": source_binding(row)}
    if include_d20:
        value["existing_D20"] = row["existing_D20"]
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def unique_sources(path, *, need_d20):
    """One producer metadata pass; retain byte offsets rather than copying rows."""
    unique, seen = [], {}
    with Path(path).open("rb") as stream:
        while True:
            offset = stream.tell()
            line = stream.readline()
            if not line:
                break
            row = json.loads(line)
            validate_source(row, need_d20=need_d20)
            mid, identity = row["molecule_id"], signature(row, include_d20=need_d20)
            if mid in seen:
                if seen[mid] != identity:
                    raise ValueError("Conflicting source rows for the same molecule_id")
                continue
            seen[mid] = identity
            index = {"molecule_id": mid, "feature_row": len(unique), "input_byte_offset": offset}
            index.update({key: row[key] for key in ("source_member_uid", "source_ordinal") if key in row})
            unique.append(index)
    if not unique:
        raise ValueError("Nonempty downstream source population required")
    return unique


def load_sources(path, indices):
    with Path(path).open("rb") as stream:
        for index in indices:
            stream.seek(index["input_byte_offset"])
            row = json.loads(stream.readline())
            if row["molecule_id"] != index["molecule_id"]:
                raise ValueError("Source input changed after producer indexing")
            yield row


def frozen_library(entry, actual_fields, actual_versions):
    if (entry.get("fit_role") != "TRAIN" or entry.get("producer_alignment_checked") is not True
            or entry.get("normalization") is None):
        raise ValueError("Frozen TRAIN fields and parameters required before export")
    if entry["ordered_fields"] != list(actual_fields):
        raise ValueError("TRAIN field order differs from installed calculator")
    if not entry.get("software_versions") or entry["software_versions"] != actual_versions:
        raise ValueError("TRAIN software versions differ from export calculator")
    fields, columns, parameters = entry["ordered_fields"], entry["enabled_columns"], entry["normalization"]
    if (len(fields) != len(set(fields)) or len(parameters) != len(fields)
            or len(columns) != len(set(columns))
            or any(type(c) is not int or not 0 <= c < len(fields) for c in columns)
            or any(parameters[c] is None for c in columns)):
        raise ValueError("Frozen TRAIN enabled columns/parameter layout invalid")
    return copy.deepcopy({key: entry[key] for key in
        ("ordered_fields", "enabled_columns", "normalization", "fit_role", "software_versions")})


def override_d20(raw, status, fields, existing):
    raw, status = np.asarray(raw, dtype=np.float64).copy(), np.asarray(status, dtype=np.uint8).copy()
    for column, name in enumerate(fields):
        if name not in D20_NAMES:
            continue
        value = existing[name]
        raw[column] = np.nan if value is None else value
        valid = np.array([value is not None], dtype=bool)
        numeric = np.array([value is not None and (not np.isfinite(value)
                            or abs(value) > np.finfo(np.float32).max)], dtype=bool)
        status[column] = encode_status(raw[column:column + 1], valid, numeric)[0]
    return raw, status


def native_d20_library(parameters, source):
    normalization, enabled = [], []
    for column, name in enumerate(D20_NAMES):
        if name in DISABLED_D20:
            normalization.append(None)
            continue
        spec = parameters.get(name)
        if (not isinstance(spec, dict) or spec.get("fit_role") != "TRAIN"
                or "center" not in spec or "scale" not in spec):
            raise ValueError("Existing resolved TRAIN D20 parameters required: " + name)
        normalization.append(dict(copy.deepcopy(spec), field_name=name))
        enabled.append(column)
    return {"ordered_fields": list(D20_NAMES), "enabled_columns": enabled,
            "normalization": normalization, "fit_role": "TRAIN", "software_versions": {},
            "normalization_source": source, "source": "ORIGINAL_CANONICAL_D20_VALUES_NO_RECOMPUTATION"}


def copy_native_d20(source_rows):
    values, flags = [], []
    for row in source_rows:
        validate_source(row, need_d20=True)
        raw, status = override_d20(np.full(len(D20_NAMES), np.nan),
            np.zeros(len(D20_NAMES), dtype=np.uint8), D20_NAMES, row["existing_D20"])
        values.append(raw); flags.append(status)
    return np.asarray(values, dtype=np.float64), np.asarray(flags, dtype=np.uint8)


def compute_chunk(source_rows, *, library, fields, calculate, reuse=None, compatible_cache=None):
    resolved, pending = {}, []
    for index, row in enumerate(source_rows):
        found = None if reuse is None else reuse(row)
        if found is None:
            working = row
            if (library == "L1" and compatible_cache is not None and row.get("source_member_uid")
                    and row.get("smiles") and not row.get("source_error")):
                cached = compatible_cache.get(row["source_member_uid"], row["smiles"], row.get("source_ordinal"))
                if cached is not None:
                    working = dict(row, existing_L1=cached)
            pending.append((index, working))
        else:
            resolved[index] = found
    reused = len(resolved)
    results = list(calculate([pilot.descriptor_input(row) for _, row in pending]))
    if len(results) != len(pending):
        raise ValueError("Calculator did not return one result per unique source")
    for (index, _), result in zip(pending, results):
        raw = np.asarray(result[0], dtype=np.float64)
        status = encode_status(raw, np.asarray(result[1], dtype=bool), np.asarray(result[2], dtype=bool))
        resolved[index] = (raw, status)
    raw_rows, status_rows = [], []
    for index, row in enumerate(source_rows):
        raw, status = resolved[index]
        if library == "L1":
            raw, status = override_d20(raw, status, fields, row["existing_D20"])
        if np.shape(raw) != (len(fields),) or np.shape(status) != (len(fields),):
            raise ValueError("Calculator/reused row does not match frozen field order")
        raw_rows.append(raw); status_rows.append(status)
    return np.asarray(raw_rows, dtype=np.float64), np.asarray(status_rows, dtype=np.uint8), reused


def main_reuse(entry, main_rows, requested_ids):
    addresses = {row["molecule_id"]: (signature(row), index)
                 for index, row in enumerate(main_rows) if row["molecule_id"] in requested_ids}
    raw = np.load(entry["values"], mmap_mode="r", allow_pickle=False)
    status = np.load(entry["status"], mmap_mode="r", allow_pickle=False)
    if (raw.ndim != 2 or raw.shape != status.shape or raw.shape[1] != len(entry["ordered_fields"])
            or raw.dtype != np.dtype(np.float64) or status.dtype != np.dtype(np.uint8)):
        raise ValueError("Main raw-store header differs from frozen field metadata")
    def reuse(row):
        hit = addresses.get(row["molecule_id"])
        if hit is None or hit[0] != signature(row):
            return None
        index = hit[1]
        return np.asarray(raw[index]).copy(), np.asarray(status[index]).copy()
    return reuse


def publish(path, value, config):
    guard(Path(path).parent, config)
    pending = Path(str(path) + ".partial")
    with pending.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
    os.replace(pending, path)


def commit_part(values, status, raw, flags, *, offset, part, checkpoint, marker, config, reused):
    if part in checkpoint["completed_parts"]:
        return False
    guard(Path(values.filename).parent, config)
    values[offset:offset + len(raw)] = raw
    status[offset:offset + len(flags)] = flags
    sync_arrays(values, status)
    checkpoint["completed_parts"].append(part)
    checkpoint["main_rows_reused"] += reused
    publish(marker, checkpoint, config)
    return True


def run(config):
    train_ref, native_ref, libraries = None, None, {}
    if config.get("train_manifest"):
        train_ref = reference(config["train_manifest"])
        frozen = read_json(train_ref["path"])
        if frozen.get("schema") != "D_WIDE_DESCRIPTOR_STORE_V1":
            raise ValueError("Frozen main TRAIN descriptor manifest required")
        requested = config.get("libraries", ("L1", "L2"))
        if (not isinstance(requested, (list, tuple)) or not requested
                or len(set(requested)) != len(requested) or not set(requested) <= {"L1", "L2"}):
            raise ValueError("Select complete registered L1/L2 library families only")
        libraries = {name: entry for name, entry in frozen["libraries"].items()
                     if name in requested and entry.get("status") != "UNRESOLVED"}
    elif not config.get("include_D20"):
        raise ValueError("Frozen main TRAIN descriptor manifest required")
    has_wide = bool(libraries)
    if config.get("include_D20"):
        native_ref = reference(config["native_D20_parameters"])
        libraries["D20"] = native_d20_library(read_json(native_ref["path"]), native_ref["path"])
    if not libraries:
        raise ValueError("No frozen wide library is available for downstream export")
    require_cpu(config if has_wide else dict(config, workers=1))
    if has_wide and config["workers"] + 1 > int(os.environ["SLURM_CPUS_PER_TASK"]):
        raise ValueError("Calculator workers plus encoding parent CPU required")
    input_ref = reference(config["input_rows"])
    membership = copy.deepcopy(config["membership_reference"])
    if not Path(membership["path"]).is_absolute():
        raise ValueError("Existing membership reference must use its absolute path")
    membership_ref = reference(membership["path"])  # Stat only; never open labels/splits.
    output = Path(config["output"]).resolve()
    guard(output.parent, config); output.mkdir(parents=True, exist_ok=True)
    index_path = output / "source_index.json"
    binding = {"input": input_ref, "train_manifest": train_ref, "membership": membership_ref,
               "native_D20_parameters": native_ref, "membership_layout": membership, "libraries": list(libraries),
               "reuse_main_raw": config.get("reuse_main_raw", True),
               "b6_manifest": reference(config["b6_manifest"]) if config.get("b6_manifest") else None}
    if index_path.exists():
        index_document = read_json(index_path)
        if index_document["binding"] != binding:
            raise ValueError("Export source/partition/TRAIN binding changed")
        unique = index_document["rows"]
    else:
        unique = unique_sources(input_ref["path"], need_d20="L1" in libraries or "D20" in libraries)
    minimum = len(unique) * (9 * sum(len(e["ordered_fields"]) for e in libraries.values()) + 512)
    if config["peak_bytes"] < minimum + 2**21:
        raise ValueError("Explicit peak does not cover downstream arrays/index/temporary output")
    if not index_path.exists():
        publish(index_path, {"binding": binding, "rows": unique}, config)
    ids_path = output / "unique_ids.jsonl"
    if not ids_path.exists():
        guard(output, config)
        pending = Path(str(ids_path) + ".partial")
        with pending.open("w", encoding="utf-8") as stream:
            for row in unique:
                stream.write(json.dumps({key: row[key] for key in
                    ("molecule_id", "feature_row", "source_member_uid", "source_ordinal") if key in row}) + "\n")
            stream.flush(); os.fsync(stream.fileno())
        os.replace(pending, ids_path)
    manifest = {"schema": SCHEMA, "molecules": str(ids_path), "membership_reference": membership,
                "members": membership["path"], "input_rows": input_ref["path"],
                "normalization_source": train_ref["path"] if has_wide else native_ref["path"],
                "unique_molecules": len(unique),
                "libraries": {}, "reception_acceptance": "pending", "current_C1_complete": False,
                "membership_or_split_changed": False, "statistics_fitted": False,
                "canonical_D20_required": "L1" in libraries or "D20" in libraries,
                "source_canonical_D20_status": config.get("canonical_D20_source_status")}
    requested_ids = {row["molecule_id"] for row in unique}
    for library, entry in libraries.items():
        begin = time.monotonic()
        if library == "D20":
            spec = copy.deepcopy(entry)
        else:
            pilot.initialize(library)
            versions = {name: importlib.metadata.version(dist) for name, dist in
                        (("rdkit_version", "rdkit"), ("mordredcommunity_version", "mordredcommunity"))}
            spec = frozen_library(entry, pilot.FIELDS, versions)
        compatible_cache = None
        if library == "L1" and config.get("b6_manifest"):
            from .b6_cache import B6L1Cache
            compatible_cache = B6L1Cache(config["b6_manifest"], fields=spec["ordered_fields"],
                rdkit_version=spec["software_versions"]["rdkit_version"],
                member_uids={row["source_member_uid"] for row in unique if row.get("source_member_uid")})
        shape = (len(unique), len(spec["ordered_fields"]))
        identity = dict(binding, library=library, fields=spec, chunk_rows=config["chunk_rows"])
        marker = output / (library + "_checkpoint.json")
        checkpoint = read_json(marker) if marker.exists() else {
            "identity": identity, "completed_parts": [], "main_rows_reused": 0, "attempts": []}
        parts = (len(unique) + config["chunk_rows"] - 1) // config["chunk_rows"]
        completed = check_checkpoint(checkpoint, identity, parts)
        arrays = []
        for name, dtype in (("values", np.float64), ("status", np.uint8)):
            path = output / (library + "_" + name + ".npy")
            if path.exists():
                array = np.load(path, mmap_mode="r+", allow_pickle=False)
                if array.shape != shape or array.dtype != dtype:
                    raise ValueError("Export resume array shape/dtype changed")
            else:
                if completed:
                    raise ValueError("Closed export parts lost their array")
                guard(output, config)
                array = np.lib.format.open_memmap(path, mode="w+", dtype=dtype, shape=shape)
            arrays.append(array)
        values, status = arrays
        reuse = (main_reuse(entry, rows(entry["rows"]), requested_ids)
                 if library != "D20" and config.get("reuse_main_raw", True) else None)
        pool_context = (nullcontext(None) if library == "D20" else cf.ProcessPoolExecutor(
            max_workers=config["workers"], mp_context=mp.get_context("spawn"),
            initializer=pilot.initialize, initargs=(library,)))
        with pool_context as pool:
            for part, offset in enumerate(range(0, len(unique), config["chunk_rows"])):
                if part in completed:
                    continue
                source = list(load_sources(input_ref["path"], unique[offset:offset + config["chunk_rows"]]))
                if library == "D20":
                    raw, flags = copy_native_d20(source)
                    reused = 0
                else:
                    raw, flags, reused = compute_chunk(source, library=library, fields=spec["ordered_fields"],
                        calculate=lambda items: pool.map(pilot.one, items, chunksize=4), reuse=reuse,
                        compatible_cache=compatible_cache)
                commit_part(values, status, raw, flags, offset=offset, part=part, checkpoint=checkpoint,
                            marker=marker, config=config, reused=reused)
        checkpoint["attempts"].append({"job_id": os.environ["SLURM_JOB_ID"], "node": platform.node(),
                                       "elapsed_seconds": time.monotonic() - begin})
        checkpoint["state"] = "EXPORT_SOURCE_PROCESSING_COMPLETE"
        publish(marker, checkpoint, config)
        manifest["libraries"][library] = dict(spec, values=str(values.filename), status=str(status.filename),
            normalization_source=spec.get("normalization_source", train_ref["path"] if train_ref else None),
            checkpoint=str(marker), raw_values_clipped=False,
            status_codes={"0": "missing", "1": "valid", "2": "nonfinite_or_overflow"})
        if compatible_cache is not None:
            manifest["libraries"][library]["compatible_L1_cache"] = compatible_cache.provenance()
        del arrays, values, status, reuse
    manifest["source_processing_complete"] = True
    publish(output / "manifest.json", manifest, config)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    run(read_json(args.config))


if __name__ == "__main__":
    main()
