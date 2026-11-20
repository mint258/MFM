"""New B/C factories and data layout only; mock the native training loop."""
from dataclasses import replace
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

import numpy as np
import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "current"))
sys.path.insert(0, str(ROOT / "tools" / "d_recipe"))
from phychem_mfm.phase1.v3_dev_evaluation import TaskMolecule, TaskSpec
from phychem_mfm.phase1.v3_dev_readouts import FrozenFeatureProbe
from dev_descriptor_readouts import (DescriptorMLP, H0DescriptorR3, attach_descriptors,
                                    capacity_plan, composition_features, model_descriptor_features,
                                    optimization_h0_statistics, run_descriptor_probe,
                                    trainable_parameters)


def rows(prefix="train", count=12):
    result = []
    for index in range(count):
        result.append(TaskMolecule(
            prefix + ":" + str(index),
            torch.tensor([[float(index), 9., index * .5], [index + 1., 9., index * .5 + 1.]]),
            torch.arange(2), torch.tensor([float(index)]), torch.tensor([True]), torch.tensor([True]),
            prefix + ":member:" + str(index)))
    return tuple(result)


def descriptor_batch(source_rows):
    count = len(source_rows)
    raw = np.stack((np.arange(count, dtype=np.float64), np.full(count, 3.)), axis=1)
    valid = np.ones_like(raw, dtype=bool)
    raw[0, 1], valid[0, 1] = np.nan, False
    return SimpleNamespace(fields=("first", "second"), raw_values=raw, values=raw / 2,
                           observed_valid=valid,
                           molecule_ids=tuple(row.molecule_uid for row in source_rows),
                           member_uids=tuple(row.source_member_uid for row in source_rows))


