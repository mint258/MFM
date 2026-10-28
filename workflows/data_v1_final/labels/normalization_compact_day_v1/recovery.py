"""Root-authorized failed closed prefix: readonly bytes/typed verification only."""
import collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,sqlite3,stat,time,types
from pathlib import Path
from . import contract as C,io as I
from workflows.data_v1_final.labels.bounded_projection_v1.parts import Ledger
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K,bindings as B
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity
WORK={}
STATUS='ROOT_ADOPTED_FAILED_DAY_CLOSED_WINDOWS_CURRENT_PARENT_VERIFIED'

def authority(ref):
    a=C.meta(ref);C.need(a['schema']=='ROOT_FAILED_LABEL_DAY_CLOSED_PREFIX_RECOVERY_AUTHORITY_V1'
      and a['status']=='APPROVED_READONLY_FAILED_PREFIX_THEN_UNREAD_CONTINUATION' and a['reviewer']=='root'
      and a['old_job_id']=='4524575' and a['old_parent_state']=='FAILED' and a['old_parent_core_seconds']==603392
      and a['old_source_archive_never_executed'] is True and a['no_original_parts_copied_rewritten_deleted'] is True
      and a['old_FAILED_and_all_costs_and_UNKNOWN_preserved'] is True,'REAL_EXACT_FAILED_PREFIX_ROOT_ADOPTION_SCOPE')
    inventory=C.meta(a['lstat_inventory_reference'])
    C.need(inventory['schema']=='LABEL_DAY_FAILED_CLOSED_PREFIX_LSTAT_V1' and inventory['status']=='ACTUAL_FAILED_WRAPPER_CLOSED_PREFIX_METADATA_ONLY_NOT_SCIENTIFIC_ACCEPTANCE'
      and inventory['job_id']=='4524575' and inventory['uid']==1278 and inventory['closed_worker_report_count']==64
      and inventory['unexpected_partial_or_SQLite_sidecar_paths']==[] and inventory['scientific_DATA_bodies_opened_or_hashed'] is False,
      'ROOT_FRAME_INVENTORY_NOT_FAKE_SCIENTIFIC_SHA')
    account=C.meta(inventory['failed_accounting_reference']);rows=[r for r in account['parents'] if str(r['job_id'])=='4524575']
    C.need(account['status']=='ACTUAL_PARENT_ACCOUNTING_CLOSED' and account['uid']==1278 and account['raw_sacct_reference']==inventory['raw_accounting_reference']
      and len(rows)==1 and rows[0]['state']=='FAILED' and rows[0]['exit_code']=='1:0' and rows[0]['alloc_cpus']==64
      and rows[0]['elapsed_raw_seconds']*64==603392,'ACTUAL_FAILED_64_PARENT_NOT_C0')
    raw=C.A.O.pin_bytes(inventory['raw_accounting_reference'],C.A.Q.read_small).decode('utf-8-sig').splitlines();head=raw[0].split('|')
    rr=[dict(zip(head,line.split('|'))) for line in raw[1:] if line.split('|')[0]=='4524575']
    C.need(len(rr)==1 and rr[0]['UID']=='1278' and rr[0]['State']=='FAILED' and rr[0]['ExitCode']=='1:0'
      and rr[0]['AllocCPUS']=='64','ACTUAL_FAILED_RAW_ACCOUNT_ROW')
    original=C.meta(inventory['original_fixture3_reference']);day=C.meta(inventory['day_fixture6_reference']);check=C.meta(inventory['whole_repository_check_actual_reference'])
    C.need(original['status']=='PASS' and original['tests_run']==3 and original['errors']==original['failures']==0
      and day['status']=='PASS' and day['tests']==6 and day['errors']==day['failures']==0 and day['scientific_DATA_read'] is False
      and check['status']=='PASS' and check['returncode']==0,'REAL_OLD_SOURCE3_DAY6_WHOLECHECK_FACTS_NOT_NEW_R2_ACCEPTANCE')
    result=C.meta(check['result_reference']);C.need(result['status']=='PASS' and result['export_verification_required'] is False,'ACTUAL_ORIGINAL_WHOLE_REPOSITORY_CHECK')
    failure=C.meta(inventory['failure_operational_reference'])
    C.need(failure['error']=='''ModuleNotFoundError("No module named 'workflows.data_v1_final.labels.normalization_compact_day_v1.bindings'")'''
      and 'project.py' in failure['traceback'] and failure['automatic_retry'] is False,'EXACT_LATE_WRAPPER_IMPORT_FAILURE_ONLY')
    archive=C.meta(inventory['source_archive_reference']);C.need(archive['schema']=='LABEL_DAY_FAILED_PARENT_SOURCE14_ARCHIVE_V1'
      and archive['source_files']==14 and archive['old_FAILED_preserved'] is True and archive['source_archive_never_executed'] is True,'EXACT_ARCHIVED_R1_WITNESS_ONLY')
    for e in archive['entries']:
        C.need(e['origin_reference']['bytes']==e['snapshot_reference']['bytes'] and e['origin_reference']['sha256']==e['snapshot_reference']['sha256'],
          'ORIGINAL_SOURCE14_EXACT_ARCHIVE')
        C.A.O.pin_bytes(e['snapshot_reference'],C.A.Q.read_small)
    oldplan=C.meta(inventory['plan_reference']);proof=C.meta(inventory['startup_proof_reference']);request=C.meta(inventory['request_reference'])
    C.need(str(proof['job_id'])=='4524575' and proof['request']==request and request['cpus']==64 and request['node']=='compute-0-14'
      and request['scope_key']==C.KEY and request['producer_plan_reference']==inventory['plan_reference']
      and oldplan['output_directory']==inventory['old_output_directory'],'EXACT_OLD_PLAN_SOURCE_ARGV_PROOF')
    C.need(a['same_storage_mapping_review_reference'] and a['lstat_inventory_reference']==a['root_frozen_lstat_reference'],
      'REAL14_18_STORAGE_MAPPING_AND_EXACT_LSTAT_AUTHORITY')
    mapping=C.meta(a['same_storage_mapping_review_reference'])
    C.need(mapping['schema']=='ROOT_ACTUAL_MAIN_COMPUTE14_18_SHARED_STORAGE_MAPPING_PROBE_V1'
      and mapping['scientific_computation'] is False,'ACTUAL_SHARED_STORAGE_METADATA_PROBE_NOT_A_SCIENTIFIC_ACCEPTANCE')
    observed={r['decoded']['node']:r for r in mapping['observations']}
    C.need({'sonmi','compute-0-14','compute-0-18'}<=set(observed) and all(observed[n]['returncode']==0
      and observed[n]['decoded']['uid']==1278 and observed[n]['decoded']['scientific_body_read_or_computation'] is False
      for n in ('sonmi','compute-0-14','compute-0-18')),'REAL_SAME_UID14_18_STORAGE_OBSERVATIONS')
    marker=observed['sonmi']['decoded']['marker_reference'];intrinsic=('inode','uid','bytes','mtime_ns')
    C.need(all(observed[n]['decoded']['marker_reference']==marker and all(observed[n]['decoded']['marker_stat'][k]
      ==observed['sonmi']['decoded']['marker_stat'][k] for k in intrinsic) for n in ('compute-0-14','compute-0-18')),
      'SAME_ACTUAL_MARKER_INTRINSIC_FRAME_NOT_CROSS_NODE_DEVICE_EQUALITY')
    return a,inventory,oldplan

