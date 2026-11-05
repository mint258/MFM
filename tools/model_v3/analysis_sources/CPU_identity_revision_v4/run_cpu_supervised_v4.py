"""Run CPU regression with durable strict identities and opt-in pytest4 receipts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil

from identity_revision_v4 import (EventLog, IdentityRegistry, IdentityViolation,
    PINS_SCHEMA, REGISTRATION_DIRECTORY, capture_identity, file_ref, load_fixed_control,
    load_fixed_runtime, partition_groups, pytest_roles, read_json, require, changed_keys,
    verify_source_pins)

HERE = Path(__file__).resolve().parent
RUNS = Path("/share/home/zixiao/descriptor_analysis/runs/model_v3_20261025")


def enrollment_context(command, output, pins_path, pins_sha, control):
    """Independently derive the same four commands from the frozen assignment."""
    job = os.environ["SLURM_JOB_ID"]
    plan_path, plan_sha = Path(os.environ["MODEL_V3_CONTROL_PLAN"]), os.environ["MODEL_V3_CONTROL_PLAN_SHA"]
    plan, assignment = control.verify_frozen_plan(plan_path, plan_sha, verify_runtime=False)
    contract = plan["contract"]
    index = int(os.environ["MODEL_V3_PARTITION_INDEX"])
    bindings = control.launch_bindings(plan, plan_sha, index)
    require(all(os.environ.get(key) == value for key, value in bindings.items()),
            "Exact frozen control-plan bindings required")
    require(command == control.expected_supervisor_command(bindings, os.environ["MODEL_V3_EXPECTED_NODE"], job),
            "Exact new worker command differs from frozen plan")
    worker_ref = file_ref(HERE / "run_regression_worker_identity_v4.py")
    require(contract["runner"] == {"path": worker_ref["path"], "sha256": worker_ref["sha256"]},
            "Control plan does not bind the new worker")
    pins_ref = file_ref(pins_path)
    require(pins_ref["sha256"] == pins_sha and
            {"path": pins_ref["path"], "sha256": pins_sha} in contract["control_files"],
            "Control plan must bind the exact new runtime inventory")
    root = Path(contract["tree"])
    files = [root / name for name in assignment["assignments"][index]["files"]]
    roles = pytest_roles(command[0], root, output, partition_groups(files))
    return {"source_pins": pins_ref, "worker_source": worker_ref,
            "control_plan": file_ref(plan_path), "roles": roles}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--source-pins", type=Path, required=True)
    parser.add_argument("--source-pins-sha256", required=True)
    parser.add_argument("--registration-mode", choices=["strict", "pytest4"], default="strict")
    parser.add_argument("--wall-seconds", type=int, default=3300)
    parser.add_argument("--rss-limit-bytes", type=int, default=48 * 1024**3)
    parser.add_argument("--output-budget-bytes", type=int, default=2 * 1024**3)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    require(command and Path(command[0]).is_absolute() and os.environ.get("SLURM_JOB_ID", "").isdigit()
            and os.environ.get("CUDA_VISIBLE_DEVICES") == ""
            and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16,
            "Explicit CPU-only command in owned >=16CPU allocation required")
    require(60 <= args.wall_seconds <= 3600 and 0 < args.rss_limit_bytes <= 48 * 1024**3,
            "Original bounded CPU wall/RSS required")
    require(args.output_budget_bytes == 2 * 1024**3
            and not args.record.absolute().is_relative_to(args.output_root.absolute()),
            "Original2GiB output cap and external record required")
    journal = args.record.with_suffix(".journal.jsonl")
    events_path = args.record.with_suffix(".identity_events.jsonl")
    storage_receipt = args.record.with_suffix(".storage.json")
    fixture_receipt = args.record.with_suffix(".fixture_policy.json")
    require(not any(path.exists() for path in (args.output_root, args.record, journal,
                                               storage_receipt, fixture_receipt, events_path)),
            "Fresh output and supervision paths required")
    pins = verify_source_pins(args.source_pins, args.source_pins_sha256)
    require(file_ref(Path(__file__).resolve()) in pins["runtime_sources"]
            and file_ref(HERE / "identity_revision_v4.py") in pins["runtime_sources"],
            "Supervisor/core not bound by this source inventory")
    runtime = load_fixed_runtime(pins)
    monitor, cleanup = runtime["runtime_monitor"], runtime["run_supervised"]
    storage_module = runtime["private_runtime_storage"]
    context = None
    if args.registration_mode == "pytest4":
        context = enrollment_context(command, args.output_root, args.source_pins,
                                     args.source_pins_sha256, load_fixed_control(pins))
    group = Path("/proc/self/cgroup").read_text()
    args.record.parent.mkdir(parents=True, exist_ok=True)
    emit = EventLog(events_path)
    # The fixture census is copied unchanged from the old wrapper, not monkeypatched.
    from fixture_census_v4 import fixture_output_bytes, fixture_policy
    require(file_ref(HERE / "fixture_census_v4.py") in pins["runtime_sources"],
            "Fixture census source not bound")
    output_bytes, policy = fixture_policy(args.output_root, args.record, args.source_pins, args.source_pins_sha256)
    storage_module._write_exclusive(fixture_receipt, policy)
    storage = storage_module.PrivateStorage(Path("/tmp") / ("mv3n_" + os.environ["SLURM_JOB_ID"]),
                                            budget_bytes=args.output_budget_bytes)
    storage_sha = storage_module._write_exclusive(storage_receipt, storage.bindings)
    environment = {**os.environ, **storage.bindings["environment"],
                   "MODEL_V3_STORAGE_BINDINGS_PATH": str(storage_receipt),
                   "MODEL_V3_STORAGE_BINDINGS_SHA256": storage_sha,
                   "MODEL_V3_CPU_IDENTITY_SOURCE_PINS": str(args.source_pins.absolute()),
                   "MODEL_V3_CPU_IDENTITY_SOURCE_PINS_SHA": args.source_pins_sha256}
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=True, env=environment)
    registry = None
    cleanup_diagnostics = []
    first_failure, retirement, remaining, code = None, None, [], None
    start, launch, last_bytes = time.monotonic(), None, 0
    registration = args.output_root / REGISTRATION_DIRECTORY
    storage.start()

    def capture(pid, expected_argv=None):
        return capture_identity(monitor, pid, expected_cgroup=group, expected_argv=expected_argv)

    def checkpoint_sources():
        verify_source_pins(args.source_pins, args.source_pins_sha256)

    def refresh_manifest():
        manifest_path = registration / "manifest.json"
        if context is not None and manifest_path.exists():
            value, ref = read_json(manifest_path), file_ref(manifest_path)
            registry.set_manifest(value, ref)

    def check_receipts():
        if registry.manifest is None:
            return
        for role in registry.manifest["roles"]:
            path = registration / (role["role"] + ".exec.json")
            if role["role"] not in registry.roles and path.exists():
                receipt = read_json(path)
                bound = capture(receipt["child_pid"])
                require(bound["status"] == "ACTIVE", "Exec receipt child is no longer ACTIVE")
                key = bound["pid"], bound["start_ticks"]
                if key not in registry.pending:
                    registry.observe(bound)
                registry.enroll_receipt(receipt, bound)

    def discover_without_authority():
        if registry is None:
            return
        try:
            for row in monitor.owned_process_observation(child.pid)["processes"]:
                bound = capture(row["pid"])
                if bound["status"] not in {"GONE", "EXITING"}:
                    registry.quarantine(bound, "Discovered during failed cleanup; no enrollment permitted")
        except psutil.NoSuchProcess:
            pass
        except BaseException as exc:
            cleanup_diagnostics.append({"phase": "cleanup_discovery", "type": type(exc).__name__, "message": str(exc)})

    def live_unresolved():
        if registry is None:
            return [{"status": "UNRESOLVED_DESCENDANT_SCOPE", "pid": child.pid,
                     "reason": "Root launch was never bound; no descendant cleanup authority"}]
        try:
            rows = cleanup.live_recorded(registry.observed) + registry.unresolved(capture)
        except BaseException as exc:
            rows = [{"status": "UNRESOLVED_OBSERVATION", "type": type(exc).__name__, "message": str(exc)}]
        if cleanup_diagnostics:
            rows.append({"status": "UNRESOLVED_CLEANUP_SCOPE", "diagnostics": list(cleanup_diagnostics)})
        return rows

    def retire():
        # stop_recorded performs a complete MATCH immediately before each signal.
        # We never overwrite observed in an exception handler.
        discover_without_authority()
        try:
            result = cleanup.stop_recorded(registry.observed if registry is not None else {})
        except BaseException as exc:
            cleanup_diagnostics.append({"phase": "strict_retirement", "type": type(exc).__name__, "message": str(exc)})
            result = {"actions": [], "remaining": []}
        result["remaining"] = live_unresolved()
        return result

    try:
        launch = capture(child.pid, expected_argv=command)
        require(launch["status"] == "ACTIVE", "Full root launch identity required")
        registry = IdentityRegistry(launch, emit, context=context)
        while child.poll() is None:
            try:
                processes = monitor.owned_process_observation(child.pid)
                refresh_manifest()
                for process in processes["processes"]:
                    bound = capture(process["pid"])
                    if bound["status"] == "ACTIVE":
                        registry.observe(bound)
                    elif bound["status"] not in ("GONE", "EXITING"):
                        prior = [value for key, value in registry.observed.items() if key[0] == bound['pid']]
                        if not prior:
                            prior = [value['first'] for key, value in registry.pending.items() if key[0] == bound['pid']]
                        diagnostic = bound.get('diagnostic_identity', bound)
                        registry.last_failure = {"kind": "CAPTURE_REJECTED", "before": prior[-1] if prior else None,
                                                 "after": diagnostic, "capture_result": bound,
                                                 "changed_keys": changed_keys(prior[-1], diagnostic) if prior else []}
                        emit(registry.last_failure)
                        raise RuntimeError("CPU descendant left the bound identity/cgroup")
                check_receipts()
                private = storage.check()
                logs = monitor.inherited_log_bytes(exclude_root=args.output_root)
                journal_bytes = journal.stat().st_size if journal.exists() else 0
                event_bytes = events_path.stat().st_size if events_path.exists() else 0
                last_bytes = (output_bytes(args.output_root) + private["last"]["bytes"] + logs
                              + journal_bytes + event_bytes + storage_receipt.stat().st_size
                              + fixture_receipt.stat().st_size)
                row = {"elapsed_seconds": time.monotonic() - start, "processes": processes,
                       "total_observed_bytes": last_bytes, "private_storage": private,
                       "pending_births": [list(k) for k in registry.pending],
                       "enrolled_pytest_roles": sorted(registry.roles)}
                encoded = json.dumps(row) + "\n"
                require(journal_bytes + event_bytes + len(encoded.encode()) <= 32 * 1024**2
                        and logs <= 32 * 1024**2, "Original supervision/job log bounds exceeded")
                with journal.open("a") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                require(processes["rss_sum_bytes"] <= args.rss_limit_bytes,
                        "Owned CPU child tree exceeded RSS cap (including pending)")
                require(last_bytes <= args.output_budget_bytes - 16 * 1024**2,
                        "Owned output/private scratch reached original reserve")
                require(time.monotonic() - start <= args.wall_seconds - 30,
                        "CPU child reached wall/finalization reserve")
            except psutil.NoSuchProcess:
                if child.poll() is None:
                    raise
                break
            time.sleep(1.0)
        registry.require_completed_enrollment()
    except BaseException as exc:
        first_failure = {"type": type(exc).__name__, "message": str(exc),
                         "identity_detail": registry.last_failure if registry else None}
        retirement = retire()
    finally:
        if child.poll() is None:
            retirement = retire()
        try:
            code = child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            code = None
        remaining = live_unresolved()
        if remaining:
            retirement = retire()
            remaining = live_unresolved()
        if code != 0 and first_failure is None:
            first_failure = {"phase": "child_exit", "exit_code": code}
        try:
            private_final = storage.stop()
        except BaseException as exc:
            private_final = storage.observation()
            first_failure = first_failure or {"phase": "storage_close", "type": type(exc).__name__, "message": str(exc)}
        try:
            extra = sum(path.stat().st_size for path in (journal, events_path, storage_receipt, fixture_receipt) if path.exists())
            last_bytes = (output_bytes(args.output_root) + private_final["last"]["bytes"]
                          + monitor.inherited_log_bytes(exclude_root=args.output_root) + extra)
            require(last_bytes <= args.output_budget_bytes - 16 * 1024**2,
                    "Final CPU output/private scratch exceeded original reserve")
        except BaseException as exc:
            first_failure = first_failure or {"phase": "final_census", "type": type(exc).__name__, "message": str(exc)}
        try:
            checkpoint_sources()
        except BaseException as exc:
            first_failure = first_failure or {"phase": "source_changed", "type": type(exc).__name__, "message": str(exc)}
        report = {"schema": "model_v3_CPU_supervisor_revision_v4",
                  "status": "COMPLETED" if code == 0 and first_failure is None and not remaining else "FAILED",
                  "job_id": os.environ["SLURM_JOB_ID"], "command": command, "launch_identity": launch,
                  "supervisor_cgroup": group, "exit_code": code, "first_failure": first_failure,
                  "retirement": retirement, "remaining": remaining, "elapsed_seconds": time.monotonic() - start,
                  "last_total_bytes": last_bytes, "private_storage": private_final,
                  "sources_sha256": {ref["path"]: ref["sha256"] for ref in pins["runtime_sources"]},
                  "source_inventory": file_ref(args.source_pins), "registration_mode": args.registration_mode,
                  "identity_events": file_ref(events_path) if events_path.exists() else None,
                  "enrolled_pytest_roles": sorted(registry.roles) if registry else [],
                  "cleanup_diagnostics": cleanup_diagnostics,
                  "unresolved_enrollment_blocks_C0": True, "gpu_initialization_permitted": False}
        storage_module._write_exclusive(args.record, report)
    return int(report["status"] != "COMPLETED")


if __name__ == "__main__":
    raise SystemExit(main())
