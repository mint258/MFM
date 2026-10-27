"""Own IO globals; original worker full bytes/AST, new explicit numeric sink."""
import collections,hashlib,json,os,stat,time
from pathlib import Path
from .codec import TypedPart,project
from .contract import need
from . import bindings as B
from workflows.data_v1_final.labels.bounded_projection_v1.parts import Ledger,TicketStop,publish_bytes,pin,slices
from workflows.data_v1_final.labels.bounded_projection_v1.run import frame
from workflows.data_v1_final.labels.footer_inventory_v1.footer import footer_only
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import load,require,save,sqlite_ro,lookup_batch,classify_owner,TASKS,TASK_FAMILIES
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import stop_requested,soft_worker_rss,mark_stop
from workflows.data_v1_final.labels.payload_audit_v1.run import source_columns
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.run import BASE_COLUMNS
WORK={}


def initialize(cfg,root,barrier):
    import pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    common,masks=B.legacy(cfg['science']);fields=load(require(cfg['science']['sources']['registry']))['fields']
    enabled=sorted((f for f in fields if f['status']=='enabled'),key=lambda f:f['field_key']);ids={f['field_key']:i for i,f in enumerate(enabled)}
    need(len(fields)==264 and len(enabled)==146,'FROZEN_264_146_MAPPING');fields=[dict(f,field_id=ids.get(f['field_key'])) for f in fields]
    selection=None
    if cfg['mode']=='pilot512':
        selection=set()
        for group in cfg['pilot_groups']:
            h=pq.ParquetFile(require(group['owner_index']))
            try:
                for batch in h.iter_batches(batch_size=512,columns=['record_id'],use_threads=False):selection.update(batch.column(0).to_pylist())
            finally:h.close()
        need(len(selection)==4251,'EXACT_BOUND_ORIGINAL512_OWNER_SELECTION')
    calibration=load(require(cfg['science']['calibration']))['fields'] if cfg['mode']=='pilot512' else {}
    WORK.update(cfg=cfg,root=Path(root),barrier=barrier,common=common,masks=masks,selection=selection,
      task_fields={t:[f for f in fields if f['task']==t] for t in TASKS},calibration=calibration)

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
            body={'schema':'COMPACT_NUMERIC_PHYSICAL_WINDOW_V1','ticket':self.ticket,'range_id':self.item['range_id'],
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


