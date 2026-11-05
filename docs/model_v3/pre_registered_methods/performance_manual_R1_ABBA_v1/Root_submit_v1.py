"""One explicit Root submission of a fixed manualR1 ABBA member; no dispatcher or automatic retry."""
import argparse,ast,csv,datetime,hashlib,json,os,pathlib,re,socket,stat,subprocess,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';O=B/'runs/model_v3_20261025'
W=B/'MFM_model_v3_performance_integration_v1';PKG=N/'performance_manual_R1_ABBA_GPU_v1_source'
SERIES_ROOT=N/'performance_manual_R1_ABBA_v1';SERIES='A00_manual_R1_C35_9e16_v1'
ROLES=('reference','candidate','candidate','reference')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--position',type=int,choices=(1,2,3,4),required=True)
parser.add_argument('--method-publication',type=pathlib.Path,required=True)
parser.add_argument('--method-publication-sha256',required=True)
args=parser.parse_args()
POSITION=args.position;ROLE=ROLES[POSITION-1]
RESERVATION_ID='performance_manual_R1_ABBA_v1_member_'+str(POSITION)
FAMILY=SERIES_ROOT/('member_'+str(POSITION));CONTROL=FAMILY/'control';OUT=FAMILY/'child';RECORD=FAMILY/'supervisor.json'
NODE='compute-0-21';GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243';MEM=65536;LIMIT=2147483648
GIT=O/'cpu_git_tools_v1/bin/git';SB=PKG/'run_manual_R1_ABBA.sbatch';REG=N/'native_S_profile_registered_reservations_v6.json'
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

def bound(item):
 need(isinstance(item,dict) and set(item)=={'path','bytes','sha256'} and ref(item['path'])==item,'Exact small rawref changed')
 return read(item['path'])
