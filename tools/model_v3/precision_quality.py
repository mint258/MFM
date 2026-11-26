"""Own precision tasks, NFS disk guard and complete-state SSH/Slurm handoff."""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

REPO=Path(__file__).resolve().parents[2]
BASE=REPO.parent
ROOT=REPO/'results/precision_20261115'
sys.path.insert(0,str(REPO/'tools/p_recipe'))
from native_run import identity
from execution_ledger import read,write
import v2_diagnosis_disk as disk


def capacity():
    allocated=sum(p.stat().st_blocks*512 for p in ROOT.rglob('*') if p.is_file())
    remaining=max(200_000_000,18_000_000_000-allocated)
    disk.m.require_capacity(disk.m.filesystem_status('/'),0,0)
    disk.m.require_capacity(disk.m.filesystem_status(ROOT),remaining,10000)
    disk.m.quota_headroom(disk.CONTROL/'share_quota_available_v3.json','/share',remaining,disk.remaining_nfs_other())


def acquire(task):
    gpu=task['gpu_uuid']
    lock=(BASE/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')).open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    raw=subprocess.check_output(['nvidia-smi','-i',gpu,'--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],text=True)
    used,total=map(float,raw.strip().split(','))
    if used/total>.30 or total-used<18432:raise RuntimeError('GPU memory admission failed')
    pids=subprocess.check_output(['nvidia-smi','-i',gpu,'--query-compute-apps=pid','--format=csv,noheader,nounits'],text=True).splitlines()
    for pid in pids:
        command=subprocess.run(['ps','-p',pid.strip(),'-o','args='],capture_output=True,text=True).stdout
        if any(name in command for name in ('tools/p_recipe/train.py','native_run.py','precision_study.py','precision_quality.py')):
            raise RuntimeError('A model/P process already uses the selected GPU: '+command)
    return lock,used,total


def run(task,configuration,*,slurm=False):
    if task['node']=='compute-0-21':raise RuntimeError('User excludes compute-0-21 from this study')
    if socket.gethostname().split('.')[0]!=task['node']:raise RuntimeError('Wrong target node')
    if not slurm and task['node'] not in ('compute-0-20','compute-0-21','compute-0-22'):
        raise RuntimeError('Native sharing is authorized only on development nodes20-22')
    capacity()
    lock,used,total=acquire(task)
    c=read(configuration)
    if slurm and int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<c['workers']+2:
        raise RuntimeError('Insufficient real Slurm CPU allocation')
    environment=dict(os.environ,CUDA_VISIBLE_DEVICES=task['gpu_uuid'],PYTHONDONTWRITEBYTECODE='1',
        PYTHONHASHSEED='0',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',
        PYTHONPATH=str(REPO/'current')+':'+str(BASE/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'),
        PHASE1_NATIVE_TRANSPORT_PATH=str(BASE/'docs/phase1/evidence/stage48_full_corpus_qa/native_qa_stats_v3.py'),
        PHASE1_JOINT_REFERENCE_PATH=str(BASE/'docs/phase1/evidence/stage50_full_corpus_training/actual_api_reference/full_corpus_training.py'))
    if not slurm:
        for key in tuple(environment):
            if key.startswith('SLURM_'):environment.pop(key)
    temporary=BASE/('.pq_'+str(os.getpid()))
    temporary.mkdir();environment['TMPDIR']=str(temporary)
    command=task.get('command') or [task['python'],'-B','-u','tools/p_recipe/train.py','--configuration',str(configuration)]
    child=subprocess.Popen(command,cwd=REPO,env=environment,start_new_session=True)
    bound=identity(child.pid)
    state=task['slurm_state'] if slurm else task['native_state']
    record=dict(**bound,status='RUNNING',run=c['run'],node=task['node'],gpu_uuid=task['gpu_uuid'],
        started_at=time.time(),execution='Slurm' if slurm else 'native_SSH',admission_used_mib=used,total_mib=total,
        command=command,job_id=int(os.environ['SLURM_JOB_ID']) if slurm else None)
    write(state,record)
    paused=False
    while child.poll() is None:
        try:capacity();ok=True
        except (OSError,ValueError,KeyError,TypeError) as error:
            ok=False;record['disk_reason']=str(error)
        if ok==paused and child.poll() is None:
            if identity(child.pid)!=bound:raise RuntimeError('Child identity changed')
            os.killpg(bound['pgid'],signal.SIGCONT if ok else signal.SIGSTOP);paused=not ok
        record['status']='DISK_PAUSED' if paused else 'RUNNING';write(state,record)
        time.sleep(5)
    code=child.wait()
    record.update(status='COMPLETED' if code==0 else 'FAILED',exit_code=code,ended_at=time.time(),elapsed_seconds=time.time()-record['started_at'])
    write(state,record);lock.close()
    return code


def standby(task):
    if not os.environ.get('SLURM_JOB_ID'):raise RuntimeError('A real Slurm allocation is required')
    from scheduled_run import handoff
    result=handoff(task,int(os.environ['SLURM_JOB_ID']))
    if result is None:return 0
    original,native,ack=result
    while True:
        try:
            if identity(native['pid'])=={k:native[k] for k in ('pid','uid','start_ticks','pgid')}:
                time.sleep(1);continue
        except FileNotFoundError:pass
        break
    c=dict(original,resume=ack['checkpoint'])
    c.pop('handoff_request',None);c.pop('handoff_ack',None)
    destination=ROOT/'control'/(c['run']+'_resume_'+os.environ['SLURM_JOB_ID']+'.json')
    write(destination,c)
    while True:
        try:
            return run(task,destination,slurm=True)
        except BlockingIOError:time.sleep(1)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=('native','standby','slurm'));p.add_argument('--task',required=True)
    a=p.parse_args();task=read(a.task)
    raise SystemExit(standby(task) if a.action=='standby' else run(task,task['configuration'],slurm=a.action=='slurm'))
