"""Run one reviewed development command with bounded own-resource supervision.

This launcher never submits Slurm jobs and never signals a process group. Only
the exact child/descendant identities observed after this invocation's Popen
may be terminated. Foreign GPU processes are recorded and never signalled.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

import psutil

from runtime_monitor import (gpu_observation, owned_output_bytes, owned_process_observation,
                             inherited_log_bytes, capture_process_identity)
from private_runtime_storage import PrivateStorage, _write_exclusive

IDENTITY_KEYS = ("pid", "uid", "boot_id", "start_ticks", "pgid", "sid",
                 "argv_sha256", "cgroup", "slurm_job_id")
# psutil derives create_time from wall-clock boot time. A clock correction can
# change it for a live process. Kernel boot_id/start_ticks bind its lifetime;
# created remains recorded for diagnostics and is never signal authority.
RECORDED_KEYS = (*IDENTITY_KEYS, "created")


def recorded_process_state(row):
    if not all(key in row for key in RECORDED_KEYS):
        return {"status": "IDENTITY_CHANGED", "reason": "incomplete_recorded_identity"}
    try:
        current = capture_process_identity(row["pid"], expected_cgroup=row["cgroup"])
    except (OSError, psutil.Error) as exc:
        return {"status": "UNREADABLE", "reason": type(exc).__name__}
    if current["status"] in {"GONE", "EXITING"}:
        return current
    if current["status"] != "ACTIVE" or any(current.get(key) != row[key] for key in IDENTITY_KEYS):
        return {"status": "IDENTITY_CHANGED", "current": current}
    return {"status": "MATCH", "current": current,
            "wall_clock_creation_time_changed": current.get("created") != row["created"]}


def same_owned_process(row):
    try:
        return psutil.Process(row["pid"]) if recorded_process_state(row)["status"] == "MATCH" else None
    except psutil.NoSuchProcess:
        return None


def live_recorded(rows):
    result = []
    for row in rows.values():
        state = recorded_process_state(row)
        if state["status"] == "MATCH":
            result.append(row)
        elif state["status"] not in {"GONE", "EXITING"}:
            result.append({**row, "identity_error": state})
    return result


def stop_recorded(rows, *, grace_seconds=15):
    """Recheck identity immediately before individual signals; no group kills."""
    actions = []
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for row in reversed(tuple(rows.values())):
            try:
                process = same_owned_process(row)
                if process is not None:
                    # The site's Python lacks pidfd_open; this is a rechecked
                    # operation, not atomic PID-reuse protection.
                    process.send_signal(sig)
                    actions.append({"pid": row["pid"], "created": row["created"], "signal": int(sig)})
                else:
                    state = recorded_process_state(row)
                    if state["status"] not in {"GONE", "EXITING"}:
                        actions.append({"pid": row["pid"], "signal_refused": state})
            except psutil.NoSuchProcess:
                actions.append({"pid": row["pid"], "state": "NATURAL_EXIT_BEFORE_SIGNAL"})
            except psutil.Error as exc:
                actions.append({"pid": row["pid"], "identity_or_signal_error": type(exc).__name__})
        deadline = time.monotonic() + (grace_seconds if sig == signal.SIGTERM else 5)
        while time.monotonic() < deadline and live_recorded(rows):
            time.sleep(.2)
    remaining = live_recorded(rows)
    return {"actions": actions, "remaining": remaining}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--record", type=Path, required=True)
    parser.add_argument("--gpu-uuid", required=True)
    parser.add_argument("--wall-seconds", type=int, default=2100)
    parser.add_argument("--rss-limit-bytes", type=int, default=56 * 1024**3)
    parser.add_argument("--output-budget-bytes", type=int, default=2 * 1024**3)
    parser.add_argument("--poll-seconds", type=float, default=2.)
    parser.add_argument("--private-scratch-root", type=Path)
    parser.add_argument("--private-storage-budget-bytes", type=int, default=2 * 1024**3)
    parser.add_argument("--compile-cache-root", type=Path)
    parser.add_argument("--compile-cache-key")
    parser.add_argument("--reuse-compile-cache", action="store_true")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command or not Path(command[0]).is_absolute() or not os.environ.get("SLURM_JOB_ID"):
        raise ValueError("Explicit logical interpreter/command in an existing owned Slurm allocation required")
    if not 60 <= args.wall_seconds <= 7200 or not 1 <= args.poll_seconds <= 10:
        raise ValueError("Bounded monitoring wall/poll interval required")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != args.gpu_uuid or not args.gpu_uuid.startswith("GPU-"):
        raise ValueError("Supervisor and child must share one explicit physical GPU UUID")
    if not (128 * 1024**2 <= args.output_budget_bytes <= 2 * 1024**3 and 0 < args.rss_limit_bytes <= 56 * 1024**3):
        raise ValueError("Explicit bounded output/RSS caps required")
    journal = args.record.with_suffix(args.record.suffix + ".jsonl")
    storage_receipt = args.record.with_suffix(args.record.suffix + ".storage.json")
    if args.record.absolute().is_relative_to(args.output_root.absolute()):
        raise ValueError("Supervision records must be outside the fresh child output root")
    if args.record.exists() or journal.exists() or storage_receipt.exists() or args.output_root.exists():
        raise FileExistsError("Fresh supervision paths/output root required")
    if args.private_scratch_root is None and (args.compile_cache_root or args.compile_cache_key or args.reuse_compile_cache):
        raise ValueError("Explicit task scratch required with compiler cache settings")
    args.record.parent.mkdir(parents=True, exist_ok=True)
    before = gpu_observation(args.gpu_uuid, own_pids=(os.getpid(),))
    if before["foreign_processes"]:
        raise RuntimeError("GPU was occupied before this child started; no work launched")
    started = time.monotonic()
    child_environment = dict(os.environ)
    # Leave explicit room for supervision/Slurm logs outside the child root.
    child_environment["MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES"] = str(args.output_budget_bytes - 96 * 1024**2)
    storage, storage_final, storage_cleanup_errors = None, None, []
    if args.private_scratch_root is not None:
        for root in (args.private_scratch_root, args.compile_cache_root):
            if root is not None and (root.absolute().is_relative_to(args.output_root.absolute())
                                     or args.output_root.absolute().is_relative_to(root.absolute())):
                raise ValueError("Private storage and persistent child output must be disjoint")
        storage = PrivateStorage(args.private_scratch_root, budget_bytes=args.private_storage_budget_bytes,
                                 cache_root=args.compile_cache_root, cache_key=args.compile_cache_key,
                                 reuse_cache=args.reuse_compile_cache)
        storage_pin = _write_exclusive(storage_receipt, storage.bindings)
        child_environment.update(storage.bindings["environment"])
        child_environment["MODEL_V3_STORAGE_BINDINGS_PATH"] = str(storage_receipt.absolute())
        child_environment["MODEL_V3_STORAGE_BINDINGS_SHA256"] = storage_pin
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=True, env=child_environment)
    observed, first_failure, retirement = {}, None, None
    last_output_bytes = 0
    launch_identity = None
    supervisor_cgroup = Path("/proc/self/cgroup").read_text()
    try:
        launch_identity = capture_process_identity(child.pid, expected_cgroup=supervisor_cgroup,
                                                   expected_argv=command)
        if launch_identity["status"] == "ACTIVE":
            observed[(child.pid, launch_identity["start_ticks"])] = launch_identity
        elif launch_identity["status"] not in {"GONE", "EXITING"}:
            raise RuntimeError("Root child argv/session/actual Slurm cgroup could not be bound: " + str(launch_identity))
        if storage is not None:
            storage.start()
        while child.poll() is None:
            try:
                private_observation = storage.check() if storage is not None else None
                processes = owned_process_observation(child.pid)
                for row in processes["processes"]:
                    bound = capture_process_identity(row["pid"], expected_cgroup=supervisor_cgroup)
                    if bound["status"] == "ACTIVE":
                        key = row["pid"], bound["start_ticks"]
                        if key in observed and any(observed[key][name] != bound[name] for name in IDENTITY_KEYS):
                            raise RuntimeError("Live observed child identity changed; no signal authority inferred")
                        observed[key] = {**bound, "rss_bytes": row["rss_bytes"]}
                        row["identity"] = bound
                    elif bound["status"] not in {"GONE", "EXITING"}:
                        raise RuntimeError("Live descendant identity/cgroup could not be bound: " + str(bound))
                gpu = gpu_observation(args.gpu_uuid, own_pids=[row["pid"] for row in processes["processes"]])
                journal_bytes = journal.stat().st_size if journal.exists() else 0
                log_bytes = inherited_log_bytes(exclude_root=args.output_root)
                if log_bytes > 32 * 1024**2:
                    raise MemoryError("Owned inherited job logs exceeded their explicit 32 MiB bound")
                receipt_bytes = storage_receipt.stat().st_size if storage is not None else 0
                last_output_bytes = owned_output_bytes(args.output_root) + journal_bytes + log_bytes + receipt_bytes
                elapsed = time.monotonic() - started
                row = {"elapsed_seconds": elapsed, "processes": processes, "gpu": gpu,
                       "inherited_job_log_bytes": log_bytes, "supervision_journal_bytes": journal_bytes,
                       "output_bytes": last_output_bytes, "private_storage": private_observation}
                encoded = json.dumps(row, allow_nan=False) + "\n"
                if journal_bytes + len(encoded.encode()) > 32 * 1024**2:
                    raise MemoryError("Supervision journal reached its explicit 32 MiB bound")
                with journal.open("a") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                own_gpu_memory = sum(item["used_memory_bytes"] or 0 for item in gpu["compute_processes"] if item["own"])
                if elapsed >= args.wall_seconds - 30:
                    raise TimeoutError("Owned child reached the wall cap/finalization reserve")
                if processes["rss_sum_bytes"] > args.rss_limit_bytes:
                    raise MemoryError("Owned child process tree exceeded RSS cap")
                if last_output_bytes > args.output_budget_bytes - 16 * 1024**2:
                    raise MemoryError("Owned output reached finalization reserve")
                if own_gpu_memory > .85 * gpu["total_bytes"]:
                    raise MemoryError("Owned GPU process memory exceeded 85% of physical capacity")
            except psutil.NoSuchProcess:
                if child.poll() is None:
                    raise
                break
            time.sleep(args.poll_seconds)
    except BaseException as exc:
        first_failure = {"type": type(exc).__name__, "message": str(exc)}
        # Capture newly created own descendants before closing known identities.
        try:
            for row in owned_process_observation(child.pid)["processes"]:
                bound = capture_process_identity(row["pid"], expected_cgroup=supervisor_cgroup)
                if bound["status"] == "ACTIVE":
                    key = row["pid"], bound["start_ticks"]
                    if key not in observed:
                        observed[key] = bound
        except (OSError, psutil.Error) as secondary:
            first_failure["final_process_observation_error"] = type(secondary).__name__
        retirement = stop_recorded(observed)
    finally:
        if child.poll() is None:
            retirement = stop_recorded(observed)
        try:
            code = child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            code = None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and live_recorded(observed):
            time.sleep(.2)
        remaining = live_recorded(observed)
        if remaining:
            retirement = stop_recorded(observed)
        if code != 0 and first_failure is None:
            first_failure = {"phase": "child_exit", "exit_code": code}
        if storage is not None:
            try:
                storage_final = storage.stop()
            except BaseException as exc:
                storage_final = storage.observation()
                problem = {"type": type(exc).__name__, "message": str(exc)}
                storage_cleanup_errors.append(problem)
                if first_failure is None:
                    first_failure = {"phase": "private_storage_finalization", **problem}
        report = {"status": "COMPLETED" if code == 0 and first_failure is None and not remaining else "FAILED",
                  "command": command, "job_id": os.environ["SLURM_JOB_ID"], "child_pid": child.pid,
                  "launch_identity": launch_identity, "supervisor_slurm_cgroup": supervisor_cgroup,
                  "elapsed_seconds": time.monotonic() - started, "exit_code": code,
                  "first_failure": first_failure, "retirement": retirement,
                  "remaining_recorded_processes_before_retirement": remaining,
                  "output_budget_bytes": args.output_budget_bytes, "last_output_bytes": last_output_bytes,
                  "child_output_budget_bytes": int(child_environment["MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES"]),
                  "private_storage_bindings_path": str(storage_receipt.absolute()) if storage is not None else None,
                  "private_storage_final": storage_final, "private_storage_cleanup_errors": storage_cleanup_errors,
                  "gpu_uuid": args.gpu_uuid, "foreign_gpu_processes_signalled": False,
                  "supervisor_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        args.record.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return 0 if report["status"] == "COMPLETED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
