"""Fit the authorized reversible label recipes on supplied TRAIN observations."""
from copy import deepcopy
import numpy as np
from .p_recipe import fit_element_residual


def reference_difference(state,neutral):
    a=state.get('element_reference') or {};b=neutral.get('element_reference') or {}
    if not a and not b:return None
    ca=dict(zip(a.get('basis',[]),a.get('coefficients',[])));cb=dict(zip(b.get('basis',[]),b.get('coefficients',[])))
    basis=sorted(set(ca)|set(cb))
    return dict(basis=basis,coefficients=[ca.get(z,0.)-cb.get(z,0.) for z in basis],intercept=a.get('intercept',0.)-b.get('intercept',0.))


def reference_values(counts,reference):
    if not reference:return np.zeros(len(counts),dtype=np.float64)
    return counts[:,np.asarray(reference['basis'],dtype=int)-1]@np.asarray(reference['coefficients'],dtype=np.float64)+reference.get('intercept',0.)


def fit_parameters(normalizations,definitions,selections,counts,values,*,a1_fields=(),differences=None,tail_fields=(),minimum_a1_molecules=100000):
    """Values already contain A2's aligned state differences, before references.

    Vector components keep a zero center and one per-head scale, equal to the
    population standard deviation of their norm, as in the frozen D4 policy.
    All fitting and transform composition use FP64, with no invented epsilon.
    """
    differences=differences or {};tail_fields=set(tail_fields)
    parameters=dict(normalizations={},state_difference=dict(differences),heavy_tail={},fit={})
    specs={name:deepcopy(normalizations[name]) for name in values}
    y={name:np.asarray(value,dtype=np.float64).copy() for name,value in values.items()}
    for name,neutral in differences.items():
        specs[name]['element_reference']=reference_difference(normalizations[name],normalizations[neutral])
    basis=(np.flatnonzero(np.asarray(counts).sum(0))+1).tolist()
    for name in a1_fields:
        result=fit_element_residual(counts[:,np.asarray(basis)-1],y[name].reshape(-1))
        if result['fit_molecules']<minimum_a1_molecules:
            raise ValueError(f'A1 lacks100000 valid TRAIN molecules: {name}: {result["fit_molecules"]}')
        specs[name]['element_reference']={k:result[k] for k in ('coefficients','intercept')}
        specs[name]['element_reference']['basis']=basis
        parameters['fit'][name]=dict(A1_molecules=result['fit_molecules'])
    for name,value in y.items():
        reference=specs[name].get('element_reference')
        if reference is not None:
            if definitions[name]['level'] not in ('graph','molecule','molecule_vector'):
                raise ValueError('Element reference requires molecular observations')
            y[name]=value-reference_values(counts,reference)[:,None]
    heads={}
    for name in y:heads.setdefault(selections[name][0],[]).append(name)
    for head,names in heads.items():
        ordered=sorted(names,key=lambda n:selections[n][1] if selections[n][1] is not None else -1)
        if any(n in tail_fields for n in ordered):
            absolute=np.concatenate([np.abs(y[n]).reshape(-1) for n in ordered]);m=float(np.nanmedian(absolute))
            if not np.isfinite(m) or m<=0:raise ValueError('A5 median absolute target is zero or unavailable: '+head)
            for name in ordered:
                reference=specs[name].get('element_reference')
                parameters['heavy_tail'][name]=dict(m=m,offset_reference=reference)
                specs[name]['element_reference']=None
                y[name]=np.sign(y[name])*np.log1p(np.abs(y[name])/m)
        vector=len(ordered)>1 or definitions[ordered[0]].get('representation')=='vector' or definitions[ordered[0]]['level'] in ('molecule_vector','atom_vector')
        if vector:
            block=np.concatenate([y[n] for n in ordered],axis=1) if len(ordered)>1 else y[ordered[0]]
            complete=block[np.isfinite(block).all(1)];scale=float(np.linalg.norm(complete,axis=1).std(ddof=0));center=0.
        else:
            observed=y[ordered[0]][np.isfinite(y[ordered[0]])];center=float(observed.mean());scale=float(observed.std(ddof=0))
        if not np.isfinite(scale) or scale<=0:raise ValueError('Undefined transformed TRAIN scale: '+head)
        for name in ordered:
            specs[name].update(center=center,scale=scale,fit_role='TRAIN',p_recipe_fitted=True)
            parameters['normalizations'][name]=specs[name]
            parameters['fit'].setdefault(name,{})['observations']=int(np.isfinite(y[name]).sum())
    return parameters