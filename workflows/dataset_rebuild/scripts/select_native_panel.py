"""Select whole retained molecules for the real WP4 pilot; no LMDB writes."""
import argparse, hashlib, json, os, time
from pathlib import Path
import duckdb

def q(value):return "'"+str(value).replace("'","''")+"'"
def dictrows(db,query):
 result=db.execute(query); names=[x[0] for x in result.description]
 return [dict(zip(names,row)) for row in result.fetchall()]

def main():
 p=argparse.ArgumentParser();p.add_argument('--quality',required=True)
 p.add_argument('--out',required=True);p.add_argument('--records',type=int,default=10000)
 p.add_argument('--seed',type=int,default=20261010);p.add_argument('--workers',type=int,default=16)
 a=p.parse_args();allocated=int(os.environ.get('SLURM_CPUS_PER_TASK','0'))
 if not os.environ.get('SLURM_JOB_ID') or allocated<16 or not 16<=a.workers<=allocated:
  raise RuntimeError('Requires >=16 allocated Slurm CPUs')
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 db=duckdb.connect();db.execute(f'SET threads={a.workers}')
 db.execute("SET memory_limit='24GB'")
 db.execute(f'CREATE VIEW quality AS SELECT * FROM read_parquet({q(a.quality)})')
 db.execute('''CREATE TABLE molecules AS SELECT molecule_id,count(*) AS conformers,
  max(total_atoms) AS total_atoms,max(heavy_atoms) AS heavy_atoms,
  min(energy_raw) AS lowest_stored_energy,
  CASE WHEN max(heavy_atoms)<=10 THEN '0_10' WHEN max(heavy_atoms)<=20 THEN '11_20'
       WHEN max(heavy_atoms)<=30 THEN '21_30' WHEN max(heavy_atoms)<=50 THEN '31_50'
       WHEN max(heavy_atoms)<=75 THEN '51_75' WHEN max(heavy_atoms)<=100 THEN '76_100'
       ELSE 'above_100' END AS size_stratum
  FROM quality WHERE retained GROUP BY molecule_id''')
 strata=dictrows(db,'SELECT size_stratum,count(*) AS molecules,sum(conformers) AS records FROM molecules GROUP BY size_stratum ORDER BY size_stratum')
 if not strata:raise RuntimeError('No retained molecules')
 # Allocate similar record counts across nonempty size strata; redistribute
 # unused rare-stratum budgets. Population weights accompany the panel.
 budgets={r['size_stratum']:min(int(r['records']),a.records//len(strata)) for r in strata}
 remaining=a.records-sum(budgets.values())
 while remaining>0:
  available=[r for r in strata if budgets[r['size_stratum']]<r['records']]
  if not available:break
  step=max(1,remaining//len(available))
  for r in available:
   add=min(step,remaining,int(r['records'])-budgets[r['size_stratum']]);budgets[r['size_stratum']]+=add;remaining-=add
 db.execute('CREATE TABLE budgets(size_stratum VARCHAR,records BIGINT)')
 db.executemany('INSERT INTO budgets VALUES (?,?)',list(budgets.items()))
 db.execute(f'''CREATE TABLE selected AS SELECT * EXCLUDE(cumulative)
  FROM (SELECT m.*,sum(conformers) OVER(PARTITION BY size_stratum ORDER BY sha256(molecule_id||'|{a.seed}'),molecule_id) AS cumulative
    FROM molecules m) JOIN budgets b USING(size_stratum)
  WHERE cumulative-conformers < b.records''')
 panel=out/'pilot_panel.parquet'
 db.execute(f'''COPY (SELECT q.*,s.size_stratum,s.conformers AS retained_conformer_count,
   q.energy_raw IS NOT NULL AND q.record_id=(SELECT record_id FROM quality e
    WHERE e.retained AND e.molecule_id=q.molecule_id AND e.energy_raw IS NOT NULL
    ORDER BY energy_raw,conformer_id,record_id LIMIT 1) AS molecule_lowest_energy_conformer
   FROM quality q JOIN selected s USING(molecule_id) WHERE q.retained)
   TO {q(panel)} (FORMAT PARQUET,COMPRESSION ZSTD)''')
 selected=dictrows(db,'SELECT size_stratum,count(*) AS molecules,sum(conformers) AS records FROM selected GROUP BY size_stratum ORDER BY size_stratum')
 for r in selected:
  population=next(x for x in strata if x['size_stratum']==r['size_stratum'])
  r['population_records']=population['records'];r['population_molecules']=population['molecules']
  r['record_population_weight']=population['records']/r['records']
  r['molecule_population_weight']=population['molecules']/r['molecules']
 report={'status':'READY_FOR_NATIVE_WP4','seed':a.seed,'target_records':a.records,
   'actual_records':sum(r['records'] for r in selected),'molecules':sum(r['molecules'] for r in selected),
   'strata':selected,'input':a.quality,'output':str(panel),'threads':a.workers,
   'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
   'job_id':os.environ['SLURM_JOB_ID'],'all_retained_conformers_of_each_selected_molecule':True,
   'sampling':'Deterministic whole-molecule hash sample, balanced retained-record budgets by heavy-atom strata',
   'panel_columns_added':['size_stratum','retained_conformer_count','molecule_lowest_energy_conformer'],
   'no_lmdb_created_or_written':True}
 (out/'pilot_panel_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ['status','actual_records','molecules']}))

if __name__=='__main__':main()
