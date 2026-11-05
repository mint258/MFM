"""Finite CPU-only actual3532/3538 native-body evidence, never a science runner."""
from __future__ import annotations
import argparse,concurrent.futures as cf,contextlib,hashlib,importlib.util,io,json,os,pathlib,sys,tempfile,threading,time,traceback,unittest
from workflows.data_v1_final.export.native_availability_v1 import reader as I
from . import contract as C,reader as D,observe as O


def fixtures(out):
    from workflows.data_v1_final.export.native_availability_v1.test_v1 import Boundaries as Original
    from .test_v1 import Boundaries as New
    loader=unittest.TestLoader();old=loader.loadTestsFromTestCase(Original);new=loader.loadTestsFromTestCase(New)
    C.need(old.countTestCases()==new.countTestCases()==3,'EXACT_ORIGINAL3_PLUS_NEW3')
    stream=io.StringIO();result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite([old,new]))
    receipt={'tests_run':result.testsRun,'original_methods':3,'new_methods':3,'failures':len(result.failures),
        'errors':len(result.errors),'skips':len(result.skipped),'expected_failures':len(result.expectedFailures),
        'unexpected_successes':len(result.unexpectedSuccesses),'transcript':stream.getvalue(),
        'before_resource_observer_and_DATA':True,'temporary_directories_created':0,'new_QM_calls':0,'new_UFF_calls':0}
    ref=C.Q.write_new(out/'fixtures6.json',receipt)
    C.need(result.testsRun==6 and result.wasSuccessful() and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses),
        'ORIGINAL3_AND_NEW3_MUST_PASS_BEFORE_DATA')
    return ref


def guard(path,plan,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    mode=plan['mode'];C.need(plan['schema']=='NATIVE_BODY_FRAME32_PLAN_V1' and plan['scope_parameters']==C.parameters(mode)
        and plan['wall_seconds']==C.WALLS[mode] and plan['output_cap_bytes']==C.CAPS[mode],'EXACT_FINITE_NATIVE_BODY_PLAN')
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)]
    proof=require_startup(proof_path,expected_scope_key=C.scope(mode),expected_scope_parameters=C.parameters(mode),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',
        required_references=[C.Q.pin(path),plan['resource_authority_reference'],plan['cost_decision_reference']])
    req=proof['request']
    C.need(req['cpus']==16 and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['pilot'] is False
        and req['wall_seconds']==C.WALLS[mode] and req['estimated_peak_output_bytes']==C.CAPS[mode]
        and req['data_references']==plan['data_references'] and not req.get('deferred_authority_references'),
        'EXACT16_NO_MEM_WALL_AND_DECLARED_DATA')
    for ref in plan['source_references']:
        C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'EXACT_NEW_AND_REUSED_SOURCES')
    prepared,probe,prior,data,extra=C.derivation(plan)
    protocolref,_=C.recipe_sources(prepared)
    C.need(data==plan['data_references'] and protocolref==plan['protocol_reference'],'ACTUAL_PARENTS_AND_PROTOCOL_REDERIVATION')
    cost=C.meta(plan['cost_decision_reference'])
    C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'QUALITY_UNCHANGED_COST_REPORT_CONTINUE')
    return proof,prepared,probe,prior


