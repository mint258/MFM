import unittest
from rdkit import Chem
from .ppe_author_state import geometry_metadata,target_binding,binding_from_inferred

class AuthorStateTests(unittest.TestCase):
    def test_declared_state_is_read_without_replacing_reference_coordinates(self):
        self.assertEqual(geometry_metadata('0,1,C,9,8,7,O,6,5,4'),(0,1,[6,8]))
        self.assertEqual(geometry_metadata('-1,2,O,0,0,0'),(-1,2,[8]))
        with self.assertRaises(ValueError):geometry_metadata('0,1,C,1,2')

    def test_specific_typo_needs_index_formula_and_equal_original_expt(self):
        a='Tricyclo(5.2.1.0(2,6))decane';b='Tricyclo[5.2.1.0(2,6))decane'
        self.assertTrue(target_binding(644,a,b,'-14.34','-14.340',True)[0])
        self.assertFalse(target_binding(643,a,b,'-14.34','-14.34',True)[0])
        self.assertFalse(target_binding(644,a,b,'-14.34','-14.35',True)[0])
        self.assertFalse(target_binding(644,a,b,'-14.34','-14.34',False)[0])

    def test_already_inferred_graph_reuses_explicit_reference_indices(self):
        ref=Chem.AddHs(Chem.MolFromSmiles('CCO'))
        ref=Chem.RenumberAtoms(ref,list(reversed(range(ref.GetNumAtoms()))))
        z=[a.GetAtomicNum() for a in ref.GetAtoms()]
        bound=binding_from_inferred(ref,'CCO',z,None)
        self.assertEqual(sorted(bound['model_to_reference']),list(range(len(z))))
        mapped=[z[i] for i in bound['model_to_reference']]
        self.assertEqual(mapped,[a.GetAtomicNum() for a in Chem.AddHs(Chem.MolFromSmiles(bound['model_smiles'])).GetAtoms()])

if __name__=='__main__':unittest.main()