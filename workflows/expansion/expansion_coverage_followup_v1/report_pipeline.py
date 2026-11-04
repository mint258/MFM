"""Actual closed dependencies and native-block budgets for three report phases."""
import argparse
import copy
import importlib.util
import os
from pathlib import Path
import sys
from ..alpha_runtime_v1 import common as Q
from ..uff3_alpha_runtime_v1.prepare_pipeline import upstream, terminal_account, literal
from ..uff3_alpha_runtime_v1 import budget
from .prepare_pipeline import A, B, D, BASE, PY, ACCOUNT, read

REPORTS = Path('/gfshome/alpha/pubchem_expansion_20261103/reports')
PHASES = ('baseline-report', 'rn-populations', 'batch-graph-report')


def before_receipt(meta):
    """Only closed small scientific attempt receipts; never open201 SQLite."""
    plan = read(meta['plan_reference']); matches = []
    for path in Path(meta['output_directory']).glob('attempt*.receipt.json'):
        ref = Q.reference(path); value = read(ref)
        if (value.get('schema') == 'EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1'
                and value.get('status') == 'COMPLETE' and value.get('reference_role') == 'before'
                and value.get('resource_plan') == meta['plan_reference']
                and value.get('launcher_startup_proof_reference') == meta['startup_proof_reference']):
            Q.need(value['queries'] == value['projection']['rows'] == 1000000
                   and value['nearest_similarity_exact'] is True
                   and value['baseline_receipt'] == plan['baseline_receipt']
                   and value['reference_manifest'] == plan['reference_manifest']
                   and value['decontamination_applied_to_sample'] is False
                   and value['candidate_pool_release_authorized'] is False,
                   'Actual fixed1M scientific EOF/membership/reference, not a full-pool release')
            matches.append(ref)
    Q.need(len(matches) == 1, 'Exactly one completed actual producer scientific attempt for its real plan/startup')
    return matches[0]


def result(meta, phase):
    root = Path(meta['output_directory']); job = meta['runtime']['job_id']
    if phase == 'before': return before_receipt(meta)
    name = 'compiled_coverage_manifest.json' if phase == 'after' else ('source_manifest.json' if phase == 'source' else 'manifest.json')
    ref = Q.reference(root / name); value = read(ref)
    Q.need(str(value['actual_parent']['job_id']) == job and value['actual_parent']['uid'] == Q.UID,
           'Actual dependency result job and UID')
    if phase == 'source':
        Q.need(value['schema'] == 'PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1'
               and value['molecules'] == 2500000 and value['molecules_by_stream'] == {'R':1250000,'N':1250000}
               and value['resource_plan'] == meta['plan_reference'], 'Actual full217 ordered graph source')
    elif phase == 'after':
        Q.need(value['schema'] == 'EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1' and value['status'] == 'COMPLETE'
               and value['producer_schema'] == 'CPP_FULL_MANIFEST_FIXED1M_COVERAGE_V1'
               and value['queries'] == value['projection']['rows'] == 1000000
               and value['reference_role'] == 'after' and value['reference_molecules'] == 3696122
               and value['nearest_similarity_exact'] is True and value['resource_plan'] == meta['plan_reference']
               and value['launcher_startup_proof_reference'] == meta['startup_proof_reference'],
               'Actual complete223 same-fixed1M augmented-reference coverage')
    else:
        Q.need(phase == 'rn' and value['schema'] == 'PUBCHEM_RN_DISTRIBUTION_SOURCES_V1'
               and value['status'] == 'COMPLETE' and value['molecules_by_stream'] == {'R':1250000,'N':1250000}
               and value['plan_reference'] == meta['plan_reference'], 'Actual complete R/N statistical graph sources')
    return ref


def partition(config, phase, inline):
    Q.need(phase in PHASES, 'Only three report phases')
    remaining = inline['remaining_reserved_bytes_by_scope']['reports']
    defaults = {'baseline-report':1500000000, 'rn-populations':1500000000,
                'batch-graph-report':inline['scope_total_caps_bytes']['reports']}
    requested = config.get('private_caps_bytes', {}).get(phase, defaults[phase])
    Q.need(type(requested) is int and requested > 0, 'Explicit positive private report cap')
    cap = min(requested, remaining) if phase == 'batch-graph-report' else requested
    Q.need(0 < cap <= remaining, 'Full report cap does not fit native remaining reports allowance; never truncate source data')
    return cap, inline['other_future_reserved_bytes_for_each_scope']['reports'] + remaining - cap


