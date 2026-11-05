"""Explicit closed-long input adapter; header access is CPU-job-only."""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sys
import time
HERE=Path(__file__).absolute().parent
V3=HERE.parent/'wandb_selective_sync50_v3'
sys.path.insert(0,str(V3))
import sync_common as base
from sync_common import *
HERE=Path(__file__).absolute().parent
V3_SHA='4e97d0f413564ace06555067e828bb7109334573c5e43338426cdecf083609c3'


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

def verify(expected=None):
    pin=ref(HERE/'source_pins.json')
    if expected is not None:require(pin['sha256']==expected,'Closed-long source manifest differs')
    for leaf in read(pin)['files']:
        actual=ref(HERE/leaf['relative_path'])
        require((actual['bytes'],actual['sha256'])==(leaf['bytes'],leaf['sha256']),'Closed-long source changed')
    deps=read(HERE/'dependencies.json')
    for raw in deps['source_refs']:bind(raw)
    base.verify(V3_SHA)
    changes={
        'one_run_long.py':[('from sync_common import *','from long_common import *')],
        'sync_selected_long.py':[('from sync_common import *','from long_common import *'),
            ("HERE/'one_run.py'","HERE/'one_run_long.py'"),
            ("[HERE/'source_pins.json',a.request]","[HERE/'source_pins.json',a.request]+closed_source_paths(request)")],
    }
    for own,edits in changes.items():
        old={'one_run_long.py':'one_run.py','sync_selected_long.py':'sync_selected.py'}[own]
        wanted=(V3/old).read_bytes()
        for before,after in edits:
            require(wanted.count(before.encode())==1,'Frozen transport adaptation point changed')
            wanted=wanted.replace(before.encode(),after.encode())
        require((HERE/own).read_bytes()==wanted,'Transport must be exact v3 body plus declared input bindings')
    require((HERE/'installed_sources.json').read_bytes()==(V3/'installed_sources.json').read_bytes(),
        'Reviewed installed API/CLI bindings changed')
    return pin


def source_inventory(raw):
    deps=read(HERE/'dependencies.json')
    require(raw==deps['closed_audit_source'],'Only the exact reviewed two-entry audit producer may qualify sync')
    pins=read(raw);root=Path(raw['path']).parent;refs=[raw]
    require(pins['schema']=='native_S_long_segment_log_source_pins_v3'
        and type(pins.get('files')) is list,'Supported exact audit-v3 source inventory missing')
    for leaf in pins['files']:
        name=leaf['file'];require(Path(name).name==name and name not in ('.','..'),'Flat exact audit source filename required')
        path=root/name
        item=dict(path=str(path),bytes=leaf['bytes'],sha256=leaf['sha256']);bind(item);refs.append(item)
    return refs


def proof_rows(entries):
    require(type(entries) is list and 1<=len(entries)<=3,'One to three explicitly supplied closed-long proofs required')
    rows=[];seen=set()
    for entry in entries:
        require(set(entry)=={'verification','audit_batch','audit_supervisor','actual_audit_C0'},'Exact explicit proof tuple required')
        proof=read(entry['verification']);batch=read(entry['audit_batch']);sup=read(entry['audit_supervisor'])
        terminal=terminal_C0(entry['actual_audit_C0']);job=str(batch['actual_job_id'])
        require(job==terminal['job_id']==str(sup['job_id']) and batch['returncode']==0 and batch['failure'] is None
            and batch['schema']=='native_S_long_segment_log_audit_batch_v1'
            and batch['status']=='CLOSED_SEGMENT_LOGS_MATCHED_PENDING_CPU_OUTER_C0'
            and entry['verification'] in batch['verifications']
            and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and sup['remaining']==[]
            and sup['command']==batch['actual_argv']
            and sup['private_storage']['first_sampling_failure'] is None,'Actual same-job full-log audit C0/process closure required')
        source_inventory(batch['source_pins']);bind(batch['inputs'])
        require(proof['schema']=='native_S_long_segment_full_log_comparison_v1'
            and proof['status']=='ALL_SAVED_SCIENTIFIC_LOG_FIELDS_MATCHED'
            and proof['full_config_summary_typed_exact'] is True and proof['raw_before_after_binding_closed'] is True,
            'Only supported actual full closed-long verification schema is admitted')
        history=proof['history'];key=proof['run_id'];sdk=proof['sdk']
        require(key not in seen and type(key) is str and key and Path(sdk['path']).name=='run-'+key+'.wandb'
            and set(sdk)=={'path','bytes','sha256'} and type(sdk['bytes']) is int and 0<=sdk['bytes']<=128<<20,
            'Unique bounded exact SDK identity required')
        require(key in ('2wh2cs0m','dp8xtsi9'),
            'Only explicitly closed028/029 may sync; other segments and old cohorts are excluded')
        seen.add(key)
        require(history['schema']=='model_v3_native_mirror_verification_v7'
            and history['status']=='VERIFIED_COMMITTED_HISTORY' and history['sdk_run_ids']==[key]
            and history['clean_eof'] is True and history['native_closed'] is True
            and history['decode_error'] is None and history['uncommitted_native_requests']==0
            and len(history['sdk_exit_codes'])==1 and type(history['sdk_exit_codes'][0]) is int
            and history['sdk_exit_codes'][0] in (0,1)
            and type(history['history_rows']) is int and 0<=history['history_rows']<=100000
            and proof['first_global_cursor']==history['first_explicit_step']
            and proof['last_global_cursor']==history['last_explicit_step'],
            'Actual native rows/steps/exit/EOF proof missing; no directory-name clock inference')
        for raw in proof['closed_metadata_refs'].values():bind(raw)
        bind(proof['history_reader_source']);bind(proof['tap_source']);bind(proof['operational_package'])
        model_terminal=read(proof['closed_metadata_refs']['terminal'])
        exit_code=history['sdk_exit_codes'][0]
        rows.append(dict(run_id=key,SDK_raw_ref=sdk,native_exit_code=exit_code,
            expected_API_state='failed' if exit_code else 'finished',history_rows=history['history_rows'],
            first_explicit_step=history['first_explicit_step'],last_explicit_step=history['last_explicit_step'],
            original_model_status=model_terminal['status'],verification=entry['verification'],
            scope='CLOSED_NATIVE_LONG_SEGMENT_LOGGING_ONLY_NO_B_ACCEPTANCE'))
    return rows