def canonical(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
def parent_c0(raw,job):
 argv=['sacct','-X','-n','-P','-j',job,'--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList']
 need(raw['argv']==argv and raw['returncode']==0 and raw['stderr']=='','Exact successful parent sacct observation required')
 rows=[line.split('|') for line in raw['stdout'].splitlines() if line.strip()]
 need(len(rows)==1 and len(rows[0])==7 and rows[0][0]==job and rows[0][1:4]==['zixiao','COMPLETED','0:0']
      and rows[0][4].isdigit() and int(rows[0][4])>0 and rows[0][5:]==['16',NODE],'Actual owned CPU16/node21 parent C0 required')
def stat_only(item,root,cap):
 need(isinstance(item,dict) and set(item)=={'path','bytes'},'Root stat-only artifact descriptor required')
 path=pathlib.Path(item['path']);s=path.lstat()
 need(path.is_absolute() and path.resolve()==path and path.is_relative_to(root)
      and stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_nlink==1
      and 0<s.st_size==item['bytes']<=cap,'Durable original step/SDK stat differs')
 return dict(path=str(path),bytes=s.st_size,device=s.st_dev,inode=s.st_ino,mtime_ns=s.st_mtime_ns,
             uid=s.st_uid,nlink=s.st_nlink,payload_opened=False,independent_native_verification=False)
def predecessor(pins,pack,deps):
 if POSITION==1:return None
 number=POSITION-1;role=ROLES[number-1]
 family=SERIES_ROOT/('member_'+str(number));output=family/'child'
 path=family/'control/Root_closure_actual_v1.json';proof=ref(path);closed=bound(proof)
 need(closed['schema']=='model_v3_Root_single_R1_ABBA_member_closure_v1'
      and closed['status']=='ACTUAL_C0_SOURCE_INPUT_22_UPDATES_TRAINER_SDK_FINISHED'
      and type(closed['position']) is int and closed['position']==number and closed['role']==role
      and closed['series_id']==SERIES and closed['source_package']==pins,'Previous actual Root member closure required')
 job=closed['job_id'];need(type(job) is str and job.isdigit(),'Actual previous parent job ID required')
 parent_c0(closed['actual_sacct'],job)
 expected=dict(configuration=output/'configuration.json',summary=output/'summary.json',
               run_status=output/'run_status.json',supervisor=family/'supervisor.json')
 values={}
 for key,target in expected.items():
  need(closed[key]['path']==str(target),'Previous member rawref location differs')
  values[key]=bound(closed[key])
 cfg,summary,status,sup=[values[k] for k in ('configuration','summary','run_status','supervisor')]
 need(str(cfg['job_id'])==str(sup['job_id'])==job and cfg['node'].split('.')[0]==NODE
      and cfg['gpu_uuid']==summary['gpu_uuid']==sup['gpu_uuid']==GPU,'Previous actual GPU/job/node identity differs')
 need(cfg['role']==summary['role']==role and cfg['abba_position']==summary['abba_position']==number
      and cfg['series_id']==summary['series_id']==SERIES,'Previous actual ABBA identity differs')
 need(summary['status']==status['status']=='STANDALONE_TIMING_COMPLETED' and summary['warmup_updates']==2
      and summary['measured_updates']==20 and summary['smoke'] is cfg['smoke'] is False
      and cfg['seed']==summary['seed']==0 and cfg['input']==summary['input']=='native_s'
      and summary['foreign_gpu_risk_observed'] is False and summary['padding_exploration'] is False
      and summary['tracking_mode']=='offline','Previous complete original standalone2+20 scope differs')
 need(status['failure'] is None and status['cleanup_errors']==[] and status['stream_cleanup']['errors']==[]
      and status['stream_cleanup']['input_descriptors_closed'] is True,'Previous trainer/input/SDK cleanup failed')
 need(sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
      and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
      and sup['foreign_gpu_processes_signalled'] is False,'Previous original supervisor/private closure failed')
 need(sup['supervisor_source_sha256']==deps['raw_refs']['supervisor_source']['sha256'],'Previous original guard source differs')
 need(cfg['code_sha']==summary['code_sha']=='9e16d4c5a15c558051499d3dc0c55c9bd3787734'
      and cfg['prereg_sha']==summary['prereg_sha']=='8147f44baa1ea1ecc3822af7affd0a95401ed248'
      and cfg['candidate_options_sha256']==summary['candidate_options_sha256']==deps['raw_refs']['candidate_options']['sha256']
      and cfg['performance_execution_request']==deps['raw_refs']['manual_execution'],'Previous original input options/source differs')
 need(canonical({k:v for k,v in cfg.items() if k!='configuration_sha256'})
      ==cfg['configuration_sha256']==summary['configuration_sha256'],'Previous saved configuration hash differs')
 original=bound(deps['raw_refs']['R2_numeric_configuration'])
 for key in ('model','optimizer','loss_policy','loss_weights','supervision','schedule','reference_configuration',
             'a4_configuration','original_shard_snapshot_prejob_sha256','data_version'):
  need(cfg[key]==original[key],'Previous original native workload changed: '+key)
 mandatory=original['performance_execution']['implementation_sha256']
 need(isinstance(cfg['source_sha256'],dict) and set(mandatory)<=set(cfg['source_sha256'])
      and all(cfg['source_sha256'][name]==sha for name,sha in mandatory.items()),'Previous actual complete mandatory source graph differs')
 for name,sha in cfg['source_sha256'].items():
  relative=pathlib.Path(name)
  need(not relative.is_absolute() and '..' not in relative.parts and relative.suffix=='.py'
       and pack['full_current_source_map'].get(str(W/relative))==sha
       and ref(W/relative)['sha256']==sha,'Previous saved/current source drift')
 if role=='candidate':
  execution=cfg['performance_execution']
  need(execution['requested']['resident_models']==1 and execution['requested']['checkpoint_policy']=='manual'
       and execution['requested']['padding'] is None and execution['requested']['batch_padded_cost']==8000000
       and execution['implementation_sha256']==mandatory
       and all(execution['resolved_options'][key] is True for key in ('backbone_checkpointing','distance_checkpointing','head_checkpointing')),
       'Previous candidate is not this actual manualR1 execution')
 else:
  need(cfg['performance_execution'].get('applied') is False,'Previous reference must keep original execution')
 # No SDK or journal payload is opened/hashed here. Original finish is proven by fixed source + actual clean C0.
 need(closed['trainer_SDK_finish_completed'] is True and closed['SDK_native_stream_independent_audit_pending'] is True
      and closed['step_journal_body_independent_audit_pending'] is True,'Per-member versus deferred batch SDK scope differs')
 run_id=summary['tracking_run_id']
 need(closed['tracking_run_id']==run_id and type(run_id) is str and re.fullmatch(r'[a-z0-9]{8}',run_id),'Previous actual SDK run identity differs')
 sdk=stat_only(closed['SDK'],output,128<<20);journal=stat_only(closed['step_journal'],output,32<<20)
 sdk_path=pathlib.Path(sdk['path'])
 need(sdk_path.parent.parent==output/'wandb' and sdk_path.parent.name.startswith('offline-run-')
      and sdk_path.parent.name.endswith('-'+run_id) and sdk_path.name=='run-'+run_id+'.wandb'
      and journal['path']==str(output/'steps.jsonl'),'Previous durable original SDK/journal location differs')
 submission=bound(closed['submission'])
 need(closed['submission']['path']==str(family/'control/Root_submission_actual_v1.json')
      and submission['status']=='SUBMITTED' and submission['job_id']==job
      and submission['source_package']==pins,'Previous actual submission differs')
 fresh=command(closed['actual_sacct']['argv'],30);parent_c0(fresh,job)
 return dict(closure=proof,position=number,role=role,job_id=job,actual_sacct_fresh=fresh,
             bound_metadata={key:closed[key] for key in expected},SDK_stat=sdk,step_journal_stat=journal,
             SDK_native_verification_deferred_until_all_four=True,no_SDK_or_journal_payload_read=True)

need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),'Root login metadata only')
for task_git_args,expected in [(['rev-parse','HEAD'],'9e16d4c5a15c558051499d3dc0c55c9bd3787734'),(['rev-parse','HEAD^{tree}'],'98b3b4bd8bc083a4150f536024e4dc81e6fb6108'),(['status','--porcelain=v1','--untracked-files=all'],'')]:
 r=command([str(GIT),'-C',str(W),*task_git_args]);need(r['returncode']==0 and r['stdout'].strip()==expected,'Exact clean tested W/code/tree required')
