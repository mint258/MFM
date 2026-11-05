"""One explicit Root metadata admission/submission for the frozen manual R2 task."""
import ast,csv,datetime,hashlib,json,os,pathlib,re,socket,stat,subprocess,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';O=B/'runs/model_v3_20261025'
W=B/'MFM_model_v3_performance_integration_v1';PKG=N/'performance_manual_R2_4090_GPU_v1_source'
FAMILY=N/'performance_manual_R2_4090_v1';CONTROL=FAMILY/'control';OUT=FAMILY/'child';RECORD=FAMILY/'supervisor.json'
NODE='compute-0-20';GPU='GPU-ec788ed1-7da1-8f93-bb23-b4fdb2018b02';MEM=65536;LIMIT=2147483648
GIT=O/'cpu_git_tools_v1/bin/git';SB=O/'run_performance_manual_R2_4090_v1.sbatch';REG=N/'native_S_profile_registered_reservations_v6.json'
def need(value,message):
 if not value:raise ValueError(message)
def ref(path):
 path=pathlib.Path(path);s=path.lstat()
 need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_nlink==1 and s.st_size<=2<<20,'Small owned raw source/metadata required: '+str(path))
 raw=path.read_bytes();return dict(path=str(path),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
def read(path):return json.loads(pathlib.Path(path).read_bytes())
def write(path,value,fresh=True):
 raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=2<<20,'Small control cap')
 if fresh:
  with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
 else:
  tmp=path.with_name(path.name+'.pending');need(not tmp.exists(),'Fresh atomic update path')
  with tmp.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  os.replace(tmp,path)
 return ref(path)
def command(argv,timeout=45,env=None):
 r=subprocess.run(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout,env=env)
 need(len(r.stdout)+len(r.stderr)<=2<<20,'Bounded raw command output')
 return dict(argv=argv,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)
need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),'Root login metadata only')
for args,expected in [(['rev-parse','HEAD'],'9e16d4c5a15c558051499d3dc0c55c9bd3787734'),(['rev-parse','HEAD^{tree}'],'98b3b4bd8bc083a4150f536024e4dc81e6fb6108'),(['status','--porcelain=v1','--untracked-files=all'],'')]:
 r=command([str(GIT),'-C',str(W),*args]);need(r['returncode']==0 and r['stdout'].strip()==expected,'Exact clean tested W/code/tree required')
pins=ref(PKG/'source_pins.json');need(pins['sha256']=='1016eea78da6d689fb697b18f03fd492dc4ab4887d8d7eec07a773a2894a87a1','Frozen source package differs')
for item in read(PKG/'source_pins.json')['files']:
 actual=ref(item['path']);need(all(actual[k]==item[k] for k in actual),'Frozen package leaf drift')
need(ref(SB)['sha256']==ref(PKG/'run_manual_R2_4090.sbatch')['sha256'],'Installed thin SB must be byte-identical')
# Reuse only Root's existing strict node20 trust projection; no new key discovery.
deps=read(PKG/'dependencies.json')
for key in ('node20_trust_projection','node20_public_hostkeys'):
 item=deps['raw_refs'][key];need(ref(item['path'])==item,'Exact existing node20 trust rawref required')
