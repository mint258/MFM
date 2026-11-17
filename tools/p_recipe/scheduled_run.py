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

def reentered_handoff(task,configuration,job,started):
 """A re-entered allocation resumes its trainer, never its old SSH handoff."""
 state_path=Path(task['handoff_state'])
 if not state_path.is_file():return None
 state=read(state_path)
 if state.get('phase')!='SOURCE_EXITED_RESUME_READY':return None
 if state.get('run')!=configuration['run'] or int(state['job_id'])!=job:
  raise RuntimeError('Handoff/configuration/job identity mismatch')
 output=Path(configuration['output']);summary=output/'summary.json'
 while True:
  process=C/(configuration['run']+'_slurm.json');previous=read(process) if process.is_file() else {};live=False
  if all(k in previous for k in ('pid','uid','start_ticks','pgid')):
   bound={k:previous[k] for k in ('pid','uid','start_ticks','pgid')}
   try:live=bound['uid']==os.getuid() and identity(bound['pid'])==bound
   except (FileNotFoundError,ProcessLookupError):pass
  if not live:
   if summary.is_file() and read(summary).get('status')=='COMPLETE':return 'COMPLETE'
   break
  time.sleep(1)
 points=[]
 for path in output.glob('samples_*.pt'):
  sample=path.stem.removeprefix('samples_')
  if sample.isdigit() and 0<int(sample)<=configuration['samples']:points.append((int(sample),path))
 if configuration.get('resume') and Path(configuration['resume']).is_file():
  points.append((int(configuration['resume_samples']),Path(configuration['resume'])))
 if not points:raise RuntimeError('No complete checkpoint for re-entry; preserve output')
 samples,checkpoint=max(points,key=lambda p:p[0]);name=configuration['run']+'_reentry_'+str(int(started))
 destination=output.parent/name
 if destination.exists():raise RuntimeError('Re-entry output exists; inspect actual handle')
 archive=Path(task['configuration']).parent/'archive'/f'reentry_{job}_{int(started)}.json'
 archive.parent.mkdir(parents=True,exist_ok=True)
 if archive.exists():raise RuntimeError('Re-entry archive already exists')
 write(archive,configuration)
 c=dict(configuration,run=name,output=str(destination),resume=str(checkpoint),resume_samples=samples,
        resume_from_output=str(output),attempt=configuration.get('attempt',1)+1)
 for key in ('handoff_request','handoff_ack'):c.pop(key,None)
 measured=0.;losses=output/'losses.csv'
 if losses.is_file():
  with losses.open() as stream:timings=[float(row[5]) for row in csv.reader(stream) if len(row)==6 and row[0].isdigit()]
  if timings:measured=max(0.,timings[-1]-timings[0])
 with locked_ledger() as ledger:
  old=ledger['runs'][configuration['run']]
  old['last_allocation_observation']={k:old.get(k) for k in ('state','elapsed_seconds','exit_code','job_id')}
  old.update(configuration=str(archive),accounting_closed=True,state='FAILED',exit_code=None,
      end_reason='allocation_reentry_previous_worker_missing',
      elapsed_seconds=max(old.get('elapsed_seconds',0.),old.get('elapsed_seconds_floor',0.),measured),
      cost_note='Previous observation or CSV duration lower bound retained; old worker absent')
  ledger['runs'][name]=dict(backend='Slurm',node=task['node'],gpu_uuid=task['gpu_uuid'],job_id=job,
      state='RUNNING',submitted_at=time.time(),configuration=task['configuration'],stage=c['stage'],round=c['round'],
      study_revision=c.get('study_revision','original_20261113'),resume_from_run=configuration['run'],
      resume_samples=samples,allocation_pretraining_seconds=max(0,time.time()-started))
  ledger['reservations'][task['reservation_key']].update(phase='HANDED_OFF',training_run=name)
  write(task['configuration'],c)
  plan_path=Path(task['configuration']).parent/'plan.json'
  if plan_path.is_file():
   plan=read(plan_path);sizes=plan.setdefault('batch_size_by_run',{});sizes.pop(configuration['run'],None);sizes[name]=c['batch_size']
   plan.setdefault('archived_configurations',[]).append(str(archive));write(plan_path,plan)
 write(state_path,dict(phase='SOURCE_EXITED_RESUME_READY',job_id=job,run=name,resume=str(checkpoint),resume_samples=samples))
 return c


def main(task_path):
 task=read(task_path);job=int(os.environ['SLURM_JOB_ID']);node=socket.gethostname().split('.')[0]
 if node!=task['node']:raise RuntimeError('Allocation is on a different node')
 configuration=read(task['configuration']);policy=read(REPO/'configs/p_recipe/scheduling.json')
 if int(os.environ['SLURM_CPUS_PER_TASK'])<requested_cpus(configuration,policy):raise RuntimeError('Insufficient allocated CPU count')
 started=allocation_start(job)
 replay=reentered_handoff(task,configuration,job,started) if task['mode']=='native_with_standby' else None
 if replay=='COMPLETE':return 0
 if replay:configuration=replay
 if task['mode']=='native_with_standby' and not replay:
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
   ledger['runs'][name]=dict(backend='Slurm',node=node,gpu_uuid=task['gpu_uuid'],job_id=job,state='RUNNING',submitted_at=task['submitted_at'],configuration=task['configuration'],stage=c['stage'],round=c['round'],study_revision=c.get('study_revision','original_20261113'),resume_from_run=original['run'],resume_samples=c['resume_samples'],allocation_pretraining_seconds=max(0,time.time()-started))
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
  old_context=task['mode']=='native_with_standby' and not replay and any(row and row[0].strip()==task['gpu_uuid'] and int(row[1])==native['pid'] for row in rows)
  if not old_context and not own_gpu_busy(task['gpu_uuid']):break
  time.sleep(1)
 launch=dict(run=configuration['run'],execution='Slurm',node=node,gpu_uuid=task['gpu_uuid'],output=configuration['output'],root_future_bytes=16777216,nfs_future_bytes=configuration.get('nfs_future_bytes',67108864),minimum_free_gpu_mib=task['minimum_free_gpu_mib'],state_path=str(C/(configuration['run']+'_slurm.json')),command=[task['python'],'-B','-u','tools/p_recipe/train.py','--configuration',str(new_configuration)])
 return guarded_run(launch)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--task',required=True);a=p.parse_args();raise SystemExit(main(a.task))
