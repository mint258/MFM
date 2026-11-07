"""Real Alpha CPU profile, clean code cwd and original-source pin admission."""
import os
from pathlib import Path
import socket
import sys
from .common import ENDPOINT, UID, load, need, verify


def admit(plan, minimum_workers=16):
    need(sys.flags.isolated == 1, 'Alpha project entry must run with Python-I before imports')
    p = load(verify(plan['runtime_profile_reference']))
    need(p['schema'] == 'ALPHA_FREE_CPU_RUNTIME_PROFILE_V1' and p['endpoint'] == plan['endpoint'] == ENDPOINT and p['uid'] == plan['uid'] == os.getuid() == UID and p['username'] == 'alpha' and p['no_gpu'] is True and p['no_paid_server'] is True, 'True Alpha runtime profile/UID required')
    cwd = Path.cwd().resolve(); code = Path(p['clean_code_root']).resolve()
    need(cwd == code and code != Path.home().resolve() and code.is_relative_to(Path('/gfshome/alpha')) and not (code / 'string.py').exists(), 'Execute from the exact clean Alpha code cwd; never home/string.py')
    module = sys.modules.get('string')
    need(module is None or not str(getattr(module, '__file__', '')).startswith(str(Path.home()) + '/'), 'Home string.py shadowed stdlib')
    node, partition = socket.gethostname().split('.')[0], os.environ.get('SLURM_JOB_PARTITION')
    need(os.environ.get('SLURM_JOB_ID') and node in p['allowed_nodes'] and partition in p['allowed_partitions'], 'Actual approved Alpha Slurm node/partition required')
    workers = plan['workers']; cpus = int(os.environ.get('SLURM_CPUS_PER_TASK', 0))
    need(type(workers) is int and max(minimum_workers, p['minimum_workers']) <= workers <= min(cpus, len(os.sched_getaffinity(0))), 'Workers must fit the actual Alpha CPU allocation')
    need(not os.environ.get('SLURM_JOB_GPUS') and not os.environ.get('SLURM_STEP_GPUS'), 'CPU-only profile cannot request GPUs')
    for ref in plan.get('code_references', []):verify(ref)
    scope, output = Path(plan['output_scope_root']), Path(plan['output_directory'])
    need(scope.is_absolute() and scope.is_relative_to(Path('/gfshome/alpha')) and output.is_relative_to(scope) and not scope.is_symlink() and not output.is_symlink(), 'Private own output within the actual directory quota required')
    scope.mkdir(parents=True, exist_ok=True, mode=0o700)
    need(scope.stat().st_uid == UID and (not output.exists() or output.stat().st_uid == UID), 'Actual Alpha output ownership differs')
    return {'endpoint': ENDPOINT, 'uid': UID, 'pid': os.getpid(), 'node': node, 'partition': partition, 'job_id': os.environ['SLURM_JOB_ID'], 'cpus_per_task': cpus, 'workers': workers, 'clean_code_root': str(code), 'Slurm_memory_environment_observed': {k: os.environ.get(k) for k in ('SLURM_MEM_PER_NODE', 'SLURM_MEM_PER_CPU')}, 'explicit_Slurm_memory_requested': False, 'software_budget_is_not_scheduler_memory_reservation': True}
