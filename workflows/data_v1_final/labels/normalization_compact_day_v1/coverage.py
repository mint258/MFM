"""Actual-C0 independent numeric coverage; old TIMEOUT book remains untouched."""
import argparse,collections,hashlib,json,os,re,sqlite3,struct
from pathlib import Path
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import contract as C,codec as K,bindings as B
from . import io as I
from .lineage import actual
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import identity,lookup_batch,sqlite_ro


def execute(cfg,proof,root,gate):
    import numpy as np,pyarrow.parquet as pq
    book=I.load(I.require(cfg['source_inventory_reference']));files=book['files'];sources={s['file_id']:s for s in files};C.source_contract(files)
    n=4251 if cfg['mode']=='pilot512' else 11231854
    # Direct canonical ordinal addresses are retained even for the512 subset.
    total=11231854;seen=np.memmap(root/'tasks.uint8',mode='w+',dtype=np.uint8,shape=(14,total));seen[:]=0
    base_seen=np.memmap(root/'base.uint8',mode='w+',dtype=np.uint8,shape=(total,));base_seen[:]=0
    db=sqlite3.connect(root/'numeric_catalog.sqlite');db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=-8192')
    db.execute('PRAGMA max_page_count='+str((cfg['whole_output_cap_bytes']-(512<<20))//4096))
    db.executescript('CREATE TABLE parts(file INTEGER,lo INTEGER,hi INTEGER,task INTEGER,kind TEXT,ref TEXT,window TEXT,parent TEXT,PRIMARY KEY(file,lo,task));'
      'CREATE TABLE base(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,numbers BLOB,meta TEXT,owner_sha BLOB,usable INTEGER);'
      'CREATE TABLE formal(rid TEXT PRIMARY KEY,mol TEXT,payload TEXT,natoms INTEGER);CREATE TABLE molecules(mol TEXT PRIMARY KEY) WITHOUT ROWID;')
    canonical=sqlite_ro(I.require(cfg['canonical_index']));formal=I.require(cfg['formal_record_index_reference']);before=identity(formal);h=pq.ParquetFile(formal)
    formal_count=0;wanted=None
    if cfg['mode']=='pilot512':
        wanted=set()
        for g in cfg['pilot_groups']:
            owner=pq.ParquetFile(I.require(g['owner_index']))
            try:
                for batch in owner.iter_batches(batch_size=512,columns=['record_id'],use_threads=False):wanted.update(batch.column(0).to_pylist())
            finally:owner.close()
        C.need(len(wanted)==4251,'EXACT512_FORMAL_POINTER_SUBSET')
    try:
        needed=['record_id','molecule_id','record_payload_sha256','total_atoms'];C.need(set(needed)<=set(h.schema_arrow.names),'ACTUAL_FORMAL_POINTER_FIELDS_REQUIRED_NO_INVENTED_HEAVY_OR_SHA')
        for batch in h.iter_batches(batch_size=1024,columns=needed,use_threads=False):
            for r in batch.to_pylist():
                formal_count+=1
                if wanted is not None and r['record_id'] not in wanted:continue
                C.need(type(r['record_payload_sha256']) is str and re.fullmatch('[0-9a-f]{64}',r['record_payload_sha256']),'REAL_FORMAL_PAYLOAD_SHA')
                db.execute('INSERT INTO formal VALUES(?,?,?,?)',(r['record_id'],r['molecule_id'],r['record_payload_sha256'],r['total_atoms']))
            db.commit()
    finally:h.close()
    C.need(identity(formal)==before,'FORMAL_POINTER_SOURCE_CHANGED')
    intervals=[];stats=collections.defaultdict(collections.Counter);physical=collections.defaultdict(collections.Counter);roles=collections.Counter();errors=[];base_pending=0;parts=0;task_rows=base_rows=0
    try:
        for parent in cfg['batch_history']:
            C.need(not I.stop_requested(),'DAY_RESOURCE_STOP_COVERAGE_NO_ACCEPTANCE')
            m,_=actual(parent);parent_root=Path(parent['manifest']['path']).parent
            oldcfg=I.load(I.require(m['config']));C.need(oldcfg['canonical_index']==cfg['canonical_index'] and oldcfg['footer_manifest_reference']==cfg['footer_manifest_reference']
              and oldcfg['logical_group_plan_reference']==cfg['logical_group_plan_reference'] and oldcfg['mode']==cfg['mode'],'ONE_EXACT_SOURCE_AND_NUMERIC_ORDER_AUTHORITY')
            C.need(m['status'] in ('CLOSED_WINDOWS_ACTUAL_PARENT_ACCOUNTING_REQUIRED','DAY_INTERNAL_COMMITTED_WINDOWS_NOT_CHILD_C0') and not(m['errors'] or m['quality_hold_fields'] or m['unpublished_tickets']),'NO_PARTIAL_PARENT_OR_QUALITY_HOLD_ACCEPTANCE')
            for wr in m['verified_window_receipts']:
                C.need(not I.stop_requested(),'DAY_RESOURCE_STOP_COVERAGE_NO_ACCEPTANCE')
                C.need(Path(wr['path']).parent==parent_root/'parts','ONLY_BOUND_ACTUAL_PARENT_WINDOW');window=I.load(I.require(wr));fid=window['file_id']
                C.need(window['schema']=='COMPACT_NUMERIC_PHYSICAL_WINDOW_V1' and window['source_reference']==sources[fid]
                  and window['all_part_reopen_bits_verified'] is True,'EXACT_ORIGINAL_SOURCE_WINDOW_AUTHORITY')
                lo,hi=window['physical_row_lo'],window['physical_row_hi'];intervals.append({'file_id':fid,'lo':lo,'hi':hi,'all_part_reopen_bits_verified':True})
                physical[sources[fid]['source_kind']].update(window['physical_classifications'])
                for k,v in window['field_stats'].items():stats[k].update(v)
                for part in window['parts']:
                    pr=part['reference'];C.need(Path(pr['path']).parent==parent_root/'parts' and Path(pr['path']).suffix=='.parquet','ONLY_TRANSITIVE_ACTUAL_C0_NUMERIC_PART')
                    path=I.require(pr);frame=identity(path);src=pq.ParquetFile(path);count=0;digest=hashlib.sha256()
                    try:
                        for batch in src.iter_batches(batch_size=16,use_threads=False):
                            rows=batch.to_pylist();owners=lookup_batch(canonical,[r['record_id'] for r in rows])
                            for r in rows:
                                C.need(K.row_signature(r)==r['view_sha256'] and r['file_id']==fid and lo<=r['physical_row']<hi,'PART_NUMERIC_BITS_OR_SOURCE_INTERVAL_CHANGED')
                                owner=owners.get(r['record_id']);C.need(owner is not None and owner['record_ordinal']==r['record_ordinal'] and owner['job_id']==sources[fid]['source_job_id']
                                  and K.owner_signature(owner)==r['owner_sha256'] and B.ROLES[owner['new_role']]==r['role_code'],'EXACT_ALL_ROLE_CANONICAL_OWNER_NO_SOURCE_ALIAS')
                                ordinal=r['record_ordinal'];C.need(0<=ordinal<total,'CANONICAL_ORDINAL_BOUNDS');roles[owner['new_role']]+=1
                                if r['row_kind']=='base':
                                    C.need(r['task_code']==255 and not base_seen[ordinal],'DUPLICATE_OR_WRONG_BASE');base_seen[ordinal]=1;base_rows+=1;db.execute('INSERT OR IGNORE INTO molecules VALUES(?)',(owner['molecule_id'],))
                                    pool=[struct.unpack_from('<d',r['base_f64'],i)[0] for i in range(0,len(r['base_f64']),8)];g=B.decode(r['base_json'],pool);z=g['atomic_numbers']
                                    pointer=db.execute('SELECT mol,payload,natoms FROM formal WHERE rid=?',(r['record_id'],)).fetchone()
                                    C.need(pointer is not None and pointer[0]==owner['molecule_id'] and pointer[1]==g['source_payload_sha256'] and pointer[2]==owner['total_atoms'],'ACTUAL_FORMAL_BASE_PAYLOAD_AND_OWNER_NOT_FABRICATED')
                                    usable=(type(z) is list and len(z)==owner['total_atoms'] and all(type(v) is int and 1<=v<=118 for v in z)
                                      and hashlib.sha256(b''.join(struct.pack('<q',v) for v in z)).hexdigest()==g['native_atom_order_sha256'] and g['geometry_status']=='ORIGINAL_PM7_GEOMETRY')
                                    base_pending+=not usable;packed=b''.join(struct.pack('<q',v) for v in z) if usable else None
                                    db.execute('INSERT INTO base VALUES(?,?,?,?,?,?)',(ordinal,r['record_id'],packed,r['base_json'],r['owner_sha256'],int(usable)))
                                else:
                                    task=r['task_code'];C.need(type(task) is int and 0<=task<14 and not seen[task,ordinal],'DUPLICATE_CANONICAL_RECORD_TASK');seen[task,ordinal]=1;task_rows+=1
                                digest.update(r['view_sha256']);count+=1
                    finally:src.close()
                    C.need(identity(path)==frame and count==part['rows'] and digest.hexdigest()==part['typed_stream_sha256'],'ACTUAL_REOPEN_WHOLE_SHA_STREAM_FRAME_AND_MASS')
                    db.execute('INSERT INTO parts VALUES(?,?,?,?,?,?,?,?)',(fid,lo,hi,part['task_code'],part['row_kind'],K.canonical(pr).decode(),K.canonical(wr).decode(),K.canonical(parent['manifest']).decode()));parts+=1
                db.commit()
        cursors=C.advance_cursors(files,{},intervals)
        if cfg['mode']=='full':
            C.need(all(cursors[str(s['file_id'])]==s['rows'] for s in files),'EXACT_ALL2208_SOURCE_PHYSICAL_COVERAGE')
            C.need(np.all(seen==1) and np.all(base_seen==1),'ALL14_AND_BASE_EVERY_CANONICAL_ORDINAL_EXACTLY_ONCE')
            C.need(physical['label']['CANONICAL']==157245956 and sum(physical['label'].values())==157254650
              and physical['base']['CANONICAL']==11231854 and sum(physical['base'].values())==11232475,'FULL_PHYSICAL_CANONICAL_AND_SHADOW_MASSES')
        else:
            C.need(base_rows==4251 and task_rows==4251*14 and np.all(seen[:,base_seen==1]==1) and int(seen.sum())==4251*14,'EXACT512_ALL14_SELECTED_RECORD_MASS')
        C.need(base_rows==n and task_rows==14*n and len(stats)==146 and all(s['records']==n for s in stats.values()),'EXACT_NUMERIC_FIELD_RECORD_DENOMINATORS')
        molecules=db.execute('SELECT count(*) FROM molecules').fetchone()[0];C.need(molecules==(512 if cfg['mode']=='pilot512' else 1220466),'EXACT_SOURCE_MOLECULE_CARDINALITY_NOT_RECORD_COUNT')
        holds=B.quality_stop_fields(stats,n,.01)
        if holds:I.save(root/'quality_hold.json',{'quality_hold_fields':holds,'field_stats':{k:dict(v) for k,v in stats.items()},'scope_records':n,'old_books_unchanged':True})
        C.need(not holds,'UNCHANGED_ONE_PERCENT_COMPLETE_SOURCE_QUALITY_HOLD')
        db.execute('DROP TABLE formal');db.commit();db.close();db=None
        catalog=I.pin(root/'numeric_catalog.sqlite');seen.flush();base_seen.flush()
        result={'schema':C.COVERAGE,'status':'EXACT_NUMERIC_SOURCE_COVERAGE_NOT_FINAL_MASKS','config':I.small_ref(cfg['config_path']),'job_id':str(proof['job_id']),
          'mode':cfg['mode'],'records':n,'molecules':molecules,'task_rows':task_rows,'base_rows':base_rows,'parts':parts,'parts_catalog':catalog,'base_index':catalog,
          'field_map_reference':cfg['field_map_reference'],'element_basis':cfg['element_basis'],
          'canonical_index':cfg['canonical_index'],'logical_group_plan_reference':cfg['logical_group_plan_reference'],'source_inventory_reference':cfg['source_inventory_reference'],
          'field_stats':{k:dict(v) for k,v in stats.items()},'role_numeric_rows_including14tasks_and_base':dict(roles),'physical_classifications':{k:dict(v) for k,v in physical.items()},
          'quality_hold_fields':holds,'errors':errors,'base_geometry_pending_records':base_pending,'formal_pointer_rows_observed':formal_count,'fixture_gate':gate,
          'all14task_and_base_exact_once':True,'old1904_state':'TIMEOUT','old_UNKNOWN_or_RESERVED_promoted':False,
          'independent_reprojection_origin':'SINGLE_REAL_DAY_PARENT_AWAIT_ACTUAL_ACCOUNTING','final_mask_release':False,'final_Common_D4':False,
          'normalization_completed':False,'native_text_precision_or_frame_verified':False,'joint_model_policy_release_reference':None}
        C.need(I.unique_bytes(root)+(64<<20)+(2<<20)<=cfg['whole_output_cap_bytes'],'WHOLE_COVERAGE_SQLITE_AND_MEMMAP_CAP')
        I.save(root/'manifest.json',result);return 0
    finally:
        canonical.close()
        if db is not None:db.close()


