"""Retire only full-budget S training futures with native and Slurm closure."""
import fcntl
import json
from pathlib import Path

C=Path('/share/home/zixiao/descriptor_analysis/runs/s_recipe_20261120')

def retire(ledger,jobs):
    terminal={row['job_id'] for row in jobs if row['state']=='COMPLETED' and row['exit_code']=='0:0'}
    retired=[]
    for run,record in ledger['runs'].items():
        if record.get('job_id') not in terminal or not record.get('lifecycle_record'):
            continue
        path=Path(record['lifecycle_record'])
        if not path.is_file():
            continue
        proof=json.loads(path.read_text())
        configuration_path=Path(record.get('configuration',''))
        if not configuration_path.is_file():
            continue
        configuration=json.loads(configuration_path.read_text())
        if (proof.get('run')==run and proof.get('job_id')==record['job_id'] and
                proof.get('owned_descendants_exited') and proof.get('ended_at') and
                proof.get('status')=='TRAINING_COMPLETE_READOUT_PENDING' and
                proof.get('result',{}).get('samples')==configuration['samples'] and
                configuration['samples'] in (3000000,9000000)):
            retired.append(run)
    if not retired:
        return []
    with (C/'execution.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return []
        path=C/'storage_additional_entries.json'
        budget=json.loads(path.read_text())
        identifiers={run+'_'+kind for run in retired for kind in ('node_disk','node_ram')}
        if 'S_N2_s0_3M' in retired:
            identifiers.update('N2_available20_'+kind for kind in ('node_disk','node_ram'))
        removed=[row['id'] for row in budget['entries'] if row['id'] in identifiers]
        if removed:
            budget['entries']=[row for row in budget['entries'] if row['id'] not in identifiers]
            temporary=path.with_name(path.name+'.next.retire')
            temporary.write_text(json.dumps(budget,indent=2)+'\n')
            temporary.replace(path)
        return removed
