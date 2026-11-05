"""Original typed float64 entries, exact logical order and final TRAIN predicate."""
import collections,heapq,json,math,struct
from pathlib import Path
from . import io as I
from ..normalization_compact_runtime_v3 import codec as K
from ..common_train_normalization_day_v1 import bindings as B
from ..source_status_cpu_auto_memory_v1.support import sqlite_ro,RECORD_COLUMNS
from ..window2_validity_v1.policy import apply_ea_entry,apply_sparse_entry


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
    # Closed canonical job_id is INTEGER; eligibility.job has TEXT affinity.
    # Compare their exact decimal representation, keeping every identity check
    # and returning the original canonical owner/job type unchanged.
    need(side is not None and side[:2]==(owner['record_id'],owner['molecule_id'])
         and type(side[2]) in (int,str) and type(owner['job_id']) in (int,str)
         and str(side[2])==str(owner['job_id']) and side[3]==owner['new_role'],
         'FINAL_ELIGIBILITY_OWNER_ALIGNMENT')
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
    numbers_cache={};counts={task:0 for task in B.TASKS};overrides=[];means={}
    from .r73 import Derived
    derived=Derived(cfg,group,fields) if any(f['field_id']>=146 for f in fields) else None
    sparse={};purpose=cfg['statistics_purpose']
    if cfg.get('mask_overrides_reference'):
        import pyarrow.parquet as pq
        for ref in I.load_data(cfg['mask_overrides_reference'])['files']:
            if ref['group_index']==group['group_index']:
                for override in pq.read_table(ref['path']).to_pylist():sparse[(override['record_id'],override['field_id'])]=override
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
                        ordinal=row['record_ordinal'];selected=not cfg.get('filter_mids') or owner['molecule_id'] in cfg['filter_mids']
                        if selected and ordinal not in numbers_cache:
                            base=db.execute('SELECT numbers,owner_sha,usable FROM base WHERE ordinal=?',(ordinal,)).fetchone()
                            need(base is not None and base[1]==row['owner_sha256'],'ORIGINAL_BASE_OWNER_ALIGNMENT')
                            need(not owner['fit_eligible'] or base[2]==1,'UNKNOWN_BASE_Z_CANNOT_ENTER_TRAIN')
                            numbers_cache[ordinal]=[struct.unpack_from('<q',base[0],i)[0] for i in range(0,len(base[0]),8)] if base[2] else []
                        entries=K.unpack_entries(row,byid) if selected else [];entries.sort(key=lambda e:e['field_id'])
                        original_r73=next((e for e in entries if e['field'].get('registry_id')==73 and e['field_id']<146),None)
                        if derived is not None and original_r73 is not None:entries.extend(derived.entries(row,source,original_r73))
                        for entry in entries:
                            key=(owner['record_id'],entry['field_id'])
                            if purpose=='element_reference':
                                override=apply_ea_entry(entry)
                                if override is not None:overrides.append(dict(override,record_id=owner['record_id'],molecule_id=owner['molecule_id'],record_ordinal=ordinal,source_path=source['path'],physical_row=row['physical_row']))
                            elif key in sparse:apply_sparse_entry(entry,sparse[key])
                            if purpose=='normalization_moments' and owner['fit_eligible']:
                                valid=[value for value,keep in zip(entry['values_float64'],entry['value_mask']) if keep]
                                if valid:
                                    mk=(owner['molecule_id'],entry['field_id']);prior=means.get(mk,(0.0,0))
                                    means[mk]=(math.fsum((prior[0],math.fsum(valid))),prior[1]+len(valid))
                        task=next(t for t,c in B.TASKS.items() if c==row['task_code']);counts[task]+=1
                        if selected:
                            if cfg.get('emit_source'):yield owner,numbers_cache[ordinal],entries,row,source
                            else:yield owner,numbers_cache[ordinal],entries
                        nxt=next(streams[k],None)
                        if nxt is not None:heapq.heappush(heap,(nxt['physical_row'],k,nxt))
                finally:
                    for stream in streams:stream.close()
        need(all(value==len(owners) for value in counts.values()),'ORIGINAL_14_TASK_RECORD_MASS')
        if purpose=='element_reference':
            cfg['mask_override_rows']=len(overrides);cfg['EA_newly_masked_records']=sum(override['newly_masked_leaves']>0 for override in overrides)
            write_overrides(Path(cfg['group_output_root'])/'mask_overrides.parquet',overrides)
        if purpose=='normalization_moments':write_means(Path(cfg['group_output_root'])/'molecule_field_means.parquet',means)
    finally:
        if derived is not None:derived.close()
        db.close();index.close();side.close()



def write_overrides(path,rows):
    import pyarrow as pa,pyarrow.parquet as pq
    schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('record_ordinal',pa.uint64()),
        ('field_id',pa.uint16()),('field_key',pa.string()),('reason',pa.string()),
        ('leaf_indices',pa.list_(pa.int32())),('newly_masked_leaves',pa.uint64()),
        ('source_convergence_state',pa.string()),('original_values_modified',pa.bool_()),
        ('source_path',pa.string()),('physical_row',pa.uint64())])
    pq.write_table(pa.Table.from_pylist(rows,schema=schema),path,compression='zstd')


def write_means(path,means):
    import pyarrow as pa,pyarrow.parquet as pq
    rows=[{'molecule_id':mid,'field_id':fid,'sum':total,'n':n,'mean':total/n}
          for (mid,fid),(total,n) in sorted(means.items())]
    schema=pa.schema([('molecule_id',pa.string()),('field_id',pa.uint16()),('sum',pa.float64()),('n',pa.uint64()),('mean',pa.float64())])
    pq.write_table(pa.Table.from_pylist(rows,schema=schema),path,compression='zstd')
