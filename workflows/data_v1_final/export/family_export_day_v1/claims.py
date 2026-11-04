"""Full Common per-field source/geometry claims, original input bytes and payloads."""
from __future__ import annotations
import hashlib,json,os,sqlite3
from workflows.data_v1_final.labels.source_status_cpu_auto_memory_v1.support import lookup_batch,classify_owner,TASKS,TASK_FAMILIES
from workflows.data_v1_final.export.d5_inputs_builder_v1 import children as H
from . import contract as C,io as I,project as P


def claim_geometry(db,row,source,offset,rule,protocols,objects,actual_d5_reference,input_cache):
    mode=rule['binding_rule'];record=row['record_id'];src=rule['geometry_source']
    if mode=='EXACT_STORED_GEOMETRY_ID':
        gid=row[rule['geometry_id_column']];geometry=P.geometry(db,gid)
    elif mode=='ACTUAL_INPUT_CHILD_DOUBLE_HASH':
        found=db.execute('SELECT geometry_id FROM actual_child_rows WHERE source_sha=? AND physical_row_index=?',(source['sha256'],offset)).fetchall()
        C.need(len(found)==1,'ACTUAL_D5_BYTE_BOUND_CHILD_SOURCE_OCCURRENCE_REQUIRED');geometry=P.geometry(db,found[0][0]);gid=geometry['geometry_id']
    elif mode in ('ORIGINAL_NATIVE_PARENT_DOUBLE_HASH','ORIGINAL_NATIVE_PAYLOAD_SOURCE'):
        found=db.execute("SELECT geometry_id FROM full_geometries WHERE molecule_id=? AND geometry_source='pm7' AND native_record_id=? AND parent_geometry_id IS NULL",(row['molecule_id'],record)).fetchall()
        C.need(len(found)==1,'UNIQUE_NATIVE_PARENT_FROM_ACCEPTED_D5_MAP');geometry=P.geometry(db,found[0][0]);gid=geometry['geometry_id']
    else:raise ValueError('UNSUPPORTED_FINAL_FIELD_GEOMETRY_RULE_NO_SCIENTIFIC_DEFAULT:'+str(mode))
    C.need(geometry['molecule_id']==row['molecule_id'] and geometry['geometry_source']==src,'FIELD_ACTUAL_GEOMETRY_SOURCE_AND_MID_BINDING')
    if mode=='ORIGINAL_NATIVE_PAYLOAD_SOURCE':
        C.need(row['calc_type'] in ('D20','D3'),'NATIVE_PAYLOAD_RULE_ONLY_EXPLICIT_NON_QM_SOURCE')
        pointer=json.loads(geometry['source_provenance_json']);C.need(pointer['record_id']==record and len(pointer['record_payload_sha256'])==64,'ORIGINAL_NATIVE_PAYLOAD_SHA_NOT_RECONSTRUCTED_GRAPH')
        return gid,{'kind':mode,'D5_source_geometry_sha256':geometry['geometry_sha256'],'native_payload_sha256':pointer['record_payload_sha256'],
            'actual_D5_source_reader_and_full_readback_inherited':True,'input_hashes':'NOT_APPLICABLE_NON_QM',
            'field_frame_acceptance_reference':rule['frame_acceptance_reference']}
    protocol,pref=protocols[row['reproduction_package_sha256']];engine,legacy,archive,_=objects;engine.load_protocol(protocol)
    recipe=next(t for t in protocol['tasks'] if t['name']==row['calc_type'])
    base=P.geometry(db,geometry['parent_geometry_id']) if geometry['parent_geometry_id'] is not None else geometry
    if mode=='ACTUAL_INPUT_CHILD_DOUBLE_HASH':
        provenance=json.loads(geometry['source_provenance_json']);occ=provenance['canonical_source_occurrence']
        C.need(actual_d5_reference and C.reference(occ['source_reference'])==C.reference(source)
            and occ['physical_row_index']==offset and occ['record_id']==record and occ['calc_type']==row['calc_type']
            and provenance['original_input_file_sha256']==row['input_file_sha256']
            and geometry['actual_input_bundle_sha256']==row['input_bundle_sha256']
            and geometry['actual_protocol_sha256']==pref['sha256'],'REUSE_EXACT_ACTUAL_D5_C0_BOTH_INPUT_HASHES_AND_SOURCE_OCCURRENCE')
        return gid,{'kind':mode,'base_geometry_id':base['geometry_id'],'target_geometry_id':gid,
            'target_geometry_sha256':geometry['geometry_sha256'],'source_input_file_hashes_exact':True,
            'source_input_bundle_sha256':row['input_bundle_sha256'],'source_input_bundle_hash_exact':True,
            'actual_D5_input_binding_inherited_from':actual_d5_reference,'original_protocol_reference':pref,
            'original_seed_record_id':record,'field_frame_acceptance_reference':rule['frame_acceptance_reference'],
            'native_output_frame_not_inferred_from_input_binding':True,'source_values_not_transformed':True}
    from rdkit import Chem
    symbols=[Chem.GetPeriodicTable().GetElementSymbol(z) for z in base['atomic_numbers']]
    cache_key=(base['geometry_id'],record,row['calc_type'],pref['sha256'],row['input_bundle_sha256'],json.dumps(row['input_file_sha256'],sort_keys=True,separators=(',',':')))
    if cache_key not in input_cache:
        rendered=engine.render_inputs(recipe,{'symbols':symbols,'coords':base['positions_A']},{'record_id':record},protocol)
        H.O.input_binding(rendered,row['input_file_sha256'],row['input_bundle_sha256'],archive.bundle)
        name='input.mop' if recipe['family']=='mopac' else 'input.xyz';coords=H.O.input_coordinates(rendered[name],name,symbols,legacy.f)
        C.need(H.O.equal_numbers(coords,H.O.input_coordinates(rendered['input.xyz'],'input.xyz',symbols,legacy.f)),'ACTUAL_PROGRAM_AND_XYZ_INPUT_COORDINATES')
        input_cache[cache_key]=coords
    coords=input_cache[cache_key]
    if geometry['parent_geometry_id'] is not None:
        C.need(H.O.equal_numbers(coords,geometry['positions_A']) and geometry['actual_input_bundle_sha256']==row['input_bundle_sha256'],
            'ACTUAL_CHILD_INPUT_BITS_NOT_SECOND_PERTURBATION_OR_BASE')
    else:
        C.need(rule.get('native_parent_input_print_relation')=='ROOT_MODEL_VERIFIED_ORIGINAL_SOURCE_RENDER',
            'NATIVE_PARENT_PRINTING_RELATION_EXPLICIT_NOT_TOLERANCE_OVERRIDE')
    return gid,{'kind':mode,'base_geometry_id':base['geometry_id'],'target_geometry_id':gid,
        'target_geometry_sha256':geometry['geometry_sha256'],'source_input_file_hashes_exact':True,'source_input_bundle_sha256':row['input_bundle_sha256'],
        'source_input_bundle_hash_exact':True,'original_protocol_reference':pref,'original_seed_record_id':record,
        'field_frame_acceptance_reference':rule['frame_acceptance_reference'],'source_values_not_transformed':True}


