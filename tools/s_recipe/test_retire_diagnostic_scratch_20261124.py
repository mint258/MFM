"""New cleanup safety on tiny synthetic files only."""
from pathlib import Path
import tempfile
import unittest
from retire_diagnostic_scratch_20261124 import checked_file,retire_one


class ClosedScratchSafety(unittest.TestCase):
    def test_exact_planned_owned_inode_only(self):
        with tempfile.TemporaryDirectory(prefix='S_retire_newlogic_') as root:
            base=Path(root)
            path=base/'chunk_0.pt'
            path.write_bytes(b'fake closed H')
            row=checked_file(path,base)
            retire_one(row,base)
            self.assertFalse(path.exists())

    def test_changed_file_link_or_escape_is_retained(self):
        with tempfile.TemporaryDirectory(prefix='S_retire_newlogic_') as root:
            base=Path(root)
            allowed=base/'allowed'
            allowed.mkdir()
            path=allowed/'chunk_0.pt'
            path.write_bytes(b'initial')
            row=checked_file(path,allowed)
            path.write_bytes(b'changed state')
            with self.assertRaises(ValueError):retire_one(row,allowed)
            self.assertTrue(path.exists())
            link=allowed/'chunk_1.pt'
            link.symlink_to(path)
            with self.assertRaises(ValueError):checked_file(link,allowed)
            outside=base/'foreign.pt'
            outside.write_bytes(b'keep')
            with self.assertRaises(ValueError):checked_file(outside,allowed)
            self.assertTrue(outside.exists())


if __name__=='__main__':unittest.main()
