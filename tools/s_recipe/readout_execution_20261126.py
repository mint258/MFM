"""Original layer6 probes on ordinary GPUs or finite mixed-node native work."""
import argparse
import csv
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import resource
import socket
import sys
import threading
import time
from types import SimpleNamespace
import lifecycle_20261122 as life
from storage_20261122 import CONTROL as C,ROOT,write
from storage_line_20261122 import admit
from finetune_extension_20261124 import query
from readout_task_20261126 import binding,native_guard,native_closed

read=lambda path:json.loads(Path(path).read_text())


def load_task(path):
    path=Path(path)
    task=read(path)
    if path!=C/(task['handle']+'_task.json') or os.getuid()!=1278:
        raise ValueError('Exact owned readout task file required')
    c=read(task['configuration'])
    binding(task,c)
    if (task['run']!=c['run'] or c['node']!=socket.gethostname().split('.')[0]
            or c.get('gpu_uuid')!=os.environ.get('CUDA_VISIBLE_DEVICES')
            or task['native']!=(c['node'] in ('compute-0-20','compute-0-22'))):
        raise ValueError('Wrong actual readout node/UUID/backend')
    return task,c


def registered(task,c):
    binding(task,c)
    if task['role']=='budget':
        from budget_readouts_extension_20261124 import registered as validate
        validate(c,task['samples'])
    else:
        from terminal_readouts_20261122 import registered as validate
        from extension_training_20261124 import validate as extension
        from storage_20261122 import REPO as R
        base=R/'configs/s_recipe'/('screening/S-R1.json' if c['extension_kind']=='E1' else 'confirmation/S-final.json')
        extension(c,read(base),read(c['population']))
        validate(c,task['samples'])


def actual_guard(task,c):
    job=int(os.environ['SLURM_JOB_ID'])
    expected=task['standby_job_id'] if task['native'] else task['job_id']
    if job!=expected or int(os.environ['SLURM_CPUS_PER_TASK'])<16:
        raise ValueError('Actual exact readout allocation required')
    text=query(['/usr/bin/scontrol','show','job',str(job),'-o'],SimpleNamespace(requested=False))
    values=dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',text))
    if (values.get('JobId')!=str(job) or values.get('UserId')!='zixiao(1278)'
            or values.get('NodeList')!=c['node'] or values.get('JobState')!='RUNNING'
            or values.get('TimeLimit')!='02:00:00'):
        raise ValueError('Actual healthy finite RUNNING readout allocation required')
    return life.Guard(datetime.datetime.fromisoformat(values['EndTime']).timestamp(),900)


def gpu_work(task,c,guard,record):
    if task['role']=='budget':
        from budget_readouts_extension_20261124 import work
        return work(c,task['samples'],'gpu',guard)
    import readouts
    import snapshot_readouts_20261122 as original
    started=time.monotonic()
    with original.evaluation_scope(readouts,guard):
        for count in c['evaluation_samples']:
            original.boundary(guard,'formal_extension_checkpoint_readout')
            readouts.gpu(readouts.configuration(c,count))
    summary=read(Path(c['output'])/'summary.json')
    summary.update(status='GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS',
        gpu_readout_seconds_this_process=time.monotonic()-started,
        gpu_readout_job=record['job_id'],gpu_readout_node=c['node'],
        gpu_readout_execution=dict(resource_handle=task['handle'],execution=record['execution'],
            producer=record['producer'],lifecycle_record=record['lifecycle_record']))
    write(Path(c['output'])/'summary.json',summary)
    return dict(status='GPU_TERMINAL_COMPLETE_WAITING_CPU',layer=6,samples=task['samples'])


