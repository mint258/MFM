import unittest
from rdkit import Chem
from workflows.benchmark_data.domain import assess

class DomainTests(unittest.TestCase):
    def test_salt_removal_keeps_source_atom_mapping(self):
        r = assess("[Na+].CCO", adme=True)
        self.assertTrue(r["domain_eligible"])
        self.assertEqual(r["model_atom_to_source"], [1, 2, 3])
        self.assertTrue(r["salt_removed"])
        self.assertFalse(assess("[Na+].CCO", adme=False)["domain_eligible"])

    def test_charge_is_not_neutralized_and_blind_rows_are_retained(self):
        normal = assess("C[NH+](C)C", adme=True)
        blind = assess("C[NH+](C)C", adme=True, blind=True)
        self.assertEqual(normal["charge"], 1)
        self.assertFalse(normal["retained"])
        self.assertTrue(blind["retained"])
        self.assertTrue(blind["blind_fallback_required"])
        self.assertIn("NONZERO_CHARGE", blind["reasons"])

    def test_source_isotope_and_stereochemistry_are_preserved(self):
        source = "[13CH3][C@H](O)F"
        r = assess(source)
        self.assertTrue(r["domain_eligible"])
        self.assertEqual(Chem.MolToSmiles(Chem.MolFromSmiles(source)),
                         Chem.MolToSmiles(Chem.MolFromSmiles(r["model_smiles"])))

    def test_explicit_hydrogen_order_is_retained(self):
        r = assess("[H]C(C)O")
        self.assertTrue(r["domain_eligible"])
        self.assertEqual(r["model_atom_to_source"], [0, 1, 2, 3])

    def test_non_adme_fragments_are_not_an_extra_domain_exclusion(self):
        r = assess("CCC.CCC")
        self.assertTrue(r["domain_eligible"])
        self.assertFalse(r["salt_removed"])
    def test_domain_boundaries_and_declared_spin(self):
        self.assertTrue(assess("CCO")["domain_eligible"])
        self.assertIn("HEAVY_ATOMS_OUTSIDE_3_200", assess("CC")["reasons"])
        self.assertIn("NON_SINGLET_OR_UNKNOWN", assess("CCC", multiplicity=3)["reasons"])
        self.assertIn("RADICAL", assess("[CH2]CC")["reasons"])
        self.assertTrue(assess("invalid", blind=True)["retained"])

if __name__ == "__main__":
    unittest.main()
