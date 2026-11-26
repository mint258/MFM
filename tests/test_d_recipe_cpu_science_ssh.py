"""Actual CPU allocation, preserved GPU input binding and reversible dispatch."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.d_recipe.cpu_science_ssh import (authenticated_site, cpu_configuration,
                                           dispatch, thread_limit)


class DCPUScienceSSHTests(unittest.TestCase):
    def test_exact_input_snapshot_and_authenticated_cpu_site_restore(self):
        source = dict(phase="gpu", node="original_GPU_node", output="/owned/result",
                      safe_exit_control=dict(job_id="actual_old_GPU_job"))
        c = cpu_configuration("development_panel", source)
        self.assertEqual({k:v for k,v in c.items() if k != "phase"},
                         {k:v for k,v in source.items() if k != "phase"})
        original = object(); resources = SimpleNamespace(execution_site=original)
        verified = []
        with self.assertRaisesRegex(ValueError, "exact CPU"):
            with authenticated_site(resources, c, lambda: verified.append(True)):
                resources.execution_site(c, cpu=True)
                resources.execution_site(dict(c), cpu=True)
        self.assertEqual(verified, [True])
        self.assertIs(resources.execution_site, original)
        calls = []
        fake = SimpleNamespace(run_cpu=lambda config, **kwargs: calls.append((config, kwargs)))
        dispatch("development_panel", c, "actual_CPU_guard", 1, importer=lambda name: fake)
        self.assertEqual(calls, [(c, dict(guard="actual_CPU_guard", allocated_cpus=1))])
        with self.assertRaises(ValueError):
            dispatch("train", c, None, 1, importer=lambda name: self.fail("No GPU dispatch"))

    def test_original_development_CPU_phase_works_without_fake_Slurm_allocation(self):
        from tools.d_recipe import development_panel as panel
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp); (output / "scores.json").write_text("{}")
            c = dict(cpu_threads=8)
            state = dict(status="GPU_DEVELOPMENT_READOUTS_COMPLETE_WAITING_CPU", cells={})
            guard = SimpleNamespace(check=lambda path: None)
            context = ({}, output, output / "summary.json", {}, state, guard, {})
            with patch.object(panel, "_context", return_value=context), patch.dict(os.environ, {}, clear=True), \
                    patch.object(panel.torch, "set_num_threads") as setter:
                result = panel.run_cpu(c, guard=guard, inputs=[], allocated_cpus=1)
                setter.assert_called_once_with(1)
            self.assertEqual(result["cpu_threads_effective"], 1)
            self.assertEqual(result["status"], "COMPLETE")
            self.assertEqual(c, dict(cpu_threads=8))
            self.assertEqual(json.loads((output / "summary.json").read_text())["cpu_threads_effective"], 1)
        for requested, allocated in ((0, 1), (1, 0), (True, 1)):
            with self.assertRaises(ValueError):thread_limit(requested, allocated)


if __name__ == "__main__":
    unittest.main()

