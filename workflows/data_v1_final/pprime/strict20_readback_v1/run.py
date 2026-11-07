"""Actual Main readonly CPU stage: source3, finite resource observations, evidence."""
from __future__ import annotations
import argparse,io,json,os,pathlib,socket,time,traceback,unittest
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R
from . import contract as C,io as I

def fixtures(out,store):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT3_MEANINGFUL_BOUNDARY_METHODS')
    text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    ref=store.json(out/'source3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':text.getvalue(),
        'synthetic_only':True,'before_scientific_DATA_and_observer':True,'native_calls':0})
    C.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'ALL3_PASSED_BEFORE_DATA')
    return ref

def guard(path,plan,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    mode=plan['mode'];params=C.parameters(mode,plan.get('group_index'))
    C.need(plan['schema']=='STRICT20_READBACK_PLAN_V1' and plan['scope_parameters']==params
        and plan['wall_seconds']==C.WALL and plan['output_cap_bytes']==C.cap(mode),'EXACT_FINITE_TWO_STAGE_PLAN')
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)]
    proof=require_startup(proof_path,expected_scope_key=C.scope(mode),expected_scope_parameters=params,
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',
        required_references=[C.Q.pin(path),plan['resource_authority_reference'],plan['cost_decision_reference'],plan['quota_reuse_reference']])
    req=proof['request'];C.need(req['cpus']==16 and req['pilot'] is False and req['wall_seconds']==C.WALL
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['estimated_peak_output_bytes']==C.cap(mode)
        and req['data_references']==plan['data_references'] and not req.get('deferred_authority_references'),
        'ACTUAL16_NO_MEM_EXACT_DECLARATIONS_NOT_QM')
    for ref in plan['source_references']:C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'FROZEN_SOURCE_AND_SMALL_PARENT_BEFORE_DATA')
    parent=C.parents(plan);C.need(parent[2]==plan['data_references'],'SAME_ACTUAL_C0_PARENT_LOCATORS')
    quota=C.meta(plan['quota_reuse_reference']);C.F.Provider.load_review(quota['provider_review_reference'])
    C.need(quota['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY' and quota['compute_node']==req['node']=='compute-0-13',
        'ORIGINAL_PROVIDER_NODE13_RESOURCE_BOUNDARY_NOT_SCIENTIFIC_PORT')
    return proof,parent,quota

class Budget:
    def __init__(self,plan,proof,quota,out):
        self.plan=plan;self.proof=proof;self.quota=quota;self.out=out;self.start=time.monotonic();self.last=0;self.poll=0;self.observations=0;self.latest=None
        self.client=C.F.Provider.Client(quota['provider_review_reference'],proof['request'])
        job=C.Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata']
        text=job['RunTime'];days,text=text.split('-',1) if '-' in text else ('0',text);h,m,s=map(int,text.split(':'))
        self.initial=int(days)*86400+h*3600+m*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    def check(self):
        now=time.monotonic();R.soft_worker_rss(3<<30)
        if now-self.start+self.initial>=C.WALL-300:R.mark_stop('READBACK_FINITE_WALL_NATURAL_DRAIN',{'elapsed_seconds':now-self.start})
        C.need(not R.stop_requested(),'READBACK_STOP_NEW_READS_PRESERVE_ALL_OLD_EVIDENCE')
        if now-self.last<1:return
        self.last=now;C.need(os.getuid()==1278 and os.environ.get('SLURM_CPUS_PER_TASK')=='16'
            and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id']) and socket.gethostname().split('.')[0]=='compute-0-13'
            and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_ADMITTED_MAIN_PARENT')
        cap=C.cap(self.plan['mode']);wave=self.quota['whole_wave_output_reserve_bytes'];v=os.statvfs(C.ROOT)
        C.need(v.f_bavail*v.f_frsize-wave-cap>=200000000000,'WHOLE_WAVE_PLUS_OWN_CAP_PLUS200GB_PHYSICAL')
        if self.observations==0 or now-self.poll>=60:
            self.poll=now;self.latest=self.client.observe();self.observations+=1
            C.need(self.latest['free_bytes']-wave-cap>=200000000000,'FINITE_ACCOUNT_PROVIDER_WHOLE_WAVE_PLUS_OWN_PLUS200GB')
    def report(self):return {'actual_account_observations':self.observations,'last_account_observation':self.latest,
        'whole_wave_reserve_bytes':self.quota['whole_wave_output_reserve_bytes'],'physical_free_is_not_account_quota':True,
        'provider_auto_renewed':False,'forced_signals_sent':False,'current_provider_resource_node':'compute-0-13'}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.Q.load(a.plan);proof,parent,quota=guard(a.plan,plan,a.startup_proof);mode=plan['mode']
    out=I.fresh(plan['output_directory'],C.BASE);out.mkdir(parents=True,mode=0o700)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';started=time.monotonic();store=I.Store(out,lambda:None,mode);gate=resource=None;result={};error=None;budget=None
    try:
        gate=fixtures(out,store)
        R.start_observer(proof,{'resource_evidence_output':str(out/'resources'),'resource_evidence_local_cap_bytes':8<<20,
            'memavailable_soft_floor_bytes':4<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.cap(mode)})
        budget=Budget(plan,proof,quota,out);store.check=budget.check;budget.check()
        if mode=='inventory':from .inventory import produce
        else:from .replay import produce
        result=produce(plan,parent,out,store,budget.check);budget.check()
        for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'FROZEN_SOURCE_SMALL_PARENTS_UNCHANGED_AFTER_DATA')
    except BaseException as exc:
        error={'type':type(exc).__name__,'scope':'READONLY_AUDIT_HOLD_NOT_NEW_QM_FAILURE'}
        try:store.json(out/'stage_failure.DATA.json',{'error':str(exc),'traceback':traceback.format_exc()},failure=True)
        except Exception:pass
    finally:
        if R.MONITOR is not None:
            try:R.MONITOR.finish();resource=C.Q.pin(out/'resources/closure.json')
            except BaseException as exc:error=error or {'type':type(exc).__name__,'scope':'RESOURCE_CLOSURE_HOLD'}
    complete=error is None and resource is not None and not R.stop_requested() and result.get('held_calls')==0
    complete=complete and (result.get('completed_calls')==1200 if mode=='inventory' else result.get('all60_and25_exact') is True)
    manifest={'schema':'STRICT20_READBACK_MANIFEST_V1','status':'COMPLETE_READONLY_EVIDENCE_PHYSICAL_UNKNOWN' if complete else 'INCOMPLETE_READONLY_AUDIT_HOLD',
        'mode':mode,'group_index':plan.get('group_index'),'job_id':str(proof['job_id']),'uid':1278,'node':proof['request']['node'],
        'endpoint':'202.38.247.57:22','plan_reference':C.Q.pin(a.plan),'startup_proof_reference':C.Q.pin(a.startup_proof),
        'actual_root_review_reference':plan['actual_root_review_reference'],'source3_reference':gate,'resource_observation_reference':resource,
        'budget':budget.report() if budget else None,'error':error,**result,'new_QM_UFF_calls':0,'native_initialize_or_invoke_calls':0,
        'native_inline_processing_independently_replayed':False,'native_units_sign_basis_origin_axes_accepted':False,
        'SCF_cause':'UNKNOWN','scientific_PASS':False,'full_or2000_release':'HOLD','old15FAIL_preserved':True,
        'all_original_DATA_masks_and_tolerances_unchanged':True,'automatic_retry':False,'elapsed_seconds':time.monotonic()-started}
    ref=C.Q.write_new(out/'manifest.json',manifest)
    C.need(sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<=C.cap(mode),'ACTUAL_WHOLE_STAGE_PARTITION_CAP')
    print(json.dumps({'status':manifest['status'],'manifest':ref,'new_QM_calls':0}));return 0 if complete else 3
if __name__=='__main__':raise SystemExit(main())
