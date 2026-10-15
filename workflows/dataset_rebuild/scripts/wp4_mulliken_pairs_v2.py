#!/usr/bin/env python3
"""Sparse PM7/v23.0.3 Mulliken pairs from AUX Coulson density.

Dense density/overlap working arrays stay in this function only. Exported AUX
overlap uses beta_d for d AOs, whereas official v23.0.3 MULLIK uses beta_p for
every non-first AO. Correct that inter-atom overlap before the internal inverse
root and transform, then check reconstructed charges against this calculation.
The returned label contains only requested atom pairs and compact QC metadata.
"""
from __future__ import annotations
import hashlib
import math
from pathlib import Path
import re
import time

PM7_BETA = {
    'H': (-8.389745, None, None),
    'B': (-7.509528, -3.775165, None),
    'C': (-14.414930, -7.893717, None),
    'N': (-22.110958, -15.464433, None),
    'O': (-67.776339, -20.267981, None),
    'F': (-69.725688, -29.746124, None),
    'Si': (-10.755885, -3.922152, -4.736877),
    'P': (-45.578128, -12.487910, -34.182622),
    'S': (-11.422550, -7.191896, -10.695329),
    'Cl': (-2.893931, -13.528255, 1.888153),
    'Se': (-9.614158, -6.121302, None),
    'Br': (-32.458894, -10.270309, -19.977175),
    'I': (-37.373318, -10.174482, -11.807267),
}
ELEMENT_Z = dict(zip(PM7_BETA, (1,5,6,7,8,9,14,15,16,17,34,35,53)))
SOURCE_URLS = {
    'parameters': 'https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/src/models/parameters_for_PM7_C.F90',
    'mullik': 'https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/src/properties/mullik.F90',
    'aux_export': 'https://raw.githubusercontent.com/openmopac/mopac/v23.0.3/src/output/to_screen.F90',
}
METHOD = 'PM7_v23.0.3_AUX_total_density_beta_p_for_d_MULLIK_overlap'
FLOAT = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'
HEADER = re.compile(r'^[ \t]*([A-Z][A-Z0-9_:./ -]*?)(?:\[(\d+)\])?[ \t]*=[ \t]*(.*)$')
D_AO_TYPES = {'X2','XZ','Z2','YZ','XY','DX2','DXZ','DZ2','DYZ','DXY',
              'DX2-Y2','DX2Y2','DZ2-R2'}
FIELDS = {'MOPAC_VERSION','METHOD','ATOM_EL','ATOM_CORE','AO_ATOMINDEX',
          'ATOM_SYMTYPE','OVERLAP_MATRIX','TOTAL_DENSITY_MATRIX','MULLIKEN_ATOM_CHARGES'}


def _number(value):
    result=float(value.replace('D','E').replace('d','e'))
    if not math.isfinite(result): raise ValueError('AUX_NONFINITE_VALUE')
    return result


def read_selected_aux(path):
    """Stream only these fields; skip MOs/Hamiltonian and other large arrays."""
    arrays,errors={},[]
    active,count,tokens=None,None,[]
    def finish():
        if active is None: return
        if count is None:
            literal=' '.join(tokens).strip().strip('"')
            arrays[active]=_number(literal) if re.fullmatch(FLOAT,literal) else literal
        else:
            if len(tokens)!=count: errors.append('AUX_COUNT_MISMATCH:'+active)
            arrays[active]=[_number(x) if re.fullmatch(FLOAT,x) else x.strip('"') for x in tokens[:count]]
    with Path(path).open(errors='replace') as stream:
        for line in stream:
            match=HEADER.match(line.rstrip('\n'))
            if match:
                finish()
                name=match.group(1).strip()
                active=name if name in FIELDS else None
                count=int(match.group(2)) if match.group(2) else None
                tokens=match.group(3).split() if active else []
            elif active and not line.lstrip().startswith('#'):
                tokens.extend(line.split())
        finish()
    return arrays,errors


def _triangle(values,size):
    import numpy as np
    if values is None or len(values)!=size*(size+1)//2:
        raise ValueError('AUX_PACKED_MATRIX_DIMENSION_MISMATCH')
    matrix=np.zeros((size,size),dtype=np.float64)
    matrix[np.tril_indices(size)]=values
    matrix+=matrix.T-np.diag(np.diag(matrix))
    if not np.isfinite(matrix).all(): raise ValueError('AUX_MATRIX_NONFINITE')
    return matrix


