"""Run exactly fifteen new synthetic fixtures after central-v2 fresh admission."""
import argparse
import os
from pathlib import Path
import subprocess
import threading
import time
import traceback

from ..cpu_auto_memory_queue_v2 import runtime as central
from ..cpu_auto_memory_queue_v2 import shared
from . import policy


class Capture:
    """Retain a bounded log prefix and continue draining without sending signals."""
    def __init__(self, stream, path):
        self.stream, self.path = stream, path
        self.total = self.kept = 0
        self.error = None
        self.thread = threading.Thread(target=self.drain, daemon=True)

    def drain(self):
        target = None
        try:
            target = self.path.open("xb")
        except Exception as exc:
            self.error = repr(exc)
        try:
            while True:
                chunk = self.stream.read(65536)
                if not chunk:
                    break
                self.total += len(chunk)
                take = min(len(chunk), policy.LOG_CAP - self.kept)
                if target is not None and take > 0:
                    try:
                        target.write(chunk[:take])
                        target.flush()
                        self.kept += take
                    except Exception as exc:
                        self.error = repr(exc)
                        target.close()
                        target = None
            if target is not None:
                target.flush()
                os.fsync(target.fileno())
        except Exception as exc:
            self.error = repr(exc)
        finally:
            if target is not None:
                target.close()
            self.stream.close()

    def result(self):
        return {"reference": shared.pin(self.path) if self.path.stat().st_size <= 2 * 1024 ** 2 else
                    {"path": str(self.path), "bytes": self.path.stat().st_size,
                     "sha256": file_sha(self.path)},
                "bytes_observed": self.total, "bytes_retained": self.kept,
                "truncated": self.total > self.kept, "capture_error": self.error}


def file_sha(path):
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def owned_bytes(root):
    """Only this newly created task-owned output tree is inspected."""
    total = 0
    for path in root.rglob("*"):
        shared.need(not path.is_symlink(), "NO_SYMLINK_IN_OWNED_FIXTURE_OUTPUT")
        status = path.stat()
        total += max(status.st_size, status.st_blocks * 512)
    return total


