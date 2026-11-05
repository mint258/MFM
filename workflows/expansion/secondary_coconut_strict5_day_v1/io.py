"""Actual allocation FD/SHA IO; bounded batches and durable output chunks."""
import contextlib,hashlib,json,os,stat
from pathlib import Path
from . import contracts as C

def encoded(v):return (json.dumps(v,ensure_ascii=False,allow_nan=False,sort_keys=True,separators=(',',':'))+'\n').encode()

def triple(v):
    import re
    C.need(isinstance(v,dict) and type(v.get('bytes'))is int and v['bytes']>0
        and isinstance(v.get('sha256'),str) and re.fullmatch('[0-9a-f]{64}',v['sha256'])
        and isinstance(v.get('path'),str) and Path(v['path']).is_absolute(),'POSITIVE_NONBOOL_FULL64_DATA_LOCATOR')
    C.q.literal(v['path']);return {k:v[k] for k in ('path','bytes','sha256')}

def frame(s):return (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_nlink)

def pin(path):
    p=Path(path);h=hashlib.sha256()
    with p.open('rb') as f:
        before=os.fstat(f.fileno())
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
        C.need(frame(before)==frame(os.fstat(f.fileno()))==frame(p.lstat()),'OUTPUT_PIN_CURRENT_FD_STABLE')
    return {'path':str(p),'bytes':before.st_size,'sha256':h.hexdigest()}

@contextlib.contextmanager
def held(ref,budget):
    r=triple(ref);p=Path(r['path']);C.need(not any(x.is_symlink() for x in (p,*p.parents)),'NO_DATA_SYMLINK')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd);C.need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_nlink==1
            and before.st_size==r['bytes'],'ACTUAL_DATA_REGULAR_SINGLE_LINK_ALPHA_FD')
        h=hashlib.sha256()
        while True:
            budget.dispatch_check();block=os.read(fd,1<<20)
            if not block:break
            h.update(block)
        C.need(h.hexdigest()==r['sha256'] and frame(before)==frame(os.fstat(fd))==frame(p.lstat()),'WHOLE_DATA_SHA_CURRENT_FD_AND_PATH')
        os.lseek(fd,0,os.SEEK_SET);yield fd
        C.need(frame(before)==frame(os.fstat(fd))==frame(p.lstat()),'DATA_FD_CHANGED_DURING_READ')
    finally:os.close(fd)

def parquet(ref,budget,kind,expected):
    import pyarrow as pa,pyarrow.parquet as pq
    names=['source_table','copy_block','source_row_ordinal','observation_json'] if kind=='norm' else list(C.RAW_COLUMNS)
    types=[pa.string(),pa.int64(),pa.int64(),pa.string()] if kind=='norm' else [pa.string(),pa.int64(),pa.int64(),pa.int64(),pa.int64(),pa.string(),pa.string()]
    with held(ref,budget) as fd:
        with os.fdopen(os.dup(fd),'rb') as stream:
            p=pq.ParquetFile(stream)
            try:
                C.need(p.schema_arrow.equals(pa.schema(list(zip(names,types)))) and p.metadata.num_rows==expected,'EXACT_CLOSED_PARQUET_SCHEMA_AND_ROWS')
                for batch in p.iter_batches(batch_size=16,use_threads=False):
                    budget.dispatch_check();C.need(batch.nbytes<=128<<20,'ORIGINAL_BOUNDED_COMPLETE_ROWS_NO_TRUNCATION');yield batch.to_pylist()
            finally:p.close()

class Jsonl:
    def __init__(self,path,budget):
        self.path=Path(path);self.temporary=self.path.with_suffix(self.path.suffix+'.partial');self.f=self.temporary.open('xb')
        self.budget=budget;self.buffer=bytearray();self.rows=0;self.since_sync=0
    def add(self,value):
        raw=encoded(value);C.need(len(raw)<=8<<20,'BOUNDED_WHOLE_OUTPUT_ROW_NOT_PREFIX');self.buffer.extend(raw);self.rows+=1;self.since_sync+=1
        if len(self.buffer)>=1<<20:self.flush(False)
        if self.since_sync>=65536:self.flush(True)
    def flush(self,sync):
        self.budget.capacity(len(self.buffer));self.f.write(self.buffer);self.buffer.clear();self.f.flush()
        if sync:os.fsync(self.f.fileno());self.since_sync=0
    def close(self):
        self.flush(True);self.f.close();C.need(not self.path.exists(),'FRESH_CLOSED_OUTPUT_PATH');self.temporary.rename(self.path);r=pin(self.path)
        return dict(r,rows=self.rows)

def read_jsonl(ref,budget):
    with held(ref,budget) as fd:
        with os.fdopen(os.dup(fd),'rb') as f:
            for raw in f:
                budget.dispatch_check();C.need(len(raw)<=8<<20,'CLOSED_OUTPUT_WHOLE_LINE_BOUND');yield json.loads(raw)
