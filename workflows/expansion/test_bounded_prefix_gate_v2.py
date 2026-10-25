"""Small authority checks: COMMON_PENDING never releases beyond the raw prefix."""
from copy import deepcopy
import unittest

from . import bounded_prefix_gate_v2 as gate


def fixtures():
    ref = {"path": "/synthetic/full_receipt.json", "bytes": 10, "sha256": "a" * 64}
    runner = {"path": "/synthetic/regression_x_full_v3.py", "bytes": 10, "sha256": "b" * 64}
    plan_ref = {"path": "/synthetic/full_plan.json", "bytes": 10, "sha256": "c" * 64}
    sources = {"original_index": {"path": "/synthetic/original.parquet", "bytes": 2005784925, "sha256": "d" * 64},
               "relaxed_quality": {}, "formal_population": {}, "common_population": None}
    plan = {"schema": "pubchem_bounded_prefix_plan_v2", "status": "READY", "workers": 16,
            "prefix_start_ordinal": 1, "max_input_rows": 10000, "peak_output_cap_bytes": 512 * 1024 ** 2,
            "expected_full_job_id": "4520999", "required_regression_sources": sources,
            "full_gate_refs": {"receipt": ref, "plan": plan_ref, "runner": runner, "actual_closure": {}},
            **{k: False for k in gate.FORBIDDEN_RELEASES}}
    submission = {"uid": 1278, "request": {"node": "compute-0-20", "cpus": 16, "memory_gib": 16,
                  "wall_seconds": 3600, "estimated_peak_output_bytes": 512 * 1024 ** 2,
                  "root_review": {"status": "APPROVED", "reviewer": "root"}, "source_references": []}}
    n = 15879477
    worker_counts = {str(i + 1): n // 16 + int(i < n % 16) for i in range(16)}
    receipt = {"schema": "pubchem_v1_complete_input_regression_full_v3", "mode": "full",
               "status": "FULL_X_RULE_PASS_COMMON_SCOPE_PENDING", "job_id": "4520999", "uid": 1278,
               "node": "compute-0-20", "plan": plan_ref, "source_refs": sources,
               "all_original_records": n, "evaluated_records": n,
               "complete_source_coverage": {"records": n, "unique_records": n, "matched_unique_original_ids": n,
                                             "complete_original_source_coverage": True},
               "counts": {k: 0 for k in ("native_rule_mismatch", "raw_native_rule_mismatch", "enriched_native_rule_mismatch",
                                         "enrichment_metadata_mismatch", "unexplained")},
               "chemical_admission_agreement": 1.0, "conditional_geometry_identity_selection_agreement": 1.0,
               "conditional_molecule_agreement": 1.0, "all_mismatch_details_stored": True,
               "frozen_v1_pilot_comparison": {"compared_records": 8741, "decision_or_portable_changes": 0,
                                               "legacy_replay_changes": 0, "cohort_symmetric_difference": 0,
                                               "exact_diagnosed_cohort_records": 335, "all_frozen_v1_pilot_records_checked": True},
               "closed_v2_pilot_comparison": {"compared_records": 8741, "changed_rows": 0,
                                               "all_v2_boolean_decisions_identical": True},
               "actual_worker_records": worker_counts, "worker_pids_observed": list(range(1, 17)),
               "historical_coalesce_applied_to_all_source_records": True,
               "original_335_ids_are_regression_checks_not_a_full_scope_whitelist": True,
               "rdkit": "2025.09.5", "full_v1_selection_regression_passed": False,
               "common_population_scope_bound": False, "final_training_or_full_expansion_gate_released": False,
               "source_screening_run": False, "old_geometry_identity_decisions_held_fixed": True,
               "original_lmdb_opened_or_modified": False}
    closure = {"status": "ROOT_X_FULL_V3_ACTUAL_COMPLETED_COMMON_SCOPE_PENDING", "receipt": ref,
               "actual_parent": {"JobIDRaw": "4520999", "State": "COMPLETED", "ExitCode": "0:0", "AllocCPUS": "16", "NodeList": "compute-0-20"}}
    full_plan = {"schema": "v1_X_full_regression_execution_plan_v3", "status": "READY", "mode": "full",
                 "workers": 16, "sources": sources, "code_sources": [runner]}
    return plan, submission, receipt, closure, full_plan


class BoundedPrefixGateTests(unittest.TestCase):
    def test_common_pending_grants_only_exact_prefix_and_no_release_switch(self):
        plan, submission, receipt, closure, full_plan = fixtures()
        gate.validate_scope(plan, submission)
        scope = gate.validate_full_evidence(plan, receipt, closure, full_plan)
        self.assertEqual(scope["authorized_scope"], "OFFICIAL_RAW_FIRST10000_INPUT_ROWS_ONLY")
        self.assertTrue(scope["common_scope_pending"])
        for field in gate.FORBIDDEN_RELEASES:
            self.assertIs(scope[field], False)
            altered = deepcopy(plan); altered[field] = True
            with self.assertRaises(ValueError): gate.validate_scope(altered, submission)
        for field, value in (("max_input_rows", 10001), ("prefix_start_ordinal", 2)):
            altered = deepcopy(plan); altered[field] = value
            with self.assertRaises(ValueError): gate.validate_scope(altered, submission)

    def test_noncompleted_or_wrong_job_or_unbound_proof_never_authorizes(self):
        plan, submission, receipt, closure, full_plan = fixtures()
        for field, value in (("State", "FAILED"), ("ExitCode", "1:0"), ("JobIDRaw", "4520998")):
            altered = deepcopy(closure); altered["actual_parent"][field] = value
            with self.assertRaises(ValueError): gate.validate_full_evidence(plan, receipt, altered, full_plan)
        with self.assertRaisesRegex(ValueError, "Root did not bind"):
            gate.authorize_full_gate(plan, submission)

    def test_status_string_cannot_hide_incomplete_ids_drift_or_missing_detail(self):
        plan, _, receipt, closure, full_plan = fixtures()
        variants = []
        a = deepcopy(receipt); a["complete_source_coverage"]["unique_records"] -= 1; variants.append(a)
        a = deepcopy(receipt); a["counts"]["raw_native_rule_mismatch"] = 1; variants.append(a)
        a = deepcopy(receipt); a["all_mismatch_details_stored"] = False; variants.append(a)
        a = deepcopy(receipt); a["conditional_molecule_agreement"] = .998; variants.append(a)
        a = deepcopy(receipt); a["frozen_v1_pilot_comparison"]["cohort_symmetric_difference"] = 1; variants.append(a)
        a = deepcopy(receipt); a["final_training_or_full_expansion_gate_released"] = True; variants.append(a)
        for altered in variants:
            with self.assertRaises(ValueError): gate.validate_full_evidence(plan, altered, closure, full_plan)


if __name__ == "__main__":
    unittest.main()
