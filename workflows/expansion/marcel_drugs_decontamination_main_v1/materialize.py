"""Unsigned stage -> Root exact approval; actual C0 -> separate READY candidate."""
import argparse,copy
from pathlib import Path
from workflows.expansion.marcel_kraken_decontamination_main_v1.materialize import approved
from . import contract as C
Q=C.Q

def fresh(path,kind='control'):
    p=Path(path);Q.need(p.is_absolute() and '..' not in p.parts and Q.ROOT/kind in p.parents and not p.exists()
        and not any(x.is_symlink() for x in (p,*p.parents)),'FRESH_LITERAL_NON_SYMLINK_'+kind.upper());return p

def draft(request_path,out):
    request=Q.load(request_path);Q.need(request['schema']=='ROOT_REQUESTED_DRUGS_DECONTAMINATION_PROJECTION_V1'
        and request['status']=='REQUESTED_FOR_REVIEW' and request['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_APPROVAL')
    accepted=C.meta(request['accepted_native_union_root_review_reference'])
    union=accepted['declared_large_DATA_references_not_opened_by_Root']['all_name_union_reference']
    plan={'schema':'MARCEL_DRUGS_DECONTAMINATION_PLAN_V1','scope_parameters':C.PARAMETERS,
        'accepted_native_union_root_review_reference':request['accepted_native_union_root_review_reference'],
        'decontamination_policy_reference':request['decontamination_policy_reference'],'cost_decision_reference':request['cost_decision_reference'],
        'data_references':[union],'wall_seconds':request['wall_seconds'],'output_cap_bytes':C.CAP,
        'output_directory':str(fresh(request['output_directory'],'artifacts'))}
    _,parents,_,_=C.inputs(plan);Q.need(type(plan['wall_seconds'])is int and 600<=plan['wall_seconds']<=1800
        and plan['wall_seconds']%60==0,'FINITE_WHOLE_MINUTE_WALL')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(request['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_ORIGINAL_COST_AND_QUALITY_AUTHORITY')
    paths=[*(C.HERE/n for n in C.FILES),*C.OLD,*(Q.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py')]
    out=fresh(out);out.mkdir(parents=True,mode=0o700);pr=Q.write_new(out/'plan.json',plan)
    sources=C.unique([*(Q.pin(p) for p in paths),*parents,Q.pin(request_path),pr,request['resource_authority_reference'],plan['cost_decision_reference']])
    for ref in sources:Q.need(ref['path']!=union['path'] and Q.pin(ref['path'])==ref,'ONLY_SMALL_SOURCE_PARENTS_NEVER_LOGIN_UNION_PARSE_OR_SHA')
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':plan['wall_seconds'],
        'estimated_peak_output_bytes':C.CAP,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**copy.deepcopy(fields),
        'scope_mode':'BOUNDED_METADATA_PREPARATION','resource_authority_reference':request['resource_authority_reference'],'stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':[union],
        'accepted_complete_union_only_no_new_graph_or_keys':True,'all126_differences31_names_and290_multismiles_retained':True,'global_pool_release_authorized':False}
    tr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'DRUGS_DECONTAMINATION_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'template_reference':tr,'stage_fields':fields,'source_references':sources,'data_references':[union],
        'resource_authority_reference':request['resource_authority_reference'],'scientific_DATA_opened_or_hashed':False,'approval_job_or_READY_created':False})

def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='DRUGS_DECONTAMINATION_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=approved(d['template_reference'],review_path)
    for ref in d['source_references']:Q.need(Q.pin(ref['path'])==ref,'SAME_ACTUAL_SOURCE_AND_SMALL_PARENTS')
    plan=C.meta(d['plan_reference']);C.inputs(plan);Q.need(plan['data_references']==d['data_references'],'ONLY_ACTUAL_COMPLETE_UNION_DATA')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)

