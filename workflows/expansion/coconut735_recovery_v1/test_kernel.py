"""Meaningful no-leak boundaries for original wildcard-source evidence."""
import unittest
from .kernel import observe_variant, dominates


class Boundaries(unittest.TestCase):
    def test_wildcard_keeps_all_fixed_atoms_and_fragments(self):
        result = observe_variant('CC(*)O.CN')
        self.assertEqual(result['disposition'], 'CONSERVATIVE_NON_H_ATOM_LOWER_BOUND')
        self.assertEqual(result['bound'], [[6, 3], [7, 1], [8, 1]])
        self.assertEqual(result['dummy_atoms'], 1)
        self.assertTrue(dominates({6: 4, 7: 1, 8: 2}, result['bound']))
        self.assertFalse(dominates({6: 2, 7: 1, 8: 2}, result['bound']))
        self.assertEqual(result['full_key_computations'], 0)
        self.assertFalse(result['graph_repaired'])

    def test_invalid_dummy_only_and_names_do_not_become_covered(self):
        for text in ('*', '[H]*', 'CC(', 'CC name', 'CC\u00a0'):
            with self.subTest(text=text):
                self.assertEqual(observe_variant(text)['disposition'], 'HOLD')
        with self.assertRaises(ValueError):
            dominates({6: 10}, [])
        with self.assertRaises(ValueError):
            dominates({6: 10}, [[6, 0]])

    def test_fixed_disallowed_element_proves_x02_disjoint_without_keys(self):
        value = observe_variant('CC[Na].*')
        self.assertEqual(value['disposition'], 'CANDIDATE_DOMAIN_DISJOINT_X02')
        self.assertEqual(value['forbidden_fixed_elements'], [11])
        self.assertEqual(value['original'], 'CC[Na].*')
        self.assertEqual(value['full_keys'], [])


if __name__ == '__main__':
    unittest.main()
