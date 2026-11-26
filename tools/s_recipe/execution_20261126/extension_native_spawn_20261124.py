"""Actual-node metadata launcher; native producer owns its workers and deadline."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis')
REPO=ROOT/'MFM_s_recipe'
sys.path.insert(0,str(REPO/'tools/s_recipe'))
from lifecycle_20261122 import identity
from runtime import write

path=Path(sys.argv[1])
task=json.loads(path.read_text())
c=task['configuration']
if socket.gethostname().split('.')[0]!=c['node'] or c['node'] not in ('compute-0-20','compute-0-22') or os.getuid()!=1278:
    raise ValueError('Wrong native spawn target')
spawn=Path(task['spawn_record'])
if spawn.exists() or Path(task['lifecycle_record']).exists() or Path(c['output']).exists():
    raise ValueError('Existing launch/output must be observed; no duplicate spawn')

# Future entry only: keep the login/standby task immutable while a separate
# child copy uses an earlier-or-equal actual-node deadline anchor. Running
# producers, their loaded NativeGuard and their task files are untouched.
proof=json.loads((ROOT/'runs/s_recipe_20261120/extension_spawn_clock_check_20261127.json').read_text())
parent_path=Path(proof['native_record'])
parent=json.loads(parent_path.read_text())
command=json.loads(parent_path.with_name('command_exit.json').read_text())
if (proof.get('status')!='COMPLETE' or proof.get('new_tests')!=2
        or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
        or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
        or not parent.get('observer_joined')):
    raise ValueError('Future node-clock copy checks must actually close first')
from extension_spawn_clock_20261127 import node_clock_task
node_task_path=path.with_name(path.stem+'_node_clock_20261127.json')
if node_task_path.exists():raise ValueError('Inspect the existing node-clock task before retry')
node_task=node_clock_task(task)
write(node_task_path,node_task)
env=dict(os.environ)
for key in list(env):
    if key.startswith('SLURM_'):
        env.pop(key)
env.update(CUDA_VISIBLE_DEVICES=c['gpu_uuid'],PYTHONDONTWRITEBYTECODE='1',
    PYTHONPATH=':'.join(map(str,(REPO/'current',REPO/'tools/s_recipe',
        ROOT/'runs/data_v1_20261025/repository',
        ROOT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'))),
    OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',
    PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True')
with Path(task['native_log']).open('ab',buffering=0) as log:
    child=subprocess.Popen([task['python'],'-B','-u',str(REPO/'tools/s_recipe/extension_native_training_20261124.py'),
        '--task',str(node_task_path)],cwd=REPO,env=env,stdin=subprocess.DEVNULL,stdout=log,
        stderr=subprocess.STDOUT,start_new_session=True)
saved=identity(child.pid)
if saved is None:
    raise RuntimeError('Native process exited before its identity could be published')
record=dict(run=c['run'],node=c['node'],gpu_uuid=c['gpu_uuid'],producer=vars(saved),
    started_at=time.time(),native_log=task['native_log'],lifecycle_record=task['lifecycle_record'],
    original_standby_task=str(path),actual_native_task=str(node_task_path),
    node_clock_binding=node_task['node_clock_binding_20261127'])
write(spawn,record)
print(json.dumps(record),flush=True)
