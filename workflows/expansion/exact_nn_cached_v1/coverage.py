"""Scientific fixed1M PRE-decon baseline/coverage, never a novelty pool release."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time
from ..common import load,reference,require,dump_new,wp5_key
from ..portable_sources_v1.transport import verify,bind_plan,provenance
from .engine import RECIPE,WIDTH,ALGORITHM,file_frame
from .cache import QueryCache,canonical,record_parent_sqlite
from .contracts import baseline_query
from .run import Guard,rows,allocation_guard
from .workers import exact_batches
from .sql_runtime import literal


def validate_reference(path,role):
    m=load(path)
    require(m.get('status')=='COMPLETE' and m.get('fingerprint_recipe')==RECIPE and m.get('targets_present') is False,
        'Complete exact reference required')
    if role=='before':
        require(m.get('schema')=='expansion_exact_ecfp4_reference_v1','Baseline requires full true Common reference')
        projection=load(verify(m['input_manifest']))
        require(projection.get('schema')=='expansion_common_v1_structure_projection_v1'
            and projection.get('one_row_per_common_molecule') is True and projection.get('population_roles')==['TRAIN','VAL']
            and projection['common_molecules']==m['molecules'],'Complete Common molecular census required')
        if projection.get('producer_schema')=='ALPHA_COMMON_GRAPH_CONTINUATION_PRODUCER_V1':
            from .alpha_common import validate_manifest
            validate_manifest(projection)
        elif projection.get('producer_schema')=='ALPHA_COMMON_GENERIC_REPRESENTATION_REPAIR_COMPLETION_PRODUCER_V1':
            from .alpha_common_repaired import validate_manifest
            validate_manifest(projection)
        else:
            verify(projection['common_population_manifest']);verify(projection['actual_full_receipt_reference'])
            review=load(verify(projection['final_Root_graph_review_reference']))
            require(review.get('status')=='APPROVED_EXACT_COMMON_REFERENCE_PROJECTION' and review.get('reviewer')=='root',
                'Actual full Common graph review required')
    elif role=='after':
        require(m.get('schema')=='EXPANSION_EXACT_AUGMENTED_REFERENCE_V1' and m.get('added_molecules')==2500000,
            'Actual full2.5M augmentation required')
        base_path=verify(m['base_reference_manifest']);base=validate_reference(base_path,'before')
        source=load(verify(m['added_source_manifest']))
        require(source.get('schema')=='PUBCHEM_UFF3_ORDERED_SOURCE_MANIFEST_V1' and source.get('molecules')==2500000
            and source.get('molecules_by_stream')=={'R':1250000,'N':1250000},'Frozen actual R/N source required')
        require(m['molecules']==base['molecules']+2500000,'Augmented reference cardinality differs')
        # Independently prove that every original ordinal remains the prefix.
        for name,width in (('fingerprints',WIDTH),('keys',28)):
            path=verify(m[name]);base_ref=base[name];remaining=base['molecules']*width;sha=hashlib.sha256()
            require(base_ref['bytes']==remaining,'Base reference width differs')
            with path.open('rb') as stream:
                while remaining:
                    block=stream.read(min(8<<20,remaining));require(bool(block),'Augmented reference prefix truncated')
                    sha.update(block);remaining-=len(block)
            require(sha.hexdigest()==base_ref['sha256'],'Original full reference ordinals changed in augmentation')
    else:raise ValueError('EXPLICIT_BEFORE_OR_AFTER_REFERENCE_ROLE_REQUIRED')
    fp=verify(m['fingerprints']);keys=verify(m['keys'])
    require(fp.stat().st_size==m['molecules']*WIDTH and keys.stat().st_size==m['molecules']*28,'Reference row widths differ')
    return m


def sample_membership(q,source,plan,expected_molecules=1000000):
    """Exact membership check; no sample identities or baseline rows are dropped."""
    import duckdb
    db=duckdb.connect()
    try:
        db.execute('SET threads='+str(int(plan['workers'])));db.execute('SET memory_limit='+literal(str(plan['parent_rss_cap_bytes']//2)+'B'))
        db.read_parquet(str(verify(q['sample_membership']))).create_view('expected')
        db.execute("SET temp_directory=''")
        db.read_json(str(source),format='newline_delimited',columns={'cid':'BIGINT','full_key':'VARCHAR'}).create_view('observed')
        require(db.execute('SELECT count(*),count(DISTINCT full_key),count(DISTINCT cid),count(DISTINCT sample_ordinal),min(sample_ordinal),max(sample_ordinal) FROM expected').fetchone()
            ==(expected_molecules,expected_molecules,expected_molecules,expected_molecules,0,expected_molecules-1),'Complete frozen sample membership ordinals required')
        require(db.execute('SELECT count(*),count(DISTINCT full_key),count(DISTINCT cid) FROM observed').fetchone()==(expected_molecules,expected_molecules,expected_molecules),
            'Exactly1M unique PRE-decon query identities required')
        require(db.execute('SELECT count(*) FROM observed ANTI JOIN expected USING(cid,full_key)').fetchone()[0]==0
            and db.execute('SELECT count(*) FROM expected ANTI JOIN observed USING(cid,full_key)').fetchone()[0]==0,
            'Scientific projection differs from frozen sample membership')
    finally:db.close()


def reference_identity_index(cache,keys,n,guard):
    closed=cache.db.execute("SELECT value FROM meta WHERE key='complete_reference_identity_index'").fetchone()
    if closed:
        require(int(closed[0])==n,'Reference identity census changed');return
    cache.db.execute('CREATE TABLE IF NOT EXISTS reference_keys(full_key TEXT PRIMARY KEY) WITHOUT ROWID')
    count=0
    with keys.open('rb') as stream:
        for line in stream:
            require(len(line)==28 and line[-1:]==b'\n','Reference key row width differs')
            key=line[:-1].decode('ascii');wp5_key(key)
            cache.db.execute('INSERT OR IGNORE INTO reference_keys VALUES(?)',(key,));count+=1
            if count%2000==0:cache.commit();guard.poll(reserve=32<<20)
    require(count==n,'Complete reference identity index census differs')
    cache.db.execute("INSERT INTO meta VALUES('complete_reference_identity_index',?)",(str(n),));cache.commit()


def run(plan_path, *, startup_proof=None):
    plan=load(plan_path);require(plan.get('schema')=='PUBCHEM_EXACT_SCIENTIFIC_COVERAGE_PLAN_V1','Wrong coverage plan schema')
    startup_reference=reference(startup_proof) if startup_proof is not None else None
    bind_plan(plan)
    workers=plan['workers'];cap=plan['worker_rss_cap_bytes'];startup_memory=allocation_guard(plan)
    baseline_path=verify(plan['baseline_receipt']);q=load(baseline_path);source=baseline_query(q,actual_review_reference=plan.get('baseline_actual_review_reference'),
        receipt_reference=plan['baseline_receipt']);source_frame=file_frame(source)
    ref_path=verify(plan['reference_manifest']);role=plan['reference_role'];m=validate_reference(ref_path,role);n=m['molecules']
    root=Path(plan['output_directory']);require(root.is_absolute() and not root.is_symlink(),'Absolute dedicated coverage output required')
    root.mkdir(parents=True,exist_ok=True)
    import fcntl
    lock=(root/'parent.lock').open('a+b');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    guard=Guard(plan,root);guard.poll(True,32<<20)
    sample_membership(q,source,plan)
    cache=QueryCache(root/'queries.sqlite',plan['reference_manifest']['sha256'],n,sqlite_cache_bytes=plan.get('sqlite_cache_bytes'))
    sqlite_runtime_ref=record_parent_sqlite(root,{'query_cache':cache.sqlite_runtime})
    source_key=plan['baseline_receipt']['sha256'];member=cache.source(source_key)
    batch=plan['query_batch'];require(type(batch)is int and 1<=batch<=4096,'Bounded coverage batch required')
    commit_queries=plan.get('cache_commit_queries',4096)
    require(type(commit_queries)is int and 1<=commit_queries<=4096,'Bounded exact cache checkpoint size required')
    started=time.monotonic();computed=evaluated=pruned=0;pids=set()
    try:
        if cache.source_ingestion(source_key) is None:
            window=0
            for ordinal,row,raw,size in rows(source,1000000,source_frame):
                cache.add(raw,ordinal,member);window+=size+4096
                if window>=8<<20:cache.commit();guard.poll(True,32<<20);window=0
            cache.close_ingestion(source_key,{'rows':1000000,'baseline_receipt':plan['baseline_receipt']})
        else:require(cache.source_ingestion(source_key)=={'rows':1000000,'baseline_receipt':plan['baseline_receipt']},'Scientific baseline source changed')
        reference_identity_index(cache,verify(m['keys']),n,guard)
        guard.poll(True,64<<20)
        attempt=0
        while (root/('attempt'+str(attempt)+'.workers.jsonl')).exists():attempt+=1
        metrics=root/('attempt'+str(attempt)+'.workers.jsonl')
        with metrics.open('x',encoding='utf-8') as log:
            def ready(value):pids.add(value['worker_pid']);log.write(json.dumps({'kind':'reference_loaded',**value})+'\n');log.flush()
            uncommitted=0;last_commit=time.monotonic()
            if cache.pending_count(member):
                for result in exact_batches(verify(m['fingerprints']),n,cache.pending_batches(batch,member),
                        workers=workers,worker_rss_cap_bytes=cap,ready_callback=ready):
                    for identity,raw,value in result.pop('results'):
                        cache.store(identity,raw,value);computed+=1;uncommitted+=1
                        evaluated+=value['evaluated_references'];pruned+=value['strictly_bound_pruned_references']
                    if uncommitted>=commit_queries or time.monotonic()-last_commit>=30:
                        cache.commit();uncommitted=0;last_commit=time.monotonic()
                    log.write(json.dumps({'kind':'exact_batch',**result})+'\n');log.flush();guard.poll(reserve=64<<20)
            cache.commit()
            log.flush();os.fsync(log.fileno())
        require(cache.pending_count(member)==0,'Incomplete scientific coverage math')
        projection=root/('attempt'+str(attempt)+'.coverage.jsonl');self_counts={'identity_present':0,'fingerprint_score_one':0,'nearest_identity_equal':0}
        with projection.open('x',encoding='utf-8') as out,verify(m['keys']).open('rb') as keys:
            window=0
            for ordinal,row,raw,size in rows(source,1000000,source_frame):
                value=cache.lookup(raw);index=value['reference_ordinal'];keys.seek(index*28);key=keys.read(28).decode('ascii').rstrip('\n');wp5_key(key)
                present=cache.db.execute('SELECT 1 FROM reference_keys WHERE full_key=?',(row['full_key'],)).fetchone() is not None
                fingerprint_self=value['score']==1.;nearest_self=key==row['full_key']
                self_counts['identity_present']+=int(present);self_counts['fingerprint_score_one']+=int(fingerprint_self);self_counts['nearest_identity_equal']+=int(nearest_self)
                out.write(json.dumps({'sample_ordinal':ordinal,'cid':row['cid'],'full_key':row['full_key'],
                    'nearest_reference_tanimoto':value['score'],'reference_ordinal':index,'nearest_reference_key':key,
                    'reference_identity_present':present,'fingerprint_self_match':fingerprint_self,'nearest_identity_self_match':nearest_self,
                    'reference_manifest_sha256':plan['reference_manifest']['sha256'],'reference_role':role},separators=(',',':'),allow_nan=False)+'\n')
                window+=size+4096
                if window>=8<<20:out.flush();guard.poll(True,32<<20);window=0
            out.flush();os.fsync(out.fileno())
        guard.poll(True);verify(plan['baseline_receipt']);verify(q['projection']);verify(m['fingerprints']);verify(m['keys'])
        receipt={'schema':'EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1','status':'COMPLETE','baseline_receipt':plan['baseline_receipt'],
            'reference_manifest':plan['reference_manifest'],'reference_role':role,'queries':1000000,'reference_molecules':n,
            'distinct_query_fingerprints':cache.source_count(member),'self_match_counts':self_counts,'nearest_similarity_exact':True,
            'fingerprint_self_match_definition':'RDKit_Tanimoto_score_is_one; empty_fingerprint_self_score_is_zero_in_pinned_RDKit',
            'fingerprint_recipe':RECIPE,'algorithm':ALGORITHM,'downstream_features_used':False,'decontamination_applied_to_sample':False,
            'candidate_pool_release_authorized':False,'training_release_authorized':False,'projection':{**reference(projection),'rows':1000000},
            'new_distinct_queries_this_attempt':computed,'evaluated_references_this_attempt':evaluated,
            'strictly_bound_pruned_references_this_attempt':pruned,'worker_pids_observed':sorted(pids),'worker_metrics':reference(metrics),
            'resource_plan':reference(plan_path),'wall_seconds_this_attempt':time.monotonic()-started}
        receipt['sqlite_runtime_reference']=sqlite_runtime_ref
        receipt['startup_memory_observation']=startup_memory
        receipt['endpoint_execution']=provenance(plan)
        if startup_reference is not None:receipt['launcher_startup_proof_reference']=startup_reference
        dump_new(root/('attempt'+str(attempt)+'.receipt.json'),receipt);return receipt
    finally:cache.close();lock.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',required=True,type=Path)
    p.add_argument('--startup-proof',type=Path,help='Optional actual launcher metadata, retained by exact byte reference')
    a=p.parse_args();run(a.plan,startup_proof=a.startup_proof)


if __name__=='__main__':main()
