import copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def ref(p):return {'path':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()}
old_dir=root/'submission/recovery_attempt_v13/first_submit_handoff_v3'
new_dir=root/'submission/recovery_attempt_v13/first_submit_handoff_v4'
old_path=old_dir/'state.json';old=json.loads(old_path.read_text())
assert os.getuid()==1278 and os.uname().nodename=='sonmi'
assert old['status']=='ROOT_HANDOFF_NEEDS_CONCRETE_REPAIR'
assert '4514285' in old['error'] and 'FAILED' in old['error']
assert old['steps']['submit_bootstrap']['job_id']=='4514285'
assert not (root/'submission/recovery_attempt_v13/submitted_jobs.json').exists()
proc=Path('/proc/3452926')
if proc.exists():
    raw=(proc/'stat').read_text()
    assert raw[raw.rfind(')')+2:].split()[0]=='Z','previous coordinator still active'
source=root/'scripts/wp5_first_submit_handoff_v4.py'
assert ref(source)['sha256']=='543c3805d237b39297664e7127ac05310bd5da9ea96a6543f4568c57e87b266b'
checks=[]
for p,args in [(root/'scripts/wp5_production_bootstrap_v14.py',['--check']),(source,['--check'])]:
    result=subprocess.run([sys.executable,'-B',str(p)]+args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
    checks.append({**ref(p),'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
    assert result.returncode==0,result.stderr
batch=root/'scripts/wp5_production_bootstrap_v14.sbatch'
result=subprocess.run(['bash','-n',str(batch)],stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=60)
assert result.returncode==0 and b'\r' not in batch.read_bytes()
checks.append({**ref(batch),'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr})
new_dir.mkdir(exist_ok=False)
new=copy.deepcopy(old)
new.update(status='ROOT_HANDOFF_STARTED',source=ref(source),started_epoch=time.time(),deadline_epoch=time.time()+48*3600,previous_handoff=ref(old_path),resume_basis='Reuse actual COMPLETED dryrun4514280 and verified apply4514284; replace failed-before-queue-write bootstrap4514285 with path/SHA identity fix',actual_checks=checks)
new['failed_prior_bootstrap_steps']={k:new['steps'].pop(k) for k in ('submit_bootstrap','sacct_4514285')}
new.pop('error',None);new.pop('last_error_epoch',None)
path=new_dir/'state.json'
with path.open('x') as f:json.dump(new,f,indent=2);f.write('\n')
cmd=[sys.executable,'-B',str(source),'--run','--plan',old['plan'],'--plan-job-id',old['plan_job_id']]
log=root/'reports/r13_first_submit_handoff_v4.log'
with log.open('ab',buffering=0) as f:
    child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,cwd='/share/home/zixiao/descriptor_analysis',start_new_session=True,close_fds=True)
time.sleep(.3)
assert child.poll() is None
proc=Path('/proc')/str(child.pid);raw=(proc/'stat').read_text()
identity={'pid':child.pid,'uid':proc.stat().st_uid,'start_ticks':int(raw[raw.rfind(')')+2:].split()[19]),'source_path':str(source),'source_sha256':ref(source)['sha256'],'started_epoch':time.time(),'argv':cmd,'log':str(log),'state':str(path),'prior_handoff_state':ref(old_path),'old_apply_not_resubmitted':True,'actual_checks':checks}
out=root/'reports/r13_first_submit_handoff_v4_identity_v1.json'
with out.open('x') as f:json.dump(identity,f,indent=2);f.write('\n')
print(json.dumps(identity))
