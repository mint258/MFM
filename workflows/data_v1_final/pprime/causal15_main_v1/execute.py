"""Actual prepare C0 + independent Root review, then at most fifteen frozen invokes."""
from __future__ import annotations
import argparse,concurrent.futures as cf,copy,json,multiprocessing as mp,os,pathlib,sys,tempfile,time,traceback
REPO=pathlib.Path(__file__).absolute().parents[4];sys.path.insert(0,str(REPO));sys.dont_write_bytecode=True
from workflows.data_v1_final.pprime.causal15_main_v1 import contract as C,io as I,render as T,analysis
OPTIONS=('plan','prepared','prepare-accounting','execute-review','root-preflight','quota-reuse-review','output')
LEDGER=C.BASE/'qa_once_ledger'


def one(task_ref,claim_ref,plan,session,out_string,deadline):
    out=pathlib.Path(out_string);proof=I.continuation(session);task=I.read(task_ref);qa_id=task['qa_id'];folder=out/qa_id
    folder.mkdir(mode=0o700);claim=I.read(claim_ref)
    C.need(claim['task_reference']==task_ref and claim['job_id']==session['job_id'] and claim['qa_id']==qa_id,'ACTUAL_QA_CLAIM')
    start={'schema':'PPRIME_CAUSAL15_WORKER_STARTED_V1','qa_id':qa_id,'task_reference':task_ref,'claim_reference':claim_ref,
        'job_id':session['job_id'],'uid':os.getuid(),'pid':os.getpid(),'pid_start_ticks':I.R.proc_ticks(os.getpid()),'boot_id':session['boot_id']}
    start_ref=I.json_new(folder/'worker_start.json',start,out)
    engine=None;sink=None;scratch=pathlib.Path(tempfile.mkdtemp(prefix='causal15_'+session['job_id']+'_'+qa_id+'_',dir='/tmp'))
    record={'schema':'PPRIME_CAUSAL15_ACTUAL_CALL_V1','qa_id':qa_id,'condition':task['condition'],'arm':task['arm'],
        'rotation_matrix':task['rotation_matrix'],'task_reference':task_ref,'claim_reference':claim_ref,'worker_start_reference':start_ref,
        'origin_case_id':task['case']['case_id'],'original_evidence_reference':task['original_evidence_reference'],
        'case':copy.deepcopy(task['case']),'origin_case':copy.deepcopy(task['case']),'QM_call_attempted':False,'production_membership':False,'original15FAIL_preserved':True,
        'status':'UNSTARTED_OR_TECHNICAL_FAILURE','resource_monitor_signals_sent':False,'scientific_PASS':False,'full_or2000_release':'HOLD'}
    try:
        engine,contract,protocol,pilot=T.engine(plan,I.read)
        engine.initialize_worker(pilot['source_plan']['path'],protocol=contract['protocol']['path'],node_scratch_root=str(scratch),deadline=deadline,
            audit_membership=plan['audit_membership']['path'],reproduction_package=contract['reproduction_package']['path'])
        record['invoke_identity']=T.invoke_identity(engine,protocol)
        frozen_task=next(t for t in engine.CONFIG['tasks'] if t['name']==task['case']['calc_type'])
        C.need(frozen_task==task['original_task'] and engine.CONFIG['timeout_seconds']==900,'NO_TASK_ARGUMENT_OR_TIMEOUT_OVERRIDE')
        inputs={pathlib.Path(r['path']).name:I.body(r,C.INPUT_CAP) for r in task['target_input_references']}
        native,seed=T.bridge(task['case'],inputs,frozen_task,protocol,engine)
        C.need(seed==task['seed'] and task['case']['row']['record_id']==task['original_record_id'],'ORIGINAL_RECORD_ID_AND_SEED')
        C.need(native['coords'].tolist()==task['native_coordinates_A'],'EXACT_PREPARED_FLOAT64_RENDER_BRIDGE')
        record['case'].update(case_id=qa_id,native_coordinates_A=native['coords'].tolist(),actual_rendered_coordinates_A=T.arrays(inputs,task['case']['symbols']).tolist(),
            expected_actual_coordinates_A=T.arrays(inputs,task['case']['symbols']).tolist())
        hashes,combined=engine.rendered_input_hashes(frozen_task,native,task['case']['row'])
        C.need(hashes==[{'name':n,'sha256':C.sha(b)} for n,b in sorted(inputs.items())],'LAST_PRECALL_TARGET_BYTES')
        engine.CAPTURED=engine.CALL_SCRATCH=engine.CAPTURE_ERROR=None
        C.need(deadline-time.time()-30>=900,'INSUFFICIENT_ORIGINAL900_REMAINING_NO_NATIVE_CALL')
        I.json_new(folder/'invoke_intent.json',{'qa_id':qa_id,'state':'DURABLE_NATIVE_CALL_INTENT_NOT_RETURN','input_file_sha256':hashes,
            'input_bundle_sha256':combined,'actual_frozen_timeout_seconds':900,'original_record_id':task['original_record_id'],'seed':seed},out)
        record['QM_call_attempted']=True
        result=engine.NATIVE.invoke(frozen_task,native,task['case']['row'],engine.WORK)
        record['native_return_observed']=True;record['native_qm_termination']=result.get('qm_termination')
        C.need(engine.CAPTURE_ERROR is None and engine.CALL_SCRATCH is not None,'ORIGINAL_NATIVE_CAPTURE_REQUIRED')
        actual=[];(folder/'actual_postcall_inputs').mkdir()
        for name,expected in inputs.items():
            actual_path=engine.CALL_SCRATCH/name;C.need(actual_path.stat().st_size<=C.INPUT_CAP,'ACTUAL_POSTCALL_INPUT_CAP')
            observed=actual_path.read_bytes();C.need(observed==expected,'ACTUAL_POSTCALL_INPUT_BYTES_CHANGED')
            actual.append(dict(I.write(folder/'actual_postcall_inputs'/name,observed,out),matches_prepared_bytes=True))
        record['actual_postcall_input_references']=actual
        files=engine.CAPTURED or [];C.need(files and len(engine.OUTPUT_ARCHIVE.bundle(files)[0])<=C.RAW_CAP,'BOUNDED_ORIGINAL_RAW_BODY')
        source_status=result['status'];result['source_status']=source_status
        issues=engine.validate_atomic_arrays(result,native['z'])
        if issues and source_status=='SUCCESS':result.update(status='PROPERTY_FAILED',failure_code='REQUESTED_SCOPE_ATOMIC_ARRAY_QC_FAILED',failure_reason=' | '.join(issues))
        result['scope_status']=engine.canonical_status(result['status']);result['status']=result['scope_status']
        scf=engine.extract_scf(frozen_task['name'],files,result.get('values'),result['status'],source_status)
        result['provenance']={'status':result['status'],'software_version_id':engine.PACKAGE['software_versions'][frozen_task['family']]['software_version_id'],
            'elapsed_seconds':result.get('elapsed_seconds'),'scf_iterations':scf['scf_iterations'],'converged':scf['converged'],
            'input_file_sha256':hashes,'input_bundle_sha256':combined}
        result['raw_audit_selected']=True;record['parsed_wp5_result']=result
        context={'execution_id':'causal15:'+session['job_id']+':'+qa_id,'job_id':int(session['job_id']),'audit_only':True,'QA_arm':task['arm']}
        raw=engine.raw_record(frozen_task,task['case']['row'],result,files,context)
        from raw_archive import RawSink
        sink=RawSink(folder/'all_output_raw.sqlite',engine.OUTPUT_ARCHIVE,C.RAW_CAP);raw_ref=sink(raw)
        C.need(raw_ref.get('raw_call_durable') is True,'ALL15_DURABLE_ORIGINAL_RAW_REQUIRED');record['raw_reference']=raw_ref
        from read_outputs_v1 import parse_outputs
        record['independent_raw_readback']=parse_outputs(files,frozen_task['name'],task['case']['symbols'])
        record['status']='QA_CALL_DURABLE_INPUT_BYTES_VERIFIED_NO_SCIENTIFIC_RELEASE'
        # Same original deferred cleanup boundary, only after our own durable raw
        # and actual-input evidence. No resource controller calls stop_qm.
        record['scratch_bytes_removed']=engine.ORIGINAL_CLEANUP(engine.CALL_SCRATCH);engine.CALL_SCRATCH=None
    except BaseException as exc:
        record['error']={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        if engine is not None:engine.PRESERVE_ARCHIVE_FAILURE=True
    finally:
        if sink is not None:sink.close()
        record['engine_close']=engine.close_worker() if engine is not None else {'initialized':False}
        record['node_scratch_preserved']=str(scratch) if any(scratch.iterdir()) else None
        if not any(scratch.iterdir()):scratch.rmdir()
        from common import staging_bytes
        encoded=staging_bytes(record)+b'\n';C.need(len(encoded)<=C.RESULT_CAP,'NO_TRUNCATED_QA_RESULT')
        record_ref=I.write(folder/'result.json',encoded,out)
        I.json_new(folder/'finished.json',{'qa_id':qa_id,'result_reference':record_ref,'worker_start_reference':start_ref,
            'QM_call_attempted':record['QM_call_attempted'],'native_return_observed':record.get('native_return_observed',False),
            'status':record['status'],'error':record.get('error'),'unknown_or_failed_calls_never_retried':True},out)
    return record_ref


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in OPTIONS:p.add_argument('--'+name,type=pathlib.Path,required=True)
    args=p.parse_args();plan,proof,session=I.admit(__file__,args,OPTIONS,'execute');out=I.new_output(args.output)
    budget=I.Budget(proof,session,out);budget.start();records=[];errors=[];claims=[];index=0
    try:
        C.need(budget.observe() is None,'FRESH_RESOURCE_BEFORE_BODY');fixtures=I.fixtures(out)
        # Import only the frozen renderer/parser sources in the parent; no old
        # initialization, source LMDB read or scientific invocation happens here.
        T.engine(plan,I.read)
        prepared_ref=I.request_ref(args.root_preflight,args.prepared);prepared=I.read(prepared_ref)
        C.need(prepared['schema']=='PPRIME_CAUSAL15_PREPARED_V1' and prepared['status']=='ACTUAL15_EXACT_INPUTS_PREPARED_ZERO_QM'
            and prepared['plan_reference']==session['plan_reference'] and len(prepared['tasks'])==15 and prepared['new_QM_calls']==0,'ACTUAL_SAME_PLAN15_PREPARE')
        account_ref=I.request_ref(args.root_preflight,args.prepare_accounting);I.prepare_c0(account_ref,prepared['job_id'],proof)
        review_ref=I.request_ref(args.root_preflight,args.execute_review);review=I.read(review_ref,1<<20)
        C.need(review['schema']=='ROOT_PPRIME_CAUSAL15_EXECUTE_REVIEW_V1' and review['status']=='APPROVED_EXACT15_QA_AFTER_ACTUAL_PREPARE_C0'
            and review['reviewer']=='root' and review['plan_reference']==session['plan_reference'] and review['prepared_reference']==prepared_ref
            and review['prepare_accounting_reference']==account_ref and review['maximum_new_QM_calls']==15
            and review['task_timeout_seconds']==900 and review['full_or2000_release']=='HOLD'
            and review['automatic_retry'] is False and review['new_source_references']==session['own_source_references'],'INDEPENDENT_ROOT_ACTUAL_C0_EXECUTE_AUTHORITY')
        for row in prepared['tasks']:I.authorized(proof,[row['task_reference'],row['original_evidence_reference'],*row['target_input_references']])
        wanted=[row['qa_id'] for row in prepared['tasks']];C.need(wanted==['qa-%02d'%i for i in range(15)],'EXACT15_ORDERED_QA_IDS')
        LEDGER.mkdir(mode=0o700,exist_ok=True);C.need(not LEDGER.is_symlink(),'OWN_QA_LEDGER_ONLY')
        paths=[LEDGER/(C.key(prepared_ref,row['qa_id'])+'.json') for row in prepared['tasks']]
        C.need(not any(path.exists() or path.is_symlink() for path in paths),'QA_ONCE_ALREADY_CONSUMED_NO_AUTORETRY')
        active={};deadline=time.time()+proof['request']['wall_seconds']-60
        pool=cf.ProcessPoolExecutor(max_workers=15,mp_context=mp.get_context('spawn'))
        try:
            while active or index<15:
                budget.observe(list(pool._processes.values()))
                while index<15 and len(active)<15 and budget.observe(list(pool._processes.values())) is None:
                    row=prepared['tasks'][index];path=paths[index]
                    claim={'schema':'PPRIME_CAUSAL15_QA_DISPATCH_INTENT_V1','qa_id':row['qa_id'],'prepared_reference':prepared_ref,
                        'task_reference':row['task_reference'],'job_id':session['job_id'],'uid':1278,'boot_id':session['boot_id'],
                        'startup_proof_reference':session['proof_reference'],'state':'SUBMIT_INTENT_WORKER_NOT_YET_OBSERVED','automatic_retry':False}
                    with path.open('xb') as f:f.write(C.canonical(claim)+b'\n');f.flush();os.fsync(f.fileno())
                    I.R.fsync_dir(LEDGER);claim_ref=I.ref(path);claims.append(claim_ref);index+=1
                    active[pool.submit(one,row['task_reference'],claim_ref,plan,session,str(out),deadline)]=row['qa_id']
                if not active:break
                done,_=cf.wait(active,timeout=.25,return_when=cf.FIRST_COMPLETED)
                for future in done:
                    qa_id=active.pop(future)
                    try:records.append(future.result())
                    except BaseException as exc:errors.append({'qa_id':qa_id,'error':repr(exc),'state':'CONSUMED_UNKNOWN_NO_RETRY'})
        except BaseException as exc:
            errors.append({'phase':'parent_dispatch_or_pool','error':repr(exc),'all_existing_claims_consumed':True})
            # Preserve successful in-flight returns; no cancellation or signal.
            for future,qa_id in list(active.items()):
                try:records.append(future.result())
                except BaseException as drain_error:errors.append({'qa_id':qa_id,'error':repr(drain_error),'state':'CONSUMED_UNKNOWN_NO_RETRY'})
        finally:
            processes=list(pool._processes.values());pool.shutdown(wait=True,cancel_futures=False)
        from common import read_staging
        values=[read_staging(I.body(r,C.RESULT_CAP)) for r in records];config=I.read(plan['audit_config'])
        evidence={v['qa_id']:I.read(v['original_evidence_reference']) for v in values}
        findings=analysis.analyze(values,config,evidence);analysis_ref=I.json_new(out/'causal_analysis.json',findings,out)
        complete=len(values)==15 and len({v['qa_id'] for v in values})==15 and not errors and all(v.get('error') is None and v.get('raw_reference',{}).get('raw_call_durable') for v in values)
        receipt={'schema':'PPRIME_CAUSAL15_EXECUTION_RECEIPT_V1','status':'ACTUAL15_TECHNICALLY_CLOSED_REQUIRES_ROOT_CAUSAL_REVIEW' if complete else 'QA_CONSUMED_UNKNOWN_OR_INCOMPLETE_NO_RETRY',
            'job_id':session['job_id'],'plan_reference':session['plan_reference'],'prepared_reference':prepared_ref,'prepare_accounting_reference':account_ref,
            'execute_review_reference':review_ref,'startup_proof_reference':session['proof_reference'],'fixtures_reference':fixtures,'results':records,'claims':claims,
            'new_QM_calls_attempted':sum(v['QM_call_attempted'] for v in values),'native_task_timeout_seconds':900,
            'native_qm_termination_records':[{'qa_id':v['qa_id'],'termination':v.get('native_qm_termination')} for v in values],
            'actual_worker_pids':[p.pid for p in processes],'process_closure':[{'pid':p.pid,'exitcode':p.exitcode,'alive':p.is_alive()} for p in processes],
            'configured_max_workers':15,'errors':errors,'proven_not_dispatched_qa_ids':wanted[index:],
            'dispatched_without_return_qa_ids':sorted(set(wanted[:index])-{v['qa_id'] for v in values}),
            'causal_analysis_reference':analysis_ref,'budget':budget.report(),'production_once_ledger_opened':False,
            'actual_terminal_parent_accounting_append_required':True,'original15FAIL_preserved':True,'scientific_PASS':False,'full_or2000_release':'HOLD'}
        I.json_new(out/'receipt.json',receipt,out);return 0 if complete else 3
    finally:budget.close()


if __name__=='__main__':raise SystemExit(main())
