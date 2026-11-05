"""Own finite QA output only; original payload reader is direct and unchanged."""
import gzip,hashlib,json,os,pathlib,stat
from . import contract as C
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import io as P
ref=P.ref;read=P.read;authorized=P.authorized;read_packet=P.read_packet


def create(out):
    C.need(out.is_absolute() and C.BASE in out.parents and '..' not in out.parts and not out.exists()
        and not any(p.is_symlink() for p in (out,*out.parents)),'NEW_QA_OUTPUT_NOT_PRODUCTION')
    out.mkdir(parents=True,mode=0o700)
    for name in ('tasks','dispatch','starts','molecules','finished','progress','reservations'):(out/name).mkdir()
    return out


def write(path,raw,out,final=False):
    path=pathlib.Path(path);C.need(out in path.parents and len(raw)<=128<<20,'BOUNDED_QA_OUTPUT')
    with P.R.lock(out):
        C.need(P.R.disk_bytes(out)+len(raw)+(0 if final else C.ADMIN)<=C.CAP,'QA2GIB_WHOLE_OUTPUT_PREWRITE_STOP')
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'wb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        P.R.fsync_dir(path.parent)
    r=ref(path);C.need(r['bytes']==len(raw) and r['sha256']==hashlib.sha256(raw).hexdigest(),'ACTUAL_QA_OUTPUT_FULL_SHA_READBACK');return r


def json_new(path,value,out,final=False):return write(path,C.canonical(value)+b'\n',out,final)


def packet(path,value,out):
    raw=C.canonical(value);C.need(len(raw)<=P.C.PACKET_CAP,'ORIGINAL128MIB_PACKET_BOUND_NO_TRUNCATION')
    r=write(path,gzip.compress(raw,mtime=0),out);C.need(read_packet(r)==value,'ORIGINAL_FLOAT64_GZIP_EOF_READBACK');return r


def progress(path,value,out):
    raw=C.canonical(value)+b'\n';C.need(len(raw)<=32768,'BOUNDED_QA_PROGRESS_EVENT')
    with P.R.lock(out):
        C.need(P.R.disk_bytes(out)+len(raw)+C.ADMIN<C.CAP,'QA_PROGRESS_CAP')
        fd=os.open(path,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'ab') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        P.R.fsync_dir(path.parent)
