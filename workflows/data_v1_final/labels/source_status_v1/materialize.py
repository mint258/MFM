"""Stdlib only: exact Root metadata/specs; NEVER submit, import science, or read data bodies."""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from .support import PROJECT, RUN, TASK_FAMILIES, load, need, save, small_ref
from .prepare import make_shards
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
MODULE='workflows.data_v1_final.labels.source_status_v1.'

def stable_small(pin):
    actual=small_ref(pin['path']);need(actual==pin,'EXISTING_SMALL_SOURCE_PIN_DIFFERS:'+pin['path']);return actual

def source_refs(repository,config,extra):
    files=[*Path(repository).joinpath('workflows/data_v1_final/labels/source_status_v1').glob('*.py'),
           Path(repository)/'workflows/data_v1_final/execution/queue_v1/queue_contract.py',Path(config)]
    cost=Path(config).parent/'cost_and_scope_plan.json'
    if cost.exists():files.append(cost)
    refs={str(p.absolute()):small_ref(p) for p in files}
    for pin in extra:
        stable_small(pin);need(pin['path'] not in refs or refs[pin['path']]==pin,'CONFLICTING_ACTUAL_ROOT_PIN');refs[pin['path']]=pin
    return list(refs.values())

def spec(path,config,repository,stage,argv,cap,wall,data,extra):
    cfg=load(config);refs=source_refs(repository,config,[*cfg['metadata'].values(),*extra])
    bodies={p['path']:p for p in data}
    need(len(bodies)==len(data),'DUPLICATE_DATA_LOCATOR')
    body={'schema':'ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1','status':'ROOT_REVIEW_REQUIRED_NOT_SUBMITTED',
      'kind':'analysis','pilot':False,'source_status_stage':stage,'cpus':16,'memory_gib':64,
      'wall_seconds':wall,'stage_output_cap_bytes':cap,
      'estimated_peak_output_bytes':cfg['prepare_output_cap_bytes']+cfg['shards']*cfg['scan_output_cap_bytes']+cfg['reduce_output_cap_bytes'],
      'source_references':refs,
      'data_references':list(bodies.values()),'execution_argv':[PY,'-B','-m',MODULE+stage,*argv,
          '--startup-proof','__ROOT_STARTUP_PROOF__'],
      'complete_source_population_audit_not_final_D4':True,'full_guide_1_5_completed':False,
      'requires_nonpilot_queue_materializer':'Frozen queue_v1.materialize is pilot-only; Root must bind a NEW reviewed adapter.',
      'no_automatic_submission_retry_or_full_follow_on':True}
    return save(path,body)

