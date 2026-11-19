"""Shared B0 geometry/D queue: once-only intents, bounded workers, hard deadlines."""
import argparse
from collections import Counter
import json
import multiprocessing as mp
import os
from pathlib import Path
import signal
import sqlite3
import time
import zlib
from .admission import protect
from .downstream_science import identities

GUARD_INTERVAL_SECONDS=15


def schema(db):
    db.executescript('''
    CREATE TABLE tasks(mid TEXT PRIMARY KEY,model_smiles TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'PENDING',
      worker_pid INTEGER,started REAL,finished REAL,result BLOB,error TEXT);
    CREATE TABLE membership(dataset TEXT,record_id TEXT,mid TEXT,model_atom_to_source TEXT,
      PRIMARY KEY(dataset,record_id));
    CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
    CREATE INDEX task_state_mid ON tasks(state,mid);
    CREATE INDEX membership_mid ON membership(mid);
    ''')
    db.commit()


def claim(db,mid,pid):
    cur=db.execute("UPDATE tasks SET state='INTENT',worker_pid=?,started=? WHERE mid=? AND state='PENDING'",
                   (pid,time.time(),mid))
    if cur.rowcount!=1:raise RuntimeError('Task is not an unstarted pending molecule')
    db.commit()


def recover_intents(db):
    # Native work may have started before the prior parent disappeared. Never
    # turn such records into pending tasks or silently repeat the chemistry.
    db.execute("UPDATE tasks SET state='UNKNOWN_INTERRUPTED_NO_RETRY',error='Prior producer intent without durable result' WHERE state='INTENT'")
    db.commit()


def clean_json(value):
    import math
    if isinstance(value,float) and not math.isfinite(value):return None
    if isinstance(value,dict):return {k:clean_json(v) for k,v in value.items()}
    if isinstance(value,list):return [clean_json(v) for v in value]
    return value


def finish(db,mid,result):
    result=clean_json(result)
    payload=zlib.compress(json.dumps(result,separators=(',',':'),allow_nan=False).encode(),3)
    cur=db.execute("UPDATE tasks SET state=?,finished=?,result=?,error=? WHERE mid=? AND state='INTENT'",
        (result['state'],time.time(),payload,result.get('error'),mid))
    if cur.rowcount!=1:raise RuntimeError('Molecule result has no matching active intent')
    db.commit()


def prepare(args):
    import pyarrow.parquet as pq
    progress=json.loads(args.progress.read_text())
    out=args.output
    ancestor=out.parent
    while not ancestor.exists():ancestor=ancestor.parent
    protect(ancestor,1073741824,args.quota_snapshot)
    out.parent.mkdir(parents=True,exist_ok=True)
    if out.exists():raise FileExistsError('Existing queue is preserved; choose another preparation output')
    db=sqlite3.connect(out)
    try:
        schema(db)
        db.execute('INSERT INTO metadata VALUES (?,?)',('ready','false'))
        db.execute('INSERT INTO metadata VALUES (?,?)',('domain_progress',str(args.progress)))
        db.execute('INSERT INTO metadata VALUES (?,?)',('recipe',json.dumps({
            'rdkit':'2025.09.5','source':'sprime_v6.py','max_actual_conformers':3,
            'candidate_pool':9,'UFF':'MinimizeTrajectory snapshot1 maxIts2000 energyTol1e-6 forceTol1e-4',
            'ETKDG':'v3 numThreads1 enforceChirality maxIterations200 pruneRmsThresh-1',
            'seed':'original sha256(sprime-ETKDGv3-v1:+MID), first4 big endian,31bit,min1',
            'dedup_A':0.5,'per_molecule_hard_seconds':3600,'no_padding':True,
            'no_scientific_retry':True,'unassigned_stereo':'D20 only; no invented reference',
            'atom_order':'Source model SMILES parser order(removeHs=False); new H appended',
            'PM7_optimization':'UNRECOVERED_ORIGINAL_BINARY_VERSION; allowed Sprime/D/Pprime fallback; P pending',
            'D20':'original 20 functions and names; no Kappa',
            'D3':'original c_engineering_wire.corrected_base; original units and atom order'})))
        records=0
        for dataset,entry in progress['domains'].items():
            report=json.loads(Path(entry['manifest']).read_text())
            for batch in pq.ParquetFile(report['records']).iter_batches(batch_size=4096,
                    columns=['record_id','model_smiles','model_atom_to_source','domain_eligible']):
                protect(out.parent,1073741824,args.quota_snapshot)
                for row in batch.to_pylist():
                    if not row['domain_eligible']:continue
                    mid,_=identities(row['model_smiles'])
                    db.execute('INSERT OR IGNORE INTO tasks(mid,model_smiles) VALUES (?,?)',(mid,row['model_smiles']))
                    db.execute('INSERT INTO membership VALUES (?,?,?,?)',(dataset,row['record_id'],mid,
                        json.dumps(row['model_atom_to_source'])))
                    records+=1
                db.commit()
        db.execute("UPDATE metadata SET value='true' WHERE key='ready'")
        db.commit()
        tasks=db.execute('SELECT count(*) FROM tasks').fetchone()[0]
        forecast=max(2147483648,tasks*400000+out.stat().st_size)
        db.execute('INSERT INTO metadata VALUES (?,?)',('storage_forecast_bytes',str(forecast)));db.commit()
        report={'status':'GEOMETRY_QUEUE_PREPARED_NOT_COMPUTED','queue':str(out),
            'source_records':records,'unique_ordered_model_smiles':tasks,
            'storage_forecast_bytes':forecast,
            'cross_source_atom_remapping':False,'geometry_and_D_ready':False,
            'reference_geometry_groups_not_scheduled':['NMRShiftDB2','C7H10O2','PPE1694'],
            'source_progress':str(args.progress),'new_content_hashes':False}
        out.with_suffix('.manifest.json').write_text(json.dumps(report,indent=2)+'\n')
        print('GEOMETRY_QUEUE_PREPARED',tasks,records,out,flush=True)
    finally:db.close()


