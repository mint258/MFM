"""Tiny source fixtures for the new read-only wide descriptor consumer."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "d_recipe"))
from wide_store import SCHEMA, WideDescriptorStore


class WideStoreTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        # Deliberately physical order FULL/VAL, TRAIN index 8, TRAIN index 2.
        raw = np.array([[9., 50., 4.], [0., 70., np.nan], [np.inf, 80., 8.]], dtype=np.float64)
        status = np.array([[1, 1, 1], [1, 1, 0], [2, 1, 1]], dtype=np.uint8)
        np.save(root / "values.npy", raw)
        np.save(root / "status.npy", status)
        rows = [dict(molecule_id="val-8", molecule_index=8, split="FULL", role="VAL", smiles="O"),
                dict(molecule_id="train-8", molecule_index=8, split="TRAIN", role="TRAIN", smiles="C"),
                dict(molecule_id="train-2", molecule_index=2, split="TRAIN", role="TRAIN", smiles="CC")]
        (root / "rows.jsonl").write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        library = dict(values=str(root / "values.npy"), status=str(root / "status.npy"),
                       rows=str(root / "rows.jsonl"), ordered_fields=["f0", "filtered", "f2"],
                       enabled_columns=[2, 0], fit_role="TRAIN", producer_alignment_checked=True,
                       reception_acceptance="pending", normalization=[
                           dict(field_name="f0", mean=2., std_ddof0=2.), None,
                           dict(field_name="f2", center=4., scale=2.)])
        manifest = dict(schema=SCHEMA, libraries={"L1": library})
        path = root / "manifest.json"
        self.save(path, manifest)
        return path, manifest, rows, raw

    def save(self, path, value):
        Path(path).write_text(json.dumps(value), encoding="utf-8")

    def test_exact_split_and_source_index_alignment_preserves_requested_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _, _ = self.fixture(directory)
            store = WideDescriptorStore(path, "L1", expected_fields=["f2", "f0"])
            batch = store.get_batch("TRAIN", [2, 8], expected_ids=["train-2", "train-8"], expected_role="TRAIN")
            self.assertEqual(batch.molecule_ids, ("train-2", "train-8"))
            self.assertEqual(batch.molecule_indices, (2, 8))
            self.assertEqual(batch.fields, ("f2", "f0"))
            self.assertEqual(store.get_batch("FULL", [8]).molecule_ids, ("val-8",))
            np.testing.assert_array_equal(batch.observed_valid, [[True, False], [False, True]])

    def test_missing_numeric_event_and_true_zero_remain_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _, _ = self.fixture(directory)
            store = WideDescriptorStore(path, "L1")
            batch = store.get_batch("TRAIN", [8, 2])
            self.assertEqual(batch.raw_values[0, 1], 0.)
            self.assertTrue(batch.observed_valid[0, 1])
            self.assertEqual(batch.values[0, 1], -1.)
            self.assertTrue(np.isnan(batch.raw_values[0, 0]))
            self.assertEqual(batch.status[0, 0], 0)
            self.assertTrue(np.isinf(batch.raw_values[1, 1]))
            self.assertEqual(batch.status[1, 1], 2)
            self.assertTrue(np.isnan(batch.values[0, 0]))
            self.assertTrue(np.isnan(batch.values[1, 1]))

    def test_batch_standardization_does_not_mutate_raw_store_or_clip(self):
        with tempfile.TemporaryDirectory() as directory:
            path, manifest, _, raw = self.fixture(directory)
            store = WideDescriptorStore(path, "L1")
            batch = store.get_batch("TRAIN", [2])
            self.assertEqual(batch.values[0, 0], 2.)
            batch.values[0, 0] = -999.
            batch.raw_values[0, 0] = -888.
            np.testing.assert_array_equal(np.load(manifest["libraries"]["L1"]["values"]), raw)
            self.assertFalse(store._values.flags.writeable)
            self.assertEqual(store.reception_acceptance, "pending")

    def test_existing_d20_override_uses_original_parameters_without_refit(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _, _ = self.fixture(directory)
            store = WideDescriptorStore(path, "L1", normalization_overrides={"f2": dict(center=0., scale=.5)})
            batch = store.get_batch("TRAIN", [2])
            # Stored 8 / .5 = 16: the loader does not do loss-only +/-6 clipping.
            self.assertEqual(batch.values[0, 0], 16.)
            self.assertEqual(batch.raw_values[0, 0], 8.)

    def test_expected_field_order_and_parameter_order_are_checked_at_open(self):
        with tempfile.TemporaryDirectory() as directory:
            path, manifest, _, _ = self.fixture(directory)
            with self.assertRaisesRegex(ValueError, "field order"):
                WideDescriptorStore(path, "L1", expected_fields=["f0", "f2"])
            manifest["libraries"]["L1"]["normalization"][2]["field_name"] = "wrong"
            self.save(path, manifest)
            with self.assertRaisesRegex(ValueError, "misaligned"):
                WideDescriptorStore(path, "L1")

    def test_duplicate_molecule_ids_and_keys_are_rejected_once_at_open(self):
        for duplicate in ("molecule_id", "molecule_index"):
            with self.subTest(duplicate=duplicate), tempfile.TemporaryDirectory() as directory:
                path, manifest, rows, _ = self.fixture(directory)
                rows[2][duplicate] = rows[1][duplicate]
                Path(manifest["libraries"]["L1"]["rows"]).write_text(
                    "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    WideDescriptorStore(path, "L1")

    def test_requested_missing_molecule_or_wrong_id_or_role_is_explicit_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _, _ = self.fixture(directory)
            store = WideDescriptorStore(path, "L1")
            with self.assertRaisesRegex(KeyError, "missing"):
                store.get_batch("TRAIN", [999])
            with self.assertRaisesRegex(ValueError, "IDs"):
                store.get_batch("TRAIN", [8], expected_ids=["val-8"])
            with self.assertRaisesRegex(ValueError, "role"):
                store.get_batch("TRAIN", [8], expected_role="VAL")

    def test_train_only_statistics_and_source_split_roles_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path, manifest, rows, _ = self.fixture(directory)
            manifest["libraries"]["L1"]["fit_role"] = "VAL"
            self.save(path, manifest)
            with self.assertRaisesRegex(ValueError, "TRAIN"):
                WideDescriptorStore(path, "L1")
            manifest["libraries"]["L1"]["fit_role"] = "TRAIN"
            self.save(path, manifest)
            rows[1]["role"] = "VAL"
            Path(manifest["libraries"]["L1"]["rows"]).write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "split/role"):
                WideDescriptorStore(path, "L1")

    def test_constant_scale_is_explicit_not_replaced_with_epsilon(self):
        with tempfile.TemporaryDirectory() as directory:
            path, manifest, _, _ = self.fixture(directory)
            manifest["libraries"]["L1"]["normalization"][2]["scale"] = 0.
            self.save(path, manifest)
            with self.assertRaisesRegex(ValueError, "Nonpositive"):
                WideDescriptorStore(path, "L1")

    def test_raw_incomplete_statistics_can_only_be_read_explicitly_as_raw(self):
        with tempfile.TemporaryDirectory() as directory:
            path, manifest, _, _ = self.fixture(directory)
            del manifest["libraries"]["L1"]["normalization"]
            self.save(path, manifest)
            with self.assertRaisesRegex(ValueError, "not available"):
                WideDescriptorStore(path, "L1")
            store = WideDescriptorStore(path, "L1", require_normalization=False)
            batch = store.get_batch("TRAIN", [2], standardized=False)
            self.assertEqual(batch.values[0, 0], 8.)
            with self.assertRaisesRegex(ValueError, "not available"):
                store.get_batch("TRAIN", [2])

    def test_array_header_shape_and_source_count_mismatch_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path, manifest, _, _ = self.fixture(directory)
            np.save(manifest["libraries"]["L1"]["status"], np.ones((2, 3), dtype=np.uint8))
            with self.assertRaisesRegex(ValueError, "shape/dtype"):
                WideDescriptorStore(path, "L1")
            np.save(manifest["libraries"]["L1"]["status"], np.ones((3, 3), dtype=np.uint8))
            with Path(manifest["libraries"]["L1"]["rows"]).open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(dict(molecule_id="fourth", molecule_index=55,
                                             split="TRAIN", role="TRAIN", smiles="CCC")) + "\n")
            with self.assertRaisesRegex(ValueError, "row count"):
                WideDescriptorStore(path, "L1")

    def test_missing_source_structure_is_an_explicit_missing_population_row(self):
        with tempfile.TemporaryDirectory() as directory:
            path, manifest, rows, _ = self.fixture(directory)
            rows[1].update(smiles=None, source_error="SOURCE_GRAPH_UNAVAILABLE")
            values = np.load(manifest["libraries"]["L1"]["values"])
            status = np.load(manifest["libraries"]["L1"]["status"])
            values[1], status[1] = np.nan, 0
            np.save(manifest["libraries"]["L1"]["values"], values)
            np.save(manifest["libraries"]["L1"]["status"], status)
            Path(manifest["libraries"]["L1"]["rows"]).write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            store = WideDescriptorStore(path, "L1")
            self.assertEqual(store.rows[1]["source_error"], "SOURCE_GRAPH_UNAVAILABLE")
            self.assertFalse(store.get_batch("TRAIN", [8]).observed_valid.any())
            rows[1]["source_error"] = None
            Path(manifest["libraries"]["L1"]["rows"]).write_text(
                "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid descriptor row"):
                WideDescriptorStore(path, "L1")


if __name__ == "__main__":
    unittest.main()
