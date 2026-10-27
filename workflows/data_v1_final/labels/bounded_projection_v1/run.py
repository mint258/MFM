"""Finite physical source ranges to closed typed parts; no full release or fit."""
from __future__ import annotations
import argparse,collections,concurrent.futures as cf,hashlib,io,json,multiprocessing as mp,os,sqlite3,stat,time,unittest
from pathlib import Path
from .parts import Ledger,TypedPart,TicketStop,publish_bytes,pin,slices
from .records import project,parity_signature
from .materialize import SCOPE,resolve
from workflows.data_v1_final.labels.footer_inventory_v1.footer import footer_only
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.run import BASE_COLUMNS,fixtures as inherited_fixtures
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import verify_cache_row
from workflows.data_v1_final.labels.payload_audit_v1.run import source_columns
from workflows.data_v1_final.labels.streaming_v1.support import legacy
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import (
 TASKS,TASK_FAMILIES,need,load,require,small_ref,new_root,save,unique_bytes,sqlite_ro,lookup_batch,classify_owner)
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import (
 start_observer,stop_requested,soft_worker_rss,mark_stop)
WORK={}


def frame(s):return {'device':s.st_dev,'inode':s.st_ino,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns,'uid':s.st_uid}


def guard(cfg,path,proof_path):
    from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.runtime import require_startup
    request=load(proof_path)['request'];bp=request['producer_resource_binding_reference'];binding=load(require(bp))
    need(cfg['schema']=='BOUNDED_LABEL_PROJECTION_CONFIG_V1' and cfg['full_population_authorized'] is False
      and cfg['norm_fit_allowed'] is False and cfg['logical_statistics_partition_reference'] is None,'FINITE_CACHE_ONLY_NO_FULL_OR_NORM')
    need(binding['schema']=='BOUNDED_LABEL_PROJECTION_RESOURCE_BINDING_V1' and binding['scientific_config_reference']==small_ref(path)
      and binding['scope_key']==SCOPE and binding['scope_parameters']==cfg['scope_parameters']
      and binding['resource_authority_reference']==request['queue_authority_reference'],'EXACT_NEW_BATCH_BINDING')
    need(request['pilot'] is True and request['cpus']==16 and request['wall_seconds']<=7200
      and request['estimated_peak_output_bytes']>=cfg['whole_output_cap_bytes'],'EXACT_FINITE_PROFILE_RESOURCES')
    need(cfg['row_serialized_cap_bytes']==64<<20 and cfg['worker_rss_stop_bytes']==3<<30
      and 8<<30<=cfg['whole_output_cap_bytes']<=32<<30,'UNCHANGED_ROW_WORKER_AND_FINITE_OUTPUT_CAPS')
    need(cfg['review_calibration_reference'] is None and cfg['calibration_state']=='PENDING_MATCHED_FULL_TRAIN_NO_512_SCALE_REUSE','NO_UNMATCHED_512_SCALE_ON_BROADER_SOURCE')
    need(cfg['scope_parameters']['witness_policy']=='ACTUAL_512_DETERMINISTIC_TASK_FIELD_AND_OBSERVED_CODEC_V1'
      and cfg['scope_parameters']['max_witness_keys_and_extra_RGs']==512,'EXACT_BOUNDED_CPU_WITNESS_POLICY')
    proof=require_startup(proof_path,expected_kind='analysis',expected_scope_key=SCOPE,
      expected_scope_parameters=cfg['scope_parameters'],required_references=[small_ref(path),bp,*cfg['small_references']])
    refs={r['path']:r for r in request['source_references']}
    for r in cfg['source_references']:need(refs.get(r['path'])==r,'CURRENT_TRANSITIVE_SOURCE_PIN_REQUIRED');require(r)
    start_observer(proof,binding);return proof


