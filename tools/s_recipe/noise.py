"""Opt-in geometry-only S noise; source order and other views stay intact."""
from dataclasses import dataclass
import math

import torch


FRAD_REVISION = '9972b8d80305acef0b381cbc4df5c6fe33c530ee'
FRAD_TORSION_STD_DEGREES = 2.0
# RDKit Release_2025_09_1, Descriptors/Lipinski.cpp, Strict, version 3.1.0.
STRICT_ROTOR_SMARTS = (
    '[!$(*#*)&!D1&!$(C(F)(F)F)&!$(C(Cl)(Cl)Cl)&!$(C(Br)(Br)Br)&!$(C([CH3])('
    '[CH3])[CH3])&!$([CD3](=[N,O,S])-!@[#7,O,S!D1])&!$([#7,O,S!D1]-!@[CD3]='
    '[N,O,S])&!$([CD3](=[N+])-!@[#7!D1])&!$([#7!D1]-!@[CD3]=[N+])]-,:;!@[!$'
    '(*#*)&!D1&!$(C(F)(F)F)&!$(C(Cl)(Cl)Cl)&!$(C(Br)(Br)Br)&!$(C([CH3])(['
    'CH3])[CH3])]'
)


@dataclass(frozen=True)
class Rotor:
    fixed: int
    pivot: int
    moving: tuple[int, ...]


def source_ordered_molecule(atomic_numbers, bonds, codes, source_smiles):
    """Align an original source-SMILES graph, preserving its formal charges.

    Production SMILES must be bound to the selected original native pointer
    by the closed source record-index metadata producer.
    """
    from rdkit import Chem
    molecule = Chem.MolFromSmiles(source_smiles)
    if molecule is None:
        raise ValueError('Published source SMILES cannot be parsed')
    molecule = Chem.AddHs(molecule)
    return align_source_graph(atomic_numbers, bonds, codes, molecule)


def align_source_graph(atomic_numbers, bonds, codes, molecule):
    """Bind an original native graph to compact atom order, retaining charges.

    The production caller supplies sprime_v6.graph(raw), which uses the actual
    source formal charges and bonds. No charges or missing H are inferred from
    the compact topology. A complete element/bond isomorphism is required.
    """
    from rdkit import Chem
    if molecule.GetNumAtoms() != len(atomic_numbers):
        raise ValueError('Native graph and compact source atom counts differ')
    if len(bonds) != len(codes):
        raise ValueError('Compact source bond/code counts differ')
    query = Chem.RWMol()
    for z in atomic_numbers:
        query.AddAtom(Chem.AtomFromSmarts('[#'+str(int(z))+']'))
    types = {1: Chem.BondType.SINGLE, 2: Chem.BondType.DOUBLE,
             3: Chem.BondType.TRIPLE, 4: Chem.BondType.AROMATIC}
    edges = {}
    for (a, b), code in zip(bonds, codes):
        edge, code = tuple(sorted((int(a), int(b)))), int(code)
        if code not in types or edge[0] == edge[1]:
            raise ValueError('Unsupported published source bond code')
        if edge in edges:
            if edges[edge] != code:
                raise ValueError('Conflicting source bond codes')
            continue
        edges[edge] = code
        query.AddBond(*edge, types[code])
    if len(edges) != molecule.GetNumBonds():
        raise ValueError('Native graph and compact source bond counts differ')
    native_edges = {tuple(sorted((b.GetBeginAtomIdx(), b.GetEndAtomIdx()))): b.GetBondType()
                    for b in molecule.GetBonds()}
    if (list(map(int, atomic_numbers)) == [a.GetAtomicNum() for a in molecule.GetAtoms()]
            and all(native_edges.get(edge) == types[code] for edge, code in edges.items())):
        # Preserve the known native ordering, including graph automorphisms.
        return Chem.Mol(molecule)
    match = molecule.GetSubstructMatch(query.GetMol())
    if len(match) != len(atomic_numbers):
        raise ValueError('Native graph has no complete compact source-order graph match')
    return Chem.RenumberAtoms(molecule, list(match))


