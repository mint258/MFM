"""Hourly metadata-only resource probe and dispatch through frozen Root CLIs."""
from __future__ import annotations
import argparse,datetime,fcntl,hashlib,importlib.util,json,os
from pathlib import Path
import re,shlex,socket,subprocess,sys,time
B=Path('/share/home/zixiao/descriptor_analysis');N=B/'runs/model_v3_20261026'
CONTROL=N/'hourly_resource_dispatch_user_20261030_v1'
CPY='/share/home/zixiao/.conda/envs/chemprop/bin/python'
K=N/'native_S_long_operational_v8';PHASE=N/'native_S_B20k_v3'
PIN='785f5fe3d475316c98818ee01c50b69352d9956374e17df069a6f72868973019'
BLOCKERS={'GPU-22e21021-e572-4562-fc51-cd8c83e74141':'4525142',
 'GPU-c35f2434-9137-9723-1af5-dc69b6295243':'4525143',
 'GPU-9b6008d0-35dd-4bff-f69a-0927b04b7eef':'4515408'}
LEGACY={'C1a':N/'C1a_checkpoint_off_remaining_resource_wait_v2',
 'A438':N/'performance_old438_resource_prewait_v1',
 'NativeB':N/'native_B_remaining_GPU_auto_resource_wait_20261029_v5'}
NODES={'3090':['compute-0-'+str(i) for i in (0,1,3,4,5,6,7)],
 '5090':['compute-0-21','compute-0-22']}
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text())
def write(p,v):
 p=Path(p);t=p.with_name(p.name+'.pending')
 with t.open('w') as f:json.dump(v,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())
 os.replace(t,p)
def run(a):
 r=subprocess.run(a,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=35)
 if r.returncode or len(r.stdout)+len(r.stderr)>2**20:raise RuntimeError('Read-only observation failed: '+repr(a[:6])+': '+r.stderr[-500:])
 return r.stdout
def identity_live(saved,proc=Path('/proc')):
 i=saved.get('identity',saved);p=proc/str(i['pid'])
 if not p.exists():return False
 tail=(p/'stat').read_text().rsplit(')',1)[1].split()
 if p.stat().st_uid!=i['uid'] or i['uid']!=1278 or int(tail[19])!=i['start_ticks']:
  raise RuntimeError('Saved PID identity changed; do not infer a stopped coordinator')
 if (proc/'sys/kernel/random/boot_id').read_text().strip()!=i['boot_id']:
  raise RuntimeError('Boot identity changed; Root review required')
 return tail[0]!='Z'
def legacy_active(kind):
 p=LEGACY[kind]/'identity.json'
 return p.exists() and identity_live(read(p))