def _frame(s):return [s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns]

def safe_old(path,expected,oldroot):
    p=Path(path);C.need(oldroot in p.parents and not any(x.is_symlink() for x in (p,*p.parents)),'EXACT_FAILED_OUTPUT_ROOT_NO_SYMLINK')
    s=p.lstat();C.need(stat.S_ISREG(s.st_mode) and s.st_uid==expected['uid']==1278 and s.st_nlink==expected['nlink']==1
      and s.st_ino==expected['inode'] and s.st_size==expected['bytes'] and s.st_mtime_ns==expected['mtime_ns']
      and s.st_ctime_ns==expected['ctime_ns'],'OLD_FROZEN_INTRINSIC_FRAME_CHANGED_DEVICE_IS_LOCAL')
    return p,s

def init(cfg,oldroot,out):WORK.update(cfg=cfg,oldroot=Path(oldroot),out=Path(out))

def hash_chunk(task):
    number,ref=task;chunk=C.meta(ref);C.need(chunk['schema']=='LABEL_FAILED_CLOSED_PREFIX_LSTAT_CHUNK_V1','FROZEN_LSTAT_CHUNK_SCHEMA')
    verified=[];total=0
    for row in chunk['observations']:
        C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_RECOVERY_HASH_CHUNK')
        p,s=safe_old(row['path'],row,WORK['oldroot']);before=_frame(s);h=hashlib.sha256()
        with p.open('rb') as stream:
            C.need(_frame(os.fstat(stream.fileno()))==before,'CURRENT_OLD_DATA_FD_EQUALS_PATH')
            for block in iter(lambda:stream.read(1<<20),b''):h.update(block)
            C.need(_frame(os.fstat(stream.fileno()))==before==identity(p),'CLOSED_OLD_FILE_CHANGED_DURING_FIRST_CPU_SHA')
        verified.append({'reference':{'path':str(p),'bytes':s.st_size,'sha256':h.hexdigest()},'current_CPU_frame':before});total+=s.st_size
    return I.save(WORK['out']/('hash_chunk_%04d.json'%number),{'schema':'FAILED_PREFIX_CURRENT_CPU_HASH_CHUNK_V1','source_lstat_chunk_reference':ref,
      'files':verified,'bytes':total,'first_scientific_whole_SHA_only_on_CPU':True,'observed_device_is_current_CPU_only':True})