def gpu(task,c,native):
    registered(task,c)
    life.enable_subreaper()
    guard=native_guard(task,c) if native else actual_guard(task,c)
    usage_start=(resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN))
    output,phase=binding(task,c)
    job=None if native else int(os.environ['SLURM_JOB_ID'])
    path=Path(task['native_record']) if native else C/(task['handle']+'_guarded_'+str(job)+'.json')
    record=dict(run=c['run'],role=task['role'],samples=task['samples'],node=c['node'],
        gpu_uuid=c['gpu_uuid'],job_id=job,resource_handle=task['handle'],
        native_handle=task['handle'] if native else None,execution='native_gpu' if native else 'Slurm',
        producer=vars(life.identity(os.getpid())),started_at=time.time(),status='PREPARING',
        lifecycle_record=str(path),actual_deadline_epoch=guard.end_epoch,closing_reserve_seconds=900,
        cpus_requested=16,slurm_cpus_allocated=0 if native else int(os.environ['SLURM_CPUS_PER_TASK']))
    write(path,record)
    done=threading.Event()
    def observe():
        while not done.wait(30):
            try:
                admit(c)
                request=Path(task['handoff_request'])
                if native and request.exists():
                    value=read(request)
                    if (value.get('handle')!=task['handle'] or value.get('job_id')!=task['standby_job_id']
                            or value.get('producer')!=task['producer']):
                        raise ValueError('Readout handoff belongs to another producer')
                    guard.request('actual_same_task_Slurm_takeover')
            except Exception as error:
                record['observer_error']=type(error).__name__+': '+str(error)
                guard.request('readout_observation_failed')
    observer=threading.Thread(target=observe,daemon=False)
    lock=None
    admitted=False
    with guard:
        try:
            admit(c)
            admitted=True
            lockpath=ROOT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(c['gpu_uuid']+'.lock')
            lock=lockpath.open('a')
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            rows=list(csv.reader(query(['/usr/bin/nvidia-smi','--id='+c['gpu_uuid'],
                '--query-gpu=uuid,name,memory.used,memory.total','--format=csv,noheader,nounits'],
                SimpleNamespace(requested=False)).splitlines()))
            if len(rows)!=1 or rows[0][0].strip()!=c['gpu_uuid']:
                raise ValueError('Actual readout GPU identity differs')
            if float(rows[0][2])/float(rows[0][3])>.30 or float(rows[0][3])-float(rows[0][2])<18432:
                raise ValueError('Actual readout GPU memory no longer qualifies')
            from snapshot_readouts_20261122 import check_gpu_context
            check_gpu_context(c['node'],c['gpu_uuid'])
            record['gpu_metadata_at_start']=rows[0]
            observer.start()
            record.update(gpu_work(task,c,guard,record),exit_code=0)
            return 0
        except life.StopAtBoundary:
            record.update(status='PAUSED_READOUT',exit_code=75,reason=guard.reason)
            return 75
        except BaseException as error:
            record.update(status='FAILED',exit_code=1,error=type(error).__name__+': '+str(error))
            raise
        finally:
            guard.phase='closing'
            done.set()
            if observer.ident is not None:observer.join()
            life.close_children(180)
            if lock is not None:lock.close()
            record.update(ended_at=time.time(),owned_descendants_exited=True,
                observer_joined=not observer.is_alive(),
                peak_RSS_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024)
            usage_end=(resource.getrusage(resource.RUSAGE_SELF),resource.getrusage(resource.RUSAGE_CHILDREN))
            record.update(cpu_user_seconds=sum(end.ru_utime-start.ru_utime for start,end in zip(usage_start,usage_end)),
                cpu_system_seconds=sum(end.ru_stime-start.ru_stime for start,end in zip(usage_start,usage_end)))
            torch=sys.modules.get('torch')
            if torch is not None and torch.cuda.is_initialized():
                try:
                    record.update(peak_cuda_allocated_bytes=torch.cuda.max_memory_allocated(),
                        peak_cuda_reserved_bytes=torch.cuda.max_memory_reserved())
                except Exception as error:
                    record['memory_observation_error']=type(error).__name__+': '+str(error)
            write(path,record)
            if admitted:
                output.mkdir(parents=True,exist_ok=True)
                write(output/phase,record)


def native(path):
    until=time.monotonic()+5
    while True:
        task,c=load_task(path)
        if task.get('producer'):break
        if time.monotonic()>=until:raise RuntimeError('Native readout spawn identity was not published')
        time.sleep(.1)
    return gpu(task,c,True)


def standby(path):
    task,c=load_task(path)
    life.enable_subreaper()
    guard=actual_guard(task,c)
    job=int(os.environ['SLURM_JOB_ID'])
    value=None
    with guard:
        try:
            write(task['handoff_request'],dict(handle=task['handle'],job_id=job,producer=task['producer']))
            while True:
                if Path(task['native_record']).exists():
                    value=read(task['native_record'])
                    current=life.identity(task['producer']['pid'])
                    if native_closed(task,value,current):break
                if guard.stopping():return 75
                time.sleep(.5)
        finally:
            guard.phase='closing'
            life.close_children(180)
    if value['exit_code']==0 and value['status'] in ('GPU_SNAPSHOT_COMPLETE_WAITING_CPU','GPU_TERMINAL_COMPLETE_WAITING_CPU'):
        return 0
    if value['exit_code']!=75 or value['status']!='PAUSED_READOUT':
        raise ValueError('Native readout did not close a safe committed-cell boundary')
    with (C/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        ledger=read(C/'execution.json')
        row=ledger['statistics'][task['handle']]
        if row.get('standby_job_id')!=job:raise ValueError('Readout takeover ledger differs')
        row.update(mode='gpu',job_id=job,status='RUNNING_TAKEOVER',native_origin_record=task['native_record'],
            lifecycle_record=str(C/(task['handle']+'_guarded_'+str(job)+'.json')))
        write(C/'execution.json',ledger)
    return gpu(task,c,False)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--task',type=Path,required=True)
    parser.add_argument('--mode',choices=('native','standby','ordinary'),required=True)
    args=parser.parse_args()
    if args.mode=='native':code=native(args.task)
    elif args.mode=='standby':code=standby(args.task)
    else:
        task,c=load_task(args.task)
        if task['native']:raise ValueError('Mixed nodes require native plus same-task standby')
        code=gpu(task,c,False)
    raise SystemExit(code)
