"""Explicit candidate record wire for C4 sizing, not a chosen lmdb_1 schema.

Keep the original Data object's non-descriptor fields, replace D23 by D20 with
current NumHAcceptors, add only requested native-geometry 3D descriptors, and
store registry-indexed P labels with per-case status/QC and shared provenance.
No LMDB is created. The same functions can be used by a future chosen writer.
"""
from __future__ import annotations
import copy
import hashlib
import importlib
import json
import math
from pathlib import Path
import pickle
import struct
import sys

RUNTIME=Path('/share/home/zixiao/PhyChem_MFM_stage59_three_epoch_runtime')
sys.path.insert(0,str(RUNTIME))
D20=D23=GRAPH_NAMES=None

def metadata():
    global D20,D23,GRAPH_NAMES
    from phychem_mfm.data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
    from phychem_mfm.model.phase1_specs import PHASE1_GRAPH_DESCRIPTOR_NAMES
    from rdkit import rdBase
    GRAPH_NAMES=tuple(GRAPH_DESCRIPTOR_NAMES);D23=tuple(PHASE1_GRAPH_DESCRIPTOR_NAMES)
    D20=tuple(name for name in D23 if name not in {'Kappa1','Kappa2','Kappa3'})
    if len(D23)!=23 or len(D20)!=20:raise ValueError('Candidate D23/D20 name-count differs from user specification')
    module=importlib.import_module('phychem_mfm.model.phase1_specs')
    path=Path(module.__file__)
    return {'candidate_schema':'C4_NATIVE_DATA_D20_D3D_REGISTRY_P_V1_NOT_FINAL',
        'D23_names':D23,'D20_names':D20,'original_graph_names':GRAPH_NAMES,
        'D_schema_source':str(path),'D_schema_source_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
        'rdkit_version':rdBase.rdkitVersion,'removed_descriptors':['Kappa1','Kappa2','Kappa3'],
        'remaining_D19':'Sizing preserves stored native descriptor scalar bits; it does not replace the later formal 100k descriptor recomputation requirement.',
        'HBA':'Lipinski.NumHAcceptors on stored sanitized SMILES, current RDKit.',
        'D3D':{'PMI1_PMI2_PMI3':'RDKit principal moments with atomic masses, native PM7 geometry',
            'PBF':'RDKit PBF native PM7 geometry; Angstrom',
            'volume':'AllChem.ComputeMolVolume(gridSpacing=0.2, boxMargin=2.0); Angstrom^3',
            'SASA':'rdFreeSASA LeeRichards, explicit RDKit periodic-table VDW atom radii and 1.4 Angstrom solvent probe; total and atom areas Angstrom^2; explicit hydrogens retained'},
        'not_added':['NPR1','NPR2','RadiusOfGyration','Eccentricity','Asphericity','InertialShapeFactor','SpherocityIndex'],
        'P_wire':'Integer registry IDs reference shared canonical target/unit/method metadata. Numeric arrays remain float64/int64/bool; numeric sparse list-of-dict fields use named structured arrays with exact original scalar types. Empty/null/absent keys remain separate.',
        'format_candidates':['pickle protocol4 compatible Data','pickle protocol5 Data + registry P','pickle protocol5 plus framed lossless zstd level3'],
        'format_chosen_for_formal_lmdb_1':False,
        'official_docs':['https://www.rdkit.org/docs/source/rdkit.Chem.Descriptors3D.html',
            'https://www.rdkit.org/docs/source/rdkit.Chem.AllChem.html',
            'https://www.rdkit.org/docs/source/rdkit.Chem.rdFreeSASA.html']}

def field(raw,key):return raw.get(key) if isinstance(raw,dict) else getattr(raw,key,None)

def setfield(raw,key,value):
    if isinstance(raw,dict):raw[key]=value
    else:setattr(raw,key,value)

def numeric(raw,key):
    import numpy as np
    value=field(raw,key)
    if hasattr(value,'detach'):value=value.detach().cpu().numpy()
    return np.asarray(value)

