"""Opt-in finite Slurm entry for subsequent S launches and safe resumes.

Training only. Registered readouts remain separate work after the endpoint;
an interrupted run is never presented as a completed scientific result.
"""
import argparse
import csv
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import threading
import time

import lifecycle_20261122 as life
from runtime import CONTROL, ROOT, capacity, write


def query_gpu(uuid):
    child = subprocess.Popen(['nvidia-smi', '--id='+uuid,
        '--query-gpu=uuid,name,memory.used,memory.total,power.draw,utilization.gpu',
        '--format=csv,noheader,nounits'], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True)
    saved = life.identity(child.pid)
    try:
        stdout, stderr = child.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        if saved is not None:
            life.terminate_once(saved)
        # No timeout-based KILL. Final owned-child cleanup verifies exit.
        raise RuntimeError('GPU metadata observation did not finish; stop new work')
    if child.returncode:
        raise RuntimeError('GPU metadata observation failed: '+stderr)
    rows = list(csv.reader(stdout.splitlines()))
    if len(rows) != 1 or rows[0][0].strip() != uuid:
        raise ValueError('GPU metadata does not match the allocated UUID')
    return [field.strip() for field in rows[0]]


def observe(c, guard, stop):
    output = Path(c['output'])
    while not stop.wait(30):
        try:
            capacity()
            card = query_gpu(c['gpu_uuid'])
            path = output/'gpu_telemetry.csv'
            if not output.is_dir():
                continue
            with (output/'losses.csv').open('rb') as stream:
                stream.seek(max(0, stream.seek(0, 2)-8192))
                rows = list(csv.reader(stream.read().decode().splitlines()))
            row = next(row for row in reversed(rows) if len(row) == 9 and row[0].isdigit())
            exists = path.exists()
            with path.open('a', newline='') as stream:
                writer = csv.writer(stream)
                if not exists:
                    writer.writerow(['timestamp', 'samples', 'training_seconds', 'gpu_uuid',
                        'gpu_name', 'whole_card_power_watts', 'utilization_percent', 'memory_used_mib'])
                writer.writerow([time.time(), row[0], row[-1], card[0], card[1],
                                 card[4], card[5], card[2]])
        except FileNotFoundError:
            # The model/data entry may still be preparing its first output.
            continue
        except Exception as error:
            guard.request('storage_or_observer_failure: '+str(error))
            print('S_GUARDED_OBSERVER '+str(error), flush=True)
            return


def run(c, *, scheduler_record):
    from dispatch import gate, authorized
    blocked = gate()
    if blocked:
        raise RuntimeError(blocked)
    authorized(c)
    if socket.gethostname().split('.')[0] != c['node'] or c['node'] == 'compute-0-21':
        raise ValueError('Wrong or prohibited execution node')
    if os.environ.get('CUDA_VISIBLE_DEVICES') != c['gpu_uuid']:
        raise ValueError('The entry must bind exactly the admitted GPU UUID')
    guard = life.Guard.from_slurm(900, scheduler_record=scheduler_record)
    life.enable_subreaper()
    lockpath = ROOT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(c['gpu_uuid']+'.lock')
    with lockpath.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        card = query_gpu(c['gpu_uuid'])
        used, total = float(card[2]), float(card[3])
        if used/total > .30 or total-used < c['minimum_free_gpu_mib']:
            raise RuntimeError('Actual GPU memory admission is no longer available')
        capacity()
        statepath = CONTROL/(c['run']+'_guarded_'+os.environ['SLURM_JOB_ID']+'.json')
        state = dict(run=c['run'], job_id=int(os.environ['SLURM_JOB_ID']),
            node=c['node'], gpu_uuid=c['gpu_uuid'], producer=vars(life.identity(os.getpid())),
            started_at=time.time(), actual_deadline_epoch=guard.end_epoch,
            deadline_basis=guard.deadline_basis, closing_reserve_seconds=900,
            allocator=os.environ.get('PYTORCH_CUDA_ALLOC_CONF'), status='TRAINING',
            resume=c.get('resume'), gpu_metadata_at_start=card)
        write(statepath, state)
        stop = threading.Event()
        observer = threading.Thread(target=observe, args=(c, guard, stop), daemon=False)
        with guard:
            observer.start()
            try:
                from s_training_lifecycle_20261122 import train
                result = train(c)
                state.update(status=result['status'], result=result)
                return result
            except BaseException as error:
                state.update(status='FAILED', error=type(error).__name__+': '+str(error))
                raise
            finally:
                guard.phase = 'closing'
                stop.set()
                observer.join()
                life.close_children(180)
                state.update(ended_at=time.time(), owned_descendants_exited=True,
                             observer_joined=not observer.is_alive())
                write(statepath, state)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--configuration', type=Path, required=True)
    args = parser.parse_args()
    deadline = CONTROL/('deadline_'+os.environ['SLURM_JOB_ID']+'.json')
    print(json.dumps(run(json.loads(args.configuration.read_text()),
                         scheduler_record=json.loads(deadline.read_text()))), flush=True)
