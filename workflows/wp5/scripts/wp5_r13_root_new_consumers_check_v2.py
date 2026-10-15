import hashlib,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
parent=root/'reports/r13_root_new_consumers_actual_metadata_check_v1.json'
old=json.loads(parent.read_text())
assert sum(r['returncode']!=0 for r in old['checks'])==1
p=root/'scripts/wp5_acceptance_recompute_v9.py'
argv=[sys.executable,'-B',str(p),'plan','--check']
r=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
proof={'schema':'WP5_R13_ROOT_NEW_CONSUMERS_CORRECT_CLI_V2','status':'PASS' if r.returncode==0 else 'NOT_PASS','time':time.time(),'uid':os.getuid(),'prior_check':{'path':str(parent),'sha256':hashlib.sha256(parent.read_bytes()).hexdigest()},'checks_already_passed_and_not_repeated':7,'corrected_invocation':{'argv':argv,'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr},'queue_opened':False,'SCI_or_population_opened':False,'QM_started':False}
out=root/'reports/r13_root_new_consumers_actual_metadata_check_v2.json'
with out.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps(proof))
raise SystemExit(0 if r.returncode==0 else 2)
