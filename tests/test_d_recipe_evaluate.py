"""The wrapper redirects D results and restores P's module globals."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.d_recipe.evaluate import run, score


class EvaluationTests(unittest.TestCase):
    def test_existing_run_is_reused_and_original_globals_are_restored(self):
        root, returned, configuration = object(), object(), {"run": "D-R0"}
        module = SimpleNamespace(REPO=root)
        def original(c):
            self.assertIs(c, configuration)
            self.assertEqual(module.REPO / "configs/dev_panel_v3.json", ROOT / "configs/dev_panel_v3.json")
            self.assertEqual(module.REPO / "results/p_recipe", ROOT / "results/d_recipe")
            return returned
        module.run = original
        self.assertIs(run(configuration, module=module), returned)
        self.assertIs(module.REPO, root)

    def test_exception_also_restores_existing_evaluator(self):
        root = object()
        module = SimpleNamespace(REPO=root, run=Mock(side_effect=RuntimeError("probe failed")))
        with self.assertRaisesRegex(RuntimeError, "probe failed"):
            run({}, module=module)
        self.assertIs(module.REPO, root)

    def test_cpu_score_calls_existing_bootstrap_and_writes_only_d_results(self):
        root, returned = object(), object()
        module = SimpleNamespace(REPO=root, score=Mock(return_value=returned))
        configuration = dict(output="/D/readout", reference_manifest="/existing/random/predictions.json")
        with patch("tools.d_recipe.evaluate.platform.node", return_value="compute-0-16"), \
             patch.dict("os.environ", SLURM_JOB_ID="test"):
            self.assertIs(score(configuration, module=module), returned)
        self.assertEqual(module.score.call_args.args,
                         (Path("/D/readout/predictions.json"), configuration["reference_manifest"],
                          ROOT / "results/d_recipe/scores.csv"))
        self.assertIs(module.REPO, root)

    def test_statistics_cannot_run_on_login_or_gpu_nodes(self):
        for node in ("sonmi", "compute-0-6", "compute-0-20", "compute-0-21"):
            with self.subTest(node=node), patch("tools.d_recipe.evaluate.platform.node", return_value=node), \
                 patch.dict("os.environ", SLURM_JOB_ID="test"), self.assertRaises(RuntimeError):
                score({}, module=SimpleNamespace(REPO=None))


if __name__ == "__main__":
    unittest.main()