def initial(a,out):
    repository=Path(a.repository);old=repository/'configs/data_v1/labels/streaming_v1.json'
    previous=load(old);metadata={key:stable_small(previous['sources'][key]) for key in ('roles','registry','verification')}
    metadata['registry_v3']=metadata.pop('registry')
    metadata['source_projection']=small_ref(RUN/'control/sb3_catalog_projection_v1/source_files.json')
    metadata['projection_receipt']=small_ref(RUN/'control/sb3_catalog_projection_v1/projection_receipt.json')
    receipt=load(metadata['projection_receipt']['path'])
    need(receipt['source_files']==metadata['source_projection'] and receipt['verification']==metadata['verification'],'CLOSED_PROJECTION_DIFFERS')
    metadata['historical_projection_validator']=stable_small(receipt['script'])
    metadata['protocol']=small_ref(PROJECT/'runs/phase1_wp5_20261011/configs/protocol.json')
    protocol=load(metadata['protocol']['path']);registry_path=protocol['registry']['path']
    metadata['registry_v2']=small_ref(registry_path)
    need(metadata['registry_v2']['sha256']==protocol['registry']['sha256'],'FROZEN_ORIGINAL_REGISTRY_DIFFERS')
    metadata['frozen_parquet_encoder']=small_ref(PROJECT/'runs/phase1_wp5_20261011/scripts/wp5_parquet_v2.py')
    metadata['streaming_config_baseline']=small_ref(old)
    prepared=RUN/'artifacts/labels/streaming_v1/prepared_pilot_v1/group_plan.json'
    profile=RUN/'artifacts/labels/streaming_v1/profile_pilot_v2/scan_manifest.json'
    metadata['prior_bounded_prepare']=small_ref(prepared);metadata['prior_bounded_profile']=small_ref(profile)
    bounded=load(prepared);locators={'catalog':previous['sources']['catalog'],'population':previous['sources']['population'],
        'latest_molecules':bounded['latest_runtime_pin']}
    need(locators['catalog']==receipt['catalog'],'CATALOG_AUTHORITY_DIFFERS')
    roles=load(metadata['roles']['path']);files=load(metadata['source_projection']['path'])
    n=sum(x['records'] for x in roles['roles'].values());m=sum(x['molecules'] for x in roles['roles'].values())
    need(sum(x['latest_rows'] for x in files)==14*n,'FULL_FOURTEEN_SLOT_SOURCE_PROJECTION_DIFFERS')
    artifacts=Path(a.artifacts_root)
    need((RUN/'artifacts/labels/source_status_v1') in artifacts.parents,'NEW_SOURCE_STATUS_ARTIFACT_SUBDIR_REQUIRED')
    cfg={'schema':'SOURCE_STATUS_AUDIT_CONFIG_V1','metadata':metadata,'locators':locators,
      'workers':16,'shards':16,'batch_records':256,'worker_rss_stop_bytes':3<<30,
      'prepare_output_cap_bytes':24<<30,'scan_output_cap_bytes':2<<30,'reduce_output_cap_bytes':4<<30,
      'prepare_wall_seconds':7200,'scan_wall_seconds':7200,'reduce_wall_seconds':3600,
      'examples_per_file':32,'precision_variants_per_file':64,'artifacts_root':str(artifacts),
      'source_scope':'ALL_ORIGINAL_ROLES_NO_COMMON_NO_SPRIME_FILTER','task_to_family':TASK_FAMILIES,
      'raw_numeric_arrays_and_json_payloads_projected':False,'new_masks_created':False,
      'native_print_precision_from_parquet_inference_forbidden':True,'normalization_completed':False}
    config=out/'config.json';save(config,cfg)
    role_parts=[r for r in roles['outputs'] if Path(r['path']).parent.name=='molecule_roles']
    families={}
    for family in sorted({x['family'] for x in files}):
        members=[x for x in files if x['family']==family]
        families[family]={'files':len(members),'physical_rows':sum(x['rows'] for x in members),
            'canonical_rows':sum(x['latest_rows'] for x in members),'compressed_bytes_upper_bound':sum(x['bytes'] for x in members),
            'tasks':sorted(t for t,f in TASK_FAMILIES.items() if f==family)}
    whole=(cfg['prepare_output_cap_bytes']+cfg['shards']*cfg['scan_output_cap_bytes']+cfg['reduce_output_cap_bytes'])
    coreceil=(cfg['prepare_wall_seconds']+cfg['shards']*cfg['scan_wall_seconds']+cfg['reduce_wall_seconds'])*16/3600
    shard_costs=[{k:v for k,v in s.items() if k!='files'}|{'files':len(s['files']),'fixed_output_reservation_bytes':sum(x['latest_rows']*64+(4<<20) for x in s['files'])} for s in make_shards(files,cfg['shards'])]
    need(all(s['fixed_output_reservation_bytes']+(4<<20)<=cfg['scan_output_cap_bytes'] for s in shard_costs),'ACTUAL_METADATA_SHARD_RESERVATIONS_EXCEED_CONFIG_CAP')
    save(out/'cost_and_scope_plan.json',{'schema':'SOURCE_STATUS_FULL_SCOPE_COST_PLAN_V1','status':'METADATA_PLAN_NOT_EXECUTED',
      'shard_metadata_costs':shard_costs,'config':small_ref(config),'records':n,'molecules':m,'roles':roles['roles'],'families':families,
      'files':len(files),'source_jobs':len({x['source_job_id'] for x in files}),
      'file_groups':len({(x['source_job_id'],x['source_file_group']) for x in files}),
      'physical_task_rows':sum(x['rows'] for x in files),'canonical_task_rows':sum(x['latest_rows'] for x in files),
      'noncanonical_physical_rows':sum(x['rows']-x['latest_rows'] for x in files),
      'all_compressed_source_bytes_upper_bound':sum(x['bytes'] for x in files),
      'metadata_projection_actual_bytes_and_runtime':'UNMEASURED_NEW_PASS',
      'whole_pipeline_new_unique_inode_cap_bytes':whole,'minimum_remaining_account_bytes':200_000_000_000,
      'allocation_core_hour_ceiling_not_forecast':coreceil,
      'over_500_core_hours':coreceil>500,'before_remaining_shards':'Root must accept actual first-source-shard runtime/RSS/output evidence and whole budget; do not auto-submit all.',
      'existing_evidence_scope':'4520374: 512 molecules/4251 records/16 groups, full source bodies associated with selected jobs read, not a full-population forecast. EA4520570: IO handle/cache lifecycle only.',
      'prior_pilot_source_bytes':sum(r['bytes'] for g in bounded['groups'] for r in g['label_files']),
      'raw_print_precision_and_payload_shape_remain_pending':True,'new_masks_created':False,'normalization_completed':False})
    spec(out/'prepare_spec.json',config,a.repository,'prepare',['--config',str(config),'--output',str(artifacts/'prepared')],
      cfg['prepare_output_cap_bytes'],cfg['prepare_wall_seconds'],[locators['population'],locators['latest_molecules'],*role_parts],[small_ref(out/'cost_and_scope_plan.json')])
    return {'config':small_ref(config),'prepare_spec':small_ref(out/'prepare_spec.json'),'plan':small_ref(out/'cost_and_scope_plan.json')}

