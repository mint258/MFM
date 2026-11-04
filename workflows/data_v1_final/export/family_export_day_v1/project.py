"""Original source extraction with exact child occurrence and native graph IO."""
from __future__ import annotations
import json,os,pathlib,sqlite3
from . import contract as C,io as I,transport as T
L=C.legacy();E=L['pipeline_v1.export'];O=L['pipeline_v1.io'];S=L['pipeline_v1.source'];M=L['pipeline_v1.masks']
connect=O.connect;canonical_json=L['wire_v1.codec'].canonical_json
CTX={};PART_BYTES=PART_CAP=None


def initialize(counter,cap,context):
    global PART_BYTES,PART_CAP,CTX
    PART_BYTES,PART_CAP,CTX=counter,cap,context
    C.need(os.getuid()==1278 and str(os.environ.get('SLURM_JOB_ID'))==str(context['job_id']) and os.uname().nodename==context['node'],'REAL_SAME_PARENT_WORKER_CONTEXT')
    for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):os.environ[k]='1'


def target(compiled,tid):
    return compiled['ordered_record_targets'].get(tid) or compiled['physical_targets'][tid]

def resolve_base(db, row, spec):
    if any(row[column] != expected for column, expected in spec.get("row_filters", {}).items()):
        return None
    keys = spec["keys"]
    mid, src = row[keys["molecule_id"]], spec["geometry_source"]
    if not isinstance(mid, str) or src not in {"pm7", "uff_sprime"}:
        raise ValueError("SOURCE_ID_OR_GEOMETRY_LITERAL")
    native = row[keys["native_record_id"]] if keys.get("native_record_id") else None
    idx = row[keys["sprime_conf_idx"]] if keys.get("sprime_conf_idx") else None
    view = row[keys["view_id"]] if keys.get("view_id") else None
    if src == "pm7":
        clause, physical = "native_record_id=?", native
        if not isinstance(native, str) or not native or idx is not None:
            raise ValueError("SOURCE_PM7_NATIVE_KEY_REQUIRED")
    else:
        clause, physical = "sprime_conf_idx=?", idx
        if type(idx) is not int or idx < 0:
            raise ValueError("SOURCE_UFF_KEY_REQUIRED_NO_RECORD_ID_JOIN")
    query = "SELECT * FROM selected_geometry WHERE molecule_id=? AND geometry_source=? AND " + clause + " AND view_id IS ?"
    args = [mid, src, physical, view]
    if keys.get("geometry_id"):
        query += " AND geometry_id=?"; args.append(row[keys["geometry_id"]])
    found = db.execute(query, args).fetchall()
    if not found:
        return None
    if len(found) != 1:
        raise ValueError("AMBIGUOUS_PHYSICAL_TO_OPAQUE_GEOMETRY_MAP")
    geometry = dict(found[0])
    if keys.get("geometry_id") and row[keys["geometry_id"]] != geometry["geometry_id"]:
        raise ValueError("SOURCE_OPAQUE_GEOMETRY_ID_DISAGREES_WITH_PHYSICAL_KEY")
    owner = db.execute("SELECT * FROM latest_owners WHERE geometry_id=? AND source_family=? AND task_name=?", (geometry["geometry_id"], spec["source_family"], spec.get("task", ""))).fetchone()
    if owner is not None:
        if any(canonical_json(row[column]).decode() != owner[key] for key, column in spec.get("owner_keys", {}).items()):
            return None
        if set(spec.get("owner_keys", {})) != {"attempt_id", "job_id", "task_id"}:
            raise ValueError("COMPLETE_LATEST_OWNER_IDENTITY_KEYS_REQUIRED")
    elif spec.get("requires_latest_owner", True):
        raise ValueError("SELECTED_GEOMETRY_LATEST_OWNER_MISSING")
    if spec.get("n_atoms_column"):
        n = row[spec["n_atoms_column"]]
    elif spec.get("n_atoms_from_array"):
        n = len(row[spec["n_atoms_from_array"]])
    elif spec.get("n_atoms_from_canonical_geometry") is True:
        item = db.execute("SELECT n_atoms FROM pieces WHERE geometry_id=? AND part='__geometry__'", (geometry["geometry_id"],)).fetchone()
        if item is None:
            raise ValueError("CANONICAL_GEOMETRY_ATOM_COUNT_MISSING_BEFORE_LABEL_WAVE")
        n = item[0]
    else:
        raise ValueError("EXPLICIT_ATOM_COUNT_AUTHORITY_REQUIRED")
    if type(n) is not int or n <= 0:
        raise ValueError("SOURCE_ATOM_COUNT_INVALID")
    geometry["n_atoms"] = n
    return geometry


