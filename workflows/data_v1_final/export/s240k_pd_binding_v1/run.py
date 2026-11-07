"""Bind the original S240k MID list to final shared D6; never export labels."""
import argparse,collections,json
from pathlib import Path
from ...labels.window2_normalization_v1 import io as I
from ..v31_stream_v1.disk_guard import from_plan

MEMBERSHIP_COLUMNS=['molecule_id','effective_role','common_population']


def rows(path,columns):
    import pyarrow.parquet as pq
    table=pq.ParquetFile(path,pre_buffer=False)
    try:
        for batch in table.iter_batches(batch_size=8192,columns=columns,use_threads=False):yield from batch.to_pylist()
    finally:table.close()


def membership_binding(plan,common,guard=None):
    import pyarrow as pa,pyarrow.parquet as pq
    column=plan.get('subset_mid_column','molecule_id')
    mids=[row[column] for row in rows(plan['subset_path'],[column])]
    if any(not isinstance(mid,str) or not mid for mid in mids):raise ValueError('S240K_MID_MUST_BE_PRESENT_STRING')
    wanted=set(mids);members={}
    for reference in common['membership_tables']:
        for row in rows(reference['path'],MEMBERSHIP_COLUMNS):
            mid=row['molecule_id']
            if mid not in wanted:continue
            value=(row['effective_role'],row['common_population'])
            if mid in members and members[mid]!=value:raise ValueError('CONFLICTING_FINAL_COMMON_MEMBERSHIP:'+mid)
            members[mid]=value
    schema=pa.schema([('subset_ordinal',pa.int64()),('molecule_id',pa.string()),
                      ('effective_role',pa.string()),('common_population',pa.bool_()),
                      ('in_final_common_TRAIN',pa.bool_()),('binding_status',pa.string())])
    root=Path(plan['output_root']);path=root/'membership_binding.parquet';attempt=0
    while path.exists():attempt+=1;path=root/('membership_binding_attempt_%03d.parquet'%attempt)
    if guard:guard.wait(path,inodes_needed=2)
    writer=pq.ParquetWriter(path,schema,compression='zstd');counts=collections.Counter();pending=[]
    try:
        for ordinal,mid in enumerate(mids):
            role,common_flag=members.get(mid,(None,None))
            status=('MISSING_FROM_FINAL_COMMON' if mid not in members else 'NOT_COMMON' if common_flag is not True
                    else 'NOT_TRAIN' if str(role).upper()!='TRAIN' else 'COMMON_TRAIN')
            counts[status]+=1
            pending.append({'subset_ordinal':ordinal,'molecule_id':mid,'effective_role':role,
                            'common_population':common_flag,'in_final_common_TRAIN':status=='COMMON_TRAIN','binding_status':status})
            if len(pending)>=8192:
                batch=pa.Table.from_pylist(pending,schema=schema)
                if guard:guard.wait(path,batch.nbytes,2)
                writer.write_table(batch);pending=[]
        if pending:
            batch=pa.Table.from_pylist(pending,schema=schema)
            if guard:guard.wait(path,batch.nbytes,2)
            writer.write_table(batch)
    finally:writer.close()
    return {'table':dict(I.ref(path),records=len(mids)),
            'molecule_rows':len(mids),'unique_molecules':len(wanted),'duplicate_subset_rows':len(mids)-len(wanted),
            'counts':dict(counts),'original_subset_order_preserved':True,'rows_filtered_or_replaced':0}