def corrected_base(raw,row):
    import numpy as np,torch
    from rdkit import Chem
    from rdkit.Chem import AllChem,Descriptors3D,Lipinski
    if D20 is None:metadata()
    result=copy.deepcopy(raw);issues=[]
    mol=Chem.MolFromSmiles(str(field(raw,'smiles') or row.get('smiles','')))
    original=field(raw,'rdkit_graph_desc');mask=field(raw,'rdkit_graph_desc_mask')
    if mol is None:raise ValueError('Stored SMILES cannot construct D20/3D')
    if not hasattr(original,'detach') or original.numel()!=len(GRAPH_NAMES):raise ValueError('Original graph descriptor wire shape unavailable')
    indices=[GRAPH_NAMES.index(name) for name in D20]
    values=original.reshape(-1)[indices].clone();values[D20.index('NumHAcceptors')]=Lipinski.NumHAcceptors(mol)
    setfield(result,'rdkit_graph_desc',values)
    if hasattr(mask,'detach') and mask.numel()==len(GRAPH_NAMES):
        new_mask=mask.reshape(-1)[indices].clone();new_mask[D20.index('NumHAcceptors')]=1
        setfield(result,'rdkit_graph_desc_mask',new_mask)
    setfield(result,'descriptor_schema_ref','C4_D20_D3D_REGISTRY_V1')
    z=numeric(raw,'x').reshape(-1).astype(np.int64)+1;coords=numeric(raw,'pos').astype(np.float64)
    if coords.shape!=(len(z),3) or not np.isfinite(coords).all():raise ValueError('Native geometry invalid for 3D')
    mol3d=Chem.AddHs(mol)
    if mol3d.GetNumAtoms()!=len(z) or any(atom.GetAtomicNum()!=int(z[atom.GetIdx()]) for atom in mol3d.GetAtoms()):
        raise ValueError('Stored SMILES/element atom-order alignment unavailable for requested 3D')
    # Verify actual original graph edges before relying on the SMILES atom
    # indices; matching element sequences alone is insufficient for C4/B5.
    original_bonds=numeric(raw,'rdkit_bond_index')
    source_pairs={tuple(sorted(map(int,pair))) for pair in original_bonds.T}
    graph_pairs={tuple(sorted((bond.GetBeginAtomIdx(),bond.GetEndAtomIdx()))) for bond in mol3d.GetBonds()}
    if source_pairs!=graph_pairs:raise ValueError('Source bondgraph differs from ordered SMILES graph for 3D')
    conf=Chem.Conformer(len(z));conf.Set3D(True)
    for index,point in enumerate(coords):conf.SetAtomPosition(index,tuple(map(float,point)))
    mol3d.RemoveAllConformers();mol3d.AddConformer(conf,assignId=True)
    d3d={}
    for name in ('PMI1','PMI2','PMI3','PBF'):
        try:d3d[name]=float(getattr(Descriptors3D,name)(mol3d))
        except Exception as exc:d3d[name]=None;issues.append(name+':'+str(exc))
    try:d3d['volume_A3']=float(AllChem.ComputeMolVolume(mol3d,gridSpacing=.2,boxMargin=2.0))
    except Exception as exc:d3d['volume_A3']=None;issues.append('volume:'+str(exc))
    try:
        from rdkit.Chem import rdFreeSASA
        radii=[Chem.GetPeriodicTable().GetRvdw(int(item)) for item in z]
        opts=rdFreeSASA.SASAOpts(rdFreeSASA.SASAAlgorithm.LeeRichards,rdFreeSASA.SASAClassifier.Protor,1.4)
        d3d['SASA_total_A2']=float(rdFreeSASA.CalcSASA(mol3d,radii,opts=opts))
        atom_sasa=np.asarray([float(atom.GetProp('SASA')) for atom in mol3d.GetAtoms()],dtype=np.float64)
        if not np.isfinite(atom_sasa).all():raise ValueError('SASA nonfinite atom values')
        d3d['SASA_atom_A2']=atom_sasa
    except Exception as exc:d3d['SASA_total_A2']=None;d3d['SASA_atom_A2']=None;issues.append('SASA:'+str(exc))
    setfield(result,'D_native_3D',d3d)
    for key in ('record_id','molecule_id','conformer_id','split','member_train','member_full','member_routine','reidentified_inchikey'):
        if key in row:setfield(result,key,row[key])
    setfield(result,'phase1_quality_codes',{key:row.get(key) for key in ('H01_abs_energy_per_atom','S01','S02_delta_energy_kcal_mol','B01','T01')})
    return result,issues

