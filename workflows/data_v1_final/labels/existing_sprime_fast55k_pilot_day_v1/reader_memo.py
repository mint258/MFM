"""Verbatim frozen ReaderMemo IO/INTEGER helpers, isolated in Fast10."""
import collections,os,pathlib,sqlite3,types
from . import contract as C
from workflows.data_v1_final.labels.existing_sprime_pilot_day_v1 import io as I,eligibility as E
from workflows.data_v1_final.labels.normalization_compact_runtime_v3 import codec as K
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import sqlite_ro,identity
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
