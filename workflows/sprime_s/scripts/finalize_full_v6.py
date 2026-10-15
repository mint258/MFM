"""Verify all chunk SCI and publish five closed full S-prime Parquet file groups."""
import concurrent.futures as cf,json,os,sqlite3,tempfile,shutil,time
from pathlib import Path
import pyarrow as pa,pyarrow.parquet as pq
from prepare import ROOT,POP,save,sha

def check(ref):
    path=Path(ref['path']);assert path.stat().st_size==ref['bytes'] and sha(path)==ref['sha256'];return ref

def align(table,schema):
    arrays=[]
    for field in schema:
        if field.name in table.column_names:arrays.append(table[field.name].cast(field.type))
        else:arrays.append(pa.nulls(table.num_rows,type=field.type))
    return pa.Table.from_arrays(arrays,schema=schema)

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import duckdb
    full=ROOT/'full';out=ROOT/'dataset';out.mkdir(exist_ok=True,parents=True)
    if (out/'manifest.json').exists():raise FileExistsError('Closed dataset cannot be republished')
    queue=sqlite3.connect('file:'+str(full/'work.sqlite')+'?mode=ro',uri=True)
    states=dict(queue.execute('SELECT state,count(*) FROM chunks GROUP BY state').fetchall());assert set(states)=={'DONE'},states
    rows=queue.execute('SELECT id,file_group,receipt FROM chunks ORDER BY file_group,id').fetchall();queue.close()
    receipts=[json.loads(row[2]) for row in rows]
    refs=[ref for receipt in receipts for ref in receipt['references']]
    pilot=[]
    for group in range(1,6):
        receipt=json.loads((ROOT/'pilot_v6'/f'receipt_group{group}.json').read_text());pilot.extend(receipt['references'])
    with cf.ThreadPoolExecutor(max_workers=16) as pool:list(pool.map(check,refs+pilot))
    output_refs=[]
    for group in range(1,6):
        for kind in ['molecules','conformers']:
            schema=pa.ipc.read_schema(pa.BufferReader((full/(kind+'.schema')).read_bytes()))
            dest=out/f'{kind}_group{group}.parquet'
            if dest.exists():raise FileExistsError(dest)
            sources=[ROOT/'pilot_v6'/f'{kind}_group{group}.parquet']
            sources.extend(Path(ref['path']) for receipt in receipts if receipt['group']==group for ref in receipt['references'] if ref['kind']==kind)
            count=0
            with pq.ParquetWriter(str(dest)+'.pending',schema,compression='zstd') as writer:
                for source in sources:
                    for batch in pq.ParquetFile(source).iter_batches(batch_size=8192):
                        table=align(pa.Table.from_batches([batch]),schema);writer.write_table(table);count+=table.num_rows
            pending=Path(str(dest)+'.pending');assert pq.ParquetFile(pending).metadata.num_rows==count;pending.replace(dest)
            output_refs.append({'file_group':group,'kind':kind,'path':str(dest),'rows':count,'bytes':dest.stat().st_size,'sha256':sha(dest)})
    scratch=Path(tempfile.mkdtemp(prefix='spfullcheck_'+os.environ['SLURM_JOB_ID']+'_',dir='/tmp'))
    db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='20GB'");db.execute(f"SET temp_directory='{scratch}'")
    db.execute(f"CREATE VIEW m AS SELECT * FROM read_parquet('{out/'molecules_group*.parquet'}',union_by_name=true)")
    db.execute(f"CREATE VIEW c AS SELECT * FROM read_parquet('{out/'conformers_group*.parquet'}',union_by_name=true)")
    db.execute(f"CREATE VIEW expected AS SELECT * FROM read_parquet('{POP/'molecule_index.parquet'}')")
    counts=db.execute('SELECT count(*),count(DISTINCT molecule_id),sum(expected_conformers),sum(generated_conformers) FROM m').fetchone()
    assert counts[:3]==(1220466,1220466,11231854),counts
    assert db.execute('SELECT count(*) FROM expected e FULL JOIN m USING(molecule_id) WHERE e.molecule_id IS NULL OR m.molecule_id IS NULL OR e.records!=m.expected_conformers OR e.file_group!=m.file_group OR e.max_heavy_atoms!=m.max_heavy_atoms').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM m WHERE generated_conformers<0 OR generated_conformers>expected_conformers OR covered_pm7_conformers<0 OR covered_pm7_conformers>expected_conformers OR status IN (\'UNPROCESSED\',\'IMPLEMENTATION_ERROR\')').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM c').fetchone()[0]==counts[3]
    assert db.execute('SELECT count(*) FROM (SELECT molecule_id,sprime_conf_idx,count(*) n FROM c GROUP BY 1,2 HAVING n!=1)').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM (SELECT molecule_id,count(*) n,min(sprime_conf_idx) lo,max(sprime_conf_idx) hi FROM c GROUP BY 1) x FULL JOIN m USING(molecule_id) WHERE m.molecule_id IS NULL OR coalesce(n,0)!=generated_conformers OR (n>0 AND (lo!=0 OR hi!=n-1))').fetchone()[0]==0
    assert db.execute('SELECT count(*) FROM c JOIN m USING(molecule_id) JOIN expected e USING(molecule_id) WHERE len(coordinates)!=e.max_total_atoms OR c.seed!=m.seed OR c.atom_order_sha256!=m.atom_order_sha256 OR c.stereo_source!=m.stereo_source OR c.stereo_signature!=m.stereo_signature OR c.source_record_id!=m.source_record_id OR NOT isfinite(uff_energy_kcal_mol) OR NOT isfinite(nearest_pm7_rmsd_A)').fetchone()[0]==0
    closure={'molecules':counts[0],'source_records':counts[2],'sprime_conformers':counts[3],'statuses':db.execute('SELECT status,count(*) FROM m GROUP BY status ORDER BY 2 DESC').fetchall(),'insufficient_N_molecules':db.execute('SELECT count(*) FROM m WHERE generated_conformers<expected_conformers').fetchone()[0],'stereo_sources':db.execute('SELECT stereo_source,count(*) FROM m GROUP BY stereo_source ORDER BY 2 DESC').fetchall(),'pm7_coverage_fraction':db.execute('SELECT sum(covered_pm7_conformers)::DOUBLE/sum(expected_conformers) FROM m').fetchone()[0],'rmsd_A_quantiles':db.execute('SELECT quantile_cont(nearest_pm7_rmsd_A,[0.25,0.5,0.75,0.9,0.95,0.99]) FROM c').fetchone()[0]}
    closure['groups']=[]
    for group in range(1,6):
        closure['groups'].append({'file_group':group,'statuses':db.execute('SELECT status,count(*) FROM m WHERE file_group=? GROUP BY status ORDER BY 2 DESC',[group]).fetchall(),'rmsd_A_quantiles':db.execute('SELECT quantile_cont(c.nearest_pm7_rmsd_A,[0.25,0.5,0.75,0.9,0.95,0.99]) FROM c JOIN m USING(molecule_id) WHERE m.file_group=?',[group]).fetchone()[0],'pm7_coverage_fraction':db.execute('SELECT sum(covered_pm7_conformers)::DOUBLE/sum(expected_conformers) FROM m WHERE file_group=?',[group]).fetchone()[0]})
    for ref in output_refs:
        if ref['kind']=='conformers':
            dt=pq.read_schema(ref['path']).field('coordinates').type
            assert pa.types.is_float64(dt.value_type.value_type),dt
    db.close();shutil.rmtree(scratch)
    save(out/'closure.json',closure)
    save(out/'sha_manifest.json',output_refs)
    save(out/'manifest.json',{'status':'FULL_POPULATION_CLOSED_AWAITING_REPRODUCTION100','job_id':os.environ['SLURM_JOB_ID'],'references':output_refs,'closure':closure,'source_manifest':str(full/'prepared.json'),'original_lmdb_written':False,'new_lmdb_created':False,'coordinate_dtype':'float64','alignment':'source-atom-index proper-rotation Kabsch','embedding_max_attempts_per_conformer':200})
    print(json.dumps({'status':'FULL_POPULATION_CLOSED_AWAITING_REPRODUCTION100','closure':closure}),flush=True)

if __name__=='__main__':main()
