"""Small metadata only: explicit missing parents, exact generic16 scope, external seal."""
from __future__ import annotations
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q


def fresh(path,base):
    p=Path(path);C.need(p.is_absolute() and base in p.parents and '..' not in p.parts and not p.exists()
        and not any(x.is_symlink() for x in (p,*p.parents)),'FRESH_LITERAL_OWNED_METADATA_OR_OUTPUT');return p


def proposal(output):
    out=fresh(output,C.ROOT/'control');out.mkdir(parents=True,mode=0o700)
    request={'schema':'ROOT_REQUESTED_FAMILY_EXPORT_DAY_V1','status':'NONEXECUTABLE_MISSING_ACTUAL_FINAL_PARENTS','requested_by':None,
        'purpose':'pilot55k','node':None,'output_directory':None,'output_cap_bytes':None,
        **{k:None for k in C.REQUIRED},'actual_D3_pilot_review_reference':None,'model_loader_ACK_reference':None,
        'resume_adoption_reference':None,'final_release_mode':'SAME_PARENT_REVIEWED_CANDIDATE',
        'future_hash_or_Model_ACK_created':False,'science_DATA_read_on_login':False}
    return Q.write_new(out/'request.nonexecutable.json',request)


def draft(path,output):
    request=Q.load(path);C.need(request['schema']=='ROOT_REQUESTED_FAMILY_EXPORT_DAY_V1'
        and request['status']=='REQUESTED_FOR_REVIEW' and request['requested_by']=='root','REAL_ROOT_REQUEST_NOT_SELF_APPROVAL')
    out=fresh(output,C.ROOT/'control');out.mkdir(mode=0o700,parents=True)
    missing=[k for k in C.REQUIRED if not isinstance(request.get(k),dict)]
    if request['purpose']=='full':missing.extend(k for k in ('actual_D3_pilot_review_reference','model_loader_ACK_reference') if not isinstance(request.get(k),dict))
    if not missing:
        from workflows.data_v1_final.labels.final_release_v1.contract import validate_directive
        check=validate_directive(C.meta(request['final_release_directive_reference']))
        missing.extend(check['missing'])
    if missing:return Q.write_new(out/'NONEXECUTABLE.json',{'status':'NONEXECUTABLE','missing':missing,'stage_created':False,'DATA_opened_or_hashed':False})
    p={k:copy.deepcopy(v) for k,v in request.items() if k not in ('schema','status','requested_by')}
    C.need(p['node'] in ('compute-0-14','compute-0-18') and p['final_release_mode']=='SAME_PARENT_REVIEWED_CANDIDATE','CURRENT_NODE_RESOURCE_AND_INLINE_CANDIDATE_MODE')
    fresh(p['output_directory'],C.OUTPUT);fresh(C.resource_output(p),C.ROOT/'artifacts/labels/source_status_v1')
    p.update(schema='FAMILY_EXPORT_DAY_PLAN_V1',wall_seconds=86400);p['scope_parameters']=C.parameters(p)
    result=C.final_parents(p);data=result[7];parents=result[8]
    resource=C.meta(p['resource_review_reference']);C.need(resource['schema']=='ROOT_FAMILY_EXPORT_DAY_RESOURCE_REVIEW_V1'
        and resource['status']=='APPROVED_EXACT_CURRENT_RESOURCE_CONTEXT' and resource['reviewer']=='root'
        and resource['node']==p['node'] and resource['cpus']==16 and resource['wall_seconds']==86400
        and resource['output_directory']==p['output_directory'] and resource['parent_output_cap_bytes']==p['output_cap_bytes']
        and all(resource[k]==p[k] for k in ('quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference'))
        and resource['finite_provider_covers_parent_plus300_at_start'] is True and resource['all_other_future_writers_included'] is True,
        'SEPARATE_TRUE_CURRENT_NODE_QUOTA_PROVIDER_CARVEOUT_REVIEW_NOT_OLD13_FACTS')
    carveout=C.meta(p['root_carveout_review_reference']);C.need(carveout['parent_output_cap_bytes']==p['output_cap_bytes']
        and carveout['parent_included_exactly_once'] is True and carveout['all_other_active_and_future_writers_included'] is True,
        'WHOLE_CURRENT_FUTURE_INCLUDES_OWN_CAP_ONCE')
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(p['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(p['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_REPORT_CONTINUE_NOT_SCIENTIFIC_WAIVER')
    refs=C.unique([*C.sources(),*parents,Q.pin(path)])
    if p.get('resume_adoption_reference'):refs=C.unique([*refs,p['resume_adoption_reference']])
    C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'ALL_NUMERIC_JSON_SMALL_SIZE_STILL_DATA')
    p.update(source_references=refs,data_references=data);pr=Q.write_new(out/'plan.json',p);refs=C.unique([*refs,pr])
    fields={'kind':'analysis','scope_key':C.SCOPE,'scope_parameters':p['scope_parameters'],'pilot':False,'node':p['node'],
        'producer_plan_reference':pr,'wall_seconds':86400,'estimated_peak_output_bytes':p['output_cap_bytes'],
        'source_status_stage':'FAMILY_EXPORT_'+p['purpose'].upper(),
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',pr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__']}
    template={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**fields,
        'resource_authority_reference':p['resource_authority_reference'],'scope_mode':'BOUNDED_PERFORMANCE_BATCH',
        'stage_output_cap_bytes':p['output_cap_bytes'],'parent_evidence_references':parents,'bounded_batch_limits_reviewed':True,
        'approved_source_references':refs,'data_references':data,'resource_current_context_reviewed':False,
        'same_Parent_candidate_export_QA_not_future_C0':True,'joint_policy_not_chosen_by_exporter':True}
    rr=Q.write_new(out/'root_review.template.json',template)
    return Q.write_new(out/'draft.json',{'schema':'FAMILY_EXPORT_DAY_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'root_review_template_reference':rr,'stage_fields':fields,'source_references':refs,
        'data_references':data,'resource_authority_reference':p['resource_authority_reference'],'DATA_opened_statted_or_hashed':False})


