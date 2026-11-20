"""Run a real S allocation or take over its same-task native process."""
import argparse
import json
import os
from pathlib import Path
import socket
import time
import uuid

from dispatch import existing_scheduling, read
from runtime import CONTROL, identity, run, write


def main(task):
    job = int(os.environ['SLURM_JOB_ID'])
    if socket.gethostname().split('.')[0] != task['node'] or int(os.environ['SLURM_CPUS_PER_TASK']) < task['cpus']:
        raise RuntimeError('Actual allocation differs from the S scheduling task')
    c = read(task['configuration'])
    native = None
    if task['mode'] == 'native_with_standby':
        request = dict(action='SAVE_AND_EXIT', run=c['run'], job_id=job, request_id=str(uuid.uuid4()))
        sent = False
        while True:
            path = Path(task['state_path'])
            if not path.is_file():
                time.sleep(1)
                continue
            native = read(path)
            if 'exit_code' in native:
                if native['exit_code'] != 0:
                    raise RuntimeError('Native attempt failed; preserve it and diagnose within the taskbook timebox')
                ack = Path(c['handoff_ack'])
                if sent and ack.is_file() and read(ack)['request_id'] == request['request_id']:
                    ack = read(ack)
                    checkpoint = Path(ack['checkpoint'])
                    if checkpoint.parent != Path(c['output']) or not checkpoint.is_file():
                        raise RuntimeError('Handoff checkpoint is outside this run')
                    c.update(resume=str(checkpoint), resume_samples=ack['clock']['samples_consumed'])
                    c.pop('handoff_request', None)
                    c.pop('handoff_ack', None)
                    write(CONTROL/(c['run']+'_native_terminal.json'), native)
                    write(task['configuration'], c)
                    break
                summary = Path(c['output'])/'summary.json'
                if summary.is_file() and read(summary)['status'] in ('COMPLETE', 'GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS'):
                    return 0
                raise RuntimeError('Source exited without the matching handoff or completed readouts')
            summary = Path(c['output'])/'summary.json'
            if summary.is_file():
                # Training has completed; allow its existing readouts to finish.
                time.sleep(1)
                continue
            if not sent:
                bound = {key: native[key] for key in ('pid', 'uid', 'start_ticks', 'pgid')}
                if bound['uid'] != os.getuid() or identity(bound['pid']) != bound:
                    raise RuntimeError('Own source process identity changed')
                write(c['handoff_request'], request)
                sent = True
            time.sleep(1)
        scheduler = existing_scheduling()
        while scheduler.own_gpu_busy(task['gpu_uuid']):
            time.sleep(1)
    task = dict(task, mode='Slurm')
    return run(task)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--task', type=Path, required=True)
    raise SystemExit(main(read(p.parse_args().task)))
