"""Prepare direct CPU producer continuations inside a real Alpha allocation."""
import argparse
import json
import os
from pathlib import Path
import stat
import subprocess
import time

from ..alpha_runtime_v1 import common as Q

A = Path('/gfshome/alpha/codex_data_v1_20261026')
B = A / 'control/pubchem_expansion_runtime_20261103'
D = A / 'control/pubchem_completion_environment_20261103'
BASE = A / 'code/pubchem_completion_20261103_497c584'
PY = A / 'software/pubchem_completion_20261103_venv/bin/python'
EXACT = Path('/gfshome/alpha/pubchem_expansion_20261103/exact')


def terminal_account(job, folder):
    argv = ['sacct', '-j', job, '--parsable2',
            '--format=JobIDRaw%40,State%24,ExitCode,UID,ElapsedRaw,AllocCPUS,NodeList%128']
    result = subprocess.run(argv, capture_output=True, text=True)
    Q.need(result.returncode == 0, 'Actual upstream Slurm accounting unavailable: ' + result.stderr)
    lines = result.stdout.splitlines()
    Q.need(lines, 'Actual accounting output is empty')
    header = lines[0].split('|')
    rows = [dict(zip(header, line.split('|'))) for line in lines[1:] if line]
    parents = [row for row in rows if row.get('JobIDRaw') == job]
    Q.need(len(parents) == 1 and parents[0]['State'] == 'COMPLETED'
           and parents[0]['ExitCode'] == '0:0' and int(parents[0]['UID']) == Q.UID,
           'Same real completed Alpha upstream parent required')
    raw = folder / 'upstream_native_sacct.txt'
    with raw.open('x') as stream:
        stream.write(result.stdout)
    account = folder / 'upstream_native_accounting.json'
    ref = Q.write(account, dict(endpoint=Q.ENDPOINT, uid=Q.UID, actual_parents=parents,
                               raw_sacct_reference=Q.reference(raw)))
    from ..uff3_alpha_runtime_v1.terminal import parent
    parent(dict(endpoint=Q.ENDPOINT, uid=Q.UID, job_id=job), ref)
    return ref


def source_reservations(plan):
    """Credit closed exact outputs once; active background scopes get no credit."""
    scope = Path(plan['output_scope_root'])
    Q.need(scope != EXACT and scope.is_relative_to(EXACT), 'Private source scope in exact aggregate required')
    budget = Q.load(Q.verify(plan['reviewed_storage_budget_reference']))
    cap = budget['scope_total_caps_bytes']['exact']
    excludes = {scope, *(Path(p) for p in plan['background_scope_exclusions'])}
    Q.need(all(p != EXACT and p.is_relative_to(EXACT) for p in excludes), 'Explicit inner scope exclusions')
    cutoff = time.time() - 60
    credit = 0
    seen = set()
    for base, dirs, files in os.walk(EXACT, followlinks=False):
        base = Path(base)
        dirs[:] = [name for name in dirs if base / name not in excludes]
        for path in [base, *(base / name for name in files)]:
            if any(path == e or e in path.parents for e in excludes):
                continue
            value = path.lstat()
            Q.need(value.st_uid == Q.UID and (stat.S_ISREG(value.st_mode) or stat.S_ISDIR(value.st_mode)),
                   'Own literal native closed exact scope metadata required')
            identity = value.st_dev, value.st_ino
            if identity in seen:
                continue
            seen.add(identity)
            if max(value.st_mtime_ns, value.st_ctime_ns) < int(cutoff * 1000000000):
                credit += value.st_blocks * 512
    Q.need(credit + plan['output_cap_bytes'] <= cap, 'Source reservation must fit remaining exact aggregate cap')
    plan['other_future_reserved_bytes'] = budget['other_future_reserved_bytes_for_each_scope']['exact'] + cap - credit - plan['output_cap_bytes']
    plan['outer_closed_scope_budget_basis'] = dict(
        scope=str(EXACT), closed_prequery_allocated_bytes=credit, cutoff_unix_seconds=cutoff,
        excluded_scopes=sorted(map(str, excludes)), all_outer_cap_bytes=cap,
        source='ACTUAL_NATIVE_METADATA_AFTER_UPSTREAM_C0_NO_NEW_ROOT_APPROVAL')


