"""Read-only, explicitly scoped regression provenance and metadata validation.

No model/data imports. This module never opens labels, stores, weights or targets.
Its pure metadata validators do not establish that Slurm actually ran anything.
"""
from __future__ import annotations

import hashlib
import ast
import json
import os
from pathlib import Path
import re
import stat
import subprocess

PROJECT = Path('/share/home/zixiao/descriptor_analysis')
RUNS = PROJECT / 'runs/model_v3_20261025'
CONTROL = PROJECT / 'runs/model_v3_20261026/numeric_full_regression_v1_source'
PLAN_SCHEMA = 'model_v3_numeric_single_parent_control_v1'
ASSIGNMENT_SCHEMA = 'model_v3_numeric_single_parent_assignment_v1'
RUNTIME_SCOPE = 'explicit_project_python_configs_external_refs_v4'
LEGACY_SCOPE = 'legacy_v2_explicit_sha256sum_list_only'
TEXT_SUFFIXES = {'.json', '.yaml', '.yml', '.toml', '.ini', '.cfg', '.txt', '.md'}
REQUIRED_EXTERNAL = {'PHASE1_NATIVE_TRANSPORT_PATH', 'PHASE1_JOINT_REFERENCE_PATH',
                     'D5_PROJECTOR', 'WIRE_INIT', 'PIPELINE_INIT', 'WIRE_CODEC',
                     'WIRE_MAPPING', 'WIRE_STORE', 'WIRE_GRANULAR_STORE'}
EXCLUDED_DIRS = {'__pycache__', '.git', 'analysis_sources'}
SHA = re.compile(r'[a-f0-9]{64}')
COMMIT = re.compile(r'[a-f0-9]{40}')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()


def digest_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def read_regular(path, *, maximum=16 << 20):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'Absolute physical source/metadata path required')
    require(path.resolve(strict=True) == path, 'Source/metadata symlink or nonphysical ancestor rejected')
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= maximum, 'Bounded ordinary source/metadata file required')
    raw = path.read_bytes()
    after = path.lstat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'File changed during read')
    return raw


def file_sha(path):
    return digest_bytes(read_regular(path))


def json_file(path, expected_sha=None):
    raw = read_regular(path)
    if expected_sha is not None:
        require(SHA.fullmatch(expected_sha) and digest_bytes(raw) == expected_sha, 'Frozen metadata raw SHA differs')
    return json.loads(raw)


def write_exclusive(path, value):
    raw = json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False).encode() + b'\n'
    with Path(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return digest_bytes(raw)


def git_clean_snapshot(root):
    """Actually use Git on the allocated host, including untracked additions."""
    root = Path(root)
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True, timeout=60).strip()
    status = subprocess.check_output(['git', '-C', str(root), 'status', '--porcelain', '--untracked-files=all'], text=True, timeout=90)
    require(COMMIT.fullmatch(head) and not status.strip(), 'Exact committed clean worktree required')
    return {'head': head, 'porcelain': status, 'untracked_files': 'all'}


def source_scope(external_python, workflow_configs=()):
    """Caller explicitly lists NAME/path/expected SHA; never discovers a data tree."""
    require(set(external_python) >= REQUIRED_EXTERNAL, 'Both PHASE1 refs, D5 projector and six provider refs must be explicit')
    externals = {}
    for name, row in sorted(external_python.items()):
        require(re.fullmatch('[A-Z][A-Z0-9_]{0,80}', name) is not None, 'Explicit external source name required')
        require(set(row) == {'path', 'sha256'} and SHA.fullmatch(row['sha256']), 'Pinned external Python required')
        require(Path(row['path']).is_absolute() and Path(row['path']).suffix == '.py', 'Only explicitly named external .py files admitted')
        externals[name] = dict(row)
    configs = sorted(str(Path(name)) for name in workflow_configs)
    for name in configs:
        p = Path(name)
        require(not p.is_absolute() and '..' not in p.parts and p.parts[:1] == ('workflows',)
                and p.suffix.lower() in TEXT_SUFFIXES, 'Only explicit workflow text configuration paths admitted')
    require(len(configs) == len(set(configs)), 'Repeated workflow configuration')
    return {'schema': RUNTIME_SCOPE,
            'recursive_python_roots': ['current/phychem_mfm', 'current/tests', 'workflows'],
            'top_level_python_roots': ['tools/model_v3'],
            'recursive_text_roots': ['current/configs', 'configs'], 'text_suffixes': sorted(TEXT_SUFFIXES),
            'workflow_config_files': configs, 'external_python': externals,
            'excluded_directory_names': sorted(EXCLUDED_DIRS),
            'excluded_scope': ['analysis_sources', 'runs discovery', 'data/store/labels/weights/targets',
                               'third-party interpreter and venv source trees']}


