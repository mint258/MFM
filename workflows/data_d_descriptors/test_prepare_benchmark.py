"""Target-free scope, canonical values and member geometry tests; no real sources."""
import copy
import unittest

from .prepare_benchmark import (D20_NAMES, D3_NAMES, D20Schema, build_rows,
    canonical_d20, frozen_tasks, geometry_member, scoped_tasks, sealed_geometry, shared_source)


PROOF = {"deferred_registry_full_inventory_verified": True, "deferred_endpoint_count": 5}
SOURCES = {"inventory": "/old/catalog.json", "geometry_scope": "/old/scope.json"}


def fixture(record="original", conformer_id=0):
    return {"source_database": "/old/closed.sqlite", "shared_molecule_id": "existing-shared", "state": "SPRIME_AND_D_READY",
        "model_atom_to_source": [4, 2], "result": {"state": "SPRIME_AND_D_READY", "model_smiles": "CC", "atomic_numbers": [6, 6],
        "D20": {"names": list(D20_NAMES), "values": [float(i) for i in range(20)], "valid_mask": [True] * 20},
        "conformers": [{"conformer_id": conformer_id, "candidate_id": 9,
            "geometry_source": "UFF_Sprime", "coordinates_A": [[0., 0., 0.], [1., 0., 0.]],
            "D3": dict(zip(D3_NAMES, [1., 2., 3., 4., 5., 6.]), SASA_atom_A2=[90., 80.])}]}}


def source_row(record="original", split=None):
    return {"dataset": "A", "record_id": record, "source_file": "original.csv", "model_smiles": "CC",
            "official_split": split, "structure_store": "/old/rows.parquet", "model_atom_to_source": [1, 0]}


def route(record):
    return {"shared_geometry_queue": "/old/closed.sqlite",
            "shared_geometry_dataset": "A", "shared_geometry_record_id": record}


def build(rows, reader):
    return build_rows(rows, reader, allowed_keys={"a::original.csv"},
        canonical_key=lambda dataset, path: dataset.casefold() + "::" + path,
        graph_equivalent=lambda smiles: True, sources=SOURCES)