def precompute_rotors(molecule):
    """Use the strict rule on the heavy graph, map back to source atom order.

    Explicit H atoms rotate with their parent fragment, but cannot create
    otherwise terminal rotors. No canonical atom reordering is performed.
    """
    from rdkit import Chem
    copy = Chem.Mol(molecule)
    for atom in copy.GetAtoms():
        atom.SetIntProp('_s_source_atom', atom.GetIdx())
    heavy = Chem.RemoveHs(copy)
    source = [atom.GetIntProp('_s_source_atom') for atom in heavy.GetAtoms()]
    query = Chem.MolFromSmarts(STRICT_ROTOR_SMARTS)
    rotors = []
    for a, b in heavy.GetSubstructMatches(query):
        if heavy.GetBondBetweenAtoms(a, b).GetBondType() != Chem.BondType.SINGLE:
            continue
        if not all(any(n.GetIdx() != other and n.GetAtomicNum() > 1
                       for n in heavy.GetAtomWithIdx(index).GetNeighbors())
                   for index, other in ((a, b), (b, a))):
            continue
        fixed, pivot = source[a], source[b]
        seen, todo = {pivot}, [pivot]
        while todo:
            atom = todo.pop()
            for neighbor in molecule.GetAtomWithIdx(atom).GetNeighbors():
                index = neighbor.GetIdx()
                if {atom, index} == {fixed, pivot} or index in seen:
                    continue
                seen.add(index)
                todo.append(index)
        if fixed in seen:
            raise ValueError('A rotor must disconnect the source graph')
        rotors.append(Rotor(fixed, pivot, tuple(sorted(seen))))
    return tuple(sorted(rotors, key=lambda r: (r.fixed, r.pivot)))


def rotate_fragments(pos, rotors, angles_radians):
    """Rotate one connected side per bond using current axes (Rodrigues)."""
    result = pos.clone()
    if len(rotors) != len(angles_radians):
        raise ValueError('One angle per source rotor required')
    for rotor, angle in zip(rotors, angles_radians):
        origin = result[rotor.pivot]
        axis = result[rotor.pivot] - result[rotor.fixed]
        norm = torch.linalg.vector_norm(axis)
        if not bool(torch.isfinite(norm)) or float(norm) == 0:
            raise ValueError('Degenerate source bond axis')
        axis = axis / norm
        indices = torch.tensor(rotor.moving, dtype=torch.long, device=pos.device)
        vector = result[indices] - origin
        angle = torch.as_tensor(angle, dtype=pos.dtype, device=pos.device)
        cosine, sine = torch.cos(angle), torch.sin(angle)
        result[indices] = origin + vector * cosine + torch.linalg.cross(
            axis.expand_as(vector), vector, dim=-1) * sine + (
                vector @ axis).unsqueeze(-1) * axis * (1 - cosine)
    return result


def multiscale_sigma(seed, *, device='cpu'):
    auxiliary = torch.Generator(device=device).manual_seed(seed ^ 0x53465241)
    return (.05, math.sqrt(.0175))[int(torch.randint(2, (), generator=auxiliary, device=device))]


def geometry_noise(pos, *, mode, seed, rotors=()):
    """Return noisy coordinates, denoising reference and per-sample sigma.

    Noise target is always noisy-reference in Angstrom; caller retains the
    baseline loss denominator 3*(0.1 Angstrom)^2 for BOTH noise arms.
    """
    if mode not in ('baseline', 'multiscale', 'frad'):
        raise ValueError('Unknown registered S noise mode')
    generator = torch.Generator(device=pos.device).manual_seed(seed)
    reference, sigma = pos, .1
    # A separate deterministic stream avoids changing the coordinate noise
    # when Frad has no rotors, or changing the molecule sampler's RNG.
    auxiliary = torch.Generator(device=pos.device).manual_seed(seed ^ 0x53465241)
    if mode == 'multiscale':
        sigma = multiscale_sigma(seed, device=pos.device)
    elif mode == 'frad' and rotors:
        angles = torch.randn(len(rotors), generator=auxiliary, dtype=pos.dtype,
                             device=pos.device) * math.radians(FRAD_TORSION_STD_DEGREES)
        reference = rotate_fragments(pos, rotors, angles)
    noise = torch.randn(pos.shape, generator=generator, dtype=pos.dtype, device=pos.device) * sigma
    return reference + noise, reference, sigma


def apply_geometry_noise(views, *, mode=None, rotor_plans=None):
    """None returns the exact original object without drawing randomness."""
    if mode is None or mode == 'baseline':
        return views
    from dataclasses import replace
    from torch_geometric.data import Batch
    records = views.batch.to_data_list()
    for graph, record in enumerate(records):
        if int(record.sample_type_id.item()) != 1:
            continue
        base = int(views.base_graph_index[graph])
        rotors = () if rotor_plans is None else rotor_plans[base]
        if mode == 'frad' and not rotors:
            # The legacy geometry builder consumes RNG for zero-amplitude
            # local operations before its Cartesian draw. Preserve its exact
            # real output in this explicitly required baseline fallback.
            continue
        seed = views.config.noise_seed(views.ordinals[base])
        _, reference, sigma = geometry_noise(
            record.target_pos, mode=mode, seed=seed,
            rotors=rotors)
        cartesian = record.pos - record.target_pos
        record.pos = reference + cartesian * (sigma / .1)
        record.target_pos = reference
    return replace(views, batch=Batch.from_data_list(records))
