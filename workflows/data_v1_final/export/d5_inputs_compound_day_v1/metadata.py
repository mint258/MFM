"""Small-parent-only Root proposal, one day request, actual C0 component acceptance."""
from __future__ import annotations
import argparse,copy
from pathlib import Path
from . import contract as C
Q=C.Q
REQUIRED=('common_closure_references','postprocess_entry_reference','ordinary_source_review_reference',
    'ordinary_N1_preparation_policy_reference','hof_authority_reference','native_source_frame_review_reference',
    'resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference',
    'root_carveout_review_reference','cost_decision_reference')


def fresh(path):
    p=Path(path);C.need(p.is_absolute() and C.ROOT/'control' in p.parents and not p.exists() and '..' not in p.parts
        and not any(v.is_symlink() for v in (p,*p.parents)),'ONE_FRESH_CONTROL_DIRECTORY');p.mkdir(parents=True,mode=0o700);return p


def proposal(output):
    out=fresh(output)
    value={'schema':'ROOT_REQUESTED_D5_COMPOUND_DAY_V1','status':'UNSIGNED_NONEXECUTABLE_TEMPLATE','requested_by':None,
        'purpose':'pilot512','phase':'ordinary_WP5_and_D5','cpus':64,'node':'compute-0-14','wall_seconds':86400,
        'output_cap_bytes':64<<30,'logical_partition_molecules':512,'seed':None,'output_directory':None,'job_name':None,
        **{k:None for k in REQUIRED},'WP5_input_derivation_authority_reference':None,'D5_input_view_review_reference':None,
        'actual512_review_reference':None,'actual_child_input_authority_reference':None,'N1_final_policy_reference':None,
        'previous_compound_closures':[],'previous_prefix_adoption_review_references':[],
        'future_paths_are_not_authority':True,'D5_jointly_frozen':False}
    return Q.write_new(out/'request.template.json',value)


def draft(path,output):
    value=Q.load(path);C.need(value['schema']=='ROOT_REQUESTED_D5_COMPOUND_DAY_V1' and value['status']=='REQUESTED_FOR_REVIEW'
        and value['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_UNSIGNED_TEMPLATE')
    out=fresh(output);missing=[k for k in REQUIRED if not value.get(k)]
    for k in ('output_directory','job_name'):
        if not value.get(k):missing.append(k)
    if type(value.get('seed')) is not int:missing.append('actual_Root_seed')
    if value['purpose']=='full' and not value.get('actual512_review_reference'):missing.append('actual512_review_reference')
    if value['phase']!='ordinary_base' and not value.get('WP5_input_derivation_authority_reference'):missing.append('WP5_input_derivation_authority_reference')
    if value['purpose']=='full' and value['phase']!='ordinary_base' and not value.get('D5_input_view_review_reference'):missing.append('D5_input_view_review_reference')
    if missing:return Q.write_new(out/'pending.json',{'schema':'D5_COMPOUND_PENDING_V1','status':'NONEXECUTABLE_PENDING_ACTUAL_PARENTS',
        'missing':missing,'science_DATA_opened':False,'submitted':False,'D5_jointly_frozen':False})
    plan=copy.deepcopy(value);plan.update(schema='D5_COMPOUND_DAY_PLAN_V1')
    target=Path(plan['output_directory']);C.need(C.OUTPUT in target.parents and not target.exists() and '..' not in target.parts
        and not any(p.is_symlink() for p in (target,*target.parents)),'FRESH_OWN_CPU_OUTPUT_OLD_DATA_READONLY')
    plan['scope_parameters']=C.parameters(plan);plan['source_compatibility_references']=C.unique([Q.pin(p) for p in C.source_paths()])
    common,formal,hof,data,parents=C.inputs(plan)
    from workflows.data_v1_final.execution.cpu_analysis_day_v2 import contract as Resource
    resource={'scope_key':'d5_inputs_compound_day_v1','node':plan['node'],'cpus':plan['cpus'],
        'estimated_peak_output_bytes':plan['output_cap_bytes'],**{k:plan[k] for k in ('resource_authority_reference',
        'quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')}}
    Resource.resources(resource)
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'COST_REPORT_CONTINUE_NOT_A_QUALITY_WAIVER')
    refs=C.unique([*plan['source_compatibility_references'],*parents,Q.pin(path),*(plan[k] for k in ('resource_authority_reference',
        'quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference','cost_decision_reference')),
        *Resource.Provider.references(plan['quota_provider_review_reference'])])
    C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'SMALL_SOURCE_AND_SCIENTIFIC_DATA_SEPARATE')
    for ref in refs:C.need(Q.pin(ref['path'])==ref,'INSTALLED_CURRENT_SOURCE_AND_SMALL_AUTHORITY_BYTES_EXACT')
    plan.update(source_references=refs,data_references=data);pr=Q.write_new(out/'plan.json',plan)
    request={'schema':'ROOT_REQUESTED_ANALYSIS_DAY_V1','status':'PENDING_ROOT_REQUEST_REVIEW','requested_by':None,
        'job_name':plan['job_name'],'cpus':plan['cpus'],'node':plan['node'],'scope_key':'d5_inputs_compound_day_v1',
        'scope_parameters':plan['scope_parameters'],'producer_plan_reference':pr,'estimated_peak_output_bytes':plan['output_cap_bytes'],
        **{k:plan[k] for k in ('resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')},
        'source_references':C.unique([*refs,pr]),'data_references':data}
    rr=Q.write_new(out/'resource_request.template.json',request)
    return Q.write_new(out/'draft_receipt.json',{'schema':'D5_COMPOUND_DRAFT_V1','status':'PENDING_SEPARATE_ROOT_AND_SHARED_RESOURCE_REVIEW',
        'plan_reference':pr,'resource_request_template_reference':rr,'actual_parent_evidence_references':parents,
        'scientific_DATA_opened_statted_or_hashed_on_login':False,'submitted':False,'D5_jointly_frozen':False})


