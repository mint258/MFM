"""Boundary checks for closed diagnostic delivery policy; synthetic files only."""
import json
from pathlib import Path
import tempfile
import unittest

import check_repository as checker


class DeliveryPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.paths = []
        self.put("docs/SOURCE_MANIFEST.json", b'{"files": []}')

    def put(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        if name not in self.paths:
            self.paths.append(name)
        return name

    def native(self, rows, **changes):
        value = dict(schema="MODEL_V3_DIAGNOSTICS_DELIVERY_20261112",
                     status="ALL_SIX_EXPORTS_COMPLETE", selection_use=False,
                     file_count=len(rows), files=rows)
        value.update(changes)
        self.put(checker.DIAGNOSTIC_ROOT + "/DELIVERY_MANIFEST.json",
                 json.dumps(value).encode())

    def csv(self, rows):
        value = dict(schema="MODEL_V3_DIAGNOSTICS_CSV_DELIVERY_V1",
                     status="COMPLETE", selection_use=False,
                     csv_tables=len(rows), files=rows)
        self.put(checker.DIAGNOSTIC_ROOT + "/csv/CSV_MANIFEST.json",
                 json.dumps(value).encode())

    def check(self):
        return checker.check(self.root, self.paths, verify_export=False)

    def test_recorded_parquet_and_large_csv_are_accepted(self):
        data = b"x" * (2 * 1024**2 + 1)
        self.put(checker.DIAGNOSTIC_ROOT + "/predictions/closed.parquet", data)
        self.put(checker.DIAGNOSTIC_ROOT + "/csv/predictions/closed.csv", data)
        self.native([dict(path="predictions/closed.parquet", bytes=len(data))])
        self.csv([dict(path="predictions/closed.csv", bytes=len(data))])
        self.assertEqual(self.check()["status"], "PASS")

    def test_undeclared_data_and_manifest_listed_weights_stay_rejected(self):
        self.put(checker.DIAGNOSTIC_ROOT + "/predictions/unlisted.parquet", b"x")
        self.put(checker.DIAGNOSTIC_ROOT + "/weights.pt", b"x")
        self.put(checker.DIAGNOSTIC_ROOT + "/.env", b"x")
        self.native([dict(path="weights.pt", bytes=1), dict(path=".env", bytes=1)])
        errors = self.check()["errors"]
        self.assertEqual(len(errors), 3)
        self.assertTrue(all("data, weights" in row["reason"] for row in errors))

    def test_changed_byte_length_is_not_a_frozen_delivery(self):
        name = self.put(checker.DIAGNOSTIC_ROOT + "/predictions/closed.parquet", b"xx")
        self.native([dict(path="predictions/closed.parquet", bytes=1)])
        errors = self.check()["errors"]
        self.assertTrue(any(row["path"] == name and "byte length" in row["reason"] for row in errors))

    def test_declared_delivery_still_gets_credential_scan(self):
        raw = b"column\n" + b"ghp_" + b"X" * 30
        name = self.put(checker.DIAGNOSTIC_ROOT + "/csv/predictions/closed.csv", raw)
        self.csv([dict(path="predictions/closed.csv", bytes=len(raw))])
        self.assertTrue(any(row["path"] == name and "credential" in row["reason"]
                            for row in self.check()["errors"]))

    def test_bad_manifest_path_or_unclosed_state_fails_closed(self):
        for row, changes in [
            (dict(path="../weights.pt", bytes=1), {}),
            (dict(path="predictions/closed.parquet", bytes=1), dict(status="RUNNING")),
            (dict(path="predictions/closed.parquet", bytes=1), dict(file_count=2)),
        ]:
            with self.subTest(row=row, changes=changes):
                self.native([row], **changes)
                self.assertEqual(self.check()["status"], "FAIL")

    def test_ordinary_source_size_limit_is_preserved(self):
        self.put("results/unregistered_dump.json", b"x" * (2 * 1024**2 + 1))
        self.assertTrue(any("2 MiB" in row["reason"] for row in self.check()["errors"]))

    def test_registered_p_summaries_do_not_allow_an_unrelated_csv(self):
        for name in [
            "results/p_recipe/E1/k10_full/rows.csv",
            "results/p_recipe/fixed_20261115/analysis_20261122/I1.csv",
            "results/p_recipe/fixed_20261115/analysis_20261122/hardware_I1.csv",
        ]:
            self.put(name, b"metric,value\nexample,1\n")
        self.assertEqual(self.check()["status"], "PASS")
        self.put("results/p_recipe/E1/unregistered.csv", b"metric,value\nexample,1\n")
        self.assertEqual(self.check()["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()

