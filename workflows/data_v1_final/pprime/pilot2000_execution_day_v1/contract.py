"""One original2000-record pilot; stricter flags require a new specific decision."""
import hashlib,pathlib,stat
from workflows.data_v1_final.pprime.pilot2000_prepare_day_v1 import contract as P
Q=P.Q;need=P.need;meta=P.meta;unique=P.unique;O=P.O;M=P.ResourceOrigin
HERE=Q.REPO/'workflows/data_v1_final/pprime/pilot2000_execution_day_v1'
FILES=('contract.py','io.py','worker.py','run.py','metadata.py','test_v1.py','source_boundary.py','source_origin.json','README.md')
KEY='pprime_original2000_formal_pilot_day_v1';MODULE='workflows.data_v1_final.pprime.pilot2000_execution_day_v1.run'
CAP=32<<30;WALL=86400;WORKER_CAP=1<<30;RAW_CAP=768<<20;RESULT_CAP=128<<20;PARENT_CAP=8<<30
BASE=Q.ROOT/'artifacts/pprime2000_day_v1';NODES=P.NODES
def parameters(node,mode):
    need(node in NODES and mode in ('ORIGINAL_WP5','TIGHTER_ONLY_THREE_FIELDS'),'EXACT_NODE_AND_PRECISION_CHOICE')
    return {'original_unique_MIDs':1000,'requested_UFF_records':2000,'task_names':list(O.TASKS),'tasks_per_record':12,
      'maximum_native_invocations':24000,'arms_per_geometry':1,'no_new_QA_or_companion_calls':True,'precision_mode':mode,
      'only_three_candidate_differences':True,'timeout_seconds':900,'automatic_retry':False,'cpus':16,'node':node,
      'wall_seconds':WALL,'memory_requested':False,'output_cap_bytes':CAP,'private_record_cap_bytes':WORKER_CAP,
      'parent_export_and_metadata_cap_reservation_bytes':PARENT_CAP,'persistent_workers':16,'maximum_pending_records':16,
      'original_success_rate_gate':.995,'original_allocated_core_seconds_per_requested_record_gate':11.7,
      'allocated_core_hours_overrun_action':'REPORT_AND_CONTINUE_QUALITY_UNCHANGED',
      'WP5_record_cost_overrun_action':'REPORT_AND_HOLD_FULL_NO_SCIENTIFIC_PASS',
      'scientific_pilot_2000':True,'resource_pilot_relaxation':False,
      'full_release_authorized':False,'legacy_production_once_identity_preserved':True,'source_methods':3}

def precision(plan,review):
    mode=plan['precision_mode'];parameters(plan['node'],mode)
    need(review['original2000_formal_pilot_scope_authorized'] is True and review['maximum_native_invocations']==24000
      and review['minimum_record_success_rate']==.995 and review['maximum_allocated_core_seconds_per_requested_record']==11.7
      and review['full_submission_authorized'] is False and review['precision_mode']==mode
      and review['allocated_core_hours_overrun_action']=='REPORT_AND_CONTINUE_QUALITY_UNCHANGED'
      and review['WP5_record_cost_overrun_action']=='REPORT_AND_HOLD_FULL_NO_SCIENTIFIC_PASS',
      'EXACT_ROOT_PILOT_NOT_FULL_AND_UNCHANGED_GATES')
    if mode=='ORIGINAL_WP5':
        need(review['original_WP5_precision_guide_scope_authorized'] is True and plan.get('user_precision_decision_reference') is None,
          'ORIGINAL_RECIPE_GUIDE_AUTHORITY_NOT_DIAGNOSTIC_PRECISION_PROMOTION');return plan['original_protocol_reference']
    ref=plan.get('user_precision_decision_reference');need(type(ref)is dict,'NEW2000_TIGHTER_DECISION_REQUIRED_BEFORE_DATA_INITIALIZE_INVOKE')
    need(review.get('specific2000_user_precision_decision_reference')==ref,
      'ROOT_EXACT_SCOPE_MUST_BIND_NEW2000_USER_DECISION_NOT_DIAGNOSTIC_APPROVAL')
    d=meta(ref);user_decision_fields(d,plan);return plan['candidate_protocol_reference']