def _source_paths(root, relative, *, recursive, suffixes):
    directory = root / relative
    require(directory.resolve(strict=True) == directory and directory.is_dir(), 'Physical declared source directory required')
    if recursive:
        for base, directories, names in os.walk(directory, followlinks=False):
            directories[:] = sorted(name for name in directories if name not in EXCLUDED_DIRS)
            for name in directories:
                require(not (Path(base) / name).is_symlink(), 'Symlink source directory rejected')
            for name in sorted(names):
                path = Path(base) / name
                if path.suffix.lower() in suffixes:
                    yield path
    else:
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() in suffixes and not path.is_dir():
                yield path


def runtime_snapshot(root, scope):
    root = Path(root).absolute()
    expected = source_scope(scope['external_python'], scope['workflow_config_files'])
    require(scope == expected, 'Unknown runtime source scope')
    paths = []
    for relative in scope['recursive_python_roots']:
        paths.extend(_source_paths(root, relative, recursive=True, suffixes={'.py'}))
    for relative in scope['top_level_python_roots']:
        paths.extend(_source_paths(root, relative, recursive=False, suffixes={'.py'}))
    for relative in scope['recursive_text_roots']:
        paths.extend(_source_paths(root, relative, recursive=True, suffixes=TEXT_SUFFIXES))
    paths.extend(root / name for name in scope['workflow_config_files'])
    files = {}
    for path in sorted(set(paths)):
        require(path.is_relative_to(root) and 'analysis_sources' not in path.relative_to(root).parts, 'Runtime scope escaped')
        raw = read_regular(path)
        raw.decode('utf-8')
        files[str(path.relative_to(root))] = digest_bytes(raw)
    externals = {}
    for name, ref in scope['external_python'].items():
        raw = read_regular(Path(ref['path']))
        raw.decode('utf-8')
        require(digest_bytes(raw) == ref['sha256'], 'Explicit external Python pin differs: ' + name)
        externals[name] = dict(ref)
    validate_external_model_paths(root, externals)
    return {'scope': scope, 'project_source_sha256': files, 'external_source_refs': externals}


def validate_external_model_paths(root, externals):
    """Read model declarations as syntax only; never import/execute model code."""
    provider = root / 'current/phychem_mfm/phase1/v3_wire_provider.py'
    if provider.exists():
        declarations = {}
        for node in ast.parse(read_regular(provider).decode('utf-8')).body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        declarations[target.id] = node.value
        export = declarations.get('DATA_EXPORT')
        require(isinstance(export, ast.Call) and isinstance(export.func, ast.Name) and export.func.id == 'Path'
                and len(export.args) == 1 and isinstance(export.args[0], ast.Constant)
                and isinstance(export.args[0].value, str), 'Provider external path declaration needs explicit review')
        source_pins = ast.literal_eval(declarations['DATA_SOURCE_SHA'])
        names = {'WIRE_INIT': 'wire_v1/__init__.py', 'PIPELINE_INIT': 'pipeline_v1/__init__.py',
                 'WIRE_CODEC': 'wire_v1/codec.py', 'WIRE_MAPPING': 'wire_v1/mapping.py',
                 'WIRE_STORE': 'wire_v1/store.py', 'WIRE_GRANULAR_STORE': 'pipeline_v1/granular_store.py'}
        require(set(source_pins) == set(names.values()), 'Provider import set changed; explicit external refs need review')
        for name, relative in names.items():
            require(externals[name]['path'] == str(Path(export.args[0].value) / relative)
                    and externals[name]['sha256'] == source_pins[relative], 'Caller ref differs from actual declared provider import: ' + name)
    bridge = root / 'current/phychem_mfm/phase1/v3_sampling_bridge.py'
    if bridge.exists():
        expected = None
        for node in ast.parse(read_regular(bridge).decode('utf-8')).body:
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'PROJECTION_SOURCE_SHA256' for target in node.targets):
                expected = ast.literal_eval(node.value)
        require(externals['D5_PROJECTOR']['sha256'] == expected, 'Caller projector SHA differs from model reviewed pin')


