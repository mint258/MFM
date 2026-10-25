"""Root metadata-only SB5 profile/full export/raw-inventory stage specs.

Produces plans and queue stage specs, never scripts/requests, probes, science,
downloads, quota observations or submissions. All pins come from actual files.
"""
from __future__ import annotations

import argparse
import csv
import io
import math
from pathlib import Path
import re

from workflows.data_v1_final.execution.queue_v1 import shared
from . import full_queue_v1 as execution


ROOT, REPO = shared.ROOT, shared.REPO
STAGES = {"identity-profile": ("sb5_identity_profile_all_roles_v3", "identity_v3.export", True, 2 * 1024 ** 3),
          "identity-full": ("sb5_identity_full_all_roles_v3", "identity_v3.export", False, 16 * 1024 ** 3),
          "raw-inventory": ("sb5_pubchem_raw_inventory_v1", "pubchem_full_v1.inventory", False, 10 * 1024 ** 3)}


def verify(pin):
    execution.verify_small(pin)


def unique(pins):
    result = {}
    for pin in pins:
        shared.need(pin["path"] not in result or result[pin["path"]] == pin, "CONFLICTING_SMALL_SOURCE_PIN")
        result[pin["path"]] = pin
    return list(result.values())


def parent_from_account(account_path, job_id):
    account = shared.load(account_path)
    shared.need(account["schema"] == "DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2" and account["query_returncode"] == 0,
                "ACTUAL_ACCOUNTING_REQUIRED")
    verify(account["raw_sacct_reference"])
    parents = [row for row in account["actual_parents"] if row["JobIDRaw"] == job_id]
    raw = [row for row in csv.DictReader(io.StringIO(shared.read_small(account["raw_sacct_reference"]["path"]).decode()), delimiter="|")
           if row["JobIDRaw"] == job_id]
    shared.need(len(parents) == len(raw) == 1 and parents[0]["State"] == "COMPLETED" and parents[0]["ExitCode"] == "0:0" and
                parents[0]["Partition"] == "cpu" and int(parents[0]["AllocCPUS"]) == 16 and
                all(parents[0][key] == raw[0][key] for key in ("State", "ExitCode", "ElapsedRaw", "AllocCPUS", "NodeList", "Partition")),
                "EXACT_COMPLETED_ACTUAL_PARENT_REQUIRED")
    verify(parents[0]["receipt_reference"])
    submission = shared.load(parents[0]["receipt_reference"]["path"])
    shared.need(submission["job_id"] == job_id and submission["sbatch_returncode"] == 0, "ACTUAL_SUBMISSION_PARENT_BINDING")
    return parents[0], account["raw_sacct_reference"]