def open_catalog(path):
    return sqlite3.connect(Path(path).as_uri()+'?mode=ro&immutable=1',uri=True,timeout=120)

def accepted(ref,db):
    C.reference(ref);row=db.execute('SELECT bytes,sha,frame FROM files WHERE path=?',(ref['path'],)).fetchone()
    C.need(row is not None and row[0]==ref['bytes'] and row[1]==ref['sha256'],'ACTUAL_CPU_WHOLE_SHA_MATCHES_ORIGINAL_PRODUCER_REFERENCE')
    p=Path(ref['path']);frame=json.loads(row[2]);C.need(identity(p)==frame and not p.is_symlink(),'CURRENT_CPU_FILE_FRAME_STILL_STABLE');return p,frame

def verify_window(task):
    row,original_range,catalog=task;db=open_catalog(catalog)
    try:
        p,frame=accepted(row['receipt'],db);window=I.load(p)
        C.need(window['schema']=='COMPACT_NUMERIC_PHYSICAL_WINDOW_V1' and window['all_part_reopen_bits_verified'] is True
          and (window['physical_row_lo'],window['physical_row_hi'])==(row['lo'],row['hi']) and window['range_id']==row['range_id']
          and window['source_reference']==original_range['source'] and window['file_id']==original_range['file_id']
          and original_range['physical_row_lo']<=row['lo']<row['hi']<=original_range['physical_row_hi'],
          'ORIGINAL_CLOSED_LEDGER_WINDOW_KEY_AND_INTERVAL')
        C.need(identity(p)==frame,'WINDOW_CHANGED_AFTER_READ')
        import pyarrow.parquet as pq
        for part in window['parts']:
            path,before=accepted(part['reference'],db);stream=path.open('rb');C.need(_frame(os.fstat(stream.fileno()))==before,'PART_CURRENT_FD_FRAME')
            h=hashlib.sha256();count=0;last=-1;source=pq.ParquetFile(stream,pre_buffer=False)
            try:
                for batch in source.iter_batches(batch_size=16,use_threads=False):
                    C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_RECOVERY_TYPED_PART')
                    for item in batch.to_pylist():
                        K.validate_row_buffers(item);C.need(K.row_signature(item)==item['view_sha256']
                          and item['row_kind']==part['row_kind'] and item['task_code']==part['task_code'] and item['file_id']==window['file_id']
                          and window['physical_row_lo']<=item['physical_row']<window['physical_row_hi'] and item['physical_row']>last,
                          'REOPEN_ORIGINAL_TYPED_BITS_TASK_FILE_PHYSICAL_KEYS');last=item['physical_row'];h.update(item['view_sha256']);count+=1
                C.need(count==part['rows'] and h.hexdigest()==part['typed_stream_sha256'],'FULL_ORIGINAL_TYPED_STREAM_DIGEST_AND_ROW_COUNT')
            finally:
                current=_frame(os.fstat(stream.fileno()));source.close();stream.close()
                C.need(current==before==identity(path),'REOPEN_TYPED_PART_CHANGED')
        return {'receipt':row['receipt'],'file_id':window['file_id'],'lo':row['lo'],'hi':row['hi'],'range_id':row['range_id'],
          'field_stats':window['field_stats'],'physical_classifications':window['physical_classifications'],'source_kind':window['source_reference']['source_kind'],
          'parts':len(window['parts']),'all_part_reopen_bits_verified':True}
    finally:db.close()

