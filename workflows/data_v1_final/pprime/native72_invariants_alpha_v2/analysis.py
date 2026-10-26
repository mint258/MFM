"""Finite invariants of existing recorded values, without fitting axes or changing gates."""
from __future__ import annotations
import hashlib,math,pathlib,struct,sys
from collections import Counter
from fractions import Fraction
from . import contract as C
sys.path.insert(0,str(C.OLD))
import precision as P
import math_v1 as M
for module,name in ((P,'precision.py'),(M,'math_v1.py')):
    P.need(pathlib.Path(module.__file__).absolute()==C.OLD/name,'EXACT_ORIGINAL_NUMERICAL_HELPER_LOCATION_REQUIRED')


def matrix(values,field):
    P.need(field in C.FIELDS and isinstance(values,list) and values,'KNOWN_NONEMPTY_VECTOR_FIELD_REQUIRED')
    rows=[values] if 'dipole' in field else values
    P.need(0<len(rows)<=C.SCOPE['maximum_atoms'] and all(isinstance(row,list) and len(row)==3 for row in rows),'BOUNDED_N_BY3_RECORDED_VECTOR_REQUIRED')
    P.need(all(type(value) in (int,float) and math.isfinite(value) for row in rows for value in row),'FINITE_RECORDED_BINARY64_REQUIRED')
    return [[Fraction.from_float(float(value)) for value in row] for row in rows]


def decimal(value):return P.exact_decimal(value)
def dot(a,b):return sum((x*y for x,y in zip(a,b)),Fraction())
def norms(x):return [dot(row,row) for row in x]
def maxabs(values):return max((abs(value) for value in values),default=Fraction())


def invariant_values(x):
    squared=norms(x);gram_hash=hashlib.sha256();gram_frob=Fraction();gram_max=Fraction()
    for row in x:
        for other in x:
            value=dot(row,other);gram_hash.update((decimal(value)+'\n').encode())
            gram_frob+=value*value;gram_max=max(gram_max,abs(value))
    try:approximate=math.hypot(*(float(value) for row in x for value in row))
    except OverflowError:approximate=None
    return {'rows':len(x),'components':3*len(x),'sum_squared_norms_exact':decimal(sum(squared,Fraction())),
        'minimum_row_squared_norm_exact':decimal(min(squared)),'maximum_row_squared_norm_exact':decimal(max(squared)),
        'norm_approximate_float64':approximate if approximate is not None and math.isfinite(approximate) else None,
        'gram_trace_exact':decimal(sum(squared,Fraction())),'gram_frobenius_squared_exact':decimal(gram_frob),
        'gram_max_abs_entry_exact':decimal(gram_max),'gram_matrix_exact_decimal_SHA256':gram_hash.hexdigest(),
        'gram_hash_encoding':'full row-major exact decimal values, each followed by LF',
        'full_gram_matrix_written':False,'equality_statement_scope':'EXACT_RECORDED_BINARY64_VALUES_ONLY_NOT_PHYSICAL_ERROR_CERTIFICATION'}


def pair_metrics(base,variant,rotation):
    P.need(len(base)==len(variant) and base,'SAME_RECORDED_VECTOR_ROW_COUNT_REQUIRED')
    r=[[Fraction.from_float(float(value)) for value in row] for row in rotation]
    P.need(len(r)==3 and all(len(row)==3 for row in r),'EXACT3_BY3_DECLARED_R_REQUIRED')
    residual=[variant[i][axis]-dot(row,r[axis]) for i,row in enumerate(base) for axis in range(3)]
    nb,nv=norms(base),norms(variant);gram_max=Fraction();gram_nonzero=0
    for i in range(len(base)):
        for j in range(len(base)):
            delta=dot(variant[i],variant[j])-dot(base[i],base[j]);gram_max=max(gram_max,abs(delta));gram_nonzero+=delta!=0
    return {'max_abs_declared_R_residual_exact':decimal(maxabs(residual)),
        'max_abs_row_squared_norm_difference_exact':decimal(maxabs(a-b for a,b in zip(nb,nv))),
        'sum_squared_norm_difference_exact':decimal(sum(nv,Fraction())-sum(nb,Fraction())),
        'gram_max_abs_difference_exact':decimal(gram_max),'gram_nonzero_recorded_entry_differences':gram_nonzero,
        'recorded_gram_exactly_equal':gram_nonzero==0,'any_new_scientific_tolerance_or_PASS':False,
        'interpretation':'NONZERO_EXACT_RECORDED_DIFFERENCES_INCLUDE_FLOAT_AND_PRINT_ERRORS; NO_CAUSE_OR_PHYSICAL_FRAME_PROOF_INFERRED'}


