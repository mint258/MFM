"""Exact native-pointer joins reuse original strings, not canonical labels."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import pyarrow as pa
import pyarrow.parquet as pq

from .pilot import original_smiles
from .source_smiles import COLUMNS, SourceSmiles


class SourceSmilesTests(unittest.TestCase):
    def write(self, directory, rows):
        path = Path(directory) / "existing.parquet"
        pq.write_table(pa.Table.from_pylist(rows), path)
        return path

    def test_reads_only_exact_source_fields_and_preserves_original_stereo_salts_and_isotopes(self):
        with tempfile.TemporaryDirectory() as directory:
            value = "C[C@H]([2H])O.[Cl-]"
            path = self.write(directory, [dict(real_index=7, source_path="/original/native.lmdb",
                smiles=value, canonical_smiles="DIFFERENT", reidentified_smiles="DIFFERENT_AGAIN",
                energy_raw=12345., original_fields_json="DO_NOT_DECODE")])
            requests = []
            class Reader:
                def __init__(self, filename): self.file = pq.ParquetFile(filename)
                def __enter__(self): return self
                def __exit__(self, *args): self.file.close()
                def iter_batches(self, **kwargs):
                    requests.append(kwargs["columns"])
                    return self.file.iter_batches(**kwargs)
            pointer = dict(source_path="/original/native.lmdb", real_index=7, molecule_id="same-id")
            before = copy.deepcopy(pointer)
            source = SourceSmiles.from_parquet(path, [pointer], reader=Reader)
            self.assertEqual(original_smiles(pointer, lookup=source.get), value)
            self.assertEqual(pointer, before)
            self.assertEqual(requests, [list(COLUMNS)])

    def test_same_basename_or_other_index_cannot_substitute_a_native_pointer(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write(directory, [dict(source_path="/other/native.lmdb", real_index=7, smiles="C"),
                                         dict(source_path="/original/native.lmdb", real_index=8, smiles="CC")])
            pointer = dict(source_path="/original/native.lmdb", real_index=7)
            source = SourceSmiles.from_parquet(path, [pointer])
            with self.assertRaisesRegex(RuntimeError, "absent"):
                source.get(pointer)

    def test_conflicting_duplicate_pointer_is_not_arbitrarily_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = [dict(source_path="/original/a", real_index=1, smiles=value) for value in ("C", "CC")]
            with self.assertRaisesRegex(ValueError, "Conflicting"):
                SourceSmiles.from_parquet(self.write(directory, rows), [rows[0]])

    def test_declared_missing_string_stays_missing_and_relative_paths_keep_original_reader_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            rows = [dict(source_path="original/a", real_index=1, smiles=None),
                    dict(source_path="original/a", real_index=2, smiles="[NH4+]")]
            source = SourceSmiles.from_parquet(self.write(directory, rows), rows)
            with self.assertRaisesRegex(ValueError, "unavailable"):
                source.get(rows[0])
            self.assertEqual(source.get(rows[1]), "[NH4+]")

    def test_no_remaining_pointers_does_not_rescan_the_original_index(self):
        reader = Mock()
        source = SourceSmiles.from_parquet("/unused", [], reader=reader)
        self.assertEqual(source.values, {})
        reader.assert_not_called()


if __name__ == "__main__":
    unittest.main()
