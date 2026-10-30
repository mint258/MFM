"""Admitted CPU strict whole-FD IO; metadata never opens numeric DATA."""
import hashlib,json,math,os,sqlite3,stat,threading,time
from pathlib import Path
from workflows.data_v1_final.labels.normalization_compact_runtime_v3.runtime import new_root,unique_bytes,wall_clock,remaining_wall,failed
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support as S
from workflows.data_v1_final.labels.streaming_v1.support import sqlstr,path_list
from workflows.data_v1_final.execution.cpu_analysis_day_v1 import quota_provider as QP
from workflows.data_v1_final.execution import finite_quota_observation_guard_v1 as QG
from . import contract as C,memory as R
stop_requested=R.stop_requested;pin=S.ref;ref=S.ref
ALLOWED={};ORIGINS={};ROOT=None;CAP=None

def configure(cfg):
    global ALLOWED,ORIGINS,ROOT,CAP
    ALLOWED={r['path']:r for r in cfg['source_references']+cfg['data_references']}
    ORIGINS={o['manifest_reference']['path']:o for o in cfg['cache_transitive_output_origins']}
    ROOT=Path(cfg['output_directory']);CAP=cfg['whole_output_cap_bytes']
    for old in cfg.get('accepted_prior_output_roots',[]):ORIGINS[old['manifest_reference']['path']]=old

def local(path):return ROOT is not None and ROOT in Path(path).parents

def register_prior(reference):
    reference=C.reference(reference);p=Path(reference['path'])
    C.need(any(Path(root) in p.parents for o in ORIGINS.values() for root in [o['output_root'],*o.get('additional_output_roots',[])]),'EXACT_ROOT_ACCEPTED_PREVIOUS_OUTPUT_ONLY')
    C.need(reference['path'] not in ALLOWED or ALLOWED[reference['path']]==reference,'NO_PRIOR_DATA_REBIND')
    ALLOWED[reference['path']]=reference

def register_part(reference,parent):
    """Only refs actually read from the whole-SHA closed catalog; never scan roots."""
    reference=C.reference(reference);o=ORIGINS.get(parent['path']);C.need(o is not None and o['manifest_reference']==parent,'EXACT_CLOSED_CACHE_PARENT_AUTHORITY')
    p=Path(reference['path']);C.need(Path(o['output_root']) in p.parents and p.suffix=='.parquet','CATALOG_PART_UNDER_EXACT_ACTUAL_ORIGIN')
    C.need(reference['path'] not in ALLOWED or ALLOWED[reference['path']]==reference,'NO_TRANSITIVE_REFERENCE_REBIND');ALLOWED[reference['path']]=reference

def require(reference,content=True):
    reference=C.reference(reference,source=reference.get('bytes')==0);p=Path(reference['path'])
    C.need(ALLOWED.get(str(p))==reference or local(p),'ONLY_DECLARED_OR_CURRENT_CPU_PRODUCED_INPUT')
    C.need(not any(q.is_symlink() for q in (p,*p.parents)),'NO_SYMLINK_INPUT')
    with p.open('rb') as f:
        s=os.fstat(f.fileno());before=[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]
        C.need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_nlink==1 and s.st_size==reference['bytes'],'REAL_FD_UID_REGULAR_SINGLE_LINK_SIZE')
        if content:
            h=hashlib.sha256()
            for b in iter(lambda:f.read(1<<20),b''):h.update(b)
            C.need(h.hexdigest()==reference['sha256'],'WHOLE_CURRENT_FD_SHA256')
        t=os.fstat(f.fileno());C.need(before==[t.st_dev,t.st_ino,t.st_size,t.st_mtime_ns,t.st_ctime_ns]==S.identity(p),'CURRENT_DEVICE_AND_FD_FRAME_STABLE')
    if content and local(p):ALLOWED[str(p)]=reference
    return p

