"""Source-only Root migration of real READY plans; never submit or read data."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
import re

from workflows.data_v1_final.execution.queue_v1 import shared
from .runtime import POLICY, SCOPES, verify_small
from .source_equivalence import BASES, equivalence


STAGES = {"identity-profile": ("identity_profile", "sb5_identity_profile_source_roles_v4", "BOUNDED_PERFORMANCE_BATCH"),
          "raw-inventory": ("inventory", "sb5_pubchem_raw_inventory_v2", "FULL_SOURCE_INVENTORY_PRIOR_CRC"),
          "official-head": ("official_head", "sb5_official_source_headers_v1", "BOUNDED_METADATA_PREPARATION")}


def unique(refs):
    result = {}
    for ref in refs:
        shared.need(ref["path"] not in result or result[ref["path"]] == ref, "CONFLICTING_ACTUAL_SMALL_SOURCE_PIN")
        result[ref["path"]] = ref
    return list(result.values())


def materialize(stage, baseline_plan, tag, reviewer):
    shared.on_login()
    shared.need(reviewer == "root" and stage in STAGES and re.fullmatch(r"[a-z0-9_]+", tag), "EXACT_ROOT_STAGE_TAG_REQUIRED")
    shared.need(Path(__file__).absolute() == shared.REPO / "workflows/expansion/cpu_auto_memory_v1/materialize.py",
                "ROOT_INTEGRATED_METADATA_HELPER_REQUIRED")
    module, scope, mode = STAGES[stage]
    baseline_ref = shared.pin(baseline_plan)
    original = shared.load(baseline_plan)
    shared.need(original["status"] == "READY" and original["scope_key"] == scope and
        original["pilot"] is (stage == "identity-profile"), "ONLY_REAL_BASELINE_READY_SCIENTIFIC_PLAN")
    if stage == "identity-profile":
        shared.need(original["mode"] == "profile" and original["role_semantics"] == "ORIGINAL_PHYSICAL_RECORD_MEMBERSHIP_ONLY"
                    and original["effective_training_roles_applied"] is False, "SOURCE_ROLES_NOT_EFFECTIVE_TRAINING_ROLES")
        producer = shared.load(original["input_pin_receipt"]["path"])
        data = [row["reference"] for row in producer["outputs"] if row["kind"] != "metadata_json"]
        shared.need(len(data) == 73, "EXACT73_BODY_LOCATORS_WITHOUT_LOGIN_READ")
    elif stage == "raw-inventory":
        data = [original["raw_file"]]
    else:
        data = []
    authority_path = shared.REPO / "configs/data_v1/user_cpu_auto_memory_20261026_v1.json"
    authority_ref = shared.pin(authority_path)
    authority = shared.load(authority_path)
    shared.need(authority["schema"] == "USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1" and
        authority["status"] == "USER_AUTHORIZED" and authority["memory_policy"] == POLICY and
        authority["memory_directives_allowed"] is False and authority["exclusive_requested"] is False and
        authority["declared_memory_fraction_admission"] is False, "EXACT_NEW_USER_RESOURCE_AUTHORITY")
    stem = scope + "_cpu_default_memory_" + tag
    control = shared.ROOT / "control/cpu_default_memory_specs"
    plan_path, spec_path, proof_path = (control / (stem + suffix) for suffix in
                                      ("_plan.json", "_base_spec.json", "_source_equivalence.json"))
    branch = "identity" if stage == "identity-profile" else ("raw" if stage == "raw-inventory" else "official_sources")
    output = shared.ROOT / "artifacts/expansion" / branch / stem
    for path in (plan_path, spec_path, proof_path, output):
        shared.need(not path.exists() and not path.is_symlink(), "NEW_METADATA_AND_OUTPUTS_NO_OVERWRITE")
    explicit_head_authorities = [original["catalog_reference"], original["official_document_reference"]] if stage == "official-head" else []
    for ref in [*original["code_sources"], *original["authority_references"], *explicit_head_authorities, baseline_ref]:
        verify_small(ref)
    proof = equivalence(baseline_ref)
    code_paths = [*Path(__file__).parent.glob("*.py"),
        *(shared.REPO / "workflows/data_v1_final/execution/cpu_auto_memory_queue_v2").glob("*.py"),
        *(shared.REPO / value for value in BASES.values())]
    shared.need((shared.REPO / "workflows/data_v1_final/execution/cpu_auto_memory_queue_v2/runtime.py").is_file(),
                "ACTUAL_NEW_CENTRAL_RUNTIME_MUST_EXIST_NO_FUTURE_PIN")
    code = unique([*original["code_sources"], *(shared.pin(path) for path in code_paths)])
    shared.write_new(proof_path, proof)
    proof_ref = shared.pin(proof_path)
    plan = copy.deepcopy(original)
    plan.update(memory_policy=POLICY, baseline_plan=baseline_ref, resource_policy_authority=authority_ref,
        resource_migration_proof=proof_ref, output_root=str(output), wall_seconds=SCOPES[scope][1],
        code_sources=code, authority_references=unique([*original["authority_references"], authority_ref, baseline_ref, proof_ref, *explicit_head_authorities]),
        scheduler_memory_requested=False, scheduler_memory_allocation_assumed_gib=None,
        scientific_scope_parameters_changed=False, source_plan_READY_does_not_replace_Root_scope_review=True)
    shared.need(plan["scope_parameters"] == original["scope_parameters"], "FROZEN_SCIENTIFIC_PARAMETERS_CHANGED")
    shared.write_new(plan_path, plan)
    sources = unique([*code, *plan["authority_references"], shared.pin(plan_path)])
    shared.need(not {ref["path"] for ref in sources}.intersection(ref["path"] for ref in data), "SMALL_SOURCES_AND_DATA_DISJOINT")
    spec = {"schema": "ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1", "kind": "analysis", "pilot": plan["pilot"],
        "memory_policy": POLICY, "scope_key": scope, "scope_parameters": plan["scope_parameters"],
        "wall_seconds": SCOPES[scope][1], "estimated_peak_output_bytes": plan["whole_output_cap_bytes"],
        "stage_output_cap_bytes": plan["whole_output_cap_bytes"], "cpus": 16,
        "source_references": sources, "data_references": data, "deferred_authority_references": [],
        "execution_argv": [shared.PY, "-B", "-m", "workflows.expansion.cpu_auto_memory_v1." + module,
            "--plan", str(plan_path), "--root-preflight", "__ROOT_STARTUP_PROOF__"],
        "proposed_scope_mode": mode, "metadata_preparation_status": "NOT_REQUEST_READY_NEW_ROOT_SCOPE_REVIEW_REQUIRED",
        "no_scientific_scope_or_output_cap_changed": True}
    # No scope.review or future reference is synthesized. Root's new central
    # materializer must bind its actual exact scope review and actual script.
    shared.write_new(spec_path, spec)
    print(__import__("json").dumps({"status": "CPU_DEFAULT_MEMORY_SOURCE_BOUND_NOT_SUBMITTED",
        "plan": shared.pin(plan_path), "base_spec": shared.pin(spec_path), "source_equivalence": proof_ref,
        "memory_policy": POLICY, "scheduler_memory_requested": False, "data_bodies_read_or_stat": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=STAGES, required=True)
    parser.add_argument("--baseline-plan", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--reviewer", choices=["root"], required=True)
    args = parser.parse_args()
    materialize(args.stage, args.baseline_plan, args.tag, args.reviewer)


if __name__ == "__main__":
    main()