def body(plan,prepared,probe,prior,module,out,check,write,scratch):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    refs=plan['data_references'];locs=prior['geometry_locators'];byfile={}
    for loc in locs:byfile.setdefault(loc['base_reference']['path'],[]).append(loc)
    groups=list(byfile.values());barrier=threading.Barrier(16)
    def bases(index):
        barrier.wait(timeout=60);result={}
        for group in groups[index::16]:result.update(D.base_rows(group[0]['base_reference'],group,refs,check))
        return {'rows':result,'native_thread_id':threading.get_native_id()}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:base_reports=list(pool.map(bases,range(16)))
    C.need(len({r['native_thread_id'] for r in base_reports})==16,'ACTUAL16_BASE_WORKER_THREADS')
    base={}
    for r in base_reports:
        C.need(not set(base)&set(r['rows']),'NO_DUPLICATE_BASE_ACROSS_ORIGINAL_FILES');base.update(r['rows'])
    C.need(set(base)=={r['record_id'] for r in prepared['selected_records']},'COMPLETE_EXACT32_BASES')
    protocol=C.meta(plan['protocol_reference']);old_plan=C.meta(probe['plan_reference'])
    dicts=I.dictionaries(prepared['input_authority_references']['dictionary_manifest'],refs)
    key_positions={C.key(item):i for i,item in enumerate(prepared['execution_keys'])};archive_groups={}
    expected={r['record_id']:r for r in locs}
    for item in prepared['execution_keys']:archive_groups.setdefault(item['archive_reference']['path'],[]).append(item)
    archives=list(archive_groups.values());barrier=threading.Barrier(16)
    def worker(index):
        barrier.wait(timeout=60);original=O.originals(index);zstd=module.Zstd();rows=[];opens=closes=raw_read=raw_fetches=0;archive_reviews=[]
        try:
            for archive_index,items in enumerate(archives[index::16]):
                check();ref=items[0]['archive_reference'];db_opened=False
                try:
                    # One whole-file FD hash per unique archive, not per key/thread.
                    with D.archive(ref,refs,check,True) as db:
                        opens+=1;db_opened=True;header=I.archive_header(db,old_plan,dicts)
                        for item in items:
                            check();position=key_positions[C.key(item)];directory=out/('key_%04d'%position);directory.mkdir(mode=0o700)
                            rawref=None
                            try:
                                row,meta,observed=D.metadata(db,item,old_plan,dicts,zstd,header)
                                frozen=expected[item['record_id']]['execution_metadata'][item['calc_type']]
                                C.need(meta['file_group']==expected[item['record_id']]['file_group']
                                    and meta['source_payload_sha256']==expected[item['record_id']]['source_payload_sha256']
                                    and meta['source_reference']==expected[item['record_id']]['source_reference']
                                    and meta['input_file_sha256']==frozen['input_file_sha256']
                                    and meta['input_bundle_sha256']==frozen['input_bundle_sha256']
                                    and meta['reproduction_package_sha256']==frozen['reproduction_package_sha256']
                                    and row['raw_sha256'].lower()==frozen['raw_sha256'] and row['raw_bytes']==frozen['raw_bytes'],
                                    'BODY_MATCHES_ACTUAL_LOCATOR_PREPARATION_AND_ORIGINAL_RAW_METADATA')
                                D.raw_limits(row);raw_fetches+=1
                                raw,files=D.raw(db,item,row,meta,dicts[item['calc_type']]['data'],zstd,module.unbundle);raw_read+=1
                                rawref=write(directory/'original_raw.bundle',raw)
                                evidence,rendered=O.examine(files,base[item['record_id']],item,meta,protocol,original,module,scratch)
                                reconstruction,_=module.bundle([{'name':n,'data':b,'role':'input'} for n,b in sorted(rendered.items())])
                                inputref=write(directory/'hash_verified_reconstructed_input.bundle',reconstruction)
                                result={'key':{k:item[k] for k in ('record_id','calc_type','execution_id')},'owner':item['owner'],
                                    'original_archive_reference':ref,'original_raw_bundle_reference':rawref,
                                    'hash_reconstructed_input_DATA_reference':inputref,'original_raw_metadata':meta,
                                    'native_evidence':evidence,'original_source_status':row['source_status'],'original_scope_status':row['scope_status'],
                                    'new_QM_calls':0,'new_UFF_calls':0,'D1_jointly_frozen':False,'final_masks_created':False}
                                dataref=write(directory/'evidence.lossless.json',D.scientific_bytes(result))
                                rows.append({'position':position,'state':'OBSERVED_NATIVE_EVIDENCE_PHYSICAL_CONVENTIONS_PENDING',
                                    'raw_reference':rawref,'evidence_reference':dataref,
                                    'input_byte_binding_verified':True,'r73_state':evidence['r73']['status'],
                                    'r674_state':evidence['r674']['status'],'geometry_state':evidence['geometry_frame']['status']})
                            except Exception as exc:
                                failure={'key':{k:item[k] for k in ('record_id','calc_type','execution_id')},'owner':item['owner'],
                                    'original_archive_reference':ref,'retained_raw_reference':rawref,'error_type':type(exc).__name__,
                                    'error':str(exc),'traceback':traceback.format_exc(),'state':'UNKNOWN_HOLD_NOT_A_LABEL_MASK'}
                                failref=write(directory/'failure.lossless.json',D.scientific_bytes(failure),failure=True)
                                rows.append({'position':position,'state':'UNKNOWN_HOLD','raw_reference':rawref,'failure_DATA_reference':failref,
                                    'error_type':type(exc).__name__})
                    closes+=1
                    archive_reviews.append({'reference':ref,'current_whole_SHA_verified':True,
                        'closed_readonly_snapshot_and_full_file_FD':True,'stable_final_frame':list(I.frame(ref['path']))})
                except Exception as exc:
                    # Original immutable archive/failure evidence stays retained when a whole-SHA/open gate fails.
                    failref=write(out/('archive_%02d_%02d_failure.lossless.json'%(index,archive_index)),D.scientific_bytes({
                        'original_archive_reference':ref,'requested_keys':[list(C.key(i)) for i in items],
                        'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),
                        'state':'UNKNOWN_HOLD_ALL_KEYS_ORIGINAL_DATA_RETAINED'}),failure=True)
                    if db_opened:closes+=1
                    archive_reviews.append({'reference':ref,'state':'UNKNOWN_HOLD_NO_CLOSED_SOURCE_PROOF'})
                    completed={r['position'] for r in rows}
                    affected={key_positions[C.key(i)] for i in items}
                    for row in rows:
                        if row['position'] in affected:row.update(state='UNKNOWN_HOLD',archive_failure_DATA_reference=failref)
                    rows.extend({'position':key_positions[C.key(i)],'state':'UNKNOWN_HOLD','failure_DATA_reference':failref}
                        for i in items if key_positions[C.key(i)] not in completed)
        finally:zstd.close()
        return {'native_thread_id':threading.get_native_id(),'rows':rows,'sqlite_opens':opens,'sqlite_closes':closes,
            'raw_BLOB_fetch_attempts':raw_fetches,'raw_bundles_SHA_and_members_verified':raw_read,
            'archive_reviews':archive_reviews}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:reports=list(pool.map(worker,range(16)))
    C.need(len({r['native_thread_id'] for r in reports})==16,'ACTUAL16_NATIVE_BODY_THREADS')
    rows=sorted([r for w in reports for r in w['rows']],key=lambda r:r['position'])
    C.need([r['position'] for r in rows]==list(range(384)),'EXACT_COMPLETE384_POSITION_MATRIX_WITH_FAILURES_RETAINED')
    return {'record_evidence_references':rows,'completed_key_observations':len(rows),
        'observed_keys':sum(r['state'].startswith('OBSERVED_') for r in rows),'held_keys':sum(r['state']=='UNKNOWN_HOLD' for r in rows),
        'raw_BLOB_fetch_attempts':sum(r['raw_BLOB_fetch_attempts'] for r in reports),
        'raw_bundles_SHA_and_members_verified':sum(r['raw_bundles_SHA_and_members_verified'] for r in reports),
        'raw_archive_readback_proofs':[a for r in reports for a in r['archive_reviews']],
        'sqlite_opens':sum(r['sqlite_opens'] for r in reports),'sqlite_closes':sum(r['sqlite_closes'] for r in reports),
        'base_rows_materialized':len(base),'base_files_current_whole_SHA_verified':len(groups),
        'raw_worker_thread_ids':[r['native_thread_id'] for r in reports],
        'field_unknown_counts':{field:sum(r.get(field+'_state','').startswith('UNKNOWN') for r in rows)
            for field in ('r73','r674','geometry')},
        'physical_base_read_method':'bounded64 Arrow column batches; only exact32 rows materialized/diagnosed; not a claim of32 physical storage-row reads',
        'source_and_sign_and_axes_acceptance':'PENDING_ROOT_AND_MODEL_REVIEW_NOT_JOINTLY_SIGNED'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True)
    p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args();plan=C.Q.load(a.plan)
    proof,prepared,probe,prior=guard(a.plan,plan,a.startup_proof);mode=plan['mode'];out=pathlib.Path(plan['output_directory'])
    allowed=C.ROOT/'artifacts/labels/source_status_v1/native_body_frame32_v1'
    C.need(out.is_absolute() and allowed in out.parents and '..' not in out.parts and not out.exists()
        and not any(p.is_symlink() for p in (out,*out.parents)),'FRESH_LITERAL_NATIVE_EVIDENCE_OUTPUT')
    out.mkdir(parents=True,mode=0o700,exist_ok=False)
    for name in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    for path in (C.WP5,C.VECTOR):
        if str(path) not in sys.path:sys.path.insert(0,str(path))
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R
    started=time.monotonic();gate=observation=None;error=None;result={};budget_lock=threading.Lock();written=0
    reserve=(32<<20) if mode=='prepare' else C.SCRATCH_AND_INFLIGHT_RESERVE
    def check():
        R.soft_worker_rss(3<<30)
        if time.monotonic()-started>=C.WALLS[mode]-180:R.mark_stop('NATIVE32_FINITE_WALL_RESERVE',{'elapsed_seconds':time.monotonic()-started})
        C.need(not R.stop_requested(),'STOP_NEW_NATIVE_KEYS_NATURAL_DRAIN')
    def write(path,data,*,failure=False):
        nonlocal written
        with budget_lock:
            if not failure:check()
            reserved=(32<<20) if failure else reserve
            C.need(written+len(data)+reserved<=C.CAPS[mode],'WHOLE_OUTPUT_WITH_SCRATCH_AND_INFLIGHT_RESERVE')
            written+=len(data)
        return D.bytes_data(path,data)
    try:
        gate=fixtures(out)
        R.start_observer(proof,{'resource_evidence_output':str(out/'resources'),'resource_evidence_local_cap_bytes':16<<20,
            'memavailable_soft_floor_bytes':4<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAPS[mode]})
        check();module=O.module('_nb32_original_archive4',C.A.ARCHIVE)
        if mode=='prepare':
            from .prepare import discover
            result=discover(plan,prepared,C.meta(probe['plan_reference']),module,check)
        else:
            # Atomic fresh private scratch is created only after all6 fixtures and observer startup.
            with tempfile.TemporaryDirectory(prefix='nb32_'+str(os.getuid())+'_'+str(proof['job_id'])+'_',dir='/tmp') as scratch:
                result=body(plan,prepared,probe,prior,module,out,check,write,scratch)
        check()
        for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'ALL_ORIGINAL_AND_NEW_SOURCE_BYTES_STABLE_AFTER_RUN')
    except BaseException as exc:
        error={'type':type(exc).__name__,'code':'INCOMPLETE_NATIVE_EVIDENCE_SEE_FAILURE_DATA_NOT_LABEL_QC'}
        try:write(out/'stage_failure.lossless.json',D.scientific_bytes({'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc()}),failure=True)
        except Exception:pass
    finally:
        if R.MONITOR is not None:
            try:R.MONITOR.finish();observation=C.Q.pin(out/'resources/closure.json')
            except BaseException as exc:error=error or {'type':type(exc).__name__,'code':'RESOURCE_CLOSURE_INCOMPLETE'}
    ok=error is None and observation is not None and not R.stop_requested()
    if mode=='body':ok=ok and result.get('completed_key_observations')==384 and result.get('held_keys')==0
    manifest={'schema':'NATIVE_BODY_FRAME32_LOCATORS_V1' if mode=='prepare' else 'NATIVE_BODY_FRAME32_OBSERVATIONS_V1',
        'status':('EXACT_BASE_GEOMETRY_LOCATORS_NOT_OPENED' if mode=='prepare' else
            'FINITE_NATIVE_BODY_OBSERVED_PHYSICAL_CONVENTIONS_PENDING') if ok else 'INCOMPLETE_NATIVE_EVIDENCE_UNKNOWN_HOLD',
        'mode':mode,'job_id':str(proof['job_id']),'plan_reference':C.Q.pin(a.plan),
        'input_authority_references':plan['input_authority_references'],'source_data_references':plan['data_references'],
        'resource_observation_reference':observation,'fixtures6_reference':gate,'error':error,**result,
        'wall_seconds_observed':time.monotonic()-started,'new_QM_calls':0,'new_UFF_calls':0,
        'source_field_names_are_not_native_basis_or_frame_evidence':True,'native_physical_axes_verified':False,
        'D1_jointly_frozen':False,'final_masks_created':False,'normalization_completed':False,
        'candidate_release_authorized':False,
        'original_DATA_or_scientific_source_modified':False,'new_general_queue_or_QM_protocol':False}
    C.Q.write_new(out/'manifest.json',manifest)
    used=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    C.need(used+(16<<20)<=C.CAPS[mode],'FINAL_WHOLE_OUTPUT_AND_LOCAL_EVIDENCE_CAP')
    print(json.dumps({'status':manifest['status'],'manifest':str(out/'manifest.json'),'new_QM_calls':0,'new_UFF_calls':0}))
    return 0 if ok else 3
if __name__=='__main__':raise SystemExit(main())