def exact(left,right,path='$'):
    if type(left)!=type(right):raise ValueError('Wire scalar/container type differs at '+path)
    if isinstance(left,dict):
        if left.keys()!=right.keys():raise ValueError('Wire dictionary keys differ at '+path)
        for key in left:exact(left[key],right[key],path+'.'+key)
    elif isinstance(left,list):
        if len(left)!=len(right):raise ValueError('Wire list length differs at '+path)
        for index,(a,b) in enumerate(zip(left,right)):exact(a,b,path+'['+str(index)+']')
    elif type(left) is float:
        if struct.pack('>d',left)!=struct.pack('>d',right):raise ValueError('Wire float64 bit pattern differs at '+path)
    elif left!=right:raise ValueError('Wire scalar differs at '+path)

def pack(value):
    import numpy as np
    if isinstance(value,dict):return {key:pack(item) for key,item in value.items()}
    if not isinstance(value,list) or not value:return value
    if all(type(item) is float for item in value):return np.asarray(value,dtype=np.float64)
    if all(type(item) is int for item in value):return np.asarray(value,dtype=np.int64)
    if all(type(item) is bool for item in value):return np.asarray(value,dtype=np.bool_)
    if all(isinstance(item,dict) and item.keys()==value[0].keys() for item in value):
        keys=sorted(value[0]);types={}
        for key in keys:
            kinds={type(item[key]) for item in value}
            if len(kinds)!=1 or next(iter(kinds)) not in (float,int,bool):break
            types[key]=next(iter(kinds))
        else:
            dtype=[(key,{float:'<f8',int:'<i8',bool:'?'}[types[key]]) for key in keys]
            result=np.empty(len(value),dtype=dtype)
            for key in keys:result[key]=[item[key] for item in value]
            return {'__C4_structured_numeric_array__':result,'key_order':tuple(keys)}
    return [pack(item) for item in value]

def unpack(value):
    import numpy as np
    if isinstance(value,np.ndarray):return value.tolist()
    if isinstance(value,dict):
        if '__C4_structured_numeric_array__' in value:
            array=value['__C4_structured_numeric_array__'];keys=value['key_order']
            return [{key:array[key][index].item() for key in keys} for index in range(len(array))]
        return {key:unpack(item) for key,item in value.items()}
    if isinstance(value,list):return [unpack(item) for item in value]
    return value

MISSING=object()
def lookup(detail,path):
    if isinstance(path,list):parts=path
    else:
        text=str(path).strip('/').replace('/','.')
        if text.startswith('detail.'):text=text[7:]
        if text.startswith('details.'):text=text[8:]
        parts=text.split('.')
    value=detail
    if parts and parts[0] not in detail and isinstance(detail.get('values'),dict):value=detail['values']
    for part in parts:
        if not isinstance(value,dict) or part not in value:return MISSING
        value=value[part]
    return value

def labels(details,entries,drop_derived=False):
    selected=[];qcs=[];issues=[];groups={};present=[]
    for task,detail in sorted(details.items()):
        qcs.append((task,detail.get('status'),detail.get('failure_code'),detail.get('qc_codes',[])))
    for index,entry in enumerate(entries):
        if entry.get('classification') not in ('physical_label','QC') or entry.get('dedup_of') or entry.get('excluded'):
            continue
        if drop_derived and entry.get('classification')=='physical_label' and entry.get('derived_from'):continue
        task=entry.get('task');path=entry.get('source_path','')
        if task=='pm7_B' and any(name in str(path) for name in ('polar_blocks','static_polar_block','STATIC_finite_field_tensors')):continue
        if task not in details:continue
        value=lookup(details[task],path)
        if value is MISSING:continue
        encoded=pack(value);exact(value,unpack(encoded))
        selected.append((index,encoded));present.append(index)
        groups.setdefault(task,[]).append((index,encoded))
    return {'registry_indexed_values':selected,'task_status_QC':qcs},groups,issues

def serialized(value,protocol=5):return pickle.dumps(value,protocol=protocol)

def compressed(buffer):
    import pyarrow as pa
    codec=pa.Codec('zstd',compression_level=3)
    return b'C4ZSTD3\x00'+struct.pack('<Q',len(buffer))+bytes(codec.compress(buffer))

if __name__=='__main__':print(json.dumps(metadata(),indent=2))
