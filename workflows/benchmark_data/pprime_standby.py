"""Reserve replacement CPUs without touching the live scientific producer."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import time


def native_job(job, expires=None):
    while True:
        if expires is not None and time.monotonic() >= expires:
            raise TimeoutError('Standby metadata reservation window expired')
        try:
            raw = subprocess.check_output(['scontrol', 'show', 'job', str(int(job)), '-o'],
                                          text=True, timeout=30)
            break
        except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            print('STANDBY_NATIVE_OBSERVATION_WAIT_ZERO_NATIVE', job, repr(exc), flush=True)
            time.sleep(5)
    fields = dict(re.findall(r'\b([A-Za-z][A-Za-z0-9/]*)=([^\s]+)', raw))
    if fields.get('JobId') != str(job):
        raise ValueError('Native job identity differs')
    return fields


def remaining_wall(job, now):
    # scontrol and datetime use the same local timezone on this actual node.
    end = datetime.fromisoformat(job['EndTime']).timestamp()
    return max(0, int(end - now) - 60)


def validate_acceptance(actual, identity):
    for key in ('job', 'previous_job', 'node', 'uid', 'pid', 'start_ticks', 'root', 'workers'):
        if actual.get(key) != identity[key]:
            raise ValueError('Standby acceptance identity differs: ' + key)
    if actual.get('previous_parent_sigterm_verified') is not True:
        raise ValueError('Root has not recorded the verified graceful-stop signal')
    if actual.get('followup_requires_both_jobs') is not True:
        raise ValueError('Fallback dependency has not been protected')


def previous_closed(previous, access, report, job):
    if previous['JobState'] in {'PENDING', 'CONFIGURING', 'RUNNING', 'COMPLETING'}:
        return False
    if previous['JobState'] != 'COMPLETED' or previous.get('ExitCode') != '0:0':
        raise ValueError('Previous producer is not native COMPLETED/0:0')
    if str(access.get('producer_job')) != str(job):
        raise ValueError('Shared producer identity changed; never compete with it')
    if not access.get('writers_closed') or report is None:
        return False
    if str(report.get('job')) != str(job) or report['states'].get('INTENT', 0):
        raise ValueError('Previous producer identity/INTENT is not closed')
    return True


def read_acceptance(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd) as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Unexpected acceptance owner/type')
        return json.load(stream)


def main():
    from .pprime_tmpfs_queue import capacity
    from .shared_access import completed_evidence
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--quota-snapshot', type=Path, required=True)
    parser.add_argument('--previous-job', required=True, type=int)
    parser.add_argument('--workers', type=int, default=16)
    args = parser.parse_args()
    job = str(int(os.environ['SLURM_JOB_ID']))
    node = socket.gethostname().split('.')[0]
    started = time.monotonic()
    try:
        own = native_job(job, expires=started + 300)
    except TimeoutError:
        print('STANDBY_RELEASED_ZERO_NATIVE', job, flush=True)
        return
    if (node not in {'compute-0-' + str(i) for i in range(8, 20)}
            or own.get('NodeList') != node or own.get('Partition') != 'cpu'
            or own.get('JobState') != 'RUNNING'
            or '(' + str(os.getuid()) + ')' not in own.get('UserId', '')
            or int(own.get('CPUs/Task', '0')) < args.workers
            or int(own.get('NumCPUs', '0')) < args.workers):
        raise ValueError('Actual authorized CPU allocation is not established')
    identity = {'job': job, 'previous_job': str(args.previous_job), 'node': node,
                'uid': os.getuid(), 'pid': os.getpid(), 'workers': args.workers,
                'start_ticks': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19],
                'root': str(args.root.resolve())}
    accept_path = args.control / ('B0_pprime_standby_' + job + '_accept.json')
    ready = accepted = False
    last_phase = None
    while True:
        try:
            own = native_job(job, expires=None if accepted else started + 300)
        except TimeoutError:
            print('STANDBY_RELEASED_ZERO_NATIVE', job, flush=True)
            return
        wall = remaining_wall(own, time.time())
        if wall <= 11100 or (not accepted and time.monotonic() - started >= 300):
            print('STANDBY_RELEASED_ZERO_NATIVE', job, flush=True)
            return
        try:
            capacity(args.root, args.quota_snapshot, workers=args.workers, scratch='/dev/shm')
        except (OSError, ValueError, KeyError, RuntimeError) as exc:
            if last_phase != 'CAPACITY_WAIT':
                print('STANDBY_CAPACITY_WAIT_ZERO_NATIVE', repr(exc), flush=True)
            last_phase = 'CAPACITY_WAIT'
            time.sleep(5)
            continue
        if not ready:
            print('STANDBY_READY_ZERO_NATIVE', json.dumps(identity), flush=True)
            ready = True
        if not accepted:
            try:
                acceptance = read_acceptance(accept_path)
            except FileNotFoundError:
                time.sleep(5)
                continue
            validate_acceptance(acceptance, identity)
            accepted = True
            print('STANDBY_ROOT_ACCEPTED_ZERO_NATIVE', job, flush=True)
        previous = native_job(args.previous_job)
        access = json.loads((args.root / 'labels/Pprime/shared_v1/access.json').read_text())
        report_path = args.root / 'labels/Pprime/shared_v1' / ('producer_' + str(args.previous_job) + '.json')
        report = json.loads(report_path.read_text()) if report_path.is_file() else None
        if not previous_closed(previous, access, report, args.previous_job):
            if last_phase != 'PREVIOUS_WAIT':
                print('STANDBY_WAIT_NATIVE_C0_ZERO_NATIVE', args.previous_job, flush=True)
            last_phase = 'PREVIOUS_WAIT'
            time.sleep(5)
            continue
        completed_evidence(str(args.previous_job))
        try:
            capacity(args.root, args.quota_snapshot, workers=args.workers, scratch='/dev/shm')
        except (OSError, ValueError, KeyError, RuntimeError):
            time.sleep(5)
            continue
        wall = remaining_wall(native_job(job), time.time())
        if wall <= 11100:
            print('STANDBY_RELEASED_ZERO_NATIVE', job, flush=True)
            return
        command = [sys.executable, '-B', '-u', '-m', 'workflows.benchmark_data.pprime_tmpfs_queue',
                   'run', '--root', str(args.root), '--workers', str(args.workers),
                   '--quota-snapshot', str(args.quota_snapshot), '--wall-seconds', str(wall)]
        print('STANDBY_EXEC_ORIGINAL_PRODUCER_AFTER_NATIVE_C0', json.dumps(command), flush=True)
        os.execv(sys.executable, command)


if __name__ == '__main__':
    main()
