"""Admit reconstructed500 directly to the unchanged exact minimum-CID merge."""
from pathlib import Path
from .runtime import allocated, load, need, parent, reference, verify, write_new


def merge_core(projection_path, output, workers, memory_bytes, resource_plan, check):
    from ..pubchem_closed500_bulk_v2 import merge as original
    # Adapt runtime resource callbacks in this exclusive process, including
    # cheap stop checks around the unchanged whole-SHA verifier. Materializer,
    # SQL/Arrow/minimum-CID operations and each original SHA call remain intact.
    previous, previous_verify = original.resource_check, original.verify
    def actual_resource(unused_plan, unused_directory):
        check()
    def guarded_verify(ref):
        check()
        path = previous_verify(ref)
        check()
        return path
    original.resource_check = actual_resource
    original.verify = guarded_verify
    try:
        return original.materialize(projection_path, output, workers, memory_bytes, resource_plan, inputs_verified=False)
    finally:
        original.resource_check = previous
        original.verify = previous_verify


def run(plan_path):
    plan = load(plan_path)
    need(plan['action'] == 'merge', 'Merge-only plan required; never use old Alpha502 prepare/project')
    projection_path = verify(plan['raw_projection_manifest'])
    value = load(projection_path)
    need(value['schema'] == 'PUBCHEM_ALL_CLOSED_PROJECTIONS_V2' and value['producer_schema'] == 'PUBCHEM_FULL_RAW_RECONSTRUCTION_COVERAGE_V1' and value['status'] == 'COMPLETE_ACCEPTED_PROJECTIONS_NO_POOL_RELEASE' and value['source_rows'] == 124857440 and value['fragment_count'] == len(value['accepted_parquets']) == len(value['fragments']) == 500 and sum(value['counts'].values()) == 124857440 and value['full_raw_scope_reconstructed'] is True and value['old_502_Alpha_body_closure_claimed'] is False, 'Actual full original500 reconstructed closure required')
    with allocated(plan) as (stage, guard):
        result = merge_core(projection_path, stage / 'unfiltered_pool', plan['workers'], plan['duckdb_memory_bytes'], plan, guard.check)
        guard.check()
        final = stage / 'admitted_receipt.json'
        pool_ref = reference(stage / 'unfiltered_pool/receipt.json')
        if final.exists():
            previous = load(final)
            need(previous['raw_projection_manifest'] == plan['raw_projection_manifest'] and previous['minimum_CID_pool_receipt'] == pool_ref, 'Closed admitted handoff scope changed on resume')
            return previous
        receipt = {'schema': 'PUBCHEM_ADMITTED_MINCID_HANDOFF_V1', 'status': 'COMPLETE_INTERNAL_DEDUP_NOT_DECONTAMINATION_RELEASE', 'raw_projection_manifest': plan['raw_projection_manifest'], 'minimum_CID_pool_receipt': reference(stage / 'unfiltered_pool/receipt.json'), 'unique_full_keys': result['unique_full_keys'], 'aliases_rows': result['aliases_rows'], 'actual_parent': parent(), 'aggregate_output_scope_root': plan['output_scope_root'], 'resource_plan': reference(plan_path), 'runtime': guard.receipt()}
        write_new(final, receipt)
        return receipt
