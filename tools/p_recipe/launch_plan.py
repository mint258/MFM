"""Submit one prepared study plan using native high GPUs and established Slurm."""
import argparse,concurrent.futures,csv,json,shlex,subprocess,time
from pathlib import Path
from collect_execution import TERMINAL
R=Path('/share/home/zixiao/descriptor_analysis');REPO=Path(__file__).resolve().parents[2];C=R/'runs/p_recipe_20261113'
OLD='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
NEW=str(R/'docs/phase1/evidence/stage43_5090_environment/install_4511929/venv/bin/python')
NATIVE=('compute-0-22','compute-0-21','compute-0-20')


def read(path):return json.loads(Path(path).read_text())

def observe(node):
 command=['nvidia-smi','--query-gpu=uuid,memory.used,memory.total','--format=csv,noheader,nounits']
 result=subprocess.run(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10',node,shlex.join(command)],text=True,capture_output=True,timeout=30)
 if result.returncode:raise OSError(node+': '+result.stderr.strip())
 return [dict(node=node,gpu_uuid=row[0].strip(),used_mib=float(row[1]),total_mib=float(row[2])) for row in csv.reader(result.stdout.splitlines())]


def launch(plan):
 path=C/'study_execution.json';ledger=read(path) if path.is_file() else dict(runs={})
 inventory=read(C/'batch_gpu_inventory.json');known={gpu[0] for item in inventory for gpu in item.get('gpus',[])}
 observed={};errors={}
 with concurrent.futures.ThreadPoolExecutor(3) as pool:
  futures={pool.submit(observe,node):node for node in NATIVE}
  for future in concurrent.futures.as_completed(futures):
   node=futures[future]
   try:observed[node]=future.result()
   except (OSError,ValueError,subprocess.TimeoutExpired) as error:errors[node]=str(error)
 cards=[card for node in NATIVE for card in observed.get(node,[]) if card['gpu_uuid'] in known and card['used_mib']/card['total_mib']<=.30]
 fallback={item['node']:item['gpus'][0][0] for item in inventory if item['node'] not in NATIVE and item.get('gpus')}
 fallback=[dict(node=node,gpu_uuid=fallback[node]) for node in ('compute-0-5','compute-0-0','compute-0-6','compute-0-7','compute-0-1','compute-0-3','compute-0-4') if node in fallback]
 # Every run keeps its original handle. Repairs use an explicit new run/attempt.
 used={record['gpu_uuid'] for record in ledger['runs'].values() if record.get('state') not in TERMINAL}
 cards=[card for card in cards if card['gpu_uuid'] not in used];fallback=[card for card in fallback if card['gpu_uuid'] not in used]
 ledger.update(last_admission_at=time.time(),last_admission_errors=errors)
 for filename in plan['configurations']:
  configuration=read(filename);name=configuration['run']
  if name in ledger['runs']:continue
  if not cards and not fallback:
   print(json.dumps(dict(run=name,state='WAITING_FOR_OWN_GPU_SLOT')),flush=True);continue
  card=cards.pop(0) if cards else fallback.pop(0);node=card['node'];gpu=card['gpu_uuid'];submitted=time.time()
  reserved=dict(backend='native_SSH' if node in NATIVE else 'Slurm',node=node,gpu_uuid=gpu,state='SUBMITTING',submitted_at=submitted,configuration=filename,stage=configuration['stage'],round=configuration['round'])
  if node in NATIVE:reserved['native_state']=str(C/(name+'_native.json'))
  ledger['runs'][name]=reserved;path.write_text(json.dumps(ledger,indent=2)+'\n')
  if node in NATIVE:
   py=OLD if node=='compute-0-20' else NEW
   native=dict(run=name,node=node,gpu_uuid=gpu,output=configuration['output'],root_future_bytes=16777216,command=[py,'-B','-u','tools/p_recipe/train.py','--configuration',filename])
   native_path=C/(name+'_launch.json');native_path.write_text(json.dumps(native,indent=2)+'\n')
   command=[py,'-B','-u',str(REPO/'tools/p_recipe/native_run.py'),'--configuration',str(native_path)]
   code='import subprocess;f=open('+repr(str(C/(name+'.log')))+',"ab",buffering=0);p=subprocess.Popen('+repr(command)+',stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);print(p.pid)'
   try:pid=int(subprocess.check_output(['ssh','-n','-o','ConnectTimeout=10',node,shlex.join([py,'-c',code])],text=True,timeout=30).strip())
   except (OSError,ValueError,subprocess.SubprocessError) as error:
    reserved.update(state='SUBMISSION_OBSERVATION_UNCERTAIN',observation_error=str(error));path.write_text(json.dumps(ledger,indent=2)+'\n');continue
   record=dict(backend='native_SSH',node=node,gpu_uuid=gpu,wrapper_pid=pid,native_state=str(C/(name+'_native.json')),state='LAUNCHED',submitted_at=submitted,configuration=filename,stage=configuration['stage'],round=configuration['round'])
  else:
   command=['sbatch','--parsable','--job-name='+name,'--nodelist='+node,'--exclusive',str(REPO/'tools/p_recipe/train.sbatch'),filename,gpu,configuration['output']]
   try:job_id=int(subprocess.check_output(command,cwd=REPO,text=True,timeout=30).strip().split(';')[0])
   except (OSError,ValueError,subprocess.SubprocessError) as error:
    reserved.update(state='SUBMISSION_OBSERVATION_UNCERTAIN',observation_error=str(error));path.write_text(json.dumps(ledger,indent=2)+'\n');continue
   record=dict(backend='Slurm',node=node,gpu_uuid=gpu,job_id=job_id,state='SUBMITTED',submitted_at=submitted,configuration=filename,stage=configuration['stage'],round=configuration['round'])
  ledger['runs'][name]=record;path.write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(dict(run=name,**record)),flush=True)
 path.write_text(json.dumps(ledger,indent=2)+'\n');return ledger

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--plan',required=True);a=p.parse_args();launch(read(a.plan))