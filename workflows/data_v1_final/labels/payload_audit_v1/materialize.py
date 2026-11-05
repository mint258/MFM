"""Stdlib metadata-only payload plans/configs/specs. No data body reads or Slurm."""
from __future__ import annotations
import argparse,collections,copy,hashlib,json
from pathlib import Path
RUN=Path('/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025');REPO=RUN/'repository'
PY='/share/home/zixiao/.conda/envs/chemprop/bin/python';MODULE='workflows.data_v1_final.labels.payload_audit_v1.'

def load(path):
    p=Path(path)
    if p.stat().st_size>2<<20:raise ValueError('SMALL_METADATA_ONLY')
    return json.loads(p.read_text(encoding='utf-8-sig'))

def pin(path):
    p=Path(path).absolute();raw=p.read_bytes()
    if len(raw)>2<<20:raise ValueError('SMALL_PIN_ONLY')
    return {'path':str(p),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}

def save(path,value):
    with Path(path).open('x',encoding='utf-8') as f:json.dump(value,f,sort_keys=True,indent=2);f.write('\n')
    return pin(path)

def sources(extra):
    files=[*Path(__file__).parent.glob('*.py'),*(REPO/'workflows/data_v1_final/execution/cpu_auto_memory_queue_v2').glob('*.py'),
      *(REPO/'workflows/data_v1_final/labels/source_status_cpu_auto_memory_v1').glob('*.py'),
      REPO/'workflows/data_v1_final/labels/streaming_v1/support.py',REPO/'workflows/data_v1_final/labels/streaming_v1/compact.py',
      REPO/'workflows/data_v1_final/labels/size_cpu_v2/aggregate.py',REPO/'workflows/data_v1_final/labels/source_status_v1/reduce.py',
      REPO/'workflows/data_v1_final/labels/source_status_v1/support.py',REPO/'workflows/data_v1_final/labels/streaming_v1/scan_v2.py',
      REPO/'workflows/data_v1_final/execution/queue_v1/__init__.py',REPO/'workflows/data_v1_final/execution/queue_v1/shared.py',REPO/'workflows/data_v1_final/execution/queue_v1/queue_contract.py']
    refs={str(p):pin(p) for p in files}
    for item in extra:
        if pin(item['path'])!=item:raise ValueError('CURRENT_SMALL_PIN_DIFFERS:'+item['path'])
        refs[item['path']]=item
    return list(refs.values())

