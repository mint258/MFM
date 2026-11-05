"""Four sparse pair boundaries only; no mirror or full-pipeline test expansion."""
from __future__ import annotations
import argparse
from pathlib import Path
import unittest
import numpy as np
from .source_v2 import target_arrays
from .io import check_allocation, fresh_dir, write_json
from wire_v1.tests import fixture_mapping
from wire_v1.store import file_ref


def context(name="pair_a", directed=True):
    _, mapping, _ = fixture_mapping(kind="scalar", level="pair", name=name, family="pairs")
    target = mapping["physical_targets"][0]
    target["pair_index_policy"]["directed"] = directed
    selector = {"shape": ["n_pairs"], "pair_index_base": 0,
                "value": {"column": name + "_v"}, "valid": {"column": name + "_ok"},
                "reason": {"column": name + "_why"}, "pairs": {"column": name + "_pairs"}}
    return target, {"components": {name + ".value": selector}}


class SparsePairTests(unittest.TestCase):
    def test_zero_pairs_have_explicit_empty_m_by_two_shape(self):
        target, spec = context()
        row = {"pair_a_v": [], "pair_a_ok": [], "pair_a_why": [], "pair_a_pairs": []}
        result = target_arrays(row, spec, target, 3)
        self.assertEqual(result["pairs/pair_a"].shape, (0, 2))
        self.assertEqual(result["pairs/pair_a"].dtype.str, "<i4")
        self.assertEqual(result["values/pair_a"].shape, (0,))
        self.assertEqual(result["valid/pair_a"].shape, (0,))

    def test_nonzero_fields_own_indices_and_preserve_source_order_direction(self):
        target_a, spec_a = context()
        target_b, spec_b = context("pair_b", directed=False)
        spec = {"components": {**spec_a["components"], **spec_b["components"]}}
        row = {"pair_a_v": [1.25, 2.5], "pair_a_ok": [1, 0], "pair_a_why": [0, 3], "pair_a_pairs": [[2, 0], [0, 1]],
               "pair_b_v": [9.], "pair_b_ok": [1], "pair_b_why": [0], "pair_b_pairs": [[1, 2]]}
        before = [pair[:] for pair in row["pair_a_pairs"]]
        a = target_arrays(row, spec, target_a, 3); b = target_arrays(row, spec, target_b, 3)
        self.assertEqual(a["pairs/pair_a"].tolist(), [[2, 0], [0, 1]])
        self.assertEqual(b["pairs/pair_b"].tolist(), [[1, 2]])
        self.assertEqual(a["valid/pair_a"].tolist(), [1, 0])
        self.assertEqual(a["values/pair_a"].tolist(), [1.25, 2.5])
        self.assertEqual(row["pair_a_pairs"], before)
        self.assertEqual(spec_a["components"]["pair_a.value"]["shape"], ["n_pairs"])

    def test_pair_index_out_of_bounds_rejected(self):
        target, spec = context()
        row = {"pair_a_v": [1.], "pair_a_ok": [1], "pair_a_why": [0], "pair_a_pairs": [[0, 3]]}
        with self.assertRaisesRegex(ValueError, "PAIR_INDEX_OUT_OF_RANGE"):
            target_arrays(row, spec, target, 3)

    def test_value_length_must_match_that_fields_pair_count(self):
        target, spec = context()
        row = {"pair_a_v": [1.], "pair_a_ok": [1, 1], "pair_a_why": [0, 0], "pair_a_pairs": [[0, 1], [1, 2]]}
        with self.assertRaisesRegex(ValueError, "SOURCE_DECLARED_SHAPE_DIFFERS"):
            target_arrays(row, spec, target, 3)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(); check_allocation(True); out = fresh_dir(a.output)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(SparsePairTests))
    write_json(out / "test_summary.json", {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "source_data_read": False, "full_pipeline_repeated": False,
        "sources": [file_ref(Path(__file__)), file_ref(Path(__file__).with_name("source_v2.py")), file_ref(Path(__file__).with_name("export_source_v2.py")), file_ref(Path(__file__).with_name("verify_source_v2.py"))]})
    if not result.wasSuccessful():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
