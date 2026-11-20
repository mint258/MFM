"""New D A1 mathematics, without production-size fitting or D4 changes."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "d_recipe"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "current"))
from element_reference import (assign_folds, element_design, fit_element_reference,
                               fit_element_reference_core, make_label_parameters,
                               reference_policy)


class ElementReferenceTests(unittest.TestCase):
    def counts(self, size=100):
        generator = np.random.default_rng(73)
        x = np.zeros((size, 119), dtype=np.float64)
        x[:, 0] = generator.integers(1, 20, size=size)  # native H
        x[:, 5] = generator.integers(1, 10, size=size)  # C
        x[:, -1] = 1.
        return x

    def test_native_basis_contains_hydrogen_all_elements_and_intercept(self):
        x = element_design([[1, 1, 6], [1, 8, 118]])
        self.assertEqual(x.shape, (2, 119))
        np.testing.assert_array_equal(x[:, 0], [2., 1.])
        self.assertEqual(x[0, 5], 1.)
        self.assertEqual(x[1, 117], 1.)
        np.testing.assert_array_equal(x[:, -1], [1., 1.])
        self.assertEqual(x[0].sum(), 4.)  # 3 native atoms + intercept

    def test_unpenalized_intercept_and_constant_target_are_explicit(self):
        x = self.counts()
        y = np.full(100, 42.)
        record = fit_element_reference_core(x, y, np.ones(100, dtype=bool),
                                            ridge_alpha=1e12, fold_seed=20261120)
        field = record["fields"][0]
        coefficients = np.array(field["coefficients"])
        np.testing.assert_array_equal(coefficients[:-1], np.zeros(118))
        self.assertEqual(coefficients[-1], 42.)
        self.assertIsNone(field["oof_r2"])
        self.assertEqual(field["target_policy"], "original")
        self.assertEqual(field["reason"], "constant_target_oof_r2_undefined")
        self.assertFalse(record["intercept_penalized"])

    def test_three_r2_bands_have_taskbook_inclusive_boundaries(self):
        for r2 in (-1., .299999999, None, float("nan")):
            self.assertEqual(reference_policy(r2)[0], "original")
        for r2 in (.30, .5, .998999999):
            self.assertEqual(reference_policy(r2)[0], "element_reference_residual")
        for r2 in (.999, 1.):
            self.assertEqual(reference_policy(r2)[0], "original")

    def test_five_fold_scores_do_not_use_validation_target_in_fitting(self):
        # Every molecule has a unique elemental marker. A full-data fit can
        # memorize y, but a held-out marker has zero training observations.
        n = 20
        x = np.zeros((n, 119), dtype=np.float64)
        x[:, :n] = np.eye(n)
        x[:, -1] = 1.
        y = np.arange(n, dtype=np.float64)
        record = fit_element_reference_core(x, y, np.ones(n, dtype=bool),
                                            ridge_alpha=1e-6, fold_seed=19)
        field = record["fields"][0]
        self.assertLess(field["oof_r2"], .30)
        self.assertEqual(field["target_policy"], "original")
        self.assertEqual(record["folds"], 5)
        self.assertEqual(field["valid_by_fold"], [4] * 5)
        np.testing.assert_allclose(x @ field["coefficients"], y, rtol=1e-5, atol=1e-5)

    def test_field_missing_subsets_share_cohort_folds_and_ignore_missing_targets(self):
        x = self.counts()
        target = 2. * x[:, 0] + 3. * x[:, 5] + 5.
        y = np.stack((target, -target), axis=1)
        valid = np.ones_like(y, dtype=bool)
        valid[::7, 0] = False
        valid[::11, 1] = False
        y[~valid] = np.nan
        before = y.copy()
        record = fit_element_reference_core(x, y, valid, ridge_alpha=1e-6,
                                            fold_seed=31, field_names=["first", "second"])
        folds = assign_folds(100, fold_seed=31)
        for column, field in enumerate(record["fields"]):
            self.assertEqual(field["n_valid"], int(valid[:, column].sum()))
            self.assertEqual(field["valid_by_fold"],
                             [int((valid[:, column] & (folds == fold)).sum()) for fold in range(5)])
            self.assertGreater(field["oof_r2"], .999)
            self.assertEqual(field["target_policy"], "original")
        np.testing.assert_array_equal(y, before)
        self.assertEqual(record["fields"][0]["field_name"], "first")
        self.assertFalse(record["original_D4_modified"])

    def test_empty_or_incomplete_fold_support_is_conservative_and_recorded(self):
        x = self.counts(10)
        y = np.arange(10, dtype=np.float64)
        valid = np.zeros(10, dtype=bool)
        record = fit_element_reference_core(x, y, valid, ridge_alpha=1., fold_seed=7)
        field = record["fields"][0]
        self.assertEqual(field["n_valid"], 0)
        self.assertIsNone(field["coefficients"])
        self.assertIsNone(field["oof_r2"])
        self.assertEqual(field["target_policy"], "original")
        self.assertEqual(field["reason"], "insufficient_observed_five_fold_support")

    def test_production_rejects_non_train_and_fewer_than_100000_observed_rows(self):
        x = self.counts(10)
        y, valid = np.arange(10.), np.ones(10, dtype=bool)
        with self.assertRaisesRegex(ValueError, "100000"):
            fit_element_reference(x, y, valid, roles=["TRAIN"] * 10,
                                  ridge_alpha=1., fold_seed=7)
        with self.assertRaisesRegex(ValueError, "TRAIN molecules only"):
            fit_element_reference(x, y, valid, roles=["TRAIN"] * 9 + ["VAL"],
                                  ridge_alpha=1., fold_seed=7)

    def test_alpha_and_fold_seed_are_required_and_observed_nan_is_not_zero_filled(self):
        x = self.counts(10)
        y, valid = np.arange(10.), np.ones(10, dtype=bool)
        with self.assertRaises(TypeError):
            fit_element_reference_core(x, y, valid, fold_seed=7)
        with self.assertRaises(TypeError):
            fit_element_reference_core(x, y, valid, ridge_alpha=1.)
        with self.assertRaisesRegex(ValueError, "positive ridge_alpha"):
            fit_element_reference_core(x, y, valid, ridge_alpha=0., fold_seed=7)
        y[0] = np.nan
        with self.assertRaisesRegex(ValueError, "observed target is nonfinite"):
            fit_element_reference_core(x, y, valid, ridge_alpha=1., fold_seed=7)

    def parameter_fixture(self):
        n = 1000
        design = element_design([[1] for _ in range(n)])
        residual = np.linspace(-.5, .5, n)
        residual[-2:] = [-10., 10.]
        targets = np.stack((np.zeros(n), 1e8 + residual), axis=1)
        targets[-1, 0] = 100.
        valid = np.ones_like(targets, dtype=bool)
        valid[0] = False
        targets[0] = np.nan
        coefficients = np.zeros(119)
        coefficients[0] = 1e8
        names = ["D20.original", "D20.residual"]
        fit = dict(fit_role="TRAIN", cohort_rows=n, ridge_alpha=1., fold_seed=19, fields=[
            dict(field_name=names[0], n_valid=n - 1, oof_r2=.999, target_policy="original",
                 coefficients=np.zeros(119).tolist()),
            dict(field_name=names[1], n_valid=n - 1, oof_r2=.5,
                 target_policy="element_reference_residual", coefficients=coefficients.tolist())])
        base = {name: dict(fit_role="TRAIN", center=[0.], scale=[1.],
                           source="original_11_07", provenance={"keep": True}) for name in names}
        base["D3.SASA_atom_A2"] = dict(fit_role="TRAIN", center=[12.], scale=[10.])
        return design, targets, valid, fit, base

    def test_label_parameters_preserve_base_and_derive_only_residual_band_in_float64(self):
        from copy import deepcopy
        x, y, valid, fit, base = self.parameter_fixture()
        before, raw_before = deepcopy(base), y.copy()
        result = make_label_parameters(fit, x, y, valid, base, roles=["TRAIN"] * len(x),
                                       model_name="D-R1:seed0:A1")
        self.assertEqual(base, before)
        self.assertEqual(result["normalizations"]["D20.original"], base["D20.original"])
        self.assertEqual(result["normalizations"]["D3.SASA_atom_A2"], base["D3.SASA_atom_A2"])
        derived = result["normalizations"]["D20.residual"]
        self.assertTrue(derived["p_recipe_fitted"])
        self.assertEqual(derived["element_reference"]["coefficients"][0], 1e8)
        self.assertEqual(derived["element_reference"]["basis"], list(range(1, 119)))
        residual = y[valid[:, 1], 1] - 1e8
        lower, upper = derived["winsor_quantiles"].values()
        self.assertGreater(lower, residual.min())
        self.assertLess(upper, residual.max())
        # Reuse the actual native consumer to prove the adapter selects F64
        # subtraction before its existing final F32 cast; F32-first loses .125.
        from phychem_mfm.phase1.v31_loader import normalize_values
        observed = normalize_values(np.array([[1e8 + .125]], dtype=np.float64), derived,
                                    Z=np.array([1], dtype=np.int64))
        expected = (.125 - derived["center"][0]) / derived["scale"][0]
        np.testing.assert_allclose(observed, [[expected]], rtol=1e-6, atol=1e-7)
        self.assertEqual(result["fit"]["fields"][0]["clipped_TRAIN_count"], 1)
        self.assertEqual(result["fit"]["fields"][0]["clipping_fraction"], 1 / 999)
        self.assertEqual(result["fit"]["fields"][1]["clipped_TRAIN_count"], 2)
        self.assertFalse(result["fit"]["original_D4_modified"])
        np.testing.assert_array_equal(y, raw_before)

    def test_derived_parameter_fit_rejects_role_order_population_and_policy_changes(self):
        from copy import deepcopy
        x, y, valid, fit, base = self.parameter_fixture()
        kwargs = dict(roles=["TRAIN"] * len(x), model_name="D-R1:seed0:A1")
        with self.assertRaisesRegex(ValueError, "TRAIN observations only"):
            make_label_parameters(fit, x, y, valid, base, **{**kwargs, "roles": ["VAL"] * len(x)})
        with self.assertRaisesRegex(ValueError, "field order/cohort"):
            make_label_parameters(fit, x, y, valid, base, **kwargs,
                                  field_names=["D20.residual", "D20.original"])
        changed = valid.copy()
        changed[1, 0] = False
        with self.assertRaisesRegex(ValueError, "valid population differs"):
            make_label_parameters(fit, x, y, changed, base, **kwargs)
        changed_fit = deepcopy(fit)
        changed_fit["fields"][1]["target_policy"] = "original"
        with self.assertRaisesRegex(ValueError, "policy differs"):
            make_label_parameters(changed_fit, x, y, valid, base, **kwargs)

    def test_shared_mask_multiple_target_solve_matches_original_per_field_five_fold_math(self):
        x = self.counts(100)
        y = np.stack((x[:, 0] + 2 * x[:, 5], -x[:, 0] + np.sin(x[:, 5]),
                      x[:, 0] * x[:, 5]), axis=1)
        valid = np.ones_like(y, dtype=bool)
        valid[::11, :2] = False  # first two fields share observed rows
        valid[::7, 2] = False   # third has a genuinely different subset
        y[~valid] = np.nan
        arguments = dict(ridge_alpha=.5, fold_seed=20261120)
        old = fit_element_reference_core(x, y, valid, **arguments, shared_mask_solve=False)
        batched = fit_element_reference_core(x, y, valid, **arguments, shared_mask_solve=True)
        for first, second in zip(old["fields"], batched["fields"]):
            self.assertEqual(first["valid_by_fold"], second["valid_by_fold"])
            self.assertEqual(first["target_policy"], second["target_policy"])
            np.testing.assert_allclose(first["coefficients"], second["coefficients"],
                                       rtol=1e-10, atol=1e-11)
            np.testing.assert_allclose(first["oof_r2"], second["oof_r2"], rtol=1e-12, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
