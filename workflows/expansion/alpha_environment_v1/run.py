"""Provision an isolated Alpha SQL environment from the pinned offline wheel."""
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT=Path('/gfshome/alpha/codex_data_v1_20261026')
CONTROL=ROOT/'control/pubchem_completion_environment_20261103'
PREFIX=ROOT/'software/pubchem_completion_20261103_venv'
WHEEL=ROOT/'software/pubchem_completion_20261103_wheels/duckdb-1.2.2-cp311-cp311-manylinux_2_17_x86_64.manylinux2014_x86_64.whl'
EXPECTED='fd9c434127fd1575694e1cf19a393bed301f5d6e80b4bcdae80caa368a61a678'
assert os.getuid()==1264 and socket.gethostname().split('.')[0]=='sonmi1'
assert os.environ.get('SLURM_JOB_PARTITION')=='cpu' and int(os.environ['SLURM_CPUS_PER_TASK'])==16
jid=os.environ['SLURM_JOB_ID']; assert jid.isdecimal() and int(jid)>0
out=CONTROL/('job_'+jid); out.mkdir(mode=0o700)
before=time.monotonic()
assert WHEEL.stat().st_size==20199712 and hashlib.sha256(WHEEL.read_bytes()).hexdigest()==EXPECTED
assert not PREFIX.exists(), 'Existing private environment requires inspection rather than mutation'
PREFIX.parent.mkdir(mode=0o700,exist_ok=True)
subprocess.run([sys.executable,'-I','-m','venv','--without-pip','--system-site-packages',str(PREFIX)],check=True)
py=str(PREFIX/'bin/python')
with (out/'offline_install.log').open('wb') as log:
    subprocess.run([py,'-I','-m','pip','install','--no-index','--no-deps',str(WHEEL)],
                   stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
code='''import json,sys,platform,numpy,pyarrow,duckdb
from rdkit import rdBase
from pathlib import Path
assert platform.python_version()=='3.11.14'
assert numpy.__version__=='2.2.6' and pyarrow.__version__=='17.0.0'
assert rdBase.rdkitVersion=='2025.09.5' and duckdb.__version__=='1.2.2'
assert Path(duckdb.__file__).resolve().is_relative_to(Path(sys.prefix).resolve())
assert duckdb.connect(':memory:').execute('SELECT 1').fetchone()==(1,)
print(json.dumps(dict(python=platform.python_version(),executable=sys.executable,
prefix=sys.prefix,numpy=numpy.__version__,pyarrow=pyarrow.__version__,
rdkit=rdBase.rdkitVersion,rdkit_build=rdBase.rdkitBuild,duckdb=duckdb.__version__,
duckdb_path=duckdb.__file__,glibc=platform.libc_ver())))
'''
checked=subprocess.run([py,'-I','-c',code],capture_output=True,text=True,check=True)
v=dict(schema='PUBCHEM_ALPHA_ISOLATED_ENVIRONMENT_V1',status='SOFTWARE_READY_SCIENTIFIC_GATES_PENDING',
       endpoint='218.192.171.238:22',uid=os.getuid(),node=socket.gethostname(),job_id=jid,
       boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),cpus=16,
       source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       wheel_sha256=EXPECTED,software=json.loads(checked.stdout),
       memory_request_environment={k:os.environ.get(k) for k in ['SLURM_MEM_PER_NODE','SLURM_MEM_PER_CPU']},
       new_scientific_dataset_records=0,new_UFF_QM_calls=0,original_environment_modified=False,
       elapsed_seconds=time.monotonic()-before)
with (out/'result.json').open('x') as f:json.dump(v,f,sort_keys=True);f.write('\n')
print(json.dumps(v,sort_keys=True),flush=True)
