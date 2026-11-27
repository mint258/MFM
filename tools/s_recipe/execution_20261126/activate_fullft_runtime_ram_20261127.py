"""Activate checked accounting only for future fits at a no-active-fit boundary."""
import json
from pathlib import Path
import shutil
import sys
R=Path('/share/home/zixiao/descriptor_analysis/MFM_s_recipe')
sys.path.insert(0,str(R/'tools/s_recipe'))
from fullft_runtime_ram_20261127 import POLICY
from control_metadata_io_20261127 import write,acquire_control_lock
from storage_20261122 import CONTROL as C,REPO as R
read=lambda path:json.loads(Path(path).read_text())
lock,role=acquire_control_lock('execution_delivery')
try:
    proof=read(C/'fullft_runtime_ram_check_20261127.json')
    parent=read(proof['native_record'])
    command=read(Path(proof['native_record']).with_name('command_exit.json'))
    if (proof.get('policy')!=POLICY or proof.get('new_tests')!=9
            or parent.get('exit_code')!=0 or command.get('exit_code')!=0
            or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
        raise ValueError('Actual new-logic checks must close successfully')
    ledger=read(C/'execution.json')
    active=[name for name,row in ledger['statistics'].items()
        if row.get('mode') in ('finetune','finetune_native') and not row.get('resource_closed')]
    if active:raise ValueError('Do not change active fit configuration: '+str(active))
    state=read(C/'current_state.json')
    state['future_fullft_runtime_ram_accounting']=POLICY
    write(C/'current_state.json',state)
    result=dict(status='FUTURE_FITS_ONLY',policy=POLICY,check=proof,
        startup_full_peak_and_all_existing_reservations_unchanged=True,
        scientific_protocol_or_active_pretraining_changed=False)
    write(C/'fullft_runtime_ram_activation_20261127.json',result)
    write(R/'results/s_recipe/fullft_runtime_ram_activation_20261127.json',result)
    shutil.copyfile(C/'activate_fullft_runtime_ram_20261127.py',R/'tools/s_recipe/execution_20261126/activate_fullft_runtime_ram_20261127.py')
    print(json.dumps(dict(status=result['status'],policy=POLICY)),flush=True)
finally:
    if lock is not None:lock.close()
