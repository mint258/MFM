"""Identity-only metadata count boundaries; no physical study data consumed."""
import json
import gzip
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .pin_inputs_v1 import describe_identity_source


class IdentityInputPinTests(unittest.TestCase):
    def test_csv_counts_all_rows_and_materializes_only_identity_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rows.csv"
            path.write_text('SMILES,Molecule Name,assay_target\nCC,a,"FORBIDDEN_TARGET\nSECOND_LINE"\nCO,b,\n', encoding="utf-8")
            compressed = path.with_suffix(".csv.gz")
            compressed.write_bytes(gzip.compress(path.read_bytes(), mtime=0))
            for file, kind in ((path, "csv"), (compressed, "csv_gz")):
                item = {"path": str(file), "kind": kind, "source_id": "fixture", "expected_records": 2}
                observed = describe_identity_source(item)
                self.assertEqual(observed["records"], 2)
                self.assertEqual(observed["materialized_columns"], ["SMILES", "Molecule Name"])
                self.assertNotIn("FORBIDDEN_TARGET", json.dumps(observed))
                self.assertFalse(observed["targets_or_features_materialized"])
                item["expected_records"] = 3
                with self.assertRaisesRegex(ValueError, "Independent physical record count differs"):
                    describe_identity_source(item)

    def test_sdf_and_jsonl_count_opaque_boundaries_without_decoding_properties(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sdf = root / "rows.sdf"
            sdf.write_bytes(b"mol1\nM  END\n> <PRIMARY_SOM>\nFORBIDDEN_TARGET\n\n$$$$\nmol2\nM  END\n$$$$\n")
            observed = describe_identity_source({"path": str(sdf), "kind": "sdf", "source_id": "sdf", "expected_records": 2})
            self.assertEqual(observed["records"], 2)
            self.assertFalse(observed["sdf_properties_decoded"])
            ledger = root / "opaque.jsonl"
            ledger.write_bytes(b'{"source_id":"a","unused_target":"FORBIDDEN_TARGET"}\n\n{"source_id":"b"}\n')
            observed = describe_identity_source({"path": str(ledger), "kind": "jsonl_opaque", "source_id": "jsonl", "expected_records": 2})
            self.assertEqual(observed["records"], 2)
            self.assertFalse(observed["jsonl_value_objects_decoded"])
            self.assertNotIn("FORBIDDEN_TARGET", json.dumps(observed))

    def test_mat_probe_reads_shape_metadata_without_loading_any_numeric_array(self):
        import numpy as np
        from scipy.io import savemat
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "qm7.mat"
            savemat(path, {"Z": np.array([[6, 1, 0], [7, 1, 0], [8, 1, 0]]),
                           "X": np.ones((3, 3, 3)), "T": np.ones((1, 3)), "R": np.zeros((3, 3, 3))})
            with patch("scipy.io.loadmat", side_effect=AssertionError("numeric arrays forbidden in pin probe")):
                observed = describe_identity_source({"path": str(path), "kind": "mat_Z_metadata", "source_id": "mat", "expected_records": 3})
            self.assertEqual(observed["records"], 3)
            self.assertEqual(observed["loaded_numeric_value_variables"], [])


if __name__ == "__main__":
    unittest.main()
