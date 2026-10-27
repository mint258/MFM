"""Login SOURCE/small metadata only; independent Root reviews and actual C0."""
from __future__ import annotations
import argparse,copy,time
from pathlib import Path
from . import contract as C
Q=C.Q


def resources(plan):
    from workflows.data_v1_final.conformers.n1_pprime2_pilot_v4 import quota_provider as P
    v=C.meta(plan['quota_reuse_reference']);review=P.load_review(v['provider_review_reference'])
    C.need(v['schema']=='ROOT_D5_INPUTS_QUOTA_FACT_REUSE_REVIEW_V1' and v['status']=='APPROVED_RESOURCE_FACT_REUSE_ONLY'
        and v['reviewer']=='root' and v['compute_node']=='compute-0-13'
        and type(v['whole_wave_output_reserve_bytes']) is int and v['whole_wave_output_reserve_bytes']>=0
        and v['actual_publisher_identity_launch_first_health_reviewed'] is True,'REAL_ORIGINAL_CPU13_FINITE_RESOURCE_CHAIN')
    identity=C.meta(v['publisher_identity_reference']);first=C.meta(v['first_healthy_snapshot_reference']);C.meta(v['provider_actual_launch_reference'])
    C.need(identity['review_reference']==v['provider_review_reference'] and first['observed_unix_seconds']<=time.time(),'REAL_OBSERVED_NOT_FUTURE_IDENTITY_HEALTH')
    P.validate_observation(first,identity,v['publisher_identity_reference'],review,v['provider_review_reference'],first['observed_unix_seconds'])
    return C.unique([plan['quota_reuse_reference'],v['publisher_identity_reference'],v['first_healthy_snapshot_reference'],
        v['provider_actual_launch_reference'],*P.references(v['provider_review_reference'])])


def fresh_control(path):
    p=Path(path);C.need(p.is_absolute() and C.ROOT/'control' in p.parents and not p.exists() and '..' not in p.parts
        and not any(v.is_symlink() for v in (p,*p.parents)),'FRESH_OWN_CONTROL_ONLY');return p


def draft(request,output):
    v=Q.load(request);C.need(v['schema']=='ROOT_REQUESTED_D5_INPUTS_BUILDER_V1' and v['status']=='REQUESTED_FOR_REVIEW'
        and v['requested_by']=='root','ACTUAL_ROOT_REQUEST_NOT_TEMPLATE_OR_APPROVAL')
    out=fresh_control(output);out.mkdir(parents=True,mode=0o700);pending=C.pending(v)
    if pending['missing']:return Q.write_new(out/'pending.json',pending)
    plan=copy.deepcopy(v);plan.update(schema='D5_INPUT_BUILDER_PLAN_V1');C.limits(plan)
    target=Path(plan['output_directory']);C.need(C.OUTPUT in target.parents and not target.exists() and '..' not in target.parts
        and not any(p.is_symlink() for p in (target,*target.parents)),'FRESH_EXTERNAL_OUTPUT_NO_OLD_SOURCE_MUTATION')
    m,formal,hof,data,parents,actual=C.inputs(plan)
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
    validate_authority(plan['resource_authority_reference'],read_small=Q.read_small)
    cost=C.meta(plan['cost_decision_reference']);C.need(cost['status']=='USER_AUTHORIZED' and cost['on_overrun']=='REPORT_AND_CONTINUE'
        and cost['scientific_quality_thresholds_unchanged'] is True,'UNCHANGED_USER_COST_AND_QUALITY')
    refs=C.unique([*(Q.pin(p) for p in C.source_paths()),*parents,*resources(plan),Q.pin(request),
        plan['resource_authority_reference'],plan['cost_decision_reference']])
    C.need(not {r['path'] for r in refs}&{r['path'] for r in data},'SMALL_SOURCE_AND_LARGE_DATA_DISJOINT')
    for ref in refs:C.need(Q.pin(ref['path'])==ref,'ALL_INSTALLED_SOURCE_SMALL_PARENT_BYTES_EXACT')
    plan.update(data_references=data,source_references=refs)
    pr=Q.write_new(out/'plan.json',plan);refs=C.unique([*refs,pr])
    fields={'kind':'analysis','scope_key':'d5_inputs_builder_'+plan['mode']+'_v1','scope_parameters':C.parameters(plan),
        'pilot':False,'wall_seconds':plan['wall_seconds'],'estimated_peak_output_bytes':plan['output_cap_bytes'],'source_status_stage':None,
        'execution_argv':[C.PY,'-B','-m',C.MODULE,'--plan',pr['path'],'--startup-proof','__ROOT_STARTUP_PROOF__']}
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'PENDING_ROOT_REVIEW','reviewer':None,**fields,
        'resource_authority_reference':plan['resource_authority_reference'],'scope_mode':'BOUNDED_PERFORMANCE_BATCH',
        'stage_output_cap_bytes':plan['output_cap_bytes'],'parent_evidence_references':parents,
        'approved_source_references':refs,'data_references':data,'bounded_batch_limits_reviewed':True,
        'CPU13_finite_quota_entire_cap_and200GB_reserve_reviewed':True,'new_QM_UFF_calls':0,'D5_jointly_frozen':False}
    rr=Q.write_new(out/'root_review.template.json',review)
    return Q.write_new(out/'draft_receipt.json',{'schema':'D5_INPUT_BUILDER_DRAFT_V1','status':'PENDING_INDEPENDENT_ROOT_REVIEW',
        'plan_reference':pr,'review_template_reference':rr,'stage_fields':fields,'source_references':refs,'data_references':data,
        'resource_authority_reference':plan['resource_authority_reference'],'scientific_DATA_opened_statted_or_hashed_on_login':False})


