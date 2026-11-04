"""Read-only actual-C0 selected parts, copied working catalog, missing tasks only."""
import collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,pathlib,re,shutil,sqlite3,struct
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_fast55k_pilot_day_v1 import fast_coverage as F
I=F.I;K=F.K;B=F.B;V=F.V;CONTEXT={}

def adopt_part(task,reference):
    """The original selected row codec/owner/mask checks, without re-encoding parts."""
    import pyarrow as pa,pyarrow.parquet as pq
    source=task['source'];oldroot=C.OLDROOT/'typed_coverage';pr=C.reference(reference)
    C.need(pathlib.Path(pr['path']).parent==oldroot/'parts','EXACT_C0_SELECTED_PART_ROOT')
    I.allow(pr,origin=oldroot);path=I.require(pr);frame=F.identity(path)
    db=F.sqlite_ro(F.WORK['selected']['path']);reader=pq.ParquetFile(path)
    seen=[];base=[];stats=collections.defaultdict(collections.Counter);rows=0;digest=hashlib.sha256()
    try:
        C.need(reader.schema_arrow.equals(K.schema(pa),check_metadata=False),'EXACT_ORIGINAL_BINARY_TYPED_CACHE_SCHEMA')
        for batch in reader.iter_batches(batch_size=F.BATCH_ROWS,use_threads=False):
            C.need(not F.stop_requested(),'SOFT_RESOURCE_STOP_NO_COMPLETE_PART_ACCEPTANCE')
            F.soft_worker_rss(F.WORK['plan']['worker_rss_stop_bytes'])
            F.digest_array(digest,batch.column(batch.schema.get_field_index('view_sha256')))
            for row in batch.to_pylist():
                raw=db.execute('SELECT owner,payload FROM wanted WHERE rid=?',(row['record_id'],)).fetchone()
                C.need(raw is not None,'ONLY_EXACT_SELECTED_ORIGINAL_RID');owner=json.loads(raw[0]);payload=raw[1]
                K.validate_row_buffers(row)
                C.need(K.row_signature(row)==row['view_sha256'] and row['file_id']==source['file_id']
                  and task['lo']<=row['physical_row']<task['hi'] and K.owner_signature(owner)==row['owner_sha256']
                  and owner['record_ordinal']==row['record_ordinal'] and owner['job_id']==source['source_job_id']
                  and B.ROLES[owner['new_role']]==row['role_code'],'SELECTED_ORIGINAL_OWNER_ROLE_SOURCE_ROW_F64_BITS')
                code=row['task_code'];kind=row['row_kind']
                C.need(kind==task['part']['row_kind'] and code==task['part']['task_code']
                  and ((kind=='base'and code==255)or(kind=='task'and type(code)is int and 0<=code<14)), 'EXACT_ORIGINAL_TASK_SEQUENCE_KIND')
                seen.append((row['record_ordinal'],14 if kind=='base'else code));rows+=1
                if kind=='base':
                    pool=[struct.unpack_from('<d',row['base_f64'],i)[0]for i in range(0,len(row['base_f64']),8)]
                    g=B.decode(row['base_json'],pool);z=g['atomic_numbers']
                    usable=(type(z)is list and len(z)==owner['total_atoms'] and all(type(v)is int and 1<=v<=118 for v in z)
                      and hashlib.sha256(b''.join(struct.pack('<q',v)for v in z)).hexdigest()==g['native_atom_order_sha256']
                      and g['source_payload_sha256']==payload and g['geometry_status']=='ORIGINAL_PM7_GEOMETRY')
                    C.need(usable,'REAL_SELECTED_Z_PAYLOAD_AND_ATOM_ORDER_NO_UNKNOWN_FIT')
                    base.append((row['record_ordinal'],row['record_id'],b''.join(struct.pack('<q',v)for v in z),row['base_json'],row['owner_sha256'],1))
                else:
                    entries=K.unpack_entries(row,F.WORK['fields']);mask=K.binary_json_loads(row['compact_mask_json'])
                    C.need(B.compact.encode(row['record_ordinal'],code,entries)==mask,'ORIGINAL_PERSISTENT_MASK_REASONS_INDICES_BIT_PARITY')
                    V.field_counts(stats,entries)
        C.need(rows>0 and F.identity(path)==frame,'CLOSED_SELECTED_PART_NONEMPTY_STABLE')
        return {'sequence':task['sequence'],'out':{'reference':pr,'rows':rows,'row_kind':task['part']['row_kind'],
          'task_code':task['part']['task_code'],'typed_stream_sha256':digest.hexdigest()},'seen':seen,'base':base,
          'field_stats':{k:dict(v)for k,v in stats.items()},'old_part':{'reference':task['part']['reference'],
          'window_reference':task['window_reference'],'manifest_reference':task['manifest_reference'],'actual_parent_state':task['actual_parent_state']},
          'rows':task['part']['rows'],'kept':rows,'file_id':source['file_id'],'lo':task['lo'],'hi':task['hi'],
          'task_code':task['part']['task_code'],'row_kind':task['part']['row_kind'],'adopted':True}
    finally:
        reader.close();db.close()
        C.need(F.identity(path)==frame and F.identity(F.WORK['selected']['path'])==F.WORK['selected_frame'],'OLD_PART_AND_FROZEN_SELECTED_INDEX_STABLE')