def resolve_exact(db,row,spec,absolute_row):
    if spec.get('binding_mode')!='CANONICAL_WP5_SOURCE_OCCURRENCE':return resolve_base(db,row,spec)
    ref=spec['file'];found=db.execute('SELECT * FROM actual_child_rows WHERE source_sha=? AND physical_row_index=?',(ref['sha256'],absolute_row)).fetchone()
    if found is None:
        # A non-selected/non-Common/historical source occurrence is not a new
        # masked record and never resolves to its base as a fallback.
        return None
    if db.execute('SELECT 1 FROM selected_geometry WHERE geometry_id=?',(found['geometry_id'],)).fetchone() is None:return None
    C.need(row['record_id']==found['record_id'] and row['molecule_id']==found['molecule_id']
        and row['calc_type']==found['calc_type'] and row['input_bundle_sha256']==found['input_sha'],'ACTUAL_STORED_CHILD_INPUT_HASH_OCCURRENCE_BINDING')
    geometry=db.execute('SELECT * FROM selected_geometry WHERE geometry_id=?',(found['geometry_id'],)).fetchone()
    C.need(geometry['parent_geometry_id'] is not None and geometry['view_id'] is not None,'PERTURBED_LABEL_NEVER_BASE_GEOMETRY')
    C.need('__bound_gid' not in row and '__bound_view' not in row,'NO_SOURCE_SELECTOR_COLUMN_COLLISION')
    local=dict(row,__bound_gid=found['geometry_id'],__bound_view=geometry['view_id']);keys=dict(spec['keys'],geometry_id='__bound_gid',view_id='__bound_view')
    return resolve_base(db,local,dict(spec,keys=keys))


def row_arrays(row,spec,geometry,db,compiled,target_ids=None):
    if spec['kind']=='geometry':
        arrays=S.geometry_arrays(row,spec,geometry['n_atoms']);rid=row.get('native_record_id') if geometry['geometry_source']=='pm7' else row.get('native_anchor_record_id')
        if rid is None:
            parent=geometry['parent_geometry_id'] or geometry['geometry_id'];found=db.execute('SELECT native_anchor FROM geometry_native_anchor WHERE gid=?',(parent,)).fetchone()
            C.need(found is not None,'ACTUAL_SOURCE_NATIVE_ANCHOR_REQUIRED');rid=found[0]
        pointer=db.execute('SELECT payload FROM native_pointers WHERE rid=?',(rid,)).fetchone();C.need(pointer is not None,'NO_NATIVE_POINTER_GUESS_FROM_OPAQUE_GID')
        arrays.update(T.native_bonds(json.loads(pointer[0]),arrays['atomic_numbers'].tolist()))
        return [('__geometry__',arrays,{})]
    result=[]
    def loader(cs):
        if 'column' in cs:return S.extract(row,cs)
        code=row[cs['task_code_column']] if 'task_code_column' in cs else cs['task_code']
        value=db.execute('SELECT payload FROM compact_masks WHERE geometry_id=? AND task_code=?',(geometry['geometry_id'],code)).fetchone()
        C.need(value is not None,'ACTUAL_COMPACT_MASK_GEOMETRY_AND_TASK_BINDING');return M.decode_row(value[0])
    for tid in (spec['targets'] if target_ids is None else target_ids):
        note={};arrays=T.target_arrays(row,spec,target(compiled,tid),geometry['n_atoms'],compact_loader=loader,annotations=note)
        note.setdefault('_source_precision',{})[tid]=(row[spec['precision_column']] if spec.get('precision_column') else {'status':'ORIGINAL_PRINT_PRECISION_NOT_STORED_IN_PROJECTION','projected_source_float64_unchanged':True})
        result.append((tid,arrays,note))
    return result


def columns(spec):
    result=set(S.source_columns(spec))
    if spec.get('binding_mode')=='CANONICAL_WP5_SOURCE_OCCURRENCE':result.update(('record_id','molecule_id','calc_type','input_bundle_sha256'))
    if spec['kind']=='geometry':result.update(spec['native_anchor_columns'])
    if spec.get('precision_column'):result.add(spec['precision_column'])
    return sorted(result)


