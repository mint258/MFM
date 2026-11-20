"""Tiny input/scope adapter tests; the existing LightGBM learner is mocked."""
import dataclasses
import unittest
from unittest.mock import Mock

import numpy as np
import torch

from phychem_mfm.phase1.v3_dev_evaluation import TaskMolecule, TaskSpec
from tools.d_recipe.descriptor_features import DownstreamFeatureBatch
from tools.d_recipe.dev_lightgbm import run_lightgbm_probe


def row(mid, target, valid=True):
    return TaskMolecule(mid, torch.zeros((2, 3), dtype=torch.float32), torch.arange(2),
        torch.tensor([target], dtype=torch.float64), torch.tensor([True]), torch.tensor([valid]), "member:" + mid)


def batch(rows):
    raw = np.asarray([[float(i), np.inf] for i in range(len(rows))], dtype=np.float64)
    codes = np.tile(np.asarray([1, 2], dtype=np.uint8), (len(rows), 1))
    return DownstreamFeatureBatch(tuple(r.source_member_uid for r in rows), tuple(r.molecule_uid for r in rows),
        tuple("original" for _ in rows), ("zero", "numeric-event"), raw, raw / 2., codes, codes == 1)


class DevelopmentLightGBMTests(unittest.TestCase):
    def setUp(self):
        self.train = (row("train-a", 1.), row("held-b", 99.), row("train-c", 3., False))
        self.validation = (row("validation-d", 4.), row("validation-e", 5.))
        self.task = TaskSpec("qm9.alpha", "qm9", "alpha", "graph", "mae")
        self.model = Mock()
        self.model.get_params.return_value = {"n_estimators": 100}
        self.model.predict.return_value = np.asarray([2., 2.])
        self.factory = Mock(return_value=self.model)

    def call(self, **kwargs):
        args = dict(optimization_molecule_uids=("train-a", "train-c"), descriptor_value_source="raw",
            n_jobs=1, model_factory=self.factory)
        args.update(kwargs)
        return run_lightgbm_probe(self.train, self.validation, self.task, batch(self.train), batch(self.validation), **args)

    def test_original_scope_masks_native_missing_and_fixed_defaults_are_preserved(self):
        prediction, meta, model = self.call()
        self.factory.assert_called_once_with(random_state=20261025, n_jobs=1, verbosity=-1)
        x, y = self.model.fit.call_args.args
        self.assertEqual(x.shape, (1, 2))
        self.assertEqual(x[0, 0], 0.)
        self.assertTrue(np.isnan(x[0, 1]))
        np.testing.assert_array_equal(y, [1.])
        self.assertEqual(meta["internal_molecule_uids"], ["held-b"])
        self.assertFalse(meta["validation_used_for_fit"])
        self.assertEqual(prediction.source_record_uids, ("member:validation-d", "member:validation-e"))
        self.assertIs(model, self.model)

    def test_frozen_values_are_used_without_fitting_another_normalizer(self):
        self.call(optimization_molecule_uids=("held-b",), descriptor_value_source="frozen_train_standardized")
        x, y = self.model.fit.call_args.args
        self.assertEqual(x[0, 0], .5)
        np.testing.assert_array_equal(y, [99.])

    def test_unknown_or_validation_scope_and_source_identity_mismatch_reject_before_fit(self):
        for scope in ((), ("validation-d",), ("unknown",)):
            with self.assertRaisesRegex(ValueError, "scope"):
                self.call(optimization_molecule_uids=scope)
        bad = dataclasses.replace(batch(self.train), member_uids=("wrong", "member:held-b", "member:train-c"))
        with self.assertRaisesRegex(ValueError, "identities"):
            run_lightgbm_probe(self.train, self.validation, self.task, bad, batch(self.validation),
                optimization_molecule_uids=("train-a",), descriptor_value_source="raw", n_jobs=1, model_factory=self.factory)
        self.model.fit.assert_not_called()
