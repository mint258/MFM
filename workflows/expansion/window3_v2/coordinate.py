"""Root's lightweight submission coordinator; no scientific calls or QA jobs."""
import argparse
import fcntl
from pathlib import Path
import subprocess
import time
from .producer import read, save


def parents(ids):
    raw=subprocess.check_output(['sacct','-X','-P','-n','-j',','.join(ids),'-o','JobIDRaw,State,ExitCode'],text=True)
    return {row[0]:row[1:] for line in raw.splitlines() if line.strip() for row in [line.split('|')]}


def wait(ids):
    while True:
        status=parents(ids)
        print(time.strftime('%Y-%m-%d %H:%M:%S'),status,flush=True)
        if all(status.get(job,[])[:2]==['COMPLETED','0:0'] for job in ids):return
        if any(value[0].split()[0].rstrip('+') in {'FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED'} for value in status.values()):
            raise RuntimeError('Actual parent needs continuation; preserve its outputs: '+str(status))
        time.sleep(60)


def run(root,pilot_job):
    lock=(root/'coordinator.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    wait([pilot_job])
    pilot=read(root/'pilot/summary.json')
    if pilot['counts']['molecules']!=10000 or pilot['streams']!={'R':5000,'N':5000}:
        raise RuntimeError('Complete 10k pilot required before full submission')
    cpus=sum(read(root/f'full_{i}_config.json')['workers'] for i in range(4))
    save(root/'pilot_plan.json',{'pilot_molecules':10000,'pilot_wall_seconds':pilot['wall_seconds'],
         'pilot_states':pilot['states'],'selected_total_CPUs':cpus,
         'estimated_remaining_wall_seconds_from_observed_allocated_throughput':pilot['wall_seconds']*249*pilot['workers']/cpus,
         'estimate_is_descriptive_and_has_no_stopping_threshold':True})
    path=root/'full_jobs.json'; jobs=read(path) if path.exists() else []
    for i in range(len(jobs),4):
        config=read(root/f'full_{i}_config.json')
        job=subprocess.check_output(['sbatch','--parsable',str(root/f'full_{i}.sbatch')],text=True).strip().split(';')[0]
        if not job.isdigit():raise RuntimeError('Unexpected sbatch response: '+job)
        jobs.append({'job_id':job,'config':str(root/f'full_{i}_config.json'),'output':config['output'],'CPUs':config['workers']})
        save(path,jobs)
        print('Submitted',jobs[-1],flush=True)
    config=read(root/'report_config.json')
    config['job_ids']=list(dict.fromkeys([*config['job_ids'],*[j['job_id'] for j in jobs]]))
    save(root/'report_config.json',config)
    wait([j['job_id'] for j in jobs])
    from .report import run as report
    report(config)
    print('E2/E3 complete; batch report ready for Root GitHub publication and STATUS append',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True,type=Path);parser.add_argument('--pilot-job',required=True)
    args=parser.parse_args();run(args.root,args.pilot_job)
