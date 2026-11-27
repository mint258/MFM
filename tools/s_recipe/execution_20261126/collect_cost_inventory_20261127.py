"""CPU-only execution metadata inventory; no actual Slurm totals yet."""
from pathlib import Path
import json
import shutil
from cost_inventory_20261127 import inventory
from cpu_execution_20261126 import execution_fields
from storage_20261122 import CONTROL as C,REPO as R,write
proof=json.loads((C/'cost_inventory_check_20261127.json').read_text())
parent=json.loads(Path(proof['native_record']).read_text())
command=json.loads(Path(proof['native_record']).with_name('command_exit.json').read_text())
if (proof.get('new_tests')!=3 or parent.get('exit_code')!=0 or command.get('exit_code')!=0
        or not parent.get('owned_descendants_exited') or not parent.get('observer_joined')):
    raise ValueError('Actual inventory checks must close first')
value=dict(inventory(C),**execution_fields())
write(C/'cost_inventory_20261127.json',value)
shutil.copyfile(C/'collect_cost_inventory_20261127.py',R/'tools/s_recipe/execution_20261126/collect_cost_inventory_20261127.py')
print(json.dumps({k:value[k] for k in ('status','new_GPU_proofs','new_native_CPU_proofs','open_execution_sources','missing_bound_sources','legacy_GPU_closure_unverified')}),flush=True)
