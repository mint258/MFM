"""Real Slurm or owned native CPU metadata; never invent a job ID."""
import json
import os
from pathlib import Path
import socket
import time
from lifecycle_20261122 import identity, same_process, Identity
from storage_20261122 import CONTROL


def native_record():
    path = Path(os.environ['S_NATIVE_CPU_RECORD'])
    if path.parent.parent != CONTROL/'native_cpu_20261126' or path.name != 'record.json':
        raise ValueError('Native context must remain inside its S-owned execution directory')
    record = json.loads(path.read_text())
    saved = Identity(**record['producer'])
    if (record['execution'] != 'native_cpu' or record['job_id'] is not None
            or record['node'] != socket.gethostname().split('.')[0]
            or saved.uid != os.getuid() or not same_process(saved, identity(saved.pid))
            or time.time() >= record['hard_end_epoch']):
        raise ValueError('No matching live native CPU owner and finite deadline')
    parent = identity(os.getpid())
    for _ in range(16):
        if parent is not None and parent.pid == saved.pid:
            return record
        if parent is None or parent.uid != saved.uid or parent.ppid <= 1:
            break
        parent = identity(parent.ppid)
    raise ValueError('Caller is outside the native CPU owner subtree')


def execution_fields():
    job = os.environ.get('SLURM_JOB_ID')
    if job is not None:
        if not job.isdecimal():
            raise ValueError('Malformed actual Slurm job identity')
        return dict(job_id=int(job))
    record = native_record()
    return dict(job_id=None, native_handle=record['handle'],
                native_record=os.environ['S_NATIVE_CPU_RECORD'])


def stop_new_work_epoch():
    if os.environ.get('SLURM_JOB_ID'):
        value = json.loads((CONTROL/('deadline_'+os.environ['SLURM_JOB_ID']+'.json')).read_text())
        return value['anchor_epoch']+value['time_limit_seconds']-210
    record = native_record()
    return record['hard_end_epoch']-max(210,record['cleanup_seconds'])
