"""One actual Root-closed ordinary routing7 R2 pair selected from six; unchanged v3 transport primitives."""
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
SCOPE='ROUTING7_AV2_R2_LOG_ONLY'
CODE='7ffe8a5557590b1481f4ca74073007f070dc6a50'
PUBLIC='2b4a4df8636e5d65915d535472ba01084ea72dab'
RULE_PUBLIC='4f6ba16973ea4a30472c7fb33d3aadec974a4462'
# Each actual v7 submission binds its true operations_publication; no future commit constant.
IDS=set()  # Filled only by the bound actual two-SDK inputs, never future IDs.


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
        and info.st_uid==1278 and info.st_nlink==1 and 0<=info.st_size<=cap,'Physical owned bounded descriptor required')
    return dict(path=str(path),bytes=info.st_size)


def verify(expected=None):
    pin=ref(HERE/'source_pins.json')
    if expected is not None:require(pin['sha256']==expected,'Explicit paired source SHA differs')
    pins=read(pin);require(pins['schema']=='performance_routing7_Av2_R2_paired_log_sources_v1','Paired source inventory required')
    for item in pins['files']:
        actual=ref(HERE/item['relative_path']);require((actual['bytes'],actual['sha256'])==(item['bytes'],item['sha256']),'Paired source drift')
    deps=read(HERE/'dependencies.json')
    for raw in deps['sources'].values():bind(raw)
    require(base.verify(deps['base_manifest']['sha256'])==deps['base_manifest'],'Original v3 source identity differs')
    wanted=(V3/'one_run.py').read_bytes().replace(b'from sync_common import *',b'from paired_common import *')
    require((HERE/'one_run_paired.py').read_bytes()==wanted,'Only explicit eligible-input import may differ in v3 transport')
    require((HERE/'installed_sources.json').read_bytes()==(V3/'installed_sources.json').read_bytes(),'Installed source snapshots differ')
    return pin


def metadata_case(case):
    from routing_metadata import metadata_case as validate_routing7_case
    return validate_routing7_case(case)

def bound_inputs(raw):
    inputs=read(raw)
    require(inputs['schema']=='performance_routing7_Av2_R2_paired_log_inputs_v1'
        and inputs['scope']==SCOPE and inputs['source_pins']==ref(HERE/'source_pins.json')
        and len(inputs['cases'])==1,'One explicitly closed ordinary routing7 pair required')
    case=inputs['cases'][0];ids=[s['run_id'] for s in case['sdks']]
    require(len(ids)==len(set(ids))==2 and all(type(k) is str and re.fullmatch('[a-z0-9]+',k) for k in ids),
        'Two distinct actual runIDs required')
    IDS.clear();IDS.update(ids)
    metadata_case(case)
    require(terminal_C0(case['actual_model_C0'])['job_id']==case['job_id'],'Actual saved original GPU C0 differs')
    require(all(Path(item['descriptor']['path']).name=='run-'+item['run_id']+'.wandb'
        and Path(item['descriptor']['path']).is_relative_to(Path(case['refs']['configuration']['path']).parent)
        for item in case['sdks']),'SDK source path/runID differs from this exact original producer output')
    selected_bytes=sum(item['descriptor']['bytes'] for item in case['sdks'])
    selected_bytes+=sum(v['bytes'] for v in case['journals'].values())+sum(v['bytes'] for v in case['refs'].values())
    require(selected_bytes<=128<<20,'Explicit selected original sources exceed128MiB')
    return inputs

def header_check(header,job,role):
    require(role in ('reference','candidate') and header['run_id'] in IDS
        and header['project']=='mfm_model_v3_development' and header['display_name']==f'A_{role}_{job}'
        and type(header['entity']) is str,'Actual paired Native role/name/project differs')


