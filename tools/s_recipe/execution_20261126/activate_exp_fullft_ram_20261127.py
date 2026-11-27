"""Enable the closed Exp estimate only at a no-active-FT boundary."""
import fcntl
import time
import sys
from pathlib import Path
sys.path.insert(0,'/share/home/zixiao/descriptor_analysis/MFM_s_recipe/tools/s_recipe')
from storage_20261122 import CONTROL as C,REPO as R,claim_current
from control_metadata_io_20261127 import write
from fullft_ram_envelope_20261127 import read
from fullft_physical_ram_20261127 import SCHEMA as PHYSICAL_SCHEMA
from fullft_exp_ram_20261127 import SCHEMA,PROOF,require_proof

with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    proof=require_proof()
    check=read(C/'fullft_exp_ram_check_20261127.json')
    parent=read(check['native_record'])
    command=read(Path(check['native_record']).with_name('command_exit.json'))
    if (check.get('new_tests')!=4 or parent.get('status')!='COMPLETE'
            or parent.get('exit_code')!=0 or command.get('exit_code')!=0
            or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
        raise ValueError('All new actual CPU checks must close before activation')
    ledger=read(C/'execution.json')
    if any(row.get('mode') in ('finetune','finetune_native') and not row.get('resource_closed')
           for row in ledger['statistics'].values()):
        raise ValueError('Do not modify an active fullFT reservation')
    state=read(C/'current_state.json')
    if state.get('future_fullft_ram_policy')!=PHYSICAL_SCHEMA:
        raise ValueError('The previous traced physical policy must remain intact')
    if state.get('future_fullft_exp_ram_policy')==SCHEMA:
        raise ValueError('Exp resource activation already recorded')
    state['future_fullft_exp_ram_policy']=SCHEMA
    write(C/'current_state.json',state)
    claim_current()
    value=dict(status='FUTURE_EXP_RESOURCE_POLICY_ACTIVE',schema=SCHEMA,observed_time=time.time(),
        estimate_source=str(PROOF),new_check_source=str(C/'fullft_exp_ram_check_20261127.json'),
        tasks=list(proof['tasks']),future_peak_ram_bytes=proof['future_peak_ram_bytes'],
        runtime_python=proof['python'],no_active_fullFT=True,pretraining_reservations_changed=False,
        scientific_identity_changed=False,guard_or_system_reserve_changed=False)
    write(C/'fullft_exp_ram_activation_20261127.json',value)
    write(R/'results/s_recipe/fullft_exp_ram_activation_20261127.json',value)
    print(value,flush=True)
