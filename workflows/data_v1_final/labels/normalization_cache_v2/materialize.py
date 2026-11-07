"""Pure-stdlib finite profile metadata; no cache/owner/histogram body IO."""
from __future__ import annotations
import argparse,json
from pathlib import Path
from workflows.data_v1_final.labels.bounded_projection_v1.materialize import RUN,REPO,PY,actual_parent,load,pin,require,save,unique
SCOPE='source_train_typed_cache_512_profile_v2'


def need(ok,code):
    if not ok:raise ValueError(code)


def main():
    from .parents import failed_parent
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('cache-manifest','cache-proof','cache-accounting','cache-raw','legacy-profile','resource-authority','metadata-directory','output','reason'):
        p.add_argument('--'+key,required=True)
    p.add_argument('--query-stage')
    for key in ('previous-manifest','previous-proof','previous-accounting','previous-raw'):p.add_argument('--'+key)
    for key in ('prior-failed-proof','prior-failed-accounting','prior-fixture-gate'):p.add_argument('--'+key,required=True)
    p.add_argument('--approve',action='store_true');a=p.parse_args()
    need(a.approve and a.reason.strip(),'EXPLICIT_ROOT_FINITE_PROFILE_REVIEW')
    need(Path(__file__).absolute().parent==REPO/'workflows/data_v1_final/labels/normalization_cache_v2','ACTUAL_ROOT_SOURCE_PATH')
    failed_refs=failed_parent(a.prior_failed_proof,a.prior_failed_accounting,a.prior_fixture_gate)
    _,parents=actual_parent(a.cache_manifest,a.cache_proof,a.cache_accounting,a.cache_raw)
    cache=load(a.cache_manifest);need(cache['schema']=='LOSSLESS_LABEL_PROJECTION_PILOT_V1'
      and cache['status']=='PILOT_CACHE_CLOSED_FULL_NOT_AUTHORIZED' and cache['quality_stop_fields']==[],'ACTUAL_CLOSED512_CACHE_NOT_FULL')
    baseline=load(require(cache['config']));plan=load(require(baseline['owner_plan']));fields=load(require(plan['field_map']))
    need((plan['records'],plan['molecules'],len(plan['groups']),len(fields))==(4251,512,16,146),'EXACT_FINITE_CACHE_SCOPE')
    registered=load(require(baseline['science']['sources']['registry']))['fields']
    enabled=sorted((f for f in registered if f['status']=='enabled'),key=lambda f:f['field_key'])
    need(len(enabled)==146 and sorted(f['field_id'] for f in fields)==list(range(146)),'DENSE_146_FIELD_IDS')
    mapped={f['field_id']:f for f in fields}
    need(all(all(mapped[i][k]==f[k] for k in ('field_key','registry_id','task','source_path','component','level','physical_range'))
      for i,f in enumerate(enabled)),'LEGACY_FIELD_MAP_AND_CACHE_REGISTRY_SEMANTICS_DIFFER')
    legacy=load(a.legacy_profile);need(legacy['mode']=='pilot' and legacy['phase']=='profile' and legacy['plan']==baseline['owner_plan']
      and legacy['coverage_fingerprint']==plan['coverage_fingerprint'],'MATCHED_ORIGINAL_LEGACY_PROFILE')
    reports={};small=[*failed_refs,cache['config'],baseline['owner_plan'],plan['field_map'],pin(a.legacy_profile),legacy['queries'],
      baseline['science']['calibration'],pin(a.resource_authority),*parents,*baseline['small_references']]
    for r in legacy['group_receipts']:
        item=load(require(r));need(item['status']=='SOURCE_GROUP_SCANNED' and item['group_index'] not in reports,'UNIQUE_CLOSED_LEGACY_GROUP')
        reports[item['group_index']]=(r,item);small.append(r)
    cache_reports={};groups=[];data=[]
    for item in cache['groups']:
        report=load(require(item['report']));i=report['group_index'];need(i not in cache_reports and report['status']=='CACHE_REOPEN_VERIFIED_NOT_FINAL_LABELS','UNIQUE_CLOSED_TYPED_GROUP')
        cache_reports[i]=report;small.append(item['report'])
    need(set(cache_reports)==set(reports)=={g['group_index'] for g in plan['groups']},'SAME16_REAL_OWNER_GROUPS')
    for g in sorted(plan['groups'],key=lambda g:g['group_index']):
        i=g['group_index'];cr=cache_reports[i];rr,lr=reports[i]
        need(cr['records']==lr['records']==g['expected_records'] and lr['owner_index']==g['owner_index']
          and cr['cache_rows']==g['expected_records']*15,'MATCHED_OWNER_AND_TASK_MASS')
        groups.append({'group_index':i,'cache':cr['cache'],'owner_index':g['owner_index'],'legacy_report':rr,
          'expected_records':g['expected_records'],'expected_molecules':g['expected_molecules']})
        data.extend([cr['cache'],g['owner_index'],lr['radix_histogram']])
    old_queries=load(require(legacy['queries']))
    need(old_queries['purpose']=='median' and old_queries['round']==0,'ORIGINAL_ROUND0_MEDIAN_QUERY_ORACLE')
    if a.query_stage:
        need(all((a.previous_manifest,a.previous_proof,a.previous_accounting,a.previous_raw)),'REFINEMENT_REQUIRES_ACTUAL_PREVIOUS_C0')
        _,previous_parents=actual_parent(a.previous_manifest,a.previous_proof,a.previous_accounting,a.previous_raw)
        previous=load(a.previous_manifest)
        need(previous['schema']=='SOURCE_TRAIN_TYPED_CACHE_PROFILE_MANIFEST_V1' and previous['status']=='FINITE_PASS_CLOSED_PROVISIONAL_ONLY'
          and previous['next_query_stage']==pin(a.query_stage),'EXACT_CLOSED_PARENT_QUERY_STAGE_NOT_PARTIAL')
        previous_cfg=load(require(previous['config']))
        need(previous_cfg['cache_manifest_reference']==pin(a.cache_manifest) and previous_cfg['field_map_reference']==plan['field_map'],
          'REFINEMENT_CACHE_AND_FIELD_SCOPE_UNCHANGED')
        parents.extend(previous_parents);small.extend(previous_parents)
        stage=load(a.query_stage);small.append(pin(a.query_stage))
        need(stage['schema']=='SOURCE_TRAIN_TYPED_CACHE_QUERY_STAGE_V1' and stage['cache_manifest_reference']==pin(a.cache_manifest)
          and stage['field_map_reference']==plan['field_map'] and stage['source_role']=='TRAIN'
          and stage['final_Common_normalization_allowed'] is False and stage['full_source_population'] is False,'MATCHED_QUERY_SCOPE_NOT_COMMON_OR_OTHER_POPULATION')
    else:stage={'queries':old_queries,'finished':{'median':[],'MAD':[]}}
    queries=stage['queries'];need(queries['purpose'] in ('median','MAD') and queries['fields'],'FINITE_NEXT_QUERY_NOT_ALREADY_CLOSED_OR_FINAL_TAIL')
    comparison=(queries==old_queries);params={'records':4251,'molecules':512,'groups':16,'workers':16,'task_slots':14,
      'enabled_fields':146,'source_role':'TRAIN','query_purpose':queries['purpose'],'query_round':queries['round'],
      'whole_output_cap_bytes':4<<30,'new_UFF_QM_calls':0,'full_population':False,'final_Common_D4':False,
      'cache_manifest_sha256':pin(a.cache_manifest)['sha256'],'legacy_profile_comparison':comparison}
    directory=Path(a.metadata_directory).absolute();output=Path(a.output).absolute()
    need(RUN in directory.parents and not directory.exists() and RUN/'artifacts/labels/source_status_v1' in output.parents
      and not output.exists(),'NEW_PROFILE_METADATA_AND_OUTPUT')
    directory.mkdir(parents=True,mode=0o700)
    code=unique(baseline['source_references']+[pin(q) for q in Path(__file__).parent.iterdir() if q.suffix in ('.py','.md')]
      +[pin(REPO/'workflows/data_v1_final/labels/normalization_cache_v1/reader.py')]
      +[pin(REPO/'workflows/data_v1_final/labels/streaming_v1/calibration.py')])
    config={'schema':'SOURCE_TRAIN_TYPED_CACHE_PROFILE_CONFIG_V1','scope_parameters':params,'science':baseline['science'],
      'cache_manifest_reference':pin(a.cache_manifest),'field_map_reference':plan['field_map'],'source_role':'TRAIN',
      'groups':groups,'queries':queries,'query_stage':stage,'compare_legacy_profile':comparison,
      'matched_legacy_reference':baseline['science']['calibration'],'element_basis':plan['element_basis'],
      'row_serialized_cap_bytes':64<<20,'worker_rss_stop_bytes':3<<30,'serialized_buffer_cap_bytes':64<<20,
      'whole_output_cap_bytes':4<<30,'worker_output_cap_bytes':128<<20,'small_references':unique(small),
      'source_references':code,'full_source_population':False,'candidate_masks_are_final':False,'final_Common_normalization_allowed':False}
    cr=save(directory/'config.json',config)
    binding={'schema':'SOURCE_TRAIN_TYPED_CACHE_PROFILE_RESOURCE_BINDING_V1','scientific_config_reference':cr,'scope_key':SCOPE,'scope_parameters':params,
      'resource_authority_reference':pin(a.resource_authority),'memavailable_soft_floor_bytes':4<<30,
      'resource_evidence_local_cap_bytes':64<<20,'resource_evidence_output':str(output)+'_resource_observation'}
    bp=save(directory/'resource_binding.json',binding)
    argv=[PY,'-B','-m','workflows.data_v1_final.labels.normalization_cache_v2.run','--config',cr['path'],
      '--startup-proof','__ROOT_STARTUP_PROOF__','--output',str(output)]
    parents=unique([*parents,pin(a.legacy_profile)])
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root','reason':a.reason,
      'resource_authority_reference':pin(a.resource_authority),'kind':'analysis','pilot':True,'scope_key':SCOPE,'scope_parameters':params,
      'scope_mode':'BOUNDED_PERFORMANCE_BATCH','wall_seconds':7200,'estimated_peak_output_bytes':4<<30,'stage_output_cap_bytes':4<<30,
      'source_status_stage':None,'execution_argv':argv,'bounded_batch_limits_reviewed':True,'profile_reviewed':True,
      'approved_profile_reference':pin(a.cache_manifest),'parent_evidence_references':parents,'final_Common_D4_authorized':False}
    rp=save(directory/'scope_review.json',review)
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':True,'cpus':16,'memory_policy':'SLURM_DEFAULT_UNSPECIFIED',
      'wall_seconds':7200,'estimated_peak_output_bytes':4<<30,'stage_output_cap_bytes':4<<30,'source_status_stage':None,
      'execution_argv':argv,'source_references':unique([*code,*small,cr,bp,rp]),'data_references':unique(data),
      'scope_key':SCOPE,'scope_parameters':params,'scope':{'mode':'BOUNDED_PERFORMANCE_BATCH','review':rp,'parent_profile':pin(a.cache_manifest)},
      'producer_resource_binding_reference':bp}
    save(directory/'stage_spec.json',spec)
    save(directory/'preparation_receipt.json',{'status':'METADATA_ONLY_NOT_SUBMITTED','body_locators':len(unique(data)),
      'cache_data_bytes_inherited':sum(g['cache']['bytes'] for g in groups),'original_Parquet_LMDB_cache_owner_histogram_bodies_read':False,
      'scope':'MATCHED512_SOURCE_TRAIN_NOT_FULL_OR_COMMON','current_body_SHA_verification':'CPU_AFTER_SIX_NEW_FIXTURES'})
    print(json.dumps({'status':'METADATA_ONLY_NOT_SUBMITTED','stage_spec':str(directory/'stage_spec.json')}))

if __name__=='__main__':main()
