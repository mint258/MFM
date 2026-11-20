"""Original benchmark structure metadata only; no peer writes or target access."""
import copy
import unittest

from .prepare_benchmark import (D20_NAMES, build_rows, canonical_d20, frozen_tasks,
                                sealed_geometry)


class BenchmarkPreparationTests(unittest.TestCase):
    def test_candidate_roster_or_deferred_task_cannot_be_called_frozen(self):
        proof = {"deferred_registry_full_inventory_verified": True, "deferred_endpoint_count": 5}
        roster = {"status": "FROZEN", "final_task_roster": True,
                  "tasks": [{"dataset": "A", "source_task": "original.csv"}]}
        self.assertEqual(frozen_tasks(roster, "FROZEN", proof, lambda tasks: tasks), [("A", "original.csv")])
        with self.assertRaisesRegex(ValueError, "final frozen"):
            frozen_tasks(dict(roster, final_task_roster=False), "FROZEN", proof, lambda tasks: tasks)
        with self.assertRaisesRegex(ValueError, "deferred"):
            frozen_tasks(roster, "FROZEN", proof, lambda tasks: [])

    def test_canonical_d20_retains_native_zero_mask_and_marks_graph_policy_difference(self):
        feature = {"model_smiles": "C", "features": [float(i) for i in range(26)], "valid_mask": [True] * 26}
        feature["valid_mask"][2] = False
        values, reason = canonical_d20(feature, "C", lambda smiles: True)
        self.assertEqual(values[D20_NAMES[0]], 0.0)
        self.assertIsNone(values[D20_NAMES[2]])
        self.assertIsNone(reason)
        values, reason = canonical_d20(feature, "C", lambda smiles: False)
        self.assertTrue(all(value is None for value in values.values()))
        self.assertIn("INPUT_POLICY_NOT_EQUIVALENT", reason)

    def test_sealed_source_is_required_without_opening_or_copying_database(self):
        scope = {"queue": "/shared/new.sqlite", "reused_source_queue": "/shared/original.sqlite"}
        access = {queue: {"immutable": True, "cross_node_read_allowed": True} for queue in scope.values()}
        self.assertEqual(sealed_geometry(scope, access), "/shared/original.sqlite")
        access[scope["queue"]]["immutable"] = False
        with self.assertRaisesRegex(ValueError, "not sealed"):
            sealed_geometry(scope, access)

    def test_existing_shared_molecule_reuses_only_2d_preserving_original_record_and_split(self):
        source_rows = [{"dataset": "A", "record_id": rid, "source_file": "original.csv", "model_smiles": "C",
                        "official_split": split, "structure_store": "/old/rows.parquet",
                        "model_atom_to_source": [0], "retained": True}
                       for rid, split in (("original-train", "TRAIN"), ("original-test", "TEST"))]
        features = [{"dataset": "A", "record_id": row["record_id"], "model_smiles": "C",
                     "native_shared_molecule_id": "existing-shared-molecule", "features": [0.] * 26,
                     "valid_mask": [True] * 26} for row in source_rows]
        before = copy.deepcopy(source_rows)
        inputs, members, unresolved = build_rows(source_rows, features, allowed_keys={"A::original.csv"},
            canonical_key=lambda dataset, source: dataset + "::" + source, graph_equivalent=lambda smiles: True,
            sources={"sealed_queue": "/old/q.sqlite", "C1": "/old/c1.json", "geometry_scope": "/old/scope.json", "roster": "/old/frozen.json"})
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]["molecule_id"], "existing-shared-molecule")
        self.assertEqual([row["record_id"] for row in members], ["original-train", "original-test"])
        self.assertEqual([row["source_split"] for row in members], ["TRAIN", "TEST"])
        self.assertNotEqual(members[0]["D3_geometry_reference"], members[1]["D3_geometry_reference"])
        self.assertEqual(source_rows, before)
        self.assertEqual(unresolved, [])

    def test_missing_canonical_feature_or_cv_binding_is_unresolved_not_all_na_delivery(self):
        row = {"dataset": "A", "record_id": "original", "source_file": "original.csv",
               "model_smiles": "C", "official_split": None, "structure_store": "/old/rows.parquet"}
        inputs, members, unresolved = build_rows([row], [], allowed_keys={"A::original.csv"},
            canonical_key=lambda dataset, source: dataset + "::" + source, graph_equivalent=lambda smiles: True,
            sources={"sealed_queue": "/old/q.sqlite", "C1": "/old/c1.json", "geometry_scope": "/old/scope.json", "roster": "/old/frozen.json"})
        self.assertEqual(inputs[0]["molecule_id"], "original")
        self.assertTrue(all(value is None for value in inputs[0]["existing_D20"].values()))
        self.assertIsNone(members[0]["source_split"])
        self.assertEqual(unresolved[0]["split_binding"], "EXTERNAL_FROZEN_CV_BINDING_REQUIRED")
        self.assertEqual(unresolved[0]["canonical_D20_error"], "CANONICAL_C1_D20_SOURCE_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
