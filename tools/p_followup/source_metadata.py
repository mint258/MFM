"""Inspect only existing locator schemas and a U identity; never P label payloads."""
import json,pathlib,sqlite3
import pyarrow.parquet as pq
from resources import load,REPO,guard

def brief(value):
 if isinstance(value,dict):return {k:v for k,v in value.items() if not isinstance(v,(dict,list))} or {'keys':list(value)}
 if isinstance(value,list):return {'entries':len(value)}
 return value
if __name__=='__main__':
 guard();p='/lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3/manifest.json';m=load(p)
 for k,v in m.items():print('INDEX_META',k,brief(v),flush=True)
 for k in ['QC_locations','canonical_reference']:
  ref=m.get(k)
  if ref:
   c=sqlite3.connect('file:'+ref['path']+'?mode=ro',uri=True);print('SCHEMA',k,c.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall(),flush=True);c.close()
 cfg=load(REPO/'configs/p_followup/C_dedup.json');d=load(pathlib.Path(cfg['root'])/'manifest.json');q=pq.ParquetFile(pathlib.Path(d['split_roots']['TRAIN'])/'id_map.parquet',pre_buffer=False)
 print('ID_COLUMNS',q.schema_arrow.names,flush=True)
 names=[n for n in ['record_kind','molecule_id','molecule_index','conformer_index','native_record_id','geometry_id','sprime_conformer_id','source_row'] if n in q.schema_arrow.names]
 for batch in q.iter_batches(batch_size=32,columns=names,use_threads=False):
  found=[r for r in batch.to_pylist() if r['record_kind']=='U']
  if found:print('FIRST_U_ID',found[0],flush=True);break
 print('PARTITION_KEYS',list(m['partitions'][0]),flush=True)