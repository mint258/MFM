"""Closed diagnostic statistics must resume without a second calculation."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.d_recipe.diagnostic_statistics import run


class StatisticEntryTests(unittest.TestCase):
    def test_one_forward_cache_produces_all_registered_metrics_and_pr_intervals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binding = dict(arm="D-R0", samples=3_000_000, seed=0)
            molecules = 257
            x = np.column_stack([np.arange(float(molecules)), np.arange(float(molecules)) ** 2])
            means = np.repeat(x, 2, axis=0) + np.tile([[0., 0.], [.2, -.2]], (molecules, 1))
            means = np.repeat(means[:, None, :], 4, axis=1)
            atoms = np.repeat(np.repeat(x, 2, axis=0)[:, None, :], 4, axis=1)
            np.save(root / "means.npy", means)
            np.save(root / "atoms.npy", atoms)
            np.savez(root / "panel.npz", first=np.arange(0, 2 * molecules, 2),
                owners=np.repeat(np.arange(molecules), 2), atom_ptr=np.arange(0, 2 * molecules + 1, 2), composition=x)
            manifest = root / "forward.json"
            manifest.write_text(json.dumps(dict(schema="D_REPRESENTATION_FORWARD_V1",
                status="FORWARD_COMPLETE", binding=binding, panel=str(root / "panel.npz"),
                means=str(root / "means.npy"), first_atoms=str(root / "atoms.npy"), layers=[3, 4, 5, 6])))
            with patch("tools.d_recipe.resources.execution_site"):
                result = run(dict(output=str(root / "statistics"), forward_manifest=str(manifest),
                                  participation_molecule_chunk=256), guard=Mock())
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(result["participation_molecule_chunk"], 256)
            self.assertTrue(result["forward_reused"])
            for label in ("3", "4", "5", "6"):
                metrics = result["layers"][label]
                self.assertGreater(metrics["CEV"]["value"], .99)
                self.assertTrue(metrics["atom_PR"]["bootstrap"])
                self.assertEqual(metrics["mean_PR"]["bootstrap_summary"]["valid_bootstrap_replicates"], 1000)
                self.assertAlmostEqual(metrics["atom_PR"]["participation_ratio"],
                    metrics["atom_PR"]["bootstrap_summary"]["value"], places=10)
            with np.load(result["bootstrap_draws"]) as draws:
                self.assertEqual(len(draws.files), 20)
                self.assertEqual(draws["6_CVF_res"].shape, (1001,))
            self.assertEqual(json.loads((root / "statistics/summary.json").read_text())["status"], "COMPLETE")

    def test_closed_summary_does_not_load_cache_or_resample(self):
        with tempfile.TemporaryDirectory() as directory:
            binding = dict(arm="D-R0", samples=3_000_000, seed=0)
            manifest = Path(directory, "forward.json")
            manifest.write_text(json.dumps(dict(schema="D_REPRESENTATION_FORWARD_V1",
                status="FORWARD_COMPLETE", binding=binding)))
            closed = dict(status="COMPLETE", binding=binding)
            Path(directory, "summary.json").write_text(json.dumps(closed))
            with patch("tools.d_recipe.resources.execution_site"), \
                 patch("tools.d_recipe.diagnostic_statistics.np.load") as load, \
                 patch("tools.d_recipe.diagnostic_statistics.existing_statistics") as statistics:
                result = run(dict(output=directory, forward_manifest=str(manifest)), guard=Mock())
            self.assertEqual(result, closed)
            load.assert_not_called()
            statistics.assert_not_called()

    def test_partial_forward_is_not_accepted_as_statistical_input(self):
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory, "forward.json")
            manifest.write_text(json.dumps(dict(schema="D_REPRESENTATION_FORWARD_V1", status="PARTIAL")))
            with patch("tools.d_recipe.resources.execution_site"), self.assertRaises(ValueError):
                run(dict(output=directory, forward_manifest=str(manifest)), guard=Mock())


if __name__ == "__main__":
    unittest.main()
