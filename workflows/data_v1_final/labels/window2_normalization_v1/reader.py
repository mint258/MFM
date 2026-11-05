"""Original typed float64 entries, exact logical order and final TRAIN predicate."""
import heapq,json,struct
from pathlib import Path
from . import io as I
from ..normalization_compact_runtime_v3 import codec as K
from ..common_train_normalization_day_v1 import bindings as B
from ..source_status_cpu_auto_memory_v1.support import sqlite_ro,RECORD_COLUMNS


def need(value,message):
    if not value:raise ValueError(message)


def one_part(reference,expected_file,lo,hi):
    import pyarrow.parquet as pq
    table=pq.ParquetFile(I.require(reference),pre_buffer=False);last=-1
    try:
        for batch in table.iter_batches(batch_size=256,use_threads=False):
            for row in batch.to_pylist():
                need(row['file_id']==expected_file and lo<=row['physical_row']<hi and row['physical_row']>last,'TYPED_PART_PHYSICAL_ORDER')
                last=row['physical_row'];yield row
    finally:table.close()


def effective_owner(owner,side):
    need(side is not None and side[:4]==(owner['record_id'],owner['molecule_id'],owner['job_id'],owner['new_role']),'FINAL_ELIGIBILITY_OWNER_ALIGNMENT')
    return dict(owner,source_role=side[3],effective_role=side[4],common_population=bool(side[5]),
                geometry_source='pm7',geometry_id=side[6],parent_geometry_id=side[7],fit_eligible=bool(side[8]),fit_reason=side[9])


def observations(cfg,group,fields,**unused):
    coverage=I.load_data(cfg['coverage_reference']);db=sqlite_ro(coverage['parts_catalog']['path'])
    index=sqlite_ro(cfg['canonical_index']['path']);side=sqlite_ro(cfg['eligibility_reference']['path'])
    book=I.load_data(cfg['source_inventory_reference']);byname={s['path']:s for s in book['files']};byid={f['field_id']:f for f in fields}
    rows=side.execute('SELECT ordinal,rid,mid,job,source_role,effective_role,common_population,geometry_id,parent_geometry_id,fit_eligible,fit_reason FROM eligibility WHERE job=?',(group['source_job_id'],))
    eligibility={row[0]:row[1:] for row in rows};owners={}
    for row in index.execute('SELECT '+','.join(RECORD_COLUMNS)+' FROM records WHERE job_id=? ORDER BY record_ordinal',(group['source_job_id'],)):
        owner=dict(zip(RECORD_COLUMNS,row));owners[owner['record_id']]=effective_owner(owner,eligibility.get(owner['record_ordinal']))
    numbers_cache={};counts={task:0 for task in B.TASKS}
    try:
        for reference in group['label_files']:
            source=byname[reference['path']];fid=source['file_id']
            need(source['source_job_id']==group['source_job_id'],'ORIGINAL_GROUP_FILE_ORDER')
            windows={}
            for lo,hi,task,pr,parent in db.execute("SELECT lo,hi,task,ref,parent FROM parts WHERE file=? AND kind='task' ORDER BY lo,task",(fid,)):
                windows.setdefault((lo,hi),[]).append((task,json.loads(pr)))
            previous=-1
            for (lo,hi),parts in windows.items():
                streams=[one_part(pr,fid,lo,hi) for _,pr in parts];heap=[]
                try:
                    for k,stream in enumerate(streams):
                        row=next(stream,None)
                        if row is not None:heapq.heappush(heap,(row['physical_row'],k,row))
                    while heap:
                        physical,k,row=heapq.heappop(heap)
                        need(physical>previous,'NO_DUPLICATE_OR_BACKWARDS_SOURCE_ROW');previous=physical
                        owner=owners.get(row['record_id'])
                        need(owner is not None and owner['record_ordinal']==row['record_ordinal'] and B.ROLES[owner['new_role']]==row['role_code'],'ORIGINAL_TYPED_RECORD_ROLE_ALIGNMENT')
                        ordinal=row['record_ordinal']
                        if ordinal not in numbers_cache:
                            base=db.execute('SELECT numbers,owner_sha,usable FROM base WHERE ordinal=?',(ordinal,)).fetchone()
                            need(base is not None and base[1]==row['owner_sha256'],'ORIGINAL_BASE_OWNER_ALIGNMENT')
                            need(not owner['fit_eligible'] or base[2]==1,'UNKNOWN_BASE_Z_CANNOT_ENTER_TRAIN')
                            numbers_cache[ordinal]=[struct.unpack_from('<q',base[0],i)[0] for i in range(0,len(base[0]),8)] if base[2] else []
                        entries=K.unpack_entries(row,byid);entries.sort(key=lambda e:e['field_id'])
                        task=next(t for t,c in B.TASKS.items() if c==row['task_code']);counts[task]+=1
                        yield owner,numbers_cache[ordinal],entries
                        nxt=next(streams[k],None)
                        if nxt is not None:heapq.heappush(heap,(nxt['physical_row'],k,nxt))
                finally:
                    for stream in streams:stream.close()
        need(all(value==len(owners) for value in counts.values()),'ORIGINAL_14_TASK_RECORD_MASS')
    finally:db.close();index.close();side.close()
