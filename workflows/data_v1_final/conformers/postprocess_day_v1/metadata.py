"""Unsigned Root plan/resource requests and actual-C0 component proposals only."""
import argparse,pathlib
from . import contract as C

def fresh(path):
    p=pathlib.Path(path);C.need(p.is_absolute() and C.ROOT/'control' in p.parents and not p.exists() and '..' not in p.parts,'FRESH_ROOT_CONTROL');p.mkdir(parents=True,mode=0o700);return p

def proposal(output):
    C.G.on_login();out=fresh(output)
    cfg=C.G.meta_pin(C.G.CONFIG);cache=C.G.meta_pin(C.ROOT/'control/pm7_population5000_root_approvals_v1/plan.json')
    value={'schema':'ROOT_REQUESTED_CONFORMERS_POSTPROCESS_DAY_V1','status':'UNSIGNED_NONEXECUTABLE_MISSING_ACTUAL_PARENT_REFS','requested_by':None,
      'job_name':None,'cpus':64,'node':None,'output_cap_bytes':384<<30,'output_directory':None,
      'original_config_reference':cfg,'cache_plan_reference':cache,'packed_parent_job_id':'4524556',
      'packed_receipt_reference':None,'packed_accounting_reference':None,'related_parent_review_reference':None,'cache_registered_parents':[],
      'previous_postprocess_parents':[],'resource_authority_reference':None,'quota_provider_review_reference':None,'quota_provider_identity_reference':None,'root_carveout_review_reference':None,
      'algorithm_rss_soft_cap_bytes':64<<30,'minimum_MemAvailable_bytes':4<<30,'exact_quantile_memory_bound_bytes':16<<30,
      'wall_is_not_forecast':True,'no_new_QM_UFF_or_scientific_retries':True}
    return C.G.write_new(out/'request.template.json',value)

def draft(request_path,output):
    C.G.on_login();request=C.G.load(request_path)
    C.need(request['schema']=='ROOT_REQUESTED_CONFORMERS_POSTPROCESS_DAY_V1' and request['status']=='REQUESTED_FOR_REVIEW'
      and request['requested_by']=='root','REAL_ROOT_INPUT_REQUEST_NOT_A_PLACEHOLDER')
    keys=('cpus','node','output_cap_bytes','output_directory','original_config_reference','cache_plan_reference','packed_parent_job_id','packed_receipt_reference',
      'packed_accounting_reference','related_parent_review_reference','cache_registered_parents','resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference',
      'root_carveout_review_reference','algorithm_rss_soft_cap_bytes','minimum_MemAvailable_bytes','exact_quantile_memory_bound_bytes')
    plan={k:request[k] for k in keys};plan.update(schema='CONFORMERS_POSTPROCESS_DAY_PLAN_V1',wall_seconds=86400,drain_seconds=900,
      previous_postprocess_parents=request.get('previous_postprocess_parents',[]));plan['scope_parameters']=C.parameters(plan)
    value,receipt,packed,original,prior,cache,refs,data=C.inputs(plan)
    target=pathlib.Path(plan['output_directory']);C.need(C.ROOT/'artifacts/conformers/postprocess_day_v1' in target.parents and not target.exists()
      and '..' not in target.parts,'EXACT_FRESH_ONE_PARENT_OUTPUT')
    out=fresh(output);plan_ref=C.G.write_new(out/'plan.json',plan)
    references=C.G.References({'source_references':[],'data_references':data})
    for ref in [*C.sources(),*refs,plan_ref,C.G.meta_pin(request_path)]:references.add(ref)
    references.validate_small_sources()
    result={'schema':'ROOT_REQUESTED_ANALYSIS_DAY_V1','status':'UNSIGNED_PENDING_ROOT_EXACT_RESOURCE_REVIEW','requested_by':None,
      'job_name':request['job_name'],'cpus':plan['cpus'],'node':plan['node'],'scope_key':C.KEY,'scope_parameters':plan['scope_parameters'],
      'producer_plan_reference':plan_ref,'estimated_peak_output_bytes':plan['output_cap_bytes'],
      **{k:plan[k] for k in ('resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')},
      'source_references':list(references.sources.values()),'data_references':list(references.data.values()),
      'no_DATA_opened_or_hashed_on_login':True,'Root_signed_or_submitted':False}
    return C.G.write_new(out/'resource_request.template.json',result)

def accept(receipt_path,accounting_path,output):
    C.G.on_login();rr,receipt=C.G.metadata(receipt_path,'CONFORMERS_POSTPROCESS_DAY_RECEIPT_V1');plan=C.meta(receipt['plan_reference']);jid=receipt['job_id']
    ar,av,parents=C.G.account(accounting_path,[jid]);row=parents[jid]
    C.need(row['state']=='COMPLETED' and row['exit_code']=='0:0' and row['alloc_cpus']==plan['cpus'] and row['node']==plan['node'],
      'ACTUAL_ANALYSIS_DAY_C0_WITH_REAL_ALLOCATED_CPUS_NOT_OLD16')
    proof=C.meta(receipt['startup_proof_reference']);C.need(str(proof['job_id'])==jid and proof['request']['producer_plan_reference']==receipt['plan_reference']
      and proof['request']['scope_key']==C.KEY and receipt['no_new_UFF_or_QM'] is True and receipt['no_child_Slurm_jobs'] is True,'EXACT_ACTUAL_ONE_PARENT_PRODUCER_PROOF')
    out=fresh(output)
    return C.G.write_new(out/'component_acceptance_candidate.json',{'schema':'CONFORMERS_POSTPROCESS_ACTUAL_C0_COMPONENT_CANDIDATE_V1',
      'status':'PENDING_INDEPENDENT_ROOT_COMMON_AND_D7_REVIEW','receipt_reference':rr,'accounting_reference':ar,'raw_accounting_reference':av['raw_sacct_reference'],
      'plan_reference':receipt['plan_reference'],'actual_parent':row,'startup_proof_reference':receipt['startup_proof_reference'],'preflight_reference':receipt['preflight_reference'],'common_candidate_reference':receipt['common_candidate_reference'],
      'statistics_reference':receipt['statistics_reference'],'order_tables':receipt['order_tables'],'geometry_witness_tables':receipt['geometry_witness_tables'],
      'catalog_reference':receipt['catalog_reference'],'PM7_full_source_cache_complete':receipt['PM7_full_source_cache_complete'],
      'ordinary_Common_D7_geometry_complete':receipt['ordinary_Common_D7_geometry_complete'],'three_order_Common_release_eligible':receipt['three_order_Common_release_eligible'],
      'original_quality_hold':receipt['original_quality_hold'],'unknown_molecules':receipt['unknown_molecules'],
      'N1_extra_domain_still_independent':True,'Pprime_2000_or_full_release':False,'Common_or_training_or_full_dataset_release':False,
      'scientific_numeric_JSON_bodies_not_opened_on_login':True})

