import fcntl
import os
import sys
import time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis')
sys.path.insert(0,str(ROOT/'MFM_s_recipe/tools/s_recipe'))
from storage_20261122 import CONTROL as C,REPO as R,write
from fullft_ram_envelope_20261127 import read
from fullft_physical_ram_20261127 import SCHEMA,require_physical_proof
if os.getuid()!=1278:raise ValueError('Exact own account')
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    active=[k for k,v in read(C/'execution.json')['statistics'].items()
        if v.get('mode') in ('finetune','finetune_native') and not v.get('resource_closed')]
    if active:raise ValueError('Wait for exact complete/paused fit resource settlement')
    proof=require_physical_proof();check=read(C/'physical_fullft_integration_check_20261127.json')
    parent=read(check['native_record']);command=read(Path(check['native_record']).with_name('command_exit.json'))
    if (check.get('new_tests')!=2 or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
            or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
            or not parent.get('observer_joined')):raise ValueError('Actual integration exit0 required')
    path=C/'current_state.json';state=read(path)
    old_policy=state.get('future_fullft_ram_policy');state['future_fullft_ram_policy']=SCHEMA;write(path,state)
    value=dict(status='FUTURE_PHYSICAL_FULLFT_POLICY_ACTIVATED_AT_IDLE_BOUNDARY',observed_time=time.time(),
        previous_policy=old_policy,policy=SCHEMA,estimate_source=str(C/'fullft_physical_ram_20261127.json'),
        estimated_physical_peak_bytes=proof['estimate']['estimated_physical_host_peak_bytes'],
        future_peak_ram_bytes=proof['future_peak_ram_bytes'],integration_check=check,
        actual_cpu_integration_exit=parent,old_active_fullFT_handles=active,
        active_reservations_changed=False,pretraining_reservations_changed=False,
        scientific_protocol_changed=False)
    write(C/'physical_fullft_resource_activation_20261127.json',value)
    write(R/'results/s_recipe/physical_fullft_resource_activation_20261127.json',value)
    print(__import__('json').dumps(dict(status=value['status'],policy=SCHEMA,future_peak_ram_bytes=proof['future_peak_ram_bytes'])),flush=True)
