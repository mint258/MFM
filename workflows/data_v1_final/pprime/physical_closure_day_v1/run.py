"""One real analysis-day parent; retained outputs only, never native calls."""
from __future__ import annotations
import argparse,contextlib,importlib,io,os,pathlib,socket,sys,threading,time,traceback,unittest
from workflows.data_v1_final.execution.cpu_analysis_day_v1.runtime import require_startup
from workflows.data_v1_final.execution.cpu_analysis_day_v1.quota_provider import Client
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R
from workflows.data_v1_final.pprime.strict20_readback_v1 import replay as B
from . import contract as C,io as I,reduce as D,tensor as T,native as N

def tests(out,store):
    from .test_v1 import Boundaries
    from workflows.data_v1_final.execution.cpu_analysis_day_v1.test_v1 import Boundaries as Resources
    result=[]
    for name,cls in (('producer3',Boundaries),('resource3',Resources)):
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(cls);C.need(suite.countTestCases()==3,'EXACT3:'+name)
        stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
            'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),
            'transcript':stream.getvalue(),'before_existing_DATA_and_monitor':True,'author_execution_claimed':False}
        result.append(store.json(out/(name+'.json'),value))
        C.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE_BOUNDARIES_BEFORE_DATA:'+name)
    return result

class Budget:
    def __init__(self,plan,proof):
        self.plan=plan;self.proof=proof;self.req=proof['request'];self.start=time.monotonic();self.last=0.;self.poll=0.;self.count=0;self.latest=None
        self.carve=C.meta(self.req['root_carveout_review_reference'])
        self.client=Client(self.req['quota_provider_review_reference'],self.req)
        j=C.Q.fields(proof['job_metadata']) if isinstance(proof['job_metadata'],str) else proof['job_metadata']
        text=j['RunTime'];days,text=text.split('-',1) if '-' in text else ('0',text);h,m,s=map(int,text.split(':'))
        self.initial=int(days)*86400+h*3600+m*60+s+max(0,time.time()-proof['memory_observation']['observed_unix_seconds'])
    def check(self):
        R.soft_worker_rss(3<<30);now=time.monotonic()
        if now-self.start+self.initial>=C.WALL-300:R.mark_stop('PHYSICAL_DAY_WALL_STOP_NEW_READS_NATURAL_DRAIN',{})
        C.need(not R.stop_requested(),'PHYSICAL_DAY_STOP_PRESERVE_PARTIAL_AND_OLD_OUTPUTS')
        if now-self.last<1:return
        self.last=now
        C.need(os.getuid()==1278 and os.environ.get('SLURM_JOB_ID')==str(self.proof['job_id']) and
            os.environ.get('SLURM_CPUS_PER_TASK')=='16' and socket.gethostname().split('.')[0]==self.req['node']
            and pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==self.proof['boot_id'],'SAME_REAL_DAY_PARENT')
        reserved=self.carve['total_future_reserved_bytes'];v=os.statvfs(C.ROOT)
        C.need(v.f_bavail*v.f_frsize-reserved>=200000000000,'PHYSICAL_FREE_MINUS_WHOLE_CARVE_ONCE_MINUS200GB')
        if not self.count or now-self.poll>=30:
            self.poll=now;self.latest=self.client.observe();self.count+=1
            C.need(self.latest['free_bytes']-reserved>=200000000000,'ACTUAL_ACCOUNT_FREE_MINUS_WHOLE_CARVE_ONCE_MINUS200GB')
    def report(self):
        return {'actual_account_observations':self.count,'last_account_observation':self.latest,'total_future_reserved_bytes':self.carve['total_future_reserved_bytes'],
            'own_cap_already_in_total_not_subtracted_twice':True,'physical_statvfs_is_not_account_quota':True,
            'auto_renewal_or_forced_signals':False,'actual_elapsed_seconds_including_admission':time.monotonic()-self.start+self.initial}