def user_decision_fields(d,plan):
    need(d['schema']=='USER_AUTHORIZED_PPRIME2000_TIGHTER_PILOT_V1' and d['status']=='USER_AUTHORIZED'
      and d['prepared2000_reference']==plan['prepared2000_reference'] and d['original_protocol_reference']==plan['original_protocol_reference']
      and d['candidate_protocol_reference']==plan['candidate_protocol_reference'] and d['requested_records']==2000
      and d['maximum_native_invocations']==24000 and d['timeout_seconds']==900 and d['cpus']==16
      and d['maximum_wall_seconds']==WALL and d['output_cap_bytes']==CAP and d['only_three_frozen_protocol_differences'] is True
      and d['other9_tasks_and_quality_thresholds_unchanged'] is True and d['automatic_retry_authorized'] is False
      and d['full_submission_authorized'] is False
      and d['authorization_basis']=='EXPLICIT_USER_MESSAGE_FOR_THIS_2000_PILOT'
      and d['diagnostic15_1200_frame30_authorizations_do_not_apply'] is True,
      'SPECIFIC_ACTUAL2000_USER_CHOICE_NOT15_OR1200_AUTHORITY')
    need(d.get('synthetic_fixture_only') is not True and d.get('not_authorized_by_this_template') is not True,'REAL_DECISION_NOT_SOURCE_TEMPLATE')
    return d

def pilot_gate_state(assessment):
    """Keep every original assess gate, including the separate WP5 record cost."""
    if assessment is None:return {}
    gates=dict(assessment['gates'])
    need(type(gates.get('allocated_seconds_within_1_5x_wp5')) is bool,
      'ORIGINAL_11_7_PER_RECORD_COST_GATE_CANNOT_BE_OMITTED_OR_GENERIC_WAIVED')
    return gates

