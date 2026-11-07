"""Read-only terminal stage adoption; original native/child/math objects unchanged."""
import collections,hashlib,json,os,pathlib,sqlite3,struct,types
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_native_pilot_day_v1 import geometry as N
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I,coverage as V,eligibility as E
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import sqlite_ro,identity,lookup_batch
Wire=N.Wire;WORKER=N.WORKER;schema_header=N.schema_header;cohort=N.cohort;ResourceBudget=N.ResourceBudget
metadata_children=N.metadata_children
CONTEXT={}

# Reader IO memo only. Original algorithms and batch_size=1 remain verbatim.
import copy,stat,sys
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import reader as ORIGINAL_READER,statistics as ORIGINAL_STATISTICS
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1 import support as OWNER_SOURCE
MEMO_BYTES=64<<20
MEMO_ENTRIES=65536
BASE_SQL='SELECT numbers,owner_sha,usable,meta FROM base WHERE ordinal=?'
ELIGIBILITY_SQL='SELECT rid,mid,job,source_role,effective_role,common_population,geometry_id,parent_geometry_id,fit_eligible,fit_reason FROM eligibility WHERE ordinal=?'
OWNER_SQL='SELECT '+','.join(OWNER_SOURCE.RECORD_COLUMNS)+' FROM records WHERE record_id IN (?)'

def memo_size(value,seen=None):
    seen=set()if seen is None else seen
    if id(value)in seen:return 0
    seen.add(id(value));size=sys.getsizeof(value)
    if isinstance(value,dict):size+=sum(memo_size(k,seen)+memo_size(v,seen)for k,v in value.items())
    elif isinstance(value,(tuple,list)):size+=sum(memo_size(v,seen)for v in value)
    return size

class ReaderMemo:
    def __init__(self,cap=MEMO_BYTES,entries=MEMO_ENTRIES):
        self.cap=cap;self.entry_cap=entries;self.values={};self.used=0;self.context=None;self.lookup_paths={};self.metrics=collections.Counter()
    def get(self,key):
        if key not in self.values:self.metrics['cache_misses']+=1;return None
        self.metrics['cache_hits']+=1;return copy.deepcopy(self.values[key])
    def put(self,key,value):
        if key in self.values:return
        owned=copy.deepcopy(value);charge=memo_size((key,owned))+256
        if len(self.values)>=self.entry_cap or self.used+charge>self.cap:self.metrics['bounded_cap_misses']+=1;return
        self.values[key]=owned;self.used+=charge;self.metrics['peak_charged_bytes']=max(self.metrics['peak_charged_bytes'],self.used)
    def reset(self,context):
        self.values.clear();self.used=0;self.context=context;self.metrics['context_resets']+=1

def reader_frame(path):
    path=pathlib.Path(path);C.need(not any(p.is_symlink()for p in(path,*path.parents)),'MEMO_NO_SYMLINK')
    def fields(s):return(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)
    with path.open('rb')as stream:
        before=os.fstat(stream.fileno());C.need(stat.S_ISREG(before.st_mode)and before.st_uid==1278 and before.st_nlink==1,'MEMO_REGULAR_SINGLE_LINK_ACTUAL_UID')
        result=fields(before);C.need(result==fields(os.fstat(stream.fileno()))==fields(path.lstat()),'MEMO_CURRENT_FD_AND_PATH_FRAME_STABLE')
    return result

class ReaderMemoIO:
    def __init__(self,memo,original=I):self.memo=memo;self.original=original
    def __getattr__(self,name):return getattr(self.original,name)
    def require(self,reference,content=True):
        if not content:return self.original.require(reference,content=False)
        r=C.reference(reference,source=reference.get('bytes')==0);key=('whole_SHA',r['path'],r['bytes'],r['sha256'])
        admitted=self.original.require(r,content=False)
        before=reader_frame(admitted);known=self.memo.get(key)
        if known==before:
            path=self.original.require(r,content=False)
            C.need(reader_frame(path)==before,'MEMO_SAME_VERIFIED_SHA_FRAME_BEFORE_AND_AFTER_USE')
            self.memo.metrics['whole_SHA_frame_hits']+=1;return path
        # A changed frame never receives a cache credit: original whole SHA runs.
        self.memo.metrics['original_whole_SHA_calls']+=1;path=self.original.require(r,content=True)
        after=reader_frame(path);C.need(before==after,'MEMO_FIRST_WHOLE_SHA_STABLE_SURROUNDING_FRAME')
        if known is not None:
            self.memo.values.pop(key,None);self.memo.used=sum(memo_size((k,v))+256 for k,v in self.memo.values.items())
        self.memo.put(key,after);return path
    def load_data(self,reference,maximum=64<<20):
        function=private_reader_function(self.original.load_data,require=self.require)
        return function(reference,maximum)

