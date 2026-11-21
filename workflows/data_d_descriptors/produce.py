"""Resumable stage-0 stores; calculators are imported from the cost pilot.

Config requires input_rows, pilot_root, output, peak_bytes, workers, chunk_rows.
Run ``produce --config ...`` after both pilot cost records have closed; then
``finalize --config ...`` once, supplying existing_parameters_json for L1.
No command in this module performs reception/loader acceptance.
"""
import argparse
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
from .statistics import summarize_library


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def reference(path):
    path = Path(path).resolve()
    stat = path.stat()
    return {"path": str(path), "bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "inode": stat.st_ino}


def validate_rows(path):
    """The sole producer alignment check, with no descriptors or targets read."""
    ids, indices, counts = set(), set(), {}
    for row in rows(path):
        mid, key, role = row["molecule_id"], (row["split"], row["molecule_index"]), row["role"]
        source_error = row.get("source_error")
        usable_graph = isinstance(row["smiles"], str) and bool(row["smiles"])
        if (not isinstance(mid, str) or not mid or type(key[1]) is not int or key[1] < 0
                or role not in ("TRAIN", "VAL", "VAL_DIAGNOSTIC")
                or (not usable_graph and not (row["smiles"] is None
                    and isinstance(source_error, str) and source_error))):
            raise ValueError("INVALID_TARGET_FREE_STRUCTURE_ROW")
        if key[0] not in ("TRAIN", "FULL") or (role == "TRAIN") != (key[0] == "TRAIN"):
            raise ValueError("ROLE_SPLIT_MISMATCH")
        if mid in ids or key in indices:
            raise ValueError("DUPLICATE_MOLECULE_ID_OR_SPLIT_INDEX")
        ids.add(mid); indices.add(key)
        counts[role] = counts.get(role, 0) + 1
    if not ids or not counts.get("TRAIN"):
        raise ValueError("NONEMPTY_TRAIN_POPULATION_REQUIRED")
    return {"rows": len(ids), "role_counts": counts}


def rows(path):
    with Path(path).open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                raise ValueError("EMPTY_STRUCTURE_ROW")
            yield json.loads(line)


def chunks(path, width):
    chunk = []
    for row in rows(path):
        chunk.append(row)
        if len(chunk) == width:
            yield chunk
            chunk = []
    if chunk:
        yield chunk


def closed_pilots(root):
    result = {}
    for library in ("L1", "L2"):
        path = Path(root) / (library + "_cost.json")
        cost = read_json(path)
        if cost.get("status") == "UNRESOLVED":
            result[library] = {"status": "UNRESOLVED", "cost": str(path.resolve())}
        elif (cost.get("status") == "PILOT_COST_COMPLETE_NOT_DELIVERY"
              and cost.get("library") == library and cost.get("molecules") == 5000):
            result[library] = {"status": "READY", "cost": str(path.resolve())}
        else:
            raise ValueError("BOTH_5000_MOLECULE_COST_PILOTS_MUST_BE_CLOSED:" + library)
    return result


def pilot_cache(root, library, fields):
    root = Path(root)
    panel = read_json(root / "panel.json")["molecules"]
    if read_json(root / (library + "_fields.json"))["ordered_names"] != fields:
        raise ValueError("PILOT_FIELD_ORDER_CHANGED")
    with np.load(root / (library + "_pilot.npz"), allow_pickle=False) as data:
        values = data["values"].copy()
        status = encode_status(data["values"], data["valid"], data["bad_numeric"])
        indices = data["molecule_index"].copy()
    if values.shape != (len(panel), len(fields)) or len(panel) != 5000:
        raise ValueError("PILOT_ARRAY_PANEL_ALIGNMENT_INVALID")
    lookup = {}
    for index, row in enumerate(panel):
        if indices[index] != row["molecule_index"] or row["molecule_id"] in lookup:
            raise ValueError("PILOT_ID_ALIGNMENT_INVALID")
        lookup[row["molecule_id"]] = (row["smiles"], values[index], status[index])
    return lookup


def encode_status(values, valid, bad_numeric):
    values, valid, bad = np.asarray(values), np.asarray(valid), np.asarray(bad_numeric)
    if values.shape != valid.shape or values.shape != bad.shape or valid.dtype != bool or bad.dtype != bool:
        raise ValueError("DESCRIPTOR_RESULT_MASK_LAYOUT_INVALID")
    status = np.zeros(values.shape, dtype=np.uint8)
    status[valid & np.isfinite(values) & ~bad] = 1
    status[bad | (valid & ~np.isfinite(values))] = 2
    return status


def plan_chunk(chunk, cache):
    reused, missing = {}, []
    for index, row in enumerate(chunk):
        hit = cache.get(row["molecule_id"])
        if hit is not None:
            if hit[0] != row["smiles"] or row["role"] != "TRAIN":
                raise ValueError("PILOT_PRODUCTION_STRUCTURE_OR_ROLE_CHANGED")
            reused[index] = (hit[1], hit[2])
        else:
            # one(None) returns all missing before invoking any calculator;
            # retain source_error verbatim in the referenced original JSONL.
            missing.append((index, pilot.descriptor_input(row)))
    return reused, missing


def check_checkpoint(checkpoint, identity, parts):
    if checkpoint["identity"] != identity:
        raise ValueError("RESUME_CONDITION_CHANGED")
    completed = checkpoint["completed_parts"]
    if (len(completed) != len(set(completed)) or
            any(type(part) is not int or not 0 <= part < parts for part in completed)):
        raise ValueError("INVALID_CLOSED_PART_CHECKPOINT")
    return set(completed)


def guard(output, config):
    peak = config.get("peak_bytes")
    if type(peak) is not int or peak <= 0:
        raise ValueError("EXPLICIT_FULL_PRODUCTION_PEAK_BUDGET_REQUIRED")
    # Reserve the complete peak even after sparse arrays have been created.
    # This intentionally over-reserves rather than mistaking logical file size
    # for committed physical storage; pilot guard also reserves concurrent P.
    pilot.storage_guard(output, peak_bytes=peak)


def publish(path, value, config):
    guard(Path(path).parent, config)
    pilot.publish(path, value)


def sync_arrays(*arrays):
    for array in arrays:
        array.flush()
        with Path(array.filename).open("rb") as stream:
            os.fsync(stream.fileno())


def require_cpu(config):
    node = platform.node()
    if (not os.environ.get("SLURM_JOB_ID") or not node.startswith("compute-0-")
            or not 8 <= int(node.rsplit("-", 1)[-1]) <= 19):
        raise RuntimeError("ALLOCATED_CPU_NODE_8_TO_19_REQUIRED")
    workers = config.get("workers")
    allocated = int(os.environ.get("SLURM_CPUS_PER_TASK", 0))
    if type(workers) is not int or not 1 <= workers <= allocated:
        raise ValueError("DEMAND_BASED_ALLOCATED_WORKERS_REQUIRED")
    if config.get("chunk_rows") not in (256, 512):
        raise ValueError("REGISTERED_FIXED_CHUNK_256_OR_512_REQUIRED")
    for variable in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ[variable] = "1"


def produce(config):
    require_cpu(config)
    available = closed_pilots(config["pilot_root"])
    output = Path(config["output"]).resolve()
    guard(output.parent, config)
    output.mkdir(exist_ok=True)
    alignment_path = output / "population.json"
    input_ref = reference(config["input_rows"])
    if alignment_path.exists():
        population = read_json(alignment_path)
        if population["input"] != input_ref:
            raise ValueError("FROZEN_STRUCTURE_MANIFEST_CHANGED")
    else:
        population = dict(validate_rows(input_ref["path"]), input=input_ref,
                          producer_alignment_checked=True)
        publish(alignment_path, population, config)
    field_counts = [len(read_json(Path(config["pilot_root"]) / (lib + "_fields.json"))["ordered_names"])
                    for lib, state in available.items() if state["status"] == "READY"]
    minimum_peak = (population["rows"] * sum(field_counts) * 9
                    + config["chunk_rows"] * max(field_counts, default=0) * 18 + 2**21)
    if config["peak_bytes"] < minimum_peak:
        raise ValueError("PEAK_BUDGET_BELOW_FULL_ARRAYS_AND_WORKSPACE")
    manifest = {"schema": "D_WIDE_DESCRIPTOR_STORE_V1", "status": "RAW_COMPLETE_STATISTICS_PENDING",
        "libraries": {}, "population": str(alignment_path), "rows": input_ref["path"],
        "role_counts": population["role_counts"], "producer_alignment_checked": True,
        "reception_acceptance": "pending", "raw_targets_clipped": False,
        "source_error_reference": input_ref["path"], "source_error_field": "source_error"}
    for library, state in available.items():
        if state["status"] == "UNRESOLVED":
            manifest["libraries"][library] = state
            continue
        library_start = time.perf_counter()
        pilot.initialize(library)
        fields = list(pilot.FIELDS)
        frozen_fields = read_json(Path(config["pilot_root"]) / (library + "_fields.json"))
        versions = {name: importlib.metadata.version(distribution) for name, distribution in
            (("rdkit_version", "rdkit"), ("mordredcommunity_version", "mordredcommunity"))}
        if any(frozen_fields.get(name) != value for name, value in versions.items()):
            raise ValueError("PILOT_SOFTWARE_VERSION_CHANGED:" + library)
        cache = pilot_cache(config["pilot_root"], library, fields)
        shape = (population["rows"], len(fields))
        paths = {key: output / (library + "_" + key + ".npy") for key in ("values", "status")}
        marker = output / (library + "_checkpoint.json")
        identity = {"input": input_ref, "library": library, "fields": fields,
                    "chunk_rows": config["chunk_rows"], "shape": list(shape), "pilot": state,
                    "software_versions": versions}
        count = (shape[0] + config["chunk_rows"] - 1) // config["chunk_rows"]
        checkpoint = read_json(marker) if marker.exists() else {"identity": identity,
            "completed_parts": [], "attempts": [], "pilot_rows_reused": 0}
        completed = check_checkpoint(checkpoint, identity, count)
        arrays = []
        for name, dtype in (("values", np.float64), ("status", np.uint8)):
            path = paths[name]
            if path.exists():
                array = np.load(path, mmap_mode="r+")
                if array.shape != shape or array.dtype != dtype:
                    raise ValueError("RESUME_ARRAY_LAYOUT_CHANGED")
            else:
                if completed:
                    raise ValueError("CLOSED_PART_ARRAY_MISSING")
                guard(output, config)
                array = np.lib.format.open_memmap(path, mode="w+", dtype=dtype, shape=shape)
            arrays.append(array)
        values, status = arrays
        checkpoint["attempts"].append({"job_id": os.environ["SLURM_JOB_ID"],
            "node": platform.node(), "workers": config["workers"], "state": "RUNNING",
            "elapsed_observed_seconds": 0.0})
        publish(marker, checkpoint, config)
        with cf.ProcessPoolExecutor(max_workers=config["workers"], mp_context=mp.get_context("spawn"),
                                    initializer=pilot.initialize, initargs=(library,)) as pool:
            for part, chunk in enumerate(chunks(input_ref["path"], config["chunk_rows"])):
                if part in completed:
                    continue
                guard(output, config)
                reused, missing = plan_chunk(chunk, cache)
                results = list(pool.map(pilot.one, [smiles for _, smiles in missing], chunksize=4))
                for (index, _), result in zip(missing, results):
                    raw = np.asarray(result[0], dtype=np.float64)
                    reused[index] = (raw, encode_status(raw, np.asarray(result[1], dtype=bool),
                                                       np.asarray(result[2], dtype=bool)))
                offset = part * config["chunk_rows"]
                guard(output, config)
                for index in range(len(chunk)):
                    values[offset + index], status[offset + index] = reused[index]
                sync_arrays(values, status)
                checkpoint["completed_parts"].append(part)
                checkpoint["pilot_rows_reused"] += len(chunk) - len(missing)
                checkpoint["last_job_id"] = os.environ["SLURM_JOB_ID"]
                checkpoint["attempts"][-1]["elapsed_observed_seconds"] = time.perf_counter() - library_start
                publish(marker, checkpoint, config)
                print(json.dumps({"library": library, "closed_part": part, "parts": count}), flush=True)
        checkpoint["attempts"][-1].update(state="RAW_COMPLETE",
            elapsed_observed_seconds=time.perf_counter() - library_start)
        checkpoint["status"] = "RAW_COMPLETE"
        publish(marker, checkpoint, config)
        manifest["libraries"][library] = dict(state, status="RAW_COMPLETE", ordered_fields=fields,
            software_versions=versions,
            values=str(paths["values"]), value_dtype="float64", status_store=str(paths["status"]),
            rows=input_ref["path"], shape=list(shape), checkpoint=str(marker), fit_role="TRAIN",
            producer_alignment_checked=True, reception_acceptance="pending",
            status_codes={"0": "missing", "1": "valid", "2": "nonfinite_or_overflow"})
        # Loader schema uses `status` for the array path, state for lifecycle.
        manifest["libraries"][library]["state"] = "RAW_COMPLETE"
        manifest["libraries"][library]["status"] = str(paths["status"])
        del values, status, arrays
    publish(output / "manifest.json", manifest, config)
    return manifest


def finalize(config):
    require_cpu(config)
    output = Path(config["output"]).resolve()
    destination = output / "final_manifest.json"
    if destination.exists():
        return read_json(destination)
    manifest = read_json(output / "manifest.json")
    # Root may close one library conservatively under taskbook section 3
    # after its actual repair timebox/failure limit. Raw stores and the sole
    # TRAIN statistics stay intact; a closed peer must still be deliverable.
    unresolved = config.get("unresolved_libraries", {})
    if (not isinstance(unresolved, dict)
            or set(unresolved) - set(manifest["libraries"])
            or any(not isinstance(reason, str) or not reason.strip()
                   for reason in unresolved.values())):
        raise ValueError("Explicit known library and nonempty unresolved reason required")
    train_rows = np.asarray([i for i, row in enumerate(rows(manifest["rows"])) if row["role"] == "TRAIN"])
    for library, entry in manifest["libraries"].items():
        if library in unresolved:
            # The original manifest remains unchanged. Keep its status-array
            # path as a raw reference even though this final entry is unusable.
            if entry.get("status") != "UNRESOLVED":
                entry.setdefault("status_store", entry["status"])
            entry.update(status="UNRESOLVED", state="UNRESOLVED",
                         reason=unresolved[library],
                         reception_acceptance="not_deliverable")
            closed_statistics = output / (library + "_statistics.json")
            if closed_statistics.exists():
                entry["statistics"] = str(closed_statistics)
            continue
        if entry.get("status") == "UNRESOLVED":
            continue
        marker = output / (library + "_statistics.json")
        if marker.exists():
            statistics = read_json(marker)
        else:
            values = np.load(entry["values"], mmap_mode="r")
            status = np.load(entry["status"], mmap_mode="r")
            existing_path = config.get("existing_parameters_json", {}).get(library)
            existing = read_json(existing_path) if existing_path else {}
            fields = []
            for column, name in enumerate(entry["ordered_fields"]):
                guard(output, config)
                raw = np.asarray(values[train_rows, column], dtype=np.float64)[:, None]
                flags = np.asarray(status[train_rows, column])[:, None]
                result = summarize_library(raw, flags == 1, flags == 2, np.zeros(flags.shape, dtype=bool),
                    field_names=[name], library=library, roles=["TRAIN"] * len(train_rows),
                    existing_parameters={name: existing[name]} if name in existing else None)
                fields.extend(result["fields"])
            statistics = {"library": library, "fit_role": "TRAIN", "fields": fields,
                          "numeric_event_encoding": "status2 combines nonfinite and overflow"}
            publish(marker, statistics, config)
        entry["enabled_columns"] = [i for i, field in enumerate(statistics["fields"]) if field["enabled"]]
        if any(field["enabled"] and field["normalization_status"] == "ZERO_SCALE_NOT_DIVIDABLE"
               for field in statistics["fields"]):
            raise ValueError("UNRESOLVED_NORMALIZATION_ZERO_SCALE:" + library)
        entry["normalization"] = []
        for field in statistics["fields"]:
            parameters = field["parameters"]
            # Preserve the complete historical parameter dict. New fits use
            # std_population; publish the loader's equivalent std_ddof0 alias.
            normalized = None if not field["enabled"] else dict(parameters, field_name=field["name"])
            if normalized is not None and "std_population" in normalized and "std_ddof0" not in normalized:
                normalized["std_ddof0"] = normalized["std_population"]
            entry["normalization"].append(normalized)
        entry["statistics"] = str(marker)
        entry["state"] = "PRODUCER_COMPLETE_RECEPTION_PENDING"
    manifest["status"] = ("UNRESOLVED" if all(
        entry.get("status") == "UNRESOLVED" for entry in manifest["libraries"].values())
        else "PRODUCER_COMPLETE_RECEPTION_PENDING")
    publish(destination, manifest, config)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("produce", "finalize"))
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    (produce if args.command == "produce" else finalize)(read_json(args.config))


if __name__ == "__main__":
    main()
