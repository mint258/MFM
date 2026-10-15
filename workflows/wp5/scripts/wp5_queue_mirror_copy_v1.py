"""Terminal-only queue file mirror. Source files are never opened by SQLite.
Prepared control utility; Root is the only actor that may execute the copy.
"""
from __future__ import annotations
import argparse,fcntl,hashlib,json,os,sqlite3,stat,tempfile,time
from pathlib import Path
from urllib.parse import quote
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
QUEUE=ROOT/'queue/pending.sqlite'
SUFFIXES=('', '-journal', '-wal', '-shm')
LOCK_SUFFIX='.metadata_v12.lock'
UID=1278

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(8*1024*1024),b''):h.update(block)
    return h.hexdigest()

def write_json(path,doc):
    with Path(path).open('x',encoding='utf-8',newline='\n') as f:
        json.dump(doc,f,indent=2,allow_nan=False);f.write('\n');f.flush();os.fsync(f.fileno())

def normal(path):return os.path.normpath(os.path.abspath(os.fspath(path)))

def fingerprint(path):
    p=Path(path)
    try:s=p.lstat()
    except FileNotFoundError:return None
    if not stat.S_ISREG(s.st_mode) or stat.S_ISLNK(s.st_mode):raise ValueError('REGULAR_NONLINK_FILE_REQUIRED:'+str(p))
    if s.st_uid!=os.getuid():raise ValueError('OWNED_FILE_REQUIRED:'+str(p))
    return {'path':str(p),'device':s.st_dev,'inode':s.st_ino,'uid':s.st_uid,'bytes':s.st_size,'mtime_ns':s.st_mtime_ns,'ctime_ns':s.st_ctime_ns}

def inventory(queue):
    return {queue.name+suffix:fingerprint(Path(str(queue)+suffix)) for suffix in SUFFIXES}

def unchanged(queue,expected):
    actual=inventory(Path(queue))
    if actual!=expected:raise ValueError('SOURCE_DB_OR_JOURNAL_WAL_SHM_FILE_SET_CHANGED')
    return actual

def stream_copy(source,target,expected):
    fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        fs=os.fstat(fd)
        if (fs.st_dev,fs.st_ino,fs.st_uid,fs.st_size,fs.st_mtime_ns,fs.st_ctime_ns)!=(expected['device'],expected['inode'],expected['uid'],expected['bytes'],expected['mtime_ns'],expected['ctime_ns']):raise ValueError('SOURCE_CHANGED_BEFORE_OPEN')
        h=hashlib.sha256();count=0
        with os.fdopen(fd,'rb',closefd=False) as src,Path(target).open('xb') as dst:
            for block in iter(lambda:src.read(8*1024*1024),b''):
                h.update(block);count+=len(block);dst.write(block)
            dst.flush();os.fsync(dst.fileno())
        if count!=expected['bytes'] or fingerprint(source)!=expected:raise ValueError('SOURCE_CHANGED_DURING_STREAM')
        readback=digest(target)
        if h.hexdigest()!=readback:raise ValueError('LOCAL_STREAM_READBACK_SHA_DIFFERS')
        return {'source_stream_sha256':h.hexdigest(),'local_readback_sha256':readback,'bytes':count}
    finally:os.close(fd)

def local_schema(path,readwrite=False):
    db=sqlite3.connect('file:'+quote(str(path))+'?mode='+('rw' if readwrite else 'ro'),uri=True,timeout=1,isolation_level=None)
    try:
        db.execute('PRAGMA query_only=ON').close()
        tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        if not {'meta','molecules','tasks','sessions','export_repairs'}.issubset(tables):raise ValueError('LOCAL_QUEUE_SCHEMA_MISSING_TABLE')
        return {'tables':tables,'sqlite_version':sqlite3.sqlite_version,'query_only':db.execute('PRAGMA query_only').fetchone()[0]}
    finally:db.close()

def ready_local(queue):
    steps=[]
    try:schema=local_schema(queue)
    except sqlite3.DatabaseError as exc:
        if getattr(exc,'sqlite_errorcode',None)!=sqlite3.SQLITE_READONLY_ROLLBACK:raise
        schema=local_schema(queue,readwrite=True)
        steps.append({'kind':'SQLITE_INTERNAL_LOCAL_HOT_JOURNAL_RECOVERY','observed_errorcode':exc.sqlite_errorcode,'observed_errorname':exc.sqlite_errorname,'query_only':True})
    wal=Path(str(queue)+'-wal')
    if wal.exists() and wal.stat().st_size:
        db=sqlite3.connect('file:'+quote(str(queue))+'?mode=rw',uri=True,timeout=1,isolation_level=None)
        try:
            db.execute('PRAGMA query_only=ON').close()
            row=db.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
            if row[0]!=0:raise ValueError('LOCAL_WAL_CHECKPOINT_BUSY')
            steps.append({'kind':'OWNED_LOCAL_WAL_CHECKPOINT_ONLY','checkpoint_result':list(row),'query_only':True})
        finally:db.close()
    return steps,local_schema(queue)

