"""MID-local fair stereo assignment, independent of the UFF random stream."""
import ast
import collections
import random

from ..uff3_candidate_v1.core import seed_for, IntegrityError

STEREO_OFFSET = 0x53544552
STEREO_STRIDE = 0x9E3779B9
MAX_DRAWS = 4
FIELDS = ('stereo_assigned', 'assigned_isomeric_smiles',
          'n_assigned_tetrahedral', 'n_assigned_double_bond', 'stereo_draw_index')


def stereo_seed(mid, draw_index):
    if type(draw_index) is not int or not 0 <= draw_index < MAX_DRAWS:
        raise ValueError('STEREO_DRAW_OUT_OF_RANGE')
    return (seed_for(mid) + STEREO_OFFSET + draw_index * STEREO_STRIDE) & 0xffffffff


def in_scope(mol, info):
    from rdkit import Chem
    if str(info.type) == 'Atom_Tetrahedral':
        return True
    if str(info.type) == 'Bond_Double':
        bond = mol.GetBondWithIdx(info.centeredOn)
        return all(a.GetHybridization() != Chem.HybridizationType.SP
                   for a in (bond.GetBeginAtom(), bond.GetEndAtom()))
    return False


def graph(mol):
    return ([(a.GetAtomicNum(), a.GetIsotope(), a.GetFormalCharge()) for a in mol.GetAtoms()],
            sorted((min(b.GetBeginAtomIdx(), b.GetEndAtomIdx()),
                    max(b.GetBeginAtomIdx(), b.GetEndAtomIdx()), str(b.GetBondType()))
                   for b in mol.GetBonds()))


def preserve_specified(original, normalized):
    """Single ordered-graph check, allowing RDKit's bond/tag representation changes."""
    from rdkit import Chem
    tetra = {Chem.ChiralType.CHI_TETRAHEDRAL_CW, Chem.ChiralType.CHI_TETRAHEDRAL_CCW}
    trans = {Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOTRANS}
    cis = {Chem.BondStereo.STEREOZ, Chem.BondStereo.STEREOCIS}
    for atom in original.GetAtoms():
        if atom.GetChiralTag() not in tetra:
            continue
        other = normalized.GetAtomWithIdx(atom.GetIdx())
        before = [n.GetIdx() for n in atom.GetNeighbors()]
        after = [n.GetIdx() for n in other.GetNeighbors()]
        permutation = [before.index(i) for i in after]
        odd = sum(a > b for i,a in enumerate(permutation) for b in permutation[i+1:]) % 2
        if other.GetChiralTag() not in tetra or ((other.GetChiralTag() == atom.GetChiralTag()) == bool(odd)):
            raise IntegrityError('SPECIFIED_TETRAHEDRAL_STEREO_CHANGED')
    for bond in original.GetBonds():
        if bond.GetStereo() not in trans | cis:
            continue
        a, b = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        other = normalized.GetBondBetweenAtoms(a, b)
        refs = tuple(bond.GetStereoAtoms())
        if other.GetBeginAtomIdx() != a:
            refs = refs[::-1]
        other_refs = tuple(other.GetStereoAtoms())
        odd = sum(x != y for x,y in zip(refs,other_refs)) % 2
        if (len(other_refs) != 2 or other.GetStereo() not in trans | cis
                or (((other.GetStereo() in trans) == (bond.GetStereo() in trans)) == bool(odd))):
            raise IntegrityError('SPECIFIED_DOUBLE_BOND_STEREO_CHANGED')


