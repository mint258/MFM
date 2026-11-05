"""New regression semantics/Parquet-join checks; no real data scans."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from . import regression_x_v1 as regression
from .common import reference


def row(record="r1", smiles="CC"):
    r = {"record_id": record, "molecule_id": "mol_" + record, "source_family": "synthetic", "source_path": "/synthetic.lmdb",
        "real_index": 0, "record_payload_sha256": "a" * 64, "smiles": smiles, "stored_graph_fragments": 1,
        "elements": [1, 6], "electron_count": 18, "native_x_encoding_or_shape_invalid": False,
        "atom_sequence_mismatch": False, "H_count_mismatch": False, "parse_failed": False,
        "member_train": True, "member_full": False, "heavy_atoms": 2, "X01_geometry_checked": False,
        "geometry_evaluated": True, "geometry_X01": False, "old_retained": True, "formal_member": True, "common_member": True}
    r.update({c: False for c in regression.CODES})
    r.update({"saved_" + c: False for c in regression.CODES})
    r.update({"extra_" + c: False for c in regression.EXTRA})
    return r


class RegressionSemanticsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            regression.rdkit_modules()
        except ImportError as exc:
            raise unittest.SkipTest("RDKit is absent; new regression checks pending") from exc

    def test_unchanged_original_graph_and_native_rules(self):
        result = regression.evaluate(row())
        self.assertFalse(result["native_rule_mismatch"])
        self.assertFalse(result["portable_flag_mismatch"])
        self.assertTrue(result["old_final"])
        self.assertTrue(result["conditional_new_final"])
        self.assertFalse(result["unexplained"])

    def test_native_hydrogen_difference_is_explicit_not_silent_rule_fix(self):
        r = row()
        r.update(electron_count=17, X05=True, saved_X05=True, old_retained=False, formal_member=False)
        result = regression.evaluate(r)
        self.assertFalse(result["native_rule_mismatch"])
        self.assertTrue(result["portable_flag_mismatch"])
        self.assertFalse(result["old_chemical_admit"])
        self.assertTrue(result["new_graph_admit"])
        self.assertIn("NATIVE_GRAPH_HYDROGEN_OR_ATOM_COUNT_DIFFERENCE", result["mismatch"]["causes"])
        self.assertFalse(result["unexplained"])

    def test_geometry_component_is_not_misreported_as_SMILES_rule_drift(self):
        r = row()
        r.update(X01_geometry_checked=True, X01=True, saved_X01=True, geometry_X01=True,
                 old_retained=False, formal_member=False)
        result = regression.evaluate(r)
        self.assertFalse(result["native_rule_mismatch"])
        self.assertTrue(result["cached_geometry_x1_augmentation"])
        self.assertFalse(result["conditional_new_final"])

    def test_unexplained_cached_graph_change_does_not_get_auto_explained(self):
        r = row()
        r.update(X03=True, saved_X03=True, old_retained=False, formal_member=False)
        result = regression.evaluate(r)
        self.assertTrue(result["unexplained"])
        self.assertIn("UNEXPLAINED_CACHED_RULE_DRIFT", result["mismatch"]["causes"])

    def test_unassigned_is_retained_in_regression_denominator(self):
        r = row()
        r.update(member_train=False, member_full=False, formal_member=False)
        result = regression.evaluate(r)
        self.assertTrue(result["new_graph_admit"])
        self.assertFalse(result["old_final"])
        self.assertFalse(result["conditional_new_final"])


class RegressionIOTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import duckdb
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise unittest.SkipTest("DuckDB/pyarrow absent; regression IO checks pending") from exc
        cls.duckdb, cls.pa, cls.pq = duckdb, pa, pq

    def fixtures(self, root):
        records = [row("r1"), row("r2"), row("r3")]
        records[1].update(member_train=False, member_full=False, formal_member=False)
        records[2].update(X01=True, saved_X01=True, stored_graph_fragments=2, old_retained=False, formal_member=False)
        sources = {}
        original = [{k: v for k, v in r.items() if not k.startswith(("saved_", "extra_")) and k not in
            ("geometry_evaluated", "geometry_X01", "old_retained", "formal_member", "common_member")} for r in records]
        quality = []
        for r in records:
            q = {"record_id": r["record_id"], "molecule_id": r["molecule_id"], "retained": r["old_retained"],
                 "geometry_evaluated": r["geometry_evaluated"], "geometry_X01": r["geometry_X01"]}
            q.update({c: r["saved_" + c] for c in regression.CODES})
            q.update({c: r["extra_" + c] for c in regression.EXTRA})
            quality.append(q)
        tables = {"original_index": original, "relaxed_quality": quality, "formal_population": [{"record_id": "r1"}],
                  "common_population": [{"molecule_id": "mol_r1"}]}
        for key, rows in tables.items():
            p = root / (key + ".parquet")
            self.pq.write_table(self.pa.Table.from_pylist(rows), p)
            sources[key] = reference(p)
        return sources

    def test_join_requires_all_original_records_and_supports_common_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = self.fixtures(Path(tmp))
            db = self.duckdb.connect()
            try:
                self.assertEqual(regression.prepare_join(db, sources, 3, 1), 3)
                self.assertEqual(db.execute("SELECT count(*) FILTER(WHERE common_member) FROM joined").fetchone()[0], 1)
                sampling = regression.select_pilot(db, 20261025, 100)
                selected = {s["stratum"] for s in sampling["selected_strata"]}
                self.assertTrue(any("unassigned" in s for s in selected))
                self.assertTrue(any("excluded" in s for s in selected))
            finally:
                db.close()

    def test_retained_only_population_cannot_claim_full_input_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = self.fixtures(Path(tmp))
            db = self.duckdb.connect()
            try:
                with self.assertRaises(ValueError): regression.prepare_join(db, sources, 15879477, 11231854)
            finally:
                db.close()

    def test_common_population_cannot_contain_an_unrepresented_molecule(self):
        with tempfile.TemporaryDirectory() as tmp:
            sources = self.fixtures(Path(tmp))
            p = Path(tmp) / "unknown_common.parquet"
            self.pq.write_table(self.pa.Table.from_pylist([{"molecule_id": "not_in_original"}]), p)
            sources["common_population"] = reference(p)
            db = self.duckdb.connect()
            try:
                with self.assertRaises(ValueError): regression.prepare_join(db, sources, 3, 1)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
