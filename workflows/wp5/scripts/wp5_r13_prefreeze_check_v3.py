import hashlib,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
one=root/'reports/r13_root_new_consumers_actual_metadata_check_v1.json'
two=root/'reports/r13_root_new_consumers_actual_metadata_check_v2.json'
before=json.loads(one.read_text());corrected=json.loads(two.read_text())
assert corrected['status']=='PASS'
changed={'wp5_assemble_g0_r13_v1.py','wp5_first_submit_handoff_v2.py'}
for row in before['checks']:
    if Path(row['path']).name not in changed:assert ref(row['path'])['sha256']==row['sha256']
names=['wp5_assemble_g0_r13_v1.py','wp5_first_submit_handoff_v2.py','wp5_prepare_runtime_freeze_v13.py','wp5_production_bootstrap_v13.py','wp5_submit_formal_v13.py','wp5_cleanup_scope_fixture_v1.py']
batches=['wp5_cleanup_scope_fixture_v1.sbatch','wp5_reproduction_queue_recovery_v13.sbatch','wp5_g4_freeze_v10_project_cwd.sbatch','wp5_production_bootstrap_v13.sbatch']
rows=[]
for name in names+batches:
    p=root/'scripts'/name
    argv=[sys.executable,'-B',str(p),'--check'] if name.endswith('.py') else ['bash','-n',str(p)]
    assert b'\r' not in p.read_bytes()
    r=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
    rows.append({**ref(p),'argv':argv,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr})
out=root/'reports/r13_prefreeze_actual_metadata_check_v3.json'
proof={'schema':'WP5_R13_PREFREEZE_ACTUAL_METADATA_CHECK_V3','status':'PASS' if all(r['returncode']==0 for r in rows) else 'NOT_PASS','time':time.time(),'uid':os.getuid(),'actual_prior_cli_checks':[ref(one),ref(two)],'unchanged_previously_checked_consumers_not_repeated':True,'checks':rows,'queue_opened':False,'SCI_or_population_opened':False,'QM_started':False}
with out.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'status':proof['status'],'report':ref(out),'failures':[r for r in rows if r['returncode']!=0]}))
raise SystemExit(0 if proof['status']=='PASS' else 2)
