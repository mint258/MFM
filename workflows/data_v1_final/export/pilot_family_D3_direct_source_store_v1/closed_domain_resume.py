"""Direct closed-D4 row reuse with a narrow index; no geometry re-generation."""
import collections,json,pathlib,sqlite3
from . import contract as C,domain as D,io as I,source as X,payload_io,runtime_budget
from workflows.data_v1_final.export.pilot_D5_parallel_guide_v1 import resource as R
CONFIG_KEYS=('registry_reference','mapping_reference','projection_recipe_reference','target_policy_reference')
CACHE_KIB=2*1024*1024
def enabled(plan):return True

def reviews(plan,accepted):
    bounded=C.meta(plan['bounded_export_review_reference'])
    marker_ref=bounded['closed_configuration_marker_reference'];marker=C.meta(marker_ref)
    header_ref=bounded['configuration_header_reference'];header=C.meta(header_ref)
    configs=marker['actual_configuration_references'];producer=plan['configuration_component_producer_job_id']
    C.need(bounded['configuration_mode']=='PREEXISTING_EXACT_CONFIGURATIONS'
      and producer==marker['actual_D3_job_id']=='4525587'
      and marker['all_configuration_files_closed_and_hashed']is True
      and marker['actual_D4_acceptance_reference']==plan['pilot_acceptance_reference']
      and marker['pilot_counts']==C.COUNTS and configs['configuration_header_reference']==header_ref
      and all(bounded[k]==configs[k]==header[k]for k in CONFIG_KEYS)
      and bounded['original_series_size_rho_reference']==marker['actual_original_series_size_rho_reference']
      ==header['actual_original_series_size_rho_reference'],
      'EXACT_ALREADY_CLOSED55K_CONFIGURATIONS_NO_OLD_DOMAIN_OR_PARENT_C0_GATE')
    config=dict(configuration_component_producer_job_id=producer,original_series_size_rho_reference=bounded['original_series_size_rho_reference'])
    return config,None,[marker_ref,header_ref],C.unique([*(configs[k]for k in CONFIG_KEYS),config['original_series_size_rho_reference']])

def batches(reference,roots,budget,columns=None):
    import pyarrow.parquet as pq
    D.register(reference,roots);path=I.require(reference,content=False);before=I.identity(path)
    with path.open('rb')as stream:
        source=pq.ParquetFile(stream,pre_buffer=False)
        try:
            for batch in source.iter_batches(batch_size=8192,columns=columns,use_threads=False):
                budget.check();yield batch.to_pylist()
        finally:source.close()
    C.need(I.identity(path)==before,'CLOSED_D4_NARROW_SOURCE_FRAME_UNCHANGED')

def configure_views(db,index_path,geometry_path):
    main=pathlib.Path(db.execute('PRAGMA database_list').fetchone()[2])
    if main==pathlib.Path(index_path):index='main'
    else:
        db.execute('ATTACH DATABASE ? AS geo_index',(pathlib.Path(index_path).as_uri()+'?mode=ro&immutable=1',));index='geo_index'
        db.execute('PRAGMA main.cache_size=-1572864');db.execute('PRAGMA geo_index.cache_size=-458752')
    db.execute('ATTACH DATABASE ? AS raw_geo',(pathlib.Path(geometry_path).as_uri()+'?mode=ro&immutable=1',))
    db.execute('PRAGMA raw_geo.cache_size=-65536')
    def payload(origin,gid):
        C.need(origin in ('base','children','input_views'),'EXACT_D4_GEOMETRY_TABLE')
        row=db.execute('SELECT row FROM raw_geo.'+origin+' WHERE gid=?',(gid,)).fetchone()
        C.need(row is not None,'D4_GEOMETRY_ROW_EXISTS');return row[0]
    db.create_function('d4_payload',2,payload)
    db.execute('CREATE TEMP VIEW geometries AS SELECT gid,mid,src,parent,view,selected,aux,d4_payload(origin,gid) AS row FROM '+index+'.geometries_index')
    for table in ('molecules','orders','excluded'):db.execute('CREATE TEMP VIEW '+table+' AS SELECT * FROM '+index+'.'+table)
    db.execute("CREATE TEMP VIEW native_bases AS SELECT rid,gid FROM raw_geo.base WHERE src='pm7'")
    return db

def connect_source(path,readonly=False):
    if readonly and str(path)==X.CTX.get('domain_database'):
        db=sqlite3.connect(pathlib.Path(path).as_uri()+'?mode=ro&immutable=1',uri=True)
        db.row_factory=sqlite3.Row;db.execute('PRAGMA cache_size=-65536')
        return configure_views(db,path,X.CTX['D4_geometry_database'])
    return I.connect(path,readonly)

def one(work):
    def connect(path,readonly=False):
        db=connect_source(path,readonly)
        return payload_io.stage_connection(db)if not readonly and str(path)==str(work[2])else db
    private_io=R.ObjectProxy(I,connect=connect,F=R.ObjectProxy(I.F,worker_check=runtime_budget.worker_check))
    return R.clone(X.one,I=private_io,CTX=X.CTX,S=payload_io.stage_source())(work)

