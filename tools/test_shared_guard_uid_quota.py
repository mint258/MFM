"""Actual UID quota must limit shared writes even when whole-filesystem df is large."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

import shared_guard as g


class ActualUIDQuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.snapshot = self.root / "actual-share-quota.json"

    def row(self, **changes):
        value = dict(schema="XFS_USER_QUOTA_AVAILABLE_V1", uid=os.getuid(),
                     filesystem="/share", used_KiB=400, soft_KiB=0, hard_KiB=1000,
                     available_bytes=600*1024, observed_time=100.0)
        value.update(changes)
        self.snapshot.write_text(json.dumps(value))
        return value

    def test_zero_soft_does_not_override_positive_native_hard_limit(self):
        self.assertEqual(g.quota_remaining(2146441328, 0, 2147483648), 1067335680)
        with self.assertRaises(g.AdmissionRefused):
            g.quota_remaining(100, 0, 0)

    def test_lustre_uid_and_kib_counter_row_including_wrapped_mount(self):
        uid = os.getuid()
        text = (f"Disk quotas for usr {uid} (uid {uid}):\n"
                "Filesystem kbytes quota limit grace files quota limit grace\n"
                "/lfshome 2146441328 0 2147483648 - 27637626 0 0 -\n")
        for value in [text, text.replace("/lfshome 214", "/lfshome\n 214")]:
            with self.subTest(value=value):
                result = g.parse_lustre_uid_quota(value, uid)
                self.assertEqual(result["available"], 1067335680)
                self.assertEqual(result["hard_KiB"], 2147483648)
                self.assertEqual(result["filesystem"], "/lfshome")

    def test_lustre_wrong_uid_or_missing_limit_refuses(self):
        uid = os.getuid()
        text = (f"Disk quotas for usr {uid+1} (uid {uid+1}):\n"
                "Filesystem kbytes quota limit grace\n/lfshome 10 0 100 -\n")
        with self.assertRaises(g.AdmissionRefused):
            g.parse_lustre_uid_quota(text, uid)

    def test_fresh_nfs_publisher_identity_and_arithmetic(self):
        self.row()
        with patch.object(g, "SHARE_UID_QUOTA", self.snapshot):
            result = g.uid_quota_status("/share", now=102)
        self.assertEqual(result["available"], 600*1024)
        self.assertEqual(result["uid"], os.getuid())

    def test_missing_stale_future_or_inconsistent_nfs_snapshot_refuses(self):
        with patch.object(g, "SHARE_UID_QUOTA", self.snapshot):
            with self.assertRaises(g.AdmissionRefused):
                g.uid_quota_status("/share", now=102)
            cases = [dict(observed_time=90), dict(observed_time=103),
                     dict(uid=os.getuid()+1), dict(filesystem="/lfshome"),
                     dict(available_bytes=1), dict(schema="unrelated"),
                     dict(soft_KiB=0, hard_KiB=0, available_bytes=0)]
            for changes in cases:
                with self.subTest(changes=changes):
                    self.row(**changes)
                    with self.assertRaises(g.AdmissionRefused):
                        g.uid_quota_status("/share", now=102)

    def test_actual_hard_quota_refuses_despite_tens_of_tb_df(self):
        status = dict(total=95*10**12, available=39*10**12, inodes=10**8)
        quota = dict(available=1067335680, source="native lfs quota",
                     uid=os.getuid(), observed_time=100)
        with patch.object(g, "uid_quota_status", return_value=quota):
            for optional in [None, 90*10**12]:
                with self.subTest(optional=optional):
                    with self.assertRaisesRegex(g.AdmissionRefused, "actual UID quota"):
                        g.check("p", "shared_fs", 1024, "/lfshome",
                                registry=self.root, status=status, now=100,
                                quota_available=optional)

    def test_optional_available_can_only_lower_actual_headroom(self):
        status = dict(total=95*10**12, available=39*10**12, inodes=10**8)
        quota = dict(available=g.SHARED_RESERVE+10*g.GIB, source="fresh publisher",
                     uid=os.getuid(), observed_time=100)
        with patch.object(g, "uid_quota_status", return_value=quota):
            result = g.check("p", "shared_fs", g.GIB, "/share",
                             registry=self.root, status=status, now=100)
            self.assertEqual(result["available"], quota["available"])
            self.assertEqual(result["filesystem_available"], status["available"])
            with self.assertRaises(g.AdmissionRefused):
                g.check("p", "shared_fs", 2*g.GIB, "/share",
                        registry=self.root, status=status, now=100,
                        quota_available=g.SHARED_RESERVE+g.GIB)

    def test_native_probe_failure_or_timeout_refuses(self):
        for result in [types.SimpleNamespace(returncode=1, stdout="", stderr=""),
                       subprocess.TimeoutExpired(["lfs"], 5)]:
            with self.subTest(result=result):
                kwargs = ({"side_effect": result} if isinstance(result, Exception)
                          else {"return_value": result})
                with patch.object(g.subprocess, "run", **kwargs):
                    with self.assertRaises(g.AdmissionRefused):
                        g.uid_quota_status("/lfshome")


    def test_F_NFS_admission_uses_actual_autofs_directory(self):
        from finetune_entry import validate_output_filesystem
        canonical = "/share/home/zixiao/descriptor_analysis/MFM_p_recipe/tools"
        output = "/share/home/zixiao/new_results/run"
        def stat(path):
            return types.SimpleNamespace(st_dev=64768 if str(path)=="/share" else 49)
        with patch.object(g, "disk_probe_target", return_value=canonical):
            self.assertEqual(validate_output_filesystem(output, "/share", stat=stat),
                             Path(output).parent)

    def test_F_NFS_admission_still_refuses_a_different_real_device(self):
        from finetune_entry import validate_output_filesystem
        canonical = "/share/home/zixiao/descriptor_analysis/MFM_p_recipe/tools"
        def stat(path):
            return types.SimpleNamespace(st_dev=49 if str(path)==canonical else 50)
        with patch.object(g, "disk_probe_target", return_value=canonical):
            with self.assertRaises(ValueError):
                validate_output_filesystem("/share/home/zixiao/new_results/run",
                                           "/share", stat=stat)


if __name__ == "__main__":
    unittest.main()
