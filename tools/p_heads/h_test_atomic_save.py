"""One synthetic failure/publication test for shared JSON atomic writes."""
import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import h_resources


class AtomicSave(unittest.TestCase):
 def test_atomic_publication_failure_and_symlink_target(self):
  # Root admits this tiny CPU-only test on the actual NFS filesystem first.
  with tempfile.TemporaryDirectory(dir=os.environ['TMPDIR']) as directory,patch.object(h_resources,'guard',return_value=None):
   fixture=Path(directory).resolve();target=fixture/'shared.json';old={'generation':0,'payload':'complete-old'};new={'generation':1,'payload':'complete-new'}
   h_resources.save(target,old)
   target.chmod(0o640)
   def fail_replace(source,destination):
    self.assertEqual(Path(source).parent,target.parent)
    self.assertEqual(Path(source).stat().st_dev,target.parent.stat().st_dev)
    self.assertEqual(Path(destination),target)
    self.assertEqual(json.loads(Path(source).read_text()),new)
    raise OSError('synthetic publication failure')
   with patch.object(h_resources.os,'replace',side_effect=fail_replace),self.assertRaisesRegex(OSError,'synthetic publication failure'):
    h_resources.save(target,new)
   self.assertEqual(json.loads(target.read_text()),old)
   self.assertEqual(target.stat().st_mode&0o777,0o640)
   self.assertEqual(list(fixture.iterdir()),[target])
   h_resources.save(target,new)
   self.assertEqual(json.loads(target.read_text()),new)
   self.assertEqual(target.stat().st_mode&0o777,0o640)
   self.assertEqual(list(fixture.iterdir()),[target])
   link_directory=fixture/'links';link_directory.mkdir();link=link_directory/'shared.json';link.symlink_to(target)
   through_link={'generation':2,'payload':'complete-through-live-link'};real_replace=h_resources.os.replace
   def checked_replace(source,destination):
    self.assertEqual(Path(source).parent,target.parent)
    self.assertNotEqual(Path(source).parent,link.parent)
    self.assertEqual(Path(destination),target)
    self.assertEqual(json.loads(Path(source).read_text()),through_link)
    real_replace(source,destination)
   with patch.object(h_resources.os,'replace',side_effect=checked_replace):h_resources.save(link,through_link)
   self.assertTrue(link.is_symlink());self.assertEqual(link.resolve(),target)
   self.assertEqual(json.loads(target.read_text()),through_link)
   self.assertEqual(json.loads(link.read_text()),through_link)
   self.assertEqual(target.stat().st_mode&0o777,0o640)
   self.assertEqual(set(fixture.iterdir()),{target,link_directory})


if __name__=='__main__':unittest.main()
