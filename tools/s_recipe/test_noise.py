"""Taskbook section 5: new noise mathematics and source-graph rotor rules."""
import math

import torch
from rdkit import Chem

from noise import (Rotor, align_source_graph, apply_geometry_noise, geometry_noise,
                   precompute_rotors, rotate_fragments, source_ordered_molecule)


def test_disabled_is_exact_identity():
    sentinel = object()
    before = torch.get_rng_state().clone()
    assert apply_geometry_noise(sentinel) is sentinel
    assert torch.equal(before, torch.get_rng_state())


def test_only_geometry_view_changes_and_source_order_is_retained():
    from torch_geometric.data import Batch, Data
    from phychem_mfm.phase1.v3_structural import build_structural_views, StructuralViewConfig
    records = [Data(x=torch.tensor([[5], [7], [0], [0]]),
                    pos=torch.arange(12, dtype=torch.float32).reshape(4, 3))]
    views = build_structural_views(Batch.from_data_list(records), ordinals=(17,),
                                   config=StructuralViewConfig(seed=0))
    changed = apply_geometry_noise(views, mode='multiscale')
    fallback = apply_geometry_noise(views, mode='frad', rotor_plans=[()])
    assert torch.equal(fallback.batch.pos, views.batch.pos)
    assert torch.equal(fallback.batch.target_pos, views.batch.target_pos)
    before, after = views.batch.to_data_list(), changed.batch.to_data_list()
    for a, b in zip(before, after):
        assert torch.equal(a.x, b.x)
        assert torch.equal(a.target_x, b.target_x)
        assert torch.equal(a.element_corrupt_mask, b.element_corrupt_mask)
        assert torch.equal(a.target_pos, b.target_pos)
        if int(a.sample_type_id.item()) != 1:
            assert torch.equal(a.pos, b.pos)


def test_multiscale_probability_and_per_axis_variance():
    # Independent samples select one sigma each. Six-SE bounds include both
    # mixture uncertainty and finite-coordinate Gaussian sampling error.
    n, atoms = 10000, 12
    pos = torch.zeros((atoms, 3), dtype=torch.float64)
    squares, high = [], 0
    for seed in range(n):
        noisy, reference, sigma = geometry_noise(pos, mode='multiscale', seed=seed)
        high += sigma > .1
        squares.append((noisy - reference).square().mean(0))
    assert abs(high / n - .5) <= 6 * math.sqrt(.25 / n)
    variance = torch.stack(squares).mean(0)
    fourth = 3 * (.05**4 + .0175**2) / 2
    mixture_variance = ((.05**4 + .0175**2) / 2 - .01**2)
    se = math.sqrt((mixture_variance + (fourth - (.05**4 + .0175**2)/2) / atoms) / n)
    assert torch.all((variance - .01).abs() < 6 * se)


def test_one_side_rigid_rotation_fp64_and_fp32():
    base = torch.tensor([[0., 0., 0.], [1., 0., 0.], [2., 1., 0.],
                         [3., 1., 1.], [-1., 1., 0.]], dtype=torch.float64)
    rotor = Rotor(0, 1, (1, 2, 3))
    for dtype, tolerance in ((torch.float64, 1e-9), (torch.float32, 1e-6)):
        pos = base.to(dtype)
        rotated = rotate_fragments(pos, (rotor,), [1.23])
        assert torch.equal(pos[[0, 4]], rotated[[0, 4]])
        assert not torch.equal(pos[2], rotated[2])
        original = torch.pdist(pos[[1, 2, 3]])
        changed = torch.pdist(rotated[[1, 2, 3]])
        error = (original - changed).abs()
        if dtype == torch.float64:
            assert torch.all(error <= tolerance)
            assert torch.all(error / original <= tolerance)
            assert abs(float(torch.dist(pos[0], pos[1]) - torch.dist(rotated[0], rotated[1]))) <= tolerance
        else:
            print('FP32 report-only rigid-rotation max_abs/max_rel:',
                  float(error.max()), float((error/original).max()))