def candidate(closure_path,output):
    chain=Q.load(closure_path);receipt,plan,refs=C.closure(chain);out=fresh(output)
    value={'schema':'D5_COMPOUND_ACTUAL_C0_COMPONENT_CANDIDATE_V1','status':'PENDING_INDEPENDENT_ROOT_COMPONENT_REVIEW',
        'closure_references':chain,'common_closure_references':plan['common_closure_references'],'purpose':plan['purpose'],'phase':plan['phase'],
        'receipt_reference':chain['receipt'],'actual_source_and_parent_references':refs,
        'technical_phase_closed':receipt['technical_phase_closed'],'molecules':receipt['molecules'],
        'full_typed_source_order_identity_parity':receipt['full_typed_source_order_identity_parity'],
        'whole_true_Common_coverage_verified':receipt.get('whole_true_Common_coverage_verified',False),
        'canonical_child_census':receipt.get('canonical_child_census'),'ordinary_WP5_scope_does_not_accept_Pprime_full':True,
        'D5_sampling_and_readback':receipt.get('D5_sampling_and_readback'),'D5_jointly_frozen':False,
        'no_scientific_DATA_read_in_metadata':True}
    cr=Q.write_new(out/'candidate.json',value)
    Q.write_new(out/'root_review.template.json',{'schema':'ROOT_D5_COMPOUND_COMPONENT_ACCEPTANCE_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,
        'candidate_reference':cr,'approve_ordinary_input_tables':False,'approve_ordinary_D5_lists':False,
        'ordinary_WP5_and_independent_Pprime_N1_domains_reviewed_separately':True,'D5_jointly_frozen':False})
    return cr


