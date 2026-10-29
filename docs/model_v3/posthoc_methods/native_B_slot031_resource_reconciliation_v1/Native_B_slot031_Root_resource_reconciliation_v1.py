import json,pathlib,hashlib,fcntl,os,subprocess,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';P=N/'native_S_B20k_v3';R=N/'native_S_profile_registered_reservations_v6.json';C=N/'native_B_remaining_GPU_auto_resource_wait_20261029_v3'
out=N/'Native_B_slot031_pre_submission_resource_reconciliation_actual_v1.json'
assert not out.exists()
def ref(p):
 p=pathlib.Path(p);b=p.read_bytes();return dict(path=str(p),bytes=len(b),sha256=hashlib.sha256(b).hexdigest())
status=json.loads((C/'status.json').read_bytes())
assert status['status']=='STOPPED_REQUIRES_ROOT_RECONCILIATION_NO_RETRY' and status['completed_additional_segments']==3
identity=json.loads((C/'identity.json').read_bytes())
assert not pathlib.Path('/proc/'+str(identity['pid'])).exists(),'Old controller must actually be gone'
assert not (P/'control/attempts/slot_031.intent.json').exists() and not (P/'control/attempts/slot_031.submitted.json').exists()
assert not (P/'slots/slot_031').exists()
assert not (B/'runs/model_v3_20261025/native_S_B20k_v3_slot_031.sbatch').exists()
submitted=sorted((P/'control/attempts').glob('slot_*.submitted.json'))
intents=sorted((P/'control/attempts').glob('slot_*.intent.json'))
assert len(submitted)==len(intents)==30
assert all((P/'slots'/p.name.split('.')[0]/'management/ROOT_LONG_SEGMENT_CLOSURE.json').exists() for p in submitted)
log=(C/'controller.log').read_text();assert 'ValueError: Selected UUID has a foreign GPU compute process' in log and '"slot": 31' in log
queue=subprocess.run(['squeue','-h','-u','zixiao','-o','%i|%j|%t|%N'],capture_output=True,text=True,check=True)
assert not any('nativeS_B_' in line for line in queue.stdout.splitlines()),queue.stdout
import sys
sys.path.insert(0,str(N/'native_s_profile_launch_v8'))
import root_phase as rp
with rp.registry_lock(R):
 before=R.read_bytes();v=json.loads(before);original=json.loads(before)
 pending=[(k,r) for k,r in v.get('GPU_software_memory',{}).items() if r['status']=='PRE_SUBMISSION' and 'slot_031' in json.dumps(r)]
 assert len(pending)==1,pending
 key,registration=pending[0]
 assert registration['job_id'] is None and registration['actual_submission'] is None,registration
 assert registration['node']=='compute-0-21' and registration['software_budget_bytes']==32<<30
 del v['GPU_software_memory'][key]
 expected=json.loads(before);del expected['GPU_software_memory'][key]
 assert v==expected
 temp=R.with_suffix('.Root_reconciliation_pending')
 temp.write_text(json.dumps(v,indent=2)+'\n');os.replace(temp,R)
 record=dict(schema='NATIVE_B_ROOT_PRE_SUBMISSION_RESOURCE_RECONCILIATION_V1',status='NO_SLOT031_SBATCH_OCCURRED_EXACT_PRE_REGISTRATION_RELEASED_READY_FOR_FRESH_ROOT_RESOURCE_ADMISSION',
 old_controller_identity=identity,old_controller_status=ref(C/'status.json'),old_controller_log=ref(C/'controller.log'),actual_submitted_and_closed_slots=30,
 no_slot031_intent_submission_layout_or_sbatch_copy=True,actual_squeue=dict(argv=queue.args,returncode=queue.returncode,stdout=queue.stdout,stderr=queue.stderr),
 removed_pre_submission_registration=registration,removed_registration_id=key,registry_before_sha256=hashlib.sha256(before).hexdigest(),registry_after=ref(R),
 all_other_resource_and_storage_fields_unchanged=True,Native_principal_counters_or_future_holds_changed=False,original_outputs_retained=True,automatic_original_failure_retry=False,
 actual_unix=time.time())
 out.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(status=record['status'],receipt=ref(out))))