pins=ref(PKG/'source_pins.json');need(pins['sha256']=='51a5d9c0d8aa5ab708bea6b04d33044e7a555d41e16492dc0e1e0857777aad89','Frozen source package differs')
for item in read(PKG/'source_pins.json')['files']:
 actual=ref(item['path']);need(all(actual[k]==item[k] for k in actual),'Frozen package leaf drift')
frozen=read(PKG/'source_pins.json')
need(ref(SB) in frozen['files'],'Direct fixed package SB must be frozen')
for item in frozen['protected_dependencies']:need(ref(item['path'])==item,'Current protected source/closed metadata drift')
deps=read(PKG/'dependencies.json')
code_publication=bound(deps['raw_refs']['publication'])
need(code_publication['local_code_sha']==deps['code_sha']=='9e16d4c5a15c558051499d3dc0c55c9bd3787734'
     and code_publication['public_commit_sha']==deps['public_prereg_sha']=='8147f44baa1ea1ecc3822af7affd0a95401ed248'
     and code_publication['tree_sha']==deps['tree_sha']=='98b3b4bd8bc083a4150f536024e4dc81e6fb6108'
     and code_publication['actual_readback'][deps['branch']]==deps['public_prereg_sha']
     and code_publication['actual_public_git_tree']==deps['tree_sha']
     and code_publication['force'] is False and code_publication['main_modified'] is False,'Actual tested model publication differs')
for item in code_publication['source_files']:need(ref(W/item['path'])['sha256']==item['sha256'],'Actual model public leaf drift')
pack=read(N/'performance_packaging_CPU_4523705_Root_closure_v1.json')
for path,h in pack['full_current_source_map'].items():need(ref(path)['sha256']==h,'Current complete tested source drift')

OPUB=args.method_publication.absolute();operation_ref=ref(OPUB)
need(operation_ref['sha256']==args.method_publication_sha256,'Actual operations publication rawSHA differs')
operations=read(OPUB)
need(operations['schema']=='model_v3_exact_tree_publication_actual_v1'
     and operations['repository_full_name']=='mint258/MFM' and operations['branch']=='model-v3'
     and operations['public_branch_readback_verified'] is True
     and operations['public_Git_API_tree_readback_verified'] is True
     and all(isinstance(operations[key],str) and re.fullmatch('[0-9a-f]{40}',operations[key])
             for key in ('local_code_sha','public_code_sha','tree_sha')),
     'Actual generic exact-tree/readback operations publication required')
