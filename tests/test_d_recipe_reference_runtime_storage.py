"""Exercise original disk reserve rejection through the future writer callback."""
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tools.d_recipe import reference_segment_guarded
from tools.d_recipe.reference_runtime_storage import scoped_physical_writes
from workflows.data_v1_final.export.v31_stream_v1 import disk_guard


class ReferenceRuntimeStorageTests(unittest.TestCase):
    def test_original_guard_rejects_real_reserve_or_inode_pressure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gib = 2**30
            fact = dict(path=str(root), device=os.stat(root).st_dev,
                mount=dict(source="fixture", fstype="ext4"), total=200*gib,
                available=25*gib, inodes=20000, root_filesystem=True)
            fs = SimpleNamespace(f_bavail=25*gib, f_frsize=1, f_favail=20000)
            previous = Mock(side_effect=AssertionError("Legacy guard must not run"))
            resources = SimpleNamespace(Guard=disk_guard.Guard, admit_output=previous)
            with patch.object(disk_guard, "inspect", return_value=fact), \
                    patch.object(disk_guard.os, "statvfs", return_value=fs):
                with scoped_physical_writes(resources, root):
                    resources.admit_output({}, root / "collection")
                    # The unchanged Guard selects max(10GiB,10%):20GiB here.
                    fs.f_bavail = 20*gib + 2**26 - 1
                    with self.assertRaisesRegex(disk_guard.DiskUnavailable, "DISK_RESERVE_REACHED"):
                        resources.admit_output({}, root)
                    fs.f_bavail, fs.f_favail = 25*gib, 10999
                    with self.assertRaisesRegex(disk_guard.DiskUnavailable, "DISK_RESERVE_REACHED"):
                        resources.admit_output({}, root)
            self.assertIs(resources.admit_output, previous)
            previous.assert_not_called()

    def test_path_escape_and_write_failure_restore_original_callback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            physical = SimpleNamespace(check=Mock(side_effect=RuntimeError("no physical capacity")))
            factory = Mock(return_value=physical)
            previous = Mock()
            resources = SimpleNamespace(Guard=factory, admit_output=previous)
            with self.assertRaisesRegex(RuntimeError, "no physical capacity"):
                with scoped_physical_writes(resources, root):
                    with self.assertRaisesRegex(ValueError, "escaped"):
                        resources.admit_output({}, root.parent / "outside")
                    resources.admit_output({}, root)
            self.assertIs(resources.admit_output, previous)
            physical.check.assert_called_once_with(root)
            self.assertIs(factory.call_args.kwargs["admit"], False)

    def test_future_entry_restores_scope_after_original_entry_failure(self):
        base = reference_segment_guarded.reference_segment_canonical
        previous = base.scoped_collector_writes
        def original_entry():
            self.assertIs(base.scoped_collector_writes, scoped_physical_writes)
            raise RuntimeError("original entry failed")
        with patch.object(base, "main", side_effect=original_entry):
            with self.assertRaisesRegex(RuntimeError, "original entry failed"):
                reference_segment_guarded.main()
        self.assertIs(base.scoped_collector_writes, previous)


if __name__ == "__main__":
    unittest.main()
