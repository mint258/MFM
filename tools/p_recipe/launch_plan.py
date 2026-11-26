"""Submit prepared GPU work by sample budget, retaining the hybrid handoff."""
import argparse,concurrent.futures,csv,fcntl,json,shlex,subprocess,time
from pathlib import Path
from collect_execution import TERMINAL
from execution_ledger import locked_ledger,write
from scheduling import node_capacity,requested_cpus,route,gpu_rank
R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2];C=R/'runs/p_recipe_20261113'
OLD='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
NEW=str(R/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python')
# New submissions prefer0-7 for<=3M and20/22 for>3M. Node21 stays disabled.
NATIVE=('compute-0-22','compute-0-20')
FALLBACK=tuple('compute-0-'+str(i) for i in range(8))


def read(path):return json.loads(Path(path).read_text())


def take_card(cards,fallback,required_gpu_uuid=None,*,configuration=None,policy=None):
 pools=(cards,fallback)
 if configuration is not None:
  budget=configuration.get('samples',configuration.get('screening_samples',3000000))
  if budget<=policy.get('small_task_maximum_samples',3000000):pools=(fallback,cards)
  cpus=requested_cpus(configuration,policy)
 for pool in pools:
  for index,card in enumerate(pool):
   if required_gpu_uuid is not None and card['gpu_uuid']!=required_gpu_uuid:continue
   if configuration is not None:
    if card['node'] not in NATIVE and (card['free_cpus']<cpus or card.get('existing_compute_context',False)):continue
    if route(card['free_cpus'],cpus,card['used_mib'],card['total_mib'],policy)=='WAIT_GPU':continue
   return pool.pop(index)
 return None


def perf_priority_blocks(card,directive):
 priority=directive.get('resource_priority',{})
 return bool(priority.get('gpu_priority_active') and any(
     kind in card['gpu_name'] for kind in priority.get('preferred_gpu_types',())))

def own_gpu_busy(gpu,node=None):
 path=R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')
 if node is not None:
  code='import fcntl;f=open('+repr(str(path))+',"a")\ntry:fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB);print("FREE")\nexcept BlockingIOError:print("BUSY")'
  result=subprocess.run(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10',node,
      shlex.join(['/usr/bin/python3','-B','-c',code])],text=True,capture_output=True,timeout=15)
  return result.returncode!=0 or result.stdout.strip()!='FREE'
 with path.open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return True
 return False

def observe(node):
 text=subprocess.check_output(['scontrol','show','node',node,'-o'],text=True,timeout=15)
 free=node_capacity(text)
 partitions=next((part.split('=',1)[1] for part in text.split() if part.startswith('Partitions=')),'').split(',')
 if 'gpu' not in partitions:raise ValueError(node+' is not in the actual gpu partition')
 command=['nvidia-smi','--query-gpu=uuid,memory.used,memory.total,name','--format=csv,noheader,nounits']
 result=subprocess.run(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10',node,shlex.join(command)],text=True,capture_output=True,timeout=30)
 if result.returncode:raise OSError(node+': '+result.stderr.strip())
 busy=set()
 if node not in NATIVE:
  contexts=subprocess.check_output(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10',node,
      'nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader,nounits'],text=True,timeout=30)
  busy={row.strip() for row in contexts.splitlines() if row.strip()}
 return [dict(node=node,gpu_uuid=row[0].strip(),used_mib=float(row[1]),total_mib=float(row[2]),gpu_name=row[3].strip(),free_cpus=free,existing_compute_context=row[0].strip() in busy) for row in csv.reader(result.stdout.splitlines())]


