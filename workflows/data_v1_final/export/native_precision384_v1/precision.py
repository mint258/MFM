"""Exact lexical arithmetic; every printing interval is explicitly conditional."""
from __future__ import annotations
import collections,decimal,fractions,math,re

F=fractions.Fraction
FLOAT=r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'
ORDER=('xx','xy','yy','xz','yz','zz')


def need(ok,code):
    if not ok:raise ValueError(code)


def decimal_token(text):
    need(type(text) is str and len(text)<=128 and re.fullmatch(FLOAT,text) is not None,'FINITE_BOUNDED_DECIMAL_LEXEME')
    d=decimal.Decimal(text.replace('D','E').replace('d','e'))
    need(d.is_finite() and abs(d.as_tuple().exponent)<=1000,'FINITE_BOUNDED_DECIMAL_EXPONENT')
    return F(d),F(decimal.Decimal((0,(1,),d.as_tuple().exponent)))


def rational(value):
    value=F(value);return {'numerator':str(value.numerator),'denominator':str(value.denominator)}


def conditional_residual(input_token,native_token,factor_literal,factor_float,input_float,output_float):
    x,qx=decimal_token(input_token);y,qy=decimal_token(native_token);c,_=decimal_token(factor_literal)
    need(c>0 and all(type(v) is float and math.isfinite(v) for v in (factor_float,input_float,output_float)),
        'POSITIVE_FROZEN_FACTOR_AND_FINITE_ORIGINAL_BINARY64')
    center=c*y-x;radius=(qx+c*qy)/2;lower=center-radius;upper=center+radius
    native_float=float(native_token.replace('D','E').replace('d','e'))
    native_parse=F.from_float(native_float)-y;input_parse=F.from_float(input_float)-x
    factor_repr=F.from_float(factor_float)-c
    exact_multiply=F.from_float(native_float)*F.from_float(factor_float)
    multiplication_round=F.from_float(output_float)-exact_multiply
    direct_exact=F.from_float(output_float)-F.from_float(input_float)
    direct_float=output_float-input_float
    need(math.isfinite(direct_float),'FINITE_ORIGINAL_BINARY64_DIRECT_SUBTRACTION')
    subtraction_round=F.from_float(direct_float)-direct_exact
    # Algebraic identity, not a bound on an unknown original physical coordinate.
    reconstructed=center+c*native_parse+y*factor_repr+native_parse*factor_repr+multiplication_round-input_parse
    need(reconstructed==direct_exact,'EXACT_BINARY64_PARSE_FACTOR_MULTIPLY_DECOMPOSITION')
    return {'input_token':input_token,'native_token':native_token,'factor_literal':factor_literal,
        'input_float64_hex':input_float.hex(),'native_parse_float64_hex':native_float.hex(),'factor_float64_hex':factor_float.hex(),
        'output_reader_float64_hex':output_float.hex(),'source_decimal_converted_residual':rational(center),
        'conditional_nearest_printing_lower':rational(lower),'conditional_nearest_printing_upper':rational(upper),
        'conditional_halfwidth':rational(radius),'conditional_interval_contains_zero':lower<=0<=upper,
        'input_parse_error':rational(input_parse),'native_parse_error':rational(native_parse),
        'conversion_factor_binary64_representation_error':rational(factor_repr),'conversion_multiplication_round_error':rational(multiplication_round),
        'binary64_direct_difference_exact_rational':rational(direct_exact),
        'binary64_subtracted_residual_float64_hex':direct_float.hex(),'binary64_subtraction_round_error':rational(subtraction_round),
        'assumptions':'Independent nearest-decimal input/output printing at literal last place; exact listed positive conversion; same underlying coordinate only a hypothesis',
        'unrounded_native_geometry_or_rounding_mode_proved':False,'physical_or_QC_pass':False}


def trace(tokens):
    need(type(tokens) is list and len(tokens)==6 and [r['component'] for r in tokens]==list(ORDER),'KEEP_EXACT_NATIVE_SIX_ORDER')
    values=[decimal_token(r['native_numeric_token'])[0] for r in tokens];t=values[0]+values[2]+values[5]
    eps=F(3,2000)  # Three independent half-units in the official f12.3 diagonal.
    lexical=all(re.fullmatch(r'[-+]?\d+\.\d{3}',r['native_numeric_token']) is not None for r in tokens)
    return {'native_tokens':tokens,'native_decimal_trace':rational(t),'exactly_zero':t==0,
        'official_f12_3_three_diagonal_nearest_rounding_bound':rational(eps),
        'all_six_tokens_have_three_fixed_decimals':lexical,
        'within_conditional_f12_3_trace_envelope':abs(t)<=eps if lexical else None,
        'theoretical_assumptions':'Exactly traceless unrounded full tensor plus nearest rounding of each diagonal to 0.001; finite-arithmetic residual is not bounded by this printing-only model',
        'underlying_trace_or_native_rounding_mode_proved':False,'trace_projected_or_original_values_modified':False,'QC_authorized':False}


