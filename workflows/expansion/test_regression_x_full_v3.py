"""Small checks for new compact encoding, full coverage and non-whitelist replay."""
from itertools import product
from pathlib import Path
import tempfile
import unittest

from . import regression_x_full_v3 as full
from .test_regression_x_v2 import failed_unassigned


class CompactFullTests(unittest.TestCase):
    def test_all_243_ternary_states_round_trip_and_reserved_values_stop(self):
        for values in product((False, True, None), repeat=5):
            flags = dict(zip(full.repaired.CODES, values))
            self.assertEqual(full.decode_flags(full.encode_flags(flags)), flags)
        with self.assertRaises(ValueError):
            full.decode_flags(3)
        with self.assertRaises(ValueError):
            full.encode_flags(dict(zip(full.repaired.CODES, (False, True, None, False, 1))))

    def test_unseen_unassigned_id_gets_same_cache_semantics_and_complete_detail(self):
        source = failed_unassigned()
        source.update(record_id="brand_new_full_scope_record", molecule_id="brand_new_full_scope_molecule")
        batch = full.evaluate_batch([source])
        self.assertEqual(batch["counts"]["native_rule_mismatch"], 0)
        self.assertEqual(batch["counts"]["historical_unassigned_x1_coalesce"], 1)
        self.assertEqual(len(batch["rows"]), 1)
        self.assertEqual(len(batch["mismatches"]), 1)
        packed = dict(zip(full.ROW_FIELDS, batch["rows"][0]))
        self.assertIsNone(full.decode_flags(packed["original_raw_nullable_flags"])["X01"])
        self.assertIs(full.decode_flags(packed["native_replayed_enriched_flags"])["X01"], False)
        self.assertIn(full.repaired.COALESCE_CAUSE, batch["mismatches"][0][-1])
        self.assertEqual(batch["mismatches"][0][0], source["record_id"])

    def test_full_id_coverage_rejects_duplicate_or_foreign_record_and_decodes_decisions(self):
        import duckdb
        import pyarrow as pa
        import pyarrow.parquet as pq
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "compact.parquet"
            for ids, succeeds in [(["a", "b", "c"], True), (["a", "a", "c"], False), (["a", "b", "foreign"], False)]:
                pq.write_table(pa.table({"record_id": ids, "molecule_id": ["ma", "mb", "mc"],
                                         "source_family": ["synthetic"] * 3,
                                         "decision_bits": pa.array([1, 2, 0], type=pa.uint16())}), path)
                db = duckdb.connect()
                try:
                    db.register("original", pa.table({"record_id": ["a", "b", "c"]}))
                    if succeeds:
                        self.assertTrue(full.coverage(db, path, 3)["complete_original_source_coverage"])
                        observed = db.execute("SELECT old_chemical_admit,new_graph_admit FROM full_decisions ORDER BY record_id").fetchall()
                        self.assertEqual(observed, [(True, False), (False, True), (False, False)])
                    else:
                        with self.assertRaisesRegex(ValueError, "every unique original"):
                            full.coverage(db, path, 3)
                finally:
                    db.close()


if __name__ == "__main__":
    unittest.main()
