"""Continue only the existing preregistered Native B four-member plan.
Same original science; approved automatic GPU declaration via frozen/public v8; no failed/ambiguous retries.
"""
import fcntl,hashlib,json,os,pathlib,subprocess,sys,time,traceback
B=pathlib.Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
P=N/'native_S_B20k_v3';K=N/'native_S_long_operational_v8';CONTROL=N/'native_B_remaining_GPU_auto_20261029_v1'
PIN='785f5fe3d475316c98818ee01c50b69352d9956374e17df069a6f72868973019'
def write_status(value):
 temporary=CONTROL/'status.pending'
 with temporary.open('w') as stream:json.dump(value,stream,indent=2);stream.write('\n')
 os.replace(temporary,CONTROL/'status.json')
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
