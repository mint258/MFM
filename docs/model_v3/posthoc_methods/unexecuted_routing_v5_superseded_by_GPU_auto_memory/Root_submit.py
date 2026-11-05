"""One explicit Root selector for six declared A-v2 routes; never a retry/queue."""
import argparse,csv,datetime,hashlib,json,os,pathlib,re,socket,stat,subprocess,time
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026';O=B/'runs/model_v3_20261025'
W=B/'MFM_model_v3_A_acceptance_v2_candidate_v1'
PKG=N/'performance_remaining_Av2_20261029_routing_v5'
REG=N/'native_S_profile_registered_reservations_v6.json'
GIT=O/'cpu_git_tools_v1/bin/git';MEM=65536;LIMIT=2147483648
FILES={'PLAN.json','METHODS.md','run_remaining_Av2.sbatch','Root_submit.py','source_pins.json'}
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

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('old_job_id',choices=('4520486','4520405','4520456','4520438','4520411','4520549'))
 parser.add_argument('--method-publication',type=pathlib.Path,required=True)
 parser.add_argument('--method-publication-sha256',required=True)
 parser.add_argument('--source-pins-sha256',required=True)
 parser.add_argument('--known-hosts-sha256',help='Node0 only: exact current pre-existing ~/.ssh/known_hosts SHA; no trust edits')
 cli=parser.parse_args()
 need(os.getuid()==1278 and socket.gethostname().split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID'),'Root login metadata only')
 need(PKG.resolve()==PKG and W.resolve()==W,'Canonical existing source trees required')
 need(pathlib.Path(__file__).absolute()==PKG/'Root_submit.py','Execute only the declared live Root driver')
 pins=ref(PKG/'source_pins.json');need(pins['sha256']==cli.source_pins_sha256,'Frozen routing source differs')
 pin_document=read(PKG/'source_pins.json')
 need(pin_document['schema']=='model_v3_remaining_six_Av2_routing_sources_v2'
      and pin_document['routing_version']==5 and pin_document['source_directory']==str(PKG)
      and len(pin_document['files'])==4
      and {pathlib.Path(x['path']).name for x in pin_document['files']}==FILES-{'source_pins.json'},
      'Exact four active leaves and separate pins required')
 for item in pin_document['files']+pin_document['protected_dependencies']:
  need(ref(item['path'])==item,'Frozen operation/dependency source drift')
 planref=ref(PKG/'PLAN.json');plan=read(PKG/'PLAN.json')
 need(plan['schema']=='model_v3_remaining_six_A_cohort_v2_routing_execution_plan_v2'
      and plan['routing_version']==5 and plan['source_directory']==str(PKG)
      and plan['method_prefix']=='docs/model_v3/pre_registered_methods/performance_remaining_Av2_20261029_routing_v5/'
      and plan['current_source']['worktree']==str(W)
      and set(plan['method_files'])==FILES and len(plan['cases'])==6,'Exact routing-v5 plan required')
 rows=[x for x in plan['cases'] if x['old_job_id']==cli.old_job_id]
 need(len(rows)==1,'One original case selector required');case_spec=rows[0]
 NODE=case_spec['expected_node'];GPU=case_spec['gpu_uuid']
 need(NODE in ('compute-0-0','compute-0-20','compute-0-21') and re.fullmatch('GPU-[0-9a-f-]+',GPU),'Declared existing node/UUID required')
 need(case_spec['performance_execution_request'] is None and case_spec['old500_reused'] is False,
      'This route is ordinary original options, no manual/auto integration or old500')
 FAMILY=pathlib.Path(case_spec['family']);CONTROL=pathlib.Path(case_spec['control'])
 OUT=pathlib.Path(case_spec['child_output']);RECORD=pathlib.Path(case_spec['supervisor_record'])
 need(FAMILY.resolve()==FAMILY and FAMILY.parent==PKG/'trials'
      and CONTROL==FAMILY/'control' and OUT==FAMILY/'child' and RECORD==FAMILY/'supervisor.json',
      'Independent canonical child/control/supervisor family required')
 SB=PKG/'run_remaining_Av2.sbatch'
 for task_git_args,expected in [(['rev-parse','HEAD'],plan['current_source']['local_commit']),
                               (['rev-parse','HEAD^{tree}'],plan['current_source']['tree']),
                               (['status','--porcelain=v1','--untracked-files=all'],'')]:
  r=command([str(GIT),'-C',str(W),*task_git_args]);need(r['returncode']==0 and r['stdout'].strip()==expected,'Exact clean tested W/code/tree required')
 import importlib.util
 def load_metadata(name,source):
  need(ref(source['path'])==source,'Original metadata helper differs')
  spec=importlib.util.spec_from_file_location(name,source['path']);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  return module
 # Only current-code/full-CPU qualification; no numeric/profile reuse for this case.
 metadata=load_metadata('remaining_Av2_original_source_qualification',plan['dependencies']['existing_source_guard'])
 metadata.validate_sources()
 # Delegate ONLY the exact existing shared registry mutex, not auto/profile selection.
 lock_metadata=load_metadata('remaining_Av2_existing_shared_registry_mutex',plan['dependencies']['existing_registry_lock_delegate'])
 OPUB=cli.method_publication.absolute();operation_ref=ref(OPUB)
 need(operation_ref['sha256']==cli.method_publication_sha256,'Actual operation publication raw SHA differs')
 operations=read(OPUB)
 need(operations['schema']=='model_v3_exact_tree_publication_actual_v1'
      and operations['repository_full_name']=='mint258/MFM' and operations['branch']=='model-v3'
      and operations['public_branch_readback_verified'] is True
      and operations['public_Git_API_tree_readback_verified'] is True
      and all(type(operations[k]) is str and re.fullmatch('[0-9a-f]{40}',operations[k])
              for k in ('local_code_sha','public_code_sha','tree_sha')),
      'Actual exact-tree five-blob operation publication required')
 published={x['path']:x for x in operations['files']};need(len(published)==len(operations['files']),'Duplicate method blobs')
 for name in FILES:
  raw=(PKG/name).read_bytes();item=published[plan['method_prefix']+name]
  need(item['type']=='blob' and item['sha']==hashlib.sha1(b'blob '+str(len(raw)).encode()+bytes([0])+raw).hexdigest(),
       'Routing method source not exact published bytes: '+name)
 trust=plan['routing_trust'][NODE]
 if NODE=='compute-0-0':
  known_hosts=pathlib.Path('/share/home/zixiao/.ssh/known_hosts')
  need(trust['path']==str(known_hosts) and type(cli.known_hosts_sha256) is str
       and re.fullmatch('[0-9a-f]{64}',cli.known_hosts_sha256),'Root must bind the actual existing Node0 trust SHA')
  trust_ref=ref(known_hosts);need(trust_ref['sha256']==cli.known_hosts_sha256,'Existing personal known_hosts differs')
 else:
  need(cli.known_hosts_sha256 is None,'Projected Node20/21 trust is frozen, not caller-overridden')
  trust_ref=trust['reference'];known_hosts=pathlib.Path(trust_ref['path'])
  need(known_hosts==O/('compute21_known_hosts_v1' if NODE=='compute-0-21' else 'compute20_known_hosts_v1')
       and ref(known_hosts)==trust_ref,'Exact existing strict public host projection required')
 need(not FAMILY.exists() and not OUT.exists() and not RECORD.exists(),'Fresh one-use routed family required')
 CONTROL.mkdir(parents=True,mode=0o700)
 reservation_id='performance_remaining_Av2_routing_v5_'+cli.old_job_id
 with lock_metadata.registry_lock(REG):
  registry=read(REG);before=ref(REG);need(reservation_id not in registry['reservations'],'No duplicate hold')
  write(CONTROL/'registry_before.json',registry)
  principal=dict(schema='model_v3_Root_one_job_output_reservation_v1',authority='ROOT_ACTUAL',uid=1278,filesystem='/dev/sda1',
  reservation_id=reservation_id,phase=str(FAMILY),max_bytes=LIMIT,reserved_additional_bytes=LIMIT,
  initial_existing_bytes=0,status='ROOT_RESERVED_FINITE_SINGLE_GPU_TASK',scientific_acceptance=False,source_package=pins)
  pr=write(CONTROL/'principal.json',principal)
  entry=dict(phase=str(FAMILY),principal=pr,principal_sha256=pr['sha256'],remaining_bytes=LIMIT)
  registry['reservations'][reservation_id]=entry
  need(ref(REG)==before,'Live registry changed before addition')
  write(REG,registry,fresh=False)
  hold=write(CONTROL/'Root_hold_actual_v1.json',dict(schema='model_v3_Root_independent_output_hold_v1',authority='ROOT_ACTUAL',registry_path=str(REG),
  reservation_id=reservation_id,entry_snapshot=entry,principal=pr,reserved_additional_bytes=LIMIT,
  Native_S_principal_or_counters_changed=False,physical_allocation_of_2GiB_file_claimed=False,original_registry_before=ref(CONTROL/'registry_before.json')))
 attempt_path=CONTROL/'Root_submission_actual_v1.json'
 attempt=dict(schema='model_v3_remaining_Av2_routing_v5_Root_single_submission_v1',status='ADMISSION_STARTED',job_id=None,
 old_job_id=cli.old_job_id,declared_routing_version=5,source_package=pins,plan=planref,installed_sbatch=ref(SB),
 Root_driver=ref(__file__),operations_publication=operation_ref,hold=hold,strict_existing_host_trust=trust_ref,
 observations=[],GPU_GRES_isolation_claimed=False,automatic_retry=False,old500_or_timing_reused=False)
 write(attempt_path,attempt)
 intent=False
 def capture(argv,timeout=45):
  r=command(argv,timeout);attempt['observations'].append(r);write(attempt_path,attempt,fresh=False)
  need(r['returncode']==0,'Actual observation failed: '+str(argv));return r['stdout']
 ssh=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes',
      '-o','UserKnownHostsFile='+str(known_hosts),NODE]
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
  live=read(REG);need(live['reservations'][reservation_id]==entry,'Independent hold changed')
  need(all(type(x['remaining_bytes']) is int and x['remaining_bytes']>=0 for x in live['reservations'].values()),'Unknown holds')
  remaining=sum(x['remaining_bytes'] for x in live['reservations'].values())
  need(free>=remaining+64*1024**3,'Quota must cover every registered hold plus64GiB reserve')
  quota=write(CONTROL/'Root_quota_actual_v1.json',dict(schema='model_v3_Root_actual_quota_observation_v1',authority='ROOT_ACTUAL',
 captured_unix=time.time(),raw_quota=qraw,used_KiB=used,soft_KiB=soft,hard_KiB=hard,available_bytes=free,
 remaining_all_registered_bytes=remaining,additional_reserve_bytes=64*1024**3,hold=hold))
  gpu_raw=capture(ssh+['nvidia-smi --query-gpu=uuid,name,driver_version,memory.total,memory.free,memory.used --format=csv,noheader,nounits'])
  selected=[x for x in csv.reader(gpu_raw.splitlines(),skipinitialspace=True) if x and x[0].strip()==GPU]
  need(len(selected)==1 and len(selected[0])==6 and case_spec['expected_gpu'] in selected[0][1],'Exact selected declared GPU type missing')
  gpu=selected[0];need(int(gpu[3])>0 and 0<int(gpu[4])<=int(gpu[3]) and 0<=int(gpu[5])<=int(gpu[3]),'GPU memory fields unknown/invalid; no capacity admission')
  apps_raw=capture(ssh+['nvidia-smi --query-compute-apps=gpu_uuid,pid,used_memory,process_name --format=csv,noheader,nounits'])
  for app_row in csv.reader(apps_raw.splitlines(),skipinitialspace=True):
   if not app_row or app_row==['No running processes found']:continue
   need(len(app_row)==4 and app_row[0].startswith('GPU-') and app_row[1].strip().isdigit(),'Unknown NVML compute-process observation')
   need(app_row[0].strip()!=GPU,'Selected GPU occupied; never signal foreign processes')
  lock=B/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(GPU+'.lock')
  capture(ssh+['flock -n '+str(lock)+' true'])
  need(time.monotonic()-start<=120,'Fresh Root resource frame expired')
  frame=write(CONTROL/'Root_admission_actual_v1.json',dict(schema='model_v3_A5_R2_Root_actual_admission_v1',authority='ROOT_ACTUAL',
 captured_unix=time.time(),node=NODE,gpu_uuid=GPU,cpus=16,requested_memory_MiB=MEM,prior_all_user_declared_MiB=prior,
 prior_AllocMem_MiB=int(v['AllocMem']),prior_commitment_MiB=commitment,RealMemory_MiB=int(v['RealMemory']),
 MemAvailable_MiB=available,selected_GPU_fields=gpu,selected_compute_processes=[],quota=quota,hold=hold,
 resources_raw_observations=attempt['observations'],UUID_lock_checked_and_released=True,GPU_GRES_isolation_claimed=False,
 worker_must_revalidate_actual_UUID_foreign_processes_and_caps=True,freshness_seconds=time.monotonic()-start))
  env={**{key:value for key,value in os.environ.items() if not key.startswith('SBATCH_')},'MODEL_V3_GPU_UUID':GPU,'MODEL_V3_EXPECTED_NODE':NODE,'MODEL_V3_OUT':str(OUT),'MODEL_V3_RECORD':str(RECORD),
 'MODEL_V3_GPU_PYTHON':case_spec['logical_python'],'MODEL_V3_PLAN_SHA256':planref['sha256']}
  for name,r in [('MODEL_V3_ROOT_ADMISSION',frame),('MODEL_V3_QUOTA',quota),('MODEL_V3_HOLD',hold),('MODEL_V3_METHOD_PUBLICATION',operation_ref)]:
   env[name+'_PATH']=r['path'];env[name+'_SHA256']=r['sha256']
  argv=['sbatch','--parsable','--partition=all','--nodelist='+NODE,'--cpus-per-task=16','--mem=65536M','--time=02:00:00',
 '--export=ALL','--output='+str(CONTROL/'slurm_%j.log'),str(SB),cli.old_job_id]
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


if __name__=='__main__':main()
