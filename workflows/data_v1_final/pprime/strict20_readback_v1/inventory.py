"""CPU A: inventory only the specifically closed run and actual prepared20."""
from __future__ import annotations
import pathlib
from . import contract as C,io as I,checks as K

def produce(plan,parent,out,store,check):
    review,ep,declared,_,prepare_root,_=parent;roots=[C.ACTUAL,prepare_root,C.E.LEDGER];execution_proof=C.meta(review['startup_proof_reference'])
    receipt=I.value(review['receipt_reference'],roots,declared);prepared=I.value(ep['prepared20_reference'],roots,declared)
    analysis_ref=review['analysis_DATA_locator_not_opened_or_hashed_on_login'];analysis=I.value(analysis_ref,roots,declared)
    K.index_analysis(analysis)
    C.need(receipt['schema']=='PPRIME_NEW20_ALL12_QA_RECEIPT_V1'
        and receipt['status']=='ALL1200_TECHNICALLY_CLOSED_DEFINED_QA_RECORDED_SEMANTICS_UNKNOWN_ROOT_REVIEW'
        and str(receipt['job_id'])==C.JOB and receipt['uid']==1278 and receipt['node']=='compute-0-13'
        and receipt['endpoint']=='202.38.247.57:22' and receipt['plan_reference']==review['plan_reference']
        and receipt['startup_proof_reference']==review['startup_proof_reference'] and receipt['analysis_reference']==analysis_ref
        and receipt['prepared20_reference']==ep['prepared20_reference'] and receipt['user_decision_reference']==ep['user_decision_reference']
        and receipt['candidate_protocol_reference']==ep['candidate_protocol_reference'],'EXACT_ACTUAL_RECEIPT_LINEAGE')
    C.need(receipt['maximum_new_QM_calls']==receipt['consumed_dispatch_intents']==receipt['returned_terminals']==receipt['verified_closed25M_roles']==1200
        and receipt['original_vector_comparison_checks']==500 and receipt['all1200_defined_diagnostic_checks_complete'] is True
        and receipt['known_actual_native_counts_from_returned_terminals']=={'QM_call_attempted':1200,'native_return_observed':1200}
        and not receipt['errors'] and not receipt['preserved112M_UNKNOWN_roles'] and not receipt['proven_not_dispatched']
        and not receipt['parent_error_without_returned_future_roles'] and receipt['automatic_retry'] is False
        and receipt['scientific_PASS'] is False and receipt['full_or2000_release']=='HOLD'
        and len(receipt['process_closure'])==16 and all(r['exitcode']==0 and r['alive'] is False for r in receipt['process_closure']),
        'ACTUAL1200_CLOSED_NO_UNKNOWN_OR_LIVE_WORKERS')
    pp=C.meta(prepared['plan_reference']);proof=C.meta(prepared['startup_proof_reference'])
    C.F.account(ep['prepare_accounting_reference'],str(prepared['job_id']),prepared['node'])
    C.need(prepared['schema']=='PPRIME_NEW20_ALL12_ZERO_INVOKE_PREPARED_V1'
        and prepared['status']=='ACTUAL_NEW20_1200_INPUTS_PREPARED_NOT_EXECUTION_AUTHORITY'
        and prepared['actual_input_sets']==1200 and prepared['uid']==1278 and prepared['endpoint']=='202.38.247.57:22'
        and prepared['new_QM_calls']==prepared['native_invoke_attempts']==0 and prepared['original_protocol_initialize_calls']==1
        and prepared['candidate_protocol_initialize_calls']==0 and pp['output_directory']==str(prepare_root)
        and str(proof['job_id'])==str(prepared['job_id']) and proof['request']['scope_key']==C.E.P.KEY
        and proof['request']['scope_parameters']==C.E.P.PARAMETERS and pp['scope_parameters']==C.E.P.PARAMETERS,
        'ACTUAL_PREPARE_C0_TRANSITIVE_ROOT_NOT_FUTURE_PREPARATION')
    gate=C.meta(prepared['fixtures_reference']);C.need(gate['tests_run']==3 and all(gate[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_PREPARE3_PASSED')
    tasks=C.E.matrix(prepared['tasks']);terminals=receipt['terminal_references'];claims=receipt['claim_references']
    C.need(len(terminals)==len(claims)==1200 and len({r['path'] for r in terminals})==len({r['path'] for r in claims})==1200,'EXACT_UNIQUE1200_TERMINALS_CLAIMS')
    terms={pathlib.Path(r['path']).parent.name:r for r in terminals};claim_by_path={r['path']:r for r in claims}
    all_rows=[];all_refs=[]
    for qa in sorted(tasks):
        check();row=tasks[qa];task_ref=C.triple(row['task_reference']);C.need(task_ref in ep['data_references'],'ORIGINAL_EXACT_DECLARED1200_TASK_PIN')
        from workflows.data_v1_final.pprime.strict_numerics20_qa_v1.io import task as original_task
        with I.held(task_ref,roots):task=original_task(task_ref,row,ep)
        tr=C.triple(terms[qa]);C.need(tr['path']==str(C.ACTUAL/qa/'finished.json'),'EXACT_ACTUAL_TERMINAL_PATH')
        terminal=I.value(tr,roots);rr=C.triple(terminal['result_reference']);C.need(rr['path']==str(C.ACTUAL/qa/'result.DATA.json'),'EXACT_ACTUAL_RESULT_PATH')
        result=I.value(rr,roots);claim_ref=C.triple(result['claim_reference']);once=C.E.once_key(ep,qa)
        C.need(claim_ref['path']==str(C.E.LEDGER/(once+'.json')) and claim_by_path.get(claim_ref['path'])==claim_ref,'ORIGINAL_ONCE_LEDGER_MEMBERSHIP_ONLY_READ')
        claim=I.value(claim_ref,roots,cap=1<<20);K.identity(row,task,result,claim,ep)
        C.need(claim['startup_proof_reference']==review['startup_proof_reference'] and claim['boot_id']==execution_proof['boot_id'],
            'ACTUAL_ONCE_CLAIM_BOOT_AND_ORIGINAL_STARTUP_PROOF')
        C.need(terminal['schema']=='PPRIME_NEW20_CALL_TERMINAL_V1' and terminal['qa_id']==qa
            and terminal['QM_call_attempted'] is True and terminal['native_return_observed'] is True
            and terminal['call_technical_readback_complete'] is True and terminal['closed25M_role_eligible'] is True
            and terminal['otherwise112M_UNKNOWN_preserved'] is False and terminal['automatic_retry'] is False
            and terminal['original_return_state_not_backfilled'] is True and terminal['node_scratch_preserved'] is None
            and terminal['oversized_original_result_reference'] is None and terminal['untruncated_original_result_bytes']==rr['bytes'],
            'CLOSED25M_ORIGINAL_TERMINAL_STATE')
        C.need(result['schema']=='PPRIME_NEW20_ALL12_ACTUAL_QA_CALL_V1' and result['QM_call_attempted'] is True
            and result['native_invoke_function_return_observed'] is True and result['production_membership'] is False
            and result['original15FAIL_preserved'] is True and result['scientific_PASS'] is False and result['full_or2000_release']=='HOLD'
            and not any(result.get(k) for k in ('error','raw_close_error','engine_close_error')),'PRESERVED_ORIGINAL_NATIVE_RETURN_NOT_BACKFILLED')
        refs=[task_ref,tr,rr,claim_ref]
        expected_inputs={'input.xyz','input.mop'} if task['candidate_task']['family']=='mopac' else {'input.xyz','native.inp'}
        for key,sub in (('target_input_references','candidate_targets'),('original_target_input_references','original_targets')):
            inputs=task[key];C.need({pathlib.Path(r['path']).name for r in inputs}==expected_inputs and len(inputs)==2,'EXACT_ORIGINAL_AND_STRICT_INPUT_NAMES')
            for r in inputs:C.need(r['path']==str(prepare_root/sub/qa/pathlib.Path(r['path']).name),'PREPARED_INPUT_EXACT_PATH');refs.append(C.triple(r))
        post=result['actual_postcall_input_references'];C.need(len(post)==2 and {pathlib.Path(r['path']).name for r in post}==expected_inputs
            and all(r['matches_prepared_bytes'] is True for r in post),'ACTUAL_POSTCALL_INPUT_NAMES_AND_ORIGINAL_MATCH_FLAGS')
        for r in post:C.need(r['path']==str(C.ACTUAL/qa/'actual_postcall_inputs'/pathlib.Path(r['path']).name),'ACTUAL_POSTCALL_INPUT_PATH');refs.append(C.triple(r))
        for key,name in (('worker_start_reference','worker_start.json'),('invoke_intent_reference','invoke_intent.json'),('closed_raw_container_reference','all_output_raw.sqlite')):
            r=C.triple(result[key]);C.need(r['path']==str(C.ACTUAL/qa/name),'EXACT_CALL_LOCAL_LINEAGE_NAME');refs.append(r)
        C.need(terminal['closed_raw_container_reference']==result['closed_raw_container_reference'],'TERMINAL_RESULT_WHOLE_RAW_PIN_PARITY')
        inventory=terminal['quiescent_file_inventory'];seen=set();n=0
        for entry in inventory:
            rel=pathlib.PurePosixPath(entry['relative_path']);C.need(not rel.is_absolute() and '..' not in rel.parts and str(rel) not in seen
                and type(entry['bytes'])is int and entry['bytes']>0,'FINITE_ORIGINAL_QUIESCENT_FILE_CENSUS')
            seen.add(str(rel));pin=I.discover(C.ACTUAL/qa/str(rel),roots);C.need(pin['bytes']==entry['bytes'],'CURRENT_QUIESCENT_CENSUS_BYTES');refs.append(pin);n+=pin['bytes']
        current=set();visited=0
        for p in (C.ACTUAL/qa).rglob('*'):
            visited+=1;C.need(not p.is_symlink() and visited<=128,'BOUNDED_NO_SYMLINK_CLOSED_CALL_CENSUS')
            if p.is_file():I.safe(p);current.add(str(p.relative_to(C.ACTUAL/qa)))
            else:C.need(p.is_dir(),'ONLY_REGULAR_FILES_AND_DIRECTORIES_IN_CLOSED_CALL')
        C.need(current==seen|{'finished.json'} and n==terminal['quiescent_bytes_before_terminal']
            and n+tr['bytes']<=C.E.CLOSED_CAP,'FULL_CLOSED25M_ROLE_RECHECK_EXACT_CENSUS_NO_EXTRA_OR_MISSING')
        refs=C.unique(refs)
        for r in refs:
            check()
            with I.held(r,roots):pass
        all_rows.append({'qa_id':qa,'row':row,'task_reference':task_ref,'terminal_reference':tr,'result_reference':rr,
            'claim_reference':claim_ref,'data_references':refs})
        all_refs.extend(refs)
    groups=[]
    for i in range(20):
        rows=[r for r in all_rows if K.qa_cell(r['qa_id'])[0]==i];C.need(len(rows)==60,'EXACT60_ORIGINAL_CELLS_PER_GROUP')
        descriptor=store.json(out/('group_%02d.DATA.json'%i),{'schema':'STRICT20_READBACK_GROUP_DESCRIPTOR_V1','group_index':i,'rows':rows,
            'original_analysis_reference':analysis_ref,'execution_plan_reference':review['plan_reference'],'actual_output_root':str(C.ACTUAL),
            'actual_prepared_root':str(prepare_root),'all_numeric_values_remain_in_original_DATA':True})
        refs=C.unique([descriptor,analysis_ref,C.audit_ref(),*[r for row in rows for r in row['data_references']]])
        groups.append(store.json(out/('group_%02d.locators.json'%i),{'schema':'STRICT20_READBACK_GROUP_LOCATORS_V1','group_index':i,'calls':60,
            'descriptor_reference':descriptor,'data_references':refs,'actual_root_review_reference':plan['actual_root_review_reference'],
            'input_raw_values_opened_only_on_CPU':True,'source_inventory_manifest_is_not_QM_or_physical_release':True}))
    return {'completed_calls':1200,'held_calls':0,'groups':groups,'actual_transitive_positive_DATA_files':len(C.unique(all_refs)),
        'actual_closed25M_roles':1200,'original_vector_comparisons_located_not_yet_replayed':500,
        'native_attempt_flags_are_not_independent_Popen_or_PID_audit':True}
