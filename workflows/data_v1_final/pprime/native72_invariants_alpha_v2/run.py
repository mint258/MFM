"""One finite, guarded Alpha CPU analysis of two already-written reports."""
from __future__ import annotations
import argparse,concurrent.futures as cf,contextlib,hashlib,importlib.util,io,json,multiprocessing as mp,os,pathlib,socket,stat,sys,time,traceback,unittest
from secondary_cpu_queue_v1 import common as Q
from . import contract as C
from .guard import require_startup


def read_body(reference):
    path=Q.literal(reference['path']);limit=reference['bytes']
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());Q.need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_size==limit,'EXACT_OWNED_EXISTING_BODY_SIZE_REQUIRED')
        body=stream.read(limit+1);after=os.fstat(stream.fileno())
    linked=path.stat()
    Q.need(len(body)==limit and hashlib.sha256(body).hexdigest()==reference['sha256']
        and (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
        ==(linked.st_dev,linked.st_ino,linked.st_size,linked.st_mtime_ns),'EXISTING_BODY_SHA_OR_FSTAT_CHANGED')
    return json.loads(body,object_pairs_hook=Q.pairs_unique)


def write_new(path,value,cap,out):
    raw=Q.canonical(value)+b'\n';Q.need(len(raw)<=cap,'ARTIFACT_SIZE_CAP_NO_TRUNCATION')
    current=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    Q.need(current+len(raw)+(1<<20)<=C.SCOPE['whole_output_cap_bytes'],'WHOLE32M_CAP_WITH_FAILURE_METADATA_RESERVE')
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
    Q.need(path.stat().st_size==len(raw) and h.hexdigest()==hashlib.sha256(raw).hexdigest(),'NEW_ARTIFACT_READBACK_DIFFERS')
    return {'path':str(path),'bytes':len(raw),'sha256':h.hexdigest()}


def fixtures():
    sys.path.insert(0,str(C.OLD))
    from .test_analysis import InvariantBoundaries
    from . import analysis as A
    spec=importlib.util.spec_from_file_location('_native72_original_four',C.OLD/'test_v2.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    old=unittest.defaultTestLoader.loadTestsFromTestCase(module.NativePrecisionFixtures)
    new=unittest.defaultTestLoader.loadTestsFromTestCase(InvariantBoundaries)
    Q.need(old.countTestCases()==4 and new.countTestCases()==4,'EXACT_ORIGINAL4_AND_DERIVED4_METHODS_REQUIRED')
    successes=[]
    class Recording(unittest.TestResult):
        def addSuccess(self,test):super().addSuccess(test);successes.append(test.id())
    result=Recording();stdout=io.StringIO();stderr=io.StringIO()
    with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):unittest.TestSuite([old,new]).run(result)
    return {'schema':'NATIVE72_INVARIANTS_ACTUAL8_FIXTURE_RECEIPT_V1',
        'status':'PASS' if result.testsRun==8 and len(successes)==8 and result.wasSuccessful()
            and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses) else 'FAIL',
        'original_methods':4,'derived_methods':4,'tests_run':result.testsRun,'successful_ids':successes,
        'failures':[{'test_id':t.id(),'traceback':detail} for t,detail in result.failures],
        'errors':[{'test_id':t.id(),'traceback':detail} for t,detail in result.errors],
        'skipped':[{'test_id':t.id(),'reason':reason} for t,reason in result.skipped],
        'expected_failures':[{'test_id':t.id(),'traceback':detail} for t,detail in result.expectedFailures],
        'unexpected_successes':[t.id() for t in result.unexpectedSuccesses],
        'stdout':stdout.getvalue(),'stderr':stderr.getvalue(),'scientific_body_reads':0,'QM_or_UFF_calls':0}


