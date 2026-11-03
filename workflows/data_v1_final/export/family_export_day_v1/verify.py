"""Original f64->f32 compare and actual spawn-owned family/MID readback."""
from __future__ import annotations
import concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,pathlib,time
import numpy as np
from . import contract as C,io as I,project as P
from .store import Reader
L=C.legacy();O=L['pipeline_v1.io'];V=L['pipeline_v1.verify'];compare=V.compare
BARRIER=None


def check_group(task):
    stage,specs,compiled,index,rg,requests=task;spec=specs[index];db=O.connect(stage,readonly=True);readers={};digest=hashlib.sha256();checked=leaves=0;maximum=0.0
    claim=P.CTX['claim_database_reference'];db.execute('ATTACH DATABASE ? AS claims',(pathlib.Path(claim['path']).as_uri()+'?mode=ro&immutable=1',))
    for name in ('source_cells','claim_bindings'):db.execute('CREATE TEMP VIEW '+name+' AS SELECT * FROM claims.'+name)
    requested={}
    for r in requests:requested.setdefault(r['row_number'],[]).append(r)
    number=0
    try:
        for batch in I.worker_batches(spec,P.CTX['frames'][spec['file']['path']],lambda:I.worker_check(P.CTX['control']),[rg],P.columns(spec)):
            for row in batch.to_pylist():
                jobs=requested.get(number,[]);number+=1
                for job in jobs:
                    geometry=db.execute('SELECT * FROM selected_geometry WHERE geometry_id=?',(job['geometry_id'],)).fetchone();C.need(geometry is not None,'SOURCE_QA_EXACT_PHYSICAL_IDENTITY')
                    geometry=dict(geometry);geometry['n_atoms']=db.execute("SELECT n_atoms FROM pieces WHERE geometry_id=? AND part='__geometry__'",(job['geometry_id'],)).fetchone()[0]
                    if spec['kind']=='geometry':
                        actual=P.resolve_exact(db,row,spec,job['absolute_row']);C.need(actual is not None and actual['geometry_id']==job['geometry_id'],'SOURCE_GEOMETRY_LOCATOR_EXACT_NO_BASE_SUBSTITUTION')
                    else:
                        groups=P.target_geometries(db,row,spec,compiled,job['absolute_row'])
                        C.need(any(g['geometry_id']==job['geometry_id'] and job['part'] in tids for g,tids in groups),'SOURCE_EACH_FIELD_ACTUAL_GEOMETRY_CLAIM')
                    tid=job['part'];parts=P.row_arrays(row,spec,geometry,db,compiled,None if tid=='__geometry__' else [tid]);C.need(len(parts)==1,'EXACT_ONE_SOURCE_PART')
                    _,expected,notes=parts[0]
                    if job['store_path'] not in readers:readers[job['store_path']]=Reader(job['store_path'])
                    metadata,arrays=readers[job['store_path']].get(job['geometry_id'])
                    C.need(all(metadata[k]==geometry[k] for k in ('molecule_id','geometry_source','effective_role','source_role','parent_geometry_id','view_id','n_atoms')),'SOURCE_QA_ROLE_FRAME_AND_IDENTITY_EXACT')
                    for key,note in notes.items():
                        if key=='_source_null_fields':C.need(set(note)<=set(metadata.get('source_null_fields_with_masked_nan_placeholder',[])),'SOURCE_NULL_ANNOTATION')
                        elif key=='_source_precision':C.need(all(metadata.get('source_precision',{}).get(k)==v for k,v in note.items()),'SOURCE_NATIVE_PRECISION_METADATA')
                        else:C.need(metadata.get('reason_granularity',{}).get(key)==note,'SOURCE_REASON_GRANULARITY_EXACT')
                    digest.update(compare(expected,{k:arrays[k] for k in expected}).encode());checked+=1
                    for key,array in expected.items():
                        leaves+=array.size
                        if array.dtype.kind=='f':
                            finite=np.isfinite(array)
                            if np.any(finite):maximum=max(maximum,float(np.max(np.abs(array[finite].astype('<f8')-array[finite].astype('<f4').astype('<f8')))))
        C.need(checked==len(requests),'ALL_SOURCE_LOCATORS_READ_BACK_NO_SAMPLE_DOWNGRADE')
    finally:
        for r in readers.values():r.close()
        db.close()
    return {'pieces':checked,'leaves':leaves,'source_index':index,'row_group':rg,'source_f64_to_f32_maximum_absolute_difference':maximum,
        'allowed_error':'EXACT_SINGLE_CAST_BYTES_INTEGER_MASK_REASON_EXACT','sha256':digest.hexdigest(),'pid':os.getpid(),'all_handles_closed':True}


def read_initializer(barrier):
    global BARRIER
    BARRIER=barrier;BARRIER.wait(timeout=300)


def molecule_reader(task):
    import psutil
    index,items=task;readers={};h=hashlib.sha256();records=0;start=time.monotonic();birth=psutil.Process().create_time()
    try:
        BARRIER.wait(timeout=300)
        for mid,all_records in items:
            for path,gid in all_records:
                if path not in readers:readers[path]=Reader(path)
                meta,arrays=readers[path].get(gid);C.need(meta['molecule_id']==mid,'WHOLE_MOLECULE_FAMILY_INDEX_IDENTITY')
                h.update(L['wire_v1.codec'].canonical_json(meta))
                for key,a in sorted(arrays.items()):h.update(key.encode());h.update(a.tobytes())
                records+=1
    finally:
        for r in readers.values():r.close()
    return {'index':index,'pid':os.getpid(),'process_start':birth,'records':records,'molecules':len(items),'all_requested_families_and_conformers_per_molecule':True,
        'sha256':h.hexdigest(),'seconds':time.monotonic()-start,'all_handles_closed':True}


