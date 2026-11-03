"""Launch one real Alpha Slurm stage with a same-node native quota publisher."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import shlex
import shutil
import subprocess
import sys
import time

ROOT = Path('/gfshome/alpha/codex_data_v1_20261026')
ENDPOINT = '218.192.171.238:22'


def save(path, value):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())


def pin(path):
    path = Path(path).absolute()
    before = path.stat()
    data = path.read_bytes()
    after = path.stat()
    frame = lambda s: (s.st_dev, s.st_ino, s.st_uid, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    if frame(before) != frame(after) or before.st_uid != 1264 or path.is_symlink():
        raise ValueError('Actual owned immutable source required')
    return dict(path=str(path), bytes=len(data), sha256=hashlib.sha256(data).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--template', type=Path, required=True)
    parser.add_argument('--base-root', type=Path, required=True)
    parser.add_argument('--entry', type=Path, required=True)
    parser.add_argument('--module', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--control-root', type=Path, required=True)
    parser.add_argument('--action', choices=('baseline', 'project'))
    parser.add_argument('--bulk-coverage', type=Path)
    parser.add_argument('--preflight-module', action='append', default=[])
    parser.add_argument('--project-first', action='store_true')
    parser.add_argument('--gluster-rpc-program', type=Path)
    args = parser.parse_args()
    if os.getuid() != 1264 or not sys.flags.isolated or not os.environ.get('SLURM_JOB_ID'):
        raise ValueError('Actual Alpha isolated Slurm parent required')
    base = args.base_root.resolve()
    if Path.cwd().resolve() != base or not base.is_relative_to(ROOT / 'code') or (base / 'string.py').exists():
        raise ValueError('Exact clean immutable base code cwd required')
    if not args.module.startswith('workflows.expansion.') or '/' in args.tag or '..' in args.tag:
        raise ValueError('Explicit stage module/tag required')
    plan = json.loads(args.template.read_text())
    profile = json.loads(Path(plan['runtime_profile_reference']['path']).read_text())
    node = socket.gethostname()
    if (profile['endpoint'] != ENDPOINT or profile['uid'] != 1264
            or node.split('.')[0] not in profile['allowed_nodes']
            or os.environ.get('SLURM_JOB_PARTITION') not in profile['allowed_partitions']
            or int(os.environ.get('SLURM_CPUS_PER_TASK', 0)) < plan['workers']
            or os.environ.get('SLURM_JOB_GPUS') or os.environ.get('SLURM_STEP_GPUS')):
        raise ValueError('Actual approved CPU allocation required')
    job = os.environ['SLURM_JOB_ID']
    directory = args.control_root / (args.tag + '_job_' + job)
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    python = str(ROOT / 'software/pubchem_completion_20261103_venv/bin/python')
    base_entry = base / 'workflows/expansion/alpha_runtime_v1/entry.py'
    authority = dict(plan['quota_authority'])
    authority.pop('publisher', None)
    save(directory / 'quota_base.json', authority)
    quota = directory / 'node_quota_current.json'
    publisher_argv = [python, '-I', '-B', str(base_entry),
        'workflows.expansion.alpha_runtime_v1.quota', '--authority',
        str(directory / 'quota_base.json'), '--output', str(quota), '--publish']
    cli_refs = []
    publisher_env = None
    cli_resolution = dict(mode='LOCAL_NATIVE_CLI', executable=shutil.which('gluster'))
    if cli_resolution['executable'] is None:
        if args.gluster_rpc_program is None:
            raise ValueError('Native CLI absent: an explicit read-only RPC source is required')
        cli_directory = directory / 'readonly_native_cli'
        cli_directory.mkdir(mode=0o700)
        wrapper = cli_directory / 'gluster'
        body = '#!/bin/sh\nexec ' + shlex.quote(python) + ' -I -B ' + shlex.quote(str(args.gluster_rpc_program)) + ' --receipt-root ' + shlex.quote(str(directory / 'native_cli_rpc_receipts')) + ' "$@"\n'
        wrapper.write_text(body)
        wrapper.chmod(0o700)
        cli_refs = [pin(args.gluster_rpc_program), pin(wrapper)]
        publisher_env = dict(os.environ)
        publisher_env['PATH'] = str(cli_directory) + os.pathsep + publisher_env.get('PATH', '')
        cli_resolution = dict(mode='EXPLICIT_READONLY_SONMI1_NATIVE_CLI_RPC',
            program_reference=cli_refs[0], executable_wrapper_reference=cli_refs[1],
            local_directory_statfs_and_consumer_clock_unchanged=True,
            native_stdout_and_stderr_kept_separate=True,
            host_key_checking='StrictHostKeyChecking=yes', only_volume_info_permitted=True)
    log = (directory / 'node_quota_publisher.log').open('xb')
    publisher = subprocess.Popen(publisher_argv, cwd=base, stdin=subprocess.DEVNULL,
        stdout=log, stderr=subprocess.STDOUT, env=publisher_env)
    result = None
    try:
        while True:
            if publisher.poll() is not None:
                raise RuntimeError('Same-node native quota publisher exited before admission')
            if quota.is_file():
                snapshot = json.loads(quota.read_text())
                identity = snapshot['publisher']
                age = time.time() - snapshot['generated_unix_seconds']
                if (identity['pid'] == publisher.pid and identity['uid'] == 1264
                        and identity['hostname'] == node
                        and identity['boot_id'] == Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                        and 0 <= age <= authority['maximum_age_seconds']):
                    break
            time.sleep(0.2)
        authority['publisher'] = identity
        plan['quota_snapshot'] = str(quota)
        plan['quota_authority'] = authority
        save(directory / 'actual_node_publisher.json', dict(argv=publisher_argv,
            identity=identity, job_id=job, node=node, endpoint=ENDPOINT,
            same_clock_domain_as_consumer=True, freshness_predicate_unchanged=True,
            original_global_publisher_not_modified=True,
            native_volume_cli_resolution=cli_resolution))
        if args.bulk_coverage:
            keys = ('runtime_profile_reference', 'quota_snapshot', 'quota_authority',
                'workers', 'software_rss_budget_bytes', 'minimum_node_available_bytes',
                'output_scope_root', 'output_directory', 'output_cap_bytes',
                'other_future_reserved_bytes', 'minimum_free_bytes', 'duckdb_memory_bytes', 'batch_rows')
            resources = {key: plan[key] for key in keys}
            save(directory / 'actual_resources.json', resources)
            subprocess.run([python, '-I', '-B', str(base_entry),
                'workflows.expansion.alpha_closed500_handoff_v1.plan', '--coverage',
                str(args.bulk_coverage), '--resources', str(directory / 'actual_resources.json'),
                '--plan', str(directory / 'prepared_plan.json')], cwd=base, check=True)
            plan = json.loads((directory / 'prepared_plan.json').read_text())
        else:
            resume = plan.get('resume_output_directory')
            if resume is None:
                plan['output_directory'] = str(Path(plan['output_scope_root']) / (args.tag + '_job_' + job))
            else:
                output = Path(resume)
                scope = Path(plan['output_scope_root'])
                if (not output.is_absolute() or output != output.resolve()
                        or not output.is_relative_to(scope) or output == scope
                        or not output.is_dir() or output.stat().st_uid != 1264
                        or any(p.is_symlink() for p in (output, *output.parents))):
                    raise ValueError('Explicit existing owned stage within the same output scope required')
                plan['output_directory'] = str(output)
                plan['runtime_existing_output_stage_reused'] = True
        references = list(plan.get('code_references', [])) + cli_refs
        launcher = pin(__file__)
        if launcher not in references:
            references.append(launcher)
        plan['code_references'] = references
        plan['runtime_node_quota_publisher_reference'] = pin(directory / 'actual_node_publisher.json')
        argv = [python, '-I', '-B', str(args.entry), args.module,
            '--plan', str(directory / 'plan.json')]
        if args.action:
            argv.extend(['--action', args.action])
        else:
            argv.extend(['--startup-proof', str(directory / 'startup.json')])
        plan['execution_argv'] = argv
        save(directory / 'plan.json', plan)
        source_refs = references + plan.get('scientific_source_references', [])
        if plan.get('io_policy_reference') and plan['io_policy_reference'] not in source_refs:
            source_refs.append(plan['io_policy_reference'])
        request = dict(scope_key=plan.get('scope_key', args.tag),
            producer_plan_reference=pin(directory / 'plan.json'), execution_argv=argv,
            source_references=source_refs)
        save(directory / 'startup.json', dict(endpoint=ENDPOINT, uid=os.getuid(),
            job_id=job, node=node, boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
            request=request, launcher_reference=launcher,
            actual_same_node_quota_publisher_reference=pin(directory / 'actual_node_publisher.json')))
        for module in args.preflight_module:
            subprocess.run([python, '-I', '-B', str(args.entry), module, '-v'], cwd=base, check=True)
        if args.project_first:
            subprocess.run([python, '-I', '-B', str(args.entry), args.module,
                '--plan', str(directory / 'plan.json'), '--action', 'project',
                '--fragment-ids', '000_0'], cwd=base, check=True)
        result = subprocess.run(argv, cwd=base).returncode
        save(directory / 'actual_process_exit.json', dict(job_id=job, endpoint=ENDPOINT,
            uid=os.getuid(), returncode=result, actual_parent_C0_pending_root_accounting=True))
        return result
    finally:
        if publisher.poll() is None:
            publisher.terminate()
        try:
            publisher.wait(timeout=10)
        except subprocess.TimeoutExpired:
            publisher.kill()
            publisher.wait()
        save(directory / 'actual_owned_publisher_exit.json', dict(pid=publisher.pid,
            returncode=publisher.returncode, science_process_returncode=result,
            only_owned_child_signaled=True, global_or_other_publishers_modified=False))
        log.close()


if __name__ == '__main__':
    raise SystemExit(main())
