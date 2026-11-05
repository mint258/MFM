"""Bind closed metadata once; retain unregistered real Pprime source geometries."""
import argparse,json
from pathlib import Path
from . import identities as A
from .disk_guard import from_plan
from ...labels.window2_normalization_v1 import io as I


def source_pprime_addresses(plan,projection):
    import pyarrow as pa,pyarrow.parquet as pq
    root=Path(plan['runtime_metadata_root']);root.mkdir(parents=True,exist_ok=True);marker=root/'pprime_source_addresses.json'
    refs=projection.get('source_geometry_pointer_tables',[])
    if marker.is_file():
        prior=I.load(marker)
        if prior['inputs']!=refs:raise ValueError('FROZEN_PPRIME_SOURCE_GEOMETRIES_CHANGED')
        return prior
    path=root/'pprime_source_addresses.parquet'
    schema=pa.schema([('molecule_id',pa.string()),('geometry_source',pa.string()),('native_record_id',pa.string()),
        ('sprime_conf_idx',pa.int64()),('geometry_id',pa.string()),('storage_physical_alias',pa.string()),
        ('source_pprime_record_id',pa.string()),('source_path',pa.string()),('source_row_index',pa.int64()),
        ('source_format',pa.string()),('native_anchor_record_id',pa.string()),('atom_order_sha256',pa.string()),
        ('accepted_component_kind',pa.string()),('original_source_geometry_id',pa.string()),
        ('Pprime_only',pa.bool_()),('excluded_from_all_training',pa.bool_())])
    writer=pq.ParquetWriter(path,schema,compression='zstd');count=0
    try:
        for ref in refs:
            rows=[]
            columns=['record_id','molecule_id','sprime_conf_idx','geometry_id','fit_eligible','source_record_id','native_atom_order_sha256']
            for physical,row in enumerate(A.rows(ref,columns=columns)):
                if row['geometry_id'] is not None:continue
                if row['fit_eligible']:raise ValueError('UNREGISTERED_SOURCE_GEOMETRY_CANNOT_BE_FIT_ELIGIBLE')
                alias='pprime-source:'+row['record_id']
                rows.append({'molecule_id':row['molecule_id'],'geometry_source':'uff_sprime','native_record_id':None,
                    'sprime_conf_idx':row['sprime_conf_idx'],'geometry_id':alias,'storage_physical_alias':alias,
                    'source_pprime_record_id':row['record_id'],'source_path':ref['path'],'source_row_index':physical,
                    'source_format':'parquet','native_anchor_record_id':row['source_record_id'],
                    'atom_order_sha256':row['native_atom_order_sha256'],'accepted_component_kind':'closed_pprime_source_geometry',
                    'original_source_geometry_id':None,'Pprime_only':True,'excluded_from_all_training':True})
                count+=1
                if len(rows)>=8192:writer.write_table(pa.Table.from_pylist(rows,schema=schema));rows=[]
            if rows:writer.write_table(pa.Table.from_pylist(rows,schema=schema))
    finally:writer.close()
    result={'inputs':refs,'files':[dict(I.ref(path),records=count)] if count else [],'records':count,
        'new_scientific_conformer_IDs':False,'source_coordinates_copied':False,'original_geometry_id_remains_NULL':True}
    I.save(marker,result);return result


def prepare(plan_path):
    path=Path(plan_path);plan=I.load(path);marker=Path(plan['runtime_metadata_root'])/'bound_plan.json'
    if marker.is_file():
        bound=I.load(marker)
        if bound['plan_path']!=str(path):raise ValueError('FROZEN_RUNTIME_PLAN_PATH_CHANGED')
        resumed=dict(bound['plan'])
        for key in ('gpu_nodes','node_destination_root','metadata_working_root','disk_protection'):
            if key in plan:resumed[key]=plan[key]
        I.save(path,resumed);return resumed
    common=I.load(plan['common'])
    if common['status']!='COMMON_POPULATION_V1_FROZEN':raise ValueError('CLOSED_FINAL_COMMON_REQUIRED')
    extra=common['registered_extra_geometry_map_tables']+common.get('diagnostic_addressable_geometry_tables',[])
    projection=I.load(plan['pprime_cache']);source=source_pprime_addresses(plan,projection)
    plan['extra_geometry_tables']=extra+source['files']
    if source['records']:
        from .uff_d3 import produce
        old=plan['uff_d3_cache'];plan['base_uff_d3_cache']=old
        plan['source_working_root']=plan['source_working_root']+'_with_Pprime_sources'
        new=dict(plan,uff_d3_cache_root=plan['additional_uff_d3_cache_root'],reuse_uff_d3_caches=[old])
        produce(new);plan['uff_d3_cache']=str(Path(plan['additional_uff_d3_cache_root'])/'manifest.json')
    I.save(path,plan);I.save(marker,{'plan_path':str(path),'plan':plan});return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',required=True);args=p.parse_args()
    from_plan(I.load(args.plan),required=True)
    print(json.dumps(prepare(args.plan)),flush=True)
if __name__=='__main__':main()