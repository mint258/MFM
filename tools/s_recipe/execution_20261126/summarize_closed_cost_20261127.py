"""Summarize only cached closed phases; never claim total ongoing cost."""
import json
from pathlib import Path
import shutil
import time
from cost_accounting_20261127 import cpu_account,gpu_wall_account,identity
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
read=lambda p:json.loads(Path(p).read_text())
for name,count in (('cost_accounting_check_20261127.json',3),
        ('cost_inventory_check_20261127.json',3),('cost_slurm_check_20261127.json',2)):
    check=read(C/name);parent=read(check['native_record'])
    command=read(Path(check['native_record']).with_name('command_exit.json'))
    if (check.get('new_tests')!=count or parent.get('exit_code')!=0 or command.get('exit_code')!=0
            or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
        raise ValueError('Actual metadata arithmetic/inventory/parser checks must close first')
inventory=read(C/'cost_inventory_20261127.json')
slurm=read(C/'cost_slurm_closed_20261127.json')
gpu_rows=list(inventory['closed_GPU_proofs'].values())
cpu_rows=list(inventory['closed_native_CPU_proofs'].values())
jobs=list(slurm['jobs'].values())
gpu=gpu_wall_account(gpu_rows)
cpu=cpu_account(jobs,cpu_rows)
verified={identity(row) for row in gpu_rows if row['closure_verified']}
closure_unknown=[row for row in gpu['unique_producers'] if tuple(row['identity']) not in verified]
by_state={}
for row in jobs:by_state.setdefault(row['state'],[]).append(row)
by_stage={}
for row in cpu_rows:by_stage.setdefault(row.get('stage','unknown'),[]).append(row)
value=dict(status='CLOSED_PHASE_COST_PREPARATION_NOT_FULL_EXPERIMENT_COST',observed_time=time.time(),
    **execution_fields(),GPU=gpu,CPU=cpu,
    Slurm_by_actual_state={key:dict(job_count=len(rows),**cpu_account(rows,[])) for key,rows in by_state.items()},
    native_CPU_by_stage={key:cpu_account([],rows) for key,rows in by_stage.items()},
    producer_closure_not_fully_observed=closure_unknown,
    inventory_snapshot_time=inventory['observed_time'],Slurm_snapshot=slurm['latest_snapshot'],
    excluded_open_execution_sources=inventory['open_execution_sources'],
    missing_bound_sources=inventory['missing_bound_sources'],
    unrecognized_bound_execution_sources=inventory['unrecognized_bound_execution_sources'],
    scope='Only cached closed execution phases. Active T5/T6 and current accounting overhead are excluded; no full total-to-now, final report, CUDA busy-time, energy or currency claim. No scientific inputs.',
    models_predictions_labels_scores_VAL_read=False)
write(C/'cost_closed_summary_20261127.json',value)
shutil.copyfile(C/'summarize_closed_cost_20261127.py',
    R/'tools/s_recipe/execution_20261126/summarize_closed_cost_20261127.py')
print(json.dumps(dict(status=value['status'],unique_GPU_producers=len(gpu['unique_producers']),
    unknown_GPU_exit_codes=gpu['unknown_producer_exit_codes'],
    unique_GPU_closure_unverified=len(closure_unknown),closed_Slurm_jobs=len(jobs),
    missing_Slurm_CPU_times=len(cpu['Slurm_jobs_missing_measured_CPU_time']),
    native_CPU_missing_times=cpu['native_producers_missing_CPU_time'])),flush=True)
