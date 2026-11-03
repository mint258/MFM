"""Original columnar filter body; only scientific import relocated."""
import sqlite3
from pathlib import Path
from ..alpha_runtime_v1.common import need
from .sql import SQLStopper, connection, copy_parquet, literal, load_sqlite_table

def filter_core(pool_path, index_path, out, workers, memory_bytes, check):
    import pyarrow as pa
    from . import science_v3 as original
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
