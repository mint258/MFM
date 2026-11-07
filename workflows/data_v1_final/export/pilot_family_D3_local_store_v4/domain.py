"""Actual pilot roles, three base orders and heldout/real-child anti-join."""
import collections,json,pathlib
from . import contract as C,io as I
from workflows.data_v1_final.export.family_export_day_v1 import project as P
from workflows.data_v1_final.conformers.pm7_independent_cache32_v1 import core as NativeOrders
def register(ref,roots):
    r=C.reference(ref)
    if r['path'] in I.B.ALLOWED:return r
    root=next((v for v in roots if pathlib.Path(v) in pathlib.Path(r['path']).parents),None)
    C.need(root is not None,'TRANSITIVE_REF_UNDER_EXACT_ROOT_REVIEWED_CLOSED_ORIGIN');I.add(r,root);return r
def read(ref,roots,limit=512<<20):return I.load_data(register(ref,roots),limit)
def row_stream(ref,roots,check):
    register(ref,roots)
    for batch in I.batches(ref,check):yield from batch.to_pylist()
def order_check(ids,rows):
    C.need(len(ids)==len(set(ids)),'UNIQUE_NATIVE_BASE_PHYSICAL_IDS')
    for kind in ('fixed_random','energy','diversity'):
        ordered=sorted((r for r in rows if r['order_type']==kind),key=lambda r:r['rank'])
        C.need([r['rank'] for r in ordered]==list(range(len(ids))) and len(ordered)==len(ids)
          and {r['geometry_id'] for r in ordered}==set(ids),'ALL_THREE_ZERO_BASED_BASE_ONLY_PERMUTATIONS')
def native_order_check(mid,source,bases,rows):
    C.need(source in ('pm7','uff_sprime') and bases,'ACTUAL_NATIVE_BASE_DOMAIN_NOT_EMPTY')
    ids={}
    for row in bases:
        key=row['native_record_id'] if source=='pm7' else row['sprime_conf_idx']
        C.need((type(key)is str and key) if source=='pm7' else (type(key)is int and key>=0),'ORIGINAL_NATIVE_RID_OR_SPRIME_INT64_ID_NOT_RENUMBERED')
        C.need(key not in ids and row['geometry_id'] not in ids.values(),'UNIQUE_NATIVE_PHYSICAL_IDS_AND_GEOMETRIES');ids[key]=row['geometry_id']
    def no_distance(*args):raise AssertionError('NO_HOF_OR_RMSD_IN_FIXED_RANDOM_ORDER_IO_VERIFICATION')
    expected=NativeOrders.geometry_orders([{'conformer_id':k,'energy':None} for k in ids],no_distance,mid,source)
    C.need(expected['energy'] is None and expected['diversity'] is None and all(r['order_type']=='fixed_random' for r in rows)
      and all(type(r['rank'])is int for r in rows),'ONLY_EXACT_AVAILABLE_FIXED_RANDOM_NOT_FAKE_ENERGY_OR_DIVERSITY')
    ordered=sorted(rows,key=lambda r:r['rank'])
    C.need([r['rank'] for r in ordered]==list(range(len(ids)))
      and [r['geometry_id'] for r in ordered]==[ids[k] for k in expected['fixed_random']],
      'EXACT_ORIGINAL_SEED20261025_NATIVE_ID_FIXED_RANDOM_RANKS_ALL_BASES')
