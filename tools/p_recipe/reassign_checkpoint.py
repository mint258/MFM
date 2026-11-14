"""Move an observed slow job at an existing complete checkpoint boundary.

For an already loaded worker without a save/exit request path, pause only after
its normal atomic checkpoint publication. Proceed only while its last committed
CSV cursor still equals that checkpoint; otherwise continue the original job.
No checkpoint is reopened or hashed by this scheduling tool.
"""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import shlex
import signal
import socket
import subprocess
import time

from execution_ledger import C, locked_ledger, read, write
from launch_plan import REPO, NATIVE, observe, own_gpu_busy
from native_run import identity
from scheduling import gpu_rank, requested_cpus, route


def last_rows(output, count=128):
    path = Path(output) / 'losses.csv'
    with path.open('rb') as stream:
        stream.seek(max(0, path.stat().st_size - 65536))
        data = stream.read().decode()
    lines = data.splitlines()
    values = []
    for row in csv.reader(io.StringIO('\n'.join(lines))):
        if len(row) == 6 and row[0].isdigit():
            values.append(dict(samples=int(row[0]), seconds=float(row[-1])))
    return values[-count:]


def bound_identity(source):
    bound = {key: source[key] for key in ('pid', 'uid', 'start_ticks', 'pgid')}
    if bound['uid'] != os.getuid() or identity(bound['pid']) != bound:
        raise RuntimeError('Source identity changed; no signal sent')
    return bound


def process_state(pid):
    return Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()[0]


def resume_source(source, terminating=False):
    bound = bound_identity(source)
    guard_path = source.get('_guard_path')
    if not terminating and guard_path and read(guard_path).get('status') == 'DISK_PAUSED':
        source['_paused_by_controller'] = False
        return
    os.killpg(bound['pgid'], signal.SIGCONT)
    source['_paused_by_controller'] = False


def pause_at_checkpoint(configuration, source, point, poll_seconds=.25):
    checkpoint = Path(configuration['output']) / f'samples_{point}.pt'
    while not checkpoint.is_file():
        bound_identity(source)
        time.sleep(poll_seconds)
    bound = bound_identity(source)
    if process_state(bound['pid']) == 'T':
        return None  # Preserve a storage guard's existing pause.
    source['_paused_by_controller'] = True
    os.killpg(bound['pgid'], signal.SIGSTOP)
    try:
        observed = last_rows(configuration['output'])
        if observed[-1]['samples'] == point:
            return checkpoint, observed
    except BaseException:
        resume_source(source)
        raise
    resume_source(source)
    return None


def choose_destination(configuration, benchmark):
    policy = read(REPO / 'configs/p_recipe/scheduling.json')
    cpus = requested_cpus(configuration, policy)
    candidates = []
    for node in NATIVE:
        for card in observe(node):
            gpu = card['gpu_uuid']
            if gpu in benchmark and not own_gpu_busy(gpu) and route(card['free_cpus'], cpus,
                    card['used_mib'], card['total_mib'], policy) != 'WAIT_GPU':
                candidates.append(card)
    candidates.sort(key=lambda card: (gpu_rank(card['gpu_name'], policy), -benchmark[card['gpu_uuid']]))
    return candidates[0] if candidates else None


