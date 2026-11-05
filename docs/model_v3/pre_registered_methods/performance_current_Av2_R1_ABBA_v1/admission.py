"""One fixed current-A-v2 R1 qualification; metadata only, never an SDK/journal reader."""
from __future__ import annotations
import hashlib, importlib.util, json, math, os, re, stat
from pathlib import Path
B=Path('/share/home/zixiao/descriptor_analysis'); N=B/'runs/model_v3_20261026'
W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1'; HERE=Path(__file__).absolute().parent
CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50'; PUBLIC='2b4a4df8636e5d65915d535472ba01084ea72dab'
TREE='8f9530415034bdb885c1c765aee434797c70e7c7'
GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243'; NODE='compute-0-21'
FILES=('Root_submit.py','admission.py','run_R1_ABBA.sbatch','PLAN.json','METHODS.md','dependencies.json','source_pins.json')
PREFIX='docs/model_v3/pre_registered_methods/performance_current_Av2_R1_ABBA_v1/'
META=2<<20
def need(ok,message):
    if not ok: raise ValueError(message)
def canonical(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def reference(path,maximum=META):
    p=Path(path).absolute(); a=p.lstat()
    need(p.resolve()==p and stat.S_ISREG(a.st_mode) and a.st_uid==1278 and a.st_nlink==1
         and 0<a.st_size<=maximum,'Owned canonical bounded metadata/source required: '+str(p))
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(65536),b''): h.update(block)
    z=p.lstat()
    need(all(getattr(a,k)==getattr(z,k) for k in
         ('st_dev','st_ino','st_size','st_mtime_ns','st_uid','st_nlink')),'Input changed while read')
    return dict(path=str(p),bytes=a.st_size,sha256=h.hexdigest())
def read(path):
    before=reference(path)
    value=json.loads(Path(path).read_bytes(),parse_constant=lambda x:(_ for _ in ()).throw(ValueError('Nonfinite JSON')))
    need(reference(path)==before,'Metadata changed while parsed')
    return value
def bound(item,parse=True):
    need(type(item) is dict and set(item)=={'path','bytes','sha256'}
         and type(item['bytes']) is int and item['bytes']>0
         and type(item['sha256']) is str and re.fullmatch('[0-9a-f]{64}',item['sha256'])
         and reference(item['path'],META if parse else 16<<20)==item,'Exact typed rawref differs')
    return read(item['path']) if parse else item
def load_helper(item,name):
    bound(item,False); spec=importlib.util.spec_from_file_location(name,item['path'])
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def verify_package(sha):
    pin=reference(HERE/'source_pins.json');need(pin['sha256']==sha,'Actual package pins SHA required')
    data=read(pin['path'])
    need(data['schema']=='model_v3_current_Av2_R1_ABBA_source_pins_v1'
         and len(data['files'])==len(FILES)-1
         and {Path(r['path']).name for r in data['files']}==set(FILES)-{'source_pins.json'},
         'Exact six authored leaves and separate pins required')
    for item in data['files']:
        need(Path(item['path']).parent==HERE,'Fixed package namespace required');bound(item,False)
    return pin
