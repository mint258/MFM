"""Two finite CPU stages: declare raw archives, then inspect metadata only."""
from __future__ import annotations
import argparse,concurrent.futures as cf,importlib.util,io,json,os,pathlib,threading,time,traceback,unittest
from . import contract as C,reader as I


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT3_NEW_PURE_METHODS')
    text=io.StringIO();r=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    result={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),
        'transcript':text.getvalue(),'before_resource_observer_and_DATA':True,'temporary_directories_created':0}
    C.Q.write_new(out/'fixtures3.json',result)
    C.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'PURE3_BEFORE_RESOURCE_AND_DATA_PASS')
    return result


def guard(path,plan,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    mode=plan['mode'];params=C.parameters(mode)
    C.need(plan['schema']=='NATIVE_RAW_AVAILABILITY_PLAN_V1' and plan['scope_parameters']==params
        and plan['wall_seconds']==C.WALL and plan['output_cap_bytes']==C.CAP,'EXACT_FINITE_PLAN')
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)]
    proof=require_startup(proof_path,expected_scope_key=C.scope(mode),expected_scope_parameters=params,
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',
        required_references=[C.Q.pin(path),plan['resource_authority_reference'],plan['cost_decision_reference']])
    req=proof['request']
    C.need(req['cpus']==16 and req['pilot'] is False and req['wall_seconds']==C.WALL
        and req['estimated_peak_output_bytes']==C.CAP and req.get('data_references',[])==plan['data_references']
        and not req.get('deferred_authority_references'),'EXACT_DECLARED_FINITE_NO_MEM_STAGE')
    for ref in plan['source_references']:C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'ACTUAL_NEW_AND_REUSED_SOURCES')
    for ref in plan['input_authority_references'].values():C.meta(ref)
    if mode=='prepare':C.need(plan['data_references']==C.prepare_data(plan['input_authority_references']),'PREPARATION_DATA_EXACT')
    else:
        prior,_=C.closed_preparation(plan['preparation_closure_references'])
        C.need(plan['data_references']==C.expected_probe_data(prior)
            and plan['input_authority_references']==prior['input_authority_references'],'ONLY_CLOSED_PREDECLARED_RAW_AND_DICTIONARIES')
    cost=C.meta(plan['cost_decision_reference'])
    C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'QUALITY_AND_REPORT_CONTINUE_AUTHORITY')
    return proof