class MemoRows:
    def __init__(self,rows):self.rows=copy.deepcopy(rows);self.position=0
    def fetchone(self):
        if self.position>=len(self.rows):return None
        row=copy.deepcopy(self.rows[self.position]);self.position+=1;return row
    def fetchall(self):
        result=copy.deepcopy(self.rows[self.position:]);self.position=len(self.rows);return result
    def __iter__(self):return self
    def __next__(self):
        row=self.fetchone()
        if row is None:raise StopIteration
        return row

class MemoSQLite:
    def __init__(self,original,kind,signature,memo):self.original=original;self.kind=kind;self.signature=signature;self.memo=memo
    def __getattr__(self,name):return getattr(self.original,name)
    def execute(self,sql,parameters=()):
        expected={'canonical':OWNER_SQL,'eligibility':ELIGIBILITY_SQL,'catalog':BASE_SQL}[self.kind]
        args=tuple(parameters)
        if sql!=expected or len(args)!=1:return self.original.execute(sql,parameters)
        # Only exact original single-RID/ordinal read queries are memoized.
        if self.kind=='canonical':eligible=type(args[0])is str
        else:eligible=type(args[0])is int and args[0]>=0
        if not eligible:return self.original.execute(sql,parameters)
        key=('SQL',self.kind,self.signature,sql,args);rows=self.memo.get(key)
        if rows is not None:self.memo.metrics['SQL_result_hits']+=1;return MemoRows(rows)
        self.memo.metrics['original_SQL_queries']+=1;rows=self.original.execute(sql,parameters).fetchall()
        self.memo.put(key,rows);return MemoRows(rows)

_READER_MEMO=None
def reader_memo():
    global _READER_MEMO
    if _READER_MEMO is None:_READER_MEMO=ReaderMemo()
    return _READER_MEMO

def memo_sqlite_ro(path):
    memo=reader_memo();original=ORIGINAL_READER.sqlite_ro(path);binding=memo.lookup_paths.get(str(pathlib.Path(path)))
    return original if binding is None else MemoSQLite(original,binding[0],binding[1],memo)

def private_reader_function(original,**bindings):
    g=dict(original.__globals__);g.update(bindings)
    result=types.FunctionType(original.__code__,g,original.__name__,original.__defaults__,original.__closure__)
    result.__kwdefaults__=original.__kwdefaults__;return result

def reader_functions(memo):
    io=ReaderMemoIO(memo)
    part=private_reader_function(ORIGINAL_READER.one_part,I=io)
    records=private_reader_function(ORIGINAL_READER.records,I=io,one_part=part,sqlite_ro=memo_sqlite_ro)
    observations=private_reader_function(ORIGINAL_READER.observations,records=records)
    return io,part,records,observations

def memo_group_begin(cfg):
    memo=reader_memo();coverage=I.load_data(cfg['coverage_reference'],8<<20)
    refs={'canonical':cfg['canonical_index'],'eligibility':cfg['eligibility_reference'],'catalog':coverage['parts_catalog']}
    for ref in refs.values():I.require(ref,content=False)
    frames={kind:reader_frame(ref['path'])for kind,ref in refs.items()}
    context=(tuple((kind,tuple(sorted(ref.items())),frames[kind])for kind,ref in sorted(refs.items())),
      tuple((key,tuple(sorted(cfg[key].items())))for key in('coverage_reference','field_map_reference','source_inventory_reference','logical_group_plan_reference')))
    if context!=memo.context:memo.reset(context)
    memo.lookup_paths={r['path']:(kind,(tuple(sorted(r.items())),frames[kind]))for kind,r in refs.items()}
    io=ReaderMemoIO(memo)
    for ref in refs.values():io.require(ref)
    return refs,frames

def memo_group_end(refs,frames):
    C.need(all(reader_frame(ref['path'])==frames[kind]for kind,ref in refs.items()),'MEMO_GROUP_LOOKUP_FD_SIZE_TIME_UID_MODE_LINK_FRAME_UNCHANGED')

