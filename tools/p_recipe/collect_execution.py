"""One scheduled observation of real study handles, progress and occupied GPU time."""
import csv,json,shlex,subprocess,time
from pathlib import Path
from execution_ledger import locked_ledger,write
R=Path('/share/home/zixiao/descriptor_analysis');C=R/'runs/p_recipe_20261113'
PY='/share/home/zixiao/.venvs/model_v2_cu118_20261105/bin/python'
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}


def read(path):return json.loads(Path(path).read_text())


def completed_screening_hours(records):
 hours={};revisions={}
 for record in records:
  if record['stage']==2 and record.get('state') in TERMINAL and 'elapsed_seconds' in record:
   key=str(record['round']);value=record['elapsed_seconds']/3600
   hours[key]=hours.get(key,0.)+value
   revision=revisions.setdefault(record.get('study_revision','original_20261113'),{})
   revision[key]=revision.get(key,0.)+value
  reuse=record.get('screening_reuse_attribution')
  if reuse and record['stage']!=2 and record.get('state') in TERMINAL and 'elapsed_seconds' in record:
   key=str(reuse['round']);value=record['elapsed_seconds']/3600
   hours[key]=hours.get(key,0.)+value
   revision=revisions.setdefault(reuse['study_revision'],{})
   revision[key]=revision.get(key,0.)+value
 return hours,revisions

def observe_native(record):
 path=Path(record['native_state'])
 if not path.is_file():return dict(observation_status='WAITING_FOR_NATIVE_HANDLE; do not resubmit')
 state=read(path);result=dict(state=state['status'],native_pid=state['pid'],native_uid=state['uid'],native_start_ticks=state['start_ticks'],native_pgid=state['pgid'])
 if 'exit_code' in state:
  result.update(exit_code=state['exit_code'],state='COMPLETED' if state['exit_code']==0 else 'TIMEOUT' if state['exit_code']==124 else 'FAILED',elapsed_seconds=state['elapsed_seconds'],observation_status='TERMINAL_EXIT_RECORDED')
  if state['exit_code'] in (0,-15,143) and record.get('end_reason') in ('user_requested_sbatch_migration','user_requested_recalibration'):result['state']='CANCELLED'
  return result
 code='import json;from pathlib import Path;p=Path("/proc/'+str(state['pid'])+'");f=p.joinpath("stat").read_text().rsplit(")",1)[1].split() if p.exists() else None;print(json.dumps(dict(alive=f is not None,uid=p.stat().st_uid if f else None,start_ticks=int(f[19]) if f else None)))'
 response=subprocess.check_output(['ssh','-n','-o','BatchMode=yes','-o','ConnectTimeout=10',record['node'],shlex.join([PY,'-c',code])],text=True,timeout=30)
 observed=json.loads(response)
 matches=observed['alive'] and observed['uid']==state['uid'] and observed['start_ticks']==state['start_ticks']
 result.update(observation_status='LIVE_BOUND_PROCESS' if matches else 'BOUND_PROCESS_MISSING_AWAIT_EXIT_RECORD',live_verified_at=time.time() if matches else None)
 if not matches:result['state']='EXIT_RECORD_PENDING'
 return result


def progress(configuration):
 path=Path(configuration['output'])/'losses.csv'
 if not path.is_file():return {}
 lines=subprocess.check_output(['tail','-n','1001',str(path)],text=True,timeout=10).splitlines()
 rows=[row for row in csv.reader(lines) if len(row)==6 and row[0]!='samples']
 if not rows:return {}
 first,last=rows[0],rows[-1];elapsed=float(last[5])-float(first[5]);samples=int(last[0])-int(first[0]);speed=samples/elapsed if elapsed>0 else None
 return dict(samples=int(last[0]),budget=configuration['samples'],updates=int(last[1]),last_loss=float(last[2]),samples_per_second=speed,remaining_hours=(configuration['samples']-int(last[0]))/speed/3600 if speed else None)


def collect_locked(ledger):
 path=C/'study_execution.json';records=list(ledger['runs'].values())+list(ledger.get('reservations',{}).values())
 jobs=sorted({str(r['job_id']) for r in records if r['backend']=='Slurm' and 'job_id' in r});accounting={}
 if jobs:
  text=subprocess.check_output(['sacct','--noheader','--parsable2','--jobs',','.join(jobs),'--format','JobIDRaw,State,ElapsedRaw,ExitCode'],text=True,timeout=30)
  for row in csv.reader(text.splitlines(),delimiter='|'):
   if row and row[0] in jobs:accounting[int(row[0])]=dict(state=row[1].split()[0].split('+')[0],elapsed_seconds=float(row[2]),exit_code=row[3])
 for name,record in ledger['runs'].items():
  try:
   if record['backend']=='native_SSH':record.update(observe_native(record))
   elif not record.get('accounting_closed') and record.get('job_id') in accounting:
    observed=dict(accounting[record['job_id']]);observed['allocation_elapsed_seconds']=observed['elapsed_seconds']
    observed['elapsed_seconds']=max(0.,observed['elapsed_seconds']-record.get('allocation_pretraining_seconds',record.get('overlap_native_gpu_seconds',0.)),record.get('elapsed_seconds_floor',0.))
    record.update(observed)
   configuration=read(record['configuration']);record.setdefault('study_revision',configuration.get('study_revision','original_20261113'))
   record['progress']=progress(configuration);record['observed_at']=time.time();record.pop('observation_error',None)
  except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:record['observation_error']=str(error)
 for record in ledger.get('reservations',{}).values():
  if record.get('job_id') in accounting:record.update(accounting[record['job_id']],observed_at=time.time())
 hours,revisions=completed_screening_hours(ledger['runs'].values())
 ledger.update(last_observed_at=time.time(),completed_screening_gpu_hours_by_round=hours,completed_screening_gpu_hours_by_revision=revisions)
 write(path,ledger);print(json.dumps(ledger,indent=2),flush=True);return ledger

def collect():
 with locked_ledger() as ledger:return collect_locked(ledger)

if __name__=='__main__':collect()