def probe(plan,out,check):
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R
    prior,_=C.closed_preparation(plan['preparation_closure_references']);keys=prior['execution_keys']
    dicts=I.dictionaries(plan['input_authority_references']['dictionary_manifest'],plan['data_references'])
    spec=importlib.util.spec_from_file_location('_native_availability_wp5_archive4',C.ARCHIVE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    barrier=threading.Barrier(16)
    def worker(index):
        barrier.wait(timeout=60);rows=[];errors=[];opened=closed=0;db=None;current=None;header=None;before=None;path=None
        zstd=module.Zstd();local=sorted(keys[index::16],key=lambda r:(r['archive_reference']['path'],r['record_id'],r['calc_type']))
        try:
            for item in local:
                try:
                    check()
                    ref=item['archive_reference']
                    if current!=ref:
                        if db is not None:
                            db.close();closed+=1;db=None;C.need(I.frame(path)==before,'ARCHIVE_CHANGED_AFTER_SNAPSHOT')
                        db,path,before=I.readonly(ref,plan['data_references']);opened+=1;current=ref
                        header=I.archive_header(db,plan,dicts)
                    rows.append(I.metadata_one(db,item,plan,dicts,zstd,header));check()
                except Exception as exc:
                    errors.append({'key':{k:item[k] for k in ('record_id','calc_type','execution_id')},
                        'error_type':type(exc).__name__,'error':str(exc),'state':'PENDING_NOT_A_LABEL_MASK'})
                    # A bad header/connection cannot be reused for later keys.
                    if db is not None:
                        db.close();closed+=1;db=None;current=None
                        C.need(I.frame(path)==before,'ARCHIVE_CHANGED_ON_ERROR')
                    if R.stop_requested():break
        finally:
            if db is not None:
                db.close();closed+=1;C.need(I.frame(path)==before,'ARCHIVE_CHANGED_AFTER_FINAL_SNAPSHOT')
            zstd.close()
        report={'worker_index':index,'pid':os.getpid(),'native_thread_id':threading.get_native_id(),
            'rows':rows,'errors':errors,'sqlite_opens':opened,'sqlite_closes':closed,'raw_frame_fetched':False,
            'parsed_or_wire_BLOB_fetched':False,'dictionary_and_metadata_only':True,'new_QM_calls':0,'native_tokens_and_frame':'PENDING'}
        C.need(len((json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())<C.METADATA_CAP,'FULL_WORKER_REPORT_CAP_NO_TRUNCATION')
        reference=C.Q.write_new(out/('worker_%02d.json'%index),report)
        return {'report':reference,'native_thread_id':report['native_thread_id'],'rows':len(rows),'errors':len(errors),
            'sqlite_opens':opened,'sqlite_closes':closed,'missing_raw_keys':sum(r['status']=='RAW_KEY_MISSING' for r in rows)}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:reports=list(pool.map(worker,range(16)))
    C.need(len({r['native_thread_id'] for r in reports})==16,'ACTUAL16_METADATA_WORKER_THREADS')
    C.need(sum(r['sqlite_opens'] for r in reports)==sum(r['sqlite_closes'] for r in reports),'ALL_READONLY_HANDLES_CLOSED')
    registry=C.meta(plan['input_authority_references']['registry'])
    fields=[{k:f.get(k) for k in ('field_key','registry_id','task','source_path','component','status','unit','geometry_context')}
        for f in registry['fields'] if f['task'] in C.CALCS]
    return {'worker_reports':reports,'completed_key_observations':sum(r['rows'] for r in reports),
        'key_errors':sum(r['errors'] for r in reports),'missing_raw_keys':sum(r['missing_raw_keys'] for r in reports),
        'sqlite_opens':sum(r['sqlite_opens'] for r in reports),'sqlite_closes':sum(r['sqlite_closes'] for r in reports),
        'field_condition_matrix_definition':fields,'field_matrix_state':'DECLARED_SOURCE_FIELDS_ONLY_NATIVE_TOKENS_NOT_READ',
        'archive_whole_SHA_state':'INHERITED_CLOSED_PRODUCER_SHA_STABLE_FSTAT_NOT_REHASHED_THIS_PASS',
        'scientific_BLOBs_fetched':0,'input_bodies_read':0}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True)
    p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.Q.load(a.plan);proof=guard(a.plan,plan,a.startup_proof)
    out=pathlib.Path(plan['output_directory']);allowed=C.ROOT/'artifacts/labels/source_status_v1/native_availability_v1'
    C.need(out.is_absolute() and '..' not in out.parts and allowed in out.parents
        and not any(v.is_symlink() for v in (out,*out.parents)) and not out.exists(),'FRESH_SCOPED_OUTPUT')
    out.mkdir(parents=True,exist_ok=False,mode=0o700)
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[name]='1'
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R
    start=time.monotonic();gate=None;observation=None;result={};error=None
    def check():
        R.soft_worker_rss(3<<30)
        if time.monotonic()-start>=C.WALL-180:R.mark_stop('NATIVE_METADATA_WALL_RESERVE',{'seconds':time.monotonic()-start})
        C.need(not R.stop_requested(),'RESOURCE_STOP_NEW_METADATA_KEYS_NATURAL_DRAIN')
    try:
        gate=fixtures(out)
        # Fixtures use only in-memory SQLite and are fully closed before this creates its atomic node-local directory.
        R.start_observer(proof,{'resource_evidence_output':str(out/'resources'),
            'resource_evidence_local_cap_bytes':16<<20,'memavailable_soft_floor_bytes':4<<30,
            'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP})
        check()
        if plan['mode']=='prepare':
            from .prepare import discover
            result=discover(plan,check)
        else:result=probe(plan,out,check)
        check()
    except BaseException as exc:error={'type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()}
    finally:
        if R.MONITOR is not None:
            try:
                R.MONITOR.finish();observation=C.Q.pin(out/'resources/closure.json')
            except BaseException as exc:error=error or {'type':type(exc).__name__,'error':str(exc),'stage':'resource_export'}
    ok=error is None and observation is not None and not R.stop_requested()
    if plan['mode']=='probe':ok=ok and result.get('completed_key_observations')==384 and result.get('key_errors')==0
    report={'schema':'NATIVE_RAW_LOCATORS_PREPARATION_V1' if plan['mode']=='prepare' else 'NATIVE_RAW_METADATA_AVAILABILITY_V1',
        'status':('EXACT_NATIVE_ARCHIVE_LOCATORS_PREPARED_NOT_OPENED' if plan['mode']=='prepare' else
            'FINITE_NATIVE_METADATA_OBSERVED_FRAME_AND_VALUES_PENDING') if ok else 'INCOMPLETE_NATIVE_METADATA_NOT_A_SCIENTIFIC_FAILURE',
        'job_id':str(proof['job_id']),'mode':plan['mode'],'plan_reference':C.Q.pin(a.plan),
        'input_authority_references':plan['input_authority_references'],'source_data_references':plan['data_references'],
        'resource_observation_reference':observation,'fixtures':gate,'error':error,**result,
        'wall_seconds_observed':time.monotonic()-start,'new_QM_calls':0,'new_UFF_calls':0,
        'input_body_state':'HASH_ONLY_NOT_SAVED','native_tokens_verified':False,'native_frame_verified':False,
        'labels_masks_or_original_data_modified':False,'D1_jointly_frozen':False,'normalization_completed':False}
    C.need(len((json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode())<C.METADATA_CAP,'FULL_MANIFEST_METADATA_CAP')
    C.Q.write_new(out/'manifest.json',report)
    used=sum(v.stat().st_size for v in out.rglob('*') if v.is_file())
    # At most16 x2MiB reports +2MiB manifest +16MiB global/local observer copies <128MiB.
    C.need(used+(16<<20)<=C.CAP,'WHOLE_OUTPUT_INCLUDING_LOCAL_EVIDENCE_COPY')
    print(json.dumps({'status':report['status'],'manifest':str(out/'manifest.json'),'new_QM_calls':0,'new_UFF_calls':0}))
    return 0 if ok else 3
if __name__=='__main__':raise SystemExit(main())