"""New molecule-selection semantics on tiny synthetic IDs only."""
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from tools.d_recipe.scaling_selection import actual_intersection, installed_selection, plan_subset


class DScalingSelectionTests(unittest.TestCase):
    def inputs(self):
        best = dict(status="FROZEN", recipe_frozen=True, arm="D-R1", library="D20")
        source = dict(condition="D", arm="9M-D-final", seed=0, samples=9000000,
            resource_admission_pending=True, subset_molecules=None,
            corpus="same_original_native_corpus",
            normalizations="original_1107_full_TRAIN", label_parameters="frozen_full_TRAIN_A1",
            clip_calibration=dict(window_start_samples=60000, calibration_samples=150000,
                                  initial_clip=281.7, quantile=.99, sample_axis="optimizer_step_start"),
            d_recipe=dict(library="D20", scientific_binding=dict(arm="9M-D-final")))
        p = dict(arm="T5", subset_molecules=250000, subset_seed=20261112,
                 corpus="same_original_native_corpus",
                 actual_selected_indices="original_P_actual_list.npy", configuration="original_P_T5.json")
        return best, source, p

    def test_intersection_retains_actual_P_order_without_any_new_draw(self):
        with patch("numpy.random.default_rng", side_effect=AssertionError("No resampling")):
            np.testing.assert_array_equal(actual_intersection(np.array([7, 3, 5]), np.array([3, 4, 7])), [7, 3])
        with self.assertRaises(ValueError):
            actual_intersection(np.array([1, 1]), np.array([1, 2]))
        with self.assertRaises(ValueError):
            actual_intersection(np.array([1.]), np.array([1, 2]))

    def test_plan_requires_freeze_and_actual_source_preserving_full_TRAIN_parameters(self):
        best, source, p = self.inputs()
        with self.assertRaisesRegex(ValueError, "frozen"):
            plan_subset(dict(best, recipe_frozen=False), source, p, np.array([7, 3, 5]), np.array([3, 4, 7]),
                        output_root="/owned", run_prefix="D_")
        bad = dict(p, actual_selected_indices=None)
        with self.assertRaisesRegex(ValueError, "actual frozen P"):
            plan_subset(best, source, bad, np.array([7, 3, 5]), np.array([3, 4, 7]),
                        output_root="/owned", run_prefix="D_")
        original = deepcopy(source)
        plan = plan_subset(best, source, p, np.array([7, 3, 5]), np.array([3, 4, 7]),
                           output_root="/owned", run_prefix="D_")
        self.assertEqual(source, original)
        self.assertEqual(plan["configuration"]["normalizations"], source["normalizations"])
        self.assertEqual(plan["configuration"]["label_parameters"], source["label_parameters"])
        self.assertEqual(plan["configuration"]["clip_calibration"], source["clip_calibration"])
        self.assertIsNone(plan["configuration"]["subset_molecules"])
        self.assertEqual(plan["configuration"]["d_explicit_molecule_selection"]["intersection_molecules"], 2)
        np.testing.assert_array_equal(plan["indices"], [7, 3])

    def test_reader_override_changes_only_TRAIN_and_restores_on_failure(self):
        best, source, p = self.inputs()
        plan = plan_subset(best, source, p, np.array([7, 3, 5]), np.array([3, 4, 7]),
                           output_root="/owned", run_prefix="D_")
        c = plan["configuration"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "indices.npy"
            np.save(path, plan["indices"], allow_pickle=False)
            c["d_explicit_molecule_selection"]["indices"] = str(path)
            c["d_recipe"]["scientific_binding"]["molecule_selection"]["indices"] = str(path)
            def reader(config, *, validation=False):
                return dict(indices=np.array([91, 92]) if validation else np.arange(10),
                            normalizations=config["normalizations"])
            module = SimpleNamespace(dataset_configuration=reader)
            with self.assertRaisesRegex(RuntimeError, "fixture"):
                with installed_selection(c, module):
                    np.testing.assert_array_equal(module.dataset_configuration(c)["indices"], [7, 3])
                    np.testing.assert_array_equal(module.dataset_configuration(c, validation=True)["indices"], [91, 92])
                    self.assertEqual(module.dataset_configuration(c)["normalizations"], "original_1107_full_TRAIN")
                    raise RuntimeError("fixture")
            self.assertIs(module.dataset_configuration, reader)


if __name__ == "__main__":
    unittest.main()
