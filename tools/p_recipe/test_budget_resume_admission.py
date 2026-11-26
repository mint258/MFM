"""New regression cases for actual NFS/automount output admission only."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from budget_resume_admission import validate_canonical_filesystem


class CanonicalFilesystemTests(unittest.TestCase):
    def test_autofs_banner_may_differ_from_physical_output(self):
        with tempfile.TemporaryDirectory() as base:
            root=Path(base);physical=root/"project";physical.mkdir()
            # Actual output and canonical probe have the same device, while
            # the autofs top-level banner describes a different device.
            real_stat=__import__("os").stat
            def stat(path,*args,**kw):
                if str(path)==str(root):return SimpleNamespace(st_dev=42)
                return real_stat(path,*args,**kw)
            with patch("budget_resume_admission.shared_guard.disk_probe_target",return_value=str(physical)):
                # Root's device is irrelevant; only actual output is checked.
                with patch("budget_resume_admission.os.stat",side_effect=stat):
                    validate_canonical_filesystem(physical/"future",root)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as base:
            root=Path(base)/"mount";root.mkdir();outside=Path(base)/"outside";outside.mkdir()
            (root/"escape").symlink_to(outside,target_is_directory=True)
            with patch("budget_resume_admission.shared_guard.disk_probe_target",return_value=str(root)):
                with self.assertRaisesRegex(ValueError,"escapes"):
                    validate_canonical_filesystem(root/"escape"/"new",root)

    def test_other_registered_mount_rejected(self):
        with tempfile.TemporaryDirectory() as base:
            root=Path(base)/"mount";root.mkdir()
            with self.assertRaisesRegex(ValueError,"outside"):
                validate_canonical_filesystem(Path(base)/"other"/"future",root)


if __name__=="__main__":
    unittest.main()
