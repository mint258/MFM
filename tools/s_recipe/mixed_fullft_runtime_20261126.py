"""Explicit native metadata bridge for the unchanged P fullFT function body."""
import ast
import inspect
import json
import os
from pathlib import Path
import re
import socket
import time

import lifecycle_20261122 as life
from storage_20261122 import CONTROL,ROOT


def native_main_source(source,cpus):
    if type(cpus) is not int or cpus!=16:
        raise ValueError('The registered fullFT CPU demand remains16')
    tree=ast.parse(source)
    if len(tree.body)!=1 or not isinstance(tree.body[0],ast.FunctionDef) or tree.body[0].name!='main':
        raise ValueError('Adapt exactly the original main function')
    counts={'SLURM_CPUS_PER_TASK':0,'SLURM_JOB_ID':0}
    class Metadata(ast.NodeTransformer):
        def visit_Subscript(self,node):
            if (isinstance(node.value,ast.Attribute) and node.value.attr=='environ'
                    and isinstance(node.value.value,ast.Name) and node.value.value.id=='os'
                    and isinstance(node.slice,ast.Constant)
                    and node.slice.value in counts):
                key=node.slice.value
                counts[key]+=1
                return ast.copy_location(ast.Constant(str(cpus) if key=='SLURM_CPUS_PER_TASK' else None),node)
            return self.generic_visit(node)
    tree=Metadata().visit(tree)
    if counts!={'SLURM_CPUS_PER_TASK':1,'SLURM_JOB_ID':1}:
        raise ValueError('Inspect changed provider metadata accesses before adaptation')
    return ast.fix_missing_locations(tree)


def bind_native_main(provider,cpus):
    tree=native_main_source(inspect.getsource(provider.main),cpus)
    original=provider.main
    exec(compile(tree,'<S native fullFT metadata bridge>','exec'),provider.__dict__)
    return original


def native_guard(task,c):
    contract=task['contract']
    handle=task.get('native_handle','')
    if (os.getuid()!=1278 or os.environ.get('SLURM_JOB_ID')
            or c.get('execution_backend')!='mixed_gpu_native_20261126'
            or socket.gethostname().split('.')[0]!=c['node']
            or c['node'] not in ('compute-0-20','compute-0-22')
            or contract.get('uid')!=1278 or contract.get('run')!=c['run']
            or contract.get('node')!=c['node'] or contract.get('duration_seconds')!=2100
            or not 0<=time.time()-contract['created_at']<=60
            or not re.fullmatch(re.escape(c['run'])+r'_attempt\d+',handle)
            or Path(task['configuration'])!=CONTROL/(handle+'_configuration.json')
            or Path(task['native_record'])!=CONTROL/(handle+'_fullft_native_record.json')
            or Path(task['handoff_request'])!=CONTROL/(handle+'_fullft_handoff_request.json')
            or type(task.get('standby_job_id')) is not int):
        raise ValueError('Exact fresh native fullFT contract required')
    actual=life.identity(os.getpid())
    if not life.same_process(life.Identity(**task['producer']),actual):
        raise ValueError('Native task producer differs from this real PID identity')
    guard=life.Guard(contract['created_at']+2100,900)
    guard.deadline_basis='explicit_native_fullFT_contract'
    return guard


def observe_handoff(task,c,guard):
    path=Path(task['handoff_request'])
    if not path.exists():return
    request=json.loads(path.read_text())
    if (request.get('run')!=c['run'] or request.get('native_handle')!=task['native_handle']
            or request.get('standby_job_id')!=task['standby_job_id']
            or request.get('producer')!=task['producer']):
        raise ValueError('Handoff request is not bound to this native producer')
    guard.request('actual_same_task_Slurm_takeover')


def mixed_gpu_lock(c,stop):
    import csv
    import fcntl
    from finetune_extension_20261124 import query
    lockpath=ROOT/'docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks'/(c['gpu_uuid']+'.lock')
    lock=lockpath.open('a')
    try:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        rows=list(csv.reader(query([c['nvidia_smi'],'--id='+c['gpu_uuid'],
            '--query-gpu=uuid,name,memory.used,memory.total','--format=csv,noheader,nounits'],stop).splitlines()))
        if len(rows)!=1 or rows[0][0].strip()!=c['gpu_uuid']:
            raise ValueError('Actual mixed GPU UUID differs')
        uuid,name,used,total=[value.strip() for value in rows[0]]
        if (c['node'] not in ('compute-0-20','compute-0-22') or float(used)/float(total)>.30
                or float(total)-float(used)<c['minimum_free_gpu_mib']):
            raise ValueError('Actual mixed GPU memory no longer qualifies')
        return lock,dict(uuid=uuid,name=name,memory_used_mib=float(used),memory_total_mib=float(total))
    except BaseException:
        lock.close()
        raise
