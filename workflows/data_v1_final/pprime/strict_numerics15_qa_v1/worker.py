"""Original initialized engine/native invoke, fresh private QA output partition."""
import copy,json,os,pathlib,tempfile,time,traceback
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime.common import staging_bytes,reference
from . import contract as C,io as W
Q=C.Q


def one(task_ref,claim_ref,source,session,out_path,deadline):
    plan=W.continuation(session);C.require_user(plan);old,new,_=C.protocol(plan)
    from workflows.data_v1_final.pprime.causal15_geometry_readonly_v1.run import body
    task=json.loads(body(task_ref,1<<20));claim=C.meta(claim_ref);qa=task['qa_id'];folder=pathlib.Path(out_path)/qa;folder.mkdir(mode=0o700)
    Q.need(claim['task_reference']==task_ref and claim['candidate_protocol_reference']==plan['candidate_protocol_reference']
        and claim['user_decision_reference']==plan['user_decision_reference'] and claim['original_qa_id']==task['original_qa_id']
        and claim['original_prepared_reference']==plan['original_prepared_reference'] and claim['job_id']==session['job_id'] and claim['uid']==1278 and claim['boot_id']==session['boot_id']
        and claim_ref['path']==str(C.LEDGER/(C.once_key(plan,plan['original_prepared_reference'],task['original_qa_id'])+'.json')),'EXACT_NEW_PROTOCOL_QA_ONCE_CLAIM')
    store=W.Store(folder,C.WORKER_CAP);engine=None;sink=None;scratch=None
    record={'schema':'PPRIME_STRICT_NUMERICS15_ACTUAL_QA_CALL_V1','qa_id':qa,'original_qa_id':task['original_qa_id'],'condition':task['condition'],'arm':task['arm'],
        'rotation_matrix':task['rotation_matrix'],'case':copy.deepcopy(task['case']),'origin_case':copy.deepcopy(task['case']),
        'origin_case_id':task['case']['case_id'],'task_reference':task_ref,'claim_reference':claim_ref,'candidate_protocol_reference':plan['candidate_protocol_reference'],
        'user_decision_reference':plan['user_decision_reference'],'production_membership':False,'QM_call_attempted':False,'new_native_call_budget':1,
        'original15FAIL_preserved':True,'original_WP5_unknown_cases_preserved':['qa-02','qa-08'],'scientific_PASS':False,'full_or2000_release':'HOLD'}
    try:
        start=store.json(folder/'worker_start.json',{'qa_id':qa,'job_id':session['job_id'],'uid':os.getuid(),'pid':os.getpid(),'pid_start_ticks':W.ticks(os.getpid()),
            'boot_id':session['boot_id'],'task_reference':task_ref,'claim_reference':claim_ref})
        record['worker_start_reference']=start;scratch=pathlib.Path(tempfile.mkdtemp(prefix='strictqa15_'+session['job_id']+'_'+qa+'_',dir='/tmp'))
        engine,legacy,original,pilot=T.engine(source,C.N.G.P.I.read)
        engine.initialize_worker(pilot['source_plan']['path'],protocol=plan['candidate_protocol_reference']['path'],node_scratch_root=str(scratch),deadline=deadline,
            audit_membership=source['audit_membership']['path'],reproduction_package=legacy['reproduction_package']['path'])
        record['invoke_identity']=T.invoke_identity(engine,original);frozen=next(t for t in engine.CONFIG['tasks'] if t['name']==task['case']['calc_type'])
        Q.need(frozen==task['original_task'] and engine.CONFIG['timeout_seconds']==900,'EXACT_CANDIDATE_TASK_NO_TIMEOUT_OVERRIDE')
        inputs={pathlib.Path(r['path']).name:body(r,C.O.INPUT_CAP) for r in task['target_input_references']}
        native,seed=T.bridge(task['case'],inputs,frozen,new,engine)
        Q.need(seed==task['seed'] and native['coords'].tolist()==task['native_coordinates_A'],'EXACT_SAME_SEED_AND_NATIVE_RENDER_BRIDGE')
        record['case'].update(case_id=qa,native_coordinates_A=native['coords'].tolist(),actual_rendered_coordinates_A=T.arrays(inputs,task['case']['symbols']).tolist(),
            expected_actual_coordinates_A=T.arrays(inputs,task['case']['symbols']).tolist())
        hashes,bundle=engine.rendered_input_hashes(frozen,native,task['case']['row'])
        Q.need(hashes==[{'name':n,'sha256':C.O.sha(b)} for n,b in sorted(inputs.items())],'EXACT_PRECALL_NEW_TARGET_SHA')
        store.json(folder/'invoke_intent.json',{'qa_id':qa,'state':'DURABLE_CALL_INTENT_NOT_RETURN','input_file_sha256':hashes,'input_bundle_sha256':bundle,
            'candidate_protocol_reference':plan['candidate_protocol_reference'],'user_decision_reference':plan['user_decision_reference'],'timeout_seconds':900,
            'old_record_id':task['case']['row']['record_id'],'seed':seed,'job_id':session['job_id']})
        engine.CAPTURED=engine.CALL_SCRATCH=engine.CAPTURE_ERROR=None
        Q.need(W.continuation(session)==plan,'SAME_LIVE_PARENT_AND_CURRENT_USER_AUTHORITY_IMMEDIATELY_BEFORE_INVOKE')
        Q.need(deadline-time.time()-30>=900,'FULL_ORIGINAL900_REMAINING_REQUIRED_NO_NATIVE_CALL')
        record['QM_call_attempted']=True
        result=engine.NATIVE.invoke(frozen,native,task['case']['row'],engine.WORK)
        record['native_invoke_function_return_observed']=True;record['native_qm_termination']=result.get('qm_termination');record['original_native_result_observation']=copy.deepcopy(result)
        Q.need(engine.CAPTURE_ERROR is None and engine.CALL_SCRATCH is not None,'ORIGINAL_NATIVE_RAW_CAPTURE_REQUIRED')
        actual=[]
        for name,expected in inputs.items():
            p=engine.CALL_SCRATCH/name;Q.need(p.stat().st_size<=C.O.INPUT_CAP,'ACTUAL_INPUT_CAP');data=p.read_bytes();Q.need(data==expected,'ACTUAL_POSTCALL_INPUT_EQUALS_NEW_PREPARED')
            actual.append(dict(store.write(folder/'actual_postcall_inputs'/name,data),matches_prepared_bytes=True))
        record['actual_postcall_input_references']=actual;files=engine.CAPTURED or []
        Q.need(files and len(engine.OUTPUT_ARCHIVE.bundle(files)[0])<=C.O.RAW_CAP,'ORIGINAL_RAW_CAP_NO_TRUNCATION')
        source_status=result['status'];result['source_status']=source_status;issues=engine.validate_atomic_arrays(result,native['z'])
        if issues and source_status=='SUCCESS':result.update(status='PROPERTY_FAILED',failure_code='REQUESTED_SCOPE_ATOMIC_ARRAY_QC_FAILED',failure_reason=' | '.join(issues))
        result['scope_status']=engine.canonical_status(result['status']);result['status']=result['scope_status']
        scf=engine.extract_scf(frozen['name'],files,result.get('values'),result['status'],source_status)
        result['provenance']={'status':result['status'],'software_version_id':engine.PACKAGE['software_versions'][frozen['family']]['software_version_id'],
            'elapsed_seconds':result.get('elapsed_seconds'),'scf_iterations':scf['scf_iterations'],'converged':scf['converged'],
            'input_file_sha256':hashes,'input_bundle_sha256':bundle,'candidate_protocol_reference':plan['candidate_protocol_reference']}
        result['raw_audit_selected']=True;record['parsed_wp5_result']=result
        context={'execution_id':'strict-numerics15:'+plan['candidate_protocol_reference']['sha256']+':'+session['job_id']+':'+qa,
            'job_id':int(session['job_id']),'audit_only':True,'QA_arm':task['arm'],'diagnostic_protocol_reference':plan['candidate_protocol_reference']}
        raw=engine.raw_record(frozen,task['case']['row'],result,files,context)
        from raw_archive import RawSink
        # Prepay both SQLite file and transient journal from this worker's fixed
        # partition. No resource observer stats their paths during mutation.
        store.reserve(2*C.O.RAW_CAP);sink=RawSink(folder/'all_output_raw.sqlite',engine.OUTPUT_ARCHIVE,C.O.RAW_CAP);ref=sink(raw)
        Q.need(ref.get('raw_call_durable') is True,'DURABLE_NATIVE_RAW_REQUIRED');record['raw_reference']=ref
        from read_outputs_v1 import parse_outputs
        record['independent_raw_readback']=parse_outputs(files,frozen['name'],task['case']['symbols']);record['status']='STRICT_QA_CALL_DURABLE_NO_RELEASE'
        record['scratch_bytes_removed_after_raw_commit']=engine.ORIGINAL_CLEANUP(engine.CALL_SCRATCH);engine.CALL_SCRATCH=None
    except BaseException as exc:
        record['error']={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        if engine is not None:engine.PRESERVE_ARCHIVE_FAILURE=True
    finally:
        if sink is not None:
            try:
                sink.close();p=folder/'all_output_raw.sqlite'
                Q.need(not any(pathlib.Path(str(p)+s).exists() for s in ('-wal','-shm','-journal')),'CLOSED_OWN_RAW_NO_SIDECAR')
                record['closed_raw_container_reference']=reference(p)
            except BaseException as exc:record['raw_close_error']=repr(exc)
        try:record['engine_close']=engine.close_worker() if engine is not None else {'initialized':False}
        except BaseException as exc:record['engine_close_error']=repr(exc)
        record['node_scratch_preserved']=str(scratch) if scratch is not None and any(scratch.iterdir()) else None
        if scratch is not None and not any(scratch.iterdir()):scratch.rmdir()
        encoded=staging_bytes(record)+b'\n';Q.need(len(encoded)<=C.O.RESULT_CAP,'ORIGINAL_RESULT_CAP_NO_TRUNCATION');saved=store.write(folder/'result.json',encoded)
        store.json(folder/'finished.json',{'qa_id':qa,'result_reference':saved,'QM_call_attempted':record['QM_call_attempted'],
            'native_invoke_function_return_observed':record.get('native_invoke_function_return_observed',False),'error':record.get('error'),
            'original_source_or_return_state_not_backfilled':True,'unknown_never_automatically_retried':True,'private_partition_charged_bytes':store.charged})
    return saved
