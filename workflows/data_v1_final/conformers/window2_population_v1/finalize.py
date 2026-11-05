"""Freeze final Common, full-source physical base maps, D5 pool and final D7."""
from __future__ import annotations
import argparse
import collections
import gzip
import json
from pathlib import Path
from .run import read,info,save,original_membership_functions,check_nested,REPO
from .d7 import quote,parquet_sql,summarize


def final_member(row,state,membership):
    result=dict(row)
    result['source_fill_status_before_window2']=row.get('fill_status')
    result['Sprime_final_status']=state['status']
    result['Sprime_exhaustion_complete']=state['status'] in ('ALREADY_COMPLETE','COMPLETE','EXHAUSTED_N_NO_NEW','UFF_UNSUPPORTED')
    result['Sprime_insufficient']=state.get('insufficient')
    result['Sprime_unique_conformers']=state.get('final_unique_count')
    if state['status']=='EXECUTION_UNRESOLVED' or not state.get('source_valid'):
        result['fill_status']='EXECUTION_UNRESOLVED'
    elif state['status']=='UFF_UNSUPPORTED':
        result['Sprime_status']='UFF_UNSUPPORTED'
    else:
        result['fill_status']=state['status']
        result['merged_uff_count']=state['final_unique_count']
    predicted=membership(result)
    # Explicit taskbook B4: real exhausted shortages are retained at their actual
    # count, rather than force-filled or excluded solely for insufficient N.
    if state['status']=='EXHAUSTED_N_NO_NEW':
        if state['consecutive_no_new']<row['S_conformers'] or state['final_unique_count']>=row['S_conformers']:
            raise ValueError('UNPROVEN_N_NO_NEW_EXHAUSTION')
        predicted['exclusion_reasons']=[reason for reason in predicted['exclusion_reasons'] if reason!='INSUFFICIENT_ACCEPTED_SPRIME']
        predicted['common_population']=not predicted['exclusion_reasons']
        predicted['common_population_v1']=predicted['common_population']
    result.update(predicted)
    result['available_real_Pprime_bases']=result['merged_uff_count']+int(result.get('registered_pprime_extra_conformers',0))
    result['pprime_two_conformers_pending']=result['common_population'] and result['available_real_Pprime_bases']<2
    result['complete_Sprime_for_D5']=bool(result['common_population'] and result['effective_role']=='TRAIN'
        and state.get('source_valid') and state.get('final_unique_count') is not None
        and state['final_unique_count']>=row['S_conformers'])
    return result


def original_d5_rank_hash():
    """Original scientific rank and canonical encoding, without legacy I/O guards."""
    import ast
    import hashlib
    namespace={'hashlib':hashlib,'json':json}
    for relative,name in (('export/wire_v1/codec.py','canonical_json'),('export/pipeline_v1/io.py','rank_hash')):
        path=REPO/'workflows/data_v1_final'/relative
        tree=ast.parse(path.read_text(encoding='utf-8'))
        nodes=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name==name]
        if len(nodes)!=1:raise ValueError('ORIGINAL_D5_RANK_FUNCTION_MISSING:'+name)
        exec(compile(ast.Module(body=nodes,type_ignores=[]),str(path),'exec'),namespace)
    return namespace['rank_hash']


def final_nested_lists(complete,sizes=(120000,240000,600000)):
    """Freeze original seed/domain-ranked prefixes in the actual final complete pool."""
    rank=original_d5_rank_hash()
    mids=sorted(set(complete),key=lambda mid:(rank(20261025,'TRAIN',mid),mid))
    if len(mids)<max(sizes):raise ValueError('ACTUAL_COMPLETE_FINAL_D5_POOL_TOO_SMALL:'+str(len(mids)))
    return {**{'train_'+str(n):mids[:n] for n in sizes},'train_all':mids}