def proof_rows(manifest):
    require(manifest['schema']=='performance_routing7_Av2_R2_paired_sync_manifest_v1' and len(manifest['verifications'])==2,'Both explicit independently audited proofs required')
    batch=read(manifest['audit_result']);sup=read(manifest['audit_supervisor']);terminal=terminal_C0(manifest['actual_audit_C0']);job=terminal['job_id']
    require(batch['schema']=='performance_routing7_Av2_R2_paired_log_batch_v1' and batch['status']=='ALL_TWO_PAIRED_LOGS_MATCHED_PENDING_ROOT_C0'
        and batch['actual_job_id']==job==str(sup['job_id']) and batch['returncode']==0 and batch['failure'] is None
        and batch['verifications']==manifest['verifications'] and sup['status']=='COMPLETED' and sup['exit_code']==0
        and sup['first_failure'] is None and sup['remaining']==[] and sup['private_storage']['first_sampling_failure'] is None
        and sup['command']==batch['actual_argv'],'Actual paired audit CPU C0/supervisor required')
    require(batch['source_pins']==ref(HERE/'source_pins.json'),'Actual batch source identity differs')
    expected_argv=[str(PYTHON),'-u','-B',str(HERE/'audit_paired.py'),'--inputs',batch['inputs']['path'],
        '--inputs-sha256',batch['inputs']['sha256'],'--pins-sha256',batch['source_pins']['sha256'],
        '--output',str(Path(manifest['audit_result']['path']).parent)]
    require(batch['actual_argv']==expected_argv and batch['actual_allocation']['uid']==1278,'Actual source-bound CPU audit argv/UID differs')
    inputs=bound_inputs(batch['inputs']);case_map={c['job_id']:c for c in inputs['cases']};rows=[];roles={k:set() for k in case_map}
    deps=read(HERE/'dependencies.json')
    for raw in manifest['verifications']:
        cert=read(raw);key=cert['run_id'];case=case_map[cert['model_job_id']];h=cert['history'];role=cert['paired_role']
        require(cert['schema']=='performance_R2_paired_log_verification_v1' and cert['scope']==SCOPE
            and cert['status']=='ALL_SAVED_PAIRED_LOG_FIELDS_MATCHED' and cert['source_pins']==batch['source_pins']
            and cert['inputs']==batch['inputs'] and cert['full_config_summary_typed_exact'] is True
            and cert['raw_before_after_binding_closed'] is True and cert['history_reader_source']==deps['sources']['literal_reader']
            and cert['tap_source']==deps['sources']['tap'],
            'Exact paired typed/fullstream certificate required')
        require(cert['native_RunRecord']['run_id']==key,'Certificate/native SDK ID differs')
        header_check(cert['native_RunRecord'],case['job_id'],role)
        require(h['schema']=='model_v3_native_mirror_verification_v7' and h['status']=='VERIFIED_COMMITTED_HISTORY'
            and h['sdk_run_ids']==[key] and h['sdk_exit_codes']==[0] and type(h['sdk_exit_codes'][0]) is int
            and h['clean_eof'] is True and h['native_closed'] is True and h['decode_error'] is None
            and type(h['uncommitted_native_requests']) is int and h['uncommitted_native_requests']==0
            and type(h['history_rows']) is int and h['history_rows']==500 and h['first_explicit_step']==1 and h['last_explicit_step']==500,
            'Original exact500steps1..500/exit/fullfragmentEOF proof required')
        require(key in {s['run_id'] for s in case['sdks']} and role not in roles[case['job_id']]
            and {k:cert['sdk'][k] for k in ('path','bytes')}==next(s['descriptor'] for s in case['sdks'] if s['run_id']==key)
            and {k:cert['journal'][k] for k in ('path','bytes')}==case['journals'][role],'Role/SDK/journal cross-case identity differs')
        roles[case['job_id']].add(role)
        for source in cert['source_refs'].values():bind(source)
        rows.append(dict(run_id=key,SDK_raw_ref=cert['sdk'],native_RunRecord=cert['native_RunRecord'],native_exit_code=0,
            expected_API_state='finished',history_rows=500,first_explicit_step=1,last_explicit_step=500,
            original_model_status='PAIRED_GATES_PASS',paired_role=role,model_job_id=case['job_id'],verification=raw,scope=SCOPE))
    require({r['run_id'] for r in rows}==IDS and all(v=={'reference','candidate'} for v in roles.values()),'Both exact roles of this one head-off case must close')
    return rows


def manifest_metadata():
    raw=ref(os.environ['MODEL_V3_PAIRED_MANIFEST']);require(raw['sha256']==os.environ['MODEL_V3_PAIRED_MANIFEST_SHA'],'Explicit paired manifest drift')
    value=read(raw);require(value['runs']==proof_rows(value),'Proof-derived manifest rows differ');return raw,value


def eligible_rows():
    allocation();_,manifest=manifest_metadata();rows=proof_rows(manifest);entity_default=None
    if any(not r['native_RunRecord']['entity'] for r in rows):
        private=Path(os.environ['TMPDIR'])/('paired_authenticated_route_'+str(os.getpid()));private.mkdir(mode=0o700)
        with (private/'stdout').open('x') as out,(private/'stderr').open('x') as err,contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            for item in read(HERE/'installed_sources.json')['files']:
                current=ref(item['original']);require((current['bytes'],current['sha256'])==(item['bytes'],item['sha256']),'Installed API source drift')
            import wandb
            require(wandb.__version__=='0.28.1','Reviewed actual SDK version required');api=wandb.Api(timeout=30)
            require(api.settings['base_url']=='https://api.wandb.ai','Actual destination differs')
            entity_default=api.viewer.entity
            require(entity_default=='mint_leaf258' and api.default_entity==entity_default,'Authorized authenticated mint_leaf258 destination required')
    for row in rows:
        header=row['native_RunRecord'];require((header['entity'] or entity_default)=='mint_leaf258','Original entity must match authorized mint_leaf258; never reroute');row['routing']=dict(entity=header['entity'] or entity_default,project=header['project'],run_id=row['run_id'],
            routing_ready=True,entity_origin='original_RunRecord' if header['entity'] else 'actual_authenticated_viewer_default',project_origin='original_RunRecord')
    return manifest,{r['run_id']:r for r in rows}


def request_gate(request):
    raw,manifest=manifest_metadata();selected=request['selected_run_ids']
    require(request['schema']=='performance_routing7_Av2_R2_paired_selective_sync_request_v1' and request['eligible_manifest']==raw
        and request['source_manifest']==ref(HERE/'source_pins.json') and request['mode']=='batch'
        and request['maximum_batch_runs']==3 and 1<=len(selected)<=3 and len(set(selected))==len(selected) and set(selected)<=IDS
        and request['child_seconds']==3000 and request['CLI_timeout_seconds']==600 and request['API_verification_seconds']==180,
        'Exact explicit max3 original transport batch required')
    gate=request['pilot_gate'];terminal=terminal_C0(gate['actual_terminal']);pilot=read(gate['result']);sup=read(gate['supervisor'])
    require(terminal['job_id']==str(pilot['job_id'])==str(sup['job_id'])=='4521412'
        and pilot['source_manifest']==ref(V3/'source_pins.json') and pilot['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0'
        and len(pilot['records'])==1 and pilot['records'][0]['native_exit_code']==1
        and pilot['records'][0]['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED'
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and sup['remaining']==[]
        and gate['native_exit_code']==1 and gate['actual_replay_verified'] is True,'Original identical-v3 actual transport method C0 missing')
