"""Unsigned Root candidate/finalize, then actual-C0 independent acceptance only."""
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def fresh(path,kind='control'):
    path=Path(path);Q.need(path.is_absolute() and '..' not in path.parts and Q.ROOT/kind in path.parents and not path.exists(),'FRESH_LITERAL_'+kind.upper());return path


def draft(request_path,out):
    request=Q.load(request_path);Q.need(request['schema']=='ROOT_REQUESTED_KRAKEN_DECONTAMINATION_PROJECTION_V1'
        and request['status']=='REQUESTED_FOR_REVIEW' and request['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_APPROVAL')
    baseline=C.meta(request['accepted_full_receipt_reference'])
    plan={'schema':'MARCEL_KRAKEN_DECONTAMINATION_PLAN_V1','scope_parameters':C.PARAMETERS,
        'accepted_full_receipt_reference':request['accepted_full_receipt_reference'],'accepted_full_accounting_reference':request['accepted_full_accounting_reference'],
        'decontamination_policy_reference':request['decontamination_policy_reference'],'cost_decision_reference':request['cost_decision_reference'],
        'data_references':[baseline[k] for k in ('selected_result_journal_reference','all_source_relationship_journal_reference','all_root_union_reference')],
        'wall_seconds':request['wall_seconds'],'output_cap_bytes':C.CAP,'output_directory':str(fresh(request['output_directory'],'artifacts'))}
    _,parents=C.inputs(plan)
    Q.need(type(plan['wall_seconds']) is int and 600<=plan['wall_seconds']<=1800 and plan['wall_seconds']%60==0,'FINITE_WHOLE_MINUTE_WALL')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(request['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(plan['cost_decision_reference']);Q.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'ACTUAL_COST_AND_QUALITY_AUTHORITY')
    out=fresh(out);out.mkdir(parents=True,mode=0o700);pr=Q.write_new(out/'plan.json',plan)
    sources=C.unique([*(Q.pin(C.HERE/n) for n in C.FILES),*(Q.pin(p) for p in C.OLD),
        *(Q.pin(p) for p in (Q.REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py')),
        *parents,Q.pin(request_path),pr,request['resource_authority_reference'],plan['cost_decision_reference']])
    forbidden={r['path'] for r in plan['data_references']}
    for r in sources:Q.need(r['path'] not in forbidden and Q.pin(r['path'])==r,'SMALL_SOURCE_PARENT_ONLY_NO_LOGIN_DATA_READ_OR_HASH')
    fields={'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.PARAMETERS,'pilot':False,'wall_seconds':plan['wall_seconds'],
        'estimated_peak_output_bytes':C.CAP,'source_status_stage':C.STAGE,
        'execution_argv':[Q.PY,'-B','-m',C.MODULE,'--plan',str(out/'plan.json'),'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={**copy.deepcopy(fields),'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'scope_mode':'BOUNDED_METADATA_PREPARATION','resource_authority_reference':request['resource_authority_reference'],'stage_output_cap_bytes':C.CAP,
        'parent_evidence_references':parents,'approved_source_references':sources,'data_references':plan['data_references'],
        'identity_only_all_native_variants_authorized':True,'global_pool_release_authorized':False}
    tr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft_receipt.json',{'schema':'KRAKEN_DECONTAMINATION_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'template_reference':tr,'stage_fields':fields,'source_references':sources,'data_references':plan['data_references'],
        'resource_authority_reference':request['resource_authority_reference'],'scientific_DATA_opened_or_hashed':False,'approval_job_or_READY_created':False})


def approved(template_ref,review_path):
    ref=Q.pin(review_path);review=C.meta(ref);template=C.meta(template_ref)
    Q.need(ref!=template_ref and review['status']=='APPROVED_FOR_EXACT_STAGE' and review['reviewer']=='root','INDEPENDENT_ROOT_APPROVAL_NOT_TEMPLATE')
    for k,v in template.items():
        if k not in ('status','reviewer'):Q.need(review[k]==v,'EXACT_ROOT_REVIEW_FIELD:'+k)
    return ref


def finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='KRAKEN_DECONTAMINATION_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_PENDING_DRAFT')
    rr=approved(d['template_reference'],review_path)
    for r in d['source_references']:Q.need(Q.pin(r['path'])==r,'ALL_SOURCES_PARENTS_UNCHANGED')
    plan=C.meta(d['plan_reference']);C.inputs(plan);Q.need(plan['data_references']==d['data_references'],'ONLY_THREE_ACTUAL_DATA_LOCATORS')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':C.CAP,'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_METADATA_PREPARATION','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def closed(receipt_path,accounting_path):
    receipt_ref=Q.pin(receipt_path);account_ref=Q.pin(accounting_path);b=C.meta(receipt_ref);_,raw=C.K.account(account_ref,b)
    Q.need(b['schema']=='KRAKEN_DECONTAMINATION_PROJECTION_RECEIPT_V1'
        and b['status']=='ALL_NATIVE_VARIANTS_PROJECTED_ORIGINAL_CONSUMER_READBACK_ROOT_ACCEPTANCE_REQUIRED'
        and b['uid']==1278 and b['endpoint']=='202.38.247.57:22' and b['source_version']==C.VERSION
        and b['global_pool_release'] is False and b['new_graph_pickle_UFF_QM_network_calls']==0 and b['old_data_or_once_modified'] is False,
        'NEW_ACTUAL_C0_IDENTITY_ONLY_RECEIPT')
    plan=C.meta(b['plan_reference']);baseline,parents=C.inputs(plan);proof=C.meta(b['startup_proof_reference']);req=proof['request']
    expected=[Q.PY,'-B','-m',C.MODULE,'--plan',b['plan_reference']['path'],'--startup-proof',b['startup_proof_reference']['path']]
    Q.need(str(proof['job_id'])==str(b['job_id']) and proof['uid']==1278 and proof['node']==b['node'] and proof['execution_admission_granted'] is True
        and req['execution_argv']==expected and req['scope_key']==C.KEY and req['scope_parameters']==plan['scope_parameters']==C.PARAMETERS
        and req['data_references']==plan['data_references'] and b['plan_reference'] in req['source_references']
        and C.meta(proof['request_reference'])==req and b['accepted_full_receipt_reference']==plan['accepted_full_receipt_reference']
        and b['accepted_full_accounting_reference']==plan['accepted_full_accounting_reference'],'NEW_ACTUAL_PRIMARY_FULL_ARGV_PLAN_PROOF_AND_ORIGIN')
    output=Path(plan['output_directory'])
    Q.need(str(Path(receipt_path))==str(output/'receipt.json') and req['node']==b['node'] and req['kind']=='analysis' and req['pilot'] is False
        and req['cpus']==16 and req['memory_policy']=='SLURM_DEFAULT_UNSPECIFIED' and req['wall_seconds']==plan['wall_seconds']
        and req['stage_output_cap_bytes']==req['estimated_peak_output_bytes']==C.CAP and plan['output_cap_bytes']==C.CAP
        and not req.get('deferred_authority_references'),'EXACT_NEW_OUTPUT_AND_ACTUAL_RESOURCE_REQUEST')
    for p in [*(C.HERE/n for n in C.FILES),*C.OLD]:Q.need(Q.pin(p) in req['source_references'],'ACTUAL_CPU_USED_EXACT_ADAPTER_AND_ORIGINAL_SOURCES')
    fixture=b['fixtures'];Q.need(fixture['tests_run']==3 and all(fixture[k]==0 for k in ('failures','errors','skips','expected_failures','unexpected_successes'))
        and fixture['all_before_any_DATA'] is True,'ACTUAL3_PURE_BEFORE_DATA')
    result=b['result'];coverage=C.meta(result['coverage_reference'])
    Q.need(result['coverage_reference']['path']==str(output/'coverage.json')
        and result['identities_reference']['path']==str(output/'identities.jsonl')
        and result['native_provenance_reference']['path']==str(output/'all_native_identity_provenance.jsonl')
        and result['root_union_evidence_reference']['path']==str(output/'all_root_union_projection_evidence.jsonl'),'EXACT_PRODUCER_OUTPUT_LOCATORS')
    for key in ('identities_reference','native_provenance_reference','root_union_evidence_reference'):
        C.data_reference({k:result[key][k] for k in ('path','bytes','sha256')})
    Q.need(result['root_rows']==result['consumer_readback_rows']==1552 and result['conformer_rows']==21287 and result['relationship_rows']==22839
        and result['multiple_full_key_roots']==134 and result['comparison_counts']==baseline['root_SMILES_vs_MolBlock_comparison_counts']
        and result['unknown_by_kind']==baseline['unknown_by_kind'] and result['unresolved_root_identities']==0
        and result['all_input_and_output_SHA_EOF_and_same_FD_verified'] is True,'NEW_CPU_EXACT_ALL_SOURCE_CONSERVATION_AND_READBACK')
    Q.need(coverage['schema']=='expansion_all_source_identity_coverage_v1' and coverage['dataset']=='marcel_kraken'
        and coverage['all_splits'] is True and coverage['covered_roles']==['all'] and coverage['covered_subdatasets']==[]
        and coverage['unresolved_without_identity_or_composition']==0 and coverage['expected_identity_records']==1552
        and coverage['all_native_conformer_records']==21287 and coverage['all_native_relationship_records']==22839
        and coverage['identities']==result['identities_reference'] and coverage['identities']['rows']==1552
        and coverage['native_provenance_reference']==result['native_provenance_reference'] and coverage['root_union_evidence_reference']==result['root_union_evidence_reference']
        and coverage['raw_artifacts']==[baseline['archive_reference'],*plan['data_references']]
        and coverage['all_old_DATA_whole_SHA_same_FD_EOF_verified'] is coverage['all_new_DATA_readback_complete'] is True
        and coverage['original_strict_identity_keys_consumer_rows']==1552 and coverage['Root_candidate_acceptance_or_global_pool_release'] is False,
        'CPU_COVERAGE_MATCHES_ORIGINAL_CONSUMER_CONTRACT_NO_SELF_RELEASE')
    return b,coverage,C.unique([receipt_ref,account_ref,raw,b['plan_reference'],b['startup_proof_reference'],proof['request_reference'],
        result['coverage_reference'],req['scope']['review'],req['queue_authority_reference'],plan['cost_decision_reference'],*parents])


def acceptance_draft(receipt_path,accounting_path,out):
    b,coverage,parents=closed(receipt_path,accounting_path);out=fresh(out);out.mkdir(parents=True,mode=0o700)
    template={'schema':'ROOT_KRAKEN_DECONTAMINATION_PROJECTION_ACCEPTANCE_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'actual_projection_receipt_reference':Q.pin(receipt_path),'actual_projection_accounting_reference':Q.pin(accounting_path),
        'coverage_reference':b['result']['coverage_reference'],'parent_evidence_references':parents,
        'all1552_roots_all21287_conformers_all22839_relationships_reviewed':True,'all134_multikey_roots_and1201_differences_conservatively_retained':True,
        'all5_consumer_fields_and_no_unresolved_rows_reviewed':True,'dataset_READY_candidate_authorized_after_actual_C0':True,'global_pool_release_authorized':False}
    ref=Q.write_new(out/'acceptance.template.json',template)
    return Q.write_new(out/'acceptance_draft.json',{'schema':'KRAKEN_DECONTAMINATION_ACCEPTANCE_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'template_reference':ref,'actual_receipt_reference':Q.pin(receipt_path),'actual_accounting_reference':Q.pin(accounting_path),
        'scientific_DATA_opened_or_hashed_on_login':False,'READY_or_global_manifest_modified':False})


def acceptance_finalize(draft_path,review_path):
    d=Q.load(draft_path);Q.need(d['schema']=='KRAKEN_DECONTAMINATION_ACCEPTANCE_DRAFT_V1' and d['status']=='PENDING_INDEPENDENT_ROOT_REVIEW','EXACT_ACCEPTANCE_DRAFT')
    rr=approved(d['template_reference'],review_path)
    b,coverage,parents=closed(d['actual_receipt_reference']['path'],d['actual_accounting_reference']['path'])
    Q.need(Q.pin(d['actual_receipt_reference']['path'])==d['actual_receipt_reference'] and Q.pin(d['actual_accounting_reference']['path'])==d['actual_accounting_reference'],
        'ACTUAL_ACCEPTED_C0_REFERENCES_UNCHANGED')
    source={'dataset':'marcel_kraken','status':'READY','version':C.VERSION,'required_roles':['all'],
        'official_metadata':['https://github.com/SXKDZ/MARCEL/blob/'+C.COMMIT+'/datasets/Kraken/README.md'],
        'raw_artifacts':coverage['raw_artifacts'],'identities':coverage['identities'],'coverage_evidence':b['result']['coverage_reference'],
        'actual_CPU_receipt_reference':d['actual_receipt_reference'],'actual_CPU_accounting_reference':d['actual_accounting_reference'],
        'independent_Root_acceptance_reference':rr,'preserved_native_provenance_reference':b['result']['native_provenance_reference'],
        'preserved_root_union_evidence_reference':b['result']['root_union_evidence_reference'],'global_pool_release':False}
    return Q.write_new(Path(draft_path).parent/'kraken_READY_source_candidate.json',source)


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
