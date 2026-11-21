"""Per-library taskbook closeout preserves original producer statistics."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .produce import finalize


class FinalizationContinuationTests(unittest.TestCase):
    def fixture(self, root):
        root = Path(root)
        rows = root / "rows.jsonl"
        rows.write_text(json.dumps(dict(role="TRAIN")) + "\n")
        manifest = dict(schema="D_WIDE_DESCRIPTOR_STORE_V1", rows=str(rows),
            libraries={name: dict(values=str(root / (name + "_values.npy")),
                status=str(root / (name + "_status.npy")), ordered_fields=["x"])
                for name in ("L1", "L2")})
        (root / "manifest.json").write_text(json.dumps(manifest))
        for name, status, scale in (("L1", "ZERO_SCALE_NOT_DIVIDABLE", 0.),
                                    ("L2", "OK", 1.)):
            record = dict(library=name, fit_role="TRAIN", fields=[
                dict(name="x", enabled=True, normalization_status=status,
                     parameters=dict(mean=0., std_population=scale))])
            (root / (name + "_statistics.json")).write_text(json.dumps(record))
        config = dict(output=str(root), peak_bytes=100000)
        originals = {p.name: p.read_bytes() for p in root.iterdir()}
        return config, originals

    def test_unresolved_library_keeps_raw_and_statistics_while_peer_closes(self):
        with tempfile.TemporaryDirectory() as directory:
            config, originals = self.fixture(directory)
            config["unresolved_libraries"] = {"L1": "Taskbook two failed finalizations"}
            with patch("workflows.data_d_descriptors.produce.require_cpu"), \
                    patch("workflows.data_d_descriptors.pilot.storage_guard"), \
                    patch("workflows.data_d_descriptors.produce.np.load",
                          side_effect=AssertionError("Do not reread closed numerical arrays")), \
                    patch("workflows.data_d_descriptors.produce.summarize_library",
                          side_effect=AssertionError("Do not refit closed TRAIN statistics")):
                result = finalize(config)
            first, peer = result["libraries"]["L1"], result["libraries"]["L2"]
            self.assertEqual(first["status"], "UNRESOLVED")
            self.assertEqual(first["reception_acceptance"], "not_deliverable")
            self.assertEqual(first["status_store"],
                             str(Path(directory) / "L1_status.npy"))
            self.assertEqual(first["statistics"],
                             str(Path(directory) / "L1_statistics.json"))
            self.assertEqual(peer["state"], "PRODUCER_COMPLETE_RECEPTION_PENDING")
            self.assertEqual(peer["normalization"][0]["std_ddof0"], 1.)
            for name, before in originals.items():
                self.assertEqual((Path(directory) / name).read_bytes(), before)

    def test_default_still_rejects_zero_scale_without_changing_the_filter(self):
        with tempfile.TemporaryDirectory() as directory:
            config, originals = self.fixture(directory)
            with patch("workflows.data_d_descriptors.produce.require_cpu"), \
                    self.assertRaisesRegex(ValueError, "ZERO_SCALE:L1"):
                finalize(config)
            self.assertFalse((Path(directory) / "final_manifest.json").exists())
            for name, before in originals.items():
                self.assertEqual((Path(directory) / name).read_bytes(), before)

    def test_unresolved_override_cannot_hide_an_unknown_library_or_empty_reason(self):
        with tempfile.TemporaryDirectory() as directory:
            config, _ = self.fixture(directory)
            for bad in ({"L3": "timebox"}, {"L1": ""}, {"L1": True}, ["L1"]):
                config["unresolved_libraries"] = bad
                with patch("workflows.data_d_descriptors.produce.require_cpu"), \
                        self.assertRaisesRegex(ValueError, "known library"):
                    finalize(config)


if __name__ == "__main__":
    unittest.main()
