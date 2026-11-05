"""One-pass CPU integration regression; external production inputs stay unavailable."""
from __future__ import annotations
import ast
from concurrent.futures import ThreadPoolExecutor
import hashlib
import inspect
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path(os.environ.get('MERGE_VALIDATION_OUTPUT', '/tmp/mfm-merge-validation'))
EXTERNAL = 'User authorized skipping unavailable server/X-drive resources'


def skip_external(*args, **kwargs):
    import pytest
    pytest.skip(EXTERNAL + ': frozen preparation reference or owned Slurm allocation')


def pytest_collection_modifyitems(items):
    """Explicit environment exclusions; production code and assertions stay intact."""
    import pytest
    for item in items:
        module = item.module
        path = Path(str(item.path)).resolve()
        relative = path.relative_to(ROOT).as_posix()
        reason = None
        if item.originalname == 'test_joint_genuine_adamw_matches_immutable_52c_reference_weights_moments_controller_rng':
            reason = 'external immutable stage52 joint reference is not shipped in Git'
        if relative == 'current/tests/test_model_v3_wandb_layout.py' and item.originalname == 'test_actual_offline_sdk_layout_passes_fixed_profiler_accounting':
            reason = 'fixed profiler path exists only on the development server'
        # These suites expose CLI globals pointing at real server-only contracts.
        if relative == 'workflows/data_v1_final/pprime/test_pprime.py':
            reason = 'requires external pprime configuration, engine contract and SB2 source'
        if relative == 'workflows/data_v1_final/pprime/vector_audit/test_v1.py' and 'CONFIG' in item.obj.__code__.co_names:
            reason = 'requires the external registered vector-audit configuration'
        if relative == 'workflows/data_v1_final/labels/streaming_v1/test_semantics.py' and 'CONFIG' in item.obj.__code__.co_names:
            reason = 'requires external legacy label configuration'
        try:
            source = inspect.getsource(item.obj)
        except (OSError, TypeError):
            source = ''
        if ('SLURM_JOB_ID' in source and ('Root must' in source or 'owned Slurm' in source)):
            reason = 'requires an actual owned Slurm allocation; GitHub Actions is not Slurm'
        if reason:
            item.add_marker(pytest.mark.skip(reason=EXTERNAL + ': ' + reason))
        # Mark the exact optional helper unavailable when it is actually called.
        # Imported aliases are patched as well, without suppressing independent tests.
        for name, value in list(vars(module).items()):
            if not inspect.isfunction(value):
                continue
            if value.__name__ == '_builder' and value.__module__.endswith('test_phase1_full_corpus_original_metrics'):
                setattr(module, name, skip_external)
            elif value.__name__ in {'run_cli_pair', '_run_cli'} and value.__module__.endswith(('test_model_v3_training_entry', 'test_model_v3_pilot_entry')):
                setattr(module, name, skip_external)
        if relative in {
            'workflows/data_v1_final/export/wire_v1/tests.py',
            'workflows/data_v1_final/export/pipeline_v1/tests.py',
            'workflows/data_v1_final/export/pipeline_v1/test_parent_keys_v2.py',
        } and getattr(module, 'ROOT', 'unset') is None:
            module.ROOT = Path(tempfile.mkdtemp(prefix='mfm-synthetic-', dir=OUTPUT))


def run_group(task):
    index, files = task
    name = f'group_{index:03d}'
    log, xml = OUTPUT / (name + '.log'), OUTPUT / (name + '.xml')
    command = [sys.executable, '-B', '-m', 'pytest', *map(str, files), '-q',
               '-p', 'no:cacheprovider', '-p', 'merge_validation',
               '--junitxml=' + str(xml), '--basetemp=' + str(OUTPUT / (name + '_tmp'))]
    started = time.monotonic()
    # Test modules use a mixture of package imports and historical sibling imports.
    # One workflow module per process keeps their same-name helpers isolated.
    env = {**os.environ, 'PYTHONPATH': os.pathsep.join([
        str(ROOT / '.github'), str(ROOT), str(ROOT / 'current'),
        str(ROOT / 'current/tests'), str(files[0].parent), os.environ.get('PYTHONPATH', '')])}
    with log.open('wb') as stream:
        try:
            result = subprocess.run(command, cwd=ROOT / 'current', env=env, stdin=subprocess.DEVNULL,
                                    stdout=stream, stderr=subprocess.STDOUT, timeout=1200)
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            returncode = 124
    counts = dict(tests=0, failures=0, errors=0, skipped=0)
    skipped = []
    if xml.exists():
        tree = ET.parse(xml).getroot()
        for suite in tree.iter('testsuite'):
            for key in counts:
                counts[key] += int(suite.attrib.get(key, 0))
        for case in tree.iter('testcase'):
            node = case.find('skipped')
            if node is not None:
                skipped.append({'test': case.attrib, 'reason': node.attrib.get('message', '')})
    row = dict(group=index, files=[str(p.relative_to(ROOT)) for p in files], returncode=returncode,
               counts=counts, skipped=skipped, elapsed_seconds=time.monotonic()-started)
    (OUTPUT / (name + '.json')).write_text(json.dumps(row, indent=2) + '\n')
    print(json.dumps({'group': index, 'returncode': returncode, 'counts': counts}), flush=True)
    return row


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    core = sorted((ROOT / 'current/tests').glob('test_*.py'))
    groups, sizes = [[] for _ in range(4)], [0] * 4
    for path in sorted(core, key=lambda p: (-p.stat().st_size, p.name)):
        i = min(range(4), key=lambda j: (sizes[j], j))
        groups[i].append(path)
        sizes[i] += path.stat().st_size
    workflow = sorted((ROOT / 'workflows').rglob('test*.py'))
    groups.extend([path] for path in workflow)
    files = [p for group in groups for p in group]
    inventory = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    (OUTPUT / 'inventory.json').write_text(json.dumps(inventory, indent=2) + '\n')
    print(json.dumps({'core_modules': len(core), 'workflow_modules': len(workflow), 'workers': 2}), flush=True)
    started = time.monotonic()
    with ThreadPoolExecutor(max_workers=2) as executor:
        rows = list(executor.map(run_group, enumerate(groups)))
    counts = {key: sum(r['counts'][key] for r in rows) for key in ('tests','failures','errors','skipped')}
    result = dict(status='PASS' if all(r['returncode']==0 for r in rows) else 'FAIL',
                  commit=os.environ.get('GITHUB_SHA'), tested_tree=os.environ.get('MERGED_TREE'),
                  core_modules=len(core), workflow_modules=len(workflow),
                  counts=counts, passed=counts['tests']-counts['failures']-counts['errors']-counts['skipped'],
                  elapsed_seconds=time.monotonic()-started, groups=rows)
    (OUTPUT/'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k:v for k,v in result.items() if k!='groups'}), flush=True)
    return int(result['status'] != 'PASS')


if __name__ == '__main__':
    raise SystemExit(main())

