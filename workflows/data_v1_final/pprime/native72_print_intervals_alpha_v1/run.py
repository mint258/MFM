"""Bounded exact print-invariant hypotheses; original fifteen failures stay failures."""
import argparse,concurrent.futures as cf,contextlib,io,json,multiprocessing as mp,os,time,traceback,unittest
from pathlib import Path
from secondary_cpu_queue_v1 import common as Q
from native72_invariants_alpha_v2 import run as previous
from . import contract as C
from .guard import require_startup


def fixtures():
    old=previous.fixtures()
    from .test_analysis import IntervalBoundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(IntervalBoundaries);Q.need(suite.countTestCases()==3,'EXACT_THREE_NEW_INTERVAL_METHODS')
    successes=[]
    class Recording(unittest.TestResult):
        def addSuccess(self,test):super().addSuccess(test);successes.append(test.id())
    result=Recording();stdout=io.StringIO();stderr=io.StringIO()
    with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):suite.run(result)
    new={'tests_run':result.testsRun,'successful_ids':successes,'failures':[{'id':t.id(),'traceback':v} for t,v in result.failures],
        'errors':[{'id':t.id(),'traceback':v} for t,v in result.errors],'skipped':[{'id':t.id(),'reason':v} for t,v in result.skipped],
        'expected_failures':[{'id':t.id(),'traceback':v} for t,v in result.expectedFailures],
        'unexpected_successes':[t.id() for t in result.unexpectedSuccesses],'stdout':stdout.getvalue(),'stderr':stderr.getvalue()}
    passed=old['status']=='PASS' and old['tests_run']==8 and result.testsRun==len(successes)==3 and result.wasSuccessful()
    passed=passed and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses)
    return {'status':'PASS' if passed else 'FAIL','tests_run':old['tests_run']+result.testsRun,'unchanged8':old,'new3':new,
        'scientific_body_reads':0,'new_QM_UFF_calls':0}


def owned_bytes(out):return sum(p.stat().st_size for p in out.rglob('*') if p.is_file())