def launch_locked(plan,ledger):
 path=C/'study_execution.json';policy=read(REPO/'configs/p_recipe/scheduling.json')
 directive_path=REPO/'configs/p_recipe/user_directive_20261117.json'
 directive=read(directive_path) if directive_path.is_file() else {}
 if policy['exclusive']:raise ValueError('User forbids exclusive allocation')
 nodes=policy.get('nodes',list(NATIVE+FALLBACK))
 if 'compute-0-21' in nodes:raise ValueError('compute-0-21 remains user-disabled')
 observed={};errors={}
 with concurrent.futures.ThreadPoolExecutor(3) as pool:
  futures={pool.submit(observe,node):node for node in nodes}
  for future in concurrent.futures.as_completed(futures):
   node=futures[future]
   try:observed[node]=future.result()
   except (OSError,ValueError,subprocess.SubprocessError) as error:errors[node]=str(error)
 cards=[card for node in NATIVE for card in observed.get(node,[]) if route(card['free_cpus'],1,card['used_mib'],card['total_mib'],policy)!='WAIT_GPU']
 cards.sort(key=lambda card:gpu_rank(card['gpu_name'],policy))
 fallback=[card for node in FALLBACK for card in observed.get(node,[])
     if not card.get('existing_compute_context',False)
     and route(card['free_cpus'],1,card['used_mib'],card['total_mib'],policy)!='WAIT_GPU']
 # Every run keeps its original handle. Repairs use an explicit new run/attempt.
 used={record['gpu_uuid'] for record in ledger['runs'].values() if record.get('state') not in TERMINAL}
 used.update(record['gpu_uuid'] for record in ledger.get('reservations',{}).values() if record.get('state') in ('RUNNING','CONFIGURING') and record.get('phase') not in ('HANDED_OFF','SOURCE_ALREADY_COMPLETE','HANDOFF_ABORTED'))
 cards=[card for card in cards if not perf_priority_blocks(card,directive) and card['gpu_uuid'] not in used and not own_gpu_busy(card['gpu_uuid'],card['node'])];fallback=[card for card in fallback if not perf_priority_blocks(card,directive) and card['gpu_uuid'] not in used and not own_gpu_busy(card['gpu_uuid'],card['node'])]
 ledger.update(last_admission_at=time.time(),last_admission_errors=errors)
 for filename in plan['configurations']:
  configuration=read(filename);name=configuration['run']
  if name in ledger['runs']:continue
  card=take_card(cards,fallback,configuration.get('required_gpu_uuid'),configuration=configuration,policy=policy)
  if card is None:
   print(json.dumps(dict(run=name,state='WAITING_FOR_OWN_GPU_SLOT',required_gpu_uuid=configuration.get('required_gpu_uuid'))),flush=True);continue
  node=card['node'];gpu=card['gpu_uuid'];submitted=time.time()
  cpus=requested_cpus(configuration,policy)
  mode=route(card['free_cpus'],cpus,card['used_mib'],card['total_mib'],policy) if node in NATIVE else 'Slurm'
  py=NEW if '5090' in card.get('gpu_name','') else OLD
  task_path=C/(name+'_scheduling.json');reservation_key=name+'_standby'
  task=dict(mode=mode,node=node,gpu_uuid=gpu,python=py,configuration=filename,submitted_at=submitted,cpus=cpus,exclusive=False,minimum_free_gpu_mib=policy['minimum_free_gpu_mib'],reservation_key=reservation_key,native_state=str(C/(name+'_native.json')),handoff_state=str(C/(name+'_handoff_state.json')))
  reserved=dict(backend='native_SSH' if mode=='native_with_standby' else 'Slurm',node=node,gpu_uuid=gpu,state='SUBMITTING',submitted_at=submitted,configuration=filename,stage=configuration['stage'],round=configuration['round'],study_revision=configuration.get('study_revision','original_20261113'),scheduling_task=str(task_path),cpus=cpus,exclusive=False)
  if mode=='native_with_standby':
   reserved['native_state']=task['native_state']
  # Slurm trainers also need the existing normal full-checkpoint save/exit hook.
  configuration.update(handoff_request=str(C/(name+'_handoff_request.json')),handoff_ack=str(C/(name+'_handoff_ack.json')))
  for key in ('handoff_request','handoff_ack'):
   if Path(configuration[key]).exists():raise RuntimeError('Existing handoff control file; inspect before starting')
  write(filename,configuration)
  write(task_path,task);ledger['runs'][name]=reserved;write(path,ledger)
  if mode=='native_with_standby':
   native=dict(run=name,node=node,gpu_uuid=gpu,output=configuration['output'],root_future_bytes=16777216,nfs_future_bytes=configuration.get('nfs_future_bytes',67108864),minimum_free_gpu_mib=policy['minimum_free_gpu_mib'],
       command=[py,'-B','-u','tools/p_recipe/train.py','--configuration',filename])
   native_path=C/(name+'_launch.json');write(native_path,native)
   command=[py,'-B','-u',str(REPO/'tools/p_recipe/native_run.py'),'--configuration',str(native_path)]
   code='import subprocess;f=open('+repr(str(C/(name+'.log')))+',"ab",buffering=0);p=subprocess.Popen('+repr(command)+',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print(p.pid)'
   try:pid=int(subprocess.check_output(['ssh','-n','-o','ConnectTimeout=10',node,shlex.join([py,'-c',code])],text=True,timeout=30).strip())
   except (OSError,ValueError,subprocess.SubprocessError) as error:
    reserved.update(state='SUBMISSION_OBSERVATION_UNCERTAIN',observation_error=str(error));write(path,ledger);continue
   reserved.update(wrapper_pid=pid,state='LAUNCHED')
  command=['sbatch','--parsable','--job-name='+name+('_takeover' if mode=='native_with_standby' else ''),'--partition='+policy['partition'],'--nodelist='+node,'--cpus-per-task='+str(cpus),str(REPO/'tools/p_recipe/hybrid.sbatch'),str(task_path)]
  try:job_id=int(subprocess.check_output(command,cwd=REPO,text=True,timeout=30).strip().split(';')[0])
  except (OSError,ValueError,subprocess.SubprocessError) as error:
   reserved.update(standby_submission_error=str(error)) if mode=='native_with_standby' else reserved.update(state='SUBMISSION_OBSERVATION_UNCERTAIN',observation_error=str(error))
   write(path,ledger);continue
  if mode=='native_with_standby':
   ledger.setdefault('reservations',{})[reservation_key]=dict(backend='Slurm',job_id=job_id,node=node,gpu_uuid=gpu,state='SUBMITTED',phase='WAITING_FOR_ALLOCATION',native_run=name,purpose='Same-task SSH to Slurm checkpoint takeover',exclusive_node=False,decision_pending=False)
   reserved['standby_job_id']=job_id
  else:
   reserved.update(job_id=job_id,state='SUBMITTED')
   for other in (*cards,*fallback):
    if other['node']==node:other['free_cpus']=max(0,other['free_cpus']-cpus)
  write(path,ledger);print(json.dumps(dict(run=name,**reserved)),flush=True)
 write(path,ledger);return ledger

def launch(plan):
 with locked_ledger() as ledger:return launch_locked(plan,ledger)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();launch(read(a.plan))
