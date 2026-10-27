"""Actual prepare20 -> unapproved user proposal,or new decision -> Root scope."""
import argparse,copy,pathlib
from . import contract as C
Q=C.Q
FIELDS=('prepared20_reference','prepare_accounting_reference','original_protocol_reference','candidate_protocol_reference','quota_reuse_reference',
    'resource_authority_reference','cost_decision_reference','output_directory')
def proposal(plan,prepared):
    pp=C.meta(prepared['plan_reference']);source=C.meta(pp['source_context_reference']);old,_,_=C.P.S.protocol(plan)
    return {'schema':'PPRIME_NEW20_CONCRETE_USER_REVIEW_PROPOSAL_V1','status':'UNAPPROVED_UNEXECUTED_NEW1200_QA_ONLY',
        'actual_prepared20_reference':plan['prepared20_reference'],'actual_prepare_accounting_reference':plan['prepare_accounting_reference'],
        'original_protocol_reference':plan['original_protocol_reference'],'candidate_protocol_reference':plan['candidate_protocol_reference'],
        'new_unique_MIDs':20,'all_task_names':list(C.P.TASKS),'arms':list(C.P.ARMS),'maximum_new_native_calls':1200,'maximum_simultaneous_native_calls':16,
        'selection_seed':20261010,'selection_domain':'pprime-strict20-all12-selection-v1','selection_is_original_rank0_and_target_independent':True,
        'actual_selection_report':prepared['selection'],'geometry_domain':'original2000 eligible UFF inputs; not finalCommon',
        'limited_1to80_atom_diagnostic_only_no_extrapolation_to_over80':True,'declared_prepare_DATA_files':len(pp['data_references']),
        'prepare_original_core_DATA_files':17,'prepare_frozen_execution_asset_files':len(source['execution_asset_references']),
        'original_versions':old['expected_versions'],'all12_tasks_have_no_timeout_override':True,
        'P90_is_coordinate_axis_map_not_atom_shuffle':True,'atom_range':'original renderer1..80 only',
        'only_changes':{'pm7_B_keywords_append':'SCFCRT=1.D-9','xtb_singlepoint_args_append':['--acc','0.01'],'xtb_perturbed_gradient_args_append':['--acc','0.01']},
        'other9_task_entries_methods_versions_seeds900s_timeouts_unchanged':True,'new_tolerances_or_forcefield_or_UFF_calls':False,
        'controls':'fresh B1/B2 repeats,P1/P2 exactP90 repeats,R1 general proper rotation; actual prior strict15 review retained as ancestry',
        'no_original_protocol1200_QM_control_exists_for_these20_geometries':True,'old15_new20_different_input_values_not_claimed_identical':True,
        'original_vector_gate_expected_complete_checks':500,'native_task_status_input_raw_and_original_atomic_array_checks':1200,
        'undefined_basis_tensor_axes':'UNKNOWN; no singlepoint own-coordinate PASS claimed; not a reason alone to abort the rest of approved evidence collection',
        'STOP_NEW_DISPATCH':'any call technical/input/raw/declared WP5 or defined-vector gate FAIL or unavailable;or actual resource/provider/wall STOP;running calls naturally finish',
        'per_call_timeout_seconds':900,'automatic_retry':False,'unknown_failed_call_replacement':False,'maximum_wall_seconds':86400,'cpus':16,
        'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','exclusive':False,'actual_provider_current_node':'compute-0-13',
        'shared_caps':{'prepare':C.P.PREP_CAP,'execution':C.CAP,'combined':C.P.WHOLE_CAP,'parent':C.PARENT_CAP,
            'closed_call':C.CLOSED_CAP,'active_or_uncompacted_UNKNOWN':C.WORKER_CAP,'at_most_active_or_UNKNOWN16':True,
            'combined_managed_role_bound_bytes':32672<<20,'closed_over25M_preserved112M_UNKNOWN_and_stop_new':True},
        'scratch':'original per-file RLIMIT128MiB unchanged;2GiB/worker soft observed STOP and4GiB tmp-free floor;not total hard bound,no new forced signal',
        'RSS':'actual recursive own-tree16GiB soft STOP andMemAvailable max(4GiB,15%);not requested or guaranteed memory',
        'account_and_physical':'finite actual quota provider;whole-wave plus own remaining cap plus200GB;no auto renewal',
        'maximum_allocation_core_seconds_if24h_used':16*86400,'allocation_ceiling_not_prediction_or_actual_cost':True,
        'prior15_cost_not_extrapolated_to_other20_molecules':True,'cost_overrun_action':'REPORT_AND_CONTINUE_QUALITY_UNCHANGED',
        'approval_needed':'new explicit user authorization bound to this actual prepared20;old15 or generic cost authority insufficient',
        'no_automatic_larger_QA_2000_production_or_full':True,'old15FAIL_preserved':True,'scientific_PASS':False,'production_full2000_release':'HOLD',
        'execution_entrypoint_present':True,'QM_executed_by_metadata_helper':False}
