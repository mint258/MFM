"""Build memory-mapped record metadata and check native reads; never write LMDB."""
from __future__ import annotations
import concurrent.futures as cf
import hashlib,json,os,pickle,shutil,socket,tempfile,time
from pathlib import Path
from prepare import ROOT,POP,PROJECT,save,sha

BATCH=65536
EXPECTED={'train':(11104772,1206608),'full':(127082,13858),'routine':(11322,7610)}
COLS=['record_id','molecule_id','shard_id','real_index','record_payload_sha256','source_path','total_atoms','heavy_atoms','member_routine']

def worker_init():
    import torch
    torch.set_num_threads(1);torch.set_num_interop_threads(1)

def inspect_native(row):
    import lmdb,numpy as np
    path=Path(row['source_path'])
    if not path.is_absolute():path=PROJECT/path
    with lmdb.open(str(path),subdir=False,readonly=True,create=False,lock=False,readahead=False) as env:
        with env.begin() as tx:raw=tx.get(f"{row['real_index']:09d}".encode())
    assert raw is not None and hashlib.sha256(raw).hexdigest()==row['record_payload_sha256'],'ACTUAL_RECORD_MANIFEST_MISMATCH'
    item=pickle.loads(raw)
    field=lambda key:item.get(key) if isinstance(item,dict) else getattr(item,key,None)
    array=lambda value:value.detach().cpu().numpy() if hasattr(value,'detach') else np.asarray(value)
    x=array(field('x'));pos=array(field('pos'));n=int(row['total_atoms'])
    assert x.shape in [(n,),(n,1)] and pos.shape==(n,3),'ACTUAL_RECORD_MANIFEST_MISMATCH'
    assert np.isfinite(pos).all() and np.isfinite(x).all()
    assert np.all(x==np.floor(x)) and np.all((x>=0)&(x<=117))
    bonds=array(field('rdkit_bond_index'));orders=array(field('rdkit_bond_order')).reshape(-1)
    assert bonds.ndim==2 and bonds.shape[0]==2 and bonds.shape[1]==len(orders)
    assert np.all((bonds>=0)&(bonds<n)) and np.all((orders>=0)&(orders<=5))
    return {'record_id':row['record_id'],'molecule_id':row['molecule_id'],'total_atoms':n,
            'payload_sha256':row['record_payload_sha256'],'bond_classes':sorted(set(orders.tolist())),
            'native_x_encoding':'Z_minus_one','coordinate_dtype':str(pos.dtype),
            'atom_order_sha256':hashlib.sha256(np.asarray(x.reshape(-1)+1,dtype='<i2').tobytes()).hexdigest()}

