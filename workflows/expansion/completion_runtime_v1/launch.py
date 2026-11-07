"""Bind a reviewed expansion plan to the real CPU allocation at startup."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time


def reference(path):
    path = Path(path).absolute()
    raw = path.read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def save_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    return reference(path)


def require(value, message):
    if not value:
        raise RuntimeError(message)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--template-sha256', required=True)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--sources-sha256', required=True)
    parser.add_argument('--control', type=Path, required=True)
    args = parser.parse_args()
    require(reference(args.template)['sha256'] == args.template_sha256, 'Reviewed template changed')
    require(reference(args.sources)['sha256'] == args.sources_sha256, 'Registered source inventory changed')
    template = json.loads(args.template.read_text())
    inventory = json.loads(args.sources.read_text())
    for item in inventory['source_references']:
        require(reference(item['path']) == item, 'Source changed before actual allocation: ' + item['path'])
    job = os.environ.get('SLURM_JOB_ID', '')
    node = socket.gethostname().split('.')[0]
    cpus = int(os.environ.get('SLURM_CPUS_PER_TASK', '0'))
    require(job.isdecimal() and os.getuid() == 1278 and node in template['allowed_nodes'],
            'Actual authorized Main CPU allocation required')
    require(cpus == template['cpus'] and cpus >= 16 and os.environ.get('SLURM_JOB_PARTITION') == template.get('partition', 'cpu'),
            'Actual CPU partition and allocated CPU count required')
    for key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
        os.environ[key] = '1'
    control = args.control / ('job_' + job)
    control.mkdir(parents=True, exist_ok=False)
    plan = copy.deepcopy(template['producer_plan'])
    plan.update(node=node, cpus=cpus, python=str(sys.executable),
                output_directory=str(Path(template['output_base']) / ('job_' + job)))
    plan_ref = save_new(control / 'actual_plan.json', plan)
    proof_path = control / 'startup_proof.json'
    module = template['producer_module']
    argv = [plan['python'], '-B', '-m', module, '--plan', plan_ref['path'],
            '--startup-proof', str(proof_path)]
    stat = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    proof = dict(schema='PUBCHEM_EXPANSION_ACTUAL_ALLOCATION_STARTUP_V1',
        job_id=job, uid=os.getuid(), node=node, cpus=cpus, pid=os.getpid(),
        start_ticks=stat[19], boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
        actual_unix_seconds=time.time(), reviewed_template_reference=reference(args.template),
        source_inventory_reference=reference(args.sources),
        request=dict(scope_key=template['scope_key'], producer_plan_reference=plan_ref,
                     execution_argv=argv, node=node, cpus=cpus,
                     memory_policy='SLURM_DEFAULT_UNSPECIFIED',
                     source_references=inventory['source_references']))
    save_new(proof_path, proof)
    started = time.time()
    result = subprocess.run(argv, cwd=template['working_directory'])
    save_new(control / 'actual_process_exit.json', dict(
        job_id=job, producer_exit_code=result.returncode, started_unix_seconds=started,
        ended_unix_seconds=time.time(), execution_argv=argv,
        scientific_completion_not_inferred_from_exit=True))
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
