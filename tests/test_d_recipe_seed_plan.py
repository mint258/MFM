"""Conditional seed1 scope and reuse of a shared control."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "current"))
from tools.d_recipe.seed_plan import plan_seed1
from tools.d_recipe.training import prepare_runtime


def configuration(arm="D-R0"):
    return prepare_runtime(dict(condition="D", arm=arm, run=arm + "_seed0", seed=0, samples=3000000,
        batch_size=32, microbatch_size=32, lr=3e-4, weight_decay=.01, betas=[.9, .95],
        warmup_fraction=.02, distance_bias="C1-0", schedule="cosine", p_recipe={},
        clip_calibration=dict(calibration_samples=150000, window_start_samples=60000,
                              initial_clip=281.7, quantile=.99),
        output="/D/" + arm, source="PM7", corpus="/corpus.json",
        d_recipe=dict(enabled=True, library=arm[2:] if arm in ("D-L1", "D-L2") else "D20",
                      block_weights=dict(graph_2d=.6, molecule_3d=.3, atom_sasa=.1))))


def comparison(a, b, verdict="WIN"):
    return dict(candidate=a["run"], control=b["run"], seed=0, samples=3000000,
                R3=dict(verdict=verdict))


class SeedPlanTests(unittest.TestCase):
    def registry(self):
        return dict(schema="D_CONDITIONAL_SEED1_REGISTRY_V1", runs={})

    def test_tie_or_loss_requests_no_runs_and_does_not_modify_the_registry(self):
        a, b, state = configuration("D-L1"), configuration(), self.registry()
        before = deepcopy(state)
        for verdict in ("TIE", "LOSS"):
            result = plan_seed1(a, b, comparison(a, b, verdict), state, output_root="/seed1")
            self.assertEqual(result["new_configurations"], [])
        self.assertEqual(state, before)

    def test_winner_creates_fresh_runs_with_seed1_binding_and_no_resume(self):
        a, b = configuration("D-L1"), configuration()
        a.update(resume="/seed0.pt", resume_samples=3000000, handoff_ack="/old_ack")
        before = deepcopy(a)
        result = plan_seed1(a, b, comparison(a, b), self.registry(), output_root="/seed1")
        self.assertEqual(a, before)
        self.assertEqual(len(result["new_configurations"]), 2)
        for child in result["new_configurations"]:
            self.assertEqual(child["seed"], 1)
            self.assertEqual(child["d_recipe"]["scientific_binding"]["seed"], 1)
            self.assertNotIn("resume", child)
            self.assertNotIn("handoff_ack", child)

    def test_two_winning_libraries_request_the_shared_control_only_once(self):
        a, b, control = configuration("D-L1"), configuration("D-L2"), configuration()
        first = plan_seed1(a, control, comparison(a, control), self.registry(), output_root="/seed1")
        second = plan_seed1(b, control, comparison(b, control), first["registry"], output_root="/seed1")
        self.assertEqual([c["arm"] for c in second["new_configurations"]], ["D-L2"])
        self.assertEqual(second["reused_arms"], ["D-R0"])
        control = dict(control, run=control["run"] + "_infra_resume")
        third = plan_seed1(b, control, comparison(b, control), second["registry"], output_root="/seed1")
        self.assertEqual(third["new_configurations"], [])

    def test_changed_scientific_condition_cannot_reuse_or_duplicate_the_same_control(self):
        a, control = configuration("D-L1"), configuration()
        first = plan_seed1(a, control, comparison(a, control), self.registry(), output_root="/seed1")
        other = deepcopy(control)
        other["d_recipe"]["scientific_binding"].pop("corpus")
        other["corpus"] = "/different_corpus.json"
        with self.assertRaisesRegex(ValueError, "different scientific"):
            plan_seed1(a, other, comparison(a, other), first["registry"], output_root="/seed1")

    def test_seed1_cannot_request_a_third_seed_or_a_9m_confirmation_seed(self):
        a, control = configuration("D-L1"), configuration()
        for changes in (dict(seed=1), dict(arm="9M-D-final", samples=9000000)):
            parent = dict(a, **changes)
            with self.assertRaises(ValueError):
                plan_seed1(parent, control, comparison(parent, control), self.registry(), output_root="/seed1")

    def test_masked_seed1_requires_the_frozen_independent_mask_seed(self):
        a, control = configuration("D-L1"), configuration("D-L1")
        a["arm"], a["run"] = "D-K1", "D-K1_seed0"
        a["d_recipe"].update(graph_mask_enabled=True, mask_seed=12, adopted_wide=True)
        a["d_recipe"]["scientific_binding"]["arm"] = "D-K1"
        with self.assertRaisesRegex(ValueError, "dedicated mask seed"):
            plan_seed1(a, control, comparison(a, control), self.registry(), output_root="/seed1")
        result = plan_seed1(a, control, comparison(a, control), self.registry(), output_root="/seed1",
                            mask_seeds={"D-K1": 13})
        self.assertEqual(result["registry"]["runs"]["D-K1"]["configuration"]["d_recipe"]["mask_seed"], 13)


if __name__ == "__main__":
    unittest.main()