def open_domain(plan,accepted,root,budget):
    config,_,_,_=reviews(plan,accepted);bounded=C.meta(plan['bounded_export_review_reference'])
    roots=bounded['transitive_closed_output_roots'];components=accepted['component_references']
    geometry=D.read(components['geometry_reference'],roots)
    binding=D.register(geometry['cell_binding_reference'],roots);geometry_path=str(I.require(binding,content=False))
    prefix=D.read(components['prefix_reference'],roots)
    index_path=pathlib.Path(root)/'geometry_index.sqlite';C.need(not index_path.exists(),'FRESH_NARROW_D4_INDEX')
    narrow=sqlite3.connect(index_path);narrow.execute('PRAGMA cache_size=-'+str(CACHE_KIB))
    narrow.executescript('CREATE TABLE molecules(mid TEXT PRIMARY KEY,role TEXT,source_role TEXT,N INTEGER,row TEXT);'
      'CREATE TABLE geometries_index(gid TEXT PRIMARY KEY,mid TEXT,src TEXT,parent TEXT,view TEXT,selected INTEGER,aux INTEGER,origin TEXT);'
      'CREATE TABLE excluded(gid TEXT PRIMARY KEY);'
      'CREATE TABLE orders(mid TEXT,src TEXT,kind TEXT,rank INTEGER,gid TEXT,PRIMARY KEY(mid,src,kind,rank));')
    try:
        members={}
        for rows in batches(prefix['members_reference'],roots,budget):
            for row in rows:members[row['molecule_id']]=row
        C.need(len(members)==55000 and collections.Counter(r['effective_role']for r in members.values())==C.COUNTS,
          'SAME_FROZEN50K_TRAIN5K_ROUTINE_VAL')
        narrow.executemany('INSERT INTO molecules VALUES(?,?,?,?,?)',[(mid,r['effective_role'],r['source_role'],r['S_conformers'],json.dumps(r,sort_keys=True))for mid,r in members.items()])
        excluded=set()
        for rows in batches(geometry['diagnostic_target_reference'],roots,budget,columns=['geometry_id']):excluded.update(r['geometry_id']for r in rows)
        narrow.executemany('INSERT INTO excluded VALUES(?)',((gid,)for gid in excluded))
        columns=['geometry_id','molecule_id','geometry_source','parent_geometry_id','view_id']
        for aux,reference in ((0,geometry['table_references']['geometries']),(1,geometry['actual_program_input_view_reference'])):
            for rows in batches(reference,roots,budget,columns=columns):
                values=[]
                for row in rows:
                    mid=row['molecule_id'];gid=row['geometry_id'];C.need(mid in members,'ONLY_FROZEN_PILOT_MIDS')
                    origin='input_views'if aux else 'base'if row['parent_geometry_id']is None else 'children'
                    selected=int(not(gid in excluded and members[mid]['effective_role']=='TRAIN'))
                    values.append((gid,mid,row['geometry_source'],row['parent_geometry_id'],row['view_id'],selected,aux,origin))
                narrow.executemany('INSERT INTO geometries_index VALUES(?,?,?,?,?,?,?,?)',values)
        for rows in batches(geometry['table_references']['orders'],roots,budget):
            narrow.executemany('INSERT INTO orders VALUES(?,?,?,?,?)',[(r['molecule_id'],r['geometry_source'],r['order_type'],r['rank'],r['geometry_id'])for r in rows])
        narrow.executescript('CREATE INDEX geom_mid_selected ON geometries_index(mid,selected,gid);CREATE INDEX orders_gid_cover ON orders(gid,kind,rank);')
        narrow.commit()
    finally:narrow.close()
    index_reference=I.pin(index_path);I.add(index_reference)
    destination=pathlib.Path(root)/'domain.sqlite';C.need(not destination.exists(),'FRESH_MUTABLE_LABEL_DOMAIN')
    db=sqlite3.connect(destination.as_uri()+'?mode=rwc',uri=True);db.row_factory=sqlite3.Row
    db.execute('PRAGMA auto_vacuum=INCREMENTAL')
    db.execute('PRAGMA cache_size=-'+str(CACHE_KIB));db.execute('PRAGMA synchronous=FULL')
    configure_views(db,str(index_path),geometry_path)
    db.executescript('CREATE TABLE pieces(gid TEXT,part TEXT,n INTEGER,payload BLOB,source_locator TEXT,PRIMARY KEY(gid,part));'
      'CREATE TABLE closed_groups(key TEXT PRIMARY KEY,ref TEXT);'
      'CREATE TABLE exported(store TEXT,gid TEXT,kind TEXT,parts TEXT,PRIMARY KEY(store,gid));'
      'CREATE TABLE stores(name TEXT PRIMARY KEY,path TEXT,ref TEXT);')
    db.commit()
    return db,geometry,binding,roots,str(index_path),config['original_series_size_rho_reference'],geometry_path
