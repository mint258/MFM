"""Observe actual S handles and queue its original final bootstrap on CPU."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time

from dispatch import ledger, read
from runtime import CONTROL, REPO, write

TERMINAL = {'COMPLETED', 'FAILED', 'CANCELLED', 'TIMEOUT', 'OUT_OF_MEMORY', 'NODE_FAIL', 'PREEMPTED'}


def accounting(jobs):
    if not jobs:
        return {}
    command = ['sacct', '-X', '-n', '-P', '-j', ','.join(map(str, jobs)),
               '--format=JobIDRaw,State,ExitCode,NodeList,ElapsedRaw']
    try:
        output = subprocess.check_output(command, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        # Established HPC route when compute-node localhost:6819 is unavailable.
        # Only scheduler metadata runs on the login host; all scientific work
        # remains in the existing CPU/GPU allocations. Failure is not terminal
        # evidence for any observed training handle.
        output = subprocess.check_output(['ssh', '-n', '-o', 'BatchMode=yes',
            '-o', 'ConnectTimeout=5', 'sonmi', shlex.join(command)],
            text=True, timeout=45)
    result = {}
    for line in output.splitlines():
        row = line.split('|')
        if len(row) >= 5 and row[0].isdigit():
            result[int(row[0])] = dict(state=row[1].split()[0].rstrip('+'), exit_code=row[2],
                                      node=row[3], elapsed_seconds=int(row[4]))
    return result


def collect(queue_statistics=False):
    with ledger() as state:
        jobs = [r['job_id'] for group in ('runs', 'statistics') for r in state[group].values() if r.get('job_id')]
        observed = accounting(jobs)
        for name, run in state['runs'].items():
            actual = observed.get(run.get('job_id'))
            if actual:
                run['slurm'] = actual
                run['status'] = actual['state']
            task = read(run['task'])
            process = Path(task['state_path'])
            if process.is_file():
                run['process'] = read(process)
            configuration = read(run['configuration'])
            output = Path(configuration['output'])
            summary = output/'summary.json'
            if summary.is_file():
                summary = read(summary)
                run['scientific_status'] = summary['status']
                # A native source can complete before its standby allocation.
                if (task['mode'] == 'native_with_standby' and actual and actual['state'] == 'PENDING' and
                        run.get('process', {}).get('exit_code') == 0 and summary['status'] in
                        ('COMPLETE', 'GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS')):
                    subprocess.run(['scancel', str(run['job_id'])], check=True, timeout=30)
                    run.update(status='COMPLETED', standby_end_reason='Native task already finished; unused standby cancelled')
                if (queue_statistics and run.get('process', {}).get('exit_code') == 0 and
                        summary['status'] == 'GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS' and
                        name not in state['statistics']):
                    command = ['sbatch', '--parsable', '--job-name='+name+'_statistics',
                        '--output='+str(CONTROL/(name+'_statistics_%j.log')),
                        str(REPO/'tools/s_recipe/statistics.sbatch'), run['configuration']]
                    state['statistics'][name] = dict(status='SUBMITTING', submitted_at=time.time(),
                                                      configuration=run['configuration'])
                    write(CONTROL/'execution.json', state)
                    try:
                        job = int(subprocess.check_output(command, text=True, timeout=30).strip().split(';')[0])
                        state['statistics'][name].update(job_id=job, status='SUBMITTED')
                    except (OSError, ValueError, subprocess.SubprocessError) as error:
                        state['statistics'][name].update(status='SUBMISSION_OBSERVATION_UNCERTAIN', error=str(error))
                    write(CONTROL/'execution.json', state)
        for name, record in state['statistics'].items():
            if record.get('job_id') in observed:
                record['slurm'] = observed[record['job_id']]
                record['status'] = record['slurm']['state']
        state['last_collected_at'] = time.time()
        return state


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--queue-statistics', action='store_true')
    args = p.parse_args()
    print(json.dumps(collect(args.queue_statistics)), flush=True)
