"""Columnar parity with original full/WP5/composition and approved V3 bounds."""
from collections import Counter
import sqlite3
from pathlib import Path
from .runtime import allocated, frame, load, need, parent, pinned_frame, reference, verify, write_new
from .sql import SQLStopper, attempt, connection, copy_parquet, literal, load_sqlite_table


def filter_core(pool_path, index_path, out, workers, memory_bytes, check):
    import pyarrow as pa
    from ..coconut735_recovery_v1 import consumer as original
    db = connection(out, workers, memory_bytes)
    monitor = SQLStopper(db, check)
    incoming = sqlite3.connect(Path(index_path).as_uri() + '?mode=ro', uri=True)
    try:
        prepared = original.rules(incoming)
        load_sqlite_table(db, incoming, 'excluded', ('kind', 'key', 'dataset'), (pa.string(), pa.string(), pa.string()), check)
        db.read_parquet(str(pool_path)).create_view('candidates')
        # Validate the complete actual frozen X02 vector domain in native SQL.
        # Equality with canonical JSON also rejects coercion/truncation of counts.
        db.execute("CREATE VIEW vectors AS SELECT cid,full_key,wp5_key,non_h_composition,elements,from_json(non_h_composition,'[[\"BIGINT\"]]') AS v FROM candidates")
        whitelist = '[' + ','.join(map(str, sorted(original.X02_ATOMIC_NUMBERS))) + ']'
        invalid = db.execute("SELECT count(*) FROM vectors WHERE v IS NULL OR elements IS NULL OR non_h_composition IS NULL OR wp5_key IS NULL OR len(v)=0 OR to_json(v)<>non_h_composition OR list_transform(v,p->p[1])<>elements OR elements<>list_sort(list_distinct(elements)) OR NOT coalesce(list_bool_and(list_transform(v,p->coalesce(len(p)=2 AND p[1]>=2 AND p[1]<=118 AND list_contains(" + whitelist + ",p[1]) AND p[2]>0,false))),false) OR wp5_key<>substr(full_key,1,14)||':'||right(full_key,1)").fetchone()[0]
        need(invalid == 0, 'Every complete candidate must satisfy original canonical X02 composition and WP5 domain')
        fragments = []
        for kind, field in (('full', 'full_key'), ('wp5', 'wp5_key'), ('composition', 'non_h_composition')):
            fragments.append('SELECT c.cid,c.full_key,e.kind,e.dataset FROM candidates c JOIN excluded e ON e.kind=' + literal(kind) + ' AND e.key=c.' + field)
        for rid, dataset, bound in prepared:
            condition = ' AND '.join('coalesce(list_extract(list_filter(v,p->p[1]=' + str(z) + '),1)[2],0)>=' + str(n) for z, n in sorted(bound.items()))
            fragments.append('SELECT cid,full_key,' + literal('composition_lower_bound:' + rid) + ' AS kind,' + literal(dataset) + ' AS dataset FROM vectors WHERE ' + condition)
        check()
        db.execute('CREATE TABLE hits AS ' + ' UNION ALL '.join(fragments))
        db.execute('CREATE TABLE vetoes AS SELECT DISTINCT cid,full_key FROM hits')
        n, unique_keys, unique_cids = db.execute('SELECT count(*),count(DISTINCT full_key),count(DISTINCT cid) FROM candidates').fetchone()
        excluded = db.execute('SELECT count(*) FROM vetoes').fetchone()[0]
        need(n == unique_keys == unique_cids and 0 <= excluded <= n, 'Deduplicated whole pool identities must conserve')
        accepted = copy_parquet(db, 'SELECT c.* FROM candidates c ANTI JOIN vetoes v USING(cid,full_key)', Path(out) / 'eligible_candidates.parquet')
        evidence = copy_parquet(db, 'SELECT * FROM hits', Path(out) / 'contamination_hits.parquet')
        need(accepted['rows'] + excluded == n, 'Typed filter mass must conserve the complete minCID pool')
        counts = {'input_unique_molecules': n, 'excluded_molecules': excluded, 'eligible_molecules': accepted['rows']}
        for kind, dataset, number in db.execute('SELECT kind,dataset,count(*) FROM hits GROUP BY kind,dataset').fetchall():
            counts['reason:' + kind + ':' + dataset] = number
        counts['conservative_lower_bound_exclusions'] = db.execute("SELECT count(DISTINCT cid) FROM hits WHERE starts_with(kind,'composition_lower_bound:')").fetchone()[0]
        counts['additional_conservative_veto_beyond_exact_possible_over_exclusion'] = db.execute("SELECT count(*) FROM vetoes v WHERE EXISTS(SELECT 1 FROM hits h WHERE h.cid=v.cid AND starts_with(h.kind,'composition_lower_bound:')) AND NOT EXISTS(SELECT 1 FROM hits h WHERE h.cid=v.cid AND NOT starts_with(h.kind,'composition_lower_bound:'))").fetchone()[0]
        db.execute('CHECKPOINT')
        check()
        return accepted, evidence, counts
    finally:
        monitor.close()
        incoming.close()
        db.close()


