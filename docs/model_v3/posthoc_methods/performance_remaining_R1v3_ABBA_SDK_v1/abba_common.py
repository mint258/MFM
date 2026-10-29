"""Four actual closed manual-R1 members; exact source-only SDK/report adapter."""
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
import sync_common as base
from sync_common import *
HERE=Path(__file__).absolute().parent
SCOPE='REMAINING_R1V3_ABBA_LOG_AND_EXISTING_SPEED_REPORT_ONLY'
SERIES=None  # Actual series is selected by bound input, never prefilled.
ROLES=('reference','candidate','candidate','reference')
CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50'
PUBLIC='2b4a4df8636e5d65915d535472ba01084ea72dab'
GPU=None  # Exact cohort UUID is checked by the ordinary metadata adapter.
SERIES_ROOT=None  # Fresh actual v3 family comes from its frozen PLAN.


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
    from remaining_metadata import parent_C0 as validate_parent
    return validate_parent(raw,job)

def metadata_member(item):
    from remaining_metadata import metadata_member as validate_member
    return validate_member(item)

def bound_inputs(raw):
    from remaining_metadata import bound_inputs as validate_inputs
    return validate_inputs(raw)

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
