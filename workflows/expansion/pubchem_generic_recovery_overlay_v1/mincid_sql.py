"""Exact small-delta reduction; original canonical rows are only read by key/CID."""
from ..alpha_runtime_v1 import common as Q


def reduce(db):
    rows,cids,invalid=db.execute('SELECT count(*),count(DISTINCT cid),count(*) FILTER(WHERE cid IS NULL OR cid<=0 OR full_key IS NULL) FROM delta').fetchone()
    Q.need(rows==cids and rows>0 and invalid==0,'Complete unique positive delta source CIDs')
    Q.need(db.execute('SELECT count(*) FROM old_aliases SEMI JOIN delta USING(cid)').fetchone()[0]==0,
        'Recovered source CID must not already be an old accepted alias')
    db.execute('CREATE TEMP TABLE delta_winners AS SELECT * FROM delta QUALIFY row_number() OVER(PARTITION BY full_key ORDER BY cid)=1')
    db.execute('CREATE TEMP TABLE old_matches AS SELECT b.full_key,b.cid FROM base b SEMI JOIN delta_winners USING(full_key)')
    n,keys=db.execute('SELECT count(*),count(DISTINCT full_key) FROM old_matches').fetchone()
    Q.need(n==keys,'Original minCID canonical key uniqueness retained')
    db.execute('CREATE TEMP TABLE winning_delta AS SELECT d.* FROM delta_winners d LEFT JOIN old_matches b USING(full_key) WHERE b.cid IS NULL OR d.cid<b.cid')
    db.execute('CREATE TEMP TABLE replacement_keys AS SELECT d.full_key,b.cid AS old_cid,d.cid AS new_cid FROM winning_delta d JOIN old_matches b USING(full_key)')
    db.execute('CREATE TEMP TABLE new_keys AS SELECT d.cid,d.full_key FROM winning_delta d ANTI JOIN old_matches b USING(full_key)')
    db.execute('CREATE TEMP VIEW corrected_candidates AS SELECT b.* FROM base b ANTI JOIN replacement_keys r USING(full_key) UNION ALL SELECT * FROM winning_delta')
    return dict(delta_rows=rows,delta_unique_full_keys=db.execute('SELECT count(*) FROM delta_winners').fetchone()[0],
        new_full_keys=db.execute('SELECT count(*) FROM new_keys').fetchone()[0],
        replaced_representatives=db.execute('SELECT count(*) FROM replacement_keys').fetchone()[0],
        winning_delta_rows=db.execute('SELECT count(*) FROM winning_delta').fetchone()[0])
