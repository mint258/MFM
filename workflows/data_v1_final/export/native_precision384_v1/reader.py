"""Only retained1152 bodies; old parser f/readers, no engine/worker initialization."""
from __future__ import annotations
import hashlib,math,pathlib,sys
from workflows.data_v1_final.export.native_body_frame32_v1 import observe as O
from workflows.data_v1_final.export.native_frame_summary32_v1 import reader as I,analysis as OLD
from . import contract as C,precision as P


def originals(index):
    for path in (C.S.B.WP5,C.S.B.VECTOR):
        if str(path) not in sys.path:sys.path.insert(0,str(path))
    legacy=O.module('_np384_pure_legacy_'+str(index),C.S.B.LEGACY)
    read=O.module('_np384_original_read_'+str(index),C.S.B.VECTOR/'read_outputs_v1.py')
    archive=O.module('_np384_original_archive_'+str(index),C.S.B.WP5/'wp5_archive_v5.py')
    numeric=sys.modules['math_v1']
    C.need(pathlib.Path(numeric.__file__).absolute()==C.S.B.VECTOR/'math_v1.py'
        and read.BOHR_TO_A==numeric.BOHR_TO_A==0.529177210903,'EXACT_ORIGINAL_READER_AND_CONVERSION_SOURCE')
    C.need(pathlib.Path(archive.A.__file__).absolute()==C.S.B.WP5/'wp5_archive_v4.py'
        and archive.unbundle is archive.A.unbundle,'ORIGINAL_WP5_V5_ALIAS_CALLS_ORIGINAL_V4_UNBUNDLE')
    return legacy,read,archive