def main():
    import duckdb,pyarrow as pa,pyarrow.parquet as pq,pyarrow.compute as pc,numpy as np
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    start=time.time();out=ROOT/'training_inputs_v1';out.mkdir(parents=True,exist_ok=True)
    assert not (out/'manifest.json').exists(),'Closed input metadata cannot be republished'
    population_binding=ROOT/'prepared/population_binding.json'
    binding=json.loads(population_binding.read_text())
    source_refs=[r for r in binding['references'] if Path(r['path']).name in ['manifest.json','formal_record_index.parquet','molecule_index.parquet','train_records.parquet','full_records.parquet']]
    assert len(source_refs)==5
    def check(ref):
        path=Path(ref['path']);assert path.stat().st_size==ref['bytes'] and sha(path)==ref['sha256'];return ref
    with cf.ThreadPoolExecutor(max_workers=16) as pool:list(pool.map(check,source_refs))
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    scratch=Path(tempfile.mkdtemp(prefix='sconv_inputs_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='20GB'");db.execute(f"SET temp_directory='{scratch}'")
    db.execute(f"CREATE VIEW formal AS SELECT * FROM read_parquet('{POP/'formal_record_index.parquet'}')")
    refs=[];roles={};samples=[]
    for role,(expected_records,expected_molecules) in EXPECTED.items():
        src=ROOT/'prepared'/('train_records.parquet' if role=='train' else 'full_records.parquet')
        where=' WHERE member_routine' if role=='routine' else ''
        query=f"SELECT {','.join(COLS)} FROM read_parquet('{src}'){where} ORDER BY shard_id,real_index"
        db.execute('CREATE OR REPLACE TEMP TABLE current AS '+query)
        counts=db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM current').fetchone()
        assert counts==(expected_records,expected_records,expected_molecules),(role,counts)
        assert db.execute('SELECT count(*) FROM current c LEFT JOIN formal f USING(record_id) WHERE f.record_id IS NULL OR c.molecule_id!=f.molecule_id OR c.shard_id!=f.shard_id OR c.real_index!=f.real_index OR c.source_path!=f.source_path OR c.record_payload_sha256!=f.record_payload_sha256 OR c.total_atoms!=f.total_atoms OR c.heavy_atoms!=f.heavy_atoms OR c.member_routine!=f.member_routine').fetchone()[0]==0
        assert db.execute("SELECT count(*) FROM current c JOIN formal f USING(record_id) WHERE f.split!=?",['train' if role=='train' else 'full']).fetchone()[0]==0
        assert db.execute('SELECT count(*) FROM current WHERE total_atoms<=0 OR real_index<0 OR record_payload_sha256 IS NULL OR length(record_payload_sha256)!=64').fetchone()[0]==0
        # IPC memory maps share metadata pages across spawned loader workers. No training tensors are copied.
        dest=out/(role+'.arrow');pending=Path(str(dest)+'.pending_j'+os.environ['SLURM_JOB_ID'])
        atomdest=out/(role+'.atoms.u32');atompending=Path(str(atomdest)+'.pending_j'+os.environ['SLURM_JOB_ID'])
        schema=pa.schema([pa.field(name,pa.string() if name in ['record_id','molecule_id','record_payload_sha256','source_path'] else pa.bool_() if name=='member_routine' else pa.int64(),nullable=False) for name in COLS])
        stream=db.execute('SELECT * FROM current ORDER BY shard_id,real_index').fetch_record_batch(BATCH)
        rows=0;batch_sizes=[]
        with pa.OSFile(str(pending),'wb') as sink,pa.ipc.new_file(sink,schema) as writer,atompending.open('wb') as atomstream:
            for batch in stream:
                assert all(col.null_count==0 for col in batch.columns)
                batch=pa.RecordBatch.from_arrays([batch.column(i).cast(schema.field(i).type) for i in range(len(COLS))],schema=schema)
                writer.write_batch(batch);batch_sizes.append(batch.num_rows)
                atoms=np.asarray(batch.column(COLS.index('total_atoms')).to_numpy(),dtype='<u4')
                assert np.all(atoms>0);atomstream.write(atoms.tobytes());rows+=batch.num_rows
        assert rows==expected_records and all(n==BATCH for n in batch_sizes[:-1])
        assert atompending.stat().st_size==4*rows
        with pa.memory_map(str(pending),'r') as mapped:
            reader=pa.ipc.open_file(mapped)
            assert reader.num_record_batches==len(batch_sizes) and reader.schema==schema
            assert sum(reader.get_batch(i).num_rows for i in range(reader.num_record_batches))==rows
        pending.replace(dest);atompending.replace(atomdest)
        for kind,path in [('record_metadata',dest),('atom_counts',atomdest)]:
            refs.append({'role':role,'kind':kind,'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path),'rows':rows})
        roles[role]={'records':rows,'molecules':expected_molecules,'batch_rows':BATCH,'record_batches':len(batch_sizes)}
        # Independent random records, one record per shard, and the largest native record.
        samples.extend(db.execute("SELECT * FROM current ORDER BY md5('sconv-input-native-v1:'||record_id) LIMIT 32").fetch_arrow_table().to_pylist())
        samples.extend(db.execute('SELECT * FROM current QUALIFY row_number() OVER(PARTITION BY shard_id ORDER BY real_index)=1').fetch_arrow_table().to_pylist())
        samples.extend(db.execute('SELECT * FROM current ORDER BY total_atoms DESC,record_id LIMIT 1').fetch_arrow_table().to_pylist())
    unique={r['record_id']:r for r in samples};samples=list(unique.values())
    with cf.ProcessPoolExecutor(max_workers=16,initializer=worker_init) as pool:native=list(pool.map(inspect_native,samples,chunksize=1))
    save(out/'native_read_checks.json',{'status':'PASS','records_checked':len(native),'records':native,'population_read_once_verified':False})
    db.close();shutil.rmtree(scratch)
    save(out/'manifest.json',{'status':'INPUT_METADATA_CLOSED_NATIVE_SAMPLE_PASS','job_id':os.environ['SLURM_JOB_ID'],
        'hostname':socket.gethostname(),'roles':roles,'references':refs,'source_references':source_refs,
        'population_binding_sha256':sha(population_binding),'native_read_checks_sha256':sha(out/'native_read_checks.json'),
        'original_lmdb_written':False,'new_lmdb_created':False,'training_tensors_copied':False,
        'epoch_definition':'Each of the 11104772 distinct TRAIN record IDs is consumed exactly once per epoch; three views do not multiply record coverage.',
        'frozen_model_protocol_selected':False,'training_started':False,'elapsed_seconds':time.time()-start})
    print(json.dumps({'status':'INPUT_METADATA_CLOSED_NATIVE_SAMPLE_PASS','roles':roles,'native_records_checked':len(native)}),flush=True)

if __name__=='__main__':main()
