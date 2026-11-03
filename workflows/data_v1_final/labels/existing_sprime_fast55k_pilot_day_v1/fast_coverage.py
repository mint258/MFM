"""Whole old SHA/digest, Arrow selection before Python values, original codec."""
import collections,concurrent.futures as cf,hashlib,json,multiprocessing as mp,pathlib,sqlite3,struct
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I,coverage as V,bindings as B
from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import geometry as N
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import sqlite_ro,lookup_batch,identity
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1.memory import stop_requested,soft_worker_rss
WORK={}
BATCH_ROWS=16

def digest_array(digest,array):
    """Exact original concatenation of fixed32 view SHA bytes, no value cast."""
    C.need(array.type.byte_width==32 and array.null_count==0,'ORIGINAL_NON_NULL_FIXED32_VIEW_SHA')
    buffer=array.buffers()[1];start=array.offset*32;stop=start+len(array)*32
    C.need(buffer is not None and stop<=buffer.size,'EXACT_OWNED_FIXED32_BUFFER_SLICE')
    digest.update(memoryview(buffer)[start:stop])

def initialize(plan,selected_reference,root):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1);I.configure(plan);I.allow(selected_reference)
    I.require(selected_reference);fields=I.load_data(plan['field_map_reference'],2<<20)
    WORK.update(plan=plan,selected=selected_reference,selected_frame=identity(selected_reference['path']),root=pathlib.Path(root),
      fields={f['field_id']:f for f in fields},RID_sets=collections.OrderedDict(),RID_bytes=0)

