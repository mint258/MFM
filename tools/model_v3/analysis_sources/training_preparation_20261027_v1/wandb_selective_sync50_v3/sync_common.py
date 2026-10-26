"""Small bounded metadata and exact-source staging primitives."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import stat
import socket
import re

HERE=Path(__file__).absolute().parent
BASE=Path('/share/home/zixiao/descriptor_analysis')
OLD=BASE/'runs/model_v3_20261025'
PYTHON=BASE/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'


def require(value,message):
    if not value:raise ValueError(message)


def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def ref(path,maximum=2<<20):
    path=Path(path).absolute()
    require(not any(p.is_symlink() for p in (path,*path.parents)),'Symlink input/source rejected')
    before=path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_uid==os.getuid() and before.st_nlink==1
        and 0<=before.st_size<=maximum,'Owned bounded ordinary source required')
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):digest.update(block)
    after=path.stat()
    require((before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==
        (after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'Input/source changed during hashing')
    return dict(path=str(path),bytes=before.st_size,sha256=digest.hexdigest())


def bind(value,maximum=2<<20):
    require(ref(value['path'],maximum)==value,'Raw reference changed')
    return value


def read(value):
    if not isinstance(value,dict):value=ref(value)
    bind(value)
    def pairs(items):
        output={}
        for key,item in items:
            require(key not in output,'Duplicate metadata key');output[key]=item
        return output
    return json.loads(Path(value['path']).read_bytes(),object_pairs_hook=pairs,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('Nonfinite metadata')))


def write(path,value):
    raw=encoded(value);require(len(raw)<=2<<20,'Metadata artifact exceeds2MiB')
    path=Path(path);path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with path.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return ref(path)


def root_only():
    require(os.getuid()==1278 and socket.gethostname()=='sonmi','Actual Root sonmi metadata coordinator required')


def verify(expected=None):
    manifest=ref(HERE/'source_pins.json')
    if expected is not None:require(manifest['sha256']==expected,'Own frozen source manifest differs')
    pins=read(manifest)
    for row in pins['files']:
        actual=ref(HERE/row['relative_path'])
        require(actual['bytes']==row['bytes'] and actual['sha256']==row['sha256'],'Frozen sync source changed')
    for row in read(HERE/'installed_sources.json')['files']:
        require(ref(row['snapshot'])==dict(path=row['snapshot'],bytes=row['bytes'],sha256=row['sha256']),
            'Installed-source snapshot changed')
    for row in read(HERE/'dependencies.json')['files']:bind(row)
    return manifest


def terminal_C0(projection):
    value=read(projection);raw=read(value['raw_sacct']);job=str(value['job_id'])
    require(value['schema']=='model_v3_sync_Root_terminal_v1' and value['status']=='COMPLETED'
        and value['exit_code']=='0:0' and raw['returncode']==0
        and raw['argv']==['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode']
        and raw['stdout'].strip()==job+'|COMPLETED|0:0','Actual exact parent raw C0 required')
    return value


def eligible_rows():
    manifest=read(HERE/'explicit50.json');certificate=read(manifest['integrity'])
    require(manifest['selected_count']==50 and len(manifest['runs'])==50
        and certificate['structurally_complete_native_logs']==50 and certificate['incomplete_native_logs']==7,
        'Exact fixed50/7 integrity population required')
    source={row['run_id']:row for row in certificate['records'] if row['status']=='COMPLETE_NATIVE_LOG_ONLY'}
    require(set(source)=={row['run_id'] for row in manifest['runs']},'Explicit selection differs from complete native logs')
    rows={}
    for row in manifest['runs']:
        original=source[row['run_id']];header=original['scan']['native_run_headers']
        require(len(header)==1 and row['native_RunRecord']==header[0] and original['routing']['routing_ready'] is True
            and row['routing']==original['routing'] and row['SDK_raw_ref']==original['SDK_raw_ref']
            and row['native_exit_code'] in (0,1) and original['scan']['native_exit_codes']==[row['native_exit_code']]
            and original['scan']['clean_eof'] is True and original['scan']['partial_history_requests']==0,
            'Native routing/exit/framing source differs')
        require(row['routing']['run_id']==row['run_id']==header[0]['run_id']
            and row['routing']['project']==header[0]['project'] and row['routing']['project']
            and row['routing']['entity']==(header[0]['entity'] or 'mint_leaf258'),
            'Only original routing plus explicit empty-entity default admitted')
        require(row['history_rows']==original['scan']['history_rows']
            and row['first_explicit_step']==original['scan']['first_explicit_step']
            and row['last_explicit_step']==original['scan']['last_explicit_step']
            and row['expected_API_state']==('failed' if row['native_exit_code'] else 'finished'),
            'Original native history/step budget differs')
        rows[row['run_id']]=row
    return manifest,rows


def request_gate(request):
    require(request['schema']=='model_v3_selective_WandB_sync_request_v1'
        and request['eligible_manifest']==ref(HERE/'explicit50.json'), 'Explicit frozen50 request required')
    terminal=terminal_C0(request['integrity_terminal']);require(terminal['job_id']=='4521403','Integrity job differs')
    sup=read(request['integrity_supervisor'])
    require(str(sup['job_id'])=='4521403' and sup['status']=='COMPLETED' and sup['exit_code']==0
        and sup['first_failure'] is None and sup['remaining']==[],
        'Integrity source/process supervisor closure missing')
    if request['mode']=='batch':
        gate=request['pilot_gate'];pilot_terminal=terminal_C0(gate['actual_terminal'])
        result=read(gate['result']);pilot_sup=read(gate['supervisor'])
        require(result['status']=='SYNC_READBACK_CHILD_COMPLETED_PENDING_ROOT_C0' and result['mode']=='pilot'
            and len(result['records'])==1 and result['source_manifest']==request['source_manifest']
            and str(result['job_id'])==str(pilot_sup['job_id'])==str(pilot_terminal['job_id'])
            and gate['native_exit_code']==result['records'][0]['native_exit_code']
            and gate['actual_replay_verified']==(result['records'][0]['action']=='SYNCED_EXACT_COPY_AND_API_VERIFIED')
            and pilot_sup['status']=='COMPLETED' and pilot_sup['exit_code']==0
            and pilot_sup['first_failure'] is None and pilot_sup['remaining']==[],
            'Reviewed one-run actual C0 gate differs')
    else:require(request['mode']=='pilot' and len(request['selected_run_ids'])==1,'Only explicit single pilot before batching')


def allocation():
    job=os.environ.get('SLURM_JOB_ID','');node=os.environ.get('MODEL_V3_EXPECTED_NODE','')
    require(job.isdigit() and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==16
        and os.environ.get('SLURM_MEM_PER_NODE')=='16384' and os.environ.get('CUDA_VISIBLE_DEVICES')==''
        and socket.gethostname()==node and re.fullmatch(r'compute-0-(?:2|[89]|1[0-9])',node),
        'Actual owned CPU16/16GiB allocation/node with CUDA hidden required')
    group=Path('/proc/self/cgroup').read_text()
    require(re.search(r'(?:job[_/-])'+re.escape(job)+r'(?:/|\n|$)',group),'Actual own job cgroup required')
    return dict(job_id=job,node=node,uid=os.getuid(),cgroup=group)


def copy_exact(source,target):
    bind(source,128<<20);target=Path(target);target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    digest=hashlib.sha256();count=0
    with Path(source['path']).open('rb') as incoming,target.open('xb') as outgoing:
        for block in iter(lambda:incoming.read(1<<20),b''):
            count+=len(block);require(count<=source['bytes'],'SDK grew during copy')
            digest.update(block);outgoing.write(block)
        outgoing.flush();os.fsync(outgoing.fileno())
    require(count==source['bytes'] and digest.hexdigest()==source['sha256'],'Staged SDK differs')
    staged=ref(target,128<<20);require(staged['sha256']==source['sha256'],'Stage postcopy hash differs')
    bind(source,128<<20);return staged
