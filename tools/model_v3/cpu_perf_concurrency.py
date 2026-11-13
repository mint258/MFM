"""Controlled concurrency/CPU scaling, optionally alongside an authorized fixed job."""
import csv
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from cpu_bottleneck_step1 import BASE, REPO, SCRATCH, GPUS, capacity, idle_gpu, query
from model_gpu_registry import LOCKS, IDENTITY, compute_pids, registered_model_pids
from runtime_monitor import capture_process_identity


def cpu_layout(available, tasks, per_task):
    available = sorted(available)
    if tasks < 1 or per_task < 4 or len(available) < tasks*per_task:
        raise ValueError('Insufficient allocated CPU affinity for disjoint model tasks')
    return [available[i*per_task:(i+1)*per_task] for i in range(tasks)]


def capture_background(gpu):
    job = os.environ.get('MFM_CPU_BACKGROUND_JOB')
    pids = {int(value) for value in os.environ.get('MFM_CPU_BACKGROUND_PIDS','').split(',') if value}
    if not job and not pids:
        return {}
    if not job or not pids or compute_pids(gpu) != pids:
        raise RuntimeError('Existing GPU contexts must match the explicitly authorized background job')
    result = {}
    for pid in pids:
        identity = capture_process_identity(pid,expected_job=job)
        if identity.get('status') != 'ACTIVE':
            raise RuntimeError('Background model must be a live identified same-account Slurm job')
        result[pid] = identity
    return result


def require_controlled_contexts(gpu, background, own=(), *, registered=False):
    active = compute_pids(gpu)
    if not set(background) <= active or active-set(background)-set(own):
        raise RuntimeError('Authorized background disappeared or an unregistered context appeared')
    for pid, identity in background.items():
        current = capture_process_identity(pid,expected_job=identity['slurm_job_id'])
        if current.get('status') != 'ACTIVE' or any(current.get(k)!=identity.get(k) for k in IDENTITY):
            raise RuntimeError('Background process identity changed; comparison is no longer controlled')
    if registered and not active-set(background) <= registered_model_pids(gpu):
        raise RuntimeError('A measured participant is not a registered model process')


def background_progress():
    name = os.environ.get('MFM_CPU_BACKGROUND_LOSSES')
    if not name:
        return None
    # Read only the first header and at most 8 KiB of the existing append-only log.
    # Existing model output is never opened for writing.
    with Path(name).open('rb') as file:
        header = file.readline().decode().strip()
        file.seek(0,2)
        file.seek(max(0,file.tell()-8192))
        tail = file.read()
    lines = tail.split(b'\n')[:-1]
    if not lines or lines[-1].decode() == header:
        return None
    row = next(csv.DictReader([header,lines[-1].decode()]))
    return int(row['samples'])


def allocated_cpus():
    text = query('scontrol', 'show', 'job', os.environ['SLURM_JOB_ID'], '-dd', '--oneliner')
    fields = re.findall(r'CPU_IDs=([0-9,-]+)', text)
    if len(fields) != 1:
        raise RuntimeError('One actual node CPU allocation is required')
    cpus = set()
    for part in fields[0].split(','):
        ends = list(map(int,part.split('-')))
        cpus.update(range(ends[0],ends[-1]+1))
    cpus &= os.sched_getaffinity(0)
    if len(cpus) != int(os.environ['SLURM_CPUS_PER_TASK']):
        raise RuntimeError('Slurm allocated CPU IDs and actual process affinity disagree')
    return sorted(cpus)


def stop_own(children, identities):
    # No signals go to another job or to a PID whose kernel identity changed.
    for child in children:
        if child.poll() is not None:
            continue
        identity = identities.get(child.pid)
        current = capture_process_identity(child.pid)
        if identity is None and current.get('status') == 'ACTIVE':
            frame = Path(f'/proc/{child.pid}/stat').read_text().rsplit(')',1)[1].split()
            if int(frame[1]) == os.getpid() and current['pgid'] == current['sid'] == child.pid:
                identity = current
        if identity and all(current.get(k) == identity.get(k) for k in
                ('pid', 'uid', 'boot_id', 'start_ticks', 'pgid', 'sid', 'argv_sha256', 'cgroup', 'slurm_job_id')):
            os.killpg(child.pid, signal.SIGTERM)
    for child in children:
        if child.poll() is None:
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                current = capture_process_identity(child.pid)
                identity = identities.get(child.pid)
                if identity and all(current.get(k) == identity.get(k) for k in
                        ('pid','uid','boot_id','start_ticks','pgid','sid','argv_sha256','cgroup','slurm_job_id')):
                    os.killpg(child.pid,signal.SIGKILL)
                    child.wait(timeout=5)
                else:
                    raise RuntimeError('Cleanup identity unavailable; leaving job cleanup to Slurm')


