"""CPU full canonical input-hash projection; original renderer, no QM or UUID fiction."""
from __future__ import annotations
import hashlib,json,pathlib,sqlite3
from workflows.data_v1_final.export.d5_inputs_builder_v1 import io as I,children as H,geometry as G
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import classify_owner
from . import contract as C,core as B
COLUMNS=('record_id','molecule_id','calc_type','total_atoms','attempt_id','job_id','task_id','lane',
    'input_file_sha256','input_bundle_sha256','raw_output_locator_json','reproduction_package_sha256','status','source_status')


def canonical_occurrence(source,row_index,row):
    C.need(type(row_index) is int and row_index>=0,'ACTUAL_SOURCE_ROW_OCCURRENCE_NOT_NEW_EXECUTION_UUID')
    value={'source_reference':C.reference(source),'physical_row_index':row_index,
        **{k:row[k] for k in ('record_id','molecule_id','calc_type','attempt_id','job_id','task_id','lane','input_bundle_sha256')}}
    wire=json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
    return 'canonical-source-occurrence:'+hashlib.sha256(wire).hexdigest(),value


def child(row,base,source,index,protocol,objects):
    engine,legacy,archive,_=objects;engine.load_protocol(protocol)
    recipe=next(t for t in protocol['tasks'] if t['name']==row['calc_type']);C.need(recipe.get('perturbed') is True,'ONLY_ACTUAL_PERTURBED_CANONICAL_TASK')
    C.need(row['record_id']==base['native_record_id'] and row['molecule_id']==base['molecule_id']
        and row['total_atoms']==len(base['atomic_numbers']),'SAME_ORIGINAL_NATIVE_RECORD_AND_ATOM_ORDER')
    from rdkit import Chem
    symbols=[Chem.GetPeriodicTable().GetElementSymbol(z) for z in base['atomic_numbers']]
    rendered=engine.render_inputs(recipe,{'symbols':symbols,'coords':base['positions_A']},{'record_id':row['record_id']},protocol)
    H.O.input_binding(rendered,row['input_file_sha256'],row['input_bundle_sha256'],archive.bundle)
    name='input.mop' if recipe['family']=='mopac' else 'input.xyz'
    coords=H.O.input_coordinates(rendered[name],name,symbols,legacy.f)
    C.need(H.O.equal_numbers(coords,H.O.input_coordinates(rendered['input.xyz'],'input.xyz',symbols,legacy.f)),'EXACT_PROGRAM_AND_XYZ_INPUT_COORDINATES')
    occurrence,identity=canonical_occurrence(source,index,row);uuid=None
    if row.get('raw_output_locator_json') is not None:
        raw=json.loads(row['raw_output_locator_json']);C.need(type(raw) is dict,'ORIGINAL_RAW_LOCATOR_JSON_OBJECT')
        if raw.get('execution_id') is not None:
            C.need(raw.get('record_id')==row['record_id'] and raw.get('calc_type')==row['calc_type'] and type(raw['execution_id']) is str
                and raw['execution_id'],'ORIGINAL_UUID_ONLY_FROM_EXACT_STORED_RAW_LOCATOR');uuid=raw['execution_id']
    # Original child identity function is called with a truthful new provenance
    # domain when the old UUID was not retained. record_id/seed never change.
    execution=uuid if uuid is not None else occurrence
    gid,view=G.child_identity(base,row['record_id'],row['calc_type'],execution,row['input_bundle_sha256'])
    from workflows.data_v1_final.pprime.geometry import geometry_hash
    value=dict(base,geometry_id=gid,parent_geometry_id=base['geometry_id'],view_id=view,positions_A=coords,order_energy=None,
        geometry_sha256=geometry_hash(base['atomic_numbers'],coords),actual_input_bundle_sha256=row['input_bundle_sha256'],
        actual_input_origin='HASH_RECONSTRUCTED_CANONICAL_PROGRAM_INPUT_EXACT_NOT_SAVED_BODY',
        source_provenance_json=json.dumps({'canonical_source_occurrence':identity,'original_execution_uuid':uuid,
            'original_execution_uuid_state':'ACTUAL_STORED_RAW_LOCATOR' if uuid else 'UNKNOWN_NOT_RETAINED',
            'identity_domain':'actual_original_execution' if uuid else 'canonical-source-occurrence',
            'original_input_file_sha256':row['input_file_sha256'],'source_status':row['source_status'],
            'actual_status_not_used_as_geometry_filter':True,'perturb_seed':engine.perturb_seed(row['record_id'],protocol)},sort_keys=True))
    C.need(G.physical_key(value)==G.physical_key(base),'KEEP_ORIGINAL_BASE_PHYSICAL_SOURCE_AND_NATIVE_ID')
    return value,uuid is None


