"""D FT input scope and direct reuse of P primary/control results."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.d_recipe import finetune_statistics_entry as module


def fixture():
    files = {}
    c = dict(run="D_FT_fixture", D_authority=module.AUTHORITY, ready=True,
        registered_main_work_complete=True, selection_change_allowed=False,
        groups={"D_R1_3M": {}}, candidate_configurations={"D_R1_3M": {}},
        scratch={}, scratch_configurations={}, reference={}, frozen={},
        required_complete_summaries=[], contrasts=[])
    binding = dict(scope="registered_3M", arm="D-R1", samples=3000000,
                   pretraining_seed=0, checkpoint="/original/D_R1_3M.pt")
    for name in (None, "D_R1_3M"):
        predictions = c["scratch"] if name is None else c["groups"][name]
        configs = c["scratch_configurations"] if name is None else c["candidate_configurations"][name]
        for task in module.TASKS:
            predictions[task], configs[task] = [], []
            for seed in (0, 1, 2):
                root = "/fixture/" + (name or "P_scratch") + "/" + task + "/" + str(seed)
                filename = root + "/configuration.json"
                source = dict(authority=module.P_AUTHORITY, kind="F", task=task, seed=seed,
                    mode="scratch" if name is None else "full", internal_split_seed=20261112,
                    bootstrap_seed=20261025, output=root, store="original_R3_store",
                    reference_manifest="original_random_R3", registered_main_work_complete=True,
                    D_authority=module.AUTHORITY, selection_change_allowed=False,
                    source_binding=dict(role="architecture_only_random_initialization", pretraining_samples_used=0)
                        if name is None else deepcopy(binding))
                files[filename] = source
                files[root + "/summary.json"] = dict(status="COMPLETE", configuration=filename)
                predictions[task].append(root + "/prediction.pt"); configs[task].append(filename)
                c["required_complete_summaries"].append(root + "/summary.json")
                c["reference"][task] = ["/original/random/" + task + ".pt"]
    return c, files


class DFinetuneStatisticsTests(unittest.TestCase):
    def test_ordered_scratch_seeds_and_shared_candidate_checkpoint(self):
        c, files = fixture()
        self.assertEqual(module.validate_sources(c, reader=files.__getitem__)["D_R1_3M"]["arm"], "D-R1")
        path = c["scratch_configurations"][module.TASKS[0]][0]
        files[path]["seed"] = 1
        with self.assertRaisesRegex(ValueError, "ordered seed"):
            module.validate_sources(c, reader=files.__getitem__)
        files[path]["seed"] = 0
        other = c["candidate_configurations"]["D_R1_3M"][module.TASKS[1]][2]
        files[other]["source_binding"]["checkpoint"] = "/foreign/checkpoint.pt"
        with self.assertRaisesRegex(ValueError, "mix different"):
            module.validate_sources(c, reader=files.__getitem__)

    def test_closed_primary_control_is_reused_and_admission_restored_on_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            c, _ = fixture(); c["output"] = tmp
            c["contrasts"] = [dict(left="D_R1_3M", right="D_R0_3M", right_primary=str(Path(tmp) / "control.json"))]
            binding = dict(scratch={}, random_reference={}, conditions={}, frozen={}, scientific_protocol="original")
            primary = dict(status="COMPLETE", retained=dict(identity=dict(input_identity=binding)))
            Path(tmp, "primary.json").write_text(json.dumps(primary))
            Path(tmp, "primary_complete.json").write_text(json.dumps(dict(status="COMPLETE")))
            Path(tmp, "control.json").write_text(json.dumps(primary))
            calls = []
            original_admit = object()
            def contrast(a, left, right, task, *, right_primary):
                calls.append((left, right, task, right_primary))
                return dict(left=left, right=right, task=task, delta_seed_mean=.1)
            entry = SimpleNamespace(require_cpu_admission=original_admit,
                run=lambda c: self.fail("Closed primary must not be resampled"),
                bindings=lambda c: binding, paired_contrast=contrast)
            with patch.object(module, "validate_sources", return_value=dict(source="original")):
                result = module.run(c, entry=entry, admit=lambda c: None)
                self.assertFalse(result["selection_change_allowed"])
                self.assertEqual(len(calls), 4)
                self.assertEqual(module.run(c, entry=entry, admit=lambda c: None), result)
                self.assertEqual(len(calls), 4)
            self.assertIs(entry.require_cpu_admission, original_admit)
            def stop(config):
                self.assertIs(entry.require_cpu_admission, new_admit)
                raise RuntimeError("fixture interruption")
            new_admit = lambda c: None
            entry.run = stop
            with self.assertRaisesRegex(RuntimeError, "interruption"):
                with module.installed_admission(entry, new_admit):
                    entry.run(c)
            self.assertIs(entry.require_cpu_admission, original_admit)


if __name__ == "__main__":
    unittest.main()

