"""Necessary orthogonal invariants under an explicit native-print rounding hypothesis."""
import hashlib
from fractions import Fraction
from native72_invariants_alpha_v2 import analysis as old
from . import contract as C
P=old.P


def interval_add(values):return (sum((x[0] for x in values),Fraction()),sum((x[1] for x in values),Fraction()))
def interval_multiply(a,b):
    candidates=[x*y for x in a for y in b];return min(candidates),max(candidates)
def interval_square(a):
    lo,hi=a;return (Fraction() if lo<=0<=hi else min(lo*lo,hi*hi),max(lo*lo,hi*hi))
def intersects(a,b):return max(a[0],b[0])<=min(a[1],b[1])
def encoded(a):return {'lower':P.exact_decimal(a[0]),'upper':P.exact_decimal(a[1])}
def row_norm(row):return interval_add([interval_square(x) for x in row])
def gram(a,b,same=False):return row_norm(a) if same else interval_add([interval_multiply(x,y) for x,y in zip(a,b)])


def native_intervals(endpoint,field):
    decoded=old.native_values(endpoint,field)  # Original frozen binary64 binding, units and token sequence.
    scale=Fraction.from_float(float(decoded['factor']));values=[]
    for token in decoded['tokens']:
        value,step,half=P.token_interval(token);center=Fraction(value)*scale;width=Fraction(half)*abs(scale)
        values.append((center-width,center+width))
    P.need(len(values)%3==0 and 0<len(values)<=240,'ORIGINAL_BOUNDED_3N_TOKEN_INTERVALS')
    rows=[values[i:i+3] for i in range(0,len(values),3)]
    return rows,decoded


def compare_intervals(base,variant):
    P.need(len(base)==len(variant) and 0<len(base)<=80 and all(len(row)==3 for row in [*base,*variant]),'FIXED_SAME_ORDER_VECTOR_ROWS')
    row_pairs=[];norm_disjoint=0
    for index,(a,b) in enumerate(zip(base,variant)):
        left,right=row_norm(a),row_norm(b);disjoint=not intersects(left,right);norm_disjoint+=disjoint
        row_pairs.append({'vector_index':index,'base_squared_norm_interval':encoded(left),'variant_squared_norm_interval':encoded(right),
            'intervals_disjoint':disjoint})
    total_base=interval_add([row_norm(row) for row in base]);total_variant=interval_add([row_norm(row) for row in variant])
    total_disjoint=not intersects(total_base,total_variant);bad=0;examples=[];digest=hashlib.sha256()
    for i in range(len(base)):
        for j in range(len(base)):
            a,b=gram(base[i],base[j],i==j),gram(variant[i],variant[j],i==j);disjoint=not intersects(a,b);bad+=disjoint
            digest.update((str(i)+'|'+str(j)+'|'+P.exact_decimal(a[0])+'|'+P.exact_decimal(a[1])+'|'+P.exact_decimal(b[0])+'|'+P.exact_decimal(b[1])+'\n').encode('ascii'))
            if disjoint and len(examples)<20:examples.append({'i':i,'j':j,'base_Gram_interval':encoded(a),'variant_Gram_interval':encoded(b)})
    excluded=bool(norm_disjoint or total_disjoint or bad)
    return {'round_to_nearest_decimal_hypothesis':'ORIGINAL_HALF_PRINT_STEP_NO_ADDED_ATOL_RTOL',
        'vector_rows':len(base),'row_squared_norm_intervals':row_pairs,'disjoint_row_norm_intervals':norm_disjoint,
        'base_total_squared_norm_interval':encoded(total_base),'variant_total_squared_norm_interval':encoded(total_variant),
        'total_squared_norm_intervals_disjoint':total_disjoint,
        'any_flat_component_permutation_or_sign_flip_excluded_under_print_model':total_disjoint,'Gram_entries_checked':len(base)**2,
        'disjoint_Gram_entries':bad,'first20_disjoint_Gram_examples':examples,'all_Gram_interval_encoding_SHA256':digest.hexdigest(),
        'all_Gram_encoding':'i|j|baseLower|baseUpper|variantLower|variantUpper LF, exact decimal',
        'rotation_only_plus_native_print_rounding_hypothesis_excluded':excluded,
        'diagnostic_status':'ROTATION_ONLY_PRINT_INTERVAL_MODEL_EXCLUDED' if excluded else 'MODEL_NOT_EXCLUDED_UNKNOWN_NOT_CERTIFIED',
        'fitted_axes_scale_or_permutation':False,'new_numeric_tolerance':False,'physical_or_SCF_cause_proven':False,
        'interval_overlap_proves_common_frame':False,'original_quality_status':'ORIGINAL_FAIL_RETAINED','scientific_PASS':False}


