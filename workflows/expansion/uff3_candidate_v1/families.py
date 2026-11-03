"""Original WP5 float64 families and original masks, explicit maximum-three rows."""
from __future__ import annotations
import math
from workflows.expansion.no_pm7_uff_d_main_v1.families import load_writer, quality_init, quality_packet
from .core import canonical, sha

_QUALITY_REVIEW=None


def export_packets(items,out,budget,job_id):
    import pyarrow as pa
    pa.set_cpu_count(1);pa.set_io_thread_count(1)
    writer=load_writer()
    extra=[('dataset_version',pa.string()),('stream',pa.string()),('stream_rank',pa.int64()),
        ('pubchem_cid',pa.int64()),('pubchem_version',pa.string()),('full_key',pa.string()),
        ('wp5_key',pa.string()),('geometry_source',pa.string()),('geometry_context',pa.string()),
        ('conformer_id',pa.int64()),('training_eligible',pa.bool_()),
        ('producer_packet_sha256',pa.string()),('writer_job_id',pa.int64()),
        ('candidate_cache_sha256',pa.string())]
    d20=[];d3=[];geometry=[];statuses=[]
    for packet_ref,packet in items:
        source=packet['source'];mid=packet['molecule_id']
        if len(packet['conformers'])>3 or packet['requested_conformers']!=3:
            raise ValueError('PRODUCTION_FAMILY_EXPORT_AT_MOST_THREE')
        common={'molecule_id':mid,'file_group':None,'attempt_id':0,
            'job_id':int(packet['producer_job_id']),'task_id':packet['once_key'],
            'dataset_version':'v2_candidate','stream':source['stream'],'stream_rank':source['stream_rank'],
            'pubchem_cid':source['cid'],'pubchem_version':source['pubchem_version'],
            'full_key':source['full_key'],'wp5_key':source.get('wp5_key',source['full_key'][:14]+':'+source['full_key'][-1]),
            'geometry_source':'uff_sprime','geometry_context':'NEW_UFF_NO_PM7',
            'training_eligible':False,'producer_packet_sha256':packet_ref['sha256'],
            'writer_job_id':int(job_id),'candidate_cache_sha256':packet['candidate_cache_sha256']}
        value=packet.get('D20')
        d20.append({**common,'record_id':mid+':graph','conformer_id':None,
            'geometry_source':None,'geometry_context':'SOURCE_SMILES_GRAPH_NO_GEOMETRY',
            'schema_ref':'V2_CANDIDATE_ORIGINAL_D20_NO_KAPPA',
            'descriptor_names':value['names'] if value else None,
            'values_float64':value['values'] if value else [None]*20,
            'valid_mask':value['valid_mask'] if value else [False]*20,
            'status':'SUCCESS' if value and all(value['valid_mask']) else 'PROPERTY_FAILED',
            'issues':value['issues'] if value else ['SOURCE_LABEL_UNAVAILABLE_NO_RETRY']})
        for row in packet['conformers']:
            record_id=mid+':uff:'+str(row['conformer_id'])
            values=row['D3'];issues=list(row['D3_issues'])
            for name in ('PMI1','PMI2','PMI3','PBF_A','volume_A3','SASA_total_A2'):
                if values.get(name) is None or not math.isfinite(values[name]):
                    issues.append('D3_MISSING_OR_NONFINITE:'+name)
            atoms=values.get('SASA_atom_A2')
            if atoms is None or len(atoms)!=len(packet['atomic_numbers']) or not all(math.isfinite(v) for v in atoms):
                issues.append('D3_ATOM_SASA_UNAVAILABLE_OR_SHAPE')
            d3.append({**common,'record_id':record_id,'conformer_id':row['conformer_id'],
                'schema_ref':'V2_CANDIDATE_ORIGINAL_D3_NEW_UFF_MAX3',**values,
                'status':'PROPERTY_FAILED' if issues else 'SUCCESS','issues':issues})
            geometry.append({**common,'record_id':record_id,'conformer_id':row['conformer_id'],
                'atomic_numbers':packet['atomic_numbers'],'positions_A':row['coordinates'],
                'uff_energy_kcal_mol':row['energy'],'geometry_sha256':row['geometry_sha256'],
                'atom_order_sha256':packet['atom_order_sha256'],'native_candidate_id':row['candidate_id'],
                'embedding_seed':packet['seed'],'optimizer_code':row['optimizer_code'],
                'trajectory_snapshots':row['iterations'],'source_once_key':packet['once_key'],
                'below_dedup_threshold':False,
                'min_rmsd_to_previously_selected_A':row['min_rmsd_to_previously_selected_A'],
                'PM7_pointer':None,'PM7_HOF':None,'PM7_RMSD':None})
        statuses.append({**common,'record_id':mid,'conformer_id':None,'state':packet['state'],
            'error':packet.get('error'),'actual_conformers':None if packet.get('generation_count_unknown') else len(packet['conformers']),
            'desired_conformers':3,'insufficient_conformers':packet.get('insufficient_conformers',True),
            'orders_json':canonical(packet['orders']).decode(),
            'generation_order_json':canonical(packet.get('generation_order',[])).decode(),
            'generation_count_unknown':packet.get('generation_count_unknown',False),
            'cache_complete':packet.get('cache_complete',False),
            'source_row_sha256':source.get('source_row_sha256'),
            'source_smiles':source['source_smiles'],'isomeric_smiles':source['isomeric_smiles']})
    common_types=[('record_id',pa.string()),('molecule_id',pa.string()),('file_group',pa.int8()),
        ('attempt_id',pa.int8()),('job_id',pa.int64()),('task_id',pa.string()),*extra]
    geometry_schema=pa.schema([*common_types,('atomic_numbers',pa.large_list(pa.int64())),
        ('positions_A',pa.large_list(pa.list_(pa.float64(),3))),('uff_energy_kcal_mol',pa.float64()),
        ('geometry_sha256',pa.string()),('atom_order_sha256',pa.string()),('native_candidate_id',pa.int64()),
        ('embedding_seed',pa.int64()),('optimizer_code',pa.int64()),('trajectory_snapshots',pa.int64()),
        ('source_once_key',pa.string()),('below_dedup_threshold',pa.bool_()),
        ('min_rmsd_to_previously_selected_A',pa.float64()),('PM7_pointer',pa.string()),
        ('PM7_HOF',pa.float64()),('PM7_RMSD',pa.float64())])
    status_schema=pa.schema([*common_types,('state',pa.string()),('error',pa.large_string()),
        ('actual_conformers',pa.int64()),('desired_conformers',pa.int64()),('insufficient_conformers',pa.bool_()),
        ('orders_json',pa.large_string()),('generation_order_json',pa.large_string()),
        ('generation_count_unknown',pa.bool_()),('cache_complete',pa.bool_()),
        ('source_row_sha256',pa.string()),('source_smiles',pa.large_string()),('isomeric_smiles',pa.large_string())])
    refs=[]
    for family,rows,schema in (('D20',d20,pa.schema(list(writer.D20_SCHEMA)+extra)),
        ('D3',d3,pa.schema(list(writer.D3_SCHEMA)+extra)),('geometry',geometry,geometry_schema),
        ('source_status',statuses,status_schema)):
        if not rows:continue
        budget.check(False)
        ref=writer.write_family_rows(rows,out/(family+'.parquet'),schema,
            {'dataset_version':'v2_candidate','maximum_delivered_conformers':'3',
             'geometry_context':'new_UFF_no_PM7','training_eligible':'false'})
        refs.append(dict(ref,family=family))
    return refs


