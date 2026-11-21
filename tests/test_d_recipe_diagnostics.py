"""D diagnostics reuse the peer statistics without calling its command."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.d_recipe.diagnostics import bootstrap_participation, describe, participation_ratio


class DiagnosticTests(unittest.TestCase):
    def test_molecule_bootstrap_pr_matches_analytic_weighted_covariance(self):
        values = np.array([[1., 0.], [-1., 0.], [0., 2.], [0., -2.]])
        weights = np.array([[1., 1.], [2., 0.], [0., 2.], [0., 0.]])
        for molecules, bootstraps in ((1, 1), (32, 128), (256, 128)):
            result = bootstrap_participation(values, [0, 2, 4], weights,
                molecule_chunk=molecules, bootstrap_chunk=bootstraps)
            np.testing.assert_allclose(result[:3], [25 / 17, 1., 1.], rtol=1e-10, atol=1e-10)
            self.assertTrue(np.isnan(result[3]))

    def test_population_pr_handles_isotropic_rank_one_and_constant_features(self):
        for values, expected in ((np.array([[1., 0.], [-1., 0.], [0., 1.], [0., -1.]]), 2.),
                                 (np.array([[1., 2.], [-1., -2.]]), 1.),
                                 (np.ones((3, 2)), None)):
            result = participation_ratio(len(values), values.sum(0), values.T @ values)
            self.assertEqual(result["participation_ratio"], expected)
            self.assertFalse(result["bootstrap"])

    def test_existing_functions_receive_same_f64_cache_and_paired_weights(self):
        owners, first = np.array([0, 0, 1, 1]), np.array([0, 2])
        raw = np.array([[1.], [2.], [3.], [4.]], np.float32)
        layers = {str(k): dict(means=raw, first_atom_moments=dict(
            count=2, total=np.array([4.]), outer=np.array([[10.]]))) for k in (3, 4, 5, 6)}
        draws = np.arange(1001, dtype=np.float64)
        statistics = SimpleNamespace(
            bootstrap_weights=Mock(return_value=np.ones((1000, 2))),
            ridge_oof=Mock(return_value=(np.array([[1.], [3.]]), [1.] * 5)),
            cev_values=Mock(return_value=draws),
            cvf_values=Mock(return_value=(draws + 1, draws + 2)),
            summary=Mock(side_effect=lambda a: {"value": float(a[0])}))
        guard = Mock()
        result, bootstrap = describe(layers, owners=owners, first=first,
            composition=np.eye(2), statistics=statistics, guard=guard)
        statistics.bootstrap_weights.assert_called_once_with(2)
        self.assertEqual(statistics.ridge_oof.call_count, 4)
        self.assertEqual(guard.call_count, 5)
        original_weights = statistics.cev_values.call_args_list[0].args[2]
        for call in statistics.cvf_values.call_args_list:
            self.assertIs(call.args[3], original_weights)
            self.assertEqual(call.args[0].dtype, np.float64)
            np.testing.assert_array_equal(call.args[1], owners)
        self.assertEqual(result["layers"]["6"]["CVF_res"], {"value": 2.})
        self.assertIs(bootstrap["6_CEV"], draws)
        self.assertFalse(result["downstream_probes_fitted"])
        np.testing.assert_array_equal(raw[:, 0], [1, 2, 3, 4])

    def test_unregistered_layers_and_reordered_first_rows_are_rejected(self):
        for layers, first in (({"1": None}, [0, 2]),
                              ({str(i): None for i in (3, 4, 5, 6)}, [2, 0])):
            with self.assertRaises(ValueError):
                describe(layers, owners=np.array([0, 0, 1, 1]), first=first,
                         composition=np.eye(2), statistics=SimpleNamespace())


if __name__ == "__main__":
    unittest.main()
