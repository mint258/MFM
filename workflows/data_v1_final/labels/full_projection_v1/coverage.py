"""Compact mask/role cache and final exact slot coverage; no new mask rules."""
from __future__ import annotations
import collections,hashlib,io,json,os,time
from pathlib import Path
from .control import CALIBRATION,need
from workflows.data_v1_final.labels.bounded_projection_v1.parts import pin,fsync_directory
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import decode,signature
from workflows.data_v1_final.labels.streaming_v1 import compact
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import ROLES,identity,load,require,sqlite_ro
META_COLUMNS=['row_kind','record_ordinal','task_code','tree_json','scientific_signature']


def metadata_only(template):
    """Select non-F64 subtrees, then use the frozen typed decoder unchanged.

    Parsing tree_json still costs IO/CPU; the numeric F64 column is not read or
    traversed, and no full scientific signature is recalculated. Any unexpected
    F64 dependency inside this metadata schema is a HOLD, never an excuse to
    fetch the source numeric pool or invent a replacement value.
    """
    top=json.loads(template);need(top[0]=='d','CACHE_METADATA_ROOT_OBJECT')
    keys=[k for k,v in top[1]];need(len(keys)==len(set(keys)),'CACHE_METADATA_DUPLICATE_TOP_KEY')
    wanted={'provenance','original_compact_candidate','field_observations'}
    selected=['d',[[k,v] for k,v in top[1] if k in wanted]]
    try:value=decode(json.dumps(selected,separators=(',',':')),[])
    except IndexError as exc:raise ValueError('CACHE_METADATA_UNEXPECTED_F64_POOL_REFERENCE') from exc
    need('provenance' in value,'CACHE_METADATA_PROVENANCE_REQUIRED');return value


class CappedOutput(io.RawIOBase):
    """Direct disk writes reserve before IO; reaching cap preserves .partial."""
    def __init__(self,path,cap):super().__init__();self.stream=Path(path).open('xb');self.cap=cap;self.count=0
    def writable(self):return True
    def seekable(self):return False
    def tell(self):return self.count
    def write(self,raw):
        need(self.count+len(raw)<=self.cap,'SIDECAR_SERIALIZED_RESERVATION_NO_TRUNCATION')
        n=self.stream.write(raw);need(n==len(raw),'SIDECAR_SHORT_WRITE');self.count+=n;return n
    def flush(self):
        if not self.stream.closed:self.stream.flush()
    def close(self):pass  # Arrow owns its wrapper, not this object's durable file.
    def finish(self):self.stream.flush();os.fsync(self.stream.fileno());self.stream.close()
    def abort(self):
        if not self.stream.closed:self.stream.close()


def sidecar_row(row,payload,enabled_by_key):
    """Original compact bits/reasons/leaf exceptions are copied verbatim."""
    owner=payload['provenance']['owner'];role=owner['new_role'];candidate=payload.get('original_compact_candidate')
    need(row['record_ordinal']==owner['record_ordinal'],'SIDECAR_OWNER_ORDINAL')
    if row['row_kind']=='task':
        need(candidate['record_ordinal']==row['record_ordinal'] and candidate['task_code']==row['task_code'],'UNCHANGED_ORIGINAL_COMPACT_KEYS')
    else:need(row['row_kind']=='base' and row['task_code']==255 and candidate is None,'BASE_IS_NOT_AN_EMPTY_TASK_MASK')
    structural=[enabled_by_key[o['field_key']] for o in payload.get('field_observations',[])
      if o['field_key'] in enabled_by_key and o['payload_structural_failure']]
    return {'record_ordinal':row['record_ordinal'],'task_code':row['task_code'],'role_code':ROLES[role],
      'review_flags':0,'file_id':payload['provenance']['source_reference']['file_id'],
      'physical_row_ordinal':payload['provenance']['physical_row_ordinal'],'candidate':candidate,
      'structural_invalid_fields':compact.bits(structural),'cache_scientific_signature':bytes.fromhex(row['scientific_signature'])},role


