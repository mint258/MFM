"""Root-admitted ordinary D5 materialize/readback; never submits or publishes."""
from __future__ import annotations
import argparse,io,json,os,time,traceback,unittest
from pathlib import Path
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as O
from . import contract as C,resources as R,produce,readback


def fixtures(out):
    from .test_boundaries import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT3_NEW_SOURCE_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    value={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
        'before_DATA_and_monitor':True,'temporary_directories_created':0}
    ref=C.Q.write_new(out/'source3.json',value)
    C.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_NO_SKIP_BEFORE_DATA')
    return ref


def guard(plan_path,plan,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    mode=plan['mode'];C.need(plan['schema']=='D5_ORDINARY_CPU_PLAN_V1' and plan['scope_parameters']==C.parameters(mode,plan['seed'])
        and plan['wall_seconds']==C.WALL[mode] and plan['output_cap_bytes']==C.CAP[mode],'EXACT_BOUNDED_ORDINARY_D5_PLAN')
    proof=require_startup(proof_path,expected_scope_key='d5_ordinary_'+mode+'_cpu_v1',expected_scope_parameters=plan['scope_parameters'],
        expected_execution_argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(plan_path),'--startup-proof',str(proof_path)],
        expected_source=__file__,expected_kind='analysis',required_references=[C.Q.pin(plan_path),plan['resource_authority_reference'],plan['cost_decision_reference']])
    req=proof['request'];C.need(req['node']=='compute-0-13' and req['cpus']==16 and req['pilot'] is False
        and req['wall_seconds']==C.WALL[mode] and req['estimated_peak_output_bytes']==C.CAP[mode]
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and not req.get('deferred_authority_references')
        and req['data_references']==plan['data_references'],'ACTUAL_CPU13_16_NO_MEM_EXACT_LOCATORS')
    for ref in plan['source_references']:C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'PINNED_OLD_NEW_AND_PARENT_SOURCES')
    C.original_source_check();result=C.inputs(plan);C.need(result[3]==plan['data_references'],'NO_UNDECLARED_OR_FUTURE_DATA')
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_QUALITY_AND_COST_AUTHORITY')
    return proof,result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True);a=p.parse_args()
    plan=C.Q.load(a.plan);proof,inputs=guard(a.plan,plan,a.startup_proof);_,tables,columns,data,_,parent=inputs
    out=R.literal(plan['output_directory']);C.need(C.ROOT/'artifacts/labels/source_status_v1/d5_materialize_cpu_v1' in out.parents
        and not out.exists(),'FRESH_OWN_D5_OUTPUT');out.mkdir(parents=True,mode=0o700)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']='';os.environ['SQLITE_TMPDIR']=str(out/'sqlite_tmp');(out/'sqlite_tmp').mkdir(mode=0o700)
    start=time.monotonic();gate=observation=budget=None;error=None;result={};frames={}
    try:
        gate=fixtures(out)
        O.start_observer(proof,{'resource_evidence_output':str(out/'resources'),'resource_evidence_local_cap_bytes':32<<20,
            'memavailable_soft_floor_bytes':4<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':plan['output_cap_bytes']})
        live=dict(plan,_startup_proof_path=str(a.startup_proof));budget=R.Budget(live,proof,out)
        for ref in data:budget.check();frames[ref['path']]=R.verify_data(ref)
        if plan['mode']=='materialize':result=produce.run(live,tables,columns,frames,out,budget)
        else:result=readback.run(live,parent,out,budget)
        budget.check(force=True)
        for ref in data:R.unchanged(ref,frames[ref['path']])
        for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'OLD_NEW_AND_PARENT_SOURCE_BYTES_STABLE')
        C.original_source_check()
    except BaseException as exc:
        error={'type':type(exc).__name__,'code':'D5_INCOMPLETE_SEE_RETAINED_FAILURE_DATA'}
        try:
            raw=(json.dumps({'error':str(exc),'traceback':traceback.format_exc(),'original_inputs_untouched':True},ensure_ascii=True)+'\n').encode()
            C.need(R.used(out)+len(raw)+(64<<20)<plan['output_cap_bytes'],'FAILURE_DATA_WITHIN_ADMIN_RESERVE')
            with (out/'failure.DATA.json').open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        except BaseException:pass
    finally:
        if budget is not None:
            try:budget.finish()
            except BaseException as exc:error=error or {'type':type(exc).__name__,'code':'QUOTA_OBSERVER_NOT_CLOSED'}
        if O.MONITOR is not None:
            try:O.MONITOR.finish();observation=C.Q.pin(out/'resources/closure.json')
            except BaseException as exc:error=error or {'type':type(exc).__name__,'code':'RESOURCE_OBSERVATION_INCOMPLETE'}
    ok=error is None and observation is not None and not O.stop_requested()
    status=('ORDINARY_D5_LISTS_WRITTEN_READBACK_REQUIRED' if plan['mode']=='materialize' else 'ORDINARY_D5_FULL_READBACK_OBSERVED_ROOT_PUBLICATION_PENDING') if ok else 'INCOMPLETE_ORDINARY_D5_HOLD'
    report={'schema':'D5_CPU_LISTS_RECEIPT_V1','status':status,'mode':plan['mode'],'job_id':str(proof['job_id']),
        'node':proof['request']['node'],'plan_reference':C.Q.pin(a.plan),'startup_proof_reference':C.Q.pin(a.startup_proof),
        'source3_reference':gate,'resource_observation_reference':observation,'error':error,**result,
        'final_input_release_reference':plan['final_input_release_reference'],'resource_summary':budget.receipt() if budget else None,
        'all_declared_DATA_whole_SHA_verified':len(frames),'all_original_DATA_and_source_bytes_unchanged':ok,
        'D5_jointly_frozen':False,'D3_label_export_accepted':False,'VAL_Model_loader_accepted':False,
        'new_QM_UFF_calls':0,'Pprime_values_substituted_or_geometries_generated':False,'forced_signals_sent':False,
        'elapsed_seconds':time.monotonic()-start}
    C.Q.write_new(out/'receipt.json',report)
    C.need(R.used(out)+(32<<20)<=plan['output_cap_bytes'],'ACTUAL_WHOLE_FINAL_OUTPUT_AND_MONITOR_RESERVE')
    print(json.dumps({'status':status,'receipt':str(out/'receipt.json'),'new_QM_UFF_calls':0}))
    return 0 if ok else 3
if __name__=='__main__':raise SystemExit(main())
