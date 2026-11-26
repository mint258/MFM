"""Tiny collector resume/selection tests; no real labels or production fit."""
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "d_recipe"))
from fit_reference import COLLECTION_SEED, collect, fit_collected, molecular_fields, reference_write_guard


class FakeDataset:
    def __init__(self):
        self.split = "TRAIN"
        self.native = SimpleNamespace(evaluation=False)
        self.native._molecules = {}
        self.cache_highwater = 0
        self.indices = np.array([2, 4, 7, 9, 11, 13, 17, 20, 22], dtype=np.int64)
        self.reads = []
        self.bad_role = None
        fields = [dict(name="D20.x", group="D", level="molecule"),
                  dict(name="D3.PMI1", group="P", source_group="D", level="molecule"),
                  dict(name="D20.MolMR", group="D", level="molecule", loss_enabled=False),
                  dict(name="D3.SASA_atom_A2", group="D", level="atom"),
                  dict(name="P.energy", group="P", level="molecule")]
        normalizations = {field["name"]: dict(fit_role="TRAIN", center=[0.], scale=[1.]) for field in fields}
        self.view = SimpleNamespace(fields=fields, normalizations=normalizations)

    def choices(self, molecule):
        return np.array([0, 1, 3], dtype=np.int64)

    def read(self, molecule, conformer):
        self.reads.append((molecule, conformer))
        self.native._molecules[molecule] = (molecule, conformer)
        self.cache_highwater = max(self.cache_highwater, len(self.native._molecules))
        originals = {
            "D20.x": SimpleNamespace(raw=np.array([[np.nan if molecule == 7 else molecule + conformer / 10.]]),
                                      valid=np.array([[molecule != 7]], dtype=bool)),
            "D3.PMI1": SimpleNamespace(raw=np.array([[10 * molecule + conformer / 100.]]),
                                        valid=np.array([[True]], dtype=bool))}
        return dict(molecule_index=molecule, role="VAL" if molecule == self.bad_role else "TRAIN",
                    Z=np.array([1, 1, 6], dtype=np.int64), original_targets=originals,
                    targets={key: SimpleNamespace(raw=np.array([[999.]]), valid=np.array([[True]]))
                             for key in originals})


