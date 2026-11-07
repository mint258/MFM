"""Root small-metadata preparation for an independently reviewed full export."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import re

from workflows.data_v1_final.execution.queue_v1 import shared
from .. import full_queue_v1 as files
from ..materialize_full_sources_v2 import parent_from_account
from .policy import (CAP, FULL_FORMAL, FULL_RECORDS, MEMORY_POLICY, ROW_GROUPS, SCOPE, SPILL, WALL,
                     forecast, parameters, validate_full_plan, validate_profile)
from .provenance import BASE, PROFILE, source_proof


def unique(refs):
    result = {}
    for ref in refs:
        shared.need(ref["path"] not in result or result[ref["path"]] == ref, "CONFLICTING_SMALL_SOURCE_PIN")
        result[ref["path"]] = ref
    return list(result.values())


def materialize(profile_path, accounting_path, tag, reviewer):
    shared.on_login()
    shared.need(reviewer == "root" and re.fullmatch(r"[a-z0-9_]+", tag), "ROOT_AND_NEW_TAG_REQUIRED")
    shared.need(Path(__file__).absolute() == shared.REPO / "workflows/expansion/identity_full_after_profile_v1/materialize.py",
                "ROOT_INTEGRATED_METADATA_HELPER_REQUIRED")
    profile_ref = shared.pin(profile_path)
    profile = shared.load(profile_path)
    validate_profile(profile)
    for ref in (profile["plan"], profile["startup_proof"]):
        files.verify_small(ref)
    previous = shared.load(profile["plan"]["path"])
    historical_startup = shared.load(profile["startup_proof"]["path"])
    shared.need(Path(profile_path) == Path(previous["output_root"]) / "receipt.json" and
        previous["mode"] == "profile" and previous["scope_key"] == "sb5_identity_profile_source_roles_v4" and
        previous["pilot"] is True and historical_startup["job_id"] == profile["job_id"] and
        historical_startup["schema"] == "FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1" and
        historical_startup["request"]["scope_key"] == previous["scope_key"] and
        historical_startup["request"]["pilot"] is True, "ACTUAL_PROFILE_OUTPUT_AND_HISTORICAL_SCOPE_BINDING")
    parent, raw_sacct = parent_from_account(accounting_path, profile["job_id"])
    shared.need(parent["NodeList"] == profile["node"], "ACTUAL_PROFILE_PARENT_NODE_DIFFERS")
    profile_source = next(ref for ref in previous["code_sources"] if ref["path"] == str(shared.REPO / PROFILE))
    files.verify_small(profile_source)
    producer = shared.load(previous["input_pin_receipt"]["path"])
    formal = next(row for row in producer["outputs"] if row["source_id"] == "v1_formal")
    shared.need(formal["identity_metadata"]["records"] == FULL_FORMAL and formal["identity_metadata"]["row_groups"] == ROW_GROUPS,
                "ACTUAL_PINNED_FORMAL_FOOTER86_AND11231854_REQUIRED")
    data_refs = [row["reference"] for row in producer["outputs"] if row["kind"] != "metadata_json"]
    shared.need(len(data_refs) == 73, "EXACT73_BODY_REFS_NO_LOGIN_BODY_READ")
    budget = forecast(profile, profile_receipt_bytes=profile_ref["bytes"])
    shared.need(budget["planning_storage_upper_bytes"] <= CAP, "PLANNING_ALLOWANCE_EXCEEDS_FIXED16GIB")
    authority_path = shared.REPO / "configs/data_v1/user_cpu_auto_memory_20261026_v1.json"
    authority_ref = shared.pin(authority_path)
    authority = shared.load(authority_path)
    shared.need(authority["schema"] == "USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1" and
        authority["status"] == "USER_AUTHORIZED" and authority["memory_policy"] == MEMORY_POLICY and
        authority["memory_directives_allowed"] is False and authority["exclusive_requested"] is False,
        "CURRENT_CPU_DEFAULT_MEMORY_USER_AUTHORITY")
    stem = SCOPE + "_" + tag
    control = shared.ROOT / "control/full_identity_after_profile_specs"
    plan_path, proof_path, spec_path = (control / (stem + suffix) for suffix in
                                      ("_plan.json", "_source_proof.json", "_base_spec.json"))
    output = shared.ROOT / "artifacts/expansion/identity" / stem
    for path in (plan_path, proof_path, spec_path, output):
        shared.need(not path.exists() and not path.is_symlink(), "NEW_FULL_ATTEMPT_DESTINATIONS_PRESERVE_ALL_OLD_FILES")
    original_refs = [*previous["code_sources"], *previous["authority_references"]]
    for ref in original_refs:
        files.verify_small(ref)
    proof = source_proof(profile_source)
    accepted = {"receipt": profile_ref, "plan": profile["plan"], "startup_proof": profile["startup_proof"],
        "source_reference": profile_source, "accounting": shared.pin(accounting_path), "raw_sacct": raw_sacct,
        "actual_parent": parent, "allocated_core_seconds": int(parent["ElapsedRaw"]) * int(parent["AllocCPUS"]),
        "actual_cost_is_not_internal_dispatcher_or_worker_seconds": True}
    central = shared.REPO / "workflows/data_v1_final/execution/cpu_auto_memory_queue_v2"
    code_paths = [*Path(__file__).parent.glob("*.py"), *central.glob("*.py"), shared.REPO / BASE,
        shared.REPO / "workflows/expansion/cpu_auto_memory_v1/runtime.py",
        shared.REPO / "workflows/expansion/materialize_full_sources_v2.py"]
    shared.need((central / "runtime.py").is_file(), "ACTUAL_CENTRAL_V2_SOURCE_REQUIRED_NO_FUTURE_PINS")
    code = unique([*previous["code_sources"], *(shared.pin(path) for path in code_paths)])
    shared.write_new(proof_path, proof)
    proof_ref = shared.pin(proof_path)
    plan = copy.deepcopy(previous)
    for key in ("baseline_plan", "resource_migration_proof", "scientific_scope_parameters_changed"):
        plan.pop(key, None)
    plan.update(status="READY", scope_key=SCOPE, scope_parameters=parameters(profile_ref), mode="full", pilot=False,
        formal_row_groups=list(range(ROW_GROUPS)), output_root=str(output), whole_output_cap_bytes=CAP,
        unit_output_cap_bytes=CAP // 32, spill_cap_bytes=SPILL, wall_seconds=WALL, worker_result_timeout_seconds=7200,
        run_boundary_tests=False, accepted_profile=accepted, planning_budget=budget, memory_policy=MEMORY_POLICY,
        full_source_proof=proof_ref, resource_policy_authority=authority_ref, code_sources=code,
        expected_all_local_records=FULL_RECORDS, resource_only_change_claimed=False,
        new_full_scientific_scope_requires_separate_Root_review=True,
        inherited_profile_resource_proof_is_historical_only=True)
    additional = [profile_ref, profile["plan"], profile["startup_proof"], profile_source,
        accepted["accounting"], raw_sacct, parent["receipt_reference"], authority_ref, proof_ref]
    plan["authority_references"] = unique([*previous["authority_references"], *additional])
    validate_full_plan(plan)
    for ref in [*code, *plan["authority_references"]]:
        files.verify_small(ref)
    shared.write_new(plan_path, plan)
    sources = unique([*code, *plan["authority_references"], shared.pin(plan_path)])
    shared.need(not {r["path"] for r in sources}.intersection(r["path"] for r in data_refs), "SOURCE_DATA_REFERENCE_SEPARATION")
    spec = {"schema": "ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1", "kind": "analysis", "pilot": False,
        "memory_policy": MEMORY_POLICY, "cpus": 16, "scope_key": SCOPE, "scope_parameters": parameters(profile_ref),
        "wall_seconds": WALL, "estimated_peak_output_bytes": CAP, "stage_output_cap_bytes": CAP,
        "scope": {"mode": "FULL_SOURCE_AFTER_PROFILE", "parent_profile": profile_ref},
        "source_references": sources, "data_references": data_refs, "deferred_authority_references": [],
        "execution_argv": [shared.PY, "-B", "-m", "workflows.expansion.identity_full_after_profile_v1.run",
            "--plan", str(plan_path), "--root-preflight", "__ROOT_STARTUP_PROOF__"],
        "metadata_preparation_status": "NOT_REQUEST_READY_EXACT_ROOT_FULL_SCOPE_REVIEW_MISSING",
        "global_decontamination_or_pool_release_authorized": False,
        "actual_profile_allocation_core_seconds": accepted["allocated_core_seconds"],
        "conservative_estimate_seconds": budget["conservative_planning_seconds"],
        "cost_soft_stop_seconds": budget["soft_limit_seconds"]}
    # Root must bind actual scope.review with profile_reviewed/approved_profile_reference.
    # No future review, request, script or actual-full-parent reference is fabricated.
    shared.write_new(spec_path, spec)
    print(__import__("json").dumps({"status": "INDEPENDENT_FULL_SOURCE_BOUND_AWAITING_ROOT_REVIEW_NOT_SUBMITTED",
        "plan": shared.pin(plan_path), "base_spec": shared.pin(spec_path), "source_proof": proof_ref,
        "actual_profile_allocated_core_seconds": accepted["allocated_core_seconds"], "data_bodies_read_or_stat": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile-receipt", type=Path, required=True)
    parser.add_argument("--accounting", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--reviewer", choices=["root"], required=True)
    args = parser.parse_args()
    materialize(args.profile_receipt, args.accounting, args.tag, args.reviewer)


if __name__ == "__main__":
    main()
