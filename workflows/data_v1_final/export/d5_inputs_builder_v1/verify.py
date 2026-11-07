"""Adjacent-range merge and independent every-row/real-source order readback."""
from __future__ import annotations
import hashlib,json,pathlib,struct
from . import contract as C,io as I,geometry as G,reader as R,build as B
OBJECTS=None


def merge(plan,parents,out,budget):
    tables={};schemas=B.schemas()
    for kind,schema in schemas.items():
        def rows():
            for p in parents:yield from I.rows(p['table_references'][kind],plan['data_references'],budget.check)
        tables[kind]=I.parquet_rows(out/(kind+'.parquet'),rows(),schema,budget)
    return {'table_references':tables,'logical_range':plan['logical_range'],'molecules':sum(r['molecules'] for r in parents),
        'held_molecules':0,'table_domain':parents[0]['table_domain'],
        'all_actual_children_closed':all(r.get('all_actual_children_closed',False) for r in parents),
        'full_typed_source_order_identity_parity':False,'verified_parent_streams_concatenated_in_fixed_interval_order':True}


def source_order(work):
    global OBJECTS
    mid,bases,orders,control=work;I.worker_check(control)
    if OBJECTS is None:OBJECTS=G.originals(initialize=True)
    native,_,_=OBJECTS
    first=next(r for r in bases if r['geometry_source']=='pm7');pointer=json.loads(first['source_provenance_json'])
    mol,z,_=R.native_record(pointer,native)
    C.need(all(r['atomic_numbers']==z.tolist() for r in bases),'READBACK_ALL_NATIVE_ATOM_SEQUENCES')
    value=G.order_rows(mid,bases,mol,native,lambda:I.worker_check(control))
    from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import signature
    key=lambda r:(r['geometry_source'],r['order_type'],r['rank'])
    C.need(signature(sorted(value,key=key))==signature(sorted(orders,key=key)),'ALL_THREE_ORDERS_EXACT_ORIGINAL_OBJECT_READBACK')
    return {'molecules':1,'base_geometries':len(bases),'order_rows':len(value),'pid':__import__('os').getpid()}


