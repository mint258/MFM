"""Light controller: fresh actual idle/RAM/disk admission, then owned SSH CPU."""
import fcntl
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis')
R=ROOT/'MFM_s_recipe'
C=ROOT/'runs/s_recipe_20261120'
sys.path.insert(0,str(R/'tools/s_recipe'))
from storage_20261122 import claim_current,write

PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
PATHS=':'.join(map(str,(R/'current',R/'tools/s_recipe',
    ROOT/'runs/data_v1_20261025/repository',
    ROOT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps')))
stage,handle,node,core_text=sys.argv[1:5]
source=sys.argv[5] if len(sys.argv)>5 else None
cores=[int(item) for item in core_text.split(',')]
if (os.getuid()!=1278 or node not in {'compute-0-'+str(i) for i in (9,11,12,13,19)}
        or stage not in ('terminal','budget_statistics','matrix','population','publish','import','fullft_statistics','extension_progress','extension_daily','generic_publish','writer_admission_check','budget_adapter_check','native_output_check','fullft_provider_inspection','mixed_fullft_check','mixed_fullft_binding_check','fullft_resume_check','execution_delivery','readout_runtime_check','readout_delivery','budget_validation_curve','standby_settlement_check','e1_frozen_report')
        or not 1<=len(set(cores))==len(cores)<=16
        or not handle.replace('_','').isalnum() or not handle.startswith('S_')):
    raise ValueError('Explicit owned registered native CPU stage required')

def call(*args,timeout=25):
    return subprocess.check_output(['/usr/bin/timeout',str(timeout)+'s',*map(str,args)],text=True).strip()

def remote(command,timeout=25):
    return call('ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=5',node,command,timeout=timeout)

def environment():
    return 'env CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 OMP_NUM_THREADS='+str(len(cores))+\
        ' MKL_NUM_THREADS='+str(len(cores))+' OPENBLAS_NUM_THREADS='+str(len(cores))+\
        ' NUMEXPR_NUM_THREADS='+str(len(cores))+' PYTHONPATH='+shlex.quote(PATHS)+' '

directory=C/'native_cpu_20261126'/handle
with (C/'native_cpu_launch_20261126.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (directory/'configuration.json').exists():
        print(json.dumps(dict(status='EXISTING_HANDLE',handle=handle,
            record=str(directory/'record.json'))),flush=True)
        raise SystemExit(0)
    fields=dict(part.split('=',1) for part in call('/usr/bin/scontrol','show','node',node,'-o').split() if '=' in part)
    if any(value in fields['State'] for value in ('DRAIN','DOWN','NOT_RESPONDING','FAIL')):
        raise ValueError('Fault nodes are excluded; SSH never bypasses drain')
    # All replaced allocations must have actually remained unstarted.
    for job in (4539794,4539803,4539934,4539994,4540068):
        actual=call('/usr/bin/sacct','-X','-n','-P','-j',job,'--format=State,ElapsedRaw')
        if not actual.startswith('CANCELLED by 1278|0'):
            raise ValueError('Old zero-runtime queue must be actually cancelled before native entry')
    peak=(16 if stage in ('terminal','budget_statistics') else 4)*1024**3
    expected=3600 if stage in ('terminal','budget_statistics','fullft_statistics') else 1200 if stage=='population' else 60
    hard=max(2*expected,1800)
    cleanup=900 if stage in ('terminal','budget_statistics','population','fullft_statistics') else 180
    if stage in ('terminal','budget_statistics','fullft_statistics'):
        if source is None or Path(source).parent!=C:
            raise ValueError('Bind the existing owned terminal CPU configuration')
    elif source is not None:
        raise ValueError('This metadata stage does not take a source override')
    budget=C/'storage_additional_entries.json'
    forecast=json.loads(budget.read_text())
    active_peak=0
    for prior in (C/'native_cpu_20261126').glob('*/configuration.json'):
        other=json.loads(prior.read_text())
        if other['node']!=node:
            continue
        proof=prior.parent/'record.json'
        closed=json.loads(proof.read_text()) if proof.exists() else {}
        if closed.get('owned_descendants_exited') is True:
            continue
        if set(other['cores']) & set(cores):
            raise ValueError('A previous owned CPU handle still holds these cores; inspect before retry')
        active_peak+=other['peak_ram_bytes']
    for kind,path,need in (('node_ram',None,max(48*1024**3,active_peak+peak)),('node_disk','/',128*1024**2)):
        existing=sum(e['bytes'] for e in forecast['entries'] if e['kind']==kind and
                     e.get('node')==node and e.get('path')==path)
        if existing<need:
            entry=dict(id='S_native_CPU_20261126_'+node+'_'+kind,kind=kind,node=node,bytes=need-existing)
            if path is not None:entry['path']=path
            forecast['entries'].append(entry)
    write(budget,forecast)
    claim_current()
    # Run this observation on the actual target CPU node, never the login node.
    probe='''import json,os,time,socket
from pathlib import Path
from storage_line_20261122 import admit
def sample():
 result={}
 for line in Path('/proc/stat').read_text().splitlines():
  p=line.split()
  if p and p[0].startswith('cpu') and p[0][3:].isdigit():
   v=list(map(int,p[1:9]));result[int(p[0][3:])]=(sum(v),v[3])
 return result
a=sample();started=time.time();time.sleep(5);b=sample()
cores=CORES
ratios={str(k):(b[k][1]-a[k][1])/max(1,b[k][0]-a[k][0]) for k in cores}
mem=next(int(p.split()[1])*1024 for p in Path('/proc/meminfo').read_text().splitlines() if p.startswith('MemAvailable:'))
if any(v<.95 for v in ratios.values()) or mem<PEAK+4*1024**3:raise ValueError('Selected cores/RAM are not actually idle/available')
reports=admit(dict(peak_ram_bytes=PEAK))
fs={}
for path in ('/','/tmp',TARGET):
 s=os.statvfs(path);fs[path]=dict(available_bytes=s.f_bavail*s.f_frsize,total_bytes=s.f_blocks*s.f_frsize,available_inodes=s.f_favail)
print(json.dumps(dict(node=socket.gethostname(),observed_time=time.time(),measurement_seconds=time.time()-started,core_idle=ratios,MemAvailable=mem,filesystems=fs,admission=reports)))
'''.replace('CORES',repr(cores)).replace('PEAK',str(peak)).replace('TARGET',repr(str(C)))
    observed=json.loads(remote(environment()+PY+' -B -c '+shlex.quote(probe)))
    directory.mkdir(parents=True,exist_ok=False)
    c=dict(authority='docs/interfaces/SCHEDULING_RULE_20261126.md',stage=stage,handle=handle,
        node=node,cores=cores,cpus=len(cores),peak_ram_bytes=peak,expected_seconds=expected,
        hard_seconds=hard,cleanup_seconds=cleanup,source_configuration=source,preflight=observed)
    write(directory/'configuration.json',c)
    # timeout is a last bound. The native guard closes earlier and proves owned exit.
    body='\n'.join([
        'set -uo pipefail',
        'export S_NATIVE_CPU_HARD_END=$(( $(date +%s) + '+str(hard)+' - 5 ))',
        '/usr/bin/timeout --signal=TERM '+str(hard)+'s '+PY+' -B -u '+
            shlex.quote(str(R/'tools/s_recipe/cpu_native_20261126.py'))+' --configuration '+
            shlex.quote(str(directory/'configuration.json')),
        'native_exit=$?',
        "printf '{\"exit_code\":%s,\"ended_at\":%s}\\n' \"$native_exit\" \"$(date +%s)\" > "+
            shlex.quote(str(directory/'command_exit.json')),
        'exit "$native_exit"'])
    command='cd '+shlex.quote(str(R))+'\n'+environment()+\
        'setsid nohup /usr/bin/taskset -c '+shlex.quote(core_text)+' /bin/bash -c '+shlex.quote(body)+\
        ' > '+shlex.quote(str(directory/'run.log'))+' 2>&1 < /dev/null &\nprintf "%s\\n" "$!"'
    wrapper_pid=int(remote(command))
    write(directory/'controller.json',dict(phase='START_REQUESTED',node=node,cores=cores,
        handle=handle,wrapper_pid=wrapper_pid,started_request_at=time.time(),configuration=str(directory/'configuration.json')))
    state_path=C/'current_state.json'
    state=json.loads(state_path.read_text())
    state.setdefault('native_cpu_jobs',{})[handle]=dict(stage=stage,node=node,cores=cores,
        wrapper_pid=wrapper_pid,job_id=None,record=str(directory/'record.json'),
        configuration=str(directory/'configuration.json'))
    state['cpu_scheduling_authority']='docs/interfaces/SCHEDULING_RULE_20261126.md'
    state['short_cpu_replaced_zero_runtime_jobs']=[4539794,4539803,4539934,4539994,4540068]
    write(state_path,state)
    print(json.dumps(dict(handle=handle,stage=stage,node=node,cores=cores,
        wrapper_pid=wrapper_pid,record=str(directory/'record.json'),
        observed_idle=observed['core_idle'],MemAvailable=observed['MemAvailable'])),flush=True)
