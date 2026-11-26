"""Actual-node lightweight spawn for the new finite fullFT entry."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
ROOT=Path('/share/home/zixiao/descriptor_analysis')
R=ROOT/'MFM_s_recipe'
C=ROOT/'runs/s_recipe_20261120'
sys.path.insert(0,str(R/'tools/s_recipe'))
from lifecycle_20261122 import identity
path=Path(sys.argv[1])
if path.parent!=C:raise ValueError('Exact owned task path required')
task=json.loads(path.read_text())
c=json.loads(Path(task['configuration']).read_text())
if (os.getuid()!=1278 or socket.gethostname().split('.')[0]!=c['node']
        or c['node'] not in ('compute-0-20','compute-0-22') or task.get('producer')
        or Path(task['native_record']).exists() or Path(task['native_log']).exists()):
    raise ValueError('Wrong native target or existing launch; inspect before retry')
env={key:value for key,value in os.environ.items() if not key.startswith('SLURM_')}
env.update(CUDA_VISIBLE_DEVICES=c['gpu_uuid'],PYTHONDONTWRITEBYTECODE='1',TZ='UTC',
    PYTHONPATH=':'.join(map(str,(R/'current',R/'tools/s_recipe',ROOT/'runs/data_v1_20261025/repository',
        ROOT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'))),
    OMP_NUM_THREADS='16',MKL_NUM_THREADS='16',OPENBLAS_NUM_THREADS='16',NUMEXPR_NUM_THREADS='16',
    PYTORCH_CUDA_ALLOC_CONF='expandable_segments:True')
with Path(task['native_log']).open('ab',buffering=0) as log:
    child=subprocess.Popen([task['python'],'-B','-u',str(R/'tools/s_recipe/fullft_native_execution_20261126.py'),
        '--task',str(path),'--mode','native'],cwd=R,env=env,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
saved=identity(child.pid)
if saved is None:raise RuntimeError('Native fullFT identity was not observed; inspect this spawn')
print(json.dumps(dict(producer=vars(saved),node=c['node'],gpu_uuid=c['gpu_uuid'])),flush=True)