def test_frad_target_sign_and_no_rotor_fallback():
    pos = torch.tensor([[0., 0., 0.], [1., 0., 0.], [2., 1., 0.],
                        [3., 1., 1.], [4., 2., 1.]], dtype=torch.float64)
    baseline = geometry_noise(pos, mode='baseline', seed=31)
    fallback = geometry_noise(pos, mode='frad', seed=31)
    assert all(torch.equal(a, b) for a, b in zip(baseline[:2], fallback[:2]))
    rotor = Rotor(0, 1, (1, 2, 3, 4))
    noisy, reference, _ = geometry_noise(pos, mode='frad', seed=31, rotors=(rotor,))
    assert not torch.allclose(reference, pos)
    # Coordinate target excludes the torsion displacement, with original sign.
    assert torch.allclose(noisy - reference, baseline[0] - pos, atol=1e-14, rtol=1e-14)


def test_strict_rotors_keep_source_indices_and_reject_amides_rings_terminals():
    for smiles in ('CC', 'CCC', 'C1CCCCC1', 'CC(=O)NC'):
        assert not precompute_rotors(Chem.AddHs(Chem.MolFromSmiles(smiles)))
    mol = Chem.AddHs(Chem.MolFromSmiles('CCCC'))
    rotors = precompute_rotors(mol)
    assert len(rotors) == 1
    assert {rotors[0].fixed, rotors[0].pivot} == {1, 2}
    assert rotors[0].fixed not in rotors[0].moving
    assert any(i >= 4 for i in rotors[0].moving)


def test_source_graph_mapping_preserves_charges_and_native_permutation():
    smiles = 'CCCC[N+](=O)[O-]'
    molecule = Chem.AddHs(Chem.MolFromSmiles(smiles))
    permutation = list(reversed(range(molecule.GetNumAtoms())))
    source = Chem.RenumberAtoms(molecule, permutation)
    types = {Chem.BondType.SINGLE: 1, Chem.BondType.DOUBLE: 2,
             Chem.BondType.TRIPLE: 3, Chem.BondType.AROMATIC: 4}
    atomic_numbers = [atom.GetAtomicNum() for atom in source.GetAtoms()]
    bonds = [(bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()) for bond in source.GetBonds()]
    codes = [types[bond.GetBondType()] for bond in source.GetBonds()]
    aligned = source_ordered_molecule(atomic_numbers, bonds, codes, smiles)
    assert [atom.GetAtomicNum() for atom in aligned.GetAtoms()] == atomic_numbers
    assert [atom.GetFormalCharge() for atom in aligned.GetAtoms()] == [
        atom.GetFormalCharge() for atom in source.GetAtoms()]
    for rotor in precompute_rotors(aligned):
        assert aligned.GetBondBetweenAtoms(rotor.fixed, rotor.pivot) is not None
        assert rotor.fixed not in rotor.moving
    generator = torch.Generator().manual_seed(4)
    pos = torch.randn((len(atomic_numbers), 3), generator=generator, dtype=torch.float64)
    _, reference, _ = geometry_noise(pos, mode='frad', seed=19, rotors=precompute_rotors(aligned))
    endpoints = torch.tensor(bonds, dtype=torch.long)
    before = torch.linalg.vector_norm(pos[endpoints[:, 0]]-pos[endpoints[:, 1]], dim=-1)
    after = torch.linalg.vector_norm(reference[endpoints[:, 0]]-reference[endpoints[:, 1]], dim=-1)
    assert torch.all((after-before).abs() <= 1e-6)
    assert torch.all((after-before).abs()/before <= 1e-9)


def test_native_graph_alignment_retains_existing_native_atom_identity():
    molecule = Chem.AddHs(Chem.MolFromSmiles('CCCC[N+](=O)[O-]'))
    types = {Chem.BondType.SINGLE: 1, Chem.BondType.DOUBLE: 2,
             Chem.BondType.TRIPLE: 3, Chem.BondType.AROMATIC: 4}
    numbers = [a.GetAtomicNum() for a in molecule.GetAtoms()]
    bonds = [(b.GetBeginAtomIdx(), b.GetEndAtomIdx()) for b in molecule.GetBonds()]
    codes = [types[b.GetBondType()] for b in molecule.GetBonds()]
    # Identical-topology automorphisms must not exchange known native atoms.
    for atom in molecule.GetAtoms():
        atom.SetIntProp('native_identity', atom.GetIdx())
    aligned = align_source_graph(numbers, bonds, codes, molecule)
    assert [a.GetIntProp('native_identity') for a in aligned.GetAtoms()] == list(range(len(numbers)))
    assert [a.GetFormalCharge() for a in aligned.GetAtoms()] == [a.GetFormalCharge() for a in molecule.GetAtoms()]
