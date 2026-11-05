"""Baseline-only complete geometries; original source coordinates remain immutable."""
from __future__ import annotations
import collections
import hashlib
import json
import math

QM7_GRAPH_PROVENANCE = 'Existing split_qm7_qm9_scaffold10._mol_from_qm7_xyz perceived graph: charge candidates [0,1,-1,2,-2,3,-3], DetermineBonds then connectivity/bond-orders; not author-assigned charge/bonds'
GEOMETRY_RECIPE = {'embedding':'ETKDGv3','embedding_calls':1,'maxIterations':200,
    'timeout_seconds':2,'numThreads':1,'clearConfs':True,'enforceChirality':True,
    'force_field':'MMFF94','max_iterations':500,'nonbonded_threshold':100.0,
    'ignore_interfragment_interactions':True,'fallback':'none',
    'seed_recipe':'native_etkdgv3_mmff94_seed_v1'}


def qm7_perceived_graph(numbers,coordinates):
    """Same numerical XYZ rounding and two-pass charge order as existing pipeline."""
    from rdkit import Chem
    from rdkit.Chem import rdDetermineBonds
    block=str(len(numbers))+'\nqm7_bohr_to_angstrom\n'
    block+='\n'.join('%s %.10f %.10f %.10f'%(Chem.GetPeriodicTable().GetElementSymbol(int(z)),*xyz)
        for z,xyz in zip(numbers,coordinates))+'\n'
    template=Chem.MolFromXYZBlock(block)
    if template is None:raise ValueError('QM7_EXISTING_GRAPH_RECIPE_XYZ_FAILED')
    for second_pass in (False,True):
        for charge in (0,1,-1,2,-2,3,-3):
            try:
                mol=Chem.Mol(template)
                if second_pass:
                    rdDetermineBonds.DetermineConnectivity(mol)
                    rdDetermineBonds.DetermineBondOrders(mol,charge=charge)
                else:rdDetermineBonds.DetermineBonds(mol,charge=charge)
                Chem.SanitizeMol(mol)
                return mol
            except Exception:continue
    raise ValueError('QM7_EXISTING_GRAPH_RECIPE_BOND_PERCEPTION_FAILED')


def graph_seed(mol):
    """Original graph-only scientific seed; these digests are not file integrity QA."""
    def canonical(payload):
        return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    graph={'atoms':[[a.GetAtomicNum(),a.GetIsotope(),a.GetFormalCharge(),a.GetNumExplicitHs()] for a in mol.GetAtoms()],
        'bonds':sorted([[min(b.GetBeginAtomIdx(),b.GetEndAtomIdx()),max(b.GetBeginAtomIdx(),b.GetEndAtomIdx()),
            str(b.GetBondType()),bool(b.GetIsAromatic())] for b in mol.GetBonds()])}
    material=canonical({'recipe':'native_etkdgv3_mmff94_seed_v1',
        'atomic_numbers':[a.GetAtomicNum() for a in mol.GetAtoms()], 'ordered_graph_hash':canonical(graph)})
    return 1+int(material[:8],16)%(2**31-2)


def complete_geometry(structure):
    """Reuse complete native XYZ; otherwise preserve native rows and append work H.

    Missing all coordinates uses precisely the existing ETKDGv3/MMFF recipe once.
    No source molecule/conformer or existing data file is changed.
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem
    mol=structure['mol'];numbers=structure['atomic_numbers'];coordinates=structure['coordinates_A']
    if mol is None:raise ValueError('SOURCE_GRAPH_CHARGE_SPIN_UNDETERMINED')
    result=dict(structure)
    scratch=Chem.Mol(mol);scratch.RemoveAllConformers()
    graph_numbers=[a.GetAtomicNum() for a in scratch.GetAtoms()]
    full=Chem.AddHs(scratch)
    full_numbers=[a.GetAtomicNum() for a in full.GetAtoms()]
    if coordinates is not None and collections.Counter(full_numbers)==collections.Counter(numbers):
        result.update(geometry_policy='REUSED_COMPLETE_EXISTING_NATIVE_GEOMETRY',
            xtb_source_atom_ids=list(range(len(numbers))),geometry_seed=None,geometry_mmff_status=None,
            geometry_recipe=None)
        return result
    if len(Chem.GetMolFrags(scratch))!=1:
        raise ValueError('EXISTING_RECIPE_DISCONNECTED_GRAPH_UNSUPPORTED')
    fixed=coordinates is not None
    if fixed:
        if numbers!=graph_numbers:raise ValueError('H_COMPLETION_SOURCE_ATOM_ORDER_OR_COMPOSITION_MISMATCH')
        conformer=Chem.Conformer(len(numbers));conformer.Set3D(True)
        for i,xyz in enumerate(coordinates):conformer.SetAtomPosition(i,tuple(map(float,xyz)))
        scratch.AddConformer(conformer,assignId=True)
        full=Chem.AddHs(scratch,addCoords=True)
        seed=None
    else:
        seed=graph_seed(scratch)
        parameters=AllChem.ETKDGv3()
        parameters.randomSeed=seed;parameters.numThreads=1;parameters.maxIterations=200
        parameters.timeout=2;parameters.clearConfs=True;parameters.enforceChirality=True;parameters.trackFailures=True
        if AllChem.EmbedMolecule(full,parameters)<0 or full.GetNumConformers()!=1:
            raise ValueError('BASELINE_EXISTING_ETKDG_RECIPE_FAILED_NO_FALLBACK')
    properties=AllChem.MMFFGetMoleculeProperties(full,mmffVariant='MMFF94')
    if properties is None:raise ValueError('BASELINE_MMFF94_PARAMETERS_UNAVAILABLE')
    field=AllChem.MMFFGetMoleculeForceField(full,properties,nonBondedThresh=100.0,confId=0,ignoreInterfragInteractions=True)
    if field is None:raise ValueError('BASELINE_MMFF94_FORCEFIELD_UNAVAILABLE')
    if fixed:
        for i in range(len(numbers)):field.AddFixedPoint(i)
    status=field.Minimize(maxIts=500)
    if status!=0:raise ValueError('BASELINE_MMFF94_NOT_CONVERGED_500')
    xyz=full.GetConformer().GetPositions().tolist()
    if any(not math.isfinite(float(v)) for row in xyz for v in row):raise ValueError('BASELINE_GEOMETRY_NONFINITE')
    if fixed and xyz[:len(numbers)]!=coordinates:
        raise ValueError('BASELINE_H_COMPLETION_MOVED_EXISTING_NATIVE_COORDINATES')
    result.update(atomic_numbers=[a.GetAtomicNum() for a in full.GetAtoms()],coordinates_A=xyz,
        geometry_policy=('H_COMPLETION_MMFF94_FIXED_ALL_EXISTING_NATIVE_ATOMS' if fixed else 'BASELINE_REBUILT_EXISTING_ETKDGV3_MMFF94_RECIPE'),
        xtb_source_atom_ids=[i if i<len(graph_numbers) else None for i in range(full.GetNumAtoms())],
        geometry_seed=seed,geometry_mmff_status=status,geometry_recipe=dict(GEOMETRY_RECIPE))
    return result