published={row['path']:row for row in operations['files']}
need(len(published)==len(operations['files']),'Duplicate published paths')
prefix='docs/model_v3/pre_registered_methods/performance_manual_R1_ABBA_v1/'
operation_files={name:PKG/name for name in ('run_manual_R1_ABBA.sbatch','dependencies.json','METHODS_README.md','source_pins.json')}
operation_files['Root_submit_v1.py']=pathlib.Path(__file__).absolute()
for name,path in operation_files.items():
 raw=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest()
 item=published[prefix+name]
 need(item['type']=='blob' and item['sha']==blob,'Current one-member operation source not exact published Git blob: '+name)
previous=predecessor(pins,pack,deps)

need(not FAMILY.exists() and not OUT.exists() and not RECORD.exists(),'Fresh single-use selected R1 member required; preserve failed/unknown attempts')
CONTROL.mkdir(parents=True,mode=0o700)
registry=read(REG);before=ref(REG);need(RESERVATION_ID not in registry['reservations'],'No duplicate hold')
write(CONTROL/'registry_before.json',registry)
principal=dict(schema='model_v3_Root_one_job_output_reservation_v1',authority='ROOT_ACTUAL',uid=1278,filesystem='/dev/sda1',
reservation_id=RESERVATION_ID,phase=str(FAMILY),max_bytes=LIMIT,reserved_additional_bytes=LIMIT,
initial_existing_bytes=0,status='ROOT_RESERVED_FINITE_SINGLE_GPU_TASK',scientific_acceptance=False,source_package=pins)
pr=write(CONTROL/'principal.json',principal)
entry=dict(phase=str(FAMILY),principal=pr,principal_sha256=pr['sha256'],remaining_bytes=LIMIT)
registry['reservations'][RESERVATION_ID]=entry
need(ref(REG)==before,'Live registry changed before addition')
write(REG,registry,fresh=False)
hold=write(CONTROL/'Root_hold_actual_v1.json',dict(schema='model_v3_Root_independent_output_hold_v1',authority='ROOT_ACTUAL',registry_path=str(REG),
reservation_id=RESERVATION_ID,entry_snapshot=entry,principal=pr,reserved_additional_bytes=LIMIT,
Native_S_principal_or_counters_changed=False,physical_allocation_of_2GiB_file_claimed=False,original_registry_before=ref(CONTROL/'registry_before.json')))
attempt_path=CONTROL/'Root_submission_actual_v1.json'
attempt=dict(schema='model_v3_manual_R1_ABBA_Root_single_submission_v1',status='ADMISSION_STARTED',job_id=None,source_package=pins,installed_sbatch=ref(SB),
Root_driver=ref(__file__),operations_publication=ref(OPUB),hold=hold,observations=[] if previous is None else [previous['actual_sacct_fresh']],position=POSITION,role=ROLE,series_id=SERIES,predecessor=previous,GPU_GRES_isolation_claimed=False,automatic_retry=False)
write(attempt_path,attempt)
intent=False
def capture(argv,timeout=45):
 r=command(argv,timeout);attempt['observations'].append(r);write(attempt_path,attempt,fresh=False)
 need(r['returncode']==0,'Actual observation failed: '+str(argv));return r['stdout']
