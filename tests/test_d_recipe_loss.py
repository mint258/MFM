"""Taskbook section 6 tests for the new isolated D block/mask logic."""
import math
from pathlib import Path
import sys
import unittest

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "d_recipe"))
from loss import (BLOCKS, DBlockWeights, compute_d_loss, loss_targets,
                  mask_graph_targets)


class DLossTests(unittest.TestCase):
    def fixture(self, graph_width=2):
        prediction = {name: torch.ones((2, graph_width if name == "graph_2d" else 3),
                                      dtype=torch.float64, requires_grad=True)
                      for name in BLOCKS}
        targets = {name: torch.zeros_like(value) for name, value in prediction.items()}
        valid = {name: torch.ones_like(value, dtype=torch.bool)
                 for name, value in prediction.items()}
        return prediction, targets, valid

    def test_wide_library_preserves_3d_weights_and_gradients(self):
        weights = DBlockWeights(0.7, 0.2, 0.1)  # fixture anchor, not production
        outputs = []
        for width in (2, 1613):
            prediction, target, valid = self.fixture(width)
            result = compute_d_loss(prediction, target, valid, weights, enabled=True)
            result.total.backward()
            outputs.append((result.total.detach(), prediction["molecule_3d"].grad,
                            prediction["atom_sasa"].grad))
        for left, right in zip(*outputs):
            self.assertTrue(torch.equal(left, right))

    def test_deleting_3d_does_not_redistribute_weight(self):
        prediction, target, valid = self.fixture()
        result = compute_d_loss(prediction, target, valid, DBlockWeights(.7, .2, .1),
                                enabled=True, include_3d=False)
        torch.testing.assert_close(result.total, torch.tensor(.35, dtype=torch.float64),
                                   rtol=1e-14, atol=1e-14)
        self.assertTrue(torch.equal(result.block_means["molecule_3d"], torch.zeros(2)))
        self.assertTrue(torch.equal(result.block_means["atom_sasa"], torch.zeros(2)))

    def test_each_sample_uses_its_actual_count_and_missing_nan_has_zero_gradient(self):
        prediction, target, valid = self.fixture()
        with torch.no_grad():
            prediction["graph_2d"].copy_(torch.tensor([[1., float("nan")], [2., 0.]]))
        valid["graph_2d"][0, 1] = False
        target["graph_2d"][0, 1] = float("nan")
        result = compute_d_loss(prediction, target, valid, DBlockWeights(1., 0., 0.), enabled=True)
        # First row: one valid Huber(1) = .5; second: mean(1.5, 0) = .75.
        torch.testing.assert_close(result.per_sample, torch.tensor([.5, .75], dtype=torch.float64),
                                   rtol=1e-14, atol=1e-14)
        result.total.backward()
        self.assertEqual(prediction["graph_2d"].grad[0, 1].item(), 0.)
        self.assertTrue(torch.isfinite(prediction["graph_2d"].grad).all())

    def test_all_empty_block_is_zero_even_with_nan_storage(self):
        prediction, target, valid = self.fixture()
        valid["graph_2d"].fill_(False)
        target["graph_2d"].fill_(float("nan"))
        result = compute_d_loss(prediction, target, valid, DBlockWeights(.7, .2, .1), enabled=True)
        self.assertTrue(torch.equal(result.block_means["graph_2d"], torch.zeros(2)))
        torch.testing.assert_close(result.total, torch.tensor(.15, dtype=torch.float64), rtol=1e-14, atol=1e-14)

    def test_target_only_clipping_preserves_storage_and_default_identity(self):
        stored = torch.tensor([-20., 0., 30.], dtype=torch.float64)
        before = stored.clone()
        self.assertIs(loss_targets(stored), stored)
        self.assertTrue(torch.equal(loss_targets(stored, enabled=True), torch.tensor([-6., 0., 6.])))
        self.assertTrue(torch.equal(before, stored))
        prediction, target, valid = self.fixture()
        target["graph_2d"].fill_(20.)
        prediction["graph_2d"] = torch.full_like(target["graph_2d"], 10., requires_grad=True)
        result = compute_d_loss(prediction, target, valid, DBlockWeights(1., 0., 0.), enabled=True)
        self.assertEqual(result.total.item(), 3.5)  # Huber(10 - clipped 6)
        self.assertTrue(torch.equal(target["graph_2d"], torch.full_like(target["graph_2d"], 20.)))

    def test_disabled_d_mode_returns_exact_legacy_result_without_touching_rng(self):
        generator = torch.Generator().manual_seed(20261120)
        before = generator.get_state().clone()
        original = torch.tensor([float("nan"), -0., 1e-30], dtype=torch.float64)
        result = compute_d_loss(None, None, None, None, legacy_loss=lambda: original,
                                graph_mask_enabled=True, generator=generator)
        self.assertIs(result, original)
        self.assertTrue(torch.equal(result.view(torch.int64), original.view(torch.int64)))
        self.assertTrue(torch.equal(before, generator.get_state()))

    def test_disabled_k1_has_exact_mask_identity_and_no_rng_consumption(self):
        generator = torch.Generator().manual_seed(20261120)
        valid = torch.tensor([[True, False], [True, True]])
        state = generator.get_state().clone()
        result = mask_graph_targets(valid, generator=generator)
        self.assertIs(result.observed_valid, valid)
        self.assertIs(result.effective_valid, valid)
        self.assertFalse(result.random_dropped.any())
        self.assertTrue(torch.equal(state, generator.get_state()))

    def test_k1_fraction_reproducibility_and_source_missing_separation(self):
        generator = torch.Generator().manual_seed(20261120)
        state = generator.get_state().clone()
        valid = torch.ones((256, 512), dtype=torch.bool)
        valid[:, ::5] = False
        original = valid.clone()
        result = mask_graph_targets(valid, enabled=True, generator=generator)
        observed = int(valid.sum())
        fraction = result.random_dropped.sum().item() / observed
        absolute_tolerance = 6 * math.sqrt(.85 * .15 / observed)
        self.assertLessEqual(abs(fraction - .85), absolute_tolerance)
        # Relative tolerance is the same binomial six-sigma bound / expected rate.
        self.assertLessEqual(abs(fraction / .85 - 1), absolute_tolerance / .85)
        self.assertTrue(torch.equal(valid, original))
        self.assertFalse(result.random_dropped[~valid].any())
        self.assertTrue(torch.equal(result.effective_valid, valid & ~result.random_dropped))
        generator.set_state(state)
        replay = mask_graph_targets(valid, enabled=True, generator=generator)
        self.assertTrue(torch.equal(result.random_dropped, replay.random_dropped))

    def test_k1_does_not_modify_either_3d_block(self):
        prediction, target, valid = self.fixture(512)
        result = compute_d_loss(prediction, target, valid, DBlockWeights(.7, .2, .1),
                                enabled=True, graph_mask_enabled=True,
                                generator=torch.Generator().manual_seed(20261120))
        for name in BLOCKS[1:]:
            self.assertIs(result.masks[name].effective_valid, valid[name])
            self.assertFalse(result.masks[name].random_dropped.any())

    def test_k1_requires_caller_rng(self):
        with self.assertRaisesRegex(ValueError, "checkpointed generator"):
            mask_graph_targets(torch.ones((1, 2), dtype=torch.bool), enabled=True)


if __name__ == "__main__":
    unittest.main()
