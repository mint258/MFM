"""D-specific joint-budget refresh; inherited process control is unchanged."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.d_recipe.resources import DJointGuard, DiskUnavailable, protection_plan


class ResourceGuardTests(unittest.TestCase):
    def guard(self):
        guard = object.__new__(DJointGuard)
        guard.configuration = dict(storage_peak_bytes=3 * 2**30)
        guard.targets = [dict(filesystem="root"), dict(filesystem="share")]
        guard.check_target = Mock()
        return guard

    def test_output_monitor_also_checks_root_and_refreshes_peer_future_each_time(self):
        guard = self.guard()
        with patch("tools.d_recipe.resources.share_admission") as admit:
            guard.check("/share/own/D")
            guard.check("/share/own/D")
        self.assertEqual(guard.check_target.call_count, 4)
        self.assertEqual([call.args[0]["filesystem"] for call in guard.check_target.call_args_list],
                         ["root", "share", "root", "share"])
        self.assertEqual(admit.call_count, 2)
        admit.assert_called_with("/share/own/D", peak_bytes=3 * 2**30)

    def test_unknown_or_insufficient_joint_capacity_reaches_the_inherited_pause_path(self):
        guard = self.guard()
        for error in (RuntimeError("quota reserve reached"), OSError("actual capacity unknown")):
            with patch("tools.d_recipe.resources.share_admission", side_effect=error):
                with self.assertRaises(DiskUnavailable):
                    guard.check("/share/own/D")

    def test_root_capacity_failure_is_not_hidden_by_share_headroom(self):
        guard = self.guard()
        guard.check_target.side_effect = DiskUnavailable("root floor reached")
        with patch("tools.d_recipe.resources.share_admission") as admit:
            with self.assertRaisesRegex(DiskUnavailable, "root floor"):
                guard.check("/share/own/D")
        admit.assert_not_called()

    def test_plan_binds_the_actual_share_UID_snapshot_and_requires_explicit_growth(self):
        plan = protection_plan(dict(output="/share/own/D", storage_peak_bytes=2**30))
        root, share = plan["targets"]
        self.assertEqual(root["quota_scope"], "not_applicable")
        self.assertEqual(share["quota_expected_filesystem"], "/share")
        self.assertEqual(share["quota_max_age_seconds"], 5)
        self.assertEqual(share["quota_peak_additional_bytes"], 2**30)
        with self.assertRaisesRegex(ValueError, "positive D storage peak"):
            protection_plan(dict(output="/share/own/D", storage_peak_bytes=0))