def published_binding(plan,binding,summary):
    reasons=[];expected=plan['expected_molecules']
    if binding['molecule_rows']!=expected or binding['unique_molecules']!=expected:reasons.append('ORIGINAL_SUBSET_COUNT_OR_DUPLICATES')
    if binding['counts'].get('COMMON_TRAIN',0)!=binding['molecule_rows']:reasons.append('ORIGINAL_SUBSET_HAS_FINAL_COMMON_TRAIN_GAPS')
    if summary.get('status')!='READY' or summary.get('molecules')!=expected:reasons.append('EXISTING_S240K_SUMMARY_NOT_READY')
    manifest_path=Path(plan['d6_manifest']);manifest=None
    if not manifest_path.is_file():reasons.append('FINAL_D6_MANIFEST_NOT_PUBLISHED')
    else:
        manifest=I.load(manifest_path)
        if manifest.get('format')!='v3.1/MFM4' or manifest.get('data_version')!=plan['expected_data_version']:
            reasons.append('UNEXPECTED_D6_FORMAT_OR_VERSION')
        if not manifest.get('split_roots',{}).get('TRAIN'):reasons.append('FINAL_D6_TRAIN_SPLIT_MISSING')
    ready=not reasons;root=str(manifest_path.parent) if ready else None
    return {'status':'READY' if ready else 'NOT_READY','not_ready_reasons':reasons,'root':root,
            'published_d6_reference':I.ref(manifest_path) if manifest is not None else None,
            'shared_split_roots':manifest.get('split_roots',{}) if manifest is not None else {},
            'readiness_basis':'Final producer-published D6 manifest only; no LMDB or repeated numerical QA'}


def prepare(plan,guard=None):
    root=Path(plan['output_root']);marker=root/'manifest.json'
    if guard:guard.wait(root,inodes_needed=4)
    root.mkdir(parents=True,exist_ok=True)
    common=I.load(plan['common'])
    if common.get('status')!='COMMON_POPULATION_V1_FROZEN':raise ValueError('FROZEN_FINAL_COMMON_REQUIRED')
    template=I.load(plan['p_template']);summary=I.load(plan['s_summary'])
    if template.get('subset_path')!=plan['subset_path']:raise ValueError('P_TEMPLATE_IS_NOT_THE_ORIGINAL_S240K_SUBSET')
    if template.get('source')!='PM7':raise ValueError('ORIGINAL_P_D_INPUT_SOURCE_MUST_BE_PM7')
    if summary.get('path')!=plan['s_records']:raise ValueError('EXISTING_S240K_RECORD_REFERENCE_DIFFERS')
    inputs={key:I.ref(plan[key]) for key in ('subset_path','common','s_summary','s_records')}
    inputs['template_input_fields']={key:template[key] for key in ('subset_path','source','training_view','normalizations')}
    inputs.update(membership_tables=common['membership_tables'],subset_mid_column=plan.get('subset_mid_column','molecule_id'),
                  expected_molecules=plan['expected_molecules'],d6_manifest=plan['d6_manifest'],expected_data_version=plan['expected_data_version'])
    if marker.is_file():
        prior=I.load(marker)
        if prior['inputs']!=inputs:raise ValueError('FROZEN_S240K_BINDING_INPUTS_CHANGED')
        binding=prior['membership_binding'];I.require(binding['table'])
    else:binding=membership_binding(plan,common,guard)
    availability=published_binding(plan,binding,summary)
    shared={'root':availability['root'],'subset_path':plan['subset_path'],'source':template['source'],'split':'TRAIN',
            'training_view':template['training_view'],'normalizations':template['normalizations']}
    result={'schema':'ORIGINAL_S240K_SHARED_D6_PD_INPUT_BINDING_V1','inputs':inputs,**availability,
            'current_template_reference':I.ref(plan['p_template']),
            'membership_binding':binding,'bindings':{'P':dict(shared),'D':dict(shared)},
            'original_S':{'summary_reference':inputs['s_summary'],'record_index_reference':inputs['s_records'],
                          'records':summary.get('records'),'record_positions_reused_as_D6_indices':False},
            'subset_replaced':False,'intersection_applied':False,'new_LMDB_or_dataset_copy':False,
            'read_columns':{'subset':[plan.get('subset_mid_column','molecule_id')],'final_common':MEMBERSHIP_COLUMNS,
                            'S_records':'reference only; never opened'},'labels_read':False,'coordinates_read':False}
    if guard:guard.wait(marker,inodes_needed=2)
    I.save(marker,result);return result


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args();plan=I.load(args.plan);guard=from_plan(plan,required=True)
    result=prepare(plan,guard)
    print(json.dumps({'status':result['status'],'root':result['root'],'not_ready_reasons':result['not_ready_reasons'],
                      'membership_counts':result['membership_binding']['counts'],'manifest':str(Path(plan['output_root'])/'manifest.json')}),flush=True)

if __name__=='__main__':main()