def check_quiescence(path,expected_sha):
    if digest(path)!=expected_sha:raise ValueError('ROOT_QUIESCENCE_EVIDENCE_SHA_DIFFERS')
    doc=json.loads(Path(path).read_text())
    if doc.get('schema')!='WP5_QUEUE_MIRROR_QUIESCENCE_V1' or doc.get('status')!='QUIESCENT':raise ValueError('ACTUAL_CONTROL_QUIESCENCE_EVIDENCE_REQUIRED')
    if normal(doc.get('queue',''))!=normal(QUEUE) or doc.get('uid')!=UID:raise ValueError('QUIESCENCE_QUEUE_UID_DIFFERS')
    if doc.get('all_approved_nodes_checked') is not True or doc.get('no_remaining_queue_writers') is not True or doc.get('control_readers_exited') is not True:raise ValueError('WRITERS_OR_CONTROL_READERS_NOT_PROVEN_EXITED')
    if not isinstance(doc.get('created_epoch'),(int,float)) or not 0<=time.time()-doc['created_epoch']<=600:raise ValueError('QUIESCENCE_EVIDENCE_NOT_FRESH')
    refs=doc.get('evidence',[])
    if not refs:raise ValueError('ACTUAL_EXIT_PROCESS_EVIDENCE_REQUIRED')
    for ref in refs:
        if digest(ref['path'])!=ref['sha256']:raise ValueError('QUIESCENCE_ACTUAL_EVIDENCE_CHANGED')
    return {'path':str(path),'sha256':expected_sha,'document':doc}

def verify_manifest(path,expected_sha,hash_local=True):
    if digest(path)!=expected_sha:raise ValueError('EXACT_VERIFIED_MIRROR_MANIFEST_SHA_REQUIRED')
    doc=json.loads(Path(path).read_text())
    if doc.get('schema')!='WP5_TERMINAL_QUEUE_LOCAL_MIRROR_V1' or doc.get('status')!='VERIFIED_LOCAL_MIRROR':raise ValueError('VERIFIED_MIRROR_STATUS_REQUIRED')
    if normal(doc['source_queue'])!=normal(QUEUE) or doc['uid']!=os.getuid() or doc['uid']!=UID or doc['hostname']!=os.uname().nodename:raise ValueError('EXACT_QUEUE_UID_HOST_MIRROR_REQUIRED')
    if not doc.get('source_fingerprints_stable') or doc.get('source_SQLite_opened') is not False or doc.get('source_modified') is not False:raise ValueError('SOURCE_READONLY_STABLE_COPY_PROOF_REQUIRED')
    if doc['actual_registered_job_count']!=385 or doc['accounting']['all_terminal'] is not True:raise ValueError('COPY_ALL385_TERMINAL_PROOF_REQUIRED')
    if digest(doc['copier_source']['path'])!=doc['copier_source']['sha256'] or digest(__file__)!=doc['copier_source']['sha256']:raise ValueError('COPY_HELPER_SOURCE_CHANGED')
    directory=Path(doc['local_directory'])
    if directory.parent!=Path('/tmp') or not directory.name.startswith('wp5_queue_mirror_') or directory.is_symlink() or directory.stat().st_uid!=UID:raise ValueError('OWNED_NODE_LOCAL_PRIVATE_MIRROR_DIRECTORY_REQUIRED')
    if Path(doc['local_queue'])!=directory/QUEUE.name:raise ValueError('LOCAL_QUEUE_PATH_DIFFERS')
    unchanged(QUEUE,doc['source_fingerprints_after'])
    if inventory(Path(doc['local_queue']))!=doc['local_fingerprints_after']:raise ValueError('LOCAL_MIRROR_FILE_SET_OR_FINGERPRINT_CHANGED')
    if set(doc['source_fingerprints_after'])!={QUEUE.name+s for s in SUFFIXES}:raise ValueError('FULL_JOURNAL_WAL_SHM_INVENTORY_REQUIRED')
    if hash_local:
        for name,ref in doc['local_files_after'].items():
            if ref is not None and digest(ref['path'])!=ref['sha256']:raise ValueError('LOCAL_MIRROR_READBACK_SHA_CHANGED:'+name)
    return doc

class ExactQueueReadAdapter:
    """Only the exact source queue maps; the base factory remains read-only."""
    def __init__(self,source,mirror,readonly_factory):self.source=normal(source);self.mirror=Path(mirror);self.base=readonly_factory
    def __call__(self,path):return self.base(self.mirror if normal(path)==self.source else path)

