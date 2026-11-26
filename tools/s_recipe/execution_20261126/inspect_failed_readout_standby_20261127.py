"""One bounded, read-only settlement of actual failed waiter4540347."""
import json
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import time
ROOT=Path('/share/home/zixiao/descriptor_analysis')
C=ROOT/'runs/s_recipe_20261120'
HANDLE='S_E1_k2_s0_3M_readout_terminal_3000000_attempt0'
JOB=4540347
read=lambda path:json.loads(Path(path).read_text())

if len(sys.argv)>1:
    if (sys.argv[1:]!=['--observe','4540347','452854','89755429']
            or os.getuid()!=1278 or socket.gethostname().split('.')[0]!='compute-0-20'):
        raise ValueError('Only the exact actual failed waiter/node/native owner')
    if os.environ.get('SLURM_JOB_ID'):
        raise ValueError('This read-only SSH observer must be outside a Slurm task')
    ancestors=set()
    current=os.getpid()
    while current>1 and current not in ancestors:
        ancestors.add(current)
        try:current=int((Path('/proc')/str(current)/'stat').read_text().rsplit(')',1)[1].split()[1])
        except (FileNotFoundError,ProcessLookupError):break
    connection_parents=set()
    for pid in ancestors:
        own=Path('/proc')/str(pid)
        try:
            if own.stat().st_uid==1278 and (own/'comm').read_text().strip()=='sshd':
                connection_parents.add(int((own/'stat').read_text().rsplit(')',1)[1].split()[1]))
        except (FileNotFoundError,ProcessLookupError):continue
    matches=[]
    errors=[]
    observer_ancestors=[]
    user_services=[]
    for path in Path('/proc').iterdir():
        if not path.name.isdecimal():continue
        try:
            if path.stat().st_uid!=1278:continue
            env=(path/'environ').read_bytes().split(b'\0')
            if b'SLURM_JOB_ID=4540347' in env:matches.append(int(path.name))
        except (FileNotFoundError,ProcessLookupError):continue
        except OSError as error:
            if isinstance(error,PermissionError) and int(path.name) in ancestors:
                observer_ancestors.append(int(path.name))
            elif isinstance(error,PermissionError):
                try:
                    parent=int((path/'stat').read_text().rsplit(')',1)[1].split()[1])
                    own_connection=(path/'comm').read_text().strip()=='sshd' and parent in connection_parents
                except (FileNotFoundError,ProcessLookupError):continue
                if own_connection:observer_ancestors.append(int(path.name))
                else:
                    name=(path/'comm').read_text().strip()
                    cgroup=(path/'cgroup').read_text()
                    pam_service=(name=='(sd-pam)'
                        and '0::/user.slice/user-1278.slice/user@1278.service/init.scope' in cgroup.splitlines()
                        and (Path('/proc')/str(parent)/'comm').read_text().strip()=='systemd')
                    value=dict(pid=int(path.name),ppid=parent,name=name,cgroup=cgroup)
                    if pam_service:user_services.append(value)
                    else:errors.append(dict(value,error=type(error).__name__))
            else:errors.append(dict(pid=int(path.name),error=type(error).__name__))
    native=Path('/proc/452854')
    try:
        stat=(native/'stat').read_text().rsplit(')',1)[1].split()
        same=native.stat().st_uid==1278 and int(stat[19])==89755429
    except (FileNotFoundError,ProcessLookupError):same=False
    print(json.dumps(dict(node='compute-0-20',uid=1278,observed_time=time.time(),
        matching_job_processes=matches,observation_errors=errors,native_same_process=same,
        unreadable_observer_connection_members=observer_ancestors,
        observer_connection_parent_ids=sorted(connection_parents),
        unreadable_user_session_services=user_services,observer_outside_Slurm=True)),flush=True)
    raise SystemExit(0)

if os.getuid()!=1278:raise ValueError('Exact own account required')
destination=C/(HANDLE+'_failed_standby_exit_20261127.json')
if destination.exists():
    print(json.dumps(dict(status='ALREADY_OBSERVED',evidence=str(destination))),flush=True)
    raise SystemExit(0)
row=read(C/'execution.json')['statistics'][HANDLE]
task=read(row['native_task'])
closed=read(task['native_record'])
if (row.get('job_id') is not None or row.get('standby_job_id')!=JOB
        or row.get('node')!='compute-0-20' or task.get('handle')!=HANDLE
        or closed.get('exit_code')!=0 or closed.get('status')!='GPU_TERMINAL_COMPLETE_WAITING_CPU'
        or not closed.get('ended_at') or not closed.get('owned_descendants_exited')
        or not closed.get('observer_joined')
        or any(task['producer'][key]!=closed['producer'][key] for key in ('pid','uid','start_ticks'))):
    raise ValueError('Exact successful real native reader must already close')
def call(*args):return subprocess.check_output(['/usr/bin/timeout','15s',*map(str,args)],text=True).strip()
health=call('/usr/bin/scontrol','show','node','compute-0-20','-o')
info=dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',health))
if any(s in info['State'] for s in ('DRAIN','DOWN','NOT_RESPONDING','FAIL')):
    raise ValueError('Never probe through unhealthy-node exclusion')
actual=call('/usr/bin/sacct','-n','-P','-j',JOB,
    '--format=JobIDRaw,User,JobName%128,State,ExitCode,NodeList,ElapsedRaw')
rows=[line.split('|') for line in actual.splitlines()]
expected=[str(JOB),'zixiao',HANDLE,'FAILED','1:0','compute-0-20','1']
if (expected not in rows or not any(r[0]==str(JOB)+'.batch' and r[3:5]==['FAILED','1:0'] for r in rows)
        or not any(r[0]==str(JOB)+'.extern' and r[3:5]==['COMPLETED','0:0'] for r in rows)):
    raise ValueError('Actual parent, batch and extern terminal accounting differs')
log=C/(HANDLE+'_'+str(JOB)+'.log')
failure=log.read_text()
if ("AttributeError: 'str' object has no attribute 'with_name'" not in failure
        or "write(task['handoff_request']" not in failure or "code=standby(args.task)" not in failure
        or Path(task['handoff_request']).exists()):
    raise ValueError('Failure is not the observed pre-GPU request-write failure')
observed=json.loads(call('/usr/bin/ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',
    'compute-0-20',shlex.join(['/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python',
        '-B',str(Path(__file__)),'--observe','4540347','452854','89755429'])))
if (observed['matching_job_processes'] or observed['observation_errors']
        or observed['native_same_process']):
    print(json.dumps(observed),flush=True)
    raise ValueError('Actual own process absence is not established')
sys.path.insert(0,str(ROOT/'MFM_s_recipe/tools/s_recipe'))
from storage_20261122 import write
value=dict(status='FAILED_STANDBY_OWN_PROCESS_EXIT_CONFIRMED',handle=HANDLE,run=row['run'],
    job_id=JOB,node=row['node'],actual='FAILED|1:0|1',original_job_exit_code='1:0',
    source_accounting=actual,source_log=str(log),observation=observed,
    native_successful_producer=closed['producer'],native_source=task['native_record'],
    before_GPU_work=True,processes_signalled=False,files_deleted=False,
    engineering_failure='String path passed to atomic writer before standby GPU work; fixed future entry only',
    failure_source_commit='417c60defd415b33f44122c8d24634bd57eb1b7f')
write(destination,value)
print(json.dumps(dict(status=value['status'],evidence=str(destination),observation=observed)),flush=True)
