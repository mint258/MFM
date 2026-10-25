"""Four new CPU-control boundary fixtures; no replay of scientific test suites."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import importlib.util
import inspect
import json
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

from verify_equivalence import verify

HERE = Path(__file__).parent
CENTRAL = "workflows.data_v1_final.execution.cpu_analysis_v1.runtime"


@contextmanager
def support_with(checkpoint):
    entries = {}
    names = CENTRAL.split(".")
    for n in range(1, len(names) + 1):
        name = ".".join(names[:n])
        value = types.ModuleType(name)
        value.__path__ = []
        entries[name] = value
    calls = []
    proof = {"request": {"scope_key": "label_canonical_512"}, "fixture_only": True}
    def guard(*args):
        calls.append(args)
        return proof
    entries[CENTRAL].root_guard = guard
    entries[CENTRAL].checkpoint = checkpoint
    with mock.patch.dict(sys.modules, entries):
        spec = importlib.util.spec_from_file_location("_streaming_cpu_boundary_support", HERE / "support.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        yield module, calls, proof


class NextSpy:
    def __init__(self, values):
        self.values = iter(values)
        self.next_calls = 0

    def __iter__(self):
        return self

    def __next__(self):
        self.next_calls += 1
        return next(self.values)


class Boundaries(unittest.TestCase):
    def test_same_signature_exact_central_guard_delegation(self):
        with support_with(lambda: None) as (support, calls, proof):
            self.assertEqual(str(inspect.signature(support.root_guard)), "(path, pinned_path, cap, wall_limit=3600)")
            self.assertIs(support.root_guard("intent", "pinned", 123, 7200), proof)
            self.assertEqual(calls, [("intent", "pinned", 123, 7200)])

    def test_stop_prevents_first_source_next(self):
        def stop():
            raise RuntimeError("synthetic same-allocation STOP")
        source = NextSpy([object()])
        with support_with(stop) as (support, _, _):
            with self.assertRaisesRegex(RuntimeError, "same-allocation STOP"):
                next(support.checkpoint_iter(source))
        self.assertEqual(source.next_calls, 0)

    def test_preserve_identity_order_and_stop_before_next_batch(self):
        objects = [object(), object(), object()]
        source = NextSpy(objects)
        checks = []
        def checkpoint():
            checks.append(1)
            if len(checks) == 3:
                raise RuntimeError("synthetic same-allocation STOP")
        with support_with(checkpoint) as (support, _, _):
            iterator = support.checkpoint_iter(source)
            self.assertIs(next(iterator), objects[0])
            self.assertIs(next(iterator), objects[1])
            with self.assertRaisesRegex(RuntimeError, "same-allocation STOP"):
                next(iterator)
        self.assertEqual(source.next_calls, 2)
        self.assertEqual(len(checks), 3)

    def test_five_sources_inverse_bytes_and_all_function_asts(self):
        proof = verify(HERE)
        self.assertEqual(proof["status"], "PASS")
        self.assertEqual(len(proof["files"]), 5)
        self.assertTrue(all(f["reverse_declared_edits_full_file_bytes_identical"] for f in proof["files"]))
        unchanged = {f["filename"] for f in proof["files"] if f["raw_file_bytes_identical"]}
        self.assertEqual(unchanged, {"compact.py", "calibration.py"})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True)
    a = p.parse_args()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries))
    report = {"schema": "STREAMING_CPU_BOUNDARY_FIXTURES_V1", "status": "PASS" if result.wasSuccessful() else "FAIL",
              "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "central_runtime_mocked_only_for_boundary_fixture": True, "scientific_modules_imported": [],
              "scientific_data_bodies_read": False, "old_19_24_13_suites_repeated": False}
    with Path(a.output).open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