def source_worker(task):
    index,spec,groups,database,output,compiled,offset=task;db=connect(database,readonly=True);stage=connect(output)
    stage.execute('CREATE TABLE pieces('+E.PIECES_SCHEMA+')');examined=count=accounted=0
    claim=CTX['claim_database_reference'];db.execute('ATTACH DATABASE ? AS actual_claims',(pathlib.Path(claim['path']).as_uri()+'?mode=ro&immutable=1',))
    for name in ('source_cells','claim_bindings'):db.execute('CREATE TEMP VIEW '+name+' AS SELECT * FROM actual_claims.'+name)
    try:
        for rg in groups:
            number=0
            for batch in I.worker_batches(spec,CTX['frames'][spec['file']['path']],lambda:I.worker_check(CTX['control']),[rg],columns(spec)):
                for row in batch.to_pylist():
                    examined+=1
                    if spec['kind']=='geometry':
                        geometry=resolve_exact(db,row,spec,offset+number)
                        groups0=[] if geometry is None else [(geometry,None)]
                    else:groups0=target_geometries(db,row,spec,compiled,offset+number)
                    for geometry,tids in groups0:
                        for part,arrays,note in row_arrays(row,spec,geometry,db,compiled,tids):
                            stage.execute('INSERT INTO pieces VALUES(?,?,?,?,?,?,?)',(geometry['geometry_id'],part,geometry['n_atoms'],index,rg,number,S.pack(arrays,note)));count+=1
                    number+=1
                if examined%16==0:stage.commit()
                I.worker_check(CTX['control']);actual=pathlib.Path(output).stat().st_size
                with PART_BYTES.get_lock():
                    PART_BYTES.value+=actual-accounted;accounted=actual;C.need(PART_BYTES.value<=PART_CAP,'SHARED_WHOLE_F64_STAGING_CAP')
        stage.commit()
    finally:stage.close();db.close()
    return {'path':str(output),'source_index':index,'row_groups':groups,'source_rows_examined':examined,'pieces':count,'pid':os.getpid(),
        'source_float64_preserved':True,'new_QM_UFF_calls':0}


def claim_for(db,source_reference,physical_row_index,field_id):
    """Lookup an actual per-field claim; equal task names never imply geometry."""
    C.need(type(field_id) is int and 0<=field_id<146,'EXACT_ORIGINAL_FIELD_ID')
    rows=db.execute('SELECT b.*,c.* FROM claim_bindings b JOIN source_cells c USING(cell_id) WHERE c.source_sha=? AND c.physical_row_index=?',
        (source_reference['sha256'],physical_row_index)).fetchall()
    found=[dict(r) for r in rows if int.from_bytes(r['fields'],'little')>>field_id&1]
    C.need(len(found)==1 and found[0]['source_path']==source_reference['path'],'UNIQUE_ACTUAL_CELL_FIELD_GEOMETRY_CLAIM_REQUIRED')
    C.need(found[0]['binding_status']=='ACTUAL_DOUBLE_HASH_OR_NATIVE_PAYLOAD_BOUND','NO_UNPROVED_TASK_VIEW_FALLBACK')
    return found[0]


def mask_claim_for(db,group_key,record_ordinal,task_code,field_id):
    rows=db.execute('SELECT b.*,c.* FROM claim_bindings b JOIN source_cells c USING(cell_id) WHERE c.group_key=? AND c.record_ordinal=? AND c.task_code=?',
        (group_key,record_ordinal,task_code)).fetchall()
    found=[dict(r) for r in rows if int.from_bytes(r['fields'],'little')>>field_id&1]
    C.need(len(found)==1,'UNIQUE_ORIGINAL_MASK_CELL_FIELD_TO_ACTUAL_GEOMETRY');return found[0]


def claim_schema(db):
    db.row_factory=sqlite3.Row
    # Each immutable source locator is stored once, not repeated hundreds of
    # millions of times. The public lossless view preserves the agreed API.
    db.execute('CREATE TABLE source_files(file_id INTEGER PRIMARY KEY,source_path TEXT UNIQUE,source_bytes INTEGER,source_sha TEXT UNIQUE)')
    db.execute('CREATE TABLE source_cell_rows(cell_id INTEGER PRIMARY KEY,file_id INTEGER,physical_row_index INTEGER,record_id TEXT,molecule_id TEXT,group_key TEXT,record_ordinal INTEGER,task_code INTEGER,input_bundle_sha TEXT,input_file_sha_json TEXT,UNIQUE(file_id,physical_row_index))')
    db.execute('CREATE INDEX mask_claim_key ON source_cell_rows(group_key,record_ordinal,task_code)')
    db.execute('CREATE VIEW source_cells AS SELECT c.cell_id,f.source_path,f.source_bytes,f.source_sha,c.physical_row_index,c.record_id,c.molecule_id,c.group_key,c.record_ordinal,c.task_code,c.input_bundle_sha,c.input_file_sha_json FROM source_cell_rows c JOIN source_files f USING(file_id)')
    db.execute('CREATE TABLE claim_bindings(cell_id INTEGER,geometry_id TEXT,fields BLOB,policy_sha TEXT,binding_status TEXT,evidence BLOB,PRIMARY KEY(cell_id,geometry_id,policy_sha))')


