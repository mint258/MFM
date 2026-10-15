import copy,hashlib,json,math,os,subprocess,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def read(p):return json.loads(Path(p).read_text())
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
def once(p,obj):
    with Path(p).open('x') as f:json.dump(obj,f,indent=2,allow_nan=False);f.write('\n')
assert os.getuid()==1278 and os.uname().nodename=='sonmi'
apply_path=root/'reports/full307_apply_v6_job_4514368/report.json'
applied=read(apply_path)
assert applied['status']=='APPLIED_AND_VERIFIED' and applied['registered_jobs_count']==307
assert all(applied[k] is True for k in ('all_registered_jobs_terminal','plan_was_all307_terminal','full307_terminal_scope_verified','all_applied_rows_verified'))
assert applied['plan_skipped_count']==0 and applied['protected_jobs']=={} and applied['protected_tasks']==[]
smoke_path=root/'gates/cwd_complete_chain_smoke/job_4514366/report.json';smoke=read(smoke_path)
assert smoke['status']=='CWD_COMPLETE_CHAIN_SMOKE_PASS' and smoke['issues']==[] and smoke['science_rows']==12 and smoke['effective_worker_count']==24
g3_path=root/'gates/g3_remaining_r13_handoff_v1.json';g3=read(g3_path)
quota=subprocess.run(['quota','-v','-u','zixiao'],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
assert quota.returncode==0
lines=[line.split() for line in quota.stdout.splitlines() if line.strip().startswith('/dev/sda1 ')]
assert len(lines)==1
f=lines[0];used=int(f[1].rstrip('*'))*1024;limit=int(f[3].rstrip('*'))*1024;free=limit-used
remaining=float(g3['remaining_writeback_peak_bytes']);headroom=free-remaining
assert headroom>=float(g3['required_headroom_bytes']) and free>=300000000000
g3new={**g3,'created_epoch':time.time(),'status':'PASS','headroom_bytes':headroom,'quota':{'argv':['quota','-v','-u','zixiao'],'returncode':0,'stdout':quota.stdout,'stderr':quota.stderr,'unit_bytes':1024,'used_bytes':used,'limit_bytes':limit,'remaining_bytes':free},'previous_storage_measurement':ref(g3_path),'method_note':'Same confirmed permanent59.446GB snapshot; subsequent zero-SCI startup/test metadata already charged in fresh quota. No deduction for unconfirmed new output.'}
g3new_path=root/'gates/g3_remaining_continuation14_v1.json';once(g3new_path,g3new)
old_path=root/'gates/g0_ready_for_recovery_v13.json';old=read(old_path)
plan_path=root/'submission/recovery_attempt_v14/prepared_plan_v14.json';plan=read(plan_path)
assert plan['version']==14 and plan['runtime_version']==13 and plan['production_contract']==old['production_contract']
obj=copy.deepcopy(old)
obj.update(schema='WP5_CONTINUOUS_G0_READY_V14',status='READY_FOR_ONE_PHASE_FORMAL_SUBMISSION',created_at_epoch=time.time(),prepared_plan=ref(plan_path),previous_G0=ref(old_path),queue_reconciliation_report=ref(apply_path),cwd_complete_chain_smoke=ref(smoke_path),latest_user_continuous_directive=ref(root/'submission/recovery_attempt_v12/user_continue_all_calculations_20261012_v1.json'),submission_cwd='/share/home/zixiao/descriptor_analysis',runtime_version=13,coordination_version=14,actual_prior_formal_job_count=307,stop_retained_for_normal_drain=False,scientific_configuration_changed=False,final200_required=True)
obj['gates']['G3']={**ref(g3new_path),'status':'PASS'}
obj['current_quota_validation'].update(source_G3=ref(g3new_path),quota_remaining_bytes=free,peak_headroom_bytes=headroom)
bindings={r['path']:r for r in obj['bindings']}
for p in (plan_path,apply_path,smoke_path,g3new_path,root/'scripts/wp5_continue_formal_v14.py',root/'scripts/wp5_hourly_observe_v6.py',root/'scripts/wp5_recovery_hourly_watch_v7.py',root/'scripts/wp5_switch_watch_v7_v1.py',root/'reports/r13_actual78_startup_fact_review_accounting_followup_v1.json'):
    bindings[str(p)]=ref(p)
obj['bindings']=list(bindings.values())
assert not (root/'STOP_NEW_MOLECULES.json').exists()
for r in obj['bindings']:assert ref(r['path'])['sha256']==r['sha256']
out=root/'gates/g0_ready_for_recovery_v14.json';once(out,obj)
print(json.dumps({'status':obj['status'],'g0':ref(out),'G3':ref(g3new_path),'headroom_GB':headroom/1e9,'prior_jobs':307,'unchanged_runtime':13}))