def frame_metadata(value):
    wanted=('status','supports_input_axes','atom_order_matches','max_abs_coordinate_difference_A',
        'proper_fit_RMSD_A','input_to_output_rotation','translation_A','centered_coordinate_rank',
        'rotation_identifiable','fit_determinant','coordinate_conversion_selected','source_artifact')
    out={key:value[key] for key in wanted if key in value}
    out.update(source='ORIGINAL_MAIN_FRAME_EVALUATION_RECORDED_METADATA',new_output_coordinates_read=False,
        actual_current_program_frame_independently_reestablished=False)
    return out


def recorded_frame_transport(base,variant,rotation):
    """Only chart algebra from old coordinate fits; no new fit or raw geometry."""
    if not (base.get('rotation_identifiable') is True and variant.get('rotation_identifiable') is True):
        return {'status':'UNKNOWN_NO_IDENTIFIABLE_OWN_OUTPUT_COORDINATE_FITS','new_output_coordinate_reads':0}
    def three(value):
        P.need(isinstance(value,list) and len(value)==3 and all(isinstance(row,list) and len(row)==3 for row in value),
            'RECORDED3_BY3_OUTPUT_COORDINATE_ROTATION_REQUIRED')
        return [[P.rational_float(x) for x in row] for row in value]
    q0,q1,r=three(base['input_to_output_rotation']),three(variant['input_to_output_rotation']),three(rotation)
    transported=[[sum((q1[i][j]*r[j][k]*q0[l][k] for j in range(3) for k in range(3)),Fraction()) for l in range(3)] for i in range(3)]
    return {'status':'DERIVED_ONLY_FROM_RECORDED_OUTPUT_COORDINATE_FITS',
        'column_rule':'Q_variant @ R @ Q_base.T',
        'output_chart_expected_rotation_exact':[[decimal(x) for x in row] for row in transported],
        'max_abs_difference_from_declared_input_R_exact':decimal(maxabs(transported[i][j]-r[i][j] for i in range(3) for j in range(3))),
        'vector_values_used_to_fit_rotation':False,'new_output_coordinate_reads':0,'scientific_frame_certification':False}


def case_links(report,original):
    links={}
    def add(case_id,group,arm):
        entry={'group':list(group),'arm':arm}
        P.need(case_id not in links or links[case_id]==entry,'CONFLICTING_RECORDED_CASE_IDENTITY');links[case_id]=entry
    for orbit in report['geometry_orbits']:
        add(orbit['base_case'],orbit['group'],'base');add(orbit['variant_case'],orbit['group'],'rotated')
    for item in report['translation_orbits']:
        add(item['variant_case'],[item['molecule_id'],item['geometry_source'],'xtb_singlepoint_origin_translation'],'translated')
    P.need(set(links)==set(original['measurements']) and len(links)==72,'EXACT72_CASE_IDENTITY_COVERAGE_REQUIRED')
    return links


