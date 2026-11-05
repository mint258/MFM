"""Alpha-owned held-FD transport reads and durable output journals."""
import hashlib,json,os,stat
from pathlib import Path


def need(ok,message):
    if not ok:raise ValueError(message)
def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()+b'\n'
def frame(s):return (s.st_dev,s.st_ino,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
def triple(ref):return {k:ref[k] for k in ('path','bytes','sha256')}


class Borrowed:
    def __init__(self,stream):self.stream=stream
    @property
    def closed(self):return self.stream.closed
    def read(self,n=-1):return self.stream.read(n)
    def readinto(self,value):return self.stream.readinto(value)
    def seek(self,offset,whence=0):return self.stream.seek(offset,whence)
    def tell(self):return self.stream.tell()
    def readable(self):return True
    def seekable(self):return True
    def writable(self):return False
    def close(self):pass


class Body:
    def __init__(self,reference,budget):
        self.reference=triple(reference);self.path=Path(reference['path']);self.stream=None
        need(self.path.is_absolute() and not any(p.is_symlink() for p in (self.path,*self.path.parents)),'OWNED_NON_SYMLINK_ALPHA_INPUT')
        fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
        try:
            before=os.fstat(fd)
            need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_nlink==1 and before.st_size==reference['bytes'],'TRUE_ALPHA_UID_AND_EXACT_INPUT_LENGTH')
            self.stream=os.fdopen(fd,'rb');fd=None;digest=hashlib.sha256();size=0
            for raw in iter(lambda:self.stream.read(1<<20),b''):digest.update(raw);size+=len(raw);budget.check()
            need(size==reference['bytes'] and digest.hexdigest()==reference['sha256'],'WHOLE_TRANSPORTED_SOURCE_SHA')
            self.frame=frame(before);self.check();self.stream.seek(0)
        except BaseException:
            if self.stream is not None:self.stream.close()
            raise
        finally:
            if fd is not None:os.close(fd)
    def check(self):need(frame(os.fstat(self.stream.fileno()))==self.frame==frame(self.path.lstat()),'SAME_IMMUTABLE_HASHED_FD_AND_PATH')
    def parquet(self):
        import pyarrow.parquet as pq
        self.check();self.stream.seek(0);return pq.ParquetFile(Borrowed(self.stream))
    def close(self):
        if self.stream is not None:
            try:self.check()
            finally:self.stream.close();self.stream=None


def pin(path,check=lambda:None):
    path=Path(path).absolute();digest=hashlib.sha256();size=0
    need(not any(p.is_symlink() for p in (path,*path.parents)),'NO_SOURCE_OR_OUTPUT_SYMLINK')
    with path.open('rb') as stream:
        before=os.fstat(stream.fileno());need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_nlink==1,'ACTUAL_ALPHA_SINGLE_LINK_FILE')
        for raw in iter(lambda:stream.read(1<<20),b''):digest.update(raw);size+=len(raw);check()
        need(frame(before)==frame(os.fstat(stream.fileno()))==frame(path.lstat()),'IMMUTABLE_COMPLETE_PIN')
    return dict(path=str(path),bytes=size,sha256=digest.hexdigest())


def read(ref,limit=2<<20):
    need(ref['bytes']<=limit,'BOUNDED_METADATA_NOT_DATA_PREFIX')
    need(pin(ref['path'])==triple(ref),'ACTUAL_METADATA_REFERENCE_SHA')
    return json.loads(Path(ref['path']).read_bytes())


def read_source(ref):
    need(ref['bytes']<=2<<20 and pin(ref['path'])==triple(ref),'CURRENT_UNCHANGED_SCIENTIFIC_SOURCE')


def save(path,value):
    raw=canonical(value)
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return pin(path)


class Writer:
    def __init__(self,path,budget):
        self.path=Path(path);self.budget=budget;self.stream=self.path.open('xb');self.bytes=0;self.rows=0
    def write(self,value,durable=False):
        self.budget.check();raw=canonical(value);self.stream.write(raw);self.bytes+=len(raw);self.rows+=1
        if durable:self.stream.flush();os.fsync(self.stream.fileno())
    def close(self):
        if not self.stream.closed:self.stream.flush();os.fsync(self.stream.fileno());self.stream.close()
    def reference(self):need(self.stream.closed,'CLOSED_OUTPUT_ONLY');return pin(self.path,self.budget.check)