def run(plan,parent,common,out,budget):
    import duckdb
    import pyarrow.parquet as pq
    from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import signature
    db=duckdb.connect(str(out/'verify.duckdb'));db.execute('SET threads=16');db.execute("SET memory_limit='3GB'")
    temp=out/'sql_tmp';temp.mkdir(exist_ok=True);db.execute('SET temp_directory='+quote(temp))
    declared=plan['data_references'];tables=parent['table_references'];schemas=B.schemas();frames={}
    try:
        for kind,ref in tables.items():
            with I.held(ref,declared,budget.check) as (path,_,frame):
                C.need(pq.read_schema(path).equals(schemas[kind],check_metadata=False),'EXACT_TYPED_INPUT_SCHEMA:'+kind);frames[ref['path']]=frame
            db.execute('CREATE TABLE '+kind+' AS SELECT * FROM read_parquet('+quote(ref['path'])+')')
        db.execute('CREATE INDEX geom_mid ON geometries(molecule_id)');db.execute('CREATE INDEX geom_gid ON geometries(geometry_id)')
        db.execute('CREATE INDEX order_mid ON orders(molecule_id)');db.execute('CREATE INDEX order_gid ON orders(geometry_id)')
        from workflows.data_v1_final.pprime.geometry import geometry_hash
        from workflows.data_v1_final.export.d5_materialize_cpu_v1.produce import originals
        M,_,_,_,_=originals()
        for row in I.rows(tables['geometries'],declared,budget.check):
            M.normalize('geometries',row);G.physical_key(row)
            C.need(row['geometry_sha256']==geometry_hash(row['atomic_numbers'],row['positions_A'])
                and row['atom_order_sha256']==hashlib.sha256(struct.pack('<'+'q'*len(row['atomic_numbers']),*row['atomic_numbers'])).hexdigest(),
                'EVERY_BASE_CHILD_F64_GEOMETRY_SHA_AND_NATIVE_ATOM_ORDER')
        for kind in ('geometries','atom_counts'):
            C.need(not db.execute('SELECT geometry_id FROM '+kind+' GROUP BY geometry_id HAVING count(*)<>1 LIMIT 1').fetchall(),'UNIQUE_TYPED_GEOMETRY_IDS:'+kind)
        C.need(not db.execute('SELECT molecule_id FROM roster GROUP BY molecule_id HAVING count(*)<>1 LIMIT 1').fetchall(),'ONE_WHOLE_MOLECULE_ROSTER_ROW')
        lo,hi=plan['logical_range'];n=db.execute('SELECT count(*),min(logical_ordinal),max(logical_ordinal),count(DISTINCT logical_ordinal) FROM roster').fetchone()
        C.need(n==(hi-lo,lo,hi-1,hi-lo),'ALL_FIXED_LOGICAL_ORDINALS_NO_DUP_GAP')
        C.need(not db.execute("SELECT 1 FROM orders WHERE method<>order_type OR method NOT IN ('fixed_random','energy','diversity') OR rank<0 LIMIT 1").fetchall(),'EXACT_METHOD_ORDER_TYPE_ZERO_BASED_DUAL_COLUMNS')
        C.need(not db.execute('SELECT 1 FROM orders GROUP BY molecule_id,geometry_source,order_type HAVING min(rank)<>0 OR max(rank)+1<>count(*) OR count(*)<>count(DISTINCT geometry_id) LIMIT 1').fetchall(),'THREE_TRUE_CONTIGUOUS_PERMUTATIONS')
        C.need(not db.execute('SELECT 1 FROM orders o LEFT JOIN geometries g USING(geometry_id) WHERE g.geometry_id IS NULL OR g.parent_geometry_id IS NOT NULL OR o.molecule_id<>g.molecule_id OR o.geometry_source<>g.geometry_source LIMIT 1').fetchall(),'ORDERS_BOUND_TO_ACTUAL_ORDINARY_BASES')
        C.need(not db.execute('SELECT geometry_id FROM geometries WHERE parent_geometry_id IS NULL EXCEPT SELECT geometry_id FROM atom_counts').fetchall()
            and not db.execute('SELECT geometry_id FROM atom_counts EXCEPT SELECT geometry_id FROM geometries WHERE parent_geometry_id IS NULL').fetchall(),'EXACT_BASE_ATOM_COUNTS_DOMAIN')
        C.need(not db.execute('SELECT 1 FROM geometries g JOIN atom_counts a USING(geometry_id) WHERE array_length(g.atomic_numbers)<>a.n_atoms OR array_length(g.positions_A)<>a.n_atoms OR a.n_atoms<=0 LIMIT 1').fetchall(),'REAL_NATIVE_ATOM_COUNTS_NOT_ELEMENT_SETS')
        physical=[]
        for ref in common['physical_geometry_tables']:
            with I.held(ref,declared,budget.check):pass
            physical.append(ref)
        db.execute('CREATE VIEW physical AS SELECT * FROM read_parquet(['+','.join(quote(r['path']) for r in physical)+'],union_by_name=true)')
        key="geometry_id,molecule_id,geometry_source,CASE WHEN geometry_source='pm7' THEN native_record_id END AS native_record_id,sprime_conf_idx"
        actual='SELECT '+key+' FROM geometries WHERE parent_geometry_id IS NULL'
        expected='SELECT '+key+' FROM physical JOIN roster USING(molecule_id)'
        C.need(not db.execute(actual+' EXCEPT '+expected).fetchall() and not db.execute(expected+' EXCEPT '+actual).fetchall(),'EXACT_BIDIRECTIONAL_FINAL_COMMON_BASE_PHYSICAL_MAP')
        C.need(not db.execute("SELECT 1 FROM geometries c LEFT JOIN geometries p ON c.parent_geometry_id=p.geometry_id WHERE c.parent_geometry_id IS NOT NULL AND (p.geometry_id IS NULL OR p.parent_geometry_id IS NOT NULL OR c.molecule_id<>p.molecule_id OR c.geometry_source<>p.geometry_source OR (c.geometry_source='pm7' AND c.native_record_id<>p.native_record_id) OR (c.geometry_source='uff_sprime' AND c.sprime_conf_idx<>p.sprime_conf_idx) OR c.view_id='pprime_parent_expanded_v1') LIMIT 1").fetchall(),'ALL_ACTUAL_DIRECT_CHILDREN_SAME_SOURCE_PHYSICAL_PARENT')
        packets=parent.get('worker_packet_references',[])
        for ref in packets:
            value=B.decode(I.body(ref,declared,budget.check,I.ROW_CAP))
            C.need(value['status']=='COMPLETE_BASE_AND_ORIGINAL_ORDERS','EVERY_ORIGINAL_WORKER_PACKET_COMPLETE')
            for kind,original in (('geometries',value['bases']),('orders',value['orders']),('atom_counts',value['atom_counts']),('audit_identity',value['audit_identity'])):
                for row in original:
                    query='SELECT * FROM '+kind+' WHERE geometry_id=?'
                    args=[row['geometry_id']]
                    if kind=='orders':query+=' AND order_type=?';args.append(row['order_type'])
                    found=db.execute(query,args).fetch_arrow_table().to_pylist();expected_row={k:row.get(k) for k in schemas[kind].names}
                    C.need(len(found)==1 and signature(found[0])==signature(expected_row),'EVERY_TYPED_ROW_EXACT_SOURCE_PACKET_BITS_AND_TYPES')
        wanted=db.cursor();wanted.execute('SELECT molecule_id FROM roster ORDER BY logical_ordinal')
        workers=base_count=order_count=0;pids=set()
        def work():
            while True:
                batch=wanted.fetchmany(16)
                if not batch:break
                for (mid,) in batch:
                    budget.check()
                    bases=db.execute('SELECT * FROM geometries WHERE molecule_id=? AND parent_geometry_id IS NULL ORDER BY geometry_id',[mid]).fetch_arrow_table().to_pylist()
                    orders=db.execute('SELECT * FROM orders WHERE molecule_id=?',[mid]).fetch_arrow_table().to_pylist()
                    yield mid,bases,orders,budget.control
        for row in I.R.ordered_map(source_order,work(),budget):
            workers+=1;base_count+=row['base_geometries'];order_count+=row['order_rows'];pids.add(row['pid'])
        C.need(workers==hi-lo,'EVERY_MOLECULE_ORIGINAL_ORDER_READBACK')
        full_total=sum(r['molecules'] for r in common['roles'])
        full=lo==0 and hi==full_total
        if full:
            refs=common['membership_tables']
            for ref in refs:
                with I.held(ref,declared,budget.check):pass
            db.execute('CREATE VIEW members AS SELECT * FROM read_parquet(['+','.join(quote(r['path']) for r in refs)+'])')
            C.need(not db.execute('SELECT molecule_id FROM members WHERE common_population EXCEPT SELECT molecule_id FROM roster').fetchall()
                and not db.execute('SELECT molecule_id FROM roster EXCEPT SELECT molecule_id FROM members WHERE common_population').fetchall(),'FULL_TRUE_COMMON_MOLECULE_COVERAGE_NOT_PROFILE')
        for ref in tables.values():C.need(I.R.frame(pathlib.Path(ref['path']).lstat())==frames[ref['path']],'INPUT_TYPED_TABLE_FRAME_STABLE_AFTER_FULL_READBACK')
        # The source tables remain in their original producer directories; the
        # verification receipt points to them, without cloning scientific rows.
        return {'table_references':tables,'logical_range':[lo,hi],'molecules':hi-lo,'held_molecules':0,
            'table_domain':parent['table_domain'],'all_actual_children_closed':parent.get('all_actual_children_closed',False),
            'full_typed_source_order_identity_parity':True,'whole_true_Common_coverage_verified':full,
            'ordinary_base_geometries':base_count,'actual_original_order_rows_rechecked':order_count,
            'effective_order_readback_pids':sorted(pids),'native_record_readback_per_molecule':1,
            'WHOLE_LMDB_SHA_NOT_ORIGINALLY_AVAILABLE_NOT_CLAIMED':True}
    finally:db.close()


def quote(value):return "'"+str(value).replace("'","''")+"'"
