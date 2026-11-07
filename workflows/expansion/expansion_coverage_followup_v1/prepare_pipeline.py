"""Prepare actual closed after-reference dependencies, then exec NodeLauncher."""
import argparse
import copy
import os
from pathlib import Path
import sys
from ..alpha_runtime_v1 import common as Q
from ..uff3_alpha_runtime_v1.prepare_pipeline import upstream, terminal_account, literal
from ..alpha_sharded_novelty_v1.prepare_pipeline import source_reservations, EXACT

A = Path('/gfshome/alpha/codex_data_v1_20261026')
B = A / 'control/pubchem_expansion_runtime_20261103'
D = A / 'control/pubchem_completion_environment_20261103'
BASE = A / 'code/pubchem_completion_20261103_497c584'
PY = A / 'software/pubchem_completion_20261103_venv/bin/python'
ACCOUNT = ['ssh', '-n', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5', '218.192.171.238', 'sacct']
RESOURCE_KEYS = ('endpoint', 'uid', 'runtime_profile_reference', 'quota_snapshot', 'quota_authority',
                 'minimum_node_available_bytes', 'minimum_free_bytes', 'reviewed_storage_budget_reference',
                 'parent_transport_manifest')


def read(ref):
    Q.need(ref['bytes'] <= 2 << 20, 'Small pinned preparation metadata only')
    return Q.load(Q.verify(ref))


def resource_plan(config, phase, tag):
    resources = read(config['resources_reference'])
    before = read(config['coverage_template_reference'])
    Q.need(before['schema'] == 'PUBCHEM_EXACT_SCIENTIFIC_COVERAGE_PLAN_V1'
           and before['reference_role'] == 'before' and before['reference_manifest'] == config['before_reference_manifest'],
           'Actual original201 fixed1M plan and exact196 reference, never its active SQLite')
    Q.need(phase in ('pack-after', 'coverage-after'), 'Only two explicit after-coverage phases')
    literal('0', tag)
    plan = copy.deepcopy(before if phase == 'coverage-after' else resources)
    for key in RESOURCE_KEYS:
        if key in resources:
            plan[key] = copy.deepcopy(resources[key])
    for key in ('runtime_profile_reference', 'reviewed_storage_budget_reference'):
        if key in config:
            plan[key] = copy.deepcopy(config[key])
    deployment = read(config['deployment_reference'])
    Q.need(plan['endpoint'] == Q.ENDPOINT and plan['uid'] == Q.UID
           and Q.reference(__file__) in deployment['code_references'],
           'Actual Alpha resource identity and current immutable preparation source')
    scope = EXACT / tag
    background = set(config.get('background_scope_exclusions', []))
    # Never walk/stat the live201 tree when crediting other closed exact outputs.
    background.add(before['output_directory'])
    plan.update(workers=16, output_scope_root=str(scope),
        output_directory=str(scope / ('producer_LAUNCHER_ASSIGN_REAL_JOB_ID')),
        output_cap_bytes=4_000_000_000, parent_rss_cap_bytes=8 << 30,
        software_rss_budget_bytes=48 << 30, minimum_node_available_bytes=24 << 30,
        sqlite_cache_bytes=256 << 20, sql_memory_bytes=6 << 30, spill_cap_bytes=1_000_000_000,
        worker_rss_cap_bytes=2 << 30, background_scope_exclusions=sorted(background),
        code_references=deployment['code_references'], source_deployment_reference=config['deployment_reference'],
        scope_key='fixed1M_' + phase.replace('-', '_') + '_' + tag)
    plan.pop('execution_argv', None)
    plan.pop('launcher_startup_proof_reference', None)
    if phase == 'pack-after':
        plan.update(schema='PUBCHEM_EXACT_REFERENCE_PACK_PLAN_V1', reference_role='after',
                    base_reference_manifest=config['before_reference_manifest'])
        for key in ('input_manifest', 'reference_manifest', 'baseline_receipt', 'baseline_actual_review_reference'):
            plan.pop(key, None)
    else:
        plan.update(schema='PUBCHEM_EXACT_SCIENTIFIC_COVERAGE_PLAN_V1', reference_role='after',
                    backend_adoption_reference=config['backend_adoption_reference'])
        plan.pop('reference_manifest', None)
    return plan


def build(config, phase, job, upstream_tag, tag, inputs, control):
    config = copy.deepcopy(config); inputs = Path(inputs)
    command = config.get('accounting_command_prefix', ACCOUNT)
    Q.need(command == ACCOUNT, 'Use explicit Alpha login sacct RPC; compute-local localhost6819 is unavailable')
    meta = upstream(job, upstream_tag, control)
    folder = inputs / literal(job, upstream_tag); folder.mkdir()
    account = terminal_account(job, folder, command)
    plan = resource_plan(config, phase, tag)
    root = Path(meta['output_directory'])
    if phase == 'pack-after':
        source_ref = Q.reference(root / 'source_manifest.json'); source = read(source_ref)
        projection_ref = Q.reference(root / 'augmentation_manifest.json'); projection = read(projection_ref)
        Q.need(source['schema'] == 'PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1'
               and source['molecules'] == 2500000 and source['molecules_by_stream'] == {'R':1250000,'N':1250000}
               and str(source['actual_parent']['job_id']) == job and source['resource_plan'] == meta['plan_reference']
               and projection['schema'] == 'EXPANSION_ORDERED_RN_REFERENCE_PROJECTION_V1'
               and projection['status'] == 'COMPLETE' and projection['source_manifest'] == source_ref
               and projection['projection']['rows'] == 2500000,
               'Actual completed source217 all2.5M graph projection, not a UFF success subset')
        plan['input_manifest'] = projection_ref
    else:
        packed_ref = Q.reference(root / 'manifest.json'); packed = read(packed_ref)
        Q.need(packed['schema'] == 'EXPANSION_EXACT_AUGMENTED_REFERENCE_V1' and packed['status'] == 'COMPLETE'
               and packed['base_reference_manifest'] == config['before_reference_manifest']
               and packed['molecules'] == 3696122 and packed['added_molecules'] == 2500000
               and packed['original_reference_ordinals_preserved_as_exact_prefix'] is True
               and packed['resource_plan'] == meta['plan_reference']
               and packed['launcher_startup_proof_reference'] == meta['startup_proof_reference'],
               'Actual closed native pack parent and full prefix-preserving after reference')
        plan['reference_manifest'] = packed_ref
    plan['upstream_completed'] = dict(**meta, accounting_reference=account)
    source_reservations(plan)
    return Q.write(inputs / 'input_plan.json', plan)


def launch_argv(template, phase, entry, tag, control, *, python=PY, base=BASE,
                launcher=D / 'node_launcher_rpc_v3_resume.py', rpc=D / 'gluster_readonly_rpc.py'):
    Q.need(phase in ('pack-after', 'coverage-after'), 'Explicit native producer phase')
    literal('0', tag)
    module = ('workflows.expansion.exact_nn_cached_v1.pack_reference' if phase == 'pack-after'
              else 'workflows.expansion.expansion_coverage_followup_v1.coverage')
    return [str(python), '-I', '-B', str(launcher), '--template', str(template), '--base-root', str(base),
            '--entry', str(entry), '--module', module, '--tag', tag, '--control-root', str(control),
            '--gluster-rpc-program', str(rpc)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--phase', required=True, choices=('pack-after', 'coverage-after'))
    p.add_argument('--config', required=True, type=Path)
    p.add_argument('--upstream-job'); p.add_argument('--upstream-tag')
    p.add_argument('--entry', required=True, type=Path); p.add_argument('--tag', required=True)
    p.add_argument('--control-root', type=Path, default=B / 'node_epochs')
    p.add_argument('--python', type=Path, default=PY); p.add_argument('--base-root', type=Path, default=BASE)
    p.add_argument('--launcher', type=Path, default=D / 'node_launcher_rpc_v3_resume.py')
    p.add_argument('--gluster-rpc-program', type=Path, default=D / 'gluster_readonly_rpc.py')
    args = p.parse_args(); job = os.environ.get('SLURM_JOB_ID', '')
    Q.need(os.getuid() == Q.UID and sys.flags.isolated and job.isdigit()
           and int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) >= 16
           and not os.environ.get('SLURM_JOB_GPUS'), 'Only actual isolated16CPU Alpha Slurm preparation')
    config = Q.load(args.config)
    upstream_job = args.upstream_job or config.get('source_job_id' if args.phase == 'pack-after' else 'pack_job_id')
    upstream_tag = args.upstream_tag or config.get('source_tag' if args.phase == 'pack-after' else 'pack_tag')
    Q.need(isinstance(upstream_job, str) and isinstance(upstream_tag, str), 'Actual dependency job and tag required')
    literal(job, args.tag)
    inputs = args.control_root / (args.tag + '_inputs_job_' + job); inputs.mkdir(mode=0o700)
    template = build(config, args.phase, upstream_job, upstream_tag, args.tag, inputs, args.control_root)
    argv = launch_argv(template['path'], args.phase, args.entry, args.tag, args.control_root,
                       python=args.python, base=args.base_root, launcher=args.launcher, rpc=args.gluster_rpc_program)
    os.chdir(args.base_root); os.execv(str(args.python), argv)


if __name__ == '__main__': main()
