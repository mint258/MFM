"""Original extension endpoint statistics after real GPU success/owned exit."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
ROOT=Path('/share/home/zixiao/descriptor_analysis')
C=ROOT/'runs/s_recipe_20261120'
R=ROOT/'MFM_s_recipe'
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
sys.path.insert(0,str(R/'tools/s_recipe'))
from storage_20261122 import write
from readout_task_20261126 import EXTENSIONS
read=lambda path:json.loads(Path(path).read_text())
run,node,cores=sys.argv[1:4]
attempt=int(sys.argv[4]) if len(sys.argv)>4 else 0
if os.getuid()!=1278 or run not in EXTENSIONS or attempt<0:
    raise ValueError('Only registered new extension endpoints')
handle=run+'_terminal_statistics_native_20261126_attempt'+str(attempt)
controller=C/(handle+'_controller.json')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if controller.exists():
        print(json.dumps(read(controller)),flush=True)
        raise SystemExit(0)
    output=C/'training'/run
    summary=read(output/'summary.json')
    if summary.get('status')=='COMPLETE':
        print(json.dumps(dict(status='ALREADY_COMPLETE',run=run)),flush=True)
        raise SystemExit(0)
    gpu=read(output/'readout/terminal_gpu_status.json')
    if (gpu.get('run')!=run or gpu.get('samples')!=EXTENSIONS[run]
            or gpu.get('status')!='GPU_TERMINAL_COMPLETE_WAITING_CPU'
            or not gpu.get('owned_descendants_exited') or not gpu.get('ended_at')):
        raise ValueError('Exact full-budget GPU phase must actually close')
    if gpu.get('job_id') is not None:
        actual=subprocess.check_output(['/usr/bin/timeout','15s','/usr/bin/sacct','-X','-n','-P',
            '-j',str(gpu['job_id']),'--format=State,ExitCode'],text=True).strip()
        if actual!='COMPLETED|0:0':raise ValueError('GPU allocation did not actually succeed')
    else:
        resource_handle=gpu.get('resource_handle')
        if not resource_handle or gpu.get('native_handle')!=resource_handle:
            raise ValueError('Missing native producer handle')
        close=read(C/(resource_handle+'_resource_close.json'))
        if (close.get('status')!='OWN_RESOURCES_CLOSED' or close.get('exit_code')!=0
                or close.get('handle')!=resource_handle or close.get('run')!=run
                or close.get('samples')!=EXTENSIONS[run] or close.get('role')!='terminal'):
            raise ValueError('Native GPU producer/unused standby has not actually settled')
    previous=output/'readout/terminal_statistics_status.json'
    if previous.exists():
        old=read(previous)
        if not old.get('owned_descendants_exited') or not old.get('ended_at'):
            raise ValueError('Inspect previous unclosed terminal statistics')
        if old.get('execution')=='native_cpu':
            previous_directory=C/'native_cpu_20261126'/old['handle']
            previous_record=read(previous_directory/'record.json')
            previous_command=read(previous_directory/'command_exit.json')
            if (not previous_record.get('owned_descendants_exited') or not previous_record.get('observer_joined')
                    or previous_record.get('exit_code') is None or previous_command.get('exit_code') is None):
                raise ValueError('Previous native statistics parent must actually close')
        else:raise ValueError('Inspect an unknown previous statistics execution identity')
        archive=C/'attempt_archive'/handle
        archive.mkdir(parents=True,exist_ok=False)
        write(archive/'previous_statistics_status.json',old)
    c=read(output/'configuration.json')
    ledger=read(C/'execution.json')
    c.update(training_closure_record=ledger['runs'][run]['lifecycle_record'])
    source=C/(handle+'_configuration.json')
    write(source,c)
    launched=json.loads(subprocess.check_output([PY,'-B',str(C/'launch_cpu_native_20261126.py'),
        'terminal',handle,node,cores,str(source)],text=True))
    state=dict(run=run,mode='terminal_cpu_native',job_id=None,node=node,
        native_handle=handle,lifecycle_record=launched['record'],configuration=str(source),
        phase='NATIVE_STARTED',gpu_source_execution=dict(job_id=gpu.get('job_id'),native_handle=gpu.get('native_handle')))
    write(controller,state)
    ledger['statistics'][handle]=state
    write(C/'execution.json',ledger)
    print(json.dumps(state),flush=True)
