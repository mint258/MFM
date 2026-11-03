"""SOURCE/small Root metadata only; missing actual parents produce no runnable plan."""
import argparse,copy,json
from pathlib import Path
from . import contract as C
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import metadata as M

def sources(seed):
    out=M.sources(seed)
    out.extend(C.A.Q.pin(C.HERE/n) for n in C.FILES)
    out.extend(C.A.Q.pin(p) for p in C.A.sources())
    old=C.REPO/'workflows/data_v1_final/labels/normalization_compact_day_v1'
    out.extend(C.A.Q.pin(p) for p in old.glob('*.py'))
    out.append(C.A.Q.pin(old/'inverse_rules.json'))
    return C.unique(out)

def nested_references(value):
    if isinstance(value,dict):
        if {'path','bytes','sha256'}<=set(value):yield C.reference(value,source=value.get('bytes')==0)
        else:
            for v in value.values():yield from nested_references(v)
    elif isinstance(value,list):
        for v in value:yield from nested_references(v)

def build(path,output):
    C.A.Q.on_login();req=C.meta(C.A.Q.pin(path));C.need(req['schema']=='ROOT_COMMON_TRAIN_NORMALIZATION_DAY_REQUEST_V1' and req['requested_by']=='root','ROOT_METADATA_REQUEST_ONLY')
    out=Path(output).absolute();C.need(C.RUN/'control' in out.parents and not out.exists(),'FRESH_SMALL_METADATA_OUTPUT');out.mkdir(parents=True,mode=0o700)
    required=('input_release_reference','scientific_config_reference','coverage_reference','common_manifest_reference','roles_manifest_reference','geometry_map_manifest_reference','diagnostic_manifest_reference','d5_components_acceptance_reference')
    missing=[k for k in required if not isinstance(req.get(k),dict)]
    if missing:
        return C.A.Q.write_new(out/'NONEXECUTABLE.json',{'schema':'COMMON_TRAIN_NORMALIZATION_NONEXECUTABLE_V1','status':'NONEXECUTABLE_REAL_FINAL_PARENTS_PENDING',
          'missing':missing,'plan_generated':False,'future_hashes_or_DATA_opened':False,'final_Common_D4':False,'Pprime_formal_source_pending':True})
    release=C.release(C.meta(req['input_release_reference']));seed=C.meta(req['scientific_config_reference'])
    C.need(seed['mode']=='full' and seed['geometry_source']=='pm7' and seed['codec_schema']=='COMPACT_TYPED_BINARY_JSON_V3',
      'REAL_FULL_PM7_COMPACT_V3_SEED_NOT_PILOT_OR_PPRIME')
    authority={k:req[v] for k,v in {'common':'common_manifest_reference','roles':'roles_manifest_reference','geometry_map':'geometry_map_manifest_reference','diagnostic':'diagnostic_manifest_reference'}.items()}
    C.need(release['authority']==authority and release['coverage_reference']==req['coverage_reference'],'EXACT_ROOT_RELEASE_FINAL_INPUTS')
    C.need(release['field_scope']['source_field_map_reference']==seed['field_map_reference'],'ORIGINAL_ENABLED_FIELD_TASK_SCOPE_SHA')
    dc=C.meta(req['d5_components_acceptance_reference'])
    C.need(dc['schema']=='ROOT_ACCEPTED_D5_COMPOUND_COMPONENTS_V1' and dc['status']=='ACTUAL_C0_COMPONENTS_ACCEPTED_NOT_JOINT_D5'
      and dc['D5_jointly_frozen'] is False and dc['geometry_map_manifest_reference']==authority['geometry_map']
      and dc['diagnostic_manifest_reference']==authority['diagnostic'],'REAL_COMPOUND_COMPONENTS_NOT_SOURCE_OR_JOINT_SELF_SIGNOFF')
    dr=C.meta(dc['review_reference']);C.need(dr['schema']=='ROOT_D5_COMPOUND_COMPONENT_ACCEPTANCE_V1'
      and dr['status']=='APPROVED_EXACT_ACTUAL_COMPONENTS' and dr['reviewer']=='root' and dr['approve_ordinary_D5_lists'] is True,'ACTUAL_INDEPENDENT_ROOT_D5_COMPONENT_ACCEPTANCE')
    dc0=dc['actual_closure_references'];dp=release['actual_parents']['D5']
    C.need(dc0=={'receipt':dp['manifest'],'startup_proof':dp['proof'],'accounting':dp['accounting']},'EXACT_D5_ACTUAL_COMPOUND_RECEIPT_PROOF_ACCOUNT')
    de=C.meta(dc['TRAIN_eligibility_reference'])
    C.need(de['schema']=='ROOT_ACCEPTED_D5_TRAIN_GEOMETRY_ELIGIBILITY_V1'
      and de['status']=='ACCEPTED_ORDINARY_GEOMETRY_SELECTION_NOT_FINAL_D4_POLICY' and de['effective_role']=='TRAIN'
      and de['common_only'] is True and de['all_direct_actual_children_of_heldout_bases_excluded'] is True
      and de['no_VAL_FULL_or_embargo_fit'] is True and de['numeric_label_masks_created'] is False
      and de['common_manifest_reference']==authority['common'] and de['Root_acceptance_reference']==dc['review_reference'],
      'ACTUAL_D5_ANTI_JOIN_ELIGIBILITY_NOT_NUMERIC_MASK_AUTHORITY')
    # These are bounded authority manifests. Numeric coverage/catalog/parts are DATA, CPU-only.
    objects={k:C.meta(r) for k,r in authority.items()};common,roles,gm,diag=(objects[k] for k in ('common','roles','geometry_map','diagnostic'))
    C.need(common['schema']==common['status']=='COMMON_POPULATION_V1_FROZEN' and common.get('pilot_only') is False,
           'FINAL_FULL_COMMON_NOT_PILOT_OR_SOURCE')
    C.need(roles['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN' and gm['status']=='CANONICAL_GEOMETRY_MAP_V1_FROZEN'
           and diag['status']=='SEEN_MOLECULE_UNSEEN_GEOMETRY_DIAGNOSTIC_FROZEN','ACTUAL_ROLE_GEOMETRY_D5_MANIFESTS')
    C.need(common['roles_manifest_sha256']==authority['roles']['sha256'] and gm['common_population_manifest_sha256']==authority['common']['sha256']
           and gm['roles_manifest_sha256']==authority['roles']['sha256'] and diag['common_population_manifest_sha256']==authority['common']['sha256']
           and diag['geometry_map_manifest_sha256']==authority['geometry_map']['sha256'],'COMMON_ROLE_GEOMETRY_DIAGNOSTIC_SHA_CROSS_BINDING')
    small=[C.A.Q.pin(path),req['input_release_reference'],req['scientific_config_reference'],*authority.values(),gm['order_manifest'],
      seed['logical_group_plan_reference'],seed['logical_group_plan_authority_reference'],seed['field_map_reference'],seed['source_inventory_reference'],
      *release['accepted_parent_review_references'],*nested_references(release['actual_parents'])]
    small.extend([req['d5_components_acceptance_reference'],dc['review_reference'],dc['candidate_reference'],dc['TRAIN_eligibility_reference']])
    if release['field_scope']['closed_exposure_field_ids']:small.append(release['field_scope']['closed_exposure_review_reference'])
    C.need(de['diagnostic_base_reference'] in diag['excluded_geometry_tables']
      and de['diagnostic_targets_reference'] in diag['target_exclusion_tables'],'LEGACY_D5_TABLES_EXACT_SAME_ACTUAL_ELIGIBILITY')
    order=C.meta(gm['order_manifest']);C.need(order['status']=='CONFORMER_ORDER_V1_FROZEN' and diag['order_manifest_sha256']==gm['order_manifest']['sha256'],'TRUE_FROZEN_ORDER_PARENT')
    logical=C.meta(seed['logical_group_plan_reference']);C.logical(logical['groups'])
    small.extend(M.full_logical_authority(seed['logical_group_plan_authority_reference'],seed['logical_group_plan_reference'],logical['groups']))
    book=C.meta(seed['source_inventory_reference']);C.need(len(book['files'])==2208,'EXACT_ALL_SOURCE_INVENTORY')
    for key in ('coverage_reference','canonical_index','logical_group_plan_reference','field_map_reference','source_inventory_reference'):
        if key in release:C.need(release[key]==(req[key] if key in req else seed[key]),'RELEASE_EXACT_BOUND_INPUT:'+key)
    role_tables=roles.get('molecule_role_tables') or [r for r in roles['outputs'] if Path(r['path']).parent.name=='molecule_roles']
    data=C.unique([req['coverage_reference'],seed['canonical_index'],*common['membership_tables'],*role_tables,*gm['map_tables'],
      *diag['excluded_geometry_tables'],*diag['target_exclusion_tables'],*(C.reference(s) for s in book['files']),
      *release['additional_exact_DATA_references']])
    code=sources(seed);small.extend(seed['small_references']);small.extend(seed['science']['sources'].values())
    prior=req.get('previous_parent');prior_roots=[]
    if prior is not None:
        proof=C.actual(prior);review=C.meta(prior['root_limited_acceptance_review_reference'])
        C.need(review['schema']=='ROOT_COMMON_TRAIN_NORMALIZATION_DAY_CHECKPOINT_ACCEPTANCE_V1' and review['status']=='APPROVED_ACTUAL_C0_CLEAN_CHECKPOINTS'
          and review['reviewer']=='root' and review['actual_parent']=={k:prior[k] for k in ('manifest','proof','accounting','raw')}
          and review['input_release_reference']==req['input_release_reference'],'EXACT_ACTUAL_PRIOR_CHECKPOINT_NOT_CHANGED_INPUTS')
        small.extend(nested_references(prior));parent=C.meta(prior['manifest'])
        C.need(parent['schema']=='COMMON_TRAIN_NORMALIZATION_DAY_RECEIPT_V1' and parent['held'] is False and parent['errors']==[]
          and not parent['quality_hold_fields'] and parent['input_release_reference']==req['input_release_reference'],'PRIOR_CLEAN_DAY_ONLY_NOT_HOLD_RETRY')
        oldplan=C.meta(proof['request']['producer_plan_reference']);C.need(oldplan['input_release_reference']==req['input_release_reference'],'PRIOR_PLAN_SAME_FINAL_INPUT_RELEASE')
        data.append(parent['checkpoint_reference']);small.append(proof['request']['producer_plan_reference'])
        prior_roots.extend(oldplan['accepted_prior_output_roots']);prior_roots.append({'manifest_reference':prior['manifest'],'output_root':str(Path(prior['manifest']['path']).parent)})
    small=C.unique([*small,req['resource_authority_reference']]);denied={r['path'] for r in data}
    source=C.unique([r for r in [*code,*small] if r['path'] not in denied])
    p={k:copy.deepcopy(req[k]) for k in ('requested_cpus','output_directory','whole_output_cap_bytes','eligibility_cap_bytes','statistics_cap_bytes','audit_cap_bytes','spill_cap_bytes','admin_cap_bytes')}
    p.update(schema=C.SCHEMA,status='EXECUTABLE_ACTUAL_PARENTS_BOUND',scope_key=C.KEY,wall_seconds=86400,softwall_drain_seconds=900,
      input_release_reference=req['input_release_reference'],coverage_reference=req['coverage_reference'],authority=authority,
      d5_components_acceptance_reference=req['d5_components_acceptance_reference'],geometry_source='pm7',label_group='P_D',
      field_scope=release['field_scope'],
      scientific_config_reference=req['scientific_config_reference'],science=seed['science'],
      canonical_index=seed['canonical_index'],field_map_reference=seed['field_map_reference'],source_inventory_reference=seed['source_inventory_reference'],
      logical_group_plan_reference=seed['logical_group_plan_reference'],logical_group_plan_authority_reference=seed['logical_group_plan_authority_reference'],
      element_basis=seed['element_basis'],data_references=C.unique(data),source_references=source,
      cache_transitive_output_origins=release['cache_transitive_output_origins'],accepted_prior_output_roots=prior_roots,previous_parent=prior,
      workers=p['requested_cpus'],worker_rss_stop_bytes=seed['worker_rss_stop_bytes'],worker_histogram_row_cap=1000000,worker_serialized_buffer_cap_bytes=128<<20,
      audit_group_cap_bytes=req['audit_group_cap_bytes'],TSQR_chunk=256,QR_reduction='ORIGINAL_ORDERED_LEFT_FOLD',quality_new_mask_fraction=.01,
      independent_numeric_replay_required=True,new_QM_UFF_calls=0,raw_source_audit_seed=20261025,raw_source_audit_basis_points=100,mode='full',
      physical_unit_sign_axes_and_joint_head_policy='PENDING_SEPARATE_JOINT_RELEASE',Pprime_status='PENDING_REAL_INDEPENDENT_FORMAL_SOURCE')
    p['scope_parameters']=C.scope(p);C.plan(p);pr=C.A.Q.write_new(out/'plan.json',p)
    C.need(pr['bytes']<=2<<20,'OPERATIONAL_PLAN_BOUNDED_NOT_NUMERIC_BODY')
    template={k:req[k] for k in ('job_name','node','resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')}
    template.update(schema='ROOT_REQUESTED_ANALYSIS_DAY_V1',status='REQUESTED_FOR_REVIEW',requested_by='root',cpus=p['requested_cpus'],scope_key=C.KEY,
      scope_parameters=p['scope_parameters'],producer_plan_reference=pr,estimated_peak_output_bytes=p['whole_output_cap_bytes'],
      source_references=C.unique([*source,pr]),data_references=p['data_references'])
    tr=C.A.Q.write_new(out/'resource_request.template.json',template)
    return C.A.Q.write_new(out/'candidate_receipt.json',{'schema':'COMMON_TRAIN_NORMALIZATION_METADATA_CANDIDATE_V1','plan_reference':pr,
      'resource_request_template_reference':tr,'DATA_read_or_hashed_on_login':False,'submitted':False,'joint_signed':False})

def close(plan_path,manifest_path,proof_path,accounting_path,raw_path,output):
    p=C.plan(C.meta(C.A.Q.pin(plan_path)));parent={k:C.A.Q.pin(v) for k,v in {'manifest':manifest_path,'proof':proof_path,'accounting':accounting_path,'raw':raw_path}.items()}
    proof=C.actual(parent);m=C.meta(parent['manifest'])
    C.need(m['schema']=='COMMON_TRAIN_NORMALIZATION_DAY_RECEIPT_V1' and m['plan_reference']==C.A.Q.pin(plan_path)
      and m['job_id']==str(proof['job_id']) and proof['request']['scope_key']==C.KEY and proof['request']['cpus']==p['requested_cpus'],'ACTUAL_THIS_DAY_PLAN_RUNTIME_C0')
    return C.A.Q.write_new(Path(output),{'schema':'COMMON_TRAIN_NORMALIZATION_ACTUAL_DAY_CLOSURE_V1','status':'ACTUAL_C0_TECHNICAL_CLOSURE_PENDING_ROOT_REVIEW',
      'actual_parent':parent,'manifest_status':m['status'],'held':m['held'],'quality_hold_fields':m['quality_hold_fields'],
      'D4_published':False,'physical_joint_policy_accepted':False,'Pprime_completed':False})

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    a=s.add_parser('candidate');a.add_argument('--request',required=True);a.add_argument('--output',required=True)
    a=s.add_parser('close')
    for n in ('plan','manifest','startup-proof','accounting','raw','output'):a.add_argument('--'+n,required=True)
    a=p.parse_args()
    print(build(a.request,a.output) if a.action=='candidate' else close(a.plan,a.manifest,a.startup_proof,a.accounting,a.raw,a.output))
if __name__=='__main__':main()
