"""S-owned storage admission and guarded native/Slurm execution."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

ROOT = Path('/share/home/zixiao/descriptor_analysis')
REPO = ROOT/'MFM_s_recipe'
CONTROL = ROOT/'runs/s_recipe_20261120'
TOTAL_PEAK = 64*1024**3
# D stage0 has one shared14GiB NFS claim (2026-11-20 STATUS); do not
# let simultaneous producers spend the same headroom. Keep this until closed.
D_STAGE0_PEAK = 14*1024**3
spec = importlib.util.spec_from_file_location('s_disk', REPO/'tools/model_v3/v2_diagnosis_disk.py')
disk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(disk)


def write(path, value):
    path = Path(path)
    pending = path.with_name(path.name+'.next.'+str(os.getpid()))
    pending.write_text(json.dumps(value, indent=2)+'\n')
    pending.replace(path)


def remaining():
    # S files only: the source data and every other line stay outside this walk.
    allocated = 0
    seen = set()
    for path in CONTROL.rglob('*'):
        try:
            stat = path.lstat()
        except FileNotFoundError:
            continue
        if path.is_symlink() or not path.is_file():
            continue
        key = (stat.st_dev, stat.st_ino)
        if key not in seen:
            allocated += stat.st_blocks*512
            seen.add(key)
    if allocated > TOTAL_PEAK:
        raise OSError('S-owned outputs exceed the announced64GiB peak')
    return max(64*1024**2, TOTAL_PEAK-allocated)


def capacity():
    future = remaining()
    disk.m.require_capacity(disk.m.filesystem_status('/'), 16*1024**2, 1000)
    disk.m.require_capacity(disk.m.filesystem_status(CONTROL), future, 20000)
    return disk.m.quota_headroom(disk.CONTROL/'share_quota_available_v3.json', '/share',
                                future, disk.remaining_nfs_other()+D_STAGE0_PEAK)


def identity(pid):
    path = Path('/proc')/str(pid)
    fields = (path/'stat').read_text().rsplit(')', 1)[1].split()
    return dict(pid=pid, uid=path.stat().st_uid, start_ticks=int(fields[19]), pgid=os.getpgid(pid))


def run(c):
    node = socket.gethostname().split('.')[0]
    gpu = c.get('gpu_uuid')
    if node != c['node'] or node == 'compute-0-21':
        raise ValueError('Wrong or prohibited execution node')
    mode = c.get('mode', 'Slurm')
    if mode == 'native_with_standby' and node not in ('compute-0-20', 'compute-0-22'):
        raise ValueError('Native GPU execution is limited to20/22')
    if mode == 'Slurm' and not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Missing real Slurm allocation')
    lock = None
    if gpu:
        import csv
        rows = csv.reader(subprocess.check_output(['nvidia-smi', '--query-gpu=uuid,memory.used,memory.total',
                                                   '--format=csv,noheader,nounits'], text=True).splitlines())
        card = next(row for row in rows if row[0].strip() == gpu)
        used, total = map(float, card[1:])
        if used/total > .30 or total-used < c['minimum_free_gpu_mib']:
            raise RuntimeError('Actual UUID memory admission is no longer available')
        contexts = subprocess.check_output(['nvidia-smi', '--query-compute-apps=gpu_uuid',
                                           '--format=csv,noheader,nounits'], text=True).splitlines()
        if node not in ('compute-0-20', 'compute-0-22') and gpu in [v.strip() for v in contexts]:
            raise RuntimeError('Small-group GPU has an existing compute context')
        lock = (ROOT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(gpu+'.lock')).open('a')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    capacity()
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES=gpu or '', PYTHONDONTWRITEBYTECODE='1',
        OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1', NUMEXPR_NUM_THREADS='1',
        PYTHONPATH=':'.join(map(str, (REPO/'current', REPO/'tools/s_recipe',
            ROOT/'runs/data_v1_20261025/repository',
            ROOT/'docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps'))))
    if mode == 'native_with_standby':
        for key in list(environment):
            if key.startswith('SLURM_'):
                environment.pop(key)
    child = subprocess.Popen(c['command'], cwd=REPO, env=environment, start_new_session=True)
    bound = identity(child.pid)
    state = dict(run=c['run'], node=node, gpu_uuid=gpu, mode=mode, started_at=time.time(),
                 job_id=os.environ.get('SLURM_JOB_ID') if mode == 'Slurm' else None, **bound)
    paused = False
    while child.poll() is None:
        try:
            capacity()
            ok, reason = True, None
        except (OSError, ValueError, KeyError, TypeError) as error:
            ok, reason = False, str(error)
        if paused == ok and child.poll() is None:
            try:
                if identity(child.pid) != bound:
                    raise RuntimeError('Own process identity changed')
                os.killpg(bound['pgid'], signal.SIGCONT if ok else signal.SIGSTOP)
                paused = not ok
            except ProcessLookupError:
                pass
        state.update(status='RUNNING' if ok else 'DISK_PAUSED', disk_reason=reason)
        write(c['state_path'], state)
        time.sleep(5)
    code = child.wait()
    state.update(status='COMPLETED' if code == 0 else 'FAILED', exit_code=code,
                 ended_at=time.time(), elapsed_seconds=time.time()-state['started_at'])
    write(c['state_path'], state)
    return code


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--configuration', required=True)
    raise SystemExit(run(json.loads(Path(p.parse_args().configuration).read_text())))
