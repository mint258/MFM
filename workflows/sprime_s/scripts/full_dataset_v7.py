"""Bounded whole-molecule UFF work queue; original LMDB is always read-only."""
from __future__ import annotations
import argparse,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,sqlite3,socket,tempfile,time,shutil,signal
from pathlib import Path
import pyarrow as pa,pyarrow.parquet as pq
from prepare import PROJECT,ROOT,POP,save,sha
import sprime_v6 as science

FULL=ROOT/'full';DB=FULL/'work.sqlite'

def database():
    db=sqlite3.connect(DB,timeout=120);db.execute('PRAGMA journal_mode=DELETE');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA busy_timeout=120000');return db

def eligible():
    summary_path=ROOT/'reports/pilot_summary.json'
    result=json.loads(summary_path.read_text())
    if result['status']!='FULL_RUN_ELIGIBLE':
        decision_path=ROOT/'reports/full_run_user_decision.json'
        assert decision_path.exists(),'A7 requires an explicit user decision after the pilot report'
        decision=json.loads(decision_path.read_text())
        assert decision['status']=='APPROVED_BY_USER'
        assert decision['scope']=='A_FULL_SPRIME_GENERATION'
        assert decision['pilot_summary_sha256']==sha(summary_path),'Decision is for a different pilot report'
        assert decision['user_instruction'].strip(),'No inferred or fabricated approval permitted'
    assert json.loads((ROOT/'reports/pilot_reproduction100.json').read_text())['status']=='PASS'
    quota=json.loads((ROOT/'reports/full_quota_preflight.json').read_text())
    assert quota['valid_for_submission'] and quota['valid_until_epoch']>=time.time(),'Refresh the actual account quota preflight'
    assert quota['pilot_summary_sha256']==sha(summary_path)
    return result

