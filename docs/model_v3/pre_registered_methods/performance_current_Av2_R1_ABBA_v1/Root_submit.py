"""One selected current-A-v2 R1 member; original resource/hold flow, no loop or retry."""
import argparse,ast,csv,datetime,hashlib,json,os,pathlib,re,socket,stat,subprocess,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';O=B/'runs/model_v3_20261025'
W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1';PKG=N/'performance_current_Av2_R1_ABBA_v1_source'
NODE='compute-0-21';GPU='GPU-c35f2434-9137-9723-1af5-dc69b6295243';MEM=65536;LIMIT=2147483648
GIT=O/'cpu_git_tools_v1/bin/git';SB=PKG/'run_R1_ABBA.sbatch';REG=N/'native_S_profile_registered_reservations_v6.json'
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
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--method-publication',type=pathlib.Path,required=True)
parser.add_argument('--method-publication-sha256',required=True)
parser.add_argument('--source-pins-sha256',required=True)
parser.add_argument('--case',choices=('a00_manual','head_off'),required=True)
parser.add_argument('--position',type=int,choices=(1,2,3,4),required=True)
parser.add_argument('--SDK-closure',type=pathlib.Path,required=True)
parser.add_argument('--SDK-closure-sha256',required=True)
cli=parser.parse_args()
CASE=cli.case;POSITION=cli.position;ROLE=('reference','candidate','candidate','reference')[POSITION-1]
plan=read(PKG/'PLAN.json');case_spec=plan['cases'][CASE];SERIES=case_spec['series_id']
SERIES_ROOT=pathlib.Path(case_spec['family']);FAMILY=SERIES_ROOT/('member_'+str(POSITION))
CONTROL=FAMILY/'control';OUT=FAMILY/'child';RECORD=FAMILY/'supervisor.json'
RESERVATION_ID='current_Av2_R1_'+CASE+'_v1_member_'+str(POSITION)
need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),'Root login metadata only')
for task_git_args,expected in [(['rev-parse','HEAD'],'7ffe8a5557590b1481f4ca74073007f070dc6a50'),(['rev-parse','HEAD^{tree}'],'8f9530415034bdb885c1c765aee434797c70e7c7'),(['status','--porcelain=v1','--untracked-files=all'],'')]:
 r=command([str(GIT),'-C',str(W),*task_git_args]);need(r['returncode']==0 and r['stdout'].strip()==expected,'Exact clean tested W/code/tree required')
pins=ref(PKG/'source_pins.json');need(pins['sha256']==cli.source_pins_sha256,'Frozen source package differs')
for item in read(PKG/'source_pins.json')['files']:
 actual=ref(item['path']);need(all(actual[k]==item[k] for k in actual),'Frozen package leaf drift')
need(ref(SB) in read(PKG/'source_pins.json')['files'],'Actual fixed package SB must be frozen')
# Same current-source guard and original paired gate, plus actual SDK closure.
# No model imports, journal/SDK payload reads, auto resolution or profile reuse.
import importlib.util
spec=importlib.util.spec_from_file_location('current_Av2_R1_metadata',PKG/'admission.py')
metadata=importlib.util.module_from_spec(spec);spec.loader.exec_module(metadata)
metadata.verify_package(cli.source_pins_sha256)
sdk_ref=ref(cli.SDK_closure.absolute())
need(sdk_ref['sha256']==cli.SDK_closure_sha256,'Actual SDK closure raw SHA differs')
qualification=metadata.qualify(CASE,sdk_ref)
numeric_configuration=qualification['configuration']
# Fresh accounting for all actual SDK parents and the separate4717 consumer.
expected={}
for text in qualification['SDK']['actual_sacct']['stdout'].splitlines():
 if text.strip():
  columns=text.split('|');expected[columns[0]]=columns[-1]
numeric=metadata.bound(case_spec['numeric_closure'])
if CASE=='a00_manual':
 for text in numeric['actual_sacct']['stdout'].splitlines():
  if text.strip():
   columns=text.split('|');expected[columns[0]]=columns[-1]
