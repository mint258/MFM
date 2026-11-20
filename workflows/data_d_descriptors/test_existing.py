"""Canonical D20 reuse and descriptor input routing, without source datasets."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import lmdb
import numpy as np

from workflows.data_v1_final.export.pilot_v31_compact_v1.codec import encode, encode_key
from .existing import ExistingD20
from . import pilot


class ExistingTests(unittest.TestCase):
    def test_native_h_counts_and_d20_bits_are_reused_without_graph_recalculation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = root / "TRAIN"
            store.mkdir()
            (root / "manifest.json").write_text(json.dumps({"split_roots": {"TRAIN": str(store)}}))
            (root / "schema.json").write_text(json.dumps({"columns": {"d20": [
                {"field_key": "D20.zero", "column_index": 0},
                {"field_key": "D20.missing", "column_index": 1}]}}))
            with lmdb.open(str(store), map_size=2**20) as environment:
                with environment.begin(write=True) as transaction:
                    transaction.put(encode_key("M", 4), encode({1: np.array([1, 1, 6], dtype="u1"),
                        4: np.array([0., np.nan], dtype="<f4")}))
            reader = ExistingD20(root)
            try:
                row = reader.read("TRAIN", 4)
                self.assertEqual(row["existing_D20"], {"zero": 0., "missing": None})
                self.assertEqual(row["native_element_counts"], [[1, 2], [6, 1]])
                with self.assertRaisesRegex(ValueError, "source molecule record"):
                    reader.read("TRAIN", 5)
            finally:
                reader.close()

    def test_l1_reuses_closed_fields_even_if_the_source_graph_is_unavailable(self):
        original = Mock(side_effect=AssertionError("Canonical D20 must not be recalculated"))
        new = Mock(return_value=10.)
        with patch.object(pilot, "LIBRARY", "L1"), patch.object(pilot, "FIELDS", ["old", "new"]), \
             patch.object(pilot, "CALCULATOR", [("old", original), ("new", new)]):
            values, valid, bad, _, _, _ = pilot.one({"smiles": None, "existing_D20": {"old": 0.}})
        self.assertEqual(values[0], 0.)
        self.assertEqual(valid, [True, False])
        self.assertEqual(bad, [False, False])
        original.assert_not_called()
        new.assert_not_called()

    def test_l2_never_cross_maps_same_named_d20_fields(self):
        calculator = Mock(side_effect=AssertionError("Missing graph cannot call Mordred"))
        with patch.object(pilot, "LIBRARY", "L2"), patch.object(pilot, "FIELDS", ["same_name"]), \
             patch.object(pilot, "CALCULATOR", calculator):
            _, valid, _, _, _, _ = pilot.one({"smiles": None, "existing_D20": {"same_name": 0.}})
        self.assertEqual(valid, [False])
        calculator.assert_not_called()

    def test_fp32_transport_overflow_keeps_the_original_f64_number_with_an_event_mask(self):
        with patch.object(pilot, "LIBRARY", "L1"), patch.object(pilot, "FIELDS", ["big"]), \
             patch.object(pilot, "CALCULATOR", [("big", lambda mol: 1e100)]):
            raw, valid, bad, reasons, _, _ = pilot.one("C")
        self.assertEqual(raw, [1e100])
        self.assertEqual(valid, [False])
        self.assertEqual(bad, [True])
        self.assertIn("OVERFLOW", reasons[0])


if __name__ == "__main__":
    unittest.main()