def publish(review_path,output):
    rr=Q.pin(review_path);review=C.meta(rr);C.need(review['schema']=='ROOT_D5_COMPOUND_COMPONENT_ACCEPTANCE_V1'
        and review['status']=='APPROVED_EXACT_ACTUAL_COMPONENTS' and review['reviewer']=='root'
        and review['D5_jointly_frozen'] is False and review['ordinary_WP5_and_independent_Pprime_N1_domains_reviewed_separately'] is True,
        'SEPARATE_ACTUAL_ROOT_ACCEPTANCE_NOT_JOINT_D5_SELF_RELEASE')
    candidate=C.meta(review['candidate_reference']);receipt,plan,refs=C.closure(candidate['closure_references']);out=fresh(output)
    C.need(receipt['status']=='COMPLETE_TECHNICAL_COMPOUND_REQUIRES_ROOT_REVIEW' and receipt['technical_phase_closed'] is True
        and receipt['whole_true_Common_coverage_verified'] is True and receipt['held_molecules']==0,
        'NO_PARTIAL512_UNKNOWN_OR_INCOMPLETE_AS_FULL_INPUT_PUBLICATION')
    result={'schema':'ROOT_ACCEPTED_D5_COMPOUND_COMPONENTS_V1','status':'ACTUAL_C0_COMPONENTS_ACCEPTED_NOT_JOINT_D5',
        'review_reference':rr,'candidate_reference':review['candidate_reference'],'actual_closure_references':candidate['closure_references'],
        'common_closure_references':plan['common_closure_references'],'D5_jointly_frozen':False,
        'independent_Pprime_and_N1_extra_domain_acceptance':False,'actual_parent_evidence_references':refs}
    if review['approve_ordinary_input_tables']:
        result['ordinary_input_tables']=receipt['table_references'];result['actual_order_seed']=20261025
        result['ordinary_input_table_domain']=receipt['table_domain'];result['canonical_child_census']=receipt.get('canonical_child_census')
    if review['approve_ordinary_D5_lists']:
        sample=receipt['D5_sampling_and_readback'];C.need(plan['purpose']=='full' and sample is not None
            and sample['readback']['subset_counts']==sample['producer']['subset_counts'],'ACTUAL_COMPLETE_GUIDE_COUNTS_AND_ORIGINAL_READBACK')
        if receipt.get('canonical_child_census'):
            c=receipt['canonical_child_census'];C.need(c['missing_canonical_calls']==c['unknown_or_mismatched_inputs']==0,'NO_UNKNOWN_INPUT_CELL_IGNORED_BY_D5')
        result['ordinary_D5_artifacts']=sample['producer']['artifacts'];result['guide_subset_counts']=sample['producer']['subset_counts']
        # New Root-accepted small locators preserve all original DATA tables.
        # The old within-Parent order metadata never claimed an independent C0.
        cp=plan['common_closure_references']['manifest'];common=C.meta(cp)
        order=Q.write_new(out/'order_manifest.json',{'status':'CONFORMER_ORDER_V1_FROZEN','common_manifest_sha256':cp['sha256'],
            'common_population_manifest_sha256':cp['sha256'],'roles_manifest_sha256':common['roles_manifest_sha256'],
            'order_tables':[receipt['table_references']['orders']],'source_geometry_tables':[receipt['table_references']['geometries']],
            'rank_base':0,'order_seed':20261025,'seed':20261025,'order_types':['fixed_random','energy','diversity'],
            'actual_compound_closure_references':candidate['closure_references'],'root_component_review_reference':rr,
            'original_within_parent_order_manifest_reference':sample['current_parent_derived_order_manifest_reference'],
            'D5_jointly_frozen':False})
        original_gm=sample['producer']['artifacts']['geometry_map_manifest'];gm=C.meta(original_gm)
        gm=dict(gm,order_manifest=order,actual_compound_closure_references=candidate['closure_references'],
            root_component_review_reference=rr,original_producer_manifest_reference=original_gm,D5_jointly_frozen=False)
        geometry=Q.write_new(out/'geometry_map_manifest.json',gm)
        original_dm=sample['producer']['artifacts']['diagnostic_manifest'];dm=C.meta(original_dm)
        dm=dict(dm,geometry_map_manifest_sha256=geometry['sha256'],order_manifest_sha256=order['sha256'],
            actual_compound_closure_references=candidate['closure_references'],root_component_review_reference=rr,
            original_producer_manifest_reference=original_dm,D5_jointly_frozen=False)
        diagnostic=Q.write_new(out/'diagnostic_manifest.json',dm)
        result.update(order_manifest_reference=order,geometry_map_manifest_reference=geometry,diagnostic_manifest_reference=diagnostic)
        result['TRAIN_eligibility']=sample['eligibility'];result['TRAIN_eligibility'].update(common_manifest_reference=plan['common_closure_references']['manifest'],
            actual_compound_parent_closure_references=candidate['closure_references'],Root_acceptance_reference=rr,
            no_VAL_FULL_or_embargo_fit=True,numeric_label_masks_created=False)
        er=Q.write_new(out/'TRAIN_eligibility.json',{'schema':'ROOT_ACCEPTED_D5_TRAIN_GEOMETRY_ELIGIBILITY_V1',
            'status':'ACCEPTED_ORDINARY_GEOMETRY_SELECTION_NOT_FINAL_D4_POLICY',**result['TRAIN_eligibility'],'D5_jointly_frozen':False})
        result['TRAIN_eligibility_reference']=er
    return Q.write_new(out/'accepted_components.json',result)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('proposal');a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('candidate');a.add_argument('--closure',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=s.add_parser('publish');a.add_argument('--review',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a=p.parse_args();ref=proposal(a.output) if a.action=='proposal' else draft(a.request,a.output) if a.action=='draft' else candidate(a.closure,a.output) if a.action=='candidate' else publish(a.review,a.output)
    print(ref)
if __name__=='__main__':main()
