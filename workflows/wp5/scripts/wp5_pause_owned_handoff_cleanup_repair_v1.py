#!/usr/bin/env python3
import json,os,signal,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
identity=json.loads((root/'reports/r12_first_submit_handoff_identity_v1.json').read_text())
pid=int(identity['pid'])
state_path=root/'submission/recovery_attempt_v12/first_submit_handoff_v1/state.json'
state=json.loads(state_path.read_text())
proc=Path('/proc')/str(pid)
raw=(proc/'stat').read_text()
ticks=int(raw[raw.rfind(')')+2:].split()[19])
cmd=(proc/'cmdline').read_bytes().replace(b'\0',b' ').decode()
assert os.getuid()==1278 and proc.stat().st_uid==1278
assert pid==3450268 and ticks==8055955725
assert 'wp5_first_submit_handoff_v1.py --run' in cmd
assert state['status']=='ROOT_HANDOFF_STARTED'
assert set(state['steps'])=={'sacct_4514280'}, list(state['steps'])
before={'pid':pid,'uid':proc.stat().st_uid,'start_ticks':ticks,'cmdline':cmd,'state_status':state['status'],'steps':list(state['steps'])}
os.kill(pid,signal.SIGTERM)
for _ in range(50):
    if not proc.exists():break
    current=(proc/'stat').read_text()
    if current[current.rfind(')')+2:].split()[0]=='Z':break
    time.sleep(.1)
else:raise RuntimeError('coordinator did not exit')
out={'schema':'WP5_ROOT_OWNED_COORDINATOR_PAUSE_FOR_CONCRETE_REPAIR_V1','status':'COORDINATOR_EXITED_BEFORE_METADATA_OR_FORMAL_SUBMIT','time':time.time(),'before':before,'reason':'cleanup static index snapshot versus dynamically newly closed task claims','old_scientific_jobs_signalled':False,'frozen_scientific_sources_modified':False,'repeat_user_permission_required':False}
dest=root/'reports/r12_handoff_concrete_cleanup_repair_pause_v1.json'
assert not dest.exists()
dest.write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out))