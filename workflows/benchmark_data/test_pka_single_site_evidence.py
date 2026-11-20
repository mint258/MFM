"""Chemical counterexamples for published-catalog site selection."""
import unittest
from .pka_single_site_evidence import compiled_catalog, proposed_target, site_evidence

class SiteEvidenceTests(unittest.TestCase):
    def test_all_published_patterns_and_map_zero_compile(self):
        self.assertEqual(len(compiled_catalog()),37)
        row=site_evidence("CCN")
        self.assertEqual(row["status"],"SINGLE_CATALOG_SITE")
        self.assertEqual(row["sites"][0]["model_atom_index"],2)

    def test_multiple_sites_and_symmetric_atoms_are_not_collapsed(self):
        for smiles in ("NCCN","NCC(=O)O","Oc1cccc(O)c1","NNC"):
            row=site_evidence(smiles)
            self.assertEqual(row["status"],"MULTIPLE_CATALOG_SITES",smiles)
            self.assertGreaterEqual(row["site_count"],2)

    def test_overlapping_amide_imide_patterns_count_one_atom(self):
        row=site_evidence("CC(=O)NC(C)=O")
        self.assertEqual(row["site_count"],1)
        self.assertEqual(row["sites"][0]["model_atom_index"],3)
        self.assertIn("amide",row["sites"][0]["source_group_names"])
        self.assertIn("imide_acyclic",row["sites"][0]["source_group_names"])

    def test_unrecognized_donor_and_charged_state_are_not_certified(self):
        for smiles in ("NCCO","CC[NH3+]","N=C(N)N"):
            row=site_evidence(smiles)
            self.assertNotEqual(row["status"],"SINGLE_CATALOG_SITE",smiles)

    def test_atom_mapping_and_additional_transition_block_assignment(self):
        target=dict(endpoint="macro_pKa_acid",charge_pre=0,charge_post=-1)
        row=site_evidence("CC(=O)O")
        proposed=proposed_target(target,row,{(0,-1)},[8,3,9,6])
        self.assertEqual(proposed["source_atom_index"],6)
        self.assertFalse(proposed["definition_approved"])
        self.assertIsNone(proposed_target(target,row,{(0,-1),(-1,-2)},[8,3,9,6]))