def statistics_closure(config, deployment):
    ref = config.get('statistics_actual_review_reference') or Q.reference(B / 'current_baseline_Common_statistics_1885190_root_actual_v1.json')
    review = read(ref); original = read(review['original_population_tables_receipt_reference'])
    refs = original['source_references']
    Q.need(len(refs) == 10 and all(item in deployment['code_references'] for item in refs),
           'Current immutable deployment must include all ten original190 statistics sources')
    for item in refs:
        name = Path(item['path']).stem
        module = 'workflows.expansion.distribution_report_v1' + ('' if name == '__init__' else '.' + name)
        spec = importlib.util.find_spec(module)
        Q.need(spec is not None and Path(spec.origin).resolve() == Path(item['path']).resolve(),
               'Actual statistics namespace must resolve the unchanged190 ten-source capsule')
    return ref


def build(config, phase, tag, inputs, control, *, upstream_job=None, upstream_tag=None):
    Q.need(phase in PHASES, 'Explicit report preparation phase')
    config = copy.deepcopy(config); inputs = Path(inputs); cache = {}
    command = config.get('accounting_command_prefix', ACCOUNT)
    Q.need(command == ACCOUNT, 'Actual Alpha login sacct RPC, never compute-local localhost6819')
    def load(job, stage, closed=True):
        key = (str(job), stage)
        if key not in cache: cache[key] = upstream(str(job), stage, control)
        meta = cache[key]
        if closed and 'accounting_reference' not in meta:
            folder = inputs / literal(str(job), stage); folder.mkdir()
            meta['accounting_reference'] = terminal_account(str(job), folder, command)
        return meta
    def declared(name, *, primary=False):
        job = upstream_job if primary and upstream_job is not None else config[name + '_job_id']
        stage = upstream_tag if primary and upstream_tag is not None else config[name + '_tag']
        return load(job, stage)
    def binding(meta, scope):
        return dict(scope=scope, **{key:meta[key] for key in ('runtime','plan_reference','startup_proof_reference','accounting_reference')})
    # Read only the actual201 plan/startup for exclusion during RN prep; do not wait for201.
    before_meta = load(config.get('background_before_job_id', config['before_job_id']),
                       config.get('background_before_tag', config['before_tag']), False)
    Q.need(before_meta['runtime']['job_id'] == '1885201', 'Actual201 must remain explicitly excluded from block credits')
    active = list(config.get('excluded_active_allocations', []))
    if not any(str(b['runtime']['job_id']) == '1885201' for b in active):
        active.append({key:before_meta[key] for key in ('runtime','plan_reference','startup_proof_reference')})
    allocations = [b for b in config.get('closed_allocations', []) if str(b['runtime']['job_id']) != '1885201']
    for item in config.get('closed_allocation_sources', []):
        if str(item['job_id']) == '1885201': continue
        allocations.append(binding(load(str(item['job_id']), item['tag']), item['scope']))
    deployment_ref = config.get('deployment_reference') or config['source_deployment_reference']
    resources = read(config['resources_reference']); deployment = read(deployment_ref)
    Q.need(Q.reference(__file__) in deployment['code_references'], 'Current immutable report preparation source pin')
    plan = copy.deepcopy(resources)
    stat_ref = statistics_closure(config, deployment)
    if phase == 'rn-populations':
        source = declared('source', primary=True)
        plan['ordered_source_manifest_reference'] = result(source, 'source'); allocations.append(binding(source, 'exact'))
        plan['schema'] = 'PUBCHEM_RN_DISTRIBUTION_SOURCE_PLAN_V1'
    else:
        before = declared('before', primary=phase == 'baseline-report')
        plan['before_coverage_reference'] = result(before, 'before')
        plan.update(schema='PUBCHEM_DISTRIBUTION_FOLLOWUP_REPORT_PLAN_V1',
                    report_scope='baseline' if phase == 'baseline-report' else 'batch_graph')
        if phase == 'batch-graph-report':
            after = declared('after'); rn = declared('rn', primary=True)
            plan['after_coverage_reference'] = result(after, 'after')
            plan['rn_population_sources_reference'] = result(rn, 'rn')
            allocations.extend((binding(after, 'exact'), binding(rn, 'reports')))
    census = budget.census(config['baseline_budget_reference'], allocations, active, inputs / 'native_closed_blocks.json')
    inline = budget.inline(config['baseline_budget_reference'], census)
    cap, other = partition(config, phase, inline)
    literal('0', tag); scope = REPORTS / tag
    versions = config.get('analysis_versions', {})
    baseline_version = versions.get('baseline-report', 'current183_190_baseline_' + tag)
    batch_version = versions.get('batch-graph-report', 'current183_190_batch_graph_' + tag)
    Q.need(baseline_version != batch_version, 'Independent baseline and batch graph analysis versions')
    plan.update(workers=16, software_rss_budget_bytes=48 << 30, parent_rss_cap_bytes=40 << 30,
        minimum_node_available_bytes=24 << 30, sqlite_cache_bytes=1 << 30,
        sql_memory_bytes=32 << 30, spill_cap_bytes=min(2000000000, cap),
        output_scope_root=str(scope), output_directory=str(scope / 'producer_LAUNCHER_ASSIGN_REAL_JOB_ID'),
        output_cap_bytes=cap, other_future_reserved_bytes=other,
        minimum_free_bytes=inline['minimum_free_after_all_future_bytes'],
        scope_key='distribution_' + phase.replace('-', '_') + '_' + tag,
        statistics_actual_review_reference=stat_ref,
        analysis_version=baseline_version if phase == 'baseline-report' else batch_version,
        code_references=deployment['code_references'], source_deployment_reference=deployment_ref,
        reviewed_storage_budget_reference=config['baseline_budget_reference'], native_closed_census_reference=census,
        report_storage_partition=dict(future_budget=inline, private_report_cap_bytes=cap,
            remaining_reports_before_private_cap_bytes=inline['remaining_reserved_bytes_by_scope']['reports'],
            all_other_remaining_reserved_bytes=inline['other_future_reserved_bytes_for_each_scope']['reports'],
            other_future_reserved_bytes=other, no_source_sampling_or_truncation=True))
    if 'runtime_profile_reference' in config: plan['runtime_profile_reference'] = config['runtime_profile_reference']
    plan.pop('execution_argv', None)
    return Q.write(inputs / 'input_plan.json', plan)


