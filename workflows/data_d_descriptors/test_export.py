"""New export contracts with tiny fake calculators; no chemistry or labels."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from .export import (D20_NAMES, DISABLED_D20, commit_part, compute_chunk, copy_native_d20,
                     frozen_library, main_reuse, native_d20_library, run, unique_sources, validate_source)


def source(mid="a", smiles="C", binding=None):
    return {"molecule_id": mid, "smiles": smiles,
            "source_binding": binding or {"dataset": "original", "record_id": mid},
            "existing_D20": {name: None for name in D20_NAMES}}


def result(values, valid=None, bad=None):
    valid = np.isfinite(values) if valid is None else valid
    bad = np.zeros(len(values), dtype=bool) if bad is None else bad
    return values, valid, bad, [], 0.0, 0.0


class ExportTests(unittest.TestCase):
    def write_rows(self, root, rows):
        path = Path(root) / "source.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        return path

    def test_unique_id_is_computed_once_and_conflicting_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            a, b = source(), source("b", "CC")
            indexed = unique_sources(self.write_rows(root, [a, a, b]), need_d20=True)
            self.assertEqual([row["molecule_id"] for row in indexed], ["a", "b"])
            self.assertEqual([row["feature_row"] for row in indexed], [0, 1])
            with self.assertRaisesRegex(ValueError, "Conflicting source"):
                unique_sources(self.write_rows(root, [a, dict(a, smiles="CO")]), need_d20=True)

    def test_l1_requires_all_canonical_fields_but_l2_never_cross_maps_them(self):
        row = source()
        row["existing_D20"].pop("MolMR")
        with self.assertRaisesRegex(ValueError, "All 20"):
            validate_source(row, need_d20=True)
        validate_source(row, need_d20=False)
        raw, flags, _ = compute_chunk([row], library="L2", fields=["MolMR"],
                                      calculate=lambda inputs: [result([7.0])])
        self.assertEqual(raw[0, 0], 7)
        self.assertEqual(flags[0, 0], 1)

    def test_raw_reuse_still_overrides_shared_d20_with_canonical_zero_and_missing(self):
        row = source()
        row["existing_D20"].update(ExactMolWt=0.0, TPSA=None)
        calculator = Mock(side_effect=AssertionError("closed raw data must not be recomputed"))
        raw, flags, reused = compute_chunk([row], library="L1", fields=["ExactMolWt", "TPSA", "new"],
            calculate=lambda inputs: [] if not inputs else calculator(inputs),
            reuse=lambda row: (np.array([999., 999., 3.]), np.ones(3, dtype=np.uint8)))
        self.assertEqual(reused, 1)
        np.testing.assert_array_equal(raw, [[0., np.nan, 3.]])
        np.testing.assert_array_equal(flags, [[1, 0, 1]])
        calculator.assert_not_called()

    def test_numeric_event_and_missing_are_not_zero_filled(self):
        raw, flags, _ = compute_chunk([source()], library="L2", fields=["zero", "missing", "overflow"],
            calculate=lambda inputs: [result([0., np.nan, np.inf], [True, False, False], [False, False, True])])
        np.testing.assert_array_equal(flags, [[1, 0, 2]])
        self.assertEqual(raw[0, 0], 0)
        self.assertTrue(np.isnan(raw[0, 1]))
        self.assertTrue(np.isinf(raw[0, 2]))

    def test_fields_versions_enabled_columns_and_parameters_are_frozen_not_refitted(self):
        entry = dict(fit_role="TRAIN", producer_alignment_checked=True, ordered_fields=["new", "filtered"],
                     enabled_columns=[0], normalization=[{"mean": 2., "std_ddof0": 3.}, None],
                     software_versions={"rdkit_version": "2025.9.5"})
        before = copy.deepcopy(entry)
        exported = frozen_library(entry, ["new", "filtered"], entry["software_versions"])
        self.assertEqual(exported["enabled_columns"], [0])
        self.assertEqual(exported["normalization"], entry["normalization"])
        exported["normalization"][0]["mean"] = 999
        self.assertEqual(entry, before)
        with self.assertRaisesRegex(ValueError, "field order"):
            frozen_library(entry, ["filtered", "new"], entry["software_versions"])
        with self.assertRaisesRegex(ValueError, "software versions"):
            frozen_library(entry, ["new", "filtered"], {"rdkit_version": "different"})

    def test_main_reuse_requires_both_existing_id_graph_and_source_binding(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            np.save(root / "values.npy", np.array([[4.0]], dtype=np.float64))
            np.save(root / "status.npy", np.array([[1]], dtype=np.uint8))
            entry = {"values": str(root / "values.npy"), "status": str(root / "status.npy"),
                     "ordered_fields": ["f"]}
            row = source()
            reuse = main_reuse(entry, [row], {"a"})
            self.assertEqual(reuse(row)[0][0], 4)
            self.assertIsNone(reuse(dict(row, smiles="CC")))
            self.assertIsNone(reuse(dict(row, source_binding={"record_id": "other"})))
            self.assertIsNone(reuse(source("not-in-main")))

    def test_closed_part_does_not_write_again_and_failed_flush_is_not_closed(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            values = np.lib.format.open_memmap(root / "values.npy", mode="w+", dtype=np.float64, shape=(1, 1))
            status = np.lib.format.open_memmap(root / "status.npy", mode="w+", dtype=np.uint8, shape=(1, 1))
            checkpoint = {"completed_parts": [], "main_rows_reused": 0}
            args = dict(offset=0, part=0, checkpoint=checkpoint, marker=root / "checkpoint.json", config={}, reused=0)
            with patch("workflows.data_d_descriptors.export.guard"), patch("workflows.data_d_descriptors.export.publish") as publish:
                with patch("workflows.data_d_descriptors.export.sync_arrays", side_effect=OSError("incomplete flush")):
                    with self.assertRaises(OSError):
                        commit_part(values, status, [[2.]], [[1]], **args)
                self.assertEqual(checkpoint["completed_parts"], [])
                publish.assert_not_called()
                self.assertTrue(commit_part(values, status, [[3.]], [[1]], **args))
                self.assertFalse(commit_part(values, status, [[99.]], [[0]], **args))
                self.assertEqual(values[0, 0], 3)
                self.assertEqual(publish.call_count, 1)

    def test_compatible_cache_only_supplies_uncomputed_l1_rows(self):
        row = dict(source(), source_member_uid="qm9:existing", source_ordinal=7)
        cached = Mock()
        cached.get.return_value = {"new": 8., "ExactMolWt": 999.}
        row["existing_D20"]["ExactMolWt"] = 5.
        def fake_calculate(inputs):
            self.assertEqual(inputs[0]["existing_L1"]["new"], 8.)
            self.assertEqual(inputs[0]["existing_D20"]["ExactMolWt"], 5.)
            return [result([8., 5.])]
        raw, _, _ = compute_chunk([row], library="L1", fields=["new", "ExactMolWt"],
                                  calculate=fake_calculate, compatible_cache=cached)
        np.testing.assert_array_equal(raw, [[8., 5.]])
        cached.get.assert_called_once_with("qm9:existing", "C", 7)
        cached.reset_mock()
        compute_chunk([row], library="L2", fields=["new"],
                      calculate=lambda inputs: [result([1.])], compatible_cache=cached)
        cached.get.assert_not_called()

    def test_d20_only_exports_with_one_parent_no_calculator_pool_or_new_statistics(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            row = source()
            row["existing_D20"].update(ExactMolWt=0.0, TPSA=None, BertzCT=float("inf"))
            inputs = self.write_rows(root, [row])
            members = root / "members.jsonl"
            members.write_text(json.dumps({"member_uid": "original", "molecule_id": "a", "source_split": "train"}) + "\n")
            params = {name: {"center": 2., "scale": 3., "fit_role": "TRAIN", "unit": "original-unit"}
                      for name in D20_NAMES if name not in DISABLED_D20}
            path = root / "old_params.json"
            path.write_text(json.dumps(params))
            config = {"input_rows": str(inputs), "output": str(root / "export"), "include_D20": True,
                "native_D20_parameters": str(path), "chunk_rows": 256, "peak_bytes": 8 * 2**20,
                "membership_reference": {"path": str(members), "format": "jsonl", "member_key": "member_uid",
                    "molecule_key": "molecule_id", "source_split_key": "source_split"}}
            # CPU/storage admission is outside this tiny copied-data test.
            # Any accidental chemistry or fitting call fails the test.
            with patch("workflows.data_d_descriptors.export.require_cpu") as cpu, \
                 patch("workflows.data_d_descriptors.export.guard"), \
                 patch("workflows.data_d_descriptors.export.pilot.initialize") as initialize, \
                 patch("workflows.data_d_descriptors.export.cf.ProcessPoolExecutor") as pool, \
                 patch("workflows.data_d_descriptors.produce.summarize_library") as fit, \
                 patch.dict(os.environ, {"SLURM_JOB_ID": "UNIT_FIXTURE_NOT_AN_ACTUAL_JOB"}):
                manifest = run(config)
            cpu.assert_called_once_with(dict(config, workers=1))
            initialize.assert_not_called(); pool.assert_not_called(); fit.assert_not_called()
            spec = manifest["libraries"]["D20"]
            self.assertEqual(spec["ordered_fields"], D20_NAMES)
            self.assertEqual(len(spec["enabled_columns"]), 17)
            self.assertEqual(spec["normalization_source"], str(path.resolve()))
            self.assertEqual(spec["normalization"][0]["unit"], "original-unit")
            raw, status = np.load(spec["values"]), np.load(spec["status"])
            self.assertEqual(raw[0, D20_NAMES.index("ExactMolWt")], 0)
            self.assertEqual(status[0, D20_NAMES.index("ExactMolWt")], 1)
            self.assertEqual(status[0, D20_NAMES.index("TPSA")], 0)
            self.assertEqual(status[0, D20_NAMES.index("BertzCT")], 2)

    def test_l2_only_export_keeps_frozen_fields_when_original_d20_binding_is_unresolved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            row = source()
            del row["existing_D20"]
            row["canonical_D20_source_error"] = "UNRESOLVED_ORIGINAL_D20_BINDING"
            input_rows = self.write_rows(root, [row])
            members, train = root / "members.jsonl", root / "train_manifest.json"
            members.write_text("{}\n")  # export stats this reference, never opens labels
            entry = dict(fit_role="TRAIN", producer_alignment_checked=True, ordered_fields=["new"],
                enabled_columns=[0], normalization=[{"mean": 2., "std_ddof0": 3.}],
                software_versions={"rdkit_version": "fixed", "mordredcommunity_version": "fixed"})
            train.write_text(json.dumps(dict(schema="D_WIDE_DESCRIPTOR_STORE_V1",
                libraries={"L1": {"unusable_D20_binding": True}, "L2": entry})))
            config = dict(train_manifest=str(train), libraries=["L2"], input_rows=str(input_rows),
                membership_reference=dict(path=str(members), format="jsonl", member_key="record_id"),
                output=str(root / "export"), peak_bytes=4 * 2**20, workers=1, chunk_rows=256,
                reuse_main_raw=False, canonical_D20_source_status="UNRESOLVED_CANONICAL_D20_BINDING")
            with patch("workflows.data_d_descriptors.export.require_cpu"), \
                 patch("workflows.data_d_descriptors.export.guard"), \
                 patch("workflows.data_d_descriptors.export.pilot.FIELDS", ["new"]), \
                 patch("workflows.data_d_descriptors.export.pilot.initialize") as initialize, \
                 patch("workflows.data_d_descriptors.export.importlib.metadata.version", return_value="fixed"), \
                 patch("workflows.data_d_descriptors.export.cf.ProcessPoolExecutor") as pool, \
                 patch.dict(os.environ, SLURM_CPUS_PER_TASK="2", SLURM_JOB_ID="UNIT_FIXTURE_NOT_AN_ACTUAL_JOB"):
                pool.return_value.__enter__.return_value.map.side_effect = lambda fn, items, **kw: [result([7.]) for _ in items]
                manifest = run(config)
            initialize.assert_called_once_with("L2")
            self.assertEqual(set(manifest["libraries"]), {"L2"})
            self.assertFalse(manifest["canonical_D20_required"])
            self.assertEqual(manifest["source_canonical_D20_status"], "UNRESOLVED_CANONICAL_D20_BINDING")
            self.assertEqual(manifest["libraries"]["L2"]["normalization"], entry["normalization"])
            np.testing.assert_array_equal(np.load(manifest["libraries"]["L2"]["values"]), [[7.]])

    def test_native_d20_and_wide_sources_have_independent_values_and_parameters(self):
        row = source()
        row["existing_D20"]["ExactMolWt"] = 5.
        params = {name: {"center": 2., "scale": 3., "fit_role": "TRAIN"}
                  for name in D20_NAMES if name not in DISABLED_D20}
        before = copy.deepcopy(params)
        native = native_d20_library(params, "/original/parameters.json")
        copied, _ = copy_native_d20([row])
        wide, _, _ = compute_chunk([row], library="L2", fields=["ExactMolWt"],
                                   calculate=lambda inputs: [result([777.])])
        self.assertEqual(copied[0, D20_NAMES.index("ExactMolWt")], 5.)
        self.assertEqual(wide[0, 0], 777.)
        self.assertEqual(params, before)
        for name in DISABLED_D20:
            self.assertIsNone(native["normalization"][D20_NAMES.index(name)])


if __name__ == "__main__":
    unittest.main()
