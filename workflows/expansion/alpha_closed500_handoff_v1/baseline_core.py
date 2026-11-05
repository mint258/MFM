"""Original fixed-seed predecon sample SQL body, without Main runtime."""
from pathlib import Path
from ..alpha_runtime_v1.common import need
from .sql import SQLStopper, connection, copy_parquet, literal
from .projection import query_projection
DOMAIN="PubChem-baseline-uniform"
SEED=20261025
SIZE=1000000

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
