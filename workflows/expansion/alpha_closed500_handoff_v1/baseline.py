"""Actual Alpha fixed1M predecontamination selector with original SQL recipe."""
from pathlib import Path
from ..alpha_runtime_v1.common import ENDPOINT, UID, frame, load, need, reference, verify, write
from ..alpha_runtime_v1.guard import Guard
from ..alpha_runtime_v1.profile import admit
from .baseline_core import DOMAIN, SEED, SIZE, baseline_core
from .projection import RECIPE
from .scientific_contract import verify as verify_science


def actual_pool(plan):
    out = Path(plan['output_directory']); pool_ref = reference(out / 'unfiltered_pool/receipt.json')
    pool = load(verify(pool_ref)); projection_ref = pool['scope']['source_projection']; projection = load(verify(projection_ref))
    need(pool['schema'] == 'PUBCHEM_EXACT_MINCID_CANDIDATE_POOL_V2' and pool['status'] == 'MATERIALIZED_UNFILTERED_NO_RELEASE' and pool['source_rows'] == 124857440 and pool['original_SQL_minimum_CID_semantics'] is True and pool['decontamination_filter_rank_or_training_release'] is False, 'Complete actual internal-minCID pool required before baseline or filtering')
    need(projection['producer_schema'] == 'PUBCHEM_ALPHA_ORIGINAL502_TYPED_COVERAGE_V1' and projection['source_endpoint'] == ENDPOINT and projection['source_uid'] == UID and projection['logical_descriptor_count'] == 500 and projection['fragment_count'] == 502 and projection['source_rows'] == 124857440 and projection['source_typed_bodies_full_SHA_verified'] is True and projection['chemistry_recomputed'] is False and projection['coverage_reference'] == plan['coverage_reference'], 'Exact honest original Alpha502 source closure required')
    need(projection['source_snapshot_sha256'] == plan['source_snapshot_sha256'] and pool['source_counts'] == projection['counts'] == plan['source_counts'] and pool['aliases_rows'] == plan['source_counts']['accepted'], 'Original Alpha snapshot/category/all-CID-alias census differs')
    return pool, pool_ref


def run(plan_path):
    plan = load(plan_path); actual = admit(plan); verify_science()
    pool, pool_ref = actual_pool(plan)
    before = frame(pool['candidates']['path']); source = verify(pool['candidates']); need(frame(source) == before, 'Input changed across source SHA admission')
    stage = Path(plan['output_directory']) / 'baseline_1m'; stage.mkdir(exist_ok=True)
    guard = Guard(plan)
    try:
        scope = {'source_pool_receipt': pool_ref, 'seed': SEED, 'domain': DOMAIN, 'sample_size': SIZE, 'sample_ordinal_start': 0, 'projection_order': 'sample_ordinal_ASC', 'baseline_pool_phase': 'BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY'}
        final = stage / 'receipt.json'
        if final.exists():
            old = load(final); need(old['scope'] == scope, 'Frozen Alpha sample scope changed')
            for key in ('sample_membership', 'features', 'projection'):verify(old[key])
            return old
        from .sql import attempt
        out = attempt(stage)
        membership, features, projection, total = baseline_core(source, out, plan['workers'], plan['duckdb_memory_bytes'], guard.check)
        need(total == pool['unique_full_keys'] and frame(source) == before, 'Entire unique Alpha pool and unchanged SHA-admitted source required')
        guard.sample(); guard.check()
        result = {'schema': 'EXPANSION_PUBCHEM_PREDECON_BASELINE_V1', 'status': 'COMPLETE', 'scope': scope, 'source_endpoint': ENDPOINT, 'source_uid': UID, 'fingerprint_recipe': RECIPE, 'targets_present': False, 'downstream_features_present': False, 'projection': projection, 'sample_membership': membership, 'features': features, 'sample_seed': SEED, 'sample_hash_domain': DOMAIN, 'sample_selection': 'fixed_predecon_minCID_fullkey_unique', 'sample_molecules': SIZE, 'source_pool_molecules': total, 'sample_ordinal_start': 0, 'projection_order': 'sample_ordinal_ASC', 'all_source_internal_fullkey_dedup_before_v1_or_downstream_decontamination': True, 'source_pool_receipt': pool_ref, 'raw_chemical_screen_reference': pool['scope']['source_projection'], 'internal_deduplicated_pool_reference': pool_ref, 'screening_decisions_changed': False, 'actual_parent': actual, 'actual_parent_C0_acceptance': 'PENDING_ROOT_TERMINAL_ACCOUNTING', 'resource_plan': reference(plan_path), 'runtime': guard.receipt()}
        write(final, result); return result
    finally:guard.close()
