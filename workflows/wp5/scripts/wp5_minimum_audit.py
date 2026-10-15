"""Read-only formal original-energy minimum audit; no QM/LMDB/source changes."""
from __future__ import annotations
import argparse,ast,hashlib,json,os,shutil,socket,sys,tempfile,time
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_wp5_20261011')
DEPS=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.path[:0]=[str(DEPS/'deps'),str(DEPS/'scripts/deps')]
def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''):h.update(b)
    return h.hexdigest()
def rows(db,query):
    q=db.execute(query);names=[d[0] for d in q.description];return [dict(zip(names,r)) for r in q.fetchall()]
def save(path,value):
    p=Path(path);pending=p.with_name(p.name+'.pending');pending.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n');pending.replace(p)
def quote(value):return "'"+str(value).replace("'","''")+"'"
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true')
    p.add_argument('--record-index',type=Path,default=ROOT/'population/formal_record_index.parquet')
    p.add_argument('--molecule-index',type=Path,default=ROOT/'population/molecule_index.parquet')
    p.add_argument('--threads',type=int,default=24);p.add_argument('--memory-gb',type=int,default=20)
    p.add_argument('--output',type=Path);a=p.parse_args()
    if a.check:ast.parse(Path(__file__).read_text());print('AST_PASS_NO_QM_LMDB');return
    if a.threads<16 or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<a.threads:raise ValueError('Allocated16+ parallel metadata threads required')
    if socket.gethostname().split('.')[0] not in {f'compute-0-{n}' for n in range(14,20)}:raise ValueError('Only WP5 physical nodes14..19')
    job=os.environ['SLURM_JOB_ID'];out=(a.output or ROOT/'gates/g3'/f'minimum_audit_{job}').absolute()
    if not out.is_relative_to(ROOT) or out.exists():raise ValueError('Fresh own WP5 audit output required')
    out.mkdir(parents=True);start=time.monotonic()
    import duckdb
    db=duckdb.connect();db.execute(f'SET threads={a.threads}');db.execute('SET memory_limit='+quote(str(a.memory_gb)+'GB'))
    spill=Path(tempfile.mkdtemp(prefix=f'wp5_minimum_{os.getuid()}_{job}_',dir='/tmp'));db.execute('SET temp_directory='+quote(spill))
    try:
        db.execute('CREATE VIEW f AS SELECT record_id,molecule_id,conformer_id,try_cast(energy_raw AS DOUBLE) AS energy_raw FROM read_parquet('+quote(a.record_index)+')')
        counts=db.execute('SELECT count(*),count(DISTINCT record_id),count(DISTINCT molecule_id) FROM f').fetchone()
        if tuple(counts)!=(11231854,11231854,1220466):raise ValueError('MANIFEST_FORMAL_COUNT_MISMATCH')
        db.execute('CREATE TABLE e AS SELECT molecule_id,count(*) AS records,count(*) FILTER(WHERE energy_raw IS NULL OR NOT isfinite(energy_raw)) AS unknown_energy_records FROM f GROUP BY molecule_id')
        # Null conformer IDs sort after known IDs; record_id gives a unique final tie.
        db.execute('CREATE TABLE finite_min AS SELECT record_id,molecule_id,conformer_id,energy_raw FROM f WHERE energy_raw IS NOT NULL AND isfinite(energy_raw) QUALIFY row_number() OVER(PARTITION BY molecule_id ORDER BY energy_raw,conformer_id NULLS LAST,record_id)=1')
        db.execute('CREATE VIEW molecules AS SELECT * FROM read_parquet('+quote(a.molecule_index)+')')
        db.execute("CREATE TABLE minima AS SELECT e.*,m.max_heavy_atoms,m.max_total_atoms,m.file_group,"
            "CASE WHEN m.max_heavy_atoms<=10 THEN '0_10' WHEN m.max_heavy_atoms<=20 THEN '11_20' WHEN m.max_heavy_atoms<=30 THEN '21_30' WHEN m.max_heavy_atoms<=50 THEN '31_50' WHEN m.max_heavy_atoms<=75 THEN '51_75' WHEN m.max_heavy_atoms<=100 THEN '76_100' ELSE 'above_100' END AS size_stratum,"
            "f.record_id AS finite_candidate_record_id,f.conformer_id AS finite_candidate_conformer_id,f.energy_raw AS finite_candidate_energy_raw,"
            "(e.unknown_energy_records=0 AND f.record_id IS NOT NULL) AS minimum_known,"
            "CASE WHEN e.unknown_energy_records=0 THEN f.record_id ELSE NULL END AS minimum_record_id,"
            "CASE WHEN e.unknown_energy_records>0 THEN 'NONFINITE_OR_NULL_OLD_ENERGY' ELSE NULL END AS minimum_unknown_reason "
            "FROM e JOIN molecules m USING(molecule_id) LEFT JOIN finite_min f USING(molecule_id)")
        n=db.execute('SELECT count(*),sum(records),count(*) FILTER(WHERE minimum_known),count(*) FILTER(WHERE minimum_unknown_reason IS NOT NULL),sum(unknown_energy_records) FROM minima').fetchone()
        if n[0]!=1220466 or n[1]!=11231854:raise ValueError('MANIFEST_MINIMUM_INDEX_COUNT_MISMATCH')
        duplicate=db.execute('SELECT count(*) FROM (SELECT minimum_record_id,count(*) AS n FROM minima WHERE minimum_known GROUP BY minimum_record_id HAVING n!=1)').fetchone()[0]
        if duplicate:raise ValueError('MANIFEST_MINIMUM_RECORD_NOT_UNIQUE')
        target=out/'molecule_minima.parquet';pending=target.with_name(target.name+'.pending')
        db.execute('COPY (SELECT * FROM minima ORDER BY molecule_id) TO '+quote(pending)+' (FORMAT PARQUET, COMPRESSION ZSTD)');pending.replace(target)
        strata=rows(db,"SELECT size_stratum,count(*) AS molecules,sum(records) AS records,count(*) FILTER(WHERE minimum_known) AS known_minimum_molecules,count(*) FILTER(WHERE minimum_unknown_reason IS NOT NULL) AS unknown_energy_molecules,sum(records) FILTER(WHERE minimum_unknown_reason IS NOT NULL) AS records_in_unknown_energy_molecules,sum(unknown_energy_records) AS unknown_energy_records FROM minima GROUP BY size_stratum ORDER BY min(max_heavy_atoms)")
        for r in strata:
            if r['records_in_unknown_energy_molecules'] is None:r['records_in_unknown_energy_molecules']=0 # measured empty SQL filtered sum, not absent observation
        result={'status':'FORMAL_MINIMUM_AUDIT_CLOSED','job_id':job,'formal_records':11231854,'formal_molecules':1220466,
            'known_minimum_molecules':n[2],'unknown_energy_molecules':n[3],'unknown_energy_records':n[4],
            'strata':strata,'minimum_tie_rule':'finiteenergy ascending, conformer_id NULLS LAST ascending, record_id ascending',
            'unknown_policy':'Any unknown oldenergy prevents a confirmed minimum; finite candidate is reported separately. SELECTIVE must preserve all raw for these molecules with explicit minimum_unknown_reason.',
            'minima':{'path':str(target),'bytes':target.stat().st_size,'sha256':sha(target)},
            'source_record_index':str(a.record_index),'source_molecule_index':str(a.molecule_index),
            'threads':a.threads,'memory_limit_gb':a.memory_gb,'seconds':time.monotonic()-start,
            'QM_started':False,'LMDB_created':False,'original_source_written':False,'script_sha256':sha(__file__)}
        save(out/'manifest.json',result);print(json.dumps({'status':result['status'],'manifest':str(out/'manifest.json'),'unknown_energy_molecules':n[3],'unknown_energy_records':n[4]}))
    finally:
        db.close()
        if spill.parent==Path('/tmp') and spill.name.startswith(f'wp5_minimum_{os.getuid()}_{job}_'):shutil.rmtree(spill)
if __name__=='__main__':main()
