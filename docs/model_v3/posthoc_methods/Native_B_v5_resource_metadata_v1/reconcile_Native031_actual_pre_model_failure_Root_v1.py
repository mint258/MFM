"""Root-only pre-model failed31 reconciliation; retain actual failure and every hold."""
import ast,csv,datetime,hashlib,io,json,os,pathlib,re,stat,subprocess
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';P=N/'native_S_B20k_v3';C=N/'native_B_remaining_GPU_auto_resource_wait_20261029_v4';K=N/'native_S_long_operational_v8'
assert os.getuid()==1278 and not os.environ.get('SLURM_JOB_ID')
def ref(p):
 p=pathlib.Path(p);raw=p.read_bytes();assert p.suffix in ('.json','.py','.sbatch','.log') and 0<len(raw)<=2<<20
 return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(p):return json.loads(pathlib.Path(p).read_bytes())
def run(argv):
 r=subprocess.run([str(x) for x in argv],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
 assert r.returncode==0,(argv,r.returncode,r.stderr);return dict(argv=r.args,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
out=N/'Native_B_slot031_actual_failed_pre_model_reconciliation_v1.json';assert not out.exists()
status=read(C/'status.json');identity=read(C/'identity.json')
assert status['status']=='STOPPED_REQUIRES_ROOT_RECONCILIATION_NO_RETRY' and status['completed_additional_segments']==0 and not pathlib.Path('/proc',str(identity['pid'])).exists()
frame=P/'control/attempts/slot_031.submitted.json';f=read(frame)
assert f['actual_sbatch_job_id']=='4525157' and f['slot']==31 and f['start_update']==9000 and f['target_update']==10000 and f['seed']==0 and f['precision']=='bf16'
close=P/'slots/slot_031/management/ROOT_LONG_SEGMENT_CLOSURE.json';cl=read(close)
assert cl['status']=='FAILED_OR_STORAGE_HOLD' and cl['submission']==ref(frame) and cl['member_result'] is None and cl['supervisor'] is None and cl['storage_seal'] is None and cl['checkpoint_directory'] is None and cl['optimizer_updates']==9000
assert not (P/'slots/slot_031/child').exists()
a=run(['sacct','-X','-n','-P','-j','4525157','--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'])
assert a['stdout'].strip()=='4525157|zixiao|FAILED|1:0|0|16|compute-0-21'
log=P/'logs/slot_031.log';text=log.read_text()
assert 'observations=resources.observe(worker=True,root_frame=frame)' in text and 'ValueError: Selected UUID has a foreign GPU compute process' in text
worker=K/'long_worker.py';pins=read(K/'source_pins.json');rows=[r for r in pins['files'] if r['path']=='long_worker.py'];assert len(rows)==1
assert (ref(worker)['bytes'],ref(worker)['sha256'])==(rows[0]['bytes'],rows[0]['sha256'])
body=worker.read_text();ast.parse(body);assert body.index('observations=resources.observe(worker=True,root_frame=frame)')<body.index("layout=slot_layout(args.phase,frame['slot'])")<body.index('completed=subprocess.run(supervisor')
ssh=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(B/'runs/model_v3_20261025/compute21_known_hosts_v1'),'compute-0-21']
private=run(ssh+['test ! -e /tmp/mv3n_4525157'])
apps=run(ssh+['nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory --format=csv,noheader,nounits'])
target=[x for x in csv.reader(io.StringIO(apps['stdout']),skipinitialspace=True) if x and x[0].strip()=='GPU-22e21021-e572-4562-fc51-cd8c83e74141']
assert len(target)==1 and target[0][1].isdigit() and target[0][2]=='gmx'
pid=target[0][1];cg=run(ssh+['cat /proc/'+pid+'/cgroup'])
assert re.search(r'/slurm/uid_1275/job_4525142/',cg['stdout'])
foreign=run(['sacct','-X','-n','-P','-j','4525142','--format=JobIDRaw,User,State,ExitCode,NodeList'])
assert foreign['stdout'].strip().split('|')[:3]==['4525142','guangyuan','RUNNING'] and foreign['stdout'].strip().split('|')[-1]=='compute-0-21'
q=run(['squeue','-h','-u','zixiao','-o','%i|%j|%t|%N']);assert not any('nativeS_B_' in x for x in q['stdout'].splitlines())
assert not any((P/'control/attempts'/name).exists() for name in ['slot_032.intent.json','slot_032.submitted.json']) and not (P/'slots/slot_032').exists() and not (B/'runs/model_v3_20261025/native_S_B20k_v3_slot_032.sbatch').exists()
good=P/'slots/slot_030/management/ROOT_LONG_SEGMENT_CLOSURE.json';g=read(good)
assert g['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' and g['optimizer_updates']==9000 and g['failure'] is None
cp=pathlib.Path(g['checkpoint_directory']);st=cp.lstat();assert stat.S_ISDIR(st.st_mode) and st.st_uid==1278 and not cp.is_symlink()
record=dict(schema='NATIVE_B_ROOT_ACTUAL_FAILED_PRE_MODEL_RECONCILIATION_V1',status='ACTUAL031_FAILED_BEFORE_SUPERVISOR_NO_MODEL_UPDATE_PRESERVED_READY_FOR_EXPLICIT_ROOT_ONLY_NEXT_SLOT_AFTER_BLOCKER_TERMINAL',captured_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),actual_failed_job='4525157',submission=ref(frame),original_failed_Root_closure=ref(close),original_failed_status_preserved='FAILED_OR_STORAGE_HOLD',actual_sacct=a,guard_failure_log=ref(log),pinned_original_worker=ref(worker),worker_source_admission_precedes_snapshot_QA_supervisor_and_model=True,child_supervisor_member_result_checkpoint_and_private_scratch_absent=True,actual_private_absence_observation=private,old_v4_identity=identity,old_v4_status=ref(C/'status.json'),old_v4_log=ref(C/'controller.log'),old_v4_exited=True,actual_own_queue=q,selected_GPU_foreign_process_observation=apps,exact_target_foreign_cgroup=cg,blocking_foreign_job=dict(job_id='4525142',user='guangyuan',uid=1275,node='compute-0-21',gpu_uuid='GPU-22e21021-e572-4562-fc51-cd8c83e74141',actual_accounting=foreign),last_successful_Root_closure=ref(good),resume_checkpoint_directory_stat_only=str(cp),first_expected_step=dict(slot=32,seed=0,precision='bf16',start_update=9000,target_update=10000),one_time_explicit_Root_retry_failed_only_after_blocking_foreign_job_terminal=True,any_new_failed_or_ambiguous_child_must_stop_no_automatic_retry=True,existing_failures_registry_counters_principal_and_all_storage_holds_not_modified=True,Model_SDK_checkpoint_or_array_body_read=False,model_training_updates_or_new_submission_in_this_reconciliation=0,scientific_acceptance=False)
out.write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(status=record['status'],receipt=ref(out)),sort_keys=True))
