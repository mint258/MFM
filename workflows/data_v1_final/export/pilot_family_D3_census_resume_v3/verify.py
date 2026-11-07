"""Real10k source replay, exact one-cast comparison and16 owned spawn readers."""
import collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,time
from . import contract as C,io as I,source as X,writer as W,wire as V
from workflows.data_v1_final.export.family_export_day_v1 import verify as Original
L=C.F.legacy();S=L['pipeline_v1.source'];O=L['pipeline_v1.io']
def bit_equal(a,b):
    C.need(set(a)==set(b),'ALL_SOURCE_ARRAY_NAMES_RETAINED')
    for k,x in a.items():C.need(x.dtype.str==b[k].dtype.str and x.shape==b[k].shape and x.tobytes()==b[k].tobytes(),'EXACT_F64_INTEGER_MASK_REASON_INDEX_BITS:'+k)
def replay(work):
    part,items=work;byphysical=collections.defaultdict(list)
    for item in items:byphysical[item['locator']['physical_row']].append(item)
    first=items[0]['locator'];byid={f['field_id']:f for f in X.CTX['field_map']};raws={};checked=0;digest=hashlib.sha256()
    I.B.ALLOWED[part['path']]=part
    try:
        for typed in X.R.one_part(part,first['source_file_id'],first['typed_window_lo'],first['typed_window_hi']):
            requests=byphysical.pop(typed['physical_row'],[])
            if not requests:continue
            entries=X.K.unpack_entries(typed,byid);tr=X.CTX['recipe']['tasks'][X.task_name(typed['task_code'])]
            for item in requests:
                loc=item['locator'];C.need(typed['record_id']==loc['record_id'] and typed['view_sha256'].hex()==loc['typed_part_view_sha256'],'SOURCE10K_ORIGINAL_TYPED_RECORD_VIEW_SHA')
                raw=None
                if tr['input_kind']=='ORIGINAL_REGISTRY_CELL_PARQUET':
                    path=loc['source_reference']['path']
                    if path not in raws:raws[path]=X.RawRows(loc['source_reference'],loc['source_rows'])
                    # Several physical targets may share this exact source row.
                    cursor=raws[path];raw=cursor.row if cursor.offset==loc['physical_row'] else cursor.get(loc['physical_row'])
                    C.need(raw['record_id']==loc['record_id'] and raw['input_bundle_sha256']==loc['actual_input_bundle_sha256']
                      and raw['input_file_sha256']==loc['actual_input_file_sha256'],'SOURCE10K_ACTUAL_PROGRAM_INPUT_DOUBLE_HASH')
                target=X.CTX['compiled']['ordered_record_targets'].get(item['tid']) or X.CTX['compiled']['physical_targets'][item['tid']]
                arrays,note=X.extract(entries,typed,raw,item['n'],tr,target);expected=S.unpack(item['packed']);bit_equal(arrays,expected)
                C.need(note==S.reason_annotations(item['packed']),'SOURCE10K_ORIGINAL_MASK_REASON_GRANULARITY')
                digest.update(item['packed']);checked+=1
        C.need(not byphysical,'ALL_10K_REQUESTED_ORIGINAL_TYPED_ROWS_FOUND')
    finally:
        for cursor in raws.values():cursor.close()
    return {'pieces':checked,'sha256':digest.hexdigest(),'pid':os.getpid(),'source_values_indices_masks_reasons_replayed':True,'all_handles_closed':True}