def final_d5(common,original_d5,out,diagnostic_addressable=None):
    import pyarrow as pa
    import pyarrow.parquet as pq
    prior=read(original_d5);parts=prior['components'];out=Path(out);out.mkdir(parents=True,exist_ok=False)
    complete=set()
    train=set()
    for reference in common['membership_tables']:
        for row in pq.read_table(reference['path'],columns=['molecule_id','complete_Sprime_for_D5','common_population','effective_role']).to_pylist():
            if row['common_population'] and row['effective_role']=='TRAIN':train.add(row['molecule_id'])
            if row['complete_Sprime_for_D5']:complete.add(row['molecule_id'])
    lists=final_nested_lists(complete);check_nested(lists);refs={}
    for name,mids in lists.items():
        path=out/(name+'.parquet')
        pq.write_table(pa.table({'molecule_id':mids,'subset_rank':range(len(mids))}),path,compression='zstd')
        refs[name]=info(path,len(mids))
    mids=lists['train_all']
    diagnostic=parts['diagnostic_base_reference']
    diagnostic_mids=set(pq.read_table(diagnostic['path'],columns=['molecule_id']).column('molecule_id').to_pylist())
    if len(diagnostic_mids)!=20000 or not diagnostic_mids<=train:
        raise ValueError('DIAGNOSTIC20K_NOT_FINAL_TRAIN')
    value={'schema':'DATA_V1_FINAL_D5_V1','status':'FROZEN','subsets':refs,
        'diagnostic_molecules':20000,'diagnostic_base_reference':diagnostic,
        'heldout_PM7_bases':parts['heldout_PM7_bases'],
        'heldout_ordinary_Sprime_bases':parts['heldout_ordinary_Sprime_bases'],
        'diagnostic_targets_reference':parts['diagnostic_targets_reference'],
        'actual_heldout_geometry_reference':parts['actual_heldout_geometry_reference'],
        'actual_input_views_reference':parts['actual_input_views_reference'],
        'all_fixed_random_base_index_reference':parts['all_fixed_random_base_index_reference'],
        'training_fixed_random_base_index_reference':parts['training_fixed_random_base_index_reference'],
        'copied_fixed_random_base_index_scope':'LEGACY_PROVISIONAL_ONLY; final ordinary enumeration uses final Common maps and final D7 orders',
        'all_training_lists_anti_join_global_base_child_inputview_targets_before_first_k':True,
        'pool_scope':'ALL_FINAL_COMMON_TRAIN_WITH_EXISTING_COMPLETE_UNIQUE_SPRIME_AT_FREEZE',
        'pool_molecules':len(mids),'nested_selection_recomputed_for_final_complete_pool':True,
        'diagnostic_selection_changed':False,'original_provisional_D5_reference':original_d5,
        'nested_selection':{'seed':20261025,'domain':'TRAIN','rank_function':'original pipeline_v1.io.rank_hash','tie_break':'molecule_id','prefix_sizes':[120000,240000,600000]},
        'diagnostic_addressable_geometry_tables':([diagnostic_addressable] if diagnostic_addressable else []),
        'content_hashes_computed':False}
    save(out/'manifest.json',value)
    return info(out/'manifest.json')