def memo_day_group(item):
    cfg,stage,root,group,first=item;memo=reader_memo();io,part,records,observations=reader_functions(memo)
    initialize=private_reader_function(ORIGINAL_STATISTICS.initialize,I=io)
    initialize(cfg,stage,root,ORIGINAL_STATISTICS.BARRIER);refs,frames=memo_group_begin(cfg);before=dict(memo.metrics)
    body=private_reader_function(ORIGINAL_STATISTICS._group_pass,observations=observations)
    guarded=private_reader_function(ORIGINAL_STATISTICS.group_pass,_group_pass=body)
    try:return guarded((group,first))
    finally:
        memo_group_end(refs,frames)
        # Optional, bounded operational metrics; never included in numeric replay.
        metrics={'schema':'NATIVE_RESUME_READER_IO_MEMO_GROUP_V1','pid':os.getpid(),'group_index':group['group_index'],
          'cap_bytes':memo.cap,'entry_cap':memo.entry_cap,'charged_bytes':memo.used,'entries':len(memo.values),
          'metrics_delta':{k:v-before.get(k,0)for k,v in memo.metrics.items()},'original_numeric_functions_and_batch1_unchanged':True}
        raw=K.canonical(metrics);C.need(len(raw)<=4096,'BOUNDED_READER_MEMO_OPERATIONAL_METRICS')
        I.save(pathlib.Path(root)/('reader_io_memo_group_%04d.json'%group['group_index']),metrics)

class StatisticsMemo:
    def __init__(self):self.original=ORIGINAL_STATISTICS;self.PROGRESS_CALLBACK=None;self.B=ORIGINAL_STATISTICS.B
    def __getattr__(self,name):return getattr(self.original,name)
    def execute(self,cfg,proof,root,gate,pool):
        memo=reader_memo();io=ReaderMemoIO(memo);refs,frames=memo_group_begin(cfg)
        dispatch=private_reader_function(self.original.dispatch_groups,day_group=memo_day_group,PROGRESS_CALLBACK=self.PROGRESS_CALLBACK)
        function=private_reader_function(self.original.execute,I=io,dispatch_groups=dispatch)
        try:return function(cfg,proof,root,gate,pool)
        finally:memo_group_end(refs,frames)

STATISTICS=StatisticsMemo()

def positive_job(value):
    if type(value)is int:C.need(value>0,'POSITIVE_CANONICAL_JOB_ID');return value
    C.need(type(value)is str and value.isascii() and value.isdecimal() and value and value[0]!='0','EXACT_SQLITE_DECIMAL_POSITIVE_JOB_NOT_BOOL_FLOAT_OR_ALIAS')
    result=int(value);C.need(result>0 and str(result)==value,'CANONICAL_POSITIVE_JOB_DECIMAL');return result

def adopted_file(path,root):
    path=pathlib.Path(path);root=pathlib.Path(root)
    C.need(root in path.parents and not any(q.is_symlink()for q in (path,*path.parents)),'ONLY_FIXED_REGISTERED_TERMINAL_STAGE_REAL_FILES')
    ref=I.pin(path);I.allow(ref,origin=root);I.require(ref);return ref

def prepare(plan,proof,root,budget):
    review,old,oldproof=C.resume_authority(plan);oldroot=pathlib.Path(old['output_directory']);a=review['parent_registration']
    old_receipt_ref=adopted_file(review['deferred_stage_locators']['receipt'],oldroot)
    receipt=I.load_data(old_receipt_ref,8<<20)
    C.need(str(receipt['job_id'])==str(oldproof['job_id']) and receipt['schema']=='EXISTING_SPRIME_NATIVE_PILOT_DAY_RECEIPT_V1'
      and receipt['plan_reference']==a['plan_reference'] and receipt['startup_proof_reference']==a['proof_reference']
      and receipt['full_Common_D2_D3_D4_D5_D6_release']is False,'REAL_OLD_RECEIPT_NOT_WHOLE_D4_ACCEPTANCE')
    gate=receipt['fixture_gate'];I.allow(gate,origin=oldroot);old_gate=I.load_data(gate,8<<20)
    C.need(old_gate['status']=='PASS' and old_gate['tests']==6 and old_gate['errors']==old_gate['failures']==0,'ACTUAL_OLD_PARENT_SOURCE6_GATE_NO_STATUS_GUESS')
    prefix_ref=receipt['prefix_reference'];C.need(prefix_ref and prefix_ref['path']==review['deferred_stage_locators']['prefix'],'REAL_CLOSED_PREFIX_REFERENCE_NOT_PREDICTION')
    I.allow(prefix_ref,origin=oldroot);prefix=I.load_data(prefix_ref,8<<20)
    C.need(prefix['schema']=='CURRENT_PARENT_FROZEN_OLD55K_NATIVE_INPUTS_V1' and str(prefix['actual_parent_job_id'])==str(oldproof['job_id'])
      and prefix['no_new_molecule_selection']is True,'EXACT_ALREADY_FROZEN_ORIGINAL55K')
    for key in ('preselection_reference','members_reference','native_catalog_reference'):
        r=prefix[key];I.allow(r,origin=pathlib.Path(r['path']).parent);I.require(r)
    C.need(receipt['coverage_reference'] and receipt['coverage_reference']['path']==review['deferred_stage_locators']['coverage_manifest'],
      'ONLY_ACTUAL_COMPLETE_TYPED_COVERAGE_REFERENCE_NO_PARTIAL_AS_COMPLETE')
    CONTEXT.clear();CONTEXT.update(review=review,old=old,oldproof=oldproof,oldroot=oldroot,receipt=receipt,old_receipt_ref=old_receipt_ref,prefix=prefix,proof=proof)
    report={'schema':'CURRENT_PARENT_READONLY_NATIVE_RESUME_PREFIX_V2','original_prefix_reference':prefix_ref,
      'original_parent_registration':a,'actual_CPU_observed_old_receipt_reference':old_receipt_ref,'original_terminal_state_and_costs_preserved':True,'old_full_D4_complete':False}
    ref=I.save(root/'resume_stage_origin.json',report)
    return prefix_ref,prefix,old,oldproof

