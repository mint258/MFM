"""Continue only the existing preregistered Native B four-member plan.
Same original science and frozen/public v8; resource-only read-only wait before each fresh submission; no failed/ambiguous retries.
"""
import fcntl,hashlib,json,os,pathlib,subprocess,sys,time,traceback
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
P=N/'native_S_B20k_v3';K=N/'native_S_long_operational_v8';CONTROL=N/'native_B_remaining_GPU_auto_resource_wait_20261029_v5'
PIN='785f5fe3d475316c98818ee01c50b69352d9956374e17df069a6f72868973019'
RECONCILIATION={"path":"/share/home/zixiao/descriptor_analysis/runs/model_v3_20261026/Native_B_slot031_actual_failed_pre_model_reconciliation_v1.json","bytes":6449,"sha256":"568c713e4641c8e9419315aa63942dbd65f668f88298ee6f51c8bad5192e28be"}
def write_status(value):
 temporary=CONTROL/'status.pending'
 with temporary.open('w') as stream:json.dump(value,stream,indent=2);stream.write('\n')
 os.replace(temporary,CONTROL/'status.json')
def foreign_job_terminal():
 # Only this Root-proven Slurm job blocked the original UUID. A gap between
 # its gmx processes is not terminal and cannot pass this predicate.
 import re
 queue_argv=['squeue','-h','-u','guangyuan','-o','%i|%u|%T|%N']
 def query(argv):
  result=subprocess.run(argv,capture_output=True,text=True,timeout=30)
  assert result.returncode==0 and len(result.stdout)+len(result.stderr)<=65536,'Foreign-job observation failed/unknown; stop'
  return dict(argv=result.args,returncode=result.returncode,stdout=result.stdout,stderr=result.stderr)
 def queued(row):
  all_rows=[[x.strip() for x in line.split('|')] for line in row['stdout'].splitlines() if line.strip()]
  assert all(len(fields)==4 and fields[1]=='guangyuan' for fields in all_rows),'Unknown user-queue transport'
  rows=[fields for fields in all_rows if fields[0]=='4525142']
  assert len(rows)<=1,'Ambiguous foreign-job queue'
  if rows:
   fields=rows[0]
   assert len(fields)==4 and fields[0]=='4525142' and fields[1]=='guangyuan' and fields[3]=='compute-0-21','Foreign-job queue identity/node changed'
   assert fields[2] in ('RUNNING','COMPLETING','CONFIGURING','PENDING','SUSPENDED','RESIZING','STAGE_OUT'),'Unknown foreign-job live state'
  return bool(rows)
 queue=query(queue_argv);observation=dict(job_id='4525142',user='guangyuan',node='compute-0-21',queue=queue,observed_unix=time.time())
 if queued(queue):return False,observation
 accounting=query(['sacct','-X','-n','-P','-j','4525142','--format=JobIDRaw,User,State,ExitCode,NodeList'])
 rows=[[x.strip() for x in line.split('|')] for line in accounting['stdout'].splitlines() if line.strip()]
 assert len(rows)==1 and len(rows[0])==5,'Missing/ambiguous foreign-job parent accounting'
 job,user,state,exitcode,node=rows[0]
 assert job=='4525142' and user=='guangyuan' and node=='compute-0-21' and re.fullmatch(r'\d+:\d+',exitcode),'Foreign-job accounting identity/node changed'
 observation['accounting']=accounting
 base=state.split(' ',1)[0]
 terminal=('COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','BOOT_FAIL','DEADLINE')
 live=('RUNNING','COMPLETING','CONFIGURING','PENDING','SUSPENDED','RESIZING','STAGE_OUT','REQUEUED','REQUEUE_HOLD','REQUEUE_FED')
 assert base in terminal+live,'Unknown foreign-job accounting state'
 assert state==base or base=='CANCELLED' and re.fullmatch(r'CANCELLED by \d+',state),'Ambiguous foreign-job state suffix'
 if base in live:return False,observation
 confirm=query(queue_argv);observation['queue_after_terminal']=confirm
 return not queued(confirm),observation

