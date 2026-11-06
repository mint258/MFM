"""New stereo logic only: synthetic structures and mocked native failures."""
import collections
import unittest

from . import stereo
from .kernel import generate


class AssignmentTests(unittest.TestCase):
    def setUp(self):
        from rdkit import Chem
        self.Chem = Chem
        self.mol = Chem.MolFromSmiles('FC(Cl)C(Br)C=CC=CC')

    def test_same_mid_and_draw_are_reproducible_and_independent_of_uff_seed(self):
        for draw in range(4):
            a, x = stereo.assign(self.mol, 'synthetic:repeat', draw)
            b, y = stereo.assign(self.mol, 'synthetic:repeat', draw)
            self.assertEqual(x, y)
            self.assertEqual(stereo.graph(a), stereo.graph(self.mol))
            self.assertEqual(stereo.stereo_seed('synthetic:repeat', draw),
                             (stereo.seed_for('synthetic:repeat') + stereo.STEREO_OFFSET
                              + draw * stereo.STEREO_STRIDE) & 0xffffffff)
        self.assertEqual(stereo.assign(self.mol, 'synthetic:repeat', 0)[1]['n_assigned_tetrahedral'], 2)
        self.assertEqual(stereo.assign(self.mol, 'synthetic:repeat', 0)[1]['n_assigned_double_bond'], 2)

    def test_specified_stereo_is_preserved_in_source_atom_order(self):
        Chem = self.Chem
        mol = Chem.MolFromSmiles('F[C@H](Cl)C(Br)/C=C/C=CC')
        original_atoms = {a.GetIdx(): a.GetChiralTag() for a in mol.GetAtoms()
                          if a.GetChiralTag() != Chem.ChiralType.CHI_UNSPECIFIED}
        original_bonds = [(b.GetBeginAtomIdx(), b.GetEndAtomIdx(), b.GetStereo(), tuple(b.GetStereoAtoms()))
                          for b in mol.GetBonds() if b.GetStereo() != Chem.BondStereo.STEREONONE]
        for index in range(32):
            result, _ = stereo.assign(mol, 'synthetic:specified:' + str(index), index % 4)
            self.assertTrue(result.HasSubstructMatch(mol, useChirality=True))
            for atom, tag in original_atoms.items():
                self.assertEqual(result.GetAtomWithIdx(atom).GetChiralTag(), tag)
            for a, b, tag, refs in original_bonds:
                bond = result.GetBondBetweenAtoms(a, b)
                # Preserve geometric relation for the original reference pair.
                observed = tuple(bond.GetStereoAtoms())
                expected = refs if bond.GetBeginAtomIdx() == a else refs[::-1]
                flips = sum(x != y for x, y in zip(observed, expected))
                trans = {Chem.BondStereo.STEREOE, Chem.BondStereo.STEREOTRANS}
                self.assertEqual((bond.GetStereo() in trans) == (tag in trans), flips % 2 == 0)

    def test_multi_element_synthetic_collection_is_near_half(self):
        atoms, bonds = collections.Counter(), collections.Counter()
        for i in range(1024):
            _, result = stereo.assign(self.mol, 'synthetic:balanced:' + str(i), 0)
            atoms.update(result['assigned_CIP_counts'])
            bonds.update(result['assigned_EZ_counts'])
        self.assertEqual(atoms['R'] + atoms['S'], 2048)
        self.assertEqual(bonds['E'] + bonds['Z'], 2048)
        self.assertTrue(.45 < atoms['R'] / 2048 < .55, atoms)
        self.assertTrue(.45 < bonds['E'] / 2048 < .55, bonds)

    def test_normalization_does_not_invent_symmetric_centers(self):
        mol = self.Chem.MolFromSmiles('CC(C)CC=CC')
        _, result = stereo.assign(mol, 'synthetic:symmetry', 0)
        self.assertEqual(result['n_assigned_tetrahedral'], 0)
        self.assertEqual(result['n_assigned_double_bond'], 1)

    def test_fully_specified_input_preserves_native_neighbor_and_bond_order(self):
        mol = self.Chem.MolFromSmiles('F[C@H](Cl)/C=C/C')
        def native_graph(m):
            return ([(a.GetChiralTag(),tuple(n.GetIdx() for n in a.GetNeighbors())) for a in m.GetAtoms()],
                [(b.GetBeginAtomIdx(),b.GetEndAtomIdx(),b.GetStereo(),tuple(b.GetStereoAtoms())) for b in m.GetBonds()])
        before=native_graph(mol)
        result,metadata=stereo.assign(mol,'synthetic:already-specified',0)
        self.assertFalse(metadata['stereo_assigned'])
        self.assertEqual(native_graph(result),before)


class MockNative:
    def __init__(self, successes):
        self.successes = successes
        self.draws = []
        self.d20_calls = 0

    def prepare_geometry(self, source):
        self.draws.append(self.stereo_draw_index)
        self.stereo_metadata = dict(stereo.defaults(), stereo_assigned=True,
            assigned_isomeric_smiles='F[C@H](Cl)Br', n_assigned_tetrahedral=1,
            stereo_draw_index=self.stereo_draw_index)
        return dict(D20=None, atomic_numbers=[6], unassigned_stereo=[], uff_supported=True)

    def prepare(self, source):
        p = self.prepare_geometry(source)
        self.d20_calls += 1
        p['D20'] = {'original': 'reused across redraws'}
        return p

    def embed(self, seed, count):
        return list(range(self.successes[self.stereo_draw_index]))

    def optimize(self, cid):
        return dict(candidate_id=cid, coordinates=[[0., 0., 0.]], energy=float(cid),
                    optimizer_code=0, stereo_valid=True, iterations=1)

    def distance(self, a, b):
        return 1.

    def d3(self, row):
        return {'SASA_atom_A2': [1.]}, []


SOURCE = dict(pubchem_version='synthetic', cid=1, full_key='synthetic',
              source_smiles='FC(Cl)Br', isomeric_smiles='FC(Cl)Br', stream='R', stream_rank=1)


class RedrawTests(unittest.TestCase):
    def test_impossible_combination_redraws_but_shortage_does_not(self):
        k = MockNative([0, 1, 3, 3])
        p = generate(SOURCE, k)
        self.assertEqual(k.draws, [0, 1])
        self.assertEqual(k.d20_calls, 1)
        self.assertEqual(len(p['conformers']), 1)
        self.assertEqual(p['stereo_draw_index'], 1)
        self.assertEqual(p['state'], 'INSUFFICIENT_UNIQUE_CONFORMERS')

    def test_four_failed_draws_are_retained_and_no_d20_is_recomputed(self):
        k = MockNative([0, 0, 0, 0])
        p = generate(SOURCE, k, reuse_d20=True)
        self.assertEqual(k.draws, [0, 1, 2, 3])
        self.assertEqual(k.d20_calls, 0)
        self.assertEqual(len(p['stereo_draws']), 4)
        self.assertEqual(p['state'], 'EMBED_FAILED')

    def test_all_uff_rejected_redraws_and_positive_result_stops(self):
        k = MockNative([2, 3, 3, 3])
        optimize = k.optimize
        k.optimize = lambda cid: dict(optimize(cid), optimizer_code=int(k.stereo_draw_index == 0))
        p = generate(SOURCE, k, reuse_d20=True)
        self.assertEqual(k.draws, [0, 1])
        self.assertEqual(len(p['conformers']), 3)


if __name__ == '__main__':
    unittest.main()