def initial(a,out):
    census=load(a.census);full=load(census['prepared_plan']['path']);pilot=load(a.pilot_plan)
    if census['status']!='SOURCE_METADATA_CENSUS_COMPLETE_PAYLOAD_AUDIT_PENDING':raise ValueError('FULL_SOURCE_CENSUS_REQUIRED')
    bypath={r['path']:r for shard in full['shards'] for r in shard['files']}
    groups=[]
    if a.mode=='pilot':
        for old in pilot['groups']:
            members=[]
            for r in old['label_files']:
                actual=bypath[r['path']]
                if any(actual[k]!=r[k] for k in ('bytes','sha256','family','source_job_id')):raise ValueError('PILOT_SOURCE_IDENTITY_CHANGED')
                members.append(actual)
            groups.append({k:copy.deepcopy(v) for k,v in old.items() if k not in ('base_files','label_files')})
            groups[-1].update(label_files=members,shard_id=0)
        records=pilot['records'];molecules=pilot['molecules'];fingerprint=pilot['coverage_fingerprint'];shards=1
    else:
        jobs=collections.defaultdict(list)
        for r in bypath.values():jobs[r['source_job_id']].append(r)
        masses=[0]*8
        for i,(job,files) in enumerate(sorted(jobs.items(),key=lambda item:-sum(r['bytes'] for r in item[1]))):
            shard=min(range(8),key=lambda sid:(masses[sid],sid));masses[shard]+=sum(r['bytes'] for r in files)
            groups.append({'group_index':i,'source_job_id':job,'label_files':files,'owner_index':None,
              'expected_records':sum(r['latest_rows'] for r in files if r['family']=='D20'),'expected_molecules':None,'shard_id':shard})
        if any(sum(g['shard_id']==sid for g in groups)<16 for sid in range(8)):raise ValueError('SIXTEEN_TASKS_PER_FULL_SHARD')
        records=full['record_count'];molecules=full['molecule_count'];fingerprint=full['canonical_index']['sha256'];shards=8
    plan={'schema':'LABEL_PAYLOAD_OWNER_PLAN_V1','mode':a.mode,'groups':groups,'records':records,'molecules':molecules,
      'global_records':full['record_count'],'canonical_index':full['canonical_index'],'expected_roles':census['role_ledger'],
      'coverage_fingerprint':fingerprint,'shards':shards,'source_census':pin(a.census),'calibration_scope':'source TRAIN before common/diagnostic, never final D4'}
    plan_ref=save(out/'plan.json',plan)
    stream=load(REPO/'configs/data_v1/labels/streaming_v1.json')
    adapters=stream['adapter_source_pins'];cal=None
    if a.mode=='pilot':
        cal=pin(a.pilot_calibration);body=load(a.pilot_calibration)
        if body['mode']!='pilot' or body['coverage_fingerprint']!=fingerprint:raise ValueError('MATCHED_PILOT_CALIBRATION_ONLY')
    cfg={'schema':'LABEL_PAYLOAD_AUDIT_CONFIG_V1','mode':a.mode,'sources':{'plan':plan_ref,'census':pin(a.census),
      'registry':full['sources']['registry_v3'],'raw_registry':full['sources']['registry_v2'],'frozen_source_plan':census['prepared_plan']},'adapter_source_pins':adapters,
      'calibration':cal,'workers':16,'source_read_batch_records':stream['source_read_batch_records'],'output_batch_records':4096,'worker_rss_stop_bytes':3<<30,
      'group_output_cap_bytes':(64<<20) if a.mode=='pilot' else (2<<30),
      'shard_output_cap_bytes':(2<<30) if a.mode=='pilot' else (12<<30),'reduce_output_cap_bytes':4<<30,
      'preview_leaves':32,'raw_candidates_per_group':64,'raw_candidates_per_task':4,'within_molecule_examples_per_group':1000,
      'new_mask_fraction_stop':.01,'within_molecule_ratio_review':1000,'robust_z_review':20,
      'whole_output_budget_bytes':(8<<30) if a.mode=='pilot' else (128<<30),
      'wall_seconds':7200 if a.mode=='pilot' else 28800,'artifacts_root':a.artifacts_root,
      'cost_overrun_authority':pin(REPO/'configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json'),
      'native_print_precision_verified':False,'frame_origin_units_verified':False,'normalization_completed':False}
    cfg_ref=save(out/'config.json',cfg)
    save(out/'plan_receipt.json',{'status':'PAYLOAD_METADATA_PLAN_PREPARED_NOT_EXECUTED','config':cfg_ref,'plan':plan_ref,
      'source_body_read_or_stat':False,'pilot_original_selection_reused':a.mode=='pilot','full_status_not_rescanned':True,
      'calibration_state':'MATCHED_PILOT_ONLY' if cal else 'PENDING_MATCHED_FULL_TRAIN',
      'allocation_ceiling_core_hours_not_forecast':(shards*cfg['wall_seconds']+7200)*16/3600,
      'before_full_submit':'Root must accept actual bounded-payload pilot time/RSS/output and quality; REPORT_AND_CONTINUE only changes cost overrun stop rule'})

