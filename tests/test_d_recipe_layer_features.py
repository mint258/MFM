"""Capture intermediate tensors while the unchanged producer forwards once."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.d_recipe.layer_features import capture_existing_forward, cached_features_only, cached_layer_configuration


class Encoder:
    def encode_atoms(self, batch, return_intermediates=False):
        return (batch + 100, [batch + i for i in range(1, 7)]) if return_intermediates else batch + 100


class LayerFeatureTests(unittest.TestCase):
    def fixture(self, root):
        model_module = SimpleNamespace(s_model=Mock(side_effect=lambda: (SimpleNamespace(encoder=Encoder()), {})))
        def producer(c, dataset, view):
            self.assertFalse(c["persist_features"])
            model, _ = model_module.s_model()
            first = model.encoder.encode_atoms(torch.arange(4.).reshape(2, 2))
            last = model.encoder.encode_atoms(torch.arange(4., 6.).reshape(1, 2))
            return dict(records=[dict(molecule_uid="a", source_atom_ids=["a1", "a0"], h0=first),
                                 dict(molecule_uid="b", source_atom_ids=["b0"], h0=last)], n_ref=1.5)
        evaluator = SimpleNamespace(produce_missing_features=Mock(side_effect=producer))
        c = dict(run="D-native", checkpoint="/own/3M.pt", store="/existing/dev.json", diagnostic_feature_root=str(root))
        return c, evaluator, model_module

    def test_single_native_forward_captures_layers_and_preserves_source_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            c, evaluator, model_module = self.fixture(directory)
            original, factory = evaluator.produce_missing_features, model_module.s_model
            with capture_existing_forward(c, evaluator=evaluator, model_module=model_module, guard=Mock()):
                result = evaluator.produce_missing_features(c, "qm9", None)
            self.assertIs(evaluator.produce_missing_features, original)
            self.assertIs(model_module.s_model, factory)
            original.assert_called_once()
            factory.assert_called_once()
            manifest = json.loads(Path(directory, "qm9/manifest.json").read_text())
            for layer in (3, 4, 5, 6):
                payload = torch.load(manifest["features"][str(layer)], weights_only=True)
                self.assertEqual(payload["n_ref"], 1.5)
                self.assertEqual(payload["records"][0]["source_atom_ids"], ["a1", "a0"])
                offset = 100 if layer == 6 else layer
                torch.testing.assert_close(payload["records"][0]["h0"], torch.arange(4.).reshape(2, 2) + offset)
            torch.testing.assert_close(result["records"][1]["h0"], torch.tensor([[104., 105.]]))
            with capture_existing_forward(c, evaluator=evaluator, model_module=model_module, guard=Mock()):
                reused = evaluator.produce_missing_features(c, "qm9", None)
            self.assertEqual(original.call_count, 1)
            torch.testing.assert_close(reused["records"][1]["h0"], result["records"][1]["h0"])

    def test_failure_restores_native_factory_and_producer(self):
        with tempfile.TemporaryDirectory() as directory:
            c, evaluator, model_module = self.fixture(directory)
            original, factory = evaluator.produce_missing_features, model_module.s_model
            original.side_effect = RuntimeError("native failed")
            with self.assertRaises(RuntimeError):
                with capture_existing_forward(c, evaluator=evaluator, model_module=model_module, guard=Mock()):
                    evaluator.produce_missing_features(c, "qm9", None)
            self.assertIs(evaluator.produce_missing_features, original)
            self.assertIs(model_module.s_model, factory)

    def test_old_final_layer_cache_does_not_trigger_an_additional_forward(self):
        with tempfile.TemporaryDirectory() as directory:
            c, evaluator, model_module = self.fixture(directory)
            evaluator.produce_missing_features = Mock(return_value=None)
            with capture_existing_forward(c, evaluator=evaluator, model_module=model_module, guard=Mock()):
                self.assertIsNone(evaluator.produce_missing_features(c, "qm9", None))
            model_module.s_model.assert_not_called()
            self.assertFalse(Path(directory, "qm9").exists())

    def test_cached_probe_mode_cannot_fall_back_to_extraction(self):
        with tempfile.TemporaryDirectory() as directory:
            module = SimpleNamespace(produce_missing_features=Mock(),
                feature_path=lambda c, d: Path(directory, d + ".pt"))
            original = module.produce_missing_features
            with self.assertRaises(FileNotFoundError):
                with cached_features_only(module):
                    module.produce_missing_features({}, "qm9", None)
            self.assertIs(module.produce_missing_features, original)
            original.assert_not_called()

    def test_layer_configuration_retains_original_binding_and_rejects_other_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            c, evaluator, model_module = self.fixture(directory)
            with capture_existing_forward(c, evaluator=evaluator, model_module=model_module, guard=Mock()):
                for dataset in ("expansionrx", "cyp_isoform", "qm9"):
                    evaluator.produce_missing_features(c, dataset, None)
            selected = cached_layer_configuration(c, 3, output=Path(directory, "probes"))
            self.assertEqual(selected["run"], "D-native__diagnostic_layer3")
            self.assertNotIn("diagnostic_feature_root", selected)
            self.assertEqual(selected["layer"], 3)
            with self.assertRaises(ValueError):
                cached_layer_configuration(dict(c, checkpoint="/other.pt"), 3, output=directory)


if __name__ == "__main__":
    unittest.main()
