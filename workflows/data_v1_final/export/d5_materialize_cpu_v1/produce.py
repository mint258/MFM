"""Resource orchestration around original D5 normalization/validation/selection."""
from __future__ import annotations
import os
from pathlib import Path
from . import contract as C,resources as R


def originals():
    import sys
    if str(C.EXPORT) not in sys.path:sys.path.insert(0,str(C.EXPORT))
    from pipeline_v1 import materialize as M,materialize_v2 as V,io as I,distributions as D
    from wire_v1 import sampling_projection_v1 as P
    for module,relative in ((M,'pipeline_v1/materialize.py'),(V,'pipeline_v1/materialize_v2.py'),
            (I,'pipeline_v1/io.py'),(D,'pipeline_v1/distributions.py'),(P,'wire_v1/sampling_projection_v1.py')):
        C.need(Path(module.__file__).absolute()==C.EXPORT/relative,'ORIGINAL_MODULE_OBJECT_NOT_CLONE')
    C.need(V.baseline is M and V._BASE_VALIDATE is M.validate,'ORIGINAL_PHYSICAL_PARENT_ADAPTER_OBJECTS')
    C.need(all(tuple(M.COLUMNS[k])==C.COLUMNS[k] for k in M.COLUMNS),'ORIGINAL_COLUMNS_NOT_SILENTLY_REDEFINED')
    return M,V,I,D,P


def ingest(task):
    ref,groups,kinds,columns,observed,destination,control,options=task
    M,_,I,_,_=originals();R.worker_check(control);R.unchanged(ref,observed)
    db=I.connect(destination);counts={k:0 for k in kinds}
    try:
        for kind in kinds:
            definition=M.SCHEMA[kind] if kind!='atom_counts' else 'geometry_id TEXT PRIMARY KEY,n_atoms INTEGER NOT NULL CHECK(n_atoms>0)'
            db.execute('CREATE TABLE data_'+kind+'('+definition+')')
        names=sorted({source for kind in kinds for source in columns[kind].values()})
        if 'features' in kinds and options['feature_filter_column'] is not None:
            names=sorted(set(names)|{options['feature_filter_column']})
        for batch in I.batches(ref,columns=names,row_groups=groups,hash_input=False):
            R.worker_check(control)
            C.need(batch.nbytes<=R.BATCH_BYTES,'FINITE_METADATA_BATCH_SOFTWARE_BOUND_NO_TRUNCATION')
            source=batch.to_pylist()
            for kind in kinds:
                normalized=[]
                for row in source:
                    if kind=='features' and options['feature_filter_column'] is not None:
                        flag=row[options['feature_filter_column']];C.need(type(flag) is bool,'ACTUAL_COMMON_FEATURE_FILTER_BOOL')
                        if not flag:continue
                    selected={key:row[value] for key,value in columns[kind].items()}
                    if kind=='geometries':C.need(selected['view_id']!='pprime_parent_expanded_v1','N1_PARENT_COLLECTION_IS_NOT_PERTURBATION_CHILD')
                    if kind=='atom_counts':
                        C.need(type(selected['n_atoms']) is int and selected['n_atoms']>0,'POSITIVE_ACTUAL_ATOM_COUNT_NOT_BOOL')
                        value=(M.text(selected['geometry_id']),selected['n_atoms'])
                    else:value=M.normalize(kind,selected)
                    normalized.append(value)
                if normalized:
                    db.executemany('INSERT INTO data_'+kind+' VALUES('+','.join('?' for _ in normalized[0])+')',normalized)
                    db.commit();counts[kind]+=len(normalized)
            I.memory_guard();R.worker_check(control)
    finally:db.close()
    R.unchanged(ref,observed)
    return {'kinds':kinds,'path':destination,'rows':counts,'pid':os.getpid(),'row_groups':groups,'input_reference':ref}


def import_tables(db,tables,columns,frames,out,budget,options):
    import pyarrow.parquet as pq
    by_ref={}
    # Coalesce common/features when they are the same physical Parquet. Each
    # physical input row group is read once by one task, not once per role.
    for kind in C.TABLES:
        for ref in tables[kind]:
            key=(ref['path'],ref['bytes'],ref['sha256'])
            entry=by_ref.setdefault(key,{'ref':ref,'kinds':[]})
            C.need(kind not in entry['kinds'],'DUPLICATE_TABLE_REFERENCE_IN_SAME_KIND')
            entry['kinds'].append(kind)
    def tasks():
        ordinal=0
        for item in by_ref.values():
            ref=item['ref'];R.unchanged(ref,frames[ref['path']]);p=pq.ParquetFile(ref['path'])
            try:
                for rg in range(p.metadata.num_row_groups):
                    yield (ref,[rg],item['kinds'],columns,frames[ref['path']],str(out/('ingest-%08d.sqlite'%ordinal)),budget.control,options)
                    ordinal+=1
            finally:p.close()
    results=[]
    for result in R.ordered_map(ingest,tasks(),budget):
        db.execute('ATTACH DATABASE ? AS shard',(result['path'],))
        try:
            for kind in result['kinds']:db.execute('INSERT INTO '+kind+' SELECT * FROM shard.data_'+kind)
            db.commit()
        finally:db.execute('DETACH DATABASE shard')
        results.append(result)
    return results


