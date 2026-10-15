import hashlib,json,os,subprocess,sys,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
p=root/'scripts/wp5_first_submit_handoff_v3.py'
expected='8afc705c9fc2e456c8d470ce016ee30b167f42952ff42208406fac7d126f9d16'
assert os.getuid()==1278 and os.uname().nodename=='sonmi'
assert hashlib.sha256(p.read_bytes()).hexdigest()==expected
identity=root/'reports/r13_first_submit_handoff_v3_identity_v1.json'
assert not identity.exists()
cmd=[sys.executable,'-B',str(p),'--run','--plan',str(root/'reports/full229_dryrun_v5_job_4514280/plan.json'),'--plan-job-id','4514280']
log=root/'reports/r13_first_submit_handoff_v3.log'
with log.open('ab',buffering=0) as f:
    child=subprocess.Popen(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,cwd='/share/home/zixiao/descriptor_analysis',start_new_session=True,close_fds=True)
time.sleep(.3)
assert child.poll() is None
proc=Path('/proc')/str(child.pid)
stat=(proc/'stat').read_text()
ticks=int(stat[stat.rfind(')')+2:].split()[19])
data={'pid':child.pid,'uid':proc.stat().st_uid,'start_ticks':ticks,'source_path':str(p),'source_sha256':expected,'argv':cmd,'started_epoch':time.time(),'log':str(log),'state':str(root/'submission/recovery_attempt_v13/first_submit_handoff_v3/state.json'),'actual_authorization_basis':'LATEST_USER_DIRECTIVE_AUTONOMOUS_METADATA_REPAIR_WITH_UNCHANGED_SCIENCE','unused_frozen_handoff_v2_preserved':True,'actual_R12_normal_drain_STOP_preserved':True}
with identity.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
print(json.dumps(data))
