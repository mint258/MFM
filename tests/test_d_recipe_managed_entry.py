"""Only the new exit-entry admission/control transformations."""
from copy import deepcopy
import datetime
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools.d_recipe import managed_entry as entry


class ManagedEntryPolicyTests(unittest.TestCase):
    def test_actual_allocation_identity_and_end_are_required(self):
        with self.assertRaises(RuntimeError):
            entry.allocation_end({"JobId": "2", "EndTime": "2026-11-22T16:00:00"}, "1")
        with self.assertRaises(RuntimeError):
            entry.allocation_end({"JobId": "1", "TimeLimit": "01:00:00", "EndTime": "Unknown"}, "1")
        self.assertIsNone(entry.allocation_end({"JobId": "1", "TimeLimit": "UNLIMITED"}, "1"))
        text = "2026-11-22T16:00:00"
        self.assertEqual(entry.allocation_end({"JobId": "1", "TimeLimit": "01:00:00", "EndTime": text}, "1"),
                         datetime.datetime.fromisoformat(text).timestamp())

    def test_fault_node_refuses_admission(self):
        for state in ("DRAIN", "MIXED+DRAIN", "DOWN", "IDLE+NOT_RESPONDING"):
            with self.assertRaises(RuntimeError):
                entry.require_healthy_node({"NodeName": "compute-0-10", "State": state}, "compute-0-10")
        entry.require_healthy_node({"NodeName": "compute-0-10", "State": "MIXED"}, "compute-0-10")

    def test_runtime_preserves_science_and_does_not_mutate_parent(self):
        with tempfile.TemporaryDirectory(prefix="d_exit_policy_unit_") as root:
            c = dict(run="D_R1_seed1", control_directory=root, seed=1, samples=3000000,
                     p_recipe={"element_residual": True}, d_recipe={"block_weights": [17/24, 6/24, 1/24]},
                     clip_calibration={"initial_clip": 281.7}, local_concurrent_bytes=123,
                     exit_root_log_future_bytes=64*2**20)
            original = deepcopy(c)
            with patch.object(entry, "_CONTROL_ROOT", Path(root)):
                path, runtime = entry.runtime_payload(c, 4538551, "train")
            self.assertEqual(c, original)
            for key in ("seed", "samples", "p_recipe", "d_recipe", "clip_calibration"):
                self.assertEqual(runtime[key], original[key])
            self.assertEqual(runtime["local_concurrent_bytes"], 123 + 64*2**20)
            self.assertEqual(path.parent.name, "job_4538551")
            self.assertEqual(Path(runtime["handoff_request"]).parent, path.parent)
            self.assertFalse(path.exists())

    def test_exit_control_cannot_escape_its_registered_scope(self):
        with tempfile.TemporaryDirectory(prefix="d_exit_policy_unit_") as root:
            with patch.object(entry, "_CONTROL_ROOT", Path(root)):
                with self.assertRaises(ValueError):
                    entry.runtime_payload(dict(run="../escape", control_directory=root), 1, "train")
                with self.assertRaises(ValueError):
                    entry.runtime_payload(dict(run="D_R0", control_directory="/etc"), 1, "cpu")

    def test_missing_joint_log_registration_refuses_start(self):
        with tempfile.TemporaryDirectory(prefix="d_exit_policy_unit_") as root:
            with patch.object(entry, "_CONTROL_ROOT", Path(root)):
                with self.assertRaises(ValueError):
                    entry.runtime_payload(dict(run="D_R0", control_directory=root), 1, "cpu")

    def test_shared_slurm_log_is_rejected(self):
        with self.assertRaises(RuntimeError):
            entry.require_local_log({"StdOut": "/share/home/zixiao/model.log"})


if __name__ == "__main__":
    unittest.main()