def finalize(draft_path,root_review):
    d=Q.load(draft_path);C.need(d['schema']=='D5_INPUT_BUILDER_DRAFT_V1','EXACT_DRAFT')
    rr=Q.pin(root_review);v=C.meta(rr);template=C.meta(d['review_template_reference'])
    C.need(rr!=d['review_template_reference'] and v['status']=='APPROVED_FOR_EXACT_STAGE' and v['reviewer']=='root','SEPARATE_ACTUAL_ROOT_SCOPE_REVIEW')
    for k,value in template.items():
        if k not in ('status','reviewer'):C.need(v[k]==value,'EXACT_REVIEWED_FIELD:'+k)
    for ref in d['source_references']:C.need(Q.pin(ref['path'])==ref,'FROZEN_REVIEW_SOURCE_PARENT_CHANGED')
    p=C.meta(d['plan_reference']);C.need(C.inputs(p)[3]==d['data_references']==p['data_references'],'SAME_ACTUAL_DATA_ONLY')
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1',**d['stage_fields'],'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
        'stage_output_cap_bytes':p['output_cap_bytes'],'source_references':d['source_references'],'data_references':d['data_references'],
        'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','parent_profile':None,'review':rr}}
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_scope_spec
    validate_scope_spec(spec,d['resource_authority_reference'],read_small=Q.read_small)
    return Q.write_new(Path(draft_path).parent/'stage_spec.json',spec)