def catalogue_digest(db,normalize=False):
    digest=hashlib.sha256();counts={}
    specs=(('parts','file,lo,task'),('base','ordinal'),('selected','ordinal'))
    C.need({r[0]for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}=={x[0]for x in specs},'EXACT_ORIGINAL_THREE_TECHNICAL_TABLES')
    for table,order in specs:
        count=0
        for row in db.execute('SELECT * FROM '+table+' ORDER BY '+order):
            row=list(row)
            if table=='selected':row[3]=positive_job(row[3]) if normalize else row[3]
            digest.update(Wire.encode([table,row]));count+=1
        counts[table]=count
    return digest.hexdigest(),counts

def convert_catalogue(source,target,budget):
    """Copy only technical DB; only selected.job TEXT becomes INTEGER."""
    C.need(not target.exists() and not any(pathlib.Path(str(source)+s).exists()for s in ('-wal','-journal','-shm')),
      'CLOSED_ORIGINAL_CATALOGUE_NO_ACTIVE_SIDECARS_AND_FRESH_TARGET')
    frame=identity(source);before=sqlite_ro(source);destination=sqlite3.connect(target)
    try:
        expected,mass=catalogue_digest(before,True);before.backup(destination)
        destination.execute('PRAGMA synchronous=FULL');destination.execute('ALTER TABLE selected RENAME TO original_selected_text_job')
        destination.execute('CREATE TABLE selected(ordinal INTEGER PRIMARY KEY,rid TEXT UNIQUE,mid TEXT,job INTEGER,role TEXT,owner TEXT,seen INTEGER DEFAULT 0)')
        for ordinal,row in enumerate(before.execute('SELECT * FROM selected ORDER BY ordinal')):
            if ordinal%256==0:budget.check()
            row=list(row);row[3]=positive_job(row[3]);destination.execute('INSERT INTO selected VALUES(?,?,?,?,?,?,?)',row)
        destination.execute('DROP TABLE original_selected_text_job');destination.commit()
        actual,newmass=catalogue_digest(destination)
        C.need((actual,newmass)==(expected,mass) and destination.execute("SELECT count(*)FROM selected WHERE typeof(job)<>'integer' OR job<=0").fetchone()[0]==0,
          'ONLY_JOB_STORAGE_TYPE_CHANGED_ALL_OTHER_ROWS_REFS_BLOB_F64_OWNER_JSON_BITS_UNCHANGED')
        C.need(destination.execute('PRAGMA integrity_check').fetchall()==[('ok',)],'NEW_TECHNICAL_CATALOGUE_INTEGRITY')
    finally:destination.close();before.close();C.need(identity(source)==frame,'ORIGINAL_CATALOGUE_UNCHANGED_AFTER_READONLY_BACKUP')
    return {'semantic_sha256_with_positive_job_normalization':expected,'table_row_counts':mass,'original_SQLite_unchanged':True}