def write_diagnostic_addressable(db,prior,out):
    """Only missing frozen U holdouts get independent diagnostic-only addresses.

    Read original holdout IDs and pointer metadata once inside this producer;
    original F64 coordinates, target values and task-view arrays are not decoded.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq
    components=prior['components']
    held=components['actual_heldout_geometry_reference']
    wanted=set(pq.read_table(components['diagnostic_base_reference']['path'],columns=['geometry_id']).column('geometry_id').to_pylist())
    columns=['geometry_id','molecule_id','geometry_source','sprime_conf_idx','parent_geometry_id','view_id','native_anchor_record_id']
    pointers=[];seen=set();ordinal=0
    for batch in pq.ParquetFile(held['path']).iter_batches(batch_size=8192,columns=columns):
        for row in batch.to_pylist():
            position=ordinal;ordinal+=1
            if row['geometry_id'] not in wanted or row['geometry_source']!='uff_sprime' or row['parent_geometry_id'] is not None or row['view_id'] is not None:continue
            if row['geometry_id'] in seen:raise ValueError('FROZEN_D5_HELDOUT_GEOMETRY_DUPLICATE')
            seen.add(row['geometry_id'])
            if row['sprime_conf_idx'] is None:raise ValueError('FROZEN_D5_HELDOUT_CONF_ID_MISSING')
            pointers.append({'molecule_id':row['molecule_id'],'sprime_conf_idx':row['sprime_conf_idx'],
                'canonical_sprime_conf_idx':row['sprime_conf_idx'],'geometry_id':row['geometry_id'],
                'geometry_source':'uff_sprime','native_record_id':None,'native_anchor_record_id':row['native_anchor_record_id'],
                'source_path':held['path'],'source_row_index':position,'source_format':'parquet',
                'accepted_component_kind':'frozen_d5_actual_heldout_geometry',
                'diagnostic_only':True,'excluded_from_all_training':True,
                'storage_physical_alias':'d5-diagnostic:'+row['geometry_id']})
    if len(pointers)!=components['heldout_ordinary_Sprime_bases']:
        raise ValueError('FROZEN_D5_HELDOUT_UFF_POINTER_COUNT_ALIGNMENT')
    schema=pa.schema([('molecule_id',pa.string()),('sprime_conf_idx',pa.int64()),('canonical_sprime_conf_idx',pa.int64()),
        ('geometry_id',pa.string()),('geometry_source',pa.string()),('native_record_id',pa.string()),
        ('native_anchor_record_id',pa.string()),('source_path',pa.string()),('source_row_index',pa.int64()),
        ('source_format',pa.string()),('accepted_component_kind',pa.string()),('diagnostic_only',pa.bool_()),
        ('excluded_from_all_training',pa.bool_()),('storage_physical_alias',pa.string())])
    db.register('frozen_diagnostic_pointers',pa.Table.from_pylist(pointers,schema=schema))
    if db.execute('''SELECT count(*) FROM frozen_diagnostic_pointers d JOIN uff_map u USING(geometry_id)
        WHERE d.molecule_id<>u.molecule_id OR d.sprime_conf_idx<>u.sprime_conf_idx''').fetchone()[0]:
        raise ValueError('FROZEN_D5_ORDINARY_GEOMETRY_ID_BINDING_CONFLICT')
    if db.execute('''SELECT count(*) FROM frozen_diagnostic_pointers d ANTI JOIN members m USING(molecule_id)''').fetchone()[0]:
        raise ValueError('FROZEN_D5_DIAGNOSTIC_MEMBER_MISSING')
    table=db.execute('''SELECT d.*,m.effective_role,m.source_role,m.common_population,
        EXISTS(SELECT 1 FROM uff_map x WHERE x.molecule_id=d.molecule_id AND x.sprime_conf_idx=d.sprime_conf_idx
            AND x.geometry_id<>d.geometry_id) AS ordinary_physical_id_collision
        FROM frozen_diagnostic_pointers d JOIN members m USING(molecule_id)
        ANTI JOIN uff_map u USING(geometry_id) ORDER BY d.molecule_id,d.geometry_id''').fetch_arrow_table()
    path=Path(out)/'diagnostic_addressable_uff_geometry.parquet'
    pq.write_table(table,path,compression='zstd',row_group_size=8192)
    db.unregister('frozen_diagnostic_pointers')
    return dict(info(path,table.num_rows),accepted_component_kind='frozen_d5_actual_heldout_geometry',
        source_values='original actual_heldout_geometry_reference atomic_numbers/positions_A; no coordinate copy or new numeric calculation',
        scope='Only frozen UFF holdout geometry IDs absent from final ordinary maps; no ordinary N/order change',
        diagnostic_only=True,excluded_from_all_training=True)

def refreshed_orders(task):
    from . import d7 as engine
    raw=engine.native(task['anchor'])
    mol,numbers,_=engine.SCIENCE.graph(raw)
    rows=[{'conformer_id':row['sprime_conf_idx'],'coordinates':row['coordinates'],
        'energy':float(row['uff_energy_kcal_mol'])} for row in task['uff']]
    distance=lambda left,right:engine.SCIENCE.rmsd(mol,left['coordinates'],right['coordinates'])
    value=engine.source_orders(rows,distance,task['molecule_id'],'uff_sprime')
    return task['molecule_id'],json.dumps(value)


def refresh_final_orders(plan,db,rows,states,newrefs,out):
    import concurrent.futures as cf
    import multiprocessing as mp
    import pyarrow as pa
    import pyarrow.parquet as pq
    from . import d7 as engine
    changed={row['molecule_id'] for row in rows if states[row['molecule_id']].get('final_unique_count') is not None
        and (row['uff_sprime_count']!=states[row['molecule_id']]['final_unique_count'] or
        states[row['molecule_id']].get('optimized_candidates',0)>0)}
    refreshed={}
    if changed:
        db.execute('ATTACH '+quote(plan['coordinate_db'])+' AS source_coordinates (READ_ONLY)')
        db.execute('CREATE TABLE final_coordinates AS SELECT u.* FROM source_coordinates.uff u JOIN keep k USING(molecule_id,sprime_conf_idx)')
        if newrefs:
            db.execute('''INSERT INTO final_coordinates SELECT molecule_id,sprime_conf_idx,NULL,coordinates,uff_energy_kcal_mol FROM '''+parquet_sql(newrefs))
        mids=sorted(changed)
        with cf.ProcessPoolExecutor(max_workers=plan['workers'],mp_context=mp.get_context('spawn'),initializer=engine.initialize,
            initargs=(plan['science_path'],)) as pool:
            for offset in range(0,len(mids),1024):
                batch=mids[offset:offset+1024];db.register('batch',pa.table({'molecule_id':batch}))
                anchors=db.execute('SELECT f.* FROM formal f JOIN batch USING(molecule_id) QUALIFY row_number() OVER(PARTITION BY molecule_id ORDER BY record_id)=1').fetch_arrow_table().to_pylist()
                coordinates=db.execute('SELECT f.* FROM final_coordinates f JOIN batch USING(molecule_id)').fetch_arrow_table().to_pylist()
                byid=collections.defaultdict(list)
                for row in coordinates:byid[row['molecule_id']].append(row)
                tasks=[{'molecule_id':row['molecule_id'],'anchor':row,'uff':byid[row['molecule_id']]} for row in anchors]
                refreshed.update(pool.map(refreshed_orders,tasks,chunksize=4));db.unregister('batch')
    actual_common=dict(db.execute('SELECT molecule_id,common_population FROM members').fetchall())
    parts=[]
    for offset in range(0,len(rows),8192):
        values=[]
        for source in rows[offset:offset+8192]:
            row=dict(source);state=states[row['molecule_id']]
            row['common_population']=actual_common[row['molecule_id']]
            if state.get('final_unique_count') is not None:
                row['uff_sprime_count']=row['uff_sprime_unique']=state['final_unique_count']
                if row['molecule_id'] in refreshed:row['sprime_orders_json']=refreshed[row['molecule_id']]
                row['sprime_unique_ids_json']=json.dumps(json.loads(row['sprime_orders_json'])['fixed_random']) if row.get('sprime_orders_json') else '[]'
            values.append(row)
        path=out/('final_orders-%06d.parquet'%(offset//8192));pq.write_table(pa.Table.from_pylist(values),path,compression='zstd')
        parts.append(info(path,len(values)))
    return parts


def write_pprime_first2(db,old,out):
    """Actual first min(2,available), including already registered N1 extras."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    extras=[]
    for reference in old.get('registered_extra_geometry_map_tables',[]):
        if reference['path'].endswith('.jsonl'):
            with Path(reference['path']).open(encoding='utf-8') as stream:
                extras.extend(json.loads(line) for line in stream)
        else:
            extras.extend(pq.read_table(reference['path']).to_pylist())
    locator=old.get('n1_component_config',old.get('n1_component_config_reference'))
    if locator:
        for component in read(locator)['components']:
            accepted=read(component['accepted_extra_index_reference'])
            for position,row in enumerate(accepted['records']):
                extras.append(dict(row,source_path=accepted['geometry_table']['path'],source_row_index=position,source_format='parquet'))
    unique={}
    for row in extras:
        key=(row['molecule_id'],row['sprime_conf_idx'])
        if key in unique and unique[key]['geometry_id']!=row['geometry_id']:
            raise ValueError('REGISTERED_EXTRA_ID_BINDING_CONFLICT')
        unique[key]=row
    extras=list(unique.values())
    shape=pa.schema([('molecule_id',pa.string()),('sprime_conf_idx',pa.int64()),('geometry_id',pa.string()),
        ('source_path',pa.string()),('source_row_index',pa.int64()),('source_format',pa.string())])
    values=[{key:row.get(key) for key in shape.names} for row in extras]
    extra_path=out/'registered_extra_physical_geometry.parquet'
    extra_schema=shape.append(pa.field('geometry_source',pa.string())).append(pa.field('native_record_id',pa.string())).append(pa.field('accepted_component_kind',pa.string()))
    pointer_rows=[dict(row,geometry_source='uff_sprime',native_record_id=None,accepted_component_kind='CURRENT_CANONICAL_N1_PHYSICAL_ACCEPTED') for row in values]
    pq.write_table(pa.Table.from_pylist(pointer_rows,schema=extra_schema),extra_path,compression='zstd')
    db.register('registered_extras',pa.Table.from_pylist(values,schema=shape))
    db.execute('''CREATE TEMP VIEW all_available_for_pprime AS
        SELECT molecule_id,sprime_conf_idx,geometry_id,source_path,source_row_index,source_format,'ordinary' AS usage_domain FROM uff_map
        UNION ALL SELECT molecule_id,sprime_conf_idx,geometry_id,source_path,source_row_index,source_format,'registered_pprime_extra' FROM registered_extras''')
    if db.execute('SELECT count(*) FROM (SELECT molecule_id,sprime_conf_idx FROM all_available_for_pprime GROUP BY ALL HAVING count(*)<>1)').fetchone()[0]:
        raise ValueError('PPRIME_ORDINARY_AND_EXTRA_PHYSICAL_ID_COLLISION')
    # Scientific fixed-random identity/order is unchanged. These are key-based
    # random ranks, never file or record-content integrity hashes.
    selected=db.execute('''SELECT a.*,m.effective_role,m.source_role,m.common_population,
        row_number() OVER(PARTITION BY a.molecule_id ORDER BY
        sha256('data-v1-conformer-order:20261025:'||a.molecule_id||':uff_sprime:'||CAST(a.sprime_conf_idx AS VARCHAR)),CAST(a.sprime_conf_idx AS VARCHAR))-1 AS fixed_random_rank
        FROM all_available_for_pprime a JOIN members m USING(molecule_id)
        QUALIFY fixed_random_rank<2''').fetch_arrow_table()
    path=out/'Pprime_first2_available.parquet';pq.write_table(selected,path,compression='zstd',row_group_size=8192)
    states=db.execute('''SELECT m.molecule_id,m.effective_role,m.source_role,m.common_population,m.Sprime_final_status,
        coalesce(a.available,0) AS actual_available_geometries,least(2,coalesce(a.available,0)) AS selected_first2,
        greatest(0,2-coalesce(a.available,0)) AS missing_to_two,
        CASE WHEN coalesce(a.available,0)>=2 THEN 'TWO_REAL_GEOMETRIES_AVAILABLE'
        WHEN m.Sprime_final_status='EXECUTION_UNRESOLVED' THEN 'EXECUTION_UNRESOLVED_NOT_ASSUMED_EMPTY_OR_COMPLETE'
        WHEN m.Sprime_final_status='UFF_UNSUPPORTED' THEN 'UFF_UNSUPPORTED'
        WHEN coalesce(a.available,0)=1 AND m.S_conformers=1 THEN 'ORIGINAL_N1_ONLY_ONE_REAL_GEOMETRY_NO_REGISTERED_SECOND'
        WHEN m.Sprime_final_status='EXHAUSTED_N_NO_NEW' THEN 'EXHAUSTED_N_NO_NEW_ACTUAL_SHORTFALL'
        ELSE 'ACTUAL_AVAILABLE_COUNT_BELOW_TWO' END AS reason
        FROM members m LEFT JOIN (SELECT molecule_id,count(*) AS available FROM all_available_for_pprime GROUP BY molecule_id) a USING(molecule_id)''').fetch_arrow_table()
    statepath=out/'Pprime_first2_scope_states.parquet';pq.write_table(states,statepath,compression='zstd',row_group_size=8192)
    manifest={'schema':'PPRIME_ACTUAL_FIXED_RANDOM_FIRST2_SCOPE_V1','status':'PHYSICAL_SCOPE_ONLY_NOT_LABEL_COMPUTATION',
        'selected_geometry_table':info(path,selected.num_rows),'record_level_state_table':info(statepath,states.num_rows),
        'registered_extra_geometry_table':info(extra_path,len(pointer_rows)),
        'selection':'first min(2,actual_available) in unchanged seed20261025 physical-ID fixed_random order',
        'registered_real_N1_extras_used':True,'new_N1_generation_for_pprime':False,
        'duplicate_or_padding_geometry':False,'Pprime_third_or_later_in_scope':False,
        'completed_matching_physical_ID_labels_reused_by_consumer':True}
    save(out/'Pprime_first2_scope.json',manifest)
    return info(out/'Pprime_first2_scope.json')

