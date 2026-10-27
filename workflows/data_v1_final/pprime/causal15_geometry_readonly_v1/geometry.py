"""Exact native decimal token geometry comparisons; no adjustable tolerances."""
from decimal import Decimal,localcontext
from fractions import Fraction as F
from workflows.data_v1_final.pprime.causal15_main_v1 import render as T


def fp(value):return F.from_float(float(value))
def dot(x,y):return sum((a*b for a,b in zip(x,y)),F(0))
def exact(value):return {'numerator':str(value.numerator),'denominator':str(value.denominator),'binary64_display':float(value)}
def center(x):
    mean=[sum((r[j] for r in x),F(0))/len(x) for j in range(3)]
    return [[r[j]-mean[j] for j in range(3)] for r in x]
def center_h(h):
    mean=[sum((r[j] for r in h),F(0))/len(h) for j in range(3)]
    return [[r[j]+mean[j] for j in range(3)] for r in h]
def transform(x,r):return [[dot(row,axis) for axis in r] for row in x]
def product_bound(x,y,hx,hy):return sum((abs(a)*hb+abs(b)*ha+ha*hb for a,b,ha,hb in zip(x,y,hx,hy)),F(0))
def interval_norm_squared(v,h):
    return (sum((max(F(0),abs(a)-b)**2 for a,b in zip(v,h)),F(0)),sum(((abs(a)+b)**2 for a,b in zip(v,h)),F(0)))
def sqrt_display(value):
    with localcontext() as ctx:ctx.prec=70;return float((Decimal(value.numerator)/Decimal(value.denominator)).sqrt())


def coordinates(inputs,symbols):
    import numpy as np
    name='input.mop' if 'input.mop' in inputs else 'input.xyz';_,parsed=T.rows(inputs[name],name);array=T.arrays(inputs,symbols)
    tokens=[r[2] for r in parsed];values=[[F(Decimal(v)) for v in row] for row in tokens]
    half=[[F(Decimal(1).scaleb(Decimal(v).as_tuple().exponent))/2 for v in row] for row in tokens]
    T.C.need([r[1] for r in parsed]==symbols and np.isfinite(array).all()
        and np.asarray([[float(v) for v in row] for row in tokens],dtype='<f8').tobytes()==array.tobytes(),'ORIGINAL_T_ARRAYS_AND_EXACT_TOKEN_VALUES_AGREE')
    redundant={}
    for other in sorted(set(inputs)&{'input.xyz','input.mop'}):
        _,rows=T.rows(inputs[other],other);same=[r[1] for r in rows]==symbols and len(rows)==len(values)
        diffs=[abs(F(Decimal(t))-v) for row,expected in zip(rows,values) for t,v in zip(row[2],expected)]
        redundant[other]={'same_symbols_and_order':same,'max_exact_difference_from_program_selected_input_A':exact(max(diffs,default=F(0))),
            'same_exact_native_decimal_coordinates':same and all(d==0 for d in diffs)}
    return {'name':name,'symbols':symbols,'array':array,'values':values,'half':half,'tokens':tokens,'redundant_coordinate_inputs':redundant}


