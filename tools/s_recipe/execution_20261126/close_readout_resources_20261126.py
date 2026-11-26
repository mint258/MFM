"""Settle only the exact registered readout resource and unused standby."""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
ROOT=Path('/share/home/zixiao/descriptor_analysis')
C=ROOT/'runs/s_recipe_20261120'
R=ROOT/'MFM_s_recipe'
sys.path.insert(0,str(R/'tools/s_recipe'))
from storage_20261122 import claim_current,write
read=lambda path:json.loads(Path(path).read_text())
def call(*args):return subprocess.check_output(['/usr/bin/timeout','15s',*map(str,args)],text=True).strip()
def fields(raw):return dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',raw))
handle=sys.argv[1]
if os.getuid()!=1278 or not re.fullmatch(r'S_[A-Za-z0-9_]+_readout_(?:budget|terminal)_\d+_attempt\d+',handle):
    raise ValueError('Exact registered owned fit handle required')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=read(C/'execution.json')
    row=ledger['statistics'][handle]
    if row.get('resource_closed'):
        print(json.dumps(dict(status='ALREADY_CLOSED',handle=handle)),flush=True)
        raise SystemExit(0)
    if row.get('mode') not in ('gpu','gpu_native'):raise ValueError('Not an owned fit')
    path=Path(row['lifecycle_record'])
    if not path.exists():
        print(json.dumps(dict(status='WAITING_FIT_CLOSURE',handle=handle)),flush=True)
        raise SystemExit(0)
    closure=read(path)
    if (not closure.get('ended_at') or not closure.get('owned_descendants_exited')
            or not closure.get('observer_joined') or closure.get('exit_code') not in (0,75)
            or closure.get('status') not in ('GPU_SNAPSHOT_COMPLETE_WAITING_CPU','GPU_TERMINAL_COMPLETE_WAITING_CPU','PAUSED_READOUT')):
        print(json.dumps(dict(status='WAITING_COMPLETE_OWNED_EXIT',handle=handle)),flush=True)
        raise SystemExit(0)
    if row.get('job_id') is None:
        task=read(row['native_task'])
        expected=task['producer']
        if (closure.get('native_handle')!=handle or closure.get('run')!=row['run']
                or any(expected[key]!=closure['producer'][key] for key in ('pid','uid','start_ticks'))):
            raise ValueError('Native closure does not match the actual task producer')
        code=('import sys,json;sys.path.insert(0,'+repr(str(R/'tools/s_recipe'))+
            ');import lifecycle_20261122 as l;s=l.Identity(**'+repr(expected)+
            ');print(json.dumps(dict(same=l.same_process(s,l.identity(s.pid)))))')
        alive=json.loads(call('ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',row['node'],
            shlex.join(['/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python','-B','-c',code])))
        if alive['same']:raise ValueError('The native producer is still the same live PID')
        job=row['standby_job_id']
        closepath=C/(handle+'_resource_close.json')
        progress=read(closepath) if closepath.exists() else {}
        actual=call('/usr/bin/sacct','-X','-n','-P','-j',job,'--format=State,ExitCode,ElapsedRaw')
        if actual=='PENDING|0:0|0' and not progress.get('cancel_requested'):
            before=fields(call('/usr/bin/scontrol','show','job',job,'-o'))
            if before.get('UserId')!='zixiao(1278)' or before.get('JobName')!=handle or before.get('JobState')!='PENDING':
                raise ValueError('Unused standby is not the exact own pending job')
            call('/usr/bin/scontrol','hold',job)
            held=fields(call('/usr/bin/scontrol','show','job',job,'-o'))
            if (held.get('UserId')!='zixiao(1278)' or held.get('JobState')!='PENDING'
                    or held.get('Reason')!='JobHeldUser'
                    or call('/usr/bin/sacct','-X','-n','-P','-j',job,'--format=ElapsedRaw')!='0'):
                raise ValueError('Standby crossed the verified zero-work boundary')
            write(closepath,dict(cancel_requested=True,standby_job_id=job,handle=handle))
            call('/usr/bin/scancel',job)
            actual=call('/usr/bin/sacct','-X','-n','-P','-j',job,'--format=State,ExitCode,ElapsedRaw')
        failed_path=C/(handle+'_failed_standby_exit_20261127.json')
        failed=read(failed_path) if failed_path.exists() else {}
        failed_closed=(closure['exit_code']==0 and actual=='FAILED|1:0|1'
            and failed.get('status')=='FAILED_STANDBY_OWN_PROCESS_EXIT_CONFIRMED'
            and failed.get('handle')==handle and failed.get('job_id')==job
            and failed.get('actual')==actual and failed.get('node')==row['node']
            and failed.get('before_GPU_work') is True
            and failed.get('observation',{}).get('matching_job_processes')==[]
            and failed.get('observation',{}).get('observation_errors')==[]
            and failed.get('observation',{}).get('native_same_process') is False
            and all(failed.get('native_successful_producer',{}).get(key)==expected[key]
                    for key in ('pid','uid','start_ticks')))
        if not (actual.startswith('CANCELLED by 1278|0:0|0')
                or (closure['exit_code']==0 and actual.startswith('COMPLETED|0:0|'))
                or failed_closed):
            print(json.dumps(dict(status='WAITING_ACTUAL_STANDBY_SETTLEMENT',handle=handle,actual=actual)),flush=True)
            raise SystemExit(0)
    else:
        actual=call('/usr/bin/sacct','-X','-n','-P','-j',row['job_id'],'--format=State,ExitCode')
        if actual not in ('COMPLETED|0:0','FAILED|75:0'):
            print(json.dumps(dict(status='WAITING_ACTUAL_SOURCE_TERMINAL',handle=handle,actual=actual)),flush=True)
            raise SystemExit(0)
    config=read(row['configuration'])
    task=read(row['native_task'])
    from readout_task_20261126 import binding
    output,phase=binding(task,config)
    if closure.get('samples')!=row['samples'] or closure.get('role')!=row['role']:
        raise ValueError('Closed reader belongs to another checkpoint or role')
    if closure['exit_code']==0:
        value=read(output/phase)
        if (value.get('resource_handle')!=handle or value.get('run')!=row['run']
                or value.get('samples')!=row['samples']
                or value.get('status') not in ('GPU_SNAPSHOT_COMPLETE_WAITING_CPU','GPU_TERMINAL_COMPLETE_WAITING_CPU')
                or value.get('job_id')!=closure.get('job_id')
                or any(value['producer'][key]!=closure['producer'][key] for key in ('pid','uid','start_ticks'))):
            raise ValueError('Phase result does not match its actual closed producer')
    budget=read(C/'storage_additional_entries.json')
    ids=set(row['resource_ids'])
    if any(identifier not in {entry['id'] for entry in budget['entries']} for identifier in ids):
        raise ValueError('Inspect a changed resource registration before retiring it')
    budget['entries']=[entry for entry in budget['entries'] if entry['id'] not in ids]
    write(C/'storage_additional_entries.json',budget)
    claim_current()
    row.update(resource_closed=True,status='COMPLETE' if closure['exit_code']==0 else 'PAUSED_SAFE_CONTINUATION',
        resource_close_actual=actual)
    write(C/'execution.json',ledger)
    write(C/(handle+'_resource_close.json'),dict(status='OWN_RESOURCES_CLOSED',handle=handle,
        exit_code=closure['exit_code'],run=row['run'],samples=row['samples'],role=row['role'],
        phase_record=str(path),retired_ids=sorted(ids),actual=actual,files_deleted=False,
        failed_standby_evidence=str(failed_path) if row.get('job_id') is None and failed_closed else None))
    print(json.dumps(dict(status='OWN_RESOURCES_CLOSED',handle=handle,exit_code=closure['exit_code'],files_deleted=False)),flush=True)