def parallel(pool,fn,items,workers,budget):
    iterator=iter(items);pending={};saved=[]
    def fill():
        budget.observe()
        if I.stop_requested():return
        while len(pending)<workers:
            try:item=next(iterator)
            except StopIteration:return
            pending[pool.submit(fn,item)]=item
    fill()
    while pending:
        done,_=cf.wait(pending,return_when=cf.FIRST_COMPLETED)
        for f in done:pending.pop(f);saved.append(f.result())
        fill()
    C.need(not I.stop_requested(),'SOFT_RESOURCE_STOP_FAILED_PREFIX_NOT_ADOPTED');return saved

def execute(plan,cfg,proof,root,gate,budget):
    a,inventory,oldplan=authority(plan['failed_prefix_recovery_reference']);root=Path(root);root.mkdir()
    C.need(cfg['mode']=='full' and oldplan['scientific_config_reference']==plan['scientific_config_reference']
      and proof['request']['cpus']==plan['requested_cpus']>=16,'EXACT_ORIGINAL_SCIENTIFIC_INPUTS_NEW_REAL_CPU_PARENT')
    chunks=inventory['lstat_observation_chunk_references'];C.need(chunks and all(r['bytes']<=2<<20 for r in chunks),'CHUNK_REFS_ONLY_NOT_115K_INLINE_SOURCE')
    ctx=mp.get_context('spawn');pool_count=plan['requested_cpus'];hash_refs=[]
    if plan.get('prior_hash_stage_reference'):
        from . import prior_hash_stage
        hash_refs,total=prior_hash_stage.reuse(plan,cfg,proof,root,budget)
        catalog=sqlite3.connect(root/'verified_files.sqlite')
    else:
        C.need(pool_count==64,'ORIGINAL_FIRST_HASH_RECOVERY_REMAINS_EXACT64')
        out=root/'hash_chunks';out.mkdir()
        with cf.ProcessPoolExecutor(max_workers=pool_count,mp_context=ctx,initializer=init,initargs=(cfg,inventory['exact_closed_projection_directory'],str(out))) as pool:
            hash_refs=parallel(pool,hash_chunk,list(enumerate(chunks)),pool_count,budget)
        catalog=sqlite3.connect(root/'verified_files.sqlite');catalog.execute('CREATE TABLE files(path TEXT PRIMARY KEY,bytes INTEGER,sha TEXT,frame TEXT) WITHOUT ROWID')
        n=total=0
        for ref in hash_refs:
            chunk=I.load(I.require(ref));total+=chunk['bytes']
            for r in chunk['files']:
                q=r['reference'];catalog.execute('INSERT INTO files VALUES(?,?,?,?)',(q['path'],q['bytes'],q['sha256'],json.dumps(r['current_CPU_frame'])));n+=1
        catalog.commit();C.need(n==inventory['files'] and total==inventory['bytes'],'EXACT_FROZEN115K_CENSUS_NO_EXTRA_MISSING_OR_DUPLICATES')
    oldroot=Path(inventory['exact_closed_projection_directory']);ledger_path=oldroot/'state.sqlite'
    ledger_ref=catalog.execute('SELECT bytes,sha FROM files WHERE path=?',(str(ledger_path),)).fetchone();C.need(ledger_ref,'FROZEN_CLOSED_LEDGER_PRESENT')
    accepted({'path':str(ledger_path),'bytes':ledger_ref[0],'sha256':ledger_ref[1]},catalog)
    ledger=open_catalog(ledger_path);before=identity(ledger_path)
    try:snapshot=Ledger.snapshot(types.SimpleNamespace(db=ledger))
    finally:ledger.close();C.need(identity(ledger_path)==before,'OLD_READONLY_LEDGER_CHANGED')
    C.need(snapshot['unpublished_tickets']==[],'NO_UNKNOWN_OR_RESERVED_LEDGER_TICKET_PROMOTION')
    range_path=oldroot/'actual_range_plan.json';rp=catalog.execute('SELECT bytes,sha FROM files WHERE path=?',(str(range_path),)).fetchone()
    C.need(rp,'ORIGINAL_ACTUAL_RANGE_PLAN_PRESENT');accepted({'path':str(range_path),'bytes':rp[0],'sha256':rp[1]},catalog)
    actual=I.load(range_path);ranges={r['range_id']:r for r in actual['ranges']}
    original_receipts=[];workerrefs=[]
    for path in inventory['worker_report_paths']:
        rr=catalog.execute('SELECT bytes,sha FROM files WHERE path=?',(path,)).fetchone();C.need(rr,'ALL64_REAL_WORKER_RECEIPTS_IN_FROZEN_CENSUS')
        ref={'path':path,'bytes':rr[0],'sha256':rr[1]};accepted(ref,catalog);worker=I.load(path)
        C.need(worker['schema']=='BOUNDED_LABEL_RANGE_WORKER_V1' and worker['errors']==[] and worker['opens']==worker['closes'],
          'ORIGINAL_WORKER_ERROR_FD_UNKNOWN_HOLD');original_receipts.append(worker);workerrefs.append(ref)
    C.need(len(original_receipts)==len({w['pid'] for w in original_receipts})==64,'ORIGINAL64_DISTINCT_RETURNED_WORKERS')
    assigned=[key for w in original_receipts for key in w['done_ranges']+w['pending_ranges']]
    C.need(len(assigned)==len(set(assigned))==len(ranges) and set(assigned)==set(ranges),'ORIGINAL_WORKER_RANGE_PARTITION')
    previous={key:r['physical_row_lo'] for key,r in ranges.items()}
    for row in snapshot['closed_windows']:
        C.need(row['range_id'] in previous and row['lo']==previous[row['range_id']] and row['lo']<row['hi']<=ranges[row['range_id']]['physical_row_hi'],
          'CLOSED_WINDOWS_NO_GAP_OVERLAP_OR_CURSOR_JUMP');previous[row['range_id']]=row['hi']
    C.need(set(previous)=={r['range_id'] for r in snapshot['ranges']} and all(previous[r['range_id']]==r['next_physical_row'] for r in snapshot['ranges']),
      'READONLY_LEDGER_CURSOR_EQUALS_EXACT_CLOSED_WINDOWS')
    catalog.commit();catalog.close();catalog_ref=I.pin(root/'verified_files.sqlite')
    with cf.ProcessPoolExecutor(max_workers=pool_count,mp_context=ctx) as pool:
        windows=parallel(pool,verify_window,[(w,ranges[w['range_id']],str(root/'verified_files.sqlite')) for w in snapshot['closed_windows']],pool_count,budget)
    windows.sort(key=lambda w:(w['file_id'],w['lo']));stats=collections.defaultdict(collections.Counter);classes=collections.defaultdict(collections.Counter)
    for w in windows:
        classes[w['source_kind']].update(w['physical_classifications'])
        for fid,s in w['field_stats'].items():stats[fid].update(s)
    holds=sorted(set(B.quality_stop_fields(stats,11231854,.01))|{fid for fid,s in stats.items() if s['records'] and
      (s['newly_masked_records']/s['records']>.01 or s['new_payload_structural_invalid_records']/s['records']>.01)})
    I.save(root/'quality_report.json',{'field_stats':{k:dict(v) for k,v in stats.items()},'quality_hold_fields':holds,'original_threshold':.01,'old_parent_state':'FAILED'})
    C.need(windows and not holds,'ORIGINAL_ONE_PERCENT_HOLD_FAILED_PREFIX_NOT_ADOPTED')
    cfgref=I.save(root/'scientific_config.json',dict(cfg,config_path=str(root/'scientific_config.json')))
    intervals=[{k:w[k] for k in ('file_id','lo','hi','all_part_reopen_bits_verified')} for w in windows]
    m={'schema':C.OLD.BATCH,'status':STATUS,'config':cfgref,'job_id':str(proof['job_id']),'mode':'full','fixture_gate':gate,
      'worker_reports':workerrefs,'verified_window_receipts':[w['receipt'] for w in windows],'closed_physical_intervals':intervals,
      'source_cursors':snapshot['ranges'],'field_stats':{k:dict(v) for k,v in stats.items()},'physical_classifications':{k:dict(v) for k,v in classes.items()},
      'quality_hold_fields':[],'errors':[],'unpublished_tickets':[],'actual_range_plan':{'path':str(range_path),'bytes':rp[0],'sha256':rp[1]},
      'adopted_original_projection_root':str(oldroot),'failed_prefix_recovery_reference':plan['failed_prefix_recovery_reference'],
      'old_actual_failed_accounting_reference':inventory['failed_accounting_reference'],'old_parent_state':'FAILED','old_parent_job_id':'4524575','old_parent_core_seconds':603392,
      'old_actual_used_bytes_preserved':total,'original_Source14_archive_reference':inventory['source_archive_reference'],
      'current_CPU_complete_whole_SHA_and_typed_readback':not bool(plan.get('prior_hash_stage_reference')),
      'current_CPU_unchanged_frames_and_complete_typed_readback':True,
      'prior_hash_stage_reference':plan.get('prior_hash_stage_reference'),
      'prior_hash_stage_reuse_reference':I.pin(root/'prior_hash_stage_reuse.json') if plan.get('prior_hash_stage_reference') else None,
      'whole_SHA_basis':'ACTUAL_PRIOR_C0_COMPLETE_HASH_CURRENT_FD_STABLE' if plan.get('prior_hash_stage_reference') else 'CURRENT_PARENT_COMPLETE_HASH',
      'old_C0_claimed':False,'original_Parquets_reread':False,
      'verified_file_catalog_reference':catalog_ref,'hash_inventory_chunk_references':hash_refs,'charged_output_bytes':I.unique_bytes(root)+(64<<20)}
    I.save(root/'manifest.json',m);return I.pin(root/'manifest.json')