def export_masks(items,out,budget,quality_review):
    """Call the unchanged original mask/review function objects, no R/N fit."""
    import pyarrow as pa
    global _QUALITY_REVIEW
    fingerprint=sha(canonical(quality_review))
    if _QUALITY_REVIEW!=fingerprint:
        quality_init(quality_review);_QUALITY_REVIEW=fingerprint
    values=[]
    for packet_reference,packet in items:
        result=quality_packet(packet)
        for item in result['items']:
            values.append({'record_id':item['record_id'],'molecule_id':item['molecule_id'],
                'field_id':str(item['field_id']),'field_key':item['field_key'],'source_path':item['source_path'],
                'values_float64':item['values_float64'],'atom_indices':item.get('atom_indices'),
                'source_value_mask':item['source_value_mask'],'value_mask':item['value_mask'],
                'source_reasons_json':canonical(item['source_reasons']).decode(),
                'new_reasons_json':canonical(item['new_reasons']).decode(),
                'review_reasons_json':canonical(item['review_reasons']).decode(),
                'robust_z_review_score_json':canonical(item['robust_z_review_score']).decode(),
                'within_molecule_jumps_json':canonical(result['jumps']).decode(),
                'producer_packet_sha256':packet_reference['sha256'],
                'dataset_version':'v2_candidate','stream':packet['source']['stream']})
    schema=pa.schema([('record_id',pa.string()),('molecule_id',pa.string()),('field_id',pa.string()),
        ('field_key',pa.string()),('source_path',pa.string()),('values_float64',pa.large_list(pa.float64())),
        ('atom_indices',pa.large_list(pa.int64())),('source_value_mask',pa.large_list(pa.bool_())),
        ('value_mask',pa.large_list(pa.bool_())),('source_reasons_json',pa.large_string()),
        ('new_reasons_json',pa.large_string()),('review_reasons_json',pa.large_string()),
        ('robust_z_review_score_json',pa.large_string()),('within_molecule_jumps_json',pa.large_string()),
        ('producer_packet_sha256',pa.string()),('dataset_version',pa.string()),('stream',pa.string())])
    if not values:return None
    budget.check(False)
    return dict(load_writer().write_family_rows(values,out/'validity_masks.parquet',schema,
        {'dataset_version':'v2_candidate','fit_new_R_N_reference':'false',
         'mask_functions':'unchanged_original'}),family='validity_masks')
