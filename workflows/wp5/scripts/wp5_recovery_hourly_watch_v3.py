"""Bounded read-only hourly monitor of the latest effective72main+6cleanup jobs."""
import argparse, collections, hashlib, json, os, socket, subprocess, time
from pathlib import Path
from wp5_hourly_observe_v3 import ROOT, effective_jobs
R=ROOT
ACTIVE={'RUNNING','PENDING','COMPLETING','CONFIGURING','RESIZING','SUSPENDED'}
TERMINAL={'COMPLETED','FAILED','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL','OUT_OF_MEMORY','TIMEOUT','DEADLINE','REVOKED'}
def emit(event,**data):print(json.dumps({'event':event,'time':time.time(),**data},ensure_ascii=False),flush=True)
def atomic(path,data):
    tmp=path.with_name(path.name+'.'+str(os.getpid())+'.pending')
    tmp.write_text(json.dumps(data,indent=2)+'\n');os.replace(tmp,path)
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hours-limit',type=float,default=192)
    parser.add_argument('--first-hour',type=int,default=1)
    a=parser.parse_args()
    assert socket.gethostname().split('.')[0]=='sonmi' and os.getuid()==1278
    stat=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()
    identity={'status':'READONLY_EFFECTIVE_HOURLY_WATCH_PROCESS_STARTED','time':time.time(),
        'uid':os.getuid(),'pid':os.getpid(),'start_ticks':stat[19],
        'source_path':str(Path(__file__).resolve()),'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'hours_limit':a.hours_limit,'science_queue_writes':False,'Slurm_submission':False}
    atomic(R/'reports/recovery_hourly_watch_v3_identity.json',identity)
    (R/'reports/recovery_hourly_watch_v3.pid').write_text(str(os.getpid())+'\n')
    start=time.monotonic();next_report=start+3600;hour=a.first_hour;previous_alert=None;waiting=False
    emit('WATCH_STARTED',**identity,termination_scope='Latest effective72logicalmains+6cleanup, never old78')
    while time.monotonic()-start<a.hours_limit*3600:
        selection=effective_jobs()
        if not selection['ready']:
            if not waiting:emit('WAITING_FOR_EFFECTIVE_SUBMISSION_MANIFEST',status=selection['startup_manifest_status'])
            waiting=True;time.sleep(60);continue
        waiting=False;ids=set(selection['effective_job_ids'])
        p=json.loads((R/'reports/observation_latest.json').read_text())
        assert p['uid']==1278 and p['hostname']=='sonmi'
        age=time.time()-p['time'];states={j:p.get('registered_job_states',{}).get(j) for j in ids}
        normalized={j:s.split()[0] if s else None for j,s in states.items()}
        stop=R/'STOP_NEW_MOLECULES.json'
        failed={j:s for j,s in normalized.items() if s and s not in ACTIVE|{'COMPLETED'}}
        alert=(stop.exists(),tuple(sorted(failed.items())),age>180)
        if alert!=previous_alert and any((alert[0],alert[1],alert[2])):
            emit('RUNTIME_ALERT_CURRENT_EFFECTIVE_ONLY',STOP=json.loads(stop.read_text()) if stop.exists() else None,
                 states=failed,publisher_age_seconds=age,superseded_historical_failures_ignored=True)
        previous_alert=alert
        terminal=age<=180 and len(ids)==78 and all(s in TERMINAL for s in normalized.values())
        if time.monotonic()>=next_report or terminal:
            command=['ssh','-n','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','compute-0-20',
                'cd /share/home/zixiao/descriptor_analysis && PYTHONPATH='+str(R/'scripts')+
                ' /share/home/zixiao/.conda/envs/chemprop/bin/python -B '+str(R/'scripts/wp5_hourly_observe_v3.py')+
                ' --hour '+str(hour)+' --write-latest']
            result=subprocess.run(command,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=600)
            (R/'reports'/('startup_replacement_hour_'+str(hour)+'_observer_stdout.json')).write_text(result.stdout)
            if result.returncode:emit('OBSERVER_COMMAND_ERROR',exit_code=result.returncode,stderr=result.stderr);return
            out=json.loads(result.stdout)
            emit('HOURLY_PROGRESS',hour=hour,complete_molecules=out['complete_molecules'],
                complete_records=out['complete_records'],retry_molecules=out['retry_molecules'],
                population_closed=out['population_closed'],task_denominators_closed=out['task_denominators_closed'],
                effective_job_count=out['effective_job_count'],current_states=out['current_phase']['state_counts'],
                current_runtime_errors=out['runtime_errors_current'],
                cumulative_core_hours=out['cumulative_actual_allocated_core_hours_known_sum'],
                cumulative_core_hours_extrapolated_at10pct=out['cumulative_allocated_core_hours_extrapolated_at10pct'],
                projection_status=out['core_hours_projection_status'])
            hour+=1;next_report=time.monotonic()+3600
        if terminal:
            emit('ALL_EFFECTIVE_72MAIN_6CLEANUP_TERMINAL_REQUIRES_ROOT_REVIEW',
                 states=dict(collections.Counter(normalized.values())),scientific_completion_claimed=False);return
        time.sleep(60)
    emit('BOUNDED_WATCH_LIFETIME_ENDED')
if __name__=='__main__':main()
