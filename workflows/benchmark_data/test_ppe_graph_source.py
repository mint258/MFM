import unittest
from workflows.benchmark_data.ppe_graph_source import name_key,formula_matches


class OriginalNameTests(unittest.TestCase):
    def test_only_lexical_name_differences_are_bound(self):
        self.assertEqual(name_key('1,1-Dichloroethane'),name_key('1,1-dichloroethane'))
        self.assertEqual(name_key('(1R,2S)‐1,2‐diethenylcyclobutane'),name_key('(1R,2S)-1,2-diethenylcyclobutane'))
        self.assertNotEqual(name_key('(1R,2S)-test'),name_key('(1r,2S)-test'))
        self.assertNotEqual(name_key('2-[2-(hydroxyethoxy)]ethanol'),name_key('2[2-(hydroxyethoxy)]ethanol'))

    def test_named_graph_formula_does_not_depend_on_atom_order(self):
        self.assertTrue(formula_matches('CCO',[8,6,6]+[1]*6))
        self.assertFalse(formula_matches('CCN',[8,6,6]+[1]*6))

if __name__=='__main__':unittest.main()
