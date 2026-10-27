"""Finite retained-B input locator/condition summary producers, zero QM/UFF."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,hashlib,io,json,os,pathlib,sys,tempfile,threading,time,traceback,unittest
from workflows.data_v1_final.export.native_body_frame32_v1 import observe as O,reader as D
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import resource_runtime as R
from . import contract as C,reader as I,analysis as A


def fixtures(out):
    from .test_v1 import Boundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Boundaries);C.need(suite.countTestCases()==3,'EXACT3_NATIVE_SUMMARY_BOUNDARIES')
    stream=io.StringIO();r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    receipt={'tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skips':len(r.skipped),
        'expected_failures':len(r.expectedFailures),'unexpected_successes':len(r.unexpectedSuccesses),'transcript':stream.getvalue(),
        'before_DATA_and_resource_observer':True,'temporary_directories_created':0}
    ref=C.Q.write_new(out/'source3.json',receipt)
    C.need(r.testsRun==3 and r.wasSuccessful() and not(r.skipped or r.expectedFailures or r.unexpectedSuccesses),'SOURCE3_BEFORE_ANY_BODY')
    return ref


def guard(path,plan,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    mode=plan['mode'];C.need(plan['schema']=='NATIVE_FRAME_SUMMARY32_PLAN_V1' and plan['scope_parameters']==C.parameters(mode)
        and plan['wall_seconds']==C.WALL[mode] and plan['output_cap_bytes']==C.CAP[mode],'EXACT_FINITE_SUMMARY_PLAN')
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(path),'--startup-proof',str(proof_path)]
    proof=require_startup(proof_path,expected_scope_key=C.scope(mode),expected_scope_parameters=C.parameters(mode),
        expected_execution_argv=argv,expected_source=__file__,expected_kind='analysis',
        required_references=[C.Q.pin(path),plan['resource_authority_reference'],plan['cost_decision_reference']])
    req=proof['request'];C.need(req['cpus']==16 and req['pilot'] is False and req['wall_seconds']==C.WALL[mode]
        and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['estimated_peak_output_bytes']==C.CAP[mode]
        and req['data_references']==plan['data_references'] and not req.get('deferred_authority_references'),'EXACT16_NO_MEM_FINITE_DECLARED_DATA')
    for ref in plan['source_references']:C.need(ref in req['source_references'] and C.Q.pin(ref['path'])==ref,'EXACT_SOURCE_CONTEXT_AND_PARENT_PINS')
    result=C.derive(plan);C.need(result[4]==plan['data_references'],'ONLY_ACTUAL_CLOSED_INPUT_LOCATORS')
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_QUALITY_COST_REPORT_CONTINUE')
    return proof,result


def produce(plan,body,bodyplan,rows,prior,out,check,write,scratch):
    mode=plan['mode'];refs=plan['data_references'];barrier=threading.Barrier(16)
    protocol=C.meta(bodyplan['protocol_reference'])
    prepared,_,_,_,_=C.B.derivation(bodyplan)
    registry=C.meta(prepared['input_authority_references']['registry'])
    locators=rows if mode=='prepare' else prior['locators']
    def worker(index):
        barrier.wait(timeout=60);result=[];objects=None;archive=None
        if mode=='summary':objects=O.originals(index);archive=O.module('_native_summary_archive_'+str(index),C.B.A.ARCHIVE)
        for row in locators[index::16]:
            check()
            if mode=='prepare':result.append(I.prepare_one(row,refs,check));continue
            position=row['position']
            try:
                value,inputref=I.evidence(row,refs,check);C.need(inputref==row['input_reference'] and value['key']==row['key'],'SAME_ACTUAL_PREPARED_KEY_INPUT_AUTHORITY')
                raw=I.read(row['raw_reference'],refs,check,C.B.RAW_CAP);rawfiles,rawmanifest=archive.unbundle(raw)
                C.need(rawmanifest==value['original_raw_metadata']['output_file_manifest'],'ORIGINAL_COMPLETE_OUTPUT_MEMBER_MANIFEST_SHA')
                encoded=I.read(row['input_reference'],refs,check,8<<20);inputfiles,inputmanifest=archive.unbundle(encoded)
                C.need(hashlib.sha256(encoded).hexdigest()==value['original_raw_metadata']['input_bundle_sha256'],'ACTUAL_RECONSTRUCTED_INPUT_WHOLE_SHA_EQUALS_ORIGINAL')
                for f in [*rawfiles,*inputfiles]:
                    p=pathlib.PurePosixPath(f['name']);C.need(p.name==str(p) and f['byte_count']<=C.B.MEMBER_CAP,'SAFE_BOUNDED_COMPLETE_MEMBER')
                observed=A.examine(value,rawfiles,inputfiles,objects,registry,protocol,scratch)
                report={'schema':'NATIVE_FRAME32_PER_KEY_SUMMARY_DATA_V1','position':position,
                    'retained_B_evidence_reference':row['evidence_reference'],'retained_B_raw_reference':row['raw_reference'],
                    'retained_B_input_reference':row['input_reference'],**observed}
                ref=write(out/('key_%04d.lossless.json'%position),D.scientific_bytes(report))
                result.append({'position':position,'calc_type':row['calc_type'],'state':'COMPLETE_DESCRIPTIVE_NATIVE_EVIDENCE_PHYSICAL_ACCEPTANCE_PENDING',
                    'scientific_DATA_reference':ref,'parser_exact':observed['original_parser_and_projection_exact_to_B'],
                    'input_binding_exact':True,'r73_state':observed['r73']['state'],'r73_entries':observed['r73'].get('native_entries_count',0),
                    'r73_onsite_entries':observed['r73'].get('same_atom_entries',0),'r73_duplicates':observed['r73'].get('duplicate_native_keys_preserved',0),
                    'r674_state':observed['r674']['status'],'r674_native_decimal_trace_zero':observed['r674'].get('trace_observation',{}).get('native_decimal_trace_exactly_zero'),
                    'geometry_state':observed['geometry']['state'],'direct_coordinates_exact':observed['geometry'].get('float64_coordinates_exactly_equal'),
                    'unit_sign_property_axis_PASS':False})
            except Exception as exc:
                ref=write(out/('key_%04d.failure.lossless.json'%position),D.scientific_bytes({'position':position,'key':row['key'],
                    'original_retained_B_locators':row,'error_type':type(exc).__name__,'error':str(exc),'traceback':traceback.format_exc(),
                    'state':'UNKNOWN_HOLD_NOT_LABEL_FAILURE','original_scientific_DATA_retained':True}),failure=True)
                result.append({'position':position,'calc_type':row['calc_type'],'state':'UNKNOWN_HOLD','failure_DATA_reference':ref})
        return {'native_thread_id':threading.get_native_id(),'rows':result}
    with cf.ThreadPoolExecutor(max_workers=16) as pool:reports=list(pool.map(worker,range(16)))
    C.need(len({r['native_thread_id'] for r in reports})==16,'ACTUAL16_RETAINED_EVIDENCE_WORKER_THREADS')
    combined=sorted([r for w in reports for r in w['rows']],key=lambda r:r['position'])
    C.need([r['position'] for r in combined]==list(range(384)),'COMPLETE_FIXED384_KEY_MATRIX')
    if mode=='prepare':return {'locators':combined,'input_bundles_opened':0,'evidence_DATA_files_SHA_verified':384,
        'worker_thread_ids':[r['native_thread_id'] for r in reports]}
    counts=[]
    for calc in C.CALCS:
        items=[r for r in combined if r['calc_type']==calc];C.need(len(items)==32,'EXACT32_PER_CONDITION')
        counts.append({'condition':calc,'records':32,'held_keys':sum(r['state']=='UNKNOWN_HOLD' for r in items),
            'original_parser_exact_records':sum(r.get('parser_exact',False) for r in items),
            'actual_original_input_binding_exact_records':sum(r.get('input_binding_exact',False) for r in items),
            'r73_status_counts':dict(collections.Counter(r.get('r73_state','HOLD') for r in items)),
            'r73_native_entries_observed':sum(r.get('r73_entries',0) for r in items),
            'r73_onsite_entries_observed':sum(r.get('r73_onsite_entries',0) for r in items),
            'r73_duplicate_keys_preserved':sum(r.get('r73_duplicates',0) for r in items),
            'r674_status_counts':dict(collections.Counter(r.get('r674_state','HOLD') for r in items)),
            'r674_native_decimal_trace_exactly_zero_records':sum(r.get('r674_native_decimal_trace_zero') is True for r in items),
            'geometry_status_counts':dict(collections.Counter(r.get('geometry_state','HOLD') for r in items)),
            'printed_coordinate_values_float64_exact_records':sum(r.get('direct_coordinates_exact') is True for r in items),
            'native_unit_sign_property_axes_accepted':False})
    return {'per_condition_counts':counts,'per_key_scientific_DATA_references':combined,
        'completed_key_observations':384,'held_keys':sum(r['state']=='UNKNOWN_HOLD' for r in combined),
        'worker_thread_ids':[r['native_thread_id'] for r in reports],
        'basis_indices_are_original_print_slots_not_AO_indices':True,'full20k_native_audit_completed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True);a=p.parse_args()
    plan=C.Q.load(a.plan);proof,parents=guard(a.plan,plan,a.startup_proof);body,bodyplan,rows,prior,_,_=parents;mode=plan['mode']
    out=pathlib.Path(plan['output_directory']);allowed=C.ROOT/'artifacts/labels/source_status_v1/native_frame_summary32_v1'
    C.need(out.is_absolute() and allowed in out.parents and not out.exists() and '..' not in out.parts
        and not any(s.is_symlink() for s in (out,*out.parents)),'FRESH_LITERAL_SUMMARY_OUTPUT');out.mkdir(parents=True,mode=0o700)
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    for path in (C.B.WP5,C.B.VECTOR):
        if str(path) not in sys.path:sys.path.insert(0,str(path))
    start=time.monotonic();gate=observation=None;error=None;result={};lock=threading.Lock();written=0
    reserve=(32<<20) if mode=='prepare' else (160<<20)
    def check():
        R.soft_worker_rss(3<<30)
        if time.monotonic()-start>=C.WALL[mode]-180:R.mark_stop('NATIVE_SUMMARY_FINITE_WALL_RESERVE',{'elapsed_seconds':time.monotonic()-start})
        C.need(not R.stop_requested(),'NATIVE_SUMMARY_STOP_NEW_WORK_NATURAL_DRAIN')
    def write(path,data,*,failure=False):
        nonlocal written
        with lock:
            if not failure:check()
            C.need(written+len(data)+reserve<=C.CAP[mode],'WHOLE_SUMMARY_OUTPUT_AND_TMP_DRAIN_CAP');written+=len(data)
        return D.bytes_data(path,data)
    try:
        gate=fixtures(out)
        R.start_observer(proof,{'resource_evidence_output':str(out/'resources'),'resource_evidence_local_cap_bytes':16<<20,
            'memavailable_soft_floor_bytes':4<<30,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP[mode]})
        check()
        if mode=='prepare':result=produce(plan,body,bodyplan,rows,prior,out,check,write,None)
        else:
            with tempfile.TemporaryDirectory(prefix='native_summary32_'+str(os.getuid())+'_'+str(proof['job_id'])+'_',dir='/tmp') as scratch:
                result=produce(plan,body,bodyplan,rows,prior,out,check,write,scratch)
        check()
        for ref in plan['source_references']:C.need(C.Q.pin(ref['path'])==ref,'ALL_ORIGINAL_NEW_AND_OFFICIAL_SOURCE_BYTES_STABLE')
    except BaseException as exc:
        error={'type':type(exc).__name__,'code':'INCOMPLETE_RETAINED_NATIVE_SUMMARY_SEE_FAILURE_DATA'}
        try:write(out/'stage_failure.lossless.json',D.scientific_bytes({'error':str(exc),'traceback':traceback.format_exc()}),failure=True)
        except Exception:pass
    finally:
        if R.MONITOR is not None:
            try:R.MONITOR.finish();observation=C.Q.pin(out/'resources/closure.json')
            except BaseException as exc:error=error or {'type':type(exc).__name__,'code':'RESOURCE_CLOSURE_INCOMPLETE'}
    ok=error is None and observation is not None and not R.stop_requested()
    if mode=='summary':ok=ok and result.get('completed_key_observations')==384 and result.get('held_keys')==0
    report={'schema':'NATIVE_FRAME_SUMMARY32_INPUT_LOCATORS_V1' if mode=='prepare' else 'NATIVE_FRAME_SUMMARY32_OBSERVATIONS_V1',
        'status':('EXACT384_RETAINED_INPUT_BUNDLE_LOCATORS_NOT_OPENED' if mode=='prepare' else
            'EXACT384_NATIVE_PARSER_INPUT_DOMAIN_STATISTICS_OBSERVED_PHYSICAL_D1_REVIEW_PENDING') if ok else 'INCOMPLETE_NATIVE_SUMMARY_UNKNOWN_HOLD',
        'mode':mode,'job_id':str(proof['job_id']),'plan_reference':C.Q.pin(a.plan),'body_closure_references':plan['body_closure_references'],
        'fixtures3_reference':gate,'resource_observation_reference':observation,'error':error,**result,
        'official_context_source_references':plan.get('official_context_references',[]),
        'official_source_pins_do_not_close_unit_charge_sign_or_property_axis_call_chain':True,
        'native_units_sign_property_axes_accepted':False,'D1_jointly_frozen':False,'new_QM_UFF_calls':0,
        'original_DATA_masks_tolerances_or_sources_modified':False,'normalization_or_full20k_completed':False,
        'elapsed_seconds':time.monotonic()-start}
    C.Q.write_new(out/'manifest.json',report)
    C.need(sum(p.stat().st_size for p in out.rglob('*') if p.is_file())+(16<<20)<=C.CAP[mode],'ACTUAL_WHOLE_SUMMARY_OUTPUT_CAP')
    print(json.dumps({'status':report['status'],'manifest':str(out/'manifest.json'),'new_QM_UFF_calls':0}))
    return 0 if ok else 3
if __name__=='__main__':raise SystemExit(main())
