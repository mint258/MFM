"""Panel construction and cache placement require no trained model."""
from pathlib import Path
import json
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.d_recipe.diagnostic_forward import make_panel, registered_endpoint, run, store_batch


class ForwardTests(unittest.TestCase):
    def test_closed_cache_is_reused_without_loading_or_forwarding_an_encoder(self):
        with tempfile.TemporaryDirectory() as directory:
            binding = dict(arm="D-R0", run="native", samples=3_000_000, seed=0,
                           checkpoint="/own/3M.pt", root="/existing/native", source="PM7")
            closed = dict(schema="D_REPRESENTATION_FORWARD_V1", status="FORWARD_COMPLETE", binding=binding)
            Path(directory, "manifest.json").write_text(json.dumps(closed))
            module = Mock()
            with patch("tools.d_recipe.resources.execution_site"):
                self.assertEqual(run(dict(binding, output=directory), module=module, guard=Mock()), closed)
            module.load_representation_encoder.assert_not_called()
            module.validation_indices.assert_not_called()

    def test_panel_retains_choice_order_explicit_hydrogens_and_composition(self):
        atoms = {8: np.array([6, 1, 1]), 2: np.array([8, 6, 1, 1])}
        geometry = SimpleNamespace(record=lambda kind, mi: {1: atoms[mi]},
                                   choices=lambda mi: [3, 1] if mi == 8 else [7])
        panel = make_panel(geometry, [8, 2], [1, 6, 8])
        np.testing.assert_array_equal(panel["rows"], [[8, 3], [8, 1], [2, 7]])
        np.testing.assert_array_equal(panel["first"], [0, 2])
        np.testing.assert_array_equal(panel["atom_ptr"], [0, 3, 7])
        np.testing.assert_array_equal(panel["composition"], [[2, 1, 0, 3, 1], [2, 1, 1, 4, 2]])

    def test_atom_cache_uses_first_conformer_and_preserves_atom_row_order(self):
        panel = dict(owners=np.array([0, 0, 1]), first=np.array([0, 2]), atom_ptr=np.array([0, 2, 3]))
        means, atoms = np.zeros((3, 4, 2)), np.zeros((3, 4, 2))
        features = np.arange(5 * 4 * 2).reshape(5, 4, 2).astype(np.float64)
        store_batch(means, atoms, panel, 0, features, [0, 2, 4, 5])
        np.testing.assert_array_equal(atoms, features[[0, 1, 4]])
        np.testing.assert_array_equal(means[1], features[2:4].mean(0))

    def test_only_registered_native_or_adopted_seed0_endpoints(self):
        for arm in ("D-R0", "D-R1", "D-G1"):
            registered_endpoint(dict(arm=arm, samples=3_000_000, seed=0))
        registered_endpoint(dict(arm="D-L2", adopted_arm="D-L2", samples=3_000_000, seed=0))
        for arm, samples, seed in (("D-L1", 3_000_000, 0), ("D-R0", 9_000_000, 0),
                                   ("D-R1", 3_000_000, 1), ("P0", 3_000_000, 0)):
            with self.assertRaises(ValueError):
                registered_endpoint(dict(arm=arm, samples=samples, seed=seed))


if __name__ == "__main__":
    unittest.main()