ssh=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(O/'compute21_known_hosts_v1'),NODE]
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
 live=read(REG);need(live['reservations'][RESERVATION_ID]==entry,'Independent hold changed')
 need(all(type(x['remaining_bytes']) is int and x['remaining_bytes']>=0 for x in live['reservations'].values()),'Unknown holds')
 remaining=sum(x['remaining_bytes'] for x in live['reservations'].values())
 need(free>=remaining+64*1024**3,'Quota must cover every registered hold plus64GiB reserve')
 quota=write(CONTROL/'Root_quota_actual_v1.json',dict(schema='model_v3_Root_actual_quota_observation_v1',authority='ROOT_ACTUAL',
captured_unix=time.time(),raw_quota=qraw,used_KiB=used,soft_KiB=soft,hard_KiB=hard,available_bytes=free,
remaining_all_registered_bytes=remaining,additional_reserve_bytes=64*1024**3,hold=hold))
 gpu_raw=capture(ssh+['nvidia-smi --query-gpu=uuid,name,driver_version,memory.total,memory.free,memory.used --format=csv,noheader,nounits'])
 selected=[x for x in csv.reader(gpu_raw.splitlines(),skipinitialspace=True) if x and x[0].strip()==GPU]
 need(len(selected)==1 and len(selected[0])==6 and '5090' in selected[0][1],'Exact selected5090 missing')
 gpu=selected[0];need(0<=int(gpu[5])<=int(gpu[3]) and int(gpu[4])>0,'GPU memory fields invalid')
 apps_raw=capture(ssh+['nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader,nounits'])
 for row in csv.reader(apps_raw.splitlines(),skipinitialspace=True):
  if not row or row==['No running processes found']:continue
  need(len(row)==4 and row[0].startswith('GPU-') and row[1].strip().isdigit(),'Unknown NVML compute-process observation')
  need(row[0].strip()!=GPU,'Selected GPU occupied; never signal foreign processes')
 lock=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
 capture(ssh+['flock -n '+str(lock)+' true'])
 need(time.monotonic()-start<=120,'Fresh Root resource frame expired')
 frame=write(CONTROL/'Root_admission_actual_v1.json',dict(schema='model_v3_manual_R1_ABBA_Root_actual_admission_v1',authority='ROOT_ACTUAL',
captured_unix=time.time(),node=NODE,gpu_uuid=GPU,cpus=16,requested_memory_MiB=MEM,prior_all_user_declared_MiB=prior,
prior_AllocMem_MiB=int(v['AllocMem']),prior_commitment_MiB=commitment,RealMemory_MiB=int(v['RealMemory']),
MemAvailable_MiB=available,selected_GPU_fields=gpu,selected_compute_processes=[],quota=quota,hold=hold,
resources_raw_observations=attempt['observations'],UUID_lock_checked_and_released=True,GPU_GRES_isolation_claimed=False,
worker_must_revalidate_actual_UUID_foreign_processes_and_caps=True,freshness_seconds=time.monotonic()-start))
 env={**os.environ,'MODEL_V3_ABBA_SERIES_ID':SERIES,'MODEL_V3_ABBA_POSITION':str(POSITION),'MODEL_V3_ABBA_ROLE':ROLE,'MODEL_V3_GPU_UUID':GPU,'MODEL_V3_EXPECTED_NODE':NODE,'MODEL_V3_OUT':str(OUT),'MODEL_V3_RECORD':str(RECORD),
'MODEL_V3_PACKAGE_PINS_SHA256':pins['sha256']}
 for name,r in [('MODEL_V3_ROOT_ADMISSION',frame),('MODEL_V3_QUOTA',quota),('MODEL_V3_HOLD',hold)]:
  env[name+'_PATH']=r['path'];env[name+'_SHA256']=r['sha256']
 argv=['sbatch','--parsable','--export=ALL','--partition=all','--nodelist='+NODE,'--cpus-per-task=16','--mem=65536M','--time=02:00:00',
'--output='+str(CONTROL/'slurm_%j.log'),str(SB)]
 attempt.update(status='SUBMISSION_INTENT_PERSISTED',admission=frame,quota=quota,bindings={k:env[k] for k in env if k.startswith('MODEL_V3_')},argv=argv)
 write(attempt_path,attempt,fresh=False);intent=True
 need(time.monotonic()-start<=120,'Resource frame became stale before sbatch')
 r=command(argv,45,env);attempt['observations'].append(r)
 m=re.fullmatch(r'(\d+)(?:;[A-Za-z0-9_.-]+)?',r['stdout'].strip())
 need(r['returncode']==0 and m is not None,'Unconfirmed sbatch outcome; inspect before retry')
 attempt.update(status='SUBMITTED',job_id=m[1],finished_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
 write(attempt_path,attempt,fresh=False)
 print(json.dumps(dict(status='SUBMITTED',job_id=m[1],receipt=ref(attempt_path),family=str(FAMILY),position=POSITION,role=ROLE,series_id=SERIES,gpu_uuid=GPU,resource_freshness_seconds=time.monotonic()-start)),flush=True)
except Exception as e:
 attempt.update(status='SUBMISSION_OUTCOME_UNKNOWN_DO_NOT_RETRY' if intent else 'FAILED_BEFORE_SBATCH_NO_AUTORETRY',exception=type(e).__name__,message=str(e))
 write(attempt_path,attempt,fresh=False);raise

