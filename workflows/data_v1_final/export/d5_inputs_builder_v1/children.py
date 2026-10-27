"""Actual source-call inputs only; unknown future/N1 views never become children."""
from __future__ import annotations
import hashlib,json,pathlib,struct,sys
from workflows.data_v1_final.export.native_body_frame32_v1 import observe as O
from workflows.data_v1_final.export.native_frame_summary32_v1.reader import decode_evidence
from . import contract as C,io as I,geometry as G,build as B


def sources():
    refs=C.source_check();wp5=pathlib.Path(refs['native_renderer']['path']).parent
    if str(wp5) not in sys.path:sys.path.insert(0,str(wp5))
    engine=O.module('_d5_inputs_original_wp5_render',pathlib.Path(refs['native_renderer']['path']))
    legacy=O.module('_d5_inputs_original_native_float',pathlib.Path(refs['native_legacy']['path']))
    archive=O.module('_d5_inputs_original_archive',pathlib.Path(refs['native_archive']['path']))
    pprime=O.module('_d5_inputs_original_pprime_staging',pathlib.Path(refs['pprime_common']['path']))
    return engine,legacy,archive,pprime


def coordinate_sha(coords):return hashlib.sha256(b''.join(struct.pack('<d',v) for row in coords for v in row)).hexdigest()


