"""Include the old-QA complement in the WP0 index without inventing a split."""
import argparse,hashlib,json,os,time
from pathlib import Path
import duckdb

def q(value):return "'"+str(value).replace("'","''")+"'"
def main():
 p=argparse.ArgumentParser();p.add_argument('--root',required=True)
 p.add_argument('--unassigned-root')
 p.add_argument('--workers',type=int,default=16);a=p.parse_args()
 allocated=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
 if not os.environ.get('SLURM_JOB_ID') or allocated<16 or not 16<=a.workers<=allocated:
  raise RuntimeError('Requires >=16 allocated Slurm CPUs')
 root=Path(a.root);unassigned_root=Path(a.unassigned_root) if a.unassigned_root else root
 index=root/'record_index.parquet';extra=unassigned_root/'unassigned_record_index.parquet'
 old_index=root/'record_index_existing_memberships.parquet'
 old_inventory=root/'inventory_existing_memberships.json'
 if old_index.exists() or old_inventory.exists():raise RuntimeError('Merge already started or complete; inspect existing result')
 original=json.loads((root/'inventory.json').read_text())
 complement=json.loads((unassigned_root/'unassigned_inventory.json').read_text())
 plan=json.loads(Path('/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/plan.json').read_text())
 expected=sum(s['length'] for s in plan['sources'])
 db=duckdb.connect();db.execute(f'SET threads={a.workers}');db.execute("SET memory_limit='24GB'")
 paths='['+q(index)+','+q(extra)+']'
 db.execute(f'CREATE VIEW joined AS SELECT * FROM read_parquet({paths},union_by_name=true)')
 total,unique,unassigned,molecules=db.execute("SELECT count(*),count(DISTINCT record_id),count(*) FILTER(WHERE split='unassigned'),count(DISTINCT molecule_id) FROM joined").fetchone()
 if total!=expected or unique!=expected:raise RuntimeError(f'Original source conservation failed: {total}/{unique}/{expected}')
 pending=root/'record_index_all_original.parquet.pending'
 db.execute(f'COPY joined TO {q(pending)} (FORMAT PARQUET,COMPRESSION ZSTD,ROW_GROUP_SIZE 100000)')
 db.close()
 index.rename(old_index);(root/'inventory.json').rename(old_inventory);os.replace(pending,index)
 original['status']='ALL_ORIGINAL_SOURCE_WP0_INDEXED_WP1_GEOMETRY_PENDING'
 original['population']['physical_records']=total;original['population']['distinct_records']=unique
 original['population']['physical_molecules']=molecules
 original['population']['unassigned_records']=unassigned
 original['source_gap']['old_source_missing_from_new_index']=0
 original['source_gap']['unassigned_original_records']=unassigned
 original['source_gap']['policy']='All original records are now indexed and eligible for new-rule analysis. Old-QA exclusion is an annotation; existing train/full memberships are preserved and missing memberships remain unassigned.'
 original['supplements']={'existing_memberships_inventory':str(old_inventory),
   'existing_memberships_index':str(old_index),'unassigned_inventory':str(unassigned_root/'unassigned_inventory.json'),
   'merge_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   'job_id':os.environ['SLURM_JOB_ID'],'created_UTC':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}
 original['record_index_bytes']=index.stat().st_size
 (root/'inventory.json').write_text(json.dumps(original,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'records':total,'unassigned_records':unassigned,'new_source_rules_applied':False}))

if __name__=='__main__':main()
