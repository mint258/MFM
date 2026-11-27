"""Retire a proved unchanged partial fit's failed startup; preserve unknown exit."""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
ROOT=Path('/share/home/zixiao/descriptor_analysis')
C=ROOT/'runs/s_recipe_20261120'
R=ROOT/'MFM_s_recipe'
sys.path.insert(0,str(R/'tools/s_recipe'))
from fullft_startup_failure_20261127 import (POLICY,STATUS,validate_failure,snapshots,
    require_pending,retire_entries,validate_wait_exit)
from storage_20261122 import claim_current
from control_metadata_io_20261127 import write
read=lambda p:json.loads(Path(p).read_text())
def call(*args):
    return subprocess.check_output(['/usr/bin/timeout','15s',*map(str,args)],text=True).strip()
def fields(raw):return dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',raw))
handle=sys.argv[1]
if os.getuid()!=1278 or not re.fullmatch(r'S_FT_[A-Za-z0-9_]+_attempt\d+',handle):
    raise ValueError('Exact own registered failed startup required')
check=read(C/'fullft_startup_failure_check_20261127.json')
parent=read(check['native_record'])
command=read(Path(check['native_record']).with_name('command_exit.json'))
if (check.get('policy')!=POLICY or check.get('new_tests')!=12
        or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
        or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
        or not parent.get('observer_joined')):
    raise ValueError('Actual successful new boundary checks required first')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=read(C/'execution.json')
    row=ledger['statistics'][handle]
    if row.get('resource_closed'):
        print(json.dumps(dict(status='ALREADY_CLOSED',handle=handle)),flush=True)
        raise SystemExit(0)
    closure=read(row['lifecycle_record'])
    configuration=read(row['configuration'])
    task=read(row['native_task'])
    value=validate_failure(handle,row,closure,configuration,task,snapshots(configuration))
    node=fields(call('/usr/bin/scontrol','show','node',row['node'],'-o'))
    if any(flag in node['State'] for flag in ('DRAIN','DOWN','NOT_RESPONDING','FAIL')):
        raise ValueError('No SSH workaround for an unhealthy node')
    expected=task['producer']
    code=('import sys,json;sys.path.insert(0,'+repr(str(R/'tools/s_recipe'))+
        ');import lifecycle_20261122 as l;s=l.Identity(**'+repr(expected)+
        ');print(json.dumps(dict(same=l.same_process(s,l.identity(s.pid)))))')
    alive=json.loads(call('ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',row['node'],
        shlex.join([task['python'],'-B','-c',code])))
    if alive.get('same') is not False:raise ValueError('Exact native producer has not been verified gone')
    progress_path=C/(handle+'_startup_failure_retirement.json')
    progress=read(progress_path) if progress_path.exists() else {}
    if progress and any(progress.get(k)!=v for k,v in value.items()):
        raise ValueError('The failed startup or saved state changed during settlement')
    job=row['standby_job_id']
    actual=call('/usr/bin/sacct','-X','-n','-P','-j',job,'--format=State,ExitCode,ElapsedRaw')
    if actual=='PENDING|0:0|0' and not progress.get('cancel_requested'):
        info=fields(call('/usr/bin/scontrol','show','job',job,'-o'))
        require_pending(info,actual,handle,job)
        call('/usr/bin/scontrol','hold',job)
        info=fields(call('/usr/bin/scontrol','show','job',job,'-o'))
        require_pending(info,call('/usr/bin/sacct','-X','-n','-P','-j',job,
            '--format=State,ExitCode,ElapsedRaw'),handle,job,held=True)
        progress=dict(value,cancel_requested=True,native_producer_verified_gone=True)
        write(progress_path,progress)
        call('/usr/bin/scancel',job)
        actual=call('/usr/bin/sacct','-X','-n','-P','-j',job,'--format=State,ExitCode,ElapsedRaw')
    wait_proof={}
    if not actual.startswith('CANCELLED by 1278|0:0|0'):
        wait_path=C/(handle+'_standby_wait_'+str(job)+'.json')
        if not actual.startswith(('FAILED|75:0|','FAILED|1:0|')) or not wait_path.is_file():
            print(json.dumps(dict(status='WAITING_ACTUAL_UNUSED_STANDBY_SETTLEMENT',handle=handle,
                actual=actual)),flush=True)
            raise SystemExit(0)
        info=fields(call('/usr/bin/scontrol','show','job',job,'-o'))
        if (info.get('UserId')!='zixiao(1278)' or info.get('JobName')!=handle
                or info.get('JobState')!='FAILED' or info.get('NodeList')!=row['node']):
            raise ValueError('Exact own failed wait-only allocation required')
        if (C/(row['run']+'_guarded_'+str(job)+'.json')).exists():
            raise ValueError('Standby entered a fitting lifecycle; inspect it separately')
        wait=read(wait_path)
        wait_proof=validate_wait_exit(handle,row,wait,actual)
        waiting=wait['producer']
        code=('import sys,json;sys.path.insert(0,'+repr(str(R/'tools/s_recipe'))+
            ');import lifecycle_20261122 as l;s=l.Identity(**'+repr(waiting)+
            ');print(json.dumps(dict(same=l.same_process(s,l.identity(s.pid)))))')
        gone=json.loads(call('ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',row['node'],
            shlex.join([task['python'],'-B','-c',code])))
        if gone.get('same') is not False:raise ValueError('Wait-only producer has not been verified gone')
        wait_proof['standby_wait_producer_verified_gone']=True
    expected_entries=[dict(id=handle+'_node_ram',kind='node_ram',node=row['node'],
            bytes=configuration['peak_ram_bytes']),
        dict(id=handle+'_node_disk',kind='node_disk',node=row['node'],path='/',bytes=32*1024**2)]
    if set(row['resource_ids'])!={entry['id'] for entry in expected_entries}:
        raise ValueError('Changed owned resource handle list')
    budget=read(C/'storage_additional_entries.json')
    updated=retire_entries(budget['entries'],expected_entries,
        allow_absent=progress.get('retirement_started') is True)
    progress=dict(value,cancel_requested=actual.startswith('CANCELLED by 1278|0:0|0'),
        native_producer_verified_gone=True,retirement_started=True,standby_actual=actual,
        retired_ids=row['resource_ids'])
    progress.update(wait_proof)
    write(progress_path,progress)
    budget['entries']=updated
    write(C/'storage_additional_entries.json',budget)
    claim_current()
    receipt=dict(progress,status='FAILED_STARTUP_OWN_RESOURCES_CLOSED',observed_time=time.time(),
        files_deleted=False,scientific_updates_in_this_startup=0,
        original_native_record_modified=False)
    receipt_path=C/(handle+'_startup_failure_settlement.json')
    write(receipt_path,receipt)
    row.update(resource_closed=True,status=STATUS,startup_failure_receipt=str(receipt_path),
        resource_close_actual=actual,actual_native_exit_code=None,exit_code_observed=False)
    write(C/'execution.json',ledger)
    write(C/(handle+'_resource_close.json'),receipt)
    print(json.dumps(dict(status=receipt['status'],handle=handle,standby_actual=actual,
        actual_native_exit_code=None,files_deleted=False)),flush=True)