def compare(a,b,matrix):
    import numpy as np
    from math_v1 import checked_rotation
    checked_rotation(matrix);r=[[fp(v) for v in row] for row in matrix];ar=[[abs(v) for v in row] for row in r]
    T.C.need(a['symbols']==b['symbols'] and len(a['values'])==len(b['values']),'SAME_NATIVE_SYMBOLS_AND_ATOM_ORDER_REQUIRED')
    x,y=a['values'],b['values'];hx,hy=a['half'],b['half'];e=transform(x,r);eh=transform(hx,ar)
    residual=[[y[i][j]-e[i][j] for j in range(3)] for i in range(len(x))]
    bounds=[[hy[i][j]+eh[i][j] for j in range(3)] for i in range(len(x))]
    exceed=[(i,j) for i in range(len(x)) for j in range(3) if abs(residual[i][j])>bounds[i][j]]
    worst=max(((abs(residual[i][j]),i,j) for i in range(len(x)) for j in range(3)))
    xc,yc,ec=center(x),center(y),center(e);hxc,hyc,hec=center_h(hx),center_h(hy),center_h(eh)
    gram={'components':len(x)**2,'outside_propagated_native_token_bound':0,'first8_exceeding_components':[]};distance={'pairs':len(x)*(len(x)-1)//2,'outside_squared_distance_token_bound':0,'nonoverlapping_distance_token_intervals':0,'first8_exceeding_pairs':[]}
    gmax=F(-1);dmax=F(-1);rawg=F(0);rawd=F(0);max_distance_A=0.;matrix_gram=F(0);matrix_distance=F(0)
    for i in range(len(x)):
        for j in range(len(x)):
            gx,gy,ge=dot(xc[i],xc[j]),dot(yc[i],yc[j]),dot(ec[i],ec[j]);delta=abs(gy-ge)
            bound=product_bound(yc[i],yc[j],hyc[i],hyc[j])+product_bound(ec[i],ec[j],hec[i],hec[j])
            rawg=max(rawg,abs(gy-gx));matrix_gram=max(matrix_gram,abs(ge-gx));gram['outside_propagated_native_token_bound']+=delta>bound
            if delta>bound and len(gram['first8_exceeding_components'])<8:gram['first8_exceeding_components'].append({'atoms':[i,j],'residual_A2':exact(delta),'bound_A2':exact(bound)})
            if delta>gmax:gmax=delta;gram['worst_component']={'atoms':[i,j],'residual_from_binary64_R_prediction_A2':exact(delta),'propagated_token_bound_A2':exact(bound)}
            if j<=i:continue
            dx=[x[i][k]-x[j][k] for k in range(3)];dy=[y[i][k]-y[j][k] for k in range(3)];de=[e[i][k]-e[j][k] for k in range(3)]
            hd_y=[hy[i][k]+hy[j][k] for k in range(3)];hd_e=[eh[i][k]+eh[j][k] for k in range(3)]
            qx,qy,qe=dot(dx,dx),dot(dy,dy),dot(de,de);delta=abs(qy-qe)
            bound=product_bound(dy,dy,hd_y,hd_y)+product_bound(de,de,hd_e,hd_e)
            iy,ie=interval_norm_squared(dy,hd_y),interval_norm_squared(de,hd_e)
            distance['outside_squared_distance_token_bound']+=delta>bound;distance['nonoverlapping_distance_token_intervals']+=iy[1]<ie[0] or ie[1]<iy[0]
            if (delta>bound or iy[1]<ie[0] or ie[1]<iy[0]) and len(distance['first8_exceeding_pairs'])<8:distance['first8_exceeding_pairs'].append({'atoms':[i,j],'squared_distance_residual_A2':exact(delta),'bound_A2':exact(bound),'intervals_overlap':not(iy[1]<ie[0] or ie[1]<iy[0])})
            rawd=max(rawd,abs(qy-qx));matrix_distance=max(matrix_distance,abs(qe-qx));max_distance_A=max(max_distance_A,abs(sqrt_display(qy)-sqrt_display(qx)))
            if delta>dmax:dmax=delta;distance['worst_pair']={'atoms':[i,j],'residual_from_binary64_R_prediction_A2':exact(delta),'propagated_token_bound_A2':exact(bound),
                'variant_distance_interval_A':[sqrt_display(v) for v in iy],'expected_rotated_base_distance_interval_A':[sqrt_display(v) for v in ie]}
    gram.update(max_abs_unadjusted_native_Gram_change_A2=exact(rawg),max_predicted_binary64_R_orthogonality_Gram_change_A2=exact(matrix_gram))
    distance.update(max_abs_unadjusted_native_squared_distance_change_A2=exact(rawd),max_predicted_binary64_R_squared_distance_change_A2=exact(matrix_distance),max_abs_unadjusted_native_distance_change_A_display=max_distance_A)
    orth=[[dot(r[i],r[j])-F(i==j) for j in range(3)] for i in range(3)]
    return {'same_symbols_and_native_atom_order':True,'atoms':len(x),'R_convention':'row_coordinates @ outer_record_R.T; no fitted or substituted R',
        'original_outer_R':matrix,'binary64_R_orthogonality_defect_max':exact(max(abs(v) for row in orth for v in row)),
        'coordinate_residuals_A':[[float(v) for v in row] for row in residual],
        'coordinate_native_token_propagation_bounds_A':[[float(v) for v in row] for row in bounds],
        'coordinate_components_outside_native_token_bound':len(exceed),'exceeding_atom_component_indices':exceed,
        'worst_coordinate':{'atom':worst[1],'component':worst[2],'base_tokens':a['tokens'][worst[1]],'variant_tokens':b['tokens'][worst[1]],
            'absolute_exact_residual_A':exact(worst[0]),'native_input_token_bound_A':exact(bounds[worst[1]][worst[2]])},
        'mean_translation_residual_A':[float(sum((row[j] for row in residual),F(0))/len(x)) for j in range(3)],
        'centered_Gram':gram,'pair_distances':distance,'new_atol_or_rtol':False,'scientific_covariance_checks_reclassified':False}