fresh_numeric=command(['sacct','-X','-n','-P','-j',','.join(sorted(expected)),
 '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],30)
rows=[text.split('|') for text in fresh_numeric['stdout'].splitlines() if text.strip()]
need(fresh_numeric['returncode']==0 and fresh_numeric['stderr']=='' and len(rows)==len(expected)
 and {r[0] for r in rows}==set(expected) and all(len(r)==7 and r[1:4]==['zixiao','COMPLETED','0:0']
 and r[4].isdigit() and r[5]=='16' and r[6]==expected[r[0]] for r in rows),'Fresh original numeric/SDK C0 accounting required')
OPUB=cli.method_publication.absolute();operation_ref=ref(OPUB)
need(operation_ref['sha256']==cli.method_publication_sha256,'Actual operations publication rawSHA differs')
operations=read(OPUB)
metadata.verify_method(operation_ref)
# Previous new member must be complete before this sole selected submission.
# This is metadata readiness only; Root closes all four and later audits SDKs.
previous=None
if POSITION>1:
 number=POSITION-1;prior_family=SERIES_ROOT/('member_'+str(number));output=prior_family/'child'
 receipt_ref=ref(prior_family/'control/Root_submission_actual_v1.json');receipt=metadata.bound(receipt_ref)
 need(receipt['status']=='SUBMITTED' and receipt['source_package']==pins and receipt['case']==CASE
      and receipt['series_id']==SERIES and receipt['position']==number
      and receipt['numeric_qualification']==case_spec['numeric_closure'] and receipt['SDK_qualification']==sdk_ref,
      'Previous new member submission/qualification differs')
 job=receipt['job_id'];need(type(job) is str and job.isdigit(),'Previous real job ID required')
 member_refs={k:ref(p) for k,p in dict(configuration=output/'configuration.json',summary=output/'summary.json',
   run_status=output/'run_status.json',supervisor=prior_family/'supervisor.json').items()}
 cfg,summary,status,sup=[metadata.bound(member_refs[k]) for k in ('configuration','summary','run_status','supervisor')]
 need(cfg['job_id']==sup['job_id']==job and cfg['node'].split('.')[0]==NODE
      and cfg['gpu_uuid']==summary['gpu_uuid']==sup['gpu_uuid']==GPU,'Previous actual GPU/job/node differs')
 prior_role=('reference','candidate','candidate','reference')[number-1]
 need(cfg['role']==summary['role']==prior_role and cfg['abba_position']==summary['abba_position']==number
      and cfg['series_id']==summary['series_id']==SERIES
      and cfg['code_sha']==summary['code_sha']==plan['code_sha']
      and cfg['prereg_sha']==summary['prereg_sha']==plan['public_prereg_sha']
      and cfg['candidate_options_sha256']==summary['candidate_options_sha256']==case_spec['candidate_options']['sha256'],
      'Previous complete new member identity differs')
 need(summary['status']==status['status']=='STANDALONE_TIMING_COMPLETED' and summary['warmup_updates']==2
      and summary['measured_updates']==20 and summary['smoke'] is cfg['smoke'] is False
      and summary['seed']==cfg['seed']==0 and summary['input']==cfg['input']=='native_s'
      and summary['foreign_gpu_risk_observed'] is summary['padding_exploration'] is False
      and summary['tracking_mode']=='offline','Previous original2+20 scope differs')
 need(status['failure'] is None and status['cleanup_errors']==[] and status['stream_cleanup']['errors']==[]
      and status['stream_cleanup']['input_descriptors_closed'] is True,'Previous original trainer/SDK finish not clean')
 need(sup['status']=='COMPLETED' and sup['exit_code']==0 and sup['first_failure'] is None
      and sup['remaining_recorded_processes_before_retirement']==[] and sup['private_storage_cleanup_errors']==[]
      and sup['foreign_gpu_processes_signalled'] is False,'Previous supervisor/private cleanup not closed')
 need(cfg['configuration_sha256']==summary['configuration_sha256']==metadata.canonical(
      {k:v for k,v in cfg.items() if k!='configuration_sha256'}),'Previous configuration canonical hash differs')
 for key in ('model','optimizer','loss_policy','loss_weights','supervision','schedule','reference_configuration',
             'a4_configuration','original_shard_snapshot_prejob_sha256','data_version','candidate'):
  need(cfg[key]==numeric_configuration[key],'Previous original numeric workload differs: '+key)
 mandatory=numeric_configuration['performance_execution']['implementation_sha256']
 need(set(mandatory)<=set(cfg['source_sha256']) and all(cfg['source_sha256'][k]==v for k,v in mandatory.items()),
      'Previous complete same-source mandatory projection differs')
 for name,digest in cfg['source_sha256'].items():
  rel=pathlib.Path(name)
  need(not rel.is_absolute() and '..' not in rel.parts and metadata.reference(W/rel)['sha256']==digest,
       'Previous saved/current implementation source differs')
 if prior_role=='candidate':
  execution=cfg['performance_execution']
  need(execution['requested']['resident_models']==1 and execution['requested']['checkpoint_policy']=='manual'
       and execution['requested']['padding'] is None and execution['requested']['capacity_profile'] is None
       and execution['resolved_options']==numeric_configuration['candidate']
       and execution['implementation_sha256']==mandatory,'Previous actual single-resident manual candidate differs')
 else:
  need(cfg['performance_execution'].get('applied') is False and cfg['effective_options']==numeric_configuration['reference'],
       'Previous reference must keep original execution')
 need(cfg['performance_execution_request']==numeric_configuration['performance_execution_request']
      and sup['supervisor_source_sha256']==metadata.reference(W/'tools/model_v3/run_supervised.py')['sha256'],
      'Previous explicit manual request/guard source differs')
 run=summary['tracking_run_id'];need(type(run) is str and re.fullmatch('[a-z0-9]{8}',run),'Previous SDK identity required')
 sdk_paths=list((output/'wandb').glob('offline-run-*/run-'+run+'.wandb'))
 need(len(sdk_paths)==1,'One original finished SDK path required')
 descriptors={}
 for label,path,cap in [('SDK',sdk_paths[0],128<<20),('steps',output/'steps.jsonl',32<<20)]:
  info=path.lstat()
  need(stat.S_ISREG(info.st_mode) and info.st_uid==1278 and info.st_nlink==1
       and path.resolve()==path and path.is_relative_to(output) and 0<info.st_size<=cap,'Previous stat-only artifact differs')
  descriptors[label]=dict(path=str(path),bytes=info.st_size,payload_opened=False)
 prior_sacct=command(['sacct','-X','-n','-P','-j',job,
   '--format=JobIDRaw,User,State,ExitCode,ElapsedRaw,AllocCPUS,NodeList'],30)
 metadata.load_helper(case_spec['source_guard'],'current_R1_predecessor_parent').parent(prior_sacct,job,node=NODE)
 previous=dict(submission=receipt_ref,job_id=job,metadata=member_refs,actual_sacct=prior_sacct,
               SDK_and_steps_stat_only=descriptors,independent_member_SDK_audit_pending=True)
need(not FAMILY.exists() and not OUT.exists() and not RECORD.exists(),'Fresh independent selected ABBA member required')
CONTROL.mkdir(parents=True,mode=0o700)
with metadata.registry_lock(REG):
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
attempt=dict(schema='model_v3_current_Av2_R1_ABBA_Root_single_submission_v1',status='ADMISSION_STARTED',job_id=None,source_package=pins,installed_sbatch=ref(SB),
Root_driver=ref(__file__),operations_publication=ref(OPUB),hold=hold,numeric_qualification=case_spec['numeric_closure'],SDK_qualification=sdk_ref,
case=CASE,series_id=SERIES,position=POSITION,role=ROLE,predecessor=previous,
observations=[fresh_numeric],GPU_GRES_isolation_claimed=False,automatic_retry=False)
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
 gpu=selected[0];need(int(gpu[3])>0 and 0<int(gpu[4])<=int(gpu[3]) and 0<=int(gpu[5])<=int(gpu[3]),'GPU memory fields unknown/invalid; no capacity admission')
 apps_raw=capture(ssh+['nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader,nounits'])
 for app_row in csv.reader(apps_raw.splitlines(),skipinitialspace=True):
  if not app_row or app_row==['No running processes found']:continue
  need(len(app_row)==4 and app_row[0].startswith('GPU-') and app_row[1].strip().isdigit(),'Unknown NVML compute-process observation')
  need(app_row[0].strip()!=GPU,'Selected GPU occupied; never signal foreign processes')
 lock=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
 capture(ssh+['flock -n '+str(lock)+' true'])
 need(time.monotonic()-start<=120,'Fresh Root resource frame expired')
 frame=write(CONTROL/'Root_admission_actual_v1.json',dict(schema='model_v3_current_Av2_R1_ABBA_Root_actual_admission_v1',authority='ROOT_ACTUAL',
captured_unix=time.time(),node=NODE,gpu_uuid=GPU,cpus=16,requested_memory_MiB=MEM,prior_all_user_declared_MiB=prior,
prior_AllocMem_MiB=int(v['AllocMem']),prior_commitment_MiB=commitment,RealMemory_MiB=int(v['RealMemory']),
MemAvailable_MiB=available,selected_GPU_fields=gpu,selected_compute_processes=[],quota=quota,hold=hold,
resources_raw_observations=attempt['observations'],UUID_lock_checked_and_released=True,GPU_GRES_isolation_claimed=False,
worker_must_revalidate_actual_UUID_foreign_processes_and_caps=True,freshness_seconds=time.monotonic()-start))
 env={**{k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')},
'MODEL_V3_R1_CASE':CASE,'MODEL_V3_ABBA_POSITION':str(POSITION),'MODEL_V3_ABBA_ROLE':ROLE,
'MODEL_V3_ABBA_SERIES_ID':SERIES,'MODEL_V3_CANDIDATE_OPTIONS':case_spec['candidate_options']['path'],
'MODEL_V3_GPU_UUID':GPU,'MODEL_V3_EXPECTED_NODE':NODE,'MODEL_V3_OUT':str(OUT),'MODEL_V3_RECORD':str(RECORD),
'MODEL_V3_PACKAGE_PINS_SHA256':pins['sha256']}
 for name,r in [('MODEL_V3_ROOT_ADMISSION',frame),('MODEL_V3_QUOTA',quota),('MODEL_V3_HOLD',hold),('MODEL_V3_METHOD_PUBLICATION',operation_ref),('MODEL_V3_SDK_CLOSURE',sdk_ref)]:
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
