"""All-source metadata census; never fits, changes labels, or creates masks."""
from __future__ import annotations
import argparse, collections, concurrent.futures, hashlib, json, multiprocessing, os, time
from pathlib import Path
from .support import (BOUNDARY, OWNER, ROLES, TASKS, TASK_FAMILIES, classify_owner,
    compact_key, declared_shape, guard, identity, load, lookup_batch, need, new_root,
    ref, report_flags, require, rss, save, scf_state, sqlite_ro, unique_bytes)
WORK={}

def serialized(entry):
    p=entry.get('source_path','').lower()
    return entry['task'] in TASK_FAMILIES and entry['task'] not in ('D20','D3') and not any(
        x in p for x in ('polar_blocks','static_polar_block','static_finite_field_tensors'))

def source_columns(source):
    family=source['family'];common=list(OWNER)+['status']
    if family=='D20':return common+['descriptor_names','valid_mask','values_float64','issues']
    if family=='D3':return common+['PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2','issues']
    return common+['calc_type','lane','total_atoms','source_status','failure_code','converged',
      'scf_iterations','software_version_id','numeric_issues','precision_by_field_json',
      'raw_audit_selected','raw_output_locator_json','reproduction_package_sha256']

def metadata_projection(handle, source):
    cols=source_columns(source);missing=set(cols)-set(handle.schema_arrow.names)
    need(not missing,'EXPECTED_FROZEN_SOURCE_COLUMNS_MISSING:'+repr(sorted(missing)))
    if source['family'] not in ('D20','D3'):
        leaf=[]
        for i in range(len(handle.schema)):
            path=handle.schema.column(i).path
            if path.startswith('values.') and (path.endswith('.registry_id') or path.endswith('.kind') or '.shape.' in path):leaf.append(path)
        need(any(p.endswith('.registry_id') for p in leaf) and any(p.endswith('.kind') for p in leaf),'CELL_METADATA_LEAVES_MISSING')
        # Physical leaf names avoid guessing Arrow nested-list aliases.
        cols+=leaf
    return cols

def precision_metadata(value):
    if value is None:return 'COLUMN_NULL',{},None
    if not isinstance(value,str) or len(value)>65536:return 'MALFORMED_OR_OVER_BOUND',{},None
    try:parsed=json.loads(value)
    except (ValueError,TypeError):return 'MALFORMED_JSON',{},None
    if not isinstance(parsed,dict):return 'NONOBJECT_JSON',{},None
    raw=json.dumps(parsed,sort_keys=True,separators=(',',':'),allow_nan=True)
    return ('EMPTY_OBJECT' if not parsed else 'DECLARED_SOURCE_METADATA'),parsed,hashlib.sha256(raw.encode()).hexdigest()

def native_observations(row, family):
    if family=='D20':
        names=row['descriptor_names'];masks=row['valid_mask'];values=row['values_float64']
        layout=(isinstance(masks,list) and len(masks)==20 and all(type(x) is bool for x in masks)
                and isinstance(values,list) and len(values)==20)
        if names is None and isinstance(masks,list) and not any(masks):names=WORK['d20_names']
        names_ok=names==WORK['d20_names']
        for i,name in enumerate(WORK['d20_names']):
            value=values[i] if layout else None
            yield name,('SOURCE_VALID_TRUE' if masks[i] else 'SOURCE_VALID_FALSE') if layout and names_ok else 'NATIVE_LAYOUT_INVALID',('NULL' if value is None else 'NONNULL'), 'float64[20]',None
    else:
        for name in ('PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2','SASA_atom_A2'):
            value=row[name]
            shape='[N]' if name=='SASA_atom_A2' and isinstance(value,list) and len(value)==row['_atoms'] else ('ATOM_LENGTH_DIFFERS' if name=='SASA_atom_A2' and value is not None else 'SCALAR')
            yield name,'OBSERVED_SOURCE_VALUE_NULLNESS',('NULL' if value is None else 'NONNULL'),shape,None

def initialize(cfg, index, raw_registry, d20_names, stop, barrier):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    WORK.update(cfg=cfg,index=index,raw_registry=raw_registry,d20_names=d20_names,stop=stop,barrier=barrier)