def capture_sources(root, scope, expected_commit, *, git_reader=git_clean_snapshot):
    first = git_reader(root)
    require(first['head'] == expected_commit, 'Runtime HEAD differs from frozen commit')
    snapshot = runtime_snapshot(root, scope)
    second = git_reader(root)
    require(first == second, 'Git identity/cleanliness changed during source inventory')
    return {'git': second, 'runtime': snapshot, 'runtime_sha256': digest_bytes(canonical(snapshot))}


def validate_source_observation(observation, contract):
    require(observation['git']['head'] == contract['code_sha'] and not observation['git']['porcelain'].strip()
            and observation['git']['untracked_files'] == 'all', 'Clean HEAD source observation differs')
    require(observation['runtime'] == contract['runtime'] and
            observation['runtime_sha256'] == digest_bytes(canonical(contract['runtime'])), 'Runtime bytes/file membership/scope differs')


def validate_assignment(assignment, code_sha):
    require(assignment['schema'] == ASSIGNMENT_SCHEMA and assignment['code_sha'] == code_sha
            and assignment['partitions'] == 1, 'Exact single-parent assignment required')
    sources = assignment['all_test_file_sha256']
    require(sources and all(SHA.fullmatch(value) for value in sources.values()), 'Exact complete test source pins required')
    rows = assignment['assignments']
    names = [name for row in rows for name in row['files']]
    require([row['index'] for row in rows] == list(range(1)) and all(row['files'] for row in rows)
            and len(names) == len(set(names)) and set(names) == set(sources), 'Assignment must be disjoint and exhaustive')
    require(assignment['per_job_output_budget_bytes'] == 2 * 1024**3, 'Original2GiB budget required')
    for name in names:
        p = Path(name)
        require(not p.is_absolute() and p.parts[:2] == ('current', 'tests') and '..' not in p.parts
                and len(p.parts) == 3 and p.name.startswith('test_') and p.suffix == '.py', 'Only core test module paths admitted')


def base_bindings(contract, index):
    return {'MODEL_V3_EXECUTION_SHA': contract['code_sha'],
            'MODEL_V3_CPU_EXECUTION_TREE': contract['tree'],
            'MODEL_V3_REGRESSION_RUNNER': contract['runner']['path'],
            'MODEL_V3_REGRESSION_RUNNER_SHA': contract['runner']['sha256'],
            'MODEL_V3_PARTITION_COUNT': '1', 'MODEL_V3_PARTITION_INDEX': str(index),
            'MODEL_V3_PARTITION_PLAN': contract['assignment']['path'],
            'MODEL_V3_PARTITION_PLAN_SHA': contract['assignment']['sha256'],
            'MODEL_V3_CONTROL_ROOT': contract['control_root'],
            'MODEL_V3_CONTROL_PLAN': contract['plan_path'],
            'MODEL_V3_CONTROL_CONTRACT_SHA': digest_bytes(canonical(contract)),
            'MODEL_V3_D5_PROJECTION_SOURCE': contract['runtime']['scope']['external_python']['D5_PROJECTOR']['path'],
            **{'MODEL_V3_' + name: row['path'] for name, row in contract['runtime']['scope']['external_python'].items()
               if name.startswith('PHASE1_')}}


def launch_bindings(plan, plan_sha, index):
    ref = plan['bindings'][index]
    return {**ref['values'], 'MODEL_V3_CONTROL_PLAN_SHA': plan_sha,
            'MODEL_V3_CONTROL_BINDING_PATH': ref['path'],
            'MODEL_V3_CONTROL_BINDING_SHA': ref['sha256']}


