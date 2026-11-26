"""Activate only after all old fits settle and new CPU integration actually0."""
import fcntl
import os
import sys
import time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis')
sys.path.insert(0,str(ROOT/'MFM_s_recipe/tools/s_recipe'))
from storage_20261122 import CONTROL as C,REPO as R,write
from control_metadata_io_20261127 import write
from fullft_ram_envelope_20261127 import SCHEMA,PROOF,read,require_closed_proof
if os.getuid()!=1278:raise ValueError('Exact own account only')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    active=[k for k,v in read(C/'execution.json')['statistics'].items()
        if v.get('mode') in ('finetune','finetune_native') and not v.get('resource_closed')]
    if active:raise ValueError('Wait for actual natural fullFT exit and resource closure: '+repr(active))
    proof=require_closed_proof()
    check=read(C/'future_fullft_resources_check_20261127.json')
    parent=read(check['native_record'])
    command=read(Path(check['native_record']).with_name('command_exit.json'))
    if (check.get('new_tests')!=2 or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
            or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
            or not parent.get('observer_joined')):
        raise ValueError('Actual new integration checks must close before activation')
    path=C/'current_state.json';state=read(path)
    state['future_fullft_ram_policy']=SCHEMA
    write(path,state)
    value=dict(status='FUTURE_FULLFT_POLICY_ACTIVATED_AT_IDLE_BOUNDARY',observed_time=time.time(),
        policy=SCHEMA,estimate_source=str(PROOF),estimated_peak_bytes=proof['estimate']['estimated_concurrent_host_peak_bytes'],
        future_peak_ram_bytes=proof['future_peak_ram_bytes'],integration_check=check,
        actual_cpu_integration_exit=parent,old_active_fullFT_handles=active,
        active_reservations_changed=False,pretraining_reservations_changed=False,
        scientific_protocol_changed=False,legacy_dispatch_enabled=False)
    write(C/'future_fullft_resource_activation_20261127.json',value)
    write(R/'results/s_recipe/future_fullft_resource_activation_20261127.json',value)
    print(__import__('json').dumps(value),flush=True)
