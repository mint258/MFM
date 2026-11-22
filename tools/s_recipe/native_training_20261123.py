"""Opt-in finite native training on20/22, with cooperative Slurm takeover.

Reuse the guarded training mathematics and owned-child lifecycle. Native work
has a real PID identity and explicit finite deadline, never a Slurm identity.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import threading
import time

import lifecycle_20261122 as life
import train_guarded_startup_20261122 as entry
from runtime import CONTROL, ROOT, write
from storage_line_20261122 import admit


class NativeGuard(life.Guard):
    def __init__(self, contract, configuration, *, now=time.time):
        c = configuration
        if (contract.get('schema') != 'S_FINITE_NATIVE_V1' or
                contract.get('uid') != os.getuid() or
                contract.get('run') != c['run'] or contract.get('node') != c['node'] or
                c['node'] not in ('compute-0-20', 'compute-0-22') or
                not 0 <= now()-contract['created_at'] <= 60 or
                not 1800 <= contract['duration_seconds'] <= 48*3600):
            raise ValueError('A fresh finite native contract bound to this producer is required')
        super().__init__(contract['created_at']+contract['duration_seconds'], 900, now=now)
        self.deadline_basis = 'explicit_native_contract'

    def handoff(self, configuration):
        return dict(action='SAVE_AND_EXIT', run=configuration['run'], job_id=None,
                    request_id=self.request_id, reason=self.reason,
                    origin='S_finite_native_20261123')


def verify_closure(task, value, current_identity):
    """Closure and actual PID disappearance are both needed before takeover."""
    c = task['configuration']
    expected = task.get('producer')
    if (value.get('run') != c['run'] or value.get('node') != c['node'] or
            value.get('gpu_uuid') != c['gpu_uuid'] or not expected or
            not value.get('producer') or
            not life.same_process(life.Identity(**expected), life.Identity(**value['producer'])) or
            expected.get('uid') != os.getuid()):
        raise ValueError('Closure is not bound to the exact native producer')
    if not value.get('owned_descendants_exited') or not value.get('ended_at'):
        return False
    return not life.same_process(life.Identity(**expected), current_identity)


def resume_from_closure(task, value):
    c = dict(task['configuration'])
    result = value.get('result', {})
    if (result.get('status') == 'TRAINING_COMPLETE_READOUT_PENDING' and
            result.get('samples') == c['samples']):
        return None
    if result.get('status') != 'HANDOFF_SAVED':
        raise ValueError('Native producer did not close a complete checkpoint')
    ack = json.loads(Path(c['handoff_ack']).read_text())
    if any(ack.get(key) != result.get(key) for key in ('request_id', 'run', 'job_id', 'checkpoint', 'clock')):
        raise ValueError('Acknowledgement differs from the producer closure')
    checkpoint = Path(ack['checkpoint'])
    samples = ack['clock']['samples_consumed']
    if (ack['run'] != c['run'] or not 0 <= samples < c['samples'] or
            checkpoint != Path(c['output'])/('samples_'+str(samples)+'.pt') or
            not checkpoint.is_file()):
        raise ValueError('Takeover checkpoint is not the producer-published committed boundary')
    c['resume'] = str(checkpoint)
    return c


def run(task):
    from dispatch import gate, authorized
    c = task['configuration']
    if os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Native work must not inherit a Slurm identity')
    if gate():
        raise ValueError(gate())
    authorized(c)
    if (socket.gethostname().split('.')[0] != c['node'] or
            os.environ.get('CUDA_VISIBLE_DEVICES') != c['gpu_uuid']):
        raise ValueError('Wrong native node/GPU binding')
    guard = NativeGuard(task['contract'], c)
    life.enable_subreaper()
    lockpath = ROOT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(c['gpu_uuid']+'.lock')
    with lockpath.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        card = entry.query_gpu(c['gpu_uuid'])
        used, total = float(card[2]), float(card[3])
        if used/total > .30 or total-used < c['minimum_free_gpu_mib']:
            raise RuntimeError('Actual native GPU memory is no longer available')
        print(json.dumps(dict(S_LINE_RESOURCE_ADMISSION=admit(c))), flush=True)
        state = dict(run=c['run'], job_id=None, standby_job_id=task['standby_job_id'],
            node=c['node'], gpu_uuid=c['gpu_uuid'], producer=vars(life.identity(os.getpid())),
            mode='native_with_standby', started_at=time.time(),
            actual_deadline_epoch=guard.end_epoch, deadline_basis=guard.deadline_basis,
            closing_reserve_seconds=900, status='TRAINING', resume=c.get('resume'),
            gpu_metadata_at_start=card)
        write(task['lifecycle_record'], state)
        stop = threading.Event()
        # This admission replaces the old repeated peer-budget callback only
        # inside this new native process. Existing producers remain unchanged.
        entry.capacity = lambda: None
        observer = threading.Thread(target=entry.observe, args=(c, guard, stop), daemon=False)
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
                write(task['lifecycle_record'], state)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(json.loads(args.task.read_text()))), flush=True)