def run(db,stage,out,specs,compiled,context,budget):
    db.create_function('sample_rank',2,lambda store,gid:O.rank_hash(20261025,store,gid),deterministic=True)
    samples=[dict(r) for r in db.execute('SELECT * FROM exported ORDER BY sample_rank(store_name,geometry_id),store_name,geometry_id LIMIT 10000')]
    C.need(len(samples)==10000,'EXACT10000_UNIQUE_SOURCE_RECORDS_NOT_SMALLER_SAMPLE')
    groups={};offsets={}
    import pyarrow.parquet as pq
    for index in {r[0] for r in db.execute('SELECT DISTINCT source_index FROM pieces')}:
        ref=specs[index]['file'];offset=0
        with I.same_parent_fd(ref,context['frames'][ref['path']]) as fd:
            with os.fdopen(os.dup(fd),'rb') as raw:
                pf=pq.ParquetFile(raw)
                try:
                    for rg in range(pf.metadata.num_row_groups):offsets[index,rg]=offset;offset+=pf.metadata.row_group(rg).num_rows
                finally:pf.close()
    for row in samples:
        store=db.execute('SELECT path FROM stores WHERE name=?',(row['store_name'],)).fetchone();C.need(store is not None,'EXACT_IMMUTABLE_STORE_CATALOGUE')
        for part in json.loads(row['parts_json']):
            locator=db.execute('SELECT source_index,row_group,row_number FROM pieces WHERE geometry_id=? AND part=?',(row['geometry_id'],part)).fetchone();C.need(locator is not None,'SOURCE_LOCATOR_RETAINED')
            index,rg,number=locator;groups.setdefault((index,rg),[]).append(dict(store_path=store[0],geometry_id=row['geometry_id'],part=part,row_number=number,absolute_row=offsets[index,rg]+number))
    ctx=mp.get_context('spawn');counter=ctx.Value('q',0);results=[]
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=P.initialize,initargs=(counter,1<<40,context)) as pool:
        tasks=[(str(stage),specs,compiled,i,rg,requests) for (i,rg),requests in sorted(groups.items())]
        pending={};cursor=iter(tasks);done=False
        while pending or not done:
            while len(pending)<32 and not done:
                budget.check()
                try:task=next(cursor)
                except StopIteration:done=True;break
                pending[pool.submit(check_group,task)]=True
            if pending:
                finished,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
                for f in finished:pending.pop(f);results.append(f.result())
    C.need(sum(x['pieces'] for x in results)==sum(len(json.loads(r['parts_json'])) for r in samples),'ALL_SELECTED_SOURCE_PIECES_QA')
    # Exactly sixteen sampled MIDs, each read with all exported records. This
    # reports molecules/s as well as records/s instead of relabelling records.
    mids=[r[0] for r in db.execute("SELECT molecule_id FROM selected_molecules ORDER BY sample_rank('whole_molecule',molecule_id),molecule_id LIMIT 16")]
    C.need(len(mids)==16,'SIXTEEN_DISTINCT_WHOLE_MOLECULE_BENCHMARKS');queues=[]
    for index,mid in enumerate(mids):
        records=[(r[0],r[1]) for r in db.execute('SELECT s.path,e.geometry_id FROM exported e JOIN stores s ON s.name=e.store_name JOIN selected_geometry g ON g.geometry_id=e.geometry_id WHERE g.molecule_id=? ORDER BY e.store_name,e.geometry_id',(mid,))]
        C.need(records,'NO_EMPTY_MOLECULE_BENCHMARK');queues.append((index,[(mid,records)]))
    barrier=ctx.Barrier(16);start=time.monotonic()
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=read_initializer,initargs=(barrier,)) as pool:spawn=list(pool.map(molecule_reader,queues,chunksize=1))
    seconds=time.monotonic()-start;C.need(len({x['pid'] for x in spawn})==16 and all(x['all_handles_closed'] for x in spawn),'SIXTEEN_REAL_SPAWN_READERS_CLOSED')
    import psutil
    for r in spawn:
        try:alive=psutil.Process(r['pid']).create_time()==r['process_start']
        except psutil.NoSuchProcess:alive=False
        C.need(not alive,'ACTUAL_READER_PROCESS_CLOSED_NO_SIGNAL')
    # Whole SHA/count/schema/readback of every store, not only ten thousand.
    catalogue=[];data_bytes=manifest_bytes=0
    for row in db.execute('SELECT manifest FROM stores ORDER BY name'):
        store=json.loads(row[0]);budget.check();data_bytes+=store['data']['bytes'];manifest_bytes+=store['manifest']['bytes']
        for key in ('manifest','data','schema'):
            if key in store and isinstance(store[key],dict):
                with I.held(store[key],[store[key]],budget.check):pass
        with Reader(store['path']) as reader:C.need(reader.count==store['records'] and reader.molecule_count==store['molecules'],'FULL_LMDB_RECORD_MID_COUNTS')
        catalogue.append(store['name'])
    result={'schema':'FAMILY_SOURCE_AND_SPAWN_READBACK_V1','source_roundtrip_records':10000,'fixed_seed':20261025,
        'source_piece_groups':results,'all_handles_closed':True,'spawn_workers':spawn,'spawn_elapsed_including_startup_seconds':seconds,
        'molecules_per_second_including_startup':16/seconds,'records_per_second_including_startup':sum(r['records'] for r in spawn)/seconds,
        'stores_whole_SHA_and_counts_verified':len(catalogue),'LMDB_data_bytes':data_bytes,'immutable_manifest_bytes':manifest_bytes,'gpu_tmp_local_disk':False,'Model_loader_ACK':False}
    ref=I.data_json_new(out/'verification.DATA.json',result)
    return dict(result,reference=ref)