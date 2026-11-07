"""Small owned immutable references; independent of Main UID and budgets."""
import hashlib,json,os,stat
from pathlib import Path
from .kernel import need


def canonical(value):return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()+b'\n'
def frame(s):return (s.st_dev,s.st_ino,s.st_uid,s.st_nlink,s.st_size,s.st_mtime_ns,s.st_ctime_ns)


def read(ref,cap=16<<20):
    path=Path(ref['path']);need(path.is_absolute() and type(ref['bytes']) is int and 0<=ref['bytes']<=cap,'BOUNDED_ABSOLUTE_INPUT')
    need(not any(p.is_symlink() for p in (path,*path.parents)),'NO_SYMLINK_INPUT')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd);need(stat.S_ISREG(before.st_mode) and before.st_uid==1264 and before.st_nlink==1 and before.st_size==ref['bytes'],'OWNED_SINGLE_LINK_EXACT_INPUT')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(cap+1)
        need(frame(before)==frame(os.fstat(fd))==frame(path.stat()),'IMMUTABLE_INPUT_DURING_READ')
        need(len(raw)==ref['bytes'] and hashlib.sha256(raw).hexdigest()==ref['sha256'],'ACTUAL_COMPLETE_INPUT_SHA')
        return raw
    finally:os.close(fd)


def verify(ref):read(ref,2<<20);return Path(ref['path'])


def pin(path):
    p=Path(path).absolute();raw=p.read_bytes();return dict(path=str(p),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())


def save(path,value):
    raw=canonical(value)
    with Path(path).open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return pin(path)


def rows(ref):
    raw=read(ref)
    need(not raw or raw.endswith(b'\n'),'CLOSED_JSONL_NO_TRUNCATION')
    result=[json.loads(line) for line in raw.splitlines()]
    need(len(result)==ref['rows'],'EXACT_REFERENCE_ROW_COUNT');return result