def prepare_full():
    import duckdb
    eligible();assert int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    if DB.exists():raise FileExistsError('Full queue already prepared')
    FULL.mkdir(exist_ok=True,parents=True);(FULL/'parts').mkdir(exist_ok=True)
    scratch=Path(tempfile.mkdtemp(prefix='spfullprep_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='20GB'");db.execute(f"SET temp_directory='{scratch}'")
    columns='record_id,molecule_id,file_group,source_path,real_index,record_payload_sha256,total_atoms,energy_raw,smiles,QC_molecule_chirality_conflict,QC_molecule_ez_conflict'
    pointers=FULL/'record_pointers.parquet'
    db.execute(f"COPY (SELECT {columns} FROM read_parquet('{POP/'formal_record_index.parquet'}') ORDER BY file_group,molecule_id,real_index) TO '{pointers}.pending' (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 65536)")
    Path(str(pointers)+'.pending').replace(pointers)
    db.execute(f"CREATE VIEW mol AS SELECT * FROM read_parquet('{POP/'molecule_index.parquet'}')")
    db.execute(f"CREATE VIEW pilot AS SELECT molecule_id FROM read_parquet('{ROOT/'prepared/pilot_molecules.parquet'}')")
    remaining=db.execute('SELECT molecule_id,file_group,max_heavy_atoms,max_total_atoms,records FROM mol ANTI JOIN pilot USING(molecule_id) ORDER BY file_group,molecule_id').fetchall()
    queue=database()
    queue.execute('CREATE TABLE chunks(id INTEGER PRIMARY KEY,file_group INTEGER,lo TEXT,hi TEXT,molecules INTEGER,predicted_seconds REAL,state TEXT,owner TEXT,job_id TEXT,receipt TEXT)')
    means={g['file_group']:g['mean_seconds_per_molecule'] for g in eligible()['groups']}
    chunks=[];cid=0
    for group in range(1,6):
        selected=[r for r in remaining if r[1]==group]
        for offset in range(0,len(selected),5000):
            piece=selected[offset:offset+5000];cid+=1
            chunks.append((cid,group,piece[0][0],piece[-1][0],len(piece),len(piece)*means[group],'PENDING',None,None,None))
    queue.executemany('INSERT INTO chunks VALUES(?,?,?,?,?,?,?,?,?,?)',chunks);queue.commit();queue.close();db.close();shutil.rmtree(scratch)
    schemas={'molecules':pq.read_schema(ROOT/'pilot_v6/molecules_group1.parquet'),'conformers':pq.read_schema(ROOT/'pilot_v6/conformers_group1.parquet')}
    # A rare embedding exception adds a nullable diagnostic; coordinate and key types are fixed.
    m_schema=schemas['molecules']
    if 'first_embedding_error' not in m_schema.names:m_schema=m_schema.append(pa.field('first_embedding_error',pa.string()))
    for name,schema in [('molecules',m_schema),('conformers',schemas['conformers'])]:
        (FULL/(name+'.schema')).write_bytes(schema.serialize().to_pybytes())
    save(FULL/'prepared.json',{'status':'READY','remaining_molecules':len(remaining),'pilot_reused_molecules':10000,'chunks':len(chunks),'source_sha256':sha(science.__file__),'worker_sha256':sha(__file__),'record_pointers':{'path':str(pointers),'bytes':pointers.stat().st_size,'sha256':sha(pointers)},'queue_path':str(DB),'formal_molecules':1220466,'formal_records':11231854,'rmsd_mapping':'source_atom_index_heavy_atoms','original_lmdb_written':False,'new_lmdb_created':False})

def claim(owner,job):
    db=database()
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT id,file_group,lo,hi,molecules,receipt FROM chunks WHERE state='PENDING' ORDER BY predicted_seconds DESC,id LIMIT 1").fetchone()
        if row:db.execute("UPDATE chunks SET state='RUNNING',owner=?,job_id=? WHERE id=? AND state='PENDING'",(owner,job,row[0]))
        db.commit();return row
    finally:db.close()

def finish(cid,owner,receipt):
    db=database()
    try:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute("SELECT molecules,receipt FROM chunks WHERE id=? AND owner=? AND state='RUNNING'",(cid,owner)).fetchone();assert row is not None
        expected,old=row;prior=json.loads(old)['segments'] if old else []
        assert receipt['segment_index']==len(prior) and receipt['molecules']>0
        segments=prior+[receipt];count=sum(r['molecules'] for r in segments);assert count<=expected
        aggregate={'chunk_id':cid,'group':receipt['group'],'molecules':count,'conformers':sum(r['conformers'] for r in segments),'source_sha256':receipt['source_sha256'],'segments':segments,'references':[ref for r in segments for ref in r['references']]}
        state='DONE' if count==expected else 'PENDING'
        cur=db.execute("UPDATE chunks SET state=?,receipt=?,owner=NULL,job_id=NULL WHERE id=? AND owner=? AND state='RUNNING'",(state,json.dumps(aggregate),cid,owner));assert cur.rowcount==1;db.commit();return state
    finally:db.close()

def worker_init():
    science.worker_init()
    import torch
    torch.set_num_threads(1)
    if torch.get_num_interop_threads()!=1:torch.set_num_interop_threads(1)

def run_full(workers):
    import duckdb
    job=os.environ['SLURM_JOB_ID'];assert 16<=workers<int(os.environ['SLURM_CPUS_PER_TASK'])
    assert socket.gethostname() in {'compute-0-2','compute-0-8','compute-0-9','compute-0-10','compute-0-11'}
    prepared=json.loads((FULL/'prepared.json').read_text());assert sha(science.__file__)==prepared['source_sha256'] and sha(__file__)==prepared['worker_sha256']
    owner=socket.gethostname()+':'+job;started=time.monotonic();stop_feeding_at=started+38*3600
    scratch=Path(tempfile.mkdtemp(prefix='spfull_'+job+'_',dir='/tmp'));os.chmod(scratch,0o700)
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    db=duckdb.connect();db.execute('SET threads=1');db.execute("SET memory_limit='10GB'");db.execute(f"SET temp_directory='{scratch}'")
    schemas={name:pa.ipc.read_schema(pa.BufferReader((FULL/(name+'.schema')).read_bytes())) for name in ['molecules','conformers']}
    db.execute(f"CREATE VIEW pointers AS SELECT * FROM read_parquet('{FULL/'record_pointers.parquet'}')")
    db.execute(f"CREATE VIEW mol AS SELECT * FROM read_parquet('{POP/'molecule_index.parquet'}')")
    db.execute(f"CREATE VIEW pilot AS SELECT molecule_id FROM read_parquet('{ROOT/'prepared/pilot_molecules.parquet'}')")
    active={};inflight={};feeder=None;completed=0;segments_closed=0;last_progress=0.;no_pending_until=0.;stop_requested=False
    def request_stop(signum,frame):
        nonlocal stop_requested
        stop_requested=True
    signal.signal(signal.SIGTERM,request_stop)
    signal.signal(signal.SIGUSR1,request_stop)
    def may_feed():return not stop_requested and time.monotonic()<stop_feeding_at
    def flush(c):
        if not c['buffer_m']:return
        c['writers']['molecules'].write_table(pa.Table.from_pylist(c['buffer_m'],schema=schemas['molecules']))
        if c['buffer_c']:c['writers']['conformers'].write_table(pa.Table.from_pylist(c['buffer_c'],schema=schemas['conformers']))
        c['buffer_m']=[];c['buffer_c']=[]
    def close_segment(c):
        nonlocal completed,segments_closed,feeder
        flush(c)
        for writer in c['writers'].values():writer.close()
        if c['done']:
            refs=[]
            for kind,path in c['paths'].items():
                pending=Path(str(path)+'.pending');assert pq.ParquetFile(pending).metadata.num_rows==(c['done'] if kind=='molecules' else c['conformers']);pending.replace(path)
                refs.append({'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'kind':kind})
            receipt={'chunk_id':c['cid'],'segment_index':c['segment_index'],'group':c['group'],'job_id':job,'owner':owner,'molecules':c['done'],'conformers':c['conformers'],'seconds':time.monotonic()-c['started'],'source_sha256':prepared['source_sha256'],'references':refs}
            state=finish(c['cid'],owner,receipt);completed+=state=='DONE';segments_closed+=1
        else:
            queue=database();cur=queue.execute("UPDATE chunks SET state='PENDING',owner=NULL,job_id=NULL WHERE id=? AND owner=? AND state='RUNNING'",(c['cid'],owner));assert cur.rowcount==1;queue.commit();queue.close()
        active.pop(c['cid'])
        if feeder==c['cid']:feeder=None
    def load_chunk():
        nonlocal feeder,no_pending_until
        row=claim(owner,job)
        if row is None:no_pending_until=time.monotonic()+60;return False
        cid,group,lo,hi,expected,old=row;prior=json.loads(old) if old else {'segments':[],'molecules':0};skip=set()
        for ref in prior.get('references',[]):
            path=Path(ref['path']);assert path.stat().st_size==ref['bytes'] and sha(path)==ref['sha256']
            if ref['kind']=='molecules':
                ids=pq.read_table(path,columns=['molecule_id'],use_threads=False).column(0).to_pylist();assert not skip.intersection(ids);skip.update(ids)
        assert len(skip)==prior['molecules']<expected
        metas=db.execute('SELECT m.* FROM mol m ANTI JOIN pilot USING(molecule_id) WHERE file_group=? AND molecule_id BETWEEN ? AND ? ORDER BY molecule_id',(group,lo,hi)).fetch_arrow_table().to_pylist()
        rows=db.execute('SELECT p.* FROM pointers p ANTI JOIN pilot USING(molecule_id) WHERE file_group=? AND molecule_id BETWEEN ? AND ? ORDER BY molecule_id,real_index',(group,lo,hi)).fetch_arrow_table().to_pylist()
        assert len(metas)==expected and sum(m['records'] for m in metas)==len(rows)
        metas=[m for m in metas if m['molecule_id'] not in skip];indexed={m['molecule_id']:[] for m in metas}
        for r in rows:
            if r['molecule_id'] in indexed:indexed[r['molecule_id']].append(r)
        seq=len(prior['segments']);paths={kind:FULL/'parts'/f'g{group}_c{cid:04d}_s{seq:02d}_j{job}_{kind}.parquet' for kind in ['molecules','conformers']}
        assert not any(p.exists() or Path(str(p)+'.pending').exists() for p in paths.values())
        c={'cid':cid,'group':group,'segment_index':seq,'started':time.monotonic(),'remaining':len(metas),'iterator':iter(sorted(metas,key=lambda m:(-int(m['max_heavy_atoms']),-int(m['records']),m['molecule_id']))),'indexed':indexed,'exhausted':False,'pending':0,'done':0,'conformers':0,'buffer_m':[],'buffer_c':[],'paths':paths,'writers':{kind:pq.ParquetWriter(str(path)+'.pending',schemas[kind],compression='zstd') for kind,path in paths.items()}}
        active[cid]=c;feeder=cid;return True
    def fill(pool):
        nonlocal feeder
        while len(inflight)<workers*2 and may_feed():
            if feeder is None:
                if len(active)>=8 or time.monotonic()<no_pending_until or not load_chunk():break
            c=active[feeder]
            try:m=next(c['iterator'])
            except StopIteration:
                c['exhausted']=True;feeder=None
                if c['pending']==0:close_segment(c)
                continue
            rows=c['indexed'].pop(m['molecule_id']);f=pool.submit(science.process,(rows,m));inflight[f]=c['cid'];c['pending']+=1
    def progress():
        nonlocal last_progress
        if time.monotonic()-last_progress<60:return
        save(FULL/f'progress_{job}.json',{'job_id':job,'owner':owner,'elapsed_seconds':time.monotonic()-started,'closed_chunks':completed,'closed_segments':segments_closed,'active_chunks':[{'chunk_id':c['cid'],'new_done_molecules':c['done'],'remaining_at_claim':c['remaining'],'inflight':c['pending'],'feed_exhausted':c['exhausted']} for c in active.values()],'inflight':len(inflight),'stop_feeding':not may_feed(),'science_source_sha256':prepared['source_sha256']});last_progress=time.monotonic()
    try:
        with cf.ProcessPoolExecutor(max_workers=workers,mp_context=mp.get_context('spawn'),initializer=worker_init) as pool:
            while True:
                fill(pool);progress()
                if not inflight:
                    for c in list(active.values()):close_segment(c)
                    break
                done,_=cf.wait(inflight,timeout=60,return_when=cf.FIRST_COMPLETED)
                for f in done:
                    cid=inflight.pop(f);c=active[cid];summary,confs=f.result();c['pending']-=1;c['done']+=1;c['conformers']+=len(confs);c['buffer_m'].append(summary);c['buffer_c'].extend(confs)
                    if len(c['buffer_m'])>=64:flush(c)
                    if c['pending']==0 and (c['exhausted'] or not may_feed()):close_segment(c)
        save(FULL/f'job_{job}_closed.json',{'job_id':job,'owner':owner,'closed_chunks':completed,'closed_segments':segments_closed,'deadline_normal_exit':not may_feed(),'source_sha256':prepared['source_sha256']})
    finally:
        for c in active.values():
            for writer in c['writers'].values():writer.close()
        db.close();shutil.rmtree(scratch)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','run']);ap.add_argument('--workers',type=int,default=16);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    if a.mode=='prepare':prepare_full()
    else:run_full(a.workers)

if __name__=='__main__':main()
