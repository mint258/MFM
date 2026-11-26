"""Start one required original9M trajectory statistic after real GPU closure."""
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
from budget_readouts_extension_20261124 import registered
read=lambda path:json.loads(Path(path).read_text())
run,sample_text,node,cores=sys.argv[1:5]
samples=int(sample_text)
attempt=int(sys.argv[5]) if len(sys.argv)>5 else 0
if (os.getuid()!=1278 or run not in ('S_B0_s0_9M','S_final_s0_9M')
        or samples not in range(1000000,9000000,1000000) or attempt<0):
    raise ValueError('Explicit original trajectory point and actual owner required')
handle=run+'_budget_'+str(samples)+'_statistics_native_20261126_attempt'+str(attempt)
controller=C/(handle+'_controller.json')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if controller.exists():
        print(json.dumps(read(controller)),flush=True)
        raise SystemExit(0)
    metadata=read(C/'current_state.json')
    if not metadata.get('extension_registration_published'):
        raise ValueError('Publish the registration before new statistics')
    ledger=read(C/'execution.json')
    c=read(C/'training'/run/'configuration.json')
    c.update(readout_authority='docs/s_recipe/USER_DIRECTIVE_20261123C.md',
        training_closure_record=ledger['runs'][run]['lifecycle_record'])
    registered(c,samples)
    output=Path(c['output'])/('readout_'+str(samples))
    gpu=read(output/'snapshot_gpu_status.json')
    if (gpu.get('run')!=run or gpu.get('samples')!=samples
            or gpu.get('status')!='GPU_SNAPSHOT_COMPLETE_WAITING_CPU'
            or not gpu.get('owned_descendants_exited') or not gpu.get('ended_at')):
        raise ValueError('Wait for a closed actual original GPU readout')
    if gpu.get('job_id') is not None:
        actual=subprocess.check_output(['/usr/bin/timeout','15s','/usr/bin/sacct','-X','-n','-P',
            '-j',str(gpu['job_id']),'--format=State,ExitCode'],text=True).strip()
        if actual!='COMPLETED|0:0':raise ValueError('Original GPU allocation has not succeeded')
    else:
        resource_handle=gpu.get('resource_handle')
        if not resource_handle or gpu.get('native_handle')!=resource_handle:
            raise ValueError('Missing actual native readout identity')
        close=read(C/(resource_handle+'_resource_close.json'))
        if (close.get('status')!='OWN_RESOURCES_CLOSED' or close.get('exit_code')!=0
                or close.get('handle')!=resource_handle or close.get('run')!=run
                or close.get('samples')!=samples or close.get('role')!='budget'):
            raise ValueError('Native readout and its unused standby must actually settle')
    previous=output/'snapshot_statistics_status.json'
    if previous.exists():
        old=read(previous)
        if old.get('status')=='COMPLETE':
            print(json.dumps(dict(status='ALREADY_COMPLETE',source=str(previous))),flush=True)
            raise SystemExit(0)
        if (not old.get('owned_descendants_exited') or not old.get('ended_at')
                or old.get('status') not in ('FAILED','PAUSED_READOUT')):
            raise ValueError('Inspect an unclosed previous statistics producer')
        if old.get('native_record'):
            old_record=read(old['native_record'])
            old_exit=read(Path(old['native_record']).with_name('command_exit.json'))
            if (not old_record.get('owned_descendants_exited') or not old_record.get('observer_joined')
                    or old_record.get('exit_code') is None or old_exit.get('exit_code') is None):
                raise ValueError('Previous native CPU execution must actually close')
        elif old.get('job_id'):
            old_actual=subprocess.check_output(['/usr/bin/timeout','15s','/usr/bin/sacct','-X','-n','-P',
                '-j',str(old['job_id']),'--format=State'],text=True).strip()
            if not old_actual.startswith(('FAILED','CANCELLED','COMPLETED')):
                raise ValueError('Previous CPU allocation has not closed')
        else:raise ValueError('Unknown previous execution identity')
        archive=C/'attempt_archive'/handle
        archive.mkdir(parents=True,exist_ok=False)
        write(archive/'previous_statistics_status.json',old)
    c.update(node=node,gpu_uuid='',peak_ram_bytes=16*1024**3,readout_samples=samples)
    source=C/(handle+'_configuration.json')
    write(source,c)
    launched=json.loads(subprocess.check_output([PY,'-B',str(C/'launch_cpu_native_20261126.py'),
        'budget_statistics',handle,node,cores,str(source)],text=True))
    state=dict(phase='NATIVE_SPAWNED',mode='budget_cpu_native',run=run,samples=samples,
        node=node,job_id=None,native_handle=handle,lifecycle_record=launched['record'],
        configuration=str(source),upstream_gpu_job=gpu['job_id'])
    write(controller,state)
    ledger['statistics'][handle]=state
    write(C/'execution.json',ledger)
    print(json.dumps(state),flush=True)
