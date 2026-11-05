"""Small Root proposal/stage/closure only; never opens MID/coordinate containers."""
import argparse,copy,json,os,socket
from pathlib import Path
from . import contract as C
P=C.P
REVIEWS=('closed_feature_reuse_review_reference','base_cache_plan_reference','pilot_priority_review_reference','hof_closed_prefix_reuse_review_reference',
 'bounded_input_review_reference','source_metadata_frame_review_reference','WP5_input_derivation_authority_reference','actual_UFF_child_census_review_reference',
 'quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')
DATA=('canonical_index','source_inventory_reference','footer_manifest_reference')

def source_paths():
    from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import metadata as D4
    from workflows.data_v1_final.conformers.pm7_precache_hof_resume_day_v1 import metadata as GENERAL
    from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import metadata as Native
    from workflows.data_v1_final.labels.existing_sprime_pilot_general_cpu_day_v1 import contract as General
    from workflows.data_v1_final.export.family_export_day_v1 import contract as Family
    resource=list(Native.source_paths())
    resource.extend(C.REPO/'workflows/data_v1_final/export/pilot_family_D3_day_v1'/n for n in ('__init__.py','contract.py','io.py'))
    resource.extend(General.HERE/n for n in General.FILES)
    resource.extend(Family.HERE/n for n in Family.FILES)
    return list(dict.fromkeys([*resource,*(C.HERE/n for n in C.FILES),*(C.REPO/'workflows/data_v1_final/export/bounded_old_complete_d5_day_v1'/n for n in C.FILES),*D4.source_paths(),*GENERAL.source_paths()]))

def login():C.need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),'ROOT_MAIN_SMALL_METADATA_LOGIN_ONLY')

def references(v):
    if type(v)is dict:
        if {'path','bytes','sha256'}<=set(v):yield C.reference({k:v[k] for k in ('path','bytes','sha256')})
        else:
            for x in v.values():yield from references(x)
    elif type(v)is list:
        for x in v:yield from references(x)

