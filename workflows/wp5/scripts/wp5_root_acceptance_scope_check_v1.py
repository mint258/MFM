"""Root actual checks of only changed acceptance scope interfaces; no QM."""
import hashlib,json,os,socket,subprocess
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi':raise ValueError('Root zixiao login required')
rows=[]
for name in ['wp5_acceptance_recompute_v2.py','wp5_acceptance_launch_v2.py','wp5_acceptance_storage_v2.py','wp5_acceptance_delivery_v2.py']:
    path=ROOT/'scripts'/name
    q=subprocess.run(['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B',str(path),'--check'],capture_output=True,text=True,timeout=60)
    rows.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'argv':q.args,'returncode':q.returncode,'stdout':q.stdout,'stderr':q.stderr})
path=ROOT/'scripts/wp5_acceptance_v3.sbatch'
q=subprocess.run(['bash','-n',str(path)],capture_output=True,text=True,timeout=60)
rows.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'argv':q.args,'returncode':q.returncode,'stdout':q.stdout,'stderr':q.stderr})
report={'status':'ACCEPTANCE_NODE_INTERFACE_CHECKS_PASS' if all(r['returncode']==0 for r in rows) else 'NOT_PASS','checks':rows,'SCI_200_recompute_started':False,'exact200_requirement_waived':False,'QM_started':False,'formal_submitted':False}
with (ROOT/'reports/acceptance_scope_interface_actual_checks_v1.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'status':report['status'],'results':[{'path':r['path'],'returncode':r['returncode'],'stdout':r['stdout'],'stderr':r['stderr']} for r in rows]}))
if any(r['returncode']!=0 for r in rows):raise SystemExit(1)