def fixtures(root,proof_path):
    old=inherited_fixtures(root,proof_path)
    from .test_bounded import BoundedBoundaries
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(BoundedBoundaries);need(suite.countTestCases()==4,'EXACT_FOUR_NEW_BOUNDARIES')
    text=io.StringIO();result=unittest.TextTestRunner(stream=text,verbosity=2).run(suite)
    passed=(result.testsRun==4 and result.wasSuccessful() and not result.skipped and not result.expectedFailures and not result.unexpectedSuccesses)
    r=save(root/'bounded_fixture_gate.json',{'status':'PASS' if passed else 'FAIL_NO_BODY','tests_run':result.testsRun,
      'transcript':text.getvalue(),'original_six_plus_three':old,'real_gzip_Parquet_SQLite_cache_body_opened':False})
    print(text.getvalue(),flush=True);need(passed,'ALL_BOUNDARIES_BEFORE_REAL_BODIES');return r


def discover_witnesses(cfg):
    """Actual produced512 cache only; deterministic witnesses before source IO."""
    import pyarrow.parquet as pq
    footer=load(require(cfg['footer_manifest_reference']));book=load(require(footer['source_inventory_reference']))
    bypath={r['path']:r for r in book['files']};fields=load(require(cfg['science']['sources']['registry']))['fields']
    enabled={f['field_key']:f for f in fields if f['status']=='enabled'};chosen={};rows=0;kinds=set();widths=set()
    for reference in sorted(cfg['parity_cache_references'],key=lambda r:r['path']):
        f=pq.ParquetFile(require(reference))
        try:
            for batch in f.iter_batches(batch_size=16,use_threads=False):
                for row in batch.to_pylist():
                    rows+=1;payload=verify_cache_row(row);provenance=payload['provenance'];old=provenance['source_reference'];source=bypath[old['path']]
                    need(all(old[k]==source[k] for k in ('path','bytes','sha256')),'WITNESS_SOURCE_MUST_MATCH_ACTUAL_FOOTER_BOOK')
                    categories={'task:'+str(row['task_code']),'family:'+source['family']}
                    for cell in payload.get('cells',[]):
                        if type(cell.get('kind')) is int:kinds.add(cell['kind']);categories.add('CELL_KIND:'+str(cell['kind']))
                        if cell.get('native_family'):categories.add('NATIVE:'+cell['native_family'])
                    for key,n in payload.get('raw_counts',{}).items():
                        if n and key.startswith('kind:'):
                            text=key[5:];kind=int(text) if text.isdecimal() else text
                            kinds.add(kind);categories.add('RAW_KIND_COUNT:'+text)
                    for width,n in payload['source_float_bits']['observed_float_width_counts'].items():
                        if n:widths.add(width);categories.add('STORAGE_FLOAT_WIDTH:'+width)
                    for component in payload.get('component_map',[]):
                        key=component['field_key']
                        if key in enabled:
                            categories.add('FIELD:'+key)
                            if component['ordered_leaf_paths']:categories.add('LAYOUT:'+enabled[key]['level']+':'+enabled[key]['source_path'].rsplit('.',1)[-1])
                    rank=(source['path'],provenance['physical_row_ordinal'],row['record_ordinal'],row['task_code'])
                    winners=[k for k in categories if k not in chosen or rank<chosen[k][0]]
                    if winners:
                        info={'file_id':source['file_id'],'record_ordinal':row['record_ordinal'],'task_code':row['task_code'],
                          'family':source['family'],'row_group':provenance['row_group'],'physical_row_ordinal':provenance['physical_row_ordinal'],
                          'expected_science_signature':parity_signature(payload,row['row_kind'])}
                        for key in winners:chosen[key]=(rank,info)
        finally:f.close()
    need(rows==4251*15 and len(chosen)<=512,'ACTUAL_512_ROW_MASS_AND_BOUNDED_WITNESS_CATEGORIES')
    need({'task:'+str(t) for t in [*TASKS.values(),255]}<=set(chosen),'ALL_FOURTEEN_TASKS_AND_BASE_ACTUAL_WITNESSES')
    need({'FIELD:'+key for key in enabled}<=set(chosen),'ALL_ENABLED_STORED_REPRESENTATIONS_HAVE_WITNESSES')
    witnesses={}
    for category,(_,info) in sorted(chosen.items()):
        key=(info['record_ordinal'],info['task_code'])
        if key not in witnesses:witnesses[key]=dict(info,encoding_keys=[])
        witnesses[key]['encoding_keys'].append(category)
    return {'schema':'BOUNDED_LABEL_ACTUAL512_WITNESS_DISCOVERY_V1','policy':cfg['scope_parameters']['witness_policy'],
      'actual_old_cache_rows':rows,'observed_encoding_keys':sorted(chosen),'witnesses':[witnesses[k] for k in sorted(witnesses)],
      'observed_source_CELL_kinds':sorted(kinds,key=str),'observed_storage_float_widths':sorted(widths,key=int),
      'unobserved_supported_CELL_kinds_not_claimed':[i for i in range(11) if i not in kinds],
      'field_witness_means':'STORED_REPRESENTATION_INCLUDING_NULL_NOT_NUMERIC_VALIDITY',
      'original_label_Parquet_opened':False,'native_precision_or_actual_coordinate_frame_proved':False}


