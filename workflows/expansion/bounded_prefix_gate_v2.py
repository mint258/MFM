"""Only a completed full-rule COMMON_PENDING proof may open a 10k prefix pilot."""
from pathlib import Path

from .common import load, require, verify

FORBIDDEN_RELEASES = ("full_source_screening_authorized", "released_candidate_pool_authorized",
                      "decontamination_acceptance_authorized", "uff_or_D_family_export_authorized", "training_authorized")


def validate_scope(plan, submission):
    require(plan.get("schema") == "pubchem_bounded_prefix_plan_v2" and plan.get("status") == "READY",
            "A separately reviewed READY bounded-prefix plan is required")
    require(plan["workers"] == 16 and plan["prefix_start_ordinal"] == 1 and plan["max_input_rows"] == 10000 and
            all(plan[k] is False for k in FORBIDDEN_RELEASES), "COMMON_PENDING authorizes only the first10000 official input rows")
    require(32 * 1024 ** 2 <= plan["peak_output_cap_bytes"] <= 512 * 1024 ** 2, "Unreviewed prefix output cap")
    request = submission["request"]
    require(submission["uid"] == 1278 and request["node"] == "compute-0-20" and request["cpus"] == 16 and
            request["memory_gib"] == 16 and 0 < request["wall_seconds"] <= 3600 and
            request["estimated_peak_output_bytes"] == plan["peak_output_cap_bytes"] and
            request["root_review"]["status"] == "APPROVED" and request["root_review"]["reviewer"] == "root",
            "Root resources or bounded-prefix scope differ")


def validate_full_evidence(plan, receipt, closure, full_plan):
    expected_job = plan["expected_full_job_id"]
    refs = plan["full_gate_refs"]
    require(isinstance(expected_job, str) and expected_job.isdecimal() and receipt["job_id"] == expected_job,
            "An exact actual full-regression job ID is required")
    require(receipt["schema"] == "pubchem_v1_complete_input_regression_full_v3" and receipt["mode"] == "full" and
            receipt["status"] == "FULL_X_RULE_PASS_COMMON_SCOPE_PENDING" and receipt["node"] == "compute-0-20" and
            receipt["uid"] == 1278 and receipt["plan"] == refs["plan"], "Full-rule COMMON_PENDING receipt differs")
    require(full_plan["schema"] == "v1_X_full_regression_execution_plan_v3" and full_plan["status"] == "READY" and
            full_plan["mode"] == "full" and full_plan["workers"] == 16 and
            full_plan["sources"] == receipt["source_refs"] == plan["required_regression_sources"] and
            full_plan["sources"].get("common_population") is None and
            refs["runner"] in full_plan["code_sources"], "Actual full plan/source/runtime proof differs")
    parent = closure["actual_parent"]
    require(closure["status"] == "ROOT_X_FULL_V3_ACTUAL_COMPLETED_COMMON_SCOPE_PENDING" and
            closure["receipt"] == refs["receipt"] and parent["JobIDRaw"] == expected_job and
            parent["State"] == "COMPLETED" and parent["ExitCode"] == "0:0" and parent["AllocCPUS"] == "16" and
            parent["NodeList"] == "compute-0-20", "Actual successful Slurm parent closure required")
    n = 15879477
    scope = receipt["complete_source_coverage"]
    require(receipt["all_original_records"] == receipt["evaluated_records"] == n and
            scope["records"] == scope["unique_records"] == scope["matched_unique_original_ids"] == n and
            scope["complete_original_source_coverage"] is True, "Full proof does not cover every original unique source ID")
    require(all(receipt["counts"][k] == 0 for k in ("native_rule_mismatch", "raw_native_rule_mismatch",
                "enriched_native_rule_mismatch", "enrichment_metadata_mismatch", "unexplained")) and
            all(receipt[k] >= .999 for k in ("chemical_admission_agreement",
                "conditional_geometry_identity_selection_agreement", "conditional_molecule_agreement")) and
            receipt["all_mismatch_details_stored"] is True, "Full proof has unresolved drift, low agreement or missing mismatch detail")
    prior, repaired = receipt["frozen_v1_pilot_comparison"], receipt["closed_v2_pilot_comparison"]
    require(prior["compared_records"] == 8741 and prior["decision_or_portable_changes"] == 0 and
            prior["legacy_replay_changes"] == 0 and prior["cohort_symmetric_difference"] == 0 and
            prior["exact_diagnosed_cohort_records"] == 335 and prior["all_frozen_v1_pilot_records_checked"] is True and
            repaired["compared_records"] == 8741 and repaired["changed_rows"] == 0 and
            repaired["all_v2_boolean_decisions_identical"] is True, "Full proof did not preserve the closed pilot and exact335 cohort")
    workers = receipt["actual_worker_records"]
    require(len(workers) == 16 and all(str(k).isdecimal() and int(k) > 0 and type(v) is int and v > 0 for k, v in workers.items()) and
            sum(workers.values()) == n and len(receipt["worker_pids_observed"]) == 16 and
            set(map(str, receipt["worker_pids_observed"])) == set(map(str, workers)), "Full proof lacks actual sixteen-worker coverage")
    require(receipt["historical_coalesce_applied_to_all_source_records"] is True and
            receipt["original_335_ids_are_regression_checks_not_a_full_scope_whitelist"] is True and
            receipt["rdkit"] == "2025.09.5" and receipt["full_v1_selection_regression_passed"] is False and
            receipt["common_population_scope_bound"] is False and receipt["final_training_or_full_expansion_gate_released"] is False and
            receipt["source_screening_run"] is False and receipt["old_geometry_identity_decisions_held_fixed"] is True and
            receipt["original_lmdb_opened_or_modified"] is False, "COMMON_PENDING must not release a formal pool, UFF or training gate")
    return {"schema": "FULL_X_COMMON_PENDING_TO_BOUNDED_PREFIX_AUTHORIZATION_V2", "full_job_id": expected_job,
            "full_receipt": refs["receipt"], "full_actual_closure": refs["actual_closure"],
            "authorized_scope": "OFFICIAL_RAW_FIRST10000_INPUT_ROWS_ONLY", "prefix_start_ordinal": 1,
            "max_input_rows": 10000, "common_scope_pending": True,
            **{k: False for k in FORBIDDEN_RELEASES}}


def authorize_full_gate(plan, submission):
    validate_scope(plan, submission)
    refs = plan["full_gate_refs"]
    require(set(refs) == {"receipt", "actual_closure", "plan", "runner"}, "Exact small full-gate proof references required")
    declared = {r["path"]: r for r in submission["request"]["source_references"]}
    for ref in refs.values():
        require(ref["bytes"] <= 8 * 1024 ** 2 and declared.get(ref["path"]) == ref,
                "Root did not bind a small full-gate proof; large output bodies must not enter this path")
        verify(ref)
    require(Path(refs["runner"]["path"]).name == "regression_x_full_v3.py", "Wrong full-rule runner proof")
    return validate_full_evidence(plan, load(refs["receipt"]["path"]), load(refs["actual_closure"]["path"]), load(refs["plan"]["path"]))