def validate_inputs(report,original,config):
    P.need(report['schema']=='PPRIME_NATIVE72_READONLY_ALPHA_DIAGNOSIS_V2'
        and report['runtime']['job_id']=='1884773' and report['runtime']['endpoint']=='218.192.171.238:22'
        and report['runtime']['uid']==1264 and report['all72_inputs_closed'] is True and report['actual_cases_read']==72
        and report['case_read_errors']==[] and report['QM_or_UFF_calls']==0,'EXACT_CLOSED_EXISTING_DIAGNOSIS_REQUIRED')
    tests=report['synthetic_test_receipt']
    P.need(tests['status']=='PASS' and tests['tests_run']==4 and len(tests['successful_test_ids'])==4,'ORIGINAL_ACTUAL_FOUR_FIXTURES_REQUIRED')
    P.need(original['status']=='ACTUAL_FRAME_CONTRADICTION_REPORT_ROOT' and len(original['measurements'])==72
        and report['original_failures']==original['contradictions'] and len(report['original_failures'])==15
        and dict(Counter(row['field'] for row in original['contradictions']))==C.FIELDS
        and all(row['reason']=='VECTOR_NOT_COVARIANT' for row in original['contradictions']),'EXACT_ORIGINAL15_FAILS_REQUIRED')
    P.need(report['config']==original['config']==C.ORIGINAL_CONFIG
        and config['rotation_matrix']==M.ROTATION and config['maximum_atoms']==80
        and config['vector_tolerances']==report['original_all_predeclared_vector_tolerances'],
        'ORIGINAL_CONFIG_ROTATION_AND_TOLERANCES_REQUIRED')
    P.need(len(report['input_checks'])==72 and len({row['case_id'] for row in report['input_checks']})==72
        and all(row['all_actual_input_bindings_and_target_verified'] is True for row in report['input_checks']),
        'RECORDED_ALL72_ACTUAL_INPUT_BINDINGS_REQUIRED')
    P.need([row['original_failure'] for row in report['failures']]==original['contradictions']
        and all(row['original_failure_retained'] is True and row['original_frozen_check_reproduced'] is True
            and row['diagnosis_status']=='RESIDUAL_NOT_EXPLAINED_BY_NATIVE_PRINT_PROPAGATION' for row in report['failures']),
        'ORIGINAL_PRECISION_DIAGNOSIS_AND_FAILURES_MUST_REMAIN')
    links=case_links(report,original)
    P.need({row['case_id'] for row in report['input_checks']}==set(links),'INPUT_BINDING_AND_MEASUREMENT_CASE_SETS_DIFFER')
    return links


def case_analysis(item):
    case_id,measurement,link=item
    fields={}
    P.need(len(measurement['vectors'])<=4,'BOUNDED_VECTOR_FIELD_COUNT')
    for field,value in measurement['vectors'].items():fields[field]=invariant_values(matrix(value['values'],field))
    return {'case_id':case_id,**link,'fields':fields,'recorded_output_frame':frame_metadata(measurement['coordinates']),
        'unavailable_fields_not_synthesized':True,'new_raw_or_input_reads':0}


def rotations(report,original,config):
    old={(row['molecule_id'],row['geometry_source'],row['condition']):row for row in original['rotation_comparisons']}
    rows=[]
    for orbit in report['geometry_orbits']:
        key=tuple(orbit['group']);b=original['measurements'][orbit['base_case']];v=original['measurements'][orbit['variant_case']]
        fields={}
        for field in sorted(set(b['vectors'])&set(v['vectors'])):
            x,y=b['vectors'][field],v['vectors'][field]
            fresh=M.covariance(x['values'],y['values'],x['rounding_halfwidth'],y['rounding_halfwidth'],config['vector_tolerances'][field])
            fields[field]={'invariants':pair_metrics(matrix(x['values'],field),matrix(y['values'],field),config['rotation_matrix']),
                'original_check':old[key]['vector_covariance'][field],'same_frozen_covariance_from_recorded_vectors':fresh,
                'original_check_reproduced':fresh==old[key]['vector_covariance'][field]}
        rows.append({'group':list(key),'base_case':orbit['base_case'],'variant_case':orbit['variant_case'],'fields':fields,
            'recorded_input_coordinate_orbit':orbit,'input_coordinate_residual_recomputed_from_raw':False,
            'recorded_output_coordinate_chart_transport':recorded_frame_transport(b['coordinates'],v['coordinates'],config['rotation_matrix'])})
    return rows


def native_values(endpoint,field):
    P.need(endpoint['status']=='EXACT_NATIVE_VALUES_AND_UNITS_VERIFIED','ORIGINAL_EXACT_TOKEN_CHAIN_REQUIRED')
    selection=endpoint['native_selection'];details=endpoint['native_token_details'];factor=selection['factor_from_frozen_parser']
    expected_factor=M.AU_DIPOLE_TO_DEBYE if field=='xtb_dipole_Debye' else 1.
    P.need(float(factor).hex()==float(expected_factor).hex() and selection['status']=='UNIQUE_NATIVE_TOKEN_SELECTION','ORIGINAL_FIELD_CONVERSION_REQUIRED')
    P.need(0<len(details)<=240 and [row['selected_token_index'] for row in details]==list(range(len(details))),
        'BOUNDED_ORIGINAL_NATIVE_TOKEN_INDEX_SEQUENCE_REQUIRED')
    parsed=[];native=[];tokens=[]
    for row in details:
        value=float(row['token'].replace('D','E').replace('d','e'))*factor
        P.need(row['frozen_parser_conversion_factor_hex']==float(factor).hex()
            and P.same_numbers(value,row['parsed_value_field_units']),'TOKEN_TO_RECORDED_BINARY64_BINDING_CHANGED')
        parsed.append(row['parsed_value_field_units']);native.append(Fraction(P.number(row['token']))*Fraction.from_float(float(factor)));tokens.append(row['token'])
    floats=matrix(parsed if 'dipole' in field else [parsed[i:i+3] for i in range(0,len(parsed),3)],field)
    native=[native[i:i+3] for i in range(0,len(native),3)]
    return {'parsed':floats,'native':native,'tokens':tokens,'factor':factor}


