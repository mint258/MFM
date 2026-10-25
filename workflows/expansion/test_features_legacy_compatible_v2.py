"""New compatibility fixtures only; original3 paired-prefix fixtures stay frozen."""
import unittest
from unittest.mock import patch

from . import features_legacy_compatible_v2 as compatible, features_generic_candidate_v1 as generic, screen


OLD_PASS_CASES = ((409, "C[N+]1(CCCC1C2=CN=CC=C2)[O-]", 387, ["C1CCCCC1", "[C]1CCCC1"]),
                  (554, "C[N+]1(CCCC1C(=O)[O-])C", 523, ["[C]1CCCC1"]))
OLD_FAILURE_CASES = (
    (7, "CCN1C=NC2=C(N=CN=C21)N", 7),
    (52, "CC(C(C)O)C(=O)SCCNC(=O)CCNC(=O)C(C(C)(C)COP(=O)(O)OP(=O)(O)OCC1C(C(C(O1)N2C=NC3=C(N=CN=C32)N)O)OP(=O)(O)O)O", 49),
    (53, "CC(C(=O)C)C(=O)SCCNC(=O)CCNC(=O)C(C(C)(C)COP(=O)(O)OP(=O)(O)OCC1C(C(C(O1)N2C=NC3=C(N=CN=C32)N)O)OP(=O)(O)O)O", 50),
)


class LegacyCompatibleFeatureTests(unittest.TestCase):
    def test_compositional_source_proof_and_passthrough_object(self):
        proof = compatible.source_scope_proof()
        self.assertEqual(proof["strategy"], compatible.STRATEGY)
        self.assertEqual(proof["nested_generic_fallback_proof"], generic.source_scope_proof())
        self.assertFalse(proof["wrapper_AST_equals_original_features_AST"])
        self.assertIs(compatible.chemical_flags, screen.chemical_flags)
        self.assertIs(compatible.wp5_key, screen.wp5_key)
        sentinel = {"sentinel": True}
        with patch.object(compatible, "_legacy_features", return_value=sentinel), \
                patch.object(compatible, "_fallback_features", side_effect=AssertionError("no fallback on success")):
            self.assertIs(compatible.features_candidate(1, "C", 1), sentinel)

    def test_real_old_success409_554_preserves_every_original_field(self):
        for cid, smiles, ordinal, expected_rings in OLD_PASS_CASES:
            with self.subTest(cid=cid):
                old = screen.features(cid, smiles, ordinal)
                self.assertEqual(old["generic_ring_systems"], expected_rings)
                self.assertNotEqual(generic.features_candidate(cid, smiles, ordinal)["generic_ring_systems"], expected_rings)
                with patch.object(compatible, "_fallback_features", side_effect=AssertionError("no fallback on oldPASS")):
                    new = compatible.features_candidate(cid, smiles, ordinal)
                self.assertEqual(new, old)

    def test_three_original_ring_kekulize_failures_use_tested_fallback(self):
        Chem, *_ = screen.rdkit_modules()
        for cid, smiles, ordinal in OLD_FAILURE_CASES:
            with self.subTest(cid=cid):
                with self.assertRaises(Chem.KekulizeException) as error:
                    screen.features(cid, smiles, ordinal)
                self.assertIs(type(error.exception), Chem.KekulizeException)
                self.assertEqual(compatible.features_candidate(cid, smiles, ordinal), generic.features_candidate(cid, smiles, ordinal))

    def test_non_kekulize_or_wrong_real_old_callsite_never_falls_back(self):
        Chem, *_ = screen.rdkit_modules()
        error = ValueError("non-kekulize must remain original")
        with patch.object(compatible, "_legacy_features", side_effect=error), \
                patch.object(compatible, "_fallback_features", side_effect=AssertionError("not allowed")):
            with self.assertRaises(ValueError) as caught:
                compatible.features_candidate(1, "C", 1)
            self.assertIs(caught.exception, error)
        wrong_site = Chem.KekulizeException("exact type but wrong old callsite")
        # This real frozen features frame is at MolToInchiKey, not line70.
        with patch.object(Chem, "MolToInchiKey", side_effect=wrong_site), \
                patch.object(compatible, "_fallback_features", side_effect=AssertionError("wrong site")):
            with self.assertRaises(Chem.KekulizeException) as caught:
                compatible.features_candidate(1, "CC", 1)
            self.assertIs(caught.exception, wrong_site)


if __name__ == "__main__":
    unittest.main()
