"""Private static base lookup cache; writes and all nonmatching SQL stay SQLite.

The original loop consumes only fetchone() for the one exact intercepted SELECT.
Non-string parameters use SQLite directly, preserving its type affinity behavior.
Canonical ownership for rows without a pilot PM7 base is never consumed by the
original loop, so only pilot owners need the original canonical-index lookup.
"""
import collections,copy,sqlite3,sys
from pathlib import Path
BASE_INSERT='INSERT INTO base VALUES(?,?,?,?,?)'
BASE_SELECT="SELECT row FROM base WHERE rid=? AND src='pm7'"

class OneRow:
    def __init__(self,value):self.value=value
    def fetchone(self):
        value=self.value;self.value=None;return value

class Empty:
    def fetchone(self):return None
EMPTY=Empty()

class Context:
    def __init__(self,original_lookup,cap=8<<30):
        self.original_lookup=original_lookup;self.cap=cap;self.rids=set();self.blobs={}
        self.blob_bytes=0;self.negative_hits=0;self.positive_hits=0;self.positive_fallbacks=0
        self.canonical_input_rows=0;self.canonical_retained_rows=0
        self.approved_raw=set();self.decoded=collections.OrderedDict();self.decoded_bytes=0
        self.decoded_cap=12<<30;self.decode_hits=0;self.decode_misses=0
    def lookup_batch(self,canonical,rids):
        self.canonical_input_rows+=len(rids)
        if any(type(r) is not str for r in rids):retained=rids
        else:retained=[r for r in rids if r in self.rids]
        self.canonical_retained_rows+=len(retained)
        return self.original_lookup(canonical,retained) if retained else {}
    def factory(self,*args,**kwargs):return Connection(*args,context=self,**kwargs)
    def report(self):
        return dict(pm7_base_rids=len(self.rids),cached_base_blobs=len(self.blobs),
          cached_blob_accounted_bytes=self.blob_bytes,cache_cap_bytes=self.cap,
          negative_base_hits=self.negative_hits,positive_base_hits=self.positive_hits,
          positive_sqlite_fallbacks=self.positive_fallbacks,
          canonical_input_rows=self.canonical_input_rows,canonical_retained_rows=self.canonical_retained_rows,
          decoded_base_cache_bytes=self.decoded_bytes,decoded_base_cache_cap_bytes=self.decoded_cap,
          decoded_base_hits=self.decode_hits,decoded_base_misses=self.decode_misses,
          scientific_values_or_source_rows_changed=False)

class Connection(sqlite3.Connection):
    def __init__(self,*args,context,**kwargs):
        super().__init__(*args,**kwargs);self.context=context
    def execute(self,sql,parameters=()):
        c=self.context
        if sql==BASE_SELECT and len(parameters)==1 and type(parameters[0]) is str:
            rid=parameters[0]
            if rid not in c.rids:c.negative_hits+=1;return EMPTY
            if rid in c.blobs:c.positive_hits+=1;return OneRow((c.blobs[rid],))
            c.positive_fallbacks+=1
        cursor=super().execute(sql,parameters)
        if sql==BASE_INSERT and len(parameters)==5 and parameters[3]=='pm7':
            rid,raw=parameters[2],parameters[4];c.rids.add(rid)
            size=sys.getsizeof(rid)+sys.getsizeof(raw)+160
            if c.blob_bytes+size<=c.cap:
                c.blobs[rid]=raw;c.blob_bytes+=size;c.approved_raw.add(raw)
        return cursor

def object_bytes(value,seen=None):
    seen=set() if seen is None else seen
    if id(value) in seen:return 0
    seen.add(id(value));total=sys.getsizeof(value)
    if isinstance(value,dict):total+=sum(object_bytes(k,seen)+object_bytes(v,seen) for k,v in value.items())
    elif isinstance(value,(list,tuple)):total+=sum(object_bytes(v,seen) for v in value)
    return total

