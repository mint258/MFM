"""Actual-node metadata spawn for one registered native readout."""
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
from readout_task_20261126 import binding
path=Path(sys.argv[1])
task=json.loads(path.read_text())
c=json.loads(Path(task['configuration']).read_text())
binding(task,c)
logpath=C/(task['handle']+'_native.log')
if (path!=C/(task['handle']+'_task.json') or os.getuid()!=1278 or not task['native']
        or c['node']!=socket.gethostname().split('.')[0] or task.get('producer')
        or Path(task['native_record']).exists() or logpath.exists()):
    raise ValueError('Wrong actual native readout target or existing spawn')
environment={key:value for key,value in os.environ.items() if not key.startswith('SLURM_')}
environment.update(TZ='UTC',CUDA_VISIBLE_DEVICES=c['gpu_uuid'],PYTHONDONTWRITEBYTECODE='1',
    OMP_NUM_THREADS='16',MKL_NUM_THREADS='16',OPENBLAS_NUM_THREADS='16',NUMEXPR_NUM_THREADS='16',
    PYTHONPATH=':'.join(map(str,(R/'current',R/'tools/s_recipe',ROOT/'runs/data_v1_20261025/repository',
        ROOT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'))))
with logpath.open('ab',buffering=0) as log:
    child=subprocess.Popen([sys.argv[2],'-B','-u',str(R/'tools/s_recipe/readout_execution_20261126.py'),
        '--task',str(path),'--mode','native'],cwd=R,env=environment,stdin=subprocess.DEVNULL,
        stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
producer=identity(child.pid)
if producer is None:raise RuntimeError('Native readout PID unobserved; inspect before retry')
print(json.dumps(dict(producer=vars(producer),node=c['node'],gpu_uuid=c['gpu_uuid'])),flush=True)