def add_claims(db,cell,bindings):
    prior=db.execute('SELECT * FROM source_files WHERE source_path=? OR source_sha=?',(cell['source_path'],cell['source_sha'])).fetchall()
    if prior:
        C.need(len(prior)==1 and prior[0]['source_path']==cell['source_path'] and prior[0]['source_bytes']==cell['source_bytes'] and prior[0]['source_sha']==cell['source_sha'],'ONE_EXACT_IMMUTABLE_SOURCE_LOCATOR_NOT_ALIAS')
        file_id=prior[0]['file_id']
    else:file_id=db.execute('INSERT INTO source_files(source_path,source_bytes,source_sha) VALUES(?,?,?)',(cell['source_path'],cell['source_bytes'],cell['source_sha'])).lastrowid
    keys=('physical_row_index','record_id','molecule_id','group_key','record_ordinal','task_code','input_bundle_sha','input_file_sha_json')
    cursor=db.execute('INSERT INTO source_cell_rows(file_id,'+','.join(keys)+') VALUES('+','.join('?' for _ in range(len(keys)+1))+')',(file_id,*(cell[k] for k in keys)))
    grouped={};seen=set()
    for field_id,gid,policy_sha,evidence in bindings:
        C.need(type(field_id) is int and 0<=field_id<146 and field_id not in seen,'NO_DUPLICATE_OR_UNASSIGNED_SOURCE_FIELD_CLAIM');seen.add(field_id)
        key=(gid,policy_sha);entry=grouped.setdefault(key,{'bits':0,'evidence':evidence})
        C.need(entry['evidence']==evidence,'GROUP_ONLY_ACTUALLY_EQUAL_GEOMETRY_EVIDENCE_NOT_TASK_NAME');entry['bits']|=1<<field_id
    for (gid,sha),v in grouped.items():
        db.execute('INSERT INTO claim_bindings VALUES(?,?,?,?,?,?)',(cursor.lastrowid,gid,v['bits'].to_bytes(19,'little'),sha,
            'ACTUAL_DOUBLE_HASH_OR_NATIVE_PAYLOAD_BOUND',json.dumps(v['evidence'],sort_keys=True,separators=(',',':')).encode()))
    return len(seen)

def close_claims(db,database,output,plan,proof,expected,observed,unknown):
    C.need(set(expected)==set(observed) and all(type(v) is int and v>=0 for v in expected.values()),'EXACT_PER_FIELD_SCOPE_DENOMINATORS')
    complete=unknown==0 and expected==observed
    db.commit();db.close();data=I.actual_ref(database)
    value={'schema':'FAMILY_ACTUAL_FIELD_GEOMETRY_CLAIMS_V1',
        'status':'COMPLETE_COMMON_FIELD_GEOMETRY_CLAIMS_NOT_FINAL_RELEASE' if complete else 'INCOMPLETE_FIELD_GEOMETRY_CLAIMS_HOLD',
        'actual_parent_job_id':str(proof['job_id']),'actual_node':proof['request']['node'],'uid':1278,
        'startup_proof_reference':C.Q.pin(plan['_startup_proof_path']),'source_entry_reference':C.Q.pin(__file__),
        'D5_components_reference':plan['D5_components_reference'],'field_policy_reference':plan['field_geometry_policy_reference'],
        'field_map_reference':plan['field_map_reference'],'database_reference':data,
        'expected_Common_field_counts':expected,'observed_Common_field_counts':observed,'unknown_field_claims':unknown,
        'coverage_scope':'ALL_FINAL_COMMON_ACTUAL_CELLS_BY_FIELD_NOT_TASK_NAME',
        'original_mask_bits_and_reasons_rewritten':False,'field_specific_geometry_claims':True,
        'current_parent_C0_claimed':False,'final_consumer_release_created':False,'new_QM_UFF_calls':0}
    return I.data_json_new(output,value)


def pack_geometry(row):
    import numpy as np
    metadata={k:v for k,v in row.items() if k not in ('atomic_numbers','positions_A')}
    return S.pack({'atomic_numbers':np.asarray(row['atomic_numbers'],dtype='<i2'),'positions_A':np.asarray(row['positions_A'],dtype='<f8')},{'_geometry_metadata':metadata})


