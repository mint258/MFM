"""Original WP5 float64 family schemas/writer,explicit new source/geometry extension."""
import importlib.util,math,os,pathlib,sys
from . import contract as C
Q=C.Q
def load_writer():
    path=C.catalog_paths()['family_writer'];sys.path.insert(0,str(path.parent))
    try:
        spec=importlib.util.spec_from_file_location('_no_pm7_original_family_writer',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    finally:sys.path.pop(0)
    return module
def export_packets(items,out,budget,job_id):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    writer=load_writer();extra=[('dataset_version',pa.string()),('stream',pa.string()),('stream_rank',pa.int64()),('pubchem_cid',pa.int64()),
        ('pubchem_version',pa.string()),('full_key',pa.string()),('wp5_key',pa.string()),('geometry_source',pa.string()),('geometry_context',pa.string()),
        ('conformer_id',pa.int64()),('training_eligible',pa.bool_()),('producer_packet_sha256',pa.string()),('writer_job_id',pa.int64())]
    d20=[];d3=[];base=[];statuses=[]
    for packet_ref,packet in items:
        s=packet['source'];mid=packet['molecule_id'];common={'molecule_id':mid,'file_group':None,'attempt_id':0,'job_id':int(packet['producer_job_id']),
            'task_id':packet['once_key'],'dataset_version':'v2_candidate','stream':s['stream'],'stream_rank':s['stream_rank'],'pubchem_cid':s['cid'],
            'pubchem_version':s['pubchem_version'],'full_key':s['full_key'],'wp5_key':s['wp5_key'],'geometry_source':'uff_sprime','geometry_context':'NEW_UFF_NO_PM7',
            'training_eligible':False,'producer_packet_sha256':packet_ref['sha256'] if packet_ref else None,'writer_job_id':int(job_id)}
        value=packet.get('D20');d20.append({**common,'record_id':mid+':graph','conformer_id':None,'geometry_source':None,'geometry_context':'SOURCE_SMILES_GRAPH_NO_GEOMETRY','schema_ref':'V2_CANDIDATE_ORIGINAL_D20_NO_KAPPA',
            'descriptor_names':value['names'] if value else None,'values_float64':value['values'] if value else [None]*20,'valid_mask':value['valid_mask'] if value else [False]*20,
            'status':'SUCCESS' if value and all(value['valid_mask']) else 'PROPERTY_FAILED','issues':value['issues'] if value else ['SOURCE_GRAPH_UNAVAILABLE']})
        for row in packet['conformers']:
            rid=mid+':uff:'+str(row['conformer_id']);v=row['D3'];issues=list(row['D3_issues'])
            for n in ('PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2'):
                if v.get(n) is None or not math.isfinite(v[n]):issues.append('D3_MISSING_OR_NONFINITE:'+n)
            if v.get('SASA_atom_A2') is None or len(v['SASA_atom_A2'])!=len(packet['atomic_numbers']) or not all(math.isfinite(a) for a in v['SASA_atom_A2']):issues.append('D3_SASA_ATOM_MISSING_NONFINITE_OR_N_MISMATCH')
            d3.append({**common,'record_id':rid,'conformer_id':row['conformer_id'],'schema_ref':'V2_CANDIDATE_ORIGINAL_D3_NEW_UFF',**v,
                'status':'SUCCESS' if not issues else 'PROPERTY_FAILED','issues':issues})
            base.append({**common,'record_id':rid,'conformer_id':row['conformer_id'],'atomic_numbers':packet['atomic_numbers'],'positions_A':row['coordinates'],
                'uff_energy_kcal_mol':row['energy'],'geometry_sha256':row['geometry_sha256'],'atom_order_sha256':packet['atom_order_sha256'],
                'native_candidate_id':row['candidate_id'],'embedding_seed':packet['seed'],'optimizer_code':row['optimizer_code'],'trajectory_snapshots':row['iterations'],'source_once_key':packet['once_key'],
                'below_dedup_threshold':row['below_dedup_threshold'],'min_rmsd_to_previously_selected_A':row['min_rmsd_to_previously_selected_A'],
                'PM7_pointer':None,'PM7_HOF':None,'PM7_RMSD':None})
        statuses.append({**common,'record_id':mid,'conformer_id':None,'state':packet['state'],'error':packet.get('error'),
            'actual_conformers':None if packet.get('generation_count_unknown') else len(packet['conformers']),'desired_conformers':10,'orders_json':C.canonical(packet['orders']).decode(),
            'generation_count_unknown':packet.get('generation_count_unknown',False),
            'source_row_sha256':s['source_row_sha256'],'source_smiles':s['source_smiles'],'isomeric_smiles':s['isomeric_smiles']})
    common_types=[('record_id',pa.string()),('molecule_id',pa.string()),('file_group',pa.int8()),('attempt_id',pa.int8()),('job_id',pa.int64()),('task_id',pa.string()),*extra]
    geometry_schema=pa.schema([*common_types,('atomic_numbers',pa.large_list(pa.int64())),('positions_A',pa.large_list(pa.list_(pa.float64(),3))),
        ('uff_energy_kcal_mol',pa.float64()),('geometry_sha256',pa.string()),('atom_order_sha256',pa.string()),('below_dedup_threshold',pa.bool_()),
        ('native_candidate_id',pa.int64()),('embedding_seed',pa.int64()),('optimizer_code',pa.int64()),('trajectory_snapshots',pa.int64()),('source_once_key',pa.string()),
        ('min_rmsd_to_previously_selected_A',pa.float64()),('PM7_pointer',pa.string()),('PM7_HOF',pa.float64()),('PM7_RMSD',pa.float64())])
    status_schema=pa.schema([*common_types,('state',pa.string()),('error',pa.large_string()),('actual_conformers',pa.int64()),('desired_conformers',pa.int64()),
        ('orders_json',pa.large_string()),('generation_count_unknown',pa.bool_()),('source_row_sha256',pa.string()),('source_smiles',pa.large_string()),('isomeric_smiles',pa.large_string())])
    refs=[]
    for name,rows,schema in (('D20',d20,pa.schema(list(writer.D20_SCHEMA)+extra)),('D3',d3,pa.schema(list(writer.D3_SCHEMA)+extra)),('geometry',base,geometry_schema),('source_status',statuses,status_schema)):
        if not rows:continue
        budget.check(False);path=out/(name+'.parquet')
        ref=writer.write_family_rows(rows,path,schema or pa.Table.from_pylist(rows).schema,{'dataset_version':'v2_candidate','geometry_context':'new_UFF_no_PM7','training_eligible':'false'})
        refs.append(dict(ref,family=name))
    return refs

QUALITY={}
def quality_init(review):
    """Fresh spawn only:original label common cannot collide with S' common."""
    import importlib
    for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
    folder=Q.REPO/'workflows/data_v1_final/labels/streaming_cpu_v1';sys.path.insert(0,str(folder))
    try:
        support=importlib.import_module('support');Q.need(pathlib.Path(support.__file__).absolute()==folder/'support.py','ORIGINAL_LABEL_SUPPORT_PATH')
        cfg=C.meta(review['original_mask_config_reference']);common,masks=support.legacy(cfg);scan=importlib.import_module('scan_v2')
        Q.need(pathlib.Path(scan.__file__).absolute()==folder/'scan_v2.py','ORIGINAL_REFERENCE_REVIEW_FUNCTION_PATH')
    finally:sys.path.pop(0)
    fields=[f for f in C.meta(review['field_map_reference']) if f['task'] in ('D20','D3')]
    calibration=C.meta(review['TRAIN_calibration_reference'])['fields'] if review.get('TRAIN_calibration_reference') else {}
    QUALITY.update(common=common,masks=masks,scan=scan,fields=fields,calibration=calibration)

def quality_packet(packet):
    """Read actual packet numbers;no graph/UFF/QM call,no reference fitting."""
    common,masks=QUALITY['common'],QUALITY['masks'];result=[];mid=packet['molecule_id'];d20=packet.get('D20');atoms=len(packet.get('atomic_numbers',[]))
    rows=[('D20',{'record_id':mid+':graph','total_atoms':atoms,'calc_type':'D20','status':'SUCCESS' if d20 and all(d20['valid_mask']) else 'PROPERTY_FAILED',
        'values_float64':d20['values'] if d20 else [None]*20,'valid_mask':d20['valid_mask'] if d20 else [False]*20,'descriptor_names':d20['names'] if d20 else None})]
    for c in packet['conformers']:
        rows.append(('D3',{'record_id':mid+':uff:'+str(c['conformer_id']),'total_atoms':atoms,'calc_type':'D3','status':'PROPERTY_FAILED' if c['D3_issues'] else 'SUCCESS',**c['D3'],'issues':c['D3_issues']}))
    for family,row in rows:
        fields=[f for f in QUALITY['fields'] if f['task']==family]
        items=[]
        for field,values,indices,reason in common.task_components(row,family,fields):
            valid,source_mask,mask,source_reasons,new_reasons,review=masks.source_value_mask(field,row,values,reason)
            item={'record_id':row['record_id'],'molecule_id':mid,'field_id':field['field_id'],'field_key':field['field_key'],'source_path':field['source_path'],
                'values_float64':values,'atom_indices':indices,'source_value_mask':source_mask,'value_mask':mask,
                'source_reasons':source_reasons,'new_reasons':new_reasons,'review_reasons':review}
            item['robust_z_review_score']=QUALITY['scan'].add_reference_reviews(item,QUALITY['calibration']);items.append(item)
        masks.add_cross_field_checks(items,row);result.extend(items)
    # Original scan_v2's same-sign scalar magnitude factor>1000 is review-only.
    # It does not mask values and does not replace the per-field original gate.
    jumps=[]
    for field in QUALITY['fields']:
        values=[(i['record_id'],i['values_float64'][0]) for i in result if i['field_id']==field['field_id']
            and field['level']=='molecule' and len(i['values_float64'])==1 and all(i['value_mask']) and i['values_float64'][0]!=0]
        if len(values)>=2 and (all(v>0 for _,v in values) or all(v<0 for _,v in values)):
            low=min(values,key=lambda x:abs(x[1]));high=max(values,key=lambda x:abs(x[1]))
            if abs(high[1])/abs(low[1])>1000:jumps.append({'field_id':field['field_id'],'molecule_id':mid,'min_record_id':low[0],
                'max_record_id':high[0],'factor':abs(high[1])/abs(low[1]),'reason':'WITHIN_MOLECULE_JUMP_REVIEW_ONLY'})
    return {'pid':os.getpid(),'items':result,'jumps':jumps,'new_UFF_QM_calls':0,'TRAIN_reference_fit_performed':False}
