"""Only new D clipping aggregation, native precision and resume behavior."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from tools.d_recipe.clip_report import ATOM, AtomicSource, counts, molecular_counts, report, standardized
from phychem_mfm.phase1.v31_loader import normalize_values


class ClippingTests(unittest.TestCase):
    def normalization(self, **values):
        return dict(fit_role="TRAIN", center=[0.], scale=[1.], **values)

    def test_exact_six_is_not_clipped_and_missing_leaves_do_not_enter_denominator(self):
        value = np.array([-7., -6., 0., 6., 7., 99., np.nan])
        self.assertEqual(counts(value, [1, 1, 1, 1, 1, 0, 0]), dict(valid=5, clipped=2))
        self.assertEqual(counts([], []), dict(valid=0, clipped=0))

    def test_original_fp32_rounding_is_preserved_at_the_boundary(self):
        raw = np.array([6. + 2e-7, np.nextafter(np.float32(6), np.float32(7))], dtype=np.float64)
        value = standardized(raw, np.zeros((2, 119)), self.normalization())
        self.assertEqual(value.dtype, np.float32)
        self.assertEqual(counts(value, np.ones(2, bool)), dict(valid=2, clipped=1))

    def test_vector_element_offset_matches_the_actual_native_normalizer(self):
        atoms = [np.array([1, 1, 6]), np.array([6, 1, 6, 1, 1]), np.array([8])]
        design = np.zeros((len(atoms), 119))
        for row, z in enumerate(atoms):
            design[row, :-1] = np.bincount(z, minlength=119)[1:]
        raw = np.array([8.2, -7.4, 0.1])
        for fitted in (False, True):
            spec = self.normalization(p_recipe_fitted=fitted,
                element_reference=dict(basis=[1, 6, 8], coefficients=[.23, -.72, 8.9], intercept=2.4))
            observed = standardized(raw, design, spec)
            expected = np.array([normalize_values(np.array([[value]]), spec, Z=z).item()
                                 for value, z in zip(raw, atoms)], dtype=np.float32)
            np.testing.assert_array_equal(observed, expected)

    def fixture(self, directory):
        source = Path(directory) / "collection"
        source.mkdir()
        config = dict(peak_bytes=1000000, ridge_alpha=1., fold_seed=20261112)
        state = dict(status="COLLECTION_COMPLETE", binding=dict(split="TRAIN", configuration=config,
                    fields=["D20.x"], rows=3))
        (source / "collection_checkpoint.json").write_text(json.dumps(state))
        np.save(source / "raw.npy", [[6.], [-8.], [np.nan]])
        np.save(source / "valid.npy", [[True], [True], [False]])
        np.save(source / "design.npy", np.zeros((3, 119)))
        np.save(source / "choices.npy", [[10, 2], [20, 3], [30, 1]])
        base = {"D20.x": self.normalization(), ATOM: self.normalization()}
        transferred = {**base, "D20.x": {**base["D20.x"], "scale": [2.]}}
        return source, config, base, transferred

    def guard(self, directory, peak):
        self.assertTrue(Path(directory).is_dir())
        self.assertEqual(peak, 1000000)

    def test_both_original_and_transferred_targets_get_their_own_counts(self):
        with tempfile.TemporaryDirectory() as directory:
            source, _, base, transferred = self.fixture(directory)
            rows = molecular_counts(source, ["D20.x"], base, transferred, chunk_rows=2)
            self.assertEqual(rows[0]["D_R0"], dict(valid=2, clipped=1))
            self.assertEqual(rows[0]["D_R1"], dict(valid=2, clipped=0))

    def test_closed_chunks_resume_without_recounting_and_closed_report_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            source, config, base, transferred = self.fixture(directory)
            output = Path(directory) / "report"
            calls = []
            def atomic(molecule, conformer):
                calls.append((molecule, conformer))
                return {10: dict(valid=2, clipped=1), 20: dict(valid=0, clipped=0),
                        30: dict(valid=3, clipped=1)}[molecule]
            state = report(source, output, config, base, transferred, atomic, guard=self.guard,
                           chunk_rows=2, stop_after_chunks=1)
            self.assertEqual(state["atomic_cursor"], 2)
            self.assertEqual(calls, [(10, 2), (20, 3)])
            with patch("tools.d_recipe.clip_report.molecular_counts", side_effect=AssertionError("already closed")):
                closed = report(source, output, config, base, transferred, atomic, guard=self.guard, chunk_rows=2)
                again = report(source, output, config, base, transferred, atomic, guard=self.guard, chunk_rows=2)
            self.assertEqual(closed, again)
            self.assertEqual(calls, [(10, 2), (20, 3), (30, 1)])
            atom = closed["fields"][-1]
            self.assertEqual(atom["field_name"], ATOM)
            self.assertEqual(atom["D_R0"], dict(valid=5, clipped=2, fraction=.4))
            self.assertEqual(atom["D_R0"], atom["D_R1"])
            self.assertFalse(closed["stored_values_modified"])
            self.assertFalse(closed["decision_input"])

    def test_incomplete_collection_and_changed_atomic_parameters_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            source, config, base, transferred = self.fixture(directory)
            with self.assertRaisesRegex(ValueError, "preserve"):
                report(source, Path(directory)/"report", config, base,
                       {**transferred, ATOM: {**base[ATOM], "scale": [2.]}}, None, guard=self.guard)
            path = source / "collection_checkpoint.json"
            value = json.loads(path.read_text());value["status"] = "COLLECTING";path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "must close"):
                report(source, Path(directory)/"report", config, base, transferred, None, guard=self.guard)

    def test_atomic_reader_uses_native_field_location_and_published_masks(self):
        atom = dict(name=ATOM, field_key="source_atom_sasa", level="atom", loss_enabled=True)
        view = SimpleNamespace(fields=[dict(name="D20.x"), atom],
                               locations={"source_atom_sasa": [("atom_labels", 2)]})
        view.extract = MagicMock(return_value={ATOM: SimpleNamespace(values=np.array([[-7.], [6.]]),
                                                               valid=np.array([[True], [False]]))})
        transaction = MagicMock();transaction.get.side_effect=[b"m", b"c"]
        context = MagicMock();context.__enter__.return_value=transaction
        native = SimpleNamespace(view=view, source="PM7", _record_masks={(10, 2): {"mask": [0]}},
                                 _open=MagicMock(), _env=SimpleNamespace(begin=MagicMock(return_value=context)))
        with patch("phychem_mfm.phase1.v31_loader.decode_mfm4", side_effect=[{1: np.array([1, 6])}, {24: "atom values"}]) as decode:
            result = AtomicSource(native)(10, 2)
        self.assertEqual(result, dict(valid=1, clipped=1))
        self.assertEqual([call.kwargs["array_ids"] for call in decode.call_args_list], [{1}, {24}])
        self.assertEqual(view.fields, [atom])
        self.assertEqual(view.extract.call_args.kwargs["mask_overrides"], {"mask": [0]})


if __name__ == "__main__":
    unittest.main()