def closed(receipt_path,accounting_path):
    receipt_ref=Q.pin(receipt_path);account_ref=Q.pin(accounting_path);b=C.meta(receipt_ref);_,raw=C.K.K.account(account_ref,b)
    Q.need(b['schema']=='DRUGS_DECONTAMINATION_PROJECTION_RECEIPT_V1'
        and b['status']=='ALL75099_CONSERVATIVE_UNIONS_STRICT_CONSUMER_READBACK_ROOT_ACCEPTANCE_REQUIRED'
        and b['uid']==1278 and b['endpoint']=='202.38.247.57:22' and b['source_version']==C.VERSION
        and b['global_pool_release'] is False and b['new_graph_key_SDF_UFF_QM_network_calls']==0 and b['old_DATA_or_once_modified'] is False,
        'NEW_ACTUAL_C0_ONLY_IDENTITY_PROJECTION')
    plan=C.meta(b['plan_reference']);baseline,parents,archive,_=C.inputs(plan);proof=C.meta(b['startup_proof_reference']);req=proof['request']
    Q.need(proof['schema']=='FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1' and str(proof['job_id'])==str(b['job_id'])
        and proof['uid']==1278 and proof['node']==b['node'] and proof['execution_admission_granted'] is True
        and req['execution_argv']==[Q.PY,'-B','-m',C.MODULE,'--plan',b['plan_reference']['path'],'--startup-proof',b['startup_proof_reference']['path']]
        and req['scope_key']==C.KEY and req['scope_parameters']==plan['scope_parameters']==C.PARAMETERS
        and req['data_references']==plan['data_references'] and b['plan_reference'] in req['source_references']
        and C.meta(proof['request_reference'])==req and b['accepted_native_union_root_review_reference']==plan['accepted_native_union_root_review_reference'],
        'ACTUAL_PRIMARY_PLAN_PROOF_DATA_AND_ACCEPTED_UNION_ANCESTRY')
    out=Path(plan['output_directory']);Q.need(Path(receipt_path)==out/'receipt.json' and req['node']==b['node']
        and req['kind']=='analysis' and req['pilot'] is False and req['cpus']==16 and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED'
        and req['wall_seconds']==plan['wall_seconds'] and type(plan['wall_seconds'])is int and 600<=plan['wall_seconds']<=1800
        and req['stage_output_cap_bytes']==req['estimated_peak_output_bytes']==plan['output_cap_bytes']==C.CAP
        and not req.get('deferred_authority_references'),'EXACT_ACTUAL_RESOURCE_AND_OUTPUT_SCOPE')
    for path in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(path) in req['source_references'],'ACTUAL_CPU_EXACT_NEW_AND_ORIGINAL_SOURCE_PINS')
    f=b['fixtures'];Q.need(f['tests_run']==3 and f['all_before_any_DATA'] is True and all(f[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes')),'ACTUAL3_IO_GUARD_METHODS_PASS')
    result=b['result'];coverage=C.meta(result['coverage_reference'])
    for key,name in (('identities_reference','identities.jsonl'),('name_union_evidence_reference','all_name_union_projection_evidence.jsonl')):
        ref=result[key];C.data_reference({k:ref[k] for k in ('path','bytes','sha256')});Q.need(ref['path']==str(out/name),'EXACT_CLOSED_PRODUCER_OUTPUT_PATH')
    Q.need(result['coverage_reference']['path']==str(out/'coverage.json') and result['names']==75099
        and result['conservation']=={'conformers':558002,'native_unknown':0,'mismatch_conformers':126,'mismatch_names':31,'multi_SMILES_names':290,'unresolved':0}
        and result['all_input_and_output_SHA_EOF_and_same_FD_verified'] is True,'ACTUAL_ALL_POPULATIONS_AND_VARIANTS_CONSERVED')
    Q.need(coverage['schema']=='expansion_all_source_identity_coverage_v1' and coverage['dataset']=='marcel_drugs75k'
        and coverage['all_splits'] is True and coverage['covered_roles']==['all'] and coverage['covered_subdatasets']==[]
        and coverage['unresolved_without_identity_or_composition']==0 and coverage['expected_identity_records']==75099
        and coverage['all_native_SDF_conformers']==558002 and coverage['all_source_context_rows']==633101 and coverage['all_original_CSV_names']==75099
        and coverage['conservation']==result['conservation'] and coverage['identities']==result['identities_reference'] and coverage['identities']['rows']==75099
        and coverage['raw_artifacts']==[archive,*plan['data_references']] and coverage['name_union_evidence_reference']==result['name_union_evidence_reference']
        and coverage['actual_union_root_review_reference']==plan['accepted_native_union_root_review_reference'] and coverage['native_split']=='UNKNOWN_NOT_INFERRED'
        and coverage['all_old_consumed_DATA_whole_SHA_same_FD_EOF_verified'] is coverage['all_new_DATA_readback_complete'] is True
        and coverage['original_strict_identity_keys_consumer_rows']==75099 and coverage['Root_candidate_acceptance_or_global_pool_release'] is False,
        'EXACT_ORIGINAL_CONSUMER_COVERAGE_NO_SELF_RELEASE')
    return b,coverage,C.unique([receipt_ref,account_ref,raw,b['plan_reference'],b['startup_proof_reference'],proof['request_reference'],
        result['coverage_reference'],req['scope']['review'],req['queue_authority_reference'],plan['cost_decision_reference'],*parents])

def acceptance_draft(receipt_path,accounting_path,out):
    b,coverage,parents=closed(receipt_path,accounting_path);out=fresh(out);out.mkdir(parents=True,mode=0o700)
    template={'schema':'ROOT_DRUGS_DECONTAMINATION_PROJECTION_ACCEPTANCE_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'actual_projection_receipt_reference':Q.pin(receipt_path),'actual_projection_accounting_reference':Q.pin(accounting_path),
        'coverage_reference':b['result']['coverage_reference'],'parent_evidence_references':parents,
        'all75099_names558002_conformers633101_context_reviewed':True,'all126_differences31_names_and290_multismiles_conservatively_retained':True,
        'all5_consumer_fields_no_unresolved_rows_and_native_split_UNKNOWN_reviewed':True,'dataset_READY_candidate_authorized_after_actual_C0':True,
        'global_pool_release_authorized':False}
    tr=Q.write_new(out/'acceptance.template.json',template)
    return Q.write_new(out/'acceptance_draft.json',{'schema':'DRUGS_DECONTAMINATION_ACCEPTANCE_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'template_reference':tr,'actual_receipt_reference':Q.pin(receipt_path),'actual_accounting_reference':Q.pin(accounting_path),
        'scientific_DATA_opened_or_hashed_on_login':False,'READY_or_global_manifest_modified':False})

def acceptance_finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='DRUGS_DECONTAMINATION_ACCEPTANCE_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_ACTUAL_ACCEPTANCE_DRAFT')
    rr=approved(d['template_reference'],review_path);b,coverage,parents=closed(d['actual_receipt_reference']['path'],d['actual_accounting_reference']['path'])
    Q.need(Q.pin(d['actual_receipt_reference']['path'])==d['actual_receipt_reference'] and Q.pin(d['actual_accounting_reference']['path'])==d['actual_accounting_reference'],
        'ACTUAL_ACCEPTED_C0_PARENTS_UNCHANGED')
    plan=C.meta(b['plan_reference']);_,_,_,entry=C.inputs(plan)
    source={'dataset':'marcel_drugs75k','status':'READY','version':C.VERSION,'required_roles':['all'],'official_metadata':entry['official_metadata'],
        'raw_artifacts':coverage['raw_artifacts'],'identities':coverage['identities'],'coverage_evidence':b['result']['coverage_reference'],
        'actual_CPU_receipt_reference':d['actual_receipt_reference'],'actual_CPU_accounting_reference':d['actual_accounting_reference'],
        'independent_Root_acceptance_reference':rr,'preserved_name_union_evidence_reference':b['result']['name_union_evidence_reference'],
        'original_native_union_root_review_reference':plan['accepted_native_union_root_review_reference'],'global_pool_release':False}
    return Q.write_new(Path(draft_path).parent/'drugs_READY_source_candidate.json',source)

def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=s.add_parser('acceptance-draft');a.add_argument('--receipt',type=Path,required=True);a.add_argument('--accounting',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('acceptance-finalize');a.add_argument('--draft',type=Path,required=True);a.add_argument('--root-review',type=Path,required=True)
    a=p.parse_args()
    if a.action=='draft':result=draft(a.request,a.output)
    elif a.action=='finalize':result=finalize(a.draft,a.root_review)
    elif a.action=='acceptance-draft':result=acceptance_draft(a.receipt,a.accounting,a.output)
    else:result=acceptance_finalize(a.draft,a.root_review)
    print(result)
if __name__=='__main__':main()
