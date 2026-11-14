"""Submit one prepared study plan using native high GPUs and established Slurm."""
import argparse,concurrent.futures,csv,fcntl,json,shlex,subprocess,time
from pathlib import Path
from collect_execution import TERMINAL
from execution_ledger import locked_ledger,write
from scheduling import node_capacity,requested_cpus,route,gpu_rank
R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2];C=R/'runs/p_recipe_20261113'
OLD='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
NEW=str(R/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python')
# Idle compatible resources: RTX5090 (22/21), then RTX4090 (20), then3090.
NATIVE=('compute-0-22','compute-0-21','compute-0-20')


def read(path):return json.loads(Path(path).read_text())


def take_card(cards,fallback,required_gpu_uuid=None):
 for pool in (cards,fallback):
  for index,card in enumerate(pool):
   if required_gpu_uuid is None or card['gpu_uuid']==required_gpu_uuid:
    return pool.pop(index)
 return None

def own_gpu_busy(gpu):
 path=R/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')
 with path.open('a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  except BlockingIOError:return True
 return False

def observe(node):
 command=['nvidia-smi','--query-gpu=uuid,memory.used,memory.total,name','--format=csv,noheader,nounits']
 result=subprocess.run(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10',node,shlex.join(command)],text=True,capture_output=True,timeout=30)
 if result.returncode:raise OSError(node+': '+result.stderr.strip())
 text=subprocess.check_output(['scontrol','show','node',node,'-o'],text=True,timeout=15)
 free=node_capacity(text)
 return [dict(node=node,gpu_uuid=row[0].strip(),used_mib=float(row[1]),total_mib=float(row[2]),gpu_name=row[3].strip(),free_cpus=free) for row in csv.reader(result.stdout.splitlines())]


def launch_locked(plan,ledger):
 path=C/'study_execution.json';policy=read(REPO/'configs/p_recipe/scheduling.json')
 if policy['exclusive']:raise ValueError('User forbids exclusive allocation')
 inventory=read(C/'batch_gpu_inventory.json');known={gpu[0] for item in inventory for gpu in item.get('gpus',[])}
 observed={};errors={}
 with concurrent.futures.ThreadPoolExecutor(3) as pool:
  futures={pool.submit(observe,node):node for node in NATIVE}
  for future in concurrent.futures.as_completed(futures):
   node=futures[future]
   try:observed[node]=future.result()
   except (OSError,ValueError,subprocess.SubprocessError) as error:errors[node]=str(error)
 cards=[card for node in NATIVE for card in observed.get(node,[]) if card['gpu_uuid'] in known and route(card['free_cpus'],1,card['used_mib'],card['total_mib'],policy)!='WAIT_GPU']
 cards.sort(key=lambda card:gpu_rank(card['gpu_name'],policy))
 fallback={item['node']:item['gpus'][0][0] for item in inventory if item['node'] not in NATIVE and item.get('gpus')}
 fallback=[dict(node=node,gpu_uuid=fallback[node]) for node in ('compute-0-5','compute-0-0','compute-0-6','compute-0-7','compute-0-1','compute-0-3','compute-0-4') if node in fallback]
 # Every run keeps its original handle. Repairs use an explicit new run/attempt.
 used={record['gpu_uuid'] for record in ledger['runs'].values() if record.get('state') not in TERMINAL}
 used.update(record['gpu_uuid'] for record in ledger.get('reservations',{}).values() if record.get('state') in ('RUNNING','CONFIGURING') and record.get('phase') not in ('HANDED_OFF','SOURCE_ALREADY_COMPLETE','HANDOFF_ABORTED'))
 cards=[card for card in cards if card['gpu_uuid'] not in used and not own_gpu_busy(card['gpu_uuid'])];fallback=[card for card in fallback if card['gpu_uuid'] not in used and not own_gpu_busy(card['gpu_uuid'])]
 ledger.update(last_admission_at=time.time(),last_admission_errors=errors)
 for filename in plan['configurations']:
  configuration=read(filename);name=configuration['run']
  if name in ledger['runs']:continue
  card=take_card(cards,fallback,configuration.get('required_gpu_uuid'))
  if card is None:
   print(json.dumps(dict(run=name,state='WAITING_FOR_OWN_GPU_SLOT',required_gpu_uuid=configuration.get('required_gpu_uuid'))),flush=True);continue
  node=card['node'];gpu=card['gpu_uuid'];submitted=time.time()
  cpus=requested_cpus(configuration,policy)
  mode=route(card['free_cpus'],cpus,card['used_mib'],card['total_mib'],policy) if node in NATIVE else 'Slurm'
  py=NEW if '5090' in card.get('gpu_name','') else OLD
  task_path=C/(name+'_scheduling.json');reservation_key=name+'_standby'
  task=dict(mode=mode,node=node,gpu_uuid=gpu,python=py,configuration=filename,submitted_at=submitted,cpus=cpus,exclusive=False,minimum_free_gpu_mib=policy['minimum_free_gpu_mib'],reservation_key=reservation_key,native_state=str(C/(name+'_native.json')),handoff_state=str(C/(name+'_handoff_state.json')))
  reserved=dict(backend='native_SSH' if mode=='native_with_standby' else 'Slurm',node=node,gpu_uuid=gpu,state='SUBMITTING',submitted_at=submitted,configuration=filename,stage=configuration['stage'],round=configuration['round'],scheduling_task=str(task_path),cpus=cpus,exclusive=False)
  if mode=='native_with_standby':
   reserved['native_state']=task['native_state']
   configuration.update(handoff_request=str(C/(name+'_handoff_request.json')),handoff_ack=str(C/(name+'_handoff_ack.json')))
   for key in ('handoff_request','handoff_ack'):
    if Path(configuration[key]).exists():raise RuntimeError('Existing handoff control file; inspect before starting')
   write(filename,configuration)
  write(task_path,task);ledger['runs'][name]=reserved;write(path,ledger)
  if mode=='native_with_standby':
   native=dict(run=name,node=node,gpu_uuid=gpu,output=configuration['output'],root_future_bytes=16777216,minimum_free_gpu_mib=policy['minimum_free_gpu_mib'],
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
   for other in cards:
    if other['node']==node:other['free_cpus']=max(0,other['free_cpus']-cpus)
  write(path,ledger);print(json.dumps(dict(run=name,**reserved)),flush=True)
 write(path,ledger);return ledger

def launch(plan):
 with locked_ledger() as ledger:return launch_locked(plan,ledger)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();launch(read(a.plan))