def copy_closed(path,destination,*,mutable=False):
    C.need(path.parent==C.OLDROOT/'typed_coverage' and not any(pathlib.Path(str(path)+s).exists()for s in ('-wal','-shm','-journal')),
      'TERMINAL_DELETE_JOURNAL_CATALOG_ONLY')
    reference=I.pin(path);I.allow(reference,origin=C.OLDROOT);I.require(reference);before=F.identity(path)
    with path.open('rb')as src,destination.open('xb')as dst:shutil.copyfileobj(src,dst,1<<20);dst.flush();__import__('os').fsync(dst.fileno())
    copied=I.pin(destination)
    if not mutable:I.allow(copied)
    C.need(reference['bytes']==copied['bytes']and reference['sha256']==copied['sha256']
      and F.identity(path)==before,'READONLY_BYTE_IDENTICAL_CATALOG_COPY')
    return reference,copied

def build(plan,proof,root,budget,members):
    C.need(CONTEXT.get('prefix')is not None,'EXPLICIT_TERMINAL_C0_PREFIX_REQUIRED')
    root=pathlib.Path(root);root.mkdir();(root/'parts').mkdir();oldroot=C.OLDROOT/'typed_coverage'
    oldselected,selected=copy_closed(oldroot/'selected_owner.sqlite',root/'selected_owner.sqlite')
    oldcatalog,copied=copy_closed(oldroot/'numeric_catalog.sqlite',root/'numeric_catalog.sqlite',mutable=True)
    db=sqlite3.connect(copied['path']);db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=-16384')
    wanted=F.sqlite_ro(selected['path']);groups=collections.Counter();expected=sum(m['S_conformers']for m in members.values());mass=collections.Counter()
    try:
        C.need(db.execute('PRAGMA table_info(selected)').fetchall()[3][2]=='INTEGER','ORIGINAL_FAST_JOB_INTEGER_NO_SCHEMA_CAST')
        rows=wanted.execute('SELECT ordinal,rid,mid,job,role,owner FROM wanted ORDER BY ordinal')
        count=0
        for row in rows:
            C.need(db.execute('SELECT ordinal,rid,mid,job,role,owner FROM selected WHERE ordinal=?',(row[0],)).fetchone()==row,
              'COPIED_CATALOG_AND_FROZEN_SELECTED_OWNER_INDEX_IDENTICAL')
            mid=row[2];C.need(mid in members and members[mid]['effective_role']==row[4],'SAME_FROZEN55K_MEMBER_ROLE')
            mass[mid]+=1;groups[row[3]]+=1;count+=1
        C.need(count==expected and db.execute('SELECT count(*)FROM selected').fetchone()[0]==expected
          and set(mass)==set(members)and all(mass[mid]==m['S_conformers']for mid,m in members.items()),'EXACT_SAME55K_RECORD_MASS')
    finally:wanted.close()
    files={}
    for path in (oldroot/'parts').iterdir():
        match=re.fullmatch(r'part_(\d{8})\.parquet',path.name)
        C.need(match is not None and path.is_file()and not path.is_symlink(),'ONLY_CLOSED_ORIGINAL_SELECTED_TASK_PARTS')
        sequence=int(match.group(1));C.need(sequence not in files,'NO_DUPLICATE_PART_SEQUENCE');files[sequence]=path
    registered={}
    for file,lo,hi,task,kind,ref,window,parent in db.execute('SELECT *FROM parts'):
        ref=json.loads(ref);path=pathlib.Path(ref['path']);match=re.fullmatch(r'part_(\d{8})\.parquet',path.name)
        C.need(path.parent==oldroot/'parts'and match is not None and files.get(int(match.group(1)))==path,'ALL_REGISTERED_OLD_PARTS_PRESENT')
        key=(file,lo,task);C.need(key not in registered,'UNIQUE_ORIGINAL_CATALOG_KEY');registered[key]=(hi,kind,ref,json.loads(window))
    review=C.projection_origins(plan);book=I.load_data(plan['source_inventory_reference'],2<<20);byfile={r['file_id']:r for r in book['files']}
    cfg=dict(plan,data_references=C.unique([*plan['data_references'],selected]));stats=collections.defaultdict(collections.Counter)
    oldparts=[];base_rows=task_rows=0;adopted=created=skipped=0;seen_files=set();seen_registered=set();new_paths=set()
    iterator=iter(F.tasks(plan,budget,review,byfile));finished=False;checkpoint_sequence=0;observed={}
    def merge(r):
        nonlocal base_rows,task_rows,adopted,created
        key=(r['file_id'],r['lo'],r['task_code']);old=registered.get(key);out=r['out']
        for ordinal,bit in r['seen']:
            value=observed.get(ordinal,0);C.need(not value&(1<<bit),'READBACK_SELECTED_BASE_AND_TASK_EXACT_ONCE')
            observed[ordinal]=value|(1<<bit)
        if old is not None:
            C.need(out is not None and old==(r['hi'],r['row_kind'],out['reference'],r['old_part']['window_reference']), 'EXACT_REGISTERED_PART_KEY_AND_REFERENCE')
            for ordinal,bit in r['seen']:
                v=db.execute('SELECT seen FROM selected WHERE ordinal=?',(ordinal,)).fetchone()
                C.need(v is not None and v[0]&(1<<bit),'REGISTERED_PART_BITS_ALREADY_COMMITTED')
            for b in r['base']:C.need(db.execute('SELECT *FROM base WHERE ordinal=?',(b[0],)).fetchone()==b,'REGISTERED_BASE_BYTES_NOT_REPLACED')
            seen_registered.add(key)
        else:
            F.update_seen(db,r['seen'])
            if r['base']:db.executemany('INSERT INTO base VALUES(?,?,?,?,?,?)',r['base'])
            if out is not None:
                p=pathlib.Path(out['reference']['path']);I.allow(out['reference'],origin=oldroot if r.get('adopted')else None)
                db.execute('INSERT INTO parts VALUES(?,?,?,?,?,?,?,?)',(r['file_id'],r['lo'],r['hi'],r['task_code'],r['row_kind'],
                  K.canonical(out['reference']).decode(),K.canonical(r['old_part']['window_reference']).decode(),K.canonical(r['old_part']['manifest_reference']).decode()))
                if not r.get('adopted'):new_paths.add(str(p))
        base_rows+=len(r['base'])
        if r['row_kind']=='task':task_rows+=r['kept']
        for fid,counters in r['field_stats'].items():stats[fid].update(counters)
        oldparts.append(r['old_part']);db.commit()
        if r.get('adopted'):adopted+=1
        else:created+=int(out is not None)
    try:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=F.initialize,initargs=(cfg,selected,str(root)))as pool:
            while not finished:
                budget.check();used=I.unique_bytes(budget.root)
                capacity=min(32,(plan['whole_output_cap_bytes']-used-(256<<20))//plan['typed_part_cap_bytes'])
                if capacity<=0:
                    I.R.mark_stop('FAST55K_RESUME_BOUNDED_PART_ADMISSION_CAP',{'used':used,'whole_cap':plan['whole_output_cap_bytes']})
                    raise ValueError('SOFT_RESOURCE_STOP_FAST55K_NO_BOUNDED_PART_RESERVATION')
                wave=[]
                while len(wave)<capacity and not finished:
                    try:task=next(iterator)
                    except StopIteration:finished=True;break
                    key=(task['source']['file_id'],task['lo'],task['part']['task_code']);path=files.get(task['sequence'])
                    if path is not None:
                        seen_files.add(task['sequence']);known=registered.get(key)
                        ref=known[2]if known is not None else I.pin(path)
                        C.need(ref['path']==str(path),'SEQUENCE_CATALOG_PATH_SAME_ORIGINAL_TASK')
                        wave.append((task,ref))
                    else:
                        C.need(key not in registered,'NO_REBUILD_MISSING_REGISTERED_PART')
                        bit=14 if task['part']['row_kind']=='base'else task['part']['task_code']
                        missing=db.execute('SELECT 1 FROM selected WHERE job=? AND (seen & ?)=0 LIMIT 1',(task['source']['source_job_id'],1<<bit)).fetchone()
                        if missing is None:
                            skipped+=1;oldparts.append({'reference':task['part']['reference'],'window_reference':task['window_reference'],
                              'manifest_reference':task['manifest_reference'],'actual_parent_state':task['actual_parent_state']});continue
                        wave.append((task,None))
                pending={pool.submit(adopt_part,task,ref)if ref is not None else pool.submit(F.part,task):task['sequence']for task,ref in wave}
                cf.wait(pending,return_when=cf.ALL_COMPLETED);results=[]
                for future,key in pending.items():
                    r=future.result();C.need(r['sequence']==key,'EXACT_PART_WORKER_IDENTITY');results.append(r)
                budget.check()
                for r in sorted(results,key=lambda x:x['sequence']):budget.check();merge(r)
                checkpoint_sequence+=1
                I.save(root/('resume_checkpoint_%08d.json'%checkpoint_sequence),{'schema':'CURRENT_PARENT_FAST55K_RESUME_PROGRESS_V1',
                  'adopted_closed_parts':adopted,'new_selected_parts':created,'empty_already_complete_tasks':skipped,
                  'phase':'CACHE_READBACK_AND_MISSING_ONLY','old_catalog_reference':oldcatalog,'old_selected_owner_reference':oldselected,
                  'closed_old_parts_written':False,'complete_or_release':False})
        C.need(seen_files==set(files)and seen_registered==set(registered),'EVERY_OLD_FILE_AND_REGISTERED_PART_EXACT_ONCE')
        C.need(len(observed)==expected and all(v==32767 for v in observed.values())and db.execute('SELECT count(*)FROM base').fetchone()[0]==expected,
          'READBACK_EVERY_SELECTED_BASE_AND14_TASKS_ONCE_NOT_COPIED_SEEN_ASSUMPTION')
        F.complete_mass(db,expected,base_rows,task_rows,stats);holds=V.quality_fields(stats,active_field_ids=plan['field_scope']['active_field_ids'])
        lineage=I.save(root/'original_part_lineage.DATA.json',{'parts':oldparts})
        body={'schema':'CURRENT_PARENT_SELECTED_TYPED_ORIGIN_V1','status':'ACTUAL_CLOSED_SUBSET_WITHIN_PARENT_NOT_CHILD_C0',
          'job_id':str(proof['job_id']),'Root_projection_review_reference':plan['projection_origin_review_reference'],
          'original_part_lineage_reference':lineage,'original_failed_timeout_states_preserved':True,'full_Common_D4_D5_D3_D6_release':False}
        oldorigin=I.save(root/'readback_old_selected_typed_origin.json',dict(body,readonly_C0_parent_job_id='4525232',old_catalog_reference=oldcatalog,
          old_selected_owner_reference=oldselected,readback_closed_parts=adopted,closed_old_parts_written=False))
        origin=I.save(root/'current_parent_typed_origin.json',body)
        for file,lo,task,ref in db.execute('SELECT file,lo,task,ref FROM parts').fetchall():
            p=pathlib.Path(json.loads(ref)['path']);parent=oldorigin if p.parent==oldroot/'parts'else origin
            C.need(parent==oldorigin or str(p)in new_paths,'ONLY_ORIGINAL_READONLY_OR_CURRENT_PARENT_PART')
            db.execute('UPDATE parts SET parent=? WHERE file=? AND lo=? AND task=?',(K.canonical(parent).decode(),file,lo,task))
        db.commit();db.close();db=None
        catalog=I.allow(I.pin(root/'numeric_catalog.sqlite'))
        plan.setdefault('cache_transitive_output_origins',[]).append({'manifest_reference':oldorigin,'output_root':str(oldroot)})
        report={'schema':'BOUNDED_COMPLETE_SPRIME_TYPED_COVERAGE_V1','status':'EXACT_NUMERIC_SOURCE_COVERAGE_NOT_FINAL_MASKS','mode':'bounded_pilot55k',
          'job_id':str(proof['job_id']),'records':expected,'molecules':55000,'task_rows':task_rows,'base_rows':base_rows,
          'field_stats':{k:dict(v)for k,v in stats.items()},'selected_group_record_counts':dict(groups),'quality_hold_fields':holds,'errors':[],
          'original_projection_origins':review['projection_origins'],'old_parent_states_and_costs_unchanged':True,'old_FAILED_or_TIMEOUT_not_promoted':True,
          'all14task_and_base_exact_once':True,'original_values_masks_None_IEEE_bits_and_indices_unchanged':True,
          'original_source_full_population_counts':C.GLOBAL_SOURCE_COUNTS,'full_Common_or_D4_D5_D3_D6_release':False,'parts_catalog':catalog,'base_index':catalog,
          'current_parent_typed_origin_reference':origin,'original_part_lineage_reference':lineage,'fast_IO_not_new_science':True,'workers':16,
          'source_batch_rows':F.BATCH_ROWS,'readonly_old_typed_origin_reference':oldorigin,'readonly_old_catalog_reference':oldcatalog,
          'readonly_old_selected_owner_reference':oldselected,'readback_closed_parts':adopted,'new_selected_parts':created,'old_cache_written':False}
        for key in('canonical_index','field_map_reference','logical_group_plan_reference','source_inventory_reference'):report[key]=plan[key]
        return I.save(root/'manifest.json',report),report,oldparts
    finally:
        if db is not None:db.close()