def load(path,limit=512<<20):
    p=Path(path);before=S.identity(p);C.need(0<before[2]<=limit,'BOUNDED_CPU_JSON_DATA')
    with p.open('rb') as f:
        raw=f.read(limit+1);s=os.fstat(f.fileno());C.need(before==[s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]==S.identity(p),'JSON_FD_STABLE')
    C.need(len(raw)==before[2]<=limit,'JSON_NOT_TRUNCATED');return json.loads(raw.decode('utf-8-sig'))

def load_data(reference,maximum=64<<20):
    r=C.reference(reference,source=reference.get('bytes')==0)
    if r['path'] not in ALLOWED and not local(r['path']):register_prior(r)
    return load(require(r),maximum)
def semantic_sha(value):return hashlib.sha256((json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)+'\n').encode()).hexdigest()
def small_ref(path):return pin(path)

def save(path,value):
    raw=(json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode();p=Path(path)
    C.need(local(p),'NEW_OUTPUT_ONLY');p.parent.mkdir(parents=True,exist_ok=True)
    C.need(unique_bytes(ROOT)+len(raw)+(64<<20)<=CAP,'WHOLE_OUTPUT_WITH_OBSERVER_AND_ADMIN_RESERVE')
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    r=pin(p);ALLOWED[str(p)]=r;return r

def write_text(path,value):
    raw=value.encode('utf-8');p=Path(path);C.need(local(p),'NEW_CPU_REPORT_ONLY')
    C.need(unique_bytes(ROOT)+len(raw)+(64<<20)<=CAP,'WHOLE_OUTPUT_TEXT_CAP')
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    r=pin(p);ALLOWED[str(p)]=r;return r

EXTERNAL_CREDIT_PATH=str(C.RUN/'artifacts/labels/source_status_v1/compact_numeric_day_v1/day06_coverage_reuse_EOL_r6/coverage/numeric_catalog.sqlite')

def external_source_shape(value):
    """The only registered mutable writer permitted by this resource revision."""
    C.need(value['path']==EXTERNAL_CREDIT_PATH and value['cap_bytes']==336<<30 and value['uid']==1278
        and all(type(value[k])is int and value[k]>=0 for k in ('cap_bytes','uid','device','inode','initial_credited_allocated_bytes'))
        and value['inode']>0 and value['initial_credited_allocated_bytes']<=value['cap_bytes']
        and value['device_identity_is_endpoint_local_not_compared_across_login_and_NFS']is True
        and value['same_storage_as_validated_provider_marker']is True,
        'ONE_EXACT_REGISTERED729_MAIN_DATABASE_RESOURCE_ONLY_NOT_SCIENTIFIC_ADOPTION')
    return C.reference(value['initial_observation_reference'])

def initial_external_inventory(value,observation):
    C.need(observation['schema']=='ROOT_ACTIVE_OUTPUT_ALLOCATED_BYTES_METADATA_OBSERVATION_V1'
        and observation['database_bodies_read_or_hashed']is False and observation['scientific_adoption_or_C0_claimed']is False,
        'REAL_ROOT_METADATA_ONLY_INITIAL_ALLOCATED_OBSERVATION')
    timestamp=observation['observed_unix_seconds'];C.need(type(timestamp)in(int,float) and math.isfinite(timestamp) and timestamp>0,'FINITE_ACTUAL_INITIAL_INVENTORY_TIME')
    rows=[r for r in observation['files'] if r['path']==value['path']];C.need(len(rows)==1,'EXACT_UNIQUE_REGISTERED_EXTERNAL_PATH_IN_ROOT_OBSERVATION');row=rows[0]
    C.need(row['registered_parent']=='labels4524729' and all(row[k]==value[k] for k in ('device','inode','uid'))
        and type(row['size'])is int and row['size']>=0 and type(row['allocated_bytes'])is int and type(row['allocated_bytes_after_quota'])is int
        and row['allocated_bytes_after_quota']>=row['allocated_bytes']>=value['initial_credited_allocated_bytes']
        and row['allocated_bytes_after_quota']<=value['cap_bytes'] and row['source_database_body_not_read']is True
        and row['mutable_not_scientific_adoption']is True,'EXACT_INITIAL_INODE_UID_ALLOCATED_AFTER_QUOTA_RECHECK_NOT_BODY_ADOPTION')
    # The review may initially credit less than the observed allocation. Do not
    # silently credit its unreviewed remainder before a CPU inventory.
    return {'observed_unix_seconds':timestamp,'allocated_bytes':value['initial_credited_allocated_bytes'],'size':row['size'],
        'high_water_allocated_bytes':row['allocated_bytes_after_quota'],
        'origin':'ROOT_REVIEWED_INITIAL_METADATA_INVENTORY','device':row['device'],'inode':row['inode'],'uid':row['uid']}

def external_metadata_inventory(path,expected,marker_device,previous):
    """lstat only: never open, hash, query or read DB/WAL/scientific bytes."""
    p=Path(path);C.need(not any(q.is_symlink() for q in (p,*p.parents)),'NO_EXTERNAL_RESOURCE_SYMLINK')
    first=p.lstat();last=p.lstat()
    for s in (first,last):
        C.need(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and s.st_uid==expected['uid'] and s.st_ino==expected['inode']
            and s.st_dev==marker_device,'EXTERNAL_CURRENT_UID_INODE_AND_VALIDATED_SHARED_MARKER_DEVICE')
    a,b=first.st_blocks*512,last.st_blocks*512
    C.need(type(a)is int and type(b)is int and 0<=a<=b<=expected['cap_bytes'] and last.st_size>=first.st_size
        and b>=previous.get('high_water_allocated_bytes',previous['allocated_bytes']) and last.st_size>=previous.get('size',0),'EXTERNAL_ALLOCATION_OR_SIZE_SHRANK_OR_EXCEEDED_REGISTERED_CAP')
    return {'observed_unix_seconds':time.time(),'allocated_bytes':b,'size':last.st_size,'device':last.st_dev,'inode':last.st_ino,
        'uid':last.st_uid,'mtime_ns':last.st_mtime_ns,'body_opened_or_hashed':False,'origin':'ACTUAL_CPU_LSTAT_METADATA_ONLY'}

def covered_external_credit(samples,quota_timestamp,current,cap):
    C.need(type(quota_timestamp)in(int,float) and math.isfinite(quota_timestamp) and quota_timestamp>0,'FINITE_ORIGINAL_VALIDATED_QUOTA_OBSERVATION_TIME')
    if current is None:return 0
    C.need(type(cap)is int and cap>0 and type(current['allocated_bytes'])is int and 0<=current['allocated_bytes']<=cap,'FINITE_REGISTERED_CURRENT_ALLOCATION')
    eligible=[r['allocated_bytes'] for r in samples if r['observed_unix_seconds']<=quota_timestamp
        and r['inode']==current['inode'] and r['uid']==current['uid'] and r['allocated_bytes']<=current['allocated_bytes']]
    return min(cap,max(eligible+[0]))

def retain_external_samples(samples,quota_timestamp):
    eligible=[r for r in samples if r['observed_unix_seconds']<=quota_timestamp]
    anchor=max(eligible,key=lambda r:(r['allocated_bytes'],r['observed_unix_seconds'])) if eligible else samples[0]
    return [anchor,*[r for r in samples[-7:] if r is not anchor]]

class Budget:
    def __init__(self,plan,proof,root):
        self.plan=plan;self.root=Path(root);self.done=threading.Event();self.clock=wall_clock(proof,86400)
        save(self.root/'actual_wall_clock.json',self.clock)
        provider=QP
        if plan['node'] not in ('compute-0-14','compute-0-18'):
            from workflows.data_v1_final.execution.cpu_analysis_general_nodes_v1 import quota_provider as provider
        self.client=provider.Client(plan['quota_provider_review_reference'],proof['request'])
        self.expected_identity=plan['quota_provider_identity_reference'];self.quota_events=0;self.poll_lock=threading.RLock()
        carve=C.meta(plan['root_carveout_review_reference']);self.total=carve['total_future_reserved_bytes'];self.next_quota=0;self.quota=None
        C.need(carve['parent_output_cap_bytes']==plan['whole_output_cap_bytes'] and carve['parent_included_exactly_once'] is True,'CURRENT_PARENT_CAP_INCLUDED_ONCE')
        self.covered_samples=[];self.quota_covered_closed_allocated_bytes=0
        self.external=[];self.external_initial_credit=0;self.external_events=0;self.external_credit_revoked=False
        sources=carve.get('registered_external_allocated_credit_sources',[])
        C.need(type(sources)is list and len(sources)<=1,'ONLY_ONE_EXPLICIT_REGISTERED_EXTERNAL_RESOURCE_FILE')
        if sources:C.need(carve['registered_external_initial_credit_already_subtracted_from_total_future_reserved_bytes']is True,'ROOT_TOTAL_IS_NET_OF_EXACT_INITIAL_EXTERNAL_CREDIT')
        for source in sources:
            initial_ref=external_source_shape(source)
            C.need(initial_ref in plan['source_references'] and initial_ref in carve['accounting_basis_references'],'INITIAL_RESOURCE_EVIDENCE_EXPLICITLY_PINNED_IN_CURRENT_REQUEST_SOURCE')
            initial=initial_external_inventory(source,C.meta(initial_ref));self.external_initial_credit+=source['initial_credited_allocated_bytes']
            self.external.append({'source':source,'samples':[initial],'last':initial})
        self.control={'root':str(root),'cap':plan['whole_output_cap_bytes'],'reserve':256<<20}
        R.start_observer(proof,{'resource_evidence_output':str(root)+'_resource_observation','memavailable_soft_floor_bytes':4<<30,'resource_evidence_local_cap_bytes':64<<20})
        self.observe();self.thread=threading.Thread(target=self.loop,daemon=True);self.thread.start()
    def observe(self):
        with self.poll_lock:self._observe()
    def _observe(self):
        try:
            if time.monotonic()>=self.next_quota:
                self.quota=QG.observe(self.client,expected_identity_reference=self.expected_identity,record=self.record_quota_event);self.next_quota=time.monotonic()+60
            C.need(self.client.identity==self.expected_identity,'SAME_PINNED_FINITE_QUOTA_PUBLISHER_IDENTITY')
            C.need(self.quota['publisher_expires_unix_seconds']>=self.clock['cpu_wall_at_anchor']+self.clock['remaining_at_anchor_seconds']+300,
                'ACTUAL_FINITE_PROVIDER_COVERS_THIS_PARENT_PLUS300_NO_RENEWAL')
            observed=self.quota['observed_unix_seconds']
            self.quota_covered_closed_allocated_bytes=max([n for timestamp,n in self.covered_samples if timestamp<=observed]+[0])
            external_credit=0;observations=[]
            try:
                for state in self.external:
                    source=state['source'];marker=self.quota['cpu_marker']['stat'];C.need(marker['uid']==1278,'ACTUAL_VALIDATED_SAME_STORAGE_MARKER_UID')
                    current=external_metadata_inventory(source['path'],source,marker['device'],state['last'])
                    credit=covered_external_credit(state['samples'],observed,current,source['cap_bytes'])
                    state['last']=current;state['samples'].append(current);state['samples']=retain_external_samples(state['samples'],observed)
                    external_credit+=credit;observations.append({'path':source['path'],'current_metadata':current,
                        'initial_source_reference':source['initial_observation_reference'],'Root_login_device':source['device'],
                        'quota_observed_unix_seconds':observed,'credited_allocated_bytes':credit,'scientific_adoption':False})
            except Exception as exc:
                external_credit=0;self.external_credit_revoked=True
                observations.append({'error':repr(exc),'all_external_credit_revoked':True,'database_bodies_read_or_hashed':False})
                R.mark_stop('REGISTERED_EXTERNAL_ALLOCATION_METADATA_UNKNOWN_OR_SHRANK_CREDIT_REVOKED',{'error':repr(exc)})
            if self.external_credit_revoked:external_credit=0
            restored=self.total+self.external_initial_credit
            remaining_future=C.remaining_future(restored-external_credit,self.plan['whole_output_cap_bytes'],self.quota_covered_closed_allocated_bytes)
            if self.external:
                self.external_events+=1;save(self.root/'external_resource_credit_events'/('event_%06d.json'%self.external_events),
                    {'schema':'REGISTERED_EXTERNAL_ALLOCATED_FUTURE_CREDIT_OBSERVATION_V1','Root_net_total_future_reserved_bytes':self.total,
                    'initial_credit_added_back_bytes':self.external_initial_credit,'current_external_credit_bytes':external_credit,
                    'own_closed_quota_covered_allocated_bytes':self.quota_covered_closed_allocated_bytes,
                    'remaining_future_reserved_bytes':remaining_future,'original_quota_snapshot_reference':self.quota['snapshot_reference'],
                    'original_account_free_bytes':self.quota['free_bytes'],'observations':observations,'free_bytes_rewritten':False,
                    'no_SQL_DB_WAL_body_or_scientific_adoption':True})
            if self.quota['free_bytes']-remaining_future<200000000000:R.mark_stop('COMMON_TRAIN_ACCOUNT_FREE_FUTURE_ONCE_PLUS200GB',dict(self.quota,remaining_future_reserved_bytes=remaining_future))
            # Credit only immutable, already SHA-registered current-parent
            # allocated blocks observed BEFORE a later quota query. Current
            # unclosed files and logical bytes are never subtracted from quota.
            seen=set();allocated=0
            for ref in list(ALLOWED.values()):
                if not local(ref['path']):continue
                value=Path(ref['path']).lstat();key=(value.st_dev,value.st_ino)
                C.need(stat.S_ISREG(value.st_mode) and value.st_uid==1278 and value.st_nlink==1 and value.st_size==ref['bytes'],'IMMUTABLE_REGISTERED_OUTPUT_QUOTA_FRAME')
                if key not in seen:allocated+=value.st_blocks*512;seen.add(key)
            self.covered_samples.append((time.time(),allocated));self.covered_samples=self.covered_samples[-8:]
            if remaining_wall(self.clock,time.monotonic())<=900:R.mark_stop('COMMON_TRAIN_WALL900_NATURAL_DRAIN',self.clock)
            if unique_bytes(self.root)+(256<<20)>=self.plan['whole_output_cap_bytes']:R.mark_stop('COMMON_TRAIN_WHOLE_OUTPUT_SOFT_CAP',{})
        except Exception as e:R.mark_stop('COMMON_TRAIN_RESOURCE_OBSERVATION_UNKNOWN',{'error':repr(e)})
    def loop(self):
        while not self.done.wait(60):self.observe()
    def close(self):self.done.set();self.thread.join();R.MONITOR.finish()
    def check(self,*,force=False,dispatch=True):
        if force:self.observe()
        if dispatch:C.need(not stop_requested(),'SOFT_RESOURCE_STOP_PILOT_NO_NEW_WORK_NATURAL_DRAIN')
        C.need(unique_bytes(self.root)+(256<<20)<self.plan['whole_output_cap_bytes'],'FINITE_PILOT_WHOLE_OUTPUT_CAP')
    def record_quota_event(self,event):
        self.quota_events+=1;save(self.root/'quota_resource_events'/('event_%06d.json'%self.quota_events),event)

def allow(reference,*,origin=None):
    reference=C.reference(reference,source=reference.get('bytes')==0);p=Path(reference['path'])
    C.need(local(p) or (origin is not None and Path(origin) in p.parents),'ONLY_NEW_PARENT_OR_EXPLICIT_ROOT_REVIEWED_ORIGIN')
    C.need(reference['path'] not in ALLOWED or ALLOWED[reference['path']]==reference,'NO_TRANSITIVE_REFERENCE_REBIND')
    ALLOWED[reference['path']]=reference;return reference

def discover_prefix(plan):
    review,old,proof=C.prefix_origin(plan);path=Path(review['prefix_locator']);root=Path(old['output_directory'])
    C.need(path==root/'pilot_cache_prefix.json' and not any(p.is_symlink() for p in (path,*path.parents)),'UNIQUE_ROOT_REVIEWED_DEFERRED_PREFIX')
    # CPU-only: a positive actual reference is first established on the real
    # already-closed file, never filled with a predicted or zero SHA on login.
    r=allow(pin(path),origin=root);body=load_data(r,8<<20)
    C.need(body['schema']=='CURRENT_PARENT_PM7_PILOT_CACHE_PREFIX_V1'
        and body['status']=='DURABLE55K_PREFIX_WITHIN_RUNNING_PARENT_NOT_C0_OR_COMMON'
        and str(body['job_id'])==str(proof['job_id']) and body['molecules']==55000
        and body['plan_reference']==review['plan_reference'] and body['startup_proof_reference']==review['proof_reference']
        and body['future_parent_accounting_and_independent_Root_acceptance_required']is True
        and body['D3_D4_D5_or_Common_release']is False,'ACTUAL_DURABLE_PREFIX_NOT_SOURCE_PREDICTION_OR_PRODUCER_C0')
    pre=body['preselection_reference'];C.need(Path(pre['path'])==root/'pilot_preselection/preselection.json','FIXED_ACTUAL_PRESELECTION_LOCATOR')
    allow(pre,origin=root)
    for ref in body['catalog_part_references']:
        C.need(Path(ref['path']).parent==root/'catalog_parts','ONLY_CLOSED_PREFIX_CATALOG_PARTS')
        allow(ref,origin=root)
    return r,body,old,proof

def write_parquet(path,rows,schema,*,row_group_size=256):
    import pyarrow as pa,pyarrow.parquet as pq
    p=Path(path);C.need(local(p) and not p.exists(),'FRESH_CURRENT_PARENT_PARQUET_ONLY');p.parent.mkdir(parents=True,exist_ok=True)
    writer=pq.ParquetWriter(p,schema,compression='zstd');buffer=[];count=0;digest=hashlib.sha256()
    from workflows.data_v1_final.export.d5_inputs_compound_day_v1.core import encode
    def flush(values):
        table=pa.Table.from_pylist(values,schema=schema)
        for row in table.to_pylist():digest.update(encode(row))
        writer.write_table(table)
    try:
        for row in rows:
            C.need(not stop_requested(),'SOFT_RESOURCE_STOP_BEFORE_NEXT_TYPED_ROW');buffer.append(row);count+=1
            if len(buffer)>=row_group_size:flush(buffer);buffer=[]
        if buffer:flush(buffer)
    finally:writer.close()
    result=allow(pin(p));actual=pq.ParquetFile(require(result))
    try:
        C.need(actual.metadata.num_rows==count and actual.schema_arrow.equals(schema,check_metadata=False),'CURRENT_TYPED_PARQUET_SCHEMA_AND_ROWS_REOPEN')
        reopened=hashlib.sha256()
        for batch in actual.iter_batches(batch_size=256,use_threads=False):
            for row in batch.to_pylist():reopened.update(encode(row))
        C.need(reopened.digest()==digest.digest(),'CURRENT_TYPED_PARQUET_F64_NONE_MASK_ORDER_EXACT_REOPEN')
    finally:actual.close()
    return result
