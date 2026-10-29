"""Release only now-unused future output reservations of20 fully closed R1 members."""
import copy,hashlib,importlib.util,json,pathlib,subprocess,sys,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';R=N/'native_S_profile_registered_reservations_v6.json'
def ref(p):
 raw=pathlib.Path(p).read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(p):return json.loads(pathlib.Path(p).read_bytes())
def load(rr,name):
 assert ref(rr['path'])==rr;p=pathlib.Path(rr['path']);sys.path.insert(0,str(p.parent));s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
gate=read(N/'native_S20000_dev_panel_GPU_4525060_Root_closure_v1.json')
assert ref(gate['spec']['path'])==gate['spec'];spec=read(gate['spec']['path'])
m=load(spec['native_admission_implementation'],'R1_closed_storage_only_admission');monitor=load(spec['runtime_monitor'],'R1_closed_storage_only_monitor')
items=[];jobs=[]
for old in ['4520405','4520486','4520456','4520411','4520549']:
 p=N/('R1v3_old'+old+'_SDK_speed_Root_closure_actual_v1.json');closed=read(p)
 assert closed['status']=='FOUR_C0_NATIVE_SDK_AND_ORIGINAL_SPEED_REPORT_OFFICIAL_SYNC_CLOUD_READBACK_CLOSED' and closed['failure'] is None
 for rr in closed['runs']:
  family=pathlib.Path(rr['supervisor']['path']).parent
  assert family==N/('performance_remaining_Av2_R1_ABBA_v3/cohort_'+old+'/member_'+str(rr['position']))
  principal=ref(family/'control/principal.json');pr=read(principal['path']);rid=pr['reservation_id']
  assert rid=='remaining_Av2_R1_v3_'+old+'_member_'+str(rr['position'])
  sup=read(rr['supervisor']['path']);assert ref(rr['supervisor']['path'])==rr['supervisor'] and sup['status']=='COMPLETED' and not sup['remaining_recorded_processes_before_retirement'] and not sup['private_storage_cleanup_errors']
  whole=m.whole_output_bytes(family,monitor);assert 0<whole<=2<<30
  items.append(dict(reservation_id=rid,phase=str(family),principal=principal,current_closed_whole_bytes=whole,full_R1_Root_closure=ref(p),job_id=rr['job_id']))
  jobs.append(rr['job_id'])
assert len(items)==len(set(jobs))==20
q=subprocess.run(['sacct','-X','-n','-P','-j',','.join(jobs),'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],capture_output=True,text=True,timeout=30)
rows=[x.split('|') for x in q.stdout.splitlines() if x]
assert q.returncode==0 and q.stderr=='' and len(rows)==20 and {x[0] for x in rows}==set(jobs) and all(x[1:4]==['zixiao','COMPLETED','0:0'] and int(x[4])>0 and x[5]=='16' for x in rows)
assert not any(key.split('.',1)[0] in ('torch','numpy','wandb','phychem_mfm') for key in sys.modules)
sys.path.insert(0,str(N/'native_s_profile_launch_v8'));import root_phase as rp
out=N/'R1five_20_closed_members_unused_future_release_Root_actual_v1.json';assert not out.exists()
with rp.registry_lock(R):
 before=rp.registry_value(R);after=copy.deepcopy(before);oldrows={};newrows={}
 for item in items:
  rid=item['reservation_id'];row=before['reservations'][rid]
  assert row['phase']==item['phase'] and row['principal']==item['principal'] and row['remaining_bytes']==2<<30
  oldrows[rid]=row;after['reservations'][rid]=dict(row,remaining_bytes=0,closure=item['full_R1_Root_closure'],current_closed_whole_bytes=item['current_closed_whole_bytes'],unused_future_only_released=True,files_deleted=False);newrows[rid]=after['reservations'][rid]
 a=copy.deepcopy(before);b=copy.deepcopy(after)
 for item in items:del a['reservations'][item['reservation_id']];del b['reservations'][item['reservation_id']]
 assert a==b
 rp.replace_feed(R,after);assert rp.registry_value(R)==after and after['reservations']['native_S_B20k_v3']==before['reservations']['native_S_B20k_v3']
 record=dict(schema='model_v3_twenty_closed_R1_unused_future_release_actual_v1',captured_unix=time.time(),closed_members=items,before=oldrows,after=newrows,actual_sacct=dict(argv=q.args,returncode=q.returncode,stdout=q.stdout,stderr=q.stderr),released_only_unused_future_bytes=20*(2<<30),files_removed=0,all_principals_and_actual_outputs_retained=True,Native_B_and_all_other_registry_fields_unchanged=True,Root_no_SDK_resource_journal_model_or_array_body_read=True,scientific_acceptance=False)
 out.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(dict(status='ONLY_TWENTY_CLOSED_R1_UNUSED_FUTURE_HOLDS_RELEASED',bytes=20*(2<<30),receipt=ref(out)),sort_keys=True))
