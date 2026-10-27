"""Adopted sidecars plus real new-C0 contributions; original integer/mask maths."""
from __future__ import annotations
import argparse,ast,inspect
from . import contract as C,io as I
from workflows.data_v1_final.labels.full_projection_v1 import coverage as F
from workflows.data_v1_final.labels.full_projection_v1.coverage import (
 collections,hashlib,io,json,os,time,Path,CALIBRATION,need,pin,fsync_directory,decode,signature,
 compact,ROLES,identity,load,require,sqlite_ro,META_COLUMNS,metadata_only,sidecar_row,CappedOutput)

def write_adopted_sidecar(root,cfg,snapshot,authorized_parts,deadline):
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
                # Original inventory already verified exact numeric/type/key rows.
                # This seed hashes every selected historical part again before
                # projecting the unchanged metadata/mask view; F64 is not decoded.
                reference=part['reference'];p=Path(reference['path']);before=identity(p)
                need(authorized_parts.get(str(p))==reference and before[2]==reference['bytes'],'ROOT_SELECTED_HISTORICAL_PART_LOCATOR')
                I.data_ref(p,deadline,reference)
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
      'cache_F64_science_signature_recomputed':False,'closed_part_wholebody_SHA':'ACTUAL_SEED_CPU_SHA_MATCH_TO_INVENTORY_VERIFIED_HISTORICAL_PART',
      'tree_json_still_read_and_parsed_not_free_IO':True,
      'cost':{'metadata_projection_and_sidecar_write_seconds':projection_seconds,'sidecar_reopen_seconds':reopen_seconds,
        'sidecar_whole_SHA_seconds':hash_seconds,'cache_parts_opened':opened,'cache_parts_closed':closed,
        'closed_part_whole_SHA_bytes_read':part_bytes,
        'selected_column_compressed_bytes_from_actual_Parquet_metadata_not_physical_IO':chunk_bytes,
        'window_receipt_bytes_verified':sum(w['receipt']['bytes'] for w in snapshot['closed_windows']),
        'actual_physical_storage_read_bytes':'NOT_MEASURED'}}


def close_recovered_coverage(root,master,dispatch_snapshot,canonical_reference,adoption):
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
    need(not dispatch_snapshot['recovery_holds'],'ALL_RECOVERY_HOLDS_MUST_BE_RESOLVED_BEFORE_FINAL_COVERAGE')
    need(adoption['schema']==C.SUMMARY and adoption['origin']==C.ORIGIN and adoption['old_parent_state']=='TIMEOUT'
      and adoption['old_parent_c0'] is False,'ADOPTED_ORIGIN_IS_NOT_OLD_C0')
    contributions=[{'origin':C.ORIGIN,'manifest':adoption}]
    for accepted in dispatch_snapshot['batches']:
        receipt=accepted['receipt'];I.actual(receipt['actual_parent_chain'],'workflows.data_v1_final.labels.full_recovery_book_v1.run')
        m=load(require(receipt['manifest']))
        need(m['status']=='BATCH_CLOSED_CURSOR_ADVANCE_REQUIRED' and not m['quality_hold_fields'],'ACTUAL_ACCEPTED_BATCH_STATUS')
        contributions.append({'origin':'ACTUAL_C0_BATCH','manifest':m})
    for contribution in contributions:
        m=contribution['manifest']
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