def run_suite(row, plan_path, started_path, output, deadline, stop_notice):
    own = output / row["suite_id"]
    own.mkdir()
    temporary = own / "synthetic_tmp"
    temporary.mkdir()
    env = os.environ.copy()
    env["TMPDIR"] = str(temporary)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    argv = [shared.PY, "-B", "-m", policy.HERE.replace("/", ".") + ".child",
        "--plan", str(plan_path), "--parent-started", str(started_path),
        "--parent-pid", str(os.getpid()), "--suite-id", row["suite_id"]]
    shared.write_new(own / "dispatch.json", {"schema": "INCREMENTAL_FIXTURE_SUITE_DISPATCH_V1",
        "suite_id": row["suite_id"], "expected_tests": row["count"], "argv": argv,
        "observed_at": shared.now(), "is_scientific_stage": False})
    started = time.monotonic()
    child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, cwd=shared.REPO)
    captures = {"stdout": Capture(child.stdout, own / "stdout.log"),
                "stderr": Capture(child.stderr, own / "stderr.log")}
    for capture in captures.values():
        capture.thread.start()
    while child.poll() is None:
        if time.monotonic() >= deadline:
            stop_notice("WALL_SOFT_STOP_DRAIN_CURRENT_SUITE")
        if owned_bytes(output) >= policy.CAP - 16 * 1024 ** 2:
            stop_notice("OWNED_OUTPUT_SOFT_STOP_DRAIN_CURRENT_SUITE")
        time.sleep(.2)
    for capture in captures.values():
        capture.thread.join()
    logs = {name: capture.result() for name, capture in captures.items()}
    result_path = own / "suite_result.json"
    result = shared.load(result_path) if result_path.is_file() else None
    passed = (child.returncode == 0 and result is not None and
        result.get("schema") == policy.CHILD_SCHEMA and result.get("status") == "EXACT_SUITE_PASSED" and
        result.get("suite_id") == row["suite_id"] and result.get("expected_tests") == row["count"] and
        result.get("tests_run") == row["count"] and
        all(result.get(key) == 0 for key in ("failures", "errors", "skips", "expected_failures", "unexpected_successes")) and
        all(not log["truncated"] and log["capture_error"] is None for log in logs.values()))
    record = {"suite_id": row["suite_id"], "status": "EXACT_SUITE_PASSED" if passed else "SUITE_FAILED_CLOSED",
        "expected_tests": row["count"], "exit_code": child.returncode, "child_pid": child.pid,
        "tests_run": result.get("tests_run", 0) if result else 0,
        "failures": result.get("failures", 0) if result else 0,
        "errors": result.get("errors", 0) if result else 0,
        "skips": result.get("skips", 0) if result else 0,
        "expected_failures": result.get("expected_failures", 0) if result else 0,
        "unexpected_successes": result.get("unexpected_successes", 0) if result else 0,
        "suite_result_reference": shared.pin(result_path) if result else None,
        "logs": logs, "elapsed_seconds": time.monotonic() - started}
    shared.write_new(own / "disposition.json", record)
    return record, passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--startup-proof", type=Path, required=True)
    args = parser.parse_args()
    plan = shared.load(args.plan)
    output = policy.validate_plan(plan)
    plan_reference = shared.pin(args.plan)
    proof = central.require_startup(args.startup_proof, expected_scope_key=policy.SCOPE,
        expected_scope_parameters=policy.parameters(),
        expected_execution_argv=policy.execution_argv(args.plan, args.startup_proof),
        expected_source=Path(__file__), expected_kind="analysis", required_references=(plan_reference,))
    request = proof["request"]
    shared.need(request["pilot"] is True and request["scope"]["mode"] == policy.MODE and
        request["wall_seconds"] == policy.WALL and request["estimated_peak_output_bytes"] == policy.CAP and
        request.get("data_references", []) == [] and
        request.get("source_status_stage") == policy.MODE, "FIXTURE_ONLY_600_SECONDS_1GIB_NO_DATA_REQUIRED")
    declared = {r["path"]: r for r in request["source_references"]}
    for reference in [*plan["code_sources"], plan["resource_authority_reference"]]:
        shared.need(declared.get(reference["path"]) == reference and shared.pin(reference["path"]) == reference,
                    "EVERY_CURRENT_FIXTURE_SOURCE_MUST_BE_ROOT_AUTHORIZED")
    shared.need(not output.exists(), "FRESH_FIXTURE_OUTPUT_REQUIRED_NO_OVERWRITE")
    output.mkdir(parents=True)
    started = time.monotonic()
    started_path = output / "started.json"
    shared.write_new(started_path, {"schema": "INCREMENTAL_FIXTURE_PARENT_STARTED_V1", "job_id": str(proof["job_id"]),
        "parent_pid": os.getpid(), "plan_reference": plan_reference,
        "request_reference": proof["request_reference"], "expected_test_cases": policy.TOTAL,
        "observed_at": shared.now(), "scope_key": policy.SCOPE, "stage": policy.MODE})
    stop = []

    def stop_notice(reason):
        if not stop:
            stop.append(reason)
            shared.write_new(output / "stop_new_suites.json", {"schema": "INCREMENTAL_FIXTURE_STOP_DRAIN_V1",
                "reason": reason, "elapsed_seconds": time.monotonic() - started,
                "forced_signals_sent": False, "running_child_is_allowed_to_drain": True})

    results, failure = [], None
    try:
        for row in policy.SUITES:
            if time.monotonic() >= started + policy.WALL - 30:
                stop_notice("WALL_SOFT_STOP_BEFORE_NEXT_SUITE")
            if stop:
                break
            record, passed = run_suite(row, args.plan, started_path, output, started + policy.WALL - 30, stop_notice)
            results.append(record)
            if not passed:
                stop_notice("PREVIOUS_SUITE_NOT_EXACT_PASS")
    except Exception as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)[:8192]}
        traceback.print_exc()
    passed = not stop and failure is None and len(results) == len(policy.SUITES) and all(
        row["status"] == "EXACT_SUITE_PASSED" for row in results) and sum(row["tests_run"] for row in results) == policy.TOTAL
    receipt = {"schema": policy.RECEIPT_SCHEMA, "status": "FIFTEEN_NEW_INCREMENTAL_FIXTURES_PASSED" if passed else
        "INCREMENTAL_FIXTURE_STAGE_FAILED_CLOSED", "job_id": str(proof["job_id"]),
        "node": request["node"], "uid": os.getuid(), "observed_at": shared.now(), "stage": policy.MODE,
        "scope_key": policy.SCOPE, "plan_reference": plan_reference, "request_reference": proof["request_reference"],
        "started_reference": shared.pin(started_path), "expected_tests": policy.TOTAL,
        "tests_run": sum(row["tests_run"] for row in results),
        "failures": sum(row["failures"] for row in results), "errors": sum(row["errors"] for row in results),
        "skips": sum(row["skips"] for row in results), "suites": {row["suite_id"]: row for row in results},
        "not_dispatched_suites": [row["suite_id"] for row in policy.SUITES if row["suite_id"] not in
            {result["suite_id"] for result in results}], "failure": failure, "stop_reasons": stop,
        "elapsed_seconds": time.monotonic() - started, "memory_policy": proof["memory_policy"],
        "memory_admission_evaluated": False, "memory_limits_requested": False, "allocated_cpus": 16,
        "suite_execution": "SEQUENTIAL_ISOLATED_CHILDREN", "sixteen_parallel_workers_claimed": False,
        "old_tests_rerun": False, "real_scientific_records_read": 0,
        "network_requests": 0, "new_UFF_tasks": 0, "new_QM_tasks": 0,
        "synthetic_temporary_IO_and_numerical_fixtures_used": True,
        "forced_signals_sent": False, "pool_or_training_release_authorized": False,
        "whole_output_cap_bytes": policy.CAP, "owned_output_bytes_before_final_receipt": owned_bytes(output),
        "actual_parent_allocation_cost_requires_later_accounting": True}
    shared.need(receipt["owned_output_bytes_before_final_receipt"] < policy.CAP - 2 * 1024 ** 2,
                "WHOLE_FIXTURE_OUTPUT_CAP_REACHED")
    shared.write_new(output / "receipt.json", receipt)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
