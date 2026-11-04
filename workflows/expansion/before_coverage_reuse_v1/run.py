"""Actual Alpha before coverage; closed FP reuse plus missing-only exact workers."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import sys
import time
import traceback
from . import catalog as C


def read(Q,ref):
    Q.need(ref['bytes']<=2<<20,'Small closed producer/plan/proof metadata')
    return Q.load(Q.verify(ref))


def dependencies(plan,Q,parent):
    """All actual current writers/rank are C0 before opening source journals."""
    from ..alpha_sharded_novelty_v1.partition import cover,assignment
    rank_binding=plan['rank_completed'];rank=read(Q,rank_binding['receipt_reference'])
    parent(rank_binding['runtime'],rank_binding['accounting_reference'])
    proof=read(Q,rank_binding['startup_proof_reference'])
    Q.need(proof['request']['producer_plan_reference']==rank['resource_plan']==rank_binding['plan_reference']
        and str(proof['job_id'])==rank_binding['runtime']['job_id']==rank['actual_parent']['job_id']
        and proof['uid']==1264 and proof['endpoint']==Q.ENDPOINT,'Actual completed rank plan/startup/result')
    novelty=read(Q,rank['novelty_receipt'])
    Q.need(rank['schema']=='expansion_nested_queues_v1'and rank['status']=='CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED'
        and novelty['status']=='COMPLETE'and novelty['schema']=='PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1'
        and novelty['reference']==plan['reference_manifest']and novelty['reference_molecules']==C.N
        and novelty['nearest_similarity_exact']is True and novelty['pairwise_disjoint_hash_assignments_and_complete_cover']is True,
        'Actual complete all-pool exact source, same full196 reference, not a partial shard')
    sources=plan['closed_score_sources'];Q.need(len(sources)==2,'Both real closed source roots required')
    Q.need({Q.canonical(v['manifest_reference'])for v in sources}=={Q.canonical(v)for v in novelty['partition_manifest_references']},
        'Exactly the two actual full novelty partitions adopted by rank')
    observed=[];assignments=[];locks=[]
    try:
        for item in sources:
            parent(item['runtime'],item['accounting_reference'])
            original_plan=read(Q,item['plan_reference']);proof=read(Q,item['startup_proof_reference']);manifest=read(Q,item['manifest_reference'])
            root=Path(item['manifest_reference']['path']).parent
            Q.need(Path(original_plan['output_directory'])==root and proof['request']['producer_plan_reference']==item['plan_reference']==manifest['resource_plan']
                and str(proof['job_id'])==item['runtime']['job_id']and proof['uid']==1264 and proof['endpoint']==Q.ENDPOINT
                and manifest['status']=='SHARD_COMPLETE'and manifest['reference']==plan['reference_manifest']
                and manifest['filtered_pool_reference']==rank['filtered_pool']and manifest['nearest_similarity_exact']is True
                and manifest['reference_molecules']==C.N and manifest['backend_adoption_reference']==plan['backend_adoption_reference'],
                'Own terminal original-score-root actual writer/proof/reference binding')
            binding=read(Q,manifest['source_binding_reference'])
            Q.need(binding=={k:manifest[k]for k in(*C.PRESERVED,'backend_adoption_reference')},'Exact derived six-field source binding')
            old_ref=Q.reference(root/'source_binding.json');old=read(Q,old_ref)
            Q.need(all(old[k]==binding[k]for k in C.PRESERVED),'All five original non-backend binding fields preserved')
            lineage_ref=manifest.get('equivalent_backend_continuation_reference')
            if old!=binding:
                lineage=read(Q,lineage_ref)
                Q.need(lineage['original_source_binding_reference']==old_ref
                    and lineage['derived_source_binding_reference']==manifest['source_binding_reference']
                    and lineage['native_equivalence_reference']==plan['backend_adoption_reference']
                    and lineage['original_binding_rewritten']is False,'Actual old206/new-equivalent cache lineage')
            assignments.append(assignment(manifest))
            handle=(root/'parent.lock').open('rb');fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(handle)
            observed.append(dict(binding=item,manifest=manifest,root=str(root),original_binding_reference=old_ref,
                                 derived_binding_reference=manifest['source_binding_reference'],lineage_reference=lineage_ref))
        cover(assignments)
        Q.need(sum(v['manifest']['queries']for v in observed)==novelty['queries']==rank['pool_molecules'],
               'Complete source-partition/rank candidate mass')
        return observed,locks
    except BaseException:
        for lock in locks:lock.close()
        raise


def populate(db,source,source_frame,q,plan,guard,Q,rows,pa):
    db.execute('CREATE TABLE sample(ordinal BIGINT,cid BIGINT,full_key VARCHAR,ecfp4_2048_hex VARCHAR)')
    values=[];bytes_read=0;count=0
    for ordinal,row,raw,size in rows(source,1000000,source_frame):
        values.append(dict(ordinal=ordinal,cid=row['cid'],full_key=row['full_key'],ecfp4_2048_hex=raw.hex()));bytes_read+=size;count+=1
        if len(values)>=8192:
            db.register('_input',pa.Table.from_pylist(values));db.execute('INSERT INTO sample SELECT * FROM _input');db.unregister('_input');values=[];guard.poll()
    if values:
        db.register('_input',pa.Table.from_pylist(values));db.execute('INSERT INTO sample SELECT * FROM _input');db.unregister('_input')
    Q.need(count==1000000 and bytes_read==source_frame[2],'Exact whole1M query EOF, no extra or missing rows')
    db.read_parquet(str(Q.verify(q['sample_membership']))).create_view('membership')
    Q.need(db.execute('SELECT count(*),count(DISTINCT cid),count(DISTINCT full_key),min(ordinal),max(ordinal)FROM sample').fetchone()
        ==(1000000,1000000,1000000,0,999999),'All original sample identities/ordinals once')
    Q.need(db.execute('SELECT count(*)FROM sample s FULL JOIN membership m ON s.ordinal=m.sample_ordinal WHERE s.cid IS DISTINCT FROM m.cid OR s.full_key IS DISTINCT FROM m.full_key').fetchone()[0]==0,
        'Exact frozen1M membership AND original sampleOrdinal order')
    db.execute('CREATE TABLE query_fp AS SELECT ecfp4_2048_hex,min(ordinal)first_ordinal FROM sample GROUP BY ecfp4_2048_hex')
    return db.execute('SELECT count(*)FROM query_fp').fetchone()[0]


def import_hits(db,sources,out,guard,Q,pq,literal,*,uid=1264):
    catalogs=[];score_parts=score_rows=0;paths={};frames={}
    with(out/'all_score_parts.jsonl').open('xb')as allparts:
        for index,source in enumerate(sources):
            path=out/('score_catalog_%d.jsonl'%index)
            stats=C.collect(source['root'],uid,path,guard.poll)
            Q.need(stats['rows']==source['manifest']['distinct_query_fingerprints'],'Closed score catalog has every unique FP exactly once')
            entry=dict(source=source['binding'],original_binding_reference=source['original_binding_reference'],
                derived_binding_reference=source['derived_binding_reference'],lineage_reference=source['lineage_reference'],
                catalog_reference=Q.reference(path),**stats)
            # Keep even the journal reference list outside the small final JSON.
            record=out/('score_catalog_%d.json'%index);Q.write(record,entry);catalogs.append(Q.reference(record))
            with path.open('rb')as stream:
                for line in stream:
                    item=json.loads(line);ref=item['reference'];before=C.actual_frame(ref['path'],uid)
                    Q.need(list(before)==item['current_frame'],'Score frame changed after terminal catalog closure')
                    actual=Q.verify(ref);footer=pq.ParquetFile(actual)
                    Q.need(footer.metadata.num_rows==ref['rows']and set(footer.schema_arrow.names)==C.FIELDS
                        and str(footer.schema_arrow.field('nearest_v1_tanimoto').type)=='double',
                        'Actual score footer/nine-column schema and original binary64 score type')
                    Q.need(str(actual)not in frames,'A physical source score path cannot occur in both partitions')
                    paths.setdefault(ref['fp_bucket'],[]).append(str(actual));frames[str(actual)]=before
                    allparts.write(C.canonical(item)+b'\n');score_parts+=1;score_rows+=ref['rows'];guard.poll()
        allparts.flush();os.fsync(allparts.fileno())
    Q.need(paths,'No complete score rows')
    created=False
    columns=','.join(sorted(C.FIELDS))
    # Hash the matching sample-FP set once per physical bucket, never once per
    # 4096-row score file. Only path/frame metadata is retained in Python.
    for bucket,items in sorted(paths.items()):
        db.read_parquet(items,union_by_name=True).create_view('incoming_score',replace=True)
        if not created:
            db.execute('CREATE TABLE hits AS SELECT '+columns+' FROM incoming_score WHERE false');created=True
        db.execute('CREATE OR REPLACE TEMP TABLE needed_fp AS SELECT ecfp4_2048_hex FROM query_fp WHERE substr(ecfp4_2048_hex,1,1)='+literal(bucket))
        db.execute('INSERT INTO hits SELECT '+','.join('s.'+name for name in sorted(C.FIELDS))+' FROM incoming_score s SEMI JOIN needed_fp q USING(ecfp4_2048_hex)')
        guard.poll(True)
    for path,before in frames.items():
        Q.need(C.actual_frame(path,uid)==before,'Score bytes/frame changed during bulk verified scan')
    hits,unique=db.execute('SELECT count(*),count(DISTINCT ecfp4_2048_hex)FROM hits').fetchone()
    Q.need(hits==unique,'No duplicated/conflicting reused FP across original closed partitions')
    path=out/'reused_baseline_scores.parquet'
    db.execute('COPY(SELECT * FROM hits ORDER BY ecfp4_2048_hex)TO '+literal(path)+'(FORMAT PARQUET,COMPRESSION ZSTD)')
    return dict(score_source_catalog_references=catalogs,closed_score_part_catalog_reference=Q.reference(out/'all_score_parts.jsonl'),
        scanned_closed_score_parts=score_parts,scanned_closed_score_rows=score_rows,reused_distinct_query_fingerprints=hits,
        reused_original9_column_results_reference=dict(Q.reference(path),rows=hits),source_score_whole_SHA_verified=True)


def seed(cache,db,member,key_data,guard,Q):
    columns=['ecfp4_2048_hex','first_ordinal',*sorted(C.FIELDS-{'ecfp4_2048_hex'})]
    sql='SELECT q.ecfp4_2048_hex,q.first_ordinal,'+','.join('h.'+k for k in columns[2:])+' FROM query_fp q LEFT JOIN hits h USING(ecfp4_2048_hex) ORDER BY q.ecfp4_2048_hex'
    cursor=db.execute(sql);reused=missing=0
    while True:
        records=cursor.fetchmany(4096)
        if not records:break
        for values in records:
            row=dict(zip(columns,values));raw=bytes.fromhex(row['ecfp4_2048_hex']);identity=cache.add(raw,row.pop('first_ordinal'),member)
            if row['reference_molecules']is None:missing+=1;continue
            result=C.result_value(row);ordinal=result['reference_ordinal']
            Q.need(key_data[ordinal*28:(ordinal+1)*28].decode('ascii').rstrip('\n')==row['nearest_v1_key'],
                   'Original stored nearest key equals complete196 ordinal key')
            cache.store(identity,raw,result);reused+=1
        cache.commit();guard.poll()
    return reused,missing


def execute(plan_path,proof_path):
    from ..alpha_runtime_v1 import common as Q,profile
    from ..portable_sources_v1.transport import bind_plan,verify,provenance
    from ..exact_nn_cached_v1 import engine,coverage,cache as K,contracts,run as original_run
    from ..alpha_sharded_novelty_v1.run import ShardGuard
    from ..exact_nn_inverted_production_v1 import workers,authority
    from ..uff3_alpha_runtime_v1.terminal import parent
    from ..exact_nn_cached_v1.sql_runtime import configure,literal
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    plan=Q.load(plan_path);proof=Q.load(proof_path);actual=profile.admit(plan,minimum_workers=16);request=proof['request']
    Q.need(plan['schema']=='PUBCHEM_FIXED1M_CLOSED_FP_REUSE_COVERAGE_PLAN_V1'and plan['reference_role']=='before'
        and request['producer_plan_reference']==Q.reference(plan_path)and request['execution_argv']==plan['execution_argv']
        and request['scope_key']==plan['scope_key']and str(proof['job_id'])==actual['job_id']
        and proof['uid']==1264 and proof['endpoint']==Q.ENDPOINT
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and sys.argv[-4:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],
        'Actual independent before producer plan/startup/Alpha UID; never original201 lineage')
    bind_plan(plan)
    borrowed=dict(engine=engine,coverage=coverage,cache=K,contracts=contracts,workers=workers,authority=authority)
    for name,module in borrowed.items():
        ref=Q.reference(module.__file__)
        Q.need(ref==plan['borrowed_source_references'][name]and ref in request['source_references'],
               'Exact actual borrowed absolute source path/body; no engine/Core5 shadowing')
    pins=[Q.reference(path)for path in Path(__file__).parent.glob('*.py')]
    Q.need(all(ref in request['source_references']for ref in pins),'Actual new adapter sources startup pinned')
    Q.need(str(actual['job_id'])!='1885201'and any(str(item['runtime']['job_id'])=='1885201'
        for item in plan['excluded_active_allocations']),'201 remains independent active budget exclusion')
    active=next(item for item in plan['excluded_active_allocations']if str(item['runtime']['job_id'])=='1885201')
    active_plan=read(Q,active['plan_reference']);out=Path(plan['output_directory'])
    Q.need(out.is_absolute()and not out.exists()and not out.is_relative_to(Path(active_plan['output_directory']))
        and not Path(active_plan['output_directory']).is_relative_to(out),'Fresh independent output, never active201 cache/tree')
    original_run.allocation_guard(plan);adopted,packed=authority.adopted(plan['backend_adoption_reference'])
    Q.need(adopted['reference_manifest_reference']==plan['reference_manifest']and packed['molecules']==C.N,'Same proven full196 native kernel')
    q=read(Q,plan['baseline_receipt']);source=contracts.baseline_query(q,actual_review_reference=plan.get('baseline_actual_review_reference'),receipt_reference=plan['baseline_receipt'])
    source_frame=engine.file_frame(source);coverage.validate_reference(verify(plan['reference_manifest']),'before')
    guard=ShardGuard(plan,out);locks=[];cache=None;db=None;started=time.monotonic()
    out.mkdir(mode=0o700,parents=True)
    try:
        sources,locks=dependencies(plan,Q,parent)
        for item in sources:
            root=Path(item['root']);scope=Path(plan['output_scope_root'])
            Q.need(not out.is_relative_to(root)and not root.is_relative_to(out)
                and not scope.is_relative_to(root)and not root.is_relative_to(scope),'Independent private runtime scope, never an upstream score root')
        Q.need(not Path(plan['output_scope_root']).is_relative_to(Path(active_plan['output_directory']))
            and not Path(active_plan['output_directory']).is_relative_to(Path(plan['output_scope_root'])),
            'Private budget scope excludes the active201 tree')
        guard.poll(True)
        key_data=verify(packed['keys']).read_bytes();Q.need(len(key_data)==C.N*28,'All original reference ordinal keys')
        reference_keys={key_data[i:i+27].decode('ascii')for i in range(0,len(key_data),28)}
        coverage.sample_membership(q,source,plan)
        db=duckdb.connect(str(out/'join.duckdb'));configure(db,plan,out/'spill')
        distinct=populate(db,source,source_frame,q,plan,guard,Q,original_run.rows,pa)
        reused=import_hits(db,sources,out,guard,Q,pq,literal)
        cache=K.QueryCache(out/'queries.sqlite',plan['reference_manifest']['sha256'],C.N,sqlite_cache_bytes=plan.get('sqlite_cache_bytes',1<<30))
        member=cache.source(plan['baseline_receipt']['sha256']);n_reused,n_missing=seed(cache,db,member,key_data,guard,Q)
        Q.need(n_reused==reused['reused_distinct_query_fingerprints']and n_reused+n_missing==distinct
            and cache.source_count(member)==distinct and cache.pending_count(member)==n_missing,'Exact reused/pending distinct FP conservation')
        cache.close_ingestion(plan['baseline_receipt']['sha256'],dict(rows=1000000,baseline_receipt=plan['baseline_receipt']))
        db.execute('CHECKPOINT');db.close();db=None
        metrics=out/'missing_only.workers.jsonl';computed=evaluated=pruned=0;pids=set()
        with metrics.open('x')as log:
            def ready(value):
                pids.add(value['worker_pid']);log.write(json.dumps(dict(kind='reference_loaded',**value))+'\n');log.flush()
            if n_missing:
                for result in workers.exact_batches(verify(packed['fingerprints']),C.N,cache.pending_batches(plan.get('query_batch',128),member),
                    workers=plan['workers'],worker_rss_cap_bytes=plan['worker_rss_cap_bytes'],ready_callback=ready,
                    backend_adoption_reference=plan['backend_adoption_reference']):
                    for identity,raw,value in result.pop('results'):
                        cache.store(identity,raw,value);computed+=1;evaluated+=value['evaluated_references'];pruned+=value['strictly_bound_pruned_references']
                    cache.commit();log.write(json.dumps(dict(kind='exact_missing_batch',**result))+'\n');log.flush();guard.poll()
            log.flush();os.fsync(log.fileno())
        Q.need(computed==n_missing and cache.pending_count(member)==0,'All and only missing FPs freshly computed; pending0')
        projection=out/'attempt0.coverage.jsonl';counts=dict(identity_present=0,fingerprint_score_one=0,nearest_identity_equal=0);count=size_read=0
        with projection.open('x')as stream:
            for ordinal,row,raw,size in original_run.rows(source,1000000,source_frame):
                value=cache.lookup(raw);index=value['reference_ordinal'];key=key_data[index*28:index*28+27].decode('ascii')
                present=row['full_key']in reference_keys;score_one=value['score']==1.;equal=key==row['full_key']
                counts['identity_present']+=present;counts['fingerprint_score_one']+=score_one;counts['nearest_identity_equal']+=equal
                stream.write(json.dumps(dict(sample_ordinal=ordinal,cid=row['cid'],full_key=row['full_key'],
                    nearest_reference_tanimoto=value['score'],reference_ordinal=index,nearest_reference_key=key,
                    reference_identity_present=present,fingerprint_self_match=score_one,nearest_identity_self_match=equal,
                    reference_manifest_sha256=plan['reference_manifest']['sha256'],reference_role='before'),separators=(',',':'),allow_nan=False)+'\n')
                count+=1;size_read+=size
                if count%8192==0:stream.flush();guard.poll()
            stream.flush();os.fsync(stream.fileno())
        Q.need(count==1000000 and size_read==source_frame[2]and engine.file_frame(source)==source_frame,'Whole unchanged1M sample EOF/order after export')
        cache.commit();cache.close();cache=None;guard.poll(True)
        result=dict(schema='EXPANSION_EXACT_SCIENTIFIC_COVERAGE_V1',status='COMPLETE',
            producer_schema='CLOSED_FP_REUSE_PLUS_INVERTED_MISSING_FIXED1M_V1',baseline_receipt=plan['baseline_receipt'],
            reference_manifest=plan['reference_manifest'],reference_role='before',queries=1000000,reference_molecules=C.N,
            distinct_query_fingerprints=distinct,self_match_counts=counts,nearest_similarity_exact=True,
            fingerprint_self_match_definition='RDKit_Tanimoto_score_is_one; empty_fingerprint_self_score_is_zero_in_pinned_RDKit',
            fingerprint_recipe=engine.RECIPE,algorithm=engine.ALGORITHM,downstream_features_used=False,
            decontamination_applied_to_sample=False,candidate_pool_release_authorized=False,training_release_authorized=False,
            projection=dict(Q.reference(projection),rows=1000000),
            new_distinct_queries_this_attempt=computed,evaluated_references_this_attempt=evaluated,
            strictly_bound_pruned_references_this_attempt=pruned,worker_pids_observed=sorted(pids),worker_metrics=Q.reference(metrics),
            resource_plan=Q.reference(plan_path),launcher_startup_proof_reference=Q.reference(proof_path),
            actual_parent=actual,endpoint_execution=provenance(plan),wall_seconds_this_attempt=time.monotonic()-started,
            original201_touched=False,original_coverage_function_or_source_modified=False,
            new_independent_adapter_source_references=pins,borrowed_source_references=plan['borrowed_source_references'],
            actual_closed_source_bindings=plan['closed_score_sources'],actual_closed_rank_binding=plan['rank_completed'],**reused)
        Q.write(out/'attempt0.receipt.json',result);return result
    except BaseException:
        Q.write(out/'failure.json',dict(error=traceback.format_exc(),partials_preserved=True,original201_touched=False));raise
    finally:
        if cache is not None:cache.close()
        if db is not None:db.close()
        for lock in locks:lock.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True,type=Path);parser.add_argument('--startup-proof',required=True,type=Path)
    args=parser.parse_args();print(json.dumps(execute(args.plan,args.startup_proof),sort_keys=True))


if __name__=='__main__':main()
