"""Existing input/checkpoint and D6 source metadata; no label scan or forward."""
import pathlib,sqlite3,sys
import pyarrow.parquet as pq
from resources import REPO,R,CONTROL,OLD,load,save,guard
sys.path.insert(0,str(REPO/'tools/p_recipe'))
from checkpoint_paths import evaluation_checkpoint
from phychem_mfm.phase1.v31_loader import split_metadata

def main():
 guard();conditions={}
 inputs=load(R/'runs/p_recipe_20261113/input_metadata.json')['features']
 for key in ['S','P']:
  source=next((v for v in inputs if v.get('candidate')=='C1-0' and v.get('condition')==key),None)
  conditions['P0-'+key]=dict(source=source,checkpoint=source.get('checkpoint') if source else None,status='EXISTS' if source and pathlib.Path(source['checkpoint']).is_file() else 'MISSING')
 for name,relative in [('R1-B0','fixed_20261115/round1/B0.json'),('R1-A1','fixed_20261115/round1/A1.json'),('R2-M1','fixed_20261115/provisional_B_20261116/round2/M1.json'),('R2-B1','fixed_20261115/provisional_B_20261116/round2/B1.json')]:
  path=REPO/'configs/p_recipe'/relative;c=load(path)
  try:checkpoint=str(evaluation_checkpoint(c,3000000));status='EXISTS';reason=None
  except FileNotFoundError as e:checkpoint=None;status='MISSING';reason=str(e)
  conditions[name]=dict(configuration=str(path),checkpoint=checkpoint,status=status,reason=reason)
 c=load(REPO/'configs/p_recipe/fixed_20261115/provisional_B_20261116/round2/M1.json');root=pathlib.Path(c['root']);manifest=load(root/'manifest.json');summary={}
 for split,path in manifest['split_roots'].items():
  p,meta=split_metadata(root,split);q=pq.ParquetFile(p/'id_map.parquet',pre_buffer=False)
  first=q.read_row_group(0,columns=[n for n in ['record_kind','molecule_id','molecule_index','conformer_index','native_record_id','lmdb_key','record_key','record_handle','ordinal'] if n in q.schema_arrow.names],use_threads=False).slice(0,3).to_pylist();print('ID_MAP_FIRST',split,first,flush=True);summary[split]=dict(path=str(p),manifest=meta,id_map_columns=q.schema_arrow.names,id_map_row_groups=q.num_row_groups,id_map_rows=q.metadata.num_rows)
  names=[n for n in ['record_kind','molecule_index','conformer_index','molecule_id','native_record_id','record_key','record_ordinal','stable_handle','geometry_source'] if n in q.schema_arrow.names]
  summary[split]['first_metadata_rows']=q.read_row_group(0,columns=names,use_threads=False).slice(0,8).to_pylist()
  print('D6_METADATA',split,meta,summary[split]['first_metadata_rows'],flush=True)
 physical=load('/lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3/manifest.json')
 print('PHYSICAL_MANIFEST',physical,flush=True)
 for name,ref in [('canonical',physical['canonical_reference']),('locations',physical['partitions'][0]['storage'])]:
  db=sqlite3.connect('file:'+ref['path']+'?mode=ro',uri=True)
  print(name,db.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall(),flush=True);db.close()
 save(CONTROL/'input_metadata.json',dict(conditions=conditions,D6=summary,physical_index=physical,label_payloads_read=0))
 save(REPO/'configs/p_followup/A_conditions.json',dict(conditions=conditions,checkpoint_policy='Only specified conditions/exact sample endpoint; source metadata and payload condition checked at forward load'))
 print('A_CONDITIONS',conditions,flush=True)
if __name__=='__main__':main()