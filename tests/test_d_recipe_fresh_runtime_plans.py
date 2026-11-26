"""Canonical phase claims and old native identities never authorize fresh runs."""
from copy import deepcopy
import unittest

from test_d_recipe_confirmation_plan import screening, frozen, plan
from test_d_recipe_seed_plan import configuration, comparison
from tools.d_recipe.seed_plan import plan_seed1


RUNTIME = dict(node="old_node", local_node="old_node", gpu_uuid="old_GPU",
    canonical_admission=True, ram_peak_bytes=123, local_future_bytes=456,
    shared_future_bytes={"/share": 789}, reservation_ids=["old_seed0_claim"],
    canonical_phase_admission=dict(job_id="old_actual_job"),
    safe_exit_control=dict(job_id="old_actual_job"), exit_root_log_future_bytes=123,
    continuation_activation="old_execution", execution_backend="ssh_gpu",
    ssh_execution_id="ssh:P_D_old", ssh_runtime_receipt="/old/receipt.json",
    cpu_ssh_provider="/old/provider.py", local_output_root="/tmp/d_recipe_old",
    diagnostic_feature_root="/tmp/d_recipe_old/development_layers")


class DFreshRuntimePlanTests(unittest.TestCase):
    def test_cold_confirmation_requires_new_claims_and_actual_runtime_identity(self):
        source = screening("D-L1"); source.update(deepcopy(RUNTIME))
        before = deepcopy(source)
        result = plan(frozen("D-L1"), selected=source)
        for child in result["configurations"]:
            self.assertFalse(set(child) & set(RUNTIME))
            self.assertTrue(child["resource_admission_pending"])
        self.assertEqual(source, before)
        self.assertEqual(result["configurations"][1]["d_recipe"]["label_parameters"],
                         source["d_recipe"]["label_parameters"])

    def test_only_new_seed_unbinds_runtime_and_existing_control_is_reused(self):
        candidate, control = configuration("D-L1"), configuration("D-R1")
        candidate.update(deepcopy(RUNTIME)); control.update(deepcopy(RUNTIME))
        original = deepcopy((candidate, control))
        registry = dict(schema="D_CONDITIONAL_SEED1_REGISTRY_V1", runs={})
        first = plan_seed1(candidate, control, comparison(candidate, control), registry, output_root="/new")
        for child in first["new_configurations"]:
            self.assertFalse(set(child) & set(RUNTIME))
            self.assertTrue(child["resource_admission_pending"])
            self.assertEqual(child["seed"], 1)
            self.assertEqual(child["seed0_run"], (control if child["arm"] == "D-R1" else candidate)["run"])
            self.assertEqual(child["d_recipe"]["block_weights"], candidate["d_recipe"]["block_weights"])
        second = plan_seed1(candidate, control, comparison(candidate, control),
                            first["registry"], output_root="/new")
        self.assertEqual(second["new_configurations"], [])
        self.assertCountEqual(second["reused_arms"], ["D-R1", "D-L1"])
        self.assertEqual((candidate, control), original)


if __name__ == "__main__":
    unittest.main()

