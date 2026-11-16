from collections import Counter
import pyarrow.parquet as pq
from resources import REPO,load,guard
if __name__=='__main__':
 guard();m=load('/lfshome/zixiao/data_v1_20261025/D6_full_physical_index_20261105_v3/manifest.json')
 fields=load(load('/lfshome/zixiao/data_v1_20261025/full_projection_coverage_20261105_r2/manifest.json')['field_map_reference']['path'])
 if isinstance(fields,dict):print('FIELDMAP_KEYS',list(fields));fields=fields.get('fields',fields.get('rows',[]))
 wanted=set(load(REPO/'results/p_followup/B_field_selection.json')['selected_fields'])
 for f in fields:
  if f.get('field_key') in wanted:print('SELECTED_META',f)
 files=load(m['files_reference']['path']);print('FAMILIES',Counter(f['family'] for f in files))
 seen=set()
 for f in files:
  if f['family'] in seen or not any(x in f['family'].lower() for x in ['pm7','xtb']):continue
  seen.add(f['family']);q=pq.ParquetFile(f['reference']['path'],pre_buffer=False)
  print('SOURCE_SCHEMA',f['family'],f['reference']['path'],q.schema_arrow.names,str(q.schema_arrow.field('values').type)[:1200]);q.close()
 print('PARTITIONS',[(p['partition'],p['storage']['path']) for p in m['partitions']]);print('QC',m['QC_locations']['path'])