def physical_map(db,plan,frames,budget):
    M,_,I,_,_=originals();common=C.meta(plan['parent_references']['common_manifest'])
    db.execute('CREATE TABLE actual_physical(geometry_id TEXT PRIMARY KEY,molecule_id TEXT,geometry_source TEXT,native_record_id TEXT,sprime_conf_idx INTEGER)')
    columns=['geometry_id','molecule_id','geometry_source','native_record_id','sprime_conf_idx']
    for raw in common['physical_geometry_tables']:
        ref=C.reference(raw);R.unchanged(ref,frames[ref['path']])
        for batch in I.batches(ref,columns=columns,hash_input=False):
            budget.check();rows=[]
            for value in batch.to_pylist():
                row={**value,'parent_geometry_id':None,'view_id':None};M.normalize('geometries',row)
                rows.append(tuple(value[k] for k in columns))
            db.executemany('INSERT INTO actual_physical VALUES(?,?,?,?,?)',rows);db.commit()
        R.unchanged(ref,frames[ref['path']])
    # UFF native_record_id remains provenance, not its physical identity.
    left="SELECT geometry_id,molecule_id,geometry_source,CASE WHEN geometry_source='pm7' THEN native_record_id END AS native_record_id,sprime_conf_idx FROM geometries WHERE parent_geometry_id IS NULL"
    right="SELECT geometry_id,molecule_id,geometry_source,CASE WHEN geometry_source='pm7' THEN native_record_id END AS native_record_id,sprime_conf_idx FROM actual_physical"
    I.reject_rows(db,left+' EXCEPT '+right,'BASE_GEOMETRY_NOT_FROM_ACTUAL_ORDINARY_COMMON_MAP')
    I.reject_rows(db,right+' EXCEPT '+left,'ACTUAL_ORDINARY_COMMON_BASE_MISSING_NO_N1_EXTRA_SUBSTITUTION')