class DescriptorReadoutTests(unittest.TestCase):
    def test_composition_uses_explicit_hydrogen_and_heavy_counts_without_inference(self):
        observed = composition_features(np.array([1, 1, 6, 8], dtype=np.int64))
        self.assertEqual(observed.shape, (119,))
        self.assertEqual(observed[0], 2)
        self.assertEqual(observed[5], 1)
        self.assertEqual(observed[7], 1)
        self.assertEqual(observed[-1], 2)
        np.testing.assert_array_equal(observed, composition_features({1: 2, 6: 1, 8: 1}))
        self.assertEqual(composition_features([6])[0], 0)  # never infer four H from carbon

    def test_capacity_is_explicit_and_analytical_counts_match_actual_models(self):
        prototype = FrozenFeatureProbe(3, readout="R3", output_level="graph", n_ref=2.,
                                       mean=torch.zeros(3), scale=torch.ones(3))
        for branch in ("B", "C"):
            for policy in ("total_params_matching", "hidden_width_256"):
                plan = capacity_plan(branch=branch, capacity_policy=policy, descriptor_fields=2,
                                     native_prototype=prototype)
                model = (DescriptorMLP(2, plan["hidden_width"]) if branch == "B" else
                         H0DescriptorR3(3, field_count=2, hidden_width=plan["hidden_width"],
                                        n_ref=2., mean=torch.zeros(3), scale=torch.ones(3),
                                        native_factory=FrozenFeatureProbe))
                self.assertEqual(trainable_parameters(model), plan["trainable_parameters"])
                self.assertEqual(plan["native_A_trainable_parameters"], trainable_parameters(prototype))
                if policy == "hidden_width_256":
                    self.assertEqual(plan["hidden_width"], 256)
                else:
                    self.assertLessEqual(abs(plan["parameter_difference"]),
                                         (plan["molecular_mlp_input_width"] + 2) / 2)
        with self.assertRaisesRegex(ValueError, "capacity_policy"):
            capacity_plan(branch="B", capacity_policy="choose_by_validation", descriptor_fields=2,
                          native_prototype=prototype)
        with self.assertRaises(TypeError):
            run_descriptor_probe(None, None, None, None, None, branch="B", descriptor_value_source="raw",
                                 n_ref=2., tracker=None, relative_std_floor=True, internal_epoch_selection=True)

    def test_h0_stats_exclude_internal_holdout_and_keep_native_relative_std_mask(self):
        source = rows()
        scope = optimization_h0_statistics(source, relative_std_floor=True, internal_epoch_selection=True)
        self.assertEqual(len(scope.internal_uids), 2)
        self.assertEqual(scope.keep.tolist(), [True, False, True])
        changed = tuple(replace(row, h0=torch.full_like(row.h0, 1e20)) if row.molecule_uid in scope.internal_uids
                        else row for row in source)
        again = optimization_h0_statistics(changed, relative_std_floor=True, internal_epoch_selection=True)
        self.assertTrue(torch.equal(scope.keep, again.keep))
        self.assertTrue(torch.equal(scope.mean, again.mean))
        self.assertTrue(torch.equal(scope.scale, again.scale))
        self.assertFalse(set(scope.internal_uids) & set(scope.optimization_uids))

    def test_missing_padding_is_model_boundary_only_and_valid_overflow_is_rejected(self):
        source = rows(count=2)
        batch = descriptor_batch(source)
        before = batch.raw_values.copy()
        attached = attach_descriptors(source, batch, value_source="raw")
        self.assertIsNone(source[0].graph_features)
        direct = torch.stack([row.graph_features for row in attached])
        model_input = model_descriptor_features(direct, 2)
        self.assertTrue(torch.equal(model_input[0], torch.tensor([0., 0., 0., 1.])))
        self.assertTrue(torch.isnan(attached[0].graph_features[1]))
        np.testing.assert_array_equal(batch.raw_values, before)
        overflow = torch.tensor([[1e300, 0., 1., 0.]], dtype=torch.float64)
        with self.assertRaisesRegex(ValueError, "finite model FP32"):
            model_descriptor_features(overflow, 2)

    def test_namespace_member_keys_are_explicit_and_not_guessed(self):
        source = rows(count=1)
        batch = descriptor_batch(source)
        batch.member_uids = (("original-dataset", "42"),)
        with self.assertRaisesRegex(ValueError, "member identities"):
            attach_descriptors(source, batch, value_source="raw")
        attached = attach_descriptors(source, batch, value_source="raw", member_keys=[("original-dataset", "42")])
        self.assertEqual(len(attached), 1)

    def test_c_uses_native_atom_r3_then_concat_and_does_not_backprop_to_h0(self):
        model = H0DescriptorR3(3, field_count=2, hidden_width=7, n_ref=2.,
                               mean=torch.zeros(3), scale=torch.ones(3), native_factory=FrozenFeatureProbe)
        h = torch.ones((2, 2, 3), requires_grad=True)
        mask = torch.tensor([[True, False], [True, True]])
        direct = torch.tensor([[0., float("nan"), 1., 0.], [2., 3., 1., 1.]], dtype=torch.float64)
        prediction = model(h, mask, direct)
        self.assertEqual(prediction.shape, (2,))
        self.assertTrue(torch.isfinite(prediction).all())
        prediction.sum().backward()
        self.assertIsNone(h.grad)
        self.assertIsNotNone(model.native.atom[0].weight.grad)
        self.assertEqual(model.native.output[0].in_features, 512 + 4)

    def test_wrapper_reuses_loop_and_c_h0_scope_and_restores_factory(self):
        train, validation = rows(), rows("validation", 3)
        train_batch, val_batch = descriptor_batch(train), descriptor_batch(validation)
        scope = optimization_h0_statistics(train, relative_std_floor=True, internal_epoch_selection=True)
        seen = {}
        module = SimpleNamespace(FrozenFeatureProbe=FrozenFeatureProbe)

        def fake_loop(actual_train, actual_validation, task, **options):
            seen.update(options)
            # Reproduce the native constructor call after its relative mask.
            # Its direct descriptor mean/scale intentionally cannot be H0 stats.
            model = module.FrozenFeatureProbe(len(scope.mean), readout="R3", output_level="graph", n_ref=2.,
                                               mean=torch.full((4,), float("nan")), scale=torch.zeros(4), direct_features=True)
            self.assertTrue(torch.equal(model.native.feature_mean, scope.mean.float()))
            self.assertTrue(torch.equal(model.native.feature_scale, scope.scale.float()))
            self.assertTrue(torch.isnan(actual_train[0].graph_features[1]))
            self.assertEqual(actual_validation[0].molecule_uid, "validation:0")
            return "predictions", {"updates": 0, "state_dict": {}}

        module.run_probe = fake_loop
        task = TaskSpec("task", "dataset", "value", "graph", "mae")
        prediction, report = run_descriptor_probe(
            train, validation, task, train_batch, val_batch, branch="C", capacity_policy="hidden_width_256",
            descriptor_value_source="frozen_train_standardized", n_ref=2., tracker=object(),
            relative_std_floor=True, internal_epoch_selection=True, module=module)
        self.assertEqual(prediction, "predictions")
        self.assertIs(module.FrozenFeatureProbe, FrozenFeatureProbe)
        self.assertTrue(seen["relative_std_floor"])
        self.assertTrue(seen["internal_epoch_selection"])
        self.assertFalse(report["descriptor_statistics_refitted"])
        self.assertEqual(report["capacity"]["capacity_policy"], "hidden_width_256")
        self.assertEqual(set(report["internal_molecule_uids"]), set(scope.internal_uids))

    def test_factory_is_restored_when_the_unchanged_native_loop_raises(self):
        train, validation = rows(), rows("validation", 2)
        module = SimpleNamespace(FrozenFeatureProbe=FrozenFeatureProbe)

        def fail(*args, **kwargs):
            raise RuntimeError("original loop failure")

        module.run_probe = fail
        with self.assertRaisesRegex(RuntimeError, "original loop failure"):
            run_descriptor_probe(train, validation, TaskSpec("task", "dataset", "value", "graph", "mae"),
                                 descriptor_batch(train), descriptor_batch(validation), branch="B",
                                 capacity_policy="total_params_matching", descriptor_value_source="raw",
                                 n_ref=2., tracker=object(), relative_std_floor=True,
                                 internal_epoch_selection=True, module=module)
        self.assertIs(module.FrozenFeatureProbe, FrozenFeatureProbe)


if __name__ == "__main__":
    unittest.main()