def write_sidecar(root,cfg,snapshot):
    import pyarrow as pa
    import pyarrow.parquet as pq
    started=time.monotonic()
    fields=load(require(cfg['science']['sources']['registry']))['fields']
    enabled={f['field_key']:i for i,f in enumerate(sorted((f for f in fields if f['status']=='enabled'),key=lambda f:f['field_key']))}
    need(len(enabled)==146,'SAME_FIELD_ID_ORDER_AS_FROZEN_INITIALIZER')
    schema=pa.schema([('record_ordinal',pa.uint64()),('task_code',pa.uint8()),('role_code',pa.uint8()),('review_flags',pa.uint32()),
      ('file_id',pa.uint32()),('physical_row_ordinal',pa.uint64()),('candidate',pa.struct(list(compact.arrow_schema()))),
      ('structural_invalid_fields',pa.binary(compact.WIDTH)),('cache_scientific_signature',pa.binary(32))])
    path=Path(root)/'mask_role_sidecar.parquet';temporary=Path(str(path)+'.partial')
    sink=CappedOutput(temporary,cfg['sidecar_reserve_bytes']);writer=pq.ParquetWriter(sink,schema,compression='zstd')
    stats=collections.defaultdict(collections.Counter);declared=collections.defaultdict(collections.Counter)
    classes=collections.defaultdict(collections.Counter);role_task=collections.Counter();rows=0;buffer=[];buffer_estimate=0;logical=hashlib.sha256()
    opened=closed=chunk_bytes=part_bytes=0
    try:
        for window in snapshot['closed_windows']:
            body=load(require(window['receipt']));classes[body['source_reference']['source_kind']].update(body['physical_classifications'])
            for part in body['parts']:
                # Fresh closed parts from THIS allocation already underwent
                # frozen writer whole SHA + exact numerical/type/key reopen.
                # Keep that receipt lineage and stable current file identity;
                # do not repeat a whole F64-body hash/decode for a mask view.
                reference=part['reference'];p=Path(reference['path']);before=identity(p)
                need(p.parent==Path(root)/'parts' and before[2]==reference['bytes'],'CURRENT_ALLOCATION_CLOSED_PART_FRAME')
                stream=p.open('rb');source=None;mass=0;opened+=1;part_bytes+=reference['bytes']
                try:
                    current=os.fstat(stream.fileno())
                    need([current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns,current.st_ctime_ns]==before,'SIDECAR_SAME_FD_CLOSED_PART')
                    source=pq.ParquetFile(stream,pre_buffer=False)
                    for g in range(source.num_row_groups):
                        rg=source.metadata.row_group(g)
                        chunk_bytes+=sum(rg.column(i).total_compressed_size for i in range(rg.num_columns)
                          if rg.column(i).path_in_schema.split('.')[0] in META_COLUMNS)
                    for batch in source.iter_batches(batch_size=16,columns=META_COLUMNS,use_threads=False):
                        for row in batch.to_pylist():
                            payload=metadata_only(row['tree_json']);out,role=sidecar_row(row,payload,enabled);c=out['candidate']
                            if c is not None:
                                axes={k:set(compact.unpack(c[k])) for k in ('in_scope_fields','source_valid_fields','valid_fields','all_leaves_valid_fields','newly_masked_fields')}
                                structural=set(compact.unpack(out['structural_invalid_fields']))
                                for fid in axes['in_scope_fields']:
                                    counter=stats[json.dumps([role,fid],separators=(',',':'))];counter['records']+=1
                                    for name in ('source_valid_fields','valid_fields','all_leaves_valid_fields','newly_masked_fields'):counter[name]+=fid in axes[name]
                                    counter['new_payload_structural_invalid_records']+=fid in structural
                                for observation in payload['field_observations']:
                                    counter=declared[json.dumps([role,observation['field_key']],separators=(',',':'))]
                                    for name in ('records','numeric_leaves','nonnumeric_or_nonfinite_leaves','zero_leaves','payload_structural_failure'):counter[name]+=int(observation[name])
                            logical.update(signature(out).encode())
                            estimate=1024+(128*len(c['leaf_exceptions'])+128*sum(len(c[k]) for k in ('source_reason_groups','new_reason_groups','review_groups')) if c else 0)
                            if buffer and buffer_estimate+estimate>8<<20:
                                writer.write_table(pa.Table.from_pylist(buffer,schema=schema),row_group_size=4096);buffer=[];buffer_estimate=0
                            buffer.append(out);buffer_estimate+=estimate;rows+=1;mass+=1;role_task[json.dumps([role,out['task_code']],separators=(',',':'))]+=1
                            if len(buffer)>=4096 or buffer_estimate>=8<<20:
                                writer.write_table(pa.Table.from_pylist(buffer,schema=schema),row_group_size=4096);buffer=[];buffer_estimate=0
                    current=os.fstat(stream.fileno())
                    need([current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns,current.st_ctime_ns]==before==identity(p),'CLOSED_PART_CHANGED_DURING_SMALL_COLUMN_PROJECTION')
                finally:
                    if source is not None:source.close()
                    stream.close();closed+=1
                need(mass==part['rows'],'SIDECAR_CLOSED_PART_ROW_MASS')
        if buffer:writer.write_table(pa.Table.from_pylist(buffer,schema=schema),row_group_size=4096)
        writer.close();sink.finish();os.rename(temporary,path);fsync_directory(path.parent)
    except BaseException:sink.abort();raise
    projection_seconds=time.monotonic()-started;reopen_started=time.monotonic()
    read=0;reopened=hashlib.sha256();source=pq.ParquetFile(path)
    try:
        for batch in source.iter_batches(batch_size=16,use_threads=False):
            for row in batch.to_pylist():reopened.update(signature(row).encode());read+=1
    finally:source.close()
    need(read==rows and reopened.digest()==logical.digest(),'SIDECAR_REOPEN_ORIGINAL_BITS_REASONS_KEYS_MASS')
    reopen_seconds=time.monotonic()-reopen_started;hash_started=time.monotonic();reference=pin(path);hash_seconds=time.monotonic()-hash_started
    return {'reference':reference,'rows':rows,'field_stats_by_source_role':{k:dict(v) for k,v in stats.items()},
      'all264_declaration_observations_by_source_role':{k:dict(v) for k,v in declared.items()},'role_task_counts':dict(role_task),
      'physical_classifications_by_kind':{k:dict(v) for k,v in classes.items()},'ordered_key_role_original_science_signature':logical.hexdigest(),
      'source_new_review_bits_and_sparse_leaf_exceptions_copied':True,'sidecar_reopen_verified':True,'candidate_masks_frozen':False,
      'calibration_state':CALIBRATION,'base_candidate_is_null_not_task_missing':True,
      'cache_Arrow_columns_read':META_COLUMNS,'cache_F64_pool_column_read':False,
      'cache_F64_science_signature_recomputed':False,'closed_part_wholebody_SHA':'INHERITED_FROM_VERIFIED_SAME_ALLOCATION_TYPED_WRITER',
      'tree_json_still_read_and_parsed_not_free_IO':True,
      'cost':{'metadata_projection_and_sidecar_write_seconds':projection_seconds,'sidecar_reopen_seconds':reopen_seconds,
        'sidecar_whole_SHA_seconds':hash_seconds,'cache_parts_opened':opened,'cache_parts_closed':closed,
        'available_closed_part_total_bytes_not_all_read':part_bytes,
        'selected_column_compressed_bytes_from_actual_Parquet_metadata_not_physical_IO':chunk_bytes,
        'window_receipt_bytes_verified':sum(w['receipt']['bytes'] for w in snapshot['closed_windows']),
        'actual_physical_storage_read_bytes':'NOT_MEASURED'}}


