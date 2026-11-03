"""Durable original502 Arrow projections and unchanged external minCID merge."""
import argparse
import concurrent.futures as cf
import fcntl
import multiprocessing as mp
from pathlib import Path
import time
from ..alpha_runtime_v1.common import canonical, load, need, reference, verify, write
from ..alpha_runtime_v1.guard import Guard
from ..alpha_runtime_v1.profile import admit
from ..pubchem_closed500_bulk_v2 import project as P
from .plan import validate


def project_fragments(plan, selected, guard):
    directory = Path(plan['output_directory']) / 'fragments'
    directory.mkdir(parents=True, exist_ok=True)
    closed, todo = [], []
    for spec in plan['fragments']:
        if spec['fragment_id'] not in selected:continue
        guard.check()
        receipt = P.closed_fragment(directory, spec)
        (todo if receipt is None else closed).append(spec if receipt is None else receipt)
    with cf.ProcessPoolExecutor(max_workers=plan['workers'], mp_context=mp.get_context('spawn')) as pool:
        pending, source = {}, iter(todo)
        def dispatch():
            guard.check()
            spec = next(source, None)
            if spec is not None:pending[pool.submit(P.project_fragment, spec, str(directory), plan['batch_rows'])] = spec
        for unused in range(plan['workers']):dispatch()
        while pending:
            done, unused = cf.wait(pending, timeout=1, return_when=cf.FIRST_COMPLETED)
            guard.check()
            for future in done:
                spec = pending.pop(future); receipt = future.result(); closed.append(receipt)
                print(canonical({'event': 'ALPHA_ORIGINAL_TYPED_FRAGMENT_CLOSED', 'fragment_id': spec['fragment_id'], 'closed_this_scope': len(closed), 'declared_scope': len(selected)}).decode(), flush=True)
                dispatch()
    guard.check()
    return closed


def projection_manifest(plan, receipts):
    by_id = {r['source_fragment']['fragment_id']: r for r in receipts}
    need(len(by_id) == len(plan['fragments']) == 502 and set(by_id) == {f['fragment_id'] for f in plan['fragments']}, 'All actual502 durable projections required')
    counts = {k: sum(r['all_source_counts'][k] for r in receipts) for k in plan['source_counts']}
    need(counts == plan['source_counts'] and sum(counts.values()) == 124857440, 'Original Alpha full row/category census must conserve')
    out = Path(plan['output_directory']); directory = out / 'fragments'
    return {'schema': 'PUBCHEM_ALL_CLOSED_PROJECTIONS_V2', 'status': 'COMPLETE_ACCEPTED_PROJECTIONS_NO_POOL_RELEASE', 'producer_schema': 'PUBCHEM_ALPHA_ORIGINAL502_TYPED_COVERAGE_V1', 'source_endpoint': plan['endpoint'], 'source_uid': plan['uid'], 'logical_descriptor_count': 500, 'fragment_count': 502, 'source_rows': 124857440, 'counts': counts, 'coverage_reference': plan['coverage_reference'], 'frozen_manifest_reference': plan['frozen_manifest_reference'], 'source_snapshot_sha256': plan['source_snapshot_sha256'], 'original_science_references': plan['original_science_references'], 'fragments': [reference(directory / f['fragment_id'] / 'complete.json') for f in plan['fragments']], 'accepted_parquets': [by_id[f['fragment_id']]['accepted_parquet'] for f in plan['fragments']], 'source_typed_bodies_full_SHA_verified': all(r['source_whole_SHA_verified_on_same_FD'] is True for r in receipts), 'source_journals_replayed_again': False, 'chemistry_recomputed': False, 'old_partial_SQLite_reused': False, 'technical_UNKNOWN_is_not_chemical_exclusion': True}


def merge_original(manifest, output, plan, guard):
    from ..pubchem_closed500_bulk_v2 import merge as M
    old_resource, old_verify = M.resource_check, M.verify
    def runtime(unused_plan, unused_out):guard.check()
    def guarded_verify(ref):
        guard.check(); path = old_verify(ref); guard.check(); return path
    M.resource_check, M.verify = runtime, guarded_verify
    try:
        return M.materialize(manifest, output, plan['workers'], plan['duckdb_memory_bytes'], plan, inputs_verified=False)
    finally:
        M.resource_check, M.verify = old_resource, old_verify


