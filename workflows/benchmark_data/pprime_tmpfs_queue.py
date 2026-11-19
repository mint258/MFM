"""Immutable tmpfs continuation of the existing once-only P-prime scheduler."""
import argparse
from collections import Counter
import fcntl
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import socket
import sqlite3
import stat
import time
import zlib
from .admission import protect
from .pprime_store import LaneStore,pack,unpack
from .shared_reader import SharedB0Reader
from .shared_access import check_access,publish,seal_geometry

FORECAST=80000000000
LOCAL_PER_WORKER=8*1024**3


def capacity(root,snapshot,needed=67108864,workers=0,scratch=None):
    g=json.loads((root/'geometry/shared_v1/queue.manifest.json').read_text())
    geometry_future=max(67108864,g['storage_forecast_bytes']-Path(g['queue']).stat().st_size)
    pp=root/'labels/Pprime/shared_v1';used=0
    if pp.exists():
        for path in pp.glob('*.sqlite'):
            s=path.lstat()
            if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid():raise ValueError('Unexpected P-prime output owner/type')
            used+=s.st_size
    protect(root,max(needed,FORECAST-used,67108864),snapshot,own_concurrent_bytes=1073741824+geometry_future)
    if scratch is not None:tmpfs_capacity(scratch,workers)


def tmpfs_capacity(scratch,workers):
    path=Path(scratch).resolve()
    if path!=Path('/dev/shm'):raise ValueError('Only the actual node /dev/shm filesystem is admitted')
    s=os.statvfs(path);total=s.f_blocks*s.f_frsize
    reserve=max(32*1024**3,int(total*.1))
    if s.f_bavail*s.f_frsize<reserve+workers*LOCAL_PER_WORKER or s.f_favail<1024+workers*128:
        raise RuntimeError('Actual tmpfs bytes/inodes cannot cover concurrent scratch plus system/peer reserve')
    memory={line.split(':',1)[0]:int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith(('MemTotal:','MemAvailable:'))}
    if memory['MemAvailable']<workers*LOCAL_PER_WORKER+int(memory['MemTotal']*.15):
        raise RuntimeError('Actual available RAM cannot cover tmpfs peak plus 15 percent node reserve')
    root=os.statvfs('/tmp');root_total=root.f_blocks*root.f_frsize
    if root.f_bavail*root.f_frsize<max(10*1024**3,int(root_total*.1)) or root.f_favail<1024:
        raise RuntimeError('Root filesystem system/Slurm reserve is unavailable')

def schema(db):
    db.executescript('''CREATE TABLE IF NOT EXISTS tasks(record_id TEXT PRIMARY KEY,mid TEXT,conformer_id INTEGER,
        state TEXT NOT NULL DEFAULT 'PENDING',worker_pid INTEGER,job TEXT,started REAL,finished REAL,
        result BLOB,error TEXT,UNIQUE(mid,conformer_id));
        CREATE INDEX IF NOT EXISTS task_state_id ON tasks(state,record_id);
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT);''')
    db.commit()


def prepare(a):
    capacity(a.root,a.quota_snapshot)
    if getattr(a,'source_producer_job',None) is not None:seal_geometry(a.root,a.source_producer_job)
    out=a.root/'labels/Pprime/shared_v1';out.mkdir(parents=True,exist_ok=True)
    path=out/'queue.sqlite';check_access(path);db=sqlite3.connect(path,timeout=60);schema(db)
    inserted=source_records=0
    with SharedB0Reader(a.root/'geometry/shared_v1/queue.sqlite') as reader:
        for state in ('SPRIME_AND_D_READY','SPRIME_READY_D_PARTIAL'):
            after=''
            while True:
                rows=reader.db.execute('SELECT mid,result FROM tasks WHERE state=? AND mid>? ORDER BY mid LIMIT 16',
                    (state,after)).fetchall()
                if not rows:break
                after=rows[-1][0];capacity(a.root,a.quota_snapshot)
                for mid,payload in rows:
                    source=json.loads(zlib.decompress(payload));source_records+=1
                    if source['molecule_id']!=mid:raise ValueError('Source geometry identity differs')
                    for conformer in source['conformers']:
                        cid=int(conformer['conformer_id']);rid=mid+':sprime:'+str(cid)
                        inserted+=db.execute('INSERT OR IGNORE INTO tasks(record_id,mid,conformer_id) VALUES(?,?,?)',
                            (rid,mid,cid)).rowcount
                db.commit()
    total=db.execute('SELECT count(*) FROM tasks').fetchone()[0]
    source_access=check_access(a.root/'geometry/shared_v1/queue.sqlite')
    source_complete=bool(source_access and source_access.get('immutable'))
    db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('source_all_geometry_complete',json.dumps(source_complete)))
    db.execute('INSERT OR REPLACE INTO metadata VALUES(?,?)',('ready','true'));db.commit();db.close()
    report={'status':'ALL_ACCEPTED_SPRIME_QUEUED' if source_complete else 'AVAILABLE_SPRIME_PREFIX_QUEUED_NOT_ALL_SOURCE_COMPLETE','source_molecules_consumed':source_records,
        'new_conformers_queued':inserted,'total_conformers_queued':total,'queue':str(path),
        'storage_forecast_bytes':FORECAST,'same_source_geometry_no_regeneration':True,
        'source_geometry_root':str(a.root/'geometry/shared_v1'),'P_ready':False,'Pprime_ready':False,
        'source_reference_groups_not_scheduled':['C7H10O2','NMRShiftDB2','PPE1694'],
        'source_all_geometry_complete':source_complete,
        'no_scientific_retry':True,'new_data_content_hashes':False,'independent_numeric_readback':False}
    capacity(a.root,a.quota_snapshot)
    p=out/('preparation_'+str(os.environ.get('SLURM_JOB_ID','node_metadata'))+'_'+str(time.time_ns())+'.json')
    p.write_text(json.dumps(report,indent=2)+'\n');print('PPRIME_QUEUE_PREPARED',report,flush=True)


