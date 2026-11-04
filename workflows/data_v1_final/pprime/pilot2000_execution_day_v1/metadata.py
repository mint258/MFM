"""Small Root metadata only; no DATA read, submission or implicit precision grant."""
import argparse,copy,csv,io,pathlib
from . import contract as C,source_boundary
Q=C.Q;M=C.M
KEYS=('prepared2000_reference','prepared2000_header_reference','prepare_accounting_reference','original_prepared_reference',
 'original_preparation_closure_reference','source_context_reference','original_protocol_reference',
 'candidate_protocol_reference','retention_policy_reference','original_sprime_recipe_reference',
 'resource_authority_reference','cost_decision_reference','quota_provider_review_reference',
 'quota_provider_identity_reference','root_carveout_review_reference')

def draft(path,out):
    Q.on_login();root=Q.load(path)
    C.need(root['schema']=='ROOT_REQUESTED_PPRIME_ORIGINAL2000_FORMAL_PILOT_DAY_V1'
      and root['status']=='REQUESTED_FOR_REVIEW' and root['requested_by']=='root','ACTUAL_ROOT_2000_REQUEST')
    out=M.fresh(out);out.mkdir(parents=True,mode=0o700)
    missing=[k for k in KEYS if not root.get(k)]
    if root.get('precision_mode')=='TIGHTER_ONLY_THREE_FIELDS' and not root.get('user_precision_decision_reference'):
        missing.append('NEW_SPECIFIC_ACTUAL_USER_AUTHORIZED_PPRIME2000_TIGHTER_PILOT_V1')
    if missing:
        return Q.write_new(out/'NONEXECUTABLE.json',{'schema':'PPRIME2000_FORMAL_PILOT_NONEXECUTABLE_V1',
          'status':'NONEXECUTABLE_MISSING_ACTUAL_INPUT_OR_PRECISION_AUTHORITY','missing':missing,
          'request_reference':Q.pin(path),'plan_created':False,'native_initialize_or_invoke':False})
    plan={k:root[k] for k in KEYS};plan.update(node=root['node'],precision_mode=root['precision_mode'],
      user_precision_decision_reference=root.get('user_precision_decision_reference'))
    params=C.parameters(plan['node'],plan['precision_mode'])
    old,new,diff,context,pilot,prepared,pair,data,parents=C.inputs(plan)
    M.validate_authority(plan['resource_authority_reference'],read_small=Q.read_small)
    resources=[plan[k] for k in KEYS[-5:]]
    for ref in resources:C.meta(ref)
    cost=C.meta(plan['cost_decision_reference'])
    C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
      and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_REPORT_AND_CONTINUE_NOT_QUALITY_WAIVER')
    M.carveout(C.meta(plan['root_carveout_review_reference']),{'scope_key':C.KEY,'node':root['node'],
      'resource_authority_reference':plan['resource_authority_reference'],'estimated_peak_output_bytes':C.CAP})
    plan.update(schema='PPRIME2000_FORMAL_PILOT_DAY_PLAN_V1',scope_parameters=params,wall_seconds=C.WALL,
      output_cap_bytes=C.CAP,output_directory=str(M.fresh(root['output_directory'],'artifacts')),data_references=data)
    fields={'kind':'qm','scope_key':C.KEY,'scope_parameters':params,'pilot':False,'wall_seconds':C.WALL,
      'estimated_peak_output_bytes':C.CAP,'source_status_stage':'PPRIME_ORIGINAL2000_ALL12_FORMAL_PILOT_ONCE',
      'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
      **copy.deepcopy(fields),'scope_mode':'BOUNDED_PERFORMANCE_BATCH','bounded_batch_limits_reviewed':True,
      'resource_authority_reference':plan['resource_authority_reference'],'stage_output_cap_bytes':C.CAP,
      'original2000_formal_pilot_scope_authorized':True,'maximum_native_invocations':24000,
      'minimum_record_success_rate':.995,'maximum_allocated_core_seconds_per_requested_record':11.7,
      'allocated_core_hours_overrun_action':'REPORT_AND_CONTINUE_QUALITY_UNCHANGED',
      'WP5_record_cost_overrun_action':'REPORT_AND_HOLD_FULL_NO_SCIENTIFIC_PASS','full_submission_authorized':False,
      'precision_mode':plan['precision_mode'],
      'original_WP5_precision_guide_scope_authorized':plan['precision_mode']=='ORIGINAL_WP5',
      'specific2000_user_precision_decision_reference':plan['user_precision_decision_reference']}
    C.precision(plan,review)  # missing tight authority refuses before running plan
    extra=[plan['user_precision_decision_reference']] if plan['user_precision_decision_reference'] else []
    plan['source_references']=C.unique([*C.sources(plan),*parents,*resources,*extra,Q.pin(path)])
    pr=Q.write_new(out/'plan.json',plan);src=C.unique([*plan['source_references'],pr])
    review.update(parent_evidence_references=C.unique([*parents,*resources,*extra,Q.pin(path)]),
      approved_source_references=src,data_references=data)
    tr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'PPRIME2000_FORMAL_PILOT_DAY_DRAFT_V1',
      'plan_reference':pr,'template_reference':tr,'stage_fields':fields,'source_references':src,
      'data_references':data,'resource_authority_reference':plan['resource_authority_reference'],
      'precision_mode':plan['precision_mode'],'DATA_on_login':False,'not_a_user_precision_grant':True})

