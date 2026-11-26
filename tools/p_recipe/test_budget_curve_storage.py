"""Declared same-node peer writes must remain protected before an ADMITTED record."""
from pathlib import Path
import runpy
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import budget_curve as curve
import cpu_statistics


class BudgetCurveStorageTests(unittest.TestCase):
    def test_declared_peer_root_budget_precedes_joint_guard_and_preserves_system_floor(self):
        real = runpy.run_path(str(curve.REPO / "tools/model_v3/v2_diagnosis_disk.py"))["m"]
        gib = 2**30
        root = dict(total=100*gib, available=20*gib, total_inodes=10000,
                    inodes=9000, root=True)
        disk = SimpleNamespace(filesystem_status=lambda path: root,
                               require_capacity=real.require_capacity)
        plan = dict(resources=dict(declared_peer_root_future_bytes={
            "compute-0-7":16*gib, "compute-0-10":12*gib, "compute-0-17":0}))
        with patch.object(curve, "read", return_value=plan), \
             patch.object(curve.socket, "gethostname", return_value="compute-0-7"), \
             patch.object(curve.runpy, "run_path", return_value=dict(m=disk)) as loader:
            with self.assertRaises(OSError):
                curve.admit_joint_storage()
            self.assertEqual(loader.call_count, 1)  # No premature ADMITTED output.
        root["available"] = 32*gib
        with patch.object(curve, "read", return_value=plan), \
             patch.object(curve.socket, "gethostname", return_value="compute-0-10"), \
             patch.object(curve.runpy, "run_path", side_effect=[
                 dict(m=disk), dict(status="ADMITTED")]) as loader:
            self.assertEqual(curve.admit_joint_storage()["status"], "ADMITTED")
            self.assertEqual(loader.call_count, 2)

    def test_original_CPU_statistics_also_protect_declared_peer_root_writes(self):
        real = runpy.run_path(str(curve.REPO / "tools/model_v3/v2_diagnosis_disk.py"))["m"]
        gib = 2**30
        root = dict(total=100*gib,available=20*gib,total_inodes=10000,
                    inodes=9000,root=True)
        disk = SimpleNamespace(filesystem_status=lambda path: root,
                               require_capacity=real.require_capacity)
        plan = dict(resources=dict(declared_peer_root_future_bytes={"compute-0-10":12*gib}))
        with patch.object(curve,"read",return_value=plan), \
             patch.object(curve.socket,"gethostname",return_value="compute-0-10"), \
             patch.object(curve.runpy,"run_path",return_value=dict(m=disk)):
            with self.assertRaises(OSError):
                cpu_statistics.admit(dict(output="/unused_synthetic_output"))


if __name__ == "__main__":
    unittest.main()
