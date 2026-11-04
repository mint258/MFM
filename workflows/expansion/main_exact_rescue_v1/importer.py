"""Offline Alpha import of Main-native closed scores; original data never rewritten."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import threading
import uuid
from . import common as C

FIELDS={'ecfp4_2048_hex','nearest_v1_key','nearest_v1_tanimoto','reference_ordinal','score_numerator',
        'score_denominator','evaluated_references','strictly_bound_pruned_references','reference_molecules'}
INTS=FIELDS-{'ecfp4_2048_hex','nearest_v1_key','nearest_v1_tanimoto'}


def bits(value:float)->bytes:return struct.pack('<d',value)


def load_main_parts(main,transport,pq):
    catalog=transport.resolve(main['parts_catalog_reference']);path=C.verify(catalog);before=C.frame(path);parts=[];counts={b:0 for b in '0123456789abcdef'}
    with path.open('rb')as stream:
        for raw in stream:
            C.need(len(raw)<=1<<20 and raw.endswith(b'\n'),'Whole newline Main score catalog')
            part=json.loads(raw);bucket=part['fp_bucket'];C.need(bucket in counts,'Actual physical FP bucket')
            local=transport.resolve(part);file=pq.ParquetFile(C.verify(local))
            C.need(file.metadata.num_rows==part['rows']and set(file.schema_arrow.names)==FIELDS
                and str(file.schema_arrow.field('nearest_v1_tanimoto').type)=='double', 'Actual nine original columns/DOUBLE/footer')
            C.need(all(str(file.schema_arrow.field(k).type).startswith(('int','uint'))for k in INTS), 'Original integer counter types')
            parts.append(dict(origin=part,replica=local,frame=C.frame(local['path'])));counts[bucket]+=part['rows']
    C.need(C.frame(path)==before and len(parts)==main['part_count']and counts==main['per_bucket_counts']
        and sum(counts.values())==main['distinct_fingerprints'],'Complete Main catalog/counts/EOF')
    return parts


def validate_rows(db):
    db.create_function('rescue_f64_bits',bits,return_type='BLOB')
    bad=' OR '.join('s.'+k+' IS NULL'for k in FIELDS)
    bad+=''' OR NOT regexp_full_match(s.ecfp4_2048_hex,'[0-9a-f]{512}')
        OR substr(md5(s.ecfp4_2048_hex),1,1)NOT IN('8','9','a','e','f')
        OR s.reference_molecules<>1196122 OR s.reference_ordinal<0 OR s.reference_ordinal>=1196122
        OR s.score_denominator<1 OR s.score_denominator>2048 OR s.score_numerator<0 OR s.score_numerator>s.score_denominator
        OR s.evaluated_references<0 OR s.strictly_bound_pruned_references<0
        OR s.evaluated_references+s.strictly_bound_pruned_references<>1196122
        OR NOT isfinite(s.nearest_v1_tanimoto)
        OR rescue_f64_bits(s.nearest_v1_tanimoto)<>rescue_f64_bits(s.score_numerator::DOUBLE/s.score_denominator::DOUBLE)'''
    C.need(db.execute('SELECT count(*)FROM main_scores s WHERE '+bad).fetchone()[0]==0,'Every Main row exact FP/F64/unreduced counters/full reference')
    C.need(db.execute('SELECT count(*),count(DISTINCT ecfp4_2048_hex)FROM main_scores').fetchone()[0]
        ==db.execute('SELECT count(DISTINCT ecfp4_2048_hex)FROM main_scores').fetchone()[0],'Unique whole Main FP result scope')
    C.need(db.execute('SELECT count(*)FROM main_scores s LEFT JOIN ref_keys k ON s.reference_ordinal=k.ordinal WHERE s.nearest_v1_key IS DISTINCT FROM k.full_key').fetchone()[0]==0,
           'Every stored nearest key matches actual196 original ordinal')


def mismatch_sql():
    tests=['m.'+k+' IS DISTINCT FROM e.'+k for k in sorted(FIELDS-{'ecfp4_2048_hex','nearest_v1_tanimoto'})]
    tests.append('rescue_f64_bits(m.nearest_v1_tanimoto)IS DISTINCT FROM rescue_f64_bits(e.nearest_v1_tanimoto)')
    return 'SELECT count(*)FROM main_scores m JOIN existing e USING(ecfp4_2048_hex)WHERE '+' OR '.join(tests)


def execute(plan_path,proof_path):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from ..alpha_runtime_v1 import common as Q,profile
    from ..alpha_runtime_v1.guard import Guard
    from ..uff3_alpha_runtime_v1.terminal import parent
    from ..alpha_sharded_novelty_v1.partition import assignment,cover
    from ..exact_nn_cached_v1.sql_runtime import configure,literal
    from ..before_coverage_reuse_v1.catalog import collect
    plan=C.body(C.reference(plan_path));proof=C.body(C.reference(proof_path));actual=profile.admit(plan,minimum_workers=16)
    C.need(plan['schema']=='ALPHA_MAIN_EXACT_RESCUE_IMPORT_PLAN_V1'and os.getuid()==1264
        and proof['request']['producer_plan_reference']==C.reference(plan_path)and str(proof['job_id'])==actual['job_id']
        and proof['uid']==1264 and proof['endpoint']==C.ALPHA
        and proof['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and proof['request']['execution_argv']==plan['execution_argv']
        and proof['request']['scope_key']==plan['scope_key']
        and plan['execution_argv'][0]==sys.executable and plan['execution_argv'][1:3]==['-I','-B']
        and plan['execution_argv'][4]=='workflows.expansion.main_exact_rescue_v1.importer'
        and plan['execution_argv'][5:]==sys.argv[1:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],
        'Actual Alpha import allocation/source plan/boot/argv')
    from ..exact_nn_inverted_cpp_v1 import backend as native_backend
    from ..exact_nn_cached_v1 import engine
    from ..before_coverage_reuse_v1 import catalog as closed_catalog
    from ..uff3_alpha_runtime_v1 import terminal
    from ..exact_nn_cached_v1 import sql_runtime
    pins=[C.reference(p)for p in Path(__file__).parent.glob('*.py')]
    pins += [C.reference(m.__file__)for m in(profile,engine,closed_catalog,terminal,sql_runtime)]
    pins += [C.reference(Path(native_backend.__file__).parent/n)for n in native_backend.SOURCES]
    pins.append(C.reference(plan['execution_argv'][3]))
    C.need(all(r in proof['request']['source_references']and r in plan['code_references']for r in pins),'All actual rescue adapter sources pinned')
    C.need(plan['output_scope_root']=='/gfshome/alpha/pubchem_expansion_20261103/exact'
        and plan['output_cap_bytes']==300000000000 and plan['minimum_free_bytes']>=200000000000,
        'Actual original exact aggregate cap/floor; imported copies are not hidden outside private accounting')
    guard=Guard(plan);locks=[];db=None;monitor=None;finished=threading.Event();source_frames={};out=Path(plan['output_directory']);out.mkdir(mode=0o700,parents=True,exist_ok=False)
    try:
        transport=C.Transport(plan['transport_reference'],C.MAIN,C.ALPHA,1264)
        main=C.body(transport.resolve(plan['main_manifest_reference']))
        C.need(main['schema']=='MAIN_EXACT_FP_RESCUE_SCORES_V1'and main['status']=='COMPLETE'
            and main['actual']['endpoint']==C.MAIN and main['actual']['uid']==1278 and main['reference_molecules']==C.N
            and main['nearest_similarity_exact']is True and main['reference_manifest_reference']==plan['reference_manifest_reference'],
            'Honest complete Main1278 rescue, same whole196 reference')
        C.native_closed(main['actual'],transport.resolve(plan['main_native_sacct_reference']),1278,parent_required=True)
        pre=C.body(transport.resolve(main['preflight_reference']))
        C.need(pre['native_tests']==10 and pre['queries']==64 and pre['full_reference_records_per_backend']==C.N
            and pre['all8_fields_and_F64_equal_local_old_and_historical206']is True,'Actual Main local build/preflight evidence')
        native_build=C.body(transport.resolve(main['builds']['new']))
        current={Path(r['path']).name:(r['bytes'],r['sha256'])for r in pins if Path(r['path']).name in native_backend.SOURCES
            and Path(r['path']).parent==Path(native_backend.__file__).parent}
        C.need(native_build['implementation']==native_backend.IMPLEMENTATION
            and {Path(r['path']).name:(r['bytes'],r['sha256'])for r in native_build['source_references']}==current
            and(native_build['oracle_source_reference']['bytes'],native_build['oracle_source_reference']['sha256'])
                ==(C.reference(engine.__file__)['bytes'],C.reference(engine.__file__)['sha256']),
            'Main native build binds identical complete Core5 and original mathematical oracle bodies, honest distinct paths')
        exported=C.body(main['origin_export_manifest_reference'])
        C.native_closed(exported['actual'],main['origin_export_native_sacct_reference'],1264,parent_required=False)
        C.need(exported['source_filter_reference']==main['source_filter_reference']
            and exported['reference_manifest_reference']==main['reference_manifest_reference']
            and exported['md5_hex_text_prefixes']==main['md5_hex_text_prefixes']==C.PREFIXES,'Original Alpha export/209/196 scope retained')
        class Local:
            @staticmethod
            def resolve(ref):return ref
        query_parts=C.exported_parts(exported,Local())
        parts=load_main_parts(main,transport,pq)
        db=duckdb.connect(str(out/'import.duckdb'));configure(db,plan,out/'spill')
        def observe_SQL():
            while not finished.wait(1):
                try:
                    guard.check();C.need(engine.current_rss()<=plan['parent_rss_cap_bytes'],'Actual import parent SQL RSS cap')
                except BaseException as exc:
                    guard.reason=repr(exc);guard.stop.set();db.interrupt();return
        monitor=threading.Thread(target=observe_SQL,daemon=True);monitor.start()
        source_frames.update({p['path']:C.frame(C.verify(p))for p in query_parts})
        db.read_parquet([v['replica']['path']for v in parts],union_by_name=True).create_view('main_scores')
        db.read_parquet([str(C.verify(p))for p in query_parts]).create_view('exported_fp')
        expected=main['distinct_fingerprints']
        C.need(db.execute('SELECT count(*),count(DISTINCT ecfp4_2048_hex)FROM exported_fp').fetchone()==(expected,expected)
            and expected==exported['distinct_fingerprints'],'Whole original exported FP membership')
        C.need(db.execute('SELECT count(*)FROM((SELECT ecfp4_2048_hex FROM exported_fp EXCEPT SELECT ecfp4_2048_hex FROM main_scores)UNION ALL(SELECT ecfp4_2048_hex FROM main_scores EXCEPT SELECT ecfp4_2048_hex FROM exported_fp))').fetchone()[0]==0,
               'Exact Main score/export FP set, no omitted/replaced results')
        packed=C.body(plan['reference_manifest_reference'])
        C.need(main['reference_fingerprints_origin']==packed['fingerprints']and main['reference_keys_origin']==packed['keys']
            and(main['local_fingerprints']['bytes'],main['local_fingerprints']['sha256'])
                ==(packed['fingerprints']['bytes'],packed['fingerprints']['sha256']), 'Main full reference bytes are exact same original196 body/order')
        keyref=packed['keys'];keybytes=C.verify(keyref).read_bytes()
        C.need(len(keybytes)==C.N*28,'Entire original ordinal-key map')
        db.execute('CREATE TABLE ref_keys(ordinal BIGINT,full_key VARCHAR)')
        for start in range(0,C.N,65536):
            rows=[dict(ordinal=i,full_key=keybytes[i*28:i*28+27].decode('ascii'))for i in range(start,min(start+65536,C.N))]
            db.register('_keys',pa.Table.from_pylist(rows));db.execute('INSERT INTO ref_keys SELECT *FROM _keys');db.unregister('_keys');guard.check()
        validate_rows(db)
        targets=sorted(plan['targets'],key=lambda x:x['root']);C.need(len(targets)==2 and len({t['root']for t in targets})==2,'Two original logical roots only')
        assigned=[];sources=[]
        for index,target in enumerate(targets):
            parent(target['runtime'],target['accounting_reference'],require_C0=False)
            old=C.body(target['plan_reference']);startup=C.body(target['startup_proof_reference']);root=Path(target['root'])
            C.need(root.is_absolute()and root.is_relative_to(Path(plan['output_scope_root']))and root.resolve(strict=True)==root
                and root!=out and root.stat().st_uid==1264,'Distinct actual own literal exact output root')
            C.frame(root/'parent.lock')
            C.need(old['output_directory']==str(root)and old['reference_manifest']==main['reference_manifest_reference']
                and old['filtered_pool_reference']==main['source_filter_reference']
                and startup['request']['producer_plan_reference']==target['plan_reference']
                and startup['uid']==target['runtime']['uid']==1264 and startup['endpoint']==target['runtime']['endpoint']==C.ALPHA
                and str(startup['job_id'])==str(target['runtime']['job_id']), 'Actual terminal original root/source/reference/startup')
            h=(root/'parent.lock').open('rb');fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(h)
            binding=C.body(C.reference(root/'source_binding.json'))
            C.need(all(binding[k]==v for k,v in dict(filtered_pool_reference=old['filtered_pool_reference'],
                reference=old['reference_manifest'],assigned_hash_buckets=assignment(old),partition_id=old['partition_id'],
                scope_key=old['scope_key']).items()),'All five original non-backend cache bindings retained')
            assigned.append(assignment(old));path=out/('old_score_catalog_%d.jsonl'%index)
            stats=collect(root,1264,path,guard.check);sources.append((target,old,path,stats))
        cover(assigned)
        db.execute('CREATE TABLE existing AS SELECT *FROM main_scores WHERE false')
        seen_paths=set()
        for target,old,path,stats in sources:
            paths=[]
            with path.open('rb')as stream:
                for line in stream:
                    part=json.loads(line)['reference'];C.need(part['path']not in seen_paths,'Distinct original score paths across roots')
                    seen_paths.add(part['path']);source_frames[part['path']]=C.frame(C.verify(part));paths.append(part['path'])
            db.read_parquet(paths,union_by_name=True).create_view('old_parts',replace=True)
            db.execute('INSERT INTO existing SELECT e.*FROM old_parts e SEMI JOIN main_scores m USING(ecfp4_2048_hex)');guard.check()
        C.need(db.execute('SELECT count(*),count(DISTINCT ecfp4_2048_hex)FROM existing').fetchone()[0]
            ==db.execute('SELECT count(DISTINCT ecfp4_2048_hex)FROM existing').fetchone()[0],'No repeated old closed result')
        C.need(db.execute(mismatch_sql()).fetchone()[0]==0,'Every overlapping FP has identical all9 fields including binary64 bits')
        db.execute('CREATE TABLE new_scores AS SELECT m.*FROM main_scores m ANTI JOIN existing e USING(ecfp4_2048_hex)')
        imports=[];new_count=0
        for target,old,path,stats in sources:
            root=Path(target['root']);nibbles=assignment(old);condition='substr(md5(ecfp4_2048_hex),1,1)IN('+','.join(literal(x)for x in nibbles)+')'
            total=db.execute('SELECT count(*)FROM new_scores WHERE '+condition).fetchone()[0]
            if not total:continue
            C.need(not(root/'manifest.json').exists(),'Cannot modify an already complete immutable shard')
            token=uuid.uuid4().hex;jpath=root/('closed_files_import_'+token+'.jsonl');made=[]
            with jpath.open('xb')as journal:
                reader=db.execute('SELECT *FROM new_scores WHERE '+condition+' ORDER BY ecfp4_2048_hex').fetch_record_batch(200000)
                for batch in reader:
                    # Split each bounded batch by physical raw-FP bucket.
                    table=pa.Table.from_batches([batch]);texts=table['ecfp4_2048_hex'].to_pylist()
                    for bucket in sorted({v[0]for v in texts}):
                        subset=table.filter(pa.array([v[0]==bucket for v in texts]))
                        folder=root/'scores'/bucket;folder.mkdir(parents=True,exist_ok=True)
                        file=folder/('import_main_'+token+'_%06d.parquet'%len(made))
                        pq.write_table(subset,file,compression='zstd')
                        with file.open('rb')as fd:os.fsync(fd.fileno())
                        ref=dict(C.reference(file),rows=subset.num_rows,fp_bucket=bucket)
                        journal.write(json.dumps(ref,sort_keys=True).encode()+b'\n');journal.flush();os.fsync(journal.fileno());made.append(ref);guard.check()
            C.need(sum(r['rows']for r in made)==total,'Every anti-joined Main row copied exactly once')
            imports.append(dict(root=str(root),journal_reference=C.reference(jpath),new_parts=made,new_rows=total));new_count+=total
        overlap=db.execute('SELECT count(*)FROM existing').fetchone()[0]
        C.need(overlap+new_count==expected,'Main score mass: overlap retained once plus all new imported rows')
        for item in parts:C.need(C.frame(item['replica']['path'])==item['frame'],'Main replica changed during import')
        transport.finish()
        C.need(all(C.frame(p)==stamp for p,stamp in source_frames.items()),'Every Alpha export/old score source unchanged through whole import')
        db.execute('CHECKPOINT');finished.set();monitor.join();monitor=None;db.close();db=None;guard.sample();guard.check()
        return C.write_new(out/'manifest.json',dict(schema='ALPHA_MAIN_EXACT_RESCUE_IMPORT_V1',status='COMPLETE',actual=actual,
            originating_Main_manifest_reference=plan['main_manifest_reference'],Main_native_C0_reference=plan['main_native_sacct_reference'],
            Main_original_runtime=main['actual'],transport_reference=plan['transport_reference'],reference_manifest_reference=plan['reference_manifest_reference'],
            source_filter_reference=main['source_filter_reference'],original_export_reference=main['origin_export_manifest_reference'],
            expected_distinct_FPs=expected,overlap_all9_fields_and_F64_equal=overlap,new_imported_FPs=new_count,imports=imports,
            original_binding_journals_data_rewritten=False,physical_copies_not_free_hardlinks=True,resource_observation=guard.receipt(),
            resource_plan=C.reference(plan_path),startup_proof_reference=C.reference(proof_path),source_references=pins,
            next_epoch_must_reference_this_import_manifest=True))
    finally:
        finished.set()
        if monitor is not None:monitor.join()
        if db is not None:db.close()
        for h in reversed(locks):h.close()
        guard.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True,type=Path);p.add_argument('--startup-proof',required=True,type=Path)
    a=p.parse_args();print(execute(a.plan,a.startup_proof))


if __name__=='__main__':main()