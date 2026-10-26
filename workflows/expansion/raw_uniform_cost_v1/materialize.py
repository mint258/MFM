"""Root-only small metadata preparation; raw/index/part bodies remain CPU-only."""
import argparse
from pathlib import Path
import re

from workflows.data_v1_final.execution.queue_v1 import shared
from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2.contract import validate_authority
from .. import full_queue_v1 as files
from . import policy, runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-receipt", type=Path, required=True)
    parser.add_argument("--accounting", type=Path, required=True)
    parser.add_argument("--cost-decision", type=Path, required=True)
    parser.add_argument("--tag", required=True); parser.add_argument("--reviewer", choices=["root"], required=True)
    args = parser.parse_args(); shared.on_login()
    here = shared.REPO / "workflows/expansion/raw_uniform_cost_v1"
    shared.need(Path(__file__).absolute().parent == here and re.fullmatch(r"[a-z0-9][a-z0-9_]{0,63}", args.tag),
                "ROOT_INTEGRATED_NEW_UNIFORM_METADATA_TAG_REQUIRED")
    control = shared.ROOT / "control/raw_uniform_cost_specs" / args.tag
    output = files.ARTIFACTS / "cost_profiles" / (policy.SCOPE + "_" + args.tag)
    shared.need(not control.exists() and not control.is_symlink() and not output.exists() and not output.is_symlink(),
                "NEW_UNIFORM_PLAN_AND_OUTPUT_REQUIRED")
    receipt_ref = shared.pin(args.inventory_receipt)
    receipt = shared.load(args.inventory_receipt)
    n, index_ref, owned_root = policy.inventory_metadata(receipt)
    parent, raw_sacct = policy.validate_actual_parent(receipt, args.accounting)
    inventory_plan = shared.load(receipt["plan"]["path"])
    files.verify_small(receipt["plan"]); files.verify_small(receipt["startup_proof"])
    anchors = inventory_plan["anchors"]
    references = {}

    def bind(reference):
        files.verify_small(reference)
        shared.need(reference["path"] not in references or references[reference["path"]] == reference, "CONFLICTING_SOURCE_REFERENCE")
        references[reference["path"]] = reference
        return reference

    for reference in (receipt_ref, receipt["plan"], receipt["startup_proof"], shared.pin(args.accounting), raw_sacct,
                      parent["receipt_reference"], *anchors.values()):
        bind(reference)
    cost = bind(shared.pin(args.cost_decision)); runtime.validate_cost(cost)
    authority = bind(shared.pin(shared.REPO / "configs/data_v1/user_cpu_auto_memory_20261026_v1.json"))
    validate_authority(authority, read_small=shared.read_small)
    raw_receipt = bind(shared.pin(files.ARTIFACTS / "raw/pubchem_20261025_v1/attempt_4520348/receipt.json"))
    raw = shared.load(raw_receipt["path"])
    shared.need(raw["job_id"] == "4520348" and raw["file"] == receipt["raw_source"], "EXACT_RAW348_1093_SOURCE_BINDING")
    source_paths = set(here.glob("*.py"))
    source_paths.update((shared.REPO / "workflows/data_v1_final/execution/cpu_auto_memory_queue_v2").glob("*.py"))
    for relative in ("workflows/expansion/common.py", "workflows/expansion/full_queue_v1.py",
        "workflows/expansion/cpu_auto_memory_v1/runtime.py", "workflows/expansion/materialize_full_sources_v2.py",
        "workflows/expansion/pubchem_full_v1/inventory_v2.py", "workflows/expansion/screen.py",
        "workflows/expansion/features_generic_candidate_v1.py", "workflows/expansion/features_legacy_compatible_v2.py",
        "workflows/data_v1_final/execution/queue_v1/shared.py", "workflows/data_v1_final/execution/queue_v1/queue_contract.py"):
        source_paths.add(shared.REPO / relative)
    for path in tuple(source_paths):
        for directory in path.parents:
            if directory == shared.REPO: break
            if shared.REPO in directory.parents and (directory / "__init__.py").is_file():
                source_paths.add(directory / "__init__.py")
    code = [shared.pin(path) for path in sorted(source_paths)]
    authority_refs = list(references.values())
    plan = {"schema": "PUBCHEM_RAW_UNIFORM_COST_PLAN_V1", "status": "READY", "scope_key": policy.SCOPE,
        "scope_parameters": policy.parameters(receipt_ref, index_ref, owned_root, n, cost), "pilot": True,
        "whole_output_cap_bytes": policy.CAP, "output_root": str(output), "code_sources": code,
        "authority_references": authority_refs, "anchors": anchors, "cost_decision_reference": cost,
        "resource_policy_authority": authority, "inventory_receipt": receipt_ref,
        "inventory_accounting": shared.pin(args.accounting), "inventory_actual_parent": parent,
        "raw_producer_receipt": raw_receipt, "raw_file": raw["file"], "source_index": index_ref,
        "inventory_owned_root": owned_root, "population_N": n,
        "uniform_chemical_production_cost_forecast_available": False,
        "allocation_ceiling_is_not_a_cost_forecast": True, "scope_review_not_implied_by_ready_plan": True}
    files.validate_scientific_anchors(plan)
    policy.verify_compatible_source(plan)
    plan_path = control / "plan.json"; plan_ref = shared.write_new(plan_path, plan)
    all_refs = {r["path"]: r for r in [*code, *authority_refs, plan_ref]}
    shared.need(not {raw["file"]["path"], index_ref["path"]}.intersection(all_refs), "RAW_INDEX_MUST_STAY_DISJOINT_DATA_LOCATORS")
    spec = {"schema": "ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1", "kind": "analysis", "pilot": True,
        "scope_key": policy.SCOPE, "scope_parameters": plan["scope_parameters"],
        "scope": {"mode": "BOUNDED_PERFORMANCE_BATCH", "review": None, "parent_profile": None},
        "source_status_stage": "UNIFORM_RAW_ROW_COST_PROFILE_NOT_GUIDE1M", "wall_seconds": policy.WALL,
        "estimated_peak_output_bytes": policy.CAP, "stage_output_cap_bytes": policy.CAP,
        "execution_argv": [shared.PY, "-B", "-m", "workflows.expansion.raw_uniform_cost_v1.run",
                           "--plan", str(plan_path), "--root-preflight", "__ROOT_STARTUP_PROOF__"],
        "source_references": list(all_refs.values()), "data_references": [raw["file"], index_ref],
        "deferred_authority_references": []}
    spec_ref = shared.write_new(control / "base_spec_not_request_ready.json", spec)
    parents = [receipt_ref, receipt["plan"], receipt["startup_proof"], shared.pin(args.accounting), raw_sacct,
               parent["receipt_reference"], raw_receipt, *anchors.values(), cost]
    shared.write_new(control / "metadata_preparation_receipt.json", {
        "schema": "RAW_UNIFORM_COST_METADATA_PREPARATION_V1", "status": "NOT_REQUEST_READY_REQUIRES_ROOT_BOUNDED_SCOPE_REVIEW",
        "plan_reference": plan_ref, "base_spec_reference": spec_ref, "parent_evidence_for_root_review": parents,
        "inventory_actual_parent_allocated_core_seconds": int(parent["ElapsedRaw"]) * int(parent["AllocCPUS"]),
        "source_stage_parent_cost_is_not_uniform_chemical_forecast": True,
        "raw_index_or_part_bodies_read_or_statted": False, "scientific_calls_or_tests_run": False,
        "future_scope_review_or_source_SHA_fabricated": False})
    import json
    print(json.dumps({"status": "RAW_UNIFORM_METADATA_PREPARED_NOT_SUBMITTED", "plan_reference": plan_ref,
                      "base_spec_reference": spec_ref, "parent_evidence_for_root_review": parents}))


if __name__ == "__main__":
    main()
