"""Read-only 30-minute monitoring of this study's development jobs."""
import argparse
import csv
import json
from pathlib import Path
import socket
import subprocess
import time

from precision_quality import ROOT,capacity,read,write


def tail_row(path):
    if not path.is_file():return None
    with path.open('rb') as stream:
        stream.seek(max(0,path.stat().st_size-8192))
        rows=list(csv.reader(stream.read().decode().splitlines()))
    return next((row for row in reversed(rows) if len(row)==6 and row[0].isdigit()),None)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);args=parser.parse_args()
    if socket.gethostname().split('.')[0]!='compute-0-20':raise RuntimeError('Metadata monitor belongs on development compute20')
    while True:
        capacity();plan=read(args.plan)
        jobs=','.join(str(item['job_id']) for item in plan['jobs'])
        query=subprocess.run(['sacct','-n','-P','-j',jobs,'--format=JobIDRaw,State,ExitCode,Elapsed,NodeList'],text=True,capture_output=True)
        accounting=query.stdout;accounting_source='sacct';accounting_error=None
        if query.returncode:
            # This cluster's compute nodes can submit/query allocations, but
            # their accounting database connection can be unavailable.
            accounting_error=query.stderr.strip()
            fallback=subprocess.run(['squeue','-h','-j',jobs,'-o','%i|%T|%M|%N'],text=True,capture_output=True)
            accounting=fallback.stdout;accounting_source='squeue'
            if fallback.returncode:accounting_error+='; '+fallback.stderr.strip()
        progress=[]
        for item in plan['jobs']:
            if item['node']=='compute-0-21':raise RuntimeError('User excludes node21')
            row=dict(item)
            if item.get('configuration'):
                c=read(item['configuration']);output=Path(c['output']);last=tail_row(output/'losses.csv')
                if last:row.update(samples=int(last[0]),updates=int(last[1]),last_loss=float(last[2]),active_training_seconds=float(last[5]))
                if (output/'summary.json').is_file():row['summary']=read(output/'summary.json')
                state=ROOT/'control'/(c['run']+'_slurm.json')
                if state.is_file():row['process_state']=read(state)
            progress.append(row)
        payload=dict(observed_at=time.time(),node=socket.gethostname(),jobs=progress,accounting=accounting,
            accounting_source=accounting_source,accounting_error=accounting_error,
            closed_speed_cells=[str(p) for p in ROOT.glob('speed_*/benchmark.json')],
            school_job_id=plan.get('school_job_id'),excluded_nodes=['compute-0-21'])
        write(ROOT/'CURRENT.json',payload)
        print(json.dumps(payload),flush=True)
        for _ in range(30):time.sleep(60)
