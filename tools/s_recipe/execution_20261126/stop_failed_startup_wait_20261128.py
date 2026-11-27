"""Request an existing Guard's USR1 exit for one proved own wait-only job."""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

ROOT=Path('/share/home/zixiao/descriptor_analysis')
R=ROOT/'MFM_s_recipe'
C=ROOT/'runs/s_recipe_20261120'
sys.path.insert(0,str(R/'tools/s_recipe'))
from fullft_startup_failure_20261127 import validate_failure,snapshots
from control_metadata_io_20261127 import write
read=lambda p:json.loads(Path(p).read_text())

REMOTE=r'''
import json,os,re,signal,subprocess,sys,time
from pathlib import Path
p=json.loads(sys.argv[1]); R=Path(p['repo']); C=Path(p['control'])
sys.path.insert(0,str(R/'tools/s_recipe'))
import lifecycle_20261122 as life
from fullft_startup_failure_20261127 import snapshots
from control_metadata_io_20261127 import write
task=json.loads(Path(p['task']).read_text()); pid=p['pid']; job=task['standby_job_id']
fields=lambda t:dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',t))
node=fields(subprocess.check_output(['/usr/bin/scontrol','show','node',p['node'],'-o'],text=True,timeout=8))
if any(x in node['State'] for x in ('DRAIN','DOWN','NOT_RESPONDING','FAIL')):raise ValueError('Unhealthy node')
info=fields(subprocess.check_output(['/usr/bin/scontrol','show','job',str(job),'-o'],text=True,timeout=8))
if (info.get('UserId')!='zixiao(1278)' or info.get('JobName')!=task['native_handle']
        or info.get('JobState')!='RUNNING' or info.get('NodeList')!=p['node']):
    raise ValueError('Exact own running standby required')
saved=life.identity(pid)
if not saved or saved.uid!=1278:raise ValueError('Wrong standby owner or absent process')
if p['expected_ticks'] is not None and saved.start_ticks!=p['expected_ticks']:raise ValueError('PID reused')
native=life.Identity(**task['producer'])
if life.same_process(native,life.identity(native.pid)):raise ValueError('Native still alive')
argv=Path('/proc/'+str(pid)+'/cmdline').read_bytes().rstrip(b'\0').decode().split('\0')
expected=['-B','-u','tools/s_recipe/fullft_native_execution_20261126.py','--task',p['task'],'--mode','standby']
if Path(argv[0]).resolve()!=Path(task['python']).resolve() or argv[1:]!=expected:
    raise ValueError('Not the exact wait-only command')
if Path('/proc/'+str(pid)+'/cwd').resolve()!=R:raise ValueError('Unexpected cwd')
cgroup=Path('/proc/'+str(pid)+'/cgroup').read_text()
if '/job_'+str(job)+'/step_batch' not in cgroup:raise ValueError('Wrong Slurm cgroup')
status=Path('/proc/'+str(pid)+'/status').read_text()
caught=int(re.search(r'^SigCgt:\s*([0-9a-f]+)',status,re.M).group(1),16)
if not caught & (1 << (signal.SIGUSR1-1)):raise ValueError('USR1 Guard handler absent')
handoff=json.loads(Path(task['handoff_request']).read_text())
if (handoff.get('native_handle')!=task['native_handle'] or handoff.get('standby_job_id')!=job
        or any(handoff.get('producer',{}).get(k)!=task['producer'][k] for k in ('pid','uid','start_ticks'))):
    raise ValueError('Existing entered-Guard handoff binding differs')
cfg=json.loads(Path(task['configuration']).read_text())
observed_files=snapshots(cfg)
# st_dev identifies a mount on one host: login /share is 2049, node20 is 49.
# Preserve exact inode, owner, size and nanosecond times across this shared path.
stable=lambda values:{n:{k:v for k,v in row.items() if k!='dev'} for n,row in values.items()}
if stable(observed_files)!=stable(p['files']):
    differences={name:{key:[p['files'][name].get(key),value.get(key)]
        for key in value if p['files'][name].get(key)!=value.get(key)}
        for name,value in observed_files.items()}
    raise ValueError('Cross-node metadata differs: '+json.dumps(differences))
row=json.loads((C/'execution.json').read_text())['statistics'][task['native_handle']]
if row.get('mode')!='finetune_native' or row.get('job_id') is not None:raise ValueError('Fit already took over')
value=dict(status='PROBED_OWN_WAIT_ONLY',producer=vars(saved),job_id=job,node=p['node'],
    native_handle=task['native_handle'],argv=argv,cgroup=cgroup,signal_caught_hex=hex(caught),
    files=p['files'],node_files=observed_files,observed_time=time.time(),native_verified_gone=True)
if p['request']:
    if p['expected_ticks'] is None:raise ValueError('Explicit probed start_ticks required')
    if not life.same_process(saved,life.identity(pid)):raise ValueError('Standby identity changed')
    target=C/(task['native_handle']+'_wait_exit_request_20261128.json')
    if target.exists():raise ValueError('Do not repeat the existing exit request')
    value.update(status='REQUESTING_EXISTING_GUARD_USR1',signal=int(signal.SIGUSR1))
    write(target,value)
    os.kill(pid,signal.SIGUSR1)
    value.update(status='EXISTING_GUARD_USR1_SENT',sent_time=time.time())
    write(target,value)
print(json.dumps(value))
'''

handle=sys.argv[1]; pid=int(sys.argv[2])
request=len(sys.argv)>3 and sys.argv[3]=='--request'
ticks=int(sys.argv[4]) if request else None
if os.getuid()!=1278 or not re.fullmatch(r'S_FT_[A-Za-z0-9_]+_attempt\d+',handle):
    raise ValueError('Exact own task required')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    row=read(C/'execution.json')['statistics'][handle]
    task=read(row['native_task']); cfg=read(row['configuration']); files=snapshots(cfg)
    validate_failure(handle,row,read(row['lifecycle_record']),cfg,task,files)
    payload=dict(repo=str(R),control=str(C),node=row['node'],task=row['native_task'],
        pid=pid,expected_ticks=ticks,request=request,files=files)
    command=shlex.join([task['python'],'-B','-c',REMOTE,json.dumps(payload)])
    result=subprocess.run(['/usr/bin/timeout','20s','ssh','-n','-o','BatchMode=yes',
        '-o','ConnectTimeout=3',row['node'],command],text=True,capture_output=True)
    if result.returncode:
        print(result.stderr.strip(),file=sys.stderr)
        raise SystemExit(result.returncode)
    value=json.loads(result.stdout)
    if not request:write(C/(handle+'_wait_exit_probe_20261128.json'),value)
    print(json.dumps(value),flush=True)
