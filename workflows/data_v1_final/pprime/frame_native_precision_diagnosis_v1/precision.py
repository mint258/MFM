"""Native-token Decimal intervals and explicit geometry orbits; no tolerance fitting."""
from __future__ import annotations
from decimal import Decimal,localcontext
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
    step=Decimal(1).scaleb(value.as_tuple().exponent)
    return value,step,step/2


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
    converted=[];details=[]
    for entry in entries:
        value,step,half=token_interval(entry['token'])
        actual=parse_float(entry['token'])*factor
        need(math.isfinite(actual),'NONFINITE_TOKEN_CONVERSION')
        converted.append(actual)
        details.append(dict(entry,step_native=str(step),halfwidth_native=str(half),
            parsed_value_field_units=actual,halfwidth_field_units=str(half*abs(Decimal.from_float(float(factor)))),
            frozen_parser_conversion_factor_hex=float(factor).hex()))
    return converted,details


def propagate_native(entries_base,entries_variant,factor,rotation,parsed_base,parsed_variant):
    """Componentwise |R|epsilon_base+epsilon_variant; no atol/rtol/norm substitute."""
    x,y=flatten(parsed_base),flatten(parsed_variant)
    need(len(entries_base)==len(entries_variant)==len(x)==len(y) and len(x)%3==0,'EXACT_3VECTOR_TOKEN_SHAPE_REQUIRED')
    with localcontext() as context:
        context.prec=100
        r=[[Decimal.from_float(float(v)) for v in row] for row in rotation]
        scale=Decimal.from_float(float(factor));result=[]
        for start in range(0,len(x),3):
            b=[token_interval(e['token']) for e in entries_base[start:start+3]]
            v=[token_interval(e['token']) for e in entries_variant[start:start+3]]
            for axis in range(3):
                propagated=sum(abs(r[axis][j])*b[j][2]*abs(scale) for j in range(3))
                variant_half=v[axis][2]*abs(scale);bound=propagated+variant_half
                native_expected=sum(r[axis][j]*b[j][0]*scale for j in range(3))
                native_residual=abs(v[axis][0]*scale-native_expected)
                parsed_expected=sum(r[axis][j]*Decimal.from_float(float(x[start+j])) for j in range(3))
                parsed_residual=abs(Decimal.from_float(float(y[start+axis]))-parsed_expected)
                result.append({'vector_index':start//3,'component':axis,
                    'propagated_base_print_halfwidth':str(propagated),'variant_print_halfwidth':str(variant_half),
                    'native_print_propagation_bound':str(bound),'residual_exact_native_token_centers':str(native_residual),
                    'residual_exact_linear_combination_of_parser_floats':str(parsed_residual),
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