def close_full_coverage(root,master,dispatch_snapshot,canonical_reference):
    """Allocation-only library API, called under a separately reviewed close stage.

    Caller supplies the actual DispatchBook snapshot after actual-C0 acceptance;
    every referenced sidecar is SHA-verified here. No source Parquet is opened.
    review_flags=0 is the projection coverage-view placeholder, not an assertion
    that a row has no source/new/statistical reviews (those remain in candidate).
    """
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from workflows.data_v1_final.labels.source_status_v1.reduce import consume_coverage
    started=time.monotonic();n=master['scope']['canonical_records'];root=Path(root)
    need(all(s['lease'] is None and s['next_physical_row']==s['physical_row_hi'] for s in dispatch_snapshot['sources'])
      and len(dispatch_snapshot['sources'])==2208,'ALL_SOURCE_PHYSICAL_CURSORS_CLOSED')
    need(all(b['state']=='ACTUAL_C0_CLOSED' for b in dispatch_snapshot['batches']),'ALL_BATCHES_ACTUAL_C0_ACCEPTED')
    seen=np.memmap(root/'all14task_coverage.uint8',mode='w+',dtype=np.uint8,shape=(14,n));seen[:]=0
    bases=np.memmap(root/'base_coverage.uint8',mode='w+',dtype=np.uint8,shape=(1,n));bases[:]=0
    roles=np.memmap(root/'source_role.uint8',mode='w+',dtype=np.uint8,shape=(n,));roles[:]=255
    hash_start=time.monotonic();canonical_path=require(canonical_reference);canonical_hash_seconds=time.monotonic()-hash_start
    db=sqlite_ro(canonical_path);count=0
    try:
        for ordinal,role in db.execute('SELECT record_ordinal,new_role FROM records ORDER BY record_ordinal'):
            need(type(ordinal) is int and 0<=ordinal<n and roles[ordinal]==255,'UNIQUE_ROLE_ORDINAL');roles[ordinal]=ROLES[role];count+=1
    finally:db.close()
    need(count==n and not np.any(roles==255),'COMPLETE_ACTUAL_SOURCE_ROLE_AUTHORITY')
    intervals=collections.defaultdict(list);classes=collections.defaultdict(collections.Counter)
    fieldstats=collections.defaultdict(collections.Counter);declarations=collections.defaultdict(collections.Counter)
    role_task=collections.Counter();sidecarrows=0;hash_seconds=sidecar_hash_bytes=0;projection_started=time.monotonic()
    for accepted in dispatch_snapshot['batches']:
        receipt=accepted['receipt'];m=load(require(receipt['manifest']))
        need(m['status']=='BATCH_CLOSED_CURSOR_ADVANCE_REQUIRED' and not m['quality_hold_fields'],'ACTUAL_ACCEPTED_BATCH_STATUS')
        for span in m['closed_physical_intervals']:intervals[span['file_id']].append((span['lo'],span['hi']))
        sc=m['sidecar']
        for k,v in sc['physical_classifications_by_kind'].items():classes[k].update(v)
        for k,v in sc['field_stats_by_source_role'].items():fieldstats[k].update(v)
        for k,v in sc['all264_declaration_observations_by_source_role'].items():declarations[k].update(v)
        role_task.update(sc['role_task_counts']);hash_start=time.monotonic();sidecar_path=require(sc['reference'])
        hash_seconds+=time.monotonic()-hash_start;sidecar_hash_bytes+=sc['reference']['bytes']
        source=pq.ParquetFile(sidecar_path);mass=0
        try:
            for batch in source.iter_batches(batch_size=65536,columns=['record_ordinal','task_code','role_code','review_flags'],use_threads=False):
                task=batch.column('task_code').to_numpy(zero_copy_only=False)
                labels=batch.filter(pa.array(task!=255));base=batch.filter(pa.array(task==255))
                if labels.num_rows:consume_coverage(labels,seen,roles,n)
                if base.num_rows:
                    # This isolated one-slot coverage view maps BASE255->0 only
                    # for the frozen coverage function; published data stays255.
                    base=base.set_column(base.schema.get_field_index('task_code'),'task_code',pa.array(np.zeros(base.num_rows,dtype=np.uint8)))
                    consume_coverage(base,bases,roles,n)
                mass+=batch.num_rows
        finally:source.close()
        need(mass==sc['rows'],'EXACT_SIDECAR_ROWS');sidecarrows+=mass
    need(set(intervals)=={s['file_id'] for s in master['sources']},'ALL2208_PHYSICAL_SOURCES')
    for source in master['sources']:
        cursor=0
        for lo,hi in sorted(intervals[source['file_id']]):need(cursor==lo<hi<=source['rows'],'PHYSICAL_GAP_OR_DUPLICATE');cursor=hi
        need(cursor==source['rows'],'PHYSICAL_SOURCE_TAIL_PENDING')
    need(all(int(np.count_nonzero(seen[i]))==n for i in range(14)) and int(np.count_nonzero(bases))==n,'ALL14TASK_PLUS_BASE_EXACT_ONCE')
    need(classes['label']['CANONICAL']==14*n and classes['base']['CANONICAL']==n
      and sum(classes['label'].values())==master['scope']['label_physical_rows']
      and sum(classes['base'].values())==master['scope']['base_physical_rows'],'PHYSICAL_CANONICAL_CLASSIFICATIONS')
    need(sum(v for k,v in classes['label'].items() if k!='CANONICAL')==8694
      and sum(v for k,v in classes['base'].items() if k!='CANONICAL')==621,'SHADOW_AND_BASE_DIFFERENCE_SEPARATE')
    rates=collections.defaultdict(collections.Counter)
    for k,v in fieldstats.items():rates[str(json.loads(k)[1])].update(v)
    need(set(rates)=={str(i) for i in range(146)} and all(v['records']==n for v in rates.values()),'ALL146_ENABLED_FIELD_RECORD_DENOMINATORS')
    role_counts={role:int(np.count_nonzero(roles==code)) for role,code in ROLES.items()}
    need(all(fieldstats.get(json.dumps([role,fid],separators=(',',':')),{}).get('records',0)==mass
      for role,mass in role_counts.items() for fid in range(146)),'ALL_FIELD_SOURCE_ROLE_DENOMINATORS')
    hold=sorted(k for k,v in rates.items() if v['newly_masked_fields']/n>.01 or v['new_payload_structural_invalid_records']/n>.01)
    seen.flush();bases.flush();roles.flush()
    return {'status':'FULL_NUMERIC_SOURCE_COVERAGE_QUALITY_HOLD' if hold else 'FULL_NUMERIC_SOURCE_COVERAGE_OBSERVED_NOT_FINAL_MASKS',
      'all14task_and_base_exact_once':True,'sidecar_rows':sidecarrows,'physical_classifications_by_kind':{k:dict(v) for k,v in classes.items()},
      'field_stats_by_source_role':{k:dict(v) for k,v in fieldstats.items()},'role_task_counts':dict(role_task),'quality_hold_fields':hold,
      'all264_declaration_observations_by_source_role':{k:dict(v) for k,v in declarations.items()},'actual_source_role_records':role_counts,
      'coverage_files':[pin(root/name) for name in ('all14task_coverage.uint8','base_coverage.uint8','source_role.uint8')],
      'calibration_state':CALIBRATION,'guide1p5_complete':False,'candidate_masks_frozen':False,'normalization_completed':False,
      'native_print_precision_actual_frame_and_withinmol_reviews':'PENDING_INDEPENDENT_EVIDENCE',
      'cost':{'canonical_whole_SHA_bytes':canonical_reference['bytes'],'canonical_whole_SHA_seconds':canonical_hash_seconds,
        'sidecar_whole_SHA_bytes':sidecar_hash_bytes,'sidecar_whole_SHA_seconds':hash_seconds,
        'sidecar_projection_and_checks_elapsed_seconds_including_hash':time.monotonic()-projection_started,
        'whole_close_elapsed_seconds':time.monotonic()-started,'original_source_Parquet_read':False,
        'typed_cache_F64_pool_read':False,'typed_cache_full_science_signature_recomputed':False,
        'sidecar_columns_read':['record_ordinal','task_code','role_code','review_flags'],'actual_physical_storage_read_bytes':'NOT_MEASURED'}}
