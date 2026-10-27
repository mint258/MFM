"""One finite cache pass: legacy-input oracle, exact radix counts and TSQR."""
from __future__ import annotations
import collections,hashlib,json,os,sqlite3,struct,sys,time
from pathlib import Path
from .reader import CompatibilityGap,base_metadata,entries,finite_train,need,projected_decode
from workflows.data_v1_final.labels.streaming_v1.calibration import RadixCounts,TSQR,train_values
from workflows.data_v1_final.labels.streaming_v1.support import legacy,ParquetSink
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import load,require,ref,save,identity,unique_bytes,TASKS
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import stop_requested,soft_worker_rss
WORK={}


class PointerIndex:
    def __init__(self,path):
        self.db=sqlite3.connect(path);self.db.execute('PRAGMA journal_mode=DELETE');self.db.execute('PRAGMA synchronous=FULL')
        self.db.execute('PRAGMA cache_size=-2048');self.db.execute('PRAGMA max_page_count=8192')
        self.db.execute('CREATE TABLE pointers(ordinal INTEGER,task INTEGER,rg INTEGER,local_row INTEGER,PRIMARY KEY(ordinal,task)) WITHOUT ROWID')
    def add(self,ordinal,task,rg,row):
        try:self.db.execute('INSERT INTO pointers VALUES(?,?,?,?)',(ordinal,task,rg,row))
        except sqlite3.IntegrityError as exc:raise CompatibilityGap('DUPLICATE_CANONICAL_KEY_ANY_VALUE_HOLD') from exc
    def close(self):self.db.commit();self.db.close()


def initialize(cfg,root,barrier):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    common,masks=legacy(cfg['science']);fields=load(require(cfg['field_map_reference']))
    WORK.update(cfg=cfg,root=Path(root),barrier=barrier,common=common,masks=masks,fields=fields,
      bytask={t:[f for f in fields if f['task']==t] for t in TASKS})


def groups_with_kind(source,kind):
    """Use actual row-kind statistics, conservatively include unknown/mixed RGs."""
    index=source.schema_arrow.get_field_index('row_kind');out=[]
    for i in range(source.num_row_groups):
        stat=source.metadata.row_group(i).column(index).statistics
        if stat is None or not stat.has_min_max or stat.min<=kind<=stat.max:out.append(i)
    return out


