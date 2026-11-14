"""Run an ordinary allocation directly, or cooperatively take over its SSH twin."""
import argparse,csv,datetime,json,os,socket,subprocess,time,uuid
from pathlib import Path
from execution_ledger import C,locked_ledger,read,write
from native_run import identity,run as guarded_run
from scheduling import requested_cpus
R=Path('/share/home/zixiao/descriptor_analysis');REPO=R/'MFM_p_recipe'

def allocation_start(job):
 text=subprocess.check_output(['scontrol','show','job',str(job),'-o'],text=True)
 if 'JobState=RUNNING' not in text:raise RuntimeError('Allocation is not running')
 value=next(t.split('=',1)[1] for t in text.split() if t.startswith('StartTime='))
 return datetime.datetime.fromisoformat(value).replace(tzinfo=datetime.timezone(datetime.timedelta(hours=8))).timestamp()

def handoff(task,job):
 """No signal to the trainer: it saves at a committed update and exits itself."""
 configuration=read(task['configuration']);state_path=Path(task['native_state'])
 request=dict(action='SAVE_AND_EXIT',run=configuration['run'],job_id=job,request_id=str(uuid.uuid4()))
 sent=False
 while True:
  if not state_path.is_file():time.sleep(1);continue
  native=read(state_path)
  if 'exit_code' in native:
   ack_path=Path(configuration['handoff_ack'])
   ack=read(ack_path) if ack_path.is_file() else None
   if sent and ack and ack.get('request_id')==request['request_id']:
    if native['exit_code']!=0:raise RuntimeError('Source failed after saving; inspect before resuming')
    checkpoint=Path(ack['checkpoint'])
    if checkpoint.parent.resolve()!=Path(configuration['output']).resolve() or not checkpoint.is_file():raise RuntimeError('Invalid handoff checkpoint')
    samples=int(ack['clock']['samples_consumed'])
    if samples<=0 or samples>=configuration['samples']:raise RuntimeError('Invalid handoff sample cursor')
    return configuration,native,ack
   summary_path=Path(configuration['output'])/'summary.json'
   if native['exit_code']==0 and summary_path.is_file() and read(summary_path).get('status')=='COMPLETE':return None
   raise RuntimeError('Source exited without a matching completed handoff or final evaluation')
  # The worker may exit before its 5-second wrapper publishes the terminal state.
  # A complete matching acknowledgement permits waiting, never another signal.
  ack_path=Path(configuration['handoff_ack'])
  if sent and ack_path.is_file() and read(ack_path).get('request_id')==request['request_id']:
   time.sleep(1);continue
  bound={key:native[key] for key in ('pid','uid','start_ticks','pgid')}
  if bound['uid']!=os.getuid() or identity(bound['pid'])!=bound:raise RuntimeError('Source identity changed; no action taken')
  if not sent:
   # An already completed training budget finishes its existing evaluation on SSH.
   summary_path=Path(configuration['output'])/'summary.json'
   if not summary_path.is_file():
    write(configuration['handoff_request'],request);sent=True
    write(task['handoff_state'],dict(phase='REQUESTED',job_id=job,request=request,requested_at=time.time()))
  time.sleep(1)

def main(task_path):
 task=read(task_path);job=int(os.environ['SLURM_JOB_ID']);node=socket.gethostname().split('.')[0]
 if node!=task['node']:raise RuntimeError('Allocation is on a different node')
 configuration=read(task['configuration']);policy=read(REPO/'configs/p_recipe/scheduling.json')
 if int(os.environ['SLURM_CPUS_PER_TASK'])<requested_cpus(configuration,policy):raise RuntimeError('Insufficient allocated CPU count')
 started=allocation_start(job)
 if task['mode']=='native_with_standby':
  result=handoff(task,job)
  if result is None:
   with locked_ledger() as ledger:
    ledger['reservations'][task['reservation_key']].update(phase='SOURCE_ALREADY_COMPLETE',state='COMPLETED')
   return 0
  original,native,ack=result
  name=original['run']+'_sbatch';new_configuration=C/(name+'_configuration.json');snapshot=C/(original['run']+'_native_configuration.json')
  c=dict(original,run=name,output=str(Path(original['output']).parent/name),attempt=original.get('attempt',1)+1,resume=ack['checkpoint'],resume_samples=ack['clock']['samples_consumed'],resume_from_output=original['output'])
  c.pop('handoff_request',None);c.pop('handoff_ack',None)
  if Path(c['output']).exists():raise RuntimeError('Takeover output already exists; inspect existing handle')
  write(snapshot,original);write(new_configuration,c)
  with locked_ledger() as ledger:
   source=ledger['runs'][original['run']]
   source.update(configuration=str(snapshot),end_reason='user_requested_sbatch_migration',handoff_job_id=job,state='CANCELLED',exit_code=native['exit_code'],elapsed_seconds=native['elapsed_seconds'])
   ledger['runs'][name]=dict(backend='Slurm',node=node,gpu_uuid=task['gpu_uuid'],job_id=job,state='RUNNING',submitted_at=task['submitted_at'],configuration=task['configuration'],stage=c['stage'],round=c['round'],resume_from_run=original['run'],resume_samples=c['resume_samples'],allocation_pretraining_seconds=max(0,time.time()-started))
   ledger['reservations'][task['reservation_key']].update(phase='HANDED_OFF',training_run=name)
   write(task['configuration'],c)
   plan_path=Path(task['configuration']).parent/'plan.json'
   if plan_path.is_file():
    plan=read(plan_path);sizes=plan.setdefault('batch_size_by_run',{});sizes.pop(original['run'],None);sizes[name]=c['batch_size'];write(plan_path,plan)
  configuration=c
  write(task['handoff_state'],dict(phase='SOURCE_EXITED_RESUME_READY',job_id=job,run=name,resume=ack['checkpoint'],resume_samples=c['resume_samples']))
 else:
  new_configuration=Path(task['configuration'])
  with locked_ledger() as ledger:
   ledger['runs'][configuration['run']].update(allocation_pretraining_seconds=max(0,time.time()-started))
 # Wait only for our departing CUDA context and UUID lock to be released.
 from launch_plan import own_gpu_busy
 while True:
  rows=csv.reader(subprocess.check_output(['nvidia-smi','--query-compute-apps=gpu_uuid,pid','--format=csv,noheader,nounits'],text=True).splitlines())
  old_context=task['mode']=='native_with_standby' and any(row and row[0].strip()==task['gpu_uuid'] and int(row[1])==native['pid'] for row in rows)
  if not old_context and not own_gpu_busy(task['gpu_uuid']):break
  time.sleep(1)
 launch=dict(run=configuration['run'],execution='Slurm',node=node,gpu_uuid=task['gpu_uuid'],output=configuration['output'],root_future_bytes=16777216,minimum_free_gpu_mib=task['minimum_free_gpu_mib'],state_path=str(C/(configuration['run']+'_slurm.json')),command=[task['python'],'-B','-u','tools/p_recipe/train.py','--configuration',str(new_configuration)])
 return guarded_run(launch)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--task',required=True);a=p.parse_args();raise SystemExit(main(a.task))