def run(plan,tables,columns,frames,out,budget):
    import pyarrow as pa
    M,V,I,D,_=originals();I.check_allocation(False)
    target=out/'lists';target.mkdir(mode=0o700);db=I.connect(target/'authority.sqlite')
    config={'maximum_output_bytes':plan['output_cap_bytes'],'storage_budget':budget.legacy_quota(out)}
    I.quota_preflight(config,False)  # Original actual-quota/200GB gate unchanged.
    try:
        for kind,definition in M.SCHEMA.items():db.execute('CREATE TABLE '+kind+'('+definition+')')
        db.execute('CREATE TABLE atom_counts(geometry_id TEXT PRIMARY KEY,n_atoms INTEGER NOT NULL CHECK(n_atoms>0))')
        views=C.meta(plan['parent_references']['input_view_review'])
        workers=import_tables(db,tables,columns,frames,target,budget,{'feature_filter_column':views['feature_filter_column']});budget.check()
        V.validate(db)  # Original adapter distinguishes PM7/UFF physical keys.
        physical_map(db,plan,frames,budget)
        roles=C.meta(plan['parent_references']['roles_authority'])
        for role,expected in roles['roles'].items():
            C.need(I.scalar(db,'SELECT count(*) FROM roles WHERE effective_role=?',(role,))==expected['molecules'],'WHOLE_ROLE_SOURCE_CLOSURE')
        I.reject_rows(db,'SELECT g.geometry_id FROM geometries g WHERE g.parent_geometry_id IS NULL EXCEPT SELECT geometry_id FROM atom_counts','MISSING_BASE_NATIVE_ATOM_COUNTS')
        I.reject_rows(db,'SELECT geometry_id FROM atom_counts EXCEPT SELECT geometry_id FROM geometries WHERE parent_geometry_id IS NULL','EXTRA_BASE_NATIVE_ATOM_COUNTS')
        budget.check()
        counts=M.selection(db,plan['seed'],tuple(C.COUNTS['nested_TRAIN']),C.COUNTS['pilot_TRAIN'],C.COUNTS['pilot_ROUTINE_VAL'],C.COUNTS['diagnostic_TRAIN'])
        db.executescript('CREATE INDEX training_geom_mid ON training_geometry(molecule_id); CREATE INDEX training_order_mid ON training_orders(molecule_id); CREATE INDEX diagnostic_mid ON diagnostic_targets(molecule_id);')
        db.commit()
        budget.check()
        gs=pa.schema([(n,pa.int64() if n=='sprime_conf_idx' else pa.string()) for n in M.COLUMNS['geometries']]+[('effective_role',pa.string()),('source_role',pa.string())])
        ks=pa.schema([(n,pa.string()) for n in ('molecule_id','geometry_source','geometry_id')])
        ss=pa.schema([('subset',pa.string()),('molecule_id',pa.string()),('effective_role',pa.string()),('selection_rank',pa.int64())])
        oschema=pa.schema([(n,pa.int64() if n in ('rank','training_rank') else pa.string()) for n in M.COLUMNS['orders']+['training_rank']])
        q=lambda sql,name,schema,args=():R.parquet(db,sql,target/name,schema,budget,args)
        geometry=q('SELECT g.*,r.effective_role,r.source_role FROM geometries g JOIN roles r USING(molecule_id) ORDER BY g.geometry_id','geometry_map.parquet',gs)
        pref=plan['parent_references'];source_roles=roles['source_role_manifest']
        gm={'status':'CANONICAL_GEOMETRY_MAP_V1_FROZEN','map_tables':[geometry],'order_manifest':pref['order_manifest'],
            'common_population_manifest_sha256':pref['common_manifest']['sha256'],'roles_manifest_sha256':source_roles['sha256'],
            'roles_authority':pref['roles_authority'],'source_geometry_tables':tables['geometries'],'fixture':False}
        gmref=I.write_json(target/'geometry_map_manifest.json',gm)
        base=q('SELECT * FROM diagnostic_base ORDER BY molecule_id,geometry_source','diagnostic_base.parquet',ks)
        targets=q('SELECT * FROM diagnostic_targets ORDER BY molecule_id,geometry_source,geometry_id','diagnostic_targets.parquet',ks)
        dm={'status':'SEEN_MOLECULE_UNSEEN_GEOMETRY_DIAGNOSTIC_FROZEN','excluded_geometry_tables':[base],'target_exclusion_tables':[targets],
            'diagnostic_TRAIN_molecules':20000,'excluded_PM7_geometries':20000,'excluded_Sprime_geometries':20000,
            'all_excluded_geometries_materialized':True,'common_population_manifest_sha256':pref['common_manifest']['sha256'],
            'geometry_map_manifest_sha256':gmref['sha256'],'order_manifest_sha256':pref['order_manifest']['sha256'],
            'use':'pretraining-loss diagnostics only; never model selection','fixture':False}
        dmref=I.write_json(target/'diagnostic_manifest.json',dm)
        subsets={name:q('SELECT * FROM subset_members WHERE subset=? ORDER BY selection_rank',name+'.parquet',ss,(name,)) for name in counts}
        orders=q('SELECT * FROM training_orders ORDER BY molecule_id,geometry_source,order_type,training_rank','training_orders.parquet',oschema)
        training=q('SELECT g.*,r.effective_role,r.source_role FROM training_geometry g JOIN roles r USING(molecule_id) ORDER BY g.geometry_id','training_geometry.parquet',gs)
        atomref=q('SELECT * FROM atom_counts ORDER BY geometry_id','native_atom_counts.parquet',pa.schema([('geometry_id',pa.string()),('n_atoms',pa.int64())]))
        from wire_v1.store import file_ref
        result={'status':'D5_PARQUET_LISTS_FROZEN','fixture':False,'roles_authority':pref['roles_authority'],
            'common_population':pref['common_manifest'],'conformer_orders':pref['order_manifest'],'geometry_map':gmref,'diagnostic':dmref,
            'subsets':subsets,'training_orders':orders,'training_geometry':training,'seed':plan['seed'],
            'sampling_algorithm':'SHA256-uniform-order-v1; hash(seed,domain,molecule_id), tie=molecule_id','subset_counts':counts,
            'diagnostic_molecules':20000,'all_training_conditions_filter':'anti-join diagnostic target keys BEFORE first-k conformer selection',
            'database':file_ref(target/'authority.sqlite'),'input_workers':workers,'effective_worker_pids':sorted({r['pid'] for r in workers}),
            'original_normalize_validate_selection_objects':True,'native_atom_counts':atomref,'Root_joint_D5_acceptance':False}
    finally:db.close()
    result['database']=file_ref(target/'authority.sqlite')
    I.write_json(target/'manifest.json',result)
    # Sixteen finite original dimension tasks; no extra task is dispatched after
    # this already admitted call. Original frequency/zero-category SQL unchanged.
    budget.check();D.run(target/'manifest.json',out/'distributions',fixture=False);budget.check()
    artifacts={'d5_manifest':file_ref(target/'manifest.json'),'database':file_ref(target/'authority.sqlite'),
        'geometry_map_manifest':gmref,'diagnostic_manifest':dmref,'geometry_map':geometry,'diagnostic_base':base,'diagnostic_targets':targets,
        'training_orders':orders,'training_geometry':training,'native_atom_counts':atomref,
        'distributions_manifest':file_ref(out/'distributions/manifest.json'),
        'distributions_table':file_ref(out/'distributions/subset_distributions.parquet'),
        'distributions_database':file_ref(out/'distributions/distributions.sqlite')}
    artifacts.update({'subset_'+k:v for k,v in subsets.items()})
    return {'artifacts':{k:C.reference(v) for k,v in artifacts.items()},'subset_counts':counts,
        'actual_ingest_row_groups':len(workers),'effective_ingest_worker_pids':result['effective_worker_pids'],
        'ordinary_D5_only':True,'input_views_from_explicit_Root_column_map':True}
