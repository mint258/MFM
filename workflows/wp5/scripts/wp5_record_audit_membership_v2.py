"""New user-authorized record-level 1% raw-output audit membership. No QM/LMDB."""
from __future__ import annotations
import argparse,ast,json,os,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
POP_RECORDS=11231854;POP_MOLECULES=1220466
OVERRIDE_SHA='b368187eb93d0641c0628fc33ed447192cf0e260bcfb0e01230812c49ba72b2c'
def digest(path):
    import hashlib
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(8<<20),b''):h.update(block)
    return h.hexdigest()
def quoted(value):return "'"+str(value).replace("'","''")+"'"
def save(path,value):
    path=Path(path)
    if path.exists():raise FileExistsError(path)
    with path.open('x') as stream:json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False);stream.write('\n');stream.flush();os.fsync(stream.fileno())
def rows(db,sql):
    cursor=db.execute(sql);names=[item[0] for item in cursor.description]
    return [dict(zip(names,row)) for row in cursor.fetchall()]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--population',type=Path,default=ROOT/'population/formal_record_index.parquet')
    p.add_argument('--authority',type=Path,default=ROOT/'configs/user_raw_retention_override_20261011_v1.json')
    p.add_argument('--out',type=Path);p.add_argument('--workers',type=int,default=24);p.add_argument('--memory-gb',type=int,default=20);p.add_argument('--check',action='store_true');a=p.parse_args()
    if a.check:
        ast.parse(Path(__file__).read_text());assert 184467440737095516==2**64//100
        print('AUDIT_MEMBERSHIP_AST_RULE_PASS_NO_SCAN_NO_QM');return
    if not os.environ.get('SLURM_JOB_ID') or a.workers<24 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.workers:raise ValueError('Allocated24+ actual DuckDB workers required')
    if digest(a.authority)!=OVERRIDE_SHA:raise ValueError('Actual new user override authority changed')
    authority=json.loads(a.authority.read_text())
    if authority.get('audit_unit')!='record' or authority.get('audit_fraction')!=.01 or authority.get('inputs_saved') is not False:raise ValueError('Expected latest record-audit/no-input scope')
    out=a.out or ROOT/'audit_membership'/('job_'+os.environ['SLURM_JOB_ID'])
    if not out.resolve().is_relative_to(ROOT):raise ValueError('Outputs only in current WP5 root')
    out.mkdir(parents=True,exist_ok=False)
    import duckdb,pyarrow as pa,pyarrow.parquet as pq
    pa.set_cpu_count(a.workers);db=duckdb.connect();db.execute('SET threads='+str(a.workers));db.execute('SET memory_limit='+quoted(str(a.memory_gb)+'GB'))
    spill=Path('/tmp')/('wp5audit_'+str(os.getuid())+'_'+os.environ['SLURM_JOB_ID']);spill.mkdir(exist_ok=False);db.execute('SET temp_directory='+quoted(spill))
    started=time.monotonic()
    db.execute("CREATE VIEW population AS SELECT record_id,molecule_id,file_group,CASE WHEN molecule_max_heavy_atoms<=10 THEN '0_10' WHEN molecule_max_heavy_atoms<=20 THEN '11_20' WHEN molecule_max_heavy_atoms<=30 THEN '21_30' WHEN molecule_max_heavy_atoms<=50 THEN '31_50' WHEN molecule_max_heavy_atoms<=75 THEN '51_75' WHEN molecule_max_heavy_atoms<=100 THEN '76_100' ELSE 'above_100' END AS size_stratum FROM read_parquet("+quoted(a.population)+")")
    counts=db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM population').fetchone()
    if counts!=(POP_RECORDS,POP_RECORDS,POP_MOLECULES):raise ValueError('FORMAL_PHYSICAL_MANIFEST_COUNT_MISMATCH')
    # Bernoulli threshold per independent physical record; no molecule bias.
    db.execute("CREATE VIEW selected AS SELECT * FROM population WHERE md5_number_lower('20261010:'||file_group::VARCHAR||':'||size_stratum||':'||record_id) <184467440737095516::UBIGINT")
    target=out/'selected_records.parquet';pending=target.with_name(target.name+'.pending')
    db.execute("COPY (SELECT record_id,molecule_id,file_group::TINYINT AS file_group,size_stratum FROM selected ORDER BY file_group,size_stratum,record_id) TO "+quoted(pending)+" (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 131072)")
    with pending.open('rb') as stream:os.fsync(stream.fileno())
    pending.rename(target)
    selected_counts=db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM selected').fetchone()
    if selected_counts[0]!=selected_counts[1] or pq.ParquetFile(target).metadata.num_rows!=selected_counts[0]:raise ValueError('AUDIT_RECORD_DUPLICATE_OR_FOOTER_MISMATCH')
    strata=rows(db,"WITH pop AS (SELECT file_group,size_stratum,count(*) AS population_records,count(DISTINCT molecule_id) AS population_molecules FROM population GROUP BY 1,2),sel AS (SELECT file_group,size_stratum,count(*) AS selected_records,count(DISTINCT molecule_id) AS selected_molecules FROM selected GROUP BY 1,2) SELECT pop.*,coalesce(sel.selected_records,0) AS selected_records,coalesce(sel.selected_molecules,0) AS selected_molecules,coalesce(sel.selected_records,0)::DOUBLE/pop.population_records AS actual_fraction FROM pop LEFT JOIN sel USING(file_group,size_stratum) ORDER BY file_group,size_stratum")
    for layer in strata:layer['formal_records']=layer['population_records']
    membership={'path':str(target),'sha256':digest(target),'bytes':target.stat().st_size,'rows':selected_counts[0]}
    manifest={'schema':'WP5_STRATIFIED_RECORD_AUDIT_V1','status':'AUDIT_MEMBERSHIP_CLOSED','job_id':os.environ['SLURM_JOB_ID'],'uid':os.getuid(),
      'population':{'path':str(a.population),'sha256':digest(a.population),'records':POP_RECORDS,'molecules':POP_MOLECULES},
      'selected_records':membership,'membership':membership,
      'selected_molecules':selected_counts[2],'actual_fraction':selected_counts[0]/POP_RECORDS,
      'selection':{'unit':'record','strata':['file_group','size_stratum'],'fraction':.01,'seed':20261010,
         'hash_rule':'md5_number_lower(seed:group:stratum:record_id) <184467440737095516','unsigned64_threshold':184467440737095516,
         'minimum_conformer_required':False,'whole_molecule_selection':False,'selected_record_all12_complete_outputs':True},
      'strata':strata,'authority':{'path':str(a.authority),'sha256':OVERRIDE_SHA},'runtime':{'threads':a.workers,'memory_gb':a.memory_gb,'duckdb':duckdb.__version__,'seconds':time.monotonic()-started},
      'script_sha256':digest(__file__),'new_QM_calls':0,'source_LMDB_opened':False,'original_data_written':False}
    save(out/'manifest.json',manifest);db.close()
    import shutil;shutil.rmtree(spill)
    print(json.dumps({'manifest':str(out/'manifest.json'),'selected_records':selected_counts[0],'strata':len(strata)}))
if __name__=='__main__':main()