def launch_argv(template, phase, entry, tag, control, *, python=PY, base=BASE,
                launcher=D / 'node_launcher_rpc_v3_resume.py', rpc=D / 'gluster_readonly_rpc.py'):
    Q.need(phase in PHASES, 'Only report/source native dispatch')
    literal('0', tag)
    module = 'workflows.expansion.expansion_coverage_followup_v1.' + ('rn_populations' if phase == 'rn-populations' else 'report')
    return [str(python), '-I', '-B', str(launcher), '--template', str(template), '--base-root', str(base),
            '--entry', str(entry), '--module', module, '--tag', tag, '--control-root', str(control), '--gluster-rpc-program', str(rpc)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', required=True, choices=PHASES); p.add_argument('--config', required=True, type=Path)
    p.add_argument('--upstream-job'); p.add_argument('--upstream-tag')
    p.add_argument('--entry', required=True, type=Path); p.add_argument('--tag', required=True)
    p.add_argument('--control-root', type=Path, default=B / 'node_epochs'); p.add_argument('--python', type=Path, default=PY)
    p.add_argument('--base-root', type=Path, default=BASE); p.add_argument('--launcher', type=Path, default=D / 'node_launcher_rpc_v3_resume.py')
    p.add_argument('--gluster-rpc-program', type=Path, default=D / 'gluster_readonly_rpc.py'); args = p.parse_args()
    job = os.environ.get('SLURM_JOB_ID', '')
    Q.need(os.getuid() == Q.UID and sys.flags.isolated and job.isdigit()
           and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= 16 and not os.environ.get('SLURM_JOB_GPUS'),
           'Only actual isolated16CPU Alpha report preparation')
    literal(job, args.tag); inputs = args.control_root / (args.tag + '_inputs_job_' + job); inputs.mkdir(mode=0o700)
    template = build(Q.load(args.config), args.phase, args.tag, inputs, args.control_root,
                     upstream_job=args.upstream_job, upstream_tag=args.upstream_tag)
    argv = launch_argv(template['path'], args.phase, args.entry, args.tag, args.control_root,
                       python=args.python, base=args.base_root, launcher=args.launcher, rpc=args.gluster_rpc_program)
    os.chdir(args.base_root); os.execv(str(args.python), argv)


if __name__ == '__main__': main()