class FitReferenceCollectorTests(unittest.TestCase):
    def test_shared_reference_keeps_the_joint_forecast_instead_of_only_its_small_collection(self):
        config = dict(peak_bytes=2 * 2**30, share_storage_peak_bytes=36706053853,
            peer_storage_guard_root="/existing/heads", output_filesystem="/share")
        with patch("tools.d_recipe.resources.execution_site") as site, \
             patch("tools.d_recipe.resources.admit_output") as admit:
            guard = reference_write_guard(config, "/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/full/reference")
            guard(Path("/share/home/zixiao/descriptor_analysis/runs/d_recipe_20261120/full/reference"), config["peak_bytes"])
        self.assertEqual(admit.call_args.args[0]["storage_peak_bytes"], 36706053853)
        site.assert_called_once_with(admit.call_args.args[0], cpu=True)

    def configuration(self):
        return dict(ridge_alpha=1., fold_seed=15, model_name="D-R1:seed0:A1",
                    peak_bytes=1000000, collector_chunk_rows=2)

    def guard(self, path, peak):
        self.assertTrue(Path(path).is_dir())
        self.assertEqual(peak, 1000000)

    def test_field_selection_uses_enabled_molecular_d_scalars_including_3d(self):
        self.assertEqual(molecular_fields(FakeDataset()), ("D20.x", "D3.PMI1"))

    def test_same_order_choices_and_raw_observations_survive_chunk_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = self.configuration()
            full, partial = FakeDataset(), FakeDataset()
            complete = collect(full, root / "full", config, guard=self.guard)
            first = collect(partial, root / "resumed", config, guard=self.guard, stop_after_chunks=1)
            self.assertEqual(first["closed_rows"], 2)
            # Simulate writes past the last closed checkpoint, then a crash.
            raw = np.lib.format.open_memmap(root / "resumed" / "raw.npy", mode="r+")
            raw[2] = [-999., -999.]
            raw.flush()
            resumed = FakeDataset()
            closed = collect(resumed, root / "resumed", config, guard=self.guard)
            self.assertEqual(closed["status"], "COLLECTION_COMPLETE")
            self.assertEqual(complete["closed_rows"], len(full.indices))
            self.assertEqual(partial.reads + resumed.reads, full.reads)
            for name in ("order.npy", "choices.npy", "design.npy", "raw.npy", "valid.npy"):
                np.testing.assert_array_equal(np.load(root / "full" / name), np.load(root / "resumed" / name))
            order = np.random.default_rng(COLLECTION_SEED).permutation(full.indices)
            rng = np.random.default_rng(COLLECTION_SEED)
            expected = np.array([(molecule, rng.choice(full.choices(molecule))) for molecule in order])
            np.testing.assert_array_equal(np.load(root / "full" / "choices.npy"), expected)
            np.testing.assert_array_equal(np.load(root / "full" / "design.npy")[:, 0], np.full(len(order), 2.))
            self.assertEqual(closed["binding"]["fields"], ["D20.x", "D3.PMI1"])
            self.assertFalse(np.any(np.load(root / "full" / "raw.npy") == 999.))
            previous_reads = list(resumed.reads)
            collect(resumed, root / "resumed", config, guard=self.guard)
            self.assertEqual(previous_reads, resumed.reads)  # closed data are not recomputed

    def test_validation_population_or_validation_sample_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dataset = FakeDataset()
            dataset.split = "FULL"
            with self.assertRaisesRegex(ValueError, "TRAIN corpus only"):
                collect(dataset, root / "not_train", self.configuration(), guard=self.guard)
            dataset = FakeDataset()
            dataset.bad_role = int(np.random.default_rng(COLLECTION_SEED).permutation(dataset.indices)[0])
            with self.assertRaisesRegex(ValueError, "sample role"):
                collect(dataset, root / "bad_sample", self.configuration(), guard=self.guard)
            state = json.loads((root / "bad_sample" / "collection_checkpoint.json").read_text())
            self.assertEqual(state["closed_rows"], 0)

    def test_cooperative_stop_observes_committed_cursor_and_preserves_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            root, config = Path(directory), self.configuration()
            full, partial, resumed = FakeDataset(), FakeDataset(), FakeDataset()
            collect(full, root / "full", config, guard=self.guard)
            observed = []

            def stop():
                marker = json.loads((root / "segmented" / "collection_checkpoint.json").read_text())
                observed.append(marker["closed_rows"])
                return True

            first = collect(partial, root / "segmented", config, guard=self.guard, should_stop=stop)
            self.assertEqual(observed, [2])
            self.assertEqual(first["closed_rows"], 2)
            self.assertEqual(first["status"], "COLLECTING")
            final = collect(resumed, root / "segmented", config, guard=self.guard)
            self.assertEqual(final["status"], "COLLECTION_COMPLETE")
            self.assertEqual(partial.reads + resumed.reads, full.reads)
            for name in ("order.npy", "choices.npy", "design.npy", "raw.npy", "valid.npy"):
                np.testing.assert_array_equal(np.load(root / "full" / name),
                                              np.load(root / "segmented" / name))

    def test_changed_frozen_config_cannot_resume_a_different_condition(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "store"
            collect(FakeDataset(), output, self.configuration(), guard=self.guard, stop_after_chunks=1)
            dataset = FakeDataset()
            with self.assertRaisesRegex(ValueError, "configuration or field population changed"):
                collect(dataset, output, {**self.configuration(), "fold_seed": 16}, guard=self.guard)
            self.assertEqual(dataset.reads, [])

    def test_underpowered_fields_are_recorded_unresolved_and_keep_original_parameters(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "store"
            dataset, config = FakeDataset(), self.configuration()
            collect(dataset, output, config, guard=self.guard)
            destination = fit_collected(dataset, output, config, guard=self.guard)
            parameters = json.loads(destination.read_text())
            self.assertEqual(parameters["fit"]["status"], "UNRESOLVED_NO_ELIGIBLE_FIELDS")
            self.assertEqual(parameters["normalizations"], dataset.view.normalizations)
            self.assertEqual({field["field_name"] for field in parameters["fit"]["unresolved_fields"]},
                             {"D20.x", "D3.PMI1"})
            self.assertEqual(next(field["n_valid"] for field in parameters["fit"]["unresolved_fields"]
                                  if field["field_name"] == "D20.x"), 8)
            self.assertEqual(next(field["clipped_TRAIN_count"] for field in parameters["fit"]["fields"]
                                  if field["field_name"] == "D3.PMI1"), 9)
            # Existing published parameters close the fit; no new fit is run.
            self.assertEqual(fit_collected(dataset, output, config, guard=self.guard), destination)

    def test_native_molecule_cache_is_bounded_without_clearing_other_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            dataset = FakeDataset()
            sentinel = object()
            dataset.native._molecules["untouched"] = sentinel
            # New nested parents are created only after guarding their nearest
            # existing ancestor, then the final output directory is guarded.
            output = Path(directory) / "new_reference" / "nested" / "store"
            collect(dataset, output, self.configuration(), guard=self.guard)
            self.assertEqual(dataset.cache_highwater, 2)
            self.assertEqual(list(dataset.native._molecules), ["untouched"])
            self.assertIs(dataset.native._molecules["untouched"], sentinel)


if __name__ == "__main__":
    unittest.main()
