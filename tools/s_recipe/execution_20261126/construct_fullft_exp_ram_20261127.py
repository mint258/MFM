"""First Exp-specific estimate from retained closed resource metadata only."""
from pathlib import Path
from cpu_execution_20261126 import execution_fields,native_record
from storage_20261122 import CONTROL as C,REPO as R,write
from fullft_ram_envelope_20261127 import GiB,read
from fullft_physical_ram_20261127 import require_physical_proof,estimate_physical
from fullft_exp_ram_20261127 import PROOF,SCHEMA,TASKS

native_record()
if PROOF.exists():raise ValueError('Reuse the closed estimate; never repeat its observations')
physical=require_physical_proof()
ledger=read(C/'execution.json')
tasks={task:dict(observed_logical_fits=0,observed_main_peak_bytes=0,sources=[])
       for task in TASKS}
for handle,row in ledger['statistics'].items():
    task=row.get('task')
    if (task not in TASKS or row.get('mode') not in ('finetune','finetune_native')
            or not row.get('resource_closed')):continue
    cfg=read(row['configuration'])
    if (cfg.get('host_ram_runtime_python')!=physical['python']
            or cfg.get('providers_sha256')!=physical['providers_sha256']):continue
    observed=[]
    for path in {row['lifecycle_record'],row.get('native_lifecycle_record') or row['lifecycle_record']}:
        record=read(path)
        if (record.get('exit_code') in (0,75) and record.get('owned_descendants_exited')
                and record.get('observer_joined') and record.get('ended_at')
                and record.get('peak_RSS_bytes',0)>0):
            observed.append(dict(source=path,peak_RSS_bytes=record['peak_RSS_bytes'],
                exit_code=record['exit_code'],producer=record['producer']))
    if not observed:continue
    item=tasks[task]
    item['observed_logical_fits']+=1
    item['observed_main_peak_bytes']=max(item['observed_main_peak_bytes'],
        max(value['peak_RSS_bytes'] for value in observed))
    item['sources'].append(dict(handle=handle,run=row['run'],observed_producers=observed))
for task,item in tasks.items():
    if item['observed_logical_fits']<6:raise ValueError('At least six closed observations per Exp task')
    bound=estimate_physical(item['observed_main_peak_bytes'],
        physical['estimate']['observed_metadata_peak_bytes'],verified_shared_address_spawn=True)
    if bound['estimated_physical_host_peak_bytes']>6*GiB:
        raise ValueError('The actual Exp estimate does not fit6GiB; keep the current policy')
    item.update(bound)
value=dict(schema=SCHEMA,status='RESOURCE_ESTIMATE_READY',tasks=tasks,
    python=physical['python'],providers_sha256=physical['providers_sha256'],
    observed_metadata_peak_bytes=physical['estimate']['observed_metadata_peak_bytes'],
    future_peak_ram_bytes=6*GiB,source_physical_proof=str(C/'fullft_physical_ram_20261127.json'),
    active_reservations_changed=False,pretraining_reservations_changed=False,
    new_models_or_benchmarks=0,original_predictions_or_scores_read=False,
    activation='Default off until the new checks close and root activates at no-active-FT boundary',
    **execution_fields())
write(PROOF,value)
write(R/'results/s_recipe/fullft_exp_ram_20261127.json',value)
print({task:dict(fits=item['observed_logical_fits'],main=item['observed_main_peak_bytes'],
    estimate=item['estimated_physical_host_peak_bytes']) for task,item in tasks.items()},flush=True)
