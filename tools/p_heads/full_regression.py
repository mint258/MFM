"""Final current/tests suite, isolated on this task's NFS and local scratch.

Preserves the established per-module pytest protocol without changing p_recipe.
Run only after all registered scientific work has finished.
"""
import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import re
import signal
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from h_resources import CONTROL, GIB, R, REPO, allocated, disk, guard, load, save
from t_runtime_identity import identity


def core(output, scratch):
    """Same module discovery, pytest arguments and JUnit totals as p_recipe."""
    output.mkdir()
    scratch.mkdir(mode=0o700)
    files = sorted((REPO / 'current/tests').glob('test_*.py'))
    if not files:
        raise ValueError('No current/tests modules found')
    started = time.monotonic()

    def run(item):
        index, path = item
        xml = output / (path.stem + '.xml')
        argv = [sys.executable, '-B', '-m', 'pytest', str(path), '-q',
                '-p', 'no:cacheprovider', '--junitxml=' + str(xml),
                '--basetemp=' + str(scratch / str(index))]
        with (output / (path.stem + '.log')).open('wb') as stream:
            result = subprocess.run(argv, cwd=REPO / 'current', stdout=stream,
                                    stderr=subprocess.STDOUT)
        counts = dict.fromkeys(('tests', 'failures', 'errors', 'skipped'), 0)
        if xml.exists():
            for suite in ET.parse(xml).getroot().iter('testsuite'):
                for key in counts:
                    counts[key] += int(suite.get(key, 0))
        row = dict(module=path.name, returncode=result.returncode, counts=counts)
        (output / (path.stem + '.json')).write_text(json.dumps(row) + '\n')
        print(json.dumps(row), flush=True)
        return row

    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        rows = list(pool.map(run, enumerate(files)))
    result = dict(status='PASS' if all(r['returncode'] == 0 for r in rows) else 'FAIL',
                  counts={k: sum(r['counts'][k] for r in rows) for k in rows[0]['counts']},
                  modules=len(rows), seconds=time.monotonic() - started, workers=2,
                  failed_modules=[r for r in rows if r['returncode']])
    (output / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    return int(result['status'] != 'PASS')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core', action='store_true')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--scratch', type=Path)
    args = parser.parse_args()
    if args.core:
        if args.output is None or args.scratch is None:
            parser.error('--core requires --output and --scratch')
        return core(args.output, args.scratch)

    job = os.environ['SLURM_JOB_ID']
    cpus = int(os.environ['SLURM_CPUS_PER_TASK'])
    if cpus != 16:
        raise ValueError('Final CPU regression needs a real 16-CPU Slurm allocation')
    allocation = subprocess.check_output(['scontrol', 'show', 'job', '-d', job], text=True)
    if not re.search(r'\bNumNodes=1\b', allocation):
        raise ValueError('Final CPU regression requires a single-node allocation')
    ids = re.search(r'\bCPU_IDs=([^\s]+)', allocation)
    if ids is None:
        raise ValueError('Slurm did not report its allocated CPU IDs')
    # CPU_IDs are scheduler indices, which can differ from Linux IDs on SMT nodes.
    # Use the same actual srun Linux-mask check as the completed H CPU workers.
    binding = os.environ.get('SLURM_CPU_BIND_LIST', '')
    if not binding:
        raise ValueError('Final CPU regression requires the srun CPU binding')
    bits = int(binding.split(',')[0], 16)
    bound_cpu_ids = {i for i in range(bits.bit_length()) if bits & (1 << i)}
    cpu_ids = set(os.sched_getaffinity(0))
    if len(cpu_ids) != cpus or cpu_ids != bound_cpu_ids:
        raise ValueError('Linux affinity does not match the actual 16-CPU srun mask')
    process = identity(os.getpid())
    print('P_HEADS_REGRESSION_BINDING', json.dumps(dict(
        process=process, slurm_cpu_ids=ids[1], srun_cpu_bind_list=binding,
        srun_cpu_bind_type=os.environ.get('SLURM_CPU_BIND_TYPE'))), flush=True)
    output = CONTROL / ('regression_' + job)
    scratch = Path('/tmp') / ('mpHeads_' + job)
    private = Path('/tmp') / ('mv3n_' + job)

    def capacity():
        guard(force=True)
        future = max(0, 10 * GIB - allocated(scratch) - allocated(private))
        disk.m.require_capacity(disk.m.filesystem_status('/tmp'), future, 10000)

    capacity()
    git = shutil.which('git') or str(R / 'runs/p_followup_20261116/test_tools/git/bin/git')
    commit = subprocess.check_output([git, 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip()
    sys.path.insert(0, str(REPO / 'tools/model_v3'))
    from private_runtime_storage import PrivateStorage, _write_exclusive
    output.mkdir()
    storage = PrivateStorage(private, budget_bytes=2 * GIB)
    binding = output / 'private_storage.json'
    pin = _write_exclusive(binding, storage.bindings)
    os.environ.update(storage.bindings['environment'])
    os.environ.update(MODEL_V3_STORAGE_BINDINGS_PATH=str(binding),
                      MODEL_V3_STORAGE_BINDINGS_SHA256=pin, CUDA_VISIBLE_DEVICES='',
                      PYTHONDONTWRITEBYTECODE='1', OMP_NUM_THREADS='1',
                      OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
    storage.start()
    child = subprocess.Popen([sys.executable, '-B', '-u', __file__, '--core',
                              '--output', str(output / 'core'), '--scratch', str(scratch)],
                             cwd=REPO, start_new_session=True)
    try:
        while child.poll() is None:
            capacity()
            time.sleep(2)
    except BaseException:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
            try:
                child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()
        raise
    finally:
        try:
            storage_observation = storage.stop()
        except (ValueError, RuntimeError, MemoryError) as error:
            storage_observation = dict(error=str(error))
    summary = load(output / 'core/summary.json')
    summary.update(job_id=job, output=str(output / 'core'), scratch=str(scratch),
                   source_commit=commit, allocated_cpus=cpus, cpu_ids=sorted(cpu_ids),
                   process=process, slurm_cpu_ids=ids[1],
                   srun_cpu_bind_list=binding,
                   srun_cpu_bind_type=os.environ.get('SLURM_CPU_BIND_TYPE'),
                   private_storage=storage_observation,
                   scope='All current/tests/test_*.py, established isolated CPU module protocol')
    save(output / 'summary.json', summary)
    save(REPO / 'results/p_heads/REGRESSION_FULL.json', summary)
    print('P_HEADS_FULL_REGRESSION', json.dumps(summary), flush=True)
    return child.returncode


if __name__ == '__main__':
    raise SystemExit(main())