def unpack_geometry(raw):
    arrays=S.unpack(raw);metadata=S.reason_annotations(raw)['_geometry_metadata']
    return dict(metadata,atomic_numbers=arrays['atomic_numbers'].tolist(),positions_A=arrays['positions_A'].tolist())


def geometry(db,gid):
    row=db.execute('SELECT payload FROM full_geometries WHERE geometry_id=?',(gid,)).fetchone();C.need(row is not None,'ACTUAL_FROZEN_GEOMETRY_ID_ONLY')
    return unpack_geometry(row[0])


def target_geometries(db,row,spec,compiled,absolute_row):
    if any(row[k]!=v for k,v in spec.get('row_filters',{}).items()):return []
    cell=db.execute('SELECT cell_id FROM source_cells WHERE source_sha=? AND physical_row_index=?',(spec['file']['sha256'],absolute_row)).fetchone()
    if cell is None:return []  # Complete all-Common claim authority checked by Parent.
    grouped={}
    for tid in spec['targets']:
        t=target(compiled,tid);claims=[claim_for(db,spec['file'],absolute_row,CTX['field_ids'][m['field_key']]) for m in t['members']]
        gids={c['geometry_id'] for c in claims};C.need(len(gids)==1,'PHYSICAL_TARGET_MEMBERS_CANNOT_MIX_ACTUAL_GEOMETRIES')
        gid=next(iter(gids));g=db.execute('SELECT * FROM selected_geometry WHERE geometry_id=?',(gid,)).fetchone()
        if g is None:continue  # Frozen D5 subset/diagnostic anti-join, not source failure masking.
        g=dict(g);C.need(g['molecule_id']==row[spec['keys']['molecule_id']] and g['geometry_source']==spec['geometry_source'],'FIELD_SOURCE_GEOMETRY_CONTEXT')
        atom=db.execute("SELECT n_atoms FROM pieces WHERE geometry_id=? AND part='__geometry__'",(gid,)).fetchone();C.need(atom is not None,'GEOMETRY_WAVE_PRECEDES_LABELS')
        g['n_atoms']=atom[0];entry=grouped.setdefault(gid,(g,[]));entry[1].append(tid)
    return list(grouped.values())


def geometry_database(plan,component,source,out,budget,authority):
    """Compact f64 geometry reference index, not 146-field JSON duplication."""
    db=connect(out/'geometry.sqlite');db.execute('CREATE TABLE full_geometries(geometry_id TEXT PRIMARY KEY,molecule_id TEXT,geometry_source TEXT,native_record_id TEXT,sprime_conf_idx INTEGER,parent_geometry_id TEXT,view_id TEXT,payload BLOB)')
    db.execute('CREATE INDEX native_base ON full_geometries(molecule_id,geometry_source,native_record_id,parent_geometry_id)')
    db.execute('CREATE TABLE actual_child_rows(source_sha TEXT,physical_row_index INTEGER,geometry_id TEXT,record_id TEXT,molecule_id TEXT,calc_type TEXT,input_sha TEXT,PRIMARY KEY(source_sha,physical_row_index))')
    db.execute('CREATE TABLE common_members(molecule_id TEXT PRIMARY KEY)')
    common=C.meta(component['common_closure_references']['manifest'])
    for ref in common['membership_tables']:
        for batch in I.batches(ref,authority,budget.check,columns=['molecule_id','common_population']):
            for row in batch.to_pylist():
                if row['common_population']:db.execute('INSERT INTO common_members VALUES(?)',(row['molecule_id'],))
            db.commit()
    refs=[component['ordinary_input_tables']['geometries'],*source.get('additional_actual_geometry_tables',[])]
    for ref in refs:
        for batch in I.batches(ref,authority,budget.check):
            for row in batch.to_pylist():
                C.need(db.execute('SELECT 1 FROM common_members WHERE molecule_id=?',(row['molecule_id'],)).fetchone() is not None,'ALL_EXPORT_GEOMETRY_DOMAINS_SAME_ACTUAL_COMMON')
                db.execute('INSERT INTO full_geometries VALUES(?,?,?,?,?,?,?,?)',tuple(row[k] for k in ('geometry_id','molecule_id','geometry_source','native_record_id','sprime_conf_idx','parent_geometry_id','view_id'))+(pack_geometry(row),))
                if row['parent_geometry_id'] is not None:
                    provenance=json.loads(row['source_provenance_json']);occ=provenance.get('canonical_source_occurrence')
                    if occ is not None:db.execute('INSERT INTO actual_child_rows VALUES(?,?,?,?,?,?,?)',
                        (occ['source_reference']['sha256'],occ['physical_row_index'],row['geometry_id'],occ['record_id'],occ['molecule_id'],occ['calc_type'],occ['input_bundle_sha256']))
            db.commit();budget.check()
    db.close();return I.actual_ref(out/'geometry.sqlite')


