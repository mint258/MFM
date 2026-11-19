"""Pure-stdlib tests for the endpoint scope selector."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from workflows.benchmark_data.task_selection import (
    canonical_task_key, task_fingerprint, load_deferred_policy,
    is_active_task, select_active_tasks,
)


class TestBenchmarkTaskSelection(unittest.TestCase):
    def test_canonical_source_paths(self):
        self.assertEqual(
            canonical_task_key("TDC_ADMET", "admet_group/example1/test.csv"),
            "tdc_admet::example1",
        )
        self.assertEqual(
            canonical_task_key("TDC_ADMET", "admet_group/Example1/train_val.csv"),
            "tdc_admet::example1",
        )
        self.assertEqual(
            canonical_task_key("PharmaBench", "models/example.csv"),
            "pharmabench::example.csv",
        )

    def test_fingerprint_and_scope(self):
        identifier = "demo::example.csv"
        marker = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        self.assertEqual(task_fingerprint("Demo", "example.csv"), marker)
        self.assertFalse(is_active_task("Demo", "example.csv", fingerprints={marker}))
        self.assertTrue(is_active_task("Demo", "other.csv", fingerprints={marker}))
        tasks = [("Demo", "example.csv"), ("Demo", "other.csv")]
        self.assertEqual(
            select_active_tasks(tasks, fingerprints={marker}, verify_full_inventory=True),
            [("Demo", "other.csv")],
        )
        with self.assertRaises(ValueError):
            select_active_tasks([("Demo", "other.csv")], fingerprints={marker}, verify_full_inventory=True)

    def test_real_registry_is_opaque_and_complete(self):
        values = load_deferred_policy()
        self.assertEqual(len(values), 5)
        self.assertTrue(all(len(x) == 64 for x in values))


if __name__ == "__main__":
    unittest.main()