def proposal(request_path,out):
    login();reqref=P.pin(request_path);v=C.meta(reqref);out=Path(out);out.mkdir(parents=True,exist_ok=True)
    required=(*REVIEWS,*DATA,'node','scope_version','output_directory')
    missing=[k for k in required if v.get(k)is None]
    C.need(v['schema']=='ROOT_REQUESTED_BOUNDED_OLD_COMPLETE_D5_DAY_V1' and v['requested_by']=='root','REAL_ROOT_REQUEST_NOT_AUTOSIGNED')
    if missing:return P.write(out/'nonexecutable.json',{'schema':'BOUNDED_OLD_COMPLETE_D5_METADATA_PENDING_V1','status':'NONEXECUTABLE_MISSING_ACTUAL_ROOT_INPUTS','missing':missing,'scientific_DATA_opened':False,'stage_spec_generated':False})
    C.need(v['status']=='REQUESTED_FOR_REVIEW','INDEPENDENT_ROOT_INPUT_REQUEST')
    p={k:copy.deepcopy(v[k]) for k in required};p.update(schema=C.PLAN,status='ROOT_REVIEW_REQUIRED',reviewer=None,
      cpus=16,requested_cpus=16,workers=16,wall_seconds=86400,softwall_drain_seconds=900,whole_output_cap_bytes=32<<30,
      pilot_input_review_reference=v['bounded_input_review_reference'],cache_transitive_output_origins=[],accepted_prior_output_roots=[])
    scope,reuse,qa,origin,accepted=C.reviews(p);base=C.meta(p['base_cache_plan_reference'])
    from . import resume
    _,_,closed_refs=resume.review(p)
    p['future_shards_reference']=base['future_shards_reference']
    from workflows.data_v1_final.conformers.pm7_precache_day_v1.pilot_prepare import policy
    _,old_sources,old_data=policy(p['pilot_priority_review_reference'],base)
    sources=[reqref,*closed_refs,*(p[k] for k in REVIEWS),*old_sources,*scope['actual_parent_evidence_references'],*(P.pin(x) for x in source_paths())]
    # This function is expressly small metadata. No preselection/prepared/packet body is read.
    sources.extend(reuse['actual_CPU_QA_parent_references']);sources.extend(references(reuse['failed_parent_registration']))
    sources.extend([reuse['actual_CPU_SQL_QA_reference'],reuse['actual_CPU_QA_accounting_reference']])
    data=[*(p[k] for k in DATA),p['future_shards_reference'],base['formal_source'],base['per_molecule'],*old_data,
        reuse['failed_receipt_reference'],reuse['closed_state_reference'],reuse['observations_reference']]
    sources.extend([accepted['declared_Pprime_preparation_pureQA_reference'],accepted['actual_after_native30_physical_policy_reference']])
    frame=C.meta(p['source_metadata_frame_review_reference']);sources.append(frame['actual_same_storage_mapping_probe_reference'])
    wp5=C.meta(p['WP5_input_derivation_authority_reference'])
    for item in wp5['package_protocol_references']:sources.extend([item['package_reference'],item['protocol_reference']])
    provider=C.meta(p['quota_provider_review_reference'])
    for k in ('provider_source_references','evidence_references'):sources.extend(provider.get(k,[]))
    for k in ('marker_reference','probe_reference'):
        if provider.get(k)is not None:sources.append(provider[k])
    carve=C.meta(p['root_carveout_review_reference']);sources.extend(carve.get('accounting_basis_references',[]))
    if carve.get('registered_external_allocated_credit_sources'):
        sources.extend(x['initial_observation_reference'] for x in carve['registered_external_allocated_credit_sources'])
    # Literal Source allowlist only; scientific JSON does not become metadata by size.
    known={str(x) for x in source_paths()};data=C.unique(r for r in data if r['path']not in known);data_paths={r['path'] for r in data}
    sources=C.unique(r for r in sources if r['path']not in data_paths)
    for r in sources:C.need(P.pin(r['path'])==r,'EXACT_CURRENT_SOURCE_OR_ACTUAL_SMALL_METADATA')
    p.update(source_references=sources,data_references=data,actual_parent_evidence_references=C.unique([*scope['actual_parent_evidence_references'],*closed_refs]))
    p['scope_parameters']=C.scope(p);return P.write(out/'plan_candidate.json',p)

def stage(plan_path,out,scope_review=None):
    login();planref=P.pin(plan_path);p=C.plan(C.meta(planref));out=Path(out);out.mkdir(parents=True,exist_ok=True)
    authority=P.pin(C.REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json')
    argv=[C.PY,'-B','-m',C.MODULE,'--plan',str(plan_path),'--startup-proof','__ROOT_STARTUP_PROOF__']
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':None,
      'resource_authority_reference':authority,'kind':'analysis','scope_key':C.KEY,'scope_parameters':C.scope(p),'pilot':False,
      'wall_seconds':86400,'estimated_peak_output_bytes':32<<30,'stage_output_cap_bytes':32<<30,'execution_argv':argv,
      'source_status_stage':None,'scope_mode':'BOUNDED_METADATA_PREPARATION','parent_evidence_references':p['actual_parent_evidence_references'],'root_review_reason':None}
    template=P.write(out/'scope_candidate.json',review)
    spec={k:review[k] for k in ('kind','scope_key','scope_parameters','pilot','wall_seconds','estimated_peak_output_bytes','stage_output_cap_bytes','execution_argv','source_status_stage')}
    spec.update(schema='UNSIGNED_BOUNDED_OLD_COMPLETE_D5_STAGE_INPUTS_V1',cpus=16,memory_policy='SLURM_DEFAULT_UNSPECIFIED',
      source_references=C.unique([*p['source_references'],planref]),data_references=p['data_references'],scope={'mode':'BOUNDED_METADATA_PREPARATION','review':None,'parent_profile':None},unsigned_scope_candidate_reference=template)
    if scope_review:
        ref=P.pin(scope_review);r=C.meta(ref)
        for k,value in review.items():
            if k not in ('status','reviewer','root_review_reason'):C.need(r[k]==value,'EXACT_ACTUAL_ROOT_SCOPE_FIELD:'+k)
        C.need(r['status']=='APPROVED_FOR_EXACT_STAGE' and r['reviewer']=='root' and r['root_review_reason'],'REAL_EXACT_ROOT_SCOPE_APPROVAL')
        spec.update(schema='ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1');spec['scope']['review']=ref;spec['source_references']=C.unique([*spec['source_references'],ref]);spec.pop('unsigned_scope_candidate_reference')
    return P.write(out/('stage_spec.json' if scope_review else 'stage_inputs_candidate.json'),spec)