def source_inverse():
    old=inspect.getsource(F.write_sidecar);new=inspect.getsource(write_adopted_sidecar)
    new=new.replace('def write_adopted_sidecar(root,cfg,snapshot,authorized_parts,deadline):','def write_sidecar(root,cfg,snapshot):')
    new=new.replace("need(authorized_parts.get(str(p))==reference and before[2]==reference['bytes'],'ROOT_SELECTED_HISTORICAL_PART_LOCATOR')\n                I.data_ref(p,deadline,reference)",
      "need(p.parent==Path(root)/'parts' and before[2]==reference['bytes'],'CURRENT_ALLOCATION_CLOSED_PART_FRAME')")
    new=new.replace("'closed_part_wholebody_SHA':'ACTUAL_SEED_CPU_SHA_MATCH_TO_INVENTORY_VERIFIED_HISTORICAL_PART'",
      "'closed_part_wholebody_SHA':'INHERITED_FROM_VERIFIED_SAME_ALLOCATION_TYPED_WRITER'")
    new=new.replace("'closed_part_whole_SHA_bytes_read':part_bytes","'available_closed_part_total_bytes_not_all_read':part_bytes")
    new=new.replace("                # Original inventory already verified exact numeric/type/key rows.\n                # This seed hashes every selected historical part again before\n                # projecting the unchanged metadata/mask view; F64 is not decoded.",
      "                # Fresh closed parts from THIS allocation already underwent\n                # frozen writer whole SHA + exact numerical/type/key reopen.\n                # Keep that receipt lineage and stable current file identity;\n                # do not repeat a whole F64-body hash/decode for a mask view.")
    need(new==old and ast.dump(ast.parse(new),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),'ADOPTION_SIDECAR_EXACT_RESOLVER_ONLY_INVERSE')
    need(sidecar_row is F.sidecar_row and metadata_only is F.metadata_only and signature is F.signature and compact is F.compact,'DIRECT_FROZEN_MASK_AND_TREE_OBJECTS')
    # Full closure changes only the origin loop plus the hold guard. Every
    # numeric/coverage/role/rate statement outside this declared block is exact.
    old=inspect.getsource(F.close_full_coverage);new=inspect.getsource(close_recovered_coverage)
    new=new.replace('def close_recovered_coverage(root,master,dispatch_snapshot,canonical_reference,adoption):',
      'def close_full_coverage(root,master,dispatch_snapshot,canonical_reference):')
    start=new.index("    need(not dispatch_snapshot['recovery_holds']")
    end=new.index("        for span in m['closed_physical_intervals']",start)
    original_start=old.index("    for accepted in dispatch_snapshot['batches']:")
    original_end=old.index("        for span in m['closed_physical_intervals']",original_start)
    new=new[:start]+old[original_start:original_end]+new[end:]
    need(new==old and ast.dump(ast.parse(new),include_attributes=False)==ast.dump(ast.parse(old),include_attributes=False),'MIXED_ORIGIN_ONLY_EXACT_COVERAGE_MATH_INVERSE')
    return {'status':'EXACT_RESOLVER_AND_ORIGIN_ONLY_BYTES_AST_INVERSE','mask_science_direct_objects':True,'thresholds_changed':False}


