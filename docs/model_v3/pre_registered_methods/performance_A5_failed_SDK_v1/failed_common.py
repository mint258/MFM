"""Two explicit failed A5 SDKs; original v3 bounded primitives/transport only."""
from __future__ import annotations
import contextlib
import importlib.util
import sys
from pathlib import Path
HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
import sync_common as base
from sync_common import *
HERE=Path(__file__).absolute().parent
SCOPE='A5_FIXED20_FAILED_ZERO_HISTORY_LOG_ONLY'
JOB='4524601'
IDS=('89mp3smr','9j1swwgi')
CHILD=HERE.parent/'performance_A5_R2_v1'/'child'
CODE='9e16d4c5a15c558051499d3dc0c55c9bd3787734'


def load(raw,name):
    bind(raw);spec=importlib.util.spec_from_file_location(name,raw['path'])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def descriptor(path,cap):
    path=Path(path).absolute();before=path.lstat()
    require(not any(p.is_symlink() for p in (path,*path.parents)) and stat.S_ISREG(before.st_mode)
        and before.st_uid==1278 and before.st_nlink==1 and 0<before.st_size<=cap,
        'Bounded owned ordinary descriptor required')
    return dict(path=str(path),bytes=before.st_size)


def verify(expected=None):
    pin=ref(HERE/'source_pins.json')
    if expected is not None:require(pin['sha256']==expected,'Explicit failed-log source SHA differs')
    pins=read(pin);require(pins['schema']=='A5_failed_log_sources_v1','Exact failed-log source family required')
    for item in pins['files']:
        actual=ref(HERE/item['relative_path'])
        require((actual['bytes'],actual['sha256'])==(item['bytes'],item['sha256']),'Failed-log source drift')
    deps=read(HERE/'dependencies.json')
    for raw in deps['sources'].values():bind(raw)
    require(base.verify(deps['base_manifest']['sha256'])==deps['base_manifest'],'Original v3 source drift')
    wanted=(V3/'one_run.py').read_bytes().replace(b'from sync_common import *',b'from failed_common import *')
    require((HERE/'one_run_failed.py').read_bytes()==wanted,'Only eligibility import may differ in original transport')
    require((HERE/'installed_sources.json').read_bytes()==(V3/'installed_sources.json').read_bytes(),
        'Installed source snapshot differs')
    return pin