def decision_template(plan):
    return {'schema':'USER_AUTHORIZED_PPRIME_NEW20_ALL12_STRICT_QA_V1','status':'PENDING_USER_APPROVAL','authorization_basis':'EXPLICIT_USER_MESSAGE_IN_THIS_SESSION',
        'actual_user_statement':None,'candidate_protocol_reference':plan['candidate_protocol_reference'],'original_protocol_reference':plan['original_protocol_reference'],
        'prepared20_reference':plan['prepared20_reference'],'maximum_new_QM_calls':1200,'new_unique_MIDs':20,'task_names':list(C.P.TASKS),'arms':list(C.P.ARMS),
        'cpus':16,'maximum_wall_seconds':86400,'per_call_timeout_seconds':900,'combined_shared_output_cap_bytes':C.P.WHOLE_CAP,
        'execution_cap_bytes':C.CAP,'prepare_cap_bytes':C.P.PREP_CAP,'closed_call_cap_bytes':C.CLOSED_CAP,'UNKNOWN_private_partition_bytes':C.WORKER_CAP,
        'maximum_simultaneous_native_calls':16,'scratch_soft_observation_is_not_hard_limit_acknowledged':True,'unsupported_semantics_remain_UNKNOWN_no_scientific_release':True,
        'automatic_retry':False,'original_quality_thresholds_unchanged':True,'production_recipe_unchanged':True,'original15FAIL_preserved':True,'production_or2000_full_release':'HOLD',
        'not_authorized_by_this_template':True}