def manifest_metadata():
    raw=ref(os.environ['MODEL_V3_LONGSYNC_MANIFEST'])
    require(raw['sha256']==os.environ['MODEL_V3_LONGSYNC_MANIFEST_SHA'],'Explicit manifest changed')
    value=read(raw);require(value['schema']=='native_closed_long_sync_manifest_v1','Closed-long manifest schema differs')
    require(value['runs']==proof_rows(value['entries']),'Manifest must preserve actual proof-derived counts and exits')
    require(type(value['default_entity']) is str and value['default_entity'],'Root explicit empty-entity default missing')
    return raw,value


def load_frozen(raw,name):
    bind(raw);spec=importlib.util.spec_from_file_location(name,raw['path'])
    module=importlib.util.module_from_spec(spec);sys.modules[name]=module;spec.loader.exec_module(module)
    return module


def eligible_rows():
    allocation()  # Mandatory before any SDK open; Root prepare never calls this.
    _,value=manifest_metadata();deps=read(HERE/'dependencies.json')
    inspector=load_frozen(deps['inspector'],'longsync_frozen_native_inspector')
    kernel=load_frozen(deps['header_kernel'],'longsync_frozen_header_kernel')
    Scanner,Record,_,_=inspector.load_decoder(read(deps['decoder_reference']))
    rows={};deadline=time.monotonic()+180
    for row in value['runs']:
        sdk=row['SDK_raw_ref'];inspector.bind(sdk,128<<20,deadline)
        observed=kernel.read_profile_header(Scanner,Record,sdk,row['run_id'],deadline,None)
        inspector.bind(sdk,128<<20,deadline)
        header=observed['header'];route=inspector.route(header,value['default_entity'])
        require(route['routing_ready'] is True,'Original native project/entity routing not established')
        rows[row['run_id']]={**row,'native_RunRecord':header,'routing':route}
    return value,rows


def closed_source_paths(request):
    raw,value=manifest_metadata();paths={Path(raw['path'])}
    for entry in value['entries']:
        paths.update(Path(item['path']) for item in entry.values())
        terminal=read(entry['actual_audit_C0']);paths.add(Path(terminal['raw_sacct']['path']))
        batch=read(entry['audit_batch']);paths.add(Path(batch['inputs']['path']))
        paths.update(Path(item['path']) for item in source_inventory(batch['source_pins']))
        proof=read(entry['verification'])
        paths.update(Path(item['path']) for item in proof['closed_metadata_refs'].values())
        paths.update(Path(proof[name]['path']) for name in ('history_reader_source','tap_source','operational_package'))
    return sorted(paths,key=str)


def request_gate(request):
    raw,value=manifest_metadata()  # Metadata only, safe on Root; no header access here.
    require(request['schema']=='native_closed_long_sync_request_v1' and request['eligible_manifest']==raw
        and request['mode']=='batch' and request['selected_run_ids']==[row['run_id'] for row in value['runs']],
        'Only this explicit one-to-three manifest is admitted; no selection or queue')
    gate=request['pilot_gate'];terminal=terminal_C0(gate['actual_terminal'])
    pilot=read(gate['result']);sup=read(gate['supervisor'])
    require(terminal['job_id']==str(pilot['job_id'])==str(sup['job_id'])=='4521412'
        and pilot['source_manifest']==ref(V3/'source_pins.json')
        and pilot['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0'
        and len(pilot['records'])==1 and pilot['records'][0]['native_exit_code']==1
        and pilot['records'][0]['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED'
        and sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None and sup['remaining']==[]
        and gate['native_exit_code']==1 and gate['actual_replay_verified'] is True,
        'Actual identical-v3 failed-exit transport method C0 missing')