def model_terminal(raw):
    argv=['sacct','-X','-n','-P','-j',JOB,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
    rows=[line.split('|') for line in raw['stdout'].splitlines() if line.strip()]
    require(raw['argv']==argv and raw['returncode']==0 and raw['stderr']==''
        and rows==[[JOB,'zixiao','FAILED','1:0','127','16','compute-0-21']],
        'Exact actual failed model parent required; this is not model C0')


def metadata_inputs(value):
    scope=read(HERE/'scope.json')
    require(value['schema']=='A5_failed_log_inputs_v1' and value['scope']==SCOPE
        and value['model_job_id']==JOB and value['root_closure']==scope['root_closure']
        and type(value['expected_history_rows']) is int and value['expected_history_rows']==0
        and type(value['expected_native_exit']) is int and value['expected_native_exit']==1
        and value['expected_summary_file'] is None,
        'One exact failed A5 model source required')
    root=read(value['root_closure']);model_terminal(root['actual_sacct'])
    require(root['schema']=='model_v3_Root_A5_R2_fixed20_gradient_failure_closure_v1'
        and root['status']=='ACTUAL_FAILED1_ALL20_FORWARD_PASS_120_ZERO_BIAS_RELATIVE_GRADIENT_FAILURES_SOURCE_RESOURCE_CLOSED'
        and root['job_id']==JOB and root['actual_scientific_child_exit_code']==2
        and root['all_current_2131_source_refs_equal'] is True and root['all20_forward_pass'] is True
        and root['fixed_batches']==20 and len(root['failed_gradient_records'])==120
        and root['fixed_gate_satisfied'] is False and root['trajectory500_started'] is False
        and root['R1_started'] is False and root['NVML_used_memory_all_known'] is True
        and root['private_sampling_cleanup_closed'] is True and root['scientific_adoption'] is False,
        'Original negative source/resource/unchanged gate closure differs')
    names=('configuration','run_status','supervisor','submission','source_package','method_publication')
    require(set(value['refs'])==set(names) and all(value['refs'][k]==root[k] for k in names),
        'Actual negative metadata reference membership differs')
    metadata={k:read(value['refs'][k]) for k in names}
    c,r,sup=(metadata[k] for k in ('configuration','run_status','supervisor'))
    require(value['refs']['configuration']['path']==str(CHILD/'configuration.json') and c['job_id']==JOB
        and c['code_sha']==CODE and c['tracking_mode']=='offline' and c['input']=='native_s'
        and type(c['seed']) is int and c['seed']==0 and c['smoke'] is False
        and c['fixed_batches']==20 and c['trajectory_updates']==500
        and c['performance_execution']['requested']['checkpoint_policy']=='manual'
        and c['performance_execution']['requested']['resident_models']==2
        and c['performance_execution']['requested']['padding']==dict(mode='logical_batch_chunks_v1',
            atom_bucket_width=16,max_graphs_per_chunk=32,max_padded_cost_per_chunk=1000000)
        and c['candidate']['distance_checkpointing'] is True and c['candidate']['backbone_checkpointing'] is True
        and c['candidate']['head_checkpointing'] is True,'Original full A5 config differs')
    digest=hashlib.sha256(json.dumps({k:v for k,v in c.items() if k!='configuration_sha256'},
        sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(digest==c['configuration_sha256'],'Original configuration canonical hash differs')
    require(r['job_id']==JOB and r['status']=='FIXED_BATCH_GATE_FAILED' and r['failure'] is None
        and r['cleanup_errors']==[] and r['stream_cleanup']==dict(input_descriptors_closed=True,errors=[])
        and r['checkpoint_export'] is None and r['resume_supported'] is False,
        'Actual child2 fixed-gate failure/cleanup differs')
    require(sup['job_id']==JOB and sup['status']=='FAILED' and type(sup['exit_code']) is int and sup['exit_code']==2
        and sup['first_failure']==dict(phase='child_exit',exit_code=2)
        and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
        and sup['foreign_gpu_processes_signalled'] is False,'Actual failed supervisor closure differs')
    forbidden=('summary.json','trajectory_gate.json','reference_history.jsonl','candidate_history.jsonl','SDK_expected_summary.json')
    require(all(not (CHILD/name).exists() and not (CHILD/name).is_symlink() for name in forbidden),
        'Failure-path source has no saved summary or trajectory journal; do not invent one')
    expected=[dict(run_id=row['run_id'],descriptor={k:row[k] for k in ('path','bytes')})
        for row in root['SDK_descriptors_stat_only']]
    require(value['sdks']==scope['sdks']==expected and len(expected)==2
        and tuple(row['run_id'] for row in expected)==IDS,'Both explicit original SDK descriptors required')
    for row in expected:
        sdk=row['descriptor'];path=Path(sdk['path']);key=row['run_id']
        require(descriptor(path,128<<20)==sdk and path.name=='run-'+key+'.wandb'
            and path.parent.parent==CHILD/'wandb' and path.parent.name.startswith('offline-run-')
            and path.parent.name.endswith('-'+key),'Exact original failed offline SDK differs')
    gate=root['fixed_batch_gate']
    require(root['fixed_gate_metadata_cap_bytes']==4<<20 and gate['path']==str(CHILD/'fixed_batch_gate.json')
        and descriptor(gate['path'],4<<20)=={k:gate[k] for k in ('path','bytes')},
        'Original fixed gate metadata descriptor differs')
    metadata['Root_negative']=root
    return metadata


def bound_inputs(raw):
    value=read(raw);metadata_inputs(value)
    require(sum(row['descriptor']['bytes'] for row in value['sdks'])+value['root_closure']['bytes']
        +sum(row['bytes'] for row in value['refs'].values())<=256<<20,'Explicit failed-log input envelope exceeded')
    return value


def header_check(header,role):
    require(role in ('reference','candidate') and set(header)=={'run_id','display_name','project','entity'}
        and header['run_id'] in IDS and header['display_name']=='A_'+role+'_'+JOB
        and header['project']=='mfm_model_v3_development' and type(header['entity']) is str,
        'Actual failed paired RunRecord ID/name/project/role differs')


def proof_rows(manifest):
    require(manifest['schema']=='A5_failed_sync_manifest_v1' and len(manifest['verifications'])==2,
        'Both independently audited failed SDKs required')
    batch=read(manifest['audit_result']);sup=read(manifest['audit_supervisor'])
    terminal=terminal_C0(manifest['actual_audit_C0']);job=terminal['job_id']
    require(batch['schema']=='A5_failed_log_audit_result_v1'
        and batch['status']=='BOTH_FAILED_ZERO_HISTORY_LOGS_MATCHED_PENDING_ACTUAL_CPU_C0'
        and batch['actual_job_id']==job==str(sup['job_id']) and batch['returncode']==0 and batch['failure'] is None
        and batch['verifications']==manifest['verifications'] and batch['source_pins']==ref(HERE/'source_pins.json')
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining']==[] and sup['private_storage']['first_sampling_failure'] is None
        and sup['command']==batch['actual_argv'],'Actual audit CPU C0/source/supervisor required')
    expected=[str(PYTHON),'-u','-B',str(HERE/'audit_failed.py'),'--inputs',batch['inputs']['path'],
        '--inputs-sha256',batch['inputs']['sha256'],'--pins-sha256',batch['source_pins']['sha256'],
        '--output',str(Path(manifest['audit_result']['path']).parent)]
    require(batch['actual_argv']==expected and batch['actual_allocation']['uid']==1278,'Actual CPU audit argv/UID differs')
    inputs=bound_inputs(batch['inputs']);deps=read(HERE/'dependencies.json');rows=[];roles=set()
    require(batch['fixed_gate_raw_binding']==read(inputs['root_closure'])['fixed_batch_gate']
        and batch['fixed_gate_numerical_recomputation'] is False,'Original gate raw-hash scope differs')
    descriptors={row['run_id']:row['descriptor'] for row in inputs['sdks']}
    for raw in manifest['verifications']:
        cert=read(raw);key=cert['run_id'];role=cert['paired_role'];h=cert['history'];header_check(cert['native_RunRecord'],role)
        require(cert['schema']=='A5_failed_zero_history_verification_v1' and cert['scope']==SCOPE
            and cert['status']=='FULL_CONFIG_ZERO_HISTORY_FAILED_EXIT_AND_SOURCE_SUMMARY_RULE_MATCHED'
            and cert['model_job_id']==JOB and cert['source_pins']==batch['source_pins'] and cert['inputs']==batch['inputs']
            and cert['full_config_typed_exact'] is True and cert['source_summary_rule_exact'] is True
            and cert['raw_before_after_binding_closed'] is True and cert['native_RunRecord']['run_id']==key
            and role not in roles and key not in {row['run_id'] for row in rows},'Exact separate failed-run certificate required')
        require(cert['history_reader_source']==deps['sources']['literal_reader'] and cert['tap_source']==deps['sources']['tap']
            and h['schema']=='model_v3_native_mirror_verification_v7' and h['status']=='VERIFIED_COMMITTED_HISTORY'
            and h['sdk_run_ids']==[key] and h['sdk_exit_codes']==[1] and type(h['sdk_exit_codes'][0]) is int
            and h['clean_eof'] is True and h['native_closed'] is True and h['decode_error'] is None
            and type(h['uncommitted_native_requests']) is int and h['uncommitted_native_requests']==0
            and type(h['history_rows']) is int and h['history_rows']==0
            and h['first_explicit_step'] is None and h['last_explicit_step'] is None
            and h['paired_role']==role,'No history, exact exit1/full-fragment EOF and actual role required')
        require({k:cert['sdk'][k] for k in ('path','bytes')}==descriptors[key]
            and cert['summary_observation']['scientific_summary_leaf_count']==0
            and cert['summary_observation']['source_summary_file'] is None,'Original zero-summary source policy differs')
        for source in cert['source_refs'].values():bind(source)
        roles.add(role);rows.append(dict(run_id=key,paired_role=role,SDK_raw_ref=cert['sdk'],
            native_RunRecord=cert['native_RunRecord'],native_exit_code=1,expected_API_state='failed',
            history_rows=0,first_explicit_step=None,last_explicit_step=None,model_job_id=JOB,verification=raw,scope=SCOPE))
    require(set(row['run_id'] for row in rows)==set(IDS) and roles=={'reference','candidate'},
        'Both exact IDs and distinct actual native roles required')
    return rows


def manifest_metadata():
    raw=ref(os.environ['MODEL_V3_A5_FAILED_MANIFEST'])
    require(raw['sha256']==os.environ['MODEL_V3_A5_FAILED_MANIFEST_SHA'],'Explicit failed-pair manifest drift')
    value=read(raw);require(value['runs']==proof_rows(value),'Proof-derived eligible failed rows differ')
    return raw,value


def eligible_rows():
    allocation();_,manifest=manifest_metadata();rows=proof_rows(manifest);entity_default=None
    if any(not row['native_RunRecord']['entity'] for row in rows):
        private=Path(os.environ['TMPDIR'])/('A5_failed_authenticated_route_'+str(os.getpid()));private.mkdir(mode=0o700)
        with (private/'stdout').open('x') as out,(private/'stderr').open('x') as err,contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            for item in read(HERE/'installed_sources.json')['files']:
                current=ref(item['original']);require((current['bytes'],current['sha256'])==(item['bytes'],item['sha256']),'Installed API drift')
            import wandb
            require(wandb.__version__=='0.28.1','Reviewed SDK0.28.1 required');api=wandb.Api(timeout=30)
            require(api.settings['base_url']=='https://api.wandb.ai','Actual destination differs')
            entity_default=api.viewer.entity
            require(type(entity_default) is str and entity_default and api.default_entity==entity_default,'Actual authenticated route missing')
    for row in rows:
        h=row['native_RunRecord'];row['routing']=dict(entity=h['entity'] or entity_default,project=h['project'],run_id=row['run_id'],
            routing_ready=True,entity_origin='original_RunRecord' if h['entity'] else 'actual_authenticated_viewer_default',project_origin='original_RunRecord')
    return manifest,{row['run_id']:row for row in rows}


def request_gate(request):
    raw,manifest=manifest_metadata();proof_rows(manifest)
    require(request['schema']=='A5_failed_selective_sync_request_v1' and request['selected_run_ids']==list(IDS)
        and request['eligible_manifest']==raw and request['source_manifest']==ref(HERE/'source_pins.json')
        and request['mode']=='batch' and request['maximum_batch_runs']==3 and request['child_seconds']==3000
        and request['CLI_timeout_seconds']==600 and request['API_verification_seconds']==180,
        'Only the two certified failed SDKs with original finite transport budgets are admitted')
    gate=request['pilot_gate'];terminal=terminal_C0(gate['actual_terminal']);pilot=read(gate['result']);sup=read(gate['supervisor'])
    require(terminal['job_id']==str(pilot['job_id'])==str(sup['job_id'])=='4521412'
        and pilot['source_manifest']==ref(V3/'source_pins.json') and pilot['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0'
        and len(pilot['records'])==1 and pilot['records'][0]['native_exit_code']==1
        and pilot['records'][0]['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED'
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and sup['remaining']==[]
        and gate['native_exit_code']==1 and gate['actual_replay_verified'] is True,'Original actual failed-exit v3 method gate required')
