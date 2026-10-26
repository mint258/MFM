"""Freeze the unchanged stable assignment algorithm; submit only exact frozen bytes."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

from identity_revision_v4 import file_ref, load_fixed_control, verify_source_pins

HERE = Path(__file__).resolve().parent

PYTHON = '/share/home/zixiao/.conda/envs/chemprop/bin/python'


def stable_assignment(tree, code, baseline_path, reserve_mib):
    """Retain old module-to-parent assignment, measured last bytes + declared reserve.

    Deliberately identical planning algorithm to prepare_stable_regression_v1.
    Last sampled bytes and reserves do not establish an output peak bound.
    """
    baseline = json_file(baseline_path)
    require(baseline['status'] == 'PASS' and len(baseline['job_ids']) == 8
            and not baseline['counts']['failures'] and not baseline['counts']['errors'], 'Successful eight-parent baseline required')
    current = {str(path.relative_to(tree)): file_sha(path) for path in sorted((tree / 'current/tests').glob('test_*.py'))}
    rows, seen, refs = [None] * 8, {}, []
    for job in baseline['job_ids']:
        summary_path, supervisor_path = RUNS / ('integration_tests_' + job) / 'summary.json', RUNS / ('integration_supervisor_' + job + '.json')
        summary, supervisor = json_file(summary_path), json_file(supervisor_path)
        require(summary['job_id'] == job == supervisor['job_id'] and summary['status'] == 'PASS'
                and summary['code_commit'] == baseline['code_commit'] and supervisor['status'] == 'COMPLETED'
                and supervisor['exit_code'] == 0 and supervisor['first_failure'] is None
                and not supervisor['remaining'], 'Exact successful baseline parents required')
        index, observed = summary['partition_index'], supervisor['last_total_bytes']
        require(type(index) is int and 0 <= index < 8 and rows[index] is None and 0 <= observed < 2 * 1024**3, 'Valid unique baseline partition/last bytes required')
        rows[index] = {'index': index, 'files': [], 'baseline_last_observed_combined_bytes': observed,
                       'new_reserved_bytes': 0, 'planned_bytes': observed, 'baseline_job_id': job}
        for name, sha in summary['test_source_sha256'].items():
            require(name not in seen, 'Overlapping baseline tests')
            seen[name] = index, sha
        refs.extend({'path': str(path), 'sha256': file_sha(path)} for path in (summary_path, supervisor_path))
    require({name: value[1] for name, value in seen.items()} == baseline['test_source_sha256'], 'Baseline full source coverage differs')
    reserve, limit, changed = reserve_mib * 1024**2, 2 * 1024**3 - 64 * 1024**2, []
    for name, sha in current.items():
        if name in seen:
            index, previous = seen[name]
            rows[index]['files'].append(name)
            if previous != sha:
                rows[index]['new_reserved_bytes'] += reserve
                rows[index]['planned_bytes'] += reserve
                changed.append(name)
    new = sorted(set(current) - set(seen))
    for name in new:
        eligible = [row for row in rows if row['planned_bytes'] + reserve <= limit]
        require(eligible, 'No measured headroom; profile/split without relaxing2GiB')
        row = min(eligible, key=lambda value: (value['planned_bytes'], value['index']))
        row['files'].append(name)
        row['new_reserved_bytes'] += reserve
        row['planned_bytes'] += reserve
    require(all(row['files'] and row['planned_bytes'] <= limit for row in rows), 'Every partition needs declared headroom')
    for row in rows:
        row['files'].sort()
    return {'schema': 'model_v3_stable_regression_plan_v1', 'code_sha': code, 'partitions': 8,
            'all_test_file_sha256': current, 'assignments': rows,
            'baseline_certificate': {'path': str(baseline_path), 'sha256': file_sha(baseline_path)},
            'baseline_source_refs': refs, 'new_test_files': new, 'changed_test_files': changed,
            'removed_test_files': sorted(set(seen) - set(current)), 'per_job_output_budget_bytes': 2 * 1024**3,
            'per_new_or_changed_module_reserve_bytes': reserve, 'old_successful_assignments_retained': True,
            'capacity_is_a_conservative_plan_not_peak_proof': True}


def parse_external(values):
    result = {}
    for value in values:
        name, path, sha = value.split('=', 2)
        require(name not in result, 'Duplicate external source name')
        result[name] = {'path': path, 'sha256': sha}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-pins', type=Path, required=True)
    parser.add_argument('--source-pins-sha256', required=True)
    parser.add_argument('--action', choices=['freeze', 'submit'], required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--tree', type=Path)
    parser.add_argument('--baseline', default='wire_provider_postmerge_v1')
    parser.add_argument('--scheduler-script', type=Path)
    parser.add_argument('--new-module-reserve-MiB', type=int, default=512)
    parser.add_argument('--external-python', action='append', default=[], metavar='NAME=ABS_PATH=SHA256')
    parser.add_argument('--workflow-config', action='append', default=[])
    parser.add_argument('--plan-sha256')
    parser.add_argument('--indices', type=int, nargs='+')
    parser.add_argument('--node')
    args = parser.parse_args()
    pins = verify_source_pins(args.source_pins, args.source_pins_sha256)
    control = load_fixed_control(pins)
    # Import the original algorithms only after their exact source admission.
    for name in ('CONTROL', 'RUNS', 'PLAN_SCHEMA', 'REQUIRED_EXTERNAL', 'base_bindings',
                 'canonical', 'capture_sources', 'digest_bytes', 'file_sha', 'git_clean_snapshot',
                 'json_file', 'launch_bindings', 'require', 'source_scope', 'validate_assignment',
                 'verify_frozen_plan', 'write_exclusive'):
        globals()[name] = getattr(control, name)
    require(re.fullmatch('[A-Za-z0-9_]{1,64}', args.label) and re.fullmatch('[A-Za-z0-9_]{1,64}', args.baseline), 'Simple fresh labels required')
    plan_path = RUNS / (args.label + '_control_v4.json')
    if args.action == 'freeze':
        require(not plan_path.exists() and args.tree is not None and args.scheduler_script is not None
                and 16 <= args.new_module_reserve_MiB <= 1024, 'Fresh bounded explicit freeze required')
        tree = args.tree.absolute()
        head = git_clean_snapshot(tree)['head']
        scope = source_scope(parse_external(args.external_python), args.workflow_config)
        sources = capture_sources(tree, scope, head)
        assignment = stable_assignment(tree, head, RUNS / (args.baseline + '_complete.json'), args.new_module_reserve_MiB)
        validate_assignment(assignment, head)
        assignment_path = RUNS / (args.label + '_assignment_v4.json')
        assignment_sha = write_exclusive(assignment_path, assignment)
        binding_paths = [str(RUNS / (args.label + f'_part{index}_bindings_v4.json')) for index in range(8)]
        # Control sources include admission, supervision and its real helper imports.
        helpers = Path('/share/home/zixiao/descriptor_analysis/MFM_model_v3_sa1_a/tools/model_v3')
        controls = [*sorted(CONTROL.glob('*.py')), RUNS / 'submit_cpu_task_v2.py',
                    RUNS / 'run_cpu_test_supervised_v2.py', RUNS / 'run_cpu_supervised_v3.py',
                    *(helpers / name for name in ('runtime_monitor.py', 'run_supervised.py', 'private_runtime_storage.py'))]
        controls = sorted(set([*controls, *(Path(ref['path']) for ref in pins['runtime_sources']),
                               args.source_pins.absolute()]))
        contract = {'tree': str(tree), 'code_sha': head, 'runs': str(RUNS), 'control_root': str(CONTROL),
                    'plan_path': str(plan_path), 'python': PYTHON, 'runtime': sources['runtime'],
                    'assignment': {'path': str(assignment_path), 'sha256': assignment_sha},
                    'runner': {'path': str(HERE / 'run_regression_worker_identity_v4.py'), 'sha256': file_sha(HERE / 'run_regression_worker_identity_v4.py')},
                    'scheduler_script': {'path': str(args.scheduler_script.absolute()), 'sha256': file_sha(args.scheduler_script.absolute())},
                    'control_files': [{'path': str(path), 'sha256': file_sha(path)} for path in controls],
                    'binding_paths': binding_paths,
                    'receipt_paths': [str(RUNS / (args.label + f'_part{index}_submission_v4.json')) for index in range(8)],
                    'capacity_is_a_conservative_plan_not_peak_proof': True}
        bindings = []
        for index, path in enumerate(binding_paths):
            values = base_bindings(contract, index)
            bindings.append({'path': path, 'sha256': write_exclusive(path, values), 'values': values})
        plan = {'schema': PLAN_SCHEMA, 'contract': contract, 'contract_sha256': digest_bytes(canonical(contract)), 'bindings': bindings}
        plan_sha = write_exclusive(plan_path, plan)
        # A new/removed source or control change during freeze fails and leaves evidence.
        verify_frozen_plan(plan_path, plan_sha)
        print(json.dumps({'status': 'FROZEN_NOT_EXECUTED', 'plan': str(plan_path), 'plan_sha256': plan_sha,
                          'code_sha': head, 'runtime_scope': scope['schema'],
                          'planned_MiB': [round(row['planned_bytes'] / 1024**2, 2) for row in assignment['assignments']]}))
    else:
        require(args.plan_sha256 and args.indices and len(set(args.indices)) == len(args.indices)
                and all(index in range(8) for index in args.indices)
                and args.node is not None and re.fullmatch(r'compute-0-(2|8|9|1[0-9])', args.node),
                'Pinned plan, explicit CPU node and exact unique wave indices required')
        plan, _ = verify_frozen_plan(plan_path, args.plan_sha256)
        contract = plan['contract']
        wave = RUNS / (args.label + '_wave_v4_' + '_'.join(map(str, args.indices)) + '.json')
        require(not wave.exists(), 'Inspect preserved actual partial submissions before any retry')
        submitted = []
        try:
            for index in args.indices:
                # Recheck all files immediately before each admission/submission.
                verify_frozen_plan(plan_path, args.plan_sha256)
                launch_path = RUNS / (args.label + f'_part{index}_launch_v4.json')
                values = launch_bindings(plan, args.plan_sha256, index)
                launch_sha = write_exclusive(launch_path, values)
                require(json_file(launch_path, launch_sha) == values, 'Just-written launch binding drift')
                receipt = Path(contract['receipt_paths'][index])
                subprocess.run([PYTHON, '-B', str(RUNS / 'submit_cpu_task_v2.py'), '--node', args.node,
                                '--memory-MiB', '32768', '--script', contract['scheduler_script']['path'],
                                '--bindings', str(launch_path), '--output', str(receipt)], check=True)
                submitted.append({'receipt': str(receipt), 'launch_bindings': str(launch_path), 'launch_sha256': launch_sha})
        finally:
            write_exclusive(wave, {'plan': str(plan_path), 'plan_sha256': args.plan_sha256,
                                   'indices': args.indices, 'actual_confirmed_submissions': submitted})


if __name__ == '__main__':
    main()
