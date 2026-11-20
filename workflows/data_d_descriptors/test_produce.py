"""New store-state, mask and identity behavior without calculator execution."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from .produce import (check_checkpoint, closed_pilots, encode_status, guard,
                      plan_chunk, validate_rows)


class ProduceTests(unittest.TestCase):
    def test_mordred_missing_wrapped_overflow_and_returned_nonfinite_are_distinct(self):
        from mordred.error import Error, Missing
        from . import pilot
        results = [0., Missing(ZeroDivisionError("undefined descriptor"), []),
                   Error(OverflowError("descriptor overflow"), []), np.nan, np.inf,
                   Error(ValueError("not applicable"), [])]
        with patch.object(pilot, "LIBRARY", "L2"), patch.object(pilot, "FIELDS", list("abcdef")), \
                patch.object(pilot, "CALCULATOR", lambda molecule: results):
            raw, valid, numeric, reasons, _, _ = pilot.one("CC")
        np.testing.assert_array_equal(encode_status(np.asarray(raw), np.asarray(valid), np.asarray(numeric)),
                                      [1, 0, 2, 2, 2, 0])
        self.assertEqual(raw[0], 0.)
        self.assertTrue(np.isinf(raw[4]))
        self.assertIn("undefined descriptor", reasons[1])
        self.assertIn("NUMERIC_OVERFLOW", reasons[2])

    def write_rows(self, root, values):
        path = Path(root) / "rows.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in values), encoding="utf-8")
        return path

    def row(self, mid="a", index=0, split="TRAIN", role="TRAIN"):
        return dict(molecule_id=mid, molecule_index=index, split=split, role=role, smiles="CC")

    def test_missing_true_zero_and_numerical_failures_have_separate_states(self):
        raw = np.array([0.0, np.nan, np.nan, np.inf])
        result = encode_status(raw, np.array([True, False, False, True]),
                               np.array([False, False, True, False]))
        np.testing.assert_array_equal(result, [1, 0, 2, 2])
        self.assertEqual(raw[0], 0)

    def test_producer_checks_unique_id_and_split_index(self):
        with tempfile.TemporaryDirectory() as root:
            for rows in ([self.row(), self.row(index=1)],
                         [self.row(), self.row(mid="b")]):
                with self.assertRaisesRegex(ValueError, "DUPLICATE"):
                    validate_rows(self.write_rows(root, rows))
            result = validate_rows(self.write_rows(root, [self.row(), self.row("v", 0, "FULL", "VAL")]))
            self.assertEqual(result["role_counts"], {"TRAIN": 1, "VAL": 1})

    def test_forbids_test_or_role_split_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            for row in (self.row(role="TEST"), self.row(role="VAL"), self.row(split="FULL")):
                with self.assertRaises(ValueError):
                    validate_rows(self.write_rows(root, [row]))

    def test_resume_skips_only_valid_closed_parts_and_rejects_changed_identity(self):
        identity = {"library": "L2", "fields": ["x"], "chunk_rows": 256}
        state = {"identity": identity, "completed_parts": [0, 2]}
        self.assertEqual(check_checkpoint(state, identity, 4), {0, 2})
        with self.assertRaisesRegex(ValueError, "CONDITION_CHANGED"):
            check_checkpoint(state, dict(identity, fields=["y"]), 4)
        for bad in ([0, 0], [4], [-1], [True]):
            with self.assertRaisesRegex(ValueError, "INVALID_CLOSED"):
                check_checkpoint(dict(state, completed_parts=bad), identity, 4)

    def test_pilot_results_reused_only_for_identical_id_smiles_and_train_role(self):
        raw, flags = np.array([0.0, 3.0]), np.array([1, 1], dtype=np.uint8)
        cache = {"a": ("CC", raw, flags)}
        reused, missing = plan_chunk([self.row(), self.row("b", 1)], cache)
        self.assertIs(reused[0][0], raw)
        self.assertEqual(missing, [(1, "CC")])
        for row in (dict(self.row(), smiles="CCC"), self.row(split="FULL", role="VAL")):
            with self.assertRaisesRegex(ValueError, "STRUCTURE_OR_ROLE_CHANGED"):
                plan_chunk([row], cache)

    def test_both_costs_must_close_and_unresolved_library_is_not_invented(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path / "L1_cost.json").write_text(json.dumps({"status": "PILOT_COST_COMPLETE_NOT_DELIVERY",
                                                         "library": "L1", "molecules": 5000}))
            with self.assertRaises(FileNotFoundError):
                closed_pilots(path)
            (path / "L2_cost.json").write_text(json.dumps({"status": "UNRESOLVED"}))
            self.assertEqual(closed_pilots(path)["L2"]["status"], "UNRESOLVED")
            (path / "L2_cost.json").write_text(json.dumps({"status": "RUNNING"}))
            with self.assertRaisesRegex(ValueError, "MUST_BE_CLOSED"):
                closed_pilots(path)

    def test_storage_guard_requires_explicit_full_peak_and_never_defaults_to_pilot(self):
        with patch("workflows.data_d_descriptors.produce.pilot.storage_guard") as actual:
            with self.assertRaisesRegex(ValueError, "EXPLICIT_FULL"):
                guard("/output", {})
            guard("/output", {"peak_bytes": 35_000_000_000})
            actual.assert_called_once_with("/output", peak_bytes=35_000_000_000)

    def test_source_failure_preserves_population_and_skips_graph_retry(self):
        row = dict(self.row(), smiles=None, source_error="ORIGINAL_LMDB_POINTER_UNAVAILABLE")
        with tempfile.TemporaryDirectory() as root:
            result = validate_rows(self.write_rows(root, [row]))
            self.assertEqual(result["rows"], 1)
        reused, missing = plan_chunk([row], {})
        self.assertEqual(reused, {})
        self.assertEqual(missing, [(0, None)])
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "INVALID_TARGET_FREE"):
                validate_rows(self.write_rows(root, [dict(row, source_error=None)]))


if __name__ == "__main__":
    unittest.main()
