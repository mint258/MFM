"""Finite Alpha CPU readback; no launcher, submission, new QM or tolerance revision."""
from __future__ import annotations
import argparse,concurrent.futures as cf,contextlib,hashlib,io,json,multiprocessing as mp,os,pathlib,socket,stat,sys,time,traceback,unittest
from decimal import Decimal
from fractions import Fraction
from secondary_cpu_queue_v1 import common as Q
from . import contract as C
from .guard import require_startup


def write_new(path,value,cap,out):
    raw=Q.canonical(value)+b'\n';Q.need(len(raw)<=cap,'FINITE_DIAGNOSTIC_ARTIFACT_CAP_NO_TRUNCATION')
    current=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
    Q.need(current+len(raw)+(1<<20)<=C.SCOPE['whole_output_cap_bytes'],'WHOLE64M_CAP_WITH_ERROR_RESERVE')
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    Q.need(path.read_bytes()==raw,'ACTUAL_NEW_REPORT_READBACK_DIFFERS')
    return {'path':str(path),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def body(reference):
    path=Q.literal(reference['path']);Q.need(0<reference['bytes']<=16<<20,'BOUNDED_PREVIOUS_REPORT_REQUIRED')
    with path.open('rb') as stream:
        a=os.fstat(stream.fileno());Q.need(stat.S_ISREG(a.st_mode) and a.st_uid==1264 and a.st_size==reference['bytes'],'ACTUAL_OWNED_PREVIOUS_REPORT_REQUIRED')
        raw=stream.read(reference['bytes']+1);b=os.fstat(stream.fileno())
    c=path.stat();Q.need((a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns)==(c.st_dev,c.st_ino,c.st_size,c.st_mtime_ns)
        and len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'],'PREVIOUS_REPORT_SHA_OR_FSTAT_CHANGED')
    return json.loads(raw,object_pairs_hook=Q.pairs_unique)


def fixtures():
    from .test_analysis import EvidenceBoundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(EvidenceBoundaries);Q.need(suite.countTestCases()==3,'EXACT_NEW3_PURE_METHODS_REQUIRED')
    successes=[]
    class Result(unittest.TestResult):
        def addSuccess(self,test):super().addSuccess(test);successes.append(test.id())
    result=Result();stdout=io.StringIO();stderr=io.StringIO()
    with contextlib.redirect_stdout(stdout),contextlib.redirect_stderr(stderr):suite.run(result)
    return {'status':'PASS' if result.testsRun==3 and len(successes)==3 and result.wasSuccessful()
        and not(result.skipped or result.expectedFailures or result.unexpectedSuccesses) else 'FAIL',
        'tests_run':result.testsRun,'successful_ids':successes,'failures':[str(value) for value in result.failures],
        'errors':[str(value) for value in result.errors],'skipped':[str(value) for value in result.skipped],
        'expected_failures':[str(value) for value in result.expectedFailures],'unexpected_successes':[str(value) for value in result.unexpectedSuccesses],
        'stdout':stdout.getvalue(),'stderr':stderr.getvalue(),'scientific_body_reads':0,'QM_or_UFF_calls':0}


def memory(processes):
    pids=[os.getpid()]+[p.pid for p in processes if p.pid and p.is_alive()];rss=0
    for pid in pids:
        try:rss+=int(pathlib.Path('/proc',str(pid),'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        except FileNotFoundError:continue
    free=next(int(line.split()[1])*1024 for line in pathlib.Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:'))
    return {'observed_unix_seconds':time.time(),'owned_parent_workers_RSS_bytes':rss,'MemAvailable_bytes':free}


def pair_evidence(rows):
    groups={}
    for row in rows:groups.setdefault(tuple(row['identity'][:3]),{})[row['identity'][3]]=row
    result=[]
    for group,arms in sorted(groups.items()):
        if set(arms)!={'base','rotated'}:continue
        a,b=arms['base'],arms['rotated'];ea,eb=a['termination']['energy_tokens'],b['termination']['energy_tokens'];delta=None
        if len(ea)==len(eb)==1 and ea[0]['units']==eb[0]['units']:
            tokens=[value[0]['token'].replace('D','E').replace('d','e') for value in (ea,eb)]
            if all(len(token)<=256 and abs(Decimal(token).as_tuple().exponent)<=4096 for token in tokens):
                delta=str(Fraction(Decimal(tokens[1]))-Fraction(Decimal(tokens[0])))
        result.append({'group':list(group),'base_case':a['case_id'],'rotated_case':b['case_id'],
            'SCF_converged':[a['frozen_SCF_metadata']['converged'],b['frozen_SCF_metadata']['converged']],
            'SCF_iterations':[a['frozen_SCF_metadata']['scf_iterations'],b['frozen_SCF_metadata']['scf_iterations']],
            'native_returncodes':[a['stored_native_result']['returncode'],b['stored_native_result']['returncode']],
            'terminal_marker_status':[a['termination']['status'],b['termination']['status']],
            'own_output_frame_status':[a['own_output_frame']['status'],b['own_output_frame']['status']],
            'unique_native_energy_token_center_delta_exact_rational':delta,'energy_delta_has_no_new_tolerance_or_PASS':True,
            'different_SCF_or_energy_is_not_a_proven_causal_explanation':True,'physical_cause_proven':False,'original_failure_status_revised':False})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',type=pathlib.Path,required=True);parser.add_argument('--startup-proof',type=pathlib.Path,required=True)
    args=parser.parse_args();plan,proof=require_startup(args.plan,args.startup_proof)
    started=time.monotonic();out=Q.literal(plan['output_directory']);out.mkdir(mode=0o700,parents=True,exist_ok=False)
    runtime={'endpoint':Q.ENDPOINT,'uid':os.getuid(),'node':socket.gethostname().split('.')[0],'job_id':str(proof['job_id']),
        'allocated_cpus':16,'worker_limit':16,'memory_policy':Q.POLICY,'memory_requested':False,'forced_signals_sent':False}
    tests=None;rows=[];errors=[];samples=[];stop=None;data_reads=0;dispatched=0;report_ref=None;pairs=[]
    try:
        tests=fixtures();write_new(out/'fixtures3.json',tests,C.SCOPE['maximum_summary_bytes'],out)
        Q.need(tests['status']=='PASS','THREE_PURE_FIXTURES_PASS_BEFORE_ANY_BODY_READ')
        from . import analysis as A
        summary=Q.load_ref(C.SMALL_SUMMARY);diagnosis=body(C.DATA[0]);data_reads+=1;original=body(C.DATA[1]);data_reads+=1
        config=Q.load_ref(C.CONFIG)
        Q.need(diagnosis['config']==original['config'] and all(diagnosis['config'][key]==C.CONFIG[key] for key in ('bytes','sha256'))
            and diagnosis['original_all_predeclared_vector_tolerances']==config['vector_tolerances'],'ORIGINAL_CONFIG_AND_ALL_VECTOR_TOLERANCES_UNCHANGED')
        selected=A.choose_cases(diagnosis,original,summary)
        write_new(out/'selection24.json',{'case_ids':[row['case_id'] for row in selected],'identities':[row['identity'] for row in selected],
            'maximum_raw_calls':24,'new_QM_calls':0,'original15FAIL':C.EXPECTED_FAILURES},C.SCOPE['maximum_summary_bytes'],out)
        index=0;active={}
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=A.init_worker,initargs=(plan,)) as pool:
            while active or index<len(selected):
                observed=memory(list(pool._processes.values()))
                if len(samples)<1024:samples.append(observed)
                if observed['owned_parent_workers_RSS_bytes']>C.SCOPE['algorithm_rss_soft_cap_bytes'] or observed['MemAvailable_bytes']<C.SCOPE['minimum_mem_available_bytes']:
                    stop='OBSERVED_MEMORY_STOP_NEW_CALLS_NATURAL_DRAIN'
                if time.monotonic()-started>=C.SCOPE['wall_seconds']-C.SCOPE['dispatch_reserve_seconds']:stop='WALL_RESERVE_STOP_NEW_CALLS_NATURAL_DRAIN'
                while stop is None and index<len(selected) and len(active)<16:
                    item=selected[index];active[pool.submit(A.diagnose,item)]=item['case_id'];index+=1;dispatched+=1
                if not active:break
                done,_=cf.wait(active,timeout=1,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    case_id=active.pop(future)
                    try:
                        row=future.result();write_new(out/(case_id+'.json'),row,C.SCOPE['maximum_case_evidence_bytes'],out);rows.append(row)
                    except Exception as exc:errors.append({'stage':'retained_call_diagnosis','case_id':case_id,'status':'UNKNOWN','error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
        pairs=pair_evidence(rows)
        complete=len(rows)==24 and len({row['case_id'] for row in rows})==24 and len(pairs)==12 and not errors and stop is None
        detail={'schema':'NATIVE72_RETAINED_RAW_SCF_TERMINATION_FRAME_ALPHA_V1','technical_analysis_complete':complete,
            'runtime':runtime,'scope_parameters':C.SCOPE,'original15FAIL':C.EXPECTED_FAILURES,'original15FAIL_preserved':True,
            'prior789_eight_fixture_receipt':summary['fixture_receipt'],'new_fixture_receipt':tests,'data_references':C.DATA,
            'relocation_map_reference':plan['relocation_map_reference'],'SCF_source_reference':Q.ref(C.HERE/'frozen_scf.py'),
            'fixed_selected_case_ids':[row['case_id'] for row in selected],'raw_call_diagnoses':sorted(rows,key=lambda row:row['case_id']),
            'pair_evidence':pairs,'case_errors':errors,'raw_call_tasks_dispatched':dispatched,'previous_report_bodies_loaded':data_reads,
            'actual_memory_samples':samples,'soft_stop':stop,'scientific_PASS':False,'full_or2000_release':'HOLD','new_QM_calls':0,'new_UFF_calls':0,
            'all_causal_claims_remain_UNKNOWN':True,'original_tolerances_changed':False,'wall_seconds_observed':time.monotonic()-started,
            'limitations':['Explicit convergence or normal termination does not certify covariance or a unique electronic solution.',
                'Missing native markers or own coordinates remain UNKNOWN; a companion coordinate frame is never substituted.',
                'Native energy-token differences are observations without a new quality threshold or causal PASS.',
                'Only these existing24 calls are reopened; absent output or discarded SCF history cannot be reconstructed.'],
            'actual_terminal_parent_accounting_required':True}
        report_ref=write_new(out/'retained_raw_diagnosis.json',detail,C.SCOPE['maximum_report_bytes'],out)
    except Exception as exc:
        complete=False;errors.append({'stage':'diagnosis_or_publication','status':'UNKNOWN','error':type(exc).__name__+': '+str(exc),'traceback':traceback.format_exc()})
    receipt={'schema':'NATIVE72_RETAINED_RAW_SMALL_RECEIPT_ALPHA_V1','technical_analysis_complete':complete,'runtime':runtime,
        'report_reference':report_ref,'actual_cases_diagnosed':len(rows),'raw_call_tasks_dispatched':dispatched,
        'new_fixture_receipt':tests,'original15FAIL':C.EXPECTED_FAILURES,'original15FAIL_preserved':True,
        'explicit_SCF_failure_cases':[row['case_id'] for row in rows if row['explicit_SCF_failure_observed']],
        'termination_marker_counts':{status:sum(row['termination']['status']==status for row in rows) for status in sorted({row['termination']['status'] for row in rows})},
        'own_frame_status_counts':{status:sum(row['own_output_frame']['status']==status for row in rows) for status in sorted({row['own_output_frame']['status'] for row in rows})},
        'SCF_recorded_metadata_mismatch_cases':[row['case_id'] for row in rows if not row['fresh_SCF_matches_recorded']],
        'pair_evidence':pairs,'all_causal_claims_remain_UNKNOWN':True,'scientific_PASS':False,'full_or2000_release':'HOLD',
        'new_QM_calls':0,'new_UFF_calls':0,'error_count':len(errors),'errors':[{'case_id':row.get('case_id'),'stage':row['stage'],'error':row['error'][:1600]} for row in errors[:24]],
        'soft_stop':stop,'wall_seconds_observed':time.monotonic()-started,'actual_terminal_parent_accounting_required':True}
    published=write_new(out/'diagnosis_summary.json',receipt,C.SCOPE['maximum_summary_bytes'],out)
    print(json.dumps({'summary_reference':published,'report_reference':report_ref,'technical_analysis_complete':complete,'scientific_PASS':False,'full_or2000_release':'HOLD'}))
    return 0 if complete else 3

if __name__=='__main__':sys.exit(main())