trust=read(deps['raw_refs']['node20_trust_projection']['path'])
need(trust['schema']=='model_v3_Root_existing_trusted_public_host_key_projection_v1' and trust['host']==NODE and trust['new_keyscan_or_accept_new_used'] is False,'Existing strict node20 trust projection required')
need(trust['projected_public_hostkeys']==deps['raw_refs']['node20_public_hostkeys'] and trust['projected_public_hostkeys']['path']==str(O/'compute20_known_hosts_v1'),'Fixed node20 existing public hostkey path/ref required')
need(deps['operational_target']['node']==NODE and deps['operational_target']['gpu_uuid']==GPU and deps['fixed_execution']['expected_gpu']=='4090','Exact independent4090 target required')
pack=read(N/'performance_packaging_CPU_4523705_Root_closure_v1.json')
for path,h in pack['full_current_source_map'].items():need(ref(path)['sha256']==h,'Current complete tested source drift')
need(not FAMILY.exists() and not OUT.exists() and not RECORD.exists(),'Fresh single-use R2 family required')
CONTROL.mkdir(parents=True,mode=0o700)
registry=read(REG);before=ref(REG);need('performance_manual_R2_4090_v1' not in registry['reservations'],'No duplicate hold')
write(CONTROL/'registry_before.json',registry)
principal=dict(schema='model_v3_Root_one_job_output_reservation_v1',authority='ROOT_ACTUAL',uid=1278,filesystem='/dev/sda1',
reservation_id='performance_manual_R2_4090_v1',phase=str(FAMILY),max_bytes=LIMIT,reserved_additional_bytes=LIMIT,
initial_existing_bytes=0,status='ROOT_RESERVED_FINITE_SINGLE_GPU_TASK',scientific_acceptance=False,source_package=pins)
pr=write(CONTROL/'principal.json',principal)
entry=dict(phase=str(FAMILY),principal=pr,principal_sha256=pr['sha256'],remaining_bytes=LIMIT)
registry['reservations']['performance_manual_R2_4090_v1']=entry
need(ref(REG)==before,'Live registry changed before addition')
write(REG,registry,fresh=False)
hold=write(CONTROL/'Root_hold_actual_v1.json',dict(schema='model_v3_Root_independent_output_hold_v1',authority='ROOT_ACTUAL',registry_path=str(REG),
reservation_id='performance_manual_R2_4090_v1',entry_snapshot=entry,principal=pr,reserved_additional_bytes=LIMIT,
Native_S_principal_or_counters_changed=False,physical_allocation_of_2GiB_file_claimed=False,original_registry_before=ref(CONTROL/'registry_before.json')))
attempt_path=CONTROL/'Root_submission_actual_v1.json'
attempt=dict(schema='model_v3_manual_R2_Root_single_submission_v1',status='ADMISSION_STARTED',job_id=None,source_package=pins,installed_sbatch=ref(SB),
Root_driver=ref(__file__),hold=hold,observations=[],GPU_GRES_isolation_claimed=False,automatic_retry=False)
write(attempt_path,attempt)
intent=False
def capture(argv,timeout=45):
 r=command(argv,timeout);attempt['observations'].append(r);write(attempt_path,attempt,fresh=False)
 need(r['returncode']==0,'Actual observation failed: '+str(argv));return r['stdout']