def claim(db,record_id,pid,job):
    c=db.execute("UPDATE tasks SET state='INTENT',worker_pid=?,job=?,started=? WHERE record_id=? AND state='PENDING'",
        (pid,job,time.time(),record_id))
    if c.rowcount!=1:raise RuntimeError('P-prime record already started; no scientific retry')
    db.commit()


def finish(db,record_id,result):
    c=db.execute("UPDATE tasks SET state=?,finished=?,result=?,error=? WHERE record_id=? AND state='INTENT'",
        (result['state'],time.time(),pack(result),result.get('error'),record_id))
    if c.rowcount!=1:raise RuntimeError('No matching P-prime intent')
    db.commit()


def worker(connection,root,snapshot,workers,deadline,stop_event):
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','BLIS_NUM_THREADS'):os.environ[key]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    root=Path(root);snapshot=Path(snapshot);store=reader=None
    scratch=Path('/dev/shm')/('b0pp_'+os.environ['SLURM_JOB_ID']+'_'+str(os.getpid()))
    def admit(needed):
        waiting=False
        while True:
            if stop_event.is_set():raise RuntimeError('Own producer stopped; partial outputs preserved without retry')
            try:
                capacity(root,snapshot,needed,workers=workers,scratch='/dev/shm')
                if waiting:print('PPRIME_DISK_RESUMED',os.getpid(),flush=True)
                return
            except (OSError,ValueError,KeyError,RuntimeError) as exc:
                if not waiting:print('PPRIME_DISK_WAIT',os.getpid(),repr(exc),flush=True)
                waiting=True
                if time.time()>=deadline-30:raise RuntimeError('Storage observation unavailable at original lifecycle deadline')
                time.sleep(2)
    try:
        admit(67108864);scratch.mkdir(mode=0o700,exist_ok=False)
        from .pprime_tmpfs_science import load
        science=load(scratch,deadline,stop_event)
        store=LaneStore(root/'labels/Pprime/shared_v1'/('lane_'+os.environ['SLURM_JOB_ID']+'_'+str(os.getpid())+'.sqlite'))
        reader=SharedB0Reader(root/'geometry/shared_v1/queue.sqlite')
        connection.send({'event':'ready'})
        while True:
            task=connection.recv()
            if task is None:return
            began=time.monotonic()
            retire=False
            try:
                source_row=reader.db.execute('SELECT state,result FROM tasks WHERE mid=?',(task['mid'],)).fetchone()
                if source_row is None or source_row[1] is None:raise ValueError('Accepted source S-prime record is unavailable')
                source=json.loads(zlib.decompress(source_row[1]))
                conformers=[c for c in source['conformers'] if c['conformer_id']==task['conformer_id']]
                if source['molecule_id']!=task['mid'] or len(conformers)!=1:raise ValueError('Source molecule/conformer identity differs')
                cid=task['conformer_id'];heavy=sum(n!=1 for n in source['atomic_numbers'])
                stratum=next((str(bound) for bound in (22,26,30,36) if heavy<=bound),'above36')
                # A deterministic record audit within size strata; this hashes
                # the scientific identity only, never the data payload.
                audit=int.from_bytes(hashlib.sha256(('B0:Pprime:audit:20261010:'+stratum+':'+task['record_id']).encode()).digest()[:8],'big')%100==0
                row={'record_id':task['record_id'],'molecule_id':task['mid'],'conformer_id':cid,
                    'record_payload_sha256':None,'audit_selected':audit,'size_stratum':stratum}
                result=science.compute(source,conformers[0],row,store,admit)
                neutral=next(d for d in result['tasks'] if d['task']=='pm7_B')
                result['derived_same_geometry']=neutral.get('values',{}).get('derived_from_same_geometry_charged_states',{})
                # Parsed values exist exactly once in the lane's per-call store.
                # Keep only outcomes/locators and the final cross-task derivation
                # in the coordinating database, avoiding a second label copy.
                result['tasks']=[{k:d.get(k) for k in ('task','source_status','scope_status','failure_code','raw_ref')}
                    for d in result['tasks']]
                result['state']='PPRIME_READY' if result['all_twelve_tasks_success'] else 'PPRIME_PARTIAL_WITH_RECORDED_OUTCOMES'
                result.update(lane_store=str(store.path),elapsed_seconds=time.monotonic()-began,
                    source_queue=str(reader.path),additional_data_hashes=False)
            except Exception as exc:
                result={'state':'PARTIAL_OR_IMPLEMENTATION_FAILED_NO_RETRY','error':repr(exc),
                    'lane_store':str(store.path),'elapsed_seconds':time.monotonic()-began,
                    'parsed_calls_preserved':True,'scratch_preserved':science.call_scratch is not None,
                    'preserved_scratch':str(science.call_scratch) if science.call_scratch is not None else None}
                retire=science.call_scratch is not None or stop_event.is_set()
            connection.send({'event':'result','record_id':task['record_id'],'result':result})
            if retire:
                connection.send({'event':'initialization_failed','error':'Own partial scratch retained; no new calls on this lane'})
                return
    except Exception as exc:connection.send({'event':'initialization_failed','error':repr(exc)})
    finally:
        if store is not None:store.close()
        if reader is not None:reader.close()


