"""Deliver selected models of truly completed own fits; never inspect live states."""
import json
from pathlib import Path
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,write
from seal_finetune_20261124 import seal
read=lambda path:json.loads(Path(path).read_text())
ledger=read(C/'execution.json')
delivered=[]
for handle,row in ledger['statistics'].items():
    if (row.get('mode') not in ('finetune','finetune_native')
            or not row.get('resource_closed') or row.get('status')!='COMPLETE'):
        continue
    cfg=read(row['configuration'])
    output=Path(cfg['output'])
    if (output/'selected_model_receipt.json').exists():continue
    if cfg['run']!=row['run'] or output.parent!=C/'finetune_20261124':
        raise ValueError('Exact registered own fit output required')
    # Native fits have their actual producer closure plus a settled standby;
    # successful genuine Slurm fits must retain their actual C0 accounting.
    if row.get('job_id') is not None and row.get('resource_close_actual')!='COMPLETED|0:0':
        raise ValueError('Actual successful fit settlement required')
    receipt=seal(output,row['lifecycle_record'])
    delivered.append(dict(handle=handle,run=row['run'],receipt=receipt))
value=dict(status='COMPLETED_SELECTED_MODELS_DELIVERED',newly_sealed=delivered,
    **execution_fields(),new_fits=0,new_bootstraps=0,
    scope='Existing checked sealer only; selected best encoder/head/normalization retained before exact own completed continuation retirement')
write(C/'selected_artifact_sealing_20261127.json',value)
print(json.dumps(value),flush=True)