def finalize(plan):
    import duckdb
    import pyarrow as pa
    import pyarrow.parquet as pq
    old=read(plan['common']);fill=read(plan['fill']);d7=read(plan['d7'])
    out=Path(plan['output']);out.mkdir(parents=True,exist_ok=False);(out/'membership').mkdir();(out/'physical_geometry').mkdir()
    states={};keep=[];newrefs=[]
    for part in fill['parts']:
        for row in pq.read_table(part['states']['path']).to_pylist():
            mid=row['molecule_id']
            if mid in states:raise ValueError('DUPLICATE_FINAL_SPRIME_STATE')
            states[mid]=row
            if row.get('source_valid'):
                keep.extend({'molecule_id':mid,'sprime_conf_idx':idx} for idx in row['kept_original_sprime_ids'])
        if part['new_geometry']:newrefs.append(part['new_geometry'])
    if len(states)!=1220466:raise ValueError('INCOMPLETE_FULL_SOURCE_SPRIME_STATES')
    membership,_=original_membership_functions();members=[];allrows=[];counts=collections.Counter()
    for reference in old['membership_tables']:
        rows=[]
        for row in pq.read_table(reference['path']).to_pylist():
            value=final_member(row,states[row['molecule_id']],membership);rows.append(value);allrows.append(value)
            if value['common_population']:counts[value['effective_role']]+=1
        path=out/'membership'/Path(reference['path']).name
        pq.write_table(pa.Table.from_pylist(rows),path,compression='zstd',row_group_size=8192);members.append(info(path,len(rows)))
    db=duckdb.connect(str(Path(plan['workspace'])/'final_population.duckdb'))
    db.execute('SET threads='+str(plan['workers']))
    db.register('population',pa.Table.from_pylist(allrows))
    db.execute('CREATE TABLE members AS SELECT * FROM population');db.unregister('population')
    db.register('keep_input',pa.Table.from_pylist(keep,schema=pa.schema([('molecule_id',pa.string()),('sprime_conf_idx',pa.int64())])))
    db.execute('CREATE TABLE keep AS SELECT * FROM keep_input');db.unregister('keep_input');keep=[]
    db.execute('CREATE TABLE formal AS SELECT * FROM read_parquet('+quote(plan['formal_index'])+')')
    old_pm7=[r for r in old['physical_geometry_tables'] if Path(r['path']).name.startswith('pm7-')]
    old_uff=[r for r in old['physical_geometry_tables'] if Path(r['path']).name.startswith('uff_sprime-')]
    db.execute('CREATE TABLE old_pm7 AS SELECT * FROM '+parquet_sql(old_pm7))
    db.execute('CREATE TABLE old_uff AS SELECT * FROM '+parquet_sql(old_uff))
    # sha256 below is only the already frozen scientific geometry-ID derivation
    # for previously excluded source IDs, never a source/payload integrity hash.
    db.execute('''CREATE TABLE pm7_map AS SELECT f.molecule_id,f.record_id AS native_record_id,NULL::BIGINT AS sprime_conf_idx,
        'pm7' AS geometry_source,coalesce(p.geometry_id,'pm7:'||sha256(f.record_id)) AS geometry_id,
        f.source_path,f.real_index,f.record_payload_sha256,'native_lmdb' AS source_format,
        m.effective_role,m.source_role,m.common_population,m.legacy_routine_molecule,
        NULL::VARCHAR AS parent_geometry_id,NULL::VARCHAR AS view_id,
        CASE WHEN length(CAST(f.real_index AS VARCHAR))<9 THEN lpad(CAST(f.real_index AS VARCHAR),9,'0') ELSE CAST(f.real_index AS VARCHAR) END AS source_key
        FROM formal f JOIN members m USING(molecule_id) LEFT JOIN old_pm7 p ON p.native_record_id=f.record_id''')
    originals=read(old['old_sprime_manifest']);sources=[r for r in originals['references'] if r.get('kind')=='conformers']
    scan='read_parquet(['+','.join(quote(r['path']) for r in sources)+'],filename=true,file_row_number=true)'
    db.execute('''CREATE TABLE baseline AS SELECT molecule_id,sprime_conf_idx,filename,file_row_number,
        status,converged,source_record_id,seed,uff_energy_kcal_mol FROM '''+scan)
    db.execute('''CREATE TABLE uff_map AS SELECT b.molecule_id,NULL::VARCHAR AS native_record_id,b.sprime_conf_idx,
        b.sprime_conf_idx AS canonical_sprime_conf_idx,'uff_sprime' AS geometry_source,
        coalesce(u.geometry_id,'uff_sprime:'||sha256(b.molecule_id||':'||CAST(b.sprime_conf_idx AS VARCHAR))) AS geometry_id,
        b.filename AS source_path,b.file_row_number AS source_row_index,'parquet' AS source_format,
        b.source_record_id AS native_anchor_record_id,b.seed,b.uff_energy_kcal_mol,
        m.effective_role,m.source_role,m.common_population,m.legacy_routine_molecule,
        NULL::VARCHAR AS parent_geometry_id,NULL::VARCHAR AS view_id
        FROM baseline b JOIN keep k USING(molecule_id,sprime_conf_idx) JOIN members m USING(molecule_id)
        LEFT JOIN old_uff u ON u.source_path=b.filename AND u.source_row_index=b.file_row_number
        WHERE b.status='SUCCESS' AND b.converged IS TRUE''')
    # Existing generated Common maps already carry exact original packet locator.
    db.execute('''INSERT INTO uff_map SELECT u.molecule_id,NULL,u.sprime_conf_idx,u.sprime_conf_idx,'uff_sprime',u.geometry_id,
        u.source_path,u.source_row_index,u.source_format,u.native_anchor_record_id,u.seed,u.uff_energy_kcal_mol,
        m.effective_role,m.source_role,m.common_population,m.legacy_routine_molecule,NULL,NULL
        FROM old_uff u JOIN keep USING(molecule_id,sprime_conf_idx) JOIN members m USING(molecule_id)
        WHERE u.source_format<>'parquet' ''')
    existing=set(row[0] for row in db.execute('SELECT DISTINCT source_path FROM old_uff').fetchall())
    bounds=dict(db.execute('SELECT molecule_id,max(sprime_conf_idx) FROM baseline GROUP BY molecule_id').fetchall())
    index=read(old['completion_index']);extra=[]
    n_by_id={row['molecule_id']:row['S_conformers'] for row in allrows}
    role_by_id={row['molecule_id']:row for row in allrows}
    wanted=collections.defaultdict(set)
    for mid,idx in db.execute('SELECT * FROM keep').fetchall():wanted[mid].add(idx)
    for outcome in read(index['outcomes']):
        mid=outcome['molecule_id'];reference=outcome.get('package_reference')
        if not reference or reference['path'] in existing or not wanted[mid]:continue
        with gzip.open(reference['path'],'rt',encoding='utf-8') as stream:packet=json.load(stream)
        generated=[row for row in packet['conformers'] if row['origin']!='accepted_sprime']
        start=max(bounds.get(mid,-1),n_by_id[mid]-1)+1
        for ordinal,row in enumerate(generated):
            idx=start+ordinal
            if idx not in wanted[mid]:continue
            member=role_by_id[mid]
            # The SQL layer supplies the unchanged stable-ID recipe uniformly.
            extra.append({'molecule_id':mid,'sprime_conf_idx':idx,'source_path':reference['path'],
                'source_row_index':packet['conformers'].index(row),'source_format':'reproduction_json_gz',
                'native_anchor_record_id':row['source_record_id'],'seed':row['seed'],
                'uff_energy_kcal_mol':row['uff_energy_kcal_mol']})
    for reference in newrefs:
        for position,row in enumerate(pq.read_table(reference['path']).to_pylist()):
            extra.append({'molecule_id':row['molecule_id'],'sprime_conf_idx':row['sprime_conf_idx'],
                'source_path':reference['path'],'source_row_index':position,'source_format':'parquet',
                'native_anchor_record_id':row['source_record_id'],'seed':row['seed'],
                'uff_energy_kcal_mol':row['uff_energy_kcal_mol']})
    if extra:
        db.register('extra',pa.Table.from_pylist(extra))
        db.execute('''INSERT INTO uff_map SELECT e.molecule_id,NULL,e.sprime_conf_idx,e.sprime_conf_idx,'uff_sprime',
            'uff_sprime:'||sha256(e.molecule_id||':'||CAST(e.sprime_conf_idx AS VARCHAR)),
            e.source_path,e.source_row_index,e.source_format,e.native_anchor_record_id,e.seed,e.uff_energy_kcal_mol,
            m.effective_role,m.source_role,m.common_population,m.legacy_routine_molecule,NULL,NULL
            FROM extra e JOIN members m USING(molecule_id)''');db.unregister('extra')
    if db.execute('SELECT count(*) FROM (SELECT geometry_id FROM uff_map GROUP BY geometry_id HAVING count(*)<>1)').fetchone()[0]:
        raise ValueError('FINAL_PHYSICAL_SPRIME_ID_DUPLICATE')
    if db.execute('''SELECT count(*) FROM members m LEFT JOIN (SELECT molecule_id,count(*) n FROM uff_map GROUP BY molecule_id) u USING(molecule_id)
        WHERE m.Sprime_exhaustion_complete AND m.Sprime_final_status<>'UFF_UNSUPPORTED'
        AND coalesce(u.n,0)<>m.Sprime_unique_conformers''').fetchone()[0]:
        raise ValueError('FINAL_SPRIME_STATE_PHYSICAL_MAP_COUNT_ALIGNMENT')
    maps=[]
    for source in ('pm7','uff'):
        for part in range(16):
            path=out/'physical_geometry'/('%s-%04d.parquet'%('uff_sprime' if source=='uff' else source,part))
            table=db.execute('SELECT * FROM '+source+'_map WHERE hash(molecule_id)%16=?',[part]).fetch_arrow_table()
            pq.write_table(table,path,compression='zstd',row_group_size=8192);maps.append(info(path,table.num_rows))
    role_rows=[dict(effective_role=role,molecules=number,pm7_records=npm7,uff_records=nuff) for role,number,npm7,nuff in db.execute('SELECT effective_role,count(*),sum(S_conformers),sum(merged_uff_count) FROM members WHERE common_population GROUP BY effective_role ORDER BY effective_role').fetchall()]
    common=dict(old,roles=role_rows,status='COMMON_POPULATION_V1_FROZEN',version='v1-final',membership_tables=members,
        physical_geometry_tables=maps,full_source_physical_geometry_tables=maps,
        physical_map_scope='ALL_SOURCE_TRAIN_AND_FULL_WITH_COMMON_FLAG_AND_ROUTINE_MARKER',
        source_sprime_closure=plan['fill'],Sprime_exhaustion_complete=fill['status']=='COMPLETE',
        common_role_counts=dict(counts),Sprime_status_counts=fill['status_counts'],
        pprime_n1_molecules=sum(row['pprime_two_conformers_pending'] for row in allrows),
        shortage_policy='EXHAUSTED_N_NO_NEW_KEPT_AT_ACTUAL_COUNT_WITH_EXPLICIT_MASKS',
        source_integrity_hashes_computed=False,normalization_train_only=True)
    diagnostic_addressable=write_diagnostic_addressable(db,read(plan['original_d5']),out)
    common['diagnostic_addressable_geometry_tables']=[diagnostic_addressable]
    first2_ref=write_pprime_first2(db,old,out)
    common['Pprime_first2_scope_reference']=first2_ref
    common['registered_extra_geometry_map_tables']=[read(first2_ref)['registered_extra_geometry_table']]
    common_ref=save(out/'manifest.json',common)
    d5ref=final_d5(common,plan['original_d5'],out/'D5',diagnostic_addressable)
    # Reuse produced PM7 statistics and update S-prime unique counts to actual
    # final retained geometries. No geometry or numeric label is reread for QA.
    rows=[]
    for reference in d7['order_tables']:
        for row in pq.read_table(reference['path']).to_pylist():
            rows.append(row)
    final_orders=refresh_final_orders(plan,db,rows,states,newrefs,out)
    final_rows=[]
    for reference in final_orders:final_rows.extend(pq.read_table(reference['path']).to_pylist())
    report=summarize(final_rows);report.update(status='COMPLETE' if fill['status']=='COMPLETE' and d7['status']=='COMPLETE' else 'PARTIAL_WITH_EXPLICIT_FAILURES',
        original_D7_reference=plan['d7'],source_sprime_closure=plan['fill'],
        order_tables=final_orders,Sprime_orders_require_new_geometry_merge=False)
    save(out/'D7.json',report)
    save(out/'delivery_manifest.json',{'files':[*members,*maps,diagnostic_addressable,common_ref,d5ref,first2_ref,info(out/'D7.json')]})
    db.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--plan',required=True)
    args=parser.parse_args();finalize(read(args.plan))


if __name__=='__main__':main()