def wait_for_observed_CPU_and_MemAvailable(deadline,step,completed,identity):
 # A read-only delay, NEVER a substitute for the original frozen submit-next
 # registration/software/CPU/MemAvailable/GPU/UUID/lock/quota admission.
 import re
 while time.monotonic()<deadline:
  node=subprocess.run(['scontrol','show','node','compute-0-21','-o'],capture_output=True,text=True,timeout=30)
  cpu=dict(re.findall(r'\b(CPUAlloc|CPUTot|RealMemory)=(\d+)',node.stdout))
  eligible=node.returncode==0 and len(cpu)==3 and int(cpu['CPUTot'])-int(cpu['CPUAlloc'])>=16 and not any(x in node.stdout for x in ('DOWN','DRAIN','UNKNOWN','NOT_RESPONDING'))
  mem=gpu=apps=None;selected=None;foreign=None
  if eligible:
   mem=subprocess.run(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(B/'runs/model_v3_20261025/compute21_known_hosts_v1'),'compute-0-21',"awk '/^MemAvailable:/ {print}' /proc/meminfo"],capture_output=True,text=True,timeout=30)
   match=re.fullmatch(r'MemAvailable:\s+(\d+) kB\s*',mem.stdout)
   eligible=mem.returncode==0 and match is not None and (int(match[1])<<10)>=(32<<30)+(int(cpu['RealMemory'])<<20)*15//100
  if eligible:eligible,foreign=foreign_job_terminal()
  if eligible:
   # Reuse the exact frozen v8 identity predicate. A known target process only
   # delays this prewait; unknown/failed GPU observations stop for Root.
   ssh=mem.args[:-1]
   gpu=subprocess.run(ssh+['nvidia-smi --query-gpu=uuid,name,driver_version,memory.total,memory.free --format=csv,noheader,nounits'],capture_output=True,text=True,timeout=30)
   apps=subprocess.run(ssh+['nvidia-smi --query-compute-apps=gpu_uuid,pid,process_name,used_gpu_memory --format=csv,noheader,nounits'],capture_output=True,text=True,timeout=30)
   assert gpu.returncode==apps.returncode==0,'Read-only GPU observation failed/unknown; stop, never retry a submission'
   selected=gpu_rules.selected_gpu(gpu.stdout,'')
   occupied=any(normalized_uuid(line.split(',')[0])==common.GPU for line in apps.stdout.splitlines() if line.strip())
   if not occupied:gpu_rules.selected_gpu(gpu.stdout,apps.stdout)
   eligible=not occupied
  observation=dict(node=dict(argv=node.args,returncode=node.returncode,stdout=node.stdout,stderr=node.stderr),memory=None if mem is None else dict(argv=mem.args,returncode=mem.returncode,stdout=mem.stdout,stderr=mem.stderr),gpu=None if gpu is None else dict(argv=gpu.args,returncode=gpu.returncode,stdout=gpu.stdout,stderr=gpu.stderr),compute_apps=None if apps is None else dict(argv=apps.args,returncode=apps.returncode,stdout=apps.stdout,stderr=apps.stderr),selected_gpu_row=selected,foreign_job_observation=foreign,observed_unix=time.time())
  if eligible:
   write_status(dict(status='READ_ONLY_PREWAIT_READY_ORIGINAL_SUBMIT_WILL_REVALIDATE',next=step,completed_additional_segments=completed,identity=identity,resource_observation=observation,automatic_failure_retry=False))
   return
  write_status(dict(status='WAITING_WITHOUT_SUBMISSION_FOR_CPU_MEMORY_JOB5142_TERMINAL_AND_IDLE_GPU',next=step,completed_additional_segments=completed,identity=identity,resource_observation=observation,automatic_failure_retry=False))
  time.sleep(min(60,max(0,deadline-time.monotonic())))
 raise RuntimeError('Original seven-day horizon reached while waiting; no submission')

