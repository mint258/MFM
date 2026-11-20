"""Layer probes and bootstrap consume caches and reuse the main layer6 result."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.d_recipe.layer_readouts import run_cpu, run_gpu


class LayerReadoutTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        main, cache = root / "main", root / "features"
        main.mkdir()
        (main / "predictions.json").write_text("{}")
        (main / "scores.json").write_text("{}")
        native = dict(run="D-native", arm="D-R0", samples=3_000_000, seed=0,
                      checkpoint="/own/3M.pt", store="/original/store", reference_manifest="/original/random.json",
                      diagnostic_feature_root=str(cache), output=str(main))
        for dataset in ("expansionrx", "cyp_isoform", "qm9"):
            folder = cache / dataset
            folder.mkdir(parents=True)
            features = {}
            for layer in (3, 4, 5, 6):
                file = folder / (str(layer) + ".pt")
                file.write_bytes(b"existing producer fixture")
                features[str(layer)] = str(file)
            (folder / "manifest.json").write_text(json.dumps(dict(binding={
                k: native[k] for k in ("run", "checkpoint", "store")} | {"dataset": dataset}, features=features)))
        module = SimpleNamespace(REPO=object(), produce_missing_features=Mock(side_effect=AssertionError("No encoder fallback")),
            feature_path=lambda c, dataset: Path(c["features"][dataset]))
        def native_run(c):
            for dataset in ("expansionrx", "cyp_isoform", "qm9"):
                module.produce_missing_features(c, dataset, None)
            output = Path(c["output"])
            output.mkdir(parents=True)
            (output / "predictions.json").write_text(json.dumps(dict(run=c["run"])))
        def native_score(predictions, reference, csv):
            Path(predictions).with_name("scores.json").write_text("{}")
        module.run, module.score = Mock(side_effect=native_run), Mock(side_effect=native_score)
        return dict(output=str(root / "diagnostics"), readout_configuration=native), module

    def test_only_three_cached_layer_probes_are_fitted_and_main_layer6_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            c, module = self.fixture(directory)
            original = module.produce_missing_features
            with patch("tools.d_recipe.resources.execution_site"):
                gpu = run_gpu(c, evaluator=module, guard=Mock())
                run_gpu(c, evaluator=module, guard=Mock())
                cpu = run_cpu(c, evaluator=module, guard=Mock())
                run_cpu(c, evaluator=module, guard=Mock())
            self.assertEqual(gpu["status"], "GPU_LAYER_READOUTS_COMPLETE_WAITING_CPU")
            self.assertEqual(cpu["status"], "COMPLETE")
            self.assertEqual(module.run.call_count, 3)
            self.assertEqual(module.score.call_count, 3)
            self.assertIs(module.produce_missing_features, original)
            original.assert_not_called()
            self.assertFalse(cpu["decision_input"])
            self.assertFalse(cpu["encoder_forward_repeated"])
            self.assertTrue(cpu["layers"]["6"]["reused_main_readout"])
            self.assertEqual(cpu["layers"]["6"]["scores"], str(Path(directory, "main/scores.json")))

    def test_changed_checkpoint_cannot_reuse_closed_diagnostic_results(self):
        with tempfile.TemporaryDirectory() as directory:
            c, module = self.fixture(directory)
            with patch("tools.d_recipe.resources.execution_site"):
                run_gpu(c, evaluator=module, guard=Mock())
                c["readout_configuration"]["checkpoint"] = "/other/3M.pt"
                with self.assertRaises(ValueError):
                    run_gpu(c, evaluator=module, guard=Mock())

    def test_nonadopted_wide_conditions_cannot_start_diagnostic_probe_fits(self):
        with tempfile.TemporaryDirectory() as directory:
            c, module = self.fixture(directory)
            c["readout_configuration"]["arm"] = "D-L1"
            with patch("tools.d_recipe.resources.execution_site"), self.assertRaises(ValueError):
                run_gpu(c, evaluator=module, guard=Mock())
            module.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
