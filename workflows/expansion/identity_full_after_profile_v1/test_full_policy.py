"""Three incremental metadata/budget boundaries; no bodies or scientific work."""
import copy
import tempfile
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from . import policy, runtime


def fixture_profile():
    datasets = dict(policy.EXPECTED_DATASETS, v1_all_roles_and_embargo=70436)
    return {"schema": "SB5_IDENTITY_EXPORT_RECEIPT_V4", "job_id": "4521092", "mode": "profile",
        "status": "LOCAL_IDENTITY_PROFILE_COMPLETE_EXTERNAL_PENDING", "uid": 1278, "node": "compute-0-12",
        "counts": {"records": 232234}, "coverage": {"records": 232234, "globally_unique_source_ids": 232234,
            "v1": {"records": 70436, "whole_v1_coverage_claimed": False}}, "dataset_counts": datasets,
        "role_semantics": "ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY", "effective_training_roles_applied": False,
        "apply_common_filter": False, "all_source_all_split_decontamination_accepted": False,
        "pool_UFF_QM_training_release_authorized": False,
        "actual_worker_records": {str(i): 232234 - 15 if i == 0 else 1 for i in range(16)},
        "new_boundary_tests": {"tests_run": 4, "failures": 0, "errors": 0, "real_data_bodies_or_chemistry_used": False},
        "phase_seconds": {"complete_source_hashes": 102.06592186167836}, "wall_seconds": 138.50787906348705,
        "formal_unit_worker_seconds": 6.526868797838688, "nonformal_unit_worker_seconds": 61.98315993696451,
        "formal_unit_bytes": 1005186, "final_owned_output_bytes": 14175997}


def fixture_plan():
    ref = {"path": "/synthetic/profile.json", "bytes": 1, "sha256": "0" * 64}
    return {"schema": "SB5_IDENTITY_EXPORT_PLAN_V4", "status": "READY", "scope_key": policy.SCOPE,
        "scope_parameters": policy.parameters(ref), "mode": "full", "pilot": False,
        "formal_row_groups": list(range(86)), "apply_common_filter": False, "effective_training_roles_applied": False,
        "role_semantics": "ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY", "whole_output_cap_bytes": policy.CAP,
        "spill_cap_bytes": policy.SPILL, "planning_budget": policy.forecast(fixture_profile()),
        "accepted_profile": {"receipt": ref}}


class FullIdentityPolicyBoundaries(unittest.TestCase):
    def test_forecast_uses_actual_nonhash_but_does_not_claim_measured_full_runtime(self):
        estimate = policy.forecast(fixture_profile(), profile_receipt_bytes=149751)
        self.assertGreater(estimate["coarse_planning_seconds_not_actual"], 31 * 60)
        self.assertLess(estimate["twice_coarse_planning_seconds"], 64 * 60)
        self.assertEqual(estimate["soft_limit_seconds"], estimate["conservative_planning_seconds"] * 1.5)
        self.assertEqual(estimate["hard_wall_ceiling_seconds"], 4 * 3600)
        self.assertFalse(estimate["global_aggregation_at_full_scale_measured"])
        self.assertFalse(estimate["full_RSS_measured"])
        self.assertLess(estimate["planning_storage_upper_bytes"], policy.CAP)

    def test96min_cost_stop_is_durable_once_and_sends_no_signal(self):
        with tempfile.TemporaryDirectory() as directory:
            stop = threading.Event()
            budget = runtime.RuntimeBudget(Path(directory), fixture_plan(),
                {"job_id": "synthetic", "request": {"wall_seconds": policy.WALL}}, stop)
            with patch.object(runtime.time, "monotonic", return_value=budget.started + policy.SOFT_SECONDS - .1):
                budget._cost_check()
            self.assertFalse(stop.is_set())
            with patch.object(runtime.time, "monotonic", return_value=budget.started + policy.SOFT_SECONDS):
                budget._cost_check()
                budget._cost_check()
                result = budget.receipt()
            self.assertTrue(stop.is_set())
            self.assertEqual(len(list(Path(directory).glob("cost_soft_deadline_notice.json"))), 1)
            self.assertTrue(result["cost_soft_limit_reached"])
            self.assertFalse(result["forced_signals_sent"])
            self.assertTrue(result["96min_is_not_absolute_process_or_Slurm_wall_guarantee"])

    def test_profile_mode_common_filter_or_shortened_formal_scope_cannot_enter_full(self):
        plan = fixture_plan()
        policy.validate_full_plan(plan)
        for key, value in (("mode", "profile"), ("pilot", True), ("apply_common_filter", True), ("formal_row_groups", list(range(16)))):
            changed = copy.deepcopy(plan)
            changed[key] = value
            with self.assertRaisesRegex(ValueError, "EXACT_SEPARATE_FULL_SCOPE"):
                policy.validate_full_plan(changed)


if __name__ == "__main__":
    unittest.main()
