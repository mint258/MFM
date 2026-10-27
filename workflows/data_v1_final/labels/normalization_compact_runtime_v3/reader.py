"""Original logical group/file/physical order across every compact part/window."""
import hashlib,heapq,json,struct
from pathlib import Path
from . import contract as C,codec as K,bindings as B,runtime as I
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity,sqlite_ro,lookup_batch


def one_part(reference,expected_file,lo,hi,hash_content):
    import pyarrow.parquet as pq
    p=I.require(reference,content=hash_content);before=identity(p);stream=p.open('rb');source=pq.ParquetFile(stream,pre_buffer=False);last=-1
    try:
        for batch in source.iter_batches(batch_size=1,use_threads=False):
            row=batch.to_pylist()[0];C.need(K.row_signature(row)==row['view_sha256'] and row['file_id']==expected_file
              and lo<=row['physical_row']<hi and row['physical_row']>last,'VERIFIED_PART_KEY_BITS_OR_PHYSICAL_ORDER_CHANGED');last=row['physical_row'];yield row
    finally:source.close();stream.close();C.need(identity(p)==before,'CLOSED_COMPACT_PART_FRAME_CHANGED')


def observations(cfg,group,fields,*,hash_sources=False,include_all_roles=False):
    """One uninterrupted generator per original group. No physical-part QR state."""
    import pyarrow.parquet as pq
    coverage=I.load(I.require(cfg['coverage_reference']));catalog=Path(coverage['parts_catalog']['path'])
    C.need(identity(catalog)==cfg['catalog_frame'],'PARENT_CPU_VERIFIED_CATALOG_FRAME');db=sqlite_ro(catalog);index=sqlite_ro(cfg['canonical_index']['path'])
    source_book=I.load(I.require(cfg['source_inventory_reference']));byname={s['path']:s for s in source_book['files']};byid={f['field_id']:f for f in fields};selection=None
    if cfg['mode']=='pilot512':
        owner=pq.ParquetFile(I.require(group['owner_index']));selection={}
        try:
            for batch in owner.iter_batches(batch_size=512,use_threads=False):
                for row in batch.to_pylist():selection[row['record_id']]=row
        finally:owner.close()
    counts={t:0 for t in B.TASKS};fit_records=None;last_file=-1
    try:
        for filepos,reference in enumerate(group['label_files']):
            source=byname[reference['path']];fid=source['file_id'];C.need(source['source_job_id']==group['source_job_id'],'ORIGINAL_OWNER_GROUP_SOURCE_JOB')
            windows={}
            for lo,hi,task,pr in db.execute("SELECT lo,hi,task,ref FROM parts WHERE file=? AND kind='task' ORDER BY lo,task",(fid,)):
                windows.setdefault((lo,hi),[]).append((task,json.loads(pr)))
            previous=-1
            for (lo,hi),parts in windows.items():
                # Each actual source window has at most the original family's tasks.
                # Heap merge restores native physical row order across task-separated parts.
                streams=[one_part(pr,fid,lo,hi,hash_sources) for _,pr in parts];heap=[]
                try:
                    for k,stream in enumerate(streams):
                        row=next(stream,None)
                        if row is not None:heapq.heappush(heap,(row['physical_row'],k,row))
                    while heap:
                        physical,k,row=heapq.heappop(heap);C.need(physical>previous,'NO_DUPLICATE_OR_BACKWARDS_ORIGINAL_SOURCE_ROW');previous=physical
                        owner=lookup_batch(index,[row['record_id']]).get(row['record_id'])
                        C.need(owner and K.owner_signature(owner)==row['owner_sha256'] and owner['record_ordinal']==row['record_ordinal']
                          and B.ROLES[owner['new_role']]==row['role_code'],'UNCHANGED_COMPLETE_SOURCE_OWNER_ROLE_TUPLE')
                        if selection is not None:C.need(row['record_id'] in selection,'PILOT_SELECTION_DID_NOT_EXPAND')
                        if include_all_roles or owner['new_role']=='TRAIN':
                            base=db.execute('SELECT numbers,owner_sha,usable,meta FROM base WHERE ordinal=?',(row['record_ordinal'],)).fetchone()
                            C.need(base is not None and base[1]==row['owner_sha256'] and base[2]==1,'REAL_BASE_Z_ORIGINAL_ORDER_AND_PAYLOAD_REQUIRED')
                            numbers=[struct.unpack_from('<q',base[0],i)[0] for i in range(0,len(base[0]),8)]
                            if selection is not None:
                                original=selection[row['record_id']];g=B.decode(base[3],[])
                                C.need(g['source_payload_sha256']==original['record_payload_sha256'] and sum(z>1 for z in numbers)==original['heavy_atoms'],'ORIGINAL512_PAYLOAD_HEAVY_OR_ORDER_DIFFERS')
                            entries=K.unpack_entries(row,byid);mask=K.binary_json_loads(row['compact_mask_json']);fresh=B.compact.encode(row['record_ordinal'],row['task_code'],entries)
                            C.need(fresh==mask,'PERSISTED_MASK_SOURCE_NEW_REVIEW_AND_LEAF_PARITY')
                            entries.sort(key=lambda e:e['field_id'])
                            for entry in entries:
                                entry['persisted_review_codes']=[r['code'] for r in mask['review_groups'] if entry['field_id'] in B.compact.unpack(r['fields'])]
                            task=next(t for t,c in B.TASKS.items() if c==row['task_code']);counts[task]+=1
                            # These are source-TRAIN statistics. None is not a physical ID.
                            owner=dict(owner,effective_role=owner['new_role'],geometry_source='pm7',geometry_id=None,common_population=None)
                            yield owner,numbers,entries
                        nxt=next(streams[k],None)
                        if nxt is not None:heapq.heappush(heap,(nxt['physical_row'],k,nxt))
                finally:
                    for stream in streams:stream.close()
        if selection is not None:fit_records=len(selection) if include_all_roles else sum(r['new_role']=='TRAIN' for r in selection.values())
        else:fit_records=index.execute("SELECT count(*) FROM records WHERE job_id=?"+("" if include_all_roles else " AND new_role='TRAIN'"),(group['source_job_id'],)).fetchone()[0]
        C.need(all(v==fit_records for v in counts.values()),'UNCHANGED_SOURCE_TRAIN_ALL14_TASK_RECORD_MASS')
    finally:db.close();index.close();C.need(identity(catalog)==cfg['catalog_frame'],'VERIFIED_CATALOG_CHANGED_DURING_SOURCE_TRAIN_PASS')