def inputs(plan):
    # This is the producer's PURE count/locator header, never its scientific
    # prepared2000 body. That body is an explicitly declared CPU DATA input.
    prepared=meta(plan['prepared2000_header_reference']);pp=meta(prepared['plan_reference']);proof=meta(prepared['startup_proof_reference'])
    need(prepared['schema']=='PPRIME_ORIGINAL2000_ZERO_INVOKE_PURE_CLOSURE_HEADER_V1'
      and prepared['status']=='ACTUAL_PREPARED_OUTPUT_CLOSED_ACCOUNTING_PENDING_NOT_NATIVE_AUTHORITY'
      and prepared['prepared_reference']==plan['prepared2000_reference'] and prepared['uid']==1278
      and prepared['MIDs']==1000 and prepared['UFF_geometries']==2000 and prepared['maximum_formal_native_calls']==24000
      and prepared['all12_tasks']==list(O.TASKS) and prepared['scientific_ids_coordinates_and_values_in_header'] is False
      and prepared['actual_terminal_accounting_required'] is True
      and prepared['native_invoke_attempts']==prepared['candidate_initialize_calls']==prepared['new_QM_UFF_calls']==0
      and prepared['original_initialize_calls']==1 and prepared['production_once_written'] is False and prepared['scientific_PASS'] is False,
      'ACTUAL_ZERO_INVOKE2000_PREPARATION_NOT_FUTURE_OR_DIAGNOSTIC20')
    need(proof['request']['scope_key']==P.KEY and proof['request']['scope_parameters']==P.parameters(pp['node'])==pp['scope_parameters']
      and str(proof['job_id'])==str(prepared['job_id']) and proof['uid']==1278 and proof['node']==prepared['node'],'REAL_PREPARE_PLAN_PROOF')
    for name in P.FILES:need(Q.pin(P.HERE/name) in proof['request']['source_references'],'SAME_ACTUAL_PREPARATION_SOURCE:'+name)
    tests=meta(prepared['fixtures_reference']);need(tests['tests_run']==3 and not any(tests[k] for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL_PREPARE3_PASS')
    software=tests.get('software_reader_synthetic_boundary_checks',{})
    need(software.get('registered_alias_whole_FD_SHA') is True and software.get('wrong_SHA_rejected') is True
      and software.get('alias_cycle_rejected') is True and prepared['software_original_count']==14
      and prepared['execution_assets_whole_SHA_count']==446,'REAL_R2_SOFTWARE_READER_AND_ALL446_ASSETS_PREPARED')
    _,raw=P.OriginalInputs.C.F.account(plan['prepare_accounting_reference'],prepared['job_id'],prepared['node'])
    old,new,diff,context,pilot,original,pair,sprime,population,val,olddata,parents=P.parents(pp)
    need(all(plan[k]==pp[k] for k in ('original_prepared_reference','original_preparation_closure_reference','source_context_reference',
      'original_protocol_reference','candidate_protocol_reference','retention_policy_reference','original_sprime_recipe_reference')),'SAME_CLOSED_PREPARE_SCIENCE_AUTHORITIES')
    need(prepared['source_context_reference']==plan['source_context_reference']
      and prepared['original_pairs_reference']==pair and prepared['original_protocol_reference']==plan['original_protocol_reference']
      and prepared['candidate_protocol_reference']==plan['candidate_protocol_reference'],'EXACT_PREPARED_ORIGINAL_PAIRS_AND_PROTOCOLS')
    audit=meta(prepared['audit_membership_reference']);need(audit['schema']=='WP5_STRATIFIED_RECORD_AUDIT_V1' and audit['status']=='AUDIT_MEMBERSHIP_CLOSED','ACTUAL_UNION_MEMBERSHIP')
    root=pathlib.Path(prepared['prepared_reference']['path']).parent
    need(pathlib.Path(plan['prepared2000_header_reference']['path'])==root/'prepared2000_closure_header.json'
      and pathlib.Path(prepared['prepared_reference']['path'])==root/'prepared2000.json'
      and root==pathlib.Path(pp['output_directory']),'EXACT_SAME_ACTUAL_PREPARATION_OUTPUT_TREE')
    data=unique([P.triple(plan['prepared2000_reference']),pair,P.triple(prepared['record_input_hashes_reference']),
      P.triple(prepared['orders_and_lineage_reference']),P.triple(prepared['stable_source_audit_reference']),P.triple(audit['selected_records']),*olddata])
    refs=unique([*parents,plan['prepared2000_header_reference'],prepared['plan_reference'],prepared['startup_proof_reference'],prepared['fixtures_reference'],
      plan['prepare_accounting_reference'],raw,prepared['audit_membership_reference']])
    return old,new,diff,context,pilot,prepared,pair,data,refs

def sources(plan):
    _,_,_,_,_,prepared,_,_,_=inputs(plan)
    # Import only Source definitions, never initialize/execute. Metadata and
    # runtime must collect the same transitive modules before freezing pins.
    from . import io,worker,run,test_v1
    refs=[*P.sources(meta(prepared['plan_reference'])),*(Q.pin(HERE/n) for n in FILES)]
    refs += [Q.pin(Q.REPO/'workflows/data_v1_final/pprime/strict_numerics15_qa_v1/io.py')]
    from . import source_boundary
    refs += source_boundary.verify_sources()
    import sys
    for name,module in tuple(sys.modules.items()):
        path=getattr(module,'__file__',None)
        if name.startswith('workflows.') and path and pathlib.Path(path).suffix=='.py':
            path=pathlib.Path(path).absolute();need(Q.REPO in path.parents,'CURRENT_PROJECT_WORKFLOW_SOURCE');refs.append(Q.pin(path))
    return unique(refs)

def legacy_once_key(pair_reference,original_protocol_reference):
    return hashlib.sha256(O.canonical(['original2000-pilot-science-once-v1',pair_reference['sha256'],original_protocol_reference['sha256']])).hexdigest()

def record_once_key(pair,original_protocol_reference):
    # Precision/output/mode are deliberately absent: they cannot re-open a
    # consumed production physical geometry. Diagnostic ledgers are separate.
    return hashlib.sha256(O.canonical(['pprime-production-physical-v1',pair['molecule_id'],pair['conformer']['sprime_conf_idx'],
      pair['uff_coordinate_sha256'],original_protocol_reference['sha256']])).hexdigest()

def ledger(plan):
    need(Q.pin(Q.REPO/'configs/data_v1/pprime/stable_raw_retention_v1.json')==plan['retention_policy_reference'],'SAME_ORIGINAL_ROOT_ACCEPTED_RETENTION_POLICY')
    policy=meta(plan['retention_policy_reference']);root=pathlib.Path(policy['pilot_once_ledger_root'])
    need(root==Q.ROOT/'artifacts/pprime_retention_v1/pilot_once' and not any(p.is_symlink() for p in (root,*root.parents)),
      'ORIGINAL_GLOBAL_PILOT_ONCE_ROOT_NO_NEW_NAMESPACE_ESCAPE')
    for path in (root,root/'physical_records_v1'):
        if path.exists() or path.is_symlink():
            frame=path.lstat();need(frame.st_uid==1278 and stat.S_ISDIR(frame.st_mode)
              and not stat.S_ISLNK(frame.st_mode),'OWN_REAL_GLOBAL_ONCE_DIRECTORY_NO_SYMLINK_ESCAPE')
    return root
