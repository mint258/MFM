"""Bounded metadata primitives. Importing this module performs no admission."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import time

PROJECT=Path('/share/home/zixiao/descriptor_analysis')
N=PROJECT/'runs/model_v3_20261026'
OLD=PROJECT/'runs/model_v3_20261025'
HERE=Path(__file__).absolute().parent
V2=N/'native_s_precision_storage_adapter_v2'
RUNTIME=PROJECT/'MFM_model_v3_native_s_runtime_v1'
PYTHON=PROJECT/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python'
DEPS=PROJECT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'
CODE='3d9b1cc0c580dacc9398a5570b0c2fff3e257618'
TREE='73a9e47af34aa6e46c2b421c946b1dc39209a584'
PUBLIC='ce7cbf5776ff546cd47538b120c8f884e2e5867d'
GPU='GPU-22e21021-e572-4562-fc51-cd8c83e74141'
NODE='compute-0-21'
LOCK=PROJECT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
OUTER=2<<30
CHILD=OUTER-(96<<20)
PRIVATE=2<<30
RSS=28<<30
WALL=1100
CHILD_WALL=1000
V2_PIN='97951800a9770d11777c4bf1ab89409167eefde506f2381f9433574a9cb02cc2'

def require(value,message):
    if not value: raise ValueError(message)

def encoded(value):
    return (json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def binding(path,maximum=2<<20):
    path=Path(path).absolute()
    require(not any(p.is_symlink() for p in (path,*path.parents)),'Symlink metadata/source refused')
    info=path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid==os.getuid() and info.st_nlink==1 and info.st_size<=maximum,
        'Owned bounded regular file required: '+str(path))
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''): value.update(block)
    after=path.stat()
    require((info.st_ino,info.st_dev,info.st_size,info.st_mtime_ns)==
        (after.st_ino,after.st_dev,after.st_size,after.st_mtime_ns),'File changed during binding')
    return dict(path=str(path),bytes=info.st_size,sha256=value.hexdigest())

def read(path):
    ref=binding(path)
    def reject(value):raise ValueError('Nonfinite JSON token: '+value)
    value=json.loads(Path(ref['path']).read_bytes(),parse_constant=reject)
    require(binding(path)==ref,'Metadata changed during read')
    return value

def read_ref(ref):
    require(binding(ref['path'])==ref,'Bound metadata differs')
    return read(ref['path'])

def write(path,value):
    path=Path(path); path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with path.open('xb') as stream:
        stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
    return binding(path)

def replace_feed(path,value):
    path=Path(path); temporary=path.with_name(path.name+'.'+str(os.getpid())+'.tmp')
    with temporary.open('xb') as stream:
        stream.write(encoded(value)); stream.flush(); os.fsync(stream.fileno())
    os.replace(temporary,path)

def actual(argv,*,check=True,timeout=20,env=None):
    start=time.time()
    try:
        result=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=timeout,env=env)
        row=dict(argv=list(map(str,argv)),started_unix=start,completed_unix=time.time(),
            returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
    except (OSError,subprocess.TimeoutExpired) as error:
        row=dict(argv=list(map(str,argv)),started_unix=start,completed_unix=time.time(),returncode=None,
            stdout='',stderr=str(error),exception=type(error).__name__)
    require(len(encoded(row))<1<<20,'Raw command exceeds metadata budget')
    if check: require(row['returncode']==0,'Command failed: '+repr(row))
    return row

def fresh(row,now=None,seconds=120):
    now=time.time() if now is None else now
    require(-5<=now-row['completed_unix']<=seconds and row['started_unix']<=row['completed_unix'],
        'Admission observation stale/future')

def runtime_environment(*,cpu=False,contract=None):
    value={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'8','MKL_NUM_THREADS':'8',
        'OPENBLAS_NUM_THREADS':'8','NUMEXPR_NUM_THREADS':'8',
        'PYTHONPATH':':'.join(map(str,[HERE,V2,RUNTIME/'current',RUNTIME/'current/tests',RUNTIME/'tools/model_v3',
            RUNTIME/'workflows/sprime_s/scripts',DEPS])),
        'CUDA_VISIBLE_DEVICES':'' if cpu else GPU}
    if cpu:value['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    if contract is not None: value['MODEL_V3_NATIVE_S_RUNTIME_CONTRACT']=str(contract)
    return value

def verify_package(path=HERE,expected=None):
    path=Path(path); ref=binding(path/'source_pins.json')
    if expected is not None: require(ref['sha256']==expected,'Package manifest raw SHA differs')
    manifest=read_ref(ref)
    for row in manifest['files']:
        target=Path(row['path']); require(not target.is_absolute() and '..' not in target.parts,'Relative source leaf required')
        actual_ref=binding(path/target)
        require(actual_ref['sha256']==row['sha256'] and actual_ref['bytes']==row['bytes'],'Frozen package source differs')
    if manifest.get('dependency_manifest'):
        dependencies=read(path/manifest['dependency_manifest'])
        for row in dependencies['references']:
            require(binding(row['path'])==row,'Frozen external dependency/evidence bytes differ: '+row['path'])
    return ref,manifest

def root_identity():
    require(os.getuid()==1278 and socket.gethostname()=='sonmi','Root coordinator must run on actual sonmi as project UID')

def terminal_rows(raw,job):
    require(raw['returncode']==0 and '-j' in raw['argv'] and raw['argv'][raw['argv'].index('-j')+1]==str(job),
        'Actual exact-job accounting command required')
    rows=[x.split('|') for x in raw['stdout'].splitlines() if x.split('|')[0]==str(job)]
    require(len(rows)==1 and len(rows[0])>=3,'Unique parent accounting row required')
    require(re.fullmatch(r'\d+:\d+',rows[0][2]),'Unknown raw Slurm exit code')
    return rows[0][1:3]

def require_C0(raw,job):
    require(terminal_rows(raw,job)==['COMPLETED','0:0'],'Actual QA parent is not C0')

def normalized_uuid(value):
    value=str(value).strip()
    return value if value.startswith('GPU-') else 'GPU-'+value