def prepare(plan, mode, inputs, upstream, shard_paths):
    if mode == 'nn':
        Q.need(upstream is not None, 'Actual filter manifest required')
        value = Q.load(upstream)
        Q.need(value['schema'] == 'PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1' and value['status'] == 'COMPLETE',
               'Whole closed filter producer required')
        from .partition import assignment
        assignment(plan)
        plan['filtered_pool_reference'] = Q.reference(upstream)
    elif mode == 'rank':
        from .aggregate import aggregate
        Q.need(len(shard_paths) == 2, 'Both completed NN work manifests required')
        plan['novelty_reference'] = aggregate([Q.reference(path) for path in shard_paths],
                                               inputs / 'full_novelty_manifest.json')
    else:
        Q.need(upstream is not None, 'Actual ranking receipt required')
        rank = Q.load(upstream)
        Q.need(rank['schema'] == 'expansion_nested_queues_v1'
               and rank['status'] == 'CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED'
               and rank['actual_parent']['uid'] == Q.UID, 'Actual whole R/N producer required')
        job = str(rank['actual_parent']['job_id'])
        startup = Path(rank['resource_plan']['path']).parent / 'startup.json'
        proof = Q.load(startup)
        Q.need(proof['request']['producer_plan_reference'] == rank['resource_plan']
               and str(proof['job_id']) == job and proof['uid'] == Q.UID, 'Actual rank startup/source binding')
        plan['ranking_receipt'] = Q.reference(upstream)
        plan['ranking_completed'] = dict(
            runtime=dict(endpoint=Q.ENDPOINT, uid=Q.UID, job_id=job),
            accounting_reference=terminal_account(job, inputs), startup_proof_reference=Q.reference(startup))
        filtered = Q.load(Q.verify(rank['filtered_pool']))
        pool = Q.load(Q.verify(filtered['source_pool_receipt']))
        plan['pubchem_version'] = 'pubchem-source-sha256:' + pool['source_snapshot_sha256']
        source_reservations(plan)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', required=True, choices=['nn', 'rank', 'source'])
    parser.add_argument('--seed', required=True, type=Path)
    parser.add_argument('--upstream', type=Path)
    parser.add_argument('--shard-manifest', action='append', type=Path, default=[])
    parser.add_argument('--entry', required=True, type=Path)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    Q.need(os.getuid() == Q.UID and os.environ.get('SLURM_JOB_ID') and __import__('sys').flags.isolated,
           'Only actual isolated Alpha allocated producer preparation')
    Q.need('/' not in args.tag and '..' not in args.tag, 'Literal stage tag')
    plan = Q.load(args.seed)
    inputs = B / 'node_epochs' / (args.tag + '_inputs_job_' + os.environ['SLURM_JOB_ID'])
    inputs.mkdir(mode=0o700)
    plan = prepare(plan, args.mode, inputs, args.upstream, args.shard_manifest)
    path = inputs / 'input_plan.json'
    Q.write(path, plan)
    module = ('workflows.expansion.uff3_alpha_runtime_v1.typed_source_entry' if args.mode == 'source'
              else 'workflows.expansion.alpha_sharded_novelty_v1.run')
    argv = [str(PY), '-I', '-B', str(D / 'node_launcher_rpc_v3_resume.py'), '--template', str(path),
            '--base-root', str(BASE), '--entry', str(args.entry), '--module', module, '--tag', args.tag,
            '--control-root', str(B / 'node_epochs'), '--gluster-rpc-program', str(D / 'gluster_readonly_rpc.py')]
    os.chdir(BASE)
    os.execv(str(PY), argv)


if __name__ == '__main__':
    main()