def run(db,store_refs,root,context,pool,budget):
    db.create_function('sample_rank',2,lambda store,gid:O.rank_hash(20261025,store,gid),deterministic=True)
    samples=db.execute("SELECT store,gid,parts FROM exported WHERE kind='labels' ORDER BY sample_rank(store,gid),store,gid LIMIT 10000").fetchall()
    C.need(len(samples)==10000,'D3_EXACT10K_DISTINCT_SOURCE_RECORDS_NO_DOWNGRADE');by_store=collections.defaultdict(list)
    for r in samples:by_store[r['store']].append(r)
    replay_tasks={};sidecar_checks=[];cast_digest=hashlib.sha256()
    for ref in store_refs:
        manifest=I.load_data(ref,8<<20);side=manifest['f64_authority']['reference'];I.add(side);I.require(side)
        db64=I.connect(side['path'],True)
        with W.Reader(manifest['path']) as reader:
            C.need(reader.count==manifest['records'] and reader.molecule_count==manifest['molecules'],'ALL_LMDB_STORE_MID_RECORD_COUNTS')
            C.need(db64.execute('SELECT count(*) FROM authority').fetchone()[0]==reader.count,'EVERY_TRAIN_RECORD_HAS_PERMANENT_F64_AUTHORITY')
            for row in by_store.get(manifest['name'],[]):
                budget.check();meta,actual=reader.get(row['gid']);saved=db64.execute('SELECT metadata,payload,sha FROM authority WHERE rid=?',(row['gid'],)).fetchone()
                C.need(saved is not None and hashlib.sha256(saved['payload']).hexdigest()==saved['sha']==meta['permanent_F64_sidecar_record']['payload_sha256'],'D3_SIDECAR_FULL_F64_PAYLOAD_SHA')
                source_arrays={}
                for tid in json.loads(row['parts']):
                    p=db.execute('SELECT n,payload,source_locator FROM pieces WHERE gid=? AND part=?',(row['gid'],tid)).fetchone();C.need(p is not None,'EXACT_PERSISTED_SOURCE_LOCATOR')
                    arrays=S.unpack(p['payload']);C.need(not set(source_arrays)&set(arrays),'NO_DUPLICATE_FIELD_ARRAY');source_arrays.update(arrays);loc=json.loads(p['source_locator'])
                    key=loc['typed_part_reference']['path'];task=replay_tasks.setdefault(key,(loc['typed_part_reference'],[]));task[1].append({'locator':loc,'n':p['n'],'tid':tid,'packed':p['payload']})
                bit_equal(source_arrays,S.unpack(saved['payload']));cast_digest.update(V.original_cast_compare(source_arrays,actual).encode())
                C.need(meta['geometry_sha256'] and meta['atom_order_sha256'] and meta['effective_role'] in ('TRAIN','VAL'),'D3_ACTUAL_GEOMETRY_ROLE_ATOM_IDENTITY')
        db64.close();sidecar_checks.append({'reference':side,'records':manifest['records'],'whole_SHA_checked':True})
    pending={};tasks=iter(replay_tasks.values());exhausted=False;results=[]
    while pending or not exhausted:
        while not exhausted and len(pending)<32:
            budget.check()
            try:task=next(tasks)
            except StopIteration:exhausted=True;break
            pending[pool.submit(replay,task)]=True
        if pending:
            ready,_=cf.wait(pending,timeout=1,return_when=cf.FIRST_COMPLETED)
            for f in ready:pending.pop(f);results.append(f.result())
    C.need(sum(r['pieces'] for r in results)==sum(len(json.loads(r['parts'])) for r in samples),'ALL_SELECTED_SOURCE_PIECES_ACTUALLY_REPLAYED')
    mids=[r[0] for r in db.execute("SELECT mid FROM molecules ORDER BY sample_rank('whole_MID',mid),mid LIMIT 16")];C.need(len(mids)==16,'SIXTEEN_WHOLE_MID_READERS')
    work=[]
    for index,mid in enumerate(mids):
        rows=db.execute('SELECT s.path,e.gid FROM exported e JOIN stores s ON s.name=e.store JOIN geometries g ON g.gid=e.gid WHERE g.mid=? ORDER BY e.store,e.gid',(mid,)).fetchall()
        work.append((index,[(mid,[(r[0],r[1]) for r in rows])]))
    ctx=mp.get_context('spawn');barrier=ctx.Barrier(16);start=time.monotonic()
    with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=Original.read_initializer,initargs=(barrier,)) as readers:
        process_rows=list(readers.map(Original.molecule_reader,work,chunksize=1))
    elapsed=time.monotonic()-start;C.need(len({r['pid'] for r in process_rows})==16 and all(r['all_handles_closed'] for r in process_rows),'ACTUAL16_SPAWN_READERS_NOT_SYNTHETIC_COUNT')
    import psutil
    for r in process_rows:
        try:live=psutil.Process(r['pid']).create_time()==r['process_start']
        except psutil.NoSuchProcess:live=False
        C.need(not live,'OWNED_READER_BIRTH_PID_ACTUALLY_CLOSED_NO_SIGNALS')
    result={'schema':'BOUNDED_PILOT_FAMILY_ACTUAL_D3_READBACK_V1','source_roundtrip_records':10000,'source_piece_results':results,
      'exact_original_single_F32_cast_digest':cast_digest.hexdigest(),'permanent_F64_sidecars':sidecar_checks,'spawn_workers':process_rows,
      'molecules_per_second_including_startup':16/elapsed,'records_per_second_including_startup':sum(r['records'] for r in process_rows)/elapsed,
      'all_handles_closed':True,'Model_loader_ACK':False,'full_Common_or_D6_release':False}
    return I.save(root/'actual_D3_readback.DATA.json',result),result
