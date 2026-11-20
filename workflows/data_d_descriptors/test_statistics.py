"""Only new stage-0 filtering/statistics behavior; no source data required."""
import copy
import unittest

import numpy as np

from .statistics import summarize_library, winsorized_parameters


def summarize(values, names=None, library="L1", observed=None, nonfinite=None,
              overflow=None, roles=None, existing=None):
    values = np.asarray(values, dtype=np.float64)
    if values.ndim == 1:
        values = values[:, None]
    return summarize_library(
        values, np.isfinite(values) if observed is None else observed,
        np.zeros(values.shape, dtype=bool) if nonfinite is None else nonfinite,
        np.zeros(values.shape, dtype=bool) if overflow is None else overflow,
        field_names=names or ["new"], library=library,
        roles=["TRAIN"] * len(values) if roles is None else roles,
        existing_parameters=existing,
    )


class StatisticsTests(unittest.TestCase):
    def test_true_zero_missing_and_constant_are_distinct(self):
        values = np.column_stack((np.arange(100), np.zeros(100), np.full(100, np.nan)))
        values[0, 0] = np.nan
        result = summarize(values, ["varying", "constant_zero", "missing"])
        varying, constant, missing = result["fields"]
        self.assertTrue(varying["enabled"])
        self.assertEqual(varying["missing_count"], 1)
        self.assertEqual(varying["nonfinite_numeric_events"], 0)
        self.assertEqual(constant["true_zero_count"], 100)
        self.assertEqual(constant["removal_reasons"], ["finite_constant"])
        self.assertEqual(missing["true_zero_count"], 0)
        self.assertFalse(missing["finite_constant"])
        self.assertEqual(missing["removal_reasons"], ["valid_fraction_below_0.95"])

    def test_exact_95_percent_boundary(self):
        values = np.arange(200, dtype=np.float64).reshape(100, 2)
        values[:5, 0] = np.nan
        values[:6, 1] = np.nan
        result = summarize(values, ["at_threshold", "below_threshold"])
        self.assertEqual(result["enabled_field_order"], ["at_threshold"])
        self.assertEqual(result["fields"][0]["valid_fraction"], 0.95)

    def test_numerical_events_drop_fields_even_when_marked_missing(self):
        values = np.tile(np.arange(100, dtype=np.float64)[:, None], (1, 3))
        values[0, 0] = np.inf
        values[0, 1] = np.nan
        observed = np.isfinite(values)
        nonfinite = np.zeros(values.shape, dtype=bool)
        overflow = np.zeros(values.shape, dtype=bool)
        nonfinite[0, 0] = True
        overflow[0, 1] = True
        # An erroneously observed infinity must also be excluded even if its
        # explicit event mask was omitted by the producer.
        values[0, 2] = np.inf
        result = summarize(values, ["numeric", "overflow", "observed_inf"],
                           observed=observed, nonfinite=nonfinite, overflow=overflow)
        self.assertEqual(result["enabled_field_order"], [])
        self.assertIn("nonfinite_numeric_event", result["fields"][0]["removal_reasons"])
        self.assertIn("numeric_overflow_event", result["fields"][1]["removal_reasons"])
        self.assertIn("nonfinite_numeric_event", result["fields"][2]["removal_reasons"])

    def test_rejects_any_non_train_role_and_ambiguous_masks(self):
        with self.assertRaisesRegex(ValueError, "TRAIN_ONLY"):
            summarize([1, 2, 3], roles=["TRAIN", "VAL", "TRAIN"])
        with self.assertRaisesRegex(ValueError, "BOOLEAN_SHAPE"):
            summarize([1, 2, 3], observed=np.ones((3, 1), dtype=np.float64))

    def test_type7_population_moments_and_raw_values_unchanged(self):
        values = np.array([0, 1, 2, 1000], dtype=np.float64)
        original = values.copy()
        result = winsorized_parameters(values)
        self.assertAlmostEqual(result["q001"], 0.003)
        self.assertAlmostEqual(result["q999"], 997.006)
        expected = np.array([0.003, 1, 2, 997.006])
        self.assertAlmostEqual(result["mean"], expected.mean())
        self.assertAlmostEqual(result["std_population"], expected.std(ddof=0))
        np.testing.assert_array_equal(values, original)

    def test_original_parameters_are_preserved_and_used_for_clip_fraction(self):
        parameters = {"mean": 0.0, "std": 1.0, "historical_metadata": {"scope": "full_TRAIN"}}
        before = copy.deepcopy(parameters)
        values = np.array([-7, -6, 0, 6, 7], dtype=np.float64)
        result = summarize(values, ["ExactMolWt"], existing={"ExactMolWt": parameters})
        field = result["fields"][0]
        self.assertIs(field["parameters"], parameters)
        self.assertEqual(parameters, before)
        self.assertEqual(field["normalization_status"], "REUSED_UNCHANGED")
        self.assertEqual(field["train_loss_abs_standardized_gt6_fraction"], 0.4)
        d3 = summarize(values, ["SASA_total_A2"], "D3",
                       existing={"SASA_total_A2": parameters})
        self.assertIs(d3["fields"][0]["parameters"], parameters)
        for name, library in (("ExactMolWt", "L1"), ("PMI1", "D3")):
            with self.assertRaisesRegex(ValueError, "EXISTING_D20_D3_PARAMETERS"):
                summarize(values, [name], library)

    def test_l1_disablements_do_not_cross_map_to_l2(self):
        values = np.tile(np.arange(100, dtype=np.float64)[:, None], (1, 3))
        names = ["NumBridgeheadAtoms", "MolMR", "NumSpiroAtoms"]
        self.assertEqual(summarize(values, names, "L1")["enabled_field_order"], [])
        self.assertEqual(summarize(values, names, "L2")["enabled_field_order"], names)
        with self.assertRaisesRegex(ValueError, "CROSS_LIBRARY"):
            summarize(values, names, "L2", existing={"MolMR": {"mean": 0, "std": 1}})

    def test_real_d4_route_and_resolved_loader_parameter_names(self):
        for parameters in ({"mean": 0, "std_ddof0": 1}, {"center": 0, "scale": 1}):
            field = summarize([-7, 0, 7], ["ExactMolWt"],
                existing={"ExactMolWt": parameters})["fields"][0]
            self.assertIs(field["parameters"], parameters)
            self.assertEqual(field["train_loss_abs_standardized_gt6_count"], 2)

    def test_new_fit_reports_tail_fraction_on_unclipped_values(self):
        values = np.zeros(10000, dtype=np.float64)
        values[::2] = 1
        values[-1] = 10000
        result = summarize(values)
        field = result["fields"][0]
        self.assertTrue(field["enabled"])
        self.assertEqual(field["train_loss_abs_standardized_gt6_count"], 1)
        self.assertEqual(field["train_loss_abs_standardized_gt6_fraction"], 0.0001)
        self.assertEqual(values[-1], 10000)


if __name__ == "__main__":
    unittest.main()
