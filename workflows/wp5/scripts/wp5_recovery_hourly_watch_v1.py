"""Bounded read-only hourly recovery monitor; submits no jobs and writes no queue."""
import collections,json,os,socket,subprocess,time
from pathlib import Path
R=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
def emit(event,**data):print(json.dumps({'event':event,'time':time.time(),**data},ensure_ascii=False),flush=True)
def main():
 assert socket.gethostname().split('.')[0]=='sonmi' and os.getuid()==1278
 sub=json.loads((R/'submission/recovery_attempt_v11/submitted_jobs.json').read_text());assert sub['status']=='ALL_MAIN_AND_SIX_CLEANUP_SUBMITTED'
 ids={str(x['job_id']) for x in sub['main']+sub['cleanup']};assert len(ids)==78
 start=time.monotonic();next_hour=1;previous=None
 emit('WATCH_STARTED',pid=os.getpid(),hours_limit=192,formal_jobs=78)
 while time.monotonic()-start<192*3600:
  p=json.loads((R/'reports/observation_latest.json').read_text());assert p['uid']==1278 and p['hostname']=='sonmi'
  age=time.time()-p['time'];states={j:p['registered_job_states'].get(j) for j in ids}
  stop=R/'STOP_NEW_MOLECULES.json';failed={j:s for j,s in states.items() if s and s not in ('RUNNING','PENDING','COMPLETED','COMPLETING','CONFIGURING')}
  alert=(bool(stop.exists()),tuple(sorted(failed.items())),age>180)
  if alert!=previous and (alert[0] or alert[1] or alert[2]):emit('RUNTIME_ALERT',STOP=json.loads(stop.read_text()) if stop.exists() else None,states=failed,publisher_age_seconds=age)
  previous=alert
  terminal=all(s in ('COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL','OUT_OF_MEMORY','TIMEOUT') for s in states.values())
  elapsed=time.monotonic()-start
  if elapsed>=next_hour*3600 or terminal:
   command=['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','compute-0-20',
    'cd /share/home/zixiao/descriptor_analysis && PYTHONPATH='+str(R/'scripts')+' /share/home/zixiao/.conda/envs/chemprop/bin/python -B '+str(R/'scripts/wp5_hourly_observe_v2.py')+' --hour '+str(next_hour)+' --write-latest']
   result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
   (R/'reports'/('recovery_hour_'+str(next_hour)+'_observer_stdout.json')).write_text(result.stdout)
   if result.returncode:emit('OBSERVER_COMMAND_ERROR',exit_code=result.returncode,stderr=result.stderr);return
   out=json.loads(result.stdout)
   emit('HOURLY_PROGRESS',hour=next_hour,complete_molecules=out['complete_molecules'],complete_records=out['complete_records'],retry_molecules=out['retry_molecules'],population_closed=out['population_closed'],task_denominators_closed=out['task_denominators_closed'],current_states=out['current_phase']['state_counts'],current_runtime_errors=out['runtime_errors_current'],cumulative_core_hours=out['cumulative_actual_allocated_core_hours_known_sum'])
   next_hour+=1
  if terminal:emit('ALL_78_TERMINAL_REQUIRES_ROOT_REVIEW',states=dict(collections.Counter(states.values())));return
  time.sleep(60)
 emit('BOUNDED_WATCH_LIFETIME_ENDED')
if __name__=='__main__':main()