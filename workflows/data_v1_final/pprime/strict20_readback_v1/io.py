"""Positive DATA, full same-FD SHA and stable frame; no symlink or hardlink."""
from __future__ import annotations
import contextlib,hashlib,json,os,pathlib,stat,threading
from workflows.data_v1_final.pprime.common import read_staging,staging_bytes
from . import contract as C

def frame(s):return tuple(getattr(s,k) for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns','st_uid','st_mode','st_nlink'))

def safe(path):
    p=pathlib.Path(path);C.need(p.is_absolute() and '..' not in p.parts and not any(x.is_symlink() for x in (p,*p.parents)),'LITERAL_NON_SYMLINK_DATA_PATH')
    s=p.lstat();C.need(stat.S_ISREG(s.st_mode) and s.st_uid==1278 and s.st_nlink==1,'OWN_REGULAR_SINGLE_LINK_DATA');return p,s

@contextlib.contextmanager
def held(ref,roots,declared=None):
    r=C.within(ref,roots)
    if declared is not None:C.need(r in declared,'EXACT_DECLARED_DATA_BEFORE_OPEN')
    p,s=safe(r['path']);C.need(s.st_size==r['bytes'],'EXACT_PRODUCER_BYTES')
    with p.open('rb') as f:
        before=frame(s);C.need(frame(os.fstat(f.fileno()))==before,'SAME_OPEN_DATA_FD');h=hashlib.sha256()
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
        C.need(h.hexdigest()==r['sha256'] and frame(os.fstat(f.fileno()))==before==frame(p.lstat()),'WHOLE_SHA_BEFORE_DATA_PARSE')
        f.seek(0)
        try:yield f,before
        finally:C.need(frame(os.fstat(f.fileno()))==before==frame(p.lstat()) and not p.is_symlink(),'DATA_FRAME_STABLE_AFTER_PARSE')

def body(ref,roots,declared=None,cap=8<<20):
    C.need(ref['bytes']<=cap,'FINITE_BODY_CAP_NOT_LARGE_LOCATOR_CAP')
    with held(ref,roots,declared) as (f,_):return f.read(cap+1)

def value(ref,roots,declared=None,cap=8<<20):return read_staging(body(ref,roots,declared,cap))

def discover(path,roots):
    """CPU-only first pin, permitted solely inside Root's actual closed roots."""
    p,s=safe(path);C.need(s.st_size>0,'POSITIVE_ACTUAL_TRANSITIVE_OUTPUT')
    C.within({'path':str(p),'bytes':s.st_size,'sha256':'0'*64},roots)
    with p.open('rb') as f:
        before=frame(s);C.need(frame(os.fstat(f.fileno()))==before,'FIRST_PIN_SAME_FD');h=hashlib.sha256()
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
        C.need(frame(os.fstat(f.fileno()))==before==frame(p.lstat()),'FIRST_PIN_FULL_SHA_STABLE_FD')
    return {'path':str(p),'bytes':s.st_size,'sha256':h.hexdigest()}

def fresh(path,allowed):
    p=pathlib.Path(path);C.need(p.is_absolute() and pathlib.Path(allowed) in p.parents and '..' not in p.parts and not p.exists()
        and not any(x.is_symlink() for x in (p,*p.parents)),'FRESH_OWN_LITERAL_OUTPUT');return p

class Store:
    def __init__(self,root,check,mode):
        self.root=pathlib.Path(root);self.charged=0;self.lock=threading.Lock();self.check=check;self.cap=C.cap(mode);self.reserve=C.reserve(mode)
    def write(self,path,body,*,failure=False):
        p=pathlib.Path(path);C.need(self.root in p.parents and not p.exists(),'NEW_OWN_OUTPUT_ONLY')
        if not failure:self.check()
        with self.lock:
            C.need(self.charged+len(body)+self.reserve<=self.cap,'WHOLE_OUTPUT_AND_DRAIN_RESERVE');self.charged+=len(body)
        p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        with p.open('xb') as f:f.write(body);f.flush();os.fsync(f.fileno())
        return {'path':str(p),'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest()}
    def json(self,path,value,**kw):return self.write(path,staging_bytes(value)+b'\n',**kw)
