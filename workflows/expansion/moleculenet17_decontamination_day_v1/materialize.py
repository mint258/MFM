"""One original generic stage. Actual C0 and independent Root review precede READY."""
import argparse,copy
from pathlib import Path
from workflows.expansion.marcel_drugs_decontamination_main_v1.materialize import fresh,approved
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority,validate_scope_spec
from workflows.data_v1_final.execution.cpu_analysis_day_v1.contract import carveout
from . import contract as C
Q=C.Q

def parent_sources(context):
    values=[context['partial9_registry_reference'],context['remote_acquisition_authority_reference']]
    for p in context['closed_parents'].values():
        values.extend(p.values());proof=C.meta(p['startup_proof_reference'])
        receipt=C.meta(p['receipt_reference']);values.append(C.alias(context,receipt.get('plan_reference',receipt.get('plan'))))
        review=proof.get('request',{}).get('scope',{}).get('review')
        if review is not None:values.append(review)
        if 'request_reference' in proof:values.append(proof['request_reference'])
    values.extend(u['receipt_reference'] for u in context['local6_original_units'])
    return C.unique(values)

def draft(path,out):
    request=Q.load(path);C.need(request['schema']=='ROOT_REQUESTED_MOLECULENET17_DECONTAMINATION_DAY_V1'
      and request['status']=='REQUESTED_FOR_REVIEW' and request['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_APPROVAL')
    context=C.meta(request['input_context_reference']);authority=C.inputs(context)
    validate_authority(request['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(request['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
      and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_COST_AND_QUALITY_AUTHORITY')
    resource={k:request[k] for k in ('quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference','resource_authority_reference','cost_decision_reference')}
    C.meta(resource['quota_provider_review_reference']);C.meta(resource['quota_provider_identity_reference'])
    carveout(C.meta(resource['root_carveout_review_reference']),{'scope_key':C.KEY,'node':request['node'],
      'resource_authority_reference':request['resource_authority_reference'],'estimated_peak_output_bytes':C.CAP})
    plan={'schema':'MOLECULENET17_DECONTAMINATION_DAY_PLAN_V1','scope_parameters':C.PARAMETERS,'wall_seconds':C.WALL,
      'output_cap_bytes':C.CAP,'output_directory':str(fresh(request['output_directory'],'artifacts')),
      'input_context_reference':request['input_context_reference'],'data_references':authority['data_references'],**resource}
    parents=C.unique([*parent_sources(context),request['input_context_reference'],Q.pin(path),*resource.values()])
    out=fresh(out);out.mkdir(parents=True,mode=0o700)
    plan['source_references']=C.unique([*C.sources(),*parents]);pr=Q.write_new(out/'plan.json',plan)
    sources=C.unique([*plan['source_references'],pr])
    for ref in sources:C.need(ref['path'] not in {d['path'] for d in plan['data_references']} and Q.pin(ref['path'])==ref,'ONLY_SOURCE_OR_SMALL_PARENTS_NO_LOGIN_BODY_HASH')
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':C.WALL,
      'estimated_peak_output_bytes':C.CAP,'source_status_stage':'MOLECULENET17_ALL_SOURCE_IDENTITY_AND_OFFICIAL27_CLOSURE',
      'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
      'scope_mode':'BOUNDED_METADATA_PREPARATION','resource_authority_reference':request['resource_authority_reference'],
      'stage_output_cap_bytes':C.CAP,'parent_evidence_references':parents,'approved_source_references':sources,'data_references':plan['data_references'],
      'all17_original_identity_and_exact27_official_acquisition_authorized':True,'unknown_or_ambiguous_is_HOLD':True,
      'global_pool_release_authorized':False}
    tr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'MOLECULENET17_DAY_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
      'plan_reference':pr,'template_reference':tr,'stage_fields':fields,'source_references':sources,'data_references':plan['data_references'],
      'resource_authority_reference':request['resource_authority_reference'],'scientific_DATA_or_network_read_on_login':False})

def finalize(path,review):
    d=Q.load(path);C.need(d['schema']=='MOLECULENET17_DAY_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=approved(d['template_reference'],review);plan=C.meta(d['plan_reference']);actual=C.inputs(C.meta(plan['input_context_reference']))
    C.need(actual['data_references']==d['data_references']==plan['data_references'],'UNCHANGED_ACTUAL_COMPLETE_INPUTS')
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'CURRENT_SOURCE_AND_SMALL_PARENT_BYTES')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
      'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':d['data_references'],
      'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(path).parent/'stage_spec.json',spec)