def verify_method(item):
    pub=bound(item)
    need(pub['schema']=='model_v3_exact_tree_publication_actual_v1' and pub['repository_full_name']=='mint258/MFM'
         and pub['branch']=='model-v3' and pub['public_branch_readback_verified'] is True
         and pub['public_Git_API_tree_readback_verified'] is True,'Actual new method exact-tree publication required')
    table={x['path']:x for x in pub['files']};need(len(table)==len(pub['files']),'Duplicate public paths')
    for name in FILES:
        raw=(HERE/name).read_bytes(); row=table[PREFIX+name]
        need(row['type']=='blob' and row['sha']==hashlib.sha1(
             b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest(),'Method source not exact published blob: '+name)
    return pub
def positive(value,cap):
    return type(value) in (int,float) and math.isfinite(value) and 0<=value<=cap
def validate_numeric(case_spec):
    closed=bound(case_spec['numeric_closure'])
    if case_spec['numeric_schema'] is None:
        need('schema' not in closed,'This exact historical Root closure has no schema alias')
    else: need(closed['schema']==case_spec['numeric_schema'],'Wrong actual numeric closure schema')
    need(closed['status']==case_spec['numeric_status'],'Incomplete actual current A-v2 numeric closure')
    job=case_spec['numeric_job_id']
    if job=='4524712':
        need(closed['GPU_job_id']==job and closed['CPU_job_id']=='4524717'
             and closed['local_code_sha']==CODE and closed['public_prereg_sha']==PUBLIC
             and closed['rule_public_sha']=='4f6ba16973ea4a30472c7fb33d3aadec974a4462'
             and closed['source_current_graph_verified_by_binder_and_CPU'] is True
             and closed['six_closed_rawrefs']==case_spec['numeric_artifacts']
             and positive(closed['maximum_trajectory_loss_relative_difference'],1e-3),'Actual4712/4717 source/v2 numeric binding differs')
        fixed=closed['fixed20']
    else:
        need(job=='4524722' and closed['job_id']==job and closed['actual_code_sha']==CODE
             and closed['original_scientific_prereg_sha']==PUBLIC
             and {r['path']:r for r in closed['closed_metadata']}==
                 {r['path']:r for r in case_spec['numeric_artifacts'].values()}
             and positive(closed['maximum_loss_difference'],1e-3),'Actual4722 source/v2 numeric binding differs')
        fixed=closed['fixed']
    need(fixed['passed'] is True and fixed['batches']==20 and fixed['outputs_each']==8
         and fixed['parameters_each']==329 and fixed['both_disabled_records']==4240
         and positive(fixed['maximum_forward_relative_l2'],1e-5)
         and positive(fixed['maximum_error_to_threshold'],1)
         and positive(fixed['maximum_analytic_zero_norm'],1e-8)
         and closed['trajectory_updates']==500,'Complete current20/all-element-v2/500 Root closure required')
    artifacts=case_spec['numeric_artifacts']
    # The original six references are retained. Large fixed-gate/steps bodies are
    # hashed only; no numeric-gate re-audit or SDK/journal decode happens here.
    for item in artifacts.values():bound(item,False)
    cfg=bound(artifacts['configuration']); summary=bound(artifacts['summary'])
    status=bound(artifacts['run_status']); sup=bound(artifacts['supervisor'])
    need(cfg['job_id']==sup['job_id']==job and cfg['node'].split('.')[0]==NODE
         and cfg['code_sha']==summary['code_sha']==CODE and cfg['prereg_sha']==summary['prereg_sha']==PUBLIC
         and cfg['gpu_uuid']==summary['gpu_uuid']==sup['gpu_uuid']==GPU
         and cfg['acceptance_scope']==summary['acceptance_scope']=='V2_FULL20_AND500'
         and cfg['acceptance_rules']['version']=='v2' and cfg['fixed_batches']==20 and cfg['trajectory_updates']==500,
         'Actual current code/card/full-v2 scope differs')
    need(canonical({k:v for k,v in cfg.items() if k!='configuration_sha256'})==
         cfg['configuration_sha256']==summary['configuration_sha256'],'Numeric configuration canonical identity differs')
    need(summary['status']==status['status']=='PAIRED_GATES_PASS' and summary['full_A_numeric_acceptance'] is True
         and summary['fixed_batch_pass'] is True and summary['trajectory_pass'] is True
         and status['committed_trajectory_updates']==500 and status['trajectory_completed'] is True
         and status['failure'] is None and status['cleanup_errors']==[]
         and status['stream_cleanup']['errors']==[] and status['stream_cleanup']['input_descriptors_closed'] is True,
         'Actual current trainer/SDK-finish/500 cleanup differs')
    need(sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
         and sup['remaining_recorded_processes_before_retirement']==[]
         and sup['private_storage_cleanup_errors']==[] and sup['foreign_gpu_processes_signalled'] is False,
         'Actual numeric supervision/private cleanup not closed')
    options=bound(case_spec['candidate_options'])
    need(cfg['candidate']==options and cfg['candidate_options_sha256']==case_spec['candidate_options']['sha256']
         and all(type(options[k]) is bool and options[k] is v for k,v in case_spec['checkpoint_flags'].items())
         and options['precision']=='fp32' and options['tf32'] is options['fused_adamw'] is options['compile_backbone'] is False,
         'Fixed a00/head-off options differ')
    need(cfg['seed']==0 and cfg['input']=='native_s' and cfg['smoke'] is False
         and cfg['data_version']['loader']['num_workers']==8 and cfg['data_version']['sampler']['max_padded_cost']==8000000
         and cfg['original_shard_snapshot_prejob_sha256']=='d2e1ace1636485cd3dd0106b1177518dd37eb9741919195a9efcd846c1c2242f'
         and cfg['deterministic_controls']['requested'] is True,'Original native input/model control differs')
    execution=cfg['performance_execution']
    need(execution['requested']['checkpoint_policy']=='manual' and execution['requested']['resident_models']==2
         and execution['requested']['capacity_profile'] is None and execution['requested']['padding'] is None
         and execution['resolved_options']==options,'Actual manual paired execution differs')
    # Full current-source validation is delegated to the already-tested source
    # guard below. This additionally forbids relabeling the saved R2 source graph.
    need(execution['implementation_sha256']==cfg['source_sha256'] and len(cfg['source_sha256'])==305,
         'Complete actual R2 mandatory graph must remain present')
    for name,digest in cfg['source_sha256'].items():
        rel=Path(name);need(not rel.is_absolute() and '..' not in rel.parts and rel.suffix=='.py'
                           and reference(W/rel)['sha256']==digest,'R2/current mandatory source differs')
    return cfg
def validate_sdk(case_spec,item):
    proof=bound(item)
    need(proof['schema']==case_spec['SDK_schema']
         and proof['status']=='ACTUAL_C0_FULL_NATIVE_LOG_MATCH_AND_SELECTIVE_SYNC_CLOSED'
         and proof['GPU_job_id']==case_spec['numeric_job_id']
         and proof['numeric_Root_closure']==case_spec['numeric_closure']
         and proof['full_native_config_summary_history_matched'] is True
         and proof['official_selective_sync_and_cloud_readback_verified'] is True
         and proof['original_SDKs_retained'] is True
         and proof['history_rows_each']==500 and proof['first_step']==1 and proof['last_step']==500,
         'Actual fixed-job full SDK audit/sync/cloud-readback closure required; missing means HOLD')
    roles=proof['run_roles']
    need(type(roles) is dict and set(roles)==set(case_spec['SDK_run_ids'])
         and sorted(roles.values())==['candidate','reference'],'Actual two run/role identities required')
    if case_spec['SDK_known_role_map'] is not None:
        need(roles==case_spec['SDK_known_role_map'],'Actual known A00 role mapping differs')
    need(len(proof['verifications'])==len(proof['sync_run_results'])==len(proof['CPU_supervisors'])==2,
         'Both audited and synced original runs required')
    bound(proof['audit']);bound(proof['sync'])
    seen={}
    for item in proof['verifications']:
        v=bound(item);h=v['history'];rid=v['run_id']
        need(v['schema']=='performance_R2_paired_log_verification_v1'
             and v['status']=='ALL_SAVED_PAIRED_LOG_FIELDS_MATCHED'
             and v['model_job_id']==case_spec['numeric_job_id']
             and rid in roles and rid not in seen and v['paired_role']==roles[rid]
             and v['full_config_summary_typed_exact'] is True and v['raw_before_after_binding_closed'] is True
             and h['schema']=='model_v3_native_mirror_verification_v7'
             and h['status']=='VERIFIED_COMMITTED_HISTORY' and h['history_rows']==500
             and h['first_explicit_step']==1 and h['last_explicit_step']==500
             and h['clean_eof'] is h['native_closed'] is True and h['decode_error'] is None
             and type(h['uncommitted_native_requests']) is int and h['uncommitted_native_requests']==0
             and h['sdk_exit_codes']==[0] and h['sdk_run_ids']==[rid],
             'Actual full-config/summary/500-row native verification differs')
        seen[rid]=roles[rid]
    need(seen==roles,'Both actual SDK roles must be independently verified')
    synced=set()
    for item in proof['sync_run_results']:
        v=bound(item);remote=v['actual_remote_metadata'];rid=v['run_id']
        need(v['schema']=='model_v3_one_WandB_sync_readback_v1'
             and v['status']=='SOURCE_AND_REMOTE_METADATA_VERIFIED' and v['failure'] is None
             and v['native_exit_code']==0 and v['source_hash_before_after_equal'] is True
             and v['original_SDK_repaired_or_deleted'] is False
             and remote==v['expected_remote_metadata'] and rid in roles and rid not in synced
             and remote['run_id']==rid and remote['state']=='finished'
             and remote['history_rows']==500 and remote['first_step']==1 and remote['last_step']==500,
             'Actual selective sync and official remote readback differs')
        synced.add(rid)
    need(synced==set(roles),'Both actual original runs must be synced/read back')
    for item in proof['CPU_supervisors']:
        s=bound(item)
        need(s['status']=='COMPLETED' and s['exit_code']==0 and s['first_failure'] is None
             and s['remaining']==[] and s['private_storage']['first_sampling_failure'] is None
             and s['private_storage']['budget_bytes']==2147483648,
             'Actual SDK CPU supervision/cleanup must be closed')
    raw=proof['actual_sacct'];need(raw['returncode']==0 and raw['stderr']=='','Actual SDK parent accounting required')
    expected={proof['GPU_job_id'],proof['audit_CPU_job_id'],proof['sync_CPU_job_id']}
    rows=[r.split('|') for r in raw['stdout'].splitlines() if r.strip()]
    need(len(rows)==len(expected)==3 and {r[0] for r in rows}==expected and all(
         len(r)==7 and r[1:4]==['zixiao','COMPLETED','0:0'] and r[4].isdigit() and r[5]=='16' for r in rows),
         'Actual GPU/audit/sync three owned16CPU C0 parents required')
    return proof
def qualify(case_name,sdk_ref):
    plan=read(HERE/'PLAN.json');need(case_name in ('a00_manual','head_off'),'Only two fixed current-source cases')
    case_spec=plan['cases'][case_name]
    d=read(HERE/'dependencies.json')
    for item in d['raw_refs'].values():bound(item,False)
    bound(case_spec['source_guard_dependencies'],False)
    guard=load_helper(case_spec['source_guard'],'current_R1_original_'+case_name+'_source_guard')
    guard.validate_sources()
    cfg=validate_numeric(case_spec)
    need(case_spec['SDK_closure'] is None or sdk_ref==case_spec['SDK_closure'],'Use the exact actual A00 SDK closure')
    sdk=validate_sdk(case_spec,sdk_ref)
    return dict(case=case_spec,configuration=cfg,SDK=sdk)
def registry_lock(path):
    d=read(HERE/'dependencies.json');bound(d['raw_refs']['registry_delegate_dependencies'],False)
    helper=load_helper(d['raw_refs']['registry_delegate'],'current_R1_original_registry_delegate')
    return helper.registry_lock(path)
