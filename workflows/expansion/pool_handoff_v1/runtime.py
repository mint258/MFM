"""Shared aggregate storage scope and actual approved allocation admission."""
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import socket
import threading
from ..pubchem_raw_reconstruction_v1.support import RuntimeGuard, frame, load, need, reference, verify, write_new


def pinned_frame(ref):
    body = {k: ref[k] for k in ('path', 'bytes', 'sha256')}
    before = frame(body['path'])
    path = verify(body)
    need(frame(path) == before, 'Source changed across SHA admission')
    return path, before


def admission(plan):
    need(plan['schema'] == 'PUBCHEM_POOL_HANDOFF_PLAN_V1', 'Versioned pool handoff plan required')
    need(plan['code_references'], 'Actual runtime and unchanged scientific source pins required')
    for ref in plan['code_references']:
        verify(ref)
    need(os.getuid() == 1278 and os.environ.get('SLURM_JOB_ID'), 'Actual Main user Slurm allocation required')
    node = socket.gethostname().split('.')[0]
    need(node.startswith('compute-0-'), 'Actual compute node required')
    n = plan['workers']
    need(type(n) is int and 16 <= n <= min(len(os.sched_getaffinity(0)), int(os.environ.get('SLURM_CPUS_PER_TASK', 0))), 'Workers exceed actual CPU allocation')
    if node == 'compute-0-21':
        a = load(verify(plan['cpu21_authorization_reference']))
        need(a['schema'] == 'PUBCHEM_EXPANSION_USER_CPU21_AUTHORIZATION_V1' and a['status'] == 'USER_APPROVED' and a['node'] == node and a['partition'] == os.environ.get('SLURM_JOB_PARTITION') == 'all' and a['GPU_used'] is False and a['paid_server_used'] is False, 'Actual approved CPU21/all policy required')
    root, stage = Path(plan['output_scope_root']), Path(plan['stage_output_directory'])
    need(root.is_absolute() and root == Path(plan['output_directory']) and stage.is_relative_to(root) and stage != root and not root.is_symlink() and not stage.is_symlink(), 'Dedicated private stage under aggregate raw scope required')
    need(plan['quota_authority']['kind'] == 'lustre' and plan['quota_snapshot'], 'Actual Lustre account quota authority required')
    need(plan['output_cap_bytes'] == 550000000000 and plan['other_future_reserved_bytes'] == 950000000000 and plan['minimum_free_bytes'] == 200000000000, 'One combined Root-reviewed550GB allowance plus950GB other future reserve required')
    need(type(plan['duckdb_memory_bytes']) is int and 0 < plan['duckdb_memory_bytes'] < plan['software_rss_budget_bytes'], 'DuckDB internal allowance must leave RSS overhead')
    stage.mkdir(parents=True, exist_ok=True, mode=0o700)
    return stage


@contextmanager
def allocated(plan):
    stage = admission(plan)
    with (stage / 'parent.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        guard = RuntimeGuard(plan, threading.Event())
        try:
            yield stage, guard
        finally:
            guard.close()


def parent():
    return {'pid': os.getpid(), 'uid': os.getuid(), 'node': socket.gethostname(), 'SlurmJobID': os.environ.get('SLURM_JOB_ID'), 'actual_partition': os.environ.get('SLURM_JOB_PARTITION'), 'actual_CPUs_per_task': os.environ.get('SLURM_CPUS_PER_TASK'), 'actual_default_memory_environment': {k: os.environ.get(k) for k in ('SLURM_MEM_PER_NODE', 'SLURM_MEM_PER_CPU')}, 'explicit_Slurm_memory_requested': False}
