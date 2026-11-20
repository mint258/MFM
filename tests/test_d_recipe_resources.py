"""D-specific joint-budget refresh; inherited process control is unchanged."""
from pathlib import Path
import json
import os
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.d_recipe.resources import (DJointGuard, DiskUnavailable, admit_output,
    allocated_local_bytes, execution_site, model_admission, protection_plan,
    remaining_local_bytes, storage_locations)


class ResourceGuardTests(unittest.TestCase):
    def test_cpu_diagnostics_require_a_real_cpu_allocation(self):
        with patch.dict("os.environ", SLURM_JOB_ID="own-test"):
            with patch("tools.d_recipe.resources.platform.node", return_value="compute-0-17"):
                execution_site({}, cpu=True)
            for node in ("sonmi", "compute-0-2", "compute-0-6", "compute-0-20", "compute-0-21"):
                with patch("tools.d_recipe.resources.platform.node", return_value=node), self.assertRaises(RuntimeError):
                    execution_site({}, cpu=True)
        with patch.dict("os.environ", {}, clear=True), \
             patch("tools.d_recipe.resources.platform.node", return_value="compute-0-17"), self.assertRaises(RuntimeError):
            execution_site({}, cpu=True)

    def guard(self):
        guard = object.__new__(DJointGuard)
        guard.configuration = dict(output="/share/own/D", storage_peak_bytes=3 * 2**30)
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

    def lustre_configuration(self):
        scope = "/lfshome/zixiao/model_v31_20261105/D_RECIPE_20261120"
        return dict(output=scope + "/training/D-R0", output_filesystem="/lfshome",
            model_budget_root=scope, storage_peak_bytes=8 * 2**30,
            share_output="/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120",
            share_storage_peak_bytes=36706053853, lustre_other_future_bytes=6_000_000_000)

    def test_lustre_output_keeps_a_separate_actual_NFS_quota_plan(self):
        configuration = self.lustre_configuration()
        root, share = protection_plan(configuration)["targets"]
        self.assertEqual(share["paths"], [configuration["share_output"]])
        self.assertEqual(share["quota_expected_filesystem"], "/share")
        self.assertEqual(share["quota_peak_additional_bytes"], 36706053853)
        self.assertEqual(root["quota_scope"], "not_applicable")

    def test_lustre_configuration_requires_original_scopes_and_explicit_NFS_growth(self):
        configuration = self.lustre_configuration()
        for update in (dict(output="/share/home/redirected"), dict(model_budget_root="/tmp/D"),
                dict(share_output="/tmp/control"), dict(share_storage_peak_bytes=0),
                dict(lustre_other_future_bytes=0), dict(output_filesystem="unknown")):
            with self.subTest(update=update), self.assertRaises(ValueError):
                storage_locations({**configuration, **update})

    def test_lustre_monitor_refreshes_native_model_and_NFS_admission_each_time(self):
        guard = self.guard()
        guard.configuration = self.lustre_configuration()
        with patch("tools.d_recipe.resources.model_admission") as model, \
             patch("tools.d_recipe.resources.share_admission") as share:
            guard.check(guard.configuration["output"])
            guard.check(guard.configuration["output"])
        self.assertEqual(model.call_count, 2)
        self.assertEqual(share.call_count, 2)
        share.assert_called_with(guard.configuration["share_output"], peak_bytes=36706053853)
        self.assertEqual(guard.check_target.call_count, 4)

    def native_model_guard(self):
        return SimpleNamespace(ROOT=Path("/native"), CONTROL=Path("/native/control"),
            model_growth_forecast=Mock(return_value=(5, 17)), remaining_d6=Mock(return_value=11),
            m=SimpleNamespace(filesystem_status=Mock(return_value={"root": False}),
                require_capacity=Mock(), quota_headroom=Mock(return_value={"status": "PASS"})))

    def test_NFS_layer_cache_write_checks_both_its_scope_and_the_Lustre_model_pool(self):
        guard = self.guard()
        guard.configuration = self.lustre_configuration()
        cache = Path(guard.configuration["share_output"]) / "diagnostics/D-R0/layers"
        with patch("tools.d_recipe.resources.model_admission") as model, \
             patch("tools.d_recipe.resources.share_admission") as share:
            guard.check(cache)
        model.assert_called_once_with(guard.configuration, guard.configuration["output"])
        share.assert_called_once_with(cache, peak_bytes=36706053853)
        with patch("tools.d_recipe.resources.model_admission"), \
             patch("tools.d_recipe.resources.share_admission"), self.assertRaises(DiskUnavailable):
            guard.check("/tmp/unbudgeted-cache")

    def test_existing_global_model_forecast_is_not_double_counted(self):
        configuration, native = self.lustre_configuration(), self.native_model_guard()
        registry = json.dumps(dict(roots=[configuration["model_budget_root"]]))
        with patch.object(Path, "read_text", return_value=registry):
            result = model_admission(configuration, configuration["output"], native=native)
        self.assertEqual(result, {"status": "PASS"})
        native.m.require_capacity.assert_called_once_with({"root": False}, 6_000_000_028, 10000)
        native.m.quota_headroom.assert_called_once_with(
            native.CONTROL / "lustre_quota_available_v2_20261107.json", "/lfshome", 17, 6_000_000_011)

    def test_unregistered_D_root_does_not_spend_an_existing_model_forecast(self):
        configuration, native = self.lustre_configuration(), self.native_model_guard()
        with patch.object(Path, "read_text", return_value='{"roots": []}'), \
             self.assertRaisesRegex(ValueError, "Register D model growth"):
            model_admission(configuration, configuration["output"], native=native)
        native.model_growth_forecast.assert_not_called()
        native.m.quota_headroom.assert_not_called()

    def test_missing_Lustre_mount_or_stale_native_quota_stops_own_writes(self):
        configuration, native = self.lustre_configuration(), self.native_model_guard()
        registry = json.dumps(dict(roots=[configuration["model_budget_root"]]))
        native.m.filesystem_status.return_value = {"root": True}
        with patch.object(Path, "read_text", return_value=registry), \
             self.assertRaisesRegex(ValueError, "node root filesystem"):
            model_admission(configuration, configuration["output"], native=native)
        native.m.filesystem_status.return_value = {"root": False}
        native.m.quota_headroom.side_effect = OSError("native snapshot stale")
        with patch.object(Path, "read_text", return_value=registry), \
             self.assertRaisesRegex(OSError, "snapshot stale"):
            model_admission(configuration, configuration["output"], native=native)

    def test_direct_summary_writer_uses_the_same_lustre_monitor(self):
        configuration = self.lustre_configuration()
        with patch("tools.d_recipe.resources.DJointGuard") as guard:
            admit_output(configuration, Path(configuration["output"]) / "readout")
        guard.assert_called_once_with(configuration)
        guard.return_value.check.assert_called_once_with(Path(configuration["output"]) / "readout")

    def test_local_cache_plan_debits_actual_root_and_keeps_shared_quota_separate(self):
        configuration = dict(self.lustre_configuration(),
            local_output_root="/tmp/d_recipe_unused_fixture", local_storage_peak_bytes=24 * 2**30)
        root, share = protection_plan(configuration)["targets"]
        self.assertEqual(root["paths"], ["/", configuration["local_output_root"]])
        self.assertEqual(root["peak_additional_bytes"], 24 * 2**30)
        self.assertEqual(share["quota_peak_additional_bytes"], 36706053853)
        with self.assertRaises(ValueError):
            protection_plan({**configuration, "local_output_root": "/tmp"})

    def test_local_layer_cache_still_refreshes_both_shared_filesystems(self):
        guard = self.guard()
        guard.configuration = dict(self.lustre_configuration(),
            local_output_root="/tmp/d_recipe_unused_fixture", local_storage_peak_bytes=24 * 2**30)
        with patch("tools.d_recipe.resources.model_admission") as model, \
             patch("tools.d_recipe.resources.share_admission") as share:
            guard.check("/tmp/d_recipe_unused_fixture/D-R0/layers")
        model.assert_called_once_with(guard.configuration, guard.configuration["output"])
        share.assert_called_once_with(guard.configuration["share_output"], peak_bytes=36706053853)
        self.assertEqual(guard.check_target.call_args_list[0].kwargs["bytes_needed"], 24 * 2**30)

    def test_CPU_local_collection_does_not_debit_a_model_pool_it_never_writes(self):
        guard = self.guard()
        guard.configuration = dict(output_filesystem="node_local",
            output="/tmp/d_recipe_unused_fixture/reference/D20", storage_peak_bytes=2 * 2**30,
            local_output_root="/tmp/d_recipe_unused_fixture", local_storage_peak_bytes=4 * 2**30,
            share_output="/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120",
            share_storage_peak_bytes=36706053853)
        with patch("tools.d_recipe.resources.model_admission") as model, \
             patch("tools.d_recipe.resources.share_admission") as share:
            guard.check(guard.configuration["output"])
        model.assert_not_called()
        share.assert_called_once_with(guard.configuration["share_output"], peak_bytes=36706053853)
        self.assertEqual(guard.check_target.call_args_list[0].kwargs["bytes_needed"], 4 * 2**30)

    def test_node_bound_cache_cannot_be_silently_reused_on_another_host(self):
        with patch.dict("os.environ", SLURM_JOB_ID="own-test"), \
             patch("tools.d_recipe.resources.platform.node", return_value="compute-0-19"):
            with self.assertRaisesRegex(RuntimeError, "recorded host"):
                execution_site(dict(local_node="compute-0-17"), cpu=True)

    def test_local_block_accounting_deduplicates_hardlinks_and_does_not_credit_symlink_targets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "owned"
            root.mkdir()
            first = root / "first"
            first.write_bytes(b"a" * 4096)
            os.link(first, root / "same_inode")
            sparse = root / "sparse"
            with sparse.open("wb") as stream:
                stream.write(b"b" * 4096)
                stream.truncate(16 * 2**20)
            outside = Path(folder) / "outside"
            outside.write_bytes(b"c" * 4096)
            (root / "not_our_allocation").symlink_to(outside)
            expected = sum(min(p.stat().st_size, p.stat().st_blocks * 512) for p in (first, sparse))
            self.assertEqual(allocated_local_bytes(root), expected)
            with patch("tools.d_recipe.resources.os.getuid", return_value=os.getuid() + 1):
                self.assertEqual(allocated_local_bytes(root), 0)

    def test_committed_local_files_reduce_future_but_keep_the_native_burst_margin(self):
        configuration = dict(local_output_root="/tmp/d_recipe_unused_fixture",
                             local_storage_peak_bytes=24 * 2**30)
        with patch("tools.d_recipe.resources.allocated_local_bytes", return_value=5 * 2**30):
            self.assertEqual(remaining_local_bytes(configuration), 19 * 2**30)
        with patch("tools.d_recipe.resources.allocated_local_bytes", return_value=30 * 2**30):
            self.assertEqual(remaining_local_bytes(configuration), 8 * 2**30)
            self.assertEqual(remaining_local_bytes({**configuration, "local_storage_peak_bytes": 4 * 2**30}), 4 * 2**30)

    def test_registered_peer_closeout_forecast_is_checked_by_the_same_parent(self):
        guard = self.guard()
        guard.configuration["peer_storage_guard_root"] = "/existing/heads"
        with patch("tools.d_recipe.resources.share_admission"), \
             patch("tools.d_recipe.resources.peer_share_admission") as peer:
            guard.check(guard.configuration["output"])
        peer.assert_called_once_with(guard.configuration)

    def test_insufficient_peer_headroom_reaches_existing_owned_process_pause(self):
        guard = self.guard()
        with patch("tools.d_recipe.resources.share_admission"), \
             patch("tools.d_recipe.resources.peer_share_admission", side_effect=OSError("peer future reserved")), \
             self.assertRaisesRegex(DiskUnavailable, "peer future reserved"):
            guard.check(guard.configuration["output"])