def scan_specs(a,out):
    config=Path(a.config);cfg=load(config);plan=load(a.prepared)
    need(plan['config']==small_ref(config) and plan['status']=='PREPARED_NOT_SCANNED','ACTUAL_PREPARED_PLAN_REQUIRED')
    selected=plan['shards'] if a.only_shard is None else [s for s in plan['shards'] if s['shard_id']==a.only_shard]
    need(bool(selected),'SELECTED_SHARD_NOT_FOUND');result=[]
    for shard in selected:
        sid=shard['shard_id'];output=Path(cfg['artifacts_root'])/('shard_'+str(sid).zfill(2))
        result.append(spec(out/('scan_'+str(sid).zfill(2)+'_spec.json'),config,a.repository,'scan',
          ['--config',str(config),'--plan',str(Path(a.prepared)),'--shard-id',str(sid),'--output',str(output)],
          cfg['scan_output_cap_bytes'],cfg['scan_wall_seconds'],[plan['canonical_index'],*shard['files']], [small_ref(a.prepared)]))
    return {'specs':result,'new_scientific_data_bodies_read_or_stat':False,'submitted':False}

def reduce_spec(a,out):
    config=Path(a.config);cfg=load(config);plan=load(a.prepared);need(plan['config']==small_ref(config),'PLAN_CONFIG_DIFFERS')
    need(len(a.shard_manifest)==len(plan['shards']),'ALL_ACTUAL_SHARD_MANIFESTS_REQUIRED')
    extra=[small_ref(a.prepared)];data=[plan['canonical_index']];argv=['--config',str(config),'--plan',str(Path(a.prepared))]
    seen=set()
    for path in a.shard_manifest:
        manifest=load(path);need(manifest['prepared_plan']==small_ref(a.prepared) and manifest['status']=='SHARD_COMPLETE_REDUCTION_REQUIRED','ACTUAL_SHARD_CLOSURE_REQUIRED')
        need(manifest['shard_id'] not in seen,'DUPLICATE_SHARD');seen.add(manifest['shard_id'])
        extra.append(small_ref(path));argv+=['--shard-manifest',str(Path(path))]
        for item in manifest['files']:
            data.append(item['report'])
            if item['coverage'] is not None:data.append(item['coverage'])
    argv+=['--output',str(Path(cfg['artifacts_root'])/'reduction')]
    result=spec(out/'reduce_spec.json',config,a.repository,'reduce',argv,cfg['reduce_output_cap_bytes'],cfg['reduce_wall_seconds'],data,extra)
    return {'reduce_spec':result,'data_bodies_read_or_stat':False,'submitted':False}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('initial','scan','reduce'))
    p.add_argument('--repository',required=True);p.add_argument('--output-directory',required=True)
    p.add_argument('--artifacts-root');p.add_argument('--config');p.add_argument('--prepared')
    p.add_argument('--only-shard',type=int);p.add_argument('--shard-manifest',action='append',default=[]);a=p.parse_args()
    repository=Path(a.repository);need(repository==RUN/'repository','ACTUAL_ROOT_REPOSITORY_REQUIRED')
    out=Path(a.output_directory).absolute();need(RUN in out.parents and not out.exists(),'NEW_EXTERNAL_METADATA_DIRECTORY_REQUIRED')
    need(not any(x.is_symlink() for x in (out,*out.parents)),'NO_OUTPUT_SYMLINKS');out.mkdir(parents=True,mode=0o700)
    if a.stage=='initial':need(a.artifacts_root is not None,'ARTIFACTS_ROOT_REQUIRED');result=initial(a,out)
    elif a.stage=='scan':need(a.config is not None and a.prepared is not None,'CONFIG_AND_PREPARED_REQUIRED');result=scan_specs(a,out)
    else:need(a.config is not None and a.prepared is not None,'CONFIG_AND_PREPARED_REQUIRED');result=reduce_spec(a,out)
    save(out/'materialization_receipt.json',{'status':'METADATA_ONLY_PREPARED_NOT_SUBMITTED','stage':a.stage,'result':result,
      'helper':small_ref(__file__),'scientific_imports':False,'large_data_body_reads_or_stats':False,'slurm_calls':False})
    print(json.dumps(result))
if __name__=='__main__':main()