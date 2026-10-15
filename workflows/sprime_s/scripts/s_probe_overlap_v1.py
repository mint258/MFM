"""Report connectivity InChIKey14 overlap; do not remove any benchmark member."""
import json,os,tempfile,shutil
from pathlib import Path
from prepare import ROOT,PROJECT,save,sha

def main():
    assert os.environ.get('SLURM_JOB_ID') and int(os.environ['SLURM_CPUS_PER_TASK'])>=16
    import duckdb
    scratch=Path(tempfile.mkdtemp(prefix='sprobe_overlap_',dir='/tmp'))
    try:
        db=duckdb.connect();db.execute('SET threads=16');db.execute("SET memory_limit='20GB'")
        db.execute(f"SET temp_directory='{scratch}'")
        source=PROJECT/'runs/phase1_wp5_20261011/population/formal_record_index.parquet'
        columns={row[0] for row in db.execute(f"DESCRIBE SELECT * FROM read_parquet('{source}')").fetchall()}
        assert {'molecule_id','reidentified_inchikey','split'}<=columns,columns
        db.execute(f"CREATE TABLE pretrain_keys AS SELECT substr(reidentified_inchikey,1,14) AS key14,bool_or(lower(split)='train') AS in_train,count(DISTINCT molecule_id) AS molecules FROM read_parquet('{source}') GROUP BY key14")
        results=[];refs=[]
        for dataset in ['qm7','qm9','cyp_isoform','az_exactsom','expansionrx']:
            receipt=json.loads((ROOT/'probe_data_v3'/(dataset+'_receipt.json')).read_text())
            assert receipt['status']=='DATASET_MEMBERS_AND_COMMON_UFF_GEOMETRY_CLOSED'
            ref=receipt['output'];assert sha(ref['path'])==ref['sha256'];refs.append(ref)
            query=f"SELECT count(*),count(inchikey14),count(*) FILTER(WHERE p.key14 IS NOT NULL),count(*) FILTER(WHERE p.in_train),count(DISTINCT b.inchikey14) FILTER(WHERE p.key14 IS NOT NULL),count(DISTINCT b.inchikey14) FILTER(WHERE p.in_train) FROM read_parquet('{ref['path']}') b LEFT JOIN pretrain_keys p ON b.inchikey14=p.key14"
            row=db.execute(query).fetchone()
            results.append(dict(zip(['benchmark_members','identity_available_members','overlap_all_formal_members','overlap_train_members','overlap_all_formal_unique_keys','overlap_train_unique_keys'],row))|{'dataset':dataset})
        save(ROOT/'reports/s_probe_pretraining_overlap_v1.json',{'status':'FIVE_BENCHMARK_CONNECTIVITY_INCHIKEY14_OVERLAP_REPORTED',
            'job_id':os.environ['SLURM_JOB_ID'],'results':results,'benchmark_sources':refs,
            'pretraining_population_source':{'path':str(source),'sha256':sha(source)},
            'key_recipe':'first14 characters of standard InChIKey; connectivity block, distinct from Bemis-Murcko scaffold split key',
            'benchmark_records_deleted':0,'pretraining_records_deleted':0,'script_sha256':sha(__file__)})
    finally:shutil.rmtree(scratch)

if __name__=='__main__':main()
