"""Two new authorization cases; no real datasets or old-suite repetition."""
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest

from . import data_authority_v1 as authority
from .common import dump_new, reference


class DataAuthorityTests(unittest.TestCase):
    def fixture(self, root):
        data = root / "dataset.bin"
        data.write_bytes(b"ABCD")
        ref, snapshot = reference(data), authority.file_stat(data)
        receipt = root / "compute_pin.json"
        dump_new(receipt, {"schema": "DATA_V1_SOURCE_PIN_RECEIPT_V1", "status": "ALL_BOUND_INPUTS_SHA_VERIFIED",
            "node": "compute-0-20", "job_id": "4520999", "outputs": [{"name": "original_index", "reference": ref,
            "before": snapshot, "after": snapshot, "stable_file_identity": {
                "dev": snapshot["device"], "ino": snapshot["inode"], "mtime_ns": snapshot["mtime_ns"]}}]})
        pin = reference(receipt)
        plan = {"data_authorization_receipts": [pin], "authorized_data_pin_jobs": ["4520999"], "allow_small_fixture_legacy_authority": False}
        submission = {"request": {"source_references": [pin], "data_references": [ref]}}
        return data, ref, plan, submission

    def test_bound_small_receipt_authorizes_data_only_in_data_references(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, ref, plan, submission = self.fixture(Path(tmp))
            self.assertNotIn(str(data), [r["path"] for r in submission["request"]["source_references"]])
            accepted = authority.authorize_data(plan, submission, [ref])
            authority.verify_authorized_data(accepted)
            authority.verify_final_stats(accepted)
            self.assertEqual(accepted["files"][0]["producer_job_id"], "4520999")

    def test_unbound_wrong_job_and_same_stat_wrong_body_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, ref, plan, submission = self.fixture(Path(tmp))
            changed = deepcopy(submission); changed["request"]["source_references"] = []
            with self.assertRaises(ValueError): authority.authorize_data(plan, changed, [ref])
            changed_plan = deepcopy(plan); changed_plan["authorized_data_pin_jobs"] = ["4520888"]
            with self.assertRaises(ValueError): authority.authorize_data(changed_plan, submission, [ref])
            accepted = authority.authorize_data(plan, submission, [ref])
            previous = data.stat()
            data.write_bytes(b"WXYZ")
            os.utime(data, ns=(previous.st_atime_ns, previous.st_mtime_ns))
            self.assertEqual(authority.file_stat(data), accepted["files"][0]["expected_stat"])
            with self.assertRaises(ValueError): authority.verify_authorized_data(accepted)


if __name__ == "__main__":
    unittest.main()