def examine(row,references,check,objects,protocol):
    legacy,read,archive=objects;value,inputref=I.evidence(row,references,check)
    C.need(inputref==row['input_reference'] and value['key']==row['key'],'ACTUAL_PREPARED_KEY_INPUT_BINDING')
    raw=I.read(row['raw_reference'],references,check,C.S.B.RAW_CAP);outputs,manifest=archive.unbundle(raw)
    meta=value['original_raw_metadata'];prior=value['native_evidence']
    C.need(manifest==meta['output_file_manifest'],'COMPLETE_ORIGINAL_RAW_MEMBER_MANIFEST')
    encoded=I.read(inputref,references,check,8<<20);inputs,_=archive.unbundle(encoded)
    C.need(hashlib.sha256(encoded).hexdigest()==meta['input_bundle_sha256'],'EXACT_ORIGINAL_INPUT_BUNDLE_SHA')
    for f in [*outputs,*inputs]:
        path=pathlib.PurePosixPath(f['name']);C.need(path.name==str(path) and f['byte_count']<=C.S.B.MEMBER_CAP,'SAFE_FULL_RETAINED_MEMBER')
    inp={f['name']:f['data'] for f in inputs};text={f['name']:f['data'].decode('utf-8','replace') for f in outputs}
    checks=[{'name':name,'sha256':hashlib.sha256(body).hexdigest()} for name,body in sorted(inp.items())]
    C.need(checks==meta['input_file_sha256']==prior['input_binding']['file_checks'],'ALL_ORIGINAL_PROGRAM_INPUT_HASHES')
    symbols=[line.split()[0] for line in inp['input.xyz'].decode('utf-8','strict').splitlines()[2:] if line.strip()]
    C.need(len(symbols)==value['owner']['total_atoms'],'EXACT_ORIGINAL_ATOM_COUNT')
    recipe=next(t for t in protocol['tasks'] if t['name']==row['calc_type'])
    name='input.mop' if recipe['family']=='mopac' else 'input.xyz'
    coords=O.input_coordinates(inp[name],name,symbols,legacy.f)
    C.need(O.equal_numbers(coords,O.input_coordinates(inp['input.xyz'],'input.xyz',symbols,legacy.f))
        and O.equal_numbers(coords,prior['input_binding']['reconstructed_program_coordinates_A']),'ORIGINAL_INPUT_COORDINATE_BINARY64_BITS')
    itokens=P.input_tokens(inp[name],name,symbols)
    geometry=OLD.geometry(outputs,coords,symbols,recipe,read,prior)
    coordinate={'state':geometry['state'],'native_unit_sign_origin_property_axes_accepted':False}
    metrics=None
    if geometry['state']=='DIRECT_PRINTED_COORDINATE_COMPARISON_OBSERVED_PROPERTY_AXES_UNKNOWN':
        original=geometry['original_reader_output']
        if recipe['family']=='mopac':
            tokens=P.aux_tokens(text.get('input.aux',''),len(symbols));native=original['ATOM_X_OPT:ANGSTROMS']['values']
            C.need(tokens is not None,'NATIVE_AUX_TOKENS_EXIST_FOR_OBSERVED_READER')
            formulas=[('ORIGINAL_AUX_ANGSTROMS_DIRECT','1',1.0,native)]
        else:
            tokens=P.gradient_tokens(text['gradient'],symbols)
            native=original['coordinates_bohr']
            formulas=[('ORIGINAL_WP5_BOHR_TO_A','0.529177210903',read.BOHR_TO_A,original['coordinates_A']),
                ('FROZEN_LEGACY_AUTOAA_UNCHOSEN','0.52917726',0.52917726,original['coordinate_conversion_hypotheses_A']['xTB_legacy_autoaa_0.52917726'])]
        C.need(O.equal_numbers([[legacy.f(t) for t in line] for line in tokens],native),'LEXICAL_NATIVE_TOKENS_EQUAL_ORIGINAL_READER')
        intervals={};bounds={}
        for label,literal,factor,converted in formulas:
            cells=[]
            for atom,(xt,yt) in enumerate(zip(itokens,tokens)):
                check()
                for axis,(x,y) in enumerate(zip(xt,yt)):
                    cells.append({'atom':atom,'axis':axis,**P.conditional_residual(x,y,literal,factor,coords[atom][axis],converted[atom][axis])})
            intervals[label]=cells
            def numeric(key):
                return [float(P.F(int(r[key]['numerator']),int(r[key]['denominator']))) for r in cells]
            centers=numeric('source_decimal_converted_residual');lower=numeric('conditional_nearest_printing_lower');upper=numeric('conditional_nearest_printing_upper')
            bounds[label]={'components':len(cells),'conditional_interval_contains_zero_components':sum(r['conditional_interval_contains_zero'] for r in cells),
                'maximum_conditional_halfwidth_A':max(float(P.F(int(r['conditional_halfwidth']['numerator']),int(r['conditional_halfwidth']['denominator']))) for r in cells),
                'minimum_decimal_center_A':min(centers),'maximum_decimal_center_A':max(centers),
                'minimum_conditional_lower_A':min(lower),'maximum_conditional_upper_A':max(upper),
                'display_extrema_are_binary64_only_exact_rational_per_component_retained_in_DATA':True,
                'formula_was_selected_as_native_physical_truth':False}
        delta=[v for row0 in geometry['coordinate_difference_A'] for v in row0]
        metrics={'components':len(delta),'minimum_signed_residual_A':min(delta),'maximum_signed_residual_A':max(delta),
            'maximum_absolute_residual_A':max(abs(v) for v in delta),'sum_signed_residual_A':math.fsum(delta),
            'sum_squared_residual_A2':math.fsum(v*v for v in delta),'component_RMS_A':math.sqrt(math.fsum(v*v for v in delta)/len(delta)),
            'float64_exact':geometry['float64_coordinates_exactly_equal'],'formula_rounding_observations':bounds}
        coordinate.update(original_geometry_observation=geometry,input_coordinate_tokens=itokens,native_coordinate_tokens=tokens,
            conditional_residual_components=intervals,metrics=metrics,
            input_output_printing_mode_and_same_underlying_coordinate_are_unproved=True)
    else:
        coordinate.update(reason=geometry.get('reason'),state_is_technical_failure=False,
            unretained_native_coordinates_not_reconstructed=True)
    q=None
    if row['calc_type']=='xtb_singlepoint':
        tokens=O.quadrupole_tokens(text.get('process.out',''))
        C.need(tokens==prior['r674']['tokens'],'EXACT_OLD_B_R674_SIX_LEXEMES')
        original=read.xtb_quadrupole(text['process.out'])
        C.need(O.equal_numbers(original,prior['r674']['original_vector_audit_result']),'EXACT_ORIGINAL_R674_READER_VALUES')
        q=P.trace(tokens);q['original_six_parser_float64_hex']=[legacy.f(r['native_numeric_token']).hex() for r in tokens]
        q['original_binary64_trace_left_fold_hex']=((legacy.f(tokens[0]['native_numeric_token'])+legacy.f(tokens[2]['native_numeric_token']))+legacy.f(tokens[5]['native_numeric_token'])).hex()
    controls=P.controls(meta,inputs,outputs)
    return {'schema':'NATIVE_PRECISION384_PER_KEY_EVIDENCE_V1','position':row['position'],'key':row['key'],
        'retained_references':{k:row[k] for k in ('evidence_reference','raw_reference','input_reference')},
        'original_full_parser_replay_basis':'actual3953 same1152 parent; not replayed or initialized again',
        'original_input_bundle_and_coordinate_bits_verified':True,'coordinate':coordinate,'r674':q,'controls':controls,
        'all_old_values_and_masks_unchanged':True,'physical_acceptance':False,'D1_jointly_frozen':False,'new_QM_UFF_calls':0},metrics,q,controls