def validate_plan_metadata(plan):
    require(plan['schema'] == PLAN_SCHEMA, 'Explicit v4 control plan required')
    contract = plan['contract']
    require(plan['contract_sha256'] == digest_bytes(canonical(contract)), 'Control contract digest differs')
    require(COMMIT.fullmatch(contract['code_sha']) and len(plan['bindings']) == 1, 'Committed single-parent control contract required')
    for index, ref in enumerate(plan['bindings']):
        require(ref['path'] == contract['binding_paths'][index] and SHA.fullmatch(ref['sha256'])
                and ref['values'] == base_bindings(contract, index), 'Frozen binding values/index/path differ')
    return contract


def verify_frozen_plan(path, expected_sha, *, verify_runtime=True, git_reader=git_clean_snapshot):
    plan = json_file(path, expected_sha)
    contract = validate_plan_metadata(plan)
    require(str(Path(path)) == contract['plan_path'], 'Control plan path differs')
    assignment = json_file(contract['assignment']['path'], contract['assignment']['sha256'])
    validate_assignment(assignment, contract['code_sha'])
    runtime_tests = {name: sha for name, sha in contract['runtime']['project_source_sha256'].items()
                     if Path(name).parent == Path('current/tests') and Path(name).name.startswith('test_')}
    require(runtime_tests == assignment['all_test_file_sha256'], 'Runtime and assigned test file sets differ')
    for ref in [contract['runner'], contract['scheduler_script'], *contract['control_files']]:
        require(file_sha(ref['path']) == ref['sha256'], 'Runner/script/control source drift')
    for ref in plan['bindings']:
        require(json_file(ref['path'], ref['sha256']) == ref['values'], 'Raw binding SHA/values changed after freeze')
    if verify_runtime:
        actual = capture_sources(contract['tree'], contract['runtime']['scope'], contract['code_sha'], git_reader=git_reader)
        validate_source_observation(actual, contract)
    return plan, assignment


def validate_submission_metadata(plan, plan_sha, receipt, summary, supervisor, assignment):
    """Validate supplied metadata only. Caller must independently observe sacct."""
    contract = validate_plan_metadata(plan)
    job = receipt['job_id']
    require(isinstance(job, str) and job.isdigit(), 'Exact actual job ID string required')
    bindings = receipt['bindings']
    index = int(bindings['MODEL_V3_PARTITION_INDEX'])
    require(0 <= index < 1 and bindings == launch_bindings(plan, plan_sha, index), 'Submitted binding values/plan/runner differ')
    require(receipt['sbatch_returncode'] == 0 and receipt['cpus'] == 16, 'Confirmed16CPU submission required')
    require(receipt['script_sha256'] == contract['scheduler_script']['sha256'], 'Submitted scheduler bytes differ')
    node = receipt['node']
    require(re.fullmatch(r'compute-0-(2|8|9|1[0-9])', node) is not None, 'Explicit CPU node required')
    expected_sbatch = ['sbatch', '--parsable', '--partition=cpu', '--nodelist=' + node,
                       '--cpus-per-task=16', '--mem=32768M', contract['scheduler_script']['path']]
    require(receipt['argv'] == expected_sbatch and receipt['requested_memory_MiB'] == 32768,
            'Submitted scheduler arguments differ')
    require(summary['job_id'] == job == supervisor['job_id'], 'Job identity differs between path/receipt/result')
    require(summary['node'].split('.')[0] == node == summary['expected_node'], 'Actual/expected/submitted node differs')
    require(summary['code_commit'] == contract['code_sha'] and summary['partitions'] == 1
            and summary['partition_index'] == index, 'Commit/index/count differs from submitted contract')
    require(summary['runner_sha256'] == contract['runner']['sha256'] and
            summary['partition_plan_sha256'] == contract['assignment']['sha256'] and
            summary['control_plan_sha256'] == plan_sha, 'Executed runner/assignment/control plan differs')
    expected = {name: assignment['all_test_file_sha256'][name] for name in assignment['assignments'][index]['files']}
    require(summary['test_source_sha256'] == expected and summary['test_file_count'] == len(expected)
            and summary['all_test_file_sha256'] == assignment['all_test_file_sha256'], 'Exact per-part test file set differs')
    shard_files = [name for row in summary['shards'] for name in row['files']]
    require(len(shard_files) == len(set(shard_files)) and set(shard_files) == set(expected), 'Executed shard file coverage differs')
    require(summary['status'] == 'PASS' and summary.get('failure') is None and summary['counts']['failures'] == 0 and summary['counts']['errors'] == 0
            and summary['counts']['tests'] > 0 and all(row['returncode'] == 0 for row in summary['shards']), 'Tests did not succeed')
    require(supervisor['status'] == 'COMPLETED' and supervisor['exit_code'] == 0
            and supervisor['first_failure'] is None and not supervisor['remaining'], 'Supervision did not close')
    require(supervisor['command'] == expected_supervisor_command(bindings, node, job,
            python=contract['python'], runs=contract['runs']), 'Supervised command differs from frozen binding')
    require(summary['source_scope'] == RUNTIME_SCOPE, 'Explicit runtime scope required')
    validate_source_observation(summary['sources_before'], contract)
    validate_source_observation(summary['sources_after'], contract)
    require(summary['sources_before'] == summary['sources_after'], 'Before/after source observations differ')
    validate_counts(summary)
    return index


