"""New recovered-pilot closure; original TIMEOUT never becomes original C0."""
from __future__ import annotations
import argparse,concurrent.futures as cf,json,sys
from collections import Counter
from pathlib import Path
from recovery_common import (IO,MISSING,bind_inputs,load_plan,named,packet_reader,read_packet,
    require,require_sources,scientific_sha,small_load,task_sha,terminal_parents,expected_seed)

def merged_refs(closed,new):
    old={r['molecule_id']:r['reference'] for r in closed}
    added={r['molecule_id']:r for r in new}
    require(len(old)==334 and len(added)==len(new)==2 and set(added)==set(MISSING),'EXACT334_OLD_AND_TWO_NEW_REQUIRED')
    require(not set(old)&set(added),'REPLAY_CONTROLS_CANNOT_REPLACE_OR_JOIN_POPULATION')
    refs=[old[mid] for mid in sorted(old)]+[added[mid] for mid in sorted(added)]
    require(len({r['molecule_id'] for r in refs})==336 and len({r['path'] for r in refs})==336,'336_UNIQUE_UNION_PACKAGES_REQUIRED')
    return sorted(refs,key=lambda r:r['molecule_id'])

def require_original_identity(row):
    path=Path(row['reference']['path']);st=path.stat();expected=row['file_identity']
    actual={'device':st.st_dev,'inode':st.st_ino,'bytes':st.st_size,'mtime_ns':st.st_mtime_ns,'uid':st.st_uid}
    require(actual==expected,'ORIGINAL334_PACKAGE_IDENTITY_CHANGED')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--recovery-receipt',type=Path,required=True)
    p.add_argument('--recovery-submission',type=Path,required=True);p.add_argument('--sacct-evidence',type=Path,required=True)
    p.add_argument('--root-preflight',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime_v2 as runtime
    proof=runtime.root_guard(a.root_preflight,a.plan,1024**3,3600);request=proof['request']
    require(request['scope_key']=='sprime_pilot_closure_336' and request['scope_parameters']==
        {'expected_molecules':336,'original_pilot_job':'4520364','new_UFF_QM_calls':0},'READONLY336_CLOSURE_SCOPE_REQUIRED')
    for path in (a.plan,a.recovery_receipt,a.recovery_submission,a.sacct_evidence):
        require(IO.reference(path) in request['source_references'],'ACTUAL_NEW_CLOSURE_AUTHORITY_NOT_PINNED')
    require_sources(request['source_references'])
    require(not a.output.exists(),'NEW_RECOVERED_CLOSURE_OUTPUT_REQUIRED')
    value=load_plan(a.plan,approved=True);audit,closed,tasks=bind_inputs(value)
    monitor=small_load(value['partial_audit_monitor_closure'])
    require(monitor['job_id']=='4520527' and monitor['status']=='COMPLETED_NO_MEMORY_DENIAL' and
            monitor['durable_evidence_exported'] is True,'REAL_PARTIAL_AUDIT_MONITOR_CLOSED_REQUIRED')
    receipt=json.loads(a.recovery_receipt.read_text());submission=json.loads(a.recovery_submission.read_text())
    require(receipt['schema']=='SPRIME_MISSING_RECOVERY_EXECUTION_RECEIPT_V1' and
        receipt['status']=='RECOVERY_PHYSICAL_EXECUTIONS_COMPLETE_REQUIRES_NEW_CLOSURE','COMPLETE_NEW_RECOVERY_REQUIRED')
    require(receipt['plan_reference']==IO.reference(a.plan) and receipt['partial_audit_report']==value['partial_audit_report'],'RECOVERY_PLAN_OR_PARTIAL_CHAIN_CHANGED')
    require(receipt['new_logical_retries']==0 and receipt['new_seeds']==0 and
            receipt['physical_executions_closed']==16 and receipt['actual_completed_worker_identities']==16 and
            receipt['resource_denial'] is None and receipt['monitor_thread_closed'] is True and
            receipt['signals_sent'] is False and receipt['scientific_recipe_changed'] is False,'REPLAY_OR_RESOURCE_GATES_NOT_CLOSED')
    job=str(receipt['runtime']['job_id'])
    require(job not in {'4520364','4520527'} and str(submission['job_id'])==job,'NEW_ACTUAL_RECOVERY_SUBMISSION_REQUIRED')
    intent=small_load(receipt['root_preflight'])
    require(submission['request']==intent['request'] and intent['request']['kind']=='conformer' and
        intent['request']['memory_gib']==64 and intent['request']['pilot'] is True,'STRICT_NEW_GENERATION_INTENT_REQUIRED')
    require(IO.reference(a.plan) in intent['request']['source_references'],'RECOVERY_GENERATION_PLAN_NOT_PINNED')
    approval=small_load(receipt['approval_reference'])
    require(approval.get('status')=='APPROVED_FOR_THIS_RECOVERY_ONLY' and
            approval.get('plan_reference')==IO.reference(a.plan),'NEW_GENERATION_DECISION_NOT_BOUND')
    rows=small_load(named(receipt['outputs'],'physical_executions.json'))
    require(len(rows)==16 and len({r['molecule_id'] for r in rows})==16,'16_UNIQUE_PHYSICAL_EXECUTION_ROWS_REQUIRED')
    require(not small_load(named(receipt['outputs'],'errors.json')),'RECOVERY_EXECUTION_ERRORS_PRESENT')
    controls={r['molecule_id']:r for r in rows if r['role']=='independent_same_seed_replay_control'}
    missing={r['molecule_id']:r for r in rows if r['role']=='missing_original_task_reexecution'}
    require(set(controls)==set(value['replay_control_ids']) and set(missing)==set(MISSING),'EXACT_CONTROL_AND_MISSING_ROLES_REQUIRED')
    require(len({(r['worker_identity']['pid'],r['worker_identity']['start_ticks']) for r in rows})==16,'ACTUAL16_DISTINCT_WORKER_IDENTITIES_REQUIRED')
    for row in rows:
        require(row['seed']==expected_seed(tasks[row['molecule_id']]),'RECOVERY_EXECUTION_SEED_CHANGED')
        require(row['original_task_sha256']==task_sha(tasks[row['molecule_id']]) and
                row['worker_identity']['job_id']==job and row['worker_identity']['uid']==1278 and
                row['new_logical_retry'] is False and row['additional_physical_execution'] is True,'ORIGINAL_TASK_OR_EXECUTION_PROVENANCE_CHANGED')
    validator=packet_reader();old_by_id={r['molecule_id']:r for r in closed}
    for mid,row in controls.items():
        runtime.checkpoint();original,_=read_packet(old_by_id[mid]['reference'],tasks[mid],validator)
        replay,_=read_packet(row['package_reference'],tasks[mid],validator)
        require(row['same_seed_control_exact_match'] is True and
                scientific_sha(original)==scientific_sha(replay)==row['scientific_sha256_excluding_summary_elapsed_seconds'],
                'INDEPENDENT_SAME_SEED_CONTROL_DRIFT')
    refs=merged_refs(closed,receipt['new_missing_packages'])
    for mid,row in missing.items():require(row['package_reference']==next(r for r in refs if r['molecule_id']==mid),'MISSING_PACKAGE_REFERENCE_CHANGED')
    packets={};details=[];iterator=iter(refs);active={};exhausted=False
    def read(ref):
        mid=ref['molecule_id']
        if mid in old_by_id:require_original_identity(old_by_id[mid])
        packet,detail=read_packet(ref,tasks[mid],validator)
        require(packet['summary']['seed']==expected_seed(tasks[mid]),'ORIGINAL_DETERMINISTIC_SEED_CHANGED')
        if mid in old_by_id:require_original_identity(old_by_id[mid])
        return mid,packet,detail
    with cf.ThreadPoolExecutor(max_workers=16) as pool:
        while active or not exhausted:
            runtime.checkpoint()
            while len(active)<16 and not exhausted:
                try:ref=next(iterator)
                except StopIteration:exhausted=True;break
                active[pool.submit(read,ref)]=ref['molecule_id']
            done,_=cf.wait(active,timeout=.5,return_when=cf.FIRST_COMPLETED)
            for future in done:
                active.pop(future);mid,packet,detail=future.result();packets[mid]=packet;details.append(detail)
    require(set(packets)==set(tasks) and len(details)==336,'UNION_PACKAGE_COVERAGE_INCOMPLETE')
    evidence=json.loads(a.sacct_evidence.read_text())
    require(evidence['schema']=='DATA_V1_SACCT_QUERY_EVIDENCE_V1' and evidence['query_returncode']==0 and
        Path(evidence['command_argv'][0]).name=='sacct','REAL_ROOT_SACCT_QUERY_REQUIRED')
    parents=terminal_parents(IO.require_pin(evidence['raw_sacct_reference']).read_text())
    require(set(map(str,evidence['requested_parent_job_ids']))==set(parents),'QUERY_PARENT_SET_CHANGED')
    require(parents['4520364']['state']=='TIMEOUT' and parents['4520364']['allocated_core_seconds']==230800,'ORIGINAL_TIMEOUT_AND_COST_MUST_REMAIN')
    require(parents[job]['state']=='COMPLETED' and parents[job]['exit_code']=='0:0' and parents[job]['alloc_cpus']==16,'NEW_RECOVERY_PARENT_C0_REQUIRED')
    require(parents['4520527']['state']=='COMPLETED' and parents['4520527']['exit_code']=='0:0','PARTIAL_AUDIT_PARENT_C0_REQUIRED')
    generation_cost=parents['4520364']['allocated_core_seconds']+parents[job]['allocated_core_seconds']
    root=value['external_output_root'];storage=dict(value,max_output_bytes=1024**3)
    out=IO.new_output_directory(a.output,storage)
    from run_pilot import parquet_new,verify_readback
    from statistics_tools import aggregate_statistics
    ordered=[packets[mid] for mid in sorted(packets)]
    summaries=[packet['summary'] for packet in ordered]
    geometries=sorted((row for packet in ordered for row in packet['conformers']),key=lambda r:(r['molecule_id'],r['sprime_conf_idx']))
    parquet_new(out/'package_molecules.parquet',summaries)
    parquet_new(out/'package_conformers.parquet',geometries,coordinates=True)
    readback=verify_readback(out/'package_conformers.parquet',geometries)
    IO.write_json_new(out/'package_orders.json',{'seed':20261025,'molecules':[
        {'molecule_id':packet['summary']['molecule_id'],'orders':packet['orders']} for packet in ordered],
        'pm7_order_authority':'native_anchor_diagnostic_not_final_canonical_WP5_HOF'})
    IO.write_json_new(out/'recovered_reproduction_manifest.json',refs)
    IO.write_json_new(out/'cohort_report.json',validator.distribution(details))
    IO.write_json_new(out/'pilot_descriptive_statistics.json',aggregate_statistics(ordered))
    IO.write_json_new(out/'actual_parent_accounting.json',{'all_included_actual_parents':list(parents.values()),
        'query_evidence_reference':IO.reference(a.sacct_evidence),'generation_core_seconds_including_TIMEOUT':generation_cost,
        'generation_core_hours_including_TIMEOUT':generation_cost/3600,
        'all_included_parent_core_hours':sum(r['allocated_core_seconds'] for r in parents.values())/3600,
        'steps_never_double_charged':True,'integer_elapsed_raw_floor_is_not_zero_physical_cost':True})
    gate=generation_cost>1.5*230400
    report={'schema':'RECOVERED_SPRIME336_PILOT_CLOSURE_V1',
        'status':'RECOVERED336_VALID_REQUIRES_USER_COST_REPORT' if gate else 'RECOVERED336_VALID_REQUIRES_ROOT_REVIEW',
        'original_job_id':'4520364','original_parent_state':'TIMEOUT','original_receipt_fabricated':False,
        'recovery_job_id':job,'recovery_parent_state':'COMPLETED','partial_audit_job_id':'4520527',
        'plan_reference':IO.reference(a.plan),'partial_audit_report':value['partial_audit_report'],
        'recovery_receipt_reference':IO.reference(a.recovery_receipt),'recovery_submission_reference':IO.reference(a.recovery_submission),
        'old_package_paths_reused_without_copy':334,'new_missing_package_paths':2,'union_molecules':336,
        'independent_replay_control_executions':14,'controls_added_to_union':0,
        'status_counts':dict(Counter(r['status'] for r in summaries)),
        'closed_package_science_worker_seconds':sum(r['elapsed_seconds'] for r in summaries),
        'additional_missing_closed_worker_seconds':sum(r['detail']['elapsed_seconds'] for r in missing.values()),
        'independent_replay_control_worker_seconds':sum(r['detail']['elapsed_seconds'] for r in controls.values()),
        'original_missing_unsaved_worker_seconds':'UNKNOWN_NOT_INFERRED',
        'science_seconds_excludes_unsaved_original_missing_attempts_and_replay_controls':True,
        'actual_generation_core_hours_including_TIMEOUT':generation_cost/3600,
        'original1p5_estimate_gate_exceeded_requires_user_report':gate,
        'coordinate_readback':readback,'new_once_keys_created':0,'new_logical_retries':0,
        'formal_physical_IDs_reassigned':False,'physical_ID_scope':'original_package_row_rank_only; formal_v2 mapping remains required',
        'common_frozen':False,'pilot_accepted_for_planning':False,'formal_generation_authorized':False,
        'root_review_granted':False,'original_data_modified':False,'new_UFF_QM_calls_by_closure':0,
        'root_preflight':IO.reference(a.root_preflight),
        'outputs':[IO.reference(p) for p in sorted(out.iterdir()) if p.is_file()],
        'remaining_gates':['User cost report if1.5gate;Root scientific-failure/timing review',
            'Separate recovered-pilot planning compatibility;old336C0 validator unchanged',
            'Full90069 task closure/common exclusions;Se exception only',
            'ROUTINE roles,canonical WP5 PM7 energy order,formal_v2 physicalID mapping']}
    IO.write_json_new(out/'recovered_closure_report.json',report)
    print(json.dumps({'status':report['status'],'union_molecules':336,'controls_excluded':14,'generation_core_hours':generation_cost/3600}))
    return 0
if __name__=='__main__':raise SystemExit(main())