def selection_database(plan,component,source,compiled,mask_release,out,budget,authority,geometry_reference):
    d5=I.json_body(component['ordinary_D5_artifacts']['d5_manifest'],authority,budget.check)
    # The published three manifests retain all original DATA but carry the
    # independent actual Parent/Root acceptance. This is a current-parent view.
    d5=dict(d5,geometry_map=component['geometry_map_manifest_reference'],diagnostic=component['diagnostic_manifest_reference'],conformer_orders=component['order_manifest_reference'])
    config={'subsets':['pilot_train','pilot_val'] if plan['purpose']=='pilot55k' else ['train_all','val_all'],
        'full_export_authorized_after_model_loader_acceptance':plan['purpose']=='full'}
    db=connect(out/'export_stage.sqlite');E.prepare_selection(db,d5,config,False,out)
    db.execute('CREATE TABLE native_pointers(rid TEXT PRIMARY KEY,payload TEXT)')
    db.execute('CREATE TABLE geometry_native_anchor(gid TEXT PRIMARY KEY,native_anchor TEXT)')
    db.execute('CREATE TABLE shard_members(geometry_id TEXT PRIMARY KEY)');db.execute('CREATE TABLE partition_members(name TEXT,geometry_id TEXT,PRIMARY KEY(name,geometry_id))')
    db.execute('CREATE TABLE exported(store_name TEXT,geometry_id TEXT,kind TEXT,parts_json TEXT,PRIMARY KEY(store_name,geometry_id))')
    db.execute('CREATE TABLE stores(name TEXT PRIMARY KEY,path TEXT,manifest BLOB,records INTEGER,molecules INTEGER,geometry_source TEXT,view_id TEXT,kind TEXT)')
    db.execute('CREATE TABLE complete_shards(shard_index INTEGER PRIMARY KEY,header BLOB)')
    db.execute('ATTACH DATABASE ? AS actual_geometry',(pathlib.Path(geometry_reference['path']).as_uri()+'?mode=ro&immutable=1',))
    # Explicit N1/Pprime-only domains enter only from the independently accepted
    # source release, never by inflating ordinary D5 N or copying PM7 pointers.
    for ref in source.get('additional_actual_geometry_tables',[]):
        for batch in I.batches(ref,authority,budget.check):
            for row in batch.to_pylist():
                role=db.execute('SELECT effective_role FROM selected_molecules WHERE molecule_id=?',(row['molecule_id'],)).fetchone()
                if role is None:continue
                C.need(row['identity_namespace'] in source['accepted_additional_identity_namespaces'],'ROOT_RELEASED_ADDITIONAL_PHYSICAL_DOMAIN_ONLY')
                db.execute('INSERT INTO selected_geometry VALUES(?,?,?,?,?,?,?,?,?)',tuple(row[k] for k in ('geometry_id','molecule_id','geometry_source','native_record_id','sprime_conf_idx','parent_geometry_id','view_id'))+(role[0],row['source_role']))
    # Original exclusions are rechecked after every independently accepted
    # additional domain has entered this current selection. New real children
    # inherit exclusion through their actual parent chain, never by task name.
    diagnostic=C.meta(d5['diagnostic']);db.execute('CREATE TEMP TABLE diagnostic_forbidden(gid TEXT PRIMARY KEY)')
    for ref in diagnostic['target_exclusion_tables']:
        authority.add(ref)
        for batch in I.batches(ref,authority,budget.check,columns=['geometry_id']):
            for row in batch.to_pylist():db.execute('INSERT OR IGNORE INTO diagnostic_forbidden VALUES(?)',(row['geometry_id'],))
    def excluded(gid):return db.execute('SELECT 1 FROM diagnostic_forbidden WHERE gid=?',(gid,)).fetchone() is not None
    def parent(gid):
        found=db.execute('SELECT parent_geometry_id FROM actual_geometry.full_geometries WHERE geometry_id=?',(gid,)).fetchone()
        return (found is not None,found[0] if found else None)
    assert_diagnostic_lineage((dict(r) for r in db.execute('SELECT geometry_id,parent_geometry_id FROM selected_geometry')),excluded,parent,budget.check)
    columns=['record_id','molecule_id','source_path','real_index','record_payload_sha256','total_atoms']
    for batch in I.batches(source['native_pointer_reference'],authority,budget.check,columns=columns):
        for row in batch.to_pylist():
            if db.execute('SELECT 1 FROM selected_molecules WHERE molecule_id=?',(row['molecule_id'],)).fetchone():
                db.execute('INSERT INTO native_pointers VALUES(?,?)',(row['record_id'],json.dumps(row,sort_keys=True,separators=(',',':'))))
        db.commit()
    for gid,raw in db.execute('SELECT geometry_id,payload FROM actual_geometry.full_geometries'):
        row=unpack_geometry(raw);anchor=row.get('native_record_id') if row['geometry_source']=='pm7' else row.get('native_anchor_record_id')
        if anchor is not None:db.execute('INSERT INTO geometry_native_anchor VALUES(?,?)',(gid,anchor))
    owners=C.meta(source['latest_owner_manifest_reference'])
    C.need(owners['status']=='CANONICAL_LATEST_OWNERS_FROZEN','ACTUAL_LATEST_OWNER_MANIFEST')
    for ref in owners['owner_tables']:
        for batch in I.batches(ref,authority,budget.check):
            for row in batch.to_pylist():
                if db.execute('SELECT 1 FROM selected_geometry WHERE geometry_id=?',(row['geometry_id'],)).fetchone():
                    db.execute('INSERT INTO latest_owners VALUES(?,?,?,?,?,?)',(row['geometry_id'],row['source_family'],row['task_name'],*[canonical_json(row[k]).decode() for k in ('attempt_id','job_id','task_id')]))
    C.need(mask_release['schema']=='FINAL_GEOMETRY_BOUND_VALIDITY_MASK_CANDIDATE_V1' and mask_release['status']=='EXACT_ORIGINAL_MASKS_BOUND_TO_ACCEPTED_D5_TARGETS','ACTUAL_PER_FIELD_GEOMETRY_BOUND_MASKS_NOT_TASK_NAME_VIEWS')
    mask_refs=list(mask_release['mask_tables'])
    if source.get('independent_Pprime_field_and_mask_authority_reference'):
        pp=C.meta(source['independent_Pprime_field_and_mask_authority_reference']);ppmask=C.meta(pp['mask_release_reference']);mask_refs.extend(ppmask['mask_tables'])
    for ref in mask_refs:
        authority.add(ref)
        for batch in I.batches(ref,authority,budget.check):
            for row in batch.to_pylist():
                if db.execute('SELECT 1 FROM selected_geometry WHERE geometry_id=?',(row['geometry_id'],)).fetchone():
                    db.execute('INSERT INTO compact_masks VALUES(?,?,?)',(row['geometry_id'],row['task_code'],M.encode_row(row)))
            db.commit()
    db.execute('DETACH DATABASE actual_geometry');db.commit();return db,d5

