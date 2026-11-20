"""Tiny metadata/SMILES/cache fixtures; native target access is forbidden."""
import copy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from .prepare_development import (D20_NAMES, build_rows, development_datasets,
                                  selected_metadata)


def member(uid="u1", mid="EXISTING-FULL-INCHIKEY", index=1, role="train"):
    return {"member_uid": uid, "molecule_id": mid, "member_index": index,
            "dataset": "qm9", "source_split": role, "native_n_atoms": 5}


def frame(uid="u1", ordinal=1):
    return {"source_ordinal": ordinal, "dataset": "qm9", "member_uid": uid,
            "source_frame": {"path": "/existing/" + uid + ".xyz", "source_units": "angstrom"},
            "geometry_artifact_ref": {"kind": "original", "record": uid}}


class DevelopmentPreparationTests(unittest.TestCase):
    def test_seven_tasks_select_only_the_existing_two_datasets(self):
        scored = ["e" + str(i) for i in range(3)] + ["q" + str(i) for i in range(4)]
        panel = {"tasks": [{"task_id": task, "dataset_id": "expansionrx" if task[0] == "e" else "qm9"}
                           for task in scored] + [{"task_id": "cyp.report", "dataset_id": "cyp_isoform"}]}
        self.assertEqual(development_datasets({"scored_tasks": scored}, panel), ["expansionrx", "qm9"])
        with self.assertRaisesRegex(ValueError, "seven-task"):
            development_datasets({"scored_tasks": scored[:-1]}, panel)

    def test_geometry_metadata_only_excludes_unready_without_getting_targets(self):
        store = Mock()
        store.get.side_effect = AssertionError("native targets cannot be opened")
        store.native_geometry_metadata.side_effect = lambda dataset, index: {
            "member_uid": "u" + str(index), "native_n_atoms": 5, "geometry_ready": index == 1}
        view = SimpleNamespace(membership={"roles": {
            "train": [{"member_uid": "u1", "member_index": 1, "full_inchikey": "already-bound-1"}],
            "train_inner_validation": [{"member_uid": "u2", "member_index": 2, "full_inchikey": "already-bound-2"}]}})
        selected, excluded = selected_metadata(store, {"qm9": view})
        self.assertEqual(selected[0]["member_uid"], "u1")
        self.assertEqual(excluded[0]["member_uid"], "u2")
        self.assertEqual(excluded[0]["reason"], "P_NATIVE_GEOMETRY_NOT_READY")
        store.get.assert_not_called()

    def test_duplicate_molecule_shares_only_2d_row_not_member_geometry_or_split(self):
        first, second = member(), member("u2", index=2, role="train_inner_validation")
        frames = {("qm9", "u1"): frame(), ("qm9", "u2"): frame("u2", 2)}
        cache = Mock()
        cache.get.return_value = {name: None for name in D20_NAMES}
        cache.get.return_value["ExactMolWt"] = 0.0
        smiles = Mock(return_value="C")
        original = copy.deepcopy(frames)
        inputs, mapping, unresolved = build_rows([first, second], frames, smiles_reader=smiles,
                                                  cache=cache, store_reference="/existing/native.json")
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]["molecule_id"], first["molecule_id"])
        self.assertEqual(inputs[0]["existing_D20"]["ExactMolWt"], 0.0)
        self.assertIsNone(inputs[0]["existing_D20"]["TPSA"])
        self.assertEqual(len(mapping), 2)
        self.assertNotEqual(mapping[0]["D3_geometry_reference"], mapping[1]["D3_geometry_reference"])
        self.assertEqual(mapping[1]["source_split"], "train_inner_validation")
        self.assertEqual(frames, original)
        self.assertEqual(unresolved, [])
        self.assertEqual(smiles.call_count, 1)

    def test_missing_graph_or_canonical_binding_remains_explicitly_unresolved(self):
        frames = {("qm9", "u1"): frame()}
        cache = Mock()
        cache.get.return_value = None
        inputs, mapping, unresolved = build_rows([member()], frames, smiles_reader=lambda frame: None,
                                                  cache=cache, store_reference="/existing/native.json")
        self.assertIsNone(inputs[0]["smiles"])
        self.assertEqual(inputs[0]["source_error"], "ORIGINAL_SOURCE_SMILES_UNAVAILABLE")
        self.assertEqual(set(inputs[0]["existing_D20"]), set(D20_NAMES))
        self.assertTrue(all(value is None for value in inputs[0]["existing_D20"].values()))
        self.assertEqual(len(mapping), 1)
        self.assertEqual(len(unresolved), 1)
        cache.get.assert_not_called()
        with self.assertRaises(OSError):
            build_rows([member()], frames, smiles_reader=Mock(side_effect=OSError("source read failed")),
                       cache=cache, store_reference="/existing/native.json")

    def test_duplicate_native_member_is_not_silently_collapsed(self):
        cache = Mock()
        cache.get.return_value = {name: None for name in D20_NAMES}
        with self.assertRaisesRegex(ValueError, "Duplicate original"):
            build_rows([member(), member()], {("qm9", "u1"): frame()}, smiles_reader=lambda frame: "C",
                       cache=cache, store_reference="/existing/native.json")


if __name__ == "__main__":
    unittest.main()
