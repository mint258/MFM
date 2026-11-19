"""Map a source chemical template onto unchanged author reference XYZ indices."""
from collections import Counter
import numpy as np
from rdkit import Chem,rdBase
from rdkit.Chem import rdDetermineBonds

MAPPING_MAX_ITERATIONS=100000


def infer_reference_graph(numbers,coordinates,charge):
    if rdBase.rdkitVersion!='2025.09.5':raise RuntimeError('Original RDKit version required')
    xyz=np.asarray(coordinates,dtype=np.float64)
    if xyz.shape!=(len(numbers),3) or not np.isfinite(xyz).all():raise ValueError('Incomplete reference geometry')
    builder=Chem.RWMol()
    for z in numbers:builder.AddAtom(Chem.Atom(int(z)))
    mol=builder.GetMol();conf=Chem.Conformer(len(numbers));conf.Set3D(True)
    for index,point in enumerate(xyz):conf.SetAtomPosition(index,tuple(map(float,point)))
    mol.AddConformer(conf,assignId=True)
    # One deterministic graph-recovery pass. No coordinate optimization or
    # alternative chemistry is attempted if this cannot recover the template.
    rdDetermineBonds.DetermineBonds(mol,useHueckel=False,charge=int(charge),covFactor=1.3,
        allowChargedFragments=True,embedChiral=True,useAtomMap=False,useVdw=False,
        maxIterations=MAPPING_MAX_ITERATIONS)
    return mol


def model_graph(smiles):
    params=Chem.SmilesParserParams();params.removeHs=False
    original=Chem.MolFromSmiles(smiles,params)
    if original is None:raise ValueError('Original chemical template cannot be parsed')
    if any(a.GetIsotope() for a in original.GetAtoms()):
        raise ValueError('Reference XYZ does not specify the template isotope positions')
    heavy=Chem.RemoveHs(original)
    ordered_smiles=Chem.MolToSmiles(heavy,canonical=False,isomericSmiles=True)
    model=Chem.AddHs(Chem.MolFromSmiles(ordered_smiles))
    return ordered_smiles,model


def map_reference(smiles,numbers,coordinates):
    ordered_smiles,model=model_graph(smiles)
    if Counter(a.GetAtomicNum() for a in model.GetAtoms())!=Counter(map(int,numbers)):
        raise ValueError('Original chemical template and reference atom compositions differ')
    reference=infer_reference_graph(numbers,coordinates,Chem.GetFormalCharge(model))
    canon=lambda m:Chem.MolToSmiles(Chem.RemoveHs(m),canonical=True,isomericSmiles=False)
    if canon(model)!=canon(reference):raise ValueError('Reference reconstructed graph differs from original chemical template')
    match=reference.GetSubstructMatch(model,useChirality=True)
    if len(match)!=len(numbers) or len(set(match))!=len(match):
        raise ValueError('Full reference/template atom correspondence, including specified stereo, is unavailable')
    if any(model.GetAtomWithIdx(i).GetAtomicNum()!=int(numbers[j]) for i,j in enumerate(match)):
        raise ValueError('Model/reference atom identity differs')
    pairs=sorted(tuple(sorted((match[b.GetBeginAtomIdx()],match[b.GetEndAtomIdx()]))) for b in model.GetBonds())
    return {'model_smiles':ordered_smiles,'model_mol':model,'model_to_reference':list(match),
        'model_coordinates_A':np.asarray(coordinates,dtype=np.float64)[list(match)],
        'model_atomic_numbers':[a.GetAtomicNum() for a in model.GetAtoms()],
        'reference_bond_pairs':pairs,'mapping_basis':'One XYZ graph reconstruction; exact source chemical graph and specified stereo match',
        'reference_coordinates_modified':False,'author_original_atom_lineage_claimed':False}


def restore_atom_values(values,model_to_reference):
    if values is None:return None
    if len(values)!=len(model_to_reference) or sorted(model_to_reference)!=list(range(len(values))):
        raise ValueError('Per-atom values have no complete reference-order mapping')
    result=[None]*len(values)
    for model_index,source_index in enumerate(model_to_reference):result[source_index]=values[model_index]
    return result
