"""Two explicit failed A5 SDKs; original v3 bounded primitives/transport only."""
from __future__ import annotations
import contextlib
import importlib.util
import math
import sys
from pathlib import Path
HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
import sync_common as base
from sync_common import *
HERE=Path(__file__).absolute().parent
SCOPE='A5_V2_FIXED20_FAILED_ZERO_HISTORY_LOG_ONLY'
JOB='4524704'
IDS=('n7wb3txh','0dtrjv10')
CHILD=HERE.parent/'performance_A5_R2_v2'/'child'
CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50'


def allocation():
    # Explicit local adapter, not a monkeypatch of sync_common/base globals.
    # Original job/16CPU/CUDA/node/cgroup gates remain; only fixed MEM=16384
    # is removed. Scheduler memory defaults are observed, never fabricated.
    job=os.environ.get('SLURM_JOB_ID','');node=os.environ.get('MODEL_V3_EXPECTED_NODE','')
    require(job.isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16
        and os.environ.get('CUDA_VISIBLE_DEVICES')==''
        and socket.gethostname()==node and re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])',node),
        'Actual owned CPU16 allocation/node with CUDA hidden required')
    group=Path('/proc/self/cgroup').read_text()
    require(re.search(r'(?:job[_/-])'+re.escape(job)+r'(?:/|\n|$)',group),'Actual own job cgroup required')
    require(os.getuid()==os.geteuid()==1278,'Actual owned UID1278 required')
    pid=os.getpid();raw_stat=Path('/proc/self/stat').read_text();tail=raw_stat.rsplit(')',1)[1].split()
    start_ticks=int(tail[19]);pgid=os.getpgid(pid);sid=os.getsid(pid)
    boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    argv=[part.decode('utf-8') for part in Path('/proc/self/cmdline').read_bytes().split(b'\0') if part]
    require(int(raw_stat.split(' ',1)[0])==pid and start_ticks>0
        and int(tail[2])==pgid and int(tail[3])==sid and argv==list(sys.orig_argv)
        and re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',boot_id),
        'Actual PID/start_ticks/boot/PGID/SID/argv identity differs')
    private=Path(os.environ['TMPDIR'])
    require(private.is_absolute() and not any(path.is_symlink() for path in (private,*private.parents))
        and stat.S_ISDIR(private.stat().st_mode) and private.stat().st_uid==1278,
        'Original supervisor-owned ordinary private root required')
    return dict(job_id=job,node=node,uid=os.getuid(),cgroup=group,pid=pid,start_ticks=start_ticks,
        boot_id=boot_id,pgid=pgid,sid=sid,argv=argv,private_root=str(private),
        scheduler_memory_environment={key:os.environ.get(key) for key in
            ('SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU','SLURM_MEM_PER_GPU')},
        software_working_memory_budget_bytes=16<<30,scheduler_reserved_memory_bytes_claimed=None,
        resource_policy='AUTOMATIC_SCHEDULER_MEMORY_ACTUAL_ENV_RECORDED_OR_NULL',
        original_supervisor_RSS_whole_private_identity_guards_unchanged=True)

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
    pins=read(pin);require(pins['schema']=='A5_failed_log_sources_v3','Exact failed-log source family required')
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
        and rows==[[JOB,'zixiao','FAILED','1:0','133','16','compute-0-21']],
        'Exact actual failed model parent required; this is not model C0')


def negative_refs(root):
    """Actual v2 Root structure: three nested artifacts, three top-level JSON refs."""
    return {**{key:root['artifact_refs'][key] for key in ('configuration','run_status','supervisor')},
        'submission':root['submission'],'source_package':root['source_package'],
        'method_publication':root['operations_publication']}