def finalize(path,review):
    d=Q.load(path);C.need(d['schema']=='FAMILY_EXPORT_DAY_DRAFT_V1','EXACT_DRAFT');ref=Q.pin(review);r=C.meta(ref);template=C.meta(d['root_review_template_reference'])
    C.need(ref!=d['root_review_template_reference'] and r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root'
        and r['resource_current_context_reviewed'] is True,'INDEPENDENT_ACTUAL_ROOT_APPROVAL')
    for k,v in template.items():
        if k not in ('status','reviewer','resource_current_context_reviewed'):C.need(r[k]==v,'EXACT_REVIEW_FIELD:'+k)
    for source in d['source_references']:C.need(Q.pin(source['path'])==source,'SOURCE_OR_SMALL_PARENT_CHANGED')
    p=C.meta(d['plan_reference']);C.need(C.final_parents(p)[7]==d['data_references']==p['data_references'],'SAME_DECLARED_CPU_DATA_ONLY')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':p['output_cap_bytes'],'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':ref}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(path).parent/'stage_spec.json',spec)


def candidate(chain_path,output):
    chain=Q.load(chain_path);r,proof,p=C.validate_actual_closure(chain)
    return Q.write_new(fresh(output,C.ROOT/'control'),{'schema':'FAMILY_EXPORT_EXTERNAL_SEAL_CANDIDATE_V1','status':'PENDING_INDEPENDENT_ROOT_C0_AND_EXACT_FINAL_LABEL_RELEASE_REVIEW',
        'actual_closure_references':chain,'actual_parent_job_id':str(proof['job_id']),'purpose':p['purpose'],
        'inline_final_label_candidate':r['inline_final_label_candidate'],'stores_catalogue_reference':r['stores_catalogue_reference'],
        'source_release_reference':p['source_release_reference'],'selection_reference':r['selection_reference'],'verification_reference':r['verification_reference'],
        'source_roundtrip_records':10000,'selected_molecules_by_role':r['selected_molecules_by_role'],
        'joint_policy_reference':C.meta(p['final_release_directive_reference'])['joint_policy_reference'],
        'future_Current_Parent_C0_created':False,'DATA_read_or_hashed_on_login':False,'consumer_release':False})


