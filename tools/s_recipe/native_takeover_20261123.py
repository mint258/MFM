"""Allocated standby requests a committed checkpoint, then resumes once."""
import argparse
import json
import os
from pathlib import Path
import socket
import time
import uuid

import lifecycle_20261122 as life
from native_training_20261123 import verify_closure, resume_from_closure
from runtime import CONTROL, write


def main(task_path):
    task = json.loads(task_path.read_text())
    job = int(os.environ['SLURM_JOB_ID'])
    c = task['configuration']
    if (job != task['standby_job_id'] or socket.gethostname().split('.')[0] != c['node'] or
            os.environ.get('CUDA_VISIBLE_DEVICES') != c['gpu_uuid']):
        raise ValueError('Wrong actual standby allocation')
    deadline = json.loads((CONTROL/('deadline_'+str(job)+'.json')).read_text())
    guard = life.Guard.from_slurm(900, scheduler_record=deadline)
    life.enable_subreaper()
    record = dict(run=c['run'], job_id=job, node=c['node'], mode='standby_takeover',
                  started_at=time.time(), native_lifecycle_record=task['lifecycle_record'])
    resumed = None
    with guard:
        try:
            # Queueing is done by Slurm. An allocated standby only waits for
            # the measured checkpoint/child-exit window, never indefinitely.
            end = min(time.monotonic()+600, time.monotonic()+guard.end_epoch-time.time()-900)
            requested = False
            while True:
                guard.await_next()
                task = json.loads(task_path.read_text())
                expected = task.get('producer')
                if not expected:
                    raise ValueError('Native producer identity was not published before standby release')
                value = json.loads(Path(task['lifecycle_record']).read_text())
                current = life.identity(expected['pid'])
                if verify_closure(task, value, current):
                    resumed = resume_from_closure(task, value)
                    break
                if not requested:
                    request_path = Path(c['handoff_request'])
                    if request_path.exists():
                        raise ValueError('Existing handoff request requires observation, not replacement')
                    write(request_path, dict(action='SAVE_AND_EXIT', run=c['run'], job_id=job,
                        request_id=str(uuid.uuid4()), origin='S_native_standby_20261123'))
                    requested = True
                if time.monotonic() >= end:
                    raise RuntimeError('Native checkpoint/owned-exit window exceeded; no duplicate producer')
                time.sleep(1)
            record.update(status='NATIVE_COMPLETE' if resumed is None else 'NATIVE_HANDOFF_CLOSED',
                          native_producer=expected, native_owned_exit_verified=True)
        finally:
            guard.phase = 'closing'
            life.close_children(180)
            record.update(ended_at=time.time(), owned_descendants_exited=True)
            write(CONTROL/(c['run']+'_standby_'+str(job)+'.json'), record)
    if resumed is None:
        print(json.dumps(record), flush=True)
        return
    # The previous request remains immutable evidence. A new controls pair
    # belongs to this real Slurm producer, preventing an immediate re-handoff.
    resumed.update(mode='Slurm',
        handoff_request=str(CONTROL/(c['run']+'_slurm_'+str(job)+'_request.json')),
        handoff_ack=str(CONTROL/(c['run']+'_slurm_'+str(job)+'_ack.json')))
    from dispatch import ledger
    with ledger() as execution:
        execution['runs'][c['run']].update(mode='Slurm', status='RESUMING',
            resume=resumed['resume'], native_lifecycle_record=task['lifecycle_record'],
            lifecycle_record=str(CONTROL/(c['run']+'_guarded_'+str(job)+'.json')))
    from train_line_storage_20261122 import run
    print(json.dumps(run(resumed, scheduler_record=deadline)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', type=Path, required=True)
    main(parser.parse_args().task)