class BenchmarkPreparationTests(unittest.TestCase):
    def test_final_roster_still_rejects_candidate_or_deferred_tasks(self):
        roster = {"status": "FROZEN", "final_task_roster": True,
                  "tasks": [{"dataset": "A", "source_task": "original.csv"}]}
        self.assertEqual(frozen_tasks(roster, "FROZEN", PROOF, lambda tasks: tasks), [("A", "original.csv")])
        with self.assertRaisesRegex(ValueError, "final frozen"):
            frozen_tasks(dict(roster, final_task_roster=False), "FROZEN", PROOF, lambda tasks: tasks)
        with self.assertRaisesRegex(ValueError, "deferred"):
            frozen_tasks(roster, "FROZEN", PROOF, lambda tasks: [])

    def test_feature_export_accepts_existing_candidate_catalog_without_freezing_endpoints(self):
        document = {"status": "CANDIDATE", "final_task_roster": False}
        catalog = [{"dataset": "A", "endpoint_key": "a::original.csv::endpoint"},
                   {"dataset": "A", "endpoint_key": "a::original.csv::other"},
                   {"dataset": "A", "endpoint_key": "a::deferred.csv::endpoint"}]
        before = copy.deepcopy((document, catalog))
        tasks = scoped_tasks(document, "CANDIDATE", PROOF,
            lambda tasks: [t for t in tasks if t[1] != "deferred.csv"],
            mode="FEATURE_EXPORT_ONLY", catalog_rows=catalog)
        self.assertEqual(tasks, [("A", "original.csv")])
        self.assertEqual((document, catalog), before)
        with self.assertRaisesRegex(ValueError, "scope proof"):
            scoped_tasks(document, "CANDIDATE", {}, lambda tasks: tasks,
                         mode="FEATURE_EXPORT_ONLY", catalog_rows=catalog)

    def test_canonical_d20_keeps_zero_and_missing_and_binds_original_input_policy(self):
        shared = fixture()
        shared["result"]["D20"]["valid_mask"][2] = False
        schema = D20Schema()
        values, reason = canonical_d20(shared, "CC", lambda smiles: True, schema)
        self.assertEqual(values[D20_NAMES[0]], 0.)
        self.assertIsNone(values[D20_NAMES[2]])
        self.assertIsNone(reason)
        self.assertEqual(schema.checked, {"/old/closed.sqlite"})
        values, reason = canonical_d20(shared, "CC", lambda smiles: False, schema)
        self.assertTrue(all(v is None for v in values.values()))
        self.assertIn("INPUT_POLICY_NOT_EQUIVALENT", reason)
        shared["source_database"] = "/different/closed.sqlite"
        shared["result"]["D20"]["names"].reverse()
        with self.assertRaisesRegex(ValueError, "name/order"):
            canonical_d20(shared, "CC", lambda smiles: True, schema)

    def test_actual_geometry_binding_routes_original_dataset_record_and_uses_sealed_sources(self):
        scope = {"queue": "/new/closed.sqlite", "reused_source_queue": "/old/closed.sqlite"}
        access = {q: {"immutable": True, "cross_node_read_allowed": True} for q in scope.values()}
        self.assertEqual(sealed_geometry(scope, access), set(scope.values()))
        calls = []
        class Reader:
            def __init__(self, queue): self.queue = queue
            def get(self, dataset, record_id):
                calls.append((self.queue, dataset, record_id))
                if record_id == "missing": raise KeyError((dataset, record_id))
                return fixture()
        bindings = {("original-group", "original-record"): {
            "shared_geometry_queue": scope["queue"], "shared_geometry_dataset": "source-namespace",
            "shared_geometry_record_id": "source-record"}}
        readers = {}
        _, actual = shared_source("original-group", "original-record", bindings=bindings,
                                 scope=scope, readers=readers, reader_class=Reader)
        self.assertEqual(calls, [(scope["queue"], "source-namespace", "source-record")])
        self.assertEqual(actual, bindings[("original-group", "original-record")])
        missing, _ = shared_source("A", "missing", bindings=bindings, scope=scope, readers=readers, reader_class=Reader)
        self.assertIsNone(missing)
        access[scope["queue"]]["immutable"] = False
        with self.assertRaisesRegex(ValueError, "not sealed"):
            sealed_geometry(scope, access)

    def test_shared_id_only_merges_2d_and_keeps_per_member_actual_conformer_and_atom_reference(self):
        rows = [source_row("train", "TRAIN"), source_row("test", "TEST")]
        before = copy.deepcopy(rows)
        inputs, members, unresolved = build(rows,
            lambda dataset, record: (fixture(record, conformer_id=0 if record == "train" else 2), route(record)))
        self.assertEqual(len(inputs), 1)
        self.assertEqual([m["record_id"] for m in members], ["train", "test"])
        self.assertEqual([m["source_split"] for m in members], ["TRAIN", "TEST"])
        self.assertEqual([m["D3_geometry_reference"]["conformer_id"] for m in members], [0, 2])
        self.assertEqual(members[0]["D3_geometry_reference"]["model_atom_to_source"], [4, 2])
        self.assertEqual(members[0]["original_atom_reference"]["model_atom_to_source"], [1, 0])
        self.assertEqual(members[0]["D3_raw"]["SASA_total_A2"], 6.)
        self.assertEqual(members[0]["D3_geometry_reference"]["atom_reference"]["SASA_atom_field"], "D3.SASA_atom_A2")
        self.assertEqual(rows, before)
        self.assertEqual(unresolved, [])

    def test_missing_cv_is_evaluation_pending_without_blocking_canonical_2d(self):
        inputs, members, unresolved = build([source_row()], lambda dataset, record: (fixture(), route(record)))
        self.assertEqual(unresolved, [])
        self.assertIsNone(inputs[0]["canonical_D20_source_error"])
        self.assertIsNone(members[0]["source_split"])
        self.assertEqual(members[0]["evaluation_status"], "EVALUATION_PENDING")
        self.assertEqual(members[0]["D3_status"], dict.fromkeys(D3_NAMES, 1))

    def test_missing_source_remains_unresolved_and_d3_masks_use_first_actual_conformer_only(self):
        inputs, members, unresolved = build([source_row()], lambda dataset, record: (None, route(record)))
        self.assertTrue(all(v is None for v in inputs[0]["existing_D20"].values()))
        self.assertIn("SOURCE_UNAVAILABLE", unresolved[0]["canonical_D20_error"])
        self.assertEqual(members[0]["D3_status"], dict.fromkeys(D3_NAMES, 0))
        shared = fixture()
        shared["result"]["conformers"][0]["D3"].update(PMI1=0., PMI2=None, PBF=float("inf"))
        shared["result"]["conformers"].append(fixture()["result"]["conformers"][0])
        geom = geometry_member(shared, route("original"), "/old/scope.json")
        self.assertEqual(geom["D3_raw"]["PMI1"], 0.)
        self.assertEqual(geom["D3_status"]["PMI2"], 0)
        self.assertEqual(geom["D3_status"]["PBF"], 2)
        self.assertIsNone(geom["D3_raw"]["PBF"])
        shared["result"]["conformers"] = []
        self.assertEqual(geometry_member(shared, route("original"), "/old/scope.json")["D3_status"],
                         dict.fromkeys(D3_NAMES, 0))

    def test_native_terminal_missing_masks_or_no_uff_do_not_block_2d(self):
        for state in ("D20_READY_STEREO_REFERENCE_UNAVAILABLE", "D20_READY_UFF_UNSUPPORTED",
                      "D20_READY_NO_ACCEPTED_CONFORMERS", "D20_READY_GEOMETRY_FAILED"):
            with self.subTest(state=state):
                shared = fixture()
                shared["state"] = shared["result"]["state"] = state
                shared["result"]["conformers"] = []
                inputs, members, unresolved = build([source_row()], lambda dataset, record: (shared, route(record)))
                self.assertEqual(unresolved, [])
                self.assertEqual(inputs[0]["existing_D20"][D20_NAMES[0]], 0.)
                self.assertEqual(members[0]["D3_status"], dict.fromkeys(D3_NAMES, 0))
                shared["result"]["D20"]["valid_mask"] = [False] * 20
                shared["result"]["D20"]["issues"] = ["original-source-issue"]
                inputs, _, unresolved = build([source_row()], lambda dataset, record: (shared, route(record)))
                self.assertEqual(unresolved, [])
                self.assertTrue(all(v is None for v in inputs[0]["existing_D20"].values()))
                self.assertEqual(inputs[0]["native_source"]["known_missing_reason"], "NATIVE_D20_ALL_FIELDS_MASKED")
                self.assertEqual(inputs[0]["native_source"]["D20_issues"], ["original-source-issue"])

    def test_only_exact_native_graph_failure_is_known_missing_not_unknown_or_implementation_failure(self):
        shared = fixture()
        shared["state"] = shared["result"]["state"] = "SOURCE_OR_IMPLEMENTATION_FAILED"
        shared["result"].update(D20=None, conformers=[], error="ValueError('SOURCE_MODEL_GRAPH_UNAVAILABLE')")
        inputs, members, unresolved = build([source_row()], lambda dataset, record: (shared, route(record)))
        self.assertEqual(unresolved, [])
        self.assertIsNone(inputs[0]["smiles"])
        self.assertEqual(inputs[0]["source_binding"]["source_model_smiles"], "CC")
        self.assertEqual(inputs[0]["source_error"], "SOURCE_MODEL_GRAPH_UNAVAILABLE")
        self.assertEqual(members[0]["native_source"]["state"], "SOURCE_OR_IMPLEMENTATION_FAILED")
        shared["result"]["error"] = "RuntimeError('implementation failure')"
        _, _, unresolved = build([source_row()], lambda dataset, record: (shared, route(record)))
        self.assertEqual(len(unresolved), 1)
        for unknown in (dict(fixture(), result=None), dict(fixture(), state="UNKNOWN_WORKER_LOST_NO_RETRY")):
            if unknown["result"] is not None:
                unknown["result"]["state"] = unknown["state"]
                unknown["result"]["D20"]["valid_mask"] = [False] * 20
            _, _, unresolved = build([source_row()], lambda dataset, record: (unknown, route(record)))
            self.assertEqual(len(unresolved), 1)


if __name__ == "__main__":
    unittest.main()