def run_group(group):
    import pyarrow as pa
    import pyarrow.parquet as pq
    WORK['barrier'].wait(timeout=120);cfg=WORK['cfg'];out=WORK['root']/('group_'+str(group['group_index']).zfill(4));out.mkdir(mode=0o700)
    need(not stop_requested(),'SOFT_STOP_BEFORE_FIRST_CACHE_OWNER_BODY')
    started=time.monotonic();times={};source=None;stream=None;index=None;errors=[];recovery=[];opened=closed=0
    counters=collections.defaultdict(collections.Counter);roles=collections.Counter();task_counts=collections.Counter();base={};rows=0;rss=0
    phase=time.monotonic();owner_path=require(group['owner_index']);handle=pq.ParquetFile(owner_path)
    try:owners={r['record_id']:r for batch in handle.iter_batches(batch_size=512,use_threads=False) for r in batch.to_pylist()}
    finally:handle.close()
    need(len(owners)==group['expected_records'],'EXACT_OWNER_SCOPE')
    old=load(require(group['legacy_report']));legacy_hist_path=require(old['radix_histogram'])
    hist=RadixCounts(cfg['queries']);qr={str(f['field_id']):TSQR(cfg['element_basis']) for f in WORK['fields'] if f['element_reference_eligible']}
    hashes={str(f['field_id']):hashlib.sha256() for f in WORK['fields']};all_mass=hashlib.sha256()
    try:
        path=require(group['cache']);times['input_owner_hist_cache_whole_SHA_seconds']=time.monotonic()-phase
        before=identity(path);stream=path.open('rb');opened+=1;current=os.fstat(stream.fileno())
        need([current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns,current.st_ctime_ns]==before,'SAME_FD_ACCEPTED_CACHE_FRAME')
        source=pq.ParquetFile(stream,pre_buffer=False);index=PointerIndex(out/'cache_pointer_index.sqlite');phase=time.monotonic()
        base_rgs=groups_with_kind(source,'base');task_rgs=groups_with_kind(source,'task')
        for rg in base_rgs:
            if stop_requested():break
            within=0
            for batch in source.iter_batches(batch_size=16,row_groups=[rg],columns=['row_kind','record_ordinal','record_id','tree_json'],use_threads=False):
                for row in batch.to_pylist():
                    pos=within;within+=1
                    if row['row_kind']!='base':continue
                    p=base_metadata(row['tree_json']);z=p['original_geometry']['atomic_numbers'];owner=owners[row['record_id']]
                    need(row['record_ordinal']==owner['record_ordinal']==p['provenance']['owner']['record_ordinal'],'BASE_OWNER_IDENTITY')
                    need(row['record_id'] not in base and len(z)==owner['total_atoms'] and all(type(v) is int and 1<=v<=118 for v in z),'BASE_COUNT_TYPE_UNIQUENESS')
                    sha=hashlib.sha256(b''.join(struct.pack('<q',v) for v in z)).hexdigest();g=p['original_geometry']
                    need(sha==g['native_atom_order_sha256'] and g['source_payload_sha256']==owner['record_payload_sha256']
                      and g['geometry_status']=='ORIGINAL_PM7_GEOMETRY' and sum(v>1 for v in z)==owner['heavy_atoms'],'ORIGINAL_LEGACY_BASE_ORDER_PAYLOAD_AND_HEAVY_COUNT')
                    base[row['record_id']]=z;index.add(row['record_ordinal'],255,rg,pos)
        times['base_Z_order_metadata_projection_seconds']=time.monotonic()-phase;phase=time.monotonic()
        need(len(base)==len(owners),'BASE_METADATA_INCOMPLETE_NOT_FAKE_MISSING_MASK')
        for rg in task_rgs:
            if stop_requested():break
            within=0
            for batch in source.iter_batches(batch_size=16,row_groups=[rg],columns=['row_kind','record_ordinal','task_code','record_id','tree_json','values_float64'],use_threads=False):
                for row in batch.to_pylist():
                    pos=within;within+=1
                    if row['row_kind']!='task':continue
                    need(len(row['tree_json'].encode())+8*len(row['values_float64'])<=cfg['row_serialized_cap_bytes'],'UNCHANGED64MIB_ROW_BOUND')
                    payload=projected_decode(row['tree_json'],row['values_float64']);owner=owners[row['record_id']];task=payload['task']
                    need(task in TASKS and row['task_code']==TASKS[task] and row['record_ordinal']==owner['record_ordinal'],'CANONICAL_CACHE_TASK_AND_OWNER')
                    need(all(payload['provenance']['owner'][k]==owner[k] for k in ('record_id','molecule_id','attempt_id','job_id','task_id','lane','total_atoms','new_role')),'EXACT_OLD_OWNER_TUPLE')
                    index.add(row['record_ordinal'],row['task_code'],rg,pos);rows+=1;task_counts[task]+=1;role=owner['new_role'];roles[role]+=1
                    try:items=entries(payload,WORK['bytask'][task],WORK['common'],WORK['masks'],row['task_code'])
                    except (CompatibilityGap,ValueError,TypeError,KeyError,OverflowError) as exc:
                        errors.append({'record_ordinal':row['record_ordinal'],'task':task,'error':type(exc).__name__+':'+str(exc)})
                        if len(recovery)<64:recovery.append({'record_id':owner['record_id'],'molecule_id':owner['molecule_id'],
                          'source_reference':payload['provenance']['source_reference'],'row_group':payload['provenance']['row_group'],
                          'physical_row_ordinal':payload['provenance']['physical_row_ordinal'],'error':str(exc),
                          'requested_read':'ONLY_THIS_CANONICAL_SOURCE_ROW_AFTER_SEPARATE_ROOT_REVIEW','automatic_raw_read':False})
                        continue
                    for item in items:
                        fid=str(item['field_id']);c=counters[fid];valid=finite_train(item,role,train_values)
                        c['records']+=1;c['source_valid_records']+=bool(any(item['source_value_mask']));c['valid_records']+=bool(any(item['value_mask']))
                        c['newly_masked_records']+=any(a and not b for a,b in zip(item['source_value_mask'],item['value_mask']))
                        c['TRAIN_valid_leaves']+=len(valid)
                        header=struct.pack('<QBHI',row['record_ordinal'],row['task_code'],item['field_id'],len(item['value_mask']))+role.encode()+bytes(item['value_mask'])
                        hashes[fid].update(header);all_mass.update(header)
                        for value in valid:raw=struct.pack('<d',value);hashes[fid].update(raw);all_mass.update(raw)
                        hist.add(item['field_id'],valid)
                        if fid in qr and valid:need(len(valid)==1,'LEGACY_REFERENCE_MOLECULE_SCALAR');qr[fid].add(base[row['record_id']],valid[0])
                    rss=max(rss,soft_worker_rss(cfg['worker_rss_stop_bytes']))
                if stop_requested():break
        times['cache_numeric_decode_legacy_mask_parity_hist_TSQR_seconds']=time.monotonic()-phase;phase=time.monotonic()
        states={k:v.state() for k,v in qr.items()};newhist=hist.rows();oldhist=pq.ParquetFile(legacy_hist_path)
        try:oldrows=[r for b in oldhist.iter_batches(batch_size=4096,use_threads=False) for r in b.to_pylist()]
        finally:oldhist.close()
        hkey=lambda r:(r['field_id'],r['node_id'],r['prefix_bits'],int(r['prefix']))
        histogram_equal=(sorted(newhist,key=hkey)==sorted(oldrows,key=hkey)) if cfg['compare_legacy_profile'] else None
        TSQR_equal=(states==old['energy_TSQR']) if cfg['compare_legacy_profile'] else None
        times['original_profile_hist_and_TSQR_comparison_seconds']=time.monotonic()-phase
        current=os.fstat(stream.fileno());need([current.st_dev,current.st_ino,current.st_size,current.st_mtime_ns,current.st_ctime_ns]==before==identity(path),'ACCEPTED_CACHE_CHANGED_DURING_PROFILE')
        source.close();source=None;stream.close();stream=None;closed+=1;index.close();index=None
        schema=pa.schema([('field_id',pa.uint16()),('node_id',pa.string()),('prefix_bits',pa.uint8()),('prefix',pa.uint64()),('n',pa.uint64())])
        sink=ParquetSink(schema,cfg['serialized_buffer_cap_bytes']);sink.add(newhist)
        histogram=sink.close(out/'TRAIN_radix_counts.parquet',out,cfg['worker_output_cap_bytes'])
        complete=all(task_counts[t]==len(owners) for t in TASKS) and len(counters)==146 and all(v['records']==len(owners) for v in counters.values())
        accepted=complete and not errors and not stop_requested() and histogram_equal is not False and TSQR_equal is not False
        need(unique_bytes(out)+(2<<20)<=cfg['worker_output_cap_bytes'],'WORKER_ALL_OUTPUT_AND_METADATA_CAP')
        report={'schema':'TYPED_CACHE_SOURCE_TRAIN_PROFILE_GROUP_V1','status':'COMPATIBLE_CLOSED' if accepted else 'COMPATIBILITY_OR_RESOURCE_HOLD',
          'group_index':group['group_index'],'pid':os.getpid(),'records':len(owners),'task_rows':rows,'task_counts':dict(task_counts),'role_task_counts':dict(roles),
          'field_counts':{k:dict(v) for k,v in counters.items()},'field_input_sha256':{k:v.hexdigest() for k,v in hashes.items()},
          'masked_source_TRAIN_input_sha256':all_mass.hexdigest(),'radix_histogram':histogram,'energy_TSQR':states,
          'legacy_profile_histogram_equal':histogram_equal,'legacy_profile_TSQR_equal':TSQR_equal,'errors':errors[:64],
          'errors_total':len(errors),'exact_row_recovery_candidates':recovery,'recovery_candidates_truncated':len(errors)>len(recovery),
          'cache_pointer_index':ref(out/'cache_pointer_index.sqlite'),'cache':group['cache'],'cache_Parquet_opens':opened,'cache_Parquet_closes':closed,
          'max_simultaneous_cache_Parquet_handles':1,'cache_row_groups':len(set(base_rgs)|set(task_rgs)),
          'cache_current_frame_before_after':before,
          'actual_cache_input_whole_SHA_bytes':group['cache']['bytes'],'cache_base_RG_count':len(base_rgs),'cache_task_RG_count':len(task_rgs),
          'cache_whole_SHA_read_passes':1,'owner_index_whole_SHA_bytes':group['owner_index']['bytes'],
          'legacy_histogram_whole_SHA_bytes':old['radix_histogram']['bytes'],'actual_physical_storage_read_bytes':'NOT_MEASURED',
          'phase_seconds':times,'elapsed_seconds':time.monotonic()-started,'maxrss_bytes':rss,
          'original_source_Parquet_or_LMDB_opened':False,'cache_full_science_signature_recomputed':False,
          'raw_JSON_text_recovered':False,'candidate_masks_frozen':False,'final_Common_D4':False,'automatic_retry':False}
        import numpy as np
        report['runtime_versions']={'python':sys.version.split()[0],'numpy':np.__version__,'pyarrow':pa.__version__,
          'longdouble_mantissa_bits':int(np.finfo(np.longdouble).nmant)}
        rp=save(out/'report.json',report);return rp
    except BaseException as exc:
        save(out/'failure.json',{'error':type(exc).__name__+':'+str(exc),'partials_preserved':True,'automatic_retry':False});raise
    finally:
        if source is not None:source.close()
        if stream is not None:stream.close()
        if index is not None:index.close()