def measured_rate(directory):
    with (directory/'losses.csv').open() as file:
        rows = list(csv.DictReader(file))
    if len(rows) != 1000 or int(rows[-1]['samples']) != 4_032_000:
        raise RuntimeError('A concurrency participant did not complete exactly 1000 updates')
    return (int(rows[-1]['samples'])-int(rows[0]['samples'])) / (float(rows[-1]['seconds'])-float(rows[0]['seconds']))


def phase(root, gpu, name, tasks, cores, allocated, background=None):
    capacity()
    background = background or {}
    require_controlled_contexts(gpu,background)
    layouts = cpu_layout(allocated, tasks, cores)
    output = root/name
    output.mkdir(exist_ok=False)
    gate = output/'release'
    children, logs, identities, previous = [], [], {}, {}
    samples = []
    try:
        for rank, affinity in enumerate(layouts):
            directory = output/f'task{rank}'
            temporary = output/f'tmp{rank}'
            temporary.mkdir()
            env = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu, TMPDIR=str(temporary),
                SLURM_CPUS_PER_TASK=str(cores), MFM_CPU_FIXED_WORKERS='14',
                MFM_CPU_COHORT_GATE=str(gate), MFM_CPU_COHORT_CORES=','.join(map(str, affinity)))
            env.pop('MFM_CPU_PROFILE_DIR', None)
            env.pop('MFM_CPU_HEAD_NO_RECOMPUTE', None)
            log = (output/f'task{rank}.log').open('x')
            logs.append(log)
            child = subprocess.Popen([sys.executable, '-B', '-u', str(REPO/'tools/model_v3/cpu_bottleneck_step1.py'),
                '--child', 'baseline', '--directory', str(directory)], env=env,
                stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            children.append(child)
        # Each child registers itself before importing torch or opening the GPU.
        while len(identities) < tasks:
            capacity()
            require_controlled_contexts(gpu,background)
            for rank, child in enumerate(children):
                ready = output/f'task{rank}.registered.json'
                if ready.is_file():
                    identity = json.loads(ready.read_text())
                    current = capture_process_identity(child.pid)
                    if identity['pid'] != child.pid or current.get('status') != 'ACTIVE' or any(
                            current.get(k) != identity.get(k) for k in
                            ('uid', 'boot_id', 'start_ticks', 'pgid', 'sid', 'argv_sha256', 'cgroup', 'slurm_job_id')):
                        raise RuntimeError('Cohort registration identity changed')
                    identities[child.pid] = identity
                elif child.poll() is not None:
                    raise RuntimeError(f'Participant exited before registration: {child.returncode}')
            time.sleep(.05)
        gate.touch(exist_ok=False)
        telemetry = output/'telemetry.csv'
        with telemetry.open('x', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(['unix_time', 'rank', 'pid', 'main_cpu_percent', 'gpu_power_watts',
                'gpu_memory_MiB', 'losses_bytes', 'background_samples'])
            while any(child.poll() is None for child in children):
                capacity()
                require_controlled_contexts(gpu,background,identities,registered=True)
                power, memory = map(float, query('nvidia-smi', '-i', gpu,
                    '--query-gpu=power.draw,memory.used', '--format=csv,noheader,nounits').split(','))
                now = time.monotonic()
                background_samples = background_progress()
                for rank, child in enumerate(children):
                    if child.poll() is not None:
                        if child.returncode:
                            raise RuntimeError(f'Participant {rank} failed with exit {child.returncode}')
                        continue
                    try:
                        fields = Path(f'/proc/{child.pid}/stat').read_text().rsplit(')', 1)[1].split()
                        cpu = (int(fields[11])+int(fields[12]))/os.sysconf('SC_CLK_TCK')
                        before = previous.get(child.pid)
                        percent = '' if before is None else 100*(cpu-before[0])/(now-before[1])
                        previous[child.pid] = cpu, now
                        loss = output/f'task{rank}/losses.csv'
                        size = loss.stat().st_size if loss.exists() else 0
                        row = [time.time(), rank, child.pid, percent, power, memory, size, background_samples]
                        writer.writerow(row)
                        samples.append(row)
                    except FileNotFoundError:
                        if child.poll() is None:
                            raise
                file.flush()
                time.sleep(1)
        if any(child.returncode for child in children):
            raise RuntimeError('A cohort participant failed; preserve all partial output')
        rates = [measured_rate(output/f'task{rank}') for rank in range(tasks)]
        # Restrict power/CPU averages to the common interval with loss-file growth.
        bounds = []
        for rank in range(tasks):
            rows = [row for row in samples if row[1] == rank]
            growth = [i for i in range(1,len(rows)) if rows[i][6] > rows[i-1][6]]
            if not growth:
                raise RuntimeError('No live training interval in telemetry')
            bounds.append((rows[growth[0]][0], rows[growth[-1]][0]))
        start, end = max(x[0] for x in bounds), min(x[1] for x in bounds)
        common = [row for row in samples if start <= row[0] <= end]
        if not common:
            raise RuntimeError('No overlapping training interval')
        result = dict(name=name, tasks=tasks, cpus_per_task=cores, workers_per_task=14,
            cpu_affinity=layouts, samples_per_second=rates, total_samples_per_second=sum(rates),
            gpu_power_watts_mean=sum(row[4] for row in common)/len(common),
            gpu_memory_MiB_max=max(row[5] for row in common),
            main_cpu_percent_mean=[sum(float(row[3]) for row in common if row[1]==rank and row[3]!='') /
                sum(row[1]==rank and row[3]!='' for row in common) for rank in range(tasks)])
        if background:
            progress = [row for row in common if row[1]==0 and row[7] is not None]
            result.update(background_job=next(iter(background.values()))['slurm_job_id'],
                background_samples_per_second=(progress[-1][7]-progress[0][7])/(progress[-1][0]-progress[0][0])
                    if len(progress)>1 else None)
        capacity()
        (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps(result), flush=True)
        return result
    finally:
        stop_own(children, identities)
        for log in logs:
            log.close()


def main():
    quota = capacity()
    shared = bool(os.environ.get('MFM_CPU_BACKGROUND_JOB'))
    if shared and len(GPUS) != 1:
        raise ValueError('A shared comparison must bind one explicit physical GPU')
    gpu = GPUS[0] if shared else idle_gpu()
    background = capture_background(gpu)
    allocated = allocated_cpus()
    per_task = int(os.environ.get('MFM_CPU_CORES_PER_MODEL', '16'))
    if per_task > int(os.environ['SLURM_CPUS_PER_TASK']):
        raise ValueError('Model core count exceeds the actual Slurm allocation')
    # A user-authorized shared benchmark uses a separate cohort lock. The running
    # background job keeps its original exclusive lock and is never signalled.
    lock_name = gpu+('.cpu_perf_benchmark.lock' if shared else '.lock')
    with (LOCKS/lock_name).open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        require_controlled_contexts(gpu,background)
        root = SCRATCH/('concurrency_'+os.environ['SLURM_JOB_ID'])
        root.mkdir(exist_ok=False)
        (root/'admission.json').write_text(json.dumps(dict(gpu=gpu, quota=quota, cpu_affinity=allocated,
            model_cores=per_task, workers=14, source_revision=os.environ.get('MFM_CPU_SOURCE_REVISION'),
            authorized_background=background,
            numerical_path='ORIGINAL_RECOMPUTATION_RESTORED'),indent=2)+'\n')
        results = [phase(root,gpu,'single',1,per_task,allocated,background)]
        for cores in (4,8):
            if cores < per_task:
                results.append(phase(root,gpu,f'cpu{cores}',1,cores,allocated,background))
        for tasks in (2,3):
            if len(allocated) >= tasks*per_task:
                results.append(phase(root,gpu,f'concurrent{tasks}',tasks,per_task,allocated,background))
        if background:
            results.append(phase(root,gpu,'single_final',1,per_task,allocated,background))
        baseline = results[0]['samples_per_second'][0]
        drift = None
        if background:
            final_rate = results[-1]['samples_per_second'][0]
            drift = final_rate/baseline-1
            baseline = max(baseline,final_rate)
        concurrency = [r for r in results if r['cpus_per_task']==per_task]
        eligible = [r['tasks'] for r in concurrency if min(r['samples_per_second']) >= .85*baseline]
        summary = dict(status='MEASUREMENTS_COMPLETE',gpu=gpu,job=os.environ['SLURM_JOB_ID'],
            results=results,recommended_concurrency=max(eligible),threshold_fraction=.85,
            background_job=os.environ.get('MFM_CPU_BACKGROUND_JOB'),single_baseline_drift_fraction=drift,
            recommendation_single_reference=baseline,
            unique_equivalence='FAILED_CANDIDATE_ABANDONED_ORIGINAL_MATH_RESTORED')
        capacity()
        (root/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(json.dumps(summary),flush=True)


if __name__ == '__main__':
    main()