def input_tokens(data,name,symbols):
    lines=data.decode('utf-8','strict').splitlines();result=[];seen=[]
    need(name in ('input.xyz','input.mop'),'KNOWN_ORIGINAL_INPUT_MEMBER')
    if name=='input.xyz':need(len(lines)>=2 and lines[0].strip()==str(len(symbols)),'EXACT_XYZ_COUNT')
    for line in lines[2 if name=='input.xyz' else 3:]:
        if not line.strip():continue
        row=line.split()
        if name=='input.xyz':need(len(row)==4,'XYZ_FOUR_COLUMNS');tokens=row[1:]
        else:need(len(row)==7 and row[2::2]==['1','1','1'],'ORIGINAL_MOPAC_SINGLE_POINT_COLUMNS');tokens=[row[1],row[3],row[5]]
        seen.append(row[0]);result.append(tokens)
        for token in tokens:decimal_token(token)
    need(seen==symbols,'EXACT_SYMBOL_ORDER_NO_REMAP');return result


def aux_tokens(text,natoms):
    # Lexical twin of the frozen aux_arrays header/continuation grammar; no
    # alternative geometry or guessed section is selected.
    header=re.compile(r'^\s*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?\s*=\s*(.*)$')
    active=False;expected=None;tokens=[];blocks=[]
    def finish():
        if active:
            need(expected==len(tokens)==3*natoms,'EXACT_AUX_COORDINATE_3N_TOKEN_COUNT');blocks.append(list(tokens))
    for line in text.splitlines():
        hit=header.match(line)
        if hit:
            finish();key,count,tail=hit.groups();active=key.strip()=='ATOM_X_OPT:ANGSTROMS';expected=int(count) if count is not None else None
            tokens=re.findall(FLOAT,tail) if active else []
        elif active and not line.lstrip().startswith('#'):tokens.extend(re.findall(FLOAT,line))
    finish();need(len(blocks)<=1,'DUPLICATE_AUX_COORDINATE_BLOCK_NOT_GUESSED')
    if not blocks:return None
    return [blocks[0][i:i+3] for i in range(0,len(blocks[0]),3)]


def gradient_tokens(text,symbols):
    rows=[line.split() for line in text.splitlines()]
    coordinates=[r for r in rows if len(r)==4 and r[-1].capitalize() in symbols]
    gradients=[r for r in rows if len(r)==3 and all(re.fullmatch(FLOAT,t) for t in r)]
    need(len(coordinates)==len(gradients)==len(symbols) and [r[3].capitalize() for r in coordinates]==symbols,
        'ORIGINAL_SINGLE_GRADIENT_BLOCK_AND_ATOM_ORDER')
    for row in coordinates:
        for token in row[:3]:decimal_token(token)
    return [row[:3] for row in coordinates]


def controls(metadata,input_files,output_files):
    inputs={r['name']:r for r in input_files};outputs={r['name']:r for r in output_files}
    found=[]
    control_names={'native.inp','xcontrol','xtb.inp','.xtbrc','xtbrc','.mopacrc','mopac.rc'}
    for origin,files in (('hash_bound_reconstructed_input',inputs),('retained_output_bundle',outputs)):
        for name,row in sorted(files.items()):
            if name.casefold() in control_names:
                found.append({'name':name,'origin':origin,'reference_member_sha256':row['sha256'],
                    'text':row['data'].decode('utf-8','strict'),'existence_means_historical_global_rc_known':False})
    argv=[];opaque=[]
    for key in ('argv','command','command_argv','execution_argv','command_line'):
        value=metadata.get(key)
        if type(value) is list and value and all(type(v) is str and len(v)<=65536 for v in value):argv.append({'key':key,'value':value})
        elif type(value) is str and len(value)<=65536:opaque.append({'key':key,'text':value,'split_or_interpreted_as_argv':False})
    fragments=[]
    for row in output_files:
        if not row['name'].lower().endswith(('.out','.log','.txt')):continue
        text=row['data'].decode('utf-8','replace')
        for number,line in enumerate(text.splitlines(),1):
            if re.search(r'center of mass|principal ax|\bcma\b|reorient|coordinate transformation|axis3',line,re.I):
                fragments.append({'member':row['name'],'line':number,'text':line})
    return {'retained_full_process_argv_candidates':argv,'retained_opaque_command_fields':opaque,
        'argv_candidate_field_name_does_not_prove_executed_argv':True,'recorded_recipe_keywords_or_args':metadata.get('keywords'),
        'recipe_keywords_are_not_full_executed_argv':True,'retained_control_members':found,'retained_preprocessing_text_fragments':fragments,
        'current_HOME_rc_or_environment_read':False,'global_or_unretained_rc_absence':'UNKNOWN_NOT_PROVED_BY_BUNDLE_OMISSION',
        'coordinate_preprocessing_axis_origin_state':'UNKNOWN_REQUIRES_COMPLETE_ACTUAL_CALL_BINDING_AND_SCIENTIFIC_REVIEW',
        'official_default_CMA_false_does_not_prove_actual_invocation_default':True}
