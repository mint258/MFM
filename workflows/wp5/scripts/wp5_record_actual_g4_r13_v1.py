import hashlib,json,os,subprocess,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
report_path=root/'gates/G4_freeze/job_4514283/report.json'
spec_path=root/'configs/g4_freeze_spec_v14.json'
contract=root/'configs/production_contract_v6.json'
report=json.loads(report_path.read_text());spec=json.loads(spec_path.read_text())
assert report['status']=='PASS' and report['uid']==1278 and report['job_id']=='4514283'
assert report['binding_differences']==[] and len(set(report['worker_pids']))==24
assert report['spec_sha256']==ref(spec_path)['sha256']
assert spec['production_contract']==ref(contract)
sacct=subprocess.run(['sacct','-X','-n','-P','-j','4514283','--format=JobID,User,State,ExitCode'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
assert sacct.returncode==0
rows=[line.split('|') for line in sacct.stdout.splitlines() if line.split('|')[0]=='4514283']
assert rows and all(row[1:4]==['zixiao','COMPLETED','0:0'] for row in rows)
out=root/'gates/g4_frozen_manifest_v7.json'
manifest={'schema':'WP5_CURRENT_RUNTIME_G4_CLOSED_V7','status':'PASS','job_id':'4514283','created_epoch':time.time(),'report':ref(report_path),'spec':ref(spec_path),'production_contract':ref(contract),'actual_workers':len(set(report['worker_pids'])),'QM_started':False,'original_data_written':False,'science_recipe_changed':False,'final200_required':True,'prior_g4_manifest_preserved':True,'previous_manifest':ref(root/'gates/g4_frozen_manifest_v6.json'),'identical_prior_duplicate_references_preserved':True,'sacct':{'returncode':sacct.returncode,'stdout':sacct.stdout,'stderr':sacct.stderr}}
with out.open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
print(json.dumps({'status':'PASS','manifest':ref(out),'workers':24}))
