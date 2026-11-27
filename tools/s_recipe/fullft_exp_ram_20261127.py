"""Default-off Exp-only RAM estimate using closed observations and vfork proof."""
import subprocess
import sys
from pathlib import Path

from fullft_ram_envelope_20261127 import GiB, read
from fullft_physical_ram_20261127 import require_physical_proof, estimate_physical
from storage_20261122 import CONTROL as C

SCHEMA='S_FUTURE_FULLFT_EXP_RAM_20261127_V1'
PROOF=C/'fullft_exp_ram_20261127.json'
TASKS=('exp.LogD','exp.LogS')


def require_proof():
    physical=require_physical_proof()
    proof=read(PROOF)
    parent=read(proof['native_record'])
    command=read(Path(proof['native_record']).with_name('command_exit.json'))
    if (proof.get('schema')!=SCHEMA or proof.get('status')!='RESOURCE_ESTIMATE_READY'
            or proof.get('python')!=physical['python']
            or proof.get('providers_sha256')!=physical['providers_sha256']
            or proof.get('future_peak_ram_bytes')!=6*GiB
            or set(proof.get('tasks',{}))!=set(TASKS)
            or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
            or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
            or not parent.get('observer_joined')):
        raise ValueError('Closed actual Exp resource estimate and same vfork proof required')
    for task in TASKS:
        item=proof['tasks'][task]
        if (item['observed_logical_fits']<6 or item['estimated_physical_host_peak_bytes']>6*GiB
                or item['observed_main_peak_bytes']<=0):
            raise ValueError('Insufficient or larger Exp observations cannot use6GiB')
    return proof


def choose(task,python,provider_pins,proof,main_peak):
    if task not in TASKS or python!=proof['python']:
        return None
    if provider_pins!=proof['providers_sha256']:
        raise ValueError('Scientific provider changed after Exp estimate')
    bound=estimate_physical(main_peak,proof['observed_metadata_peak_bytes'],
        verified_shared_address_spawn=True)
    return ((6*GiB,str(PROOF)) if bound['estimated_physical_host_peak_bytes']<=6*GiB
            else None)


def future_exp_ram(ledger,provider_pins,*,python,task,state):
    if state.get('future_fullft_exp_ram_policy')!=SCHEMA or task not in TASKS:
        return None
    proof=require_proof()
    if python!=proof['python']:
        return None
    main=proof['tasks'][task]['observed_main_peak_bytes']
    for row in ledger['statistics'].values():
        if (row.get('mode') not in ('finetune','finetune_native')
                or not row.get('resource_closed') or row.get('task')!=task):
            continue
        cfg=read(row['configuration'])
        if (cfg.get('host_ram_runtime_python')!=python
                or cfg.get('providers_sha256')!=provider_pins):
            continue
        for path in {row['lifecycle_record'],row.get('native_lifecycle_record') or row['lifecycle_record']}:
            record=read(path)
            if (record.get('exit_code') in (0,75) and record.get('owned_descendants_exited')
                    and record.get('observer_joined')):
                main=max(main,record.get('peak_RSS_bytes',0))
    return choose(task,python,provider_pins,proof,main)


def validate_exp_contract(c):
    proof=require_proof()
    if (c.get('task') not in TASKS or c.get('host_ram_envelope_source')!=str(PROOF)
            or c.get('host_ram_runtime_python')!=proof['python'] or sys.executable!=proof['python']
            or not getattr(subprocess,'_USE_VFORK',False)
            or c.get('providers_sha256')!=proof['providers_sha256']):
        raise ValueError('6GiB is restricted to the observed Exp tasks and traced interpreter')
