"""Install the native sampler in isolated scratch before occupying a GPU."""
from pathlib import Path
import os
import subprocess
import sys
root=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112')
sys.path.insert(0,str(root/'current'))
sys.path.insert(0,str(root/'tools/model_v3'))
from cpu_bottleneck_step1 import capacity, SCRATCH
print(capacity(),flush=True)
target=SCRATCH/'sampler_tools_v1'
temporary=SCRATCH/'sampler_tmp_v1'
temporary.mkdir(parents=True,exist_ok=True)
if not (target/'bin/py-spy').is_file():
    subprocess.run([sys.executable,'-m','pip','install','--no-cache-dir','--no-deps',
                    '--target',str(target),'py-spy'],check=True,
                   env=dict(os.environ,TMPDIR=str(temporary)))
subprocess.run([str(target/'bin/py-spy'),'--version'],check=True)
print('SAMPLER_READY',target/'bin/py-spy',flush=True)