def assign(template, mid, draw_index):
    """Normalize without atom-map labels, then restore the source atom order.

    Each unspecified element consumes exactly one fair bit. Sorting atom or bond
    indices only fixes bit-to-element correspondence; no isomer is enumerated.
    """
    from rdkit import Chem
    from rdkit.Chem import rdCIPLabeler
    mol = Chem.Mol(template)
    rng = random.Random(stereo_seed(mid, draw_index))
    targets = [i for i in Chem.FindPotentialStereo(mol, cleanIt=True)
               if str(i.specified) != 'Specified' and in_scope(mol, i)]
    if not targets:
        # Fully specified future inputs retain the exact native graph, including
        # bond/neighbor ordering. The new rule must not perturb their UFF path.
        result = defaults()
        result['assigned_isomeric_smiles'] = Chem.MolToSmiles(template, isomericSmiles=True)
        return Chem.Mol(template), result
    atoms, bonds = [], []
    for info in sorted(targets, key=lambda i: (str(i.type), int(i.centeredOn))):
        bit = rng.getrandbits(1)
        if str(info.type) == 'Atom_Tetrahedral':
            index = int(info.centeredOn)
            mol.GetAtomWithIdx(index).SetChiralTag(
                Chem.ChiralType.CHI_TETRAHEDRAL_CW if bit else Chem.ChiralType.CHI_TETRAHEDRAL_CCW)
            atoms.append(index)
        else:
            bond = mol.GetBondWithIdx(info.centeredOn)
            a, b = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
            # Explicit references are required by RDKit's E/Z stereo storage.
            left = sorted(n.GetIdx() for n in mol.GetAtomWithIdx(a).GetNeighbors() if n.GetIdx() != b)
            right = sorted(n.GetIdx() for n in mol.GetAtomWithIdx(b).GetNeighbors() if n.GetIdx() != a)
            if not left or not right:
                raise IntegrityError('POTENTIAL_DOUBLE_WITHOUT_STEREO_REFERENCES')
            bond.SetStereoAtoms(left[0], right[0])
            bond.SetStereo(Chem.BondStereo.STEREOE if bit else Chem.BondStereo.STEREOZ)
            bonds.append((a, b))
    Chem.SetDoubleBondNeighborDirections(mol)
    Chem.FindPotentialStereo(mol, cleanIt=True)
    smiles = Chem.MolToSmiles(mol, isomericSmiles=True)
    order = ast.literal_eval(mol.GetProp('_smilesAtomOutputOrder'))
    normalized = Chem.MolFromSmiles(smiles)
    if normalized is None or len(order) != mol.GetNumAtoms():
        raise IntegrityError('STEREO_NORMALIZATION_FAILED')
    inverse = [0] * len(order)
    for new, old in enumerate(order):
        inverse[old] = new
    normalized = Chem.RenumberAtoms(normalized, inverse)
    if graph(normalized) != graph(template):
        raise IntegrityError('STEREO_NORMALIZATION_CHANGED_ORDERED_GRAPH')
    rdCIPLabeler.AssignCIPLabels(normalized)
    specified_reference = Chem.Mol(template)
    Chem.FindPotentialStereo(specified_reference, cleanIt=True)
    preserve_specified(specified_reference, normalized)
    atom_labels = collections.Counter()
    bond_labels = collections.Counter()
    for index in atoms:
        atom = normalized.GetAtomWithIdx(index)
        if atom.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED:
            atom_labels[atom.GetProp('_CIPCode') if atom.HasProp('_CIPCode') else 'UNLABELLED'] += 1
    for a, b in bonds:
        bond = normalized.GetBondBetweenAtoms(a, b)
        if bond.GetStereo() != Chem.BondStereo.STEREONONE:
            label = bond.GetProp('_CIPCode') if bond.HasProp('_CIPCode') else str(bond.GetStereo()).removeprefix('STEREO')
            bond_labels[label] += 1
    metadata = dict(stereo_assigned=bool(targets), assigned_isomeric_smiles=smiles,
                    n_assigned_tetrahedral=sum(atom_labels.values()),
                    n_assigned_double_bond=sum(bond_labels.values()), stereo_draw_index=draw_index,
                    assigned_CIP_counts=dict(atom_labels), assigned_EZ_counts=dict(bond_labels))
    return normalized, metadata


def defaults():
    return dict(stereo_assigned=False, assigned_isomeric_smiles=None,
                n_assigned_tetrahedral=0, n_assigned_double_bond=0, stereo_draw_index=0,
                assigned_CIP_counts={}, assigned_EZ_counts={})


def redraw_required(packet):
    # Only a known all-candidate embedding/UFF failure allows another draw.
    return bool(packet.get('stereo_assigned') and packet.get('native_all_failed')
                and not packet['conformers'] and packet['state'] != 'SOURCE_INTEGRITY_HOLD')