def part(task):
    import pyarrow as pa,pyarrow.compute as pc,pyarrow.parquet as pq
    plan=WORK['plan'];source=task['source'];pr=task['part']['reference'];owner_root=pathlib.Path(task['owner_root'])
    C.need(pathlib.Path(pr['path']).parent==owner_root/'parts','EXACT_REVIEWED_CLOSED_OLD_PART_ROOT')
    I.allow(pr,origin=owner_root);path=I.require(pr);frame=identity(path);db=sqlite_ro(WORK['selected']['path'])
    C.need(identity(WORK['selected']['path'])==WORK['selected_frame'],'FROZEN_SELECTED_RID_INDEX_FRAME')
    job=source['source_job_id'];values=WORK['RID_sets'].get(job)
    if values is None:
        values=pa.array([rid for rid, in db.execute('SELECT rid FROM wanted WHERE job=? ORDER BY rid',(job,))],type=pa.string())
        if values.nbytes<=64<<20:
            while WORK['RID_sets']and(len(WORK['RID_sets'])>=8 or WORK['RID_bytes']+values.nbytes>64<<20):
                _,old=WORK['RID_sets'].popitem(last=False);WORK['RID_bytes']-=old.nbytes
            WORK['RID_sets'][job]=values;WORK['RID_bytes']+=values.nbytes
    reader=pq.ParquetFile(path);digest=hashlib.sha256();rows=0;kept=0;selected=None
    seen=[];base=[];stats=collections.defaultdict(collections.Counter)
    try:
        C.need(reader.schema_arrow.equals(K.schema(pa),check_metadata=False),'EXACT_ORIGINAL_BINARY_TYPED_CACHE_SCHEMA')
        for batch in reader.iter_batches(batch_size=BATCH_ROWS,use_threads=False):
            C.need(not stop_requested(),'SOFT_RESOURCE_STOP_NO_COMPLETE_PART_ACCEPTANCE')
            soft_worker_rss(plan['worker_rss_stop_bytes'])
            hashes=batch.column(batch.schema.get_field_index('view_sha256'));digest_array(digest,hashes);rows+=batch.num_rows
            chosen=batch.filter(pc.is_in(batch.column(batch.schema.get_field_index('record_id')),value_set=values))
            # Unselected numeric/binary/nested columns never become Python objects.
            for row in chosen.to_pylist():
                raw=db.execute('SELECT owner,payload FROM wanted WHERE rid=?',(row['record_id'],)).fetchone()
                C.need(raw is not None,'ONLY_EXACT_SELECTED_ORIGINAL_RID');owner=json.loads(raw[0]);payload=raw[1]
                K.validate_row_buffers(row)
                C.need(K.row_signature(row)==row['view_sha256'] and row['file_id']==source['file_id']
                  and task['lo']<=row['physical_row']<task['hi'] and K.owner_signature(owner)==row['owner_sha256']
                  and owner['record_ordinal']==row['record_ordinal'] and owner['job_id']==source['source_job_id']
                  and B.ROLES[owner['new_role']]==row['role_code'],'SELECTED_ORIGINAL_OWNER_ROLE_SOURCE_ROW_F64_BITS')
                code=row['task_code'];kind=row['row_kind']
                C.need((kind=='base'and code==255)or(kind=='task'and type(code)is int and 0<=code<14),'ORIGINAL_BASE_OR_TASK_CODE')
                seen.append((row['record_ordinal'],14 if kind=='base'else code));kept+=1
                if kind=='base':
                    pool=[struct.unpack_from('<d',row['base_f64'],i)[0]for i in range(0,len(row['base_f64']),8)]
                    g=B.decode(row['base_json'],pool);z=g['atomic_numbers']
                    usable=(type(z)is list and len(z)==owner['total_atoms'] and all(type(v)is int and 1<=v<=118 for v in z)
                      and hashlib.sha256(b''.join(struct.pack('<q',v)for v in z)).hexdigest()==g['native_atom_order_sha256']
                      and g['source_payload_sha256']==payload and g['geometry_status']=='ORIGINAL_PM7_GEOMETRY')
                    C.need(usable,'REAL_SELECTED_Z_PAYLOAD_AND_ATOM_ORDER_NO_UNKNOWN_FIT')
                    base.append((row['record_ordinal'],row['record_id'],b''.join(struct.pack('<q',v)for v in z),row['base_json'],row['owner_sha256'],1))
                else:
                    entries=K.unpack_entries(row,WORK['fields']);mask=K.binary_json_loads(row['compact_mask_json'])
                    C.need(B.compact.encode(row['record_ordinal'],code,entries)==mask,'ORIGINAL_PERSISTENT_MASK_REASONS_INDICES_BIT_PARITY')
                    V.field_counts(stats,entries)
                if selected is None:selected=K.TypedPart(task['part']['row_kind'],task['part']['task_code'],plan['typed_part_cap_bytes'],plan['row_serialized_cap_bytes'])
                selected.add(row)
        C.need(rows==task['part']['rows'] and digest.hexdigest()==task['part']['typed_stream_sha256']
          and identity(path)==frame,'WHOLE_OLD_SHA_FRAME_STREAM_DIGEST_AND_MASS_NO_RELAXATION')
        out=None if selected is None else selected.finish(WORK['root']/'parts'/('part_%08d.parquet'%task['sequence']))
        return {'sequence':task['sequence'],'out':out,'seen':seen,'base':base,'field_stats':{k:dict(v)for k,v in stats.items()},
          'old_part':{'reference':pr,'window_reference':task['window_reference'],'manifest_reference':task['manifest_reference'],
            'actual_parent_state':task['actual_parent_state']},'rows':rows,'kept':kept,'file_id':source['file_id'],
          'lo':task['lo'],'hi':task['hi'],'task_code':task['part']['task_code'],'row_kind':task['part']['row_kind']}
    finally:
        reader.close();db.close();C.need(identity(path)==frame and identity(WORK['selected']['path'])==WORK['selected_frame'],'ORIGINAL_PART_AND_SELECTED_INDEX_FRAME_REMAIN_STABLE')

