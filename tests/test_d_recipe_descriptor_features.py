"""Tiny downstream-export joins; no training, fitting or missing-input policy."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools" / "d_recipe"))
from descriptor_features import (D3_FEATURE_FIELDS, D3_ORDERED_FIELDS, SCHEMA,
                                 DownstreamDescriptorStore, append_member_d3)


class DownstreamFeatureTests(unittest.TestCase):
    def d3_row(self, member_uid, molecule, split, values=None):
        values = list(range(1, 7)) if values is None else values
        return dict(member_uid=member_uid, molecule_id=molecule, source_split=split,
                    D3_ordered_fields=list(D3_ORDERED_FIELDS),
                    D3_raw=dict(zip(D3_ORDERED_FIELDS, values)),
                    D3_status=dict.fromkeys(D3_ORDERED_FIELDS, 1))

    def fixture(self, directory):
        root = Path(directory)
        raw = np.array([[0., 5., 9., np.inf], [0., 6., 9., 0.], [2., 7., 9., 4.]], dtype=np.float64)
        status = np.array([[1, 1, 1, 2], [0, 1, 1, 0], [1, 1, 1, 1]], dtype=np.uint8)
        np.save(root / "values.npy", raw)
        np.save(root / "status.npy", status)
        ids = [dict(molecule_id="mol-A", feature_row=0), dict(molecule_id="mol-B", feature_row=1),
               dict(molecule_id="mol-C", feature_row=2)]
        (root / "unique_ids.jsonl").write_text("".join(json.dumps(row) + "\n" for row in ids), encoding="utf-8")
        members = [dict(member_uid="test:3", molecule_id="mol-C", source_split="TEST"),
                   dict(member_uid="train:a", molecule_id="mol-A", source_split="TRAIN"),
                   dict(member_uid="test:a", molecule_id="mol-A", source_split="TEST"),
                   dict(member_uid="test:b", molecule_id="mol-B", source_split="TEST")]
        # Extra source metadata must not become a reader-wide structures cache.
        for row in members:
            row["ignored_source_metadata"] = {"existing_D20": {"huge_unused_value": 42.}}
        (root / "original_members.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in members), encoding="utf-8")
        library = dict(values=str(root / "values.npy"), status=str(root / "status.npy"),
                       ordered_fields=["zero", "TRAIN_disabled", "constant_downstream", "numeric"],
                       enabled_columns=[2, 0, 3], fit_role="TRAIN", normalization=[
                           dict(field_name="zero", mean=0., std_ddof0=2.), None,
                           dict(field_name="constant_downstream", center=[1.], scale=[4.]),
                           dict(field_name="numeric", mean=0., std_population=1.)])
        document = dict(schema=SCHEMA, molecules=str(root / "unique_ids.jsonl"), libraries={"L1": library},
                        membership_reference=dict(path=str(root / "original_members.jsonl"), format="jsonl",
                                                  member_key="member_uid", molecule_key="molecule_id",
                                                  source_split_key="source_split"),
                        source_processing_complete=True, reception_acceptance="pending", current_C1_complete=False)
        path = root / "manifest.json"
        self.save(path, document)
        return path, document, raw

    def save(self, path, value):
        Path(path).write_text(json.dumps(value), encoding="utf-8")

    def test_original_member_join_preserves_requested_id_order_duplicates_and_test_split(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = self.fixture(directory)
            store = DownstreamDescriptorStore(path, "L1", expected_fields=["constant_downstream", "zero", "numeric"])
            batch = store.get_members(["test:3", "train:a", "test:a", "test:3"])
            self.assertEqual(batch.molecule_ids, ("mol-C", "mol-A", "mol-A", "mol-C"))
            self.assertEqual(batch.source_splits, ("TEST", "TRAIN", "TEST", "TEST"))
            self.assertEqual(batch.member_uids, ("test:3", "train:a", "test:a", "test:3"))
            self.assertEqual(batch.fields, ("constant_downstream", "zero", "numeric"))
            np.testing.assert_array_equal(batch.raw_values[0], [9., 2., 4.])
            self.assertEqual(store._member_by_uid["test:a"], ("mol-A", "TEST"))
            self.assertEqual(store.get_molecules(["mol-C"]).source_splits, (None,))
            self.assertFalse(hasattr(store, "_row_by_key"))  # no pretrain split/index route

    def test_true_zero_source_missing_zero_and_numeric_event_are_not_conflated(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = self.fixture(directory)
            batch = DownstreamDescriptorStore(path, "L1").get_members(["test:a", "test:b"], standardized=True)
            self.assertEqual(batch.raw_values[0, 1], 0.)
            self.assertEqual(batch.raw_values[1, 1], 0.)
            self.assertTrue(batch.observed_valid[0, 1])
            self.assertFalse(batch.observed_valid[1, 1])
            self.assertEqual(batch.values[0, 1], 0.)
            self.assertTrue(np.isnan(batch.values[1, 1]))
            self.assertTrue(np.isinf(batch.raw_values[0, 2]))
            self.assertTrue(batch.numeric_events[0, 2])
            self.assertTrue(batch.source_missing[1, 2])
            self.assertTrue(np.isnan(batch.values[0, 2]))

    def test_downstream_constant_fields_keep_train_frozen_order_and_no_artifact_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            path, document, raw = self.fixture(directory)
            manifest_bytes = path.read_bytes()
            store = DownstreamDescriptorStore(path, "L1")
            batch = store.get_molecules(["mol-A", "mol-B", "mol-C"], standardized=True)
            # This field is constant on every downstream molecule, but was
            # retained by TRAIN and must remain an active feature unchanged.
            self.assertEqual(batch.fields[0], "constant_downstream")
            np.testing.assert_array_equal(batch.values[:, 0], [2., 2., 2.])
            batch.values[0, 0] = -999.
            batch.raw_values[0, 0] = -888.
            np.testing.assert_array_equal(np.load(document["libraries"]["L1"]["values"]), raw)
            self.assertEqual(path.read_bytes(), manifest_bytes)
            self.assertFalse(store._values.flags.writeable)
            self.assertEqual(store.reception_acceptance, "pending")
            self.assertFalse(store.current_C1_complete)

    def test_missing_member_or_molecule_and_changed_field_order_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = self.fixture(directory)
            store = DownstreamDescriptorStore(path, "L1")
            with self.assertRaisesRegex(KeyError, "membership ID missing"):
                store.get_members(["unknown"])
            with self.assertRaisesRegex(KeyError, "exported molecule missing"):
                store.get_molecules(["not-exported"])
            with self.assertRaisesRegex(ValueError, "TRAIN-frozen field order"):
                DownstreamDescriptorStore(path, "L1", expected_fields=["zero", "constant_downstream", "numeric"])

    def test_standardization_cannot_fit_test_parameters_or_silently_replace_zero_scale(self):
        with tempfile.TemporaryDirectory() as directory:
            path, document, _ = self.fixture(directory)
            document["libraries"]["L1"]["fit_role"] = "TEST"
            self.save(path, document)
            with self.assertRaisesRegex(ValueError, "TRAIN-frozen"):
                DownstreamDescriptorStore(path, "L1")
            document["libraries"]["L1"]["fit_role"] = "TRAIN"
            document["libraries"]["L1"]["normalization"][2]["scale"] = [0.]
            self.save(path, document)
            store = DownstreamDescriptorStore(path, "L1")
            self.assertEqual(store.get_molecules(["mol-A"]).raw_values[0, 0], 9.)
            with self.assertRaisesRegex(ValueError, "frozen TRAIN affine scale"):
                store.get_molecules(["mol-A"], standardized=True)

    def test_dataset_namespace_preserves_same_record_id_without_renaming_original_ids(self):
        with tempfile.TemporaryDirectory() as directory:
            path, document, _ = self.fixture(directory)
            reference = document["membership_reference"]
            reference.update(dataset_key="dataset", member_key="record_id")
            members = [dict(dataset="set-A", record_id="42", molecule_id="mol-A", source_split="TRAIN"),
                       dict(dataset="set-B", record_id="42", molecule_id="mol-C", source_split="TEST")]
            Path(reference["path"]).write_text("".join(json.dumps(row) + "\n" for row in members), encoding="utf-8")
            self.save(path, document)
            store = DownstreamDescriptorStore(path, "L1")
            requested = [("set-B", "42"), ("set-A", "42")]
            batch = store.get_members(requested)
            self.assertEqual(batch.member_uids, tuple(requested))
            self.assertEqual(batch.molecule_ids, ("mol-C", "mol-A"))
            self.assertEqual(batch.source_splits, ("TEST", "TRAIN"))
            np.testing.assert_array_equal(batch.raw_values[0], [9., 2., 4.])
            self.assertEqual(set(store._member_by_uid), {("set-A", "42"), ("set-B", "42")})
            with self.assertRaisesRegex(ValueError, "requires \\(dataset, record_id\\) tuples"):
                store.get_members(["42"])
            # Contradictory bindings remain invalid within the same dataset.
            members.append(dict(dataset="set-A", record_id="42", molecule_id="mol-B", source_split="TEST"))
            Path(reference["path"]).write_text("".join(json.dumps(row) + "\n" for row in members), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Ambiguous original downstream membership ID"):
                DownstreamDescriptorStore(path, "L1")

    def test_append_d3_keeps_per_member_geometry_repeat_order_and_source_masks(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = self.fixture(directory)
            batch = DownstreamDescriptorStore(path, "L1").get_members(["test:a", "train:a", "test:a"])
            first = self.d3_row("test:a", "mol-A", "TEST", [0., None, np.inf, 4., 5., None])
            first["D3_status"].update(PMI2=0, PMI3=2, SASA_total_A2=2)
            first["D3_raw"]["SASA_atom_A2"] = [1., 2.]  # never aggregated/appended
            second = self.d3_row("train:a", "mol-A", "TRAIN", [7., 8., 9., 10., 11., 12.])
            joined = append_member_d3(batch, [second, first, first])
            self.assertEqual(joined.member_uids, batch.member_uids)
            self.assertEqual(joined.fields, batch.fields + D3_FEATURE_FIELDS)
            np.testing.assert_array_equal(joined.raw_values[:, :len(batch.fields)], batch.raw_values)
            np.testing.assert_array_equal(joined.observed_valid[:, :len(batch.fields)], batch.observed_valid)
            np.testing.assert_array_equal(joined.raw_values[0], joined.raw_values[2])
            np.testing.assert_array_equal(joined.raw_values[1, -6:], [7., 8., 9., 10., 11., 12.])
            self.assertEqual(joined.raw_values[0, -6], 0.)
            self.assertTrue(joined.observed_valid[0, -6])
            self.assertTrue(np.isnan(joined.raw_values[0, -5]))
            self.assertTrue(joined.source_missing[0, -5])
            self.assertTrue(np.isinf(joined.raw_values[0, -4]))
            self.assertTrue(joined.numeric_events[0, -4])
            self.assertTrue(np.isnan(joined.raw_values[0, -1]))  # JSON null stays unavailable
            self.assertTrue(joined.numeric_events[0, -1])
            self.assertIsNone(first["D3_raw"]["PMI2"])
            self.assertNotIn("D3.SASA_atom_A2", joined.fields)
            with self.assertRaisesRegex(ValueError, "already present"):
                append_member_d3(joined, [first, second])

    def test_append_d3_tuple_members_join_exact_dataset_record_and_reject_id_split_mismatch(self):
        from copy import deepcopy
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = self.fixture(directory)
            batch = DownstreamDescriptorStore(path, "L1").get_members(["test:a", "train:a"])
            batch = replace(batch, member_uids=(("A", "42"), ("B", "42")))
            first = self.d3_row("unused-same-bare-id", "mol-A", "TEST")
            first.update(dataset="A", record_id="42")
            second = self.d3_row("unused-same-bare-id", "mol-A", "TRAIN", [10.] * 6)
            second.update(dataset="B", record_id="42")
            joined = append_member_d3(batch, [second, first])
            self.assertEqual(joined.member_uids, (("A", "42"), ("B", "42")))
            np.testing.assert_array_equal(joined.raw_values[:, -6], [1., 10.])
            for key, wrong in (("molecule_id", "mol-C"), ("source_split", "TRAIN")):
                altered = deepcopy(first)
                altered[key] = wrong
                with self.subTest(key=key), self.assertRaisesRegex(ValueError, "molecule/split"):
                    append_member_d3(batch, [altered, second])
            wrong_id = deepcopy(first)
            wrong_id["record_id"] = "43"
            with self.assertRaisesRegex(KeyError, "D3 member missing"):
                append_member_d3(batch, [wrong_id, second])

    def test_append_d3_standardization_is_original_train_f64_affine_without_clipping(self):
        from copy import deepcopy
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = self.fixture(directory)
            batch = DownstreamDescriptorStore(path, "L1").get_members(["test:a"], standardized=True)
            member = self.d3_row("test:a", "mol-A", "TEST", [1e8 + .125, 3., None, 50., 7., 9.])
            member["D3_status"]["PMI3"] = 0
            parameters = {name: dict(fit_role="TRAIN", center=[1.], scale=[2.]) for name in D3_FEATURE_FIELDS}
            parameters["D3.PMI1"].update(center=[1e8], scale=[.25])
            before = deepcopy(parameters)
            joined = append_member_d3(batch, [member], standardized=True, normalization=parameters)
            self.assertEqual(joined.raw_values[0, -6], 1e8 + .125)
            self.assertEqual(joined.values[0, -6], .5)  # F64 subtraction before model conversion
            self.assertEqual(joined.values[0, -3], 24.5)  # no +/-6 loss clipping in direct features
            self.assertTrue(np.isnan(joined.values[0, -4]))
            np.testing.assert_array_equal(joined.values[:, :len(batch.fields)], batch.values)
            self.assertEqual(parameters, before)
            with self.assertRaisesRegex(ValueError, "Explicit original six-field TRAIN"):
                append_member_d3(batch, [member], standardized=True)
            parameters["D3.PMI1"]["element_reference"] = {"basis": [1], "coefficients": [1.]}
            with self.assertRaisesRegex(ValueError, "not A1 residual"):
                append_member_d3(batch, [member], standardized=True, normalization=parameters)

    def test_append_d3_development_namespace_uses_declared_original_member_uid_key(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = self.fixture(directory)
            batch = DownstreamDescriptorStore(path, "L1").get_members(["test:a", "train:a"])
            batch = replace(batch, member_uids=(("qm9", "test:a"), ("qm9", "train:a")))
            first = self.d3_row("test:a", "mol-A", "TEST")
            second = self.d3_row("train:a", "mol-A", "TRAIN", [8.] * 6)
            first.update(dataset="qm9", record_id="unrelated-original-record")
            second.update(dataset="qm9", record_id="unrelated-original-record")
            with self.assertRaisesRegex(KeyError, "D3 member missing"):
                append_member_d3(batch, [first, second])
            joined = append_member_d3(batch, [second, first], tuple_member_key="member_uid")
            self.assertEqual(joined.member_uids, batch.member_uids)
            np.testing.assert_array_equal(joined.raw_values[:, -6], [1., 8.])

    def test_append_d3_never_selects_geometry_from_only_molecule_or_wrong_field_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _, _ = self.fixture(directory)
            store = DownstreamDescriptorStore(path, "L1")
            member = self.d3_row("test:a", "mol-A", "TEST")
            with self.assertRaisesRegex(ValueError, "explicit original member IDs"):
                append_member_d3(store.get_molecules(["mol-A"]), [member])
            member["D3_ordered_fields"][0:2] = ["PMI2", "PMI1"]
            with self.assertRaisesRegex(ValueError, "fixed six molecular scalars"):
                append_member_d3(store.get_members(["test:a"]), [member])


if __name__ == "__main__":
    unittest.main()
