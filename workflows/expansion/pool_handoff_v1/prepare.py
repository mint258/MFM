"""Freeze actual closed receipt pins only; never invent future data readiness."""
import argparse
from pathlib import Path
from .runtime import load, need, reference, verify, write_new

INPUTS = {'merge': ('raw_projection_manifest',), 'baseline': ('source_pool_receipt',), 'filter': ('source_pool_receipt', 'exclusion_index_receipt', 'root_index_acceptance_reference', 'regression_reference'), 'query_projection': ('filtered_pool_receipt',)}


def prepare(request_path, sources, plan_path):
    request = load(request_path)
    need(request['schema'] == 'PUBCHEM_POOL_HANDOFF_STAGE_REQUEST_V1' and request['status'] == 'PENDING_ACTUAL_CLOSED_INPUTS', 'Explicit pending-input metadata request required')
    action = request['action']
    need(set(sources) == set(INPUTS[action]), 'Exactly the required closed stage inputs must be supplied')
    resources = load(verify(request['resources_reference']))
    pins = {}
    for key, path in sources.items():
        need(Path(path).stat().st_size <= 10 << 20, 'Receipt/source-manifest metadata only; do not hash a scientific body in preparation')
        pins[key] = reference(path)
    root = Path(request['output_scope_root'])
    stage = Path(request['stage_output_directory'])
    need(stage.is_relative_to(root) and stage != root, 'Private stage within one aggregate scope required')
    here = Path(__file__).parent
    source_files = [*sorted(here.glob('*.py')), *(here.parent / name for name in ('pubchem_closed500_bulk_v2/merge.py', 'pubchem_closed500_bulk_v2/common.py', 'coconut735_recovery_v1/consumer.py', 'coconut735_recovery_v1/kernel.py', 'decontamination.py', 'common.py', 'pubchem_raw_reconstruction_v1/support.py'))]
    value = {'schema': 'PUBCHEM_POOL_HANDOFF_PLAN_V1', 'status': 'METADATA_PINNED_PENDING_ALLOCATED_DATA_SHA_AND_C0_ADMISSION', 'action': action, **resources, **pins, 'output_scope_root': str(root), 'output_directory': str(root), 'stage_output_directory': str(stage), 'workers': request['workers'], 'duckdb_memory_bytes': request['duckdb_memory_bytes'], 'request_reference': reference(request_path), 'code_references': [reference(path) for path in source_files], 'arbitrary_wall_or_retry_limit': False, 'sampling_or_science_overrides_accepted': False}
    return write_new(plan_path, value)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request', required=True)
    p.add_argument('--source', action='append', default=[], help='Required role=/actual/closed/receipt.json; no future placeholders')
    p.add_argument('--plan', required=True)
    a = p.parse_args()
    pairs = [s.split('=', 1) for s in a.source]
    need(all(len(v) == 2 for v in pairs) and len({v[0] for v in pairs}) == len(pairs), 'Unique explicit source role=value pairs required')
    print(prepare(a.request, dict(pairs), a.plan))


if __name__ == '__main__':
    main()