def adopt_coverage(plan,proof,root,budget,members):
    import pyarrow as pa,pyarrow.parquet as pq
    root=pathlib.Path(root);root.mkdir();oldroot=CONTEXT['oldroot'];r=CONTEXT['receipt']['coverage_reference'];I.allow(r,origin=oldroot)
    report=I.load_data(r,8<<20);oldjob=str(CONTEXT['oldproof']['job_id']);expected=sum(m['S_conformers']for m in members.values())
    C.need(report['schema']=='BOUNDED_COMPLETE_SPRIME_TYPED_COVERAGE_V1' and report['status']=='EXACT_NUMERIC_SOURCE_COVERAGE_NOT_FINAL_MASKS'
      and str(report['job_id'])==oldjob and report['records']==report['base_rows']==expected and report['task_rows']==14*expected
      and report['molecules']==55000 and report['all14task_and_base_exact_once']is True and not(report['errors']or report['quality_hold_fields']),
      'COMPLETE_OLD_TYPED_STAGE_ONLY_ORIGINAL_QUALITY_HARD_GATE')
    for key in N.AUTHORITY_KEYS:C.need(report[key]['bytes']==plan[key]['bytes'] and report[key]['sha256']==plan[key]['sha256'],'EXACT_COVERAGE_AUTHORITY_CONTENT:'+key)
    for key in ('parts_catalog','current_parent_typed_origin_reference','original_part_lineage_reference'):
        I.allow(report[key],origin=oldroot);I.require(report[key])
    catalog=I.require(report['parts_catalog']);source=sqlite_ro(catalog);canonical=sqlite_ro(I.require(plan['canonical_index']));owners={};seen={};stats=collections.defaultdict(collections.Counter)
    fields=I.load_data(plan['field_map_reference'],2<<20);byfield={f['field_id']:f for f in fields};base_rows=task_rows=0;mass=collections.Counter();parts=[]
    try:
        batch=[]
        def bind(rows):
            actual=lookup_batch(canonical,[r[1]for r in rows])
            for ordinal,rid,mid,job,role,raw,bits in rows:
                owner=json.loads(raw);C.need(actual.get(rid)==owner and owner['record_ordinal']==ordinal and owner['molecule_id']==mid
                  and owner['new_role']==role and positive_job(job)==owner['job_id'] and mid in members and bits==32767,
                  'SELECTED_TECHNICAL_ROW_EXACT_CANONICAL_OWNER_ROLE_AND_INTEGER_JOB')
                C.need(rid not in owners,'NO_DUPLICATE_SELECTED_RID');owners[rid]=owner;seen[ordinal]=0;mass[mid]+=1
        for row in source.execute('SELECT * FROM selected ORDER BY ordinal'):
            batch.append(row)
            if len(batch)==256:bind(batch);batch=[]
        if batch:bind(batch)
        C.need(len(owners)==expected and set(mass)==set(members) and all(mass[mid]==m['S_conformers']for mid,m in members.items()),'EVERY_FROZEN_MID_ALL_ORIGINAL_RECORDS_NOT_RESELECTED')
        for fid,lo,hi,task,kind,raw,window,parent in source.execute('SELECT * FROM parts ORDER BY file,lo,task'):
            budget.check();pr=json.loads(raw);C.need(pathlib.Path(pr['path']).parent==oldroot/'typed_coverage/parts','ONLY_ORIGINAL_CLOSED_SELECTED_TYPED_PARTS')
            I.allow(pr,origin=oldroot);path=I.require(pr);before=identity(path);src=pq.ParquetFile(path);h=hashlib.sha256();n=0
            try:
                C.need(src.schema_arrow.equals(K.schema(pa),check_metadata=False),'EXACT_ORIGINAL_COMPACT_BINARY_SCHEMA')
                for chunk in src.iter_batches(batch_size=128,use_threads=False):
                    budget.check()
                    for row in chunk.to_pylist():
                        K.validate_row_buffers(row);owner=owners.get(row['record_id']);C.need(owner is not None and K.row_signature(row)==row['view_sha256']
                          and K.owner_signature(owner)==row['owner_sha256'] and owner['record_ordinal']==row['record_ordinal'] and row['file_id']==fid
                          and lo<=row['physical_row']<hi and row['task_code']==task and row['row_kind']==kind
                          and row['role_code']==V.B.ROLES[owner['new_role']] and ((kind=='base'and task==255)or(kind=='task'and type(task)is int and 0<=task<14)),'EXACT_ADOPTED_ROW_OWNER_TASK_SOURCE_AND_F64_BITS')
                        bit=1<<(14 if kind=='base'else task);C.need(not seen[row['record_ordinal']]&bit,'NO_DUPLICATE_ADOPTED_BASE_TASK')
                        seen[row['record_ordinal']]|=bit;h.update(row['view_sha256']);n+=1
                        if kind=='base':
                            base=source.execute('SELECT rid,numbers,meta,owner_sha,usable FROM base WHERE ordinal=?',(row['record_ordinal'],)).fetchone()
                            z=[struct.unpack_from('<q',base[1],i)[0]for i in range(0,len(base[1]),8)]
                            pool=[struct.unpack_from('<d',row['base_f64'],i)[0]for i in range(0,len(row['base_f64']),8)];value=V.B.decode(row['base_json'],pool)
                            C.need(base[0]==row['record_id'] and base[2]==row['base_json'] and base[3]==row['owner_sha256'] and base[4]==1
                              and value['atomic_numbers']==z and len(z)==owner['total_atoms'] and value['geometry_status']=='ORIGINAL_PM7_GEOMETRY',
                              'REAL_CLOSED_BASE_Z_OWNER_SOURCE_F64_AND_GRAPH_PROVENANCE_NOT_RECONSTRUCTED')
                            base_rows+=1
                        else:
                            entries=K.unpack_entries(row,byfield);C.need(V.B.compact.encode(row['record_ordinal'],task,entries)==K.binary_json_loads(row['compact_mask_json']),
                              'UNCHANGED_SOURCE_NEW_REVIEW_REASON_AND_INDICES_MASK_BITS');V.field_counts(stats,entries);task_rows+=1
            finally:src.close();C.need(identity(path)==before,'ORIGINAL_SELECTED_PART_FRAME_STABLE')
            parts.append({'reference':pr,'rows':n,'typed_stream_sha256':h.hexdigest()})
        C.need(base_rows==expected and task_rows==14*expected and all(v==32767 for v in seen.values()) and len(stats)==146,
          'ADOPTED_BASE_PLUS14_TASKS_PER_RECORD_CONSERVATION')
        C.need({str(k):dict(v)for k,v in stats.items()}==report['field_stats'] and V.quality_fields(stats,active_field_ids=plan['field_scope']['active_field_ids'])==[],
          'ORIGINAL146_OWN_DENOMINATORS_AND_ONE_PERCENT_QA_RECOMPUTED_NO_WAIVER')
    finally:source.close();canonical.close()
    conversion=convert_catalogue(catalog,root/'numeric_catalog.sqlite',budget);new_catalog=I.allow(I.pin(root/'numeric_catalog.sqlite'))
    lineage=I.save(root/'readonly_adoption.DATA.json',{'original_coverage_reference':r,'original_catalog_reference':report['parts_catalog'],
      'conversion':conversion,'parts':parts,'actual_terminal_parent_registration':CONTEXT['review']['parent_registration'],'actual_CPU_observed_old_receipt_reference':CONTEXT['old_receipt_ref'],'new_actual_parent_job_id':str(proof['job_id']),
      'old_parent_not_D4_complete':True,'no_original_typed_parts_copied_or_changed':True})
    result=dict(report,parts_catalog=new_catalog,base_index=new_catalog,original_coverage_reference=r,original_parts_output_root=str(oldroot/'typed_coverage'),
      new_current_parent_technical_adoption_job_id=str(proof['job_id']),technical_adoption_reference=lineage,job_id=str(proof['job_id']),original_actual_parent_job_id=oldjob)
    ref=I.save(root/'manifest.json',result);return ref,result,[]

