"""Prepare immutable indices from the existing WP5 population, never write LMDB."""
from __future__ import annotations
import concurrent.futures as cf
import hashlib, json, os, pickle, socket, tempfile, time
from pathlib import Path

PROJECT = Path('/share/home/zixiao/descriptor_analysis')
ROOT = PROJECT/'runs/sprime_s_convergence_20261013'
POP = PROJECT/'runs/phase1_wp5_20261011/population'

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(8<<20),b''): h.update(b)
    return h.hexdigest()

def save(path,obj):
    path=Path(path); p=path.with_suffix(path.suffix+'.pending')
    p.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    p.replace(path)

def raw_record(row):
    import lmdb, numpy as np
    path=Path(row['source_path'])
    if not path.is_absolute(): path=PROJECT/path
    with lmdb.open(str(path),subdir=False,readonly=True,lock=False,create=False,readahead=False) as env:
        with env.begin() as tx: b=tx.get(f"{int(row['real_index']):09d}".encode())
    if b is None or hashlib.sha256(b).hexdigest()!=row['record_payload_sha256']:
        raise ValueError('ACTUAL_RECORD_MANIFEST_MISMATCH')
    d=pickle.loads(b)
    field=lambda k: d.get(k) if isinstance(d,dict) else getattr(d,k,None)
    plain=lambda v: v.detach().cpu().numpy() if hasattr(v,'detach') else np.asarray(v)
    keys=list(d.keys()) if hasattr(d,'keys') else list(vars(d))
    vals={}
    for k in ['x','pos','smiles','rdkit_node_formal_charge','rdkit_node_chiral_tag','rdkit_bond_index','rdkit_bond_order','rdkit_build_mode']:
        v=field(k)
        vals[k]=v if isinstance(v,(str,int,float)) or v is None else {'shape':list(plain(v).shape),'dtype':str(plain(v).dtype),'values':plain(v).tolist() if k!='pos' else plain(v)[:2].tolist()}
    return {'record_id':row['record_id'],'keys':keys,'values':vals}

def main():
    import duckdb, pyarrow.parquet as pq
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    threads=int(os.environ['SLURM_CPUS_PER_TASK']); start=time.time()
    out=ROOT/'prepared'; out.mkdir(exist_ok=True,parents=True)
    if (out/'population_binding.json').exists(): raise FileExistsError('Prepared indices already closed')
    manifest=json.loads((POP/'manifest.json').read_text())
    scratch=Path(tempfile.mkdtemp(prefix='sprime_prepare_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
    db=duckdb.connect(); db.execute(f'SET threads={threads}'); db.execute("SET memory_limit='20GB'")
    db.execute(f"SET temp_directory='{scratch}'")
    db.execute(f"CREATE VIEW r AS SELECT * FROM read_parquet('{POP/'formal_record_index.parquet'}')")
    db.execute(f"CREATE VIEW m AS SELECT * FROM read_parquet('{POP/'molecule_index.parquet'}')")
    schema={n:str(pq.read_schema(POP/n)) for n in ['formal_record_index.parquet','molecule_index.parquet']}
    print(json.dumps(schema),flush=True)
    counts=db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM r').fetchone()
    assert counts==(manifest['formal_records'],manifest['formal_records'],manifest['formal_molecules']),counts
    cols=[x[0] for x in db.execute('DESCRIBE r').fetchall()]
    mcols=[x[0] for x in db.execute('DESCRIBE m').fetchall()]
    roles=db.execute('SELECT split,count(*),count(DISTINCT molecule_id) FROM r GROUP BY split').fetchall()
    save(out/'schemas_and_counts.json',{'schema':schema,'roles':roles,'molecule_columns':mcols,'record_columns':cols})
    # Equal per-file-group pilot weights are corrected when extrapolating the full population.
    db.execute("CREATE TABLE pilot_m AS SELECT * EXCLUDE(rank_in_group) FROM (SELECT *,row_number() OVER(PARTITION BY file_group ORDER BY md5('sprime-pilot-v1:'||molecule_id)) AS rank_in_group FROM m) WHERE rank_in_group<=2000")
    assert db.execute('SELECT count(*) FROM pilot_m').fetchone()[0]==10000
    def copy(query,name):
        dest=out/name
        if dest.exists(): raise FileExistsError(dest)
        db.execute(f"COPY ({query}) TO '{dest}.pending' (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 65536)")
        Path(str(dest)+'.pending').replace(dest)
    copy('SELECT * FROM pilot_m ORDER BY file_group,molecule_id','pilot_molecules.parquet')
    copy('SELECT r.* FROM r JOIN pilot_m USING(molecule_id) ORDER BY r.file_group,r.molecule_id,r.real_index','pilot_records.parquet')
    # Compact permanent record pointers, not copies of source tensors or a new LMDB.
    keep=['record_id','molecule_id','shard_id','real_index','record_payload_sha256','source_path','total_atoms','heavy_atoms','smiles','conformer_id','member_routine','split']
    keep=[c for c in keep if c in cols]
    select=','.join('"'+c+'"' for c in keep)
    copy(f"SELECT {select} FROM r WHERE split='train' ORDER BY shard_id,real_index",'train_records.parquet')
    copy(f"SELECT {select} FROM r WHERE split='full' ORDER BY shard_id,real_index",'full_records.parquet')
    pilot=pq.read_table(out/'pilot_records.parquet').slice(0,16).to_pylist()
    with cf.ProcessPoolExecutor(max_workers=16) as pool: observations=list(pool.map(raw_record,pilot))
    save(out/'native_graph_samples.json',observations)
    paths=[POP/'manifest.json',POP/'formal_record_index.parquet',POP/'molecule_index.parquet',out/'pilot_molecules.parquet',out/'pilot_records.parquet',out/'train_records.parquet',out/'full_records.parquet']
    with cf.ThreadPoolExecutor(max_workers=threads) as pool: hashes=list(pool.map(sha,paths))
    refs=[{'path':str(p),'bytes':p.stat().st_size,'sha256':h} for p,h in zip(paths,hashes)]
    db.close()
    import shutil; shutil.rmtree(scratch)
    save(out/'population_binding.json',{'status':'CLOSED','job_id':os.environ['SLURM_JOB_ID'],'hostname':socket.gethostname(),'counts':counts,'roles':roles,'references':refs,'pilot_molecules':10000,'original_lmdb_written':False,'new_lmdb_created':False,'effective_threads':threads,'elapsed_seconds':time.time()-start})
    print('PREPARATION_CLOSED',flush=True)

if __name__=='__main__': main()