@contextlib.contextmanager
def no_native_calls():
    """A temporary call observer, never a replacement of any scientific object."""
    attempts=[];lock=threading.Lock();old=sys.getprofile();old_thread=threading.getprofile()
    roots=(str(C.ROOT.parent/'phase1_wp5_20261011/scripts'),str(C.ROOT.parent/'phase1_dataset_rebuild_20261010/scripts'))
    def guard(frame,event,arg):
        if event=='call' and frame.f_code.co_name in ('initialize_worker','invoke') and frame.f_code.co_filename.startswith(roots):
            with lock:attempts.append({'function':frame.f_code.co_name,'source':frame.f_code.co_filename})
            raise RuntimeError('FORBIDDEN_NATIVE_INITIALIZE_OR_INVOKE_BEFORE_FUNCTION_BODY')
        return guard
    sys.setprofile(guard);threading.setprofile(guard)
    try:yield attempts
    finally:sys.setprofile(old);threading.setprofile(old_thread)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=pathlib.Path,required=True);parser.add_argument('--startup-proof',type=pathlib.Path,required=True);a=parser.parse_args()
    plan=C.Q.load(a.plan);params=C.parameters(plan['output_cap_bytes'])
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(a.plan),'--startup-proof',str(a.startup_proof)]
    proof=require_startup(a.startup_proof,expected_scope_key=C.KEY,expected_scope_parameters=params,expected_execution_argv=argv,
        expected_source=__file__,expected_kind='analysis',required_references=[C.Q.pin(a.plan),plan['resource_authority_reference'],plan['cost_decision_reference'],plan['producer_root_review_reference']])
    req=proof['request'];C.need(plan['schema']=='PPRIME_PHYSICAL_CLOSURE_DAY_PLAN_V1' and plan['scope_key']==C.KEY and plan['scope_parameters']==params
        and req['cpus']==16 and req['pilot'] is False and plan['performance_statistics'] is False
        and req['wall_seconds']==plan['wall_seconds']==C.WALL and req['estimated_peak_output_bytes']==plan['output_cap_bytes']
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED','ONE_EXACT_READONLY_DAY_PROTOCOL')
    review=C.meta(plan['producer_root_review_reference']);C.need(review['schema']=='ROOT_EXACT_PPRIME_PHYSICAL_CLOSURE_DAY_REVIEW_V1'
        and review['status']=='APPROVED' and review['reviewer']=='root' and review['candidate_plan_reference']==plan['candidate_plan_reference'],
        'ACTUAL_INDEPENDENT_ROOT_PRODUCER_REVIEW_NOT_QM_PERMISSION')
    candidate=C.meta(plan['candidate_plan_reference']);C.need({k:v for k,v in plan.items() if k not in ('producer_root_review_reference','candidate_plan_reference')}==candidate,'ONLY_REVIEW_BINDINGS_AFTER_CANDIDATE')
    authority,data,parents,ep,official=C.derive(plan)
    C.need(authority==plan['authority'] and data==plan['data_references']==req['data_references'],'EXACT_CLOSED_PRODUCER_DATA_LOCATORS')
    for ref in plan['source_references']:
        C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'CURRENT_SOURCE_AND_SMALL_PARENT_PINS')
    for path in C.sources():C.need(C.Q.pin(path) in plan['source_references'],'COMPLETE_ORIGINAL_AND_NEW_SOURCE_CLOSURE')
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_REPORT_CONTINUE_QUALITY_UNCHANGED')
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';out=I.fresh(plan['output_directory'],C.BASE);out.mkdir(parents=True,mode=0o700)
    store=I.Store(out,lambda:None,plan['output_cap_bytes']);gate=[];budget=None;observation=None;errors=[];sections={};attempts=[];objects=None
    try:
        gate=tests(out,store)
        R.start_observer(proof,{'resource_evidence_output':str(out/'resources'),'resource_evidence_local_cap_bytes':128<<20,
            'memavailable_soft_floor_bytes':4<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':plan['output_cap_bytes']})
        budget=Budget(plan,proof);store.check=budget.check;budget.check()
        with no_native_calls() as attempts:
            objects=B.originals();engine,wire,_,_=objects;math=importlib.import_module('math_v1')
            roots=[C.P.ACTUAL,C.P.BASE,C.ROOT/'artifacts',C.REPO/'configs/data_v1/pprime']
            analysis=I.value(authority['analysis_reference'],roots,data,2<<20);config=I.value(authority['audit_configuration_reference'],roots,data,2<<20)
            def groups():
                for g in authority['groups']:budget.check();yield I.value(g['evidence_reference'],roots,data,2<<20)
            result,detail=D.collect(analysis,groups(),config,wire.exact)
            result_ref=store.json(out/'defined_QC_summary.DATA.json',result);pair_ref=store.json(out/'original_pair_checks.DATA.json',detail)
            sections['defined']={'summary_DATA_reference':result_ref,'pair_DATA_reference':pair_ref,'own_rows':result['own_rows'],
                'pair_rows':result['pair_rows'],'vector_checks':result['vector_checks'],'empty_vector_pair_rows':result['empty_vector_pair_rows'],
                'SCF_original_converged_counts':result['SCF_original_converged_counts'],'vector_matrix':result['vector_matrix']}
            sections['retained_tensors_and_gradient']=T.run(plan,authority,ep,analysis,config,objects,store,out,budget.check)
            old_report=I.value(authority['old72_evaluation_reference'],roots,data,8<<20);old=T.old_controls(old_report)
            old_ref=store.json(out/'old72_controls.DATA.json',old);sections['old72']={'DATA_reference':old_ref,'origin_counts':old['origin_counts'],
                'tensor_counts':old['tensor_counts'],'companion_original_gate_counts':old['companion_original_gate_counts'],
                'old_contradictions':len(old['old_contradictions']),'missing_origin_controls':old['missing_origin_controls']}
            source=N.official(official);source_ref=store.json(out/'official_source_facts.json',source)
            sections['official_source']={'reference':source_ref,'exact_primary_source_files':len(source['source_facts']),
                'SOURCE_context_unknown_roles':[r['role'] for r in source['source_facts'] if r['source_fact_state'].startswith('UNKNOWN')]}
            sections['native384']=N.run(plan,authority,config,math,store,out,budget.check)
            C.need(engine.CONFIG is None and engine.NATIVE is None and engine.WORK is None and not attempts,'NO_INITIALIZATION_NATIVE_OR_ONCE')
            budget.check()
            for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'SOURCE_AND_SMALL_PARENTS_STABLE_AFTER_DATA')
    except BaseException as exc:
        errors.append({'type':type(exc).__name__,'state':'READONLY_PHYSICAL_EVIDENCE_HOLD_NOT_NEW_LABEL_FAILURE'})
        try:store.json(out/'failure.DATA.json',{'message':str(exc),'traceback':traceback.format_exc(),'sections_closed':list(sections)},failure=True)
        except Exception:pass
    finally:
        if R.MONITOR is not None:
            try:R.MONITOR.finish();observation=C.Q.pin(out/'resources/closure.json')
            except BaseException as exc:errors.append({'type':type(exc).__name__,'state':'RESOURCE_CLOSURE_HOLD'})
    complete=not errors and observation is not None and not R.stop_requested() and len(sections)==5
    report={'schema':'PPRIME_PHYSICAL_CLOSURE_DAY_MANIFEST_V1','status':'COMPLETE_RETAINED_PHYSICAL_EVIDENCE_REQUIRES_ROOT_D1_REVIEW' if complete else 'INCOMPLETE_PHYSICAL_EVIDENCE_HOLD',
        'job_id':str(proof['job_id']),'uid':1278,'node':req['node'],'endpoint':'202.38.247.57:22','actual_parent_only_no_child_jobs':True,
        'plan_reference':C.Q.pin(a.plan),'startup_proof_reference':C.Q.pin(a.startup_proof),'producer_root_review_reference':plan['producer_root_review_reference'],
        'pure_boundary_references':gate,'resource_observation_reference':observation,'budget':budget.report() if budget else None,
        'sections':sections,'closed_owned_output_references_before_manifest':list(store.references),
        'errors':errors,'forbidden_native_call_attempts':attempts,'native_initialize_or_invoke_calls':0,
        'new_QM_UFF_calls':0,'once_writes':0,'old15FAIL_and_old72_FAILED_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD',
        'new_precision_execution_permission':False,'D1_jointly_frozen':False,'original_tolerances_masks_and_return_states_changed':False,
        'quality_FAIL_UNKNOWN_and_Root_not_yet_adopted_are_separate_axes':True,'finite_difference_gradient_validation':'NOT_MEASURED'}
    store.json(out/'manifest.json',report,failure=True)
    C.need(sum(p.stat().st_size for p in out.rglob('*') if p.is_file())<=plan['output_cap_bytes'],'ACTUAL_WHOLE_OUTPUT_CAP')
    print({'status':report['status'],'manifest':str(out/'manifest.json'),'new_QM_calls':0});return 0 if complete else 3
if __name__=='__main__':raise SystemExit(main())