def on_login(host, command):
    return ['ssh', '-n', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', host, shlex.join(command)]


def wait_terminal(job, host):
    for _ in range(120):
        text = subprocess.check_output(on_login(host, ['sacct', '-X', '-n', '-P', '-j', str(job),
                                        '--format=JobIDRaw,State,ExitCode']), text=True, timeout=15)
        for row in csv.reader(text.splitlines(), delimiter='|'):
            if row and row[0] == str(job) and row[1].split()[0].rstrip('+') in {
                    'CANCELLED', 'COMPLETED', 'FAILED', 'TIMEOUT', 'NODE_FAIL', 'OUT_OF_MEMORY'}:
                return dict(job_id=job, state=row[1], exit_code=row[2])
        time.sleep(1)
    raise RuntimeError('Cancellation observation is incomplete; inspect the same source handle')


def run(control):
    configuration = read(control['configuration'])
    source = read(control['source_state'])
    source['_guard_path'] = control['source_state']
    if socket.gethostname().split('.')[0] != source['node']:
        raise RuntimeError('Run this controller on the actual source node')
    if configuration['run'] != source['run']:
        raise RuntimeError('Canonical configuration no longer identifies the source')
    if source['job_id'] != control['source_job_id']:
        raise RuntimeError('The source guard does not belong to the requested Slurm job')
    bound_identity(source)
    status_path = Path(control['status'])
    status = dict(phase='WAITING_FOR_CHECKPOINT', source_run=configuration['run'],
                  source_job_id=control['source_job_id'], controller=identity(os.getpid()))
    write(status_path, status)
    paused = False
    stopping = False
    try:
        initial = last_rows(configuration['output'])[-1]['samples']
        for point in configuration['checkpoint_samples']:
            if not initial < point < configuration['samples']:
                continue
            result = pause_at_checkpoint(configuration, source, point)
            if result is None:
                continue
            paused = True
            checkpoint, observed = result
            first, last = observed[0], observed[-1]
            recent = (last['samples'] - first['samples']) / (last['seconds'] - first['seconds'])
            destination = choose_destination(configuration, control['benchmark_sps_by_uuid'])
            if destination is None or recent * 1.25 >= control['benchmark_sps_by_uuid'][destination['gpu_uuid']]:
                status.update(phase='ORIGINAL_CONTINUES', point=point, source_recent_sps=recent,
                              reason='No eligible destination with a measured operating-rate advantage')
                write(status_path, status)
                return
            bound = bound_identity(source)
            if process_state(bound['pid']) != 'T' or last_rows(configuration['output'])[-1]['samples'] != point:
                raise RuntimeError('Source advanced before cancellation; original will continue')
            name = configuration['run'] + '_reassigned'
            new = dict(configuration, run=name, output=str(Path(configuration['output']).parent / name),
                       attempt=configuration.get('attempt', 1) + 1, resume=str(checkpoint), resume_samples=point,
                       resume_from_output=configuration['output'], required_gpu_uuid=destination['gpu_uuid'])
            # Fresh cooperative control paths are available in the new worker.
            new['handoff_request'] = str(C / (name + '_handoff_request.json'))
            new['handoff_ack'] = str(C / (name + '_handoff_ack.json'))
            if Path(new['output']).exists():
                raise RuntimeError('Replacement output already exists; inspect its existing handle')
            snapshot = C / (configuration['run'] + '_before_reassignment_configuration.json')
            prepared = C / (name + '_prepared_configuration.json')
            write(snapshot, configuration)
            write(prepared, new)
            status.update(phase='STOPPING_AT_COMPLETE_CHECKPOINT', point=point,
                          checkpoint=str(checkpoint), source_recent_sps=recent, destination=destination,
                          prepared_configuration=str(prepared))
            write(status_path, status)
            # Queue TERM while stopped, before Slurm's cancellation sends CONT.
            # The old worker cannot commit another update between CONT and TERM.
            stopping = True
            os.killpg(bound['pgid'], signal.SIGTERM)
            subprocess.run(on_login(control['slurm_login'], ['scancel', str(control['source_job_id'])]), check=True, timeout=15)
            terminal = wait_terminal(control['source_job_id'], control['slurm_login'])
            paused = False
            with locked_ledger() as ledger:
                record = ledger['runs'][configuration['run']]
                record.update(configuration=str(snapshot), end_reason='checkpoint_gpu_reassignment',
                              state=terminal['state'].split()[0].rstrip('+'), checkpoint_resume_samples=point)
                write(control['configuration'], new)
                plan = read(control['plan'])
                sizes = plan.setdefault('batch_size_by_run', {})
                sizes.pop(configuration['run'], None)
                sizes[name] = new['batch_size']
                write(control['plan'], plan)
            # Official admission, quota guards and normal/hybrid routing apply.
            subprocess.run(on_login(control['slurm_login'], [control['python'], '-B',
                           str(REPO / 'tools/p_recipe/launch_plan.py'), '--plan', control['plan']]),
                           check=True, timeout=90)
            status.update(phase='REPLACEMENT_SUBMITTED', new_run=name, source_terminal=terminal,
                          completed_at=time.time())
            write(status_path, status)
            return
        status.update(phase='ORIGINAL_CONTINUES', reason='No unused complete boundary remained')
        write(status_path, status)
    except BaseException as error:
        status.update(phase='ERROR_AFTER_STOP' if stopping else 'ERROR_BEFORE_STOP',
                      error=repr(error), observed_at=time.time())
        write(status_path, status)
        raise
    finally:
        if source.get('_paused_by_controller') and identity(source['pid']) == {key: source[key] for key in ('pid', 'uid', 'start_ticks', 'pgid')}:
            # Before stopping this resumes the unchanged original. After TERM
            # it lets the pending termination complete if scancel was interrupted.
            resume_source(source, terminating=stopping)


if __name__ == '__main__':
    def interrupt(signum, frame):
        raise SystemExit(128 + signum)
    signal.signal(signal.SIGTERM, interrupt)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', required=True)
    args = parser.parse_args()
    run(read(args.control))