class Coverage:
    build=staticmethod(adopt_coverage)
COVERAGE=Coverage()

def build(plan,proof,root,budget,prefix,old,oldproof,members):
    """Validate closed original packets/tables; never invoke native compute/read."""
    import duckdb,numpy as np,pyarrow as pa,pyarrow.parquet as pq
    original=pathlib.Path(CONTEXT['review']['deferred_stage_locators']['ordinary_root']);root=pathlib.Path(root);root.mkdir()
    kinds=('geometries','orders','atom_counts','audit_identity','roster');schemas=Wire.schemas();tables={k:adopted_file(original/(k+'.parquet'),CONTEXT['oldroot'])for k in kinds}
    features=adopted_file(original/'bias_features.parquet',CONTEXT['oldroot']);actual={};counts={}
    feature_schema=pa.schema([('molecule_id',pa.string()),('elements_atomic_numbers',pa.list_(pa.int64())),('heavy_atoms',pa.int64()),
      ('rotatable_bonds',pa.int64()),('rings',pa.int64()),('generic_scaffold',pa.string()),('scaffold_status',pa.string())]);schemas['bias_features']=feature_schema
    for kind,ref in [*tables.items(),('bias_features',features)]:
        path=I.require(ref);frame=identity(path);source=pq.ParquetFile(path);h=hashlib.sha256();n=0
        try:
            C.need(source.schema_arrow.equals(schemas[kind],check_metadata=False),'EXACT_CLOSED_ORIGINAL_GEOMETRY_TABLE_SCHEMA:'+kind)
            for batch in source.iter_batches(batch_size=256,use_threads=False):
                budget.check()
                for row in batch.to_pylist():h.update(Wire.encode(row));n+=1
        finally:source.close();C.need(identity(path)==frame,'CLOSED_ORDINARY_TABLE_CURRENT_FRAME_STABLE')
        actual[kind]=h.hexdigest();counts[kind]=n
    expected={k:hashlib.sha256()for k in schemas if k in (*kinds,'bias_features')};mass=collections.Counter();refs=[];geometry_ids=set()
    native_path=I.require(prefix['native_catalog_reference']);native_frame=identity(native_path);native=duckdb.connect(str(native_path),read_only=True)
    def add(kind,rows):
        for row in rows:
            converted=pa.Table.from_pylist([row],schema=schemas[kind]).to_pylist()[0];expected[kind].update(Wire.encode(converted));mass[kind]+=1
    try:
        for ordinal,mid in enumerate(sorted(members)):
            budget.check();path=original/'molecules'/(hashlib.sha256(mid.encode()).hexdigest()+'.lossless.json');r=adopted_file(path,CONTEXT['oldroot'])
            C.need(0<r['bytes']<=64<<20,'ORIGINAL_COMPLETE_MOLECULE_PACKET_64MIB_SOFTWARE_BOUND')
            packet=Wire.decode(I.require(r).read_bytes());member=members[mid]
            C.need(packet['schema']=='PROVISIONAL55K_DIRECT_NATIVE_NO_CACHE_MOLECULE_V1' and packet['molecule_id']==mid
              and packet['pm7_count']==packet['uff_sprime_count']==member['S_conformers']==member['Sprime_conformers']
              and packet['new_QM_UFF_RMSD_HOF_calls']==0 and packet['three_orders_or_D7_complete']is False,'ACTUAL_ALL_N_CLOSED_PACKET_NOT_PARTIAL')
            pointers={r['record_id']:r for r in native.execute('SELECT * FROM native55k WHERE molecule_id=? ORDER BY record_id',[mid]).fetch_arrow_table().to_pylist()}
            pm7=[b for b in packet['bases']if b['geometry_source']=='pm7'];uff=[b for b in packet['bases']if b['geometry_source']=='uff_sprime']
            C.need(len(pm7)==len(uff)==member['S_conformers'] and {b['native_record_id']for b in pm7}==set(pointers),'EXACT_NATIVE_RECORD_AND_ORIGINAL_UFF_COUNTS')
            first_atoms=packet['bases'][0]['atomic_numbers'];C.need(all(b['atomic_numbers']==first_atoms for b in packet['bases']),'EXACT_ORIGINAL_FIXED_ATOM_SEQUENCE_ACROSS_ALL_NATIVE_AND_UFF')
            C.need(len({b['native_anchor_record_id']for b in uff})==1,'UNCHANGED_SINGLE_NATIVE_UFF_ANCHOR')
            for row in packet['bases']:
                N.OLD.Geometry.physical_key(row);z=np.asarray(row['atomic_numbers'],dtype='<i8');xyz=np.asarray(row['positions_A'],dtype='<f8')
                C.need(len(z)>0 and all(1<=int(v)<=118 for v in z) and xyz.shape==(len(z),3) and np.isfinite(xyz).all()
                  and hashlib.sha256(z.tobytes()).hexdigest()==row['atom_order_sha256']
                  and N.OLD.OriginalWorker.IO.geometry_sha(z,xyz)==row['geometry_sha256'] and row['geometry_id']not in geometry_ids
                  and row['parent_geometry_id']is None and row['molecule_id']==mid,'ORIGINAL_FIXED_ATOM_F64_GEOMETRY_SHA_AND_ID')
                geometry_ids.add(row['geometry_id'])
                if row['geometry_source']=='pm7':
                    pointer=pointers[row['native_record_id']];C.need(json.loads(row['source_provenance_json'])==pointer
                      and row['source_path']==pointer['source_path'] and row['source_row_index']==pointer['real_index']
                      and row['actual_input_origin']=='ACTUAL_NATIVE_PAYLOAD_SHA_GRAPH_F64','EXACT_ORIGINAL_PAYLOAD_GRAPH_VALIDATION_PROVENANCE_NO_NEW_NATIVE_READ')
                else:
                    provenance=json.loads(row['source_provenance_json']);C.need(row['geometry_id']==N.gid('uff_sprime',mid,row['sprime_conf_idx'])
                      and row['native_anchor_record_id']in pointers and provenance['source']['path']==row['source_path']
                      and provenance['source']['bytes']==row['source_bytes'] and provenance['source']['sha256']==row['source_sha256']
                      and provenance['physical_row']==row['source_row_index'],'EXACT_OLD_UFF_GRAPH_STEREO_SOURCE_AND_PHYSICAL_ID_PROVENANCE')
            C.need(all(b['geometry_id']==N.gid('pm7',mid,b['native_record_id'])for b in pm7),'NO_NATIVE_RENUMBER_OR_CLONE')
            for source in ('pm7','uff_sprime'):
                baseids={b['geometry_id']for b in packet['bases']if b['geometry_source']==source};orders=[v for v in packet['orders']if v['geometry_source']==source]
                C.need(len(orders)==len(baseids) and {v['geometry_id']for v in orders}==baseids and [v['rank']for v in orders]==list(range(len(orders)))
                  and all(v['order_type']==v['method']=='fixed_random' and v['molecule_id']==mid for v in orders),'COMPLETE_ORIGINAL_RANDOM_PERMUTATION_NOT_REORDERED')
            add('geometries',packet['bases']);add('orders',packet['orders']);add('atom_counts',({'geometry_id':b['geometry_id'],'n_atoms':len(b['atomic_numbers'])}for b in packet['bases']))
            add('audit_identity',({'molecule_id':mid,'geometry_id':b['geometry_id'],'physical_identity_json':json.dumps({'namespace':'accepted_original_sprime','source_conformer_id':b['sprime_conf_idx']},sort_keys=True)}for b in uff))
            add('roster',[{'logical_ordinal':ordinal,'molecule_id':mid,'PM7_N':len(pm7),'UFF_N':len(uff),'child_count':0}]);add('bias_features',[packet['bias_features']]);refs.append(r)
    finally:native.close();C.need(identity(native_path)==native_frame,'OLD_NATIVE_POINTER_CATALOGUE_READONLY_FRAME_STABLE')
    C.need({p.name for p in (original/'molecules').iterdir()}=={hashlib.sha256(mid.encode()).hexdigest()+'.lossless.json'for mid in members},'EXACT55000_FIXED_PACKET_SET_NO_PARTIAL_OR_ORPHAN_ACCEPTANCE')
    C.need(len(refs)==55000 and all(expected[k].hexdigest()==actual[k]and mass[k]==counts[k]for k in expected),
      'ALL_55000_ORIGINAL_PACKETS_AND_SIX_TABLES_BIDIRECTIONAL_F64_SCHEMA_ORDER_AND_MASS_EQUAL')
    result={'schema':'PROVISIONAL_NATIVE55K_FIXED_RANDOM_BASE_GEOMETRIES_V1','table_references':tables,'molecules':55000,'actual_parent_job_id':str(proof['job_id']),
      'bias_features_reference':features,'new_PM7_RMSD_recomputed':False,'new_QM_UFF_calls':0,'ordinary_base_N_preserved':True,'N1_second_UFF_not_created':True,
      'source_worker_report_references':refs,'D5_full_guide_nested_geometry_coverage':False,'available_orders':['fixed_random'],'full_three_order':False,'D7':False,
      'three_orders_or_D7_complete':False,'PM7_HOF_RMSD_cache_required':False,'final_Common':False,
      'readonly_terminal_ordinary_adoption':{'actual_parent_registration':CONTEXT['review']['parent_registration'],'observed_whole_SHA_references_not_claimed_as_old_manifest':True,
        'all_original_table_packet_semantic_sha256':actual,'new_native_compute_or_payload_read':False,'original_graph_stereo_validation_inherited_exact_Source_proof':True}}
    I.save(root/'ordinary_adoption_manifest.DATA.json',result);return result

