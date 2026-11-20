"""CPU finalization state/reuse only; no bootstrap is sampled in these tests."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.d_recipe.cpu_statistics import finalize
from tools.d_recipe.training import prepare_runtime
from test_d_recipe_training import configuration


class FinalStatisticsTests(unittest.TestCase):
    def setup_run(self, directory, *, status="GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS"):
        c = dict(configuration(), output=directory, reference_manifest="/existing/random/predictions.json")
        summary = dict(status=status, run=c["run"], samples=c["samples"], statistics_complete=False)
        (Path(directory) / "summary.json").write_text(json.dumps(summary))
        (Path(directory) / "configuration.json").write_text(json.dumps(prepare_runtime(c)))
        return c, summary

    def test_only_CPU_scoring_of_existing_final_readout_is_requested(self):
        with tempfile.TemporaryDirectory() as directory:
            c, _ = self.setup_run(directory)
            scorer, publish = Mock(), Mock()
            result = finalize(c, scorer=scorer, publish=publish)
            self.assertEqual(scorer.call_args.args[0]["output"], str(Path(directory) / "readout"))
            self.assertEqual(scorer.call_args.args[0]["reference_manifest"], c["reference_manifest"])
            self.assertTrue(result["statistics_complete"])
            self.assertEqual(result["status"], "COMPLETE")
            publish.assert_called_once()

    def test_closed_scores_are_reused_without_another_bootstrap_or_CSV_append(self):
        with tempfile.TemporaryDirectory() as directory:
            c, _ = self.setup_run(directory)
            readout = Path(directory) / "readout"
            readout.mkdir()
            (readout / "scores.json").write_text("{}")
            scorer = Mock()
            result = finalize(c, scorer=scorer, publish=Mock())
            scorer.assert_not_called()
            self.assertTrue(result["statistics_complete"])

    def test_training_or_handoff_is_not_promoted_to_a_complete_run(self):
        with tempfile.TemporaryDirectory() as directory:
            for status in ("TRAINING_COMPLETE_EVALUATION_PENDING", "HANDOFF_SAVED"):
                c, _ = self.setup_run(directory, status=status)
                scorer = Mock()
                with self.assertRaisesRegex(ValueError, "readouts to close"):
                    finalize(c, scorer=scorer, publish=Mock())
                scorer.assert_not_called()

    def test_completed_run_is_idempotent_and_wrong_run_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            c, summary = self.setup_run(directory, status="COMPLETE")
            summary["statistics_complete"] = True
            (Path(directory) / "summary.json").write_text(json.dumps(summary))
            scorer, publish = Mock(), Mock()
            self.assertEqual(finalize(c, scorer=scorer, publish=publish), summary)
            scorer.assert_not_called()
            publish.assert_not_called()
            c["run"] = "another-run"
            with self.assertRaisesRegex(ValueError, "registered run"):
                finalize(c, scorer=scorer, publish=publish)