def selected_index(plan,root,members,prefix,budget):
    """Canonical lookup only for actual frozen55k native pointers, no full walk."""
    import duckdb
    NATIVE=I.require(prefix['native_catalog_reference']);native=duckdb.connect(str(NATIVE),read_only=True)
    canonical=sqlite_ro(I.require(plan['canonical_index']));frame=identity(plan['canonical_index']['path']);group=collections.Counter()
    destination=root/'selected_owner.sqlite';db=sqlite3.connect(destination);db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL')
    db.execute('CREATE TABLE wanted(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,mid TEXT,job INTEGER,role TEXT,owner TEXT,payload TEXT)')
    cur=native.execute('SELECT record_id,molecule_id,record_payload_sha256,total_atoms FROM native55k ORDER BY record_id');mass=collections.Counter()
    try:
        while True:
            rows=cur.fetchmany(256)
            if not rows:break
            budget.check();owners=lookup_batch(canonical,[r[0]for r in rows]);C.need(len(owners)==len(rows),'ALL_SELECTED_NATIVE_RIDS_HAVE_CANONICAL_OWNER')
            for rid,mid,payload,atoms in rows:
                owner=owners[rid];C.need(mid in members and owner['molecule_id']==mid and owner['total_atoms']==atoms
                  and owner['new_role']==members[mid]['effective_role'],'EXACT_FROZEN_COHORT_OWNER_ROLE_AND_NATIVE_POINTER')
                db.execute('INSERT INTO wanted VALUES(?,?,?,?,?,?,?)',(owner['record_ordinal'],rid,mid,owner['job_id'],owner['new_role'],K.canonical(owner).decode(),payload))
                mass[mid]+=1;group[owner['job_id']]+=1
        expected=sum(r['S_conformers']for r in members.values())
        C.need(set(mass)==set(members)and all(mass[mid]==r['S_conformers']for mid,r in members.items())and sum(mass.values())==expected,
          'EVERY_ORIGINAL_N_RECORD_OF_SAME_FROZEN55K_NOT_NEW_SAMPLE')
        db.execute('CREATE INDEX wanted_job ON wanted(job,rid)');db.commit()
    finally:db.close();native.close();canonical.close();C.need(identity(plan['canonical_index']['path'])==frame,'SELECTED_CANONICAL_FRAME_STABLE')
    return I.allow(I.pin(destination)),group,expected

def tasks(plan,budget,review,byfile):
    windows_seen=set();sequence=0
    for origin in review['projection_origins']:
        mr=origin['manifest_reference'];m=I.load_data(mr,512<<20);oldroot=pathlib.Path(origin['parts_output_root'])
        roots=[pathlib.Path(r)for r in origin.get('parts_output_roots',[str(oldroot)])]
        C.need(str(m['job_id'])==str(C.meta(origin['proof_reference'])['job_id']),'EXACT_MANIFEST_ACTUAL_PRODUCING_PARENT')
        if m.get('old_actual_failed_accounting_reference')is not None:
            historical=m['old_actual_failed_accounting_reference'];C.need(historical in origin.get('historical_parent_evidence_references',[]),'PRESERVE_ADOPTED_FAILED_PARENT_AUTHORITY')
            account=C.meta(historical);C.need(account['query_returncode']==0 and account['raw_sacct_reference']in origin['historical_parent_evidence_references'],'REAL_OLD_FAILED_RAW_EVIDENCE')
        C.need(m['schema']==V.Legacy.BATCH and m['status']in('CLOSED_WINDOWS_ACTUAL_PARENT_ACCOUNTING_REQUIRED','DAY_INTERNAL_COMMITTED_WINDOWS_NOT_CHILD_C0',
          'ROOT_ADOPTED_FAILED_DAY_CLOSED_WINDOWS_CURRENT_PARENT_VERIFIED')and not(m['errors']or m['quality_hold_fields']or m['unpublished_tickets']),
          'ONLY_REAL_CLEAN_COMMITTED_OLD_WINDOWS_NOT_FAILED_PARENT_PROMOTION')
        oldcfg=I.load_data(m['config'],8<<20);N.normalize_config_authorities(oldcfg,plan)
        for wr in m['verified_window_receipts']:
            budget.check();C.need(wr['path']not in windows_seen,'NO_DUPLICATE_OR_SILENTLY_DEDUPED_OLD_WINDOW');windows_seen.add(wr['path'])
            owner_root=next((r for r in roots if r in pathlib.Path(wr['path']).parents),None)
            C.need(owner_root is not None,'EXACT_REVIEWED_WINDOW_ROOT');I.allow(wr,origin=owner_root);window=I.load_data(wr,16<<20)
            source=byfile[window['file_id']]
            C.need(window['schema']=='COMPACT_NUMERIC_PHYSICAL_WINDOW_V1'and C.reference(window['source_reference'])==C.reference(source)
              and window['all_part_reopen_bits_verified']is True,'ORIGINAL_WINDOW_SOURCE_AND_REOPEN_AUTHORITY')
            for p in window['parts']:
                sequence+=1;yield {'sequence':sequence,'source':source,'part':p,'owner_root':str(owner_root),'lo':window['physical_row_lo'],
                  'hi':window['physical_row_hi'],'window_reference':wr,'manifest_reference':mr,'actual_parent_state':origin['actual_parent_state']}