def finalize(path,review):
    Q.on_login();d=Q.load(path);C.need(d['schema']=='PPRIME2000_FORMAL_PILOT_DAY_DRAFT_V1','EXACT_PILOT_DRAFT')
    rr=M.approved(d['template_reference'],review);plan=C.meta(d['plan_reference']);C.precision(plan,C.meta(rr))
    *_,data,parents=C.inputs(plan);C.need(data==plan['data_references']==d['data_references'],'ALL_EXACT_LARGE_DATA_DECLARED')
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'SOURCE_OR_SMALL_AUTHORITY_CHANGED')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','stage_output_cap_bytes':C.CAP,
      'source_references':d['source_references'],'data_references':data,
      'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':rr}}
    M.validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(pathlib.Path(path).parent/'stage_spec.json',spec)

def accounting(ref,job,node):
    """Original account structure, retaining all terminal failure costs too."""
    a=C.meta(ref);raw=a['raw_sacct_reference'];C.need(Q.pin(raw['path'])==raw,'ACTUAL_RAW_ACCOUNT_PIN')
    rows=[r for r in csv.DictReader(io.StringIO(Q.read_small(raw['path']).decode()),delimiter='|') if '.' not in r['JobIDRaw']]
    C.need(a['schema']=='DATA_V1_PARENT_ACCOUNTING_CLOSURE_V1' and a['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED'
      and a['endpoint']=='202.38.247.57:22' and a['uid']==1278 and a['query_returncode']==0
      and a['failed_timeout_startup_cleanup_elapsed_retained'] is True,'REAL_MAIN_TERMINAL_ACCOUNTING')
    by={r['JobIDRaw']:r for r in rows};C.need(len(by)==len(rows)==len(a['parents']),'ALL_UNIQUE_ACTUAL_PARENT_ROWS')
    total=0
    for parent in a['parents']:
        r=by[parent['job_id']]
        C.need(parent['state']==r['State'] and parent['exit_code']==r['ExitCode'] and parent['node']==r['NodeList']
          and parent['alloc_cpus']==int(r['AllocCPUS']) and parent['elapsed_raw_seconds']==int(r['ElapsedRaw'])
          and r['UID']=='1278','ACTUAL_TERMINAL_RAW_FIELDS_MATCH')
        total+=parent['alloc_cpus']*parent['elapsed_raw_seconds']
    C.need(total==a['allocated_core_seconds'],'ALL_ACCOUNT_COSTS_RETAINED')
    selected=by[str(job)];C.need(selected['NodeList']==node and selected['User']=='zixiao' and int(selected['AllocCPUS'])==16
      and selected['State'] in ('COMPLETED','FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'),
      'ONLY_REAL_TARGET_PARENT_TERMINAL16')
    return a,raw,selected,rows

def close(plan_path,proof_path,account_ref_path,out,result_path=None):
    Q.on_login();plan=C.meta(Q.pin(plan_path));proof=C.meta(Q.pin(proof_path));req=proof['request']
    C.need(req['scope_key']==C.KEY and req['scope_parameters']==plan['scope_parameters']==C.parameters(plan['node'],plan['precision_mode'])
      and req['node']==plan['node'] and req['cpus']==16 and Q.pin(plan_path) in req['source_references'],'EXACT_ACTUAL_PILOT_PARENT')
    C.precision(plan,C.meta(req['scope']['review']));aref=Q.pin(account_ref_path)
    actual,raw,parent,rows=accounting(aref,proof['job_id'],plan['node']);legacy=None;result_ref=None
    if result_path:
        result_ref=Q.pin(result_path);result=C.meta(result_ref)
        C.need(result_ref['path']==str(pathlib.Path(plan['output_directory'])/'result.json')
          and result['plan_reference']==Q.pin(plan_path) and result['startup_proof_reference']==Q.pin(proof_path)
          and str(result['runtime']['job_id'])==str(proof['job_id']) and result['runtime']['node']==plan['node'],
          'REAL_RESULT_BELONGS_TO_THIS_PARENT_AND_FROZEN_PLAN')
        originals=source_boundary.objects();pilot=C.meta(C.meta(plan['source_context_reference'])['pilot_config'])
        legacy=originals['assess'](result,rows,pilot)
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED'
      and cost['on_overrun']=='REPORT_AND_CONTINUE' and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_ONLY_USER_DECISION')
    seconds=int(parent['AllocCPUS'])*int(parent['ElapsedRaw']);rate=seconds/2000
    gates=C.pilot_gate_state(legacy)
    return Q.write_new(M.fresh(out),{'schema':'PPRIME2000_ACTUAL_TERMINAL_PILOT_CLOSURE_V1',
      'status':'ACTUAL_COMPUTE_AND_COST_GATES_CLOSED_QUALITY_REVIEW_PENDING' if gates and all(gates.values()) else 'ACTUAL_PILOT_GATES_HOLD_NO_FULL_AUTHORITY',
      'actual_parent':parent,'accounting_reference':aref,'raw_sacct_reference':raw,'plan_reference':Q.pin(plan_path),
      'startup_proof_reference':Q.pin(proof_path),'result_reference':result_ref,'original_assess_result':legacy,
      'all_original_pilot_gate_results_including_WP5_record_cost':gates,'actual_allocated_core_seconds':seconds,
      'actual_allocated_core_seconds_per_requested_record':rate,'requested_record_denominator':2000,
      'original_WP5_per_record_cost_threshold':11.7,'WP5_record_cost_overrun_reported':rate>11.7,
      'WP5_record_cost_gate_pass':rate<=11.7,'WP5_record_cost_overrun_action':'REPORT_AND_HOLD_FULL_NO_SCIENTIFIC_PASS',
      'allocated_core_hours_overrun_action':'REPORT_AND_CONTINUE_QUALITY_UNCHANGED',
      'generic_allocated_hours_authority_does_not_override_WP5_record_cost_gate':True,
      'cost_decision_reference':plan['cost_decision_reference'],'separate_prepare_accounting_reference':plan['prepare_accounting_reference'],
      'all_failure_timeout_startup_export_raw_and_unknown_costs_retained':True,
      'one_percent_quality_mask_gate_waived':False,'Pprime_all_population_outlier_scan_pending':True,
      'P_vs_Pprime_distribution_review_pending':True,'scientific_PASS':False,'full_submission_authorized':False,
      'diagnostic15_1200_frame30_not_promoted':True})

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',required=True);a.add_argument('--root-review',required=True)
    a=s.add_parser('close');a.add_argument('--plan',required=True);a.add_argument('--startup-proof',required=True)
    a.add_argument('--accounting',required=True);a.add_argument('--result');a.add_argument('--output',required=True)
    a=p.parse_args()
    print(draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review) if a.action=='finalize'
      else close(a.plan,a.startup_proof,a.accounting,a.output,a.result))
if __name__=='__main__':main()
