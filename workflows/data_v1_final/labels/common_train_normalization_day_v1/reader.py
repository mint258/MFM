"""Original binary codec/order; explicit final eligibility and raw-row locator seam."""
import hashlib,heapq,json,struct
from pathlib import Path
from . import contract as C,io as I,bindings as B,eligibility as E
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity,sqlite_ro,lookup_batch

def one_part(reference,expected_file,lo,hi):
    import pyarrow.parquet as pq
    p=I.require(reference);before=identity(p);stream=p.open('rb');source=pq.ParquetFile(stream,pre_buffer=False);last=-1
    try:
        for batch in source.iter_batches(batch_size=1,use_threads=False):
            row=batch.to_pylist()[0];K.validate_row_buffers(row)
            C.need(K.row_signature(row)==row['view_sha256'] and row['file_id']==expected_file
              and lo<=row['physical_row']<hi and row['physical_row']>last,'VERIFIED_PART_BITS_AND_PHYSICAL_ORDER');last=row['physical_row'];yield row
    finally:source.close();stream.close();C.need(identity(p)==before,'PART_FRAME_CHANGED')

def records(cfg,group,fields):
    coverage=I.load_data(cfg['coverage_reference'],8<<20);catalog=Path(coverage['parts_catalog']['path'])
    C.need(identity(catalog)==cfg['catalog_frame'],'CPU_VERIFIED_FULL_CATALOG_FRAME');db=sqlite_ro(catalog)
    index=sqlite_ro(cfg['canonical_index']['path']);side=sqlite_ro(cfg['eligibility_reference']['path'])
    side_frame=identity(cfg['eligibility_reference']['path']);index_frame=identity(cfg['canonical_index']['path'])
    book=I.load_data(cfg['source_inventory_reference'],2<<20);byname={s['path']:s for s in book['files']};byid={f['field_id']:f for f in fields};counts={t:0 for t in B.TASKS}
    try:
        for reference in group['label_files']:
            source=byname[reference['path']];fid=source['file_id'];C.need(source['source_job_id']==group['source_job_id'],'ORIGINAL_GROUP_FILE_ORDER')
            windows={}
            for lo,hi,task,pr,parent in db.execute("SELECT lo,hi,task,ref,parent FROM parts WHERE file=? AND kind='task' ORDER BY lo,task",(fid,)):
                pr=json.loads(pr);I.register_part(pr,json.loads(parent));windows.setdefault((lo,hi),[]).append((task,pr))
            previous=-1
            for (lo,hi),parts in windows.items():
                streams=[one_part(pr,fid,lo,hi) for _,pr in parts];heap=[]
                try:
                    for k,stream in enumerate(streams):
                        row=next(stream,None)
                        if row is not None:heapq.heappush(heap,(row['physical_row'],k,row))
                    while heap:
                        physical,k,row=heapq.heappop(heap);C.need(physical>previous,'NO_DUPLICATE_OR_BACKWARDS_SOURCE_ROW');previous=physical
                        owner=lookup_batch(index,[row['record_id']]).get(row['record_id'])
                        C.need(owner and K.owner_signature(owner)==row['owner_sha256'] and owner['record_ordinal']==row['record_ordinal']
                          and B.ROLES[owner['new_role']]==row['role_code'],'EXACT_ORIGINAL_SOURCE_OWNER_AND_ROLE')
                        owner=E.lookup(side,owner)
                        base=db.execute('SELECT numbers,owner_sha,usable,meta FROM base WHERE ordinal=?',(row['record_ordinal'],)).fetchone()
                        C.need(base is not None and base[1]==row['owner_sha256'],'BASE_OWNER_EXACT')
                        C.need(not owner['fit_eligible'] or base[2]==1,'UNKNOWN_BASE_Z_ORDER_CANNOT_ENTER_FIT')
                        numbers=[struct.unpack_from('<q',base[0],i)[0] for i in range(0,len(base[0]),8)] if base[2] else []
                        entries=K.unpack_entries(row,byid);mask=K.binary_json_loads(row['compact_mask_json'])
                        C.need(B.compact.encode(row['record_ordinal'],row['task_code'],entries)==mask,'ORIGINAL_PERSISTED_SOURCE_NEW_REVIEW_MASK_PARITY')
                        entries.sort(key=lambda e:e['field_id'])
                        task=next(t for t,c in B.TASKS.items() if c==row['task_code']);counts[task]+=1
                        yield owner,numbers,entries,row,source
                        nxt=next(streams[k],None)
                        if nxt is not None:heapq.heappush(heap,(nxt['physical_row'],k,nxt))
                finally:
                    for stream in streams:stream.close()
        expected=index.execute('SELECT count(*) FROM records WHERE job_id=?',(group['source_job_id'],)).fetchone()[0]
        C.need(all(v==expected for v in counts.values()),'ALL14_TASKS_ALL_ROLES_EXACT_CANONICAL_RECORD_MASS')
    finally:
        db.close();index.close();side.close()
        C.need(identity(catalog)==cfg['catalog_frame'] and identity(cfg['eligibility_reference']['path'])==side_frame
          and identity(cfg['canonical_index']['path'])==index_frame,'READONLY_CATALOG_ELIGIBILITY_CANONICAL_STABLE')

def observations(cfg,group,fields,*,hash_sources=False,include_all_roles=False):
    # No role is silently changed. Only the statistics caller interprets fit_eligible.
    for owner,numbers,entries,row,source in records(cfg,group,fields):
        if include_all_roles or owner['fit_eligible']:yield owner,numbers,entries
