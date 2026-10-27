"""Exact actual prepared20 ancestry and new user authorization, no DATA reads."""
from pathlib import Path
from workflows.data_v1_final.pprime.strict_numerics20_prepare_v1 import contract as P,execution_contract as E
Q=P.Q;meta=P.meta;unique=P.unique;O=P.O;F=P.F
HERE=Q.REPO/'workflows/data_v1_final/pprime/strict_numerics20_qa_v1'
FILES=('__init__.py','contract.py','io.py','resources.py','worker.py','analysis.py','run.py','metadata.py','test_v1.py','README.md')
MODULE='workflows.data_v1_final.pprime.strict_numerics20_qa_v1.run';KEY='pprime_strict20_all12_user_authorized_qa_v1';STAGE='PPRIME_NEW20_ALL12_USER_AUTHORIZED_STRICT_NUMERICAL_QA'
BASE=Q.ROOT/'artifacts/pprime_strict20_all12_qa_v1';LEDGER=BASE/'independent_once_ledger'
CAP=P.EXEC_CAP;WORKER_CAP=P.UNRESOLVED_CALL_CAP;CLOSED_CAP=P.CLOSED_CALL_CAP;PARENT_CAP=P.EXEC_PARENT_CAP
PARAMETERS={**P.PARAMETERS,'this_stage_new_QM_calls':1200,'this_stage_native_invoke_calls':1200,'original_protocol_only_initialize_for_readers':False,
    'candidate_protocol_render_only':False,'execution_NOT_implemented_in_this_package':False,'execution_maximum_workers':16,'maximum_pending_native_calls':16,
    'wall_seconds':86400,'per_call_timeout_seconds':900,'automatic_retry':False,'execution_cap_bytes':CAP,'combined_prepare_execution_cap_bytes':P.WHOLE_CAP,
    'closed_call_cap_bytes':CLOSED_CAP,'active_or_uncompacted_UNKNOWN_call_partition_bytes':WORKER_CAP,'parent_partition_bytes':PARENT_CAP,
    'required_new_user_decision_schema':'USER_AUTHORIZED_PPRIME_NEW20_ALL12_STRICT_QA_V1','parent_live_output_tree_scans':0,
    'scratch_soft_STOP_threshold_per_worker_bytes':2<<30,'scratch_minimum_available_bytes':4<<30,
    'scratch_threshold_is_not_hard_total_limit':True,'original_RLIMIT_FSIZE_is_per_file':True,'resource_STOP_event_not_passed_to_native':True,
    'undefined_basis_tensor_other_task_axes_remain_UNKNOWN':True,'no_new_companion_calls':True,
    'original_pair_LMDB_Sprime_readback_inherited_from_actual_prepare_not_reread':True}
def user_fields(value,plan):
    E.user_fields(value,plan)
    Q.need(value['maximum_wall_seconds']==plan['wall_seconds']==86400 and value['execution_cap_bytes']==CAP
        and value['prepare_cap_bytes']==P.PREP_CAP and value['closed_call_cap_bytes']==CLOSED_CAP and value['UNKNOWN_private_partition_bytes']==WORKER_CAP
        and value['maximum_simultaneous_native_calls']==16 and value['scratch_soft_observation_is_not_hard_limit_acknowledged'] is True
        and value['unsupported_semantics_remain_UNKNOWN_no_scientific_release'] is True and value.get('not_authorized_by_this_template') is not True,'EXACT_CONCRETE_NEW20_EXECUTION_RESOURCES_AND_UNKNOWN_BOUNDARY')
    return value
def require_user(plan):
    ref=plan.get('user_decision_reference');Q.need(isinstance(ref,dict),'NEW20_ACTUAL_USER_DECISION_ABSENT_BEFORE_PARENT_DATA_OR_INITIALIZE')
    return user_fields(meta(ref),plan)