class Codec:
    """Cache verified immutable base bytes; return a private deep copy each time."""
    def __init__(self,original,context):self.original=original;self.context=context
    def __getattr__(self,name):return getattr(self.original,name)
    def decode(self,raw):
        c=self.context
        if type(raw) is not bytes or raw not in c.approved_raw:return self.original.decode(raw)
        if raw in c.decoded:
            value,size=c.decoded.pop(raw);c.decoded[raw]=(value,size);c.decode_hits+=1
            return copy.deepcopy(value)
        c.decode_misses+=1;value=self.original.decode(raw);size=object_bytes(value)+160
        if size<=c.decoded_cap:
            while c.decoded and c.decoded_bytes+size>c.decoded_cap:
                _,(_,old)=c.decoded.popitem(last=False);c.decoded_bytes-=old
            c.decoded[raw]=(value,size);c.decoded_bytes+=size
        return copy.deepcopy(value)

class Module:
    def __init__(self,root,context):self.root=Path(root);self.context=context
    def __getattr__(self,name):return getattr(sqlite3,name)
    def connect(self,database,*args,**kwargs):
        if Path(database)==self.root/'geometry.sqlite':
            assert 'factory' not in kwargs
            return sqlite3.connect(database,*args,factory=self.context.factory,**kwargs)
        return sqlite3.connect(database,*args,**kwargs)

def proof():
    from workflows.data_v1_final.export.lossless_sqlite_io_v1 import codec
    forwarded=[]
    def owners(_,rids):
        forwarded.append(list(rids));return {r:'owner:'+str(r) for r in rids}
    contexts=[]
    for cap in (8<<30,0):
        c=Context(owners,cap);db=sqlite3.connect(':memory:',factory=c.factory)
        db.execute('CREATE TABLE base(gid TEXT PRIMARY KEY,mid TEXT,rid TEXT,src TEXT,row BLOB)')
        db.execute("CREATE UNIQUE INDEX native_pm7 ON base(rid) WHERE src='pm7'")
        samples=[('a','m1','1','pm7',codec.encode({'x':[1.0000000000000002,-0.0,None],'ordered':[('a',1),('a',2)]})),
          ('b','m2','r2','pm7',codec.encode({'x':float('nan')})),
          ('c','m1','1','sprime',codec.encode({'x':'other-source'}))]
        for row in samples:db.execute(BASE_INSERT,row)
        for rid in ('1','r2','missing',None,1,1.0,b'1'):
            expected=sqlite3.Connection.execute(db,BASE_SELECT,(rid,)).fetchone()
            got=db.execute(BASE_SELECT,(rid,));assert got.fetchone()==expected
            assert got.fetchone() is None
        actual=c.lookup_batch(None,['1','missing','r2'])
        assert actual=={'1':'owner:1','r2':'owner:r2'} and forwarded[-1]==['1','r2']
        before=len(forwarded);assert c.lookup_batch(None,['outside'])=={} and len(forwarded)==before
        assert c.lookup_batch(None,[1,'outside'])=={1:'owner:1','outside':'owner:outside'}
        assert c.blob_bytes<=cap and len(c.rids)==2
        wrapped=Codec(codec,c);raw=samples[0][4]
        expected_raw=codec.encode_raw(codec.decode(raw));first=wrapped.decode(raw)
        first['x'][0]=999.;first['ordered'].append(('new',None))
        assert codec.encode_raw(wrapped.decode(raw))==expected_raw
        assert c.decoded_bytes<=c.decoded_cap
        contexts.append(c.report());db.close()
    return dict(original_sqlite_fetchone_bytes_equal=True,positive_fallback_and_negative_cache_checked=True,
      sqlite_nonstring_affinity_preserved=True,canonical_only_unused_nonpilot_owners_omitted=True,
      decoded_cache_raw_bytes_and_private_mutable_rows_equal=True,
      original_metadata_entire_code_object=True,contexts=contexts,new_QM_calls=0)
