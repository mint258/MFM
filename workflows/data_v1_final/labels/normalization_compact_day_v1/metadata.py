"""Small Root metadata only; every numerical/cache body stays declared DATA."""
import argparse,copy,os
from pathlib import Path
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import metadata as OLD,contract as B
from workflows.data_v1_final.labels.bounded_projection_v1 import materialize as M
from . import contract as C

def build(path,output):
    req=M.load(path);C.need(req['schema']=='ROOT_COMPACT_NUMERIC_DAY_REQUEST_V1' and req['requested_by']=='root','REAL_ROOT_DAY_REQUEST')
    mode=req.get('execution_mode','PROJECT_AND_COVERAGE_ONLY');C.need(mode in ('PROJECT_AND_COVERAGE_ONLY','PROVISIONAL_SOURCE_TRAIN_DESCRIPTIVE_REVIEWED'),'FINAL_COMMON_STATS_NONEXECUTABLE_NO_FUTURE_PARENTS')
    out=Path(output).absolute();C.need(C.RUN/'control' in out.parents and not out.exists(),'FRESH_SMALL_DAY_METADATA_ONLY');out.mkdir(mode=0o700,parents=True)
    seed_ref=req['seed_config_reference'];seed=B.validate_config(M.load(M.require(seed_ref)));C.need(seed['mode']=='full' and seed['stage']=='project','ACTUAL_V3_FULL_CONFIG_PARENT')
    seed=copy.deepcopy(seed);profile,prefs=OLD.actual(req['accepted_512_profile_parent'])
    coverage_header=M.load(M.require(profile['coverage_reference']));coverage_config=M.load(M.require(coverage_header['config']))
    C.need(req['formal_record_index_reference']==coverage_config['formal_record_index_reference'],'ORIGINAL_ACTUAL_FORMAL_POINTER_NOT_NEW_LMDB_HASH')
    C.need(profile['mode']=='pilot512' and profile['statistics_purpose']=='legacy512' and profile['legacy_exact_comparison'] is True,'REAL512_EXACT_PARITY_C0_NOT_SOURCE_OR_IDENTITY')
    logical=M.load(M.require(seed['logical_group_plan_reference']));C.exact_logical_groups(logical['groups'])
    small=[M.pin(path),seed_ref,profile['coverage_reference'],coverage_header['config'],*seed['small_references'],*prefs,*OLD.full_logical_authority(seed['logical_group_plan_authority_reference'],seed['logical_group_plan_reference'],logical['groups'])]
    footer=M.load(M.require(seed['footer_manifest_reference']));book,index,streams,footer_small,_=M.footer_inputs(footer);B.source_contract(book['files']);small.extend(footer_small)
    prior={};history=[];observed_rows=observed_bytes=0
    for parent in req['batch_history']:
        row,refs=OLD.actual(parent);C.need(row['mode']=='full' and row['status']=='CLOSED_WINDOWS_ACTUAL_PARENT_ACCOUNTING_REQUIRED'
            and not(row['errors'] or row['quality_hold_fields'] or row['unpublished_tickets']),'ONLY_REAL_C0_OLD_V3_CLEAN_BATCHES')
        prior=B.advance_cursors(book['files'],prior,row['closed_physical_intervals']);history.append(parent);small.extend(refs)
        observed_rows+=sum(w['hi']-w['lo'] for w in row['closed_physical_intervals']);observed_bytes+=row['charged_output_bytes']
    for r in req['batch_limited_review_references']:
        m=M.load(M.require(r));C.need(m.get('reviewer')=='root','REAL_ROOT_OLD_BATCH_ACCEPTANCE');small.append(r)
    technical_ref=req['technical_review_reference'];technical=M.load(M.require(technical_ref))
    seed.update(technical_review_reference=technical_ref,whole_output_cap_bytes=req['projection_cap_bytes'],wall_seconds=86400)
    B.technical_review(seed,technical);small.extend([technical_ref,*B.parent_evidence(technical)])
    for ref in small:M.require(ref)
    if mode=='PROVISIONAL_SOURCE_TRAIN_DESCRIPTIVE_REVIEWED':
        r=req['provisional_statistics_review_reference'];v=M.load(M.require(r));C.need(v['schema']=='ROOT_EXACT_PROVISIONAL_SOURCE_TRAIN_STATISTICS_REVIEW_V1' and v['reviewer']=='root' and v['status']=='APPROVED_SOURCE_DESCRIPTIVE_NOT_FINAL_COMMON_D4' and v['final_Common_D4'] is False,'EXPLICIT_PROVISIONAL_POPULATION_NOT_D4');small.append(r)
    previous=[];transitive=[]
    for parent in req.get('previous_day_parents',[]):
        row=C.actual_day(parent);previous.append(parent);small.extend(parent.values())
        for key in ('checkpoint_reference',):transitive.append(row[key])
        transitive.extend(row['projection_outputs'])
    selector=M.save(out/'selector.json',{'sources':[{'file_id':s['file_id'],'physical_row_lo':prior.get(str(s['file_id']),0),'physical_row_hi':s['rows']}
      for s in sorted(book['files'],key=lambda s:s['file_id']) if prior.get(str(s['file_id']),0)<s['rows']]})
    seed.update(workers=req['requested_cpus'],max_actual_RGs_per_source=1<<30,output_inode_cap=4000000,selector_reference=selector,batch_history=history,
        formal_record_index_reference=req['formal_record_index_reference'],worker_histogram_row_cap=1000000,worker_serialized_buffer_cap_bytes=128<<20)
    seed.pop('config_path',None);cfg=M.save(out/'scientific_config.json',seed)
    # Original Parquets inherit closed producer SHA; CPU same-FD/footer guards
    # stay in original worker. No login opens Parquet/SQLite/typed parts.
    data=M.unique([seed['canonical_index'],req['formal_record_index_reference'],*(M.triple(s) for s in book['files']),
        *(index[s['file_id']]['inventory_reference'] for s in book['files']),*transitive])
    code=C.sources(seed);small=M.unique([*small,selector,cfg,req['resource_authority_reference'],req['native_git_assets_manifest_reference'],req['native_git_wrapper_reference']])
    git=M.load(M.require(req['native_git_assets_manifest_reference']));C.need(git['schema']=='ROOT_GIT2393_EXACT_SIX_ISOLATED_SOURCE_CHECK_ASSETS_V1'
        and len(git['files'])==6 and git['expected_git_version']=='git version 2.39.3','ORIGINAL_EXACT_SIX_GIT_SOFTWARE_ASSETS')
    assets=[r['origin_reference'] for r in git['files']]
    for r in assets:C.reference(r)
    # Software asset bytes are never login-read/hashed and are not science DATA.
    data=M.unique([*data,*assets]);allsource=M.unique([*code,*small]);denied={r['path'] for r in data}
    C.need(not denied&{r['path'] for r in allsource},'NO_NUMERIC_BODY_IN_SOURCE_REVIEW')
    plan={'schema':C.SCHEMA,'scope_key':C.KEY,'execution_mode':mode,'scientific_config_reference':cfg,'output_directory':req['output_directory'],
        'logical_group_plan_authority_reference':seed['logical_group_plan_authority_reference'],'requested_cpus':req['requested_cpus'],'wall_seconds':86400,'softwall_drain_seconds':900,
        'whole_output_cap_bytes':req['whole_output_cap_bytes'],'projection_cap_bytes':req['projection_cap_bytes'],
        'coverage_cap_bytes':req['coverage_cap_bytes'],'statistics_cap_bytes':req['statistics_cap_bytes'],
        'accepted_512_profile_parent':req['accepted_512_profile_parent'],'batch_history':history,'previous_day_parents':previous,
        'native_git_assets_manifest_reference':req['native_git_assets_manifest_reference'],'native_git_wrapper_reference':req['native_git_wrapper_reference'],
        'data_references':data,'source_references':allsource,'TSQR_chunk':256,'QR_reduction':'ORIGINAL_ORDERED_LEFT_FOLD',
        'quality_new_mask_fraction':.01,'new_QM_UFF_calls':0,'final_Common_D4_authorized':False,'cache_preserves_all_roles':True,
        'statistics_fit_role':'TRAIN_ONLY','requested_statistical_routes':([] if mode=='PROJECT_AND_COVERAGE_ONLY' else ['element_reference','normalization_quantiles','normalization_moments','diagnostic_median_MAD'])}
    scope=C.scope(plan);plan['scope_parameters']=scope;C.plan(plan);pr=M.save(out/'plan.json',plan);C.need(pr['bytes']<=2<<20,'SMALL_OPERATIONAL_DAY_PLAN_NOT_LARGE_DATA')
    template={k:req[k] for k in ('job_name','node','resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')}
    template.update(schema='ROOT_REQUESTED_ANALYSIS_DAY_V1',status='REQUESTED_FOR_REVIEW',requested_by='root',cpus=plan['requested_cpus'],scope_key=C.KEY,
      scope_parameters=scope,producer_plan_reference=pr,estimated_peak_output_bytes=plan['whole_output_cap_bytes'],source_references=M.unique([*allsource,pr]),data_references=data)
    physical=sum(s['rows'] for s in book['files']);remaining=physical-sum(prior.values());families={}
    for s in book['files']:
        f=families.setdefault(s['family'],{'files':0,'physical_rows':0,'closed_rows':0});f['files']+=1;f['physical_rows']+=s['rows'];f['closed_rows']+=prior.get(str(s['file_id']),0)
    M.save(out/'resource_forecast.json',{'schema':'COMPACT_DAY_ACTUAL_SMALL_HEADER_BIASED_FORECAST_V1','physical_rows':physical,'closed_rows':sum(prior.values()),'remaining_rows':remaining,
      'actual_closed_batch_output_charge_bytes':observed_bytes,'actual_closed_rows_in_those_batches':observed_rows,'family_physical_headers':families,
      'simple_remaining_byte_extrapolation':((remaining*observed_bytes+observed_rows-1)//observed_rows if observed_rows else None),
      'full_family_size_distribution_measured':False,'linear_forecast_is_not_cap_or_acceptance':True,'whole_ceiling_bytes':plan['whole_output_cap_bytes'],'guaranteed_24h_completion':False})
    M.save(out/'resource_request.json',template);M.save(out/'draft_receipt.json',{'schema':'COMPACT_NUMERIC_DAY_SMALL_DRAFT_V1','plan_reference':pr,
      'resource_request_reference':M.pin(out/'resource_request.json'),'source_only_not_submitted':True,'scientific_DATA_read_or_hashed':False,'remaining_cursors_CPU_revalidated':False,
      'observed_old_batch_cursors':prior,'physical_sources':len(book['files']),'logical_groups':len(logical['groups'])})

def main():
    C.need(hasattr(os,'getuid') and os.getuid()==1278,'MAIN_METADATA_ONLY')
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--request',required=True);p.add_argument('--output',required=True);a=p.parse_args();build(a.request,a.output)
if __name__=='__main__':main()