def finalize(candidate_path,review_path,output):
    C.G.on_login();cr,c=C.G.metadata(candidate_path,'CONFORMERS_POSTPROCESS_ACTUAL_C0_COMPONENT_CANDIDATE_V1');rv,r=C.G.metadata(review_path,'ROOT_CONFORMERS_POSTPROCESS_COMPONENT_ACCEPTANCE_V1')
    C.need(r['status']=='APPROVED_EXACT_ACTUAL_COMPONENTS' and r['reviewer']=='root' and r['candidate_reference']==cr,'INDEPENDENT_EXACT_ROOT_COMPONENT_REVIEW')
    C.need(type(r['approve_common']) is bool and type(r['approve_D7']) is bool,'SEPARATE_COMPONENT_ROOT_DECISIONS')
    out=fresh(output);result={'schema':'ROOT_ACCEPTED_CONFORMERS_COMPONENTS_V1','candidate_reference':cr,'root_review_reference':rv,'common_manifest_reference':None,'order_manifest_reference':None}
    if r['approve_common']:
        C.need(c['common_candidate_reference'] is not None and c['original_quality_hold'] is None and c['ordinary_Common_D7_geometry_complete'] is True and c['unknown_molecules']==0,'ORIGINAL_COMMON_THRESHOLDS_AND_ALL_COMMON_GEOMETRY_READBACK_MUST_PASS')
        source=C.meta(c['common_candidate_reference']);C.need(source['schema']=='COMMON_POPULATION_PRODUCER_V1'
          and source['status']=='PENDING_ACTUAL_PARENT_C0_AND_INDEPENDENT_ROOT_REVIEW','ACTUAL_CPU_COMMON_PRODUCER_ONLY')
        manifest=dict(source,schema='COMMON_POPULATION_V1_FROZEN',status='COMMON_POPULATION_V1_FROZEN',
          actual_parent_accounting=c['accounting_reference'],actual_postprocess_C0=c['actual_parent'],root_component_review=rv,
          source_producer_manifest=c['common_candidate_reference'],actual_entry_reference=c['receipt_reference'],actual_entry_preflight_reference=c['preflight_reference'],
          actual_entry_startup_proof_reference=c['startup_proof_reference'],orders_frozen=False,order_manifest=None)
        result['common_manifest_reference']=C.G.write_new(out/'common_manifest.json',manifest)
    if r['approve_D7']:
        C.need(result['common_manifest_reference'] is not None and c['PM7_full_source_cache_complete'] is True
          and c['ordinary_Common_D7_geometry_complete'] is True and c['three_order_Common_release_eligible'] is True and c['unknown_molecules']==0,
          'FULL_EXACT_COMMON_PM7_SPRIME_ORDER_AND_STATS_CLOSURE_REQUIRED')
        source=C.meta(result['common_manifest_reference'])
        order={'schema':'CONFORMER_ORDER_V1_FROZEN','status':'CONFORMER_ORDER_V1_FROZEN','order_types':['fixed_random','energy','diversity'],'rank_base':0,
          'order_tables':c['order_tables'],'source_geometry_tables':source['physical_geometry_tables'],'common_population_manifest':result['common_manifest_reference'],
          'common_population_manifest_sha256':result['common_manifest_reference']['sha256'],'roles_manifest_sha256':source['roles_manifest_sha256'],
          'roles_manifest':source['roles_manifest'],'random_order_seed':20261025,'geometry_witness_tables':c['geometry_witness_tables'],
          'statistics_reference':c['statistics_reference'],'actual_parent_accounting':c['accounting_reference'],'root_review_reference':rv,
          'ordinary_Sprime_only':True,'N1_extra_domain_included':False,'new_QM_UFF_calls':0}
        result['order_manifest_reference']=C.G.write_new(out/'order_manifest.json',order)
    return C.G.write_new(out/'accepted_components.json',result)

def main():
    p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(dest='mode',required=True)
    a=sp.add_parser('proposal');a.add_argument('--output',type=pathlib.Path,required=True)
    a=sp.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=sp.add_parser('accept');a.add_argument('--receipt',type=pathlib.Path,required=True);a.add_argument('--accounting',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=sp.add_parser('finalize');a.add_argument('--candidate',type=pathlib.Path,required=True);a.add_argument('--root-review',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args();print(proposal(a.output) if a.mode=='proposal' else draft(a.request,a.output) if a.mode=='draft' else accept(a.receipt,a.accounting,a.output) if a.mode=='accept' else finalize(a.candidate,a.root_review,a.output))

if __name__=='__main__':main()
