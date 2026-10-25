"""Targeted cache/unknown boundary and frozen-pilot authorization checks."""
from pathlib import Path
import tempfile
import unittest

from . import regression_x_v1 as old, regression_x_v2 as repaired
from .test_regression_x_v1 import row


def failed_unassigned():
    r = row(smiles="not_a_valid_smiles")
    r.update(member_train=False, member_full=False, parse_failed=True, sanitize_failed=True,
             stored_graph_fragments=None, cached_geometry_components=None, X01_geometry_checked=False,
             X01=False, X03=None, X04=None, saved_X03=None, saved_X04=None, old_retained=False,
             geometry_evaluated=False, geometry_X01=None, formal_member=False)
    return r


class CacheBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old.rdkit_modules()

    def test_exact_unassigned_unknown_cache_boundary_keeps_raw_unknown_and_admission(self):
        r = failed_unassigned()
        before, after = old.evaluate(r), repaired.evaluate(r)
        self.assertTrue(before["native_rule_mismatch"])
        self.assertFalse(after["native_rule_mismatch"])
        self.assertFalse(after["unexplained"])
        self.assertTrue(after["historical_unassigned_x1_coalesce"])
        self.assertIsNone(after["layers"]["original_raw_nullable_flags"]["X01"])
        self.assertIsNone(after["layers"]["native_replayed_raw_flags"]["X01"])
        self.assertIs(after["layers"]["native_replayed_enriched_flags"]["X01"], False)
        self.assertIn(repaired.COALESCE_CAUSE, after["mismatch"]["causes"])
        for name in ("old_chemical_admit", "new_graph_admit", "old_final", "conditional_new_final", "portable_flag_mismatch"):
            self.assertEqual(before[name], after[name])

    def test_parse_failed_with_dot_remains_true_without_unknown_coalesce_label(self):
        r = failed_unassigned()
        r.update(smiles="bad.bad", X01=True, saved_X01=True)
        result = repaired.evaluate(r)
        self.assertFalse(result["native_rule_mismatch"])
        self.assertFalse(result["historical_unassigned_x1_coalesce"])
        self.assertIs(result["layers"]["original_raw_nullable_flags"]["X01"], True)

    def test_successful_graph_and_actual_geometry_component_remain_separate(self):
        r = row()
        r.update(sanitize_failed=False, cached_geometry_components=2, X01_geometry_checked=True,
                 X01=True, saved_X01=True, geometry_X01=True, old_retained=False, formal_member=False)
        result = repaired.evaluate(r)
        self.assertFalse(result["native_rule_mismatch"])
        self.assertTrue(result["cached_geometry_x1_augmentation"])
        self.assertIs(result["layers"]["native_replayed_raw_flags"]["X01"], False)
        self.assertIs(result["layers"]["native_replayed_enriched_flags"]["X01"], True)
        self.assertFalse(result["conditional_new_final"])

    def test_other_rule_drift_is_not_waived_by_parse_failure(self):
        r = failed_unassigned()
        r.update(X03=True, saved_X03=True)
        result = repaired.evaluate(r)
        self.assertTrue(result["native_rule_mismatch"])
        self.assertTrue(result["unexplained"])
        self.assertIn("X03", result["mismatch"]["raw_native_mismatch"])

    def test_checked_marker_and_stored_cache_false_cannot_hide_bad_enrichment(self):
        r = row()
        r.update(sanitize_failed=False, cached_geometry_components=2, X01_geometry_checked=False)
        result = repaired.evaluate(r)
        self.assertTrue(result["native_rule_mismatch"])
        self.assertTrue(result["unexplained"])
        self.assertIn("X01_geometry_checked", result["mismatch"]["enrichment_metadata_mismatch_fields"])
        self.assertIn("stored_X01_vs_exact_enrichment_formula", result["mismatch"]["enrichment_metadata_mismatch_fields"])


class FrozenPilotComparisonTests(unittest.TestCase):
    def test_all_ids_and_diagnosed_cohort_required_and_one_other_decision_change_stops(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        cohort = {f"r{i:05d}" for i in range(335)}
        previous, current = [], []
        for i in range(8741):
            rid = f"r{i:05d}"
            base = {"record_id": rid, "molecule_id": "m" + rid, "source_family": "synthetic",
                    "old_chemical_admit": False, "new_graph_admit": False, "old_final": False,
                    "conditional_new_final": False, "portable_flag_mismatch": rid in cohort,
                    "cached_geometry_x1_augmentation": False}
            previous.append({**base, "native_rule_mismatch": rid in cohort, "unexplained": rid in cohort})
            current.append({**base, "legacy_native_rule_mismatch": rid in cohort, "legacy_unexplained": rid in cohort,
                            "historical_unassigned_x1_coalesce": rid in cohort})
        with tempfile.TemporaryDirectory() as tmp:
            prior, now = Path(tmp) / "previous.parquet", Path(tmp) / "now.parquet"
            pq.write_table(pa.Table.from_pylist(previous), prior)
            pq.write_table(pa.Table.from_pylist(current), now)
            db = duckdb.connect()
            try:
                result = repaired.compare_frozen_pilot(db, now, prior, cohort)
                self.assertTrue(result["all_frozen_v1_pilot_records_checked"])
                self.assertEqual(result["cohort_symmetric_difference"], 0)
            finally:
                db.close()
            current[-1]["conditional_new_final"] = True
            pq.write_table(pa.Table.from_pylist(current), now)
            db = duckdb.connect()
            try:
                with self.assertRaisesRegex(ValueError, "changes a decision"):
                    repaired.compare_frozen_pilot(db, now, prior, cohort)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
