"""Actual-profile authority and explicit uncertain full-stage planning."""
from __future__ import annotations

import math

from workflows.data_v1_final.execution.queue_v1 import shared


SCOPE = "sb5_identity_full_source_roles_after_profile_v1"
PROFILE_JOB = "4521092"
PROFILE_RECORDS, PROFILE_FORMAL = 232234, 65536
FULL_FORMAL, EMBARGO, FULL_RECORDS, ROW_GROUPS = 11231854, 4900, 11398552, 86
CAP, SPILL, WALL = 16 * 1024 ** 3, 6 * 1024 ** 3, 14400
CONSERVATIVE_SECONDS, SOFT_SECONDS = 64 * 60, 96 * 60
MEMORY_POLICY = "SLURM_DEFAULT_UNSPECIFIED"
EXPECTED_DATASETS = {"v1_all_roles_and_embargo": 11236754, "som_cyp": 2003, "som_az": 120,
    "qm7": 7165, "qm9": 133885, "expansionrx": 7608, "moleculenet_bace": 1513,
    "moleculenet_bbbp": 2050, "moleculenet_clintox": 1484, "moleculenet_esol": 1128,
    "moleculenet_freesolv": 642, "moleculenet_lipophilicity": 4200}


def validate_profile(profile):
    wanted = dict(EXPECTED_DATASETS, v1_all_roles_and_embargo=PROFILE_FORMAL + EMBARGO)
    shared.need(profile["schema"] == "SB5_IDENTITY_EXPORT_RECEIPT_V4" and profile["job_id"] == PROFILE_JOB and
        profile["status"] == "LOCAL_IDENTITY_PROFILE_COMPLETE_EXTERNAL_PENDING" and profile["mode"] == "profile" and
        profile["uid"] == 1278 and profile["node"] == "compute-0-12" and
        profile["counts"]["records"] == profile["coverage"]["records"] ==
        profile["coverage"]["globally_unique_source_ids"] == PROFILE_RECORDS and profile["dataset_counts"] == wanted,
        "EXACT_ACTUAL4521092_LOCAL_PROFILE_REQUIRED")
    shared.need(profile["coverage"]["v1"]["records"] == PROFILE_FORMAL + EMBARGO and
        profile["coverage"]["v1"]["whole_v1_coverage_claimed"] is False and
        profile["role_semantics"] == "ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY" and
        profile["effective_training_roles_applied"] is False and profile["apply_common_filter"] is False and
        profile["all_source_all_split_decontamination_accepted"] is False and
        profile["pool_UFF_QM_training_release_authorized"] is False and
        len(profile["actual_worker_records"]) == 16 and all(n > 0 for n in profile["actual_worker_records"].values()) and
        sum(profile["actual_worker_records"].values()) == PROFILE_RECORDS and
        profile["new_boundary_tests"] == {"tests_run": 4, "failures": 0, "errors": 0, "real_data_bodies_or_chemistry_used": False},
        "PROFILE_CONSERVATION_SCIENTIFIC_BOUNDARIES_OR_ACTUAL_WORKERS_DIFFER")


