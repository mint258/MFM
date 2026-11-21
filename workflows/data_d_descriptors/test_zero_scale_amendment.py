"""Approved continuation cannot refit, change arrays or broaden exclusions."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .produce import finalize


class ZeroScaleAmendmentTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        manifest = dict(schema="D_WIDE_DESCRIPTOR_STORE_V1", libraries={})
        approval = dict(schema="D_NEW_LIBRARY_ZERO_SCALE_AMENDMENT_V1",
            id="20261122_zero_scale", status="APPROVED_BEFORE_AMENDED_PRODUCTION",
            statistics_refit=False, epsilon_added=False, raw_arrays_changed=False,
            existing_D20_D3_D4_changed=False, libraries={},
            original_unresolved_manifest=str(root / "final_manifest.json"),
            amended_manifest=str(root / "final_manifest_zero_scale_amendment_20261122.json"))
        for library, count in (("L1", 7), ("L2", 65)):
            names = ["zero_" + str(i) for i in range(count)]
            fields = [dict(name=name, enabled=True,
                normalization_status="ZERO_SCALE_NOT_DIVIDABLE",
                parameters=dict(mean=0., std_population=0.)) for name in names]
            fields += [dict(name="good", enabled=True,
                normalization_status="FITTED_TRAIN_ONCE",
                parameters=dict(mean=1.25, std_population=2.5, q001=-1., q999=3.))]
            if library == "L1":
                fields += [dict(name="ExactMolWt", enabled=True,
                    normalization_status="REUSED_UNCHANGED",
                    parameters=dict(center=100., scale=2., historical="unchanged"))]
            marker = root / (library + "_statistics.json")
            marker.write_text(json.dumps(dict(library=library, fit_role="TRAIN", fields=fields)))
            manifest["libraries"][library] = dict(ordered_fields=[f["name"] for f in fields],
                values=str(root / (library + "_never_read.npy")),
                status=str(root / (library + "_never_read_status.npy")),
                rows="original_rows.jsonl", fit_role="TRAIN", producer_alignment_checked=True)
            approval["libraries"][library] = dict(excluded_fields=names,
                excluded_count=count, original_statistics=str(marker))
        (root / "manifest.json").write_text(json.dumps(manifest))
        (root / "final_manifest.json").write_text(json.dumps(dict(status="UNRESOLVED")))
        path = root / "approval.json"
        path.write_text(json.dumps(approval))
        config = dict(output=str(root), peak_bytes=100000, zero_scale_amendment=str(path))
        return config, approval, {p.name: p.read_bytes() for p in root.iterdir()}

    def run_finalizer(self, config):
        with patch("workflows.data_d_descriptors.produce.require_cpu"), \
                patch("workflows.data_d_descriptors.pilot.storage_guard"), \
                patch("workflows.data_d_descriptors.produce.np.load",
                      side_effect=AssertionError("No original arrays may be reread")), \
                patch("workflows.data_d_descriptors.produce.summarize_library",
                      side_effect=AssertionError("No closed TRAIN fit may be repeated")):
            return finalize(config)

    def test_only_metadata_changes_and_all_originals_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            config, approval, originals = self.fixture(directory)
            result = self.run_finalizer(config)
            self.assertEqual(result["status"], "PRODUCER_COMPLETE_RECEPTION_PENDING")
            for library, spec in approval["libraries"].items():
                before = json.loads(originals[library + "_statistics.json"])
                entry = result["libraries"][library]
                count = spec["excluded_count"]
                self.assertEqual(entry["enabled_columns"], list(range(count, len(before["fields"]))))
                self.assertEqual(entry["normalization"][:count], [None] * count)
                self.assertEqual(entry["normalization"][count]["std_ddof0"], 2.5)
                for index in entry["enabled_columns"]:
                    original = before["fields"][index]["parameters"]
                    self.assertTrue(all(entry["normalization"][index][k] == v for k, v in original.items()))
                self.assertEqual(entry["reception_acceptance"], "pending")
                self.assertEqual(entry["values"], str(Path(directory) / (library + "_never_read.npy")))
            for name, content in originals.items():
                self.assertEqual((Path(directory) / name).read_bytes(), content)

    def test_nonzero_or_unapproved_fields_and_old_D20_cannot_be_dropped(self):
        for invalid in ("nonzero", "unapproved", "old_D20"):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                config, approval, _ = self.fixture(directory)
                marker = Path(directory) / "L1_statistics.json"
                statistics = json.loads(marker.read_text())
                if invalid == "nonzero":
                    statistics["fields"][0]["parameters"]["std_population"] = 1e-100
                elif invalid == "unapproved":
                    statistics["fields"][0]["normalization_status"] = "FITTED_TRAIN_ONCE"
                else:
                    approval["libraries"]["L1"]["excluded_fields"][0] = "ExactMolWt"
                    Path(config["zero_scale_amendment"]).write_text(json.dumps(approval))
                marker.write_text(json.dumps(statistics))
                with self.assertRaises(ValueError):
                    self.run_finalizer(config)
                self.assertFalse(Path(approval["amended_manifest"]).exists())

    def test_replacement_statistics_reference_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config, _, _ = self.fixture(directory)
            path = Path(config["zero_scale_amendment"])
            approval = json.loads(path.read_text())
            approval["libraries"]["L1"]["original_statistics"] = str(Path(directory) / "replacement.json")
            path.write_text(json.dumps(approval))
            with self.assertRaisesRegex(ValueError, "ORIGINAL_CLOSED_STATISTICS"):
                self.run_finalizer(config)

    def test_closed_amended_manifest_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            config, approval, _ = self.fixture(directory)
            first = self.run_finalizer(config)
            destination = Path(approval["amended_manifest"])
            original_bytes = destination.read_bytes()
            second = self.run_finalizer(config)
            self.assertEqual(first, second)
            self.assertEqual(destination.read_bytes(), original_bytes)


if __name__ == "__main__":
    unittest.main()
