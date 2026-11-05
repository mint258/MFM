"""Thin native-lexeme lineage and original parser/renderer diagnostic bindings."""
from __future__ import annotations
import ast,hashlib,importlib.util,inspect,json,math,pathlib,re,struct,sys,tempfile
from . import contract as C
FLOAT=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'
CHANNEL=r'[SPDF]-(?:SIGMA|PI|DELL|DELTA|DEL)'


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def binding(function):
    source=inspect.getsource(function);ast.parse(source)
    return {'module':function.__module__,'name':function.__name__,'source_path':inspect.getsourcefile(function),
        'function_source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'whole_source_reference':C.Q.pin(inspect.getsourcefile(function)),'function_object_called_directly':True}


def originals(index):
    # These paths contain only frozen sources; every file is already in the CPU proof.
    parser=module('_nb32_parser_'+str(index),C.WP5/'wp5_parser_v2.py')
    engine=module('_nb32_engine_'+str(index),C.WP5/'wp5_engine_v3.py')
    native=module('_nb32_native_'+str(index),C.NATIVE)
    legacy=module('_nb32_legacy_'+str(index),C.LEGACY)
    read=module('_nb32_vector_read_'+str(index),C.VECTOR/'read_outputs_v1.py')
    native.PARSER=parser  # Original documented parser binding; no function is replaced.
    return parser,engine,native,legacy,read


def equal_numbers(left,right):
    def bits(value):
        if isinstance(value,list):return [bits(v) for v in value]
        if isinstance(value,dict):return {k:bits(v) for k,v in value.items()}
        if type(value) is float:return struct.pack('>d',value).hex()
        return value
    return bits(left)==bits(right)


def sigma_tokens(text):
    """Only a lexical source locator; original function results must match in full."""
    begin=text.find('SIGMA-PI BOND-ORDER MATRIX')
    C.need(begin>=0,'NATIVE_SIGMA_PI_HEADER_MISSING')
    body=text[begin:].split('TOTAL ENERGY PARTITIONING')[0];keys=[];entries=[];offset=previous=0
    header=re.compile(r'^\s*(?:'+CHANNEL+r'\s*)+$')
    row=re.compile(r'^\s*('+CHANNEL+r')\s+([A-Z][a-z]?)\s+(\d+)\s+(.*)$')
    for local,line in enumerate(body.splitlines()):
        if header.fullmatch(line):offset+=previous;previous=len(re.findall(CHANNEL,line));continue
        hit=row.match(line)
        if hit is None:continue
        key=(int(hit[3])-1,hit[1])
        if key not in keys:keys.append(key)
        values=hit[4].split()
        if not all(re.fullmatch(FLOAT,t) for t in values):continue
        for col,token in enumerate(values,offset):
            if col<len(keys):
                other=keys[col]
                entries.append({'entry_ordinal':len(entries),'src_atom':key[0],'dst_atom':other[0],
                    'src_channel':key[1],'dst_channel':other[1],'native_numeric_token':token,
                    'source_line':text[:begin].count('\n')+local+1,'row_element_token':hit[2],
                    'native_row_atom_index_1based':hit[3],'native_column_slot':col,'validity':'TOKEN_OBSERVED_NOT_FINAL_MASK'})
    return entries


def sigma_evidence(text,natoms,parser,native,legacy):
    try:
        entries=sigma_tokens(text)
        C.need(len(entries)<=262144,'BOUNDED_R73_NATIVE_ENTRIES')
        pairs=[(i,j) for i in range(natoms) for j in range(i)]
        original=native.sparse_sigma_pi(text,pairs);unfiltered=legacy.sigma_pi_entries(text)
        derived=[{'atom_i':e['src_atom'],'basis_i':e['src_channel'],'atom_j':e['dst_atom'],
            'basis_j':e['dst_channel'],'value':parser.f(e['native_numeric_token'])} for e in entries]
        C.need(equal_numbers(derived,original) and equal_numbers(original,unfiltered),'R73_LEXEMES_AND_BOTH_ORIGINAL_PARSER_FUNCTIONS_MATCH')
        C.need(all(0<=e['src_atom']<natoms and 0<=e['dst_atom']<natoms for e in entries),'R73_NATIVE_ATOM_DOMAIN')
        return {'status':'ORIGINAL_NATIVE_DOUBLE_CHANNEL_DOMAIN_OBSERVED_PHYSICAL_AXES_UNKNOWN',
            'registry_id':73,'entries':entries,'original_entries':original,
            'native_domain':'ordered (atom_i,atom_j,(basis_i,basis_j)) plus original list entry ordinal',
            'same_atom_entries':sum(e['src_atom']==e['dst_atom'] for e in entries),
            'duplicate_keys_preserved':len(entries)-len({(e['src_atom'],e['dst_atom'],e['src_channel'],e['dst_channel']) for e in entries}),
            'AO_ATOMINDEX_used_as_basis_map':False,'entries_reduced_summed_or_deduplicated':False,
            'selection_scope':'all native printed entries; all atom pairs passed only to original sparse parser; not a new production cutoff',
            'unit':'UNKNOWN_NO_INDEPENDENT_NATIVE_UNIT_CONVENTION_ACCEPTANCE',
            'physical_basis_axes':'UNKNOWN_ORIGINAL_CHANNEL_STRINGS_ONLY',
            'original_functions':[binding(native.sparse_sigma_pi),binding(legacy.sigma_pi_entries)]}
    except Exception as exc:return {'status':'UNKNOWN','registry_id':73,'reason':type(exc).__name__+': '+str(exc)}


def quadrupole_tokens(text):
    C.need('molecular quadrupole (traceless):' in text,'R674_NATIVE_HEADER_MISSING')
    part=text.rsplit('molecular quadrupole (traceless):',1)[1]
    C.need(re.search(r'xx\s+xy\s+yy\s+xz\s+yz\s+zz',part) is not None,'R674_EXPLICIT_SIX_COMPONENT_HEADER')
    rows=list(re.finditer(r'(?m)^\s*full:\s*(.*)$',part))
    C.need(len(rows)==1,'R674_UNIQUE_NATIVE_FULL_ROW_REQUIRED');row=rows[0]
    tokens=row[1].split();C.need(len(tokens)==6 and all(re.fullmatch(FLOAT,t) for t in tokens),'R674_EXACT_SIX_NATIVE_TOKENS')
    return [{'component':c,'native_numeric_token':t,'entry_ordinal':i}
        for i,(c,t) in enumerate(zip(('xx','xy','yy','xz','yz','zz'),tokens))]


def quadrupole_evidence(text,parsed,parser,read):
    try:
        tokens=quadrupole_tokens(text);independent=read.xtb_quadrupole(text)
        values=[parser.f(e['native_numeric_token']) for e in tokens]
        C.need(equal_numbers(values,parsed.get('molecular_quadrupole_traceless_au'))
            and equal_numbers(values,independent['six_components_au']),'R674_ORIGINAL_PARSER_AND_RAW_SIX_VALUES_BITWISE_MATCH')
        return {'status':'ORIGINAL_NATIVE_SIX_COMPONENT_VALUES_OBSERVED_SIGN_AND_AXES_UNKNOWN','registry_id':674,
            'source_path':'values.molecular_quadrupole_traceless_au','component_order':['xx','xy','yy','xz','yz','zz'],
            'tokens':tokens,'original_vector_audit_result':independent,'original_function':binding(read.xtb_quadrupole),
            'declared_registry_unit_separate_from_validation':'e bohr^2; source field suffix au',
            'native_unit_convention':'UNKNOWN_NOT_ACCEPTED_FROM_FIELD_NAME',
            'charge_sign_convention':'UNKNOWN','tensor_axes':'UNKNOWN_NOT_ACCEPTED_FROM_GEOMETRY_MATCH_ALONE'}
    except Exception as exc:return {'status':'UNKNOWN','registry_id':674,'reason':type(exc).__name__+': '+str(exc)}


def input_coordinates(data,name,symbols,parse_float):
    lines=data.decode('utf-8','strict').splitlines();rows=[]
    if name=='input.xyz':
        C.need(len(lines)>=2 and lines[0].strip()==str(len(symbols)),'RECONSTRUCTED_XYZ_COUNT')
        for line in lines[2:]:
            if line.strip():
                t=line.split();C.need(len(t)==4,'EXACT_XYZ_TOKEN_SHAPE');rows.append((t[0],t[1:]))
    else:
        C.need(name=='input.mop' and len(lines)>=3,'EXACT_MOPAC_INPUT_NAME')
        for line in lines[3:]:
            if line.strip():
                t=line.split();C.need(len(t)==7 and t[2::2]==['1','1','1'],'EXACT_SINGLE_POINT_MOPAC_FLAGS')
                rows.append((t[0],[t[1],t[3],t[5]]))
    C.need([r[0] for r in rows]==symbols and all(re.fullmatch(FLOAT,t) for _,v in rows for t in v),'EXACT_INPUT_ATOM_ORDER_AND_NUMERIC_LEXEMES')
    return [[parse_float(t) for t in v] for _,v in rows]


def input_binding(rendered,expected_files,expected_bundle,bundle):
    actual=[{'name':n,'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(rendered.items())]
    C.need(actual==expected_files,'ORIGINAL_PER_INPUT_FILENAME_SHA_EXACT')
    data=[{'name':n,'data':b,'role':'input','byte_count':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in sorted(rendered.items())]
    C.need(hashlib.sha256(bundle(data)[0]).hexdigest()==expected_bundle,'ORIGINAL_CANONICAL_INPUT_BUNDLE_SHA_EXACT')
    return actual


def examine(files,base,item,meta,protocol,originals_set,archive_module,scratch_base):
    import numpy as np
    parser,engine,native,legacy,read=originals_set;task=item['calc_type'];symbols=base['symbols']
    recipe=next(t for t in protocol['tasks'] if t['name']==task)
    rendered=engine.render_inputs(recipe,{'symbols':symbols,'coords':base['row']['positions_A']},{'record_id':item['record_id']},protocol)
    input_checks=input_binding(rendered,meta['input_file_sha256'],meta['input_bundle_sha256'],archive_module.bundle)
    name='input.mop' if recipe['family']=='mopac' else 'input.xyz'
    coords=input_coordinates(rendered[name],name,symbols,parser.f)
    C.need(equal_numbers(coords,input_coordinates(rendered['input.xyz'],'input.xyz',symbols,parser.f)),'RENDERED_XYZ_AND_PROGRAM_INPUT_GEOMETRY_MATCH')
    text={f['name']:f['data'].decode('utf-8','replace') for f in files}
    # Full original output members already persist as DATA before this temporary copy.
    with tempfile.TemporaryDirectory(prefix='nb32_'+str(C.Q.ROOT.name)+'_'+str(__import__('os').getuid())+'_',dir=scratch_base) as temp:
        folder=pathlib.Path(temp)
        for f in files:
            with (folder/f['name']).open('xb') as stream:stream.write(f['data'])
        parsed=parser.parse_mopac(folder,symbols,reconstruct_mulliken=False) if recipe['family']=='mopac' else parser.parse_xtb(folder,symbols)
        context=parser.context();projected=parser.project_values(task,parsed)
    evidence={'input_binding':{'status':'HASH_RECONSTRUCTED_BYTE_EXACT_NOT_SAVED_ORIGINAL_BODY','file_checks':input_checks,
        'original_renderer':binding(engine.render_inputs),'original_seed_rule':binding(engine.perturb_seed),
        'original_protocol_seed':protocol['seed'],'perturb_seed':engine.perturb_seed(item['record_id'],protocol) if recipe.get('perturbed') else None,
        'reconstructed_program_coordinates_A':coords,'reconstructed_input_sha_bundle':meta['input_bundle_sha256'],
        'base_geometry_evidence':base['provenance']},'original_parser_values':parsed,'original_projected_values':projected,
        'original_parser_context':context,'original_parser_function':binding(parser.parse_mopac if recipe['family']=='mopac' else parser.parse_xtb),
        'native_field_final_masks':'NOT_CREATED','native_physical_axes':'UNKNOWN_NOT_FROZEN',
        'r73':sigma_evidence(text.get('input.out',''),len(symbols),parser,native,legacy) if recipe['family']=='mopac' else {'status':'NOT_APPLICABLE'},
        'r674':quadrupole_evidence(text.get('process.out',''),parsed,parser,read) if task=='xtb_singlepoint' else {'status':'NOT_APPLICABLE'}}
    try:
        raw=read.aux_arrays(text['input.aux'],len(symbols)) if recipe['family']=='mopac' else read.xtb_gradient(text['gradient'],symbols) if 'gradient' in text else None
        evidence['original_output_geometry_reader']=raw
        if raw is None:evidence['geometry_frame']={'status':'UNKNOWN_NATIVE_COORDINATES_NOT_EMITTED'}
        else:
            output=raw.get('ATOM_X_OPT:ANGSTROMS',{}).get('values') if recipe['family']=='mopac' else raw.get('coordinates_A')
            if output is None:evidence['geometry_frame']={'status':'UNKNOWN_NATIVE_COORDINATES_NOT_EMITTED'}
            else:
                if recipe['family']=='mopac':C.need(raw.get('ATOM_EL',{}).get('values')==symbols,'NATIVE_MOPAC_OUTPUT_ATOM_ORDER_MUST_BE_EXPLICIT')
                x=np.asarray(coords,dtype=np.float64);y=np.asarray(output,dtype=np.float64)
                C.need(x.shape==y.shape and np.isfinite(y).all(),'EXACT_OUTPUT_GEOMETRY_SHAPE_FINITE')
                evidence['geometry_frame']={'status':'COORDINATE_RESIDUAL_OBSERVED_NOT_PROPERTY_AXIS_ACCEPTANCE',
                    'max_abs_printed_coordinate_difference_A':float(np.max(np.abs(x-y))),
                    'exact_printed_coordinate_values_equal':equal_numbers(coords,output),
                    'rounding_evidence_is_original_reader_output_not_widened_QC':True,
                    'physical_tensor_or_channel_axes':'UNKNOWN','atom_remapping_or_fitting_performed':False}
    except Exception as exc:evidence['geometry_frame']={'status':'UNKNOWN','reason':type(exc).__name__+': '+str(exc)}
    return evidence,rendered