class SchemaConnection:
    def __init__(self,original):self.original=original
    def __getattr__(self,name):return getattr(self.original,name)
    def executescript(self,sql):
        old='mid TEXT,job TEXT,source_role TEXT';new='mid TEXT,job INTEGER,source_role TEXT'
        C.need(sql.count(old)==1,'EXACT_ORIGINAL_ELIGIBILITY_DDL_ONLY_JOB_INTEGER_IO_CHANGE')
        return self.original.executescript(sql.replace(old,new))
class SQLiteSchema:
    def connect(self,*args,**kwargs):return SchemaConnection(sqlite3.connect(*args,**kwargs))
    def __getattr__(self,name):return getattr(sqlite3,name)
def eligibility_function():
    old=E.build;g=dict(old.__globals__);g['sqlite3']=SQLiteSchema();f=types.FunctionType(old.__code__,g,old.__name__,old.__defaults__,old.__closure__)
    f.__kwdefaults__=old.__kwdefaults__;return f
class Eligibility:
    lookup=staticmethod(E.lookup)
    @staticmethod
    def build(*args,**kwargs):
        result=eligibility_function()(*args,**kwargs);manifest=I.load_data(result,8<<20);db=sqlite_ro(I.require(manifest['eligibility_reference']))
        try:C.need(db.execute("SELECT count(*)FROM eligibility WHERE typeof(job)<>'integer'OR job<=0").fetchone()[0]==0,'ACTUAL_NEW_ELIGIBILITY_ON_DISK_POSITIVE_INTEGER_FOR_ALL_CONSUMERS')
        finally:db.close()
        return result
ELIGIBILITY=Eligibility()
