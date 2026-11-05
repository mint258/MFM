"""Unit tests use synthetic process files and mocked signals; no job is paused."""
import os
from pathlib import Path
import signal
import tempfile
from types import SimpleNamespace
import unittest

from workflows.expansion.window3_v2.disk_guard import (
    GIB, freeze_job, inspect_filesystem, job_processes,
    matches_job_environment, required_capacity,
)


class DiskGuardTests(unittest.TestCase):
    def test_root_reserve_and_planned_growth_are_additive(self):
        check = dict(root_filesystem=True, reserve_bytes=0, planned_bytes=2*GIB,
                     reserve_inodes=20, planned_inodes=30)
        self.assertEqual(required_capacity(check, 50*GIB), (12*GIB, 50))
        self.assertEqual(required_capacity(check, 200*GIB), (22*GIB, 50))

    def test_bytes_and_inodes_both_gate_writes(self):
        check = dict(path="/shared", reserve_bytes=10, planned_bytes=20,
                     reserve_inodes=3, planned_inodes=4)
        value = SimpleNamespace(f_blocks=100, f_frsize=1, f_bavail=30,
                                f_files=100, f_favail=7)
        self.assertTrue(inspect_filesystem(check, lambda _: value)["safe"])
        value.f_favail = 6
        self.assertFalse(inspect_filesystem(check, lambda _: value)["safe"])
        value.f_favail, value.f_bavail = 7, 29
        self.assertFalse(inspect_filesystem(check, lambda _: value)["safe"])

    def test_unknown_capacity_is_not_permission_to_write(self):
        check = dict(path="/unknown", reserve_bytes=0, planned_bytes=0,
                     reserve_inodes=0, planned_inodes=0)
        def unavailable(_):
            raise OSError("unavailable")
        result = inspect_filesystem(check, unavailable)
        self.assertFalse(result["safe"])
        self.assertIn("unknown", result)

    def test_exact_job_environment_not_prefix_or_substring(self):
        self.assertTrue(matches_job_environment(b"A=x\0SLURM_JOB_ID=1885281\0", "1885281"))
        self.assertFalse(matches_job_environment(b"SLURM_JOB_ID=18852810\0", "1885281"))
        self.assertFalse(matches_job_environment(b"OTHER=SLURM_JOB_ID=1885281\0", "1885281"))

    def test_only_matching_uid_and_job_processes_are_frozen(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for pid, job in [(100001, "1885281"), (100002, "another")]:
                folder = root / str(pid)
                folder.mkdir()
                (folder / "environ").write_bytes(("SLURM_JOB_ID=" + job).encode() + b"\0")
                fields = ["S"] + ["0"] * 18 + ["777"] + ["0"] * 4
                (folder / "stat").write_text(str(pid) + " (worker (with spaces)) " + " ".join(fields))
            uid = os.getuid()
            self.assertEqual(job_processes("1885281", uid, root), {100001: 777})
            self.assertEqual(job_processes("1885281", uid + 1, root), {})
            signals = []
            stopped = freeze_job("1885281", uid, root, lambda pid, sig: signals.append((pid, sig)))
            self.assertEqual(signals, [(100001, signal.SIGSTOP)])
            self.assertEqual(stopped, [{"pid": 100001, "start_ticks": 777}])


if __name__ == "__main__":
    unittest.main()
