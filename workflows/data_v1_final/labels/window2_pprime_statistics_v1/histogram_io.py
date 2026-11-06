"""Opt-in histogram I/O only: every physical write is guarded and bounded."""
import io,json,os
from pathlib import Path
from ..window2_normalization_v1 import io as OriginalIO
PURPOSES={'normalization_quantiles','diagnostic_median_MAD'}
CHUNK=64<<10


def enabled(cfg,purpose):
    flag=cfg.get('histogram_guard_writes_only',False)
    if type(flag)is not bool:raise ValueError('BOOLEAN_HISTOGRAM_WRITE_GUARD_OPT_IN_REQUIRED')
    return flag and purpose in PURPOSES


def open_raw(path):return io.FileIO(path,'w') # unbuffered; no hidden flush writes


class File:
    mode='wb'
    def __init__(self,path,guard):
        self.path=Path(path);self.guard=guard
        guard.wait(self.path,bytes_needed=0,inodes_needed=1)
        self._raw=open_raw(self.path)
    @property
    def closed(self):return self._raw.closed
    def writable(self):return True
    def readable(self):return False
    def seekable(self):return False
    def tell(self):return self._raw.tell()
    def flush(self):
        if self.closed:raise ValueError('CLOSED_UNBUFFERED_HISTOGRAM_STREAM')
    def write(self,data):
        if self.closed:raise ValueError('CLOSED_UNBUFFERED_HISTOGRAM_STREAM')
        view=memoryview(data).cast('B');done=0
        while done<len(view):
            chunk=view[done:done+CHUNK]
            self.guard.wait(self.path,bytes_needed=len(chunk),inodes_needed=0)
            n=self._raw.write(chunk)
            if not n:raise OSError('NO_PROGRESS_UNBUFFERED_HISTOGRAM_WRITE')
            done+=n
        return done
    def close(self):self._raw.close() # no user-space buffer, even after denial
    def __enter__(self):return self
    def __exit__(self,*unused):self.close()


class Directory:
    def __init__(self,path,guard):self.path=Path(path);self.guard=guard
    def __fspath__(self):return os.fspath(self.path)
    def __str__(self):return str(self.path)
    def __truediv__(self,name):return Directory(self.path/name,self.guard)
    def is_file(self):return self.path.is_file()
    def mkdir(self,parents=False,exist_ok=False):
        if parents and not self.path.parent.exists():Directory(self.path.parent,self.guard).mkdir(parents=True,exist_ok=True)
        self.guard.wait(self.path,bytes_needed=0,inodes_needed=1)
        self.path.mkdir(parents=False,exist_ok=exist_ok)


class IO:
    def __init__(self,guard):self.guard=guard
    def __getattr__(self,name):
        if name in ('ref','require','load','load_data'):return getattr(OriginalIO,name)
        raise AttributeError('UNSUPPORTED_HISTOGRAM_IO_API:'+name)
    def save(self,path,value):
        path=Path(path);data=(json.dumps(value,ensure_ascii=False,sort_keys=True,allow_nan=False)+'\n').encode('utf-8')
        Directory(path.parent,self.guard).mkdir(parents=True,exist_ok=True)
        partial=path.with_name(path.name+'.writing')
        with File(partial,self.guard) as target:target.write(data)
        self.guard.wait(path,bytes_needed=0,inodes_needed=1);os.replace(partial,path)
        return OriginalIO.ref(path)


class Sink(OriginalIO.ParquetSink):
    def __init__(self,schema,buffer,guard):super().__init__(schema,buffer);self.guard=guard
    def close(self,path,*unused):
        import pyarrow as pa,pyarrow.parquet as pq
        path=Path(path);target=File(path,self.guard);writer=None
        try:
            writer=pq.ParquetWriter(target,self.schema,compression='zstd')
            for start in range(0,len(self.rows),8192):writer.write_table(pa.Table.from_pylist(self.rows[start:start+8192],schema=self.schema))
        finally:
            try:
                if writer is not None:writer.close() # footer uses guarded File.write
            finally:target.close() # destructor retries cannot write through closed FD
        return dict(OriginalIO.ref(path),records=len(self.rows))


def bindings(runtime,root):
    guard=runtime.guard
    return Directory(root,guard),{'I':IO(guard),'ParquetSink':lambda schema,buffer:Sink(schema,buffer,guard)}