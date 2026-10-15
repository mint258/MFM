"""Bounded whole-molecule UFF work queue; original LMDB is always read-only."""
from __future__ import annotations
import argparse,concurrent.futures as cf,hashlib,json,multiprocessing as mp,os,sqlite3,socket,tempfile,time,shutil
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
        row=db.execute("SELECT id,file_group,lo,hi,molecules FROM chunks WHERE state='PENDING' ORDER BY predicted_seconds DESC,id LIMIT 1").fetchone()
        if row:db.execute("UPDATE chunks SET state='RUNNING',owner=?,job_id=? WHERE id=? AND state='PENDING'",(owner,job,row[0]))
        db.commit();return row
    finally:db.close()

def finish(cid,owner,receipt):
    db=database()
    try:
        db.execute('BEGIN IMMEDIATE');cur=db.execute("UPDATE chunks SET state='DONE',receipt=? WHERE id=? AND owner=? AND state='RUNNING'",(json.dumps(receipt),cid,owner));assert cur.rowcount==1;db.commit()
    finally:db.close()

def run_full(workers):
    import duckdb
    job=os.environ['SLURM_JOB_ID'];assert 16<=workers<=int(os.environ['SLURM_CPUS_PER_TASK'])
    assert socket.gethostname() in {'compute-0-2','compute-0-8','compute-0-9','compute-0-10','compute-0-11'}
    prepared=json.loads((FULL/'prepared.json').read_text());assert sha(science.__file__)==prepared['source_sha256'] and sha(__file__)==prepared['worker_sha256']
    owner=socket.gethostname()+':'+job;deadline=time.monotonic()+46*3600
    scratch=Path(tempfile.mkdtemp(prefix='spfull_'+job+'_',dir='/tmp'));os.chmod(scratch,0o700)
    db=duckdb.connect();db.execute(f'SET threads={min(workers,16)}');db.execute("SET memory_limit='10GB'");db.execute(f"SET temp_directory='{scratch}'")
    schemas={name:pa.ipc.read_schema(pa.BufferReader((FULL/(name+'.schema')).read_bytes())) for name in ['molecules','conformers']}
    db.execute(f"CREATE VIEW pointers AS SELECT * FROM read_parquet('{FULL/'record_pointers.parquet'}')")
    db.execute(f"CREATE VIEW mol AS SELECT * FROM read_parquet('{POP/'molecule_index.parquet'}')")
    db.execute(f"CREATE VIEW pilot AS SELECT molecule_id FROM read_parquet('{ROOT/'prepared/pilot_molecules.parquet'}')")
    completed=0
    try:
        with cf.ProcessPoolExecutor(max_workers=workers,mp_context=mp.get_context('spawn'),initializer=science.worker_init) as pool:
            while time.monotonic()<deadline-3600:
                chunk=claim(owner,job)
                if chunk is None:break
                cid,group,lo,hi,expected=chunk;started=time.monotonic()
                metas=db.execute('SELECT m.* FROM mol m ANTI JOIN pilot USING(molecule_id) WHERE file_group=? AND molecule_id BETWEEN ? AND ? ORDER BY molecule_id',(group,lo,hi)).fetch_arrow_table().to_pylist()
                rows=db.execute('SELECT p.* FROM pointers p ANTI JOIN pilot USING(molecule_id) WHERE file_group=? AND molecule_id BETWEEN ? AND ? ORDER BY molecule_id,real_index',(group,lo,hi)).fetch_arrow_table().to_pylist()
                indexed={m['molecule_id']:[] for m in metas}
                for r in rows:indexed[r['molecule_id']].append(r)
                assert len(metas)==expected and sum(m['records'] for m in metas)==len(rows)
                paths={n:FULL/'parts'/f'g{group}_c{cid:04d}_{n}.parquet' for n in ['molecules','conformers']}
                assert not any(p.exists() for p in paths.values())
                writers={n:pq.ParquetWriter(str(p)+'.pending',schemas[n],compression='zstd') for n,p in paths.items()}
                # Start the largest molecules first to reduce idle CPUs at chunk tails.
                task_iter=iter(sorted(metas,key=lambda m:(-int(m['max_heavy_atoms']),-int(m['records']),m['molecule_id'])));inflight={};mol_count=conf_count=0;buffer_m=[];buffer_c=[]
                def submit_one():
                    try:m=next(task_iter)
                    except StopIteration:return False
                    f=pool.submit(science.process,(indexed[m['molecule_id']],m));inflight[f]=m['molecule_id'];return True
                for _ in range(workers*3):
                    if not submit_one():break
                try:
                    while inflight:
                        done,_=cf.wait(inflight,return_when=cf.FIRST_COMPLETED)
                        for f in done:
                            inflight.pop(f);summary,confs=f.result();buffer_m.append(summary);buffer_c.extend(confs);mol_count+=1;conf_count+=len(confs);submit_one()
                        if len(buffer_m)>=64 or not inflight:
                            writers['molecules'].write_table(pa.Table.from_pylist(buffer_m,schema=schemas['molecules']))
                            if buffer_c:writers['conformers'].write_table(pa.Table.from_pylist(buffer_c,schema=schemas['conformers']))
                            buffer_m=[];buffer_c=[]
                            save(FULL/f'progress_{job}.json',{'job_id':job,'owner':owner,'chunk_id':cid,'chunk_done_molecules':mol_count,'chunk_total_molecules':expected,'closed_previous_chunks':completed,'elapsed_chunk_seconds':time.monotonic()-started})
                finally:
                    for writer in writers.values():writer.close()
                assert mol_count==expected
                refs=[]
                for name,path in paths.items():
                    pending=Path(str(path)+'.pending');assert pq.ParquetFile(pending).metadata.num_rows==(mol_count if name=='molecules' else conf_count);pending.replace(path)
                    refs.append({'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'kind':name})
                receipt={'chunk_id':cid,'group':group,'job_id':job,'owner':owner,'molecules':mol_count,'conformers':conf_count,'seconds':time.monotonic()-started,'source_sha256':prepared['source_sha256'],'references':refs}
                finish(cid,owner,receipt);completed+=1
        save(FULL/f'job_{job}_closed.json',{'job_id':job,'owner':owner,'closed_chunks':completed,'deadline_normal_exit':time.monotonic()>=deadline-3600})
    finally:db.close();shutil.rmtree(scratch)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['prepare','run']);ap.add_argument('--workers',type=int,default=16);a=ap.parse_args()
    assert os.environ.get('SLURM_JOB_ID')
    if a.mode=='prepare':prepare_full()
    else:run_full(a.workers)

if __name__=='__main__':main()
