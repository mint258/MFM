"""Four actual closed manual-R1 members; exact source-only SDK/report adapter."""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
import sync_common as base
from sync_common import *
HERE=Path(__file__).absolute().parent
SCOPE='CURRENT_A00_AV2_R1_ABBA_LOG_AND_EXISTING_SPEED_REPORT_ONLY'
SERIES='A00_manual_R1_Av2_C35_7ffe_v1'
ROLES=('reference','candidate','candidate','reference')
CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50'
PUBLIC='2b4a4df8636e5d65915d535472ba01084ea72dab'
GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243'
SERIES_ROOT=HERE.parent/'performance_A00_manual_R1_Av2_ABBA_v1'


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
    path=Path(path).absolute();info=path.stat()
    require(not any(p.is_symlink() for p in (path,*path.parents)) and path.is_file()
        and info.st_uid==1278 and info.st_nlink==1 and 0<info.st_size<=cap,'Owned bounded ordinary descriptor required')
    return dict(path=str(path),bytes=info.st_size)


def verify(expected=None):
    pin=ref(HERE/'source_pins.json')
    if expected is not None:require(pin['sha256']==expected,'Explicit R1 source SHA differs')
    pins=read(pin);require(pins['schema']=='performance_manual_R1_ABBA_log_sources_v1','Exact source family required')
    for item in pins['files']:
        actual=ref(HERE/item['relative_path'])
        require((actual['bytes'],actual['sha256'])==(item['bytes'],item['sha256']),'R1 source drift')
    deps=read(HERE/'dependencies.json')
    for raw in deps['sources'].values():bind(raw)
    require(base.verify(deps['base_manifest']['sha256'])==deps['base_manifest'],'Original v3 source drift')
    original=(V3/'one_run.py').read_bytes().replace(b'from sync_common import *',b'from abba_common import *')
    require((HERE/'one_run_abba.py').read_bytes()==original,'Only explicit eligibility import may differ in v3 transport')
    require((HERE/'installed_sources.json').read_bytes()==(V3/'installed_sources.json').read_bytes(),'Installed source snapshot differs')
    return pin


