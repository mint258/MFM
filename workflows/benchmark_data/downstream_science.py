"""Downstream input adapter for the original S-prime and D scientific routines."""
import hashlib
import importlib
import importlib.util
import math
from pathlib import Path
import sys
import types
import numpy as np
from rdkit import Chem,rdBase
from rdkit.Chem import AllChem,rdtrajectory
from workflows.data_v1_final.labels.common import D20_NAMES

OBJECTS=None
REPO=Path(__file__).resolve().parents[2]


def load():
    global OBJECTS
    if OBJECTS is not None:return OBJECTS
    if rdBase.rdkitVersion!='2025.09.5':raise RuntimeError('Original RDKit version required')
    scripts=REPO/'workflows/sprime_s/scripts'
    prior=sys.modules.get('prepare')
    if prior is not None and Path(prior.__file__).resolve()!=scripts/'prepare.py':
        raise RuntimeError('Foreign prepare module would alter original imports')
    sys.path.insert(0,str(scripts))
    try:
        spec=importlib.util.spec_from_file_location('_benchmark_original_sprime',scripts/'sprime_v6.py')
        science=importlib.util.module_from_spec(spec);spec.loader.exec_module(science)
    finally:sys.path.pop(0)
    package='_benchmark_original_descriptor_sources'
    if package not in sys.modules:
        module=types.ModuleType(package);module.__path__=[str(REPO/'legacy/descriptor/dataset')]
        module.__package__=package;sys.modules[package]=module
    generator=importlib.import_module(package+'.rdkit_descriptor_generator')
    functions={name:fn for name,fn,mode in generator.GRAPH_DESCRIPTOR_SPECS if mode=='2d'}
    if not set(D20_NAMES)<=set(functions):raise RuntimeError('Original D20 functions missing')
    path=Path('/share/home/zixiao/descriptor_analysis/runs/phase1_screening_20261011/scripts/c_engineering_wire.py')
    spec=importlib.util.spec_from_file_location('_benchmark_original_D3_wire',path)
    wire=importlib.util.module_from_spec(spec);spec.loader.exec_module(wire)
    wire.metadata()
    if list(wire.D20)!=D20_NAMES:raise RuntimeError('Original D20 order differs')
    OBJECTS=science,functions,wire
    return OBJECTS


def identities(smiles):
    # Exact ordered model SMILES share one geometry calculation. Per-source
    # atom maps remain in membership; equivalent differently ordered strings
    # are not silently atom-remapped or collapsed.
    digest=hashlib.sha256(('benchmark-ordered-model-smiles-v1:'+smiles).encode()).hexdigest()
    mid='benchmark-downstream-v1:'+digest
    seed=max(1,int.from_bytes(hashlib.sha256(('sprime-ETKDGv3-v1:'+mid).encode()).digest()[:4],'big')&0x7fffffff)
    return mid,seed


def graph_descriptors(template):
    _,functions,_=load()
    values=[];mask=[];issues=[]
    for name in D20_NAMES:
        try:
            value=float(functions[name](template));valid=math.isfinite(value)
            if not valid:issues.append(name+':NONFINITE')
        except Exception as exc:value=float('nan');valid=False;issues.append(name+':'+repr(exc))
        values.append(value);mask.append(valid)
    return {'names':D20_NAMES,'values':values,'valid_mask':mask,'issues':issues}


def geometry_descriptors(smiles,mol,z,xyz,d20):
    import torch
    _,_,wire=load()
    shell=torch.full((len(wire.GRAPH_NAMES),),float('nan'),dtype=torch.float64)
    mask=torch.zeros(len(shell),dtype=torch.bool)
    for name,value,valid in zip(d20['names'],d20['values'],d20['valid_mask']):
        index=wire.GRAPH_NAMES.index(name);shell[index]=value;mask[index]=valid
    edges=np.asarray([(b.GetBeginAtomIdx(),b.GetEndAtomIdx()) for b in mol.GetBonds()],dtype=np.int64).reshape(-1,2).T
    raw={'smiles':smiles,'x':torch.tensor(np.asarray(z)-1,dtype=torch.int64),
        'pos':torch.tensor(xyz,dtype=torch.float64),'rdkit_graph_desc':shell,
        'rdkit_graph_desc_mask':mask,'rdkit_bond_index':torch.tensor(edges,dtype=torch.int64)}
    output,issues=wire.corrected_base(raw,{'smiles':smiles})
    d3=output['D_native_3D']
    if d3['SASA_atom_A2'] is not None:d3['SASA_atom_A2']=d3['SASA_atom_A2'].tolist()
    return d3,issues