def worker(connection):
    for name in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
    os.environ['CUDA_VISIBLE_DEVICES']=''
    from .downstream_science import load,process
    try:load();connection.send({'event':'ready'})
    except BaseException as exc:connection.send({'event':'initialization_failed','error':repr(exc)});return
    while True:
        task=connection.recv()
        if task is None:return
        start=time.monotonic();cpu=time.process_time()
        arm_deadline(3600)
        result=process(task)
        signal.setitimer(signal.ITIMER_REAL,0)
        result.update(elapsed_seconds=time.monotonic()-start,worker_cpu_seconds=time.process_time()-cpu)
        connection.send({'event':'result','mid':task['mid'],'result':result})


def arm_deadline(seconds):
    # Kernel default termination applies even while a C++ RDKit call or the
    # parent filesystem RPC is blocked; no Python exception-handler latency.
    signal.signal(signal.SIGALRM,signal.SIG_DFL)
    signal.setitimer(signal.ITIMER_REAL,seconds)


def run(args):
    if int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<args.workers:
        raise RuntimeError('Workers exceed actual allocated CPUs')
    if os.environ.get('SLURM_JOB_PARTITION')!='cpu':raise RuntimeError('CPU partition required')
    out=args.queue.parent
    protect(out,1048576,args.quota_snapshot)
    db=sqlite3.connect(args.queue)
    if db.execute("SELECT value FROM metadata WHERE key='ready'").fetchone()!=('true',):
        raise RuntimeError('Input preparation is not closed')
    peak=int(db.execute("SELECT value FROM metadata WHERE key='storage_forecast_bytes'").fetchone()[0])
    protect(out,max(67108864,peak-args.queue.stat().st_size),args.quota_snapshot)
    recover_intents(db)
    ctx=mp.get_context('spawn');slots=[];started=time.monotonic();stop=[False]
    prior_handler=signal.signal(signal.SIGTERM,lambda signum,frame:stop.__setitem__(0,True))
    def launch():
        parent,child=ctx.Pipe()
        process=ctx.Process(target=worker,args=(child,));process.start();child.close()
        return {'process':process,'connection':parent,'ready':False,'mid':None,'start':time.monotonic()}
    def terminate(slot):
        process=slot['process']
        if process.is_alive():process.terminate()
        process.join(timeout=5)
        if process.is_alive():process.kill();process.join(timeout=5)
        slot['connection'].close()
    for _ in range(args.workers):slots.append(launch())
    completed=0;last_report=last_guard=0;fatal=None;admitted=True
    try:
        while True:
            now=time.monotonic()
            if now-last_guard>=GUARD_INTERVAL_SECONDS:
                # Already written bytes are part of actual quota use, not a
                # second future reservation of the whole output forecast.
                remaining=max(67108864,peak-args.queue.stat().st_size)
                try:
                    protect(out,remaining,args.quota_snapshot)
                    if not admitted:print('GEOMETRY_DISK_RESUMED',flush=True)
                    admitted=True
                except (OSError,ValueError,KeyError,RuntimeError) as exc:
                    if admitted:print('GEOMETRY_DISK_WAIT',repr(exc),flush=True)
                    admitted=False
                last_guard=now
            draining=stop[0] or now-started>=82800
            for index,slot in enumerate(slots):
                connection=slot['connection']
                if slot.get('held_result') is not None and admitted:
                    finish(db,slot['mid'],slot.pop('held_result'));completed+=1;slot['mid']=None
                    if slot.get('closed'):
                        slots[index]=launch();continue
                if slot['mid'] and slot.get('held_result') is None and time.monotonic()-slot['start']>=3600:
                    mid=slot['mid'];terminate(slot)
                    slot.update(held_result={'state':'TIMEOUT_3600_NO_RETRY','error':'Hard molecule deadline exceeded'},closed=True)
                    continue
                if not slot.get('closed') and slot.get('held_result') is None and connection.poll():
                    try:message=connection.recv()
                    except EOFError:message={'event':'worker_lost'}
                    if message['event']=='ready':slot['ready']=True
                    elif message['event']=='result':
                        if message['mid']!=slot['mid']:raise RuntimeError('Worker/molecule identity differs')
                        # Keep at most one completed result per worker in memory
                        # until a fresh actual storage/quota observation permits
                        # its commit. No new chemistry is dispatched while waiting.
                        slot['held_result']=message['result']
                    elif message['event']=='initialization_failed':
                        fatal=message['error'];stop[0]=True
                    elif slot['mid']:
                        slot['process'].join(timeout=.1)
                        timed_out=slot['process'].exitcode==-signal.SIGALRM
                        slot['held_result']={'state':'TIMEOUT_3600_NO_RETRY' if timed_out else 'UNKNOWN_WORKER_LOST_NO_RETRY',
                            'error':'Own worker kernel deadline' if timed_out else 'Own worker disappeared'}
                        terminate(slot);slot['closed']=True;continue
                    else:
                        fatal='Own worker exited before a molecule was assigned';stop[0]=True
                if slot['mid'] is None and slot['ready'] and admitted and not draining and not fatal:
                    pending=db.execute("SELECT mid,model_smiles FROM tasks WHERE state='PENDING' ORDER BY mid LIMIT 1").fetchone()
                    if pending:
                        mid,smiles=pending;claim(db,mid,slot['process'].pid)
                        slot['mid']=mid;slot['start']=time.monotonic()
                        connection.send({'mid':mid,'model_smiles':smiles})
            busy=any(slot['mid'] is not None for slot in slots)
            pending=db.execute("SELECT EXISTS(SELECT 1 FROM tasks WHERE state='PENDING')").fetchone()[0]
            if now-last_report>=30:
                states=dict(db.execute('SELECT state,count(*) FROM tasks GROUP BY state'))
                print('GEOMETRY_PROGRESS',completed,states,'busy',sum(s['mid'] is not None for s in slots),flush=True)
                last_report=now
            if admitted and not busy and (not pending or draining or fatal):break
            time.sleep(.05)
        states=dict(db.execute('SELECT state,count(*) FROM tasks GROUP BY state'))
        manifest={'status':'ALL_QUEUED_MOLECULES_TERMINAL' if not pending and not fatal else 'PARTIAL_PRESERVED',
            'queue':str(args.queue),'states':states,'job':os.environ.get('SLURM_JOB_ID'),
            'molecules_terminalized_this_parent':completed,'workers':args.workers,'error':fatal,
            'elapsed_seconds':time.monotonic()-started,'per_molecule_hard_seconds':3600,
            'storage':'One shared SQLite; zlib3 JSON results, finite F64 roundtrip, null masked failures',
            'Pprime_ready':False,'P_ready':False,'independent_numeric_readback':False,
            'no_scientific_retry':True,'new_data_hashes':False}
        protect(out,1048576,args.quota_snapshot)
        target=out/('producer_'+str(os.environ.get('SLURM_JOB_ID'))+'.json')
        with target.open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
        if fatal:raise RuntimeError(fatal)
    finally:
        for slot in slots:terminate(slot)
        signal.signal(signal.SIGTERM,prior_handler)
        db.close()


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    prep=sub.add_parser('prepare');prep.add_argument('--progress',type=Path,required=True)
    prep.add_argument('--output',type=Path,required=True)
    native=sub.add_parser('run');native.add_argument('--queue',type=Path,required=True)
    native.add_argument('--workers',type=int,required=True)
    for parser in (prep,native):parser.add_argument('--quota-snapshot',type=Path,required=True)
    args=p.parse_args()
    (prepare if args.command=='prepare' else run)(args)

if __name__=='__main__':main()
