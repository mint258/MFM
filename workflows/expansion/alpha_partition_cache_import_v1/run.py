"""Import complete same-Alpha prefix caches into one terminal original NN root."""
import argparse,fcntl,hashlib,json,os,pathlib,sys,threading,uuid
from . import checks
N=1196122
EXACT=pathlib.Path('/gfshome/alpha/pubchem_expansion_20261103/exact')
SCHEMA='PUBCHEM_ALPHA_PARTITION_CACHE_IMPORT_PLAN_V1'

def execute(plan_path,proof_path):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    from ..alpha_runtime_v1 import common as Q,profile
    from ..alpha_runtime_v1.guard import Guard
    from ..uff3_alpha_runtime_v1.terminal import parent
    from ..before_coverage_reuse_v1.catalog import collect,actual_frame,signature,PRESERVED
    from ..alpha_sharded_novelty_v1.partition import assignment
    from ..alpha_sharded_novelty_v1.run import parts_by_bucket
    from ..exact_nn_inverted_production_v1 import authority as nn_authority
    from ..exact_nn_cached_v1 import engine
    from ..exact_nn_cached_v1.sql_runtime import configure
    metadata_frames={}
    def read(ref,limit=2<<20):
        path=pathlib.Path(ref['path']);before=actual_frame(path,1264)
        Q.need(type(ref['bytes'])is int and 0<=ref['bytes']<=limit,'Bounded explicit immutable input')
        with path.open('rb')as f:
            first=signature(os.fstat(f.fileno()));raw=f.read(limit+1);last=signature(os.fstat(f.fileno()))
        Q.need(before==first==last==actual_frame(path,1264)and len(raw)==ref['bytes']and hashlib.sha256(raw).hexdigest()==ref['sha256'],'Same-FD whole-SHA input/frame')
        metadata_frames[str(path)]=before
        return raw
    body=lambda ref:json.loads(read(ref))
    plan_path=pathlib.Path(plan_path);proof_path=pathlib.Path(proof_path)
    plan=body(Q.reference(plan_path));proof=body(Q.reference(proof_path));actual=profile.admit(plan,minimum_workers=16)
    Q.need(os.getuid()==1264 and plan['schema']==SCHEMA and proof['request']['producer_plan_reference']==Q.reference(plan_path)
        and str(proof['job_id'])==actual['job_id']==os.environ['SLURM_JOB_ID']and proof['uid']==1264 and proof['endpoint']==Q.ENDPOINT
        and proof['boot_id']==pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        and proof['request']['execution_argv']==plan['execution_argv']and proof['request']['scope_key']==plan['scope_key']
        and plan['execution_argv'][:3]==[sys.executable,'-I','-B']
        and plan['execution_argv'][4]=='workflows.expansion.alpha_partition_cache_import_v1.run'
        and plan['execution_argv'][5:]==sys.argv[1:]==['--plan',str(plan_path),'--startup-proof',str(proof_path)],'Actual isolated Alpha import plan/startup/boot/argv')
    pins=[Q.reference(p)for p in pathlib.Path(__file__).parent.glob('*.py')]
    for module in(Q,profile,checks,sys.modules[Guard.__module__],sys.modules[collect.__module__],sys.modules[parent.__module__],sys.modules[configure.__module__],sys.modules[parts_by_bucket.__module__],nn_authority,engine):
        ref=Q.reference(module.__file__)
        if ref not in pins:pins.append(ref)
    pins.append(Q.reference(plan['execution_argv'][3]))
    Q.need(all(r in plan['code_references']and r in proof['request']['source_references']for r in pins),'Actual importer/helper/entry sources pinned')
    Q.need(plan['output_scope_root']==str(EXACT)and plan['output_cap_bytes']==300000000000 and plan['minimum_free_bytes']>=200000000000,'Same real aggregate exact cap and all-future floor')
    target=plan['target'];sources=plan['sources'];Q.need(len(sources)==2,'Both declared complete rescue6/7 sources')
    out=pathlib.Path(plan['output_directory']);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    guard=Guard(plan);db=None;locks=[];monitor=None;done=threading.Event();frames={};closed_catalogs=[]
    def prove(meta,complete):
        parent(meta['runtime'],meta['accounting_reference'],require_C0=complete)
        old=body(meta['plan_reference']);startup=body(meta['startup_proof_reference']);root=pathlib.Path(meta['root'])
        Q.need(root!=out and root.is_relative_to(EXACT)and root.resolve(strict=True)==root and not any(p.is_symlink()for p in(root,*root.parents))and root.stat().st_uid==1264,'Literal distinct own exact root')
        Q.need(old['schema']=='ALPHA_SHARDED_EXACT_NOVELTY_PLAN_V1'and old['execution_argv'][4]=='workflows.expansion.alpha_sharded_novelty_v1.run'and startup['request']['execution_argv']==old['execution_argv']
            and old['output_directory']==str(root)and old['reference_manifest']==plan['reference_manifest_reference']and old['filtered_pool_reference']==plan['filtered_pool_reference']
            and old['source_deployment_reference']==plan['authoritative_nn_deployment_reference']
            and startup['request']['producer_plan_reference']==meta['plan_reference']and str(startup['job_id'])==str(meta['runtime']['job_id'])
            and startup['uid']==meta['runtime']['uid']==1264 and startup['endpoint']==meta['runtime']['endpoint']==Q.ENDPOINT,'Actual same-runtime full reference/filter/source/startup')
        return old,root
    try:
        old,target_root=prove(target,False)
        Q.need(assignment(old)==list('0123456789a')and old['partition_id']=='low11'and not(target_root/'manifest.json').exists(),'Original incomplete low11 only; never rewrite a complete shard')
        for meta in target.get('additional_terminal_writers',[]):parent(meta['runtime'],meta['accounting_reference'],require_C0=False)
        adopted,accepted_reference=nn_authority.adopted(old['backend_adoption_reference'])
        Q.need(adopted['reference_manifest_reference']==plan['reference_manifest_reference'],'Existing exact backend admission and full reference')
        source_items=[];seen_prefixes=set();roots=[target_root]
        for item in sources:
            sp,sr=prove(item,True);value=body(item['manifest_reference']);prefixes=assignment(sp)
            Q.need(value['schema']=='PUBCHEM_SHARDED_FULL_POOL_NOVELTY_V1'and value['status']=='SHARD_COMPLETE'
                and value['resource_plan']==item['plan_reference']and value['reference']==plan['reference_manifest_reference']
                and value['filtered_pool_reference']==plan['filtered_pool_reference']and value['assigned_hash_buckets']==prefixes
                and value['partition_id']==sp['partition_id']and value['scope_key']==sp['scope_key']
                and value['reference_molecules']==N and value['nearest_similarity_exact']is True and value['downstream_features_used']is False
                and value['fingerprint_recipe']==engine.RECIPE and value['algorithm']==engine.ALGORITHM
                and value['backend_adoption_reference']==sp['backend_adoption_reference']==old['backend_adoption_reference']
                and prefixes in(['6'],['7'])and not seen_prefixes.intersection(prefixes),'Complete actual original-runtime disjoint6/7 exact outputs')
            binding=body(value['source_binding_reference'])
            Q.need(all(binding[k]==v for k,v in dict(filtered_pool_reference=sp['filtered_pool_reference'],reference=sp['reference_manifest'],assigned_hash_buckets=prefixes,partition_id=sp['partition_id'],scope_key=sp['scope_key'],backend_adoption_reference=sp['backend_adoption_reference']).items()),'Closed source binding and adopted exact backend')
            seen_prefixes.update(prefixes);roots.append(sr);source_items.append((item,sp,sr,value))
        Q.need(seen_prefixes=={'6','7'}and len(set(roots))==3,'Two distinct complete source roots and one original target')
        for root in sorted(roots):
            actual_frame(root/'parent.lock',1264);handle=(root/'parent.lock').open('rb');fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB);locks.append(handle)
        original_binding_ref=Q.reference(target_root/'source_binding.json');binding=body(original_binding_ref)
        expected=dict(filtered_pool_reference=old['filtered_pool_reference'],reference=old['reference_manifest'],assigned_hash_buckets=assignment(old),partition_id=old['partition_id'],scope_key=old['scope_key'])
        Q.need(all(binding[k]==expected[k]for k in PRESERVED),'All five original low11 cache bindings unchanged')
        current_binding=dict(expected,backend_adoption_reference=old['backend_adoption_reference'])
        derived=[Q.reference(p)for p in target_root.glob('source_binding_inverted_*.json')if body(Q.reference(p))==current_binding]
        Q.need(binding==current_binding or len(derived)==1,'Actual current adopted derived cache binding retained')
        def catalog(root,label):
            path=out/(label+'_closed_scores.jsonl');stats=collect(root,1264,path,guard.check);refs=[]
            with path.open('rb')as f:
                for line in f:
                    Q.need(line.endswith(b'\n')and len(line)<=65536,'Closed bounded catalog EOF')
                    item=json.loads(line);ref=item['reference'];file=Q.verify(ref);stamp=actual_frame(file,1264)
                    Q.need(list(stamp)==item['current_frame'],'Score frame stable across whole SHA')
                    footer=pq.ParquetFile(file);checks.schema(footer.schema_arrow);Q.need(footer.metadata.num_rows==ref['rows'],'Closed footer count')
                    frames[str(file)]=stamp;refs.append(ref)
            closed_catalogs.append(dict(root=str(root),reference=Q.reference(path),stats=stats))
            guard.check();return refs,stats
        incoming=[];by_source=[];expected_source_rows=0
        for index,(item,sp,sr,value)in enumerate(source_items):
            refs,stats=catalog(sr,'source_'+str(index))
            Q.need(stats['rows']==value['distinct_query_fingerprints'],'Whole complete source closed-FP count')
            incoming.extend(refs);by_source.append((refs,assignment(sp),stats['rows']));expected_source_rows+=stats['rows']
        previous,old_stats=catalog(target_root,'target')
        Q.need(len({r['path']for r in incoming+previous})==len(incoming+previous),'Distinct physical source/old score paths')
        db=duckdb.connect(str(out/'import.duckdb'));configure(db,plan,out/'spill');checks.install(db)
        def watch():
            while not done.wait(1):
                try:guard.check()
                except BaseException:db.interrupt();return
        monitor=threading.Thread(target=watch,daemon=True);monitor.start()
        db.read_parquet([r['path']for r in incoming],union_by_name=True).create_view('incoming')
        packed=body(plan['reference_manifest_reference']);Q.need(packed['status']=='COMPLETE'and packed['molecules']==N and packed['targets_present']is False,'Complete original full1196122 reference')
        payload=read(packed['keys'],64<<20);Q.need(len(payload)==N*28,'Entire original ordinal-key map')
        db.execute('CREATE TABLE ref_keys(ordinal BIGINT,full_key VARCHAR)')
        for start in range(0,N,65536):
            rows=[dict(ordinal=i,full_key=payload[i*28:i*28+27].decode('ascii'))for i in range(start,min(start+65536,N))]
            db.register('_keys',pa.Table.from_pylist(rows));db.execute('INSERT INTO ref_keys SELECT *FROM _keys');db.unregister('_keys');guard.check()
        for refs,prefixes,count in by_source:
            db.read_parquet([r['path']for r in refs],union_by_name=True).create_view('incoming',replace=True)
            checks.validate(db,'incoming',prefixes,N,count)
        db.read_parquet([r['path']for r in incoming],union_by_name=True).create_view('incoming',replace=True)
        Q.need(db.execute('SELECT count(*)FROM incoming').fetchone()[0]==expected_source_rows,'Complete disjoint source union mass')
        # Independently establish every incoming FP belongs to actual closed209 candidates.
        filtered=body(plan['filtered_pool_reference']);Q.need(filtered['schema']=='PUBCHEM_EXACT_KEY_FILTERED_SHARDS_V1'and filtered['status']=='COMPLETE','Original complete exact-policy pool')
        groups=parts_by_bucket(filtered)
        buckets={r['fp_bucket']for r in incoming};parts=[r for bucket in sorted(buckets)for r in groups[bucket]]
        eligible=[]
        for ref in parts:
            file=Q.verify(ref);frames[str(file)]=actual_frame(file,1264);eligible.append(str(file));guard.check()
        db.read_parquet(eligible).create_view('eligible')
        db.execute('CREATE TABLE seen_eligible AS SELECT DISTINCT c.ecfp4_2048_hex FROM eligible c SEMI JOIN incoming m USING(ecfp4_2048_hex)')
        Q.need(db.execute('SELECT count(*)FROM incoming ANTI JOIN seen_eligible USING(ecfp4_2048_hex)').fetchone()[0]==0,'Every source FP belongs to original209 candidate pool')
        db.read_parquet([r['path']for r in previous],union_by_name=True).create_view('old_parts')
        db.execute('CREATE TABLE existing AS SELECT e.*FROM old_parts e SEMI JOIN incoming m USING(ecfp4_2048_hex)')
        checks.validate(db,'existing',['6','7'],N)
        overlap,new=checks.overlap_and_new(db);guard.check()
        token=actual['job_id']+'_'+uuid.uuid4().hex;journal_path=target_root/('closed_files_import_alpha_'+token+'.jsonl');made=[]
        with journal_path.open('xb')as journal:
            reader=db.execute('SELECT *FROM new_scores ORDER BY ecfp4_2048_hex').fetch_record_batch(200000)
            for batch in reader:
                table=pa.Table.from_batches([batch]);values=table['ecfp4_2048_hex'].to_pylist()
                for bucket in sorted({s[0]for s in values}):
                    subset=table.filter(pa.array([s[0]==bucket for s in values]));folder=target_root/'scores'/bucket;folder.mkdir(parents=True,exist_ok=True)
                    file=folder/('import_alpha_'+token+'_%06d.parquet'%len(made));pq.write_table(subset,file,compression='zstd')
                    footer=pq.ParquetFile(file);checks.schema(footer.schema_arrow);Q.need(footer.metadata.num_rows==subset.num_rows,'Copied score footer/schema')
                    with file.open('rb')as f:os.fsync(f.fileno())
                    ref=dict(Q.reference(file),rows=subset.num_rows,fp_bucket=bucket);journal.write(json.dumps(ref,sort_keys=True).encode()+b'\n');journal.flush();os.fsync(journal.fileno());made.append(ref);guard.check()
        Q.need(sum(r['rows']for r in made)==new and overlap+new==expected_source_rows,'Every source row retained once or physically imported once')
        Q.need(all(actual_frame(path,1264)==stamp for path,stamp in frames.items()),'All closed source/old/candidate inputs unchanged')
        Q.need(all(actual_frame(path,1264)==stamp for path,stamp in metadata_frames.items()),'All original metadata and ordinal-key map unchanged')
        Q.need(Q.reference(target_root/'source_binding.json')==original_binding_ref,'Original low binding never rewritten')
        for item in closed_catalogs:
            for journal in item['stats']['journals']:Q.need(list(actual_frame(journal['reference']['path'],1264))==journal['current_frame'],'Original journals never rewritten')
        db.execute('CHECKPOINT');done.set();monitor.join();monitor=None;db.close();db=None;guard.sample();guard.check()
        return Q.write(out/'manifest.json',dict(schema='PUBCHEM_ALPHA_PARTITION_CACHE_IMPORT_V1',status='COMPLETE',actual=actual,resource_plan=Q.reference(plan_path),startup_proof_reference=Q.reference(proof_path),target=target,sources=sources,reference_manifest_reference=plan['reference_manifest_reference'],filtered_pool_reference=plan['filtered_pool_reference'],prefixes=['6','7'],source_distinct_FP_rows=expected_source_rows,overlap_all9_fields_and_F64_equal=overlap,new_imported_FP_rows=new,new_parts=made,new_journal_reference=Q.reference(journal_path),closed_input_catalogs=closed_catalogs,original_five_binding_fields=expected,original_binding_reference=original_binding_ref,current_derived_binding_references=derived,old_binding_journals_and_data_rewritten=False,physical_copies_not_hardlinks=True,all_incoming_FP_membership_in_original_pool_checked=True,source_references=pins,resource_observation=guard.receipt(),next_epoch_must_reference_this_import_manifest=True))
    finally:
        done.set()
        if monitor is not None:monitor.join()
        if db is not None:db.close()
        for handle in reversed(locks):handle.close()
        guard.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True);parser.add_argument('--startup-proof',required=True);args=parser.parse_args()
    print(execute(args.plan,args.startup_proof),flush=True)
if __name__=='__main__':main()