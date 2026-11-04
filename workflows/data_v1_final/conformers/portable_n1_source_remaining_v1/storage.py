"""Private per-parent durable bounds. Per-key reservations survive stop-new."""
import contextlib,fcntl,json,os,pathlib,time
from . import contract as C


@contextlib.contextmanager
def lock(path):
    fd=os.open(C.literal(path),os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:fcntl.flock(fd,fcntl.LOCK_EX);yield
    finally:os.close(fd)


def initialize(out,cap):
    path=pathlib.Path(out)/'writer_state_v4.json'
    C.save(path,{'cap':cap,'written':0,'reserved':{}})


def read(out):return json.loads((pathlib.Path(out)/'writer_state_v4.json').read_bytes())
def replace(out,value):
    p=pathlib.Path(out)/'writer_state_v4.json';tmp=p.with_name('.state-'+str(os.getpid())+'-'+str(time.time_ns()))
    C.save(tmp,value);os.replace(tmp,p)
    fd=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(fd)
    finally:os.close(fd)


def reserve(out,key,n):
    with lock(pathlib.Path(out)/'writer.lock'):
        s=read(out);C.need(type(n)is int and n>0,'ACTUAL_ORIGINAL_TASK_RESERVATION')
        C.need(key not in s['reserved'],'DUPLICATE_PRIVATE_RESERVATION')
        if s['written']+sum(s['reserved'].values())+n+C.ADMIN>s['cap']:return False
        s['reserved'][key]=n;replace(out,s);return True


def release(out,key):
    with lock(pathlib.Path(out)/'writer.lock'):
        s=read(out);s['reserved'].pop(key,None);replace(out,s)


def write(out,path,raw,key=None):
    out=pathlib.Path(out);path=pathlib.Path(path);C.need(out in C.literal(path).parents,'PRIVATE_CHILD_OUTPUT')
    with lock(out/'writer.lock'):
        s=read(out)
        if key is not None:
            C.need(key in s['reserved'] and len(raw)<=s['reserved'][key],'STRICT_REMAINING_PER_KEY_DRAIN_BYTES')
            s['reserved'][key]-=len(raw)
        else:C.need(len(raw)<=C.ADMIN,'FINITE_ADMIN_CONTAINER')
        C.need(s['written']+sum(s['reserved'].values())+len(raw)+C.ADMIN<=s['cap'],'WHOLE_PRIVATE_BOUND')
        r=C.exclusive(path,raw);s['written']+=len(raw);replace(out,s);return r


def charge_external(out,n):
    with lock(pathlib.Path(out)/'writer.lock'):
        s=read(out);C.need(s['written']+sum(s['reserved'].values())+n+C.ADMIN<=s['cap'],'STREAM_EXPORT_TOTAL_BOUND')
        s['written']+=n;replace(out,s)
