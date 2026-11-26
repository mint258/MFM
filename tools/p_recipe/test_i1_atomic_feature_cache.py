"""Exercise the actual I1 H0 adapter cache path on CPU, including its late import."""
import ast
from pathlib import Path
import tempfile
import types
import unittest
from unittest import mock

import torch
import finetune


class I1AtomicFeatureCacheTests(unittest.TestCase):
    def adapter(self, root):
        source = Path(__file__).with_name("i1_readout_entry.py").read_text()
        tree = ast.parse(source)
        node = next(x for x in ast.walk(tree)
                    if isinstance(x, ast.FunctionDef) and x.name == "features")
        original_payload = {
            "records": [{"molecule_uid": "cache-contract", "member_index": 7,
                         "h0": torch.arange(6, dtype=torch.float32).reshape(2, 3),
                         "source_atom_ids": torch.tensor([4, 8])}],
            "n_ref": 2.0}
        produced = []
        boundaries = []
        def path(configuration, dataset):
            return Path(configuration["features"]) / (dataset + ".pt")
        def original(configuration, dataset, view, **kwargs):
            if configuration["persist_features"]:
                return torch.load(path(configuration, dataset), weights_only=True)
            produced.append((configuration, dataset, view))
            return original_payload
        scope = {"evaluate": types.SimpleNamespace(feature_path=path),
                 "original_features": original,
                 "boundary": lambda: boundaries.append(True)}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
                     "<actual-I1-feature-adapter>", "exec"), scope)
        configuration = {"features": str(root), "persist_features": True}
        return scope["features"], configuration, original_payload, produced, boundaries

    def test_original_payload_is_atomically_saved_without_transformation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "nested-cache"
            adapter, configuration, payload, produced, boundaries = self.adapter(root)
            with mock.patch.object(finetune, "atomic_checkpoint",
                                   wraps=finetune.atomic_checkpoint) as writer:
                returned = adapter(configuration, "qm9", object())
            path = root / "qm9.pt"
            self.assertIs(returned, payload)
            self.assertEqual(writer.call_count, 1)
            self.assertEqual(writer.call_args.args[0], path)
            self.assertIs(writer.call_args.args[1], payload)
            saved = torch.load(path, weights_only=True)
            self.assertTrue(torch.equal(saved["records"][0]["h0"],
                                        payload["records"][0]["h0"]))
            self.assertEqual(saved["records"][0]["h0"].dtype, torch.float32)
            self.assertEqual(saved["records"][0]["member_index"], 7)
            self.assertEqual(saved["n_ref"], 2.0)
            self.assertEqual(len(produced), 1)
            self.assertIs(produced[0][0]["persist_features"], False)
            self.assertEqual(len(boundaries), 2)
            self.assertFalse(list(root.glob("*.tmp*")))
            self.assertIs(configuration["persist_features"], True)

    def test_closed_cache_is_reused_and_never_reencoded_or_rewritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter, configuration, payload, produced, boundaries = self.adapter(Path(tmp))
            with mock.patch.object(finetune, "atomic_checkpoint",
                                   wraps=finetune.atomic_checkpoint) as writer:
                adapter(configuration, "qm9", object())
                returned = adapter(configuration, "qm9", object())
            self.assertEqual(len(produced), 1)
            self.assertEqual(writer.call_count, 1)
            self.assertTrue(torch.equal(returned["records"][0]["h0"],
                                        payload["records"][0]["h0"]))
            self.assertEqual(len(boundaries), 3)


if __name__ == "__main__":
    unittest.main()
