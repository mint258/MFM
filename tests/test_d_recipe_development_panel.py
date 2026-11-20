"""Section5 orchestration/resume tests with fake probes, no encoder or learner."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import torch

from phychem_mfm.phase1.v3_dev_evaluation import TaskSpec, TaskMolecule, TaskPrediction
from phychem_mfm.phase1.v3_dev_evaluation_v2 import _pack
from tools.d_recipe import development_panel as panel


class DevelopmentPanelTests(unittest.TestCase):
    def fixture(self, directory):
        root = Path(directory)
        main = root / "main"
        main.mkdir()
        task = TaskSpec("qm9.alpha", "qm9", "alpha", "graph", "mae")
        def molecule(mid):
            return TaskMolecule(mid, torch.zeros((2, 3)), torch.arange(2), torch.tensor([1.]),
                torch.tensor([True]), torch.tensor([True]), "original:" + mid)
        train, validation = (molecule("train"),), (molecule("validation"),)
        prediction = TaskPrediction(task, ("validation",), np.array([1.]), np.array([1.2]),
            np.array([True]), ("original:validation",))
        reference_cell = root / "random.pt"
        torch.save(dict(prediction=_pack(prediction)), reference_cell)
        reference = root / "random.json"
        reference.write_text(json.dumps(dict(files={task.task_id + "/R3": str(reference_cell)})))
        (main / "predictions.json").write_text(json.dumps(dict(run="D-final-9M", samples=9_000_000,
            files={task.task_id + "/R3": "/existing/closed/A.pt"})))
        (main / "scores.json").write_text(json.dumps({"R3": {"existing_A_statistic": True}}))
        best = root / "best.json"
        best.write_text(json.dumps(dict(status="FROZEN", arm="D-R0", library="D20")))
        c = dict(output=str(root / "controls"), current_best=str(best), phase="gpu", library="D20",
            capacity_policy="total_params_matching", mlp_descriptor_value_source="raw",
            lightgbm_descriptor_value_source="raw", cpu_threads=1,
            readout_configuration=dict(output=str(main), run="D-final-9M", samples=9_000_000,
                seed=0, arm="9M-D-R0", reference_manifest=str(reference)))
        members = [dict(dataset="qm9", member_uid="original:" + mid, molecule_id=mid,
            source_split="train", source_smiles="C") for mid in ("train", "validation")]
        batches = (SimpleNamespace(member_uids=(("qm9", "original:train"),)),
                   SimpleNamespace(member_uids=(("qm9", "original:validation"),)))
        inputs = [dict(task=task, train=train, validation=validation, batches={"raw": batches},
            n_ref=2., d3_members=members)]
        return c, inputs, prediction

    def score(self):
        return dict(complete=True, mean_normalized_improvement=.1,
            tasks={"qm9.alpha": {"normalized_improvement": .1}},
            paired_bootstrap=dict(groups={"qm9": ["validation"]}, values=[.1] * 1000,
                task_values={"qm9.alpha": [.1] * 1000}))

    def test_gpu_resume_keeps_closed_B_and_fits_only_unclosed_C(self):
        with tempfile.TemporaryDirectory() as directory, patch("tools.d_recipe.resources.execution_site"):
            c, inputs, prediction = self.fixture(directory)
            probe = Mock(side_effect=[(prediction, {"optimization_molecule_uids": ["train"]}), OSError("own interrupted C")])
            with self.assertRaises(OSError):
                panel.run_gpu(c, guard=Mock(), inputs=inputs, probe=probe)
            probe.side_effect = None
            probe.return_value = (prediction, {"optimization_molecule_uids": ["train"]})
            closed = panel.run_gpu(c, guard=Mock(), inputs=inputs, probe=probe)
            with patch.object(panel, "_inputs", side_effect=AssertionError("No repeated source/encoder work")):
                panel.run_gpu(c, guard=Mock(), probe=probe)
            self.assertEqual([call.kwargs["branch"] for call in probe.call_args_list], ["B", "C", "C"])
            self.assertEqual(probe.call_args.kwargs["train_member_keys"], (("qm9", "original:train"),))
            self.assertTrue(closed["A_reused_main_R3"])
            self.assertFalse(closed["encoder_forward_repeated"])

    def test_cpu_resume_reuses_models_and_closed_bootstrap_and_does_not_resample_A(self):
        with tempfile.TemporaryDirectory() as directory, patch("tools.d_recipe.resources.execution_site"), patch.dict(os.environ, SLURM_CPUS_PER_TASK="1"):
            c, inputs, prediction = self.fixture(directory)
            probe = Mock(return_value=(prediction, {"optimization_molecule_uids": ["train"]}))
            panel.run_gpu(c, guard=Mock(), inputs=inputs, probe=probe)
            c["phase"] = "cpu"
            model = Mock()
            model.booster_.model_to_string.return_value = "original fixed-default booster text"
            lightgbm = Mock(return_value=(prediction, {"model": "LightGBM"}, model))
            ridge = Mock(return_value=(prediction, {"selected_alpha": 1.}))
            comparison = Mock(side_effect=[self.score(), OSError("statistics interrupted")])
            with self.assertRaises(OSError):
                panel.run_cpu(c, guard=Mock(), inputs=inputs, lightgbm=lightgbm, ridge=ridge, comparison=comparison)
            comparison.side_effect = lambda *args, **kwargs: self.score()
            closed = panel.run_cpu(c, guard=Mock(), inputs=inputs, lightgbm=lightgbm, ridge=ridge, comparison=comparison)
            panel.run_cpu(c, guard=Mock(), inputs=inputs, lightgbm=lightgbm, ridge=ridge, comparison=comparison)
            lightgbm.assert_called_once()
            ridge.assert_called_once()
            self.assertEqual(comparison.call_count, 5)
            scores = json.loads(Path(closed["scores"]).read_text())
            self.assertEqual(scores["A"], {"existing_A_statistic": True})
            contrast = scores["incremental_comparisons"]["C_vs_B_MLP"]
            self.assertEqual(contrast["additional_bootstrap_draws"], 0)
            self.assertFalse(contrast["decision_input"])
            self.assertNotIn("verdict", contrast)
            self.assertFalse(closed["recipe_selection_changed"])

    def test_unfrozen_recipe_or_different_source_endpoint_cannot_start_any_fit(self):
        with tempfile.TemporaryDirectory() as directory, patch("tools.d_recipe.resources.execution_site"):
            c, inputs, prediction = self.fixture(directory)
            probe = Mock(return_value=(prediction, {}))
            Path(c["current_best"]).write_text(json.dumps(dict(status="PENDING", arm="D-R0", library="D20")))
            with self.assertRaisesRegex(ValueError, "frozen adopted"):
                panel.run_gpu(c, guard=Mock(), inputs=inputs, probe=probe)
            Path(c["current_best"]).write_text(json.dumps(dict(status="FROZEN", arm="D-R0", library="D20")))
            c["readout_configuration"]["run"] = "different-run"
            with self.assertRaisesRegex(ValueError, "different native endpoint"):
                panel.run_gpu(c, guard=Mock(), inputs=inputs, probe=probe)
            probe.assert_not_called()

    def test_confirmation_uses_the_registered_9m_arm_and_selected_library(self):
        with tempfile.TemporaryDirectory() as directory, patch("tools.d_recipe.resources.execution_site"):
            c, _, _ = self.fixture(directory)
            Path(c["current_best"]).write_text(json.dumps(dict(status="FROZEN", arm="D-L2", library="L2")))
            c["library"] = "L2"
            c["readout_configuration"]["arm"] = "9M-D-final"
            panel._context(c, False, Mock())
            c["readout_configuration"]["arm"] = "9M-D-R0"
            with self.assertRaisesRegex(ValueError, "frozen adopted"):
                panel._context(c, False, Mock())
            Path(c["current_best"]).write_text(json.dumps(dict(status="FROZEN", arm="D-R0", library="D20")))
            c["library"] = "D20"
            c["readout_configuration"]["arm"] = "D-R0"
            with self.assertRaisesRegex(ValueError, "frozen adopted"):
                panel._context(c, False, Mock())

    def test_partial_dataset_d3_is_not_accepted_as_complete_control_input(self):
        with tempfile.TemporaryDirectory() as directory:
            c, _, _ = self.fixture(directory)
            partial = Path(directory) / "qm9_d3.json"
            partial.write_text(json.dumps(dict(status="RAW_COMPLETE", dataset_scope=["qm9"], complete_source_population=False)))
            c["d3_manifest"] = str(partial)
            with self.assertRaisesRegex(ValueError, "complete native member D3"):
                panel._inputs(c)
