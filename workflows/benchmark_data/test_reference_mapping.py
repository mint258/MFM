import unittest
import numpy as np
from workflows.benchmark_data.reference_mapping import map_reference,restore_atom_values


class ReferenceCorrespondenceTests(unittest.TestCase):
    def test_template_matches_permuted_reference_without_changing_coordinates(self):
        z=[8,8,6];xyz=[[-1.16,0.,0.],[1.18,0.,0.],[0.,0.,0.]];original=np.asarray(xyz).copy()
        result=map_reference('O=C=O',z,xyz)
        self.assertTrue(np.array_equal(original,xyz))
        self.assertEqual(result['reference_bond_pairs'],[(0,2),(1,2)])
        for atom,source_index in enumerate(result['model_to_reference']):
            self.assertEqual(result['model_atomic_numbers'][atom],z[source_index])
        self.assertFalse(result['author_original_atom_lineage_claimed'])

    def test_different_template_or_missing_isotope_binding_is_not_guessed(self):
        with self.assertRaises(ValueError):map_reference('CCO',[8,8,6],[[-1.16,0,0],[1.16,0,0],[0,0,0]])
        with self.assertRaises(ValueError):map_reference('[13C](=O)=O',[8,8,6],[[-1.16,0,0],[1.16,0,0],[0,0,0]])

    def test_atomic_labels_are_restored_to_the_original_reference_order(self):
        self.assertEqual(restore_atom_values([1.25,2.5,3.75],[2,0,1]),[2.5,3.75,1.25])
        with self.assertRaises(ValueError):restore_atom_values([1.,2.],[0,0])

if __name__=='__main__':unittest.main()
