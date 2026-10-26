"""Root-login small-metadata preparation; no old part/body stat or payload hash.

Produces an exact404-unit claimed-reference manifest and a base spec whose
scope.review remains null. Root separately reviews, materializes and submits.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import shared
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
from .. import full_queue_v1 as files
from . import close


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prior-request", type=Path, required=True)
    parser.add_argument("--prior-startup", type=Path, required=True)
    parser.add_argument("--accounting", type=Path, required=True)
    parser.add_argument("--cost-decision", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--reviewer", choices=["root"], required=True)
    args = parser.parse_args()
    shared.on_login()
    shared.need(Path(__file__).absolute().parent == shared.REPO / "workflows/expansion/identity_full_closure_v1" and
        re.fullmatch(r"[a-z0-9][a-z0-9_]{0,63}", args.tag), "ROOT_INTEGRATED_NEW_METADATA_TAG_REQUIRED")
    control = shared.ROOT / "control/identity_full_closure_specs" / args.tag
    output = shared.ROOT / "artifacts/expansion/identity" / (close.SCOPE + "_" + args.tag)
    shared.need(not control.exists() and not control.is_symlink() and not output.exists() and not output.is_symlink(),
                "NEW_CLOSURE_METADATA_AND_OUTPUT_ONLY")
    request = shared.load(args.prior_request)
    startup = shared.load(args.prior_startup)
    shared.need(startup["job_id"] == close.PRIOR_JOB and startup["request"] == request and
        startup["request_reference"] == shared.pin(args.prior_request) and request["data_references"] and
        len(request["data_references"]) == 73, "EXACT_ORIGINAL_FAILED_REQUEST_AND_STARTUP_REQUIRED")
    argv = request["execution_argv"]
    shared.need(argv[-4] == "--plan" and argv[-2:] == ["--root-preflight", str(args.prior_startup)],
                "EXACT_PRIOR_FULL_PRIMARY_OPTIONS_REQUIRED")
    prior_plan_path = Path(argv[-3])
    original = shared.load(prior_plan_path)
    close.validate_full_plan(original)
    shared.need(original["output_root"] == str(close.OLD_ROOT), "EXACT_FAILED_OUTPUT_ROOT_REQUIRED")
    failure_ref = shared.pin(close.OLD_ROOT / "failure.json")
    failure = shared.load(failure_ref["path"])
    parent, raw_accounting = close.failed_parent(args.accounting)
    refs = {}

    def bind(reference):
        files.verify_small(reference)
        shared.need(reference["path"] not in refs or refs[reference["path"]] == reference, "CONFLICTING_SMALL_REF")
        refs[reference["path"]] = reference
        return reference

    for reference in request["source_references"]:
        bind(reference)
    original_global = refs[str(Path(close.frozen.__file__).absolute())]
    # The only part source is each exact original unit receipt. No part is
    # opened, statted, hashed, decoded or assumed currently verified on login.
    units, manifest_rows = [], []
    for name in close.expected_units():
        receipt_reference = bind(shared.pin(close.OLD_ROOT / (name + ".receipt.json")))
        unit = shared.load(receipt_reference["path"])
        units.append(unit)
        manifest_rows.append({"receipt_reference": receipt_reference,
            "part_reference_claimed_by_original_unit": unit["file"]})
    summary = close.validate_unit_rows(units)
    shared.need(failure["status"] == "IDENTITY_EXPORT_FAILED_NO_RELEASE" and failure["closed_units"] == 404 and
        failure["error"] == close.ERROR and failure["runtime_budget"]["first_stop_reason"] == close.ERROR and
        failure["actual_worker_records_so_far"] == summary["original_worker_records"], "EXACT_FAILED_COMPLETE_UNITS_REQUIRED")
    for path in (args.prior_request, args.prior_startup, prior_plan_path, args.accounting, Path(failure_ref["path"])):
        bind(shared.pin(path))
    bind(raw_accounting); bind(parent["receipt_reference"])
    authority = bind(shared.pin(shared.REPO / "configs/data_v1/user_cpu_auto_memory_20261026_v1.json"))
    validate_authority(authority, read_small=shared.read_small)
    cost_decision = bind(shared.pin(args.cost_decision))
    close.validate_cost_decision(cost_decision)
    for path in Path(__file__).parent.glob("*.py"):
        bind(shared.pin(path))
    for path in (shared.REPO / "workflows/data_v1_final/execution/cpu_auto_memory_queue_v2").glob("*.py"):
        bind(shared.pin(path))
    manifest_ref = bind(shared.write_new(control / "existing_unit_locators.json", {
        "schema": "FAILED_IDENTITY_CLOSED_UNIT_LOCATORS_V1", "failed_parent": close.PRIOR_JOB,
        "part_root": str(close.OLD_ROOT / "parts"), "units": manifest_rows,
        "current_part_body_hashes_claimed": False, "current_part_footer_or_schema_read": False,
        "summary_from_receipts_not_current_part_bodies": summary}))
    plan = {"schema": "FULL_IDENTITY_READONLY_CLOSURE_PLAN_V1", "status": "READY", "scope_key": close.SCOPE,
        "scope_parameters": close.parameters(manifest_ref, cost_decision), "pilot": False,
        "output_root": str(output), "whole_output_cap_bytes": close.CAP,
        "spill_cap_bytes": original["spill_cap_bytes"], "planning_budget": original["planning_budget"],
        "prior_request": shared.pin(args.prior_request), "prior_startup": shared.pin(args.prior_startup),
        "prior_plan": shared.pin(prior_plan_path), "prior_failure": failure_ref,
        "prior_accounting": shared.pin(args.accounting), "prior_raw_accounting": raw_accounting,
        "prior_actual_parent": parent, "unit_manifest": manifest_ref, "original_global_source": original_global,
        "accepted_profile": original["accepted_profile"]["receipt"], "resource_authority_reference": authority,
        "cost_decision_reference": cost_decision,
        "bound_small_references": list(refs.values()), "prior_failed_parent_not_upgraded": True,
        "scope_review_not_implied_by_ready_plan": True}
    plan_path = control / "plan.json"
    plan_ref = shared.write_new(plan_path, plan)
    spec = {"schema": "ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1", "kind": "analysis", "pilot": False,
        "scope_key": close.SCOPE, "scope_parameters": plan["scope_parameters"],
        "scope": {"mode": "FULL_SOURCE_AFTER_PROFILE", "review": None, "parent_profile": plan["accepted_profile"]},
        "source_status_stage": "READ_ONLY_CLOSED_UNIT_COVERAGE", "wall_seconds": close.WALL,
        "estimated_peak_output_bytes": close.CAP, "stage_output_cap_bytes": close.CAP,
        "execution_argv": [shared.PY, "-B", "-m", close.MODULE, "--plan", str(plan_path),
                           "--root-preflight", "__ROOT_STARTUP_PROOF__"],
        "source_references": [*refs.values(), plan_ref], "data_references": request["data_references"],
        "deferred_authority_references": []}
    spec_ref = shared.write_new(control / "base_spec_not_request_ready.json", spec)
    parent_refs = [plan["accepted_profile"], plan["prior_request"], plan["prior_plan"], plan["prior_startup"],
                   failure_ref, manifest_ref, plan["prior_accounting"], raw_accounting, parent["receipt_reference"], cost_decision]
    shared.write_new(control / "metadata_preparation_receipt.json", {
        "schema": "FULL_IDENTITY_READONLY_CLOSURE_PREPARATION_V1",
        "status": "NOT_REQUEST_READY_REQUIRES_EXACT_ROOT_FULL_SCOPE_REVIEW",
        "plan_reference": plan_ref, "base_spec_reference": spec_ref,
        "parents_for_root_review": parent_refs, "summary_from_original_small_unit_receipts": summary,
        "original_failed_parent_allocated_core_seconds": 323 * 16,
        "old_parent_upgraded": False, "current_part_SHA_or_footer_claimed": False,
        "data_body_opened_or_statted_on_login": False, "tests_or_science_executed": False,
        "existing_part_refs_authorized_only_by_exact_root_reviewed_manifest": True})
    import json
    print(json.dumps({"status": "CLOSURE_METADATA_PREPARED_NOT_REQUEST_READY_NOT_SUBMITTED",
        "plan_reference": plan_ref, "base_spec_reference": spec_ref, "parents_for_root_review": parent_refs}))


if __name__ == "__main__":
    main()