def copy(args):
    if os.getuid()!=UID or os.uname().nodename!='compute-0-17':raise ValueError('UID1278_ACTUAL_COMPUTE17_REQUIRED')
    import wp5_queue_reconcile_v8 as B
    jobs,refs,receipts=B.registry(list(B.MANIFESTS))
    out=Path(args.out)
    if not out.resolve().is_relative_to((ROOT/'reports').resolve()):raise ValueError('NEW_PHASE_REPORT_ROOT_REQUIRED')
    out.mkdir(parents=True,exist_ok=False)
    quiescence=check_quiescence(args.quiescence_proof,args.expected_quiescence_sha256)
    proof=B.H.terminal_proof(list(jobs),out)
    if not proof['all_terminal'] or len(proof['states'])!=385:raise ValueError('ALL385_ACTUAL_JOBS_NOT_TERMINAL')
    directory=Path(args.local_directory)
    if directory.parent!=Path('/tmp') or not directory.name.startswith('wp5_queue_mirror_'):raise ValueError('EXPLICIT_NODE_LOCAL_PRIVATE_DIRECTORY_REQUIRED')
    directory.mkdir(mode=0o700,exist_ok=False)
    lock=Path(str(QUEUE)+LOCK_SUFFIX);s=lock.lstat()
    if not stat.S_ISREG(s.st_mode) or s.st_uid!=UID:raise ValueError('OWNED_EXISTING_R13_SIDECAR_LOCK_REQUIRED')
    fd=os.open(lock,os.O_RDWR|os.O_NOFOLLOW);started=time.time()
    try:
        deadline=time.monotonic()+120
        while True:
            try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>=deadline:raise TimeoutError('ACTUAL_R13_METADATA_SIDECAR_STILL_OWNED')
                time.sleep(.2)
        before=inventory(QUEUE)
        if before[QUEUE.name] is None:raise ValueError('SOURCE_QUEUE_MISSING')
        copies={}
        for name,ref in before.items():
            if ref is not None:copies[name]=stream_copy(Path(ref['path']),directory/name,ref)
        after=unchanged(QUEUE,before)
        local_queue=directory/QUEUE.name
        local_before=inventory(local_queue)
        local_before_sha={name:({'path':ref['path'],'bytes':ref['bytes'],'sha256':digest(ref['path'])} if ref else None) for name,ref in local_before.items()}
        recovery,schema=ready_local(local_queue)
        local_after=inventory(local_queue)
        local_after_sha={name:({'path':ref['path'],'bytes':ref['bytes'],'sha256':digest(ref['path'])} if ref else None) for name,ref in local_after.items()}
        unchanged(QUEUE,before)
        if digest(args.quiescence_proof)!=args.expected_quiescence_sha256:raise ValueError('QUIESCENCE_PROOF_CHANGED_DURING_COPY')
        report={'schema':'WP5_TERMINAL_QUEUE_LOCAL_MIRROR_V1','status':'VERIFIED_LOCAL_MIRROR','created_epoch':time.time(),'copy_started_epoch':started,
            'uid':UID,'hostname':os.uname().nodename,'slurm_job_id':os.environ.get('SLURM_JOB_ID'),'source_queue':str(QUEUE),'local_queue':str(local_queue),'local_directory':str(directory),
            'copier_source':{'path':str(Path(__file__).resolve()),'sha256':digest(__file__)},'control_source':{'path':B.__file__,'sha256':digest(B.__file__)},
            'actual_registered_job_count':385,'manifests':refs,'registered_receipts':receipts,'accounting':proof,'quiescence':quiescence,
            'source_fingerprints_before':before,'source_fingerprints_after':after,'source_fingerprints_stable':True,'source_file_copy_sha_readback':copies,
            'local_fingerprints_before_recovery':local_before,'local_files_before_recovery':local_before_sha,'local_recovery':recovery,'local_schema':schema,
            'local_fingerprints_after':local_after,'local_files_after':local_after_sha,'source_SQLite_opened':False,'source_modified':False,
            'local_mirror_retained_for_same_node_R9':True,'copy_parallelism':1,'copy_scope':'One sequential stream per present DB/journal/WAL/shm under existing R13 sidecar; source SHA computed from copied stream plus stable source fingerprints. No source SQL or independent source rescan.'}
        write_json(out/'manifest.json',report)
        print(json.dumps({'status':report['status'],'manifest':str(out/'manifest.json'),'sha256':digest(out/'manifest.json'),'local_queue':str(local_queue),'copied_bytes':sum(r['bytes'] for r in copies.values())}))
    finally:
        fcntl.flock(fd,fcntl.LOCK_UN);os.close(fd)

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--local-directory',type=Path,required=True)
    p.add_argument('--quiescence-proof',type=Path,required=True);p.add_argument('--expected-quiescence-sha256',required=True)
    copy(p.parse_args())
if __name__=='__main__':main()
