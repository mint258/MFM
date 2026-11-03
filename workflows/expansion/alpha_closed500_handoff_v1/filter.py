"""Typed all11 filtering of Alpha minCID data; original Main proofs stay original."""
from pathlib import Path
from ..alpha_runtime_v1.common import frame, load, need, reference, write
from ..alpha_runtime_v1.guard import Guard
from ..alpha_runtime_v1.profile import admit
from .baseline import actual_pool
from .empty_domain import EXTENSION, filter_core
from .scientific_contract import verify as verify_science
from . import science_v3


def run(plan_path):
    from ..portable_sources_v1.transport import bind_plan, verify
    plan = load(plan_path); actual = admit(plan); bind_plan(plan); verify_science()
    pool, pool_ref = actual_pool(plan)
    index_ref = plan['exclusion_index_receipt']; index = science_v3.index_header(load(verify(index_ref)))
    review = load(verify(plan['root_index_acceptance_reference']))
    need(review['schema'] == 'PUBCHEM_ALL11_EXCLUSION_INDEX_ACTUAL_ACCEPTANCE_V1' and review['status'] == 'APPROVED_COMPLETE_ALL11_INDEX' and review['reviewer'] == 'root' and review['index_receipt'] == index_ref and review['all_sources_all_splits_verified'] is True and review['original_graph_unknowns_retained'] is True, 'Actual all11 Root source acceptance required; a migrated partial/ready9 source is insufficient')
    account = load(verify(review['actual_accounting_reference'])); accepted_parent = review['actual_parent']
    need(accepted_parent['State'] == 'COMPLETED' and accepted_parent['ExitCode'] == '0:0' and str(accepted_parent['JobIDRaw']) == str(index['producer_parent_binding']['job_id']) and accepted_parent in account['actual_parents'], 'Original accepted index producer must have independent actual C0 accounting')
    verify(index['source_manifest_reference'])
    index_path = verify(index['database'])
    need(all(not Path(str(index_path) + suffix).exists() for suffix in ('-wal', '-shm', '-journal')), 'Actual Alpha index replica must be closed')
    regression = load(verify(plan['regression_reference']))
    need(regression['status'] == 'PASS' and regression['agreement'] >= .999 and regression['unexplained_mismatches'] == 0 and regression['full_v1_selection_regression_passed'] is True, 'Actual original-selection regression acceptance remains required')
    source = verify(pool['candidates']); source_frame, index_frame = frame(source), frame(index_path)
    stage = Path(plan['output_directory']) / 'filtered_all11'; stage.mkdir(exist_ok=True)
    scope = {'source_pool_receipt': pool_ref, 'exclusion_index_receipt': index_ref, 'root_index_acceptance_reference': plan['root_index_acceptance_reference'], 'regression_reference': plan['regression_reference'], 'parent_transport_manifest': plan['parent_transport_manifest'], 'candidate_domain_extension': EXTENSION}
    guard = Guard(plan)
    try:
        final = stage / 'receipt.json'
        if final.exists():
            old = load(final); need(old['scope'] == scope, 'Actual all11 filtering scope/transport changed')
            verify(old['candidates']); verify(old['contamination_hits']); return old
        from .sql import attempt
        out = attempt(stage)
        selected, hits, counts = filter_core(source, index_path, out, plan['workers'], plan['duckdb_memory_bytes'], guard.check)
        need(counts['input_unique_molecules'] == pool['unique_full_keys'] and frame(source) == source_frame and frame(index_path) == index_frame, 'Full Alpha pool/source-index frames must conserve')
        guard.sample(); guard.check()
        result = {'schema': 'expansion_filtered_columnar_pool_v1', 'status': 'COMPLETE', 'scope': scope, 'source_endpoint': plan['endpoint'], 'source_uid': plan['uid'], 'all_sources_all_splits_verified': True, 'source_pool_receipt': pool_ref, 'exclusion_index_receipt': index_ref, 'root_index_acceptance_reference': plan['root_index_acceptance_reference'], 'regression_reference': plan['regression_reference'], 'parent_transport_manifest': plan['parent_transport_manifest'], 'counts': counts, 'candidates': selected, 'contamination_hits': hits, 'aliases': pool['aliases'], 'source_aliases_preserved_by_reference': True, 'original_graph_unknowns_retained': True, 'downstream_targets_consumed': False, 'actual_parent': actual, 'actual_parent_C0_acceptance': 'PENDING_ROOT_TERMINAL_ACCOUNTING', 'resource_plan': reference(plan_path), 'runtime': guard.receipt()}
        result['candidate_domain_extension'] = EXTENSION
        write(final, result); return result
    finally:guard.close()