def build(plan,old,accepted,root,budget):
    review=C.meta(plan['bounded_export_review_reference']);roots=review['transitive_closed_output_roots'];components=accepted['component_references']
    population=read(components['population_reference'],roots);pre=read(population['preselection_reference'],roots)
    native=C.native_mode(plan)
    if native:C.need(population['status']=='ACTUAL_SAME_PARENT_NATIVE_GEOMETRY_ROLE_RANDOM_ORDER_CLOSED_PENDING_ROOT_NOT_FINAL_COMMON'
      and population['available_orders']==['fixed_random'] and population['full_three_order'] is False and population['D7'] is False,
      'ACTUAL_NATIVE_POPULATION_NOT_THREE_ORDER_OR_D7_ACCEPTANCE')
    C.need(population['pilot_counts']==C.COUNTS and pre['pilot_counts']==C.COUNTS and pre['seed']==20261025 and pre['final_Common'] is False
      and pre['pilot_ready_scalar_only'] is True,'ACTUAL_FIXED55K_PRESELECTION_NOT_FINAL_COMMON')
    C.need(pre['roles_authority_reference'] in plan['source_references'],'ORIGINAL_ROLE_AUTHORITY_FROM_EXACT_PREFIX_SOURCE_CHAIN')
    roles=C.meta(pre['roles_authority_reference']);role_source=C.meta(roles['source_role_manifest'])
    C.need(roles['status']=='FROZEN' and roles['validation_source']=='ROUTINE' and roles['all_conformers_same_role'] is True
      and role_source['status']=='ROUTINE_MOLECULE_VAL_ROLES_FROZEN','TRUE_WHOLE_MOLECULE_ROUTINE_VAL_AUTHORITY')
    selected={r['molecule_id']:r for r in row_stream(pre['tables']['pilot55k'],roots,budget.check)}
    C.need(len(selected)==55000 and collections.Counter(r['effective_role'] for r in selected.values())==C.COUNTS,'EXACT50000_TRAIN_5000_ROUTINE_VAL_MIDS')
    db=I.connect(root/'domain.sqlite');db.executescript('CREATE TABLE molecules(mid TEXT PRIMARY KEY,role TEXT,source_role TEXT,N INTEGER,row TEXT);'
      'CREATE TABLE geometries(gid TEXT PRIMARY KEY,mid TEXT,src TEXT,parent TEXT,view TEXT,selected INTEGER,aux INTEGER,row BLOB);'
      'CREATE INDEX geom_mid ON geometries(mid,src);CREATE TABLE orders(mid TEXT,src TEXT,kind TEXT,rank INTEGER,gid TEXT,PRIMARY KEY(mid,src,kind,rank));'
      'CREATE TABLE excluded(gid TEXT PRIMARY KEY);CREATE TABLE native_bases(rid TEXT PRIMARY KEY,gid TEXT UNIQUE);CREATE TABLE pieces(gid TEXT,part TEXT,n INTEGER,payload BLOB,source_locator TEXT,PRIMARY KEY(gid,part));'
      'CREATE TABLE closed_groups(key TEXT PRIMARY KEY,ref TEXT);CREATE TABLE exported(store TEXT,gid TEXT,kind TEXT,parts TEXT,PRIMARY KEY(store,gid));'
      'CREATE TABLE stores(name TEXT PRIMARY KEY,path TEXT,ref TEXT);')
    for row in row_stream(pre['tables']['complete_old_mother'],roots,budget.check):
        mid=row['molecule_id']
        if mid not in selected:continue
        C.need(row['effective_role']==selected[mid]['effective_role'] and row['selection_rank']==selected[mid]['selection_rank']
          and row['scalar_complete_old_Sprime'] is True and type(row['S_conformers']) is int and row['S_conformers']>0
          and row['Sprime_conformers']==row['S_conformers'],'ACTUAL_OLD_COMPLETE_N_UNCHANGED')
        C.need(type(row['source_role']) is str and row['source_role'],'OPAQUE_ORIGINAL_SOURCE_ROLE_PRESERVED_NOT_REWRITTEN_AS_VAL')
        db.execute('INSERT INTO molecules VALUES(?,?,?,?,?)',(mid,row['effective_role'],row['source_role'],row['S_conformers'],json.dumps(row,sort_keys=True)))
    C.need(db.execute('SELECT count(*) FROM molecules').fetchone()[0]==55000,'NO_DUPLICATE_OR_MISSING_MID_IN_FULL_MOTHER_JOIN')
    g=read(components['geometry_reference'],roots);C.need(g['all_in_scope_actual_direct_children_bound'] is True and g['unknown_input_bindings']==0,'ACTUAL_GEOMETRY_CHILD_INPUT_BINDING_CLOSED')
    if native:C.need(g['schema']=='PROVISIONAL_NATIVE55K_FIXED_RANDOM_BASE_GEOMETRIES_V1' and g['available_orders']==['fixed_random']
      and g['full_three_order'] is False and g['D7'] is False and g['PM7_HOF_RMSD_cache_required'] is False,
      'EXACT_NATIVE_GEOMETRY_ORDER_CAPABILITY_NOT_A_HOF_CACHE_OR_FULL_D7')
    from workflows.data_v1_final.export.lossless_sqlite_io_v1 import codec as W
    for aux,ref in ((0,g['table_references']['geometries']),(1,g['actual_program_input_view_reference'])):
        for row in row_stream(ref,roots,budget.check):
            C.need(row['molecule_id'] in selected and row['geometry_source'] in ('pm7','uff_sprime'),'ONLY_ACTUAL55K_GEOMETRY_SOURCE')
            # The producer's original f64/atom-order hash object, not a task-name join.
            from workflows.data_v1_final.pprime.geometry import geometry_hash
            C.need(geometry_hash(row['atomic_numbers'],row['positions_A'])==row['geometry_sha256'],'ACTUAL_F64_GEOMETRY_HASH')
            import hashlib,struct
            C.need(hashlib.sha256(b''.join(struct.pack('<q',z) for z in row['atomic_numbers'])).hexdigest()==row['atom_order_sha256'],'ACTUAL_ORIGINAL_ATOM_SEQUENCE_HASH')
            db.execute('INSERT INTO geometries VALUES(?,?,?,?,?,?,?,?)',(row['geometry_id'],row['molecule_id'],row['geometry_source'],row['parent_geometry_id'],row['view_id'],1,aux,W.encode(row)))
            if row['geometry_source']=='pm7' and row['parent_geometry_id'] is None:db.execute('INSERT INTO native_bases VALUES(?,?)',(row['native_record_id'],row['geometry_id']))
    for row in row_stream(g['diagnostic_target_reference'],roots,budget.check):db.execute('INSERT INTO excluded VALUES(?)',(row['geometry_id'],))
    db.execute("UPDATE geometries SET selected=0 WHERE gid IN(SELECT gid FROM excluded) AND mid IN(SELECT mid FROM molecules WHERE role='TRAIN')")
    for row in row_stream(g['table_references']['orders'],roots,budget.check):
        if native:
            found=db.execute('SELECT mid,src,parent,aux FROM geometries WHERE gid=?',(row['geometry_id'],)).fetchone()
            C.need(found is not None and tuple(found)==(row['molecule_id'],row['geometry_source'],None,0)
              and row['molecule_id'] in selected and row['order_type']=='fixed_random','NATIVE_ORDERS_ONLY_OWN_MID_SOURCE_ORDINARY_BASES_NOT_CHILDREN')
        db.execute('INSERT INTO orders VALUES(?,?,?,?,?)',(row['molecule_id'],row['geometry_source'],row['order_type'],row['rank'],row['geometry_id']))
    for mid,role,n in db.execute('SELECT mid,role,N FROM molecules'):
        for src in ('pm7','uff_sprime'):
            ids=[r[0] for r in db.execute('SELECT gid FROM geometries WHERE mid=? AND src=? AND parent IS NULL AND aux=0',(mid,src))]
            C.need(len(ids)==n,'ORDINARY_N_NOT_INFLATED_BY_CHILD_OR_INPUT_VIEW');orders=[{'order_type':r[0],'rank':r[1],'geometry_id':r[2]} for r in db.execute('SELECT kind,rank,gid FROM orders WHERE mid=? AND src=?',(mid,src))]
            if native:native_order_check(mid,src,[W.decode(r[0]) for r in db.execute('SELECT row FROM geometries WHERE mid=? AND src=? AND parent IS NULL AND aux=0',(mid,src))],orders)
            else:order_check(ids,orders)
    def forbidden(gid):return db.execute('SELECT 1 FROM excluded WHERE gid=?',(gid,)).fetchone() is not None
    def parent(gid):
        row=db.execute('SELECT parent FROM geometries WHERE gid=?',(gid,)).fetchone();return row is not None,row[0] if row else None
    P.assert_diagnostic_lineage(({'geometry_id':r[0],'parent_geometry_id':r[1]} for r in db.execute("SELECT gid,parent FROM geometries WHERE selected=1 AND mid IN(SELECT mid FROM molecules WHERE role='TRAIN')")),forbidden,parent,budget.check)
    C.need(db.execute('SELECT count(*) FROM molecules WHERE mid NOT IN(SELECT mid FROM geometries WHERE selected=1)').fetchone()[0]==0,'NO_COHORT_MID_DROPPED_BY_SOURCE_OR_ROLE_JOIN')
    db.commit();binding=register(g['cell_binding_reference'],roots);I.require(binding)
    return db,g,binding,roots
