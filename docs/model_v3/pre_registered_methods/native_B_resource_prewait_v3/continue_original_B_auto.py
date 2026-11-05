"""Continue only the existing preregistered Native B four-member plan.
Same original science and frozen/public v8; resource-only read-only wait before each fresh submission; no failed/ambiguous retries.
"""
import fcntl,hashlib,json,os,pathlib,subprocess,sys,time,traceback
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
P=N/'native_S_B20k_v3';K=N/'native_S_long_operational_v8';CONTROL=N/'native_B_remaining_GPU_auto_resource_wait_20261029_v3'
PIN='785f5fe3d475316c98818ee01c50b69352d9956374e17df069a6f72868973019'
def write_status(value):
 temporary=CONTROL/'status.pending'
 with temporary.open('w') as stream:json.dump(value,stream,indent=2);stream.write('\n')
 os.replace(temporary,CONTROL/'status.json')
def wait_for_observed_CPU_and_MemAvailable(deadline,step,completed,identity):
 # A read-only delay, NEVER a substitute for the original frozen submit-next
 # registration/software/CPU/MemAvailable/GPU/UUID/lock/quota admission.
 import re
 while time.monotonic()<deadline:
  node=subprocess.run(['scontrol','show','node','compute-0-21','-o'],capture_output=True,text=True,timeout=30)
  cpu=dict(re.findall(r'\b(CPUAlloc|CPUTot|RealMemory)=(\d+)',node.stdout))
  eligible=node.returncode==0 and len(cpu)==3 and int(cpu['CPUTot'])-int(cpu['CPUAlloc'])>=16 and not any(x in node.stdout for x in ('DOWN','DRAIN','UNKNOWN','NOT_RESPONDING'))
  mem=None
  if eligible:
   mem=subprocess.run(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(B/'runs/model_v3_20261025/compute21_known_hosts_v1'),'compute-0-21',"awk '/^MemAvailable:/ {print}' /proc/meminfo"],capture_output=True,text=True,timeout=30)
   match=re.fullmatch(r'MemAvailable:\s+(\d+) kB\s*',mem.stdout)
   eligible=mem.returncode==0 and match is not None and (int(match[1])<<10)>=(32<<30)+(int(cpu['RealMemory'])<<20)*15//100
  observation=dict(node=dict(argv=node.args,returncode=node.returncode,stdout=node.stdout,stderr=node.stderr),memory=None if mem is None else dict(argv=mem.args,returncode=mem.returncode,stdout=mem.stdout,stderr=mem.stderr),observed_unix=time.time())
  if eligible:
   write_status(dict(status='READ_ONLY_PREWAIT_READY_ORIGINAL_SUBMIT_WILL_REVALIDATE',next=step,completed_additional_segments=completed,identity=identity,resource_observation=observation,automatic_failure_retry=False))
   return
  write_status(dict(status='WAITING_WITHOUT_SUBMISSION_FOR_16_CPU_AND_ORIGINAL_MEMORY_RESERVE',next=step,completed_additional_segments=completed,identity=identity,resource_observation=observation,automatic_failure_retry=False))
  time.sleep(min(60,max(0,deadline-time.monotonic())))
 raise RuntimeError('Original seven-day horizon reached while waiting; no submission')

assert os.getuid()==1278 and os.uname().nodename.split('.')[0]=='sonmi' and not os.environ.get('SLURM_JOB_ID')
sys.path.insert(0,str(K));import long_common as common;import long_operations as ops
common.root_identity();common.verify(PIN)
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
   step=ops.next_member(P)
   if 'status' in step:
    assert step['status']=='ALL_FOUR_20000_UPDATES_COMPLETE_PENDING_LOG_NUMERIC_GATES'
    write_status(dict(status='FOUR_TRAINING_MEMBERS_COMPLETE_PENDING_SDK_AND_B_CURVE_GATES',completed_additional_segments=completed,next=step,identity=identity,scientific_acceptance=False))
    break
   write_status(dict(status='CALLING_ORIGINAL_FINITE_SUBMIT_NEXT',next=step,completed_additional_segments=completed,identity=identity,automatic_failure_retry=False))
   print(json.dumps(dict(status='ORIGINAL_NEXT',next={k:step[k] for k in ('slot','seed','precision','start_update','target_update')})),flush=True)
   wait_for_observed_CPU_and_MemAvailable(deadline,step,completed,identity)
   assert time.monotonic()<deadline,'Original seven-day horizon expired during resource observation; no new child'
   child=subprocess.Popen(command,cwd=str(B),env=env,stdin=subprocess.DEVNULL)
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