def failure_task(item):
    field=item['field'];P.need(item['original_failure']['field']==field,'SAME_ORIGINAL_FAILURE_FIELD')
    base,b= native_intervals(item['base'],field);variant,v=native_intervals(item['variant'],field)
    P.need(float(b['factor']).hex()==float(v['factor']).hex(),'SAME_FROZEN_FIELD_UNIT_FACTOR_BOTH_ARMS')
    P.need(item['geometry_orbit']['same_geometry_orbit_within_predeclared_coordinate_atol'] is True,'SAME_ORIGINAL_DECLARED_INPUT_GEOMETRY_ORBIT')
    result=compare_intervals(base,variant)
    return {'original_failure':item['original_failure'],'base_case':item['base_case'],'variant_case':item['variant_case'],
        'original_failure_retained':True,'original_check':item['original_check'],'original_geometry_orbit':item['geometry_orbit'],
        'base_native_tokens':b['tokens'],'variant_native_tokens':v['tokens'],
        'base_native_selection':item['base']['native_selection'],'variant_native_selection':item['variant']['native_selection'],
        'token_source_locations':{arm:[{k:entry[k] for k in ('source_artifact','source_line','selected_token_index','array_key','json_key','source_branch') if k in entry}
            for entry in item[arm]['native_token_details']] for arm in ('base','variant')},'frozen_parser_conversion_factor_hex':float(b['factor']).hex(),
        'native_print_halfwidth_rederived_from_original_lexemes':True,'interval_analysis':result,
        'hypothesis_limitations':['Printing nearest-rounding is a stated diagnostic hypothesis, not a certified bound on SCF/numerical errors.',
          'A disjoint necessary invariant excludes any shared orthogonal rotation under this print hypothesis; it does not identify why the native values differ.',
          'Overlap is not a proof of a common proper frame, correct atom mapping, correct origin, physical identity or adequate SCF accuracy.',
          'Dipole origin/charge behavior and SP own coordinate evidence are not independently established here.',
          'A common positive unit rescaling of both arms cannot restore disjoint invariant intervals; no arm-specific unit factor is fitted.'],
        'new_QM_UFF_calls':0,'raw_or_new_coordinate_reads':0,'scientific_PASS':False,'full_or2000_release':'HOLD'}


def validate(diagnosis,original,config):
    old.validate_inputs(diagnosis,original,config)
    P.need(len(diagnosis['failures'])==15,'EXACT15_EXISTING_FAILURE_ENDPOINTS')
    for item in diagnosis['failures']:
        field=item['field']
        for endpoint,case_key in ((item['base'],'base_case'),(item['variant'],'variant_case')):
            decoded=old.native_values(endpoint,field);actual=[float(x) for row in decoded['parsed'] for x in row]
            P.need(P.same_numbers(actual,original['measurements'][item[case_key]]['vectors'][field]['values']),
                'EXISTING_NATIVE_TOKEN_ENDPOINT_AND_ORIGINAL_VECTOR_EXACT_BINDING')
    return diagnosis['failures']
