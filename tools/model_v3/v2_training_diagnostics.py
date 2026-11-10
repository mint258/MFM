"""Read-only system observations and 1000-update losses, paired to real training.

This CPU sidecar never imports the model, reads training examples, or signals a
training process. Its W&B run shares the producer's group and records its ID.
W&B's internal diagnostic step is separate from the scientific sample clock.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import shlex
import socket
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).absolute().parent))
from v2_wandb_tracking import CsvTail, LOSS_KEYS, TERMINAL, job_state, save


class UpdateMeans:
    """Nonoverlapping, contiguous actual-update windows within one execution."""
    def __init__(self, size=1000):
        self.size, self.previous, self.rows = size, None, []

    def add(self, row):
        update = row['updates']
        if self.previous is not None and update != self.previous + 1:
            raise ValueError('Loss windows require consecutive producer updates')
        self.previous = update
        self.rows.append(row)
        if len(self.rows) < self.size:
            return None
        result = self.summary(partial=False)
        self.rows = []
        return result

    def summary(self, *, partial=True):
        if not self.rows:
            return None
        means, counts = {}, {}
        for key in sorted(LOSS_KEYS):
            values = [r[key] for r in self.rows if key in r and math.isfinite(r[key])]
            if values:
                means[key], counts[key] = math.fsum(values) / len(values), len(values)
        return dict(first_update=self.rows[0]['updates'], last_update=self.rows[-1]['updates'],
            first_samples=self.rows[0]['samples'], last_samples=self.rows[-1]['samples'],
            updates=len(self.rows), requested_updates=self.size, partial=partial,
            imported_records=sum(bool(r.get('_imported')) for r in self.rows),
            reduction='arithmetic mean of logged optimizer-update losses', means=means, counts=counts)


def number(value):
    try:
        value = float(value)
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def gpu_observation(gpus, processes, gpu, owns):
    columns = ['utilization_percent', 'memory_utilization_percent', 'memory_used_mib',
        'memory_total_mib', 'power_watts', 'temperature_celsius', 'sm_clock_mhz', 'memory_clock_mhz']
    selected = next((r for r in csv.reader(gpus.splitlines()) if r and r[0].strip() == gpu), None)
    if selected is None or len(selected) != len(columns) + 1:
        raise ValueError('Expected actual GPU UUID absent from telemetry')
    metrics = {'gpu/' + k: value for k, raw in zip(columns, selected[1:])
        if (value := number(raw.strip())) is not None}
    owned, foreign, memory = [], 0, []
    for row in csv.reader(processes.splitlines()):
        if len(row) != 3 or row[0].strip() != gpu:
            continue
        pid = int(row[1].strip())
        if owns(pid):
            owned.append(pid)
            value = number(row[2].strip())
            if value is not None:
                memory.append(value)
        else:
            foreign += 1
    metrics['gpu/other_process_count'] = foreign
    if memory:
        metrics['gpu/own_process_memory_mib'] = math.fsum(memory)
    return metrics, sorted(set(owned))


def owns_job(pid, job, *, proc=Path('/proc'), uid=1278):
    try:
        status = (proc / str(pid) / 'status').read_text()
        actual = next(line.split()[1] for line in status.splitlines() if line.startswith('Uid:'))
        groups = (proc / str(pid) / 'cgroup').read_text()
        return int(actual) == uid and re.search(r'/job_' + str(job) + r'(?:/|$)', groups) is not None
    except (OSError, StopIteration, ValueError):
        return False


def process_counters(pid):
    root = Path('/proc') / str(pid)
    fields = (root / 'stat').read_text().rsplit(')', 1)[1].split()
    result = dict(pid=pid, start_ticks=int(fields[19]),
        cpu_seconds=(int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK'),
        rss_bytes=int(fields[21]) * os.sysconf('SC_PAGE_SIZE'), major_faults=int(fields[9]))
    for line in (root / 'io').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in {'read_bytes', 'write_bytes'}:
            result[key] = int(value)
    return result


def collect(job, gpu):
    if os.getuid() != 1278:
        raise ValueError('System observer must run as model account UID1278')
    query = 'uuid,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw,temperature.gpu,clocks.current.sm,clocks.current.memory'
    def command(args):
        return subprocess.run(args, capture_output=True, text=True, check=True, timeout=15).stdout
    metrics, pids = gpu_observation(
        command(['nvidia-smi', '--query-gpu=' + query, '--format=csv,noheader,nounits']),
        command(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid,used_gpu_memory', '--format=csv,noheader,nounits']),
        gpu, lambda pid: owns_job(pid, job))
    counters = []
    for pid in pids:
        try:
            counters.append(process_counters(pid))
        except (OSError, ValueError, IndexError):
            pass  # A disappearing process is an observation, not a successful zero.
    if counters:
        metrics['process/main_rss_sum_bytes'] = sum(p['rss_bytes'] for p in counters)
    metrics['process/observed_main_count'] = len(counters)
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith(('MemAvailable:', 'MemTotal:')):
            key, value, _ = line.split()
            metrics['node/' + ('memory_available_bytes' if key == 'MemAvailable:' else 'memory_total_bytes')] = int(value) * 1024
    metrics['node/load1'] = os.getloadavg()[0]
    for label, path in [('root', '/'), ('output', '/lfshome/zixiao/model_v31_20261105')]:
        fs = os.statvfs(path)
        metrics['filesystem/' + label + '_available_bytes'] = fs.f_bavail * fs.f_frsize
        metrics['filesystem/' + label + '_available_inodes'] = fs.f_favail
    return dict(job=job, node=socket.gethostname().split('.')[0], gpu=gpu,
        observed_at=time.time(), available=True, metrics=metrics, processes=counters,
        power_scope='whole physical GPU; not exclusive model energy')


def rates(previous, current):
    result = {}
    if not previous or not previous.get('available') or not current.get('available'):
        return result
    elapsed = current['observed_at'] - previous['observed_at']
    if elapsed <= 0 or current['gpu'] != previous['gpu']:
        return result
    old = {(p['pid'], p['start_ticks']): p for p in previous['processes']}
    matched = [(old[(p['pid'], p['start_ticks'])], p) for p in current['processes']
        if (p['pid'], p['start_ticks']) in old]
    for key, name, scale in [('cpu_seconds', 'process/main_cpu_percent', 100),
            ('read_bytes', 'io/main_read_bytes_per_second', 1),
            ('write_bytes', 'io/main_write_bytes_per_second', 1),
            ('major_faults', 'io/main_major_faults_per_second', 1)]:
        if matched and all(key in a and key in b and b[key] >= a[key] for a, b in matched):
            result[name] = math.fsum(b[key] - a[key] for a, b in matched) / elapsed * scale
    power1 = previous['metrics'].get('gpu/power_watts')
    power2 = current['metrics'].get('gpu/power_watts')
    if power1 is not None and power2 is not None and elapsed <= 90:
        result['gpu/observed_interval_energy_joules'] = (power1 + power2) * .5 * elapsed
        result['gpu/observed_interval_seconds'] = elapsed
    return result


def remote_collect(entry):
    node, gpu, job = entry['node'], entry['gpu'], entry['job']
    if not re.fullmatch(r'compute-0-\d+', node) or not re.fullmatch(r'GPU-[0-9a-fA-F-]+', gpu) or type(job) is not int:
        raise ValueError('Diagnostics require the recorded real node, job and GPU UUID')
    if socket.gethostname().split('.')[0] == node:
        return collect(job, gpu)
    command = ['/usr/bin/python3', '-B', str(Path(__file__).absolute()), '--collect-job', str(job), '--gpu', gpu]
    output = subprocess.run(['ssh', '-n', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', node,
        shlex.join(command)], capture_output=True, text=True, check=True, timeout=25)
    result = json.loads(output.stdout)
    if result.get('node') != node or result.get('job') != job or result.get('gpu') != gpu:
        raise ValueError('Remote telemetry identity differs from registered training')
    return result


def worker(manifest_path, job):
    manifest = json.loads(manifest_path.read_text())
    entry = next(r for r in manifest['runs'] if r['job'] == job)
    directory = Path(manifest['tracking_root']) / 'diagnostics' / str(job)
    directory.mkdir(parents=True, exist_ok=True)
    for variable, child in [('WANDB_DIR', '.'), ('WANDB_CACHE_DIR', 'cache'), ('WANDB_DATA_DIR', 'data'), ('TMPDIR', 'tmp')]:
        destination = directory / child
        destination.mkdir(exist_ok=True)
        os.environ[variable] = str(destination)
    os.environ['WANDB_CONSOLE'] = 'off'
    status_path = directory / 'status.json'
    saved = json.loads(status_path.read_text()) if status_path.exists() else {}
    if saved.get('finished'):
        return
    import wandb
    mode = manifest.get('mode', 'offline')
    kwargs = dict(project=manifest['project'], entity=manifest.get('entity'), id='m3-' + str(job) + '-diagnostics',
        name=entry['name'] + '-job' + str(job) + '-diagnostics', group=entry['group'],
        job_type='training-system-and-loss-windows', dir=str(directory), mode=mode,
        config=dict(training_job=job, training_wandb_run='m3-' + str(job), node=entry['node'],
            gpu_uuid=entry['gpu'], source_revision=entry['source_revision'], sample_seconds=30,
            loss_window_updates=1000, power_scope='whole GPU', historical_system_metrics=False))
    if mode == 'online':
        kwargs['resume'] = 'allow'
    try:
        run = wandb.init(**kwargs)
    except Exception:
        if mode == 'offline':
            raise
        mode = 'offline'
        kwargs.update(mode=mode)
        kwargs.pop('resume', None)
        run = wandb.init(**kwargs)
    if run is None or run.disabled:
        raise RuntimeError('Diagnostics require a real persistent W&B run')
    run.define_metric('loss_1000_updates/*', step_metric='samples/cumulative')
    for namespace in ['gpu', 'process', 'io', 'node', 'filesystem', 'throughput']:
        run.define_metric(namespace + '/*', step_metric='time/observed_unix_seconds')
    tail, windows = CsvTail(Path(entry['output']) / 'losses.csv'), UpdateMeans()
    attachment_bytes = tail.path.stat().st_size if tail.path.exists() else 0
    latest_window, previous, previous_samples = None, None, None
    last_window = int(saved.get('last_window_update', 0))
    samples = int(entry.get('initial_samples', 0))
    state = dict(job=job, run_id=run.id, mode=mode, url=run.url if mode == 'online' else None,
        finished=False, last_window_update=last_window, synchronization='OFFLINE_UNSYNCED' if mode == 'offline' else 'ONLINE_UPLOAD_REQUESTED')
    while True:
        for row in tail.rows():
            row['_imported'] = tail.offset <= attachment_bytes
            samples = row['samples']
            window = windows.add(row)
            if window is None:
                continue
            latest_window = window
            if window['last_update'] <= last_window:
                continue
            payload = {'samples/cumulative': samples, 'window/first_update': window['first_update'],
                'window/last_update': window['last_update'], 'window/updates': window['updates'],
                'window/imported_record_count': window['imported_records']}
            payload.update({'loss_1000_updates/' + k: v for k, v in window['means'].items()})
            payload.update({'loss_1000_updates_count/' + k: v for k, v in window['counts'].items()})
            run.log(payload, commit=True)
            with (directory / 'loss_windows.jsonl').open('a') as stream:
                stream.write(json.dumps(window, allow_nan=False) + '\n')
            last_window = window['last_update']
        current_entry = next(r for r in json.loads(manifest_path.read_text())['runs'] if r['job'] == job)
        actual_state = job_state(current_entry)
        if actual_state not in TERMINAL:
            try:
                observation = remote_collect(entry)
                payload = dict(observation['metrics'])
                payload.update(rates(previous, observation))
                payload.update({'samples/cumulative': samples, 'time/observed_unix_seconds': observation['observed_at']})
                if previous_samples is not None and previous and observation['observed_at'] > previous['observed_at']:
                    payload['throughput/samples_per_second_window'] = (samples - previous_samples) / (observation['observed_at'] - previous['observed_at'])
                run.log(payload, commit=True)
                observation['metrics'] = payload
            except Exception as exc:
                observation = dict(job=job, node=entry['node'], gpu=entry['gpu'], available=False,
                    observed_at=time.time(), error_type=type(exc).__name__, metrics={}, processes=[])
                run.log({'observer/available': 0, 'samples/cumulative': samples,
                    'time/observed_unix_seconds': observation['observed_at']}, commit=True)
            with (directory / 'system_metrics.jsonl').open('a') as stream:
                stream.write(json.dumps(observation, allow_nan=False) + '\n')
            save(directory / 'latest.json', dict(**observation, wandb_run_id=run.id, wandb_url=state['url'],
                synchronization=state['synchronization'], last_completed_loss_window=latest_window))
            previous, previous_samples = observation, samples
        state.update(last_window_update=last_window, last_samples=samples, slurm_state=actual_state, observed_at=time.time())
        if actual_state in TERMINAL:
            partial = windows.summary()
            if partial:
                save(directory / 'partial_loss_window.json', partial)
            run.summary['slurm_state'] = actual_state
            run.summary['last_samples'] = samples
            run.finish(exit_code=0 if actual_state == 'COMPLETED' else 1)
            state['finished'] = True
        save(status_path, state)
        if state['finished']:
            return
        time.sleep(30)


def supervise(manifest_path):
    children = {}
    while True:
        manifest = json.loads(manifest_path.read_text())
        root = Path(manifest['tracking_root']) / 'diagnostics'
        root.mkdir(parents=True, exist_ok=True)
        for entry in manifest['runs']:
            job = entry['job']
            status = root / str(job) / 'status.json'
            if status.exists() and json.loads(status.read_text()).get('finished'):
                continue
            if job in children and children[job].poll() is None:
                continue
            with (root / ('worker_' + str(job) + '.log')).open('a') as log:
                children[job] = subprocess.Popen([sys.executable, '-B', __file__, '--manifest', str(manifest_path),
                    '--job', str(job)], stdout=log, stderr=subprocess.STDOUT)
        time.sleep(15)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path)
    parser.add_argument('--job', type=int)
    parser.add_argument('--collect-job', type=int)
    parser.add_argument('--gpu')
    args = parser.parse_args()
    if args.collect_job:
        print(json.dumps(collect(args.collect_job, args.gpu), allow_nan=False))
    elif not args.manifest:
        parser.error('The actual training manifest is required')
    elif args.job:
        worker(args.manifest, args.job)
    else:
        supervise(args.manifest)


if __name__ == '__main__':
    main()
