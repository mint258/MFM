"""Closed-cache reuse, source graph binding and zero/missing preservation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

from . import pilot
from .b6_cache import B6L1Cache, POLICY, unchanged_remove_hs


class B6CacheTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        part = root / "part.parquet"
        rows = [dict(dataset="qm9", member_uid="q1", source_ordinal=7,
                     rdkit_values=[9., 0.], rdkit_mask=[False, True], ignored_xTB="not projected"),
                dict(dataset="cyp_isoform", member_uid="sdf1", source_ordinal=8,
                     rdkit_values=[2., 3.], rdkit_mask=[True, True], ignored_xTB="not projected")]
        pq.write_table(pa.Table.from_pylist(rows), part)
        manifest = dict(schema="DATA_V1_DOWNSTREAM_BASELINE_DESCRIPTORS_V2",
                        status="SOURCE_SLICE_COMPLETE_WITH_EXPLICIT_MISSING",
                        target_or_annotation_values_decoded=False, rdkit_version="2025.09.5",
                        rdkit_2D_graph_policy=POLICY, rdkit_descriptor_names=["new", "ExactMolWt"],
                        files=[dict(path=str(part))])
        path = root / "manifest.json"
        path.write_text(json.dumps(manifest))
        return path, manifest

    def cache(self, path, **options):
        arguments = dict(fields=["ExactMolWt", "new"], rdkit_version="2025.9.5", member_uids=["q1", "sdf1"])
        arguments.update(options)
        return B6L1Cache(path, **arguments)

    def test_matching_version_reorders_fields_and_preserves_true_zero_and_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.fixture(directory)
            cache = self.cache(path)
            self.assertTrue(cache.compatible)
            self.assertEqual(cache.get("q1", "C", 7), {"ExactMolWt": 0., "new": None})
            self.assertIsNone(cache.get("q1", "C", 999))
            self.assertIsNone(cache.get("sdf1", "C"))
            self.assertFalse(cache.provenance()["task_labels_read"])

    def test_incompatible_software_or_fields_falls_back_without_loading_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.fixture(directory)
            for options in (dict(rdkit_version="2025.9.6"), dict(fields=["different"])):
                with self.subTest(options=options), patch("pyarrow.parquet.ParquetFile", side_effect=AssertionError("cache values read")):
                    cache = self.cache(path, **options)
                self.assertFalse(cache.compatible)
                self.assertIsNone(cache.get("q1", "C"))

    def test_unproved_graph_equivalence_cannot_reuse_cached_descriptors(self):
        with tempfile.TemporaryDirectory() as directory:
            path, _ = self.fixture(directory)
            cache = self.cache(path)
            with patch("workflows.data_d_descriptors.b6_cache.unchanged_remove_hs", return_value=False):
                self.assertIsNone(cache.get("q1", "C"))
            self.assertFalse(unchanged_remove_hs(None))
            self.assertTrue(unchanged_remove_hs("CCO"))

    def test_cached_fields_skip_functions_and_canonical_d20_takes_priority(self):
        def must_not_run(_):
            raise AssertionError("Closed descriptor was recomputed")
        payload = pilot.descriptor_input(dict(smiles="C", existing_L1={"ExactMolWt": 12., "new": 0.},
                                              existing_D20={"ExactMolWt": 16.}))
        with patch.object(pilot, "LIBRARY", "L1"), patch.object(pilot, "FIELDS", ["ExactMolWt", "new"]), \
             patch.object(pilot, "CALCULATOR", [("ExactMolWt", must_not_run), ("new", must_not_run)]):
            values, valid, bad, *_ = pilot.one(payload)
        self.assertEqual(values, [16., 0.])
        self.assertEqual(valid, [True, True])
        self.assertEqual(bad, [False, False])

    def test_l2_does_not_use_the_rdkit_cache(self):
        payload = pilot.descriptor_input(dict(smiles="C", existing_L1={"mordred": 999.}, existing_D20={}))
        with patch.object(pilot, "LIBRARY", "L2"), patch.object(pilot, "FIELDS", ["mordred"]), \
             patch.object(pilot, "CALCULATOR", lambda _: [3.]):
            values, valid, *_ = pilot.one(payload)
        self.assertEqual(values, [3.])
        self.assertEqual(valid, [True])


if __name__ == "__main__":
    unittest.main()
