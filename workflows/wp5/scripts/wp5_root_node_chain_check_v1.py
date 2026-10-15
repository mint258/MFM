"""Root actual metadata checks for new approved node chain, no QM."""
import hashlib,json,os,socket,subprocess
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':raise ValueError('zixiao Root login required')
checks=[]
for name in ['wp5_runner_v7.py','wp5_g6_recover_v7.py','submit_wp5_job_v2.py','wp5_submit_formal_v5.py','wp5_storage_budget_v9.py']:
    path=ROOT/'scripts'/name
    result=subprocess.run(['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B',str(path),'--check'],text=True,capture_output=True,timeout=60)
    checks.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mode':'actual --check','returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
for name in ['wp5_main_v7.sbatch','wp5_g6_recover_v7.sbatch','wp5_storage_budget_v9.sbatch']:
    path=ROOT/'scripts'/name
    result=subprocess.run(['bash','-n',str(path)],text=True,capture_output=True,timeout=60)
    checks.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'mode':'actual bash -n','returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
report={'status':'ALL_METADATA_CHECKS_PASS_NO_QM' if all(x['returncode']==0 for x in checks) else 'METADATA_CHECK_FAILED','checks':checks,'QM_started':False,'LMDB_read_or_written':False,'formal_submitted':False}
path=ROOT/'reports/node_replacement_chain_actual_checks_v1.json'
with path.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report))
if any(x['returncode']!=0 for x in checks):raise SystemExit(1)
