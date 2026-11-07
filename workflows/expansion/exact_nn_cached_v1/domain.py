"""Explicit H-only input-domain extension; original queue mathematics unchanged."""
from collections import defaultdict
from fractions import Fraction
import heapq
from .. import ranking as original
from ..common import require,stable_hash

_BAD="OR element_combination IS NULL OR NOT regexp_full_match(element_combination,'[0-9]+(,[0-9]+)*')"
_ALLOWED="OR element_combination IS NULL OR NOT (regexp_full_match(element_combination,'[0-9]+(,[0-9]+)*') OR (heavy_atoms=0 AND element_combination=''))"


def projected_row(row):
    if type(row.get('heavy_atoms'))is int and row['heavy_atoms']==0 and row.get('element_combination')=='':
        # Reuse every other original predicate. The validation-only copy is
        # never ranked/exported; actual heavy0/empty text remains unchanged.
        original.projected_row({**row,'heavy_atoms':1})
        return row
    return original.projected_row(row)


class HydrogenDomainDB:
    """Adapt only the original SQL input predicate, never its sorting queries."""
    def __init__(self,db):self.db=db;self.extended_predicates=0
    def __getattr__(self,name):return getattr(self.db,name)
    def execute(self,sql,*args,**kwargs):
        if sql.lstrip().startswith('SELECT count(*) FROM pool WHERE') and _BAD in sql:
            require(sql.count(_BAD)==1,'Original queue validation predicate changed')
            sql=sql.replace(_BAD,_ALLOWED);self.extended_predicates+=1
        return self.db.execute(sql,*args,**kwargs)


def reference_queues(rows,seed=20261025,queue_size=5,max_rows=100000):
    """Small independent exact-fraction oracle, using unchanged original keys."""
    pool=[];seen=set();refs=set()
    for value in rows:
        require(len(pool)<max_rows,'Bounded mathematical fixture oracle only')
        row=projected_row(value);require(row['full_key'] not in seen,'Duplicate input identity')
        seen.add(row['full_key']);refs.add(row['v1_reference_sha256']);pool.append(row)
    require(len(refs)==1 and 0<queue_size and 2*queue_size<=len(pool),'Exact disjoint mathematical fixture scope required')
    pool.sort(key=lambda r:(stable_hash('R-uniform',seed,r['full_key']),r['full_key'],r['cid']))
    r=pool[:queue_size];strata=defaultdict(list)
    for row in pool[queue_size:]:strata[(original.heavy_bin(row['heavy_atoms']),row['element_combination'])].append(row)
    for group in strata.values():group.sort(key=lambda row:original.novelty_key(row,seed),reverse=True)
    heap=[(Fraction(1,2*len(group)),key,0) for key,group in strata.items()];heapq.heapify(heap);n=[]
    while len(n)<queue_size:
        _,key,index=heapq.heappop(heap);group=strata[key];n.append(group[index]);index+=1
        if index<len(group):heapq.heappush(heap,(Fraction(2*index+1,2*len(group)),key,index))
    return {stream:[{'stream':stream,'stream_rank':i,'cid':row['cid'],'full_key':row['full_key']}
        for i,row in enumerate(group,1)] for stream,group in (('R',r),('N',n))}
