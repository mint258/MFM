"""Explicit node13 mount translation; immutable source bytes and physical frame remain mandatory."""
import hashlib,json,pathlib,unittest
from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1 import contract as C,runtime_io as R
HERE=pathlib.Path(__file__).absolute().parent
ORIGINAL=C.HERE/'prepare_batch.py'
EXPECTED={'path':'/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/population/formal_record_index.parquet','bytes':1242386629,'sha256':'ef2d99ae1b6c1001f6ffeb979ebafd10b04c13fa4774e52527a90a6276c06276'}

def transform(old):
 edits=[('from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1 import contract as C,runtime_io as R','from workflows.data_v1_final.conformers.sprime_cpu17_resource_v1 import contract as C,runtime_io as R\nfrom workflows.data_v1_final.conformers.formal_cpu_auto_prepare_mapping_v1 import mapping as M'),("'quota-reuse-review','output'","'quota-reuse-review','source-mapping-review','output'"),("args,'prepare',OPTIONS)\n","args,'prepare',OPTIONS)\n    M.source_proof();M.fixtures();R.authorized(proof,[C.ref(M.HERE/'mapping.py'),C.ref(M.HERE/'prepare_batch.py')])\n"),('source=R.formal_source(value)','source=M.formal_source(value,proof,args.source_mapping_review)')]
 for before,after in edits:
  C.need(old.count(before)==1,'EXACT_SINGLE_SOURCE_TRANSFORMATION_REQUIRED');old=old.replace(before,after)
 return old

def source_proof():
 from .source_proof import verify
 return verify()


def stable_frame(info):return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid)
def source_frame(info):return (info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid)
def expected_frame(value):return tuple(value[k] for k in ('inode','size','mtime_ns','uid'))

def formal_source(value,proof,review_path):
 from .quota_edge import formal_source as mapped
 return mapped(value,proof,review_path)


def fixtures():
 from types import SimpleNamespace
 class Boundaries(unittest.TestCase):
  def test_mapped_device_only(self):
   a=SimpleNamespace(st_dev=52,st_ino=10,st_size=20,st_mtime_ns=30,st_uid=1278);b=SimpleNamespace(**vars(a));b.st_dev=53;self.assertEqual(source_frame(a),source_frame(b));self.assertNotEqual(stable_frame(a),stable_frame(b))
  def test_inode(self):self.assertNotEqual(expected_frame(dict(inode=10,size=20,mtime_ns=30,uid=1278)),expected_frame(dict(inode=11,size=20,mtime_ns=30,uid=1278)))
  def test_size(self):self.assertNotEqual(expected_frame(dict(inode=10,size=20,mtime_ns=30,uid=1278)),expected_frame(dict(inode=10,size=21,mtime_ns=30,uid=1278)))
  def test_mtime(self):self.assertNotEqual(expected_frame(dict(inode=10,size=20,mtime_ns=30,uid=1278)),expected_frame(dict(inode=10,size=20,mtime_ns=31,uid=1278)))
  def test_uid(self):self.assertNotEqual(expected_frame(dict(inode=10,size=20,mtime_ns=30,uid=1278)),expected_frame(dict(inode=10,size=20,mtime_ns=30,uid=1264)))
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries));C.need(result.wasSuccessful() and result.testsRun==5,'ALL5_MAPPING_BOUNDARIES_MUST_PASS')