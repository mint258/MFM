"""Submit one fixed-card concurrency suite when real GPU/CPU resources are free."""
import json
import os
from pathlib import Path
import subprocess
import time

from cpu_bottleneck_step1 import capacity, SCRATCH
from cpu_perf_wait import choose, command, ROOT, OUT


def allocation(plan, observations):
    free = next(row['free_cpu'] for row in observations if row['node']==plan['node'])
    per_model = min(16,free)
    tasks = min(3,free//per_model)
    return per_model,tasks*per_model


def publish(value):
    capacity()
    value.update(pid=os.getpid(),host=os.uname().nodename,observed_time=time.time(),
        boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        start_ticks=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
    pending=OUT/'concurrency_wait.pending.json'
    pending.write_text(json.dumps(value,indent=2)+'\n')
    pending.replace(OUT/'concurrency_wait.json')
    print(json.dumps(value),flush=True)


def main():
    os.chdir(ROOT)
    job=None
    state=OUT/'concurrency_wait.json'
    if state.is_file():
        previous=json.loads(state.read_text())
        if previous.get('job'):
            publish(dict(status='EXISTING_SUBMISSION_REVIEW_REQUIRED',previous=previous))
            return
    if list(SCRATCH.glob('concurrency_*/admission.json')):
        publish(dict(status='EXISTING_MEASUREMENT_REVIEW_REQUIRED'))
        return
    while True:
        try:
            if job:
                live=command(['squeue','-h','-j',job,'-o','%T'])
                if live:
                    publish(dict(status='CONCURRENCY_JOB_LIVE',job=job,state=live,plan=plan))
                else:
                    terminal=command(['sacct','-n','-X','-j',job,'--format=JobID,State,ExitCode','--parsable2'])
                    publish(dict(status='CONCURRENCY_TERMINAL_REVIEW_REQUIRED',job=job,terminal=terminal,
                        plan=plan,result=str(SCRATCH/('concurrency_'+job)/'summary.json')))
                    return
            else:
                plan,observations=choose()
                if plan is None:
                    publish(dict(status='WAITING_FOR_IDLE_CONCURRENCY_GPU',observations=observations))
                else:
                    per_model,total=allocation(plan,observations)
                    plan.update(model_cores=per_model,allocation_cores=total)
                    export=','.join(['ALL','MFM_CPU_GPU_UUIDS='+plan['gpu'],'MFM_CPU_PYTHON='+plan['python'],
                        'MFM_CPU_CORES_PER_MODEL='+str(per_model)])
                    job=command(['sbatch','--parsable','--nodelist='+plan['node'],
                        '--cpus-per-task='+str(total),'--export='+export,
                        'tools/model_v3/cpu_perf_concurrency.sbatch']).split(';')[0]
                    if not job.isdigit():
                        raise RuntimeError('Scheduler did not return an actual job ID')
                    publish(dict(status='CONCURRENCY_SUBMITTED',job=job,plan=plan))
        except (OSError,RuntimeError,KeyError,subprocess.SubprocessError) as error:
            publish(dict(status='OBSERVATION_RETRY',job=job,reason=str(error)))
        time.sleep(60)


if __name__=='__main__':
    main()
