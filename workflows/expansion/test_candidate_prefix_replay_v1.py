"""Minimal source-boundary tests; no RDKit/raw/SQLite scan or allocation here."""
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from . import candidate_prefix_replay_v1 as replay


class PairedPrefixBoundaryTests(unittest.TestCase):
    def row(self, value):
        return {"cid": 7, "ordinal": 7, "old_chemical_flags": {"X01": False, "X02": False, "X03": False,
                "X04": False, "X05": False}, "legacy": {"status": "PASS", "output": deepcopy(value)},
                "candidate": {"status": "PASS", "output": deepcopy(value)}, "fragment_order_audit": None}

    def test_not_ready_and_three_cid_scope_rejected_before_guard_or_data(self):
        plans = [{"schema": replay.SCHEMA, "status": "NOT_READY"},
                 {"schema": replay.SCHEMA, "status": "READY", "independent_scope_policy_reference": {},
                  "scope_key": "prefix_feature_three_cid", "scope_parameters": replay.PARAMETERS}]
        for plan in plans:
            with self.subTest(status=plan["status"]), patch.object(replay.policy, "load", return_value=plan), \
                    patch.object(replay.runtime, "root_guard") as guard, patch.object(replay, "hash_stable") as data:
                with self.assertRaises(ValueError):
                    replay.run(Path("/unused/plan.json"), Path("/unused/intent.json"))
                guard.assert_not_called()
                data.assert_not_called()

    def test_all_fields_and_alias_history_are_separate_exact_proofs(self):
        value = {"cid": 7, "ordinal": 7, "reasons": [], "full_key": "KEY", "generic_ring_systems": ["C1CC1"],
                 "isotopic_atoms": 1, "logp": 0.5}
        alias = {"cid": 7, "ordinal": 7, "full_key": "KEY"}
        result = replay.assess(self.row(value), alias, value, None)
        self.assertEqual(result["mismatch_codes"], [])
        self.assertTrue(result["historical_full_feature_row_exists"])
        duplicate = replay.assess(self.row(value), alias, None, None)
        self.assertTrue(duplicate["old_alias_has_no_separate_historical_feature_row"])
        self.assertIn("paired_all_fields", duplicate["comparisons"])
        self.assertNotIn("historical_stored_all_fields", duplicate["comparisons"])
        changed = self.row(value)
        changed["candidate"]["output"]["generic_ring_systems"] = ["C1CCC1"]
        self.assertIn("OLD_PASS_FEATURE_FIELD_DRIFT", replay.assess(changed, alias, value, None)["mismatch_codes"])
        typed = self.row(value)
        typed["candidate"]["output"]["isotopic_atoms"] = True
        self.assertIn("OLD_PASS_FEATURE_FIELD_DRIFT", replay.assess(typed, alias, value, None)["mismatch_codes"])
        historical = deepcopy(value)
        historical["logp"] = 0.6
        self.assertIn("HISTORICAL_STORED_FEATURE_FIELD_DRIFT", replay.assess(self.row(value), alias, historical, None)["mismatch_codes"])

    def test_chemical_reasons_and_every_feature_failure_are_classified(self):
        rejected = {"cid": 7, "ordinal": 7, "reasons": ["X03", "X05"]}
        row = self.row(rejected)
        row["old_chemical_flags"].update(X03=True, X05=True)
        result = replay.assess(row, None, None, rejected)
        self.assertEqual(result["classification"], "CHEMICAL_REJECTION_UNCHANGED")
        row["candidate"]["output"]["reasons"] = ["X05", "X03"]
        self.assertIn("CANDIDATE_CHEMICAL_REJECTION_DRIFT", replay.assess(row, None, None, rejected)["mismatch_codes"])
        failed = {"cid": 7, "ordinal": 7, "reasons": ["IDENTITY_OR_FEATURE_FAILED"], "error": "KekulizeException: old"}
        row = self.row({"cid": 7, "ordinal": 7, "reasons": [], "full_key": "KEY"})
        row["legacy"] = {"status": "ERROR", "historical_screen_batch_error": failed["error"]}
        with patch.object(replay, "_ring_origin_confirmed", return_value=True):
            self.assertEqual(replay.assess(row, None, None, failed)["classification"], "RECOVERED_CONFIRMED_GENERIC_RING_ORDER")
        with patch.object(replay, "_ring_origin_confirmed", return_value=False):
            self.assertEqual(replay.assess(row, None, None, failed)["classification"], "RECOVERED_ORIGIN_NOT_CONFIRMED")
        row["candidate"]["output"]["reasons"] = ["X03"]
        self.assertEqual(replay.assess(row, None, None, failed)["classification"], "PROPOSED_NEW_EXCLUSION_NOT_ALLOWED")
        row["candidate"] = {"status": "ERROR", "message": "retained"}
        self.assertEqual(replay.assess(row, None, None, failed)["classification"], "STILL_FAILING_PROPOSED_FEATURES")
        row["legacy"]["historical_screen_batch_error"] = "different"
        self.assertEqual(replay.assess(row, None, None, failed)["classification"], "ORIGINAL_ERROR_HAS_REPLAY_DRIFT")
        self.assertEqual(replay.assess(row, None, None, None)["classification"], "HISTORICAL_PARTITION_HAS_DRIFT")


if __name__ == "__main__":
    unittest.main()