def initialize(cfg,root,barrier):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    common,masks=legacy(cfg['science']);fields=load(require(cfg['science']['sources']['registry']))['fields']
    enabled=sorted((f for f in fields if f['status']=='enabled'),key=lambda f:f['field_key']);ids={f['field_key']:i for i,f in enumerate(enabled)}
    need(len(fields)==264 and len(enabled)==146,'FROZEN_264_146_MAPPING')
    fields=[dict(f,field_id=ids.get(f['field_key'])) for f in fields]
    WORK.update(cfg=cfg,root=Path(root),barrier=barrier,common=common,masks=masks,
      task_fields={t:[f for f in fields if f['task']==t] for t in TASKS},calibration={})


class Window:
    def __init__(self,item,start,ledger,source_check):
        self.item=item;self.lo=start;self.hi=start;self.ledger=ledger;self.check=source_check;self.parts={}
        self.stats=collections.defaultdict(collections.Counter);self.observed=collections.defaultdict(collections.Counter);self.classes=collections.Counter()
        cfg=WORK['cfg'];family=item['source']['family'];tasks=[t for t,f in TASK_FAMILIES.items() if f==family] if family!='base_geometry' else [255]
        self.ticket=ledger.reserve(item['range_id'],start,len(tasks)*cfg['typed_part_cap_bytes']+(256<<10),len(tasks)+1)

    def add(self,pos,classification,row=None,stats=None,observed=None):
        need(pos==self.hi,'PHYSICAL_WINDOW_NO_GAP_OR_OVERLAP');self.hi+=1;self.classes[classification]+=1
        if row is not None:
            key=(row['row_kind'],row['task_code'])
            if key not in self.parts:self.parts[key]=TypedPart(*key,WORK['cfg']['typed_part_cap_bytes'],WORK['cfg']['row_serialized_cap_bytes'])
            self.parts[key].add(row)
            for k,v in stats.items():self.stats[k].update(v)
            for k,v in observed.items():self.observed[k].update(v)

    def full(self):
        return self.hi-self.lo>=WORK['cfg']['max_physical_window_rows'] or sum(p.approximate_bytes() for p in self.parts.values())>=WORK['cfg']['window_soft_target_bytes']

    def close(self):
        need(self.hi>self.lo,'NONEMPTY_PHYSICAL_WINDOW');root=WORK['root']/'parts';closed=[]
        try:
            for (kind,task),part in sorted(self.parts.items()):
                closed.append(part.finish(root/('part_'+self.ticket+'_'+kind+'_'+str(task)+'.parquet')))
            self.check()
            body={'schema':'BOUNDED_TYPED_PHYSICAL_WINDOW_V1','ticket':self.ticket,'range_id':self.item['range_id'],
              'file_id':self.item['file_id'],'source_reference':self.item['source'],'physical_row_lo':self.lo,'physical_row_hi':self.hi,
              'physical_classifications':dict(self.classes),'parts':closed,'field_stats':{k:dict(v) for k,v in self.stats.items()},
              'declared_field_observations':{k:dict(v) for k,v in self.observed.items()},'all_part_reopen_bits_verified':True,
              'candidate_masks_frozen':False,'calibration_state':WORK['cfg']['calibration_state']}
            raw=(json.dumps(body,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();need(len(raw)<=256<<10,'WINDOW_RECEIPT_RESERVATION')
            receipt=publish_bytes(root/('window_'+self.ticket+'.json'),raw)
            self.ledger.commit(self.ticket,self.hi,receipt,sum(r['reference']['bytes'] for r in closed)+receipt['bytes'],len(closed)+1)
            return receipt
        except BaseException:self.ledger.abandon(self.ticket);raise


def worker(shard):
    import pyarrow.parquet as pq
    WORK['barrier'].wait(timeout=120);cfg=WORK['cfg'];root=WORK['root'];ledger=Ledger(root/'state.sqlite')
    index=sqlite_ro(cfg['canonical_index']['path']);errors=[];done=[];pending=[];opened=closed=0;decoded=prefix=suffix=0;alias_footer_bytes=0;maxrss=0;start=time.monotonic()
    def process_segment(item,handle,source_check,storage,original,alias):
        nonlocal decoded,prefix,suffix,maxrss
        source=item['source'];window=None;iterator=batch=selected=row=owners=None
        cursor,stop=ledger.cursor(item['range_id']);actual_cursor=cursor
        try:
            for group in slices(item['groups'],cursor,stop):
                if stop_requested():break
                need(handle.metadata.row_group(group['row_group']).num_rows==group['physical_row_hi']-group['physical_row_lo'],'ACTUAL_RG_ROWS_DIFFER')
                iterator=iter(handle.iter_batches(batch_size=cfg['source_read_batch_records'],row_groups=[group['row_group']],
                  columns=BASE_COLUMNS if source['family']=='base_geometry' else source_columns(source['family']),use_threads=False))
                position=group['physical_row_lo']
                while position<group['selected_hi']:
                    maxrss=max(maxrss,soft_worker_rss(cfg['worker_rss_stop_bytes']))
                    if stop_requested():break
                    if window is None:window=Window(item,actual_cursor,ledger,source_check)
                    try:batch=next(iterator)
                    except StopIteration:break
                    batch_lo=position;position+=batch.num_rows;decoded+=batch.num_rows
                    a,b=max(batch_lo,group['selected_lo']),min(position,group['selected_hi'])
                    prefix+=max(0,min(position,group['selected_lo'])-batch_lo);suffix+=max(0,position-group['selected_hi'])
                    if a>=b:continue
                    selected=batch.slice(a-batch_lo,b-a);owners=lookup_batch(index,selected.column('record_id').to_pylist())
                    for i,row in enumerate(selected.to_pylist()):
                        if window is None:window=Window(item,actual_cursor,ledger,source_check)
                        physical=a+i;owner=owners.get(row['record_id']);quantum=source['family'] not in ('base_geometry','D20','D3')
                        classification=classify_owner(row,owner,quantum);cached=stats=observed=None
                        if classification=='CANONICAL':
                            need(owner['job_id']==source['source_job_id'],'CANONICAL_JOB_DIFFERS_FROM_SOURCE')
                            provenance={'source_reference':source,'source_verification':'INHERITED_PRODUCER_SHA_CURRENT_FOOTER_FRAME_MATCHED_STABLE_FSTAT',
                              'row_group':group['row_group'],'row_within_group':physical-group['physical_row_lo'],'physical_row_ordinal':physical,
                              'owner':owner,'original_storage_schema':storage,'actual_frame_origin':'PENDING_CONTROLLED_READBACK',
                              'source_role_only_not_final_common':True,'review_calibration':cfg['calibration_state'],
                              'current_storage_frame':original,'cross_node_device_alias_footer_rehashed':alias}
                            cached,stats,observed=project(row,selected,i,owner,source,provenance,WORK)
                        window.add(physical,classification,cached,stats,observed);actual_cursor=physical+1
                        if window.full():window.close();window=None
                    selected=batch=owners=row=None
                if position<group['selected_hi'] and not stop_requested():raise ValueError('SOURCE_RG_ENDED_BEFORE_SELECTED_RANGE')
                if stop_requested():break
            if window is not None:
                if window.hi>window.lo:window.close()
                else:ledger.abandon(window.ticket)
                window=None
            source_check()
        except BaseException:
            if window is not None:ledger.abandon(window.ticket)
            raise
        finally:iterator=batch=selected=row=owners=None
    try:
        for file_work in shard['sources']:
            segments=sorted(file_work['ranges'],key=lambda r:r['physical_row_lo']);item=segments[0]
            if stop_requested():pending.extend(r['range_id'] for r in segments);continue
            source=item['source'];path=Path(source['path']);handle=stream=None
            try:
                st=path.lstat();original=frame(st);expected=item['footer_observed_source_frame']
                need(stat.S_ISREG(st.st_mode) and st.st_uid==os.getuid()
                  and all(original[k]==expected[k] for k in expected if k!='device'),'ACTUAL_SOURCE_FRAME_MUST_MATCH_CLOSED_FOOTER')
                stream=path.open('rb');opened+=1;need(frame(os.fstat(stream.fileno()))==original,'OPENED_SOURCE_PATH_FRAME_DIFFERS')
                alias=original['device']!=expected['device']
                if alias:
                    current=footer_only(stream,st.st_size);alias_footer_bytes+=current['actual_source_metadata_bytes_read']
                    need(current['actual_footer_sha256']==item['expected_footer_sha256'],'CROSS_NODE_DEVICE_ALIAS_FOOTER_SHA_DIFFERS')
                    del current
                stream.seek(0)
                def source_check():need(frame(path.lstat())==frame(os.fstat(stream.fileno()))==original,'SOURCE_CHANGED_DURING_RANGE')
                handle=pq.ParquetFile(stream,pre_buffer=False)
                need(handle.metadata.num_rows==source['rows'] and handle.num_row_groups==item['file_row_groups'],'CURRENT_SOURCE_PHYSICAL_DIRECTORY_DIFFERS')
                storage=str(handle.schema_arrow)
                for item in segments:
                    if stop_requested():break
                    process_segment(item,handle,source_check,storage,original,alias)
                source_check()
            except TicketStop as exc:mark_stop(str(exc),{'range_id':item['range_id'],'pid':os.getpid()})
            except BaseException as exc:
                errors.append({'range_id':item['range_id'],'source_reference':source,'error':type(exc).__name__+':'+str(exc),'status':'PENDING_NOT_LABEL_MASK','automatic_retry':False})
                mark_stop('BOUNDED_SOURCE_RANGE_PENDING',{'range_id':item['range_id'],'error':str(exc)})
            finally:
                if handle is not None:handle.close();handle=None
                if stream is not None:stream.close();stream=None;closed+=1
                for segment in segments:
                    position,end=ledger.cursor(segment['range_id']);(done if position==end else pending).append(segment['range_id'])
        report={'schema':'BOUNDED_LABEL_RANGE_WORKER_V1','pid':os.getpid(),'done_ranges':done,'pending_ranges':pending,'errors':errors,
          'opens':opened,'closes':closed,'max_simultaneous_Parquet_handles':1,'decoded_physical_rows_including_boundary_prefix':decoded,
          'boundary_prefix_rows_redecoded':prefix,'boundary_suffix_rows_decoded':suffix,'actual_storage_read_bytes':'NOT_MEASURED_NOT_PRODUCER_REF_SUM',
          'cross_node_device_alias_extra_footer_bytes_read':alias_footer_bytes,'source_Arrow_pre_buffer':False,
          'max_worker_rss_bytes':maxrss,'elapsed_seconds':time.monotonic()-start}
        path=root/('worker_'+str(shard['shard_id']).zfill(2)+'.json');save(path,report);return pin(path)
    finally:index.close();ledger.close()


def coverage_and_parity(root,cfg,snapshot,previous,witness):
    import pyarrow.parquet as pq
    db=sqlite3.connect(root/'coverage.sqlite',uri=True);db.execute('PRAGMA cache_size=-8192');db.execute('PRAGMA max_page_count=196608')
    # Rebuildable audit index, not the authoritative cursor ledger. Avoid a
    # second768MiB rollback journal outside the fixed1GiB admin envelope.
    db.execute('PRAGMA journal_mode=OFF');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE coverage(ordinal INTEGER,task INTEGER,science_sha TEXT,PRIMARY KEY(ordinal,task)) WITHOUT ROWID')
    if previous:
        old=require(previous['coverage']['reference']);uri=Path(old).as_uri()+'?mode=ro&immutable=1'
        db.execute('ATTACH DATABASE ? AS old',(uri,));db.execute('INSERT INTO coverage SELECT * FROM old.coverage');db.commit();db.execute('DETACH DATABASE old')
    duplicate=0;examples=[];stats=collections.defaultdict(collections.Counter);observed=collections.defaultdict(collections.Counter);classes=collections.defaultdict(collections.Counter)
    kind_counts=collections.Counter();width_counts=collections.Counter()
    if previous:
        for k,v in previous['field_stats'].items():stats[k].update(v)
        for k,v in previous['declared_field_observations'].items():observed[k].update(v)
        for k,v in previous['physical_classifications_by_kind'].items():classes[k].update(v)
        kind_counts.update(previous['parity']['current_source_CELL_kind_counts']);width_counts.update(previous['parity']['current_source_float_width_counts'])
    for window in snapshot['closed_windows']:
        body=load(require(window['receipt']));source=body['source_reference'];classes[source['source_kind']].update(body['physical_classifications'])
        for k,v in body['field_stats'].items():stats[k].update(v)
        for k,v in body['declared_field_observations'].items():observed[k].update(v)
        for part in body['parts']:
            f=pq.ParquetFile(require(part['reference']))
            try:
                for batch in f.iter_batches(batch_size=16,use_threads=False):
                    for row in batch.to_pylist():
                        payload=verify_cache_row(row);sig=parity_signature(payload,row['row_kind'])
                        for key,n in payload.get('raw_counts',{}).items():
                            if key.startswith('kind:'):kind_counts[key[5:]]+=n
                        width_counts.update(payload['source_float_bits']['observed_float_width_counts'])
                        try:db.execute('INSERT INTO coverage VALUES(?,?,?)',(row['record_ordinal'],row['task_code'],sig))
                        except sqlite3.IntegrityError:
                            duplicate+=1
                            if len(examples)<20:examples.append({'record_ordinal':row['record_ordinal'],'task_code':row['task_code'],'part':part['reference']})
                db.commit()
            finally:f.close()
    matched=0;mismatch_count=0;mismatches=[];old_rows=0;bytask=collections.Counter();byfamily=collections.Counter();task_names={v:k for k,v in TASKS.items()}
    for old_cache in cfg['parity_cache_references']:
        f=pq.ParquetFile(require(old_cache))
        try:
            for batch in f.iter_batches(batch_size=16,use_threads=False):
                for row in batch.to_pylist():
                    old_rows+=1;expected=db.execute('SELECT science_sha FROM coverage WHERE ordinal=? AND task=?',(row['record_ordinal'],row['task_code'])).fetchone()
                    if expected is not None:
                        matched+=1;bytask[str(row['task_code'])]+=1
                        byfamily[TASK_FAMILIES.get(task_names.get(row['task_code']),'base_geometry')]+=1
                        if expected[0]!=parity_signature(verify_cache_row(row),row['row_kind']):
                            mismatch_count+=1
                            if len(mismatches)<20:mismatches.append({'record_ordinal':row['record_ordinal'],'task_code':row['task_code']})
        finally:f.close()
    missing_witness=[];wrong_witness=[];verified_encoding=set()
    for row in witness['witnesses']:
        actual=db.execute('SELECT science_sha FROM coverage WHERE ordinal=? AND task=?',(row['record_ordinal'],row['task_code'])).fetchone()
        if actual is None:missing_witness.append({'record_ordinal':row['record_ordinal'],'task_code':row['task_code']})
        elif actual[0]!=row['expected_science_signature']:wrong_witness.append({'record_ordinal':row['record_ordinal'],'task_code':row['task_code']})
        else:verified_encoding.update(row['encoding_keys'])
    counts={str(t):n for t,n in db.execute('SELECT task,count(*) FROM coverage GROUP BY task')};digest=hashlib.sha256()
    for ordinal,task,sig in db.execute('SELECT * FROM coverage ORDER BY ordinal,task'):digest.update((str(ordinal)+'|'+str(task)+'|'+sig+'\n').encode())
    need(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'CLOSED_COVERAGE_SQLITE_INTEGRITY')
    db.commit();db.close()
    fd=os.open(root/'coverage.sqlite',os.O_RDONLY)
    try:os.fsync(fd)
    finally:os.close(fd)
    return {'reference':pin(root/'coverage.sqlite'),'unique_keys_by_task':counts,'duplicate_keys':duplicate,'duplicate_examples':examples,
      'logical_key_science_signature':digest.hexdigest(),'logical_signature_acceptable_only_if_duplicates_zero':duplicate==0,
      'full_14task_and_base_conserved':False}, {'matched_rows':matched,'matched_rows_by_task':dict(bytask),'matched_rows_by_family':dict(byfamily),
      'task_code_names':{**{str(k):v for k,v in task_names.items()},'255':'base_geometry'},'old_cache_rows_read':old_rows,
      'mismatch_count':mismatch_count,'mismatches':mismatches,'mismatch_examples_may_be_truncated':mismatch_count>len(mismatches),
      'required_witness_rows':len(witness['witnesses']),'missing_witness_rows':missing_witness,'mismatched_witness_rows':wrong_witness,
      'verified_encoding_keys':sorted(verified_encoding),'missing_encoding_keys':sorted(set(witness['observed_encoding_keys'])-verified_encoding),
      'source_new_mask_and_source_review_axis':'PASS' if matched and not(mismatch_count or missing_witness or wrong_witness) else 'HOLD',
      'axis_scope':'ACTUAL_OVERLAPPING_KEYS_ONLY_NOT_FULL_CURRENT_BATCH_OR_POPULATION',
      'unmatched_512_statistical_review_axis':'PENDING_MATCHED_FULL_TRAIN_CALIBRATION',
      'current_source_CELL_kind_counts':dict(kind_counts),'current_source_float_width_counts':dict(width_counts),
      'unwitnessed_current_CELL_kinds':sorted(set(kind_counts)-{str(k) for k in witness['observed_source_CELL_kinds']}),
      'unwitnessed_current_float_widths':sorted({k for k,n in width_counts.items() if n}-set(witness['observed_storage_float_widths'])),
      'comparison':'RAW_TYPED_VALUES_ORDER_KEYS_BITS_AND_SOURCE_NEW_MASKS;PROVENANCE_AND_UNMATCHED_STATISTICAL_REVIEWS_EXCLUDED'},stats,observed,classes


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('config','startup-proof','output'):p.add_argument('--'+k,required=True)
    a=p.parse_args();cfg=load(a.config);proof=guard(cfg,a.config,a.startup_proof);root=new_root(a.output);start=time.monotonic()
    try:
        gate=fixtures(root,a.startup_proof);require(cfg['canonical_index'])
        previous=load(require(cfg['previous_manifest_reference'])) if cfg['previous_manifest_reference'] else None
        witness=discover_witnesses(cfg);witness_ref=save(root/'witness_discovery.json',witness)
        actual=resolve(cfg,witness);actual['witness_discovery_reference']=witness_ref
        need(len(json.dumps(actual,sort_keys=True,indent=2).encode())<=2<<20,'ACTUAL_RANGE_METADATA_CAP_BEFORE_SOURCE_READ')
        plan=save(root/'actual_range_plan.json',actual);ranges=actual['ranges'];(root/'parts').mkdir(mode=0o700)
        byfile={}
        for r in ranges:byfile.setdefault(r['file_id'],{'file_id':r['file_id'],'ranges':[]})['ranges'].append(r)
        need(len(byfile)==cfg['scope_parameters']['selected_source_files'] and len(byfile)<2208,'EXACT_FINITE_SELECTOR')
        ledger=Ledger(root/'state.sqlite',True,data_cap=cfg['whole_output_cap_bytes']-cfg['admin_reserve_bytes']-cfg['observer_reserve_bytes'],
          inode_cap=cfg['output_inode_cap']-128,ranges=ranges);ledger.close()
        shards=[{'shard_id':i,'sources':[]} for i in range(16)];weights=[0]*16
        def weight(file_work):return sum(r['physical_row_hi']-r['physical_row_lo'] for r in file_work['ranges'])
        for file_work in sorted(byfile.values(),key=lambda s:(-weight(s),s['file_id'])):
            i=min(range(16),key=lambda i:(weights[i],i));shards[i]['sources'].append(file_work);weights[i]+=weight(file_work)
        ctx=mp.get_context('spawn');barrier=ctx.Barrier(16)
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=ctx,initializer=initialize,initargs=(cfg,str(root),barrier)) as pool:
            receipts=list(pool.map(worker,shards,chunksize=1))
        reports=[load(require(r)) for r in receipts];need(len({r['pid'] for r in reports})==16,'SIXTEEN_ACTUAL_RANGE_WORKERS')
        ledger=Ledger(root/'state.sqlite');snapshot=ledger.snapshot();ledger.close()
        coverage,parity,stats,observed,classes=coverage_and_parity(root,cfg,snapshot,previous,witness)
        errors=[e for r in reports for e in r['errors']];pending=[r for r in snapshot['ranges'] if not r['complete']]
        global_stop=[fid for fid,s in stats.items() if s['newly_masked_records']/11231854>.01 or s['new_payload_structural_invalid_records']/11231854>.01]
        observed_review=[fid for fid,s in stats.items() if s['records'] and
          (s['newly_masked_records']/s['records']>.01 or s['new_payload_structural_invalid_records']/s['records']>.01)]
        hold=bool(global_stop or observed_review or parity['mismatches'] or parity['missing_witness_rows'] or parity['mismatched_witness_rows']
          or parity['missing_encoding_keys'] or parity['unwitnessed_current_CELL_kinds'] or parity['unwitnessed_current_float_widths']
          or coverage['duplicate_keys'] or parity['matched_rows']==0)
        need(unique_bytes(root)+(64<<20)<=cfg['whole_output_cap_bytes'] and len(list(root.rglob('*')))+2<=cfg['output_inode_cap'],'WHOLE_CAP_AND_INODES_WITH_PARTIALS')
        result={'schema':'BOUNDED_LABEL_PROJECTION_BATCH_V1','status':'QUALITY_HOLD' if hold else 'BATCH_PENDING' if pending or errors or snapshot['unpublished_tickets'] else 'BATCH_CACHE_CLOSED_FULL_COVERAGE_PENDING',
          'config':small_ref(a.config),'job_id':str(proof['job_id']),'scope_parameters':cfg['scope_parameters'],'actual_range_plan':plan,
          'footer_manifest_reference':cfg['footer_manifest_reference'],'fixture_gate':gate,'worker_reports':receipts,'cursors':snapshot['ranges'],
          'witness_discovery_reference':witness_ref,
          'closed_windows':snapshot['closed_windows'],'unpublished_tickets':snapshot['unpublished_tickets'],'budget_ticket':{k:v for k,v in snapshot.items() if k not in ('ranges','closed_windows','unpublished_tickets')},
          'coverage':coverage,'parity':parity,'errors':errors,'field_stats':{k:dict(v) for k,v in stats.items()},
          'declared_field_observations':{k:dict(v) for k,v in observed.items()},'physical_classifications_by_kind':{k:dict(v) for k,v in classes.items()},
          'quality_stop_fields_global_lower_bound':sorted(global_stop),'partial_observed_rate_review_fields':sorted(observed_review),
          'full_quality_denominator':11231854,'partial_rates_are_not_full_population_pass':True,
          'inherited_label_shadow_difference':8694,'inherited_base_difference':621,'differences_not_silently_reclassified':True,
          'calibration_state':cfg['calibration_state'],'normalization_completed':False,'full_population_completed':False,
          'guide1p5_complete':False,'final_common_D4':False,'registry_final':False,'candidate_masks_frozen':False,
          'within_molecule_review_completed':False,'native_program_precision_verified':False,'actual_frame_origin_verified':False,
          'source_wholebody_SHA_state':'INHERITED_PRODUCER_NOT_REHASHED_THIS_PASS','unique_new_output_bytes_before_manifest':unique_bytes(root),
          'elapsed_seconds':time.monotonic()-start,'automatic_retry':False}
        save(root/'manifest.json',result);print(json.dumps({'status':result['status'],'closed_windows':len(snapshot['closed_windows']),'pending_ranges':len(pending),'parity_rows':parity['matched_rows']}))
        need(not(hold or pending or errors or snapshot['unpublished_tickets']),'PENDING_OR_QUALITY_HOLD_PARTIALS_PRESERVED')
    except BaseException as exc:
        save(root/'failure.json',{'error':type(exc).__name__+':'+str(exc),'partials_preserved':True,'automatic_retry':False});raise

if __name__=='__main__':main()