def materialize(plan,proof,output,budget,authority):
    """Only actual Root/Model field policies determine each physical binding."""
    source=C.meta(plan['source_release_reference']);policy=C.meta(plan['field_geometry_policy_reference'])
    C.need(policy['status']=='MODEL_DATA_FIELD_GEOMETRY_BINDINGS_FROZEN' and policy['model_confirmation'] and policy['data_confirmation'],
        'PER_FIELD_ACTUAL_GEOMETRY_POLICY_REQUIRED_NOT_TASK_VIEW_HEURISTIC')
    fmap=I.json_body(plan['field_map_reference'],authority,budget.check);ids={f['field_key']:f['field_id'] for f in fmap}
    C.need(len(ids)==146 and set(ids)==set(policy['fields']),'ORIGINAL146_FIELD_IDS_EXACT_POLICY_COVERAGE')
    bytask={};protocols={};objects=H.sources()
    for key,rule in policy['fields'].items():
        C.need(ids[key]==rule['field_id'],'ORIGINAL_FROZEN_FIELD_ID_UNCHANGED');frame=C.meta(rule['frame_acceptance_reference'])
        C.need(frame['model_confirmation'] and frame['data_confirmation'] and str(frame['status']).endswith('ACCEPTED'),
            'ACTUAL_FIELD_UNIT_FRAME_BASIS_SIGN_ACCEPTANCE_NOT_INPUT_HASH_AS_OUTPUT_FRAME_PROOF')
        bytask.setdefault(rule['task'],[]).append((key,rule))
    for r in policy['package_protocol_references']:
        protocols[r['package_reference']['sha256']]=(C.meta(r['protocol_reference']),r['protocol_reference'])
    specs=list(I.jsonl(source['source_specification_reference'],authority,budget.check));files={}
    for spec in specs:
        if spec['kind']=='labels' and spec['geometry_source']=='pm7':
            r=C.reference(spec['file']);C.need(r in authority,'ALL_CLAIM_DATA_DECLARED');files.setdefault(r['path'],spec)
    db=sqlite3.connect(output/'claims.sqlite',uri=True);db.row_factory=sqlite3.Row;P.claim_schema(db)
    db.execute('ATTACH DATABASE ? AS geometry_source',(__import__('pathlib').Path(plan['_geometry_database_path']).as_uri()+'?mode=ro&immutable=1',))
    for table in ('full_geometries','actual_child_rows'):
        db.execute('CREATE TEMP VIEW '+table+' AS SELECT * FROM geometry_source.'+table)
    index=sqlite3.connect(__import__('pathlib').Path(source['canonical_index_reference']['path']).as_uri()+'?mode=ro&immutable=1',uri=True)
    index.execute('PRAGMA query_only=ON');index.execute('PRAGMA cache_size=-8192')
    observed={str(v):0 for v in ids.values()};unknown=0
    expected={str(k):v for k,v in policy['expected_Common_field_counts'].items()};unknown_path=output/'unknown_claims.DATA.jsonl';unknown_path.touch(exist_ok=False)
    try:
        for spec in files.values():
            ref=spec['file'];offset=0
            for batch in I.batches(ref,authority,budget.check,columns=spec['claim_columns'],batch_size=16):
                rows=batch.to_pylist();owners=lookup_batch(index,[r['record_id'] for r in rows])
                for row in rows:
                    number=offset;offset+=1;owner=owners.get(row['record_id'])
                    task=row.get('calc_type',spec.get('task'));row=dict(row,calc_type=task)
                    if classify_owner(row,owner,task not in ('D20','D3'))!='CANONICAL':continue
                    if db.execute('SELECT 1 FROM geometry_source.common_members WHERE molecule_id=?',(owner['molecule_id'],)).fetchone() is None:continue
                    row['total_atoms']=owner['total_atoms'];bindings=[];input_cache={}
                    for key,rule in bytask.get(task,[]):
                        try:
                            gid,evidence=claim_geometry(db,row,ref,number,rule,protocols,objects,plan['D5_components_reference'],input_cache)
                            policy_sha=hashlib.sha256(json.dumps({'rule':rule['binding_rule'],'frame':rule['frame_acceptance_reference']},sort_keys=True,separators=(',',':')).encode()).hexdigest()
                            bindings.append((ids[key],gid,policy_sha,evidence));observed[str(ids[key])]+=1
                        except Exception as exc:
                            unknown+=1;I.append(unknown_path,{'source_reference':C.reference(ref),'physical_row_index':number,'field_id':ids[key],
                                'reason_type':type(exc).__name__,'reason':str(exc),'unknown_not_bound_by_task_name':True})
                    if bindings:
                        cell={'source_path':ref['path'],'source_bytes':ref['bytes'],'source_sha':ref['sha256'],'physical_row_index':number,
                            'record_id':row['record_id'],'molecule_id':row['molecule_id'],'group_key':str(owner['job_id']),
                            'record_ordinal':owner['record_ordinal'],'task_code':TASKS[task],
                            'input_bundle_sha':row.get('input_bundle_sha256'),'input_file_sha_json':json.dumps(row.get('input_file_sha256'),sort_keys=True,separators=(',',':'))}
                        P.add_claims(db,cell,bindings)
                db.commit();budget.check()
        db.execute('DETACH DATABASE geometry_source')
        return P.close_claims(db,output/'claims.sqlite',output/'claims.json',plan,proof,expected,observed,unknown)
    except BaseException:
        db.close();raise
    finally:index.close()
