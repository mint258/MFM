"""Original-native parser replay and descriptive domains; never physical acceptance."""
from __future__ import annotations
import collections,decimal,fractions,hashlib,pathlib,re,tempfile
from workflows.data_v1_final.export.native_body_frame32_v1 import observe as O
from workflows.data_v1_final.labels.lossless_projection_pilot_v1.projection import signature
from . import contract as C


def basis_indices(text):
    """Original first-seen (atom,channel) print/parser slots, expressly not AO indices."""
    start=text.find('SIGMA-PI BOND-ORDER MATRIX');C.need(start>=0,'NATIVE_SIGMA_PI_HEADER_MISSING')
    body=text[start:].split('TOTAL ENERGY PARTITIONING')[0];keys=[];lookup={};result=[];offset=previous=0;block=-1
    header=re.compile(r'^\s*(?:'+O.CHANNEL+r'\s*)+$')
    row=re.compile(r'^\s*('+O.CHANNEL+r')\s+([A-Z][a-z]?)\s+(\d+)\s+(.*)$')
    for line_number,line in enumerate(body.splitlines(),text[:start].count('\n')+1):
        if header.fullmatch(line):offset+=previous;previous=len(re.findall(O.CHANNEL,line));block+=1;continue
        hit=row.match(line)
        if hit is None:continue
        key=(int(hit[3])-1,hit[1])
        if key not in lookup:lookup[key]=len(keys);keys.append(key)
        values=hit[4].split()
        if not all(re.fullmatch(O.FLOAT,t) for t in values):continue
        for column,token in enumerate(values,offset):
            if column<len(keys):
                other=keys[column]
                result.append({'entry_ordinal':len(result),'atom_i':key[0],'atom_j':other[0],
                    'basis_i':key[1],'basis_j':other[1],'source_native_row_basis_slot':lookup[key],
                    'source_native_column_basis_slot':column,'source_print_block':block,'source_line':line_number,
                    'native_numeric_token':token,'AO_index_or_global_xyz_map':False})
    return keys,result


def r73(text,stored,natoms,objects,registry_fields,recipe):
    parser,engine,native,legacy,read=objects
    relevant=[f for f in registry_fields if f['source_path']=='values.sigma_pi_entries']
    enabled=any(f['status']=='enabled' for f in relevant)
    result={'related_registry_fields':relevant,'registry_enabled_for_this_condition':enabled,
        'PI_keyword_present':bool(re.search(r'\bPI\b',recipe.get('keywords') or '')),
        'unit_and_physical_axis_acceptance':'UNKNOWN_REQUIRES_OFFICIAL_CALL_CHAIN_AND_MODEL_REVIEW',
        'basis_domain':'original pair-dependent printed channel strings; never AO_ATOMINDEX or global px/py/xyz'}
    if recipe['family']!='mopac':return {**result,'state':'NOT_APPLICABLE_NON_MOPAC_CONDITION'}
    fresh=O.sigma_evidence(text,natoms,parser,native,legacy)
    result['original_selection_status']=fresh['status'];result['prior_B_status']=stored['status']
    if fresh['status']=='UNKNOWN':
        return {**result,'state':'SOURCE_REGISTRY_NA_AND_NATIVE_HEADER_NOT_EMITTED' if relevant and not enabled
            and not result['PI_keyword_present'] else 'UNKNOWN_NATIVE_R73_TOKEN_OR_PARSER_SELECTION',
            'reason':fresh.get('reason'),'prior_B_reason':stored.get('reason'),'raw_header_present':'SIGMA-PI BOND-ORDER MATRIX' in text}
    keys,locators=basis_indices(text);tokens=O.sigma_tokens(text)
    C.need(len(locators)==len(tokens)==len(fresh['original_entries']),'R73_COMPLETE_ORIGINAL_ENTRY_ORDINALS')
    for loc,token,entry in zip(locators,tokens,fresh['original_entries']):
        C.need((loc['atom_i'],loc['atom_j'],loc['basis_i'],loc['basis_j'],loc['native_numeric_token'])
            ==(token['src_atom'],token['dst_atom'],token['src_channel'],token['dst_channel'],token['native_numeric_token'])
            and (entry['atom_i'],entry['atom_j'],entry['basis_i'],entry['basis_j'])
            ==(loc['atom_i'],loc['atom_j'],loc['basis_i'],loc['basis_j']), 'R73_INDEX_LOCATOR_MATCHES_ORIGINAL_LEXEME_AND_BOTH_PARSERS')
    C.need(stored['status']!='UNKNOWN' and O.equal_numbers(fresh['original_entries'],stored['original_entries'])
        and fresh['entries']==stored['entries'],'FRESH_R73_NATIVE_VALUES_AND_LEXEMES_EXACT_TO_B')
    counts=collections.Counter((r['atom_i'],r['atom_j'],r['basis_i'],r['basis_j']) for r in locators)
    return {**result,'state':'ORIGINAL_DOUBLE_CHANNEL_DOMAIN_AND_FLOAT64_VALUES_EXACT',
        'native_entries':fresh['original_entries'],'native_entry_locators':locators,
        'first_seen_native_print_keys':[[a,b] for a,b in keys],
        'row_column_slot_is_derived_print_locator_not_physical_AO_map':True,
        'native_entries_count':len(locators),'same_atom_entries':sum(r['atom_i']==r['atom_j'] for r in locators),
        'same_atom_different_channel_entries':sum(r['atom_i']==r['atom_j'] and r['basis_i']!=r['basis_j'] for r in locators),
        'duplicate_native_keys_preserved':sum(n-1 for n in counts.values()),
        'channel_pair_counts':[[a,b,n] for (a,b),n in sorted(collections.Counter((r['basis_i'],r['basis_j']) for r in locators).items())],
        'atom_index_pair_counts':[[a,b,n] for (a,b),n in sorted(collections.Counter((r['atom_i'],r['atom_j']) for r in locators).items())],
        'first_seen_slots_onsite_duplicates_and_original_list_order_retained':True}