def combined_claim_database(source,plan,claim,out,budget,authority):
    """PM7 hook counts remain original; foreign formal masks stay independent."""
    extra=source.get('independent_Pprime_field_and_mask_authority_reference')
    if not extra:return claim['database_reference']
    accepted=C.independent_pprime(extra,plan['D5_components_reference']);foreign=accepted['claim_database_reference']
    C.need(foreign in authority,'EXACT_INDEPENDENT_FORMAL_FIELD_CLAIMS_DATA_DECLARED')
    with I.held(foreign,authority,budget.check):pass
    path=out/'combined_source_claims.sqlite';target=sqlite3.connect(path);base=sqlite3.connect(pathlib.Path(claim['database_reference']['path']).as_uri()+'?mode=ro&immutable=1',uri=True)
    try:base.backup(target)
    finally:base.close()
    target.row_factory=sqlite3.Row;other=sqlite3.connect(pathlib.Path(foreign['path']).as_uri()+'?mode=ro&immutable=1',uri=True);other.row_factory=sqlite3.Row
    geometry_db=sqlite3.connect(pathlib.Path(plan['_geometry_database_path']).as_uri()+'?mode=ro&immutable=1',uri=True)
    try:
        for row in other.execute('SELECT * FROM source_cells ORDER BY cell_id'):
            budget.check();cell=dict(row);old_id=cell.pop('cell_id');bindings=[]
            C.need(C.reference({'path':cell['source_path'],'bytes':cell['source_bytes'],'sha256':cell['source_sha']}) in authority,
                'FORMAL_SOURCE_CELL_ACTUAL_BODY_REFERENCE_DECLARED')
            for binding in other.execute('SELECT * FROM claim_bindings WHERE cell_id=?',(old_id,)):
                C.need(binding['binding_status']=='ACTUAL_DOUBLE_HASH_OR_NATIVE_PAYLOAD_BOUND','REAL_PPRIME_PER_FIELD_BINDING_NOT_TASK_NAME')
                physical=geometry_db.execute('SELECT molecule_id,geometry_source FROM full_geometries WHERE geometry_id=?',(binding['geometry_id'],)).fetchone()
                C.need(physical==(cell['molecule_id'],'uff_sprime'),'PPRIME_ONLY_ACTUAL_UFF_DOMAIN')
                bits=int.from_bytes(binding['fields'],'little');C.need(bits>>146==0,'ORIGINAL146_FIELD_IDS_WITH_CONDITION_DOMAIN')
                for fid in range(146):
                    if bits>>fid&1:bindings.append((fid,binding['geometry_id'],binding['policy_sha'],json.loads(binding['evidence'])))
            add_claims(target,cell,bindings)
        target.commit()
    finally:target.close();other.close();geometry_db.close()
    ref=I.actual_ref(path);authority.add(ref);return ref
