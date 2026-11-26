"""Correct reporting provenance only; original selected12/config/primary unchanged."""
import fcntl
import json
import sys
from pathlib import Path
C=Path('/share/home/zixiao/descriptor_analysis/runs/s_recipe_20261120')
sys.path.insert(0,'/share/home/zixiao/descriptor_analysis/MFM_s_recipe/tools/s_recipe')
from control_metadata_io_20261127 import write
read=lambda p:json.loads(Path(p).read_text())
handle='S_FT_statistics_S_N1_3M_attempt0'
with (C/'execution.lock').open('a') as lock:
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    path=C/(handle+'_controller.json');old=read(path)
    config=read(old['configuration']);selected=config['completed_new_S_fits']
    if len(selected)!=12:raise ValueError('Actual producer was not bound to exactly12 selected fits')
    exits=[read(item['lifecycle_record']) for item in selected]
    if any(v.get('status')!='COMPLETE' or v.get('exit_code')!=0 or not v.get('owned_descendants_exited')
            or not v.get('observer_joined') for v in exits):raise ValueError('Exact selected12 successful exits required')
    jobs=[v['job_id'] for v in exits if v.get('job_id') is not None]
    ledger=read(C/'execution.json')
    prior=ledger['statistics']['S_FT_S_N1_3M_qm9_homo_s1_attempt0']
    pause=read(prior['lifecycle_record'])
    if (set(old['source_fit_jobs'])!=set(jobs)|{4540393} or prior.get('job_id')!=4540393
            or pause.get('exit_code')!=75 or not prior.get('resource_closed')):
        raise ValueError('Inspect any difference beyond the known reported prior75 segment')
    archive=C/'N1_statistics_source_metadata_original_20261127.json'
    if archive.exists():raise ValueError('Existing correction must not be repeated')
    write(archive,dict(controller=old,ledger_row=ledger['statistics'][handle]))
    new=dict(old,source_fit_jobs=jobs,retained_prior_safe_pause_jobs=[4540393],
        provenance_correction='Selected12 used by original producer; prior75 retained separately; no numerical/statistic rerun')
    write(path,new)
    ledger['statistics'][handle].update(source_fit_jobs=jobs,retained_prior_safe_pause_jobs=[4540393],
        provenance_correction=new['provenance_correction'])
    write(C/'execution.json',ledger)
    print(json.dumps(dict(status='REPORTING_SOURCES_CORRECTED_WITHOUT_NUMERICAL_RERUN',
        selected_successful_jobs=jobs,retained_prior_safe_pause_jobs=[4540393],original_metadata=str(archive))),flush=True)
