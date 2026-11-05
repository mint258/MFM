"""Guarded original-reader input preparation/build/merge/full readback, zero QM."""
from __future__ import annotations
import argparse,io,json,os,pathlib,time,traceback,unittest
from . import contract as C,io as I,prepare as P,build as B,verify as V,children as H


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT3_NEW_INPUT_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    ref=C.Q.write_new(out/'source3.json',{'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
        'before_DATA_and_resource_observer':True,'synthetic_source_only':True,'temporary_directories_created':0})
    C.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_BEFORE_ANY_DATA')
    return ref


def guard(path,plan,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    C.need(plan['schema']=='D5_INPUT_BUILDER_PLAN_V1','EXACT_BUILDER_PLAN');C.limits(plan)
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)]
    proof=require_startup(proof_path,expected_scope_key='d5_inputs_builder_'+plan['mode']+'_v1',expected_scope_parameters=C.parameters(plan),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',
        required_references=[C.Q.pin(path),plan['resource_authority_reference'],plan['cost_decision_reference'],plan['quota_reuse_reference']])
    req=proof['request'];C.need(req['cpus']==16 and req['pilot'] is False and req['node']=='compute-0-13'
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['wall_seconds']==plan['wall_seconds']
        and req['estimated_peak_output_bytes']==plan['output_cap_bytes'] and req['data_references']==plan['data_references']
        and not req.get('deferred_authority_references'),'EXACT_ORIGINAL_PROVIDER_CPU13_NO_MEM_FINITE_DATA_AND_CAP')
    for ref in plan['source_references']:C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'EXACT_SOURCE_AND_SMALL_PARENT_PINS')
    from .metadata import resources
    resources(plan);result=C.inputs(plan);C.need(result[3]==plan['data_references'],'EXACT_ACTUAL_PARENT_DATA_SET')
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ORIGINAL_COST_AND_QUALITY_AUTHORITY')
    return proof,result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True)
    p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.Q.load(a.plan);proof,parents=guard(a.plan,plan,a.startup_proof);common,formal,hof,_,_,actual=parents
    out=I.R.literal(plan['output_directory']);C.need(C.OUTPUT in out.parents and not out.exists(),'FRESH_OWN_BUILDER_OUTPUT')
    out.mkdir(parents=True,mode=0o700)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['SQLITE_TMPDIR']=str(out/'sql_tmp');(out/'sql_tmp').mkdir(mode=0o700)
    start=time.monotonic();gate=observation=None;budget=None;result={};error=None
    try:
        gate=fixtures(out)
        I.OBS.start_observer(proof,{'resource_evidence_output':str(out/'resources'),'resource_evidence_local_cap_bytes':512<<20,
            'memavailable_soft_floor_bytes':4<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':plan['output_cap_bytes']})
        budget=I.Budget(plan,proof,out);budget.check()
        if plan['mode']=='prepare':result=P.run(plan,common,formal,hof,out,budget,proof['job_id'])
        elif plan['mode']=='base':result=B.run(plan,C.meta(plan['prepared_range_reference']),out,budget)
        elif plan['mode']=='merge':result=V.merge(plan,actual,out,budget)
        elif plan['mode']=='verify':result=V.run(plan,actual[0],common,out,budget)
        else:result=H.run(plan,actual[0],out,budget)
        budget.check()
        for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'ALL_SOURCE_AND_SMALL_AUTHORITY_BYTES_STABLE_AFTER_DATA')
    except BaseException as exc:
        error={'type':type(exc).__name__,'code':'INCOMPLETE_BUILDER_RETAINED_EVIDENCE_UNKNOWN_NOT_CHEMICAL_EXCLUSION'}
        try:
            raw=B.encode({'error':str(exc),'traceback':traceback.format_exc(),'original_source_or_labels_modified':False})
            path=out/'stage_failure.lossless.json'
            with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        except BaseException:pass
    finally:
        if budget is not None:
            try:budget.finish()
            except BaseException as exc:error=error or {'type':type(exc).__name__,'code':'QUOTA_THREAD_NOT_CLOSED'}
        if I.OBS.MONITOR is not None:
            try:I.OBS.MONITOR.finish();observation=C.Q.pin(out/'resources/closure.json')
            except BaseException as exc:error=error or {'type':type(exc).__name__,'code':'RESOURCE_CLOSURE_NOT_CLOSED'}
    ok=error is None and observation is not None and not I.OBS.stop_requested() and result.get('held_molecules')==0
    if budget is not None:
        try:C.need(I.R.used(out)+(512<<20)<plan['output_cap_bytes'],'ACTUAL_WHOLE_CAP_INCLUDING_METADATA_AND_RESOURCE_EVIDENCE')
        except BaseException as exc:ok=False;error=error or {'type':type(exc).__name__,'code':'WHOLE_STAGE_OUTPUT_CAP'}
    receipt={'schema':'D5_INPUT_BUILDER_STAGE_RECEIPT_V1',
        'status':'COMPLETE_TECHNICAL_STAGE_REQUIRES_ROOT_REVIEW' if ok else 'INCOMPLETE_BUILDER_UNKNOWN_HOLD',
        'mode':plan['mode'],'purpose':plan['purpose'],'job_id':str(proof['job_id']),'node':proof['request']['node'],'uid':1278,
        'plan_reference':C.Q.pin(a.plan),'source3_reference':gate,'resource_observation_reference':observation,'error':error,
        'held_molecules':None,**result,'resource_summary':budget.receipt() if budget is not None else None,
        'ordinary_counts_or_original_labels_modified':False,'N1_extras_as_ordinary_or_child':False,
        'D5_jointly_frozen':False,'QM_or_UFF_authorized_or_run':False,'source_and_actual_C0_not_physical_frame_acceptance':True,
        'elapsed_seconds':time.monotonic()-start}
    C.Q.write_new(out/'receipt.json',receipt)
    print(json.dumps({'status':receipt['status'],'receipt':str(out/'receipt.json'),'new_QM_UFF_calls':0}))
    return 0 if ok else 3
if __name__=='__main__':raise SystemExit(main())
