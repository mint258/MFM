"""Run a reviewed fill pilot with bounded spawn workers and immutable evidence."""
from __future__ import annotations

import argparse
from collections import Counter
import concurrent.futures as futures
import gzip
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
from common import (load_config, new_output_directory, reference, require_pin,
                    require_preflight, runtime_guard, write_json_new, geometry_sha,
                    prewrite_guard, write_parquet_new)


def run_one(task):
    import science
    from statistics_tools import molecule_statistics
    result = science.process_task(task)
    result["statistics"] = molecule_statistics(result, science.SCIENCE)
    return result


def parquet_new(path, rows, coordinates=False):
    import pyarrow as pa
    import pyarrow.parquet as pq
    if path.exists():
        raise FileExistsError(path)
    table = pa.Table.from_pylist(rows) if rows else pa.table({"molecule_id": pa.array([], type=pa.string())})
    if coordinates and rows:
        table = table.set_column(table.schema.get_field_index("coordinates"), "coordinates",
                                 pa.array([row["coordinates"] for row in rows], type=pa.list_(pa.list_(pa.float64(), 3))))
        table = table.set_column(table.schema.get_field_index("atomic_numbers"), "atomic_numbers",
                                 pa.array([row["atomic_numbers"] for row in rows], type=pa.list_(pa.int16())))
    write_parquet_new(path, table)


