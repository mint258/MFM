"""Sixteen real ordinal partitions; only identity columns, no label values."""
import collections,os
from pathlib import Path
from . import contract as C,io as I
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import lookup_batch,sqlite_ro
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import soft_worker_rss,stop_requested
WORK={}

def initialize(cfg,frames,barrier):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);WORK.update(cfg=cfg,frames=frames,barrier=barrier)

def scan(item):
    import pyarrow.parquet as pq
    shard,lo,hi=item;cfg=WORK['cfg'];WORK['barrier'].wait(timeout=120);counts=collections.Counter();n=0;complete=True
    with I.opened(cfg['canonical_index'],WORK['frames']['canonical'],hash_content=False) as (canonical,_),I.opened(cfg['formal_record_index_reference'],WORK['frames']['formal'],hash_content=False) as (formal,_):
        db=sqlite_ro(Path('/proc/self/fd')/str(canonical.fileno()));reader=pq.ParquetFile(formal,pre_buffer=False)
        try:
            C.need(reader.metadata.num_rows==11231854,'FORMAL_PHYSICAL_RECORD_COUNT');required=['record_id','molecule_id','total_atoms'];C.need(set(required)<=set(reader.schema_arrow.names),'REAL_FORMAL_IDENTITY_COLUMNS')
            start=0
            for rg in range(reader.num_row_groups):
                rows=reader.metadata.row_group(rg).num_rows;end=start+rows
                if end<=lo or start>=hi:start=end;continue
                local=start
                for batch in reader.iter_batches(row_groups=[rg],batch_size=1024,columns=required,use_threads=False):
                    stop=local+batch.num_rows
                    if stop>lo and local<hi:
                        part=batch.slice(max(lo-local,0),min(stop,hi)-max(local,lo)).to_pylist();owners=lookup_batch(db,[r['record_id'] for r in part])
                        for ordinal,row in enumerate(part,max(local,lo)):
                            owner=owners.get(row['record_id']);C.need(owner and owner['record_ordinal']==ordinal and owner['molecule_id']==row['molecule_id']
                              and owner['total_atoms']==row['total_atoms'] and owner['new_role'] in ('TRAIN','VAL','FULL'),'EXACT_FORMAL_ORDINAL_ID_MOLECULE_NATOM_AND_CANONICAL_ROLE')
                            counts[(owner['job_id'],owner['new_role'])]+=1;n+=1
                    local=stop;soft_worker_rss(3<<30)
                    if stop_requested():complete=False;break
                if not complete:break
                start=end
            C.need(not complete or n==hi-lo,'NO_DUPLICATE_OR_MISSING_ORDINAL_PARTITION')
        finally:reader.close();db.close()
    return {'partition':shard,'lo':lo,'hi':hi,'records_verified':n,'complete':complete,'pid':os.getpid(),
      'counts':[{'source_job_id':j,'role':r,'records':v} for (j,r),v in sorted(counts.items())]}
