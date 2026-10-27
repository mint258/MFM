"""Producer plan and SB1 unsigned Root request; never submit or approve Root."""
import argparse,pathlib
from . import contract as C


def draft(request_path,output):
    C.G.on_login();request=C.G.load(request_path)
    C.need(request['schema']=='ROOT_REQUESTED_SPRIME_PACKED_DAY_V1' and request['status']=='REQUESTED_FOR_REVIEW' and request['requested_by']=='root','ACTUAL_ROOT_PACKED_INPUT_REQUEST')
    names=('original_config_reference','original_plan_reference','inputs_review_reference','source_mapping_review_reference','resource_authority_reference',
        'quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference','cpus','output_directory')
    plan={k:request[k] for k in names};cap=request.get('output_cap_bytes',request.get('estimated_peak_output_bytes'))
    C.need(cap is not None and ('estimated_peak_output_bytes' not in request or request['estimated_peak_output_bytes']==cap),'ONE_EXACT_PACKED_WRITER_CARVEOUT')
    value=C.F.config(plan['original_config_reference'])
    plan.update(schema='SPRIME_PACKED_DAY_PLAN_V1',wall_seconds=86400,stop_dispatch_before_wall_seconds=900,output_cap_bytes=cap,
        algorithm_rss_soft_cap_bytes=request.get('algorithm_rss_soft_cap_bytes',value['algorithm_rss_soft_cap_bytes']),
        minimum_MemAvailable_bytes=request.get('minimum_MemAvailable_bytes',value['minimum_MemAvailable_bytes']),
        packet_compressed_limit_bytes=value['packet_compressed_limit_bytes'],recipe_config=value['recipe_config'])
    plan['scope_parameters']=C.parameters(plan);value,original,review,parents=C.input_metadata(plan)
    data=C.data_locators(plan,value,original,review)
    out=pathlib.Path(output);target=pathlib.Path(plan['output_directory'])
    C.need(out.is_absolute() and C.ROOT/'control' in out.parents and not out.exists() and '..' not in out.parts
        and target.is_absolute() and C.ROOT/'artifacts/conformers' in target.parents and not target.exists() and '..' not in target.parts,'FRESH_CONTROL_AND_SINGLE_PARENT_OUTPUT')
    carve=C.metadata_ref(plan['root_carveout_review_reference'])
    C.need(carve['packed_parent_carveout_bytes']==cap and carve['future_after_carveout_not_greater_than_before'] is True,'ACTUAL_ROOT_EXISTING_RESERVATION_CARVEOUT_NOT_ADDED_TWICE')
    out.mkdir(parents=True,mode=0o700);plan_ref=C.G.write_new(out/'plan.json',plan)
    refs=C.G.References({'source_references':[],'data_references':data})
    for ref in [*C.sources(),*parents,plan_ref,C.small_pin(request_path)]:refs.add(ref)
    for item in review.get('existing_prepared_headers',[]):refs.add(item['prepared_reference'])
    for row in review['registered_runs']:
        r=C.metadata_ref(row['request_reference']);argv=r['execution_argv']
        if '--prepared' in argv:refs.small(argv[argv.index('--prepared')+1])
    refs.validate_small_sources()
    result={'schema':'ROOT_REQUESTED_SPRIME_PACKED_DAY_V1','status':'UNSIGNED_PENDING_ROOT_RESOURCE_REQUEST_REVIEW','requested_by':None,
        'job_name':request['job_name'],'cpus':plan['cpus'],'scope_parameters':plan['scope_parameters'],'producer_plan_reference':plan_ref,
        'estimated_peak_output_bytes':cap,'resource_authority_reference':plan['resource_authority_reference'],
        'quota_provider_review_reference':plan['quota_provider_review_reference'],'quota_provider_identity_reference':plan['quota_provider_identity_reference'],
        'root_carveout_review_reference':plan['root_carveout_review_reference'],'source_references':list(refs.sources.values()),'data_references':list(refs.data.values()),
        'wall_seconds':86400,'kind':'conformer','pilot':False,'Source_only_not_a_Submission_or_Root_signature':True}
    C.G.write_new(out/'resource_request.template.json',result)
    return C.G.write_new(out/'producer_draft.json',{'schema':'SPRIME_PACKED_PRODUCER_DRAFT_V1','status':'ACTUAL_PLAN_READY_FOR_SB1_INDEPENDENT_ROOT_RESOURCE_SCOPE_REVIEW',
        'producer_plan_reference':plan_ref,'resource_request_template_reference':C.small_pin(out/'resource_request.template.json'),
        'scientific_DATA_opened_or_hashed_on_login':False,'Root_signed_or_submitted':False})


def accept(receipt_path,accounting_path,output):
    C.G.on_login();rr,receipt=C.meta(receipt_path,'SPRIME_PACKED_DAY_RECEIPT_V1');jid=receipt['actual_single_parent_job_id']
    plan=C.metadata_ref(receipt['plan_reference']);ar,av,parent=C.packed_account(accounting_path,jid,plan['cpus']);proof=C.metadata_ref(receipt['startup_proof_reference'])
    C.need(proof['request']['producer_plan_reference']==receipt['plan_reference'] and str(proof['job_id'])==jid
        and proof['request']['cpus']==receipt['allocated_cpus']==plan['cpus'] and parent['alloc_cpus']==plan['cpus']
        and proof['request']['scope_key']==C.KEY and receipt['child_Slurm_jobs_created']==0 and receipt['new_parent_C0_or_Common_quality_release_claimed'] is False,
        'ONE_ACTUAL_PACKED_C0_NOT_CHILD_OR_SCIENTIFIC_QUALITY_RELEASE')
    out=pathlib.Path(output);C.need(out.is_absolute() and C.ROOT/'control' in out.parents and not out.exists(),'FRESH_ROOT_ACCEPTANCE_PROPOSAL');out.mkdir(parents=True,mode=0o700)
    return C.G.write_new(out/'common_collection_candidate.json',{'schema':'SPRIME_PACKED_ACTUAL_PARENT_COMMON_COLLECTION_CANDIDATE_V1',
        'status':'PENDING_INDEPENDENT_ROOT_COMMON_AND_FAILURE_THRESHOLD_REVIEW','actual_parent_receipt_reference':rr,'actual_parent_accounting_reference':ar,
        'actual_parent_raw_accounting_reference':av['raw_sacct_reference'],'actual_parent':parent,'original_plan_reference':plan['original_plan_reference'],
        'inputs_review_reference':plan['inputs_review_reference'],'resolution_index_reference':receipt['resolution_index_reference'],
        'complete_errors_reference':receipt['complete_errors_reference'],'state_counts':receipt['state_counts'],'resource_report':receipt['resource_report'],
        'original_C0_FAILED_TIMEOUT_UNKNOWN_origins_separate':True,'Root_full_population_and_Se_exclusion_gates_still_required':True,
        'Common_or_training_or_physical_int64_release':False,'scientific_DATA_opened_or_hashed_on_login':False})


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='mode',required=True)
    a=s.add_parser('draft');a.add_argument('--request',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=s.add_parser('accept');a.add_argument('--receipt',type=pathlib.Path,required=True);a.add_argument('--accounting',type=pathlib.Path,required=True);a.add_argument('--output',type=pathlib.Path,required=True)
    a=p.parse_args();print(draft(a.request,a.output) if a.mode=='draft' else accept(a.receipt,a.accounting,a.output))


if __name__=='__main__':main()
