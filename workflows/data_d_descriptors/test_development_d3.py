"""New member routing/checkpoint/mask logic only; scientific routines are fakes."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import numpy as np

from . import development_d3 as production


def member(index=0, store="/original/store.json"):
    return {"dataset": "qm9", "member_uid": "original:" + str(index), "member_index": index,
        "molecule_id": "existing-shared-mid", "source_split": "test" if index % 2 else "train",
        "D3_geometry_reference": {"dataset": "qm9", "member_uid": "original:" + str(index),
            "member_index": index, "native_n_atoms": 2, "store": store,
            "source_frame": {"own_smiles": "physical-member-graph:" + str(index)}}}


def geometry(store, dataset, index):
    return {"member_uid": "original:" + str(index), "atomic_numbers": np.array([6, 8]),
        "coordinates_A": np.array([[0., 0., 0.], [1., 0., 0.]], dtype=np.float64),
        "source_atom_ids": [0, 1], "physical_source": "/original/native.bin", "physical_offset": 8 + 100 * index}


def numerical_result():
    return {"raw_values": np.array([0., np.nan, np.inf, 3., 4., 5.], dtype=np.float64),
        "status": np.array([1, 0, 2, 1, 1, 1], dtype=np.uint8),
        "work_atom_to_native_source": [0, 1], "atomic_SASA_source_values": [0., None],
        "geometry_policy": "ORIGINAL_NATIVE_GEOMETRY", "issues": ["original-source-issue"]}


def fake_d3(*args, **kwargs):
    return numerical_result()


def graph(frame):
    return frame["source_frame"]["own_smiles"]


def local_publish(path, value, config):
    path = Path(path)
    pending = Path(str(path) + ".partial")
    pending.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
    os.replace(pending, path)


def fixture(root, count):
    native = root / "native.json"
    native.write_text("{}", encoding="utf-8")
    peer = root / "peer"
    adapter = peer / "workflows/benchmark_data/downstream_science.py"
    adapter.parent.mkdir(parents=True)
    adapter.write_text("# source reference only; never imported by these tests\n", encoding="utf-8")
    structures, members = root / "input_rows.jsonl", root / "source_members.jsonl"
    canonical = dict.fromkeys(production.D20_NAMES)
    canonical[production.D20_NAMES[0]] = 0.
    structures.write_text(json.dumps({"molecule_id": "existing-shared-mid", "existing_D20": canonical}) + "\n", encoding="utf-8")
    members.write_text("".join(json.dumps(member(i, str(native))) + "\n" for i in range(count)), encoding="utf-8")
    source = root / "source_manifest.json"
    source.write_text(json.dumps({"status": "SOURCE_READY", "input_rows": str(structures),
        "membership_reference": {"path": str(members), "format": "jsonl", "dataset_key": "dataset",
            "member_key": "member_uid", "molecule_key": "molecule_id", "source_split_key": "source_split"},
        "unique_molecules": 1, "retained_members": count,
        "source_references": {"store": production.reference(native)}}), encoding="utf-8")
    return {"source_manifest": str(source), "recipe_root": str(root / "recipe"), "peer_root": str(peer),
        "output": str(root / "own_output"), "peak_bytes": 36706053853,
        "hydrogen_policy": "native_only", "chunk_rows": 256}


class DevelopmentD3Tests(unittest.TestCase):
    def test_default_backend_is_loaded_before_member_scalar_context_and_reused_when_closed(self):
        from rdkit.Chem import Lipinski
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            config = fixture(Path(directory), 1)
            original, events = Lipinski.NumHAcceptors, []
            def load():
                self.assertIs(Lipinski.NumHAcceptors, original)
                events.append("original_backend_loaded")
            def calculate(*args, **kwargs):
                self.assertEqual(events, ["original_backend_loaded"])
                events.append("member")
                return numerical_result()
            backend = SimpleNamespace(load=Mock(side_effect=load), geometry_descriptors=object())
            with patch.object(production, "require_cpu"), patch.object(production, "guard"), \
                    patch.object(production, "publish", side_effect=local_publish), \
                    patch.object(production, "_peer_module", return_value=backend), \
                    patch.dict(os.environ, SLURM_JOB_ID="unit-fixture"):
                options = dict(store_factory=Mock(return_value=Mock()), geometry_reader=geometry,
                    smiles_reader=graph, d3_reader=calculate)
                production.produce(config, **options)
                production.produce(config, **options)
            backend.load.assert_called_once()
            self.assertEqual(events, ["original_backend_loaded", "member"])

    def test_hydrogen_policy_has_no_default_and_rejects_unknown_before_source_access(self):
        for config in ({}, {"hydrogen_policy": "choose_for_me"}):
            with self.assertRaisesRegex(ValueError, "EXPLICIT.*POLICY"):
                production.produce(config)
        self.assertEqual(production.policy({"hydrogen_policy": "B6_fixed_native_H"}), "B6_fixed_native_H")

    def test_dataset_scope_selects_complete_original_dataset_in_original_member_order(self):
        original = [member(i) for i in range(4)]
        for row in original[::2]:
            row["dataset"] = row["D3_geometry_reference"]["dataset"] = "expansionrx"
        before = copy.deepcopy(original)
        scope, selected = production.select_datasets(original, ["qm9"])
        self.assertEqual(scope, ["qm9"])
        self.assertEqual([r["member_uid"] for r in selected], ["original:1", "original:3"])
        self.assertEqual([r["source_member_row"] for r in selected], [1, 3])
        for index, row in zip((1, 3), selected):
            self.assertEqual(row, dict(original[index], source_member_row=index))
        self.assertEqual(original, before)
        self.assertEqual(len(production.select_datasets(original)[1]), 4)
        for invalid in (["unknown"], ["qm9", "qm9"], "qm9", []):
            with self.assertRaisesRegex(ValueError, "dataset scope"):
                production.select_datasets(original, invalid)
        with self.assertRaisesRegex(ValueError, "dataset scope"):
            production.select_datasets([member()], ["expansionrx"])

    def test_member_uses_own_physical_graph_and_original_d20_zero_missing_shell(self):
        canonical = dict.fromkeys(production.D20_NAMES)
        canonical[production.D20_NAMES[0]] = 0.
        before = copy.deepcopy(canonical)
        capture = Mock(side_effect=fake_d3)
        store = Mock()
        for policy in production.POLICIES:
            result = production.work_member(member(7), canonical, store, hydrogen_policy=policy,
                calculator="original-adapter", smiles_reader=graph, geometry_reader=geometry, d3_reader=capture)
            args, kwargs = capture.call_args
            self.assertEqual(args[0], "physical-member-graph:7")
            self.assertIs(args[3], canonical)
            self.assertEqual(kwargs["hydrogen_policy"], policy)
            self.assertEqual(result[4]["source_split"], "test")
            self.assertEqual(result[4]["work_atom_to_native_source"], [0, 1])
        self.assertEqual(canonical, before)
        store.get.assert_not_called()

    def test_known_unavailable_is_missing_but_io_import_and_uid_errors_propagate(self):
        missing = Mock(side_effect=production.UnavailableD3("NATIVE_EXPLICIT_H_UNAVAILABLE"))
        result = production.work_member(member(), dict.fromkeys(production.D20_NAMES), object(),
            hydrogen_policy="native_only", calculator=object(), smiles_reader=graph,
            geometry_reader=geometry, d3_reader=missing)
        self.assertEqual(result[1].tolist(), [0] * 6)
        self.assertTrue(np.isnan(result[0]).all())
        self.assertEqual(result[3].tolist(), [0, 0])
        self.assertEqual(result[4]["source_missing_reason"], "NATIVE_EXPLICIT_H_UNAVAILABLE")
        for exception in (OSError("read failed"), ImportError("original adapter unavailable")):
            with self.assertRaises(type(exception)):
                production.work_member(member(), {}, object(), hydrogen_policy="native_only", calculator=object(),
                    geometry_reader=geometry, smiles_reader=Mock(side_effect=exception))
        bad_geometry = geometry(None, "qm9", 0)
        bad_geometry["member_uid"] = "different-source-member"
        with self.assertRaisesRegex(ValueError, "UID differs"):
            production.work_member(member(), {}, object(), hydrogen_policy="native_only", calculator=object(),
                geometry_reader=Mock(return_value=bad_geometry), smiles_reader=graph)

    def test_atomic_sasa_keeps_true_zero_missing_numeric_events_and_never_aggregates(self):
        raw, status = production.atomic_values([0., None, np.inf, np.nan, 1e40], 5)
        self.assertEqual(status.tolist(), [1, 0, 2, 2, 2])
        self.assertEqual(raw.dtype, np.float64)
        self.assertEqual(raw[0], 0.)
        self.assertTrue(np.isinf(raw[2]))
        with self.assertRaisesRegex(ValueError, "length differs"):
            production.atomic_values([1.], 2)
        result = production.work_member(member(), dict.fromkeys(production.D20_NAMES), object(),
            hydrogen_policy="native_only", calculator=object(), geometry_reader=geometry,
            smiles_reader=graph, d3_reader=fake_d3)
        self.assertEqual(len(result[0]), 6)
        self.assertEqual(len(result[2]), 2)
        self.assertFalse(result[4]["atomic_SASA_in_molecular_vector"])

    def test_cursor_is_bound_to_policy_and_contiguous_closed_parts(self):
        identity = {"hydrogen_policy": "native_only"}
        cursor = {"identity": identity, "next_member": 256,
                  "parts": [{"part_index": 0, "start": 0, "stop": 256}]}
        self.assertEqual(production.check_cursor(cursor, identity, 257, 256), 256)
        with self.assertRaisesRegex(ValueError, "identity changed"):
            production.check_cursor(cursor, {"hydrogen_policy": "B6_fixed_native_H"}, 257, 256)
        cursor["parts"][0]["start"] = 1
        with self.assertRaisesRegex(ValueError, "not contiguous"):
            production.check_cursor(cursor, identity, 257, 256)

    def test_scoped_production_identity_reports_full_source_count_without_visiting_other_dataset(self):
        with tempfile.TemporaryDirectory() as directory:
            config = fixture(Path(directory), 2)
            source = production.read_json(config["source_manifest"])
            path = Path(source["membership_reference"]["path"])
            original = list(production.rows(path))
            original[0]["dataset"] = original[0]["D3_geometry_reference"]["dataset"] = "expansionrx"
            path.write_text("".join(json.dumps(row) + "\n" for row in original), encoding="utf-8")
            config["datasets"] = ["qm9"]
            calculation = Mock(side_effect=fake_d3)
            with patch.object(production, "require_cpu"), patch.object(production, "guard"), \
                    patch.object(production, "publish", side_effect=local_publish), \
                    patch.dict(os.environ, {"SLURM_JOB_ID": "unit-fixture"}):
                options = dict(store_factory=Mock(return_value=Mock()), calculator=object(),
                               geometry_reader=geometry, smiles_reader=graph, d3_reader=calculation)
                report = production.produce(config, **options)
                calculation.assert_called_once()
                self.assertEqual(calculation.call_args.args[0], "physical-member-graph:1")
                self.assertEqual(report["dataset_scope"], report["identity"]["dataset_scope"])
                self.assertEqual(report["source_member_count"], 2)
                self.assertEqual(report["member_count"], 1)
                self.assertFalse(report["complete_source_population"])
                with self.assertRaisesRegex(ValueError, "source/policy changed"):
                    production.produce(dict(config, datasets=["qm9", "expansionrx"]), **options)

    def test_resume_skips_closed_members_and_preserves_raw_arrays_and_own_partial_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            config = fixture(Path(directory), 257)
            factory, calls = Mock(return_value=Mock()), []
            def interrupted(smiles, *args, **kwargs):
                calls.append(smiles)
                if len(calls) == 257:
                    raise OSError("interrupt only the unclosed second part")
                return numerical_result()
            with patch.object(production, "require_cpu"), patch.object(production, "guard"), \
                    patch.object(production, "publish", side_effect=local_publish), \
                    patch.dict(os.environ, {"SLURM_JOB_ID": "unit-fixture"}):
                options = dict(store_factory=factory, calculator=object(), geometry_reader=geometry, smiles_reader=graph)
                with self.assertRaisesRegex(OSError, "unclosed second part"):
                    production.produce(config, d3_reader=interrupted, **options)
                output = Path(config["output"])
                cursor = production.read_json(output / "cursor.json")
                self.assertEqual(cursor["next_member"], 256)
                first = Path(cursor["parts"][0]["values"])
                unchanged = first.stat().st_mtime_ns
                unrelated = output / "not_owned_by_producer.bin"
                unrelated.write_bytes(b"preserved")
                (output / "part_000001_values.npy.partial").write_bytes(b"uncommitted")
                resumed = Mock(side_effect=fake_d3)
                report = production.produce(config, d3_reader=resumed, **options)
                self.assertEqual(resumed.call_count, 1)
                self.assertEqual(first.stat().st_mtime_ns, unchanged)
                self.assertEqual(unrelated.read_bytes(), b"preserved")
                self.assertEqual(report["member_count"], 257)
                self.assertEqual(report["dataset_scope"], ["qm9"])
                self.assertEqual(report["source_member_count"], 257)
                raw = np.load(first, allow_pickle=False)
                self.assertTrue(np.isinf(raw[0, 2]))
                self.assertEqual(np.load(cursor["parts"][0]["status"])[0].tolist(), [1, 0, 2, 1, 1, 1])
                records = list(production.rows(report["membership_reference"]["path"]))
                self.assertEqual(records[-1]["member_uid"], "original:256")
                self.assertEqual(records[-1]["source_smiles"], "physical-member-graph:256")
                self.assertEqual(records[0]["D3_status"]["PMI3"], 2)
                self.assertFalse(report["canonical_D20_replaced"])
                factory.assert_any_call(str(Path(directory) / "native.json"), verify_digests=False)
                self.assertEqual(production.produce(config, d3_reader=Mock(side_effect=AssertionError), **options), report)
                with self.assertRaisesRegex(ValueError, "source/policy changed"):
                    production.produce(dict(config, hydrogen_policy="B6_fixed_native_H"), **options)

    def test_output_allowance_is_enforced_before_writing_a_new_part(self):
        with tempfile.TemporaryDirectory() as directory:
            result = production.work_member(member(), dict.fromkeys(production.D20_NAMES), object(),
                hydrogen_policy="native_only", calculator=object(), geometry_reader=geometry,
                smiles_reader=graph, d3_reader=fake_d3)
            with patch.object(production, "guard") as physical_guard:
                with self.assertRaisesRegex(ValueError, "EXCEEDS_EXISTING_ALLOWANCE"):
                    production.write_part(Path(directory), 0, 0, [result], {"parts": []}, {"output_budget_bytes": 1024})
                physical_guard.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