def _beta_arrays(symbols,mapping,types):
    import numpy as np
    actual,legacy,d_count=[],[],0
    for atom,kind in zip(mapping,types):
        symbol=symbols[int(atom)-1]
        if symbol not in PM7_BETA: raise ValueError('PM7_BETA_ELEMENT_UNBOUND:'+symbol)
        bs,bp,bd=PM7_BETA[symbol]
        kind=str(kind).strip().upper()
        if kind=='S': native,old=bs,bs
        elif kind in ('PX','PY','PZ'): native,old=bp,bp
        elif kind in D_AO_TYPES: native,old=bd,bp; d_count+=1
        else: raise ValueError('AO_TYPE_NOT_SUPPORTED:'+symbol+'/'+kind)
        if native is None or old is None: raise ValueError('PM7_BETA_ORBITAL_UNBOUND:'+symbol+'/'+kind)
        actual.append(native); legacy.append(old)
    return np.asarray(actual),np.asarray(legacy),d_count


def sparse_mulliken_from_aux(path,symbols,pair_indices,reference_charges=None,
                             charge_tolerance_e=0.001,min_absolute_eigenvalue=1e-10):
    """Return available pairs only after this case's charge consistency check.

    This is the official code's pair decomposition with rounded AUX inputs,
    not a second electronic calculation. A missing/unreliable value is null and
    carries a QC code; callers continue other independent properties.
    """
    import numpy as np
    started=time.monotonic()
    qc={'method':METHOD,'status':'UNAVAILABLE','codes':[],
        'charge_tolerance_e':float(charge_tolerance_e),'pair_value_unit':'electrons',
        'pair_indices':'0-based i>j; one entry per requested unordered atom pair',
        'source_precision':'Rounded AUX total density and overlap; charge check per case.',
        'dense_matrices_saved_as_labels':False,'independent_pair_truth_available':False}
    result={'pairs':None,'qc':qc}
    try:
        if charge_tolerance_e<=0 or min_absolute_eigenvalue<=0:
            raise ValueError('INVALID_MULLIKEN_QC_THRESHOLD')
        aux,errors=read_selected_aux(path)
        if errors: raise ValueError(';'.join(errors))
        if aux.get('MOPAC_VERSION')!='23.0.3' or str(aux.get('METHOD')).upper()!='PM7':
            raise ValueError('MULLIKEN_RECONSTRUCTION_MODEL_VERSION_MISMATCH')
        if aux.get('ATOM_EL')!=list(symbols): raise ValueError('AUX_ATOM_ORDER_MISMATCH')
        mapping=np.asarray(aux.get('AO_ATOMINDEX',[]),dtype=int)
        types=aux.get('ATOM_SYMTYPE',[])
        core=np.asarray(aux.get('ATOM_CORE',[]),dtype=float)
        nao=len(mapping); nat=len(symbols)
        if not nao or len(types)!=nao or len(core)!=nat or np.any(mapping<1) or np.any(mapping>nat):
            raise ValueError('AUX_AO_MAPPING_DIMENSION_MISMATCH')
        requested=sorted({(max(int(i),int(j)),min(int(i),int(j))) for i,j in pair_indices})
        if any(i>=nat or j<0 or i==j for i,j in requested):
            raise ValueError('MULLIKEN_PAIR_INDEX_INVALID')
        if len(requested)!=len(pair_indices): raise ValueError('MULLIKEN_PAIR_INDICES_DUPLICATE')
        density=_triangle(aux.get('TOTAL_DENSITY_MATRIX'),nao)
        overlap=_triangle(aux.get('OVERLAP_MATRIX'),nao)
        actual,legacy,d_count=_beta_arrays(symbols,mapping,types)
        denominator=legacy[:,None]+legacy[None,:]
        inter_atom=mapping[:,None]!=mapping[None,:]
        if np.any(np.abs(denominator[inter_atom])<1e-12):
            raise ValueError('MULLIKEN_BETA_SUM_NEAR_ZERO')
        numerator=actual[:,None]+actual[None,:]
        before=overlap[inter_atom].copy()
        overlap[inter_atom]=before*numerator[inter_atom]/denominator[inter_atom]+1e-14
        qc['AUX_to_MULLIK_overlap_max_change']=float(np.max(np.abs(overlap[inter_atom]-before))) if before.size else 0.0
        del before,numerator,denominator,inter_atom
        # Official MULLIK has zero intra-atom off-diagonal and unit diagonal.
        overlap[mapping[:,None]==mapping[None,:]]=0.0
        np.fill_diagonal(overlap,1.0)
        eigenvalues,eigenvectors=np.linalg.eigh(overlap)
        minimum_abs=float(np.min(np.abs(eigenvalues)))
        qc.update(AO_count=nao,atom_count=nat,d_AO_count=d_count,
                  minimum_overlap_eigenvalue=float(eigenvalues.min()),
                  minimum_absolute_overlap_eigenvalue=minimum_abs,
                  negative_overlap_eigenvalues=int((eigenvalues<0).sum()),
                  requested_pair_count=len(requested))
        if minimum_abs<min_absolute_eigenvalue: raise ValueError('MULLIKEN_OVERLAP_NEAR_SINGULAR')
        qc['overlap_absolute_condition_number']=float(np.abs(eigenvalues).max()/minimum_abs)
        # Official v23.0.3 intentionally takes sqrt(abs(eigenvalue)).
        inverse_root=(eigenvectors/np.sqrt(np.abs(eigenvalues)))@eigenvectors.T
        del eigenvectors,eigenvalues
        density=inverse_root@density@inverse_root.T
        del inverse_root
        population=density*overlap
        del density,overlap
        atom_indices=[np.flatnonzero(mapping==atom+1) for atom in range(nat)]
        charges=core-np.asarray([population[rows,:].sum() for rows in atom_indices])
        reference=reference_charges if reference_charges is not None else aux.get('MULLIKEN_ATOM_CHARGES')
        if reference is None or len(reference)!=nat: raise ValueError('MULLIKEN_REFERENCE_CHARGES_MISSING')
        reference=np.asarray(reference,dtype=float)
        if not np.isfinite(reference).all() or not np.isfinite(charges).all():
            raise ValueError('MULLIKEN_CHARGE_NONFINITE')
        error=float(np.max(np.abs(charges-reference)))
        qc.update(reference_charge_source='.out parsed MULLIKEN charges' if reference_charges is not None else 'AUX MULLIKEN_ATOM_CHARGES',
                  reconstructed_charge_max_error_e=error,reconstructed_total_charge_e=float(charges.sum()),
                  reference_total_charge_e=float(reference.sum()))
        if error>charge_tolerance_e: raise ValueError('MULLIKEN_OVERLAP_CHARGE_MISMATCH')
        pairs=[{'i':i,'j':j,'population_e':float(2*population[np.ix_(atom_indices[i],atom_indices[j])].sum())}
               for i,j in requested]
        if any(not math.isfinite(pair['population_e']) for pair in pairs): raise ValueError('MULLIKEN_PAIR_NONFINITE')
        result['pairs']=pairs
        qc['status']='AVAILABLE_CHARGE_QC_PASS'
        if qc['negative_overlap_eigenvalues']:
            qc['codes'].append('MULLIKEN_NEGATIVE_OVERLAP_EIGENVALUES_ABS_ROOT_OFFICIAL')
    except Exception as exc:
        qc['codes'].append(str(exc).split(':',1)[0])
        qc['failure_reason']=type(exc).__name__+': '+str(exc)
    finally:
        qc['elapsed_seconds']=time.monotonic()-started
    return result


def validate_official_parameters(source_path):
    """Lightweight exact parameter verification, with no matrix or QM work."""
    source=Path(source_path).read_text()
    for element,betas in PM7_BETA.items():
        for shell,expected in zip(('s','p','d'),betas):
            match=re.search(r'data\s+beta'+shell+r'7\(\s*'+str(ELEMENT_Z[element])+r'\s*\)/\s*('+FLOAT+r')/',source,re.I)
            if expected is None:
                if match: raise ValueError('UNEXPECTED_OFFICIAL_BETA:'+element+'/'+shell)
            elif not match or _number(match.group(1))!=expected:
                raise ValueError('OFFICIAL_PM7_BETA_DIFFERS:'+element+'/'+shell)
    return {'status':'THIRTEEN_ELEMENT_OFFICIAL_PM7_BETA_PASS',
            'source_sha256':hashlib.sha256(Path(source_path).read_bytes()).hexdigest(),
            'elements':list(PM7_BETA),'version':'23.0.3','source_URL':SOURCE_URLS['parameters']}
