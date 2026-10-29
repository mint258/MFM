import ast,hashlib,json,os,pathlib,subprocess,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';P=N/'native_S_B20k_v3';K=N/'native_S_long_operational_v8'
def ref(p):
 raw=pathlib.Path(p).read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(p):return json.loads(pathlib.Path(p).read_bytes())
assert os.getuid()==1278 and not os.environ.get('SLURM_JOB_ID')
h=read(N/'Native_B_resource_prewait_v5_source_handoff_v1.json');pubpath=N/'Native_v5_resourcewait_failed031_publication_20261029_v1/PUBLICATION.json';pub=read(pubpath)
assert pub['public_branch_readback_verified'] and pub['public_Git_API_tree_readback_verified'] and pub['UTF8_raw_byte_readbacks']==12 and pub['resource_predicate_metadata_controls_count']==16
for r in [h['source_pins'],*h['files']]:
 assert ref(r['path'])==r
 path='docs/model_v3/pre_registered_methods/native_B_resource_prewait_v5/'+pathlib.Path(r['path']).name
 assert any(x['path']==path and x['bytes']==r['bytes'] and x['sha256']==r['sha256'] and x['raw_bytes_verified'] for x in pub['files'])
rec=h['Root_actual_pre_model_reconciliation'];assert ref(rec['path'])==rec
assert ref(h['old_v4_stop']['path'])==h['old_v4_stop'] and not pathlib.Path('/proc',str(h['old_v4_identity']['pid'])).exists()
failed=read(h['original_failed_Root_closure']['path']);assert ref(h['original_failed_Root_closure']['path'])==h['original_failed_Root_closure'] and failed['status']=='FAILED_OR_STORAGE_HOLD' and failed['failure']['process_private_closed'] is False
for p in [P/'slots/slot_032',P/'control/attempts/slot_032.intent.json',P/'control/attempts/slot_032.submitted.json',B/'runs/model_v3_20261025/native_S_B20k_v3_slot_032.sbatch']:assert not p.exists(),str(p)
q=subprocess.run(['squeue','-h','-u','zixiao','-o','%i|%j|%t|%N'],capture_output=True,text=True,timeout=30)
assert q.returncode==0 and not any('nativeS_B_' in row for row in q.stdout.splitlines())
import sys
sys.path.insert(0,str(K));import long_common as common;import long_operations as ops
common.verify('785f5fe3d475316c98818ee01c50b69352d9956374e17df069a6f72868973019')
step=ops.next_member(P,allow_failed=True)
assert all(step[k]==v for k,v in h['first_expected_step'].items()) and step['previous']==h['original_last_successful_closure'] and step['resume_checkpoint']==h['resume_checkpoint_path_stat_only']
control=pathlib.Path(h['control']);assert not control.exists()
source=pathlib.Path(next(r['path'] for r in h['files'] if r['path'].endswith('.py')));ast.parse(source.read_bytes())
start=read(N/'native_B_remaining_20261029/identity.json')['started_unix'];assert time.time()<start+7*86400
qa=read(pub['resource_predicate_controls']['path']);assert ref(pub['resource_predicate_controls']['path'])==pub['resource_predicate_controls'] and qa['count']==16 and qa['status']=='PASS'
control.mkdir(mode=0o700);argv=['/share/home/zixiao/.conda/envs/chemprop/bin/python','-u','-B',str(source)]
with (control/'controller.log').open('x') as log:
 child=subprocess.Popen(argv,cwd=str(B),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')})
record=dict(schema='native_B_resource_prewait_v5_Root_launch_actual_v1',pid=child.pid,source=ref(source),source_pins=h['source_pins'],public_method_receipt=ref(pubpath),actual_metadata_controls=pub['resource_predicate_controls'],actual_failed31_pre_model_reconciliation=rec,original_failed31_closure=h['original_failed_Root_closure'],actual_next=step,command=argv,original_absolute_horizon_unix=start+7*86400,started_unix=time.time(),first_only_explicit_Root_retry_failed_from_original030=True,all_subsequent_new_failure_or_unknown_stops_without_retry=True,original_31_failure_registry_storage_holds_untouched=True)
(control/'ROOT_LAUNCH_actual_v1.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(controller_PID=child.pid,slot=step['slot'],from_update=step['start_update'],waiting_only_for_exact_blocker5142=True,finite_original_plan=True),sort_keys=True))