def close(registration_path,out):
    login();registration=P.pin(registration_path);chain=C.meta(registration);job,a=C.parent(chain)
    need=C.need;req=C.meta(chain['request_reference']);proof=C.meta(chain['proof_reference']);receipt=C.meta(chain['receipt_reference'])
    need(a['state']=='COMPLETED' and a['exit_code']=='0:0' and a['alloc_cpus']==16 and a['node']==req['node'],'TRUE_ACTUAL_PARENT_C0_NOT_OLD_FAILED_ADOPTION')
    need(req['scope_key']==C.KEY and req['kind']=='analysis' and req['cpus']==16 and req['wall_seconds']==86400
      and req['execution_argv']==[C.PY,'-B','-m',C.MODULE,'--plan',receipt['plan_reference']['path'],'--startup-proof',chain['proof_reference']['path']]
      and receipt['plan_reference']in req['source_references'],'EXACT_NEW_PRIMARY_FULLARGV_PLAN_PROOF')
    need(receipt['schema']=='BOUNDED_OLD_COMPLETE_D5_DAY_RECEIPT_V1' and receipt['status']=='BOUNDED_OLD_COMPLETE_D5_COMPONENTS_COMPLETE_PENDING_ACTUAL_C0_ROOT'
      and str(receipt['job_id'])==job and receipt['held']is False and receipt['errors']==[] and receipt['components']['diagnostic_TRAIN_molecules']==20000
      and receipt['components']['heldout_PM7_bases']==receipt['components']['heldout_ordinary_Sprime_bases']==20000,'REAL_BOUND_COMPONENTS_AND_EXACT20K_NO_FUTURE_RELEASE')
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    return P.write(out/'root_bounded_acceptance_candidate.json',{'schema':'ROOT_ACCEPTED_BOUNDED_OLD_COMPLETE_D5_COMPONENTS_V1','status':'ROOT_REVIEW_REQUIRED','reviewer':None,
      'proposed_status':'ACTUAL_C0_OLD_COMPLETE_D5_COMPONENTS_ACCEPTED_NOT_FINAL_COMMON','scope_version':receipt['scope_version'],
      'actual_parent':{'manifest':chain['receipt_reference'],'proof':chain['proof_reference'],'accounting':chain['accounting_reference'],'raw':chain['raw_reference']},
      'registration_reference':registration,'components':receipt['components'],'preselection_reference':receipt['preselection_reference'],
      'ordinary_current_training_sources_only':True,'final_Common_D3_D4_D6_or_joint_release':False})

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    d=s.add_parser('proposal');d.add_argument('--request',required=True);d.add_argument('--output',required=True)
    d=s.add_parser('stage');d.add_argument('--plan',required=True);d.add_argument('--output',required=True);d.add_argument('--scope-review')
    d=s.add_parser('close');d.add_argument('--registration',required=True);d.add_argument('--output',required=True)
    a=p.parse_args();print(proposal(a.request,a.output) if a.action=='proposal' else (stage(a.plan,a.output,a.scope_review) if a.action=='stage' else close(a.registration,a.output)))
if __name__=='__main__':main()
