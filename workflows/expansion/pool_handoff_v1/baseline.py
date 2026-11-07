"""Fixed uniform1M sampled before any v1/downstream exclusion or novelty."""
from pathlib import Path
from .runtime import allocated, frame, load, need, parent, pinned_frame, reference, verify, write_new
from .sql import SQLStopper, attempt, connection, copy_parquet, literal
from .projection import RECIPE, query_projection

DOMAIN = 'PubChem-baseline-uniform'
SEED = 20261025
SIZE = 1000000


def baseline_core(pool_path, out, workers, memory_bytes, check, *, sample_size=SIZE, seed=SEED):
    db = connection(out, workers, memory_bytes)
    monitor = SQLStopper(db, check)
    try:
        db.read_parquet(str(pool_path)).create_view('candidates')
        n, keys, cids = db.execute('SELECT count(*),count(DISTINCT full_key),count(DISTINCT cid) FROM candidates').fetchone()
        need(n == keys == cids and n >= sample_size > 0, 'Complete unique minCID pool must contain the declared sample')
        # Full InChIKeys and the domain are ASCII. This exactly equals existing
        # stable_hash(domain, seed, full_key), without110M Python callbacks.
        prefix = '["' + DOMAIN + '",' + str(int(seed)) + ',"'
        expression = 'sha256(' + literal(prefix) + '||full_key||' + literal('"]') + ')'
        db.execute('CREATE TABLE chosen AS SELECT cid,full_key,(row_number() OVER(ORDER BY h,full_key,cid)-1)::BIGINT AS sample_ordinal FROM (SELECT cid,full_key,' + expression + ' AS h FROM candidates ORDER BY h,full_key,cid LIMIT ' + str(int(sample_size)) + ')')
        membership = copy_parquet(db, 'SELECT cid,full_key,sample_ordinal FROM chosen ORDER BY sample_ordinal', Path(out) / 'sample_membership.parquet')
        features = copy_parquet(db, 'SELECT c.*,s.sample_ordinal FROM candidates c JOIN chosen s USING(cid,full_key) ORDER BY s.sample_ordinal', Path(out) / 'sample_features.parquet')
        need(membership['rows'] == features['rows'] == sample_size, 'Complete fixed sample must conserve typed feature membership')
        db.read_parquet(features['path']).create_view('sampled')
        projection = query_projection(db, 'sampled', Path(out) / 'sample_query.jsonl', sample_size, check, sample_order=True)
        db.execute('CHECKPOINT')
        check()
        return membership, features, projection, n
    finally:
        monitor.close(); db.close()


def run(plan_path):
    plan = load(plan_path)
    need(plan['action'] == 'baseline' and plan.get('sample_seed', SEED) == SEED and plan.get('sample_size', SIZE) == SIZE, 'Scientific baseline is exactly fixed-seed1M; no narrowed/cost substitute')
    pool_path = verify(plan['source_pool_receipt'])
    pool = load(pool_path)
    need(pool['schema'] == 'PUBCHEM_EXACT_MINCID_CANDIDATE_POOL_V2' and pool['status'] == 'MATERIALIZED_UNFILTERED_NO_RELEASE' and pool['source_rows'] == 124857440 and pool['original_SQL_minimum_CID_semantics'] is True and pool['decontamination_filter_rank_or_training_release'] is False, 'Sample source must be screened/internal-dedup complete pool BEFORE decontamination')
    source, source_before = pinned_frame(pool['candidates'])
    with allocated(plan) as (stage, guard):
        scope = {'source_pool_receipt': plan['source_pool_receipt'], 'seed': SEED, 'domain': DOMAIN, 'sample_size': SIZE, 'sample_ordinal_start': 0, 'projection_order': 'sample_ordinal_ASC', 'baseline_pool_phase': 'BEFORE_V1_DOWNSTREAM_DECONTAMINATION_AND_NOVELTY'}
        scope_path = stage / 'scope.json'
        if scope_path.exists():
            need(load(scope_path) == scope, 'Frozen baseline source/selection changed')
        else:
            write_new(scope_path, scope)
        final = stage / 'receipt.json'
        if final.exists():
            old = load(final)
            need(old['scope'] == scope, 'Closed baseline differs')
            for key in ('sample_membership', 'features', 'projection'):
                verify({k: old[key][k] for k in ('path', 'bytes', 'sha256')})
            return old
        out = attempt(stage)
        membership, features, projection, total = baseline_core(source, out, plan['workers'], plan['duckdb_memory_bytes'], guard.check)
        need(total == pool['unique_full_keys'], 'Baseline must sample the entire actual unique-key pool')
        need(frame(source) == source_before, 'Whole-SHA-admitted predecon pool changed during frozen sample selection')
        guard.sample(); guard.check()
        result = {'schema': 'EXPANSION_PUBCHEM_PREDECON_BASELINE_V1', 'status': 'COMPLETE', 'scope': scope, 'fingerprint_recipe': RECIPE, 'targets_present': False, 'downstream_features_present': False, 'projection': projection, 'sample_membership': membership, 'features': features, 'sample_seed': SEED, 'sample_hash_domain': DOMAIN, 'sample_selection': 'fixed_predecon_minCID_fullkey_unique', 'sample_molecules': SIZE, 'source_pool_molecules': total, 'all_source_internal_fullkey_dedup_before_v1_or_downstream_decontamination': True, 'source_pool_receipt': plan['source_pool_receipt'], 'raw_chemical_screen_reference': pool['scope']['source_projection'], 'internal_deduplicated_pool_reference': plan['source_pool_receipt'], 'screening_decisions_changed': False, 'actual_parent': parent(), 'resource_plan': reference(plan_path), 'runtime': guard.receipt()}
        result['sample_ordinal_start'] = 0
        result['projection_order'] = 'sample_ordinal_ASC'
        write_new(final, result)
        return result
