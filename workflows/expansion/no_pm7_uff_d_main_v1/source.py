"""CPU-only true ordered batch1+closed filtered DB -> original graph source parts."""
import concurrent.futures as cf,hashlib,json,os,pathlib,random,sqlite3,threading
from urllib.parse import quote
from . import contract as C,io as I
Q=C.Q
def pilot_ordinals():
    # Separate stable streams,retain actual sample order rather than completion.
    rng=random.Random(C.SEED)
    return [*rng.sample(range(C.EACH),5000),*(C.EACH+i for i in rng.sample(range(C.EACH),5000))]
def selected(mode,ordinal,lower=0,upper=0):
    if mode=='full':return lower<=ordinal<upper
    values=pilot_ordinals();return ordinal in (set(values[:16]+values[5000:5016]) if mode=='compat' else set(values))
def prepare(plan,budget,out,store,proof):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    rank,filtered,review,refs,parents=C.source_parents(plan);queue=I.Body(C.triple(rank['batch1']),budget);dbbody=I.Body(C.triple(filtered['database']),budget)
    dbpath=pathlib.Path(filtered['database']['path']);Q.need(not any(pathlib.Path(str(dbpath)+s).exists() for s in ('-wal','-shm','-journal')),'CLOSED_FILTERED_DATABASE_NO_ACTIVE_SIDECAR')
    local=threading.local();connections=[];lock=threading.Lock();barrier=threading.Barrier(16)
    def lookup(row,index):
        if not hasattr(local,'db'):
            local.db=sqlite3.connect('file:'+quote(str(dbpath),safe='/')+'?mode=ro&immutable=1',uri=True,check_same_thread=False)
            with lock:connections.append(local.db)
        if index<16:barrier.wait(timeout=60)
        stream,cid,key,rank0=row['stream'],row['cid'],row['full_key'],row['stream_rank']
        value=local.db.execute('SELECT full_key,cid,wp5_key,features FROM candidates WHERE cid=? AND full_key=?',(cid,key)).fetchall()
        Q.need(len(value)==1,'EXACT_ORDERED_CID_FULLKEY_SOURCE_JOIN_NOT_ARBITRARY_ALIAS')
        raw=value[0];feature=json.loads(raw[3]);Q.need(feature['cid']==cid and feature['full_key']==key and isinstance(feature.get('isomeric_smiles'),str)
            and feature['isomeric_smiles'] and isinstance(feature.get('source_smiles'),str),'ACTUAL_SCREEN_PRODUCER_GRAPH_AND_RAW_SMILES_REQUIRED')
        ordinal=(0 if stream=='R' else C.EACH)+rank0-1
        return {'ordinal':ordinal,'stream':stream,'stream_rank':rank0,'cid':cid,'full_key':key,'wp5_key':raw[2],
            'pubchem_version':review['pubchem_version'],'pubchem_raw_source_reference':review['pubchem_raw_source_reference'],
            'isomeric_smiles':feature['isomeric_smiles'],'source_smiles':feature['source_smiles'],'source_row_sha256':C.sha(C.canonical(list(raw))),
            'filtered_database_reference':C.triple(filtered['database']),'ranking_receipt_reference':plan['ranking_receipt_reference'],
            'graph_source_field':'features.isomeric_smiles','source_ordinal':feature.get('ordinal')}
    parts=[];counts={'R':0,'N':0};seen_index=sqlite3.connect(out/'source_census.sqlite');seen_index.execute('CREATE TABLE seen(cid INTEGER UNIQUE,full_key TEXT UNIQUE,ordinal INTEGER PRIMARY KEY)')
    writer=None;part_rows=0;global_index=0;consumed=0;part_first=None;h=None;bytes0=0;pending=[]
    def consume(value):
        nonlocal writer,part_rows,part_first,h,bytes0,consumed
        ordinal=value['ordinal'];Q.need(ordinal==consumed,'EXACT_R_THEN_N_CONTIGUOUS_ORDER_NO_REORDER');consumed+=1
        seen_index.execute('INSERT INTO seen VALUES(?,?,?)',(value['cid'],value['full_key'],ordinal));counts[value['stream']]+=1
        if writer is None:
            part_first=ordinal;path=out/'source_parts'/('part_%06d.jsonl'%(ordinal//10000));path.parent.mkdir(parents=True,exist_ok=True);writer=path.open('xb');part_rows=0;h=hashlib.sha256();bytes0=0
        raw=C.canonical(value)+b'\n';Q.need(len(raw)<=1<<20,'BOUNDED_SOURCE_ROW_NO_GRAPH_TRUNCATION')
        writer.write(raw);h.update(raw);bytes0+=len(raw);part_rows+=1
        if part_rows==10000 or ordinal==C.TARGET-1:
            writer.flush();os.fsync(writer.fileno());path=pathlib.Path(writer.name);writer.close();writer=None
            parts.append({'reference':{'path':str(path),'bytes':bytes0,'sha256':h.hexdigest()},'lower_inclusive':part_first,'upper_exclusive':ordinal+1,'rows':part_rows})
        if ordinal%256==0:budget.check(True)
    try:
        parquet=queue.parquet();Q.need(parquet.metadata.num_rows==C.TARGET and set(parquet.schema_arrow.names)=={'stream','cid','full_key','stream_rank'},'ACTUAL2P5M_ORDERED_FOUR_COLUMN_BATCH1')
        with cf.ThreadPoolExecutor(max_workers=16) as pool:
            for batch in parquet.iter_batches(batch_size=4096,use_threads=False):
                for row in batch.to_pylist():
                    ordinal=global_index;stream='R' if ordinal<C.EACH else 'N';expected_rank=ordinal%C.EACH+1
                    Q.need(row['stream']==stream and type(row['stream_rank'])is int and row['stream_rank']==expected_rank and type(row['cid'])is int and 0<row['cid']<2**63,'ACTUAL_FROZEN_NESTED_R_N_RANK_CENSUS')
                    pending.append(pool.submit(lookup,row,global_index));global_index+=1
                    if len(pending)>=32:
                        consume(pending.pop(0).result())
            for future in pending:
                consume(future.result())
        seen_index.commit();Q.need(counts=={'R':C.EACH,'N':C.EACH} and len(connections)==16 and len(parts)==250,'ALL2P5M_CID_FULLKEY_UNIQUE_SOURCE_PARTS_AND16_QUERY_THREADS')
        queue.check();dbbody.check()
        return store.json(out/'source_manifest.json',{'schema':'NO_PM7_UFF_D_ORDERED_SOURCE_MANIFEST_V1','status':'ALL2500000_ORDERED_SOURCE_GRAPHS_PROJECTED_NO_UFF',
            'job_id':str(proof['job_id']),'ranking_receipt_reference':plan['ranking_receipt_reference'],
            'graph_source_review_reference':plan['graph_source_review_reference'],'recipe_reference':Q.pin(C.RECIPE),'pubchem_version':review['pubchem_version'],
            'counts':counts,'parts':parts,'profile_sample_order':pilot_ordinals(),'compat_sample_order':pilot_ordinals()[:16]+pilot_ordinals()[5000:5016],
            'new_UFF_QM_calls':0,'dataset_version':'v2_candidate','training_release':False})
    finally:
        if writer is not None:writer.flush();os.fsync(writer.fileno());writer.close()
        seen_index.close();queue.close();dbbody.close()
        # All query threads have joined before these read-only handles close.
        for connection in connections:connection.close()
def rows(manifest,mode,budget,lower=0,upper=0):
    chosen=set(manifest['compat_sample_order'] if mode=='compat' else manifest['profile_sample_order']) if mode in ('compat','profile') else None
    count=0
    for part in manifest['parts']:
        if mode=='full' and (part['upper_exclusive']<=lower or part['lower_inclusive']>=upper):continue
        if chosen is not None and not any(part['lower_inclusive']<=i<part['upper_exclusive'] for i in chosen):continue
        body=I.Body(C.triple(part['reference']),budget)
        try:
            expected=part['lower_inclusive']
            while raw:=body.stream.readline((1<<20)+1):
                Q.need(raw.endswith(b'\n') and len(raw)<=1<<20,'FULL_SOURCE_ROW_BOUNDARY')
                value=json.loads(raw);Q.need(value['ordinal']==expected,'SOURCE_PART_ORDINAL_CONTIGUITY');expected+=1
                if (value['ordinal'] in chosen if chosen is not None else lower<=value['ordinal']<upper):count+=1;yield value
            Q.need(expected==part['upper_exclusive'],'SOURCE_PART_FULL_EOF_CENSUS');body.check()
        finally:body.close()
    want=32 if mode=='compat' else 10000 if mode=='profile' else upper-lower
    Q.need(count==want,'EXACT_SELECTED_COMPAT_PROFILE_OR_BATCH_ROWS_NO_REPLACEMENT')
