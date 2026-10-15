"""Use prior graph invariants to recover cached geometric fragment counts."""
import hashlib,json,os,sys
from pathlib import Path
ROOT=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_dataset_rebuild_20261010')
AUDIT=Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2')
sys.path[:0]=[str(ROOT/'scripts'),str(AUDIT/'deps')]
import duckdb
from wp0_inventory import collect_closed_core
def q(x):return "'"+str(x).replace("'","''")+"'"
if not os.environ.get('SLURM_JOB_ID') or int(os.environ.get('SLURM_CPUS_PER_TASK','0'))<16:
 raise RuntimeError('Requires >=16 Slurm CPUs')
plan,files,receipts=collect_closed_core(AUDIT)
paths=files['train']+files['full']
db=duckdb.connect();db.execute(f'SET threads={int(os.environ["SLURM_CPUS_PER_TASK"])}')
db.execute("SET memory_limit='24GB'")
db.execute(f'CREATE VIEW idx AS SELECT * FROM read_parquet({q(ROOT/"record_index.parquet")})')
db.execute('CREATE VIEW core AS SELECT record_id,fragments,geometry_missing_bonds,geometry_extra_bonds,geometry_cycle_change FROM read_parquet(['+','.join(q(x) for x in paths)+'],union_by_name=true)')
db.execute('''CREATE TABLE cached AS SELECT record_id,
 fragments+geometry_missing_bonds-geometry_extra_bonds+geometry_cycle_change AS cached_geometry_components
 FROM core''')
pending=ROOT/'record_index_geometry_cache.parquet.pending'
db.execute(f'''COPY (SELECT i.* EXCLUDE(X01,X01_geometry_checked,X_keep,pre_geometry_keep),
 c.cached_geometry_components,
 coalesce(i.X01,false) OR coalesce(c.cached_geometry_components>1,false) AS X01,
 c.cached_geometry_components IS NOT NULL AS X01_geometry_checked,
 NOT (coalesce(i.X01,false) OR coalesce(c.cached_geometry_components>1,false))
  AND i.X02 IS FALSE AND i.X03 IS FALSE AND i.X04 IS FALSE AND i.X05 IS FALSE AS X_keep,
 NOT (coalesce(i.X01,false) OR coalesce(c.cached_geometry_components>1,false))
  AND i.X02 IS FALSE AND i.X03 IS FALSE AND i.X04 IS FALSE AND i.X05 IS FALSE
  AND i.G01 IS FALSE AND i.G02 IS FALSE AND i.G03 IS FALSE AS pre_geometry_keep
 FROM idx i LEFT JOIN cached c USING(record_id)) TO {q(pending)} (FORMAT PARQUET,COMPRESSION ZSTD)''')
known,multi,unknown=db.execute('SELECT count(*) FILTER(WHERE cached_geometry_components IS NOT NULL),count(*) FILTER(WHERE cached_geometry_components>1),count(*) FILTER(WHERE cached_geometry_components IS NULL) FROM idx LEFT JOIN cached USING(record_id)').fetchone()
db.close()
old=ROOT/'record_index_before_geometry_cache.parquet'
if old.exists():raise RuntimeError('Already enriched; inspect final index')
(ROOT/'record_index.parquet').rename(old);os.replace(pending,ROOT/'record_index.parquet')
report={'job_id':os.environ['SLURM_JOB_ID'],'known_cached_geometry_records':known,
 'cached_multi_fragment_records':multi,'unknown_cached_geometry_records':unknown,
 'formula':'components = stored graph fragments + missing bonds - extra bonds + cycle-count change',
 'method':'Prior full-scan covalent-radius connectivity at 1.25*(r_i+r_j); new charge=0 RDKit recognition still runs on after-X records',
 'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 'original_lmdb_opened_or_modified':False,'prior_index_preserved':str(old)}
(ROOT/'reports/geometry_cache_enrichment.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
