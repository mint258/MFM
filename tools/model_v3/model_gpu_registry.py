"""Admit only live, registered same-UID model processes on a physical GPU."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import runpy
import signal
import socket
import stat
import subprocess
import sys
import threading
import time

from runtime_monitor import capture_process_identity

BASE = Path('/share/home/zixiao/descriptor_analysis')
LOCKS = BASE / 'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'
REGISTRY = LOCKS / 'registered_models'
PERF = Path('/lfshome/zixiao/model_v3_perf_20261112')
IDENTITY = ('pid', 'uid', 'boot_id', 'start_ticks', 'pgid', 'sid', 'argv_sha256', 'cgroup', 'slurm_job_id')


def metadata_capacity():
    from v2_watch_disk import filesystem_status, require_capacity
    for path in (Path('/'), LOCKS):
        require_capacity(filesystem_status(path), 1024**2, 16)
    path = BASE / 'runs/data_v1_20261025/control/window2_20261105/share_quota_available_v3.json'
    value = json.loads(path.read_text())
    if (value.get('schema') != 'XFS_USER_QUOTA_AVAILABLE_V1' or value.get('uid') != os.getuid()
            or value.get('filesystem') != '/share' or not 0 <= time.time()-value['observed_time'] <= 5
            or value['available_bytes'] < 100_000_000_000+23_179_869_184+8*1024**3+1024**2):
        raise OSError('Fresh account headroom including concurrent NFS forecast is required')


def validate_output(output, *, benchmark=False):
    output = Path(output).resolve()
    if benchmark:
        root = PERF / ('concurrency_'+os.environ['SLURM_JOB_ID'])
        if not output.is_relative_to(root) or output == root:
            raise ValueError('Benchmark registration must use this job\'s independent scratch')
    else:
        from v2_run_development import require_registered_output, REGISTRY as outputs
        require_registered_output(output, json.loads(outputs.read_text()))
    return str(output)


def matches(record, current, gpu, *, uid=None, host=None):
    uid = os.getuid() if uid is None else uid
    host = socket.gethostname() if host is None else host
    common = (record.get('schema') == 'MODEL_GPU_PROCESS_V1' and record.get('gpu') == gpu
              and record.get('host') == host and record.get('uid') == uid and current.get('uid') == uid)
    if current.get('status') == 'EXITING':
        # CUDA may retain a context while an already registered process exits.
        # Only its exact kernel lifetime is exempt; stale/PID-reused records fail.
        return (common and record.get('pid') == current.get('pid')
                and record.get('start_ticks') == current.get('start_ticks')
                and record.get('boot_id') == Path('/proc/sys/kernel/random/boot_id').read_text().strip())
    return (common and current.get('status') == 'ACTIVE'
            and all(record.get(key) == current.get(key) for key in IDENTITY))


def registered_model_pids(gpu):
    admitted = set()
    directory = REGISTRY / gpu
    if not directory.exists():
        return admitted
    for path in directory.glob(socket.gethostname()+'_*_*.json'):
        try:
            info = path.lstat()
            if info.st_uid != os.getuid() or not stat.S_ISREG(info.st_mode) or info.st_size > 65536:
                continue
            record = json.loads(path.read_text())
            current = capture_process_identity(record['pid'], expected_job=record['slurm_job_id'])
            if matches(record, current, gpu):
                admitted.add(record['pid'])
        except (OSError, ValueError, KeyError):
            continue
    return admitted


def compute_pids(gpu):
    text = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid,pid',
        '--format=csv,noheader,nounits'], text=True, stdin=subprocess.DEVNULL, timeout=15)
    return {int(row.split(',')[1]) for row in text.splitlines() if row.split(',')[0].strip() == gpu}


def require_only_registered(gpu, *, own_pids=()):
    foreign = compute_pids(gpu) - registered_model_pids(gpu) - set(own_pids)
    if foreign:
        raise RuntimeError(f'Unregistered or foreign GPU contexts: {sorted(foreign)}')


def register_current(gpu, output, *, benchmark=False):
    if not re.fullmatch(r'GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', gpu):
        raise ValueError('One complete physical GPU UUID is required')
    output = validate_output(output, benchmark=benchmark)
    current = capture_process_identity(os.getpid())
    if current.get('status') != 'ACTIVE':
        raise RuntimeError('Actual same-UID Slurm process identity is required')
    value = dict(current, schema='MODEL_GPU_PROCESS_V1', gpu=gpu,
                 host=socket.gethostname(), output=output, benchmark=benchmark)
    metadata_capacity()
    directory = REGISTRY / gpu
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'{value["host"]}_{value["pid"]}_{value["start_ticks"]}.json'
    with path.open('x') as file:
        file.write(json.dumps(value, indent=2)+'\n')
    return value


@contextmanager
def shared_model_gpu(gpu, output):
    metadata_capacity()
    # NFS maps flock(LOCK_SH) to a read lock, so the descriptor must be readable.
    with (LOCKS/(gpu+'.lock')).open('a+') as shared:
        # Existing launchers retain their exclusive locks. They cannot be joined.
        fcntl.flock(shared, fcntl.LOCK_SH | fcntl.LOCK_NB)
        with (LOCKS/(gpu+'.admission.lock')).open('a') as admission:
            fcntl.flock(admission, fcntl.LOCK_EX)
            require_only_registered(gpu)
            register_current(gpu, output)
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gpu', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('program', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    program = args.program[1:] if args.program[:1] == ['--'] else args.program
    if (not re.fullmatch(r'GPU-[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}', args.gpu)
            or not program or os.environ.get('CUDA_VISIBLE_DEVICES') != args.gpu):
        raise ValueError('Bind the original Python program to exactly one GPU UUID')
    done = threading.Event()

    def watch():
        while not done.wait(5):
            try:
                require_only_registered(args.gpu)
            except Exception as error:
                print(f'GPU protection: {error}; stopping only this model process', file=sys.stderr, flush=True)
                os.kill(os.getpid(), signal.SIGTERM)
                return

    with shared_model_gpu(args.gpu, args.output):
        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        try:
            sys.argv = program
            runpy.run_path(program[0], run_name='__main__')
        finally:
            done.set()
            watcher.join(timeout=16)


if __name__ == '__main__':
    main()
