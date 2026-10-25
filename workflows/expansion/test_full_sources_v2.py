"""Four synthetic boundaries; no RDKit, real source body or scheduler calls."""
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

from . import full_queue_v1 as execution
from .identity_v2 import readers_v2 as readers
from .identity_v3 import projection_v3 as projection
from .identity_v3 import input_authority
from .pubchem_full_v1.inventory_v2 import inventory_stream, iter_index, source_budget, WHOLE_CAP
from workflows.data_v1_final.execution.queue_v1 import shared


class FullSourceBoundaries(unittest.TestCase):
    def test_inventory_preserves_utf8_long_line_and_last_line_without_newline(self):
        source = b"1\t" + b"C" * (1024 * 1024 - 3) + "é".encode() + b"\n2\tCC"
        with tempfile.TemporaryDirectory() as directory:
            index, facts = inventory_stream(io.BytesIO(source), Path(directory), expected_bytes=len(source),
                shard_rows=1, shard_bytes=64 * 1024 ** 2, stop=threading.Event(), checkpoint=lambda: None)
            self.assertEqual(facts["records"], 2)
            self.assertEqual(facts["uncompressed_bytes"], len(source))
            self.assertEqual(b"".join(Path(part["reference"]["path"]).read_bytes() for part in iter_index(index["reference"]["path"])), source)
            self.assertTrue(facts["global_unique_cids_proven"])
            self.assertTrue(all(len(line) <= 4096 for line in Path(index["reference"]["path"]).read_bytes().splitlines(keepends=True)))
        bound = source_budget(8880849781, 250000, 64 * 1024 ** 2)
        self.assertEqual(bound["max_parts"], 11974)
        self.assertLess(bound["whole_mathematical_upper_bytes"], WHOLE_CAP)

    def test_inventory_never_silently_drops_bad_framing_or_nonmonotonic_cids(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Malformed official"):
                inventory_stream(io.BytesIO(b"1\tC\textra\n"), Path(directory), expected_bytes=10,
                    shard_rows=10, shard_bytes=1000, stop=threading.Event(), checkpoint=lambda: None)
        source = b"2\tC\n1\tCC\n"
        with tempfile.TemporaryDirectory() as directory:
            _, facts = inventory_stream(io.BytesIO(source), Path(directory), expected_bytes=len(source),
                shard_rows=10, shard_bytes=1000, stop=threading.Event(), checkpoint=lambda: None)
            self.assertEqual(facts["records"], 2)
            self.assertFalse(facts["global_unique_cids_proven"])
        bound = source_budget(len(source), 10, 1000)
        with tempfile.TemporaryDirectory() as directory:
            stream = Mock()
            # The storage bound is rejected before even opening index/body.
            with self.assertRaisesRegex(ValueError, "10GiB bound"):
                inventory_stream(stream, Path(directory), expected_bytes=len(source), shard_rows=10,
                    shard_bytes=1000, stop=threading.Event(), checkpoint=lambda: None,
                    whole_cap=bound["whole_mathematical_upper_bytes"] - 1)
            self.assertFalse(list(Path(directory).iterdir()))
            stream.readline.assert_not_called()

    def test_original_physical_routine_and_unknown_embargo_are_not_training_roles(self):
        row = {key: None for key in readers.FORMAL_COLUMNS}
        row.update(record_id="original", molecule_id="m", smiles="CC", member_train=False, member_full=True,
            member_routine=True, stored_inchikey="OTMSDBZUPAUEDD-UHFFFAOYSA-N", reidentified_inchikey="OTMSDBZUPAUEDD-FUZZFUZYSA-N")
        value = projection.formal_row(row)
        self.assertEqual(value["role"], "SOURCE_ROUTINE")
        self.assertEqual(value["memberships"], ["SOURCE_FULL", "SOURCE_ROUTINE"])
        self.assertEqual(value["original_physical_member_flags"], {"member_train": False, "member_full": True, "member_routine": True})
        self.assertFalse(value["effective_training_roles_applied"])
        row["common_member"] = False
        with self.assertRaisesRegex(ValueError, "exact complete formal"):
            projection.formal_row(row)
        embargo = {key: None for key in readers.EMBARGO_COLUMNS}
        embargo.update(record_id="embargo", stored_inchikey="INVALID_CACHE", legacy_QA_status="unknown_non_h_composition_embargo",
                       element_counts=[(1, 6), (6, 2)])
        value = projection.embargo_row(embargo)
        self.assertEqual(value["non_h_composition"], [[6, 2]])
        self.assertFalse(value["missing_identity_or_composition"])
        self.assertEqual(value["role"], "SOURCE_EMBARGO")

    def test_uncompleted547_parent_rejected_before_any_body_stat(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            catalog = shared.write_new(root / "catalog.json", {"inputs": []})
            producer = shared.write_new(root / "producer.json", {"schema": "identity_only_current_physical_input_pins_cpu_v1",
                "job_id": "4520547", "node": "compute-0-17", "uid": 1278, "status": "CURRENT_BOUND_INPUT_PINS_COMPLETE",
                "source_catalog": catalog, "pending_locators": [], "blocking_source_ids": [], "worker_thread_ids_observed": list(range(16)),
                "identity_or_role_columns_only": True, "target_or_feature_values_materialized": False, "identity_export_completed": False})
            closure = shared.write_new(root / "closure.json", {"schema": "DATA_V1_IDENTITY_INPUT_PINS_ACTUAL_CLOSURE_V3",
                "status": "ACTUAL_PRODUCER_COMPLETED_NOT_IDENTITY_ACCEPTANCE", "receipt": producer,
                "actual_parent": {"JobIDRaw": "4520547", "State": "RUNNING", "ExitCode": "0:0", "NodeList": "compute-0-17",
                                  "Partition": "cpu", "AllocCPUS": "16"}})
            plan = {"input_pin_receipt": producer, "input_pin_actual_closure": closure, "source_catalog": catalog,
                    "expected_input_pin_job_id": "4520547"}
            proof = {"request": {"source_references": [producer, closure, catalog]}}
            with patch.object(execution, "frame") as body_stat:
                with self.assertRaisesRegex(ValueError, "Root actual completed-parent"):
                    input_authority.authorize(plan, proof)
                body_stat.assert_not_called()


def run_boundaries():
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(FullSourceBoundaries))
    execution.require(result.wasSuccessful() and result.testsRun == 4, "New full-source boundary fixtures failed")
    return {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "real_data_bodies_or_chemistry_used": False}


if __name__ == "__main__":
    unittest.main()
