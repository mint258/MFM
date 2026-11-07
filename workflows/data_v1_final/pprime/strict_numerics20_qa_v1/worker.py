"""One consumed NEW20 claim -> at most one unchanged native invoke,all raw retained."""
import copy,json,os,pathlib,tempfile,threading,time,traceback
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T
from workflows.data_v1_final.pprime.common import staging_bytes,reference
from workflows.data_v1_final.pprime.causal15_main_v1.prepare import raw_reader
from . import contract as C,io as W,resources as R
Q=C.Q;STOP=None
def init(stop):
    global STOP
    STOP=stop  # Scheduling only. Never passed to the original native lifecycle.

def one(expected,claim_ref,source,session,out_path,deadline):
    plan=W.continuation(session);C.require_user(plan);old,new,_=C.P.S.protocol(plan);Q.need(STOP is not None,'ACTUAL_PARENT_SOFT_STOP_CHANNEL')
    task_ref=expected['task_reference'];task=W.task(task_ref,expected,plan);claim=C.meta(claim_ref);qa=task['qa_id']
    Q.need(claim['qa_id']==qa and claim['task_reference']==task_ref and claim['candidate_protocol_reference']==plan['candidate_protocol_reference']
        and claim['prepared20_reference']==plan['prepared20_reference'] and claim['user_decision_reference']==plan['user_decision_reference']
        and claim['job_id']==session['job_id'] and claim['uid']==1278 and claim['boot_id']==session['boot_id']
        and claim_ref['path']==str(C.LEDGER/(C.once_key(plan,qa)+'.json')),'EXACT_NEW_PROTOCOL_PREPARED20_ONCE_CLAIM')
    folder=pathlib.Path(out_path)/qa;folder.mkdir(mode=0o700);store=W.Store(folder,C.WORKER_CAP)
    engine=None;sink=None;scratch=None;observer=None;watcher=None;watch_done=threading.Event()
    record={'schema':'PPRIME_NEW20_ALL12_ACTUAL_QA_CALL_V1','qa_id':qa,'molecule_id':task['molecule_id'],'condition':task['condition'],'arm':task['arm'],
        'rotation_matrix':task['case']['rotation_matrix'],'case':copy.deepcopy(task['case']),'task_reference':task_ref,'claim_reference':claim_ref,
        'candidate_protocol_reference':plan['candidate_protocol_reference'],'prepared20_reference':plan['prepared20_reference'],
        'user_decision_reference':plan['user_decision_reference'],'production_membership':False,'QM_call_attempted':False,
        'original15FAIL_preserved':True,'original_WP5_unknown_cases_preserved':['qa-02','qa-08'],'scientific_PASS':False,'full_or2000_release':'HOLD'}
    try:
        Q.need(not STOP.is_set(),'STOP_NEW_CALL_BEFORE_INITIALIZE')
        record['worker_start_reference']=store.json(folder/'worker_start.json',{'qa_id':qa,'job_id':session['job_id'],'uid':os.getuid(),'pid':os.getpid(),
            'pid_start_ticks':W.ticks(os.getpid()),'boot_id':session['boot_id'],'task_reference':task_ref,'claim_reference':claim_ref})
        scratch=pathlib.Path(tempfile.mkdtemp(prefix='strict20_'+session['job_id']+'_'+qa+'_',dir='/tmp'));observer=R.Scratch(scratch,STOP)
        def watch():
            while not watch_done.wait(1):observer.observe()
        observer.observe();watcher=threading.Thread(target=watch,name='owned_scratch_observation',daemon=False);watcher.start()
        engine,legacy,original,pilot=T.engine(source,C.meta)
        # No resource stop_event is supplied: running native work may naturally
        # finish. Only its ORIGINAL deadline/900s timeout semantics can interrupt.
        engine.initialize_worker(pilot['source_plan']['path'],protocol=plan['candidate_protocol_reference']['path'],node_scratch_root=str(scratch),deadline=deadline,
            audit_membership=plan['audit_membership_reference']['path'],reproduction_package=legacy['reproduction_package']['path'])
        record['invoke_identity']=T.invoke_identity(engine,original);frozen=next(t for t in engine.CONFIG['tasks'] if t['name']==task['condition'])
        Q.need(frozen==task['candidate_task'] and engine.CONFIG['timeout_seconds']==900,'ONLY_ACTUAL_FROZEN_CANDIDATE_TASK_NO_OVERRIDE')
        inputs={pathlib.Path(r['path']).name:W.body(r,C.O.INPUT_CAP) for r in task['target_input_references']}
        native,seed=T.bridge(task['case'],inputs,frozen,new,engine)
        Q.need(seed==task['seed'] and native['coords'].tolist()==task['native_coordinates_A'],'EXACT_ACTUAL_PREPARED_NATIVE_BRIDGE_AND_SEED')
        record['case'].update(native_coordinates_A=native['coords'].tolist(),actual_rendered_coordinates_A=T.arrays(inputs,task['case']['symbols']).tolist())
        hashes,bundle=engine.rendered_input_hashes(frozen,native,task['case']['row'])
        Q.need(hashes==[{'name':n,'sha256':C.O.sha(b)} for n,b in sorted(inputs.items())],'EXACT_ACTUAL_PRECALL_TARGET_SHA')
        record['invoke_intent_reference']=store.json(folder/'invoke_intent.json',{'qa_id':qa,'state':'DURABLE_INTENT_NOT_NATIVE_RETURN','input_file_sha256':hashes,
            'input_bundle_sha256':bundle,'candidate_protocol_reference':plan['candidate_protocol_reference'],'user_decision_reference':plan['user_decision_reference'],
            'prepared20_reference':plan['prepared20_reference'],'timeout_seconds':900,'original_record_id':task['case']['row']['record_id'],'seed':seed,'job_id':session['job_id']})
        engine.CAPTURED=engine.CALL_SCRATCH=engine.CAPTURE_ERROR=None
        Q.need(W.continuation(session)==plan and not STOP.is_set(),'LIVE_PARENT_AUTHORITY_AND_SOFT_STOP_BEFORE_INVOKE')
        Q.need(deadline-time.time()-30>=900,'FULL_ORIGINAL900_REMAINING_NO_SHORTENED_CALL')
        record['QM_call_attempted']=True
        result=engine.NATIVE.invoke(frozen,native,task['case']['row'],engine.WORK)
        record['native_invoke_function_return_observed']=True;record['original_native_result_observation']=copy.deepcopy(result)
        record['native_qm_termination']=result.get('qm_termination')
        Q.need(not(result.get('preserved_scratch') and result.get('scratch_cleanup_error')),'ORIGINAL_NATIVE_LIVE_OR_UNVERIFIED_PROCESS_SCRATCH_PRESERVED_HOLD')
        Q.need(engine.CAPTURE_ERROR is None and engine.CALL_SCRATCH is not None,'ACTUAL_ORIGINAL_RAW_CAPTURE_REQUIRED')
        actual=[]
        for name,expected_body in inputs.items():
            p=engine.CALL_SCRATCH/name;Q.need(p.stat().st_size<=C.O.INPUT_CAP,'ACTUAL_POSTCALL_INPUT_BOUND')
            data=p.read_bytes();Q.need(data==expected_body,'ACTUAL_POSTCALL_BYTES_EQUAL_PREPARED')
            actual.append(dict(store.write(folder/'actual_postcall_inputs'/name,data),matches_prepared_bytes=True))
        record['actual_postcall_input_references']=actual;files=engine.CAPTURED or []
        Q.need(files and len(engine.OUTPUT_ARCHIVE.bundle(files)[0])<=C.O.RAW_CAP,'ORIGINAL_RAW16M_CAP_NO_TRUNCATION')
        # Same original per-task enrichment/physical array checks as engine;
        # retain original return status separately, never backfill missing state.
        source_status=result['status'];result['source_status']=source_status;result['atomic_array_validation']=engine.validate_atomic_arrays(result,native['z'])
        if result['atomic_array_validation'] and source_status=='SUCCESS':result.update(status='PROPERTY_FAILED',failure_code='REQUESTED_SCOPE_ATOMIC_ARRAY_QC_FAILED',failure_reason=' | '.join(result['atomic_array_validation']))
        result['status']=engine.canonical_status(result['status']);result['scope_status']=result['status'];result['parser_context']=engine.PARSER.context()
        scf=engine.extract_scf(frozen['name'],files,result.get('values'),result['status'],source_status)
        result['provenance']={'status':result['status'],'software_version_id':engine.PACKAGE['software_versions'][frozen['family']]['software_version_id'],
            'elapsed_seconds':result.get('elapsed_seconds'),'scf_iterations':scf['scf_iterations'],'converged':scf['converged'],
            'input_file_sha256':hashes,'input_bundle_sha256':bundle,'scf_iteration_definition':scf['iteration_definition'],'scf_missing_reason':scf['missing_reason'],
            'candidate_protocol_reference':plan['candidate_protocol_reference']}
        result['raw_audit_selected']=True;result['reproduction_package_sha256']=engine.PACKAGE_SHA
        result['precision_by_field']=result['parser_context'].get('rounding_decimal_places',{});result['registry_source_evidence']=engine.concise_source_evidence(result,files)
        record['parsed_wp5_result']=result
        context={'execution_id':'strict-new20:'+plan['candidate_protocol_reference']['sha256']+':'+session['job_id']+':'+qa,'job_id':int(session['job_id']),
            'audit_only':True,'QA_arm':task['arm'],'diagnostic_protocol_reference':plan['candidate_protocol_reference']}
        raw=engine.raw_record(frozen,task['case']['row'],result,files,context)
        from raw_archive import RawSink
        store.reserve(2*C.O.RAW_CAP);sink=RawSink(folder/'all_output_raw.sqlite',engine.OUTPUT_ARCHIVE,C.O.RAW_CAP);ref=sink(raw)
        Q.need(ref.get('raw_call_durable') is True,'ALL1200_NATIVE_RAW_RETENTION_REQUIRED');record['raw_reference']=ref;sink.close();sink=None
        db=folder/'all_output_raw.sqlite';Q.need(not any(pathlib.Path(str(db)+s).exists() for s in ('-wal','-shm','-journal')),'CLOSED_RAW_NO_SIDECAR')
        before=reference(db);reader=raw_reader()(db,engine.OUTPUT_ARCHIVE,C.O.RAW_CAP,C.O.RESULT_CAP)
        try:retained=reader.get(ref['record_id'],ref['calc_type'],ref['execution_id'],ref['raw_sha256'],ref['raw_bytes'])
        finally:reader.close()
        Q.need(reference(db)==before and retained['metadata']['input_file_sha256']==hashes and retained['metadata']['input_bundle_sha256']==bundle,'CLOSED_WHOLE_SHA_RAW_MEMBER_AND_INPUT_READBACK')
        record['closed_raw_container_reference']=before
        from read_outputs_v1 import parse_outputs
        record['independent_raw_readback']=parse_outputs(retained['output_files'],frozen['name'],task['case']['symbols'])
        record['raw_readback_source']='CLOSED_SQLITE_GZIP_EOF_CRC_WHOLE_AND_MEMBER_SHA_ORIGINAL_UNBUNDLE'
        record['status']='NEW20_CALL_RAW_RETAINED_NO_SCIENTIFIC_RELEASE'
        # End private observation before deliberate directory deletion, so a
        # normal cleanup cannot reproduce the old disappearing-tree race.
        watch_done.set();watcher.join();observer.observe()
        record['scratch_bytes_removed_after_raw_readback']=engine.ORIGINAL_CLEANUP(engine.CALL_SCRATCH)
        engine.CAPTURED=None;engine.CALL_SCRATCH=None;engine.CAPTURE_ERROR=None  # original compute_molecule per-task release
        if result['scope_status']!='SUCCESS' or result['atomic_array_validation']:STOP.set()
    except BaseException as exc:
        STOP.set();record['error']={'type':type(exc).__name__,'message':str(exc),'traceback':traceback.format_exc()}
        if engine is not None:engine.PRESERVE_ARCHIVE_FAILURE=True
    finally:
        if sink is not None:
            try:sink.close()
            except BaseException as exc:record['raw_close_error']=repr(exc)
        try:record['engine_close']=engine.close_worker() if engine is not None else {'initialized':False}
        except BaseException as exc:record['engine_close_error']=repr(exc);STOP.set()
        watch_done.set()
        if watcher is not None:watcher.join()
        if observer is not None:observer.observe();record['scratch_observation']=observer.report()
        record['node_scratch_preserved']=str(scratch) if scratch is not None and scratch.exists() and any(scratch.iterdir()) else None
        if scratch is not None and scratch.exists() and not any(scratch.iterdir()):scratch.rmdir()
        encoded=staging_bytes(record)+b'\n';saved=None;oversized=None
        if len(encoded)<=C.O.RESULT_CAP:saved=store.write(folder/'result.DATA.json',encoded)
        else:
            STOP.set()
            # Never truncate a large result. Preserve within112M if possible;
            # otherwise the committed raw/original scratch stay authoritative.
            if store.charged+len(encoded)+(2<<20)<C.WORKER_CAP:oversized=store.write(folder/'oversized_result.DATA.json',encoded)
        actual,inventory=W.quiescent(folder)
        valid=saved is not None and not any(record.get(k) for k in ('error','raw_close_error','engine_close_error')) and bool(record.get('closed_raw_container_reference'))
        terminal_value={'schema':'PPRIME_NEW20_CALL_TERMINAL_V1','qa_id':qa,'result_reference':saved,'oversized_original_result_reference':oversized,
            'untruncated_original_result_bytes':len(encoded),'QM_call_attempted':record['QM_call_attempted'],'native_return_observed':record.get('native_invoke_function_return_observed',False),
            'call_technical_readback_complete':valid,'quiescent_bytes_before_terminal':actual,'quiescent_file_inventory':inventory,
            'closed25M_role_eligible':False,'otherwise112M_UNKNOWN_preserved':True,
            'node_scratch_preserved':record.get('node_scratch_preserved'),'closed_raw_container_reference':record.get('closed_raw_container_reference'),
            'private_partition_charged_bytes_before_terminal':store.charged,'automatic_retry':False,'original_return_state_not_backfilled':True}
        terminal_bytes=len(C.O.canonical(terminal_value))+1;Q.need(terminal_bytes<=1<<20,'BOUNDED_TERMINAL_METADATA')
        eligible=valid and actual+terminal_bytes<=C.CLOSED_CAP
        terminal_value.update(closed25M_role_eligible=eligible,otherwise112M_UNKNOWN_preserved=not eligible)
        Q.need(len(C.O.canonical(terminal_value))+1==terminal_bytes,'EXACT_TERMINAL_ROLE_SIZE_NO_GUESSED_MARGIN')
        if not eligible:STOP.set()
        terminal=store.json(folder/'finished.json',terminal_value)
    return terminal
