"""Exact typed pool→unchanged original create_queues; full10M/first2.5M."""
import argparse
import time
import uuid
from pathlib import Path
from ..common import load,reference,dump_new,require
from ..portable_sources_v1.transport import verify,bind_plan,provenance
from ..external_sort import create_queues,identity_digest,SCALE,MAX_POOL
from .contracts import typed_release
from .coverage import validate_reference
from .sql_runtime import SqlGuard,configure,literal
from .domain import HydrogenDomainDB


def check_membership(db,expected):
    """Full bidirectional identities and original candidate feature equality."""
    counts=db.execute('SELECT count(*),count(DISTINCT full_key),count(DISTINCT cid) FROM pool').fetchone()
    require(counts==(expected,expected,expected),'Every typed candidate must occur once in exact novelty')
    require(db.execute('SELECT count(*) FROM candidates').fetchone()[0]==expected,'Typed pool census differs')
    for left,right in (('pool','candidates'),('candidates','pool')):
        require(db.execute('SELECT count(*) FROM '+left+' ANTI JOIN '+right+' USING(cid,full_key)').fetchone()[0]==0,
            'Novelty identities differ from the full typed filtered pool')
    require(db.execute('''SELECT count(*) FROM pool p JOIN candidates c USING(cid,full_key) WHERE
        p.heavy_atoms IS DISTINCT FROM c.heavy_atoms OR p.element_combination IS DISTINCT FROM c.element_combination
        OR p.generic_murcko IS DISTINCT FROM c.generic_murcko OR p.generic_ring_systems IS DISTINCT FROM c.generic_ring_systems''').fetchone()[0]==0,
        'Ranking features differ from exact immutable candidate structures')


def run(plan_path):
    import duckdb
    plan=load(plan_path);require(plan.get('schema')=='PUBCHEM_TYPED_EXACT_RANK_PLAN_V1','Wrong typed rank plan schema')
    bind_plan(plan)
    novelty_path=verify(plan['novelty_receipt']);novelty=load(novelty_path)
    filtered_path=verify(novelty['filtered_pool_receipt']);filtered=load(filtered_path);typed_release(filtered,novelty)
    query=load(verify(novelty['query_manifest']))
    require(query.get('schema')=='EXPANSION_TYPED_DECONTAMINATED_QUERY_PROJECTION_V1'
        and query['filtered_pool_receipt']==novelty['filtered_pool_receipt'],'Actual typed query/pool binding required')
    validate_reference(verify(novelty['reference']),'before')
    candidates=verify(filtered['candidates']);projection=verify(novelty['projection']);n=filtered['counts']['eligible_molecules']
    require(novelty['queries']==novelty['projection']['rows']==n,'Full exact novelty census required')
    root=Path(plan['output_directory']);require(root.is_absolute() and not root.is_symlink(),'Dedicated absolute typed rank output required')
    root.mkdir(parents=True,exist_ok=True);guard=SqlGuard(plan,root)
    import fcntl
    lock=(root/'parent.lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    require(not (root/'receipt.json').exists(),'Closed rank receipt already exists; reuse pinned result')
    attempt=root/('attempt_'+uuid.uuid4().hex);attempt.mkdir()
    db=duckdb.connect(str(attempt/'ranking.duckdb'));started=time.monotonic()
    try:
        configure(db,plan,attempt/'spill');guard.start(db)
        db.read_parquet(str(candidates)).create_view('candidates')
        db.read_json(str(projection),format='newline_delimited').create('pool')
        check_membership(db,n)
        require(db.execute('SELECT count(DISTINCT v1_reference_sha256),min(v1_reference_sha256) FROM pool').fetchone()
            ==(1,novelty['reference']['sha256']),'Actual complete Common reference pin differs')
        domain=HydrogenDomainDB(db)
        actual=create_queues(domain,seed=20261025,queue_size=5000000);require(actual==n,'Original create_queues census differs')
        require(domain.extended_predicates==1,'Expected original validation predicate was not extended exactly once')
        db.execute('COPY (SELECT * FROM queues ORDER BY stream,stream_rank) TO '+literal(attempt/'queues.parquet')+' (FORMAT PARQUET,COMPRESSION ZSTD)')
        db.execute('CREATE TABLE batch1 AS SELECT * FROM queues WHERE stream_rank<=1250000')
        db.execute('COPY (SELECT * FROM batch1 ORDER BY stream,stream_rank) TO '+literal(attempt/'batch1.parquet')+' (FORMAT PARQUET,COMPRESSION ZSTD)')
        db.execute('COPY (SELECT heavy_stratum,element_combination,count(*) AS remaining_pubchem_population FROM n_candidates GROUP BY ALL ORDER BY ALL) TO '+literal(attempt/'novelty_strata.parquet')+' (FORMAT PARQUET,COMPRESSION ZSTD)')
        cursor=db.execute('SELECT full_key,cid FROM pool ORDER BY full_key,cid');observed=identity_digest(iter(lambda:cursor.fetchone(),None))
        require(observed[0]==n,'Complete sorted identity digest census differs');db.execute('CHECKPOINT')
    finally:
        guard.done.set()
        if hasattr(guard,'thread'):guard.thread.join()
        db.close();lock.close()
    guard.close();verify(filtered['candidates']);verify(novelty['projection'])
    receipt={'schema':'expansion_nested_queues_v1','status':'CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED',
        'novelty_receipt':plan['novelty_receipt'],'filtered_pool':novelty['filtered_pool_receipt'],'pool_identity_sha256':observed[1],
        'pool_molecules':n,'workers':plan['workers'],'seed':20261025,'queue_molecules_each':5000000,'first_batch_molecules_each':1250000,
        'R_rule':'uniform_sha256_full_identity','N_rule':'v1_only_lexicographic_novelty_with_exact_size_element_proportional_interleaving',
        'exact_rational_finish_scale':str(SCALE),'maximum_supported_pool':MAX_POOL,'original_create_queues_source':reference(Path(__file__).parents[1]/'external_sort.py'),
        'typed_full_candidate_bidirectional_anti_join':True,'all_original_structural_ranking_features_equal':True,
        'H_only_heavy0_empty_element_stratum_retained':True,'original_ranking_math_unchanged':True,
        'queues':reference(attempt/'queues.parquet'),'batch1':reference(attempt/'batch1.parquet'),'strata':reference(attempt/'novelty_strata.parquet'),
        'downstream_features_used':False,'resource_plan':reference(plan_path),'wall_seconds':time.monotonic()-started}
    receipt['endpoint_execution']=provenance(plan)
    dump_new(root/'receipt.json',receipt);return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);run(p.parse_args().plan)


if __name__=='__main__':main()