ssh=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(O/'compute20_known_hosts_v1'),NODE]
try:
 start=time.monotonic()
 raw=capture(['scontrol','show','node',NODE]);v=dict(re.findall(r'(CPUAlloc|CPUTot|RealMemory|AllocMem)=(\d+)',raw))
 need(len(v)==4 and int(v['CPUTot'])-int(v['CPUAlloc'])>=16 and not any(x in raw for x in ['State=DOWN','DRAIN','FAIL']),'No actual CPU/node headroom')
 prior=0.0
 for line in capture(['squeue','-h','-w',NODE,'-o','%i|%u|%t|%m|%C']).splitlines():
  fields=line.split('|')
  if fields[2] not in ('R','CG'):continue
  m=re.fullmatch(r'(\d+(?:\.\d+)?)([KMGT]?)([cn]?)',fields[3]);need(m is not None,'Unknown all-user memory declaration')
  prior+=float(m[1])*{'':1,'K':1/1024,'M':1,'G':1024,'T':1024**2}[m[2]]*(int(fields[4]) if m[3]=='c' else 1)
 commitment=max(prior,int(v['AllocMem']))
 need(commitment+MEM<.85*int(v['RealMemory']),'All-user declared memory85% admission failed')
 mem=capture(ssh+['head -n 5 /proc/meminfo']);available=int(re.search(r'MemAvailable:\s+(\d+) kB',mem)[1])/1024
 need(available>=MEM+.15*int(v['RealMemory']),'Actual MemAvailable reserve failed')
 qraw=capture(['quota','-v','-u','zixiao']);rows=[x.split() for x in qraw.splitlines() if x.split() and x.split()[0]=='/dev/sda1']
 need(len(rows)==1,'Actual quota row absent');used,soft,hard=[int(rows[0][x].rstrip('*')) for x in (1,2,3)]
 limits=[x for x in [soft,hard] if x>0];need(limits,'Quota limit unknown');free=(min(limits)-used)*1024
 live=read(REG);need(live['reservations']['performance_manual_R2_4090_v1']==entry,'Independent hold changed')
 need(all(type(x['remaining_bytes']) is int and x['remaining_bytes']>=0 for x in live['reservations'].values()),'Unknown holds')
 remaining=sum(x['remaining_bytes'] for x in live['reservations'].values())
 need(free>=remaining+64*1024**3,'Quota must cover every registered hold plus64GiB reserve')
 quota=write(CONTROL/'Root_quota_actual_v1.json',dict(schema='model_v3_Root_actual_quota_observation_v1',authority='ROOT_ACTUAL',
captured_unix=time.time(),raw_quota=qraw,used_KiB=used,soft_KiB=soft,hard_KiB=hard,available_bytes=free,
remaining_all_registered_bytes=remaining,additional_reserve_bytes=64*1024**3,hold=hold))
 gpu_raw=capture(ssh+['nvidia-smi --query-gpu=uuid,name,driver_version,memory.total,memory.free,memory.used --format=csv,noheader,nounits'])
 selected=[x for x in csv.reader(gpu_raw.splitlines(),skipinitialspace=True) if x and x[0].strip()==GPU]
 need(len(selected)==1 and len(selected[0])==6 and '4090' in selected[0][1],'Exact selected4090 missing')
 gpu=selected[0];need(0<=int(gpu[5])<=int(gpu[3]) and int(gpu[4])>0,'GPU memory fields invalid')
 apps_raw=capture(ssh+['nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader,nounits'])
 for row in csv.reader(apps_raw.splitlines(),skipinitialspace=True):
  if not row or row==['No running processes found']:continue
  need(len(row)==4 and row[0].startswith('GPU-') and row[1].strip().isdigit(),'Unknown NVML compute-process observation')
  need(row[0].strip()!=GPU,'Selected GPU occupied; never signal foreign processes')
 lock=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
 capture(ssh+['flock -n '+str(lock)+' true'])
 need(time.monotonic()-start<=120,'Fresh Root resource frame expired')
 frame=write(CONTROL/'Root_admission_actual_v1.json',dict(schema='model_v3_manual_R2_Root_actual_admission_v1',authority='ROOT_ACTUAL',
captured_unix=time.time(),node=NODE,gpu_uuid=GPU,cpus=16,requested_memory_MiB=MEM,prior_all_user_declared_MiB=prior,
prior_AllocMem_MiB=int(v['AllocMem']),prior_commitment_MiB=commitment,RealMemory_MiB=int(v['RealMemory']),
MemAvailable_MiB=available,selected_GPU_fields=gpu,selected_compute_processes=[],quota=quota,hold=hold,
resources_raw_observations=attempt['observations'],UUID_lock_checked_and_released=True,GPU_GRES_isolation_claimed=False,
worker_must_revalidate_actual_UUID_foreign_processes_and_caps=True,freshness_seconds=time.monotonic()-start))
 env={**os.environ,'MODEL_V3_GPU_UUID':GPU,'MODEL_V3_EXPECTED_NODE':NODE,'MODEL_V3_OUT':str(OUT),'MODEL_V3_RECORD':str(RECORD),
'MODEL_V3_PACKAGE_PINS_SHA256':pins['sha256']}
 for name,r in [('MODEL_V3_ROOT_ADMISSION',frame),('MODEL_V3_QUOTA',quota),('MODEL_V3_HOLD',hold)]:
  env[name+'_PATH']=r['path'];env[name+'_SHA256']=r['sha256']
 argv=['sbatch','--parsable','--partition=all','--nodelist='+NODE,'--cpus-per-task=16','--mem=65536M','--time=02:00:00',
'--output='+str(CONTROL/'slurm_%j.log'),str(SB)]
 attempt.update(status='SUBMISSION_INTENT_PERSISTED',admission=frame,quota=quota,bindings={k:env[k] for k in env if k.startswith('MODEL_V3_')},argv=argv)
 write(attempt_path,attempt,fresh=False);intent=True
 need(time.monotonic()-start<=120,'Resource frame became stale before sbatch')
 r=command(argv,45,env);attempt['observations'].append(r)
 m=re.fullmatch(r'(\d+)(?:;[A-Za-z0-9_.-]+)?',r['stdout'].strip())
 need(r['returncode']==0 and m is not None,'Unconfirmed sbatch outcome; inspect before retry')
 attempt.update(status='SUBMITTED',job_id=m[1],finished_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
 write(attempt_path,attempt,fresh=False)
 print(json.dumps(dict(status='SUBMITTED',job_id=m[1],receipt=ref(attempt_path),family=str(FAMILY),gpu_uuid=GPU,resource_freshness_seconds=time.monotonic()-start)),flush=True)
except Exception as e:
 attempt.update(status='SUBMISSION_OUTCOME_UNKNOWN_DO_NOT_RETRY' if intent else 'FAILED_BEFORE_SBATCH_NO_AUTORETRY',exception=type(e).__name__,message=str(e))
 write(attempt_path,attempt,fresh=False);raise
