"""Unexecuted alternative for an explicitly approved 336-molecule memory policy.

Reuses unchanged run_pilot.py utilities (SHA f7733b23602d9883159bbedc2ea712fb3
054e9e7963950c6fd6c10c1f582868f); no previous source/config/receipt is modified.
"""
from __future__ import annotations

import argparse
from collections import Counter
import concurrent.futures as futures
import gzip
import json
import multiprocessing as mp
import os
from pathlib import Path
import socket
import sys
import time

sys.dont_write_bytecode = True
from live_memory_policy_32g_v1 import (BASIS, OLD_SOURCE_SHA, MemoryMonitor, ProcSampler,
                                   file_reference, require_reference,
                                   validate_approval_payload, validate_root_intent)


def run_one(task):
    # Spawn workers call the original worker path without monkeypatching its recipe.
    from run_pilot import run_one as original_run_one
    return original_run_one(task)


def save_gzip_new(path, value):
    from common import prewrite_guard
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
    compressed = gzip.compress(raw, mtime=0)
    prewrite_guard(path, len(compressed), reserve_bytes=2 << 20)
    with path.open("xb") as stream:
        stream.write(compressed)
        stream.flush()
        os.fsync(stream.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root-preflight", type=Path, required=True)
    parser.add_argument("--approval", type=Path, required=True)
    parser.add_argument("--approval-bytes", type=int, required=True)
    parser.add_argument("--approval-sha256", required=True)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args()

    # Authorization is checked before importing chemistry or opening any LMDB.
    approval_ref = {"path": str(args.approval.absolute()), "bytes": args.approval_bytes,
                    "sha256": args.approval_sha256}
    require_reference(approval_ref)
    approval = json.loads(args.approval.read_text(encoding="utf-8"))
    config_ref, prepared_ref = file_reference(args.config), file_reference(args.prepared / "prepared.json")
    validate_approval_payload(approval, config_ref, prepared_ref)
    old_sources = []
    for name, expected in OLD_SOURCE_SHA.items():
        actual = file_reference(Path(__file__).parent / name)
        if actual["sha256"] != expected:
            raise ValueError("PREVIOUS_REGISTERED_SOURCE_CHANGED:" + name)
        old_sources.append(actual)
    from common import (load_config, new_output_directory, reference, require_pin,
                        runtime_guard, write_json_new)
    from run_pilot import parquet_new, persist_result, verify_readback
    config = load_config(args.config)
    runtime = runtime_guard(args.workers)
    if args.workers != 16 or runtime["allocated_cpus"] != 16 or os.getuid() != 1278:
        raise ValueError("LIVE_MEMORY_EXCEPTION_REQUIRES_THIS_UID_AND_EXACTLY_16_CPUS")
    receipt = json.loads(args.root_preflight.read_text(encoding="utf-8"))
    real_memory_bytes = validate_root_intent(receipt, approval_ref, config_ref, prepared_ref,
                                             node=socket.gethostname().split(".")[0], now_epoch=time.time())
    execution_refs = old_sources + [file_reference(__file__),
                                   file_reference(Path(__file__).parent / "live_memory_policy_32g_v1.py")]
    if any(pin not in receipt["request"]["source_references"] for pin in execution_refs):
        raise ValueError("ROOT_INTENT_EXECUTION_SOURCE_PINS_MISSING")
    if receipt["uid"] != os.getuid():
        raise ValueError("ROOT_INTENT_UID_MISMATCH")
    prepared = json.loads((args.prepared / "prepared.json").read_text(encoding="utf-8"))
    if prepared["status"] != "PILOT_INPUTS_READY_NOT_COMPUTED" or prepared["config"] != config_ref or prepared["molecules"] != 336:
        raise ValueError("CLOSED_ORIGINAL_336_PILOT_PREPARED_REQUIRED")
    for pin in prepared["outputs"]:
        require_pin(pin)
    tasks = [json.loads(line) for line in (args.prepared / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    if len(tasks) != 336 or len({task["meta"]["molecule_id"] for task in tasks}) != 336:
        raise ValueError("ACTUAL_RECORD_MANIFEST_MISMATCH:336_UNIQUE_PILOT_TASKS_REQUIRED")
    if config["max_output_bytes"] != 8 * 1024 ** 3:
        raise ValueError("ORIGINAL_8_GIB_OUTPUT_CAP_REQUIRED")
    out = new_output_directory(args.output, config)
    (out / "reproduction").mkdir(mode=0o700)
    started = time.monotonic()
    failure, worker_failures, results, records = None, [], [], []
    submitted = 0
    try:
        sampler = ProcSampler(runtime["job_id"], real_memory_bytes)
    except Exception as exc:
        message = type(exc).__name__ + ":" + str(exc)
        def sampler(error=message):
            raise RuntimeError(error)
    monitor = MemoryMonitor(sampler)
    monitor.start()
    try:
        # A failed admission starts no worker or UFF calculation.
        if monitor.allow_dispatch():
            import science
            with futures.ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context("spawn"),
                                             initializer=science.worker_init, initargs=(str(args.config),)) as pool:
                iterator, active, exhausted = iter(tasks), {}, False
                while active or not exhausted:
                    while not exhausted and len(active) < 16 and failure is None and monitor.allow_dispatch():
                        try:
                            task = next(iterator)
                        except StopIteration:
                            exhausted = True
                            break
                        active[pool.submit(run_one, task)] = task["meta"]["molecule_id"]
                        submitted += 1
                    if not active:
                        break
                    completed, _ = futures.wait(active, timeout=0.5, return_when=futures.FIRST_COMPLETED)
                    for future in completed:
                        mid = active.pop(future)
                        try:
                            result = future.result()
                            records.append(persist_result(out, mid, result, config["max_output_bytes"]))
                            results.append(result)
                        except Exception as exc:
                            item = {"molecule_id": mid, "exception_type": type(exc).__name__, "error": str(exc)[:4000]}
                            worker_failures.append(item)
                            if failure is None:
                                failure = {"error": "WORKER_OR_PERSISTENCE_FAILED_STOP_DISPATCH", "details": item}
                    if completed:
                        write_json_new(out / f"progress_{len(results):06d}_{len(worker_failures):03d}.json",
                                       {"completed": len(results), "submitted": submitted, "expected": 336,
                                        "dispatch_allowed": failure is None and monitor.allow_dispatch(),
                                        "resource_denial": monitor.first_denial,
                                        "seconds": time.monotonic() - started})
                    # Denial is sticky; active molecules are merely drained. No retry,
                    # cancel_futures, signal, kill, or scientific parameter change.
        else:
            failure = {"error": "LIVE_MEMORY_ADMISSION_FAILED_NO_SCIENCE_STARTED"}
    except Exception as exc:
        # Executor context joins running work. The independent monitor remains active.
        failure = {"exception_type": type(exc).__name__, "error": str(exc)[:4000]}
        for future, mid in locals().get("active", {}).items():
            try:
                result = future.result()
                records.append(persist_result(out, mid, result, config["max_output_bytes"]))
                results.append(result)
            except Exception as child_exc:
                worker_failures.append({"molecule_id": mid, "exception_type": type(child_exc).__name__, "error": str(child_exc)[:4000]})

    # Keep monitoring during serialization/readback as part of this same allocation.
    summaries = sorted((result["summary"] for result in results), key=lambda row: row["molecule_id"])
    conformers = sorted((row for result in results for row in result["conformers"]), key=lambda row: (row["molecule_id"], row["sprime_conf_idx"]))
    output_names = []
    try:
        from statistics_tools import aggregate_statistics
        write_json_new(out / "worker_failures.json", worker_failures)
        parquet_new(out / "molecules.parquet", summaries)
        parquet_new(out / "conformers.parquet", conformers, coordinates=True)
        readback = verify_readback(out / "conformers.parquet", conformers)
        write_json_new(out / "orders.json", {"seed": config["order_seed"],
                       "molecules": [{"molecule_id": result["summary"]["molecule_id"], "orders": result["orders"]} for result in results],
                       "pm7_energy_order_status": "NATIVE_ANCHOR_DIAGNOSTIC_PENDING_FINAL_CANONICAL_WP5_HOF"})
        write_json_new(out / "conformer_statistics.json", aggregate_statistics(results))
        write_json_new(out / "reproduction_manifest.json", sorted(records, key=lambda row: row["molecule_id"]))
        output_names = ["worker_failures.json", "molecules.parquet", "conformers.parquet", "orders.json", "conformer_statistics.json", "reproduction_manifest.json"]
    except Exception as exc:
        failure = {"error": "FINALIZATION_FAILED", "exception_type": type(exc).__name__, "details": str(exc)[:4000]}
        readback = {"status": "NOT_PASSED"}
    finally:
        monitor.stop()
    if monitor.first_denial is not None:
        failure = {"error": "RESOURCE_DENIAL_STOPPED_NEW_DISPATCH_CURRENT_MOLECULES_DRAINED",
                   "resource_denial": monitor.first_denial, "other_failure": failure}
    if len(results) != 336 or worker_failures or any(row["status"] == "IMPLEMENTATION_ERROR" for row in summaries):
        failure = {"error": "PILOT_NOT_FULLY_COMPLETED_OR_HAS_IMPLEMENTATION_ERRORS", "details": failure}
    save_gzip_new(out / "memory_evidence.json.gz", {"memory_basis": BASIS, "samples": monitor.samples,
                   "first_denial": monitor.first_denial, "poll_seconds": 1.0, "max_sample_age_seconds": 2.0,
                   "owned_scope": "this UID, this job ID, stable parent+descendant identity and matching cgroup/PGID/SID",
                   "action": "STOP_NEW_DISPATCH_AND_DRAIN_RUNNING_WITHOUT_SIGNALS"})
    output_names.append("memory_evidence.json.gz")
    report = {"status": "PILOT_INCOMPLETE" if failure else "PILOT_COMPLETED_REQUIRES_ROOT_REVIEW",
              "failure": failure, "runtime": runtime, "memory_basis": BASIS,
              "approval_reference": approval_ref, "root_preflight": reference(args.root_preflight),
              "config": config_ref, "prepared": prepared_ref, "old_source_references": old_sources,
              "expected_molecules": 336, "submitted_molecules": submitted, "completed_molecules": len(results),
              "never_dispatched_molecules": 336 - submitted, "conformers": len(conformers),
              "status_counts": dict(Counter(row["status"] for row in summaries)),
              "science_worker_seconds": sum(row["elapsed_seconds"] for row in summaries),
              "elapsed_seconds": time.monotonic() - started, "parquet_readback": readback,
              "resource_denial": monitor.first_denial, "memory_samples": len(monitor.samples),
              "monitor_thread_closed": monitor.thread is None or not monitor.thread.is_alive(),
              "outputs": [reference(out / name) for name in output_names],
              "output_cap_bytes": config["max_output_bytes"], "signals_sent": False,
              "original_data_modified": False, "scientific_recipe_changed": False,
              "full_population_completion_claimed": False, "common_population_v1_published": False,
              "accounting_status": "Root must attach actual Slurm parent AllocCPUS*ElapsedRaw including failures"}
    write_json_new(out / "receipt.json", report)
    print(json.dumps({"status": report["status"], "completed_molecules": len(results), "output": str(out)}))
    return 1 if failure else 0


if __name__ == "__main__":
    raise SystemExit(main())