def stage(a,out):
    cfg=load(a.config);plan=load(cfg['sources']['plan']['path']);authority=pin(a.authority)
    if not a.root_reviewed:raise ValueError('ROOT_REVIEW_REQUIRED')
    parents=[pin(p) for p in a.parent_evidence];profile=pin(a.parent_profile) if a.parent_profile else None
    if profile and profile not in parents:parents.append(profile)
    mode='BOUNDED_PERFORMANCE_BATCH' if cfg['mode']=='pilot' else 'FULL_SOURCE_AFTER_PROFILE'
    if cfg['mode']=='full' and profile is None:raise ValueError('ACTUAL_ACCEPTED_PAYLOAD_PILOT_REQUIRED')
    argv=[PY,'-B','-m',MODULE+('run' if a.command=='scan' else 'reduce'),'--config',a.config,'--output',a.output,'--startup-proof','__ROOT_STARTUP_PROOF__']
    groups=[g for g in plan['groups'] if g['shard_id']==a.shard_id] if a.command=='scan' else plan['groups']
    if a.command=='scan':argv+=['--shard-id',str(a.shard_id)]
    else:
        for p in a.shard_manifest:argv+=['--shard-manifest',p]
    key='label_payload_'+cfg['mode']+'_'+a.command+(('_'+str(a.shard_id)) if a.command=='scan' else '')
    params={'records_in_scope':plan['records'],'molecules_in_scope':plan['molecules'],'shard_id':a.shard_id if a.command=='scan' else None,
      'source_groups':len(groups),'candidate_masks_only':True,'no_source_mutation':True,'final_D4':False}
    cap=cfg['shard_output_cap_bytes'] if a.command=='scan' else cfg['reduce_output_cap_bytes']
    old_sources=cfg['adapter_source_pins'];extras=[pin(a.config),*cfg['sources'].values(),cfg['cost_overrun_authority'],authority,*old_sources,*parents]
    if cfg['calibration']:extras.append(cfg['calibration'])
    if a.command=='reduce':extras += [pin(p) for p in a.shard_manifest]
    refs=sources(extras);binding={'schema':'LABEL_PAYLOAD_AUDIT_RESOURCE_BINDING_V1','scientific_config_reference':pin(a.config),
      'scope_key':key,'scope_parameters':params,'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20,
      'resource_evidence_output':a.output+'_resource_observation','software_scan_worker_cap_bytes':cfg['worker_rss_stop_bytes']}
    binding_ref=save(out/'resource_binding.json',binding);refs.append(binding_ref)
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
      'resource_authority_reference':authority,'kind':'analysis','scope_key':key,'scope_parameters':params,'scope_mode':mode,'pilot':cfg['mode']=='pilot',
      'wall_seconds':cfg['wall_seconds'] if a.command=='scan' else 7200,'estimated_peak_output_bytes':cfg['whole_output_budget_bytes'],
      'execution_argv':argv,'source_status_stage':None,'stage_output_cap_bytes':cap,'parent_evidence_references':parents,
      'bounded_batch_limits_reviewed':True,'profile_reviewed':profile is not None,'approved_profile_reference':profile}
    review_ref=save(out/'scope_review.json',review);refs.append(review_ref)
    data=[plan['canonical_index'],plan['expected_roles']]
    if a.command=='scan':
        for g in groups:
            data += g['label_files']
            if g.get('owner_index'):data.append(g['owner_index'])
    else:
        for p in a.shard_manifest:
            manifest=load(p)
            for group in manifest['groups']:
                # Exact report pointers are already hashed by actual compute producer.
                data.append(group['report'])
                report=load(group['report']['path'])
                data += [report[k] for k in ('candidate_masks','coverage','scalar_extrema_statistics_not_training_labels','details')]
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':cfg['mode']=='pilot','cpus':16,
      'memory_policy':'SLURM_DEFAULT_UNSPECIFIED','wall_seconds':review['wall_seconds'],'estimated_peak_output_bytes':cfg['whole_output_budget_bytes'],
      'stage_output_cap_bytes':cap,'execution_argv':argv,'source_references':refs,'data_references':list({r['path']:r for r in data}.values()),
      'scope_key':key,'scope_parameters':params,'scope':{'mode':mode,'review':review_ref,'parent_profile':profile},
      'producer_resource_binding_reference':binding_ref}
    save(out/'stage_spec.json',spec)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('initial','scan','reduce'))
    p.add_argument('--output-directory',required=True);p.add_argument('--mode',choices=('pilot','full'),default='pilot')
    p.add_argument('--census',default=str(RUN/'artifacts/labels/source_status_v1/auto_memory_v1/reduction/audit.json'))
    p.add_argument('--pilot-plan',default=str(RUN/'artifacts/labels/streaming_v1/prepared_pilot_v1/group_plan.json'))
    p.add_argument('--pilot-calibration',default=str(RUN/'artifacts/labels/streaming_v1/reduce_mask_v1_cpu_v3/TRAIN_median_MAD_reference.json'))
    p.add_argument('--artifacts-root');p.add_argument('--config');p.add_argument('--output');p.add_argument('--shard-id',type=int,default=0)
    p.add_argument('--shard-manifest',action='append',default=[]);p.add_argument('--authority',default=str(REPO/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json'))
    p.add_argument('--parent-evidence',action='append',default=[]);p.add_argument('--parent-profile');p.add_argument('--root-reviewed',action='store_true');a=p.parse_args()
    if Path(__file__).absolute().parent!=REPO/'workflows/data_v1_final/labels/payload_audit_v1':raise ValueError('ACTUAL_ROOT_HELPER_REQUIRED')
    out=Path(a.output_directory).absolute()
    if RUN not in out.parents or any(x.is_symlink() for x in (out,*out.parents)):raise ValueError('NEW_OWNED_METADATA_DIRECTORY')
    if a.command=='initial' and not a.artifacts_root:raise ValueError('EXPLICIT_NEW_ARTIFACTS_ROOT_REQUIRED')
    if a.command!='initial' and (not a.config or not a.output):raise ValueError('EXPLICIT_STAGE_CONFIG_OUTPUT_REQUIRED')
    if a.output and ((RUN/'artifacts/labels/source_status_v1') not in Path(a.output).parents or Path(a.output).exists()):raise ValueError('NEW_RESOURCE_COMPATIBLE_OUTPUT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    if a.command=='initial':initial(a,out)
    else:stage(a,out)
    print(json.dumps({'status':'METADATA_ONLY_NOT_SUBMITTED','directory':str(out)}))
if __name__=='__main__':main()