def forecast(profile, *, profile_receipt_bytes=0):
    """Planning from actual internal phases; no full-runtime/RSS claim."""
    validate_profile(profile)
    phases = profile["phase_seconds"]
    hashed = phases["complete_source_hashes"]
    nonhash = profile["wall_seconds"] - hashed
    shared.need(hashed > 0 and nonhash > 0 and all(math.isfinite(v) and v >= 0 for v in
        [profile["wall_seconds"], hashed, profile["formal_unit_worker_seconds"], profile["nonformal_unit_worker_seconds"]]),
        "ACTUAL_PROFILE_PHASE_TIMES_REQUIRED")
    ratio = FULL_RECORDS / PROFILE_RECORDS
    coarse_seconds = hashed + nonhash * ratio
    formal_bytes = profile["formal_unit_bytes"] * FULL_FORMAL / PROFILE_FORMAL
    other_bytes = profile["final_owned_output_bytes"] - profile["formal_unit_bytes"]
    shared.need(other_bytes >= 0 and coarse_seconds * 2 <= CONSERVATIVE_SECONDS,
                "ACTUAL_PROFILE_NO_LONGER_FITS_REVIEWED64MIN_PLANNING_ALLOWANCE")
    return {"method": "fixed_actual_hash + all_nonhash_internal_residual * full_records/profile_records",
        "actual_hash_seconds": hashed, "actual_nonhash_internal_seconds": nonhash,
        "actual_profile_internal_seconds": profile["wall_seconds"], "record_ratio": ratio,
        "coarse_planning_seconds_not_actual": coarse_seconds,
        "twice_coarse_planning_seconds": coarse_seconds * 2,
        "conservative_planning_seconds": CONSERVATIVE_SECONDS, "planning_rounding_to64min_is_not_measurement": True,
        "soft_limit_seconds": SOFT_SECONDS, "soft_limit_multiplier": 1.5, "hard_wall_ceiling_seconds": WALL,
        "soft_clock_basis": "PRODUCER_MONOTONIC_AFTER_FRESH_STARTUP",
        "parent_startup_and_natural_drain_costs_accounted_separately": True,
        "global_aggregation_at_full_scale_measured": False, "full_RSS_measured": False,
        "uniform_random_profile_or_confidence_interval_claimed": False,
        "formal_output_linear_bytes": math.ceil(formal_bytes),
        "planning_storage_upper_bytes": math.ceil(2 * formal_bytes + 2 * (other_bytes + profile_receipt_bytes) + SPILL + 256 * 1024 ** 2),
        "storage_multiplier_not_mathematical_compression_bound": True,
        "full_pipeline_cost_forecast_not_measured_parent_cost": True}


def parameters(profile_ref):
    return {"mode": "full", "formal_records_expected": FULL_FORMAL, "all_embargo_records": EMBARGO,
        "all_original_local_records_expected": FULL_RECORDS, "formal_row_groups": list(range(ROW_GROUPS)),
        "small_cohorts": "ALL_ORIGINAL_LOCAL_ROLES_AND_FOLDS", "common_filter_applied": False,
        "targets_or_features_materialized": False, "effective_training_roles_applied": False,
        "role_semantics": "ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY", "accepted_actual_profile": profile_ref,
        "conservative_planning_seconds": CONSERVATIVE_SECONDS, "cost_soft_limit_seconds": SOFT_SECONDS,
        "cost_soft_limit_multiplier": 1.5, "soft_clock_basis": "PRODUCER_MONOTONIC_AFTER_FRESH_STARTUP",
        "new_scope_is_full_science_not_resource_only_profile_migration": True}


def validate_full_plan(plan):
    shared.need(plan["schema"] == "SB5_IDENTITY_EXPORT_PLAN_V4" and plan["status"] == "READY" and
        plan["scope_key"] == SCOPE and plan["scope_parameters"] == parameters(plan["accepted_profile"]["receipt"]) and
        plan["mode"] == "full" and plan["pilot"] is False and plan["formal_row_groups"] == list(range(ROW_GROUPS)) and
        plan["apply_common_filter"] is False and plan["effective_training_roles_applied"] is False and
        plan["role_semantics"] == "ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY" and
        plan["whole_output_cap_bytes"] == CAP and plan["spill_cap_bytes"] == SPILL and
        plan["planning_budget"]["conservative_planning_seconds"] == CONSERVATIVE_SECONDS and
        plan["planning_budget"]["soft_limit_seconds"] == SOFT_SECONDS and
        plan["planning_budget"]["hard_wall_ceiling_seconds"] == WALL,
        "EXACT_SEPARATE_FULL_SCOPE_SOURCE_ROLES_AND_BUDGET_REQUIRED")