def seal(review_path,output):
    rr=Q.pin(review_path);review=C.meta(rr);C.need(review['schema']=='ROOT_FAMILY_EXPORT_PUBLICATION_REVIEW_V1'
        and review['status']=='APPROVED_EXACT_ACTUAL_C0_AND_SAME_OBJECTS' and review['reviewer']=='root','ROOT_EXTERNAL_PUBLICATION_REVIEW')
    before=C.meta(review['candidate_reference']);r,proof,p=C.validate_actual_closure(before['actual_closure_references'])
    release=C.meta(review['final_label_release_reference']);candidate=r['inline_final_label_candidate']
    C.need(release['schema']=='ROOT_FINAL_LABEL_RELEASE_V1' and release['final_consumer_release'] is True
        and release['candidate_reference']==candidate['candidate_reference']
        and all(release[k]==candidate[k] for k in ('registry_reference','mapping_reference','normalization_reference','mask_release_reference')),
        'EXTERNAL_LABEL_RELEASE_EXACT_SAME_CANDIDATE_SHA_NOT_MUTATED_CONFIG_OR_EQUAL_BY_ASSERTION')
    C.need(before['stores_catalogue_reference']==r['stores_catalogue_reference'] and review['stores_catalogue_reference']==r['stores_catalogue_reference']
        and before['verification_reference']==r['verification_reference'],'EXACT_LMDB_CATALOGUE_AND_CPU_WHOLE_SHA_READBACK')
    full=p['purpose']=='full';C.need(not full or release['training_ready'] is True,'FULL_NEEDS_TRUE_FINAL_PPRIME_AND_MODEL_RELEASE')
    source=C.meta(p['source_release_reference'])
    independent=source.get('independent_Pprime_field_and_mask_authority_reference')
    if full:C.independent_pprime(independent,p['D5_components_reference'])
    result={'schema':'ROOT_ACCEPTED_FAMILY_EXPORT_RELEASE_V1','status':'FULL_V1_FROZEN' if full else 'BOUNDED_D3_50K_TRAIN_5K_VAL_FROZEN_NOT_FULL',
        'actual_closure_references':before['actual_closure_references'],'root_publication_review_reference':rr,'final_label_release_reference':review['final_label_release_reference'],
        'stores_catalogue_reference':r['stores_catalogue_reference'],'verification_reference':r['verification_reference'],
        'selection_reference':r['selection_reference'],'source_release_reference':p['source_release_reference'],
        'joint_policy_reference':before['joint_policy_reference'],'independent_Pprime_field_and_mask_authority_reference':independent,'purpose':p['purpose'],'consumer_release':True,'training_ready':full,
        'inner_store_or_config_bytes_changed_by_seal':False,'no_new_science_or_DATA_read_on_login':True}
    C.validate_published_release(result)
    return Q.write_new(fresh(output,C.ROOT/'control'),result)


def delivery_template(release_path,output):
    ref=Q.pin(release_path);release=C.meta(ref);C.need(release['schema']=='ROOT_ACCEPTED_FAMILY_EXPORT_RELEASE_V1' and release['consumer_release'] is True,'ACTUAL_EXTERNAL_EXPORT_RELEASE_FIRST')
    r,_,_=C.validate_actual_closure(release['actual_closure_references']);out=fresh(output,C.ROOT/'control')
    return Q.write_new(out,{'schema':'ROOT_REQUESTED_D6_CPU_ONLY_DELIVERY_V1','status':'NONEXECUTABLE_PENDING_ACTUAL_NODE_CPU_POLICY_AND_ALLOCATION',
        'accepted_export_reference':ref,'actual_node_CPU_policy_reference':None,'output_directory':None,'output_cap_bytes':None,
        'wall_seconds':86400,'local_disk_reserve_bytes':None,'actual_CPU_node_and_tmp_capacity_not_yet_observed':True,
        'actual_accepted_LMDB_data_bytes':r['LMDB_data_bytes'],'actual_immutable_manifest_bytes':r['immutable_manifest_bytes'],
        'source_references':C.unique([*C.sources(),ref,*release['actual_closure_references'].values(),release['final_label_release_reference']]),
        'data_references':[release['stores_catalogue_reference']],'transitive_source_catalogue_authority':release['stores_catalogue_reference'],
        'GPU_requested':False,'Model_loader_ACK_created':False,'DATA_opened_on_login':False})

def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    x=s.add_parser('proposal');x.add_argument('--output',type=Path,required=True)
    x=s.add_parser('delivery-template');x.add_argument('--accepted-export',type=Path,required=True);x.add_argument('--output',type=Path,required=True)
    x=s.add_parser('draft');x.add_argument('--request',type=Path,required=True);x.add_argument('--output',type=Path,required=True)
    x=s.add_parser('finalize');x.add_argument('--draft',type=Path,required=True);x.add_argument('--root-review',type=Path,required=True)
    x=s.add_parser('candidate');x.add_argument('--closure',type=Path,required=True);x.add_argument('--output',type=Path,required=True)
    x=s.add_parser('seal');x.add_argument('--root-review',type=Path,required=True);x.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.action=='delivery-template':r=delivery_template(a.accepted_export,a.output)
    elif a.action=='proposal':r=proposal(a.output)
    elif a.action=='draft':r=draft(a.request,a.output)
    elif a.action=='finalize':r=finalize(a.draft,a.root_review)
    elif a.action=='candidate':r=candidate(a.closure,a.output)
    else:r=seal(a.root_review,a.output)
    print(r)

if __name__=='__main__':main()