def validate_counts(summary):
    require(summary['shards'], 'Executed shard metadata required')
    total = {key: sum(row['counts'][key] for row in summary['shards']) for key in ('tests', 'failures', 'errors', 'skipped')}
    require(total == summary['counts'] and total['tests'] > 0 and not total['failures'] and not total['errors'], 'Shard/summary test counts differ or failed')
    for row in summary['shards']:
        require(set(row['counts']) == {'tests', 'failures', 'errors', 'skipped'} and row['returncode'] == 0
                and all(type(value) is int and value >= 0 for value in row['counts'].values())
                and row['counts']['skipped'] <= row['counts']['tests'], 'Invalid shard exit/counts')


def expected_supervisor_command(bindings, node, job, *, python='/share/home/zixiao/.conda/envs/chemprop/bin/python', runs=RUNS):
    return [python, '-u', '-B', bindings['MODEL_V3_REGRESSION_RUNNER'],
            '--root', bindings['MODEL_V3_CPU_EXECUTION_TREE'], '--output', str(Path(runs) / ('integration_tests_' + job)),
            '--code-commit', bindings['MODEL_V3_EXECUTION_SHA'], '--workers', '4', '--expected-node', node,
            '--partitions', bindings['MODEL_V3_PARTITION_COUNT'], '--partition-index', bindings['MODEL_V3_PARTITION_INDEX'],
            '--partition-plan', bindings['MODEL_V3_PARTITION_PLAN'], '--partition-plan-sha256', bindings['MODEL_V3_PARTITION_PLAN_SHA']]


def validate_artifact_paths(runs, receipt_path, job, index):
    runs, receipt_path = Path(runs), Path(receipt_path)
    require(receipt_path.parent == runs and re.fullmatch(r'[A-Za-z0-9_]+_part' + str(index) + r'_submission(?:_v4)?\.json', receipt_path.name), 'Submission receipt path/index differs')
    require(isinstance(job, str) and job.isdigit(), 'Numeric path job identity required')
    return runs / ('integration_tests_' + job) / 'summary.json', runs / ('integration_supervisor_' + job + '.json')


