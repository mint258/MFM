"""Supplement only failed check invocations; preserve all first-pass records."""
import hashlib,json,subprocess
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
rows=[]
for script,argv,previous in [
    ('submit_wp5_job_v2.py',['--check','--kind','quantum'],'node_replacement_chain_actual_checks_v1.json'),
    ('wp5_acceptance_recompute_v2.py',['plan','--check'],'acceptance_scope_interface_actual_checks_v1.json')]:
    path=ROOT/'scripts'/script
    old=ROOT/'reports'/previous
    obj=json.loads(old.read_text())
    prior=next(r for r in obj['checks'] if r['path']==str(path))
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest!=prior['sha256'] or prior['returncode']!=2:raise ValueError('Only unchanged source missing CLI arguments corrected')
    r=subprocess.run(['/share/home/zixiao/.conda/envs/chemprop/bin/python','-B',str(path),*argv],capture_output=True,text=True,timeout=60)
    rows.append({'script':str(path),'source_sha256':digest,'original_failed_check':str(old),'original_report_sha256':hashlib.sha256(old.read_bytes()).hexdigest(),'original_argv_error':prior['stderr'],'corrected_argv':r.args,'returncode':r.returncode,'stdout':r.stdout,'stderr':r.stderr,'source_changed':False})
report={'status':'MISSING_CLI_ARGUMENT_CHECKS_CORRECTED' if all(r['returncode']==0 for r in rows) else 'NOT_PASS','checks':rows,'other_already_passed_checks_not_repeated':True,'QM_started':False,'formal_submitted':False}
with (ROOT/'reports/cli_check_invocation_corrections_v1.json').open('x') as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({'status':report['status'],'checks':[{'script':r['script'],'returncode':r['returncode'],'stdout':r['stdout'],'stderr':r['stderr']} for r in rows]}))
if any(r['returncode']!=0 for r in rows):raise SystemExit(1)