def materialize(stage, tag, goal_authority, accounting_path, profile_receipt=None, large_run_reviewed=False):
    shared.on_login()
    shared.need(stage in STAGES and re.fullmatch(r"[a-z0-9_]+", tag), "EXACT_STAGE_AND_NEW_TAG_REQUIRED")
    shared.need(Path(__file__).absolute() == REPO / "workflows/expansion/materialize_full_sources_v1.py", "REVIEWED_ROOT_REPOSITORY_REQUIRED")
    scope, module, pilot, cap = STAGES[stage]
    stem = scope + "_" + tag
    control = ROOT / "control/queue_specs"
    plan_path, spec_path = control / (stem + "_plan.json"), control / (stem + ".json")
    closure_path = control / (stem + "_547_actual_closure.json")
    output = ROOT / "artifacts/expansion" / ("raw" if stage == "raw-inventory" else "identity") / stem
    for path in (plan_path, spec_path, closure_path, output):
        shared.need(not path.exists() and not path.is_symlink(), "NEW_METADATA_AND_OUTPUT_DESTINATIONS_ONLY:" + str(path))
    producer_path = ROOT / "artifacts/expansion/identity/identity_source_pins_cpu_v2/receipt.json"
    producer = shared.load(producer_path)
    catalog_ref = producer["source_catalog"]
    verify(catalog_ref)
    catalog = shared.load(catalog_ref["path"])
    parent, raw_sacct = parent_from_account(accounting_path, "4520547")
    shared.need(producer["job_id"] == "4520547" and producer["status"] == "CURRENT_BOUND_INPUT_PINS_COMPLETE" and
                producer["node"] == parent["NodeList"] == "compute-0-17" and len(producer["outputs"]) == 76 and
                not producer["pending_locators"] and not producer["blocking_source_ids"], "ACTUAL_ALL76_CURRENT_INPUT_PINS_REQUIRED")
    producer_ref = shared.pin(producer_path)
    closure = {"schema": "DATA_V1_IDENTITY_INPUT_PINS_ACTUAL_CLOSURE_V3", "status": "ACTUAL_PRODUCER_COMPLETED_NOT_IDENTITY_ACCEPTANCE",
               "receipt": producer_ref, "actual_parent": parent, "accounting_reference": shared.pin(accounting_path),
               "raw_sacct_reference": raw_sacct, "identity_export_or_decontamination_acceptance_claimed": False}
    anchors = {"guide": shared.pin(shared.PROJECT / "数据线工作流程：v1 定稿与数据扩充（Codex B）.md"),
               "root_continuous_goal": shared.pin(goal_authority),
               "full_x_receipt": shared.pin(ROOT / "artifacts/expansion/regression/full_v3/receipt.json"),
               "full_x_actual_closure": shared.pin(ROOT / "control/x_full_v3_actual_closure_v1.json"),
               "identity_input_pins": producer_ref,
               "compat_receipt": shared.pin(ROOT / "artifacts/expansion/diagnostics/paired_prefix_cpu_v2/candidate_evaluation/receipt.json"),
               "compat_actual_closure": shared.pin(ROOT / "artifacts/expansion/diagnostics/paired_prefix_compat_actual_v1.json")}
    raw_receipt_ref = shared.pin(ROOT / "artifacts/expansion/raw/pubchem_20261025_v1/attempt_4520348/receipt.json")
    raw = shared.load(raw_receipt_ref["path"])
    prefix_ref = shared.pin(ROOT / "artifacts/expansion/screening/bounded_prefix_v2/receipt.json")
    code_paths = [Path(__file__), REPO / "workflows/expansion/full_queue_v1.py", REPO / "workflows/expansion/common.py",
                  REPO / "workflows/expansion/__init__.py", REPO / "workflows/data_v1_final/execution/queue_v1/shared.py",
                  REPO / "workflows/data_v1_final/execution/queue_v1/queue_contract.py"]
    code_paths += [REPO / "workflows/expansion/test_full_sources_v1.py"]
    code_paths += list((REPO / "workflows/expansion/identity_v3").glob("*.py"))
    code_paths += list((REPO / "workflows/expansion/pubchem_full_v1").glob("*.py"))
    code_paths += [REPO / "workflows/expansion/identity_v2" / name for name in
                   ("__init__.py", "readers_v2.py", "projection_v2.py", "coverage_v2.py")]
    if stage == "raw-inventory":
        data_refs = [raw["file"]]
        extra_sources = [raw_receipt_ref, prefix_ref]
        parameters = {"full_raw_EOF_inventory": True, "chemical_screening_performed": False,
                      "source_snapshot_job": "4520348", "shard_max_records": 250000, "shard_max_bytes": 64 * 1024 ** 2}
        plan = {"schema": "SB5_PUBCHEM_RAW_INVENTORY_PLAN_V1", "raw_receipt": raw_receipt_ref, "raw_file": raw["file"],
                "original_prefix_receipt": prefix_ref, "expected_uncompressed_bytes": raw["gzip"]["uncompressed_bytes_read"],
                "shard_max_records": 250000, "shard_max_bytes": 64 * 1024 ** 2,
                "chemical_screening_performed": False, "pool_release_authorized": False}
    else:
        metadata = [row["reference"] for row in producer["outputs"] if row["kind"] == "metadata_json"]
        data_refs = [row["reference"] for row in producer["outputs"] if row["kind"] != "metadata_json"]
        shared.need(len(metadata) == 3 and len(data_refs) == 73, "EXACT_DISJOINT_METADATA3_BODY73_REQUIRED")
        extra_sources = [catalog_ref, producer_ref, *catalog["metadata_authorities"], *metadata,
                         parent["receipt_reference"], shared.pin(accounting_path), raw_sacct]
        groups = next(row["identity_metadata"]["row_groups"] for row in producer["outputs"] if row["source_id"] == "v1_formal")
        rows = [i * (groups - 1) // 15 for i in range(16)] if pilot else list(range(groups))
        parameters = {"mode": "profile" if pilot else "full", "formal_records_expected": 65536 if pilot else 11231854,
                      "all_embargo_records": 4900, "small_cohorts": "ALL_ORIGINAL_LOCAL_ROLES_AND_FOLDS",
                      "common_filter_applied": False, "targets_or_features_materialized": False}
        plan = {"schema": "SB5_IDENTITY_EXPORT_PLAN_V3", "mode": parameters["mode"], "formal_row_groups": rows,
                "expected_input_pin_job_id": "4520547", "input_pin_receipt": producer_ref,
                "input_pin_actual_closure": None, "source_catalog": catalog_ref, "apply_common_filter": False,
                "source_policy": {"targets_or_features_materialized": False, "all_source_decontamination_accepted": False},
                "unit_output_cap_bytes": cap // 32, "spill_cap_bytes": 256 * 1024 ** 2 if pilot else 6 * 1024 ** 3,
                "worker_result_timeout_seconds": 7200}
        if not pilot:
            shared.need(profile_receipt is not None, "FULL_REQUIRES_ACTUAL_PROFILE_RECEIPT_NOT_A_GUESSED_ESTIMATE")
            profile = shared.load(profile_receipt)
            profile_parent, profile_raw = parent_from_account(accounting_path, profile["job_id"])
            shared.need(profile["schema"] == "SB5_IDENTITY_EXPORT_RECEIPT_V3" and profile["mode"] == "profile" and
                        profile["status"] == "LOCAL_IDENTITY_PROFILE_COMPLETE_EXTERNAL_PENDING" and
                        profile["coverage"]["v1"]["records"] == 70436 and len(profile["actual_worker_records"]) == 16 and
                        profile["new_boundary_tests"]["tests_run"] == 4 and profile["new_boundary_tests"]["errors"] == 0,
                        "ACCEPTED_ACTUAL_PROFILE_CONSERVATION_REQUIRED")
            profile_plan = shared.load(profile["plan"]["path"])
            for pin in profile_plan["code_sources"]:
                verify(pin)
            ratio = 11231854 / 65536
            formal_forecast = math.ceil(profile["formal_unit_bytes"] * ratio)
            other_bytes = profile["final_owned_output_bytes"] - profile["formal_unit_bytes"]
            upper = formal_forecast * 2 + max(0, other_bytes) * 2 + plan["spill_cap_bytes"]
            shared.need(upper <= cap, "ACTUAL_PROFILE_UPPER_STORAGE_FORECAST_EXCEEDS_FIXED16GIB_REVIEW_REQUIRED")
            worker_forecast = profile["formal_unit_worker_seconds"] * ratio + profile["nonformal_unit_worker_seconds"]
            rough_core_hours = (worker_forecast * 2 + 16 * sum(profile["phase_seconds"][key]
                for key in ("complete_source_hashes", "whole_cohort_proof_preparation"))) / 3600
            shared.need(rough_core_hours <= 500 or large_run_reviewed, "ROOT_MUST_REVIEW_ACTUAL_PROFILE_FOR_OVER500_CORE_HOURS")
            shared.need(rough_core_hours <= 64, "PROFILE_FORECAST_EXCEEDS_SINGLE_FOUR_HOUR_ALLOCATION_NEEDS_NEW_SHARDED_SCOPE")
            plan["accepted_profile"] = {"receipt": shared.pin(profile_receipt), "actual_parent": profile_parent,
                "forecast_formal_output_bytes": formal_forecast, "planning_upper_output_bytes": upper,
                "planning_core_hours_upper_before_global_sort_uncertainty": rough_core_hours,
                "global_sort_cost_unmeasured_at_full_scale": True, "large_run_reviewed": large_run_reviewed}
            extra_sources += [shared.pin(profile_receipt), profile["plan"], profile["startup_proof"],
                              profile_parent["receipt_reference"], profile_raw]
    code_refs = unique([shared.pin(Path(path)) for path in code_paths])
    plan.update(status="READY", scope_key=scope, scope_parameters=parameters, pilot=pilot, output_root=str(output),
                whole_output_cap_bytes=cap, code_sources=code_refs, anchors=anchors,
                run_boundary_tests=(pilot or stage == "raw-inventory"),
                common_independence="Chemistry and all-role identity are independent; final common/training remains unreleased")
    execution.validate_scientific_anchors(plan)
    shared.write_new(closure_path, closure)
    if stage != "raw-inventory":
        plan["input_pin_actual_closure"] = shared.pin(closure_path)
        extra_sources.append(plan["input_pin_actual_closure"])
    authority_refs = unique([*anchors.values(), *extra_sources, shared.pin(closure_path)])
    plan["authority_references"] = authority_refs
    for pin in [*code_refs, *authority_refs]:
        verify(pin)
    shared.write_new(plan_path, plan)
    all_sources = unique([*code_refs, *authority_refs, shared.pin(plan_path)])
    shared.need(not {pin["path"] for pin in all_sources}.intersection(pin["path"] for pin in data_refs), "SOURCES_AND_DATA_MUST_STAY_DISJOINT")
    spec = {"schema": "ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1", "kind": "analysis", "pilot": pilot,
            "scope_key": scope, "scope_parameters": parameters, "wall_seconds": 14400,
            "estimated_peak_output_bytes": cap, "resources": {"cpus": 16, "memory_gib": 64, "exclusive_user": True},
            "source_references": all_sources, "data_references": data_refs,
            "deferred_authority_references": [], "execution_argv": [shared.PY, "-B", "-m", "workflows.expansion." + module,
                "--plan", str(plan_path), "--root-preflight", "__ROOT_STARTUP_PROOF__"],
            "root_review": {"reviewer": "root", "status": "APPROVED", "basis": "Root personally invoked reviewed metadata helper",
                            "no_pool_common_UFF_QM_training_release": True},
            "metadata_only_preparation_no_large_body_read_or_stat": True}
    shared.write_new(spec_path, spec)
    print(__import__("json").dumps({"status": "ROOT_METADATA_STAGE_SPEC_PREPARED_NOT_QUEUED", "plan": shared.pin(plan_path),
          "stage_spec": shared.pin(spec_path), "pilot": pilot, "whole_output_cap_bytes": cap,
          "large_bodies_read_hashed_or_stat_ed": False, "submitted": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--goal-authority", type=Path, required=True)
    parser.add_argument("--accounting", type=Path, required=True)
    parser.add_argument("--profile-receipt", type=Path)
    parser.add_argument("--large-run-reviewed", action="store_true")
    args = parser.parse_args()
    materialize(args.stage, args.tag, args.goal_authority, args.accounting, args.profile_receipt, args.large_run_reviewed)


if __name__ == "__main__":
    main()
