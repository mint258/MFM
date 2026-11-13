import ast,json,os,subprocess
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_cpu_perf_20261112')
for name in ('cpu_perf_equivalence.py','cpu_perf_equivalence_wait.py'):
    ast.parse((root/'tools/model_v3'/name).read_text(),filename=name)
state=root/'results/model_v3_perf_20261112/equivalence_wait.json'
if state.exists():
    record=json.loads(state.read_text());proc=Path('/proc')/str(record['pid'])
    if proc.exists() and proc.stat().st_uid==os.getuid() and proc.joinpath('stat').read_text().rsplit(')',1)[1].split()[19]==record['start_ticks']:
        raise RuntimeError('An acceptance observer is already live; inspect it instead of restarting')
with (root/'results/model_v3_perf_20261112/equivalence_wait.log').open('a') as log:
    child=subprocess.Popen(['/share/apps/softwares/anaconda3/bin/python',str(root/'tools/model_v3/cpu_perf_equivalence_wait.py')],
        cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print('ACCEPTANCE_OBSERVER_PID',child.pid,flush=True)
