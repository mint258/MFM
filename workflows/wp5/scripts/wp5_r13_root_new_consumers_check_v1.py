import ast,hashlib,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
names=['wp5_hourly_observe_v5.py','wp5_recovery_hourly_watch_v6.py','wp5_switch_watch_v6_v1.py','wp5_assemble_g0_r13_v1.py','wp5_first_submit_handoff_v2.py','wp5_acceptance_verify_v9.py','wp5_acceptance_recompute_v9.py']
rows=[]
for name in names:
    p=root/'scripts'/name
    r=subprocess.run([sys.executable,'-B',str(p),'--check'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
    rows.append({'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'argv':[sys.executable,'-B',str(p),'--check'],'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
for name in ['wp5_acceptance_v11.sbatch']:
    p=root/'scripts'/name
    raw=p.read_bytes()
    assert b'\r' not in raw
    r=subprocess.run(['bash','-n',str(p)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
    rows.append({'path':str(p),'sha256':hashlib.sha256(raw).hexdigest(),'argv':['bash','-n',str(p)],'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
report={'schema':'WP5_R13_ROOT_NEW_CONSUMERS_ACTUAL_METADATA_CHECK_V1','status':'PASS' if all(r['returncode']==0 for r in rows) else 'NOT_PASS','time':time.time(),'uid':os.getuid(),'hostname':os.uname().nodename,'checks':rows,'queue_opened':False,'SCI_or_population_opened':False,'QM_started':False,'Slurm_submitted':False}
out=root/'reports/r13_root_new_consumers_actual_metadata_check_v1.json'
with out.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps(report))
if report['status']!='PASS':raise SystemExit(2)
