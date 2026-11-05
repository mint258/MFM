"""Actual closed DATA whole-SHA and same-FD Parquet reads, CPU only caller."""
import hashlib,json,os,stat
from pathlib import Path
from . import contract as C
from workflows.expansion.common_molecular_fp_candidate_v1 import projection as P,census as Census
Q=C.Q
def stamp(s):return s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid
class BorrowedFile:
    """Arrow may close its view; the owner keeps the hashed FD until readback."""
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
    def __init__(self,reference,budget,*,allow_empty=False):
        if allow_empty and reference['bytes']==0:
            Q.need(set(reference)=={'path','bytes','sha256'} and reference['sha256']==hashlib.sha256(b'').hexdigest()
                and C.Q.ROOT/'artifacts' in Path(reference['path']).parents,'EXACT_ACTUAL_EMPTY_OUTPUT_ONLY')
            self.reference=dict(reference)
        else:self.reference=C.triple(reference)
        self.path=Path(reference['path']);self.stream=None
        Q.need(not any(p.is_symlink() for p in (self.path,*self.path.parents)),'NON_SYMLINK_DATA_SOURCE')
        before=self.path.lstat();Q.need(stat.S_ISREG(before.st_mode) and before.st_uid==1278 and before.st_size==reference['bytes'],'EXACT_CURRENT_MAIN_DATA_FRAME')
        self.stream=self.path.open('rb');first=os.fstat(self.stream.fileno());h=hashlib.sha256();n=0
        while chunk:=self.stream.read(1<<20):h.update(chunk);n+=len(chunk);budget.check(False)
        Q.need(n==reference['bytes'] and h.hexdigest()==reference['sha256'] and stamp(before)==stamp(first)==stamp(os.fstat(self.stream.fileno()))==stamp(self.path.lstat()),'CPU_FULL_DATA_SHA_STABLE_FD')
        self.frame=stamp(first);self.stream.seek(0)
    def parquet(self):
        import pyarrow.parquet as pq
        self.check();self.stream.seek(0);return pq.ParquetFile(BorrowedFile(self.stream))
    def check(self):Q.need(stamp(os.fstat(self.stream.fileno()))==self.frame==stamp(self.path.lstat()),'SAME_HASHED_DATA_FD_AND_PATH_STILL_IMMUTABLE')
    def close(self):
        if self.stream is not None:
            try:self.check()
            finally:self.stream.close();self.stream=None

def read_strict5_rows(stream,membership):
    census=Census.Census();rows=0
    for raw in stream:
        Q.need(len(raw)<=2<<20 and raw.endswith(b'\n'),'COMPLETE_BOUNDED_STRICT5_LINE')
        row=json.loads(raw);P.validate_projection(row);role,n=membership(row['molecule_id'])
        census.add(row['molecule_id'],role,n);rows+=1
    return rows,census.result()

def seal_closed_output(path,budget):
    path=Path(path);before=path.lstat();Q.need(stat.S_ISREG(before.st_mode) and not path.is_symlink()
        and before.st_uid==1278,'CLOSED_JOB_OWNED_OUTPUT_ONLY')
    h=hashlib.sha256();n=0
    with path.open('rb') as stream:
        first=os.fstat(stream.fileno())
        while raw:=stream.read(1<<20):h.update(raw);n+=len(raw);budget.check(False)
        last=os.fstat(stream.fileno())
    Q.need(stamp(before)==stamp(first)==stamp(last)==stamp(path.lstat()) and n==before.st_size,'CLOSED_OUTPUT_SEAL_FRAME')
    return {'path':str(path),'bytes':n,'sha256':h.hexdigest()}
