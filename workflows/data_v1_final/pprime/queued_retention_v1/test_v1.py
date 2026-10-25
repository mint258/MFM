"""Four new metadata/guard/readback boundaries; no corpus, UFF or QM calls."""
import copy,datetime,unittest
from .binding_v1 import prove_runtime_copy,validate_start,validate_closed

def start_fixture():
    now=1800000000.
    plan={'schema':'PPRIME_QUEUED_RETENTION_PREPARATION_PLAN_V1','expected_molecules':1000,'expected_pairs':2000,'new_UFF_QM_calls':0,
        'allowed_nodes':['compute-0-'+str(n) for n in range(14,20)],'wall_seconds':3600,
        'estimated_peak_output_bytes':8*1024**3+64*1024**2,'quota_reserve_bytes':200000000000}
    request={'kind':'analysis','pilot':True,'node':'compute-0-14','cpus':16,'memory_gib':64,'wall_seconds':3600,
        'root_review':{'status':'APPROVED'}}
    proof={'request':request,'uid':1278,'observed_at':datetime.datetime.fromtimestamp(now-1,datetime.timezone.utc).isoformat(),
        'existing_jobs_all_users':[],'node_metadata':'NodeName=compute-0-14 RealMemory=375000 AllocMem=65536',
        'committed_memory_mib':0,'account_free_bytes':1000000000000}
    env={'SLURM_JOB_ID':'99999','SLURM_JOB_PARTITION':'cpu','SLURM_CPUS_PER_TASK':'16','SLURM_MEM_PER_NODE':'65536',
        'CUDA_VISIBLE_DEVICES':'',**{k:'1' for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS')}}
    return plan,proof,env,now

def closed_fixture():
    plan={'original_prepared':{'path':'/fixture/prepared.json','sha256':'a','bytes':1},
        'original_pairs':{'path':'/fixture/pairs.jsonl','sha256':'b','bytes':2},'config':{'path':'/fixture/config.json','sha256':'c','bytes':3}}
    rows=[{'record_id':'r'+str(i),'geometry_source':'uff_sprime','physical_identity':{'namespace':'accepted_original_sprime','source_conformer_id':i%5},
        'original_frozen_audit':i<20,'selected':20<=i<25,'retain_all_twelve_raw':i<25,
        'legacy_engine_file_group':5,'size_stratum':'21_40'} for i in range(2000)]
    union=[{'record_id':'r'+str(i)} for i in range(25)];stable=[r for r in rows if r['selected']]
    engine=[{'record_id':'r'+str(i),'file_group':5,'size_stratum':'21_40'} for i in range(25)]
    old=['r'+str(i) for i in range(20)]
    manifest={'schema':'PPRIME_STABLE_RAW_RETENTION_EXECUTION_BINDING_V1','status':'PREPARED_NOT_QM_EXECUTED','QM_started':False,
        'scientific_input_or_numerics_changed':False,'original_prepared_or_config_bytes_changed':False,
        'original_prepared':plan['original_prepared'],'original_pairs':plan['original_pairs'],'audit_policy':plan['config'],
        'original_frozen_audit_records':20,'union_records':25,'stable_full_hits_count':5,'required_full_raw_calls':300}
    return manifest,rows,union,stable,engine,old,plan

class QueuedRetentionBoundaries(unittest.TestCase):
    def test_exact_cpu_call_edit_and_science_byte_drift_rejected(self):
        old=b'def f():\n    observed=IO.runtime(prepare=True)\n    return 1\n'
        new=old.replace(b'observed=IO.runtime(prepare=True)',b'observed=IO.runtime()')
        self.assertTrue(prove_runtime_copy(old,new)['inverse_full_file_bytes_equal'])
        with self.assertRaisesRegex(ValueError,'NON_BINDING_SOURCE_EDIT'):prove_runtime_copy(old,new.replace(b'return 1',b'return 2'))
    def test_strict_cpu_request_and_foreign_memory_denials(self):
        plan,proof,env,now=start_fixture();validate_start(plan,proof,env,'compute-0-14',1278,now)
        for change in ('memory32','legacy_small','foreign_zero','foreign_missing','declared_over85'):
            p=copy.deepcopy(proof)
            if change=='memory32':p['request']['memory_gib']=32
            elif change=='legacy_small':p['request']['resource_policy']='CPU_BOUNDED_TEST_LIVE_MEMORY_V1'
            elif change=='foreign_zero':p['existing_jobs_all_users']=[{'metadata':'JobId=1 MinMemoryNode=0'}]
            elif change=='foreign_missing':p['existing_jobs_all_users']=[{'metadata':'JobId=1'}]
            else:p['committed_memory_mib']=300000
            with self.subTest(change=change),self.assertRaises(ValueError):validate_start(plan,p,env,'compute-0-14',1278,now)
    def test_queue_time_stale_proof_wrong_node_and_quota_rejected(self):
        plan,proof,env,now=start_fixture()
        for change in ('stale','wrong_node','quota'):
            p=copy.deepcopy(proof)
            if change=='stale':p['observed_at']=datetime.datetime.fromtimestamp(now-3601,datetime.timezone.utc).isoformat()
            elif change=='wrong_node':p['request']['node']='compute-0-20'
            else:p['account_free_bytes']=plan['quota_reserve_bytes']+plan['estimated_peak_output_bytes']-1
            with self.subTest(change=change),self.assertRaises(ValueError):validate_start(plan,p,env,'compute-0-14',1278,now)
    def test_retention_union_manifest_and_engine_readback_conservation(self):
        data=closed_fixture();actual=validate_closed(*data)
        self.assertEqual((actual['source_rows'],actual['union_records'],actual['required_full_raw_calls']),(2000,25,300))
        for change in ('drop_stable','engine_source_group','old20','qm_started'):
            d=copy.deepcopy(data)
            if change=='drop_stable':d[2].pop()
            elif change=='engine_source_group':d[4][0]['file_group']=6
            elif change=='old20':d[5][0]='unknown'
            else:d[0]['QM_started']=True
            with self.subTest(change=change),self.assertRaises(ValueError):validate_closed(*d)
if __name__=='__main__':unittest.main()
