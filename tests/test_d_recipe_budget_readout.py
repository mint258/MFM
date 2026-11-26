"""Check actual source gates and single consumption across partial handoffs."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.d_recipe.budget_readout import AUTHORITY, WAITING, finalize_cpu, run_gpu


class DBudgetReadoutTests(unittest.TestCase):
    def test_native_success_gate_and_completed_prediction_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def put(path, value, unused=None):
                path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            sources = {}
            for arm in ("9M-D-R0", "9M-D-final"):
                folder = root / arm
                c = dict(arm=arm, run=arm, seed=0, condition="D", samples=9000000,
                         output=str(folder), d_recipe=dict(scientific_binding=dict(arm=arm)))
                sources[arm] = str(folder / "configuration.json")
                put(sources[arm], c)
                put(folder / "summary.json", dict(run=arm, samples=9000000,
                    status="COMPLETE", statistics_complete=True))
            c = dict(run="D_final_budget_3M", samples=3000000, source_run="9M-D-final",
                source_configuration=sources["9M-D-final"], source_training_budget=9000000,
                closed_confirmation_configurations=sources, checkpoint="actual_original_3M.pt",
                output=str(root / "readout"), authority=AUTHORITY, budget_curve=True,
                descriptive_only=True, new_training=False, new_seeds=False,
                layer=6, representation="H0", persist_features=False, readout_seed=0,
                source_scientific_binding=dict(arm="9M-D-final"), gpu_uuid="fixture_only")
            calls = []
            def evaluate(candidate):
                calls.append(candidate)
                put(Path(candidate["output"]) / "predictions.json",
                    dict(run=c["run"], samples=c["samples"]))
            resolver = lambda source, samples: "actual_original_3M.pt"
            result = run_gpu(c, evaluator=evaluate, resolver=resolver, publish=put)
            self.assertEqual(result["status"], WAITING)
            self.assertFalse(result["training_performed"])
            # Simulate an interruption after predictions but before the small
            # producer summary: the second call must not run the encoder again.
            (Path(c["output"]) / "summary.json").unlink()
            run_gpu(c, evaluator=evaluate, resolver=resolver, publish=put)
            self.assertEqual(len(calls), 1)
            path = root / "9M-D-R0/summary.json"
            value = json.loads(path.read_text()); value["statistics_complete"] = False; put(path, value)
            with self.assertRaisesRegex(ValueError, "finish first"):
                run_gpu(c, evaluator=evaluate, resolver=resolver, publish=put)
            self.assertEqual(len(calls), 1)

    def test_CPU_score_once_and_manifest_identity_before_bootstrap(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            def put(path, value):
                path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            c = dict(run="budget3M", samples=3000000, source_run="whole9M",
                     output=str(output), budget_curve=True)
            initial = dict(run=c["run"], samples=c["samples"], source_run=c["source_run"], status=WAITING)
            put(output / "summary.json", initial)
            put(output / "readout/predictions.json", dict(run="foreign", samples=3000000))
            calls = []
            def score(candidate):
                calls.append(candidate)
                values = {name: dict(complete=True, bootstrap_samples=1000, bootstrap_defined=1000,
                                     paired_bootstrap=dict(seed=20261025)) for name in ("R1", "R3")}
                put(output / "readout/scores.json", values)
            kwargs = dict(execution_id="fixture_native_handle", node="fixture_CPU", scorer=score, publish=put)
            with self.assertRaisesRegex(ValueError, "different point"):
                finalize_cpu(c, **kwargs)
            self.assertFalse(calls)
            put(output / "readout/predictions.json", dict(run=c["run"], samples=3000000))
            result = finalize_cpu(c, **kwargs)
            self.assertEqual(result["statistics_backend"], "ssh_cpu")
            self.assertEqual(result["statistics_execution_id"], "fixture_native_handle")
            self.assertTrue(result["statistics_complete"])
            put(output / "summary.json", initial)
            finalize_cpu(c, **kwargs)
            self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()