def trace(tokens,parse_float):
    C.need(len(tokens)==6 and [r['component'] for r in tokens]==['xx','xy','yy','xz','yz','zz'],'EXACT_R674_SIX_SEQUENCE_BEFORE_TRACE')
    values=[]
    for row in tokens:
        text=row['native_numeric_token'];C.need(type(text) is str and len(text)<=128,'BOUNDED_NATIVE_DECIMAL_TOKEN')
        value=decimal.Decimal(text.replace('D','E').replace('d','e'))
        C.need(value.is_finite() and abs(value.as_tuple().exponent)<=1000,'FINITE_NATIVE_DECIMAL_EXPONENT')
        values.append(fractions.Fraction(value))
    diagonal=values[0]+values[2]+values[5]
    floats=[parse_float(r['native_numeric_token']) for r in tokens];binary=(floats[0]+floats[2])+floats[5]
    return {'native_decimal_trace_numerator':str(diagonal.numerator),'native_decimal_trace_denominator':str(diagonal.denominator),
        'native_decimal_trace_exactly_zero':diagonal==0,'parser_binary64_left_fold_trace':binary,
        'parser_binary64_trace_hex':binary.hex(),'no_trace_subtraction_or_tensor_projection_performed':True,
        'trace_is_descriptive_no_new_tolerance_or_physical_acceptance':True}


def geometry(files,coords,symbols,recipe,read,stored):
    import numpy as np
    text={f['name']:f['data'].decode('utf-8','replace') for f in files}
    if recipe['family']=='mopac':
        raw=read.aux_arrays(text.get('input.aux',''),len(symbols));output=raw.get('ATOM_X_OPT:ANGSTROMS',{}).get('values')
        if output is not None:C.need(raw.get('ATOM_EL',{}).get('values')==symbols,'MOPAC_NATIVE_OUTPUT_ATOM_ORDER')
    elif 'gradient' in text:raw=read.xtb_gradient(text['gradient'],symbols);output=raw.get('coordinates_A')
    else:raw=output=None
    if output is None:return {'state':'NATIVE_COORDINATES_NOT_EMITTED_INPUT_BYTES_BOUND_PROPERTY_AXES_UNKNOWN',
        'reason':'original AUX/gradient reader has no coordinate block for this condition','prior_B_geometry_state':stored['geometry_frame']['status'],
        'unit_sign_property_axes':'UNKNOWN','native_coordinate_frame_PASS_claimed':False}
    x=np.asarray(coords,dtype=np.float64);y=np.asarray(output,dtype=np.float64)
    C.need(x.shape==y.shape and x.ndim==2 and x.shape[1]==3 and np.isfinite(y).all(),'FINITE_SAME_NATIVE_GEOMETRY_SHAPE')
    delta=y-x;residual=float(np.max(np.abs(delta)))
    C.need(O.equal_numbers(raw,stored['original_output_geometry_reader']) and residual==stored['geometry_frame']['max_abs_printed_coordinate_difference_A'],
        'FRESH_ORIGINAL_GEOMETRY_READER_AND_B_RESIDUAL_EXACT')
    hypotheses={}
    for name,rows in raw.get('coordinate_conversion_hypotheses_A',{}).items():
        hypotheses[name]={'max_abs_residual_A':float(np.max(np.abs(np.asarray(rows,dtype=np.float64)-x))),
            'original_conversion_hypothesis_not_chosen_as_physical_truth':True}
    return {'state':'DIRECT_PRINTED_COORDINATE_COMPARISON_OBSERVED_PROPERTY_AXES_UNKNOWN','original_reader_output':raw,
        'coordinate_difference_A':delta.tolist(),'max_abs_difference_A':residual,'float64_coordinates_exactly_equal':O.equal_numbers(coords,output),
        'conversion_hypotheses':hypotheses,'prior_B_geometry_state':stored['geometry_frame']['status'],
        'atom_remapping_rotation_fitting_tolerance_change_performed':False,'native_property_axes':'UNKNOWN_NOT_PROVED_BY_COORDINATE_AGREEMENT'}


