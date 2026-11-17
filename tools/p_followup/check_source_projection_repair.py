"""Diagnose the failed source-column projection using the three selected families."""
import array
import pyarrow.parquet as pq
import build_f64_sidecar as b
from resources import load,REPO,guard
if __name__=='__main__':
    guard(force=True);names=load(REPO/'results/p_followup/B_field_selection.json')['selected_fields']
    projection=load('/lfshome/zixiao/data_v1_20261025/full_projection_coverage_20261105_r2/manifest.json')
    fields=[f for f in load(projection['field_map_reference']['path']) if f['field_key'] in names]
    for f in fields:b.FIELDS.setdefault(f['task'],[]).append(f)
    physical=load(b.INDEX);files=load(physical['files_reference']['path']);b.FILES={f['id']:f for f in files}
    for family in sorted({f['family_source'] for f in fields}):
        f=next(f for f in files if f['family']==family and f['domain']==0)
        q=pq.ParquetFile(f['reference']['path'],pre_buffer=False)
        raw=q.read_row_group(0,columns=['record_id','molecule_id'],use_threads=False).slice(0,1).to_pylist()[0];q.close()
        b.WANTED={(raw['molecule_id'],raw['record_id']):0}
        output=b.source_file((f['id'],{0:array.array('I',[0,0])}))
        print('B1_SOURCE_PROJECTION_REPAIR',family,[(slot,sorted(values)) for slot,values in output],flush=True)
    print('B1_SELECTED_FAMILIES_REPAIR_OK',flush=True)