def owned_command_active(fragment):
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   if p.stat().st_uid==1278 and fragment in (p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'):return True
  except (FileNotFoundError,ProcessLookupError,PermissionError):pass
 return False
def eligible(row,software,live):
 return (row['free_cpus']>=16 and row['mem_available_bytes']>=software+row['real_memory_bytes']*15//100
  and not row['occupied'] and BLOCKERS.get(row['uuid']) not in live)
def probe():
 queue=run(['squeue','-h','-o','%i|%u|%T|%N']);live={x.split('|')[0] for x in queue.splitlines() if x.strip()}
 nodes=run(['scontrol','show','node','-o']);rows=[];errors=[]
 remote="""import json,re,subprocess
def call(a):
 r=subprocess.run(a,capture_output=True,text=True,timeout=20)
 if r.returncode:raise RuntimeError(r.stderr[-500:])
 return r.stdout
m=re.search(r'^MemAvailable:\\s+(\\d+) kB',open('/proc/meminfo').read(),re.M)
print(json.dumps(dict(memory=int(m[1])*1024,gpus=call(['nvidia-smi','--query-gpu=uuid,name','--format=csv,noheader']),apps=call(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits']))))"""
 for line in nodes.splitlines():
  f=dict(re.findall(r'\b(NodeName|CPUAlloc|CPUTot|RealMemory|State)=([^\s]+)',line))
  name=f.get('NodeName');family=next((k for k,v in NODES.items() if name in v),None)
  if family is None or any(x in f.get('State','') for x in ('DOWN','DRAIN','FAIL','UNKNOWN','MAINT','NOT_RESPONDING')):continue
  free=int(f['CPUTot'])-int(f['CPUAlloc'])
  if free<16:continue
  ssh=['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','StrictHostKeyChecking=yes']
  if name=='compute-0-21':ssh+=['-o','UserKnownHostsFile='+str(B/'runs/model_v3_20261025/compute21_known_hosts_v1')]
  try:
   value=json.loads(run(ssh+[name,shlex.quote(CPY)+' -B -c '+shlex.quote(remote)]))
   occupied={x.split(',')[0].strip() for x in value['apps'].splitlines() if x.strip() and x.strip()!='No running processes found'}
   for s in value['gpus'].splitlines():
    uuid,gpu_name=[x.strip() for x in s.split(',',1)]
    if family not in gpu_name or not re.fullmatch('GPU-[0-9a-f-]+',uuid):continue
    rows.append(dict(node=name,family=family,uuid=uuid,free_cpus=free,real_memory_bytes=int(f['RealMemory'])<<20,
     mem_available_bytes=value['memory'],occupied=uuid in occupied,looping_job_live=BLOCKERS.get(uuid) in live))
  except Exception as e:errors.append(dict(node=name,error=str(e)))
 return dict(captured_utc=now(),node_allocation=nodes,gpus=rows,read_only_errors=errors),live
def invoke(key,argv,state,env,dry):
 if key in state['calls']:return 'ALREADY_CALLED_NO_REPLAY'
 if dry:return dict(status='WOULD_CALL_FROZEN_ROOT',key=key,argv=argv)
 state['calls'][key]=dict(status='INTENT_NO_AUTOMATIC_REPLAY',argv=argv,started_utc=now())
 write(CONTROL/'state.json',state)
 logfile=CONTROL/('root_calls_'+datetime.datetime.now().strftime('%Y%m%d')+'.log')
 with logfile.open('ab',buffering=0) as stream:
  r=subprocess.run(argv,cwd=B,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
 state['calls'][key].update(status='ROOT_RETURNED_ZERO' if r.returncode==0 else 'FAILED_REQUIRES_ROOT_NO_RETRY',returncode=r.returncode,ended_utc=now())
 write(CONTROL/'state.json',state)
 return state['calls'][key]['status']
def last_attempt_requires_retry(attempts):
 if not attempts or attempts[-1][1]['status']=='OUTER_C0_SEGMENT_CLOSED_SDK_PENDING':return False
 if attempts[-1][0]['slot']!=31:raise RuntimeError('New failure requires Root; no automatic retry')
 return True
def tasks(snapshot,live,state,dry,kind):
 env={k:v for k,v in os.environ.items() if not k.startswith('SBATCH_')}
 output={};rows=snapshot['gpus']
 if kind=='C1a':
  if legacy_active('C1a'):output['C1a']='LEGACY_CONTROLLER_LIVE_NO_DUPLICATE'
  else:
   old=read(LEGACY['C1a']/'status.json');oldcalls=old.get('calls',{})
   for family in ('3090','5090'):
    key='C1a_'+family
    if family in oldcalls or (N/('C1a_checkpoint_off_'+family+'_resource_wait_v2')).exists() or (N/('C1a_checkpoint_off_'+family+'_hourly_user_v1')).exists():
     output[key]='EXISTING_CALL_OR_OUTPUT_NO_REPLAY';continue
    if owned_command_active('submit_one_C1a_checkpoint_off_Root_v2.py'):
     output[key]='ORIGINAL_ROOT_LIVE_NO_DUPLICATE';continue
    if old['status'] not in ('WAITING_RESOURCE_WITHOUT_GPU_ALLOCATION','UNRESOLVED_RESOURCE_WAIT_EXPIRED_OLD_CHECKPOINT_PATH_CONTINUES','UNRESOLVED_STOP_NO_AUTOMATIC_RETRY_MAINLINE_CONTINUES'):
     output[key]='LEGACY_REQUIRES_ROOT_NO_RETRY';continue
    available=next((r for r in rows if r['family']==family and eligible(r,64<<30,live)),None)
    if available is None:output[key]='WAITING_RESOURCES';continue
    output[key]=invoke(key,[CPY,'-B',str(N/'submit_one_C1a_checkpoint_off_Root_v2.py'),'--gpu',family,'--node',available['node'],'--uuid',available['uuid'],'--label','hourly_user_v1'],state,env,dry)
  return output
 if kind=='A438':
  if legacy_active('A438'):output['A438']='LEGACY_CONTROLLER_LIVE_NO_DUPLICATE'
  elif owned_command_active('performance_remaining_Av2_20261029_routing_v7/Root_submit.py'):output['A438']='ORIGINAL_ROOT_LIVE_NO_DUPLICATE'
  else:
   spec=importlib.util.spec_from_file_location('hourly_old438_original',N/'performance_old438_resource_prewait_v1_source/wait_then_submit_old438.py')
   oldmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(oldmod);case=oldmod.original_inputs()
   if Path(case['family']).exists():output['A438']='EXISTING_FAMILY_OR_INTENT_NO_REPLAY'
   elif not any(r['node']==oldmod.NODE and r['uuid']==oldmod.GPU and eligible(r,64<<30,live) for r in rows):output['A438']='WAITING_RESOURCES'
   else:
    trust=oldmod.rawref(oldmod.KNOWN_HOSTS)[0]
    output['A438']=invoke('A438',[case['logical_python'],'-u','-B',oldmod.DRIVER['path'],'4520438',
     '--method-publication',oldmod.PUBLICATION['path'],'--method-publication-sha256',oldmod.PUBLICATION['sha256'],
     '--source-pins-sha256',oldmod.PINS['sha256'],'--known-hosts-sha256',trust['sha256']],state,env,dry)
  return output
 if kind=='NativeB':
  if legacy_active('NativeB'):output['NativeB']='LEGACY_CONTROLLER_LIVE_NO_DUPLICATE'
  elif owned_command_active('native_S_long_operational_v8/long_operations.py'):output['NativeB']='ORIGINAL_ROOT_LIVE_NO_DUPLICATE'
  elif not any(r['uuid']=='GPU-22e21021-e572-4562-fc51-cd8c83e74141' and eligible(r,32<<30,live) for r in rows):output['NativeB']='WAITING_RESOURCES'
  else:
   sys.path.insert(0,str(K));import long_common as common;import long_operations as ops
   attempts=ops.closed_attempts(PHASE)
   retry=last_attempt_requires_retry(attempts)
   if retry:
    rec=read(N/'Native_B_slot031_actual_failed_pre_model_reconciliation_v1.json')
    step=ops.next_member(PHASE,allow_failed=True)
    if ({k:step.get(k) for k in ('slot','seed','precision','start_update','target_update')}!=rec['first_expected_step']
     or step['previous']!=rec['last_successful_Root_closure'] or step['resume_checkpoint']!=rec['resume_checkpoint_directory_stat_only']
     or rec['one_time_explicit_Root_retry_failed_only_after_blocking_foreign_job_terminal'] is not True):
     raise RuntimeError('Original once-only slot031 reconciliation differs')
    retry=True
   else:step=ops.next_member(PHASE)
   if 'status' in step:output['NativeB']=step;return output
   key='Native_slot_%03d'%step['slot']
   if any(v['status']!='ROOT_RETURNED_ZERO' for k,v in state['calls'].items() if k.startswith('Native_')):
    output['NativeB']='PRIOR_HOURLY_CALL_UNRESOLVED_NO_RETRY';return output
   validated=read(PHASE/'control/VALIDATED.json');native_env=common.environment(cpu=True,contract=validated['runtime_contract']['path'])
   native_env={k:v for k,v in native_env.items() if not k.startswith('SBATCH_')}
   cmd=[str(common.PYTHON),'-u','-B',str(K/'long_operations.py'),'submit-next','--phase',str(PHASE),'--pins-sha256',PIN]
   if retry:cmd+=['--retry-failed']
   output['NativeB']=invoke(key,cmd,state,native_env,dry)
  return output
  return output

def main(argv=None):
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check-only',action='store_true');args=parser.parse_args(argv)
 if os.getuid()!=1278 or socket.gethostname().split('.')[0]!='sonmi' or os.environ.get('SLURM_JOB_ID'):raise RuntimeError('Root login metadata-only coordinator required')
 os.umask(0o077);CONTROL.mkdir(mode=0o700,exist_ok=True)
 os.environ['PATH']=str(B/'runs/model_v3_20261025/cpu_git_tools_v1/bin')+':/usr/local/bin:/usr/bin:/bin'
 with (CONTROL/'hourly.lock').open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return 0
  state=read(CONTROL/'state.json') if (CONTROL/'state.json').exists() else dict(schema='model_v3_hourly_dispatch_state_v1',calls={})
  own=dict(pid=os.getpid(),uid=os.getuid(),start_ticks=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]),boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())
  write(CONTROL/'last_process.json',own)
  try:
   snapshot,live=probe();result={}
   # Each lineage is independent; a metadata problem does not suppress another.
   for name in ('C1a','A438','NativeB'):
    try:result.update(tasks(snapshot,live,state,args.check_only,name))
    except Exception as e:result[name]=dict(status='UNRESOLVED_REQUIRES_ROOT_NO_REPLAY',error=str(e))
   value=dict(captured_utc=now(),check_only=args.check_only,resource_probe=snapshot,tasks=result,scientific_acceptance=False,starts_formal_pretraining=False)
   write(CONTROL/('last_check_only.json' if args.check_only else 'last_tick.json'),value)
   print(json.dumps(dict(captured_utc=value['captured_utc'],check_only=args.check_only,tasks=result)))
   return 0
  except Exception as e:
   write(CONTROL/'last_error.json',dict(captured_utc=now(),type=type(e).__name__,error=str(e),calls_preserved=True,no_automatic_replay=True))
   raise
if __name__=='__main__':sys.exit(main())