def parts_inventory(root,snapshot,adoption,cfg,deadline):
    """CPU-only exact current SHA inventory; original numeric readback stays attributed."""
    import os
    master=I.load(I.require(cfg['master_reference']));sources={r['file_id']:r for r in master['sources']}
    membership=I.json_data(adoption['adoption_membership_reference'],deadline)
    need(membership['holds']=={} and all(w['adopted'] for w in membership['all_old_consumed_windows'])
      and all(t['status']=='CLOSED' for t in membership['all_old_tickets']),'NO_UNKNOWN_OR_UNADOPTED_CONSUMED_HISTORY_IN_FINAL_INVENTORY')
    contributions=[{'origin_id':'timeout1904','origin_type':C.ORIGIN,'root':str(C.OLD),
      'windows':[r['window'] for r in membership['selected_verified_windows']],
      'authority':{'old_parent_actual_references':adoption['old_parent_actual_references'],
        'old_parent_state':'TIMEOUT','old_parent_c0':False,'inventory_actual_references':adoption['inventory_actual_references'],
        'seed_actual_references':cfg['seed_actual_references'],'seed_selection_reference':adoption['seed_selection_reference'],
        'resource_review_reference':adoption['resource_review_reference'],'adoption_summary_reference':cfg['adoption_summary_reference'],
        'adoption_membership_reference':adoption['adoption_membership_reference'],'sidecar_reference':adoption['sidecar']['reference']}}]
    for batch in snapshot['batches']:
        actual=batch['receipt']['actual_parent_chain'];_,request,_=I.actual(actual,'workflows.data_v1_final.labels.full_recovery_book_v1.run')
        manifest=I.load(I.require(batch['receipt']['manifest']));index=manifest['closed_window_index_reference']
        output=request['execution_argv'][request['execution_argv'].index('--output')+1]
        need(Path(index['path'])==Path(output)/'closed_window_index.json','REGISTERED_PRODUCER_WINDOW_INDEX')
        windows=I.json_data(index,deadline)
        contributions.append({'origin_id':'actual_C0:'+batch['name'],'origin_type':'ACTUAL_C0_BATCH','root':output,'windows':windows,
          'authority':{'actual_parent_chain':actual,'producer_manifest_reference':batch['receipt']['manifest'],
            'closed_window_index_reference':index,'sidecar_reference':manifest['sidecar']['reference'],'actual_parent_C0':True}})
    seen=set();rows=byte_count=count=0;origin_counts=collections.Counter();origins=[];path=Path(root)/'actual_parts_inventory.jsonl'
    with path.open('xb') as stream:
        for origin in contributions:
            origins.append({k:v for k,v in origin.items() if k not in ('root','windows')})
            origin_counts[origin['origin_type']]+=1
            for window in origin['windows']:
                body=I.json_data(window['receipt'],deadline,256<<10);fid=body['file_id'];base=Path(origin['root'])/'parts'
                need(body['schema']=='BOUNDED_TYPED_PHYSICAL_WINDOW_V1' and body['range_id']==window['range_id']
                  and body['physical_row_lo']==window['lo']<window['hi']==body['physical_row_hi']
                  and body['all_part_reopen_bits_verified'] is True and fid in sources
                  and Path(window['receipt']['path'])==base/('window_'+body['ticket']+'.json'),'EXACT_ORIGINAL_WINDOW_IDENTITY')
                need({k:body['source_reference'][k] for k in ('path','bytes','sha256')}=={k:sources[fid][k] for k in ('path','bytes','sha256')},
                  'SAME_FROZEN_PHYSICAL_SOURCE_LOCATOR')
                classifications=body['physical_classifications']
                need(all(type(v) is int and v>=0 for v in classifications.values()) and sum(classifications.values())==window['hi']-window['lo']
                  and sum(p['rows'] for p in body['parts'])==classifications.get('CANONICAL',0),'ORIGINAL_PHYSICAL_AND_CANONICAL_ROW_MASS')
                for spec in body['parts']:
                    reference=spec['reference'];name='part_'+body['ticket']+'_'+spec['row_kind']+'_'+str(spec['task_code'])+'.parquet'
                    need(Path(reference['path'])==base/name and reference['path'] not in seen,'UNIQUE_EXACT_TICKET_PART_PATH')
                    seen.add(reference['path']);current,identity_frame=I.data_ref(reference['path'],deadline,reference)
                    record={'schema':'LABELS_RECOVERED_VERIFIED_PART_V1','origin_id':origin['origin_id'],'origin_type':origin['origin_type'],
                      'file_id':fid,'source_reference':body['source_reference'],'physical_row_lo':window['lo'],'physical_row_hi':window['hi'],
                      'range_id':window['range_id'],'ticket':body['ticket'],'window_receipt_reference':window['receipt'],
                      'reference':current,'row_kind':spec['row_kind'],'task_code':spec['task_code'],'rows':spec['rows'],
                      'typed_stream_sha256':spec['typed_stream_sha256'],'current_frame':identity_frame,
                      'current_whole_SHA_verified':True,'numeric_readback_basis':'ORIGINAL_ACTUAL_INVENTORY_AND_SEED_C0' if origin['origin_type']==C.ORIGIN
                        else 'ORIGINAL_ACTUAL_C0_WRITER_REOPEN_AND_EXACT_CURRENT_SHA','numeric_body_redecoded_this_close':False}
                    raw=(json.dumps(record,sort_keys=True,allow_nan=False)+'\n').encode()
                    need(len(raw)<=64<<10 and stream.tell()+len(raw)<=512<<20,'FINITE_PART_INVENTORY_OUTPUT')
                    stream.write(raw);count+=1;rows+=spec['rows'];byte_count+=current['bytes']
        stream.flush();os.fsync(stream.fileno())
    fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)
    ref,_=I.data_ref(path,deadline)
    return {'actual_parts_inventory_reference':ref,'actual_part_count':count,'actual_part_rows':rows,
      'actual_part_whole_SHA_bytes_read':byte_count,'accepted_origins':origins,'origin_counts':dict(origin_counts),
      'origin_count_unit':'ACCEPTED_PRODUCER_OR_ADOPTION_ORIGINS','held_source_count':len(snapshot['recovery_holds']),
      'unresolved_consumed_count':0,'unverified_part_count':0,'final_mask_release':False,'D4_release':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','startup-proof','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args();cfg=I.load(a.config);review=I.load(I.require(cfg['resource_review_reference']));C.budget(review)
    proof=I.admit(a.startup_proof,a.config,C.CLOSE_KEY,cfg['scope_parameters'],2<<30,cfg['wall_seconds'],cfg['small_references'])
    root=I.new_root(a.output)
    try:
        gate=I.fixtures(root/'recovery_fixtures.json');inverse=source_inverse()
        need(proof['request'].get('data_references',[])==cfg['known_data_references']
          and proof['request'].get('deferred_authority_references',[])==cfg['transitive_output_authority_references'],
          'EXACT_DATA_AND_C0_TRANSITIVE_PART_AUTHORITY')
        deadline=I.start(proof,root,cfg['resource_review_reference'],(2<<30)+cfg['remaining_cache_reservation_bytes'],cfg['wall_seconds'])
        adoption=I.load(I.require(cfg['adoption_summary_reference']));I.actual(cfg['seed_actual_references'],
          'workflows.data_v1_final.labels.full_recovery_book_v1.seed')
        snapshot=I.load(I.require(cfg['dispatch_snapshot_reference']));master=I.load(I.require(cfg['master_reference']))
        need(snapshot['adoption_summary_reference']==cfg['adoption_summary_reference'] and snapshot['metadata']['master']==cfg['master_reference']
          and snapshot['metadata']['review']==cfg['resource_review_reference'],'EXACT_NEWBOOK_SEED_MASTER_RESOURCE_CHAIN')
        inventory=parts_inventory(root,snapshot,adoption,cfg,deadline)
        result=close_recovered_coverage(root,master,snapshot,cfg['canonical_index'],adoption)
        result.update(inventory)
        result.update(schema='LABELS_RECOVERED_FULL_SOURCE_COVERAGE_V1',job_id=str(proof['job_id']),fixture_gate=gate,
          source_inverse_proof=inverse,old_parent_state='TIMEOUT',old_parent_c0=False,guide_complete=False,
          adoption_summary_reference=cfg['adoption_summary_reference'],dispatch_snapshot_reference=cfg['dispatch_snapshot_reference'])
        need(sum(p.stat().st_size for p in root.rglob('*') if p.is_file())+(64<<20)+(2<<20)<=2<<30,'WHOLE_COVERAGE_OUTPUT_AND_OBSERVER_RESERVES')
        I.write_new(root/'manifest.json',result)
        need(not result['quality_hold_fields'],'ORIGINAL_FULL_NEW_MASK1PCT_HOLD')
    except BaseException as exc:
        I.write_new(root/'failure.json',{'error':type(exc).__name__+':'+str(exc)[:500],'old_book_written':False,'automatic_retry':False});raise

if __name__=='__main__':main()