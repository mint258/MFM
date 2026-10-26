"""Explicit node13 mount translation; immutable source bytes and physical frame remain mandatory."""
import hashlib,json,pathlib,unittest
from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C,runtime_io as R
HERE=pathlib.Path(__file__).absolute().parent
ORIGINAL=C.HERE/'prepare_batch.py'
EXPECTED={'path':'/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011/population/formal_record_index.parquet','bytes':1242386629,'sha256':'ef2d99ae1b6c1001f6ffeb979ebafd10b04c13fa4774e52527a90a6276c06276'}

def transform(old):
 edits=[('from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C,runtime_io as R','from workflows.data_v1_final.conformers.formal_cpu_auto_v3 import contract as C,runtime_io as R\nfrom workflows.data_v1_final.conformers.formal_cpu_auto_prepare_mapping_v1 import mapping as M'),("'quota-reuse-review','output'","'quota-reuse-review','source-mapping-review','output'"),("args,'prepare',OPTIONS)\n","args,'prepare',OPTIONS)\n    M.source_proof();M.fixtures();R.authorized(proof,[C.ref(M.HERE/'mapping.py'),C.ref(M.HERE/'prepare_batch.py')])\n"),('source=R.formal_source(value)','source=M.formal_source(value,proof,args.source_mapping_review)')]
 for before,after in edits:
  C.need(old.count(before)==1,'EXACT_SINGLE_SOURCE_TRANSFORMATION_REQUIRED');old=old.replace(before,after)
 return old

def source_proof():
 C.need(C.ref(ORIGINAL) in C.sources().values() or C.ref(ORIGINAL)['sha256']=='b7d6feec05de79b0e40d6a3c0092ea07a5bdf5725ec1063f8115641e180ffa82','FROZEN_ORIGINAL_PREPARE_REQUIRED')
 C.need((HERE/'prepare_batch.py').read_text()==transform(ORIGINAL.read_text()),'ONLY_EXPLICIT_PREPARE_MOUNT_CALLSITE_ADAPTATION_ALLOWED')

def stable_frame(info):return (info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid)
def source_frame(info):return (info.st_ino,info.st_size,info.st_mtime_ns,info.st_uid)
def expected_frame(value):return tuple(value[k] for k in ('inode','size','mtime_ns','uid'))

def formal_source(value,proof,review_path):
 review_ref=R.input_ref(pathlib.Path(proof['request']['startup_proof_path']),review_path);review=C.read(review_ref)
 C.need(review['schema']=='ROOT_SPRIME_NODE13_SOURCE_MOUNT_MAPPING_V1' and review['status']=='APPROVED_EXACT_CANONICAL_SOURCE_MAPPING' and review['reviewer']=='root' and review['endpoint']=='202.38.247.57:22' and review['uid']==1278 and review['node']==proof['node']=='compute-0-13','EXPLICIT_ROOT_SAME_STORAGE_APPROVAL_REQUIRED')
 C.need(review['formal_source_receipt']==value['formal_source_receipt'] and review['canonical_reference']==EXPECTED,'ONLY_ORIGINAL_CANONICAL_SOURCE_MAPPING')
 refs=[review[k] for k in ('formal_source_receipt','prior_cpu_source_validation','same_storage_mapping','quota_provider_review')];R.authorized(proof,refs)
 receipt=C.read(review['formal_source_receipt']);C.need(receipt['status']=='ALL_BOUND_INPUTS_SHA_VERIFIED','ORIGINAL_CLOSED_SOURCE_REQUIRED');row=next(x for x in receipt['outputs'] if x['name']=='formal_population');reference=row['reference'];C.need(reference==EXPECTED and row['after']==review['historical_frame'],'HISTORICAL_SOURCE_AUTHORITY_UNCHANGED')
 validation=C.read(review['prior_cpu_source_validation']);prior=[x for x in validation['inputs'] if x['reference']==reference]
 C.need(validation['status']=='ALL_ACTUAL_SOURCE_SHA_VERIFIED' and validation['runtime']['job_id']=='4521417' and len(prior)==1 and prior[0]['actual']==reference and prior[0]['status']=='ACTUAL_FULL_SHA_MATCH' and prior[0]['inode']==row['after']['inode'] and prior[0]['mtime_ns']==row['after']['mtime_ns'] and prior[0]['uid']==1278,'ACTUAL_NODE13_SAME_INODE_AND_FULL_SHA_EVIDENCE_REQUIRED')
 R.authorized(proof,[reference]);path=pathlib.Path(reference['path']);before=path.stat()
 C.need(source_frame(before)==expected_frame(row['after']) and before.st_dev==prior[0]['device'],'CURRENT_NODE13_FRAME_MUST_MATCH_REAL_PRIOR_CPU_MAPPING')
 C.pinned(reference);after=path.stat();C.need(stable_frame(before)==stable_frame(after),'ENTIRE_CURRENT_FRAME_CHANGED_DURING_FULL_SHA_READ')
 R.write_json_new(R.OUT/'canonical_source_current_mount_identity.json',{'schema':'ACTUAL_CANONICAL_SOURCE_NODE13_MOUNT_VALIDATION_V1','reference':reference,'root_mapping_review':review_ref,'historical_frame':row['after'],'actual_current_frame':dict(zip(('device','inode','size','mtime_ns','uid'),stable_frame(after))),'complete_SHA_verified_on_actual_CPU':True,'device_translation_only':True,'original_data_modified':False})
 return reference

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