def observed_call(row,base,declared,check,objects,protocol):
    engine,legacy,archive,pprime=objects
    engine.load_protocol(protocol)  # Original exact twelve-task/geometry recipe validator.
    C.need(row['parent_geometry_id']==base['geometry_id'] and row['geometry_source']==base['geometry_source']
        and row['base_geometry_sha256']==base['geometry_sha256'] and row['base_atom_order_sha256']==base['atom_order_sha256'],
        'ACTUAL_PHYSICAL_PARENT_GRAPH_COORDINATE_BINDING_NOT_EQUAL_SHA_CLONE')
    rid,calc,execution=(row[k] for k in ('record_id','calc_type','execution_id'))
    if row['format']=='B32_LOSSLESS_INPUT_BINDING_V1':
        C.need(base['geometry_source']=='pm7' and rid==base['native_record_id'],'ORIGINAL_B32_IS_PM7_DOMAIN_NOT_UNVERIFIED_UFF_PROVIDER')
        saved=decode_evidence(I.body(row['evidence_reference'],declared,check,16<<20));meta=saved['original_raw_metadata']
        C.need(saved['key']=={'record_id':rid,'calc_type':calc,'execution_id':execution}
            and saved['original_raw_bundle_reference']==row['raw_reference']
            and saved['hash_reconstructed_input_DATA_reference']==row['input_reference'],'EXACT_REAL_B32_PRODUCER_TRIPLES_AND_KEY')
        _,manifest=archive.unbundle(I.body(row['raw_reference'],declared,check,8<<20))
        C.need(manifest==meta['output_file_manifest'],'COMPLETE_ORIGINAL_RAW_BUNDLE_EOF_SHA')
        original=I.body(row['input_reference'],declared,check,8<<20);archive.unbundle(original)
        C.need(hashlib.sha256(original).hexdigest()==meta['input_bundle_sha256'],'ACTUAL_B_INPUT_FULL_SHA')
        input_hashes=meta['input_file_sha256'];input_sha=meta['input_bundle_sha256'];prior=saved['native_evidence']['input_binding']
        pointer=json.loads(base['source_provenance_json'])
        C.need(meta['record_id']==rid and meta['molecule_id']==base['molecule_id'] and meta['calc_type']==calc
            and meta['execution_id']==execution and meta['source_payload_sha256']==pointer['record_payload_sha256'],
            'ORIGINAL_PM7_NATIVE_RECORD_AND_PAYLOAD_CALL_BINDING')
    elif row['format']=='PPRIME_FORMAL_STAGING_V1':
        C.need(base['geometry_source']=='uff_sprime','REAL_UFF_PPRIME_DOMAIN_ONLY')
        pair=None
        for candidate in I.jsonl(row['pairs_reference'],declared,check):
            if candidate['record_id']==rid:
                C.need(pair is None,'ONE_EXACT_REAL_PREPARED_PAIR');pair=candidate
        C.need(pair is not None and pair['canonical_geometry_id']==base['geometry_id']
            and pair['conformer']['sprime_conf_idx']==base['sprime_conf_idx']
            and pair['molecule_id']==base['molecule_id'] and pair['source']['record_id']==base['native_anchor_record_id']
            and pair['uff_coordinate_sha256']==coordinate_sha(base['positions_A'])
            and pair['protocol_sha256']==row['protocol_reference']['sha256'],'EXACT_REAL_PPRIME_PAIR_PHYSICAL_PARENT_AND_SEED_RECORD')
        record=None
        with I.held(row['staging_reference'],declared,check) as (_,fd,_):
            import os
            with os.fdopen(os.dup(fd),'rb') as stream:
                for line in stream:
                    check();C.need(len(line)<=I.ROW_CAP,'COMPLETE_ORIGINAL_STAGING_ROW_BOUND');candidate=pprime.read_staging(line)
                    if candidate['record_id']==rid:
                        C.need(record is None,'ONE_ACTUAL_PPRIME_STAGING_RECORD');record=candidate
        C.need(record is not None and record['canonical_geometry_id']==base['geometry_id'] and record['once_key']==pair['once_key']
            and record['molecule_id']==base['molecule_id'] and record['geometry']['uff_coordinate_sha256']==coordinate_sha(base['positions_A'])
            and O.equal_numbers(record['base_geometry']['positions_A'],base['positions_A'])
            and record['base_geometry']['z']==base['atomic_numbers'],'ACTUAL_EXECUTED_PPRIME_BASE_FULL_BITS_NOT_N1_PARENT_COLLECTION')
        ledger=I.json_body(row['once_ledger_reference'],declared,check,8<<20)
        C.need(ledger['schema']=='PPRIME_TWELVE_ONCE_ATTEMPT_V1' and ledger['key']==pair['once_key'] and ledger['record_id']==rid
            and ledger['canonical_geometry_id']==base['geometry_id'],'ORIGINAL_ACTUAL_PPRIME_ONCE_RECORD')
        details=[d for d in record['tasks'] if d['task']==calc];C.need(len(details)==1,'EXACT_ACTUAL_TASK_NO_RETRY_OR_LATEST_FALLBACK')
        detail=details[0];C.need(detail['raw_ref']['execution_id']==execution and detail['raw_ref']['record_id']==rid,'ACTUAL_TASK_EXECUTION_KEY')
        input_hashes=detail['provenance']['input_file_sha256'];input_sha=detail['provenance']['input_bundle_sha256'];prior=None
    else:raise ValueError('UNKNOWN_CHILD_EVIDENCE_FORMAT_NO_GUESSED_READER')
    from rdkit import Chem
    symbols=[Chem.GetPeriodicTable().GetElementSymbol(z) for z in base['atomic_numbers']]
    recipe=next(r for r in protocol['tasks'] if r['name']==calc)
    C.need(recipe.get('perturbed') is True,'ONLY_EXACT_RECIPE_PERTURBED_CALLS_ARE_DIRECT_CHILDREN')
    rendered=engine.render_inputs(recipe,{'symbols':symbols,'coords':base['positions_A']},{'record_id':rid},protocol)
    O.input_binding(rendered,input_hashes,input_sha,archive.bundle)
    name='input.mop' if recipe['family']=='mopac' else 'input.xyz';coords=O.input_coordinates(rendered[name],name,symbols,legacy.f)
    C.need(O.equal_numbers(coords,O.input_coordinates(rendered['input.xyz'],'input.xyz',symbols,legacy.f)),'ACTUAL_PROGRAM_AND_XYZ_INPUT_COORDINATES')
    if prior is not None:C.need(O.equal_numbers(coords,prior['reconstructed_program_coordinates_A']),'EXACT_PRIOR_B_RECONSTRUCTED_INPUT_BITS')
    gid,view=G.child_identity(base,rid,calc,execution,input_sha)
    result=dict(base,geometry_id=gid,parent_geometry_id=base['geometry_id'],view_id=view,positions_A=coords,order_energy=None,
        geometry_sha256=__import__('workflows.data_v1_final.pprime.geometry',fromlist=['geometry_hash']).geometry_hash(base['atomic_numbers'],coords),
        actual_input_bundle_sha256=input_sha,actual_protocol_sha256=row['protocol_reference']['sha256'],
        actual_input_origin='HASH_RECONSTRUCTED_BYTE_EXACT_FROM_ACTUAL_CALL_NOT_ORIGINALLY_SAVED_BODY',
        source_provenance_json=json.dumps({'actual_original_binding':row,'original_input_file_hashes':input_hashes,
            'original_perturb_seed':engine.perturb_seed(rid,protocol),'original_source_failure_status_not_used_to_drop_geometry':True},sort_keys=True))
    C.need(result['view_id']!='pprime_parent_expanded_v1' and G.physical_key(result)==G.physical_key(base),'CHILD_KEEPS_ITS_REAL_SOURCE_PHYSICAL_IDENTITY')
    return result