assert os.getuid()==1278 and os.uname().nodename.split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID')
sys.path.insert(0,str(K));import long_common as common;import long_operations as ops
common.root_identity();common.verify(PIN)
import native_resources as gpu_rules
from common import normalized_uuid
reconciliation=common.read_ref(RECONCILIATION)
assert reconciliation['schema']=='NATIVE_B_ROOT_ACTUAL_FAILED_PRE_MODEL_RECONCILIATION_V1'
assert reconciliation['status']=='ACTUAL031_FAILED_BEFORE_SUPERVISOR_NO_MODEL_UPDATE_PRESERVED_READY_FOR_EXPLICIT_ROOT_ONLY_NEXT_SLOT_AFTER_BLOCKER_TERMINAL'
assert reconciliation['actual_failed_job']=='4525157' and reconciliation['old_v4_exited'] is True
assert reconciliation['worker_source_admission_precedes_snapshot_QA_supervisor_and_model'] is True and reconciliation['child_supervisor_member_result_checkpoint_and_private_scratch_absent'] is True
assert reconciliation['one_time_explicit_Root_retry_failed_only_after_blocking_foreign_job_terminal'] is True and reconciliation['any_new_failed_or_ambiguous_child_must_stop_no_automatic_retry'] is True
assert reconciliation['first_expected_step']==dict(slot=32,seed=0,precision='bf16',start_update=9000,target_update=10000)
blocker=reconciliation['blocking_foreign_job']
assert (blocker['job_id'],blocker['user'],blocker['uid'],blocker['node'],blocker['gpu_uuid'])==('4525142','guangyuan',1275,'compute-0-21',common.GPU)
assert common.binding(reconciliation['last_successful_Root_closure']['path'])==reconciliation['last_successful_Root_closure']
assert common.read_ref(reconciliation['original_failed_Root_closure'])['status']=='FAILED_OR_STORAGE_HOLD'
validated=json.loads((P/'control/VALIDATED.json').read_bytes())
env=common.environment(cpu=True,contract=validated['runtime_contract']['path'])
env={k:v for k,v in env.items() if not k.startswith('SBATCH_')}
command=[str(common.PYTHON),'-u','-B',str(K/'long_operations.py'),'submit-next','--phase',str(P),'--pins-sha256',PIN]
with (CONTROL/'controller.lock').open('a') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 raw=pathlib.Path('/proc/self/cmdline').read_bytes()
 tail=pathlib.Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
 identity=dict(pid=os.getpid(),uid=os.getuid(),boot_id=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),start_ticks=int(tail[19]),argv_sha256=hashlib.sha256(raw).hexdigest(),pgid=os.getpgid(0),sid=os.getsid(0),source_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),started_unix=time.time())
 with (CONTROL/'identity.json').open('x') as stream:json.dump(identity,stream,indent=2)
 original_identity=json.loads((N/'native_B_remaining_20261029/identity.json').read_bytes())
 remaining_horizon=original_identity['started_unix']+7*86400-time.time()
 assert remaining_horizon>0,'Original seven-day coordinator horizon expired'
 deadline=time.monotonic()+remaining_horizon
 completed=0
 try:
  for finite_index in range(81):
   assert time.monotonic()<deadline,'Finite seven-day coordinator horizon reached'
   step=ops.next_member(P,allow_failed=finite_index==0)
   if finite_index==0:
    assert {key:step.get(key) for key in ('slot','seed','precision','start_update','target_update')}==reconciliation['first_expected_step'],'Only explicit new slot32 retry is authorized'
    assert step['previous']==reconciliation['last_successful_Root_closure'] and step['resume_checkpoint']==reconciliation['resume_checkpoint_directory_stat_only'],'Must resume unchanged successful slot030 checkpoint'
   if 'status' in step:
    assert step['status']=='ALL_FOUR_20000_UPDATES_COMPLETE_PENDING_LOG_NUMERIC_GATES'
    write_status(dict(status='FOUR_TRAINING_MEMBERS_COMPLETE_PENDING_SDK_AND_B_CURVE_GATES',completed_additional_segments=completed,next=step,identity=identity,scientific_acceptance=False))
    break
   write_status(dict(status='CALLING_ORIGINAL_FINITE_SUBMIT_NEXT',next=step,completed_additional_segments=completed,identity=identity,automatic_failure_retry=False))
   print(json.dumps(dict(status='ORIGINAL_NEXT',next={k:step[k] for k in ('slot','seed','precision','start_update','target_update')})),flush=True)
   wait_for_observed_CPU_and_MemAvailable(deadline,step,completed,identity)
   assert time.monotonic()<deadline,'Original seven-day horizon expired during resource observation; no new child'
   assert ops.next_member(P,allow_failed=finite_index==0)==step,'Native attempt changed during wait; stop before one child'
   assert time.monotonic()<deadline,'Original seven-day horizon expired before one child'
   call_command=command+(['--retry-failed'] if finite_index==0 else [])
   child=subprocess.Popen(call_command,cwd=str(B),env=env,stdin=subprocess.DEVNULL)
   while child.poll() is None:
    write_status(dict(status='ORIGINAL_FINITE_COORDINATOR_LIVE',next=step,child_pid=child.pid,completed_additional_segments=completed,identity=identity,observed_unix=time.time(),automatic_failure_retry=False))
    time.sleep(20)
   assert child.returncode==0,'Original finite coordinator failed/unknown; inspect its preserved intent and terminal, never auto-retry'
   closure=P/'slots'/('slot_%03d'%step['slot'])/'management/ROOT_LONG_SEGMENT_CLOSURE.json'
   closed=json.loads(closure.read_bytes())
   assert closed['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING' and closed['failure'] is None
   assert step['start_update']<closed['optimizer_updates']<=step['target_update']
   completed+=1
  else:raise RuntimeError('Finite existing attempt horizon exhausted')
 except BaseException as error:
  write_status(dict(status='STOPPED_REQUIRES_ROOT_RECONCILIATION_NO_RETRY',error=dict(type=type(error).__name__,message=str(error)),traceback=traceback.format_exc(),completed_additional_segments=completed,identity=identity,scientific_acceptance=False))
  raise
