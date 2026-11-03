"""Measure a complete accepted Common cache using fixed baseline prefix queries.

This operational measurement releases no candidate pool and is never a full
scientific baseline receipt. It uses the unchanged exact engine and workers.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time

from ..common import load, reference, require, dump_new
from ..portable_sources_v1.transport import bind_plan, verify, provenance
from ..alpha_runtime_v1.guard import Guard
from .contracts import baseline_query
from .coverage import validate_reference
from .engine import WIDTH, ALGORITHM, file_frame
from .run import allocation_guard, rows
from .workers import exact_batches


def execute(plan_path, startup_proof):
    plan = load(plan_path)
    require(plan.get('schema') == 'ALPHA_FULL_COMMON_EXACT_CACHE_PROFILE_PLAN_V1',
            'Explicit non-releasing operational profile plan required')
    bind_plan(plan)
    startup_memory = allocation_guard(plan)
    proof = load(startup_proof)
    require(proof['uid'] == os.getuid() == 1264
            and str(proof['job_id']) == os.environ['SLURM_JOB_ID']
            and proof['request']['producer_plan_reference'] == reference(plan_path)
            and proof['request']['execution_argv'] == plan['execution_argv']
            and reference(Path(__file__)) in proof['request']['source_references'],
            'Actual Alpha launcher and current profile source required')
    require(plan.get('query_count') == 64 and plan['workers'] == 16
            and plan.get('reference_role') == 'before',
            'Fixed64 prefix queries and16 fresh workers against complete Common')
    out = Path(plan['output_directory'])
    require(out.is_absolute() and not out.exists(), 'Fresh absolute profile output required')
    out.mkdir(parents=True)
    guard = Guard(plan)
    started = time.monotonic()
    try:
        packed_path = verify(plan['reference_manifest'])
        packed = validate_reference(packed_path, 'before')
        require(packed['molecules'] == 1196122, 'Complete actual Common1196122 required')
        baseline_path = verify(plan['baseline_receipt'])
        baseline = load(baseline_path)
        query_path = baseline_query(baseline)
        query_frame = file_frame(query_path)
        fp_path = verify(packed['fingerprints'])
        require(fp_path.stat().st_size == packed['molecules'] * WIDTH,
                'Complete packed reference bytes required')
        source_rows = list(rows(query_path, 64, query_frame))
        queries = [(ordinal, raw) for ordinal, row, raw, size in source_rows]
        query_identity_sha = hashlib.sha256()
        for ordinal, row, raw, size in source_rows:
            query_identity_sha.update(json.dumps(
                [ordinal, row['cid'], row['full_key'], raw.hex()],
                separators=(',', ':')).encode() + b'\n')
        ready = []
        results = []
        measurements = []
        batch_started = time.monotonic()
        for result in exact_batches(fp_path, packed['molecules'],
                ([query] for query in queries), workers=16,
                worker_rss_cap_bytes=plan['worker_rss_cap_bytes'],
                ready_callback=ready.append):
            guard.check()
            results.extend(result.pop('results'))
            measurements.append(result)
        engine_wall = time.monotonic() - batch_started
        require(len(ready) == 16 and len({r['worker_pid'] for r in ready}) == 16
                and all(r['reference_decode_calls'] == 1196122 for r in ready),
                'Every actual fresh worker must decode every reference once')
        require(len(results) == 64 and sorted(r[0] for r in results) == list(range(64)),
                'All fixed operational prefix queries returned exactly once')
        for ordinal, raw, result in results:
            require(raw == queries[ordinal][1]
                    and result['reference_molecules'] == 1196122
                    and result['evaluated_references'] + result['strictly_bound_pruned_references'] == 1196122,
                    'Every profile query retains exact whole-reference accounting')
        guard.sample()
        guard.check()
        reference_data = dict(
            schema='ALPHA_EXACT_FULL_COMMON_CACHE_PROFILE_DATA_V1',
            results=[dict(query_ordinal=i, fingerprint_sha256=hashlib.sha256(raw).hexdigest(),
                          result=value) for i, raw, value in sorted(results)],
            workers=ready, batches=measurements)
        dump_new(out / 'measurements.json', reference_data)
        receipt = dict(schema='ALPHA_EXACT_FULL_COMMON_CACHE_PROFILE_RECEIPT_V1',
            status='MEASURED_PENDING_ACTUAL_ALPHA_C0_AND_ROOT_REVIEW',
            job_id=os.environ['SLURM_JOB_ID'], uid=os.getuid(),
            endpoint_execution=provenance(plan), source=reference(Path(__file__)),
            resource_plan=reference(plan_path), startup_proof=reference(startup_proof),
            reference_manifest=plan['reference_manifest'], baseline_receipt=plan['baseline_receipt'],
            reference_molecules=1196122, measured_queries=64, full_baseline_queries=1000000,
            query_selection='Original frozen baseline sample ordinals0..63; operational measurement only',
            query_identity_sha256=query_identity_sha.hexdigest(), algorithm=ALGORITHM,
            worker_rss_cap_bytes=plan['worker_rss_cap_bytes'],
            max_reference_load_rss_bytes=max(r['reference_load_rss_bytes'] for r in ready),
            max_batch_rss_bytes=max(r['rss_bytes'] for r in measurements),
            engine_wall_seconds=engine_wall, total_wall_seconds=time.monotonic() - started,
            resources=guard.receipt(), startup_memory_observation=startup_memory,
            measurements=reference(out / 'measurements.json'),
            scientific_baseline_complete=False, scientific_baseline_rows_dropped=0,
            candidate_pool_release_authorized=False, training_release_authorized=False,
            scientific_recipe_changed=False, cost_based_stop_applied=False,
            actual_parent_C0_pending_Root_review=True)
        dump_new(out / 'receipt.json', receipt)
        return receipt
    finally:
        guard.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--startup-proof', required=True, type=Path)
    args = parser.parse_args()
    execute(args.plan, args.startup_proof)


if __name__ == '__main__':
    main()
