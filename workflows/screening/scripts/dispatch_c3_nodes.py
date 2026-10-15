"""Root-only sequential submission of the six explicitly requested node probes."""
import json, subprocess, sys, time
from pathlib import Path

ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011')
manifest=ROOT/'reports/c3_dispatch.json'
if manifest.exists():
    raise RuntimeError('C3 dispatch already recorded; resume only exact missing entries')
submitted=[]; errors=[]
for number in range(14,20):
    command=[sys.executable,'-B',str(ROOT/'scripts/submit_screening_job.py'),
        '--script',str(ROOT/'scripts/c_engineering_node_probe.sbatch'),
        '--name',f'p1scr_C3_n{number}','--node',f'compute-0-{number}',
        '--cpus','24','--memory-gb','32','--time','02:00:00','--kind','resource']
    if number in (15,16):
        command.append('--allow-pending')
    command.append(str(number))
    result=subprocess.run(command,capture_output=True,text=True,stdin=subprocess.DEVNULL,timeout=150)
    if result.returncode==0:
        item=json.loads(result.stdout.strip());item['node_index']=number;submitted.append(item)
    else:
        errors.append({'node_index':number,'returncode':result.returncode,
                       'stdout':result.stdout,'stderr':result.stderr})
    record={'UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),
            'submitted':submitted,'errors':errors,'requested_workers_per_job':24,
            'sample_runtime_seconds':5400,'allow_pending_node_numbers':[15,16]}
    manifest.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record))