def memory(processes):
    pids=[os.getpid()]+[p.pid for p in processes if p.pid and p.is_alive()];rss=0
    for pid in pids:
        try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        except FileNotFoundError:continue
    free=next(int(s.split()[1])*1024 for s in pathlib.Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:'))
    return {'observed_unix':time.time(),'owned_parent_worker_RSS_bytes':rss,'MemAvailable_bytes':free}


def short_exact(value):
    if not isinstance(value,str) or len(value)<=512:return value
    return {'prefix':value[:512],'full_characters':len(value),'shortened_in_small_summary':True,'complete_exact_value_in_report':True}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=pathlib.Path,required=True);p.add_argument('--startup-proof',type=pathlib.Path,required=True)
    args=p.parse_args();plan,proof=require_startup(args.plan,args.startup_proof)
    started=time.monotonic();out=Q.literal(plan['output_directory']);out.mkdir(mode=0o700,parents=True,exist_ok=False)
    runtime={'endpoint':Q.ENDPOINT,'uid':os.getuid(),'node':socket.gethostname().split('.')[0],'job_id':os.environ['SLURM_JOB_ID'],
        'allocated_cpus':16,'worker_limit':16,'memory_policy':Q.POLICY,'memory_requested':False,'forced_signals_sent':False}
    tests=None;case_rows=[];rotation_rows=[];failure_rows=[];pairs=[];errors=[];samples=[];stop=None;data_reads=0;body_attempts=0;report_ref=None;authority_checked=False
    try:
        tests=fixtures();write_new(out/'fixtures8.json',tests,C.SCOPE['maximum_summary_bytes'],out)
        Q.need(tests['status']=='PASS','EIGHT_ACTUAL_FIXTURES_MUST_PASS_BEFORE_TWO_BODY_READS')
        from . import analysis as A
        config=Q.load_ref(C.CONFIG);small=Q.load_ref(C.SMALL_SUMMARY)
        Q.need(small['full_report_reference']==C.DATA[0] and small['all72_inputs_closed'] is True and small['original_15_failures_unchanged'] is True,'EXISTING_SMALL_ACTUAL_DIAGNOSIS_AUTHORITY_REQUIRED')
        body_attempts+=1;diagnosis=read_body(C.DATA[0]);data_reads+=1
        body_attempts+=1;original=read_body(C.DATA[1]);data_reads+=1
        links=A.validate_inputs(diagnosis,original,config);authority_checked=True
        work=[(case_id,original['measurements'][case_id],links[case_id]) for case_id in sorted(links)]
        index=0;active={}
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn')) as pool:
            while active or index<len(work):
                row=memory(list(pool._processes.values()))
                if len(samples)<1024:samples.append(row)
                if row['owned_parent_worker_RSS_bytes']>C.SCOPE['algorithm_rss_soft_cap_bytes'] or row['MemAvailable_bytes']<C.SCOPE['minimum_mem_available_bytes']:stop='OBSERVED_MEMORY_STOP_NEW_TASKS_NATURAL_DRAIN'
                if time.monotonic()-started>=C.SCOPE['wall_seconds']-C.SCOPE['dispatch_reserve_seconds']:stop='WALL_RESERVE_STOP_NEW_TASKS_NATURAL_DRAIN'
                while stop is None and index<len(work) and len(active)<16:
                    item=work[index];active[pool.submit(A.case_analysis,item)]=item[0];index+=1
                if not active:break
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    case_id=active.pop(future)
                    try:case_rows.append(future.result())
                    except Exception as exc:errors.append({'stage':'case_invariants','case_id':case_id,'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
        if stop is None and not errors:
            rotation_rows=A.rotations(diagnosis,original,config)
            failure_rows,decoded=A.failures(diagnosis,original,config);pairs=A.noisy_pairs(decoded,original,config)
        complete=len(case_rows)==72 and len(rotation_rows)==32 and len(failure_rows)==15 and len(pairs)==6 and not errors and stop is None
        detail={'schema':'NATIVE72_EXISTING_REPORT_INVARIANTS_ALPHA_V1','status':'READONLY_ANALYSIS_CLOSED_ORIGINAL15FAIL_AND_RELEASE_HOLD' if complete else 'INCOMPLETE_READONLY_ANALYSIS_ORIGINAL15FAIL_AND_RELEASE_HOLD',
            'runtime':runtime,'scope_parameters':C.SCOPE,'input_body_references':C.DATA,'config_reference':C.CONFIG,
            'source_diagnosis_job_id':'1884773','fixtures':tests,'technical_analysis_complete':complete,
            'original_failures':diagnosis['original_failures'],'original_failures_retained':True,'original_15FAIL_count':15,
            'all72_cases':sorted(case_rows,key=lambda row:row['case_id']),'rotation_pairs':rotation_rows,
            'native_failure_invariants':failure_rows,'fixed_noisy_xtb_pairs':pairs,
            'original_noise_order_checks':diagnosis['noise_order_checks'],'original_translation_orbits':diagnosis['translation_orbits'],
            'coordinate_residuals_are_recorded_evidence_not_new_raw_coordinate_reads':True,
            'case_errors':errors,'soft_stop':stop,'actual_memory_samples':samples,
            'data_body_read_attempts':body_attempts,'data_bodies_verified_and_loaded':data_reads,
            'new_QM_calls':0,'new_UFF_calls':0,'raw_SQLite_reads':0,'scientific_PASS':False,'full_or2000_release':'HOLD',
            'SCF_or_printing_or_program_bug_cause_inferred':False,'original_tolerances_modified':False,
            'limitations':['Exact norm/Gram equality is about recorded binary64/decimal centers, not certified physical values.',
                'Nonzero invariant drift cannot by itself identify SCF or a program cause.',
                'Original per-run SP output coordinates remain unavailable; companion frames are recorded corroboration.',
                'Only fields present in these fixed existing reports are analyzed; absent values are not synthesized.'],
            'wall_seconds_observed':time.monotonic()-started,'actual_terminal_accounting_required':True}
        report_ref=write_new(out/'invariants_report.json',detail,C.SCOPE['maximum_report_bytes'],out)
    except Exception as exc:
        complete=False;errors.append({'stage':'analysis_or_publication','error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
    summary={'schema':'NATIVE72_INVARIANTS_SMALL_RECEIPT_ALPHA_V1','runtime':runtime,
        'status':'READONLY_ANALYSIS_CLOSED_ORIGINAL15FAIL_AND_RELEASE_HOLD' if complete else 'INCOMPLETE_READONLY_ANALYSIS_ORIGINAL15FAIL_AND_RELEASE_HOLD',
        'technical_analysis_complete':complete,'report_reference':report_ref,
        'data_body_read_attempts':body_attempts,'data_bodies_verified_and_loaded':data_reads,
        'fixture_receipt':tests,'actual_cases_analyzed':len(case_rows),'rotation_pairs':len(rotation_rows),
        'retained_original_failure_rows':len(failure_rows),'original15FAIL_preserved':True,'noisy_pairs':len(pairs),
        'original15_failure_authority_reverified_this_stage':authority_checked,
        'same_frozen_covariance_replayed_count':sum(item['original_check_reproduced'] is True for row in rotation_rows for item in row['fields'].values()),
        'same_frozen_covariance_comparison_count':sum(len(row['fields']) for row in rotation_rows),
        'same_noisy_pair_control_replayed_count':sum(row['original_control_reproduced'] is True for row in pairs),
        'per_original_failure_invariant_summary':[{'original_failure':row['original_failure'],
            'original_failure_retained':True,'original_max_residual':row['original_check'].get('max_abs_residual'),
            'original_max_allowance':row['original_check'].get('max_allowance'),
            'native_center_base_squared_norm':short_exact(row['native_decimal_center_invariants']['base']['sum_squared_norms_exact']),
            'native_center_variant_squared_norm':short_exact(row['native_decimal_center_invariants']['variant']['sum_squared_norms_exact']),
            'native_center_pair':{key:short_exact(value) for key,value in row['native_decimal_center_invariants']['pair'].items()},
            'physical_cause_proven':False} for row in failure_rows],
        'coordinate_evidence_summary':[{'group':row['group'],
            'recorded_input_orbit_max_abs_error_A':row['recorded_input_coordinate_orbit']['max_abs_orbit_error_A'],
            'output_frame_transport_status':row['recorded_output_coordinate_chart_transport']['status'],
            'recorded_output_chart_R_max_difference_exact':short_exact(row['recorded_output_coordinate_chart_transport'].get('max_abs_difference_from_declared_input_R_exact')),
            'new_input_or_output_coordinate_reads':False} for row in rotation_rows],
        'three_noisy_groups_six_arm_summary':[{'molecule_id':row['molecule_id'],'geometry_source':row['geometry_source'],'arm':row['arm'],
            'same_frozen_control_from_original_native_tokens':row['same_frozen_control_from_original_native_tokens'],
            'original_control_reproduced':row['original_control_reproduced'],
            'original_exact_same_input_geometry':row['original_same_geometry_control']['exact_same_input_geometry'],
            'original_gradient_supports_input_axes':row['original_same_geometry_control']['gradient_output_coordinates']['supports_input_axes'],
            'SP_own_output_coordinate_frame_known':False} for row in pairs],
        'original_quality_status':'15_ORIGINAL_FAIL_RETAINED','scientific_PASS':False,'full_or2000_release':'HOLD',
        'new_QM_calls':0,'new_UFF_calls':0,'raw_SQLite_reads':0,'soft_stop':stop,'error_count':len(errors),
        'errors':[{'stage':row['stage'],'error':row['error'][:1600],'traceback':row['traceback'][:4000]} for row in errors[:16]],
        'additional_errors_not_in_small_list':max(0,len(errors)-16),'wall_seconds_observed':time.monotonic()-started,
        'actual_terminal_accounting_required':True}
    receipt=write_new(out/'diagnosis_summary.json',summary,C.SCOPE['maximum_summary_bytes'],out)
    print(json.dumps({'summary':receipt,'report':report_ref,'technical_analysis_complete':complete,'scientific_PASS':False,'full_or2000_release':'HOLD'}))
    return 0 if complete else 3


if __name__=='__main__':sys.exit(main())