def persist_result(out, mid, result, cap):
    if result["summary"]["molecule_id"] != mid:
        raise ValueError("ACTUAL_RECORD_MANIFEST_MISMATCH:worker_molecule_id")
    name = hashlib.sha256(mid.encode()).hexdigest() + ".json.gz"
    path = out / "reproduction" / name
    payload = json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    compressed = gzip.compress(payload, mtime=0)
    prewrite_guard(path, len(compressed), reserve_bytes=cap // 2)
    with path.open("xb") as stream:
        stream.write(compressed)
        stream.flush()
        os.fsync(stream.fileno())
    return {"molecule_id": mid, **reference(path)}


def verify_readback(path, expected):
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pq.read_table(path)
    if expected and table.schema.field("coordinates").type.value_type.value_type != pa.float64():
        raise ValueError("PERMANENT_COORDINATES_MUST_BE_FLOAT64")
    lookup = {(row["molecule_id"], row["sprime_conf_idx"]): row["geometry_sha256"] for row in expected}
    rows = table.to_pylist()
    if len(rows) != len(lookup):
        raise ValueError("PARQUET_READBACK_RECORD_COUNT_MISMATCH")
    for row in rows:
        key = row["molecule_id"], row["sprime_conf_idx"]
        actual = geometry_sha(row["atomic_numbers"], row["coordinates"])
        if key not in lookup or actual != lookup.pop(key) or row["geometry_sha256"] != actual:
            raise ValueError("PARQUET_READBACK_GEOMETRY_SHA_MISMATCH")
    if lookup:
        raise ValueError("PARQUET_READBACK_MISSING_RECORD")
    return {"status": "ALL_PILOT_GEOMETRIES_FLOAT64_SHA_READBACK_PASSED", "records": len(rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root-preflight", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()
    config = load_config(args.config)
    runtime = runtime_guard(args.workers)
    preflight = require_preflight(args.root_preflight, args.config, config)
    prepared = json.loads((args.prepared / "prepared.json").read_text(encoding="utf-8"))
    if prepared["status"] != "PILOT_INPUTS_READY_NOT_COMPUTED" or prepared["config"] != reference(args.config):
        raise ValueError("PREPARED_CONFIG_BINDING_MISMATCH")
    for pin in prepared["outputs"]:
        require_pin(pin)
    tasks = [json.loads(line) for line in (args.prepared / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(tasks) != prepared["molecules"] or len({task["meta"]["molecule_id"] for task in tasks}) != len(tasks):
        raise ValueError("ACTUAL_RECORD_MANIFEST_MISMATCH:prepared_task_count")
    out = new_output_directory(args.output, config)
    (out / "reproduction").mkdir(mode=0o700)
    results, records, total_bytes = [], [], 0
    started = time.monotonic()
    import science
    from statistics_tools import aggregate_statistics
    failure, worker_failures, active = None, [], {}
    try:
        with futures.ProcessPoolExecutor(max_workers=args.workers, mp_context=mp.get_context("spawn"),
                                         initializer=science.worker_init, initargs=(str(args.config),)) as pool:
            iterator = iter(tasks)
            for _ in range(min(args.workers, len(tasks))):
                task = next(iterator)
                active[pool.submit(run_one, task)] = task["meta"]["molecule_id"]
            while active:
                completed, _ = futures.wait(active, return_when=futures.FIRST_COMPLETED)
                for future in completed:
                    mid = active.pop(future)
                    try:
                        result = future.result()
                    except Exception as child_exc:
                        worker_failures.append({"molecule_id": mid, "exception_type": type(child_exc).__name__,
                                                "error": str(child_exc)[:4000]})
                        raise
                    # Every completed molecule has a reproducible selected geometry package;
                    # only failures and the fixed 1% sample include all unselected raw candidates.
                    record = persist_result(out, mid, result, config["max_output_bytes"])
                    total_bytes += record["bytes"]
                    records.append(record)
                    results.append(result)
                    if total_bytes > config["max_output_bytes"] // 2:
                        raise RuntimeError("PILOT_OUTPUT_CAP_HALF_RESERVED_FOR_FINAL_PARQUET")
                    try:
                        task = next(iterator)
                    except StopIteration:
                        pass
                    else:
                        active[pool.submit(run_one, task)] = task["meta"]["molecule_id"]
                write_json_new(out / f"progress_{len(results):06d}.json",
                               {"completed": len(results), "total": len(tasks),
                                "seconds": time.monotonic() - started,
                                "status_counts": dict(Counter(r["summary"]["status"] for r in results))})
    except Exception as exc:
        # Exiting the pool waits for running workers. No signal/kill or old-job restart.
        failure = {"exception_type": type(exc).__name__, "error": str(exc)[:4000]}
        # Pool shutdown has joined all already running tasks; preserve their results
        # even when another task raised a hard identity error. Do not resubmit them.
        for future, mid in active.items():
            try:
                result = future.result()
                records.append(persist_result(out, mid, result, config["max_output_bytes"]))
                results.append(result)
            except Exception as child_exc:
                worker_failures.append({"molecule_id": mid, "exception_type": type(child_exc).__name__,
                                        "error": str(child_exc)[:4000]})
    write_json_new(out / "worker_failures.json", worker_failures)
    summaries = sorted((result["summary"] for result in results), key=lambda row: row["molecule_id"])
    conformers = sorted((row for result in results for row in result["conformers"]),
                        key=lambda row: (row["molecule_id"], row["sprime_conf_idx"]))
    parquet_new(out / "molecules.parquet", summaries)
    parquet_new(out / "conformers.parquet", conformers, coordinates=True)
    try:
        readback = verify_readback(out / "conformers.parquet", conformers)
    except Exception as exc:
        readback = {"status": "FAILED", "exception_type": type(exc).__name__, "error": str(exc)[:4000]}
        failure = {"error": "PARQUET_READBACK_FAILED", "details": readback}
    orders = [{"molecule_id": result["summary"]["molecule_id"], "orders": result["orders"]} for result in results]
    write_json_new(out / "orders.json", {"seed": config["order_seed"], "molecules": orders,
                   "pm7_energy_order_status": "NATIVE_ANCHOR_DIAGNOSTIC_PENDING_FINAL_CANONICAL_WP5_HOF"})
    write_json_new(out / "conformer_statistics.json", aggregate_statistics(results))
    write_json_new(out / "reproduction_manifest.json", sorted(records, key=lambda row: row["molecule_id"]))
    output_refs = [reference(out / name) for name in ("molecules.parquet", "conformers.parquet", "orders.json",
                   "conformer_statistics.json", "reproduction_manifest.json", "worker_failures.json")]
    total_bytes = sum(path.stat().st_size for path in out.rglob("*")) + out.stat().st_size
    if total_bytes + (2 << 20) > config["max_output_bytes"]:
        failure = {"error": "PILOT_TOTAL_OUTPUT_CAP_EXCEEDED", "bytes": total_bytes}
    implementation_failures = [row["molecule_id"] for row in summaries if row["status"] == "IMPLEMENTATION_ERROR"]
    if implementation_failures:
        failure = {"error": "PILOT_HAS_IMPLEMENTATION_ERRORS", "molecule_ids": implementation_failures}
    report = {"status": "PILOT_INCOMPLETE" if failure else "PILOT_COMPLETED_REQUIRES_ROOT_REVIEW",
              "failure": failure, "runtime": runtime, "config": reference(args.config),
              "prepared": reference(args.prepared / "prepared.json"), "root_preflight": preflight,
              "expected_molecules": len(tasks), "completed_molecules": len(results),
              "conformers": len(conformers), "status_counts": dict(Counter(row["status"] for row in summaries)),
              "science_worker_seconds": sum(row["elapsed_seconds"] for row in summaries),
              "elapsed_seconds": time.monotonic() - started, "output_bytes_before_receipt": total_bytes,
              "source_pins": config["science_source_pins"], "outputs": output_refs,
              "parquet_readback": readback,
              "full_population_completion_claimed": False, "common_population_v1_published": False,
              "original_data_modified": False, "gpu_used": False,
              "accounting_status": "Root must attach actual Slurm parent AllocCPUS*ElapsedRaw including failures",
              "remaining_gates": ["pilot timing/success/cost and additional sparse strata review",
                                  "full-population overall exclusion<=2%; Se exception only; other elements<=20%",
                                  "frozen TRAIN plus ROUTINE VAL molecular roles and original routine record membership",
                                  "canonical WP5 PM7 energy ordering"]}
    write_json_new(out / "receipt.json", report)
    print(json.dumps({"status": report["status"], "molecules": len(results), "output": str(out)}))
    return 1 if failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