def failures(report,original,config):
    rows=[];decoded={}
    for item in report['failures']:
        field=item['field'];key=tuple(item['original_failure']['group']);b=native_values(item['base'],field);v=native_values(item['variant'],field)
        for arm,values,case_id in (('base',b,item['base_case']),('rotated',v,item['variant_case'])):
            P.need(P.same_numbers([float(value) for row in values['parsed'] for value in row],
                original['measurements'][case_id]['vectors'][field]['values']),'DIAGNOSIS_TOKEN_VALUES_AND_ORIGINAL_VECTOR_VALUES_DIFFER')
        decoded[(key,field)]={'base':b,'rotated':v}
        rows.append({'original_failure':item['original_failure'],'original_failure_retained':True,'original_check':item['original_check'],
            'original_diagnosis_status':item['diagnosis_status'],
            'native_decimal_center_invariants':{'base':invariant_values(b['native']),'variant':invariant_values(v['native']),
                'pair':pair_metrics(b['native'],v['native'],config['rotation_matrix'])},
            'coordinate_evidence':item['geometry_orbit'],'cause':None,'quality_status':'ORIGINAL_FAIL_RETAINED'})
    return rows,decoded


def noisy_pairs(decoded,original,config):
    rows=[];found=set()
    old={(row['molecule_id'],row['geometry_source'],row['arm']):row for row in original['same_geometry_SP_gradient_controls']}
    for mid,geom in sorted(C.NOISY_GROUPS):
        key0=((mid,geom,'xtb_perturbed_gradient'),'xtb_dipole_Debye')
        key1=((mid,geom,'xtb_singlepoint_noisy_companion'),'xtb_dipole_Debye')
        P.need(key0 in decoded and key1 in decoded,'EXACT_THREE_FAILED_NOISY_TASK_PAIR_GROUPS_REQUIRED');found.add((mid,geom))
        for arm in ('base','rotated'):
            a=decoded[key0][arm];b=decoded[key1][arm]
            # Original JSON lexemes are in atomic units; do not invert the rounded Debye product.
            x=[float(token.replace('D','E').replace('d','e')) for token in a['tokens']]
            y=[float(token.replace('D','E').replace('d','e')) for token in b['tokens']]
            P.need(len(x)==len(y)==3,'DIPOLE_THREE_ORIGINAL_ATOMIC_UNIT_VALUES_REQUIRED')
            import numpy as np
            difference=float(np.max(np.abs(np.asarray(x)-np.asarray(y))))
            agreement={'pass':bool(np.isfinite(x).all() and np.all(np.abs(np.asarray(x)-np.asarray(y))<=config['same_geometry_dipole_atol_au'])),
                'max_abs_stored_raw_difference':difference}
            prior=old[(mid,geom,arm)]
            rows.append({'molecule_id':mid,'geometry_source':geom,'arm':arm,
                'original_same_geometry_control':prior,'same_frozen_control_from_original_native_tokens':agreement,
                'original_control_reproduced':agreement==prior['SP_gradient_raw_dipole_agreement'],
                'norm_and_Gram_in_recorded_field_units':pair_metrics(a['parsed'],b['parsed'],[[1.,0.,0.],[0.,1.,0.],[0.,0.,1.]]),
                'SP_own_output_coordinate_frame_known':False,'new_QM_or_raw_reads':0,'scientific_release':False})
    P.need(found==C.NOISY_GROUPS and len(rows)==6,'EXACT_THREE_GROUPS_SIX_SAME_ARM_COMPARISONS_REQUIRED')
    return rows