def metadata_inputs(value):
    scope=read(HERE/'scope.json')
    require(value['schema']=='A5_failed_log_inputs_v2' and value['scope']==SCOPE
        and value['model_job_id']==JOB and value['root_closure']==scope['root_closure']
        and type(value['expected_history_rows']) is int and value['expected_history_rows']==0
        and type(value['expected_native_exit']) is int and value['expected_native_exit']==1
        and value['expected_summary_file'] is None,
        'One exact failed A5-v2 model source required')
    root=read(value['root_closure']);model_terminal(root['actual_sacct'])
    require(root['schema']=='model_v3_A5_R2_v2_posthoc_Root_metadata_closure_v2'
        and root['status']=='ACTUAL_TERMINAL_A5_V2_NUMERIC_NEGATIVE_PRESERVED'
        and root['job_id']==JOB and root['full_A_numeric_acceptance'] is False
        and root['trajectory500_passed'] is False and root['summary'] is None and root['trajectory_gate'] is None
        and root['resident_models']==2 and root['original_manual_policy'] is True
        and root['posthoc_metadata_adaptation']['fixed_batch_index_base']==0
        and root['posthoc_metadata_adaptation']['resource_fixed_batch_index_base']==0
        and root['posthoc_metadata_adaptation']['trajectory_index_base']==1
        and root['posthoc_metadata_adaptation']['model_rule_parameter_or_GPU_execution_changed'] is False
        and root['posthoc_metadata_adaptation']['original_rejection_retained'] is True
        and root['SDK_payload_read_or_independent_audit_claimed'] is False,
        'Exact retained v2 posthoc negative source required; no model or trajectory acceptance')
    fixed=root['fixed20'];resources=root['resources']
    require(fixed['batches']==20 and fixed['outputs_each']==8 and fixed['parameters_each']==329
        and fixed['passed'] is False and resources['rows']==resources['fixed_batches']==20
        and resources['trajectory_updates']==0
        and type(fixed['maximum_forward_relative_l2']) in (int,float)
        and math.isfinite(fixed['maximum_forward_relative_l2']) and 0<=fixed['maximum_forward_relative_l2']<=1e-5
        and type(fixed['maximum_analytic_zero_norm']) in (int,float)
        and math.isfinite(fixed['maximum_analytic_zero_norm']) and 0<=fixed['maximum_analytic_zero_norm']<=1e-8
        and type(fixed['maximum_error_to_threshold']) in (int,float)
        and math.isfinite(fixed['maximum_error_to_threshold']) and fixed['maximum_error_to_threshold']>1,
        'Actual complete fixed20 forward/zero-pass and elementwise-gradient-negative metadata differs')
    deps=read(HERE/'dependencies.json')
    require(root['consumer_source']==deps['sources']['negative_consumer']
        and root['source_qualification']==deps['sources']['model_source_qualification'],
        'Exact real posthoc consumer and prior source qualification required')
    expected_refs=negative_refs(root)
    require(value['refs']==expected_refs,'Actual v2 negative nested/top-level metadata mapping differs')
    # All six values here are JSON. Source Python and the fixed-gate raw file
    # are bound separately; no text/source ref is passed to the JSON reader.
    metadata={key:read(raw) for key,raw in value['refs'].items()}
    c,r,sup=(metadata[k] for k in ('configuration','run_status','supervisor'))
    require(value['refs']['configuration']['path']==str(CHILD/'configuration.json') and c['job_id']==JOB
        and c['code_sha']==CODE and c['tracking_mode']=='offline' and c['input']=='native_s'
        and type(c['seed']) is int and c['seed']==0 and c['smoke'] is False
        and c['fixed_batches']==20 and c['trajectory_updates']==500
        and c['performance_execution']['requested']['checkpoint_policy']=='manual'
        and c['performance_execution']['requested']['resident_models']==2
        and c['performance_execution']['requested']['batch_padded_cost']==8000000
        and c['performance_execution']['requested']['capacity_profile'] is None
        and c['performance_execution']['requested']['padding']==dict(mode='logical_batch_chunks_v1',
            atom_bucket_width=16,max_graphs_per_chunk=32,max_padded_cost_per_chunk=1000000)
        and c['candidate']['distance_checkpointing'] is True and c['candidate']['backbone_checkpointing'] is True
        and c['candidate']['head_checkpointing'] is True
        and c['acceptance_scope']=='V2_FULL20_AND500'
        and c['acceptance_rules']['schema']=='model_v3_A_acceptance_rule_binding_v2'
        and c['acceptance_rules']['version']=='v2' and c['acceptance_rules']['fixed_batch_only'] is False,
        'Actual full A5-v2 config/rule scope differs; fixed-only is not this run')
    for key,name in (('tools/model_v3/paired_a_acceptance.py','paired_producer'),
            ('tools/model_v3/a_execution_runtime.py','paired_runtime'),
            ('current/phychem_mfm/training/v3_performance_acceptance.py','acceptance_math')):
        require(c['source_sha256'][key]==deps['sources'][name]['sha256'],
            'Actual producer config/source implementation binding differs')
    digest=hashlib.sha256(json.dumps({k:v for k,v in c.items() if k!='configuration_sha256'},
        sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(digest==c['configuration_sha256'],'Original configuration canonical hash differs')
    require(r['job_id']==JOB and r['status']=='FIXED_BATCH_GATE_FAILED' and r['failure'] is None
        and r['cleanup_errors']==[] and r['stream_cleanup']==dict(input_descriptors_closed=True,errors=[])
        and r['checkpoint_export'] is None and r['resume_supported'] is False
        and r['trajectory_started'] is False and r['trajectory_completed'] is False
        and type(r['committed_trajectory_updates']) is int and r['committed_trajectory_updates']==0
        and r['acceptance_rules']==c['acceptance_rules'] and r['acceptance_scope']==c['acceptance_scope'],
        'Actual child2 fixed-gate failure/no-trajectory cleanup differs')
    require(sup['job_id']==JOB and sup['status']=='FAILED' and type(sup['exit_code']) is int and sup['exit_code']==2
        and sup['first_failure']==dict(phase='child_exit',exit_code=2)
        and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
        and sup['foreign_gpu_processes_signalled'] is False,'Actual failed supervisor closure differs')
    forbidden=('summary.json','trajectory_gate.json','reference_history.jsonl','candidate_history.jsonl','SDK_expected_summary.json')
    require(all(not (CHILD/name).exists() and not (CHILD/name).is_symlink() for name in forbidden),
        'Failure-path source has no saved summary or trajectory journal; do not invent one')
    expected=scope['sdks']
    require(value['sdks']==expected and len(expected)==2 and tuple(row['run_id'] for row in expected)==IDS,
        'Both explicit actual stat-only SDK descriptors required')
    for row in expected:
        sdk=row['descriptor'];path=Path(sdk['path']);key=row['run_id']
        require(descriptor(path,128<<20)==sdk and path.name=='run-'+key+'.wandb'
            and path.parent.parent==CHILD/'wandb' and path.parent.name.startswith('offline-run-')
            and path.parent.name.endswith('-'+key),'Exact original failed offline SDK differs')
    gate=root['fixed_batch_gate']
    require(root['fixed_gate_metadata_cap_bytes']==16<<20 and gate['path']==str(CHILD/'fixed_batch_gate.json')
        and descriptor(gate['path'],16<<20)=={k:gate[k] for k in ('path','bytes')},
        'Only the exact v2 fixed gate has the16MiB raw-hash exception')
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
    require(manifest['schema']=='A5_failed_sync_manifest_v2' and len(manifest['verifications'])==2,
        'Both independently audited failed SDKs required')
    batch=read(manifest['audit_result']);sup=read(manifest['audit_supervisor'])
    terminal=terminal_C0(manifest['actual_audit_C0']);job=terminal['job_id']
    require(batch['schema']=='A5_failed_log_audit_result_v2'
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
        require(cert['schema']=='A5_failed_zero_history_verification_v2' and cert['scope']==SCOPE
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
        h=row['native_RunRecord'];actual_entity=h['entity'] or entity_default
        require(actual_entity=='mint_leaf258','Actual authenticated/native destination differs from this explicit Root account')
        row['routing']=dict(entity=actual_entity,project=h['project'],run_id=row['run_id'],
            routing_ready=True,entity_origin='original_RunRecord' if h['entity'] else 'actual_authenticated_viewer_default',project_origin='original_RunRecord')
    return manifest,{row['run_id']:row for row in rows}


def request_gate(request):
    raw,manifest=manifest_metadata();proof_rows(manifest)
    require(request['schema']=='A5_failed_selective_sync_request_v2' and request['selected_run_ids']==list(IDS)
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
