"""Internal synthetic-fixture child; fresh job admission belongs to run.py."""
import argparse
import importlib
import importlib.util
import os
from pathlib import Path
import sys
import time
import traceback
import unittest

from ..cpu_auto_memory_queue_v2 import shared
from . import policy


def test_ids(suite):
    result = []
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            result.extend(test_ids(item))
        else:
            shared.need(isinstance(item, unittest.TestCase), "ONLY_UNITTEST_TESTCASE_ALLOWED")
            result.append(item.id())
    return result


def imported_project_pins(declared):
    rows = {}
    for module in tuple(sys.modules.values()):
        filename = getattr(module, "__file__", None)
        if not isinstance(filename, str):
            continue
        path = Path(filename).absolute()
        if shared.REPO not in path.parents:
            continue
        shared.need(path.suffix == ".py", "PROJECT_IMPORT_MUST_HAVE_PINNED_PYTHON_SOURCE")
        reference = shared.pin(path)
        shared.need(declared.get(str(path)) == reference, "IMPORTED_PROJECT_SOURCE_NOT_PINNED:" + str(path))
        rows[str(path)] = reference
    return [rows[key] for key in sorted(rows)]


def load_exact(row):
    path = shared.REPO / row["test_path"]
    if row["import_mode"] == "direct":
        shared.need(not any(name in sys.modules for name in row["direct_names"]),
                    "FRESH_DIRECT_IMPORT_NAMESPACE_REQUIRED")
        sys.path.insert(0, str(path.parent))
        spec = importlib.util.spec_from_file_location(row["module"], path)
        shared.need(spec is not None and spec.loader is not None, "EXACT_TEST_SOURCE_LOADER_REQUIRED")
        module = importlib.util.module_from_spec(spec)
        sys.modules[row["module"]] = module
        spec.loader.exec_module(module)
    else:
        module = importlib.import_module(row["module"])
    shared.need(Path(module.__file__).absolute() == path, "ACTUAL_IMPORTED_TEST_PATH_DIFFERS")
    cls = getattr(module, row["class"])
    shared.need(isinstance(cls, type) and issubclass(cls, unittest.TestCase) and cls.__module__ == row["module"],
                "EXACT_ORIGINAL_TESTCASE_CLASS_REQUIRED")
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(cls)
    ids = test_ids(suite)
    shared.need(not loader.errors and suite.countTestCases() == row["count"] == len(ids) == len(set(ids)),
                "EXACT_SUITE_COUNT_BEFORE_EXECUTION_REQUIRED")
    return suite, ids


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--parent-started", type=Path, required=True)
    parser.add_argument("--parent-pid", type=int, required=True)
    parser.add_argument("--suite-id", required=True)
    args = parser.parse_args()
    started = time.monotonic()
    plan = shared.load(args.plan)
    output = policy.validate_plan(plan)
    parent = shared.load(args.parent_started)
    row = policy.find_suite(args.suite_id)
    own = output / row["suite_id"]
    shared.need(args.parent_pid == os.getppid() and parent["parent_pid"] == args.parent_pid and
        parent["schema"] == "INCREMENTAL_FIXTURE_PARENT_STARTED_V1" and
        parent["plan_reference"] == shared.pin(args.plan) and
        parent["job_id"] == os.environ.get("SLURM_JOB_ID") and
        args.parent_started == output / "started.json" and own.is_dir(),
        "ONLY_CHILD_OF_FRESH_ADMITTED_FIXTURE_PARENT_REQUIRED")
    declared = {r["path"]: r for r in plan["code_sources"]}
    for reference in plan["code_sources"]:
        shared.need(shared.pin(reference["path"]) == reference, "SMALL_FIXTURE_SOURCE_CHANGED")
    receipt = {"schema": policy.CHILD_SCHEMA, "suite_id": row["suite_id"],
        "job_id": parent["job_id"], "pid": os.getpid(), "parent_pid": os.getppid(),
        "status": "FIXTURE_SETUP_FAILED", "expected_tests": row["count"],
        "tests_run": 0, "failures": 0, "errors": 0, "skips": 0,
        "expected_failures": 0, "unexpected_successes": 0,
        "test_source_reference": declared[str(shared.REPO / row["test_path"])],
        "plan_reference": shared.pin(args.plan), "parent_started_reference": shared.pin(args.parent_started),
        "fresh_startup_owned_by_parent": True, "independent_child_admission_claimed": False,
        "technical_retry": policy.TECHNICAL_RETRY,
        "real_scientific_inputs_authorized": 0, "network_requests_authorized": 0,
        "new_UFF_tasks_authorized": 0, "new_QM_tasks_authorized": 0}
    passed = False
    try:
        suite, ids = load_exact(row)
        receipt["loaded_test_ids"] = ids
        receipt["imported_sources_before"] = imported_project_pins(declared)
        result = unittest.TextTestRunner(stream=sys.stdout, verbosity=2).run(suite)
        receipt.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
            skips=len(result.skipped), expected_failures=len(result.expectedFailures),
            unexpected_successes=len(result.unexpectedSuccesses))
        receipt["imported_sources_after"] = imported_project_pins(declared)
        passed = result.wasSuccessful() and result.testsRun == row["count"] and not any(
            receipt[key] for key in ("failures", "errors", "skips", "expected_failures", "unexpected_successes"))
        receipt["status"] = "EXACT_SUITE_PASSED" if passed else "FIXTURE_RESULT_REJECTED"
    except Exception as exc:
        receipt["failure_type"] = type(exc).__name__
        receipt["failure_message"] = str(exc)[:8192]
        traceback.print_exc()
    receipt["elapsed_seconds"] = time.monotonic() - started
    receipt["actual_child_CPU_seconds"] = time.process_time()
    receipt["finished_at"] = shared.now()
    shared.write_new(own / "suite_result.json", receipt)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
