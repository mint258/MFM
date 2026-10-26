"""Pure stdlib resource rebinding: old science config stays byte-identical."""
from __future__ import annotations
import argparse, copy, json, re
from pathlib import Path
from .support import RUN, TASKS, load, need, save, small_ref
ROOT=RUN/'repository'
OLD='workflows.data_v1_final.labels.source_status_v1.'
NEW='workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.'
AUTO='workflows/data_v1_final/execution/cpu_auto_memory_queue_v2'
POLICY='SLURM_DEFAULT_UNSPECIFIED'

def option(argv,name):
    need(argv.count(name)==1,'ONE_EXPLICIT_OPTION_REQUIRED:'+name);i=argv.index(name)
    need(i+1<len(argv),'OPTION_VALUE_REQUIRED');return argv[i+1]

def replace_option(argv,name,value):
    option(argv,name);result=list(argv);result[result.index(name)+1]=value;return result

def inherit_sources(legacy):
    refs={}
    for pin in legacy['source_references']:
        actual=small_ref(pin['path']);need(actual==pin,'HISTORICAL_SMALL_PIN_CHANGED:'+pin['path']);refs[pin['path']]=pin
    return refs

def rebind(legacy,new_output):
    need(legacy['kind']=='analysis' and legacy['pilot'] is False,'EXACT_SOURCE_ANALYSIS_SCOPE_REQUIRED')
    argv=list(legacy['execution_argv']);need(argv.count('-m')==1,'MODULE_ENTRY_REQUIRED')
    pos=argv.index('-m')+1;module=argv[pos]
    need(module.startswith(OLD) and module[len(OLD):] in ('prepare','scan','reduce'),'OLD_SOURCE_STATUS_ENTRY_REQUIRED')
    stage=module[len(OLD):];config=Path(option(argv,'--config'))
    argv[pos]=NEW+stage;argv=replace_option(argv,'--output',str(new_output))
    argv=replace_option(argv,'--startup-proof','__ROOT_STARTUP_PROOF__')
    # Invert precisely the three execution-only edits, including the literal old proof.
    inverse=list(argv);inverse[pos]=module
    inverse=replace_option(inverse,'--output',option(legacy['execution_argv'],'--output'))
    inverse=replace_option(inverse,'--startup-proof',option(legacy['execution_argv'],'--startup-proof'))
    need(inverse==legacy['execution_argv'],'SCIENCE_ARGV_CHANGED')
    return stage,config,argv

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('legacy-input','new-output','output-directory','equivalence-proof','root-review-reason'):
        p.add_argument('--'+name,required=True)
    p.add_argument('--authority',default=str(ROOT/'configs/data_v1/user_cpu_auto_memory_20261026_v1.json'))
    p.add_argument('--parent-evidence',action='append',required=True)
    p.add_argument('--parent-profile');p.add_argument('--root-reviewed',action='store_true',required=True)
    a=p.parse_args();need(a.root_review_reason.strip(),'EXPLICIT_ROOT_REVIEW_REASON_REQUIRED')
    need(Path(__file__).absolute().parent==ROOT/'workflows/data_v1_final/labels/source_status_cpu_auto_memory_v1','ACTUAL_ROOT_INTEGRATED_HELPER_REQUIRED')
    legacy_ref=small_ref(a.legacy_input);legacy=load(a.legacy_input);refs=inherit_sources(legacy)
    output=Path(a.new_output).absolute();allowed=RUN/'artifacts/labels/source_status_v1'
    need(allowed in output.parents and 'auto_memory' in str(output.relative_to(allowed)) and not output.exists(),'FRESH_AUTO_MEMORY_OUTPUT_TAG_REQUIRED')
    stage,config,argv=rebind(legacy,output);cfg=load(config);config_ref=small_ref(config)
    need(refs.get(str(config))==config_ref,'ORIGINAL_SCIENTIFIC_CONFIG_NOT_AUTHORIZED')
    need(config_ref==small_ref(config),'SCIENTIFIC_CONFIG_CHANGED_DURING_READ')
    proof_ref=small_ref(a.equivalence_proof);proof=load(a.equivalence_proof)
    need(proof['schema']=='SOURCE_STATUS_CPU_AUTO_MEMORY_EQUIVALENCE_V1' and proof['status']=='PASS','ACTUAL_INVERSE_PROOF_REQUIRED')
    old_sources=[x['old'] for x in proof['sources']]
    for pin in old_sources:need(refs.get(pin['path'])==pin,'OLD_ACTUAL_SOURCE_PROOF_NOT_AUTHORIZED')
    authority=small_ref(a.authority);authority_body=load(a.authority)
    need(authority_body['schema']=='USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1' and authority_body['status']=='USER_AUTHORIZED' and authority_body['memory_policy']==POLICY,'NEW_REAL_RESOURCE_AUTHORITY_REQUIRED')
    new_sources=[small_ref(path) for path in Path(__file__).parent.glob('*.py')]
    for item in proof['sources']:
        need(item['new'] in new_sources and small_ref(item['new']['path'])==item['new'],'ACTUAL_NEW_SOURCE_PROOF_DIFFERS')
    central=[small_ref(path) for path in (ROOT/AUTO).glob('*.py')]
    need(any(Path(pin['path']).name=='runtime.py' for pin in central),'INTEGRATED_V2_RUNTIME_REQUIRED_NO_V1_FALLBACK')
    parents=[small_ref(path) for path in a.parent_evidence]
    profile=small_ref(a.parent_profile) if a.parent_profile else None
    if profile is not None and profile not in parents:parents.append(profile)
    out=Path(a.output_directory).absolute()
    need(RUN in out.parents and not out.exists() and not any(x.is_symlink() for x in (out,*out.parents)),'NEW_EXTERNAL_METADATA_DIRECTORY_REQUIRED')
    out.mkdir(parents=True,mode=0o700)
    cap=cfg[stage+'_output_cap_bytes'];parameters=copy.deepcopy(legacy.get('scope_parameters',{}))
    if not parameters:
        roles=load(cfg['metadata']['roles']['path'])
        parameters={'input_records':sum(v['records'] for v in roles['roles'].values()),'input_molecules':sum(v['molecules'] for v in roles['roles'].values()),
            'roles':list(roles['roles']),'task_slots':len(TASKS),'shards_planned':cfg['shards'],'new_masks':False,'labels_modified':False,'final_common_population':False}
        if stage=='scan':parameters['shard_id']=int(option(argv,'--shard-id'))
    scope_key='source_status_auto_memory_'+stage
    if stage=='scan':scope_key+='_shard_'+str(int(option(argv,'--shard-id'))).zfill(2)
    mode='BOUNDED_METADATA_PREPARATION' if stage=='prepare' else 'FULL_SOURCE_AFTER_PROFILE' if profile is not None else 'BOUNDED_PERFORMANCE_BATCH'
    need(stage!='reduce' or profile is not None,'FULL_REDUCER_REQUIRES_REVIEWED_ACTUAL_PROFILE')
    binding={'schema':'SOURCE_STATUS_CPU_AUTO_MEMORY_BINDING_V1','resource_authority_reference':authority,
      'scientific_config_reference':config_ref,'scientific_config_bytes_modified':False,'legacy_input_reference':legacy_ref,
      'old_source_references':old_sources,'new_source_references':new_sources,'equivalence_proof_reference':proof_ref,
      'scope_key':scope_key,'scope_parameters':parameters,'stage_output_cap_bytes':cap,
      'software_limits_not_slurm_memory_request':{'duckdb_bytes':12<<30,'duckdb_spill_bytes':8<<30,
         'scan_worker_rss_bytes':cfg['worker_rss_stop_bytes'],'scan_worker_count':cfg['workers'],'batch_records':cfg['batch_records']},
      'memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20,
      'scientific_whole_phase_output_cap_bytes':cfg['prepare_output_cap_bytes']+cfg['shards']*cfg['scan_output_cap_bytes']+cfg['reduce_output_cap_bytes'],
      'resource_phase_additional_peak_bytes':(cfg['shards']+2)*(128<<20),
      'resource_evidence_output':str(output.with_name(output.name+'_resource_observation')),
      'slurm_memory_requested':False,'declared_memory_fraction_admission':False,'exclusive_requested':False,
      'floor_is_startup_or_submission_admission':False,'forced_signals_sent':False,'natural_inflight_drain':True}
    binding_ref=save(out/'resource_binding.json',binding)
    for pin in (legacy_ref,config_ref,authority,proof_ref,binding_ref,*new_sources,*central,*parents):
        need(pin['path'] not in refs or refs[pin['path']]==pin,'CONFLICTING_SMALL_PIN');refs[pin['path']]=pin
    estimated=cfg['prepare_output_cap_bytes']+cfg['shards']*cfg['scan_output_cap_bytes']+cfg['reduce_output_cap_bytes']+(cfg['shards']+2)*(128<<20)
    # Original dataset and scientific knobs remain exactly inherited; only scheduler/evidence envelope changes.
    review={'schema':'EXACT_CPU_AUTO_MEMORY_SCOPE_ROOT_REVIEW_V1','status':'APPROVED_FOR_EXACT_STAGE','reviewer':'root',
      'resource_authority_reference':authority,'kind':'analysis','scope_key':scope_key,'scope_parameters':parameters,
      'scope_mode':mode,'pilot':False,'wall_seconds':legacy['wall_seconds'],'estimated_peak_output_bytes':estimated,
      'execution_argv':argv,'source_status_stage':stage,'stage_output_cap_bytes':cap,'parent_evidence_references':parents,
      'root_review_reason':a.root_review_reason,'bounded_batch_limits_reviewed':mode=='BOUNDED_PERFORMANCE_BATCH',
      'profile_reviewed':profile is not None,'approved_profile_reference':profile}
    review_ref=save(out/'scope_review.json',review);refs[review_ref['path']]=review_ref
    spec={'schema':'ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1','kind':'analysis','pilot':False,'cpus':16,
      'memory_policy':POLICY,'wall_seconds':legacy['wall_seconds'],'estimated_peak_output_bytes':estimated,
      'stage_output_cap_bytes':cap,'execution_argv':argv,'source_references':list(refs.values()),
      'data_references':copy.deepcopy(legacy.get('data_references',[])),
      'deferred_authority_references':copy.deepcopy(legacy.get('deferred_authority_references',[])),
      'scope_key':scope_key,'scope_parameters':parameters,'scope':{'mode':mode,'review':review_ref,'parent_profile':profile},
      'source_status_stage':stage,'producer_resource_binding_reference':binding_ref}
    spec_ref=save(out/'stage_spec.json',spec)
    save(out/'materialization_receipt.json',{'status':'RESOURCE_METADATA_ONLY_NOT_SUBMITTED','new_spec':spec_ref,
      'resource_binding':binding_ref,'old_scientific_config':config_ref,'science_config_copied_or_modified':False,
      'exact_data_locators_inherited':True,'execution_edits_only':['module_namespace','new_output','fresh_startup_proof'],
      'large_scientific_data_read_or_stat':False,'science_imports':False,'Slurm_calls':False})
    print(json.dumps({'status':'NEW_RESOURCE_SPEC_MATERIALIZED_NOT_SUBMITTED','spec':spec_ref}))
if __name__=='__main__':main()