"""Export an explicitly partial accounting table from already-closed caches."""
import json
from pathlib import Path
import shutil
from cost_export_20261127 import render
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C, REPO as R, write

read = lambda path: json.loads(Path(path).read_text())
summary = read(C/'cost_closed_summary_20261127.json')
parent = read(summary['native_record'])
command = read(Path(summary['native_record']).with_name('command_exit.json'))
if (parent.get('exit_code') != 0 or command.get('exit_code') != 0
        or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
    raise ValueError('The actual closed accounting summary must succeed first')
outputs = render(summary, read(C/'cost_inventory_20261127.json'), read(C/'cost_slurm_closed_20261127.json'))
size = sum(len(value.encode('utf-8')) for value in outputs.values())
if size > 4*1024**2:
    raise ValueError('Rendered metadata tables exceed the bounded 4MiB output allowance')
destination = R/'results/s_recipe'
for name, content in outputs.items():
    (destination/name).write_text(content, encoding='utf-8')
proof = dict(status='CLOSED_PHASE_COST_EXPORT_NOT_FULL_EXPERIMENT_COST',
    **execution_fields(), outputs=list(outputs), output_bytes=size,
    summary_source=str(C/'cost_closed_summary_20261127.json'),
    inventory_snapshot_time=summary['inventory_snapshot_time'],
    Slurm_snapshot=summary['Slurm_snapshot'],
    models_predictions_labels_scores_VAL_read=False,
    scope='Formatting cached execution metadata only; active and uncaptured phases excluded')
write(C/'cost_closed_export_20261127.json', proof)
write(destination/'cost_closed_export_20261127.json', proof)
shutil.copyfile(C/'export_closed_cost_20261127.py',
    R/'tools/s_recipe/execution_20261126/export_closed_cost_20261127.py')
print(json.dumps(proof), flush=True)