def parent_C0(raw,job):
    wanted=['sacct','-X','-j','4524772,4524776,4524779,4524780','-n','-P','-o',
        'JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
    rows=[row.split('|') for row in raw['stdout'].splitlines() if row.strip()]
    require(raw['argv']==wanted and raw['returncode']==0 and raw['stderr']=='' and len(rows)==4
        and {row[0] for row in rows}=={'4524772','4524776','4524779','4524780'},
        'Exact actual current four-member raw parent query required')
    selected=[row for row in rows if row[0]==job]
    require(len(selected)==1 and len(selected[0])==7 and selected[0][1:4]==['zixiao','COMPLETED','0:0']
        and selected[0][4].isdigit() and int(selected[0][4])>0 and selected[0][5:]==['16','compute-0-21'],
        'Actual selected current R1 GPU parent C0/UID/CPU/node required')

def metadata_member(item):
    position=item['position']
    require(type(position) is int and 1<=position<=4 and item['role']==ROLES[position-1],'Exact A/B/B/A position required')
    family=SERIES_ROOT/f'member_{position}';child=family/'child';root=read(item['root']);job=item['job_id']
    require(item['root']['path']==str(HERE/f'member_{position}_BOUND_METADATA.json')
        and root['schema']=='model_v3_current_R1_SDK_bound_member_metadata_v1'
        and root['status']=='SOURCE_SELECTOR_ACTUAL_SUBMISSION_AND_C0_METADATA_ONLY'
        and root['series_id']==SERIES and type(root['position']) is int and root['position']==position and root['role']==item['role']
        and type(job) is str and job.isdigit() and root['job_id']==job,'Exact actual closed Root member required')
    parent_C0(read(root['actual_sacct']),job)
    deps=read(HERE/'dependencies.json')
    require(root['source_package']==deps['sources']['R1_GPU_package'],'Original R1 GPU package identity differs')
    expected=dict(configuration=child/'configuration.json',summary=child/'summary.json',
        run_status=child/'run_status.json',supervisor=family/'supervisor.json',submission=family/'control/Root_submission_actual_v1.json')
    require(set(item['refs'])==set(expected),'Complete explicit member metadata refs required')
    metadata={}
    for key,path in expected.items():
        raw=item['refs'][key]
        require(raw==root[key] and raw['path']==str(path),'Exact Root-bound member metadata differs')
        metadata[key]=read(raw)
    c,s,r,sup,submission=[metadata[k] for k in ('configuration','summary','run_status','supervisor','submission')]
    require(c['job_id']==str(sup['job_id'])==submission['job_id']==job and submission['status']=='SUBMITTED'
        and submission['source_package']==root['source_package'] and c['node'].split('.')[0]=='compute-0-21'
        and c['gpu_uuid']==s['gpu_uuid']==sup['gpu_uuid']==GPU,'Actual job/node/UUID/submission differs')
    require(c['role']==s['role']==item['role'] and type(c['abba_position']) is int and type(s['abba_position']) is int
        and c['abba_position']==s['abba_position']==position and c['series_id']==s['series_id']==SERIES,
        'Actual ABBA identity differs')
    require(c['code_sha']==s['code_sha']==CODE and c['prereg_sha']==s['prereg_sha']==PUBLIC
        and type(c['seed']) is int and type(s['seed']) is int and c['seed']==s['seed']==0
        and c['input']==s['input']=='native_s' and c['smoke'] is s['smoke'] is False
        and c['warmup_updates']==s['warmup_updates']==2 and c['measured_updates']==s['measured_updates']==20
        and s['tracking_mode']=='offline','Original complete seed0/native/2+20 source scope differs')
    require(s['status']==r['status']=='STANDALONE_TIMING_COMPLETED' and r['failure'] is None and r['cleanup_errors']==[]
        and r['stream_cleanup']['errors']==[] and r['stream_cleanup']['input_descriptors_closed'] is True
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
        and sup['foreign_gpu_processes_signalled'] is False,'Actual original trainer/SDK/input/outer cleanup incomplete')
    digest=hashlib.sha256(json.dumps({k:v for k,v in c.items() if k!='configuration_sha256'},
        sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    require(digest==c['configuration_sha256']==s['configuration_sha256'],'Full original config hash differs')
    scope=read(HERE/'scope.json')
    require(submission['schema']=='model_v3_current_Av2_R1_ABBA_Root_single_submission_v1'
        and submission['case']=='a00_manual' and submission['series_id']==SERIES
        and submission['position']==position and submission['role']==item['role']
        and submission['bindings']['MODEL_V3_ABBA_SERIES_ID']==SERIES
        and submission['bindings']['MODEL_V3_ABBA_POSITION']==str(position)
        and submission['bindings']['MODEL_V3_ABBA_ROLE']==item['role']
        and submission['bindings']['MODEL_V3_R1_CASE']=='a00_manual'
        and submission['numeric_qualification']==scope['numeric_gate']['Root_closure']
        and submission['SDK_qualification']==deps['sources']['current_A00_R2_SDK_closure']
        and submission['operations_publication']==deps['sources']['current_R1_method_publication']
        and root['authority']=='EXISTING_ACTUAL_ROOT_SUBMISSION_AND_SEPARATE_ACTUAL_SACCT'
        and root['old_Root_closure_schema_not_counterfeited'] is True,
        'Current authoritative submission/qualification/position binding differs; no old Root closure is fabricated')
    require(c['candidate_options_sha256']==s['candidate_options_sha256']=='52ae1dae8ff65229a2b4f26b281a0e488e751e08671dbf953d33601e6c1a6bf0'
        and tuple(c['candidate'][flag] for flag in ('distance_checkpointing','backbone_checkpointing','head_checkpointing'))==(True,True,True)
        and all(type(c['candidate'][flag]) is bool for flag in ('distance_checkpointing','backbone_checkpointing','head_checkpointing'))
        and c['source_sha256']['tools/model_v3/single_a_benchmark.py']==deps['sources']['producer']['sha256']
        and c['source_sha256']['tools/model_v3/a_execution_runtime.py']==deps['sources']['speed_runtime']['sha256'],
        'Exact current A00 candidate/runtime source binding differs')
    publication=read(submission['operations_publication']);package=read(root['source_package'])
    require(publication['schema']=='model_v3_exact_tree_publication_actual_v1'
        and publication['repository_full_name']=='mint258/MFM' and publication['branch']=='model-v3'
        and publication['public_code_sha']=='7f790e9363a5f7ec4b10d475bbabdb2e6969bd5d'
        and publication['public_branch_readback_verified'] is True and publication['public_Git_API_tree_readback_verified'] is True
        and root['source_package']['sha256']=='7a7544310828af89ef2f75446bbee3f74e029b5a4676797b30ff1bcef2866ba5'
        and package['schema']=='model_v3_current_Av2_R1_ABBA_source_pins_v1', 'Exact actual current R1 method publication/package required')
    table={row['path']:row for row in publication['files']}
    require(len(table)==len(publication['files']), 'Duplicate published current R1 method paths')
    for raw in [*package['files'],root['source_package']]:
        leaf=Path(raw['path']).name;published=table['docs/model_v3/pre_registered_methods/performance_current_Av2_R1_ABBA_v1/'+leaf]
        bind(raw);body=Path(raw['path']).read_bytes()
        require(published['type']=='blob' and published['sha256']==raw['sha256'] and published['bytes']==raw['bytes']
            and published['working_sha256']==raw['sha256'] and published['only_CRLF_to_LF_normalized'] is False
            and published['sha']==hashlib.sha1(b'blob '+str(len(body)).encode()+b'\0'+body).hexdigest(),
            'Current published R1 method raw bytes/blob differ')
    key=s['tracking_run_id']
    require(type(key) is str and re.fullmatch('[a-z0-9]{8}',key) and key==root['tracking_run_id']==item['run_id'],
        'Actual original tracking run identity differs')
    require(item['SDK']==root['SDK'] and descriptor(item['SDK']['path'],128<<20)==item['SDK']
        and item['step_journal']==root['step_journal'] and descriptor(item['step_journal']['path'],32<<20)==item['step_journal'],
        'Original SDK/journal stat descriptor differs')
    sdk=Path(item['SDK']['path'])
    require(sdk.parent.parent==child/'wandb' and sdk.parent.name.startswith('offline-run-')
        and sdk.parent.name.endswith('-'+key) and sdk.name=='run-'+key+'.wandb'
        and item['step_journal']['path']==str(child/'steps.jsonl'),'Original exact durable SDK/journal location differs')
    return metadata


def bound_inputs(raw):
    value=read(raw)
    require(value['schema']=='performance_manual_R1_ABBA_log_inputs_v1' and value['scope']==SCOPE
        and value['series_id']==SERIES and len(value['members'])==4
        and [x['position'] for x in value['members']]==[1,2,3,4],'Exactly four ordered actual members required')
    require(len({x['job_id'] for x in value['members']})==4 and len({x['run_id'] for x in value['members']})==4,
        'Actual four distinct job/run identities required')
    total=0
    for item in value['members']:
        metadata_member(item)
        total+=item['SDK']['bytes']+item['step_journal']['bytes']+item['root']['bytes']+sum(x['bytes'] for x in item['refs'].values())
    scope=read(HERE/'scope.json');require(value['numeric_gate']==scope['numeric_gate'],'Exact current A00 numeric gate binding differs')
    gate_root=read(value['numeric_gate']['Root_closure'])
    require(gate_root['schema']=='model_v3_Root_current_Av2_manual_full_and_original_capacity_consumer_closure_v1'
        and gate_root['status']=='ACTUAL_CURRENT_SOURCE_V2_FULL20_AND500_PASS_AND_EXISTING_CPU_CAPACITY_CONSUMER_C0'
        and gate_root['GPU_job_id']=='4524712' and gate_root['CPU_job_id']=='4524717'
        and gate_root['local_code_sha']==CODE and gate_root['public_prereg_sha']==PUBLIC
        and gate_root['source_current_graph_verified_by_binder_and_CPU'] is True
        and gate_root['fixed20']['passed'] is True and gate_root['fixed20']['batches']==20
        and gate_root['trajectory_updates']==500,
        'Exact current same-source A00 full20plus500/CPU4717 gate required; not R1 capacity transfer')
    require(total+sum(r['bytes'] for r in value['numeric_gate']['files'].values())<=128<<20,
        'Explicit four-run input bound128MiB exceeded')
    return value


def header_check(header,item,role):
    require(role==item['role'] and role in ROLES and header['run_id']==item['run_id']
        and header['project']=='mfm_model_v3_development'
        and header['display_name']==f'A_speed_{role}_{item["job_id"]}' and type(header['entity']) is str,
        'Actual Native role/run/name/project differs')


def proof_rows(manifest):
    require(manifest['schema']=='performance_manual_R1_ABBA_sync_manifest_v1'
        and len(manifest['verifications'])==4,'Exactly four independently audited proofs required')
    batch=read(manifest['audit_result']);sup=read(manifest['audit_supervisor'])
    terminal=terminal_C0(manifest['actual_audit_C0']);job=terminal['job_id']
    require(batch['schema']=='performance_manual_R1_ABBA_log_batch_v1'
        and batch['status']=='ALL_FOUR_STANDALONE_LOGS_AND_ORIGINAL_SPEED_REPORT_CLOSED_PENDING_ROOT_C0'
        and batch['actual_job_id']==job==str(sup['job_id']) and batch['returncode']==0 and batch['failure'] is None
        and batch['verifications']==manifest['verifications'] and batch['source_pins']==ref(HERE/'source_pins.json')
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
        and sup['remaining']==[] and sup['private_storage']['first_sampling_failure'] is None
        and sup['command']==batch['actual_argv'],'Actual batch CPU C0/source/supervisor required')
    expected=[str(PYTHON),'-u','-B',str(HERE/'audit_abba.py'),'--inputs',batch['inputs']['path'],
        '--inputs-sha256',batch['inputs']['sha256'],'--pins-sha256',batch['source_pins']['sha256'],
        '--output',str(Path(manifest['audit_result']['path']).parent)]
    require(batch['actual_argv']==expected and batch['actual_allocation']['uid']==1278,'Actual CPU audit argv/UID differs')
    inputs=bound_inputs(batch['inputs']);members={x['position']:x for x in inputs['members']}
    invocation=read(batch['speed_report_invocation']);deps=read(HERE/'dependencies.json')
    report_path=Path(manifest['audit_result']['path']).parent/'ORIGINAL_A_SPEED_REPORT.json'
    wanted_argv=[str(PYTHON),'-B',deps['sources']['speed_report']['path'],'--runs',
        *[str(Path(m['refs']['configuration']['path']).parent) for m in inputs['members']],
        '--supervisors',*[m['refs']['supervisor']['path'] for m in inputs['members']],
        '--numeric-gate',inputs['numeric_gate']['directory'],'--output',str(report_path)]
    require(invocation['returncode']==0 and invocation['report']==batch['speed_report']
        and invocation['source']==deps['sources']['speed_report'] and invocation['argv']==wanted_argv
        and invocation['job_id']==job and batch['speed_report']['path']==str(report_path),
        'Original exact four-member/numeric-gate speed CLI completion differs')
    report=read(batch['speed_report'])
    member_refs=[{k:{'path':m['refs'][k]['path'],'sha256':m['refs'][k]['sha256']}
        for k in ('summary','configuration','run_status','supervisor')} for m in inputs['members']]
    gate_refs={k:{'path':v['path'],'sha256':v['sha256']} for k,v in inputs['numeric_gate']['files'].items()}
    require(report['schema']=='model_v3_A_ABBA_speed_v1' and report['has_matched_A_numeric_acceptance'] is True
        and report['numeric_acceptance_granted_by_this_report'] is False and report['member_file_bindings']==member_refs
        and report['numeric_gate_file_bindings']==gate_refs and report['report_source_sha256']==deps['sources']['speed_report']['sha256'],
        'Original complete speed-report output/source/input identities differ')
    rows=[]
    for raw in manifest['verifications']:
        cert=read(raw);item=members[cert['position']];key=item['run_id'];h=cert['history']
        require(cert['schema']=='performance_manual_R1_ABBA_log_verification_v1' and cert['scope']==SCOPE
            and cert['status']=='ALL_SAVED_STANDALONE_LOG_FIELDS_MATCHED' and cert['run_id']==key
            and type(cert['position']) is int and cert['role']==item['role'] and cert['model_job_id']==item['job_id']
            and cert['source_pins']==batch['source_pins'] and cert['inputs']==batch['inputs']
            and cert['full_config_summary_typed_exact'] is True and cert['raw_before_after_binding_closed'] is True
            and cert['history_reader_source']==deps['sources']['literal_reader']
            and cert['tap_source']==deps['sources']['tap'],'Exact full standalone SDK certificate required')
        header_check(cert['native_RunRecord'],item,cert['role'])
        require(h['schema']=='model_v3_native_mirror_verification_v7' and h['status']=='VERIFIED_COMMITTED_HISTORY'
            and h['sdk_run_ids']==[key] and h['sdk_exit_codes']==[0] and type(h['sdk_exit_codes'][0]) is int
            and h['clean_eof'] is True and h['native_closed'] is True and h['decode_error'] is None
            and type(h['uncommitted_native_requests']) is int and h['uncommitted_native_requests']==0
            and type(h['history_rows']) is int and h['history_rows']==22
            and h['first_explicit_step']==1 and h['last_explicit_step']==22,'Exact22steps/exit0/fullfragmentEOF required')
        require({k:cert['sdk'][k] for k in ('path','bytes')}==item['SDK']
            and {k:cert['journal'][k] for k in ('path','bytes')}==item['step_journal'],'Exact original artifacts differ')
        for source in cert['source_refs'].values():bind(source,16<<20)
        rows.append(dict(run_id=key,SDK_raw_ref=cert['sdk'],native_RunRecord=cert['native_RunRecord'],native_exit_code=0,
            expected_API_state='finished',history_rows=22,first_explicit_step=1,last_explicit_step=22,
            original_model_status='STANDALONE_TIMING_COMPLETED',role=cert['role'],position=item['position'],
            model_job_id=item['job_id'],verification=raw,scope=SCOPE))
    require(len({r['run_id'] for r in rows})==4 and sorted(r['position'] for r in rows)==[1,2,3,4],
        'Each exact ABBA member must close once')
    return sorted(rows,key=lambda r:r['position'])


def manifest_metadata():
    raw=ref(os.environ['MODEL_V3_R1_MANIFEST'])
    require(raw['sha256']==os.environ['MODEL_V3_R1_MANIFEST_SHA'],'Explicit four-run manifest drift')
    value=read(raw);require(value['runs']==proof_rows(value),'Proof-derived eligible rows differ')
    return raw,value


def eligible_rows():
    allocation();_,manifest=manifest_metadata();rows=proof_rows(manifest);entity_default=None
    if any(not r['native_RunRecord']['entity'] for r in rows):
        private=Path(os.environ['TMPDIR'])/('R1_authenticated_route_'+str(os.getpid()));private.mkdir(mode=0o700)
        with (private/'stdout').open('x') as out,(private/'stderr').open('x') as err,contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            for item in read(HERE/'installed_sources.json')['files']:
                current=ref(item['original']);require((current['bytes'],current['sha256'])==(item['bytes'],item['sha256']),'Installed API drift')
            import wandb
            require(wandb.__version__=='0.28.1','Actual reviewed SDK0.28.1 required');api=wandb.Api(timeout=30)
            require(api.settings['base_url']=='https://api.wandb.ai','Actual destination differs')
            entity_default=api.viewer.entity
            require(type(entity_default) is str and entity_default and api.default_entity==entity_default,'Actual authenticated route missing')
    for row in rows:
        h=row['native_RunRecord'];row['routing']=dict(entity=h['entity'] or entity_default,project=h['project'],run_id=row['run_id'],
            routing_ready=True,entity_origin='original_RunRecord' if h['entity'] else 'actual_authenticated_viewer_default',project_origin='original_RunRecord')
    return manifest,{r['run_id']:r for r in rows}


def request_gate(request):
    raw,manifest=manifest_metadata();rows=proof_rows(manifest);by_position={r['position']:r['run_id'] for r in rows}
    positions=request['selected_positions']
    require(positions in ([1,2],[3,4]) and request['selected_run_ids']==[by_position[p] for p in positions]
        and request['schema']=='performance_manual_R1_ABBA_selective_sync_request_v1'
        and request['eligible_manifest']==raw and request['source_manifest']==ref(HERE/'source_pins.json')
        and request['mode']=='batch' and request['maximum_batch_runs']==3
        and request['child_seconds']==3000 and request['CLI_timeout_seconds']==600 and request['API_verification_seconds']==180,
        'Only explicit ABBA positions1+2 or3+4 with original max3 transport required')
    gate=request['pilot_gate'];terminal=terminal_C0(gate['actual_terminal']);pilot=read(gate['result']);sup=read(gate['supervisor'])
    require(terminal['job_id']==str(pilot['job_id'])==str(sup['job_id'])=='4521412'
        and pilot['source_manifest']==ref(V3/'source_pins.json') and pilot['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0'
        and len(pilot['records'])==1 and pilot['records'][0]['native_exit_code']==1
        and pilot['records'][0]['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED'
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and sup['remaining']==[]
        and gate['native_exit_code']==1 and gate['actual_replay_verified'] is True,'Original actual v3 transport method gate required')
