import unittest
import numpy as np
from workflows.benchmark_evaluation.selection import IncompleteComparison
from workflows.benchmark_evaluation.expansion_metrics import (
    ENDPOINTS, leaderboard_scale, leaderboard_point, leaderboard_report,
)

class LeaderboardMetricTests(unittest.TestCase):
    def test_LogD_keeps_its_original_scale(self):
        values = np.asarray([-1., 0., 2.])
        np.testing.assert_array_equal(leaderboard_scale(values, "LogD"), values)
    def test_official_non_LogD_clipping_does_not_modify_original_labels(self):
        values = np.asarray([-2., 0., 9.])
        original = values.copy()
        np.testing.assert_allclose(leaderboard_scale(values, "KSOL"), [0., 0., 1.])
        np.testing.assert_array_equal(values, original)
    def test_official_RAE_uses_TEST_mean_without_replacing_B1_TRAIN_reference(self):
        result = leaderboard_point([2., 4.], [1., 3.], "LogD")
        self.assertAlmostEqual(result["leaderboard_RAE"], 1.)
    def test_macro_bootstrap_keeps_repeated_observations_of_each_molecule_together(self):
        predictions = {}
        for endpoint in ENDPOINTS:
            predictions[endpoint] = {}
            for model in ("RF-ECFP4", "LightGBM-RDKit2D", "Chemprop-v2"):
                predictions[endpoint][model] = [
                    {"evaluation_id": str(molecule) + ":" + str(observation),
                     "full_inchikey": "synthetic-molecule-" + str(molecule),
                     "y_true": y, "prediction": 1. if model == "LightGBM-RDKit2D" else y,
                     "training_mean": 3.}
                    for molecule in range(40) for observation, y in enumerate((0., 2.))
                ]
        report = leaderboard_report(predictions)
        macro = {r["model"]: r for r in report["macro_results"]}
        self.assertAlmostEqual(macro["RF-ECFP4"]["leaderboard_MA_RAE"], 0.)
        self.assertAlmostEqual(macro["LightGBM-RDKit2D"]["leaderboard_MA_RAE"], 1.)
        self.assertAlmostEqual(macro["LightGBM-RDKit2D"]["leaderboard_MA_RAE_CI95_low"], 1.)
        self.assertAlmostEqual(macro["LightGBM-RDKit2D"]["leaderboard_MA_RAE_CI95_high"], 1.)
        self.assertFalse(report["B1_task_decisions_produced"])
    def test_missing_endpoints_are_not_averaged_away(self):
        with self.assertRaises(IncompleteComparison):
            leaderboard_report({})
    def test_nonfinite_prediction_does_not_remove_blind_TEST_rows(self):
        with self.assertRaises(IncompleteComparison):
            leaderboard_point([1., 2.], [1., float("nan")], "KSOL")
    def test_unregistered_raw_only_endpoint_is_not_added(self):
        with self.assertRaises(ValueError):
            leaderboard_scale([1.], "RLM CLint")

if __name__ == "__main__":
    unittest.main()
