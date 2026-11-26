"""Bindings for the registered trajectory/extension readouts; no model imports."""
import os
from pathlib import Path
import re
import socket
import time
import lifecycle_20261122 as life
from storage_20261122 import CONTROL

EXTENSIONS={**{'S_E1_k'+str(k)+'_s0_3M':3000000 for k in (1,2,5)},
    **{'S_subset_T'+str(k)+'_s0_9M':9000000 for k in (5,6)}}


def binding(task,c):
    role,samples=task['role'],task['samples']
    if type(samples) is not int or type(c.get('seed')) is not int or c.get('seed')!=0 or c.get('layer') not in (None,6):
        raise ValueError('Only the registered seed0 layer6 representation')
    if role=='budget':
        if (c.get('run') not in ('S_B0_s0_9M','S_final_s0_9M') or c.get('samples')!=9000000
                or samples not in range(1000000,9000000,1000000)):
            raise ValueError('Only the eight original9M trajectory snapshots')
    elif role=='terminal':
        expected=EXTENSIONS.get(c.get('run'))
        points=[3000000] if expected==3000000 else [3000000,6000000,9000000]
        if expected is None or samples!=expected or c.get('samples')!=expected or c.get('evaluation_samples')!=points:
            raise ValueError('Only the registered three E1 and two subset endpoints')
    else:raise ValueError('No additional readout role')
    handle=task['handle']
    prefix=c['run']+'_readout_'+role+'_'+str(samples)+'_attempt'
    if not re.fullmatch(re.escape(prefix)+r'\d+',handle):raise ValueError('Readout handle differs from its scope')
    if (Path(c['output'])!=CONTROL/'training'/c['run']
            or Path(task['configuration'])!=CONTROL/(handle+'_configuration.json')
            or Path(task['native_record'])!=CONTROL/(handle+'_native_record.json')
            or Path(task['handoff_request'])!=CONTROL/(handle+'_handoff_request.json')):
        raise ValueError('Readout files differ from the exact run/attempt')
    output=Path(c['output'])/('readout' if role=='terminal' else 'readout_'+str(samples))
    return output,('terminal_gpu_status.json' if role=='terminal' else 'snapshot_gpu_status.json')


def native_guard(task,c):
    binding(task,c)
    contract=task['contract']
    if (os.getuid()!=1278 or os.environ.get('SLURM_JOB_ID') or c['node'] not in ('compute-0-20','compute-0-22')
            or socket.gethostname().split('.')[0]!=c['node']
            or contract.get('uid')!=1278 or contract.get('run')!=c['run']
            or contract.get('node')!=c['node'] or contract.get('role')!=task['role']
            or contract.get('samples')!=task['samples'] or contract.get('duration_seconds')!=7200
            or not 0<=time.time()-contract['created_at']<=60
            or type(task.get('standby_job_id')) is not int):
        raise ValueError('Fresh exact native readout contract required')
    if not life.same_process(life.Identity(**task['producer']),life.identity(os.getpid())):
        raise ValueError('This native reader is not its published PID identity')
    return life.Guard(contract['created_at']+7200,900)


def native_closed(task,value,current):
    if (value.get('run')!=task['run'] or value.get('samples')!=task['samples']
            or value.get('role')!=task['role'] or value.get('resource_handle')!=task['handle']
            or not value.get('producer')
            or not life.same_process(life.Identity(**task['producer']),life.Identity(**value['producer']))):
        raise ValueError('Readout closure is not bound to this exact producer and point')
    return bool(value.get('ended_at') and value.get('owned_descendants_exited')
        and value.get('observer_joined') and value.get('exit_code') is not None
        and not life.same_process(life.Identity(**task['producer']),current))