def examine(value,raw_files,input_files,objects,registry,protocol,scratch):
    parser,engine,native,legacy,read=objects;key=value['key'];calc=key['calc_type'];meta=value['original_raw_metadata'];prior=value['native_evidence']
    recipe=next(t for t in protocol['tasks'] if t['name']==calc);inputs={f['name']:f['data'] for f in input_files}
    lines=inputs['input.xyz'].decode('utf-8','strict').splitlines();symbols=[line.split()[0] for line in lines[2:] if line.strip()]
    C.need(len(symbols)==value['owner']['total_atoms'] and len(symbols)>0,'ORIGINAL_INPUT_XYZ_EXACT_SYMBOL_COUNT')
    coords=O.input_coordinates(inputs['input.xyz'],'input.xyz',symbols,parser.f)
    program='input.mop' if recipe['family']=='mopac' else 'input.xyz'
    C.need(O.equal_numbers(coords,O.input_coordinates(inputs[program],program,symbols,parser.f))
        and O.equal_numbers(coords,prior['input_binding']['reconstructed_program_coordinates_A']),'SAVED_INPUT_BUNDLE_AND_B_RENDERED_COORDINATE_BITS_EXACT')
    actual=[{'name':name,'sha256':hashlib.sha256(body).hexdigest()} for name,body in sorted(inputs.items())]
    C.need(actual==meta['input_file_sha256']==prior['input_binding']['file_checks'],'ALL_ORIGINAL_RENDER_INPUT_FILENAME_SHA_EXACT')
    with tempfile.TemporaryDirectory(prefix='native_summary_record_',dir=scratch) as directory:
        folder=pathlib.Path(directory)
        for f in raw_files:
            with (folder/f['name']).open('xb') as stream:stream.write(f['data'])
        parsed=parser.parse_mopac(folder,symbols,reconstruct_mulliken=False) if recipe['family']=='mopac' else parser.parse_xtb(folder,symbols)
        context=parser.context();projected=parser.project_values(calc,parsed)
    exact=signature(parsed)==signature(prior['original_parser_values']) and signature(projected)==signature(prior['original_projected_values'])
    C.need(exact,'FULL_ORIGINAL_NATIVE_PARSER_VALUES_AND_TASK_PROJECTION_BITWISE_EXACT_TO_B')
    fields=[{k:f.get(k) for k in ('field_key','registry_id','task','source_path','component','status','unit','geometry_context')}
        for f in registry['fields'] if f['task']==calc]
    text={f['name']:f['data'].decode('utf-8','replace') for f in raw_files}
    sigma=r73(text.get('input.out',''),prior['r73'],len(symbols),objects,fields,recipe)
    if calc=='xtb_singlepoint':
        q=O.quadrupole_evidence(text.get('process.out',''),parsed,parser,read)
        C.need(q['status']!='UNKNOWN' and q['tokens']==prior['r674']['tokens'],'R674_NATIVE_SIX_LEXEMES_EXACT_TO_B')
        quadrupole={**q,'trace_observation':trace(q['tokens'],parser.f),'native_order':['xx','xy','yy','xz','yz','zz'],
            'unit_sign_axis_acceptance':'UNKNOWN_CALL_CHAIN_AND_MODEL_REVIEW_PENDING'}
    else:quadrupole={'status':'NOT_APPLICABLE_TO_THIS_REGISTRY_CONDITION'}
    geom=geometry(raw_files,coords,symbols,recipe,read,prior)
    return {'key':key,'owner':value['owner'],'input_binding':{'state':'ALL_ORIGINAL_INPUT_MEMBER_SHA_BUNDLE_SHA_AND_B_COORDINATE_BITS_EXACT',
        'original_input_file_hashes':actual,'original_input_bundle_sha256':meta['input_bundle_sha256'],'program_coordinates_A':coords,'symbols':symbols},
        'fresh_original_parser_values':parsed,'fresh_original_parser_context':context,'original_parser_and_projection_exact_to_B':exact,
        'related_registry_fields':fields,'r73':sigma,'r674':quadrupole,'geometry':geom,
        'scientific_units_charge_sign_native_property_axes_accepted':False,'old_tolerances_modified':False,
        'D1_jointly_frozen':False,'new_QM_UFF_calls':0}