def actual(receipt_path,account_path):
    ref=Q.pin(receipt_path);account=Q.pin(account_path);r=C.meta(ref);_,raw=C.D.K.K.account(account,r)
    C.need(r['schema']=='MOLECULENET17_DECONTAMINATION_DAY_RECEIPT_V1' and r['status']=='STRICT17_COMPLETE_PENDING_ROOT_ACTUAL_C0_ADOPTION'
      and r['result']['complete'] is True and r['result']['unresolved']==0 and r['result']['official27_completed']==27
      and set(r['result']['all17_subdatasets'])==set(C.NAMES) and r['existing39633_graph_attempts_repeated'] is False
      and r['new_QM_UFF_calls']==0 and r['old_DATA_or_once_modified'] is False,'ACTUAL_COMPLETE_STRICT17_ONLY_HOLD_IS_NOT_READY')
    plan=C.meta(r['plan_reference']);context=C.meta(plan['input_context_reference']);C.inputs(context);proof=C.meta(r['startup_proof_reference']);req=proof['request']
    C.need(str(proof['job_id'])==str(r['job_id']) and proof['uid']==1278 and proof['node']==r['node'] and req['cpus']==16
      and req['scope_key']==C.KEY and req['scope_parameters']==C.PARAMETERS and req['data_references']==plan['data_references']
      and req['wall_seconds']==86400 and req['stage_output_cap_bytes']==C.CAP and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
      and req['execution_argv']==[Q.PY,'-B','-m',C.MODULE,'--plan',r['plan_reference']['path'],'--startup-proof',r['startup_proof_reference']['path']]
      and C.meta(proof['request_reference'])==req and r['plan_reference'] in req['source_references'],'TRUE_SINGLE_PARENT_PROOF_ARGV_DATA_RESOURCE')
    for source in plan['source_references']:C.need(source in req['source_references'] and Q.pin(source['path'])==source,'ALL_ACTUAL_SOURCE_PINS_STILL_EXACT')
    f=r['fixtures'];C.need(f['tests_run']==3 and f['all_before_any_original_DATA_or_network'] is True
      and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'REAL3_BOUNDARIES')
    coverage=C.meta(r['result']['coverage_reference']);C.need(coverage['schema']=='expansion_all_source_identity_coverage_v1' and coverage['dataset']=='moleculenet'
      and coverage['strict17_complete_candidate'] is True and coverage['all_splits'] is True and coverage['covered_roles']==['all']
      and set(coverage['covered_subdatasets'])==set(C.NAMES) and coverage['unresolved_without_identity_or_composition']==0
      and coverage['raw_artifacts']==C.unique([*plan['data_references'],*coverage['remote_acquisition']['actual_response_references']])
      and coverage['identities']==r['result']['identities_reference']
      and coverage['readback']['rows']==coverage['expected_identity_records']==coverage['identities']['rows']
      and coverage['all_source_bodies_whole_SHA_current_FD_and_EOF_verified'] is True,'COMPLETE_ORIGINAL_STRICT_CONSUMER_COVERAGE')
    return r,coverage,C.unique([ref,account,raw,r['plan_reference'],r['startup_proof_reference'],proof['request_reference'],req['scope']['review'],
      r['result']['coverage_reference'],plan['input_context_reference'],*parent_sources(context)])

def acceptance_draft(receipt,account,out):
    r,c,parents=actual(receipt,account);out=fresh(out);out.mkdir(parents=True,mode=0o700)
    template={'schema':'ROOT_MOLECULENET17_STRICT_SOURCE_ACCEPTANCE_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
      'actual_receipt_reference':Q.pin(receipt),'actual_accounting_reference':Q.pin(account),'coverage_reference':r['result']['coverage_reference'],
      'parent_evidence_references':parents,'all17_all_splits_and_variants_reviewed':True,
      'all_true_empty_spans_and_all27_official_exact_ligand_conservative_evidence_reviewed':True,
      'original_UNKNOWN_graph_and_missing_reasons_preserved':True,'dataset_READY_candidate_authorized':True,'global_pool_release_authorized':False}
    tr=Q.write_new(out/'acceptance.template.json',template)
    return Q.write_new(out/'acceptance_draft.json',{'schema':'MOLECULENET17_ACTUAL_ACCEPTANCE_DRAFT_V1','template_reference':tr,
      'actual_receipt_reference':Q.pin(receipt),'actual_accounting_reference':Q.pin(account),'scientific_DATA_opened_on_login':False})

def acceptance_finalize(path,review):
    d=Q.load(path);rr=approved(d['template_reference'],review);r,c,parents=actual(d['actual_receipt_reference']['path'],d['actual_accounting_reference']['path'])
    C.need(Q.pin(d['actual_receipt_reference']['path'])==d['actual_receipt_reference'] and Q.pin(d['actual_accounting_reference']['path'])==d['actual_accounting_reference'],
      'ACTUAL_ADOPTED_PARENTS_NOT_REPLACED')
    return Q.write_new(Path(path).parent/'moleculenet17_READY_source_candidate.json',{'dataset':'moleculenet','status':'READY',
      'version':'MOLECULENET17_ACTUAL_SOURCE_UNION:'+r['input_context_reference']['sha256'],'required_roles':['all'],'required_subdatasets':list(C.NAMES),
      'raw_artifacts':c['raw_artifacts'],'identities':c['identities'],'coverage_evidence':r['result']['coverage_reference'],
      'actual_CPU_receipt_reference':d['actual_receipt_reference'],'actual_CPU_accounting_reference':d['actual_accounting_reference'],
      'independent_Root_acceptance_reference':rr,'original_graph_UNKNOWN_and_all_costs_preserved':True,'global_pool_release':False})

def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',required=True);a.add_argument('--root-review',required=True)
    a=s.add_parser('acceptance-draft');a.add_argument('--receipt',required=True);a.add_argument('--accounting',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('acceptance-finalize');a.add_argument('--draft',required=True);a.add_argument('--root-review',required=True)
    a=p.parse_args()
    if a.action=='draft':v=draft(a.request,a.output)
    elif a.action=='finalize':v=finalize(a.draft,a.root_review)
    elif a.action=='acceptance-draft':v=acceptance_draft(a.receipt,a.accounting,a.output)
    else:v=acceptance_finalize(a.draft,a.root_review)
    print(v)
if __name__=='__main__':main()