def expected_coverage(db,claim_reference,compiled,field_ids):
    class Union:
        def __init__(self):self.value=0
        def step(self,raw):self.value|=int.from_bytes(raw,'little')
        def finalize(self):return self.value.to_bytes(19,'little')
    db.create_aggregate('actual_field_union',1,Union)
    db.create_function('contains_original_fields',2,lambda a,b:int(int.from_bytes(a,'little')&int.from_bytes(b,'little')==int.from_bytes(b,'little')),deterministic=True)
    db.execute('ATTACH DATABASE ? AS expected_claims',(pathlib.Path(claim_reference['path']).as_uri()+'?mode=ro&immutable=1',))
    db.execute('CREATE TABLE expected_domains AS SELECT b.cell_id,b.geometry_id,actual_field_union(b.fields) AS fields FROM expected_claims.claim_bindings b JOIN selected_geometry g USING(geometry_id) GROUP BY b.cell_id,b.geometry_id')
    db.execute('CREATE TABLE expected_targets(geometry_id TEXT,target TEXT,PRIMARY KEY(geometry_id,target))')
    for tid,target0 in {**compiled['physical_targets'],**compiled['ordered_record_targets']}.items():
        fields=[m['field_key'] for m in target0['members']];ids=field_ids
        C.need(all(key in ids for key in fields),'ALL_TARGET_MEMBERS_ORIGINAL_FIELD_MAP')
        mask=sum(1<<ids[key] for key in fields).to_bytes(19,'little')
        db.execute('INSERT INTO expected_targets SELECT DISTINCT d.geometry_id,? FROM expected_domains d JOIN selected_geometry g USING(geometry_id) WHERE g.geometry_source=? AND contains_original_fields(d.fields,?)',(tid,target0['geometry_source'],mask))
        C.need(db.execute('SELECT 1 FROM expected_targets WHERE target=? LIMIT 1',(tid,)).fetchone() is not None,'ENABLED_TARGET_HAS_ACTUAL_REQUESTED_GEOMETRY_DOMAIN:'+tid)
    O.reject_rows(db,"SELECT geometry_id,target FROM expected_targets EXCEPT SELECT geometry_id,part FROM pieces WHERE part!='__geometry__'",'EXPECTED_REAL_FIELD_GEOMETRY_MISSING_SOURCE_VALUES')
    O.reject_rows(db,"SELECT geometry_id,part FROM pieces WHERE part!='__geometry__' EXCEPT SELECT geometry_id,target FROM expected_targets",'SOURCE_TARGET_OUTSIDE_ACTUAL_FIELD_GEOMETRY_CLAIMS')
    db.commit();db.execute('DETACH DATABASE expected_claims')

def assert_diagnostic_lineage(rows,is_excluded,parent_for,check=lambda:None):
    """Pure field/lineage gate; no sampling, value, geometry or old table edit."""
    count=0
    for row in rows:
        check();gid=row['geometry_id'];cursor=gid;seen=set()
        while cursor is not None:
            C.need(cursor not in seen,'ACTUAL_GEOMETRY_PARENT_CYCLE_HOLD');seen.add(cursor)
            C.need(not is_excluded(cursor),'DIAGNOSTIC_BASE_OR_ACTUAL_DESCENDANT_IN_EXPORT_SELECTION:'+gid)
            known,next_parent=parent_for(cursor);C.need(known,'ACTUAL_GEOMETRY_PARENT_LINEAGE_UNKNOWN_HOLD')
            if cursor==gid:C.need(next_parent==row['parent_geometry_id'],'ACTUAL_SELECTED_PARENT_BINDING_CONFLICT')
            cursor=next_parent
        count+=1
    return count