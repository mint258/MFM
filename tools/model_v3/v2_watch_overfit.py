"""Wait on actual diagnostic jobs and their existing disk guards; read no labels."""
import argparse
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess
import time

ROOT=Path('/share/home/zixiao/descriptor_analysis')
CONTROL=ROOT/'runs/model_v31_20261105'
OUTPUT=Path('/lfshome/zixiao/model_v31_20261105')
spec=importlib.util.spec_from_file_location('existing_model_log_reader',Path(__file__).with_name('v2_collect_runs.py'))
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
TERMINAL={'COMPLETED','FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',action='append',required=True,help='SlurmID,output-directory-name')
    p.add_argument('--interval',type=int,default=45)
    a=p.parse_args()
    runs=[value.split(',',1) for value in a.run]
    while True:
        try:
            query=subprocess.run(['sacct','-j',','.join(j for j,_ in runs),'-n','-P',
                '--format=JobIDRaw,State'],capture_output=True,text=True,check=True,timeout=10)
            states={parts[0]:parts[1].split()[0].rstrip('+') for line in query.stdout.splitlines()
                    if len(parts:=line.split('|'))>=2}
        except (OSError,subprocess.SubprocessError):
            states={}
        progress=[];events=[]
        for job,name in runs:
            try:
                row=collector.last_training_row(OUTPUT/name/'losses.csv')
            except (OSError,ValueError,KeyError):
                row={}
            state=states.get(job,'OBSERVATION_UNKNOWN')
            progress.append(dict(job=job,run=name,state=state,**row))
            if state in TERMINAL:
                events.append(dict(job=job,terminal=state))
                continue
            path=CONTROL/f'M2_controlled_{job}.state.json'
            if path.is_file():
                try:
                    guard=json.loads(path.read_text())
                    if guard['status']!='OBSERVING' or time.time()-guard['observed_at']>30:
                        events.append(dict(job=job,disk_guard=guard))
                except (OSError,ValueError,KeyError):
                    events.append(dict(job=job,disk_guard_observation='unknown'))
        print('MODEL_DIAG_PROGRESS '+datetime.datetime.now().isoformat(timespec='seconds')+' '+json.dumps(progress),flush=True)
        if events:
            print('MODEL_EVENT '+json.dumps(events),flush=True)
            return
        time.sleep(a.interval)


if __name__=='__main__':
    main()
