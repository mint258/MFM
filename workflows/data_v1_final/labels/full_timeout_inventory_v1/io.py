"""Bounded CPU-only reads. Never opens any original input in write mode."""
from __future__ import annotations
import contextlib,hashlib,json,os,socket,sqlite3,stat,time
from pathlib import Path
from urllib.parse import quote
from . import contract as C
SMALL=2<<20


def frame(s):return dict(zip(C.FRAME,(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns,s.st_uid,s.st_mode,s.st_nlink)))


def small(path):
    p=Path(path);C.need(p.is_absolute() and '..' not in p.parts and not p.is_symlink(),'LITERAL_SMALL_SOURCE')
    with p.open('rb') as f:
        before=frame(os.fstat(f.fileno()));C.need(stat.S_ISREG(before['mode']) and before['bytes']<=SMALL,'SMALL_SOURCE_CAP')
        raw=f.read(SMALL+1);C.need(frame(os.fstat(f.fileno()))==before==frame(p.lstat()) and len(raw)==before['bytes'],'STABLE_SMALL_SOURCE')
    return raw


def pin(path):
    raw=small(path);return {'path':str(Path(path).absolute()),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def load(path):return json.loads(small(path))


def require(ref):C.need(pin(ref['path'])==C.triple(ref),'SMALL_SOURCE_PIN_CHANGED');return Path(ref['path'])


def write_new(path,value,cap=SMALL):
    raw=(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode();C.need(len(raw)<=cap,'NEW_METADATA_CAP')
    p=Path(path);p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
    directory=os.open(p.parent,os.O_RDONLY|os.O_DIRECTORY)
    try:os.fsync(directory)
    finally:os.close(directory)
    return {'path':str(p.absolute()),'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}


def original_match(current,expected):
    # st_dev is an observed mount-local number. No old CPU hash is invented.
    fields={'inode':'st_ino','bytes':'st_size','mtime_ns':'st_mtime_ns','uid':'st_uid','mode':'st_mode'}
    C.need(expected['exists'] and not expected.get('is_symlink',False)
      and all(current[a]==expected[b] for a,b in fields.items()),'CLOSED_ROOT_LOCATOR_IDENTITY_CHANGED')


def locator_inventory(root,book):
    """lstat only; callable on login. No input body is opened or hashed."""
    root=Path(root);C.need(root==C.OLD and Path(book)==C.BOOK,'EXACT_ORIGINAL_CLOSED_LOCATORS')
    before=frame(root.lstat());entries={};directories={'.':before}
    C.need(before['uid']==1278 and stat.S_ISDIR(before['mode']),'OWN_OLD_ROOT_DIRECTORY')
    for base,dirs,files in os.walk(root,followlinks=False):
        for name in sorted(dirs+files):
            p=Path(base)/name;relative=p.relative_to(root).as_posix();f=frame(p.lstat())
            C.need(f['uid']==1278 and (stat.S_ISREG(f['mode']) or stat.S_ISDIR(f['mode'])),'NO_SYMLINK_OR_SPECIAL_OLD_ENTRY')
            (directories if stat.S_ISDIR(f['mode']) else entries)[relative]=f
            C.need(len(entries)+len(directories)<=8192,'ORIGINAL_CONFIG_INODE_CAP')
    C.need(frame(root.lstat())==before and all(frame((root/k).lstat())==v for k,v in directories.items()),'CLOSED_DIRECTORY_CHANGED_DURING_LSTAT')
    book_frame=frame(Path(book).lstat());C.need(stat.S_ISREG(book_frame['mode']) and book_frame['uid']==1278,'OWN_DISPATCH_BOOK')
    return {'schema':'LABELS_TIMEOUT_CLOSED_LOCATOR_INVENTORY_V1','origin_node':socket.gethostname().split('.')[0],'uid':1278,
      'original_root':str(root),'root_frame':before,'directories':directories,'files':entries,
      'book_path':str(book),'book_frame':book_frame,'observed_unix_seconds':time.time(),
      'pending_cpu_whole_SHA':True,'scientific_body_files_opened_or_hashed':0,
      'portable_identity_fields':['inode','bytes','mtime_ns','uid','mode'],'device_is_recorded_mount_local_observation':True}


class SoftStop(RuntimeError):pass


def checkpoint(deadline):
    from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.resource_runtime import stop_requested,soft_worker_rss
    if time.time()>=deadline:raise SoftStop('FINITE_READONLY_DEADLINE_PENDING_RETAINED')
    soft_worker_rss(3<<30)
    if stop_requested():raise SoftStop('OBSERVED_MEMORY_OR_RESOURCE_STOP_PENDING_RETAINED')


@contextlib.contextmanager
def reader(path,expected,deadline):
    checkpoint(deadline);p=Path(path)
    C.need(p.is_absolute() and '..' not in p.parts and not any(q.is_symlink() for q in (p,*p.parents)),'READONLY_LITERAL_NO_SYMLINK')
    observed=frame(p.lstat());C.need(stat.S_ISREG(observed['mode']) and observed['uid']==1278 and observed['nlink']==1,'REGULAR_SINGLE_LINK_OWN_OLD_DATA')
    C.need(all(observed[k]==expected[k] for k in ('inode','bytes','mtime_ns','ctime_ns','uid','mode','nlink')),'CLOSED_LOCATOR_PORTABLE_FRAME_DIFFERS')
    fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as f:
        C.need(frame(os.fstat(f.fileno()))==observed,'SAME_FD_INPUT_FRAME')
        yield f,observed
        C.need(frame(os.fstat(f.fileno()))==observed==frame(p.lstat()),'OLD_DATA_CHANGED_DURING_READ')


def hash_stream(f,deadline):
    h=hashlib.sha256();n=0
    while True:
        checkpoint(deadline);chunk=f.read(1<<20)
        if not chunk:break
        h.update(chunk);n+=len(chunk)
    return n,h.hexdigest()


def read_json(path,expected,deadline,cap,known=None):
    C.need(expected['bytes']<=cap,'BOUNDED_JSON_BODY')
    with reader(path,expected,deadline) as (f,current):
        n,sha=hash_stream(f,deadline);ref={'path':str(path),'bytes':n,'sha256':sha}
        if known is not None:C.need(ref==C.triple(known),'OLD_JSON_WHOLE_SHA_DIFFERS')
        f.seek(0);raw=f.read(cap+1);C.need(len(raw)==n<=cap,'JSON_SIZE_AFTER_HASH')
        value=json.loads(raw)
    return value,{'reference':ref,'current_frame':current,'origin_frame':expected}


def check_sidecars(path):
    found=[str(Path(str(path)+suffix)) for suffix in ('-journal','-wal','-shm') if Path(str(path)+suffix).exists()]
    C.need(not found,'SQLITE_SIDECAR_PRESENT_NO_READONLY_ROLLBACK_OR_IMMUTABLE_BYPASS')


def sqlite_snapshot(path,expected,deadline,tables):
    """No Ledger/DispatchBook constructor, backup, journal recovery or writes."""
    check_sidecars(path)
    with reader(path,expected,deadline) as (f,current):
        n,sha=hash_stream(f,deadline);uri='file:'+quote(str(path),safe='/')+'?mode=ro'
        db=sqlite3.connect(uri,uri=True,timeout=5,isolation_level=None)
        try:
            db.execute('PRAGMA query_only=ON');db.execute('PRAGMA trusted_schema=OFF');db.execute('BEGIN')
            C.need(db.execute('PRAGMA quick_check').fetchall()==[('ok',)],'READONLY_SQLITE_QUICK_CHECK')
            actual={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            C.need(actual==set(tables),'EXACT_FROZEN_SQLITE_TABLES')
            rows={}
            for table,columns in tables.items():
                C.need([r[1] for r in db.execute('PRAGMA table_info('+table+')')]==columns,'EXACT_SQLITE_COLUMNS:'+table)
                values=db.execute('SELECT * FROM '+table).fetchall();C.need(len(values)<=20000,'FINITE_FROZEN_BOOK_ROWS')
                rows[table]=[dict(zip(columns,r)) for r in values]
            db.execute('ROLLBACK')
        finally:db.close()
        f.seek(0);after=hash_stream(f,deadline);C.need(after==(n,sha),'OLD_DB_SHA_CHANGED_DURING_READONLY_TRANSACTION')
    check_sidecars(path)
    return rows,{'reference':{'path':str(path),'bytes':n,'sha256':sha},'current_frame':current,
      'origin_frame':expected,'connection_mode':'ro','immutable_bypass_used':False,'read_transaction_rolled_back':True}