def build_metadata(req,path,output):
    """Only bounded Source/small frames; no failed body opened or future SHA."""
    import copy
    a,inventory,old=authority(req['failed_prefix_recovery_reference'])
    out=Path(output).absolute();C.need(C.RUN/'control' in out.parents and not out.exists(),'FRESH_FAILED_RECOVERY_METADATA');out.mkdir(parents=True,mode=0o700)
    seed=C.meta(old['scientific_config_reference']);C.need(seed['mode']=='full' and old['execution_mode']=='PROJECT_AND_COVERAGE_ONLY','ORIGINAL_FULL_SOURCE_PROJECTION_SCOPE_ONLY')
    small=[C.A.Q.pin(path),req['failed_prefix_recovery_reference'],a['lstat_inventory_reference'],inventory['source_archive_reference'],
      a['same_storage_mapping_review_reference'],old['scientific_config_reference'],*inventory['lstat_observation_chunk_references']]
    for key in ('failed_accounting_reference','raw_accounting_reference','failure_operational_reference','plan_reference','request_reference','submission_reference',
      'startup_proof_reference','original_fixture3_reference','day_fixture6_reference','whole_repository_check_actual_reference'):
        small.append(inventory[key])
    archive=C.meta(inventory['source_archive_reference']);small.extend(e['snapshot_reference'] for e in archive['entries'])
    archived_paths={e['origin_reference']['path'] for e in archive['entries']}
    small.extend(r for r in old['source_references'] if r['path'] not in archived_paths)
    small.append(C.meta(inventory['whole_repository_check_actual_reference'])['result_reference'])
    small.extend(seed['small_references']);small.extend(seed['science']['sources'].values())
    p=copy.deepcopy(old);p.pop('scope_parameters',None)
    for key in ('output_directory','whole_output_cap_bytes','projection_cap_bytes','coverage_cap_bytes','requested_cpus'):
        p[key]=req[key]
    p.update(failed_prefix_recovery_reference=req['failed_prefix_recovery_reference'],execution_mode='PROJECT_AND_COVERAGE_ONLY',statistics_cap_bytes=0,
      previous_day_parents=req.get('previous_day_parents',[]),requested_statistical_routes=[])
    if req.get('prior_hash_stage_reference'):
        from . import prior_hash_stage
        _,_,_,_,prior_sources=prior_hash_stage.authority(req['prior_hash_stage_reference'],req['failed_prefix_recovery_reference'])
        p['prior_hash_stage_reference']=req['prior_hash_stage_reference'];small.extend(prior_sources)
    data=list(old['data_references'])
    for parent in p['previous_day_parents']:
        m=C.actual_day(parent);C.need(m['execution_mode']=='PROJECT_AND_COVERAGE_ONLY','ONLY_REAL_CLEAN_RECOVERY_CONTINUATION')
        small.extend(parent.values());data.extend([m['checkpoint_reference'],*m['projection_outputs']])
    C.need((p['requested_cpus']>=16 if p.get('prior_hash_stage_reference') else p['requested_cpus']==64)
      and p['projection_cap_bytes']>=8<<30 and p['coverage_cap_bytes']>=2<<30,
      'REAL_DAY_ROOT_EXPLICIT_NEW_OUTPUT_CAPS_OLD471GB_ALREADY_USED')
    p['source_references']=C.M.M.unique([*C.sources(seed),*small]);p['data_references']=C.M.M.unique(data)
    p['scope_parameters']=C.scope(p);C.plan(p);pr=C.A.Q.write_new(out/'plan.json',p)
    C.need(pr['bytes']<=2<<20,'ONLY116_CHUNK_REFS_NOT_115K_LOCATORS_IN_PLAN')
    r={key:req[key] for key in ('job_name','node','resource_authority_reference','quota_provider_review_reference','quota_provider_identity_reference','root_carveout_review_reference')}
    r.update(schema='ROOT_REQUESTED_ANALYSIS_DAY_V1',status='REQUESTED_FOR_REVIEW',requested_by='root',cpus=p['requested_cpus'],
      scope_key=C.KEY,scope_parameters=p['scope_parameters'],producer_plan_reference=pr,estimated_peak_output_bytes=p['whole_output_cap_bytes'],
      source_references=C.M.M.unique([*p['source_references'],pr]),data_references=p['data_references'])
    rr=C.A.Q.write_new(out/'resource_request.json',r)
    return C.A.Q.write_new(out/'draft_receipt.json',{'schema':'COMPACT_NUMERIC_DAY_FAILED_RECOVERY_DRAFT_V1','plan_reference':pr,
      'resource_request_reference':rr,'failed_inventory_reference':a['lstat_inventory_reference'],'old_parent_state':'FAILED','old_core_seconds':603392,
      'lstat_chunks':len(inventory['lstat_observation_chunk_references']),'old_files':inventory['files'],'old_actual_used_bytes':inventory['bytes'],
      'no_scientific_DATA_opened_or_hashed':True,'old_source_archive_witness_never_executed':True,'new_parent_submission_or_C0_claimed':False})
