"""Proposed-only small chemistry checks; never modify a pool or frozen output."""
import unittest
from unittest.mock import patch

from . import features_generic_candidate_v1 as candidate, screen


ACTUAL_CASES = (
    (7, "CCN1C=NC2=C(N=CN=C21)N", 7),
    (52, "CC(C(C)O)C(=O)SCCNC(=O)CCNC(=O)C(C(C)(C)COP(=O)(O)OP(=O)(O)OCC1C(C(C(O1)N2C=NC3=C(N=CN=C32)N)O)OP(=O)(O)O)O", 49),
    (53, "CC(C(=O)C)C(=O)SCCNC(=O)CCNC(=O)C(C(C)(C)COP(=O)(O)OP(=O)(O)OCC1C(C(C(O1)N2C=NC3=C(N=CN=C32)N)O)OP(=O)(O)O)O", 50),
)


class CandidateFeatureTests(unittest.TestCase):
    def test_source_boundary_keeps_exact_frozen_chemical_function_and_non_ring_ast(self):
        self.assertIs(candidate.chemical_flags, screen.chemical_flags)
        self.assertIs(candidate.rdkit_modules, screen.rdkit_modules)
        proof = candidate.source_scope_proof()
        self.assertFalse(proof["repair_applied"])
        self.assertFalse(proof["pool_modified"])
        self.assertEqual(proof["status"], "ONLY_GENERIC_RING_BLOCK_DIFFERS_NON_RING_AST_IDENTICAL")

    def test_old_pass_fields_remain_exact_with_ring_topology_multiplicity_and_isotope(self):
        cases = ("CC", "c1ccccc1", "c1cc[nH]c1", "C1CC2CCC1C2", "c1ccccc1-c1ccccc1", "[13CH3][C@H]1CCCCC1")
        for cid, smiles in enumerate(cases, 1001):
            with self.subTest(smiles=smiles):
                old = screen.features(cid, smiles, cid)
                new = candidate.features_candidate(cid, smiles, cid)
                self.assertEqual(old["reasons"], [])
                self.assertEqual(candidate.compare_pass_fields(old, new)["field_differences"], {})
                if smiles == "c1ccccc1-c1ccccc1":
                    self.assertEqual(len(new["generic_ring_systems"]), 2)
                if smiles.startswith("[13CH3]"):
                    self.assertEqual(new["isotopic_atoms"], 1)

    def test_original_rejections_never_reach_candidate_ring_helper(self):
        for smiles in ("C.C", "C[NH3+]"):
            with self.subTest(smiles=smiles), patch.object(candidate, "generic_ring_systems_candidate", side_effect=AssertionError("must not run")):
                old = screen.features(2001, smiles, 2001)
                self.assertTrue(old["reasons"])
                self.assertEqual(candidate.features_candidate(2001, smiles, 2001), old)

    def test_three_observed_cases_and_minimal_n_substitution_are_candidate_only(self):
        for cid, smiles, ordinal in (*ACTUAL_CASES, (3001, "Cn1cccc1", 3001)):
            with self.subTest(cid=cid):
                mol, flags = screen.chemical_flags(smiles)
                self.assertFalse(any(flags.values()))
                with self.assertRaises(Exception) as error:
                    screen.features(cid, smiles, ordinal)
                self.assertEqual(type(error.exception).__name__, "KekulizeException")
                value = candidate.features_candidate(cid, smiles, ordinal)
                self.assertEqual(value["reasons"], [])
                comparisons = candidate.evaluate_fragment_orders(mol)
                self.assertTrue(any(row["legacy"]["status"] == "ERROR" for row in comparisons))
                self.assertTrue(all(row["candidate"]["status"] == "PASS" and
                                    row["candidate"]["retained_heavy_atom_adjacency_equal"] for row in comparisons))
                self.assertEqual(len(value["generic_ring_systems"]), 2 if cid in (52, 53) else 1)


if __name__ == "__main__":
    unittest.main()
