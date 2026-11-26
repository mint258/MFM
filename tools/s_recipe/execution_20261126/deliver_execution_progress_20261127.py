"""Current closed execution metadata only; no score arrays or model rereads."""
import json
from pathlib import Path
import shutil
import time
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
read=lambda path:json.loads(Path(path).read_text())
for filename in ('e1_s_rule_check_20261127.json','controller_sequence_check_20261127.json'):
    check=read(C/filename)
    parent=read(check['native_record'])
    command=read(Path(check['native_record']).with_name('command_exit.json'))
    if (parent['status']!='COMPLETE' or parent['exit_code']!=0 or command['exit_code']!=0
            or not parent['owned_descendants_exited'] or not parent['observer_joined']):
        raise ValueError('Actual closed affected execution checks required before delivery')
ledger=read(C/'execution.json')
fits=[]
selected=[]
for handle,row in ledger['statistics'].items():
    if (row.get('mode') not in ('finetune','finetune_native')
            or not row.get('resource_closed') or row.get('status')!='COMPLETE'):continue
    closure=read(row['lifecycle_record'])
    cfg=read(row['configuration'])
    summary=read(Path(cfg['output'])/'summary.json')
    fits.append(dict(handle=handle,run=row['run'],point=row['point'],task=row['task'],seed=row['seed'],
        epochs=summary['detail']['epochs'],updates=summary['detail']['updates'],
        scientific_summary=str(Path(cfg['output'])/'summary.json'),
        closure_source=row['lifecycle_record'],actual_job=row.get('job_id'),
        actual_settlement=row['resource_close_actual'],producer=closure['producer'],
        peak_RSS_bytes=closure.get('peak_RSS_bytes'),child_peak_RSS_bytes=closure.get('child_peak_RSS_bytes')))
    receipt=Path(cfg['output'])/'selected_model_receipt.json'
    if receipt.exists():selected.append(read(receipt))
budget=[]
for run in ('S_B0_s0_9M','S_final_s0_9M'):
    for count in range(1000000,9000000,1000000):
        path=C/'training'/run/('readout_'+str(count))/'snapshot_statistics_status.json'
        if not path.exists():continue
        phase=read(path)
        if phase.get('status')!='COMPLETE' or not phase.get('owned_descendants_exited'):continue
        if not phase.get('native_record'):continue
        parent=read(phase['native_record'])
        command=read(Path(phase['native_record']).with_name('command_exit.json'))
        if (parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0 or command.get('exit_code')!=0
                or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):continue
        budget.append(dict(run=run,samples=count,source=str(path),native_record=phase['native_record']))
source=C/'selected_artifact_sealing_20261127.json'
value=dict(status='PARTIAL_EXECUTION_PROGRESS_NOT_A_COMPLETE_EXPERIMENT',observed_time=time.time(),
    completed_full_fits=fits,completed_full_fit_count=len(fits),required_seed0_full_fits=192,
    selected_models=selected,selected_model_producer=read(source) if source.exists() else None,
    completed_original9M_prefix_statistics=budget,required_new_prefix_statistics=16,
    intermediate_VAL_reopened=False,
    primary_point_status_source='Separate actual fullFT statistics deliveries; this file counts individual fits only',
    source_ledger=str(C/'execution.json'),**execution_fields(),
    scope='Closed execution metadata only; group primaries/curve delivery remain pending, no new fits/bootstrap')
write(R/'results/s_recipe/execution_progress_20261127.json',value)
target=R/'tools/s_recipe/execution_20261126'
for name in ('launch_fullft_20261124.py','launch_cpu_native_20261126.py','seal_closed_fullft_20261127.py',
    'advance_closed_gpu_20261127.py','check_controller_sequence_20261127.py','check_e1_s_rule_20261127.py',
    'refresh_extension_daily_20261126.py','deliver_execution_progress_20261127.py'):
    shutil.copyfile(C/name,target/name)
print(json.dumps(dict(status='EXECUTION_PROGRESS_DELIVERED',completed_full_fits=len(fits),
    selected_models=len(selected),completed_prefix_statistics=len(budget))),flush=True)