def once_key(plan,qa):return E.once_key(plan['candidate_protocol_reference'],plan['prepared20_reference'],qa)
def matrix(tasks):
    expected={'qa20-%02d-%02d'%(i,j) for i in range(20) for j in range(60)}
    Q.need(len(tasks)==1200 and {t['qa_id'] for t in tasks}==expected,'EXACT1200_PREPARED_QA_IDS')
    by_index={}
    for row in tasks:
        i,j=map(int,row['qa_id'].split('-')[1:]);by_index.setdefault(i,set()).add(row['molecule_id'])
        Q.need(row['condition']==P.TASKS[j//5] and row['arm']==P.ARMS[j%5],'EXACT12_TASK_ORDER_FIVE_ARMS_NO_ATOM_SHUFFLE')
    Q.need(all(len(v)==1 for v in by_index.values()) and len(set(next(iter(v)) for v in by_index.values()))==20,'EXACT20_UNIQUE_MIDs_NOT20_RECORDS')
    return {r['qa_id']:r for r in tasks}
def inputs(plan):
    old,new,diff=P.S.protocol(plan);prepared=meta(plan['prepared20_reference']);pp=meta(prepared['plan_reference']);proof=meta(prepared['startup_proof_reference'])
    Q.need(all('timeout_seconds' not in task for task in new['tasks']) and new['timeout_seconds']==900,'ALL12_ORIGINAL900_NO_TASK_TIMEOUT_OVERRIDE')
    Q.need(prepared['schema']=='PPRIME_NEW20_ALL12_ZERO_INVOKE_PREPARED_V1' and prepared['status']=='ACTUAL_NEW20_1200_INPUTS_PREPARED_NOT_EXECUTION_AUTHORITY'
        and plan['prepared20_reference']['path']==str(Path(pp['output_directory'])/'prepared20.json') and prepared['actual_input_sets']==1200
        and prepared['uid']==1278 and prepared['endpoint']=='202.38.247.57:22' and prepared['new_QM_calls']==prepared['native_invoke_attempts']==0
        and prepared['original_protocol_initialize_calls']==1 and prepared['candidate_protocol_initialize_calls']==0
        and prepared['candidate_protocol_reference']==plan['candidate_protocol_reference'] and prepared['original_protocol_reference']==plan['original_protocol_reference']
        and prepared['scientific_PASS'] is False and prepared['full_or2000_release']=='HOLD','ACTUAL_COMPLETE_ZERO_INVOKE_PREPARED20_NOT_FUTURE_QA')
    Q.need(proof['uid']==1278 and str(proof['job_id'])==str(prepared['job_id']) and proof['request']['node']==prepared['node']
        and proof['request']['scope_key']==P.KEY and proof['request']['scope_parameters']==P.PARAMETERS==pp['scope_parameters'],'ACTUAL_PREPARE_PLAN_PROOF_SCOPE')
    tests=meta(prepared['fixtures_reference']);Q.need(tests['tests_run']==3 and not any(tests[k] for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_PREPARE3_PASS')
    for n in P.FILES:Q.need(Q.pin(P.HERE/n) in proof['request']['source_references'],'SAME_FROZEN_PREPARE_SOURCE_BYTES')
    _,raw=F.account(plan['prepare_accounting_reference'],prepared['job_id'],prepared['node']);tasks=matrix(prepared['tasks'])
    *_,source,original,pair,sprime,olddata,prior=P.parents(pp)
    audit_ref=prepared['audit_membership_reference'];audit=meta(audit_ref)
    Q.need(audit['schema']=='WP5_STRATIFIED_RECORD_AUDIT_V1' and audit['status']=='AUDIT_MEMBERSHIP_CLOSED'
        and audit['fraction']==1.0 and audit['selected_records']['rows']==20,'NEW20_ALL_CALL_AUDIT_MEMBERSHIP')
    data=unique([*(O.triple(t['task_reference']) for t in tasks.values()),O.triple(audit['selected_records']),*source['execution_asset_references']])
    quota=meta(plan['quota_reuse_reference']);F.Provider.load_review(quota['provider_review_reference'])
    Q.need(quota['compute_node']=='compute-0-13' and quota['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY','CURRENT_ACTUAL_CPU13_QUOTA_MAPPING')
    parents=unique([*prior,plan['prepared20_reference'],prepared['plan_reference'],prepared['startup_proof_reference'],prepared['fixtures_reference'],
        plan['prepare_accounting_reference'],raw,audit_ref,plan['quota_reuse_reference'],*F.Provider.references(quota['provider_review_reference']),
        quota['publisher_identity_reference'],quota['provider_actual_launch_reference'],quota['resource_epoch_root_binding_reference']])
    return old,new,diff,prepared,source,audit_ref,tasks,data,parents
def sources():
    paths=[*(HERE/n for n in FILES),*P.sources()]
    reader=Q.REPO/'workflows/data_v1_final/pprime/frame_native_precision_diagnosis_v2'
    paths += list(reader.glob('*.py'))+[Q.REPO/'workflows/data_v1_final/pprime/raw_archive.py']
    return sorted(set(paths))
