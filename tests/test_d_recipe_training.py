"""Reuse/registration of the P loop, without launching training or a GPU."""
from copy import deepcopy
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.d_recipe.training import (BLOCK_ALIASES, ResultRoot, installed_bridge,
                                    prepare_runtime, train)


def configuration():
    return dict(condition="D", arm="D-R0", run="D-R0-seed0", seed=0, samples=3000000,
        batch_size=32, microbatch_size=32, lr=3e-4, weight_decay=.01, betas=[.9, .95],
        warmup_fraction=.02, distance_bias="C1-0", schedule="cosine", p_recipe={},
        clip_calibration=dict(calibration_samples=150000, window_start_samples=60000,
                              initial_clip=281.7, quantile=.99),
        d_recipe=dict(enabled=True, library="D20", block_weights=dict(
            graph_2d=.6, molecule_3d=.3, atom_sasa=.1)))


class TrainingTests(unittest.TestCase):
    def test_disabled_adapter_is_exact_pass_through(self):
        c, result = {"d_recipe": {"enabled": False}}, object()
        original = Mock(return_value=result)
        self.assertIs(train(c, module=SimpleNamespace(train=original)), result)
        self.assertIs(original.call_args.args[0], c)

    def test_runtime_weights_and_checkpoints_match_taskbook_without_mutating_input(self):
        original = configuration()
        before = deepcopy(original)
        c = prepare_runtime(original)
        self.assertEqual(original, before)
        self.assertEqual(c["checkpoint_samples"], [1000000, 2000000, 3000000])
        self.assertFalse(c["step_overhead"]["prepared_input"])
        self.assertTrue(c["d_recipe"]["pma_compatibility"])
        self.assertEqual(c["p_recipe"]["field_loss_multipliers"],
            {BLOCK_ALIASES[k]: v for k, v in original["d_recipe"]["block_weights"].items()})
        self.assertEqual(c["d_recipe"]["scientific_binding"]["samples"], 3000000)

    def test_unknown_arm_and_wrong_budget_or_seed_are_rejected(self):
        for changes in (dict(arm="extra"), dict(samples=1500000), dict(seed=2),
                        dict(arm="9M-D-R0", samples=9000000, seed=1)):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                prepare_runtime(dict(configuration(), **changes))

    def test_conditional_mask_and_deletion_cannot_leak_to_other_arms(self):
        c = configuration()
        c["d_recipe"].update(graph_mask_enabled=True)
        with self.assertRaisesRegex(ValueError, "Random target"):
            prepare_runtime(c)
        c = configuration()
        c["arm"] = "D-K1"
        with self.assertRaisesRegex(ValueError, "adopted wide"):
            prepare_runtime(c)
        c["d_recipe"].update(library="L2", adopted_wide=True, graph_mask_enabled=True)
        self.assertTrue(prepare_runtime(c)["d_recipe"]["graph_mask_enabled"])
        c = configuration()
        c["arm"] = "D-G1"
        with self.assertRaisesRegex(ValueError, "disable both"):
            prepare_runtime(c)
        c["d_recipe"]["include_3d"] = False
        self.assertEqual(prepare_runtime(c)["p_recipe"]["field_loss_multipliers"][BLOCK_ALIASES["graph_2d"]], .6)

    def test_changed_checkpoint_identity_is_not_silently_rebound(self):
        c = configuration()
        c["d_recipe"]["scientific_binding"] = {"seed": 1}
        with self.assertRaisesRegex(ValueError, "binding contradicts"):
            prepare_runtime(c)

    def test_only_result_prefix_is_redirected(self):
        root = ResultRoot("/D-project")
        self.assertEqual(root / "results/p_recipe/training" / "run", Path("/D-project/results/d_recipe/training/run"))
        self.assertEqual(root / "configs/p_recipe", Path("/D-project/configs/p_recipe"))

    def test_process_local_bridge_restores_globals_even_after_failure(self):
        originals = {name: object() for name in ("V31PDModel", "PRecipeDataset", "init_reader", "read_choice", "REPO")}
        originals["dataset_configuration"] = lambda c, validation=False: {"split": "FULL" if validation else "TRAIN"}
        module = SimpleNamespace(**originals)
        factory = Mock(return_value=object())
        c = prepare_runtime(configuration())
        with self.assertRaisesRegex(RuntimeError, "intentional"):
            with installed_bridge(c, module=module, model_class=factory, dataset_class=object) as held:
                model = module.V31PDModel("encoder", "view", forms="H1")
                self.assertIs(held["model"], model)
                self.assertEqual(factory.call_args.kwargs["d_recipe"], c["d_recipe"])
                reader = module.dataset_configuration(c, validation=True)
                self.assertEqual(reader["split"], "FULL")
                self.assertEqual(reader["d_recipe"]["library"], "D20")
                raise RuntimeError("intentional")
        for key, original in originals.items():
            self.assertIs(getattr(module, key), original)


if __name__ == "__main__":
    unittest.main()
