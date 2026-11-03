"""Root-managed complete-population distribution and exact coverage reports."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import socket
import threading
import uuid
from . import aggregate as A
from .functional_groups import recipe
from .io import canonical, load, need, reference, verify, write_new


def resources(plan, out):
    used = 0
    for path in out.rglob('*'):
        try:
            if path.is_file():
                used += path.stat().st_size
        except FileNotFoundError:
            # This connection's SQLite DELETE journal may naturally disappear
            # during a commit. Counting it as absent over-reserves future space.
            continue
    need(used < plan['output_cap_bytes'], 'Declared complete report/output storage allowance reached')
    need('quota_snapshot' in plan and 'quota_authority' in plan, 'Actual account-quota publisher and authority are required')
    if plan['quota_authority'].get('kind') == 'lustre':
        from ..completion_runtime_v1.lustre_quota import budget_check
    else:
        from ..completion_runtime_v1.quota import budget_check
    budget_check(plan, used, out)
    mem = {line.split(':')[0]: int(line.split()[1]) * 1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')}
    need(mem['MemAvailable'] >= plan['minimum_node_available_bytes'], 'Actual available node memory is below the reviewed reserve')
    pending, seen, rss = [os.getpid()], set(), 0
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        try:
            rss += int(Path('/proc', str(pid), 'statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE')
            pending.extend(map(int, Path('/proc', str(pid), 'task', str(pid), 'children').read_text().split()))
        except FileNotFoundError:
            continue
    need(rss < plan['software_rss_budget_bytes'], 'Actual report process-tree RSS exceeds its reviewed budget')


def run(plan_path, stage):
    plan = load(plan_path)
    need(plan['schema'] == 'EXPANSION_DISTRIBUTION_PLAN_V1' and plan['analysis_version'], 'Versioned Root distribution plan required')
    need(socket.gethostname().startswith('compute-') or os.environ.get('SLURM_JOB_ID'), 'Data analysis must execute on a compute node/allocation')
    workers = plan['workers']
    allowed = min(len(os.sched_getaffinity(0)), int(os.environ.get('SLURM_CPUS_PER_TASK', len(os.sched_getaffinity(0)))))
    need(type(workers) is int and 1 <= workers <= allowed, 'Workers exceed real CPU affinity/allocation')
    node = socket.gethostname().split('.')[0]
    partition = os.environ.get('SLURM_JOB_PARTITION')
    if node == 'compute-0-21':
        need(os.environ.get('SLURM_JOB_ID') and 'cpu21_authorization_reference' in plan, 'Actual Slurm allocation and explicit CPU21 user authorization required')
        approval = load(verify(plan['cpu21_authorization_reference']))
        need(approval['schema'] == 'PUBCHEM_EXPANSION_USER_CPU21_AUTHORIZATION_V1' and approval['status'] == 'USER_APPROVED' and approval['node'] == node and approval['partition'] == partition == 'all' and approval['GPU_used'] is False and approval['paid_server_used'] is False, 'Actual node21/all CPU-only approval required; never claim cpu-partition execution')
    out = Path(plan['output_directory'])
    out.mkdir(parents=True, exist_ok=True)
    recipe_value = recipe()
    recipe_path = out / 'functional_group_recipe.json'
    if recipe_path.exists():
        need(load(recipe_path) == recipe_value, 'Pinned functional-group definitions changed on resume')
    else:
        write_new(recipe_path, recipe_value)
    version_path = out / 'analysis_scope.json'
    scope = {'analysis_version': plan['analysis_version'], 'fingerprint_recipe': A.RECIPE, 'functional_group_recipe_reference': reference(recipe_path)}
    if version_path.exists():
        need(load(version_path) == scope, 'Analysis version/recipe changed in an existing output root')
    else:
        write_new(version_path, scope)
    resources(plan, out)
    done, errors = threading.Event(), []

    def observe():
        while not done.wait(15):
            try:
                resources(plan, out)
            except BaseException as exc:
                errors.append(repr(exc))
                return

    def check():
        need(not errors, 'Resource observation stopped new analysis batches: ' + str(errors))

    monitor = threading.Thread(target=observe, daemon=True)
    monitor.start()
    db = A.open_state(out / 'counted_statistics.sqlite')
    try:
        A.RESOURCE_CHECK = check
        if stage in ('populations', 'all'):
            for ref in plan['population_manifests']:
                check()
                result = A.ingest_population(db, verify(ref), workers, plan.get('batch_rows', 1024))
                print(canonical(result), flush=True)
        populations = {name: __import__('json').loads(raw) for name, raw in db.execute('SELECT name,manifest FROM populations WHERE complete=1')}
        if stage in ('nearest', 'all'):
            for ref in plan['nearest_manifests']:
                check()
                result = A.ingest_nearest(db, verify(ref), populations)
                print(canonical(result), flush=True)
        if stage in ('report', 'baseline_report', 'all'):
            from . import render
            check()
            baseline_only = stage == 'baseline_report'
            A.completion(db, baseline_only=baseline_only)
            attempt = out / ('report_' + uuid.uuid4().hex)
            attempt.mkdir(exist_ok=False)
            summary, state, fg, artifacts = render.tables(db, attempt, baseline_only=baseline_only)
            artifacts.extend(render.figures(db, attempt, state, fg, groups=tuple(summary['populations'])))
            artifacts.append(render.report_baseline(attempt, summary) if baseline_only else render.report(attempt, summary))
            artifacts.append(write_new(attempt / 'functional_group_recipe.json', recipe_value))
            check()
            resources(plan, out)
            source = Path(__file__).parent
            receipt = {'schema': 'EXPANSION_DISTRIBUTION_REPORT_RECEIPT_V1', 'status': 'ALL_REQUIRED_DISTRIBUTION_NUMERICS_AND_FIGURES_COMPLETE', 'plan_reference': reference(plan_path), 'population_manifest_references': populations, 'comparison_manifest_references': summary['comparison_manifests'], 'functional_group_recipe_reference': reference(recipe_path), 'source_references': [reference(p) for p in sorted(source.glob('*.py'))], 'artifacts': artifacts, 'full_common_not_a_sample': True, 'all_source_rows_and_exact_molecular_memberships_counted': True, 'nearest_search_is_exact_and_complete': True, 'screening_or_ranking_decisions_changed': False, 'conformers_D_labels_or_final_batch_release_claimed': False, 'actual_parent_accounting': 'PENDING_ROOT_TERMINAL_ACCOUNTING'}
            receipt['report_scope']='TASK2_1_BASELINE' if baseline_only else 'TASK2_1_AND_2_9_COMPLETE_GRAPH_BATCH'
            receipt['augmented_reference_before_after_complete']=not baseline_only
            receipt['population_manifest_references']=summary['population_manifests']
            receipt['actual_parent']={'pid':os.getpid(),'uid':os.getuid(),'node':node,'partition':partition,'SlurmJobID':os.environ.get('SLURM_JOB_ID')}
            receipt['cpu21_authorization_reference']=plan.get('cpu21_authorization_reference') if node=='compute-0-21' else None
            ref = write_new(attempt / 'receipt.json', receipt)
            print(canonical({'receipt_reference': ref, 'status': receipt['status']}), flush=True)
            return receipt
    finally:
        db.close()
        done.set()
        monitor.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--stage', choices=('populations', 'nearest', 'baseline_report', 'report', 'all'), default='all')
    args = parser.parse_args()
    run(args.plan, args.stage)


if __name__ == '__main__':
    main()