PREFIX=None
def update_seen(db,items):
    for ordinal,bit in items:
        old=db.execute('SELECT seen FROM selected WHERE ordinal=?',(ordinal,)).fetchone()
        C.need(type(bit)is int and 0<=bit<=14 and old is not None and not old[0]&(1<<bit),'NO_DUPLICATE_SELECTED_TASK_OR_BASE')
        db.execute('UPDATE selected SET seen=? WHERE ordinal=?',(old[0]|(1<<bit),ordinal))

def complete_mass(db,expected,base_rows,task_rows,stats):
    C.need(base_rows==expected and task_rows==14*expected and db.execute('SELECT count(*)FROM selected WHERE seen<>32767').fetchone()[0]==0,
      'EVERY_SELECTED_CANONICAL_BASE_AND14_TASKS_EXACT_ONCE')
    C.need(len(stats)==146 and all(s['records']==expected for s in stats.values()),'ORIGINAL_FIELD_OWN_SCOPE_SELECTED_RECORD_DENOMINATORS')

def build(plan,proof,root,budget,members):
    C.need(PREFIX is not None,'ACTUAL_CURRENT_PARENT_FROZEN_NATIVE_PREFIX_REQUIRED')
    root=pathlib.Path(root);root.mkdir();(root/'parts').mkdir();review=C.projection_origins(plan)
    book=I.load_data(plan['source_inventory_reference'],2<<20);byfile={r['file_id']:r for r in book['files']}
    fields=I.load_data(plan['field_map_reference'],2<<20);C.need({f['field_id']for f in fields}==set(range(146)),'SAME146_FIELDS_NO_RENUMBERING')
    selected,groups,expected=selected_index(plan,root,members,PREFIX,budget)
    db=sqlite3.connect(root/'numeric_catalog.sqlite');db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA cache_size=-16384')
    db.executescript('CREATE TABLE parts(file INTEGER,lo INTEGER,hi INTEGER,task INTEGER,kind TEXT,ref TEXT,window TEXT,parent TEXT,PRIMARY KEY(file,lo,task));'
      'CREATE TABLE base(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,numbers BLOB,meta TEXT,owner_sha BLOB,usable INTEGER);'
      'CREATE TABLE selected(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,mid TEXT,job INTEGER,role TEXT,owner TEXT,seen INTEGER DEFAULT 0);')
    original=sqlite_ro(selected['path'])
    try:db.executemany('INSERT INTO selected(ordinal,rid,mid,job,role,owner)VALUES(?,?,?,?,?,?)',original.execute('SELECT ordinal,rid,mid,job,role,owner FROM wanted ORDER BY ordinal'));db.commit()
    finally:original.close()
    cfg=dict(plan,data_references=C.unique([*plan['data_references'],selected]))
    stats=collections.defaultdict(collections.Counter);oldparts=[];base_rows=task_rows=0
    iterator=iter(tasks(plan,budget,review,byfile));finished=False
    def merge(r):
        nonlocal base_rows,task_rows
        update_seen(db,r['seen'])
        if r['base']:db.executemany('INSERT INTO base VALUES(?,?,?,?,?,?)',r['base']);base_rows+=len(r['base'])
        if r['row_kind']=='task':task_rows+=r['kept']
        for fid,counters in r['field_stats'].items():stats[fid].update(counters)
        oldparts.append(r['old_part'])
        if r['out']is not None:
            out=r['out'];I.allow(out['reference']);db.execute('INSERT INTO parts VALUES(?,?,?,?,?,?,?,?)',(r['file_id'],r['lo'],r['hi'],r['task_code'],r['row_kind'],
              K.canonical(out['reference']).decode(),K.canonical(r['old_part']['window_reference']).decode(),K.canonical(r['old_part']['manifest_reference']).decode()))
        db.commit()
    try:
        with cf.ProcessPoolExecutor(max_workers=16,mp_context=mp.get_context('spawn'),initializer=initialize,initargs=(cfg,selected,str(root)))as pool:
            while not finished:
                # Full original census occurs with no part writers running.
                budget.check();used=I.unique_bytes(budget.root)
                capacity=min(32,(plan['whole_output_cap_bytes']-used-(256<<20))//plan['typed_part_cap_bytes'])
                if capacity<=0:
                    I.R.mark_stop('FAST55K_BOUNDED_PART_ADMISSION_CAP',{'used':used,'whole_cap':plan['whole_output_cap_bytes']})
                    raise ValueError('SOFT_RESOURCE_STOP_FAST55K_NO_BOUNDED_PART_RESERVATION')
                wave=[]
                while len(wave)<capacity and not finished:
                    try:task=next(iterator)
                    except StopIteration:finished=True;break
                    wave.append(task)
                pending={pool.submit(part,task):task['sequence']for task in wave}
                cf.wait(pending,return_when=cf.ALL_COMPLETED)
                results=[]
                for future,key in pending.items():
                    r=future.result();C.need(r['sequence']==key,'EXACT_PART_WORKER_IDENTITY');results.append(r)
                budget.check()
                for r in sorted(results,key=lambda r:r['sequence']):budget.check();merge(r)
        C.need(finished,'NO_MISSING_PARALLEL_PART_RETURN_OR_UNMERGED_RESULT')
        complete_mass(db,expected,base_rows,task_rows,stats)
        holds=V.quality_fields(stats,active_field_ids=plan['field_scope']['active_field_ids'])
        lineage=I.save(root/'original_part_lineage.DATA.json',{'parts':oldparts})
        origin=I.save(root/'current_parent_typed_origin.json',{'schema':'CURRENT_PARENT_SELECTED_TYPED_ORIGIN_V1','status':'ACTUAL_CLOSED_SUBSET_WITHIN_PARENT_NOT_CHILD_C0',
          'job_id':str(proof['job_id']),'Root_projection_review_reference':plan['projection_origin_review_reference'],'original_part_lineage_reference':lineage,
          'original_failed_timeout_states_preserved':True,'full_Common_D4_D5_D3_D6_release':False})
        db.execute('UPDATE parts SET parent=?',(K.canonical(origin).decode(),));db.commit();db.close();db=None
        catalog=I.allow(I.pin(root/'numeric_catalog.sqlite'))
        report={'schema':'BOUNDED_COMPLETE_SPRIME_TYPED_COVERAGE_V1','status':'EXACT_NUMERIC_SOURCE_COVERAGE_NOT_FINAL_MASKS','mode':'bounded_pilot55k',
          'job_id':str(proof['job_id']),'records':expected,'molecules':55000,'task_rows':task_rows,'base_rows':base_rows,
          'field_stats':{k:dict(v)for k,v in stats.items()},'selected_group_record_counts':dict(groups),'quality_hold_fields':holds,'errors':[],
          'original_projection_origins':review['projection_origins'],'old_parent_states_and_costs_unchanged':True,'old_FAILED_or_TIMEOUT_not_promoted':True,
          'all14task_and_base_exact_once':True,'original_values_masks_None_IEEE_bits_and_indices_unchanged':True,
          'original_source_full_population_counts':C.GLOBAL_SOURCE_COUNTS,'full_Common_or_D4_D5_D3_D6_release':False,'parts_catalog':catalog,'base_index':catalog,
          'current_parent_typed_origin_reference':origin,'original_part_lineage_reference':lineage,'fast_IO_not_new_science':True,'workers':16,'source_batch_rows':BATCH_ROWS}
        for key in('canonical_index','field_map_reference','logical_group_plan_reference','source_inventory_reference'):report[key]=plan[key]
        return I.save(root/'manifest.json',report),report,oldparts
    finally:
        if db is not None:db.close()