def publish(review_path,output):
    review_ref=Q.pin(review_path);review=C.meta(review_ref)
    C.need(review['schema']=='ROOT_D5_INPUTS_TECHNICAL_PUBLICATION_REVIEW_V1'
        and review['status']=='APPROVED_EXACT_TECHNICAL_TABLE_PUBLICATION' and review['reviewer']=='root'
        and review['purpose'] in ('PPRIME_INPUT_PREPARATION_ONLY','D5_INPUT_TABLES_ONLY')
        and review['D5_jointly_frozen'] is False and review['QM_or_UFF_execution_authorized'] is False,'EXPLICIT_SEPARATE_TECHNICAL_PUBLICATION_REVIEW')
    receipt,plan,refs=C.actual(review['verification_closure_references']);common,_,_,_,_=C.common(plan)
    C.need(plan['mode']=='verify' and plan['purpose']=='full' and receipt['full_typed_source_order_identity_parity'] is True
        and receipt['whole_true_Common_coverage_verified'] is True
        and review['common_manifest_reference']==plan['common_closure_references']['manifest']
        and review['table_references']==receipt['table_references'],'ACTUAL_FULL_READBACK_NOT512_OR_PARTIAL')
    final=review['purpose']=='D5_INPUT_TABLES_ONLY'
    C.need((receipt['table_domain']=='BASE_WITH_ALL_ACTUAL_CHILDREN' and receipt['all_actual_children_closed'] is True) if final
        else receipt['table_domain']=='BASE_ONLY','SEPARATE_BOOTSTRAP_BASE_AND_FINAL_CHILD_DOMAINS')
    if final:
        policy=C.meta(review['N1_final_policy_reference'])
        C.need(policy['status']=='ROOT_REVIEWED_N1_N2_ORDINARY_D5_POLICY' and policy['reviewer']=='root'
            and policy['common_manifest_reference']==review['common_manifest_reference'],'ACTUAL_FINAL_N1_POLICY_NOT_PREPARATION_POLICY')
    out=fresh_control(output);out.mkdir(parents=True,mode=0o700);tables=receipt['table_references'];cp=review['common_manifest_reference']
    chain=review['verification_closure_references'];parent=[{'manifest':chain['receipt'],'startup_proof':chain['startup_proof'],
        'accounting':chain['accounting'],'job_id':receipt['job_id'],'node':receipt['node'],'manifest_status':receipt['status']}]
    order={'status':'CONFORMER_ORDER_V1_FROZEN','common_manifest_sha256':cp['sha256'],'common_population_manifest_sha256':cp['sha256'],
        'roles_manifest_sha256':common['roles_manifest_sha256'],'rank_base':0,'order_seed':C.ORDER_SEED,'seed':C.ORDER_SEED,
        'order_types':['fixed_random','energy','diversity'],'random_identity_basis':'canonical_sprime_conf_idx',
        'order_tables':[tables['orders']],'source_geometry_tables':[tables['geometries']],'actual_parent_chains':parent,
        'technical_publication_purpose':review['purpose'],'publication_review_reference':review_ref,'D5_jointly_frozen':False}
    order_ref=Q.write_new(out/'order_manifest.json',order)
    gm=Q.write_new(out/'geometry_map_manifest.json',{'status':'CANONICAL_GEOMETRY_MAP_V1_FROZEN','common_manifest_sha256':cp['sha256'],
        'common_population_manifest_sha256':cp['sha256'],'map_tables':[tables['geometries']],'order_manifest':order_ref,
        'publication_review_reference':review_ref,'technical_publication_purpose':review['purpose'],'D5_jointly_frozen':False})
    audit=Q.write_new(out/'pprime_audit_identity_manifest.json',{'status':'PPRIME_PHYSICAL_AUDIT_IDENTITY_MAP_FROZEN_V1',
        'common_manifest':cp,'geometry_manifest':gm,'identity_tables':[tables['audit_identity']],
        'publication_review_reference':review_ref,'ordinary_only':True,'N1_expanded_rows_accepted':False})
    result={'schema':'D5_INPUTS_TECHNICAL_PUBLICATION_V1','purpose':review['purpose'],'common_manifest':cp,'order_manifest':order_ref,
        'geometry_map_manifest':gm,'pprime_audit_identity_manifest':audit,'verification_closure_references':chain,
        'publication_review_reference':review_ref,'D5_jointly_frozen':False,'QM_UFF_authorized':False}
    if final:
        geo=Q.write_new(out/'geometry_authority.json',{'status':'ROOT_REVIEWED_ACTUAL_D5_GEOMETRY_TABLES','reviewer':'root',
            'common_manifest_reference':cp,'ordinary_physical_tables':common['physical_geometry_tables'],'geometry_tables':[tables['geometries']],
            'actual_parent_chains':parent,'publication_review_reference':review_ref})
        atoms=Q.write_new(out/'atom_counts_authority.json',{'status':'ROOT_REVIEWED_ACTUAL_D5_ATOM_COUNTS','reviewer':'root',
            'geometry_authority_reference':geo,'tables':[tables['atom_counts']],'actual_parent_chains':parent,'publication_review_reference':review_ref})
        config=C.meta(common['config']);roles_ref=config['roles_authority'];roles=C.meta(roles_ref)
        C.need(roles['source_role_manifest']==common['roles_manifest'] and roles['validation_source']=='ROUTINE','SAME_WHOLE_ROUTINE_AUTHORITY')
        f=Q.load(C.D.HERE/'frozen_sources.json');selection=next(r for r in f['files'] if r['relative_path']=='workflows/data_v1_final/conformers/selection.py')
        original_sources=C.unique([{'path':str(C.REPO/selection['relative_path']),'bytes':selection['bytes'],'sha256':selection['sha256']},*f['external_scientific_sources']])
        columns={k:{n:n for n in values} for k,values in C.D.COLUMNS.items()}
        columns['features'].update(element_z='elements_atomic_numbers',scaffold_id='generic_scaffold')
        views=Q.write_new(out/'input_view_review.json',{'status':'ROOT_REVIEWED_EXACT_D5_INPUT_COLUMNS','reviewer':'root',
            'common_manifest_reference':cp,'feature_tables':common['membership_tables'],'feature_filter_column':'common_population','columns':columns,
            'original_order_source_references':original_sources,'original_order_function_objects_verified':True,'conformer_order_seed':C.ORDER_SEED,
            'order_identity':{'pm7':'native_record_id','uff_sprime':'sprime_conf_idx_int64'},
            'distance_policy':'FIXED_SOURCE_ATOM_MAPPING_HEAVY_ATOMS_PROPER_KABSCH','energy_policy':{'pm7':'PM7_HOF_kcal_mol','uff_sprime':'UFF_energy_kcal_mol'},
            'publication_review_reference':review_ref})
        result['D5_parent_references']={'roles_authority':roles_ref,'common_manifest':cp,'order_manifest':order_ref,'geometry_authority':geo,
            'atom_counts_authority':atoms,'N1_policy':review['N1_final_policy_reference'],'input_view_review':views}
        result['independent_ROOT_D5_ORDINARY_FINAL_INPUT_RELEASE_still_required']=True
    return Q.write_new(out/'publication_receipt.json',result)


def main():
    Q.on_login();p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('draft');d.add_argument('--request',type=Path,required=True);d.add_argument('--output',type=Path,required=True)
    f=s.add_parser('finalize');f.add_argument('--draft',type=Path,required=True);f.add_argument('--root-review',type=Path,required=True)
    r=s.add_parser('publish');r.add_argument('--review',type=Path,required=True);r.add_argument('--output',type=Path,required=True)
    a=p.parse_args();result=draft(a.request,a.output) if a.action=='draft' else finalize(a.draft,a.root_review) if a.action=='finalize' else publish(a.review,a.output)
    print(result)
if __name__=='__main__':main()
