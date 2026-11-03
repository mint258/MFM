"""Exact insertion-only topK, using the original stable hash/domain/tie order."""
from ..alpha_closed500_handoff_v1.baseline_core import DOMAIN,SEED,SIZE
from ..alpha_closed500_handoff_v1.sql import literal
from ..alpha_runtime_v1 import common as Q


def choose(db,size=SIZE,seed=SEED):
    n,keys,cids,ordinals,lo,hi=db.execute('SELECT count(*),count(DISTINCT full_key),count(DISTINCT cid),count(DISTINCT sample_ordinal),min(sample_ordinal),max(sample_ordinal) FROM old_membership').fetchone()
    Q.need(n==keys==cids==ordinals==size and lo==0 and hi==size-1,'Complete proven frozen old topK membership')
    db.execute('CREATE TEMP VIEW incremental_keys AS SELECT coalesce(r.new_cid,m.cid) AS cid,m.full_key FROM old_membership m LEFT JOIN replacements r USING(full_key) UNION ALL SELECT cid,full_key FROM new_keys')
    n,k,c=db.execute('SELECT count(*),count(DISTINCT full_key),count(DISTINCT cid) FROM incremental_keys').fetchone()
    Q.need(n==k==c and n>=size,'Unique corrected old topK plus only genuinely new fullkeys')
    prefix='["'+DOMAIN+'",'+str(int(seed))+',"'
    h='sha256('+literal(prefix)+'||full_key||'+literal('"]')+')'
    db.execute('CREATE TEMP TABLE chosen AS SELECT cid,full_key,(row_number() OVER(ORDER BY h,full_key,cid)-1)::BIGINT AS sample_ordinal FROM (SELECT cid,full_key,'+h+' AS h FROM incremental_keys ORDER BY h,full_key,cid LIMIT '+str(int(size))+')')
    changes=dict(old_keys_removed=db.execute('SELECT count(*) FROM old_membership ANTI JOIN chosen USING(full_key)').fetchone()[0],
        new_full_keys_added=db.execute('SELECT count(*) FROM chosen ANTI JOIN old_membership USING(full_key)').fetchone()[0],
        representative_CIDs_changed=db.execute('SELECT count(*) FROM chosen c JOIN old_membership o USING(full_key) WHERE c.cid<>o.cid').fetchone()[0])
    Q.need(changes['old_keys_removed']==changes['new_full_keys_added'],'TopK insertion mass conservation')
    return changes,n
