"""Original molecule body; only an explicit IO reader and verified native-Z seam."""
from __future__ import annotations
import hashlib,json,math,pathlib,struct
from workflows.data_v1_final.export.d5_inputs_builder_v1 import contract as C,io as I,geometry as G,build as Original
from workflows.data_v1_final.export.d5_inputs_builder_v1 import children as Child
O=Child.O;decode_evidence=Child.decode_evidence;coordinate_sha=Child.coordinate_sha
schemas=Original.schemas;encode=Original.encode;decode=Original.decode

def molecule(task,declared,check,objects,reader):
    native,science,common=objects;mid=task['molecule_id'];by={r['native_record_id']:r for r in task['ordinary_physical_rows'] if r['geometry_source']=='pm7'}
    hof,observations=reader.hof_values(task,declared,check);bases=[];errors=[];mol=numbers=graph=None;producer_orders=[]
    for pointer in task['records']:
        check();other,z,xyz=reader.native_record(pointer,native);sig=native.ordered_graph(other)
        if mol is None:mol,numbers,graph=other,z,sig
        import numpy as np
        C.need(np.array_equal(numbers,z) and graph==sig,'ORIGINAL_SOURCE_ATOM_ORDER_AND_GRAPH_ACROSS_ALL_PM7')
        rid=pointer['record_id'];row=dict(by[rid]);G.physical_key(row);value=hof.get(rid)
        if value is None or value['valid'] is not True:
            errors.append({'record_id':rid,'state':'UNKNOWN_CANONICAL_HOF','original_reason':value.get('reason') if value else 'CANONICAL_CELL_MISSING'})
            energy=None
        else:
            from workflows.data_v1_final.conformers.pm7_independent_cache32_v1.contract import validate_hof
            validate_hof(value);energy=float(value['value_kcal_mol'])
        row.update(parent_geometry_id=None,view_id=None,positions_A=xyz.tolist(),atomic_numbers=z.tolist(),
            geometry_sha256=common.geometry_sha(z,xyz),atom_order_sha256=hashlib.sha256(z.astype('<i8').tobytes()).hexdigest(),
            source_row_index=pointer['real_index'],source_bytes=None,source_sha256=None,order_energy=energy,
            energy_source='CANONICAL_PM7_B_REGISTRY60_KCAL_MOL',source_provenance_json=json.dumps(pointer,sort_keys=True),
            actual_input_origin='ORIGINAL_LMDB_RECORD_PER_PAYLOAD_SHA_NOT_RECONSTRUCTION')
        bases.append(row)
    C.need(mol is not None and len(bases)==task['expected_PM7_N'],'ALL_REAL_PM7_BASES_PRESERVED')
    for physical in task['ordinary_physical_rows']:
        if physical['geometry_source']!='uff_sprime':continue
        check();value,packet=reader.physical_row(physical,declared,check,atomic_numbers=numbers.tolist());row=dict(physical);G.physical_key(row)
        C.need(value['atomic_numbers']==numbers.tolist(),'ORIGINAL_UFF_NATIVE_ATOM_SEQUENCE_EQUALS_FIXED_SOURCE_GRAPH')
        xyz=value['coordinates'];geo=common.geometry_sha(numbers,xyz)
        C.need(hashlib.sha256(numbers.astype('<i8').tobytes()).hexdigest()==value['atom_order_sha256']
            and (not value.get('geometry_sha256') or geo==value['geometry_sha256']), 'ACTUAL_UFF_F64_COORDINATES_ATOM_SHA')
        energy=float(value['uff_energy_kcal_mol']);C.need(math.isfinite(energy),'ACTUAL_FINITE_UFF_ENERGY_NO_NATIVE_PM7_FALLBACK')
        if value.get('origin') in ('data_v1_fill_10N','data_v1_fill_retry1'):
            C.need(value['seed']==science.seed_for(mid,value['origin']=='data_v1_fill_retry1'),'ORIGINAL_SEED_FOR_GENERATED_EVENT')
        row.update(parent_geometry_id=None,view_id=None,native_record_id=None,positions_A=xyz,atomic_numbers=numbers.tolist(),
            geometry_sha256=geo,atom_order_sha256=value['atom_order_sha256'],order_energy=energy,energy_source='ACTUAL_UFF_KCAL_MOL',
            source_provenance_json=json.dumps(physical,sort_keys=True),actual_input_origin='ACTUAL_ORDINARY_SOURCE_ROW_NOT_N1_EXTRA')
        bases.append(row)
        if packet is not None:producer_orders.append({'source_reference':C.reference({'path':physical['source_path'],'bytes':physical['source_bytes'],'sha256':physical['source_sha256']}),
            'native_orders':packet.get('orders'),'native_kernel_rank_not_promoted_to_physical_random_identity':True})
    C.need(len({G.physical_key(r) for r in bases})==len(bases),'DISTINCT_REAL_TWO_SOURCE_PHYSICAL_IDENTITIES')
    orders=G.order_rows(mid,bases,mol,native,check) if not errors else []
    # Closure of cached original native handles uses the original file frame,
    # not a newly invented whole-LMDB SHA requirement.
    for path,frame in reader.NATIVE_FRAMES.items():C.need(I.reader.frame(pathlib.Path(path).lstat())==frame,'ALL_NATIVE_RECORD_FILE_FRAMES_STILL_STABLE')
    for path,(_,frame) in reader.SOURCE_FRAMES.items():C.need(I.reader.frame(pathlib.Path(path).lstat())==frame,'ALL_HASHED_ORDINARY_SOURCE_FRAMES_STILL_STABLE')
    identities=[]
    for row in bases:
        if row['geometry_source']!='uff_sprime':continue
        ns=row['identity_namespace'];C.need(ns in ('accepted_original_sprime','data_v1_fill'),'REAL_ORDINARY_AUDIT_NAMESPACE_NO_N1_EXTRA')
        identity={'namespace':ns,'source_conformer_id':row['source_conformer_id']} if ns=='accepted_original_sprime' else {
            'namespace':ns,'task_key':row['task_key'],'seed':row['seed'],'candidate_id':row['candidate_id']}
        identities.append({'molecule_id':mid,'geometry_id':row['geometry_id'],'physical_identity_json':json.dumps(identity,sort_keys=True,separators=(',',':'))})
    return {'schema':'D5_ORDINARY_MOLECULE_SOURCE_OBSERVATION_V1','molecule_id':mid,'logical_ordinal':task['logical_ordinal'],
        'bases':bases,'orders':orders,'atom_counts':[{'geometry_id':r['geometry_id'],'n_atoms':len(r['atomic_numbers'])} for r in bases],
        'canonical_HOF_observations':observations,'canonical_HOF_values':hof,'producer_native_order_provenance':producer_orders,
        'audit_identity':identities,
        'errors':errors,'status':'COMPLETE_BASE_AND_ORIGINAL_ORDERS' if not errors else 'UNKNOWN_HOLD_ALL_GEOMETRIES_RETAINED',
        'WHOLE_LMDB_SHA_NOT_ORIGINALLY_AVAILABLE_NOT_CLAIMED':True,'new_QM_UFF_calls':0,'D5_jointly_frozen':False}


def observed_call(row,base,declared,check,objects,protocol,evidence):
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
        for candidate in evidence.pair_rows(row['pairs_reference'],rid,declared,check):
            if candidate['record_id']==rid:
                C.need(pair is None,'ONE_EXACT_REAL_PREPARED_PAIR');pair=candidate
        C.need(pair is not None and pair['canonical_geometry_id']==base['geometry_id']
            and pair['conformer']['sprime_conf_idx']==base['sprime_conf_idx']
            and pair['molecule_id']==base['molecule_id'] and pair['source']['record_id']==base['native_anchor_record_id']
            and pair['uff_coordinate_sha256']==coordinate_sha(base['positions_A'])
            and pair['protocol_sha256']==row['protocol_reference']['sha256'],'EXACT_REAL_PPRIME_PAIR_PHYSICAL_PARENT_AND_SEED_RECORD')
        record=None
        for candidate in evidence.staging_rows(row['staging_reference'],rid,declared,check,pprime):
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