OBJECTS=None


def worker(work):
    global OBJECTS
    row,base,source,index,protocol,pref,control=work;I.worker_check(control)
    if OBJECTS is None:OBJECTS=H.sources()
    try:
        result,unknown_uuid=child(row,base,source,index,protocol,OBJECTS);result['actual_protocol_sha256']=pref['sha256']
        return {'record_id':row['record_id'],'task':row['calc_type'],'result':result,'unknown_uuid':unknown_uuid}
    except Exception as exc:
        return {'record_id':row['record_id'],'task':row['calc_type'],'error':{'source_reference':C.reference(source),
            'physical_row_index':index,'reason_type':type(exc).__name__,'reason':str(exc),'input_hashes_or_binding_unknown_not_a_new_geometry':True}}


def run(plan,parent,prepared_db,out,budget,authority,pool):
    import duckdb
    from workflows.data_v1_final.export.d5_inputs_builder_v1.prepare import Dquote
    root=C.meta(plan['WP5_input_derivation_authority_reference']);hof=C.meta(plan['hof_authority_reference']);projection=C.meta(hof['projection_receipt_reference'])
    files=I.json_body(projection['source_files'],authority,budget.check);objects=H.sources();protocols={};families=set()
    for r in root['package_protocol_references']:
        pkg=C.meta(r['package_reference']);protocol=C.meta(r['protocol_reference']);objects[0].load_protocol(protocol)
        C.need(pkg['protocol']['path']==r['protocol_reference']['path'] and pkg['protocol']['sha256']==r['protocol_reference']['sha256'],'ACTUAL_REPRO_PACKAGE_PROTOCOL_LITERAL')
        selected={t['name'] for t in protocol['tasks'] if t.get('perturbed') is True}
        C.need(selected==set(root['expected_perturbed_tasks']),'EXACT_ORIGINAL_PERTURBED_TASK_SET_NOT_GUESSED_METHOD')
        protocols[r['package_reference']['sha256']]=(protocol,r['protocol_reference'])
        families.update(root['task_family_map'][t] for t in selected)
    db=sqlite3.connect(out/'canonical_children.sqlite');db.execute('CREATE TABLE bases(rid TEXT PRIMARY KEY,mid TEXT,src TEXT,value BLOB)')
    db.execute('CREATE INDEX base_mid ON bases(mid)');db.execute('CREATE TABLE children(parent TEXT,gid TEXT UNIQUE,value BLOB)')
    db.execute('CREATE INDEX child_parent ON children(parent)');db.execute('CREATE TABLE seen(rid TEXT,task TEXT,PRIMARY KEY(rid,task))')
    db.execute('CREATE TABLE unknown(rid TEXT,task TEXT,value BLOB)')
    ownerdb=duckdb.connect(prepared_db['path'],read_only=True);count=unknown_uuid=0
    try:
        for row in I.rows(parent['table_references']['geometries'],authority,budget.check):
            C.need(row['parent_geometry_id'] is None,'ONLY_ACTUALLY_VERIFIED_ORDINARY_BASES')
            db.execute('INSERT INTO bases VALUES(?,?,?,?)',('pm7:'+row['native_record_id'] if row['geometry_source']=='pm7' else row['geometry_id'],row['molecule_id'],row['geometry_source'],B.encode(row)))
        db.commit()
        def tasks():
            for source in files:
                if source['family'] not in families:continue
                authority.add(source);index=0
                for batch in I.batches(source,authority,budget.check,columns=list(COLUMNS)):
                    ids=batch.column(batch.schema.get_field_index('record_id')).to_pylist()
                    owners={r['record_id']:r for r in ownerdb.execute('SELECT n.record_id,n.molecule_id,n.total_atoms,o.attempt_id,o.job_id,o.task_id,o.lane FROM native n JOIN owners o USING(molecule_id) WHERE n.record_id IN ('+','.join('?' for _ in ids)+')',ids).fetch_arrow_table().to_pylist()} if ids else {}
                    for row in batch.to_pylist():
                        actual_index=index;index+=1;owner=owners.get(row['record_id'])
                        if row['calc_type'] not in root['expected_perturbed_tasks'] or classify_owner(row,owner,True)!='CANONICAL':continue
                        C.need(row['job_id']==source['source_job_id'],'CANONICAL_ROW_SOURCE_JOB_NOT_ANY_HISTORICAL_ATTEMPT')
                        db.execute('INSERT INTO seen VALUES(?,?)',(row['record_id'],row['calc_type']))
                        found=db.execute('SELECT value FROM bases WHERE rid=?',('pm7:'+row['record_id'],)).fetchone();C.need(found is not None,'REAL_SOURCE_BASE_EXISTS')
                        if row['reproduction_package_sha256'] not in protocols:
                            db.execute('INSERT INTO unknown VALUES(?,?,?)',(row['record_id'],row['calc_type'],B.encode({'source_reference':C.reference(source),
                                'physical_row_index':actual_index,'unreviewed_package_sha256':row['reproduction_package_sha256'],'reason':'ACTUAL_PACKAGE_NOT_IN_ROOT_REVIEWED_PROTOCOL_SET'})));continue
                        protocol,pref=protocols[row['reproduction_package_sha256']]
                        yield row,B.decode(found[0]),source,actual_index,protocol,pref,dict(budget.control)
                    db.commit()
        for report in pool.map(worker,tasks()):
            if report.get('result') is not None:
                result=report['result'];db.execute('INSERT INTO children VALUES(?,?,?)',(result['parent_geometry_id'],result['geometry_id'],B.encode(result)))
                count+=1;unknown_uuid+=report['unknown_uuid']
            else:db.execute('INSERT INTO unknown VALUES(?,?,?)',(report['record_id'],report['task'],B.encode(report['error'])))
            db.commit()
        records=db.execute("SELECT count(*) FROM bases WHERE src='pm7'").fetchone()[0];expected=records*len(root['expected_perturbed_tasks'])
        seen=db.execute('SELECT count(*) FROM seen').fetchone()[0];bad=db.execute('SELECT count(*) FROM unknown').fetchone()[0]
        missing=expected-seen;C.need(missing>=0 and count+bad==seen,'ALL_CANONICAL_ACTUAL_CALL_COUNTS_CONSERVED')
        def geometries():
            for _,raw in db.execute('SELECT rid,value FROM bases ORDER BY rid'):
                base=B.decode(raw);yield base
                for (v,) in db.execute('SELECT value FROM children WHERE parent=? ORDER BY gid',(base['geometry_id'],)):yield B.decode(v)
        tables={};schemas=B.schemas();tables['geometries']=I.parquet_rows(out/'geometries.parquet',geometries(),schemas['geometries'],budget)
        for kind in ('orders','atom_counts','audit_identity'):
            tables[kind]=I.parquet_rows(out/(kind+'.parquet'),I.rows(parent['table_references'][kind],authority,budget.check),schemas[kind],budget)
        def roster():
            for row in I.rows(parent['table_references']['roster'],authority,budget.check):
                # Lossless packets are not JSON geometry rows. Count via the
                # original base IDs rather than parsing the codec storage.
                gids=[B.decode(v)['geometry_id'] for (v,) in db.execute('SELECT value FROM bases WHERE mid=?',(row['molecule_id'],))]
                row['child_count']=sum(db.execute('SELECT count(*) FROM children WHERE parent=?',(gid,)).fetchone()[0] for gid in gids);yield row
        tables['roster']=I.parquet_rows(out/'roster.parquet',roster(),schemas['roster'],budget)
        for ref in tables.values():authority.add(ref)
        unknown_path=out/'unknown_input_bindings.lossless.jsonl'
        with unknown_path.open('xb') as f:
            for rid,task,raw in db.execute('SELECT rid,task,value FROM unknown ORDER BY rid,task'):
                f.write(B.encode({'record_id':rid,'calc_type':task,'evidence':B.decode(raw)}))
            f.flush();__import__('os').fsync(f.fileno())
        return {'table_references':tables,'logical_range':parent['logical_range'],'molecules':parent['molecules'],'held_molecules':0,
            'worker_packet_references':parent.get('worker_packet_references',[]),'table_domain':'BASE_WITH_ALL_ACTUAL_CHILDREN',
            'all_actual_children_closed':bad==missing==0,'full_typed_source_order_identity_parity':False,
            'canonical_child_census':{'expected_calls':expected,'observed_canonical_calls':seen,'byte_exact_children':count,
                'missing_canonical_calls':missing,'unknown_or_mismatched_inputs':bad,'original_execution_UUID_UNKNOWN':unknown_uuid,
                'canonical_occurrence_identity_is_not_original_UUID':True,'unknown_input_bindings_reference':I.actual_ref(unknown_path) if bad else None},
            'ordinary_WP5_child_domain_only':True,'Pprime_independent_domain_acceptance':False,'new_QM_UFF_calls':0}
    finally:ownerdb.close();db.close()
