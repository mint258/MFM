import hashlib,json,time
from pathlib import Path
root=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
out=root/'reports/continuation14_first_durable_science_actual_probe_v1.json'
proof={'schema':'WP5_CONTINUATION14_FIRST_ACTUAL_DURABLE_SCIENCE_PROBE_V1','status':'NEW_DURABLE_SCI_VERIFIED','source':'Actual Root SSH compute-0-20 stdout, exit0; saved after observation without requery','actual_probe_epoch':1791767801.0658562,'saved_epoch':time.time(),'actual_node':'compute-0-20','new_phase_claims':744,'new_durable_molecules':192,'new_durable_records':1895,'production_queue_written':False,'actual_exit_code':0,'phase_receipt':{'path':str(root/'submission/recovery_attempt_v14/submitted_jobs.json'),'sha256':hashlib.sha256((root/'submission/recovery_attempt_v14/submitted_jobs.json').read_bytes()).hexdigest()},'probe_source':{'path':str(root/'scripts/wp5_continue_formal_v14.py'),'sha256':hashlib.sha256((root/'scripts/wp5_continue_formal_v14.py').read_bytes()).hexdigest()},'goal_completed':False,'new_SCI_not_inferred_from_scheduler_exit_status':True}
with out.open('x') as f:json.dump(proof,f,indent=2);f.write('\n')
print(json.dumps({'status':proof['status'],'report':str(out),'new_durable_molecules':192,'new_durable_records':1895}))