def run(plan,parent,out,budget):
    import sqlite3
    authority=C.meta(plan['actual_child_input_authority_reference']);declared=plan['data_references'];objects=sources()
    db=sqlite3.connect(out/'children.sqlite');db.execute('CREATE TABLE children(parent TEXT,gid TEXT UNIQUE,value BLOB)')
    bases={r['geometry_id']:r for r in I.rows(parent['table_references']['geometries'],declared,budget.check)}
    C.need(all(r['parent_geometry_id'] is None for r in bases.values()),'ONLY_CLOSED_ORDINARY_BASE_INPUT')
    seen=set();count=0
    try:
        for row in I.jsonl(authority['binding_index_reference'],declared,budget.check):
            key=(row['parent_geometry_id'],row['record_id'],row['calc_type'],row['execution_id']);C.need(key not in seen,'NO_DUPLICATE_OR_REDUCED_ACTUAL_CHILD_KEYS');seen.add(key)
            C.need(row['parent_geometry_id'] in bases,'CHILD_OUTSIDE_EXACT_BASE_RANGE')
            C.need(row['protocol_reference'] in authority['protocol_source_references'],'ACTUAL_REVIEWED_PROTOCOL_SOURCE')
            protocol=C.meta(row['protocol_reference']);result=observed_call(row,bases[row['parent_geometry_id']],declared,budget.check,objects,protocol)
            db.execute('INSERT INTO children VALUES(?,?,?)',(result['parent_geometry_id'],result['geometry_id'],B.encode(result)));db.commit();count+=1
        C.need(count==authority['actual_direct_child_count'],'FULL_ACTUAL_CENSUS_NO_MISSING_CALLS_OR_UNKNOWN_FILL')
        schema=B.schemas();tables={}
        def geometries():
            for gid in sorted(bases):
                yield bases[gid]
                for (raw,) in db.execute('SELECT value FROM children WHERE parent=? ORDER BY gid',(gid,)):yield B.decode(raw)
        tables['geometries']=I.parquet_rows(out/'geometries.parquet',geometries(),schema['geometries'],budget)
        for kind in ('orders','atom_counts','audit_identity'):
            tables[kind]=I.parquet_rows(out/(kind+'.parquet'),I.rows(parent['table_references'][kind],declared,budget.check),schema[kind],budget)
        def roster():
            for row in I.rows(parent['table_references']['roster'],declared,budget.check):
                row['child_count']=sum(db.execute('SELECT count(*) FROM children WHERE parent=?',(r['geometry_id'],)).fetchone()[0] for r in bases.values() if r['molecule_id']==row['molecule_id']);yield row
        tables['roster']=I.parquet_rows(out/'roster.parquet',roster(),schema['roster'],budget)
        return {'table_references':tables,'logical_range':parent['logical_range'],'molecules':parent['molecules'],'held_molecules':0,
            'table_domain':'BASE_WITH_ALL_ACTUAL_CHILDREN','all_actual_children_closed':True,'actual_direct_children':count,
            'full_typed_source_order_identity_parity':False,'unknown_axes_origin_or_property_units_not_relabelled_PASS':True}
    finally:db.close()
