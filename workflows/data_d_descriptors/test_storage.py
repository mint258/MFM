"""Registered peer forecast accounting; no label data or native quota queries."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from .storage import _inspect_output, concurrent_reservation

GIB = 2**30


class StorageTests(unittest.TestCase):
    def config(self, root, sealed=True):
        folder = Path(root) / "geometry"
        folder.mkdir()
        (folder / "access.json").write_text(json.dumps({"immutable": sealed,
            "cross_node_read_allowed": sealed, "publishing_uid": os.getuid(),
            "actual_closure_evidence": {"raw": "JobState=COMPLETED ExitCode=0:0"}}))
        (folder / "queue.manifest.json").write_text(json.dumps({"storage_forecast_bytes": 40 * GIB}))
        return {"registered_model_pool_bytes": 100 * GIB,
            "benchmark_peer_environment_bytes": 10 * GIB, "benchmark_miscellaneous_future_bytes": GIB,
            "B0_labels": [{"directory": str(Path(root) / "old"), "forecast_bytes": 80 * GIB},
                          {"directory": str(Path(root) / "new"), "forecast_bytes": 80 * GIB}],
            "B0_geometry": [str(folder)]}

    def test_model_pool_is_counted_once_and_only_committed_peer_bytes_are_subtracted(self):
        with tempfile.TemporaryDirectory() as root:
            config = self.config(root)
            with patch("workflows.data_d_descriptors.storage.physical_sqlite_bytes", return_value=20 * GIB):
                self.assertEqual(concurrent_reservation(config), 231 * GIB)

    def test_unsealed_geometry_keeps_its_remaining_forecast(self):
        with tempfile.TemporaryDirectory() as root:
            config = self.config(root, sealed=False)
            with patch("workflows.data_d_descriptors.storage.physical_sqlite_bytes", return_value=20 * GIB):
                self.assertEqual(concurrent_reservation(config), 251 * GIB)

    def test_unknown_geometry_closure_is_not_treated_as_no_future_growth(self):
        with tempfile.TemporaryDirectory() as root:
            config = self.config(root)
            (Path(config["B0_geometry"][0]) / "access.json").unlink()
            with patch("workflows.data_d_descriptors.storage.physical_sqlite_bytes", return_value=0):
                with self.assertRaises(FileNotFoundError):
                    concurrent_reservation(config)

    def test_already_consumed_label_forecast_keeps_writer_burst_margin(self):
        with tempfile.TemporaryDirectory() as root:
            config = self.config(root)
            with patch("workflows.data_d_descriptors.storage.physical_sqlite_bytes", return_value=100 * GIB):
                self.assertEqual(concurrent_reservation(config), 111 * GIB + 2 * 2**26)

    def test_nonexistent_output_inspects_nearest_real_ancestor_without_mkdir(self):
        with tempfile.TemporaryDirectory() as folder:
            share = Path(folder) / "share"
            existing = share / "project"
            existing.mkdir(parents=True)
            target = existing / "new" / "outputs"
            inspector = Mock(return_value=object())
            facts = _inspect_output(target, inspector, share_root=share)
            self.assertIs(facts, inspector.return_value)
            inspector.assert_called_once_with(existing.resolve())
            self.assertFalse((existing / "new").exists())

    def test_existing_output_itself_is_inspected(self):
        with tempfile.TemporaryDirectory() as folder:
            share = Path(folder) / "share"
            target = share / "project" / "existing.npy"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"existing own fixture")
            inspector = Mock()
            _inspect_output(target, inspector, share_root=share)
            inspector.assert_called_once_with(target.resolve())

    def test_symlink_escape_is_rejected_before_any_disk_inspection(self):
        with tempfile.TemporaryDirectory() as folder:
            share, outside = Path(folder) / "share", Path(folder) / "outside"
            share.mkdir(); outside.mkdir()
            (share / "link").symlink_to(outside, target_is_directory=True)
            inspector = Mock()
            with self.assertRaisesRegex(RuntimeError, "registered /share"):
                _inspect_output(share / "link" / "new", inspector, share_root=share)
            inspector.assert_not_called()

    def test_unknown_capacity_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as folder:
            share = Path(folder) / "share"
            share.mkdir()
            inspector = Mock(side_effect=OSError("actual filesystem inspection unavailable"))
            with self.assertRaises(OSError):
                _inspect_output(share / "new", inspector, share_root=share)
            self.assertFalse((share / "new").exists())


if __name__ == "__main__":
    unittest.main()
