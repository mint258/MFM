"""One lightweight sacct metadata capture; no allocation or scientific inputs."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import time

CONTROL=Path('/share/home/zixiao/descriptor_analysis/runs/s_recipe_20261120')


def parse_rows(raw):
    included=[];excluded=[]
    fields=('job_id','name','user','state','exit_code','node','partition',
        'allocated_cpus','elapsed_seconds','start_UTC','end_UTC','total_cpu','user_cpu','system_cpu')
    for line in raw.splitlines():
        parts=line.strip().split('|')
        if len(parts)<len(fields) or not parts[0].isdigit():continue
        row=dict(zip(fields,parts))
        for key in ('job_id','allocated_cpus','elapsed_seconds'):row[key]=int(row[key])
        if row['user']=='zixiao' and row['name'].lower().startswith(('s_','srecipe','s_recipe')):
            included.append(row)
        else:excluded.append(row['job_id'])
    return included,excluded


def cache_ready(row):
    terminal=row['state'].split()[0] in ('COMPLETED','FAILED','CANCELLED','TIMEOUT',
        'NODE_FAIL','OUT_OF_MEMORY','PREEMPTED','BOOT_FAIL','DEADLINE','REVOKED')
    return terminal and row.get('total_cpu') not in (None,'','Unknown','N/A')


def main():
    from storage_20261122 import claim_current
    from control_metadata_io_20261127 import write
    if os.getuid()!=1278:raise ValueError('Actual S owner required')
    read=lambda p:json.loads(Path(p).read_text())
    proof=read(CONTROL/'cost_slurm_check_20261127.json')
    parent=read(proof['native_record'])
    command=read(Path(proof['native_record']).with_name('command_exit.json'))
    if (proof.get('new_tests')!=2 or parent.get('status')!='COMPLETE' or parent.get('exit_code')!=0
            or command.get('exit_code')!=0 or not parent.get('owned_descendants_exited')
            or not parent.get('observer_joined')):
        raise ValueError('Actual closed metadata parser checks required')
    with (CONTROL/'execution.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        fcntl.lockf(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        cachepath=CONTROL/'cost_slurm_closed_20261127.json'
        closed=read(cachepath).get('jobs',{}) if cachepath.exists() else {}
        documents=[read(CONTROL/name) for name in ('current_state.json','execution.json')]
        documents.extend(read(p) for p in CONTROL.glob('*controller*.json'))
        legacy=CONTROL/'cost_accounting_snapshot_20261123.json'
        if legacy.exists():documents.append(dict(jobs=[dict(job_id=r['job_id']) for r in read(legacy)['jobs']]))
        ids=set()
        def visit(value,key=''):
            if isinstance(value,dict):
                for name,item in value.items():visit(item,name)
            elif isinstance(value,list):
                for item in value:visit(item,key)
            elif isinstance(value,int) and 4000000<=value<6000000:ids.add(value)
            elif isinstance(value,str) and any(w in key.lower() for w in ('job','failure','terminal','milestone','tests','status','state','history')):
                ids.update(int(v) for v in re.findall(r'(?<![\d.])([45]\d{6})(?!\d)',value))
        for document in documents:visit(document)
        query=sorted(ids-{int(v) for v in closed})
        if claim_current()<16*1024**2:raise ValueError('Insufficient existing line output headroom')
        argv=['/usr/bin/sacct','-X','-n','-P','-j',','.join(map(str,query)),
            '--format=JobIDRaw,JobName%120,User,State,ExitCode,NodeList,Partition,AllocCPUS,ElapsedRaw,Start,End,TotalCPU,UserCPU,SystemCPU']
        raw=subprocess.check_output(['/usr/bin/timeout','20s',*argv],text=True,
            env=dict(os.environ,TZ='UTC')) if query else ''
        rows,excluded=parse_rows(raw)
        for row in rows:
            if cache_ready(row):closed[str(row['job_id'])]=row
        stamp=time.time()
        result=dict(status='PARTIAL_ACCOUNTING_METADATA_NOT_FINAL_COST_REPORT',observed_time=stamp,
            command=argv,TZ='UTC',queried_ids=query,new_observations=rows,
            excluded_non_S_job_ids=excluded,closed_jobs_cached=len(closed),
            source_metadata_only=True,active_allocations_are_not_completed_fits=True)
        directory=CONTROL/'cost_slurm_snapshots_20261127';directory.mkdir(exist_ok=True)
        path=directory/(str(int(stamp*1000000))+'.json')
        write(path,result)
        write(cachepath,dict(status='CLOSED_SLURM_COST_METADATA_CACHE',jobs=closed,latest_snapshot=str(path)))
        write(CONTROL/'latest_cost_slurm_snapshot_20261127.json',dict(path=str(path)))
        print(json.dumps(dict(snapshot=str(path),new_observations=len(rows),closed_cached=len(closed),
            active_observations=[r['job_id'] for r in rows if not cache_ready(r)])),flush=True)


if __name__=='__main__':main()