def run(plan_path, action, fragment_ids=None):
    plan = validate(load(plan_path)); actual = admit(plan)
    out = Path(plan['output_directory']); out.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (out / 'parent.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if action in ('baseline', 'filter', 'query_projection'):
            if action == 'baseline':
                from .baseline import run as downstream
            elif action == 'filter':
                from .filter import run as downstream
            else:
                from .query import run as downstream
            return downstream(plan_path)
        guard = Guard(plan); began = time.monotonic()
        try:
            scope = {'coverage_reference': plan['coverage_reference'], 'source_snapshot_sha256': plan['source_snapshot_sha256'], 'fragments': plan['fragments']}
            path = out / 'scope.json'
            if path.exists():need(load(path) == scope, 'Alpha output namespace belongs to another original snapshot')
            else:write(path, scope)
            all_ids = {f['fragment_id'] for f in plan['fragments']}
            selected = all_ids if fragment_ids is None else set(fragment_ids)
            need(selected and selected <= all_ids, 'Only explicit original fragment IDs may be selected')
            if action in ('project', 'all'):
                receipts = project_fragments(plan, selected, guard)
                if selected == all_ids:
                    result = projection_manifest(plan, receipts); manifest = out / 'projection_manifest.json'
                    if manifest.exists():need(load(manifest) == result, 'Closed original502 projection changed')
                    else:write(manifest, result)
                else:
                    result = {'schema': 'ALPHA_ORIGINAL502_PARTIAL_PARENT_SCOPE_V1', 'status': 'SELECTED_ORIGINAL_FRAGMENTS_CLOSED_NOT_GLOBAL_POOL_RELEASE', 'selected_fragment_ids': sorted(selected), 'closed_fragments': len(receipts)}
                    from .pilot import domain_observation
                    observations = [domain_observation(r, guard) for r in receipts]
                    result['actual_H_only_domain_observations'] = observations
                    write(out / ('parent_' + actual['job_id'] + '_' + str(actual['pid']) + '.json'), dict(result, actual_parent=actual, plan_reference=reference(plan_path), runtime=guard.receipt()))
                    return result
            if action in ('merge', 'all'):
                manifest = out / 'projection_manifest.json'; value = load(manifest)
                need(value['producer_schema'] == 'PUBCHEM_ALPHA_ORIGINAL502_TYPED_COVERAGE_V1' and value['coverage_reference'] == plan['coverage_reference'] and value['source_typed_bodies_full_SHA_verified'] is True, 'Full actual Alpha502 projection required before dedup')
                result = merge_original(manifest, out / 'unfiltered_pool', plan, guard)
            guard.check()
            receipt = {'schema': 'ALPHA_ORIGINAL502_ADMITTED_PARENT_RECEIPT_V1', 'status': 'DECLARED_STAGE_COMPLETE_PENDING_ROOT_ACTUAL_C0', 'stage': action, 'actual_parent': actual, 'plan_reference': reference(plan_path), 'coverage_reference': plan['coverage_reference'], 'projection_manifest': reference(out / 'projection_manifest.json'), 'minimum_CID_pool_receipt': reference(out / 'unfiltered_pool/receipt.json') if action in ('merge', 'all') else None, 'wall_seconds': time.monotonic() - began, 'runtime': guard.receipt(), 'chemistry_recomputed': False, 'journal_replayed': False, 'old_SQLite_modified': False, 'decontamination_or_ranking_release': False}
            write(out / ('parent_' + actual['job_id'] + '_' + str(actual['pid']) + '.json'), receipt)
            return receipt
        finally:guard.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', required=True); p.add_argument('--action', choices=('project', 'merge', 'all', 'baseline', 'filter', 'query_projection'), default='all')
    p.add_argument('--fragment-ids', help='Optional explicit original fragment IDs for a bounded actual cost/compatibility scope; cannot emit global closure')
    a = p.parse_args(); need(not a.fragment_ids or a.action in ('project', 'all'), 'Merge cannot narrow the source scope')
    run(a.plan, a.action, None if a.fragment_ids is None else a.fragment_ids.split(','))


if __name__ == '__main__':main()