def run(a):
    access_path=a.root/'labels/Pprime/shared_v1/access.json'
    if access_path.is_file():
        access=json.loads(access_path.read_text())
        if access.get('immutable') and access.get('writers_closed'):
            report=json.loads(Path(access['producer_manifest']).read_text())
            if report['status']!='ALL_QUEUED_PPRIME_TERMINAL':raise ValueError('Sealed producer manifest status differs')
            print('PPRIME_ALREADY_CLOSED_NO_NEW_NATIVE_CALLS',access['producer_job'],flush=True)
            return
    capacity(a.root,a.quota_snapshot,workers=a.workers,scratch='/dev/shm')
    path=a.root/'labels/Pprime/shared_v1/producer.lock'
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        s=os.fstat(fd)
        if not stat.S_ISREG(s.st_mode) or s.st_uid!=os.getuid():raise ValueError('Invalid producer lock owner/type')
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        publish(path.parent/'access.json',{'producer_job':os.environ['SLURM_JOB_ID'],
            'producer_node':socket.gethostname().split('.')[0],'cross_node_read_allowed':False,'immutable':False})
        _run(a)
        report=json.loads((path.parent/('producer_'+os.environ['SLURM_JOB_ID']+'.json')).read_text())
        fully_closed=report['status']=='ALL_QUEUED_PPRIME_TERMINAL'
        capacity(a.root,a.quota_snapshot)
        publish(path.parent/'access.json',{'producer_job':os.environ['SLURM_JOB_ID'],
            'producer_node':socket.gethostname().split('.')[0],'cross_node_read_allowed':fully_closed,
            'immutable':fully_closed,'writers_closed':True,'producer_manifest':str(path.parent/('producer_'+os.environ['SLURM_JOB_ID']+'.json'))})
    finally:os.close(fd)


