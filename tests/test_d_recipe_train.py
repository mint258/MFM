"""Final endpoint orchestration only: no model fitting or GPU work."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.d_recipe.train import gpu_telemetry, run
from tools.d_recipe.training import prepare_runtime
from test_d_recipe_training import configuration


class TrainEntryTests(unittest.TestCase):
    def config(self, directory):
        return dict(configuration(), output=directory, readout_store="/existing/development.json",
                    reference_manifest="/existing/random/predictions.json", storage_peak_bytes=2**30)

    def test_handoff_never_starts_readouts_or_overwrites_its_summary(self):
        trainer = Mock(return_value={"status": "HANDOFF_SAVED", "samples": 1000000})
        evaluator, checkpoint, publish = Mock(), Mock(), Mock()
        result = run(self.config("/own/output"), trainer=trainer, evaluator=evaluator,
                     checkpoint_resolver=checkpoint, publish=publish)
        self.assertEqual(result["status"], "HANDOFF_SAVED")
        evaluator.assert_not_called()
        checkpoint.assert_not_called()
        publish.assert_not_called()

    def test_closed_readout_is_reused_and_bootstrap_remains_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "readout"
            output.mkdir()
            (output / "predictions.json").write_text("{\"producer_closed\":true}")
            c = self.config(directory)
            before = deepcopy(c)
            evaluator, publish = Mock(), Mock()
            trainer = Mock(return_value={"status": "TRAINING_COMPLETE_EVALUATION_PENDING", "samples": 3000000})
            checkpoint = Mock(return_value=Path(directory) / "samples_3000000.pt")
            result = run(c, trainer=trainer, evaluator=evaluator,
                         checkpoint_resolver=checkpoint, publish=publish)
            self.assertEqual(c, before)
            evaluator.assert_not_called()
            self.assertEqual(result["status"], "GPU_READOUT_COMPLETE_WAITING_CPU_STATISTICS")
            self.assertFalse(result["statistics_complete"])
            publish.assert_called_once()

    def test_only_the_final_endpoint_is_dispatched_without_feature_bank(self):
        with tempfile.TemporaryDirectory() as directory:
            c = self.config(directory)
            trainer = Mock(return_value={"status": "TRAINING_COMPLETE_EVALUATION_PENDING", "samples": 3000000})
            evaluator = Mock()
            run(c, trainer=trainer, evaluator=evaluator,
                checkpoint_resolver=Mock(return_value=Path(directory) / "samples_3000000.pt"), publish=Mock())
            evaluation = evaluator.call_args.args[0]
            self.assertEqual(evaluation["samples"], 3000000)
            self.assertEqual(evaluation["store"], c["readout_store"])
            self.assertFalse(evaluation["persist_features"])
            self.assertEqual(evaluation["output"], str(Path(directory) / "readout"))
            c["evaluation_samples"] = [1000000, 3000000]
            trainer.reset_mock()
            with self.assertRaisesRegex(ValueError, "final downstream"):
                run(c, trainer=trainer, evaluator=evaluator, checkpoint_resolver=Mock(), publish=Mock())
            trainer.assert_not_called()

    def test_final_h0_retention_is_explicit_and_uses_the_original_feature_producer(self):
        from tools.d_recipe.train import final_readout
        c = self.config("/own/final")
        c["persist_final_features"] = True
        result = final_readout(c, lambda *_: Path("/own/final/samples_3000000.pt"))
        self.assertTrue(result["persist_features"])
        self.assertEqual(result["features"], "/own/final/features_3000000")
        self.assertTrue(c["persist_final_features"])

    def test_incomplete_training_cannot_be_promoted_to_readout_complete(self):
        trainer = Mock(return_value={"status": "TRAINING_COMPLETE_EVALUATION_PENDING", "samples": 1000000})
        evaluator = Mock()
        with self.assertRaisesRegex(ValueError, "completed registered"):
            run(self.config("/own/output"), trainer=trainer, evaluator=evaluator,
                checkpoint_resolver=Mock(), publish=Mock())
        evaluator.assert_not_called()

    def test_closed_training_is_not_restarted_and_changed_science_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            c = self.config(directory)
            saved = prepare_runtime(c)
            (Path(directory) / "configuration.json").write_text(json.dumps(saved))
            (Path(directory) / "summary.json").write_text(json.dumps(dict(
                status="TRAINING_COMPLETE_EVALUATION_PENDING", samples=3000000, run=c["run"])))
            trainer, evaluator = Mock(), Mock()
            run(c, trainer=trainer, evaluator=evaluator,
                checkpoint_resolver=Mock(return_value=Path(directory) / "samples_3000000.pt"), publish=Mock())
            trainer.assert_not_called()
            evaluator.assert_called_once()
            c["seed"] = 1
            with self.assertRaisesRegex(ValueError, "scientific configuration differs"):
                run(c, trainer=trainer, evaluator=evaluator, checkpoint_resolver=Mock(), publish=Mock())
            trainer.assert_not_called()

    def test_telemetry_uses_D_prefix_and_restores_shared_helper_after_exception(self):
        module = SimpleNamespace(REPO=Path("/original/P"), record_gpu_telemetry=Mock())
        sampled = threading.Event()
        def record(configuration):
            self.assertEqual(module.REPO / "results/p_recipe/training",
                Path(__file__).resolve().parents[1] / "results/d_recipe/training")
            sampled.set()
        module.record_gpu_telemetry.side_effect = record
        with patch.dict("os.environ", CUDA_VISIBLE_DEVICES="GPU-existing-uuid"):
            with self.assertRaisesRegex(RuntimeError, "caller error"):
                with gpu_telemetry(self.config("/own/output"), module=module):
                    self.assertTrue(sampled.wait(2))
                    raise RuntimeError("caller error")
        self.assertEqual(module.REPO, Path("/original/P"))
        self.assertEqual(module.record_gpu_telemetry.call_args.args[0]["gpu_uuid"], "GPU-existing-uuid")

    def test_completed_CPU_statistics_are_never_downgraded_or_recomputed(self):
        with tempfile.TemporaryDirectory() as directory:
            c = self.config(directory)
            (Path(directory) / "configuration.json").write_text(json.dumps(prepare_runtime(c)))
            expected = dict(status="COMPLETE", samples=3000000, run=c["run"], statistics_complete=True)
            (Path(directory) / "summary.json").write_text(json.dumps(expected))
            trainer, evaluator, publish = Mock(), Mock(), Mock()
            self.assertEqual(run(c, trainer=trainer, evaluator=evaluator,
                checkpoint_resolver=Mock(), publish=publish), expected)
            trainer.assert_not_called()
            evaluator.assert_not_called()
            publish.assert_not_called()


if __name__ == "__main__":
    unittest.main()
