"""Three pure resource boundaries, with an optional actual Main17 CPU receipt."""
import argparse,copy,io,pathlib,unittest
from . import contract as C,quota_edge as E,recovery as K
KEY='sprime_cpu17_resource_source3_v1'
PARAMS={'tests':3,'synthetic_only':True,'new_UFF_calls':0,'new_QM_calls':0,'DATA_bodies_opened':0,'fixed_node':'compute-0-17'}


def data_frame(reference,info):
    # Large DATA references are shapes, never small-source reads or hashes here.
    value=C.triple(reference)
    C.need(value['bytes']==info.st_size and info.st_uid==1278,'DATA_SIZE_UID_CHANGED')
    return E.frame(info)


def deadline(value,identity,now):
    C.need(type(value) in (int,float) and now<value<=identity['expires_unix_seconds']-300,'FINITE_SAME_EPOCH_ABSOLUTE_DEADLINE')
    return value


class Boundaries(unittest.TestCase):
    def test_large_data_shape_and_identity(self):
        from types import SimpleNamespace
        reference={'path':'/share/home/zixiao/existing/control_tasks.jsonl','bytes':5<<20,'sha256':'a'*64}
        info=SimpleNamespace(st_size=5<<20,st_uid=1278,st_dev=71,st_ino=9,st_mtime_ns=123)
        self.assertEqual(data_frame(reference,info)['size'],5<<20)
        for key,value in (('bytes',0),('bytes',True),('sha256','a'*65),('sha256','g'*64),('path','relative/tasks.jsonl')):
            bad=dict(reference);bad[key]=value
            with self.assertRaises(ValueError):data_frame(bad,info)
        for key,value in (('st_size',(5<<20)+1),('st_uid',1264)):
            bad=SimpleNamespace(**vars(info));setattr(bad,key,value)
            with self.assertRaises(ValueError):data_frame(reference,bad)

        empty={'path':str(C.REPO/'synthetic_source_boundary/__init__.py'),'bytes':0,'sha256':C.EMPTY_SOURCE_SHA}
        self.assertEqual(C.source_triple(empty),empty)
        from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import pin as central_source_shape
        self.assertEqual(central_source_shape(empty),empty)
        for bad in (dict(empty,sha256='0'*64),dict(empty,bytes=False),dict(empty,path=str(C.REPO/'synthetic_source_boundary/empty.py'))):
            with self.assertRaises(ValueError):C.source_triple(bad)
        with self.assertRaises(ValueError):C.triple(empty) # DATA remains strictly positive.
        from .metadata import References
        with self.assertRaises(ValueError):References({'source_references':[],'data_references':[empty]})
        import stat
        zero=SimpleNamespace(st_dev=71,st_ino=9,st_mode=stat.S_IFREG|0o644,st_nlink=1,st_size=0,st_mtime_ns=123,st_ctime_ns=456,st_uid=1278)
        self.assertEqual(C.empty_source_frame(zero,zero)[4],0)
        for key,value in (('st_uid',1264),('st_dev',72),('st_nlink',2),('st_ino',10),('st_size',1),('st_mtime_ns',124),('st_ctime_ns',457),('st_mode',stat.S_IFLNK|0o777)):
            changed=SimpleNamespace(**vars(zero));setattr(changed,key,value)
            with self.assertRaises(ValueError):C.empty_source_frame(zero,changed)

    def test_only_remaining_slots_inverse_and_original_keys(self):
        slot={'batch_id':'batch-00096','node':C.NODE,'cpus':16,'wall_seconds':28800,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
          'whole_output_cap_bytes':C.CAP,'job_name':'new17','output_root':'/share/home/zixiao/new17'}
        old=dict(slot,node='compute-0-13',job_name='old13',output_root='/share/home/zixiao/old13')
        review={'jobs':[slot],'maximum_concurrent_jobs':1}
        self.assertEqual(K.replacement_slot(old,review),slot)
        for key,value in (('cpus',32),('wall_seconds',28799),('batch_id','batch-00095'),('whole_output_cap_bytes',C.CAP-1)):
            bad=copy.deepcopy(review);bad['jobs'][0][key]=value
            with self.assertRaises(ValueError):K.replacement_slot(old,bad)
        self.assertEqual(C.task_key('m','fill_10N'),K.OLD_K.F.task_key('m','fill_10N'))
        self.assertEqual(C.seed_for('m',False),K.OLD_K.F.seed_for('m',False))

    def test_capacity_and_fixed_finite_deadline(self):
        from . import capacity_gate as G
        raw={'NodeName':C.NODE,'CPUTot':'104','CPUAlloc':'89','State':'MIXED','Partitions':'cpu'}
        self.assertEqual(G.capacity(raw)['action'],'WAIT_EXISTING_JOBS_OR_CAPACITY')
        raw['CPUAlloc']='88';self.assertEqual(G.capacity(raw)['action'],'PROCEED')
        self.assertEqual(deadline(1600,{'expires_unix_seconds':1900},1000),1600)
        for value in (1000,1601,1900):
            with self.assertRaises(ValueError):deadline(value,{'expires_unix_seconds':1900},1000)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('plan','root-preflight','output'):p.add_argument('--'+k,type=pathlib.Path,required=True)
    a=p.parse_args();pr=C.ref(a.plan);plan=E.meta(pr)
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as A
    argv=[E.Q.PY,'-B','-m',C.MODULE+'.test_binding','--plan',str(a.plan),'--root-preflight',str(a.root_preflight),'--output',str(a.output)]
    proof=A.require_startup(a.root_preflight,expected_scope_key=KEY,expected_scope_parameters=PARAMS,expected_execution_argv=argv,
      expected_source=__file__,expected_kind='analysis',required_references=[pr,*C.own_sources(),*plan['source_references']])
    C.need(proof['request']['node']==C.NODE and proof['request']['wall_seconds']==900 and plan['mode']=='source3','ACTUAL_MAIN17_SOURCE3')
    inverse=C.source_inverse_proof();suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries)
    transcript=io.StringIO();result=unittest.TextTestRunner(stream=transcript,verbosity=2).run(suite)
    passed=result.wasSuccessful() and result.testsRun==3
    out=a.output;C.need(out.is_absolute() and C.BASE in out.parents and not out.exists(),'FRESH_SOURCE3_OUTPUT');out.mkdir(parents=True,mode=0o700)
    from workflows.data_v1_final.execution.sprime_wave2_metadata_v1.generate import write_new
    write_new(out/'receipt.json',{'schema':'ACTUAL_MAIN17_RESOURCE_SOURCE3_RECEIPT_V1','status':'PASS' if passed else 'FAIL',
      'job_id':str(proof['job_id']),'node':C.NODE,'uid':1278,'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
      'transcript':transcript.getvalue(),'source_references':C.own_sources(),'inverse_proof':inverse,'new_UFF_calls':0,'new_QM_calls':0,
      'DATA_bodies_opened':0,'plan_reference':pr,'startup_proof_reference':C.ref(a.root_preflight)})
    return 0 if passed else 3


if __name__=='__main__':raise SystemExit(main())