"""Exact rational print-hypothesis checks and unchanged explicit geometry orbits."""
from __future__ import annotations
from decimal import Decimal
from fractions import Fraction
import math,re


def need(ok,message):
    if not ok:raise ValueError(message)


def number(token):
    need(isinstance(token,str) and len(token)<=128,'BOUNDED_NATIVE_TOKEN_REQUIRED')
    value=Decimal(token.replace('D','E').replace('d','e'))
    need(value.is_finite() and abs(value.as_tuple().exponent)<=1000,'FINITE_BOUNDED_NATIVE_TOKEN_REQUIRED')
    return value


def token_interval(token):
    value=number(token)
    exponent=value.as_tuple().exponent
    # Construct exactly; Decimal arithmetic must not inherit an ambient precision.
    step=Decimal((0,(1,),exponent))
    half=Decimal((0,(5,),exponent-1))
    return value,step,half


def rational_float(value):
    value=float(value);need(math.isfinite(value),'FINITE_FROZEN_FLOAT_REQUIRED')
    return Fraction.from_float(value)


def exact_decimal(value):
    """Exact terminating decimal for these rationals; no context rounding/division.

    Native decimals and binary64 values have only factors 2 and 5 in their
    denominators. All arithmetic below preserves that property.
    """
    value=Fraction(value);denominator=value.denominator;twos=fives=0
    while denominator%2==0:denominator//=2;twos+=1
    while denominator%5==0:denominator//=5;fives+=1
    need(denominator==1,'NONTERMINATING_RATIONAL_SERIALIZATION_NOT_ALLOWED')
    places=max(twos,fives)
    numerator=value.numerator*2**(places-twos)*5**(places-fives)
    if places==0:return str(numerator)
    digits=str(abs(numerator)).rjust(places+1,'0')
    return ('-' if numerator<0 else '')+digits[:-places]+'.'+digits[-places:]


def flatten(values):
    if isinstance(values,(tuple,list)):
        return [part for value in values for part in flatten(value)]
    return [values]


def same_numbers(left,right):
    import struct
    try:
        a,b=flatten(left),flatten(right)
        return len(a)==len(b) and all(math.isfinite(float(x)) and math.isfinite(float(y))
            and struct.pack('>d',float(x))==struct.pack('>d',float(y)) for x,y in zip(a,b))
    except (TypeError,ValueError,OverflowError):return False


def token_values(entries,factor,parse_float):
    converted=[];details=[];scale=rational_float(factor)
    for entry in entries:
        value,step,half=token_interval(entry['token'])
        actual=parse_float(entry['token'])*factor
        need(math.isfinite(actual),'NONFINITE_TOKEN_CONVERSION')
        converted.append(actual)
        details.append(dict(entry,step_native=str(step),halfwidth_native=str(half),
            parsed_value_field_units=actual,halfwidth_field_units=exact_decimal(Fraction(half)*abs(scale)),
            frozen_parser_conversion_factor_hex=float(factor).hex()))
    return converted,details


def propagate_native(entries_base,entries_variant,factor,rotation,parsed_base,parsed_variant):
    """Exact |R|epsilon_base+epsilon_variant under round-to-nearest-decimal hypothesis.

    Fraction(Decimal(token)) uses the original lexeme's exact decimal value;
    Fraction.from_float uses the exact frozen binary64 R, factor and parser value.
    This is a diagnostic hypothesis, never a replacement for the frozen gate.
    """
    x,y=flatten(parsed_base),flatten(parsed_variant)
    need(len(entries_base)==len(entries_variant)==len(x)==len(y) and len(x)%3==0,'EXACT_3VECTOR_TOKEN_SHAPE_REQUIRED')
    need(len(rotation)==3 and all(len(row)==3 for row in rotation),'EXACT_ROTATION_3BY3_REQUIRED')
    r=[[rational_float(value) for value in row] for row in rotation]
    scale=rational_float(factor);result=[]
    parsed_x=[rational_float(value) for value in x];parsed_y=[rational_float(value) for value in y]
    for start in range(0,len(x),3):
        b=[tuple(Fraction(value) for value in token_interval(e['token'])) for e in entries_base[start:start+3]]
        v=[tuple(Fraction(value) for value in token_interval(e['token'])) for e in entries_variant[start:start+3]]
        for axis in range(3):
            propagated=sum(abs(r[axis][j])*b[j][2]*abs(scale) for j in range(3))
            variant_half=v[axis][2]*abs(scale);bound=propagated+variant_half
            native_expected=sum(r[axis][j]*b[j][0]*scale for j in range(3))
            native_residual=abs(v[axis][0]*scale-native_expected)
            parsed_expected=sum(r[axis][j]*parsed_x[start+j] for j in range(3))
            parsed_residual=abs(parsed_y[start+axis]-parsed_expected)
            result.append({'vector_index':start//3,'component':axis,
                'propagated_base_print_halfwidth':exact_decimal(propagated),'variant_print_halfwidth':exact_decimal(variant_half),
                'native_print_propagation_bound':exact_decimal(bound),'residual_exact_native_token_centers':exact_decimal(native_residual),
                'residual_exact_linear_combination_of_parser_floats':exact_decimal(parsed_residual),
                'native_centers_within_print_bound':native_residual<=bound,
                'parser_float_centers_within_print_bound':parsed_residual<=bound})
    return result


def geometry_orbit(base,variant,rotation,translation=(0.,0.,0.),permutation_variant_to_base=None,atol=1e-10):
    """No geometry fitting or nearest-neighbor permutation inference."""
    import numpy as np
    x,y=np.asarray(base,float),np.asarray(variant,float);r=np.asarray(rotation,float);t=np.asarray(translation,float)
    need(x.shape==y.shape and x.ndim==2 and x.shape[1]==3 and r.shape==(3,3) and t.shape==(3,),'GEOMETRY_SHAPE_MISMATCH')
    need(np.isfinite(x).all() and np.isfinite(y).all(),'NONFINITE_GEOMETRY')
    p=list(range(len(x))) if permutation_variant_to_base is None else list(permutation_variant_to_base)
    need(len(p)==len(x) and sorted(p)==list(range(len(x))),'DECLARED_PERMUTATION_NOT_BIJECTION')
    residual=np.abs(y-(x[p]@r.T+t));bad=np.argwhere(residual>atol)
    return {'same_geometry_orbit_within_predeclared_coordinate_atol':bool(np.all(residual<=atol)),
        'max_abs_orbit_error_A':float(residual.max()),'coordinate_atol_A':atol,'declared_rotation':r.tolist(),
        'declared_translation_A':t.tolist(),'permutation_variant_to_base':p,
        'permutation_status':'IDENTITY_ONLY_NO_PERMUTATION_ARM_PRESENT' if permutation_variant_to_base is None else 'EXPLICIT_DECLARED_MAPPING',
        'first20_exceeding_coordinate_indices':bad[:20].tolist(),'geometry_fit_or_atom_remapping_performed':False}
