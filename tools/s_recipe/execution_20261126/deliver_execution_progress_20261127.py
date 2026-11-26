"""Current closed execution metadata only; no score arrays or model rereads."""
import json
from pathlib import Path
import shutil
import time
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
read=lambda path:json.loads(Path(path).read_text())
from fullft_delivery_20261127 import progress
closed_points=sorted((R/'results/s_recipe/full_finetune').glob('*.json'))
if closed_points:progress([read(path) for path in closed_points])
for filename in ('e1_s_rule_check_20261127.json','controller_sequence_check_20261127.json',
        'metadata_lock_check_20261127.json','reporting_delivery_check_20261127.json',
        'native_clock_anchor_check_20261127.json','fullft_contrast_check_20261127.json',
        'e1_cached_components_check_20261127.json','fullft_point_sequence_check_20261127.json',
        'molecule_scaling_delivery_check_20261127.json','extension_spawn_clock_check_20261127.json',
        'fullft_ram_envelope_20261127.json','future_fullft_resources_check_20261127.json',
        'fullft_physical_ram_20261127.json','physical_fullft_integration_check_20261127.json',
        'point_only_sequence_check_20261127.json','control_metadata_io_check_20261127.json'):
    check=read(C/filename)
    parent=read(check['native_record'])
    command=read(Path(check['native_record']).with_name('command_exit.json'))
    if (parent['status']!='COMPLETE' or parent['exit_code']!=0 or command['exit_code']!=0
            or not parent['owned_descendants_exited'] or not parent['observer_joined']):
        raise ValueError('Actual closed affected execution checks required before delivery')
ledger=read(C/'execution.json')
fits=[]
selected=[]
paused=[]
for handle,row in ledger['statistics'].items():
    if (row.get('mode') in ('finetune','finetune_native') and row.get('resource_closed')
            and row.get('status')=='PAUSED_SAFE_CONTINUATION'):
        paused.append(dict(handle=handle,run=row['run'],source_configuration=row['configuration'],
            actual_exit=read(row['lifecycle_record']),
            resource_settlement=read(C/(handle+'_resource_close.json')),
            interpretation='Actual75 complete-state pause; not a completed fit or scientific/method failure'))
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
    retained_safe_pause_segments=paused,
    completed_original9M_prefix_statistics=budget,required_new_prefix_statistics=16,
    intermediate_VAL_reopened=False,
    primary_point_status_source='Separate actual fullFT statistics deliveries; this file counts individual fits only',
    source_ledger=str(C/'execution.json'),**execution_fields(),
    scope='Closed execution metadata only; group primaries/curve delivery remain pending, no new fits/bootstrap')
write(R/'results/s_recipe/execution_progress_20261127.json',value)
target=R/'tools/s_recipe/execution_20261126'
for name in ('launch_fullft_20261124.py','launch_cpu_native_20261126.py','seal_closed_fullft_20261127.py',
    'advance_closed_gpu_20261127.py','check_controller_sequence_20261127.py','check_e1_s_rule_20261127.py',
    'refresh_extension_daily_20261126.py','deliver_execution_progress_20261127.py',
    'launch_readout_20261126.py','launch_budget_statistics_native_20261126.py',
    'launch_terminal_statistics_native_20261126.py','launch_fullft_statistics_native_20261126.py',
    'launch_extension_training_20261124.py','close_fullft_resources_20261126.py',
    'close_readout_resources_20261126.py','close_extension_native_resource_20261124.py',
    'retire_closed_training_reservations_20261122.py','reconcile_B0_8M_takeover_20261127.py',
    'check_metadata_lock_20261127.py','check_reporting_delivery_20261127.py',
    'check_native_clock_anchor_20261127.py','inspect_native_startup_clock_20261127.py',
    'recover_preGPU_native_starts_20261127.py','check_fullft_contrasts_20261127.py',
    'check_e1_cached_components_20261127.py','check_fullft_point_sequence_20261127.py',
    'run_fullft_point_sequence_20261127.py','check_molecule_scaling_delivery_20261127.py',
    'extension_native_spawn_20261124.py','check_extension_spawn_clock_20261127.py',
    'construct_fullft_ram_envelope_20261127.py','check_future_fullft_resources_20261127.py',
    'activate_future_fullft_ram_20261127.py','construct_fullft_physical_ram_20261127.py',
    'fullft_metadata_spawn_probe_20261127.py','check_physical_fullft_integration_20261127.py',
    'activate_physical_fullft_ram_20261127.py','report_extensions_startup_20261126.py',
    'check_point_only_sequence_20261127.py','check_control_metadata_io_20261127.py',
    'correct_N1_statistics_sources_20261127.py'):
    compile((C/name).read_text(),str(C/name),'exec')
    shutil.copyfile(C/name,target/name)
shutil.copyfile(C/'B0_8M_takeover_reconciliation_20261127.json',
    R/'results/s_recipe/B0_8M_takeover_reconciliation_20261127.json')
recoveries=[read(path) for path in sorted((C/'early_native_startup_recovery_20261127').glob('*.json'))]
if len(recoveries)!=2 or any(item['status']!='SAME_HELD_JOB_RELEASED_AFTER_VERIFIED_NEW_NATIVE_START' for item in recoveries):
    raise ValueError('Both exact held-job recoveries must be verified before delivery')
write(R/'results/s_recipe/native_startup_recovery_20261127.json',dict(
    status='BOTH_PRE_GPU_COLD_STARTS_RECOVERED_WITH_ORIGINAL_HELD_JOBS',
    recoveries=recoveries,clock_observation=read(C/'native_startup_clock_20261127.json'),
    original_wait_statuses_unobserved=True,new_allocations_submitted=0,
    model_updates_or_readout_fits_replayed=0,**execution_fields()))
print(json.dumps(dict(status='EXECUTION_PROGRESS_DELIVERED',completed_full_fits=len(fits),
    selected_models=len(selected),completed_prefix_statistics=len(budget))),flush=True)