def _run(a):
    if os.environ.get('SLURM_JOB_PARTITION')!='cpu' or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:
        raise RuntimeError('Actual CPU Slurm allocation required')
    node=socket.gethostname().split('.')[0]
    if node not in {'compute-0-'+str(i) for i in range(8,20)}:raise RuntimeError('Authorized CPU node required')
    path=a.root/'labels/Pprime/shared_v1/queue.sqlite'
    capacity(a.root,a.quota_snapshot,workers=a.workers,scratch='/dev/shm')
    db=sqlite3.connect(path,timeout=60)
    if db.execute("SELECT value FROM metadata WHERE key='ready'").fetchone()!=('true',):raise RuntimeError('Source queue is not prepared')
    source_complete=db.execute("SELECT value FROM metadata WHERE key='source_all_geometry_complete'").fetchone()==('true',)
    db.execute("UPDATE tasks SET state='UNKNOWN_INTERRUPTED_NO_RETRY',error='Prior parent intent without committed completion' WHERE state='INTENT'");db.commit()
    stop=[False];previous=signal.signal(signal.SIGTERM,lambda *args:stop.__setitem__(0,True))
    started=time.time();deadline=started+a.wall_seconds-120;context=mp.get_context('spawn');slots=[]
    stop_event=context.Event()
    for _ in range(a.workers):
        parent,child=context.Pipe();process=context.Process(target=worker,args=(child,str(a.root),str(a.quota_snapshot),a.workers,deadline,stop_event));process.start();child.close()
        slots.append({'process':process,'connection':parent,'ready':False,'task':None})
    admitted=True;last_guard=last_report=0;completed=0;fatal=None
    try:
        while True:
            now=time.time()
            if now-last_guard>=15:
                try:capacity(a.root,a.quota_snapshot,workers=a.workers,scratch='/dev/shm');admitted=True
                except (OSError,ValueError,KeyError,RuntimeError) as exc:
                    if admitted:print('PPRIME_PARENT_DISK_WAIT',repr(exc),flush=True)
                    admitted=False
                last_guard=now
            draining=stop[0] or now>=deadline-10920
            for slot in slots:
                connection=slot['connection']
                if slot.get('held_result') is not None and admitted:
                    finish(db,slot['task']['record_id'],slot.pop('held_result'));completed+=1;slot['task']=None
                if slot.get('held_result') is None and connection.poll():
                    try:message=connection.recv()
                    except EOFError:message={'event':'worker_lost'}
                    if message['event']=='ready':slot['ready']=True
                    elif message['event']=='result':
                        if message['record_id']!=slot['task']['record_id']:raise RuntimeError('Worker/source intent differs')
                        slot['held_result']=message['result']
                    else:
                        fatal=message.get('error','Worker lost; prior calls remain preserved');stop[0]=True
                        if slot['task'] is not None:slot['held_result']={'state':'UNKNOWN_WORKER_LOST_NO_RETRY','error':fatal}
                        slot['ready']=False
                if slot['ready'] and slot['task'] is None and admitted and not draining and fatal is None:
                    pending=db.execute("SELECT record_id,mid,conformer_id FROM tasks WHERE state='PENDING' ORDER BY record_id LIMIT 1").fetchone()
                    if pending:
                        rid,mid,cid=pending;claim(db,rid,slot['process'].pid,os.environ['SLURM_JOB_ID'])
                        slot['task']={'record_id':rid,'mid':mid,'conformer_id':cid};connection.send(slot['task'])
            busy=any(s['task'] is not None for s in slots)
            pending=db.execute("SELECT EXISTS(SELECT 1 FROM tasks WHERE state='PENDING')").fetchone()[0]
            if now-last_report>=60:
                print('PPRIME_PROGRESS',completed,dict(db.execute('SELECT state,count(*) FROM tasks GROUP BY state')),flush=True);last_report=now
            if admitted and not busy and (not pending or draining or fatal):break
            time.sleep(.1)
        capacity(a.root,a.quota_snapshot)
        status=('ALL_QUEUED_PPRIME_TERMINAL' if source_complete else 'AVAILABLE_PREFIX_TERMINAL') if not pending and not fatal else 'PARTIAL_PRESERVED'
        report={'status':status,
            'job':os.environ['SLURM_JOB_ID'],'states':dict(db.execute('SELECT state,count(*) FROM tasks GROUP BY state')),
            'completed_this_parent':completed,'workers':a.workers,'error':fatal,'P_ready':False,
            'new_data_content_hashes':False,'independent_numeric_readback':False,'source_all_geometry_complete':source_complete}
        (path.parent/('producer_'+os.environ['SLURM_JOB_ID']+'.json')).write_text(json.dumps(report,indent=2)+'\n')
        if fatal:raise RuntimeError(fatal)
    finally:
        if any(s['task'] is not None for s in slots):stop_event.set()
        for slot in slots:
            process=slot['process']
            if process.is_alive():
                try:slot['connection'].send(None)
                except (BrokenPipeError,EOFError):pass
            # The original native lifecycle owns verified QM-child shutdown.
            # Never kill its Python parent and orphan a still-running QM child.
            while process.is_alive():process.join(timeout=5)
            slot['connection'].close()
        signal.signal(signal.SIGTERM,previous);db.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','run'])
    p.add_argument('--root',type=Path,required=True);p.add_argument('--quota-snapshot',type=Path,required=True)
    p.add_argument('--workers',type=int,default=16);p.add_argument('--wall-seconds',type=int,default=86400)
    p.add_argument('--source-producer-job',type=int)
    a=p.parse_args();(prepare if a.command=='prepare' else run)(a)

if __name__=='__main__':main()
