"""Two exact cold-start recoveries: preserve held jobs and all early evidence."""
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import time
sys.path.insert(0,'/share/home/zixiao/descriptor_analysis/MFM_s_recipe/tools/s_recipe')
from storage_20261122 import CONTROL as C,REPO as R,write,claim_current
read=lambda path:json.loads(Path(path).read_text())
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
CASES={
 'readout':('S_final_s0_9M_readout_budget_2000000_attempt0',4540371,'_task.json','_native.log',
     'Fresh exact native readout contract required','readout_native_spawn_20261126.py'),
 'fullft':('S_FT_S_G1_3M_qm9_U0_atom_s2_attempt0',4540372,'_fullft_native_task.json','_fullft_native.log',
     'Exact fresh native fullFT contract required','fullft_native_spawn_20261126.py')}
kind=sys.argv[1]
handle,job,task_suffix,log_suffix,exception,spawner=CASES[kind]
if os.getuid()!=1278:raise ValueError('Only the actual owning UID')
def call(*argv):return subprocess.check_output(['/usr/bin/timeout','20s',*map(str,argv)],text=True).strip()
def remote(code):return call('ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3','compute-0-20',
    shlex.join([PY,'-B','-c',code]))
check=read(C/'native_clock_anchor_check_20261127.json')
parent_path=Path(check['native_record'])
parent=read(parent_path)
if (parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
        or read(parent_path.with_name('command_exit.json')).get('exit_code')!=0
        or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
    raise ValueError('The new clock checks must actually close before recovery')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    taskpath=C/(handle+task_suffix)
    controller=C/(handle+'_controller.json')
    task=read(taskpath)
    state=read(controller)
    config=read(task['configuration'])
    audit=C/'early_native_startup_recovery_20261127'
    audit.mkdir(exist_ok=True)
    receipt=audit/(handle+'.json')
    if receipt.exists():raise ValueError('Inspect the existing recovery; never repeat a spawn blindly')
    actual=call('/usr/bin/sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,State,ExitCode,ElapsedRaw')
    details=dict(re.findall(r'(?:^| )(\w+)=([^ ]*)',call('/usr/bin/scontrol','show','job',job,'-o')))
    logpath=C/(handle+log_suffix)
    log=logpath.read_text()
    native_path=Path(task['native_record'])
    output=Path(config['output'])
    phase_output=output/('readout_'+str(task['samples'])) if kind=='readout' else output
    phase=phase_output/'snapshot_gpu_status.json' if kind=='readout' else output/'summary.json'
    if (actual!=str(job)+'|PENDING|0:0|0' or details.get('UserId')!='zixiao(1278)'
            or details.get('JobName')!=handle or details.get('Reason')!='JobHeldUser'
            or task.get('standby_job_id')!=job or state.get('standby_job_id')!=job
            or config.get('node')!='compute-0-20' or state.get('phase')!='HELD_SUBMITTED'
            or native_path.exists() or Path(task['handoff_request']).exists()
            or ('ValueError: '+exception) not in log
            or logpath.is_symlink() or logpath.stat().st_uid!=1278
            or phase.exists() or (output/'complete_state.pt').exists() or (output/'prediction.pt').exists()):
        raise ValueError('Exact held-zero-work, pre-guard-failure evidence required')
    if phase_output.exists() and any(phase_output.iterdir()):
        raise ValueError('Unexpected existing scientific output requires inspection before a cold restart')
    expected=task['producer']
    code=('import sys,json;sys.path.insert(0,'+repr(str(R/'tools/s_recipe'))+
        ');import lifecycle_20261122 as l;s=l.Identity(**'+repr(expected)+
        ');print(json.dumps(dict(same=l.same_process(s,l.identity(s.pid)))))')
    if json.loads(remote(code))['same']:raise ValueError('Original native process is still present')
    # The original failure precedes Guard creation, model work and worker launch.
    # There is no wait status from that detached startup; do not invent one.
    archive=audit/(handle+'_original_stderr.log')
    if archive.exists():raise ValueError('Original stderr archive already exists')
    proof=dict(status='ORIGINAL_PRE_GPU_FAILURE_ARCHIVED_NEW_START_REQUESTED',handle=handle,
        original_task=task,original_controller=state,actual_held_job=actual,
        original_native_same_process=False,original_native_wait_exit_code=None,
        original_failure_before_guard_and_model_work=True,original_stderr=str(archive),
        clock_observation=str(C/'native_startup_clock_20261127.json'),new_allocation_submitted=False,
        scientific_settings_changed=False,scientific_work_replayed=False)
    write(receipt,proof)
    logpath.rename(archive)
    task=dict(task)
    task.pop('producer')
    task['contract']=dict(task['contract'],created_at=time.time())
    write(taskpath,task)
    argv=[PY,'-B',str(C/spawner),str(taskpath)]
    if kind=='readout':argv.append(PY)
    spawned=json.loads(call('ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=3','compute-0-20',shlex.join(argv)))
    if spawned['producer']['uid']!=1278:raise ValueError('Recovered producer owner differs')
    task['producer']=spawned['producer']
    write(taskpath,task)
    proof.update(new_producer=spawned['producer'],new_contract=task['contract'])
    write(receipt,proof)
    until=time.monotonic()+20
    while not native_path.exists():
        if time.monotonic()>=until:raise RuntimeError('Recovered startup uncertain; retain the same held job')
        time.sleep(.1)
    started=read(native_path)
    if any(started['producer'][key]!=spawned['producer'][key] for key in ('pid','uid','start_ticks')):
        raise ValueError('Recovered lifecycle belongs to another producer')
    if started.get('status')=='FAILED' or started.get('exit_code') not in (None,0):
        raise ValueError('Recovered lifecycle failed before release; retain the held job')
    call('/usr/bin/scontrol','release',job)
    state.update(phase='RELEASED',producer=spawned['producer'],released_at=time.time(),
        recovery_evidence=str(receipt))
    write(controller,state)
    ledger=read(C/'execution.json')
    ledger['statistics'][handle]=dict(state,status='RUNNING_NATIVE')
    write(C/'execution.json',ledger)
    proof.update(status='SAME_HELD_JOB_RELEASED_AFTER_VERIFIED_NEW_NATIVE_START',
        new_start_lifecycle=str(native_path),new_start_identity=started['producer'])
    write(receipt,proof)
    claim_current()
    print(json.dumps(dict(status=proof['status'],handle=handle,job_id=job,
        producer=spawned['producer'],new_allocation_submitted=False)),flush=True)
