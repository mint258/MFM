"""Numerical and atom-order boundaries for the one reception entry point."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.d_recipe.acceptance import fit_linear_head, reception_result, sasa_alignment


class ReceptionTests(unittest.TestCase):
    def test_missing_rows_are_excluded_and_clipped_standardized_fit_returns_raw_units(self):
        head = torch.nn.Linear(4, 1)
        features = torch.eye(4)
        targets = [0., 0., float("nan"), 20.]
        result = fit_linear_head(head, features, targets, [True, True, False, True],
                                 dict(center=[100.], scale=[5.]))
        actual = (head(features).detach().reshape(-1) - 100.) / 5.
        torch.testing.assert_close(actual[[0, 1, 3]], torch.tensor([0., 0., 6.]), atol=2e-6, rtol=2e-6)
        self.assertEqual(result["observations"], 3)
        self.assertEqual(result["design_rank"], 3)

    def test_true_zero_is_observed_and_no_observations_cannot_pass(self):
        head = torch.nn.Linear(2, 1)
        result = fit_linear_head(head, torch.eye(2), [0., 0.], [True, True], dict(center=0., scale=1.))
        self.assertEqual(result["observations"], 2)
        self.assertLess(float(head(torch.eye(2)).abs().max()), 1e-6)
        with self.assertRaisesRegex(ValueError, "No observed"):
            fit_linear_head(head, torch.eye(2), [0., 0.], [False, False], dict(center=0., scale=1.))

    def test_nonfinite_observed_targets_and_invalid_scales_raise(self):
        head = torch.nn.Linear(2, 1)
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            fit_linear_head(head, torch.eye(2), [float("nan"), 0.], [True, True], dict(center=0., scale=1.))
        with self.assertRaisesRegex(ValueError, "D4"):
            fit_linear_head(head, torch.eye(2), [0., 0.], [True, True], dict(center=0., scale=0.))

    def test_ratio_is_strict_and_absolute_noise_cannot_hide_material_failure(self):
        self.assertFalse(reception_result(1., .01)["passed"])
        self.assertTrue(reception_result(1., .009)["passed"])
        self.assertTrue(reception_result(0., 1e-14)["passed"])
        self.assertFalse(reception_result(0., 1e-5)["passed"])
        self.assertFalse(reception_result(float("nan"), 0.)["passed"])

    def fixture(self):
        atomic = np.asarray([6, 1, 1], dtype=np.uint8)
        raw = np.asarray([[4.], [0.], [float("nan")]], dtype=np.float32)
        field = dict(name="D3.SASA_atom_A2", target_id="SASA", group="D", level="atom")
        view = SimpleNamespace(fields=[field], locations={"SASA": [("atom_labels", 1)]})
        native = SimpleNamespace(view=view, record=lambda kind, *_: {1: atomic} if kind == "M" else
                                 {24: np.concatenate((np.zeros_like(raw), raw), axis=1)})
        sample = dict(molecule_index=12, conformer_index=3, Z=atomic.copy(), pos=np.zeros((3, 3)),
                      original_targets={field["name"]: SimpleNamespace(raw=raw.copy(), valid=~np.isnan(raw))})
        return native, sample

    def test_source_atom_order_and_real_zero_sasa_are_preserved(self):
        native, sample = self.fixture()
        self.assertEqual(sasa_alignment(native, sample), 3)
        sample["Z"] = np.asarray([1, 6, 1], dtype=np.uint8)
        with self.assertRaisesRegex(ValueError, "atom sequence"):
            sasa_alignment(native, sample)

    def test_sasa_atom_row_permutation_is_rejected(self):
        native, sample = self.fixture()
        target = sample["original_targets"]["D3.SASA_atom_A2"]
        target.raw = target.raw[[1, 0, 2]]
        with self.assertRaisesRegex(ValueError, "aligned"):
            sasa_alignment(native, sample)


if __name__ == "__main__":
    unittest.main()
