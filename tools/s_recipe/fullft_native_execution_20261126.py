"""Finite mixed-node fullFT and exact same-task genuine Slurm takeover."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import re
import socket
import time
from types import SimpleNamespace
import lifecycle_20261122 as life
from storage_20261122 import CONTROL as C,write
from finetune_extension_20261124 import run as fit,query,validate
from fullft_startup_failure_20261127 import standby_terminal_action

read=lambda path:json.loads(Path(path).read_text())


def task_from_path(path):
    path=Path(path)
    if path.parent!=C or not path.name.endswith('_fullft_native_task.json'):
        raise ValueError('Exact S task path required')
    task=read(path)
    if path.name!=task['native_handle']+'_fullft_native_task.json':
        raise ValueError('Task file and native execution handle differ')
    c=validate(read(task['configuration']))
    if (os.getuid()!=1278 or c.get('execution_backend')!='mixed_gpu_native_20261126'
            or c['node']!=socket.gethostname().split('.')[0]
            or Path(task['configuration']).parent!=C or Path(task['native_record']).parent!=C
            or Path(task['handoff_request']).parent!=C):
        raise ValueError('Wrong owner, role or native task binding')
    return task,c


def native(path):
    until=time.monotonic()+5
    while True:
        task,c=task_from_path(path)
        if task.get('producer'):break
        if time.monotonic()>=until:raise RuntimeError('Native spawn identity was not published')
        time.sleep(.1)
    return fit(task['configuration'],native_context=task)


def standby(path):
    task,c=task_from_path(path)
    job=int(os.environ['SLURM_JOB_ID'])
    if job!=task['standby_job_id'] or int(os.environ['SLURM_CPUS_PER_TASK'])<c['cpus']:
        raise ValueError('This is not the actual same-task allocation')
    life.enable_subreaper()
    text=query(['/usr/bin/scontrol','show','job',str(job),'-o'],SimpleNamespace(requested=False))
    actual=dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',text))
    if (actual.get('JobId')!=str(job) or actual.get('UserId')!='zixiao(1278)'
            or actual.get('JobState')!='RUNNING' or actual.get('NodeList')!=c['node']
            or actual.get('TimeLimit')!='00:35:00'):
        raise ValueError('Actual finite same-task RUNNING allocation required')
    end=datetime.datetime.fromisoformat(actual['EndTime']).timestamp()
    guard=life.Guard(end,900)
    wait_record=C/(task['native_handle']+'_standby_wait_'+str(job)+'.json')
    state=dict(run=c['run'],job_id=job,node=c['node'],status='WAITING_NATIVE_OWNED_EXIT',
        producer=vars(life.identity(os.getpid())),started_at=time.time(),actual_deadline_epoch=end)
    with guard:
        try:
            write(Path(task['handoff_request']),dict(run=c['run'],native_handle=task['native_handle'],
                standby_job_id=job,producer=task['producer'],requested_at=time.time()))
            while True:
                value=read(task['native_record']) if Path(task['native_record']).exists() else {}
                expected=life.Identity(**task['producer'])
                saved=value.get('producer')
                if (saved and not life.same_process(expected,life.Identity(**saved))):
                    raise ValueError('Native closure belongs to a different producer')
                if (value.get('ended_at') and value.get('owned_descendants_exited')
                        and value.get('observer_joined')
                        and not life.same_process(expected,life.identity(expected.pid))):
                    break
                if guard.stopping():
                    state['status']='WAITING_CONTINUATION_REQUIRED'
                    return 75
                time.sleep(.5)
            action=standby_terminal_action(value)
            if action=='STOP_UNKNOWN_EXIT':
                state['status']='NATIVE_UNKNOWN_EXIT_NO_FIT_REPLAY'
                return 1
            if action=='NO_REPLAY':
                state['status']='NATIVE_ALREADY_COMPLETE_NO_FIT_REPLAY'
                return 0
            state['status']='NATIVE_CLOSED_READY_FOR_ACTUAL_SLURM_FIT'
        finally:
            guard.phase='closing'
            life.close_children(180)
            state.update(ended_at=time.time(),owned_descendants_exited=True)
            write(wait_record,state)
    # Leave the wait Guard before entering the original fitting Guard.
    with (C/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        ledger=read(C/'execution.json')
        row=ledger['statistics'][task['native_handle']]
        if row.get('standby_job_id')!=job:raise ValueError('Takeover ledger differs')
        row.update(mode='finetune',job_id=job,status='RUNNING_TAKEOVER',
            native_origin_record=task['native_record'],
            lifecycle_record=str(C/(c['run']+'_guarded_'+str(job)+'.json')))
        write(C/'execution.json',ledger)
    return fit(task['configuration'])


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--task',type=Path,required=True)
    parser.add_argument('--mode',choices=('native','standby'),required=True)
    args=parser.parse_args()
    raise SystemExit(native(args.task) if args.mode=='native' else standby(args.task))
