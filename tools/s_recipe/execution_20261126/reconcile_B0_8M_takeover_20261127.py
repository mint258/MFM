"""Rebind one actually closed takeover; no model work, signals or deletions."""
import fcntl
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys
sys.path.insert(0,'/share/home/zixiao/descriptor_analysis/MFM_s_recipe/tools/s_recipe')
from storage_20261122 import CONTROL as C, REPO as R, write
read=lambda path:json.loads(Path(path).read_text())
handle='S_B0_s0_9M_readout_budget_8000000_attempt0'
job=4540365
def call(*args):return subprocess.check_output(['/usr/bin/timeout','15s',*map(str,args)],text=True).strip()
check=read(C/'metadata_lock_check_20261127.json')
parent_path=Path(check['native_record'])
parent=read(parent_path)
if (parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
        or read(parent_path.with_name('command_exit.json')).get('exit_code')!=0
        or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
    raise ValueError('Actual cross-host metadata lock check must close first')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    ledger=read(C/'execution.json')
    row=ledger['statistics'][handle]
    if row.get('job_id')==job:
        print(json.dumps(dict(status='ALREADY_RECONCILED',handle=handle)),flush=True)
        raise SystemExit(0)
    original=dict(row)
    task=read(row['native_task'])
    native=read(task['native_record'])
    guard_path=C/(handle+'_guarded_'+str(job)+'.json')
    guard=read(guard_path)
    phase=read(C/'training/S_B0_s0_9M/readout_8000000/snapshot_gpu_status.json')
    actual=call('/usr/bin/sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode')
    details=dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',call('/usr/bin/scontrol','show','job',job,'-o')))
    if (actual!=str(job)+'|COMPLETED|0:0' or details.get('UserId')!='zixiao(1278)'
            or details.get('JobName')!=handle or details.get('NodeList')!='compute-0-20'
            or task.get('standby_job_id')!=job or row.get('standby_job_id')!=job
            or row.get('job_id') is not None or row.get('resource_closed')
            or native.get('status')!='PAUSED_READOUT' or native.get('exit_code')!=75
            or guard.get('status')!='GPU_SNAPSHOT_COMPLETE_WAITING_CPU' or guard.get('exit_code')!=0
            or any(not p.get('owned_descendants_exited') or not p.get('observer_joined') for p in (native,guard))
            or any(guard.get(key)!=value or phase.get(key)!=value for key,value in dict(
                run='S_B0_s0_9M',samples=8000000,role='budget',job_id=job,resource_handle=handle).items())
            or any(native['producer'][key]!=task['producer'][key] or row['producer'][key]!=task['producer'][key]
                for key in ('pid','uid','start_ticks'))
            or guard['producer']!=phase['producer']):
        raise ValueError('Exact original paused-native and completed actual Slurm receipts required')
    code=('import sys,json;sys.path.insert(0,'+repr(str(R/'tools/s_recipe'))+
        ');import lifecycle_20261122 as l;s=l.Identity(**'+repr(task['producer'])+
        ');print(json.dumps(dict(same=l.same_process(s,l.identity(s.pid)))))')
    observed=json.loads(call('ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3',row['node'],
        shlex.join(['/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python','-B','-c',code])))
    if observed['same']:raise ValueError('Original native producer is still live')
    proof=dict(status='ACTUAL_CLOSED_TAKEOVER_RECONCILED',handle=handle,job_id=job,
        old_row=original,actual=actual,actual_closed_producer=str(guard_path),
        native_exit=task['native_record'],native_same_process=False,
        cross_host_lock_proof=str(C/'metadata_lock_check_20261127.json'),
        scientific_outputs_changed=False,new_fits=0,new_bootstrap_draws=0)
    write(C/'B0_8M_takeover_reconciliation_20261127.json',proof)
    row.update(mode='gpu',job_id=job,status='COMPLETE_TAKEOVER_RESOURCES_PENDING',
        native_origin_record=task['native_record'],lifecycle_record=str(guard_path),
        reconciliation_evidence=str(C/'B0_8M_takeover_reconciliation_20261127.json'))
    write(C/'execution.json',ledger)
    print(json.dumps(dict(status=proof['status'],handle=handle,job_id=job)),flush=True)
