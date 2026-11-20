"""New cohort-role alignment only; no original datasets or descriptor calls."""
import unittest
import json
from pathlib import Path
import tempfile
from .prepare import combine_population
from .full_plan import load_closed_costs


def row(mid, index):
    return {"molecule_id": mid, "molecule_index": index}


class PopulationTests(unittest.TestCase):
    def test_frozen_indices_and_val_diagnostics(self):
        actual = combine_population([row("train", 4), row("excluded", 8)],
            [row("val", 2), row("val_diag", 1), row("unrequested_full", 0)],
            {4}, {"val"}, {"val_diag"}, {"train", "val_diag"})
        self.assertEqual([r["molecule_id"] for r in actual], ["train", "val_diag", "val"])
        self.assertEqual([r["role"] for r in actual], ["TRAIN", "VAL_DIAGNOSTIC", "VAL"])
        self.assertEqual([r["diagnostic"] for r in actual], [True, True, False])

    def test_diag_flag_does_not_duplicate_or_reclassify_common_val(self):
        actual = combine_population([], [row("val", 3)], set(), {"val"}, {"val"}, {"val"})
        self.assertEqual(len(actual), 1)
        self.assertEqual(actual[0]["role"], "VAL")

    def test_train_val_overlap_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlaps"):
            combine_population([row("same", 0)], [row("same", 0)], {0}, {"same"}, set(), set())

    def test_split_local_indices_remain_distinct(self):
        actual = combine_population([row("train", 0)], [row("val", 0)], {0}, {"val"}, set(), set())
        self.assertEqual([(r["split"], r["molecule_index"]) for r in actual], [("TRAIN", 0), ("FULL", 0)])

    def test_duplicate_source_address_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "overlaps"):
            combine_population([row("one", 0), row("two", 0)], [], {0}, set(), set(), set())

    def test_closed_peer_continues_when_other_library_is_unresolved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "L1_cost.json").write_text(json.dumps({"status": "PILOT_COST_COMPLETE_NOT_DELIVERY",
                "library": "L1", "molecules": 5000}))
            (root / "L2_cost.json").write_text(json.dumps({"status": "UNRESOLVED"}))
            actual = load_closed_costs(root)
            self.assertEqual(actual["L1"]["status"], "READY")
            self.assertEqual(actual["L2"]["status"], "UNRESOLVED")

    def test_unresolved_peer_does_not_turn_partial_pilot_into_closed_cost(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "L1_cost.json").write_text(json.dumps({"status": "PILOT_COST_COMPLETE_NOT_DELIVERY",
                "library": "L1", "molecules": 4999}))
            (root / "L2_cost.json").write_text(json.dumps({"status": "UNRESOLVED"}))
            with self.assertRaisesRegex(ValueError, "must close"):
                load_closed_costs(root)


if __name__ == "__main__":
    unittest.main()