def process(task):
    science,_,_=load()
    mid,seed=identities(task['model_smiles'])
    result={'molecule_id':mid,'seed':seed,'model_smiles':task['model_smiles'],
        'state':'UNPROCESSED','D20':None,'conformers':[],'error':None,
        'embedding_calls':0,'candidate_requested':9,'candidate_embedded':0,
        'nonconverged_candidates':0,'stereo_rejected_candidates':0,
        'no_scientific_retry':True,'PM7_optimized_geometry_available':False}
    try:
        params=Chem.SmilesParserParams();params.removeHs=False
        template=Chem.MolFromSmiles(task['model_smiles'],params)
        if template is None:raise ValueError('SOURCE_MODEL_GRAPH_UNAVAILABLE')
        result['D20']=graph_descriptors(Chem.RemoveHs(Chem.Mol(template)))
        mol=Chem.AddHs(template)
        z=[a.GetAtomicNum() for a in mol.GetAtoms()]
        result['atomic_numbers']=z
        result['model_atom_to_template']=list(range(template.GetNumAtoms()))+[-1]*(len(z)-template.GetNumAtoms())
        unresolved=[{'kind':str(info.type),'source_model_atom_or_bond_index':int(info.centeredOn)}
            for info in Chem.FindPotentialStereo(mol) if str(info.specified)!='Specified' and science.stereo_scope(mol,info)]
        if unresolved:
            result.update(state='D20_READY_STEREO_REFERENCE_UNAVAILABLE',unassigned_stereo=unresolved)
            return result
        if not AllChem.UFFHasAllMoleculeParams(mol):
            result['state']='D20_READY_UFF_UNSUPPORTED';return result
        embed=AllChem.ETKDGv3();embed.randomSeed=seed;embed.numThreads=1
        embed.enforceChirality=True;embed.pruneRmsThresh=-1.;embed.maxIterations=200
        result['embedding_calls']=1
        ids=list(AllChem.EmbedMultipleConfs(mol,numConfs=9,params=embed))
        result['candidate_embedded']=len(ids)
        candidates=[]
        for cid in ids:
            ff=AllChem.UFFGetMoleculeForceField(mol,confId=cid)
            code,trajectory=ff.MinimizeTrajectory(snapshotFreq=1,maxIts=2000,energyTol=1e-6,forceTol=1e-4)
            xyz=np.asarray(mol.GetConformer(cid).GetPositions(),dtype=np.float64)
            energy=float(ff.CalcEnergy())
            if code!=0:result['nonconverged_candidates']+=1;continue
            if not np.isfinite(xyz).all() or not math.isfinite(energy):continue
            if not science.check_geometry_stereo(mol,cid):result['stereo_rejected_candidates']+=1;continue
            candidates.append((energy,int(cid),xyz,len(trajectory)))
        selected=[]
        for energy,cid,xyz,iterations in sorted(candidates,key=lambda r:(r[0],r[1])):
            if any(science.rmsd(mol,xyz,old['coordinates_A'])<0.5 for old in selected):continue
            try:d3,issues=geometry_descriptors(task['model_smiles'],mol,z,xyz,result['D20'])
            except Exception as exc:d3=None;issues=['D3_SOURCE_MAPPING_OR_PROPERTY_FAILED:'+repr(exc)]
            selected.append({'conformer_id':len(selected),'candidate_id':cid,'geometry_source':'UFF_Sprime',
                'coordinates_A':xyz.tolist(),'uff_energy_kcal_mol':energy,'converged':True,
                'trajectory_snapshots':iterations,'D3':d3,'D3_issues':issues})
            if len(selected)==3:break
        result['conformers']=selected
        if selected:
            complete=all(result['D20']['valid_mask']) and all(row['D3'] is not None and not row['D3_issues'] for row in selected)
            result['state']='SPRIME_AND_D_READY' if complete else 'SPRIME_READY_D_PARTIAL'
        else:result['state']='D20_READY_NO_ACCEPTED_CONFORMERS'
    except Exception as exc:
        result['state']='D20_READY_GEOMETRY_FAILED' if result['D20'] else 'SOURCE_OR_IMPLEMENTATION_FAILED'
        result['error']=repr(exc)
    return result