def scan_file(item):
    file_id,source,output,warmup=item;cfg=WORK['cfg'];start=time.monotonic();root=Path(output)/('file_'+str(file_id).zfill(4))
    need(not WORK['stop'].is_set(),'PEER_FAILURE_NO_NEXT_SOURCE_FILE')
    if warmup:WORK['barrier'].wait(timeout=120)
    root.mkdir(mode=0o700);handle=None;db=None;writer=None;opened=closed=0;identity_before=None
    path=Path(source['path']);limit=source['latest_rows']*64+(4<<20)
    status=collections.Counter();fields=collections.Counter();precision=collections.Counter();shadow=collections.Counter();shadow_status=collections.Counter()
    role_counts=collections.Counter();task_counts=collections.Counter();flags_counts=collections.Counter();unknown=collections.Counter();duplicates=collections.Counter()
    examples=[];precision_examples={};coverage=[];physical=canonical=0;max_rss=0
    import pyarrow as pa
    import pyarrow.parquet as pq
    schema=pa.schema([('record_ordinal',pa.uint64()),('task_code',pa.uint8()),('role_code',pa.uint8()),('review_flags',pa.uint16())])
    def flush():
        nonlocal writer,coverage
        if not coverage:return
        table=pa.Table.from_pylist(coverage,schema=schema)
        need(unique_bytes(root)+table.nbytes*2+(256<<10)<=limit,'PER_FILE_OUTPUT_RESERVATION_EXCEEDED')
        if writer is None:writer=pq.ParquetWriter(root/'coverage.parquet',schema,compression='zstd')
        writer.write_table(table,row_group_size=8192);coverage=[]
    try:
        require(source,content=False);identity_before=identity(path)
        db=sqlite_ro(WORK['index']);handle=pq.ParquetFile(path);opened=1
        columns=metadata_projection(handle,source)
        footer=[{'path':handle.schema.column(i).path,'physical_type':handle.schema.column(i).physical_type,
                 'logical_type':str(handle.schema.column(i).logical_type)} for i in range(len(handle.schema))]
        source_schema=str(handle.schema_arrow)
        for batch in handle.iter_batches(batch_size=cfg['batch_records'],columns=columns,use_threads=False):
            need(not WORK['stop'].is_set(),'PEER_FAILURE_BEFORE_NEXT_SOURCE_BATCH')
            max_rss=max(max_rss,rss(cfg['worker_rss_stop_bytes']))
            owners=lookup_batch(db,batch.column('record_id').to_pylist())
            rows=batch.to_pylist()
            # Prove nested projection never accidentally selected numeric/JSON payloads.
            if source['family'] not in ('D20','D3'):
                need('values' in batch.schema.names,'CELL_PROJECTION_NOT_RETURNED')
                for row in rows:
                    for cell in row.get('values') or []:
                        if cell is not None:need(set(cell)<={'registry_id','kind','shape'},'FORBIDDEN_CELL_PAYLOAD_IN_METADATA_PASS')
            for row in rows:
                physical+=1;owner=owners.get(row['record_id']);quantum=source['family'] not in ('D20','D3')
                classification=classify_owner(row,owner,quantum)
                if classification!='CANONICAL':
                    shadow[classification]+=1
                    shadow_status[compact_key(classification,row.get('calc_type',source['family']),row['status'],row.get('converged'),scf_state(row.get('scf_iterations')))]+=1
                    if len(examples)<cfg['examples_per_file']:examples.append({'classification':classification,**{k:row[k] for k in OWNER}})
                    continue
                task=row['calc_type'] if quantum else source['family']
                need(TASK_FAMILIES.get(task)==source['family'],'TASK_FAMILY_MAPPING_DIFFERS')
                role=owner['new_role'];need(role in ROLES,'UNKNOWN_FROZEN_ROLE')
                canonical+=1;role_counts[role]+=1;task_counts[task]+=1
                flags=report_flags(row) if quantum else 0
                converged=('COLUMN_NOT_APPLICABLE' if not quantum else 'NULL' if row.get('converged') is None else str(row['converged']))
                scf='COLUMN_NOT_APPLICABLE' if not quantum else scf_state(row.get('scf_iterations'))
                precision_state,pmeta,psha=precision_metadata(row.get('precision_by_field_json')) if quantum else ('NATIVE_TABLE_NO_PRINT_METADATA',{},None)
                status[compact_key(role,task,row['status'],row.get('source_status'),converged,scf,row.get('failure_code'),row.get('software_version_id'),bool(row.get('raw_audit_selected')),row.get('raw_output_locator_json') is not None)]+=1
                precision[compact_key(role,task,precision_state)]+=1
                if psha is not None:
                    # Exact signature counts are bounded; overflow remains explicit, not silently dropped.
                    pk=compact_key(task,psha)
                    if pk in precision_examples or len(precision_examples)<cfg['precision_variants_per_file']:
                        precision[pk]+=1
                        if pk not in precision_examples:precision_examples[pk]={'signature':psha,'declared_metadata':pmeta}
                    else:precision[compact_key(task,'VARIANT_LIMIT_OVERFLOW')]+=1
                if quantum:
                    ids=set();numeric=set(row.get('numeric_issues') or [])
                    for cell in row.get('values') or []:
                        cell=cell or {}
                        rid=cell.get('registry_id');kind=cell.get('kind')
                        if rid in ids:
                            flags|=64;duplicates[compact_key(role,task,rid,kind,declared_shape(cell,owner['total_atoms']))]+=1
                            continue
                        ids.add(rid)
                        entry=WORK['raw_registry'].get(rid)
                        if entry is None or entry['task']!=task:unknown[compact_key(task,rid)]+=1;flags|=128
                        shape=declared_shape(cell,owner['total_atoms'])
                        if shape=='INVALID_DECLARED_SHAPE':flags|=256
                        if kind not in range(11):flags|=512
                        source_path=entry['source_path'] if entry is not None else ''
                        leaf=source_path.rsplit('.',1)[-1]
                        declaration=('FULL_PATH_METADATA' if source_path in pmeta else 'LEAF_NAME_METADATA' if leaf in pmeta else 'NO_MATCHED_PRECISION_METADATA')
                        fields[compact_key(role,task,'r'+str(rid),row['status'],kind,shape,rid in numeric,declaration)]+=1
                else:
                    row['_atoms']=owner['total_atoms']
                    for key,state,nullness,shape,_ in native_observations(row,source['family']):
                        fields[compact_key(role,task,key,row['status'],state,shape,nullness,'NATIVE_PRINT_PRECISION_UNDECLARED')]+=1
                flags_counts[str(flags)]+=1
                coverage.append({'record_ordinal':owner['record_ordinal'],'task_code':TASKS[task],'role_code':ROLES[role],'review_flags':flags})
                if flags and len(examples)<cfg['examples_per_file']:
                    examples.append({'classification':'REVIEW_ONLY_NO_NEW_MASK','record_ordinal':owner['record_ordinal'],'task':task,'role':role,'flags':flags,**{k:row[k] for k in OWNER}})
                if len(coverage)>=8192:flush()
            rows=None;batch=None;owners=None
            max_rss=max(max_rss,rss(cfg['worker_rss_stop_bytes']))
        flush()
        if writer is not None:writer.close();writer=None
        handle.close();handle=None;closed=1
        need(identity(path)==identity_before,'SOURCE_CHANGED_DURING_FILE_SCAN')
        need(physical==source['rows'] and canonical==source['latest_rows'],'CLOSED_PHYSICAL_OR_LATEST_ROW_COUNT_DIFFERS')
        need(physical==canonical+sum(shadow.values()),'PHYSICAL_ROW_PARTITION_MASS')
        coverage_ref=ref(root/'coverage.parquet') if canonical else None
        report={'schema':'SOURCE_STATUS_FILE_REPORT_V1','status':'FILE_AUDITED',**BOUNDARY,
          'source':source,'file_id':file_id,'pid':os.getpid(),'physical_rows':physical,'canonical_rows':canonical,
          'noncanonical_physical_rows':dict(shadow),'noncanonical_status_counts':dict(shadow_status),'role_counts':dict(role_counts),'task_counts':dict(task_counts),
          'status_cross_counts':dict(status),'field_cell_counts':dict(fields),'precision_metadata_counts':dict(precision),
          'precision_metadata_examples':precision_examples,'unknown_registry_counts':dict(unknown),
          'duplicate_cell_counts':dict(duplicates),'review_flags_counts':dict(flags_counts),'review_flag_semantics':{'1':'SUCCESS_CONVERGENCE_NULL','2':'SUCCESS_SCF_NULL','4':'EXPLICIT_CONVERGED_FALSE','8':'SCF_NONPOSITIVE_OR_NONINTEGER','16':'SCOPE_SOURCE_STATUS_DIFFER','32':'SOURCE_NUMERIC_ISSUES','64':'DUPLICATE_REGISTRY_ID','128':'UNEXPECTED_REGISTRY_ID','256':'INVALID_DECLARED_SHAPE','512':'UNKNOWN_CELL_KIND'},
          'bounded_examples':examples,'coverage':coverage_ref,'projected_columns':columns,
          'arrow_schema_sha256':hashlib.sha256(source_schema.encode()).hexdigest(),'arrow_schema':source_schema,
          'parquet_physical_leaf_dtypes':footer,'storage_dtype_is_not_native_print_precision':True,
          'source_checksum_basis':'inherited closed full readback; size/owner/type + stable identity checked this run',
          'source_identity_before_and_after':identity_before,'io_handles_opened':opened,'io_handles_closed':closed,
          'max_simultaneous_source_handles':1,'max_rss_bytes':max_rss,'elapsed_seconds':time.monotonic()-start,
          'per_file_output_reservation_bytes':limit}
        raw=(json.dumps(report,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode()
        need(len(raw)<=3<<20,'BOUNDED_FILE_REPORT_LIMIT')
        save(root/'report.json',report);need(unique_bytes(root)<=limit,'FILE_OUTPUT_CAP_EXCEEDED')
        return {'file_id':file_id,'report':ref(root/'report.json'),'coverage':coverage_ref,'pid':os.getpid(),'physical_rows':physical,'canonical_rows':canonical,'output_bytes':unique_bytes(root)}
    except BaseException as exc:
        WORK['stop'].set()
        if writer is not None:writer.close();writer=None
        if handle is not None:handle.close();handle=None;closed+=1
        save(root/'failure.json',{'status':'FILE_FAILED_PARTIALS_PRESERVED','file_id':file_id,'source':source,'pid':os.getpid(),'error':str(exc),'type':type(exc).__name__,'physical_rows_seen':physical,'canonical_rows_seen':canonical,'max_rss_bytes':max_rss,'io_handles_opened':opened,'io_handles_closed':closed,'elapsed_seconds':time.monotonic()-start})
        raise
    finally:
        if handle is not None:handle.close()
        if db is not None:db.close()

def run(config_path,plan_path,shard_id,output,startup_proof):
    cfg=load(config_path);guard(startup_proof,config_path,cfg['scan_output_cap_bytes'])
    plan=load(plan_path);need(plan['schema']=='SOURCE_STATUS_FULL_PLAN_V1' and plan['config']==ref(config_path),'PLAN_CONFIG_MISMATCH')
    index=require(plan['canonical_index']);before=identity(index)
    for key in ('registry_v2','registry_v3'):require(cfg['metadata'][key])
    registry=load(cfg['metadata']['registry_v2']['path']);raw={int(x['registry_id']):x for x in registry['entries']}
    need(len(raw)==len(registry['entries']),'RAW_REGISTRY_DUPLICATE_ID')
    v3=load(cfg['metadata']['registry_v3']['path']);names=v3['D20_names']
    shard=next((x for x in plan['shards'] if x['shard_id']==shard_id),None);need(shard is not None,'UNKNOWN_SHARD')
    need(sum(x['latest_rows']*64+(4<<20) for x in shard['files'])+(4<<20)<=cfg['scan_output_cap_bytes'],'SHARD_FIXED_RESERVATIONS_EXCEED_CAP')
    root=new_root(output);start=time.monotonic();ctx=multiprocessing.get_context('spawn');stop=ctx.Event();barrier=ctx.Barrier(16)
    file_ids={r['path']:i for i,r in enumerate(sorted((r for s in plan['shards'] for r in s['files']),key=lambda x:x['path']))}
    items=[(file_ids[r['path']],r,str(root),i<16) for i,r in enumerate(shard['files'])]
    receipts=[]
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(cfg,str(index),raw,names,stop,barrier)) as pool:
            futures=[pool.submit(scan_file,item) for item in items]
            try:
                for future in concurrent.futures.as_completed(futures):receipts.append(future.result())
            except BaseException:
                stop.set()
                for f in futures:f.cancel()
                raise
        need(len(receipts)==len(items) and len({x['pid'] for x in receipts})==16,'ALL_FILES_AND_16_REAL_WORKERS_REQUIRED')
        need(identity(index)==before,'IMMUTABLE_CANONICAL_INDEX_CHANGED')
        need(unique_bytes(root)+(2<<20)<=cfg['scan_output_cap_bytes'],'SHARD_OUTPUT_CAP_EXCEEDED')
        report={'schema':'SOURCE_STATUS_SHARD_MANIFEST_V1','status':'SHARD_COMPLETE_REDUCTION_REQUIRED',**BOUNDARY,
          'config':ref(config_path),'prepared_plan':ref(plan_path),'shard_id':shard_id,'files':sorted(receipts,key=lambda x:x['file_id']),
          'distinct_worker_pids':sorted({x['pid'] for x in receipts}),'elapsed_seconds':time.monotonic()-start,
          'physical_rows':sum(r['physical_rows'] for r in receipts),'canonical_rows':sum(r['canonical_rows'] for r in receipts),
          'unique_inode_output_bytes_before_manifest':unique_bytes(root),'startup_proof':ref(startup_proof)}
        save(root/'manifest.json',report);return report
    except BaseException as exc:
        save(root/'failure.json',{'status':'SHARD_FAILED_NO_AUTORETRY_PARTIALS_PRESERVED','shard_id':shard_id,'error':str(exc),'type':type(exc).__name__,'closed_file_receipts':receipts})
        raise

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('config','plan','output','startup-proof'):p.add_argument('--'+key,required=True)
    p.add_argument('--shard-id',required=True,type=int);a=p.parse_args()
    result=run(a.config,a.plan,a.shard_id,a.output,a.startup_proof)
    print(json.dumps({'status':result['status'],'shard_id':result['shard_id'],'files':len(result['files'])}))
if __name__=='__main__':main()