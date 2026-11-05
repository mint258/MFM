"""Execute a frozen complete CPU partition with explicit runtime source admission."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

from identity_revision_v4 import (REGISTRATION_DIRECTORY, atomic_json, capture_identity,
    changed_keys, file_ref, load_fixed_control, load_fixed_runtime, make_exec_receipt,
    make_manifest, partition_groups, pytest_roles, require, verify_source_pins)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--code-commit', required=True)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--partition-plan', type=Path, required=True)
    parser.add_argument('--partition-plan-sha256', required=True)
    parser.add_argument('--partitions', type=int, required=True)
    parser.add_argument('--partition-index', type=int, required=True)
    parser.add_argument('--expected-node', choices=['compute-0-' + str(i) for i in (2, *range(8, 20))], required=True)
    args = parser.parse_args()
    pins_path = Path(os.environ['MODEL_V3_CPU_IDENTITY_SOURCE_PINS'])
    pins_sha = os.environ['MODEL_V3_CPU_IDENTITY_SOURCE_PINS_SHA']
    pins = verify_source_pins(pins_path, pins_sha)
    runtime = load_fixed_runtime(pins)
    control = load_fixed_control(pins)
    RUNTIME_SCOPE = control.RUNTIME_SCOPE
    capture_sources, file_sha = control.capture_sources, control.file_sha
    launch_bindings, validate_source_observation = control.launch_bindings, control.validate_source_observation
    verify_frozen_plan, write_exclusive = control.verify_frozen_plan, control.write_exclusive
    job, node = os.environ.get('SLURM_JOB_ID', ''), socket.gethostname().split('.')[0]
    require(job.isdigit() and node == args.expected_node and os.environ.get('CUDA_VISIBLE_DEVICES') == '', 'Owned CPU Slurm allocation required')
    require(1 <= args.workers <= min(4, int(os.environ['SLURM_CPUS_PER_TASK'])) and int(os.environ['SLURM_CPUS_PER_TASK']) >= 16, 'Bounded workers inside16CPU allocation required')
    plan_path, plan_sha = Path(os.environ['MODEL_V3_CONTROL_PLAN']), os.environ['MODEL_V3_CONTROL_PLAN_SHA']
    plan, assignment = verify_frozen_plan(plan_path, plan_sha)
    contract = plan['contract']
    require(0 <= args.partition_index < args.partitions == 8, 'Exact bounded partition required')
    expected_env = launch_bindings(plan, plan_sha, args.partition_index)
    require(all(os.environ.get(key) == value for key, value in expected_env.items()), 'Executed environment differs from frozen binding file')
    for name in ('PHASE1_NATIVE_TRANSPORT_PATH', 'PHASE1_JOINT_REFERENCE_PATH'):
        require(os.environ.get(name) == contract['runtime']['scope']['external_python'][name]['path'],
                'Actually imported PHASE1 path differs from explicit source ref')
    worker_ref = file_ref(Path(__file__).resolve())
    require(contract['runner'] == {'path': worker_ref['path'], 'sha256': worker_ref['sha256']},
            'New worker must be the explicitly frozen runner')
    require({'path': str(pins_path), 'sha256': pins_sha} in contract['control_files'],
            'New runtime inventory must be bound by this control plan')
    root, out = args.root.absolute(), args.output.absolute()
    require(str(root) == contract['tree'] and args.code_commit == contract['code_sha']
            and str(args.partition_plan) == contract['assignment']['path']
            and args.partition_plan_sha256 == contract['assignment']['sha256'], 'Worker CLI differs from frozen contract')
    require(out == Path(contract['runs']) / ('integration_tests_' + job), 'Exact job-owned output path required')
    before = capture_sources(root, contract['runtime']['scope'], contract['code_sha'])
    validate_source_observation(before, contract)
    out.mkdir(exist_ok=False)
    write_exclusive(out / 'sources_before.json', before)
    names = assignment['assignments'][args.partition_index]['files']
    files = [root / name for name in names]
    workers = min(args.workers, len(files))
    groups = partition_groups(files, workers)
    roles = pytest_roles(sys.executable, root, out, groups)
    group = Path('/proc/self/cgroup').read_text()
    expected_parent_argv = control.expected_supervisor_command(expected_env, args.expected_node, job)
    parent = capture_identity(runtime['runtime_monitor'], os.getpid(), expected_cgroup=group,
                              expected_argv=expected_parent_argv)
    require(parent['status'] == 'ACTIVE', 'Actual worker kernel identity required')
    context = {'source_pins': file_ref(pins_path), 'worker_source': worker_ref,
               'control_plan': file_ref(plan_path), 'roles': roles}
    registration = out / REGISTRATION_DIRECTORY
    registration.mkdir(exist_ok=False)
    manifest = make_manifest(parent, context)
    manifest_ref = atomic_json(registration / 'manifest.json', manifest)

    def run(index):
        log, xml = out / f'shard_{index:02d}.log', out / f'shard_{index:02d}.xml'
        role = roles[index]
        argv = role['expected_argv']
        start = time.monotonic()
        process, bound = None, None
        try:
            with log.open('xb') as stream:
                # Popen returns only after the exec error pipe is closed. The
                # source-bound receipt is published before wait or any success.
                process = subprocess.Popen(argv, cwd=root / 'current', stdin=subprocess.DEVNULL,
                                           stdout=stream, stderr=subprocess.STDOUT)
                bound = capture_identity(runtime['runtime_monitor'], process.pid,
                                         expected_cgroup=group, expected_argv=argv)
                require(bound['status'] == 'ACTIVE', 'Post-exec full child identity required')
                receipt = make_exec_receipt(manifest, manifest_ref, role, bound)
                atomic_json(registration / (role['role'] + '.exec.json'), receipt)
                process.wait()
        finally:
            if process is not None and process.poll() is None and bound and bound['status'] == 'ACTIVE':
                # A worker failure cannot leak its own fully bound Popen child.
                runtime['run_supervised'].stop_recorded({(bound['pid'], bound['start_ticks']): bound})
        counts = dict(tests=0, failures=0, errors=0, skipped=0)
        if xml.exists():
            for suite in ET.parse(xml).getroot().iter('testsuite'):
                for key in counts:
                    counts[key] += int(suite.attrib.get(key, 0))
        row = {'shard': index, 'returncode': process.returncode, 'argv': argv,
               'files': [str(path.relative_to(root)) for path in groups[index]],
               'counts': counts, 'elapsed_seconds': time.monotonic() - start}
        write_exclusive(out / f'shard_{index:02d}.json', row)
        return row

    started, rows, after, failure = time.monotonic(), [], None, None
    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            rows = list(executor.map(run, range(workers)))
    except BaseException as exc:
        failure = {'phase': 'test_execution', 'type': type(exc).__name__, 'message': str(exc)}
    finally:
        try:
            after = capture_sources(root, contract['runtime']['scope'], contract['code_sha'])
            write_exclusive(out / 'sources_after.json', after)
            validate_source_observation(after, contract)
            require(before == after, 'Runtime source bytes or inventory changed during tests')
            verify_frozen_plan(plan_path, plan_sha, verify_runtime=False)
        except BaseException as exc:
            source_failure = {'phase': 'source_after', 'type': type(exc).__name__, 'message': str(exc)}
            failure = {'first': failure, 'source_check': source_failure} if failure else source_failure
    counts = {key: sum(row['counts'][key] for row in rows) for key in ('tests', 'failures', 'errors', 'skipped')}
    passed = (failure is None and len(rows) == workers and all(row['returncode'] == 0 and row['counts']['tests'] > 0 for row in rows)
              and counts['tests'] > 0 and not counts['failures'] and not counts['errors'])
    summary = {'status': 'PASS' if passed else 'FAIL', 'failure': failure, 'job_id': job,
               'node': socket.gethostname(), 'expected_node': args.expected_node,
               'code_commit': args.code_commit, 'partitions': 8, 'partition_index': args.partition_index,
               'partition_plan_sha256': args.partition_plan_sha256, 'control_plan_sha256': plan_sha,
               'runner_sha256': file_sha(Path(__file__).absolute()),
               'identity_registration_manifest': manifest_ref,
               'identity_source_inventory': file_ref(pins_path),
               'all_test_file_sha256': assignment['all_test_file_sha256'],
               'test_source_sha256': {name: assignment['all_test_file_sha256'][name] for name in names},
               'test_file_count': len(names), 'source_scope': RUNTIME_SCOPE,
               'sources_before': before, 'sources_after': after,
               'workers': workers, 'counts': counts, 'shards': rows,
               'elapsed_seconds': time.monotonic() - started}
    write_exclusive(out / 'summary.json', summary)
    print(json.dumps({'status': summary['status'], 'counts': counts}), flush=True)
    return int(not passed)


if __name__ == '__main__':
    raise SystemExit(main())