def draft(request_path,out):
    request=Q.load(request_path);Q.need(request['schema']=='ROOT_REQUESTED_PPRIME_NEW20_USER_REVIEW_OR_EXECUTE_V1' and request['status']=='REQUESTED_FOR_REVIEW'
        and request['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_USER_APPROVAL')
    plan={'schema':'PPRIME_NEW20_ALL12_USER_AUTHORIZED_QA_PLAN_V1',**{k:request[k] for k in FIELDS},'scope_parameters':C.PARAMETERS,
        'wall_seconds':86400,'output_cap_bytes':C.CAP,'user_decision_reference':request.get('user_decision_reference')}
    old,new,diff,prepared,source,audit,tasks,data,parents=C.inputs(plan);plan['audit_membership_reference']=audit;plan['data_references']=data
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(plan['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_AUTHORITY_NOT_NEW20_PERMISSION')
    authorized=plan['user_decision_reference'] is not None
    if authorized:C.require_user(plan);parents=C.unique([*parents,plan['user_decision_reference']])
    out=pathlib.Path(out);output=pathlib.Path(plan['output_directory']);Q.need(out.is_absolute() and Q.ROOT/'control' in out.parents and not out.exists()
        and output.is_absolute() and C.BASE in output.parents and output!=C.LEDGER and C.LEDGER not in output.parents and not output.exists()
        and '..' not in out.parts and '..' not in output.parts and not any(p.is_symlink() for p in (out,*out.parents,output,*output.parents)),'FRESH_REVIEW_AND_FRESH_NEW20_OUTPUT_NOT_OLD_ONCE')
    refs=C.unique([*(Q.pin(p) for p in C.sources()),*parents,Q.pin(request_path),plan['resource_authority_reference'],plan['cost_decision_reference']])
    for ref in refs:Q.need(ref['path'] not in {r['path'] for r in data} and Q.pin(ref['path'])==ref,'SMALL_SOURCE_ONLY_NEVER_LOGIN_PARSE_HASH_TASK_DATA')
    out.mkdir(parents=True,exist_ok=False,mode=0o700);pr=Q.write_new(out/'plan.json',plan);refs=C.unique([*refs,pr])
    proposed=Q.write_new(out/'actual_prepared20_user_proposal.json',proposal(plan,prepared));dt=Q.write_new(out/'user_decision.UNAUTHORIZED_TEMPLATE.json',decision_template(plan))
    fields={'kind':'qm','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':86400,'estimated_peak_output_bytes':C.CAP,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    if not authorized:
        return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME_NEW20_EXECUTION_DRAFT_V1','status':'REAL_NEW20_USER_DECISION_PENDING_NO_RUNNABLE_STAGE_SPEC',
            'plan_reference':pr,'proposal_reference':proposed,'decision_UNAUTHORIZED_template_reference':dt,'root_review_template_reference':None,
            'stage_fields_for_review_only':fields,'source_references':refs,'data_references':data,'new_QM_calls':0,'submitted':False,
            'fresh_request_after_actual_explicit_user_decision_required':True})
    review={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'resource_authority_reference':plan['resource_authority_reference'],'scope_mode':'BOUNDED_METADATA_PREPARATION','stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':refs,'data_references':data,'new20_only_user_decision_reference':plan['user_decision_reference'],
        'prepared20_reference':plan['prepared20_reference'],'unsupported_semantics_remain_UNKNOWN':True,'old15FAIL_preserved':True,'full_or2000_release':'HOLD'}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME_NEW20_EXECUTION_DRAFT_V1','status':'REAL_USER_AUTHORIZED_NEW20_PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'proposal_reference':proposed,'root_review_template_reference':rr,'stage_fields':fields,'source_references':refs,'data_references':data,
        'resource_authority_reference':plan['resource_authority_reference'],'new_QM_calls':0,'submitted':False})
def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='PPRIME_NEW20_EXECUTION_DRAFT_V1' and d['status']=='REAL_USER_AUTHORIZED_NEW20_PENDING_INDEPENDENT_ROOT_REVIEW','NEW20_ACTUAL_USER_DECISION_BEFORE_RUNNABLE_STAGE')
    plan=C.meta(d['plan_reference']);C.require_user(plan);rr=Q.pin(review_path);review=C.meta(rr);template=C.meta(d['root_review_template_reference'])
    Q.need(rr!=d['root_review_template_reference'] and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','INDEPENDENT_ROOT_NOT_CHILD_SIGNATURE')
    for k,v in template.items():
        if k not in ('status','reviewer'):Q.need(review[k]==v,'EXACT_APPROVED_NEW20_FIELD:'+k)
    for ref in d['source_references']:Q.need(Q.pin(ref['path'])==ref,'SAME_FROZEN_SOURCE_AND_PARENT_BYTES')
    *_,data,parents=C.inputs(plan);Q.need(data==d['data_references'],'SAME1200_PRODUCER_BODY_LOCATORS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP,
        'source_references':d['source_references'],'data_references':data,'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small);return Q.write_new(pathlib.Path(draft_path).parent/'stage_spec.json',spec)
def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=pathlib.Path,required=True);a.add_argument('--root-review',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review))
if __name__=='__main__':main()