def accepted_index(plan):
    from ..coconut735_recovery_v1 import consumer as original
    index_ref = plan['exclusion_index_receipt']
    index = original.index_header(load(verify(index_ref)))
    review = load(verify(plan['root_index_acceptance_reference']))
    need(review['schema'] == 'PUBCHEM_ALL11_EXCLUSION_INDEX_ACTUAL_ACCEPTANCE_V1' and review['status'] == 'APPROVED_COMPLETE_ALL11_INDEX' and review['reviewer'] == 'root' and review['index_receipt'] == index_ref and review['all_sources_all_splits_verified'] is True and review['original_graph_unknowns_retained'] is True, 'Actual Root all11 index closure acceptance required; no READY9 or unaccepted735 substitution')
    account = load(verify(review['actual_accounting_reference']))
    actual = review['actual_parent']
    need(actual['State'] == 'COMPLETED' and actual['ExitCode'] == '0:0' and str(actual['JobIDRaw']) == str(index['producer_parent_binding']['job_id']) and review['actual_parent'] in account['actual_parents'], 'Independent actual C0 index accounting must match its real producer')
    verify(index['source_manifest_reference'])
    for suffix in ('-wal', '-shm', '-journal'):
        need(not Path(index['database']['path'] + suffix).exists(), 'Only a closed accepted exclusion index may be consumed')
    path, before = pinned_frame(index['database'])
    return index, path, before


def run(plan_path):
    plan = load(plan_path)
    need(plan['action'] == 'filter', 'Typed filtering plan required')
    pool = load(verify(plan['source_pool_receipt']))
    need(pool['schema'] == 'PUBCHEM_EXACT_MINCID_CANDIDATE_POOL_V2' and pool['status'] == 'MATERIALIZED_UNFILTERED_NO_RELEASE' and pool['source_rows'] == 124857440 and pool['original_SQL_minimum_CID_semantics'] is True and pool['decontamination_filter_rank_or_training_release'] is False, 'Complete unchanged minCID pool required')
    regression = load(verify(plan['regression_reference']))
    need(regression['status'] == 'PASS' and regression['agreement'] >= .999 and regression['unexplained_mismatches'] == 0 and regression['full_v1_selection_regression_passed'] is True, 'Actual full-v1 selection regression acceptance required')
    index, index_path, index_before = accepted_index(plan)
    source, source_before = pinned_frame(pool['candidates'])
    with allocated(plan) as (stage, guard):
        scope = {'pool': plan['source_pool_receipt'], 'index': plan['exclusion_index_receipt'], 'acceptance': plan['root_index_acceptance_reference'], 'regression': plan['regression_reference']}
        scope_path = stage / 'scope.json'
        if scope_path.exists():
            need(load(scope_path) == scope, 'Filtering resume inputs changed')
        else:
            write_new(scope_path, scope)
        final = stage / 'receipt.json'
        if final.exists():
            previous = load(final)
            need(previous['scope'] == scope, 'Closed filtered pool scope changed')
            verify({k: previous['candidates'][k] for k in ('path', 'bytes', 'sha256')})
            verify({k: previous['contamination_hits'][k] for k in ('path', 'bytes', 'sha256')})
            return previous
        out = attempt(stage)
        def check():
            guard.check()
        accepted, evidence, counts = filter_core(source, index_path, out, plan['workers'], plan['duckdb_memory_bytes'], check)
        need(counts['input_unique_molecules'] == pool['unique_full_keys'], 'Whole minCID source cardinality differs')
        need(frame(source) == source_before and frame(index_path) == index_before, 'Whole-SHA-admitted input/index changed during typed filtering')
        guard.sample(); guard.check()
        result = {'schema': 'expansion_filtered_columnar_pool_v1', 'status': 'COMPLETE', 'scope': scope, 'all_sources_all_splits_verified': True, 'source_pool_receipt': plan['source_pool_receipt'], 'exclusion_index_receipt': plan['exclusion_index_receipt'], 'root_index_acceptance_reference': plan['root_index_acceptance_reference'], 'regression_reference': plan['regression_reference'], 'counts': counts, 'candidates': accepted, 'contamination_hits': evidence, 'aliases': pool['aliases'], 'source_aliases_preserved_by_reference': True, 'original_graph_unknowns_retained': True, 'downstream_targets_consumed': False, 'actual_parent': parent(), 'resource_plan': reference(plan_path), 'aggregate_output_scope_root': plan['output_scope_root'], 'runtime': guard.receipt()}
        write_new(final, result)
        return result
