"""Pairing/endpoint failures must not produce a plausible scientific decision."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "current"))
from tools.d_recipe.compare import compare_runs, paired_scores

TASKS = tuple("task" + str(i) for i in range(7))


def scores(value):
    return dict(complete=True, bootstrap_samples=1000, bootstrap_defined=1000,
        bootstrap_unit="molecule", bootstrap_seed=20261025,
        included_tasks=list(TASKS), tasks={task: {} for task in TASKS},
        architecture_sha256="C1-0-reference", mean_normalized_improvement=value,
        paired_bootstrap=dict(groups={"dataset": ["m1", "m2"]}, seed=20261025,
                              samples=1000, confidence=.95, values=[value] * 1000))


class ComparisonTests(unittest.TestCase):
    def test_existing_aligned_draws_produce_taskbook_loss_below_tau(self):
        result = paired_scores(scores(.399), scores(.4), expected_tasks=TASKS)
        self.assertEqual(result["verdict"], "LOSS")
        self.assertAlmostEqual(result["ci_upper"], -.001)

    def test_different_molecules_or_bootstrap_seed_cannot_be_called_paired(self):
        for mutate in (lambda s: s["paired_bootstrap"]["groups"].update(dataset=["m1", "m3"]),
                       lambda s: s["paired_bootstrap"].update(seed=0),
                       lambda s: s.update(bootstrap_unit="row")):
            a, b = scores(.5), scores(.4)
            mutate(a)
            with self.assertRaises(ValueError):
                paired_scores(a, b, expected_tasks=TASKS)

    def test_six_task_or_incomplete_score_cannot_replace_seven_task_primary(self):
        a, b = scores(.5), scores(.4)
        a["included_tasks"].pop()
        with self.assertRaisesRegex(ValueError, "seven"):
            paired_scores(a, b, expected_tasks=TASKS)
        a = scores(.5)
        a["bootstrap_defined"] = 999
        with self.assertRaisesRegex(ValueError, "Complete"):
            paired_scores(a, b, expected_tasks=TASKS)

    def test_readout_from_different_endpoint_cannot_enter_a_comparison(self):
        a = dict(condition="D", arm="D-L1", seed=0, samples=3000000,
                 run="candidate", output="/candidate", source="PM7", corpus="/corpus.json")
        b = dict(a, arm="D-R0", run="control", output="/control")
        def load(path):
            path = str(path)
            c = a if path.startswith("/candidate/") else b
            if path.endswith("configuration.json"):
                return deepcopy(c)
            if path.endswith("predictions.json"):
                return dict(run=c["run"], samples=1000000)
            return dict(R3=scores(.5))
        with patch("tools.d_recipe.compare._load", side_effect=load), self.assertRaisesRegex(ValueError, "sample endpoint"):
            compare_runs(a, b, expected_tasks=TASKS)

    def test_matched_endpoints_keep_r1_out_of_the_primary_decision(self):
        a = dict(condition="D", arm="D-L1", seed=0, samples=3000000,
                 run="candidate", output="/candidate", source="PM7", corpus="/corpus.json")
        b = dict(a, arm="D-R0", run="control", output="/control")
        def load(path):
            path = str(path)
            c = a if path.startswith("/candidate/") else b
            if path.endswith("configuration.json"):
                return deepcopy(c)
            if path.endswith("predictions.json"):
                return dict(run=c["run"], samples=c["samples"])
            return dict(R3=scores(.5 if c is a else .4),
                        R1=scores(-1. if c is a else .4))
        with patch("tools.d_recipe.compare._load", side_effect=load):
            result = compare_runs(a, b, expected_tasks=TASKS)
        self.assertEqual(result["R3"]["verdict"], "WIN")
        self.assertLess(result["R1_report_only"]["candidate"]["mean_normalized_improvement"], 0)
        self.assertFalse(result["resampling_repeated"])


if __name__ == "__main__":
    unittest.main()