def validate_legacy_submission(assignment, assignment_path, assignment_sha, runner_sha, scheduler_sha, receipt, summary, supervisor):
    """Legacy v2 control only; runtime provenance is separately the original pin list."""
    validate_assignment(assignment, assignment['code_sha'])
    bindings, job, node = receipt['bindings'], receipt['job_id'], receipt['node']
    index = int(bindings['MODEL_V3_PARTITION_INDEX'])
    require(0 <= index < 8 and bindings['MODEL_V3_PARTITION_COUNT'] == '8', 'Legacy bounded partition binding differs')
    require(bindings['MODEL_V3_PARTITION_PLAN'] == str(assignment_path) and bindings['MODEL_V3_PARTITION_PLAN_SHA'] == assignment_sha,
            'Mixed legacy frozen assignment plans')
    require(bindings['MODEL_V3_REGRESSION_RUNNER_SHA'] == runner_sha == summary['runner_sha256'], 'Legacy runner drift/mix')
    require(receipt['script_sha256'] == scheduler_sha and receipt['sbatch_returncode'] == 0 and receipt['cpus'] == 16, 'Legacy script/submission differs')
    require(re.fullmatch(r'compute-0-(2|8|9|1[0-9])', node) and summary['node'].split('.')[0] == node == summary['expected_node'], 'Legacy node differs')
    require(isinstance(job, str) and job.isdigit() and summary['job_id'] == job == supervisor['job_id'], 'Legacy job identity differs')
    require(summary['code_commit'] == bindings['MODEL_V3_EXECUTION_SHA'] == assignment['code_sha']
            and summary['partition_index'] == index and summary['partitions'] == 8
            and summary['partition_plan_sha256'] == assignment_sha, 'Legacy commit/index/count/plan differs')
    expected = {name: assignment['all_test_file_sha256'][name] for name in assignment['assignments'][index]['files']}
    require(summary['all_test_file_sha256'] == assignment['all_test_file_sha256']
            and summary['test_source_sha256'] == expected and summary['test_file_count'] == len(expected), 'Legacy exact partition test source set differs')
    names = [name for row in summary['shards'] for name in row['files']]
    require(len(names) == len(set(names)) and set(names) == set(expected), 'Legacy actual shard file coverage differs')
    require(summary['status'] == 'PASS' and supervisor['status'] == 'COMPLETED' and supervisor['exit_code'] == 0
            and supervisor['first_failure'] is None and not supervisor['remaining'], 'Legacy execution/supervision did not close')
    require(supervisor['command'] == expected_supervisor_command(bindings, node, job), 'Legacy supervised command differs from binding/path')
    validate_counts(summary)
    return index


def validate_partition_union(summaries):
    require(len(summaries) == 1 and {row['partition_index'] for row in summaries} == set(range(1)), 'Missing or duplicate partition')
    sources, all_sources = {}, summaries[0]['all_test_file_sha256']
    for row in summaries:
        require(row['all_test_file_sha256'] == all_sources, 'Mixed full test source sets')
        for name, sha in row['test_source_sha256'].items():
            require(name not in sources, 'Repeated test module across partitions')
            sources[name] = sha
    require(sources == all_sources, 'Missing full-suite test source coverage')


def validate_accounting(raw, jobs):
    require(len(jobs) == len(set(jobs)) and len(jobs) == 1, 'Exact one Slurm parent required')
    records = {}
    for text in raw.splitlines():
        if not text.strip():
            continue
        row = text.split('|')
        require(len(row) >= 6 and row[0] in jobs and row[0] not in records, 'Unexpected/repeated accounting identity')
        require(row[1:4] == ['zixiao', 'COMPLETED', '0:0'], 'Parent accounting not successful terminal')
        require(int(row[4]) >= 0 and int(row[5]) == 16, 'Actual parent allocation differs')
        records[row[0]] = row
    require(set(records) == set(jobs), 'Missing parent accounting')
    return records


def legacy_source_list(raw):
    rows = {}
    for text in raw.decode('utf-8').splitlines():
        match = re.fullmatch(r'([a-f0-9]{64})  (.+)', text)
        require(match is not None, 'Malformed legacy source pin line')
        sha, name = match.groups()
        require(name not in rows and not Path(name).is_absolute() and '..' not in Path(name).parts, 'Duplicate/unsafe legacy source path')
        rows[name] = sha
    require(rows, 'Empty legacy explicit source pin list')
    return rows


def validate_legacy_sources(pin_raw, log_raw):
    """Old shell only persisted before pins plus sha256sum --check OK lines."""
    rows = legacy_source_list(pin_raw)
    lines = log_raw.decode('utf-8').splitlines()
    require(not any(': FAILED' in line or 'computed checksum did NOT match' in line for line in lines), 'Legacy source check failure')
    for name in rows:
        require(lines.count(name + ': OK') == 1, 'Legacy after-check OK evidence missing or repeated: ' + name)
    return {'scope': LEGACY_SCOPE, 'before_sha256': rows, 'after_sha256sum_check': 'one_exact_OK_line_per_listed_source',
            'after_digest_values_persisted': False, 'full_runtime_inventory_available': False,
            'pin_file_sha256': digest_bytes(pin_raw), 'job_log_sha256': digest_bytes(log_raw)}