def observation(out,proof,processes,started):
    value=previous.memory(processes);total=next(int(s.split()[1])*1024 for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemTotal:'))
    space=os.statvfs(C.ROOT);free=space.f_bavail*space.f_frsize;current=owned_bytes(out);cap=C.SCOPE['whole_output_cap_bytes']
    other=max(0,proof['storage_observation']['whole_output_caps_reserved_bytes']-cap)
    reasons=[]
    if value['owned_parent_worker_RSS_bytes']>=C.SCOPE['algorithm_rss_soft_cap_bytes']:reasons.append('ACTUAL_RSS_SOFT_REFERENCE')
    if value['MemAvailable_bytes']<max(C.SCOPE['minimum_mem_available_bytes'],C.SCOPE['minimum_MemAvailable_fraction']*total):reasons.append('ACTUAL_MEMAVAILABLE_LOW')
    if free-max(0,cap-current)-other<200000000000:reasons.append('CURRENT_FREE_REGISTERED_CAPS_PLUS200GB')
    elapsed=Q.duration(Q.fields(proof['job_metadata'])['RunTime'])+max(0,time.time()-proof['observed_unix_seconds'])
    if elapsed>=C.SCOPE['wall_seconds']-C.SCOPE['dispatch_reserve_seconds']:reasons.append('WALL_RESERVE')
    return dict(value,whole_owned_output_bytes=current,current_mount_free_bytes=free,stop_new_dispatch_reasons=reasons)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=Path,required=True);p.add_argument('--startup-proof',type=Path,required=True)
    args=p.parse_args();plan,proof=require_startup(args.plan,args.startup_proof)
    import sys,numpy
    Q.need(sys.version.split()[0]=='3.11.14' and numpy.__version__=='2.2.6','EXACT_ALPHA_PYTHON_NUMPY')
    out=Q.literal(plan['output_directory']);out.mkdir(parents=True,mode=0o700,exist_ok=False);started=time.monotonic()
    rows=[];errors=[];samples=[];stop=None;fixture=None;data_reads=0;detail_ref=None;authority=False;failure_authority=[]
    runtime={'endpoint':Q.ENDPOINT,'uid':1264,'node':plan['node'],'job_id':str(proof['job_id']),'allocated_cpus':16,
        'maximum_active_failure_tasks':15,'sixteen_busy_workers_claimed':False,'memory_policy':Q.POLICY,'memory_requested':False,'signals_sent':False}
    try:
        fixture=fixtures();previous.write_new(out/'fixtures11.json',fixture,C.SCOPE['maximum_summary_bytes'],out)
        Q.need(fixture['status']=='PASS' and fixture['tests_run']==11,'ALL11_ACTUAL_FIXTURES_BEFORE_EXISTING_BODY_READS')
        from . import analysis as A
        config=Q.load_ref(C.CONFIG);small=Q.load_ref(C.SMALL_SUMMARY)
        Q.need(small['full_report_reference']==C.DATA[0] and small['all72_inputs_closed'] is True and small['original_15_failures_unchanged'] is True,'ORIGINAL_CLOSED72_SMALL_AUTHORITY')
        diagnosis=previous.read_body(C.DATA[0]);data_reads+=1;original=previous.read_body(C.DATA[1]);data_reads+=1
        tasks=A.validate(diagnosis,original,config);authority=True;failure_authority=diagnosis['original_failures']
        active={};index=0
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn')) as pool:
            while active or index<len(tasks):
                sample=observation(out,proof,list(pool._processes.values()),started)
                if len(samples)<1024:samples.append(sample)
                if sample['stop_new_dispatch_reasons']:stop=sample['stop_new_dispatch_reasons']
                while stop is None and index<len(tasks) and len(active)<16:
                    item=tasks[index];active[pool.submit(A.failure_task,item)]=index;index+=1
                if not active:break
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    task_index=active.pop(future)
                    try:
                        value=future.result();value['evidence_reference']=previous.write_new(out/('failure_%02d.json'%task_index),value,C.SCOPE['maximum_failure_evidence_bytes'],out)
                        rows.append((task_index,value))
                    except Exception as exc:errors.append({'stage':'native_print_intervals','task_index':task_index,'error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
        rows=[value for _,value in sorted(rows,key=lambda pair:pair[0])]
        complete=len(rows)==15 and not errors and stop is None
        detail={'schema':'NATIVE72_PRINT_INTERVALS_EXISTING_REPORT_DIAGNOSIS_V1',
            'status':'TECHNICAL_DIAGNOSIS_CLOSED_ORIGINAL15FAIL_HOLD' if complete else 'INCOMPLETE_DIAGNOSIS_ORIGINAL15FAIL_HOLD',
            'technical_analysis_complete':complete,'runtime':runtime,'scope_parameters':C.SCOPE,'data_body_references':C.DATA,
            'config_reference':C.CONFIG,'original_tolerances':config['vector_tolerances'],'fixtures':fixture,
            'original_failure_authority':failure_authority,'original15FAIL_preserved':True,'per_original_failure':rows,
            'diagnosis_model':'ROUND_TO_NEAREST_NATIVE_DECIMAL_BOX_INTERVALS_THROUGH_FROZEN_FIELD_UNIT_FACTOR',
            'new_tolerance_axis_scale_or_atom_fit':False,'scientific_PASS':False,'full_or2000_release':'HOLD',
            'SCF_physical_or_program_cause_proven':False,'raw_new_coordinate_or_QM_UFF_reads':0,
            'data_bodies_verified_and_loaded':data_reads,'errors':errors,'soft_stop_new_dispatch':stop,'actual_memory_storage_samples':samples,
            'actual_terminal_parent_cost_pending_Root_accounting':True,'cost_decision_reference':plan['cost_decision_reference'],
            'cost_overrun_action':'REPORT_AND_CONTINUE','wall_seconds':time.monotonic()-started}
        detail_ref=previous.write_new(out/'print_interval_report.json',detail,C.SCOPE['maximum_report_bytes'],out)
    except Exception as exc:
        complete=False;errors.append({'stage':'guarded_analysis_or_publication','error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
    summary={'schema':'NATIVE72_PRINT_INTERVALS_SMALL_RECEIPT_V1','runtime':runtime,'technical_analysis_complete':complete,
        'status':'TECHNICAL_DIAGNOSIS_CLOSED_ORIGINAL15FAIL_HOLD' if complete else 'INCOMPLETE_DIAGNOSIS_ORIGINAL15FAIL_HOLD',
        'report_reference':detail_ref,'fixture_receipt':fixture,'data_bodies_verified_and_loaded':data_reads,
        'original15_failure_authority_reverified':authority,'original15FAIL_preserved':True,'failure_rows_analyzed':len(rows),
        'per_original_failure':[{'original_failure':row['original_failure'],'original_failure_retained':True,
            'native_interval_model_status':row['interval_analysis']['diagnostic_status'],
            'row_norm_intervals_disjoint':row['interval_analysis']['disjoint_row_norm_intervals'],
            'total_norm_squared_intervals_disjoint':row['interval_analysis']['total_squared_norm_intervals_disjoint'],
            'flat_component_permutations_or_signs_excluded_under_print_model':row['interval_analysis']['any_flat_component_permutation_or_sign_flip_excluded_under_print_model'],
            'Gram_entries_checked':row['interval_analysis']['Gram_entries_checked'],'disjoint_Gram_entries':row['interval_analysis']['disjoint_Gram_entries'],
            'evidence_reference':row['evidence_reference'],'cause_proven':False,'scientific_PASS':False} for row in rows],
        'native_interval_hypothesis_excluded_count':sum(row['interval_analysis']['rotation_only_plus_native_print_rounding_hypothesis_excluded'] for row in rows),
        'model_not_excluded_is_UNKNOWN_not_PASS':True,'new_numeric_tolerance':False,'physical_SCF_program_unit_cause':'UNKNOWN',
        'original_quality_status':'15_ORIGINAL_FAIL_RETAINED','scientific_PASS':False,'full_or2000_release':'HOLD',
        'new_QM_UFF_raw_coordinate_reads':0,'soft_stop':stop,'error_count':len(errors),'errors':errors[:16],
        'wall_seconds':time.monotonic()-started,'actual_terminal_parent_accounting_required':True}
    receipt=previous.write_new(out/'diagnosis_summary.json',summary,C.SCOPE['maximum_summary_bytes'],out)
    print(json.dumps({'summary':receipt,'report':detail_ref,'technical_analysis_complete':complete,'scientific_PASS':False,'full_or2000_release':'HOLD'}))
    return 0 if complete else 3

if __name__=='__main__':raise SystemExit(main())
