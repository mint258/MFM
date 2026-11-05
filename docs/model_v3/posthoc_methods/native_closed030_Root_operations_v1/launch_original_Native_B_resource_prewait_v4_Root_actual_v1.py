import ast,hashlib,json,os,pathlib,subprocess,sys,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';P=N/'native_S_B20k_v3';K=N/'native_S_long_operational_v8'
def ref(p):
 p=pathlib.Path(p);raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
h=json.loads((N/'Native_B_resource_prewait_v4_source_handoff_v1.json').read_text());pub=json.loads((N/'Native_v4_resourcewait_closed030_methods_publication_20261029_v1/PUBLICATION.json').read_text())
for r in [h['source_pins'],*h['files']]:
 assert ref(r['path'])==r
 name=pathlib.Path(r['path']).name
 assert any(x['path']=='docs/model_v3/pre_registered_methods/native_B_resource_prewait_v4/'+name and x['bytes']==r['bytes'] and x['sha256']==r['sha256'] and x['raw_bytes_verified'] for x in pub['files'])
assert ref(h['Root_reconciliation']['path'])==h['Root_reconciliation']
old=json.loads((N/'native_B_remaining_GPU_auto_resource_wait_20261029_v3/identity.json').read_text());assert not pathlib.Path('/proc',str(old['pid'])).exists(),'Old coordinator still exists'
control=pathlib.Path(h['control']);assert not control.exists()
for p in [P/'slots/slot_031',P/'control/attempts/slot_031.intent.json',P/'control/attempts/slot_031.submitted.json',B/'runs/model_v3_20261025/native_S_B20k_v3_slot_031.sbatch']:assert not p.exists(),str(p)
sys.path.insert(0,str(K));import long_common as common;import long_operations as ops
common.verify('785f5fe3d475316c98818ee01c50b69352d9956374e17df069a6f72868973019')
step=ops.next_member(P);assert all(step[key]==value for key,value in h['first_expected_step'].items())
src=pathlib.Path(h['files'][0]['path']);ast.parse(src.read_text())
start=json.loads((N/'native_B_remaining_20261029/identity.json').read_text())['started_unix'];assert time.time()<start+7*86400
control.mkdir(mode=0o700)
command=['/share/home/zixiao/.conda/envs/chemprop/bin/python','-u','-B',str(src)]
with (control/'controller.log').open('x') as log:
 child=subprocess.Popen(command,cwd=str(B),stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')})
body=dict(schema='native_B_resource_prewait_v4_Root_launch_actual_v1',pid=child.pid,source=ref(src),source_pins=h['source_pins'],public_method_receipt=ref(N/'Native_v4_resourcewait_closed030_methods_publication_20261029_v1/PUBLICATION.json'),reconciliation=h['Root_reconciliation'],actual_next=step,command=command,original_absolute_horizon_unix=start+7*86400,started_unix=time.time(),no_new_science_or_failed_retry=True)
(control/'ROOT_LAUNCH_actual_v1.json').write_text(json.dumps(body,indent=2)+'\n')
print(json.dumps(dict(controller_PID=child.pid,slot=step['slot'],from_update=step['start_update'],finite_original_plan=True)))

