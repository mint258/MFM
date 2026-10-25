"""Root metadata-only two-stage paired10000 replay preparation; never submits.

Only small source/receipt/config pins and ASTs are read. Raw and old SQLite are
locators derived from existing receipts, never opened, hashed or stat'ed here.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import socket

from . import materialize_feature_candidate_checks_v1 as small
from . import materialize_feature_candidate_eval_v2 as prior


ROOT, PYTHON, DEPS = small.ROOT, small.PYTHON, small.DEPS
SCOPE = "prefix_feature_paired_10000"
PARAMETERS = {"prefix_start_ordinal": 1, "input_prefix_limit": 10000,
              "legacy_success_cids": 8198, "legacy_unique_full_keys": 8197,
              "legacy_rejections": 1802, "legacy_feature_errors": 753,
              "repair_or_pool_release": False}
JOB = "dv1_paired_prefix_replay_cpu_v1"
NAMESPACE = "workflows.data_v1_final.execution.cpu_prefix_replay_v1"
CENTRAL = "workflows/data_v1_final/execution/cpu_prefix_replay_v1"
BASELINE = "workflows/data_v1_final/execution/cpu_analysis_v1"
REQUIRED_CENTRAL = {"__init__.py", "policy.py", "probe_memory.py", "runtime.py", "runtime_v2.py",
                    "launch.py", "launch_v2.py", "submit_cpu_pilot_v1.py", "submit_cpu_pilot_v3.py",
                    "prepare_request_v2.py", "run_stages_v1.py"}
POLICY_REL = "configs/data_v1/cpu_prefix_replay_scopes_v1.json"
DECISION_REL = "configs/data_v1/cpu_prefix_replay_decision_v1.json"
CAP = 256 * 1024 ** 2
require, read_small, ref, load = small.require, small.read_small, small.ref, small.load
verify, unique, write_new = small.verify, small.unique, small.write_new


def expansion_equivalence(repo):
    pairs = [
        ("candidate_prefix_replay_v1.py", "candidate_prefix_replay_cpu_v2.py",
         b"from workflows.data_v1_final.execution.cpu_analysis_v1 import policy, runtime_v2 as runtime",
         b"from workflows.data_v1_final.execution.cpu_prefix_replay_v1 import policy, runtime_v2 as runtime"),
        ("test_candidate_prefix_replay_v1.py", "test_candidate_prefix_replay_cpu_v2.py",
         b"from . import candidate_prefix_replay_v1 as replay", b"from . import candidate_prefix_replay_cpu_v2 as replay"),
    ]
    result = []
    for before_name, after_name, before_import, after_import in pairs:
        before_path, after_path = (repo / "workflows/expansion" / name for name in (before_name, after_name))
        before, after = read_small(before_path), read_small(after_path)
        inverse = after.replace(after_import, before_import)
        require(before.count(before_import) == after.count(after_import) == 1 and inverse == before and
                ast.dump(ast.parse(inverse), include_attributes=False) == ast.dump(ast.parse(before), include_attributes=False),
                "Expansion/test variant changed beyond its one exact import")
        result.append({"baseline_reference": ref(before_path), "variant_reference": ref(after_path),
                       "inverse_full_file_bytes_equal": True, "normalized_AST_identical": True,
                       "all_scientific_and_metadata_function_bytes_unchanged": True})
    return result


def namespace_equivalence(repo, proof_path):
    proof = load(proof_path)
    require(proof["schema"] == "CPU_PREFIX_RESOURCE_NAMESPACE_EQUIVALENCE_V1" and proof["status"] == "PASS" and
            Path(proof["namespace"]) == repo / CENTRAL and Path(proof["baseline_namespace"]) == repo / BASELINE and
            proof["resource_guards_unchanged"] is True and proof["changes_restricted_to_namespace_and_policy_paths"] is True,
            "Exact Root namespace/resource equivalence authority required")
    names, pins = set(), [ref(proof_path)]
    for row in proof["files"]:
        name = row["filename"]
        require(name == Path(name).name and name.endswith(".py") and name not in names and
                row["baseline_reference"]["path"] == str(repo / BASELINE / name) and
                row["variant_reference"]["path"] == str(repo / CENTRAL / name) and
                row["inverse_full_file_bytes_equal"] is True and row["normalized_AST_identical"] is True,
                "Root namespace proof file entry differs")
        names.add(name)
        for pin in (row["baseline_reference"], row["variant_reference"]):
            verify(pin)
            pins.append(pin)
        before, after = read_small(row["baseline_reference"]["path"]), read_small(row["variant_reference"]["path"])
        inverse = after.replace(b"cpu_prefix_replay_v1", b"cpu_analysis_v1").replace(
            POLICY_REL.encode(), b"configs/data_v1/cpu_analysis_small_scopes_v1.json").replace(
            DECISION_REL.encode(), b"configs/data_v1/run_decisions_v4.json")
        require(inverse == before and ast.dump(ast.parse(inverse), include_attributes=False) ==
                ast.dump(ast.parse(before), include_attributes=False), "Actual new namespace bytes exceed reviewed path substitutions")
    require(REQUIRED_CENTRAL <= names, "Root equivalence proof omits actual import/runtime/stage/submitter chain")
    verify(proof["proof_source_reference"])
    pins.append(proof["proof_source_reference"])
    return unique(pins), [ref(repo / CENTRAL / name) for name in sorted(names)]


def materialize(repository, run_root, reviewer, node, namespace_proof):
    repo, root = Path(repository), Path(run_root)
    require(os.name == "posix" and os.getuid() == 1278 and socket.gethostname().split(".")[0] == "sonmi" and
            reviewer == "root" and root == ROOT and repo == ROOT / "repository" and node == "compute-0-17" and
            Path(__file__).absolute() == repo / "workflows/expansion/materialize_paired_prefix_replay_cpu_v1.py" and
            Path(namespace_proof) == root / "control/root_cpu_prefix_namespace_equivalence_v1.json",
            "Root must merge/review and personally prepare exact CPU17 metadata; never submit here")
    policy_path, decision_path = repo / POLICY_REL, repo / DECISION_REL
    config = load(policy_path)
    require(set(config["scopes"]) == {SCOPE} and config["decision_reference"] == ref(decision_path),
            "Independent new Root policy/decision must contain this scope only")
    scope = config["scopes"][SCOPE]
    require(scope["parameters"] == PARAMETERS and scope["memory_gib"] == 4 and
            scope["wall_seconds"] == 3600 and scope["output_cap_bytes"] == CAP,
            "Only exact paired10000/16CPU4G1h/256MiB science+32MiBguard authority")
    verify(scope["base_request_reference"])
    base = load(scope["base_request_reference"]["path"])
    base_pins = [scope["base_request_reference"], base["script_reference"], *base["source_references"],
                 *scope.get("authority_references", [])]
    for pin in base_pins:
        verify(pin)
    namespace_pins, central_refs = namespace_equivalence(repo, namespace_proof)
    expansion_proof = expansion_equivalence(repo)
    template_path = repo / "configs/data_v1/expansion/paired_prefix_replay_plan_template_v1.json"
    plan = load(template_path)
    require(plan["schema"] == "pubchem_paired_prefix_candidate_plan_v1" and plan["status"] == "NOT_READY" and
            plan["scope_key"] == SCOPE and plan["scope_parameters"] == PARAMETERS and plan["workers"] == 16 and
            plan["max_input_rows"] == 10000 and plan["prefix_start_ordinal"] == 1 and plan["peak_output_cap_bytes"] == CAP,
            "Use the frozen proposed-only10000 template")
    evidence = [value for name, value in plan.items() if name not in ("raw_file", "legacy_database") and
                isinstance(value, dict) and set(value) == {"path", "bytes", "sha256"}]
    for pin in evidence:
        verify(pin)
    old = load(plan["original_prefix_receipt"]["path"])
    raw = load(plan["raw_receipt"]["path"])
    require(old["job_id"] == "4520427" and old["database"] == plan["legacy_database"] and
            old["source_receipt"] == plan["raw_receipt"] and old["all_rejections"] == plan["original_rejections"] and
            old["plan"] == plan["original_prefix_plan"] and old["successful_cid_aliases"] == 8198 and old["unique_full_keys"] == 8197 and
            old["counts"]["first:IDENTITY_OR_FEATURE_FAILED"] == 753 and raw["job_id"] == "4520348" and
            raw["file"] == plan["raw_file"], "Large body locators must come from exact original producer/427 metadata")
    full_refs = list(load(plan["original_prefix_plan"]["path"])["full_gate_refs"].values())
    for pin in full_refs:
        verify(pin)
    old_test_plan, test_evidence = prior.prior_evidence(root)
    three = load(plan["candidate_three_cid_receipt"]["path"])
    monitor = load(plan["candidate_three_cid_monitor"]["path"])
    require(three["job_id"] == monitor["job_id"] == "4520555" and three["status"] == "CANDIDATE_EVALUATED_NOT_APPLIED" and
            three["candidate_three_case_checks_passed"] is True and three["candidate_pass_cases"] == 3 and
            three["observed_non_ring_field_drift_cases"] == 0 and three["repair_applied"] is False and three["pool_modified"] is False and
            monitor["status"] == "COMPLETED_NO_MEMORY_DENIAL" and monitor["child_returncode"] == 0 and
            monitor["first_denial"] is None and monitor["durable_evidence_exported"] is True and
            three["root_submission"] == monitor["intent_reference"], "Actual555C0 prerequisites required, not a new approval")
    scientific_paths = ("workflows/expansion/screen.py", "workflows/expansion/features_generic_candidate_v1.py")
    for path in scientific_paths:
        pin = ref(repo / path)
        require(pin in old_test_plan["code_sources"] and pin in three["cpu_runtime_proof"]["request"]["source_references"],
                "Frozen science changed since actual545/555")
    outer = root / "artifacts/expansion/diagnostics/paired_prefix_cpu_v1"
    output, proof_path = outer / "candidate_evaluation", outer / "source_equivalence.json"
    stage_receipt = outer / "stage_receipt.json"
    plan_path = root / "control/requests" / (JOB + "_plan.json")
    stages_path = root / "control/requests" / (JOB + "_stages.json")
    argv_path = root / "control/requests" / (JOB + "_argv.json")
    prepared_path = root / "control/requests" / (JOB + ".json")
    bound_path = root / "control/requests" / (JOB + "_bound.json")
    intent_path = root / "control/submissions" / (JOB + ".intent.json")
    script_path = root / "control/scripts" / (JOB + ".sbatch")
    for path in (outer, plan_path, stages_path, argv_path, prepared_path, bound_path, intent_path, script_path,
                 root / "control/submissions" / (JOB + ".json"), root / "artifacts/cpu_analysis_guards" / JOB):
        require(not path.exists() and not path.is_symlink(), "New immutable destination required: " + str(path))
    guide_path = root.parent.parent / "数据线工作流程：v1 定稿与数据扩充（Codex B）.md"
    guide_ref = ref(guide_path)
    outer.mkdir(parents=True)
    write_new(proof_path, {"schema": "PAIRED_PREFIX_EXPANSION_NAMESPACE_SOURCE_EQUIVALENCE_V1", "status": "PASS",
                           "expansion_files": expansion_proof, "root_namespace_proof": ref(namespace_proof),
                           "scientific_functions_changed": False, "resource_guards_changed": False,
                           "source_only_no_tests_or_science_run": True})
    expansion_refs = [ref(repo / "workflows/expansion" / name) for name in
                      ("candidate_prefix_replay_cpu_v2.py", "test_candidate_prefix_replay_cpu_v2.py", "common.py", "screen.py",
                       "features_generic_candidate_v1.py", "bounded_prefix_gate_v2.py", "__init__.py")]
    unchanged = json.loads(json.dumps(plan))
    plan.update(status="READY", independent_scope_policy_reference=ref(policy_path), output_root=str(output),
                code_sources=unique([*expansion_refs, *central_refs]), central_runtime_references=central_refs,
                namespace_source_equivalence=ref(proof_path), root_namespace_equivalence=ref(namespace_proof),
                guide_reference=guide_ref, independent_decision_reference=ref(decision_path),
                resource_authority={"node": node, "cpus": 16, "memory_gib": 4, "wall_seconds": 3600,
                                    "science_cap_bytes": CAP, "guard_cap_bytes": 32 * 1024 ** 2,
                                    "estimated_peak_output_bytes": CAP + 32 * 1024 ** 2},
                prior_four_tests_actual_pass={"job_id": "4520545", "passed_tests": 4, "references": test_evidence},
                paired_boundary_tests_pending=True, paired10000_evaluation_pending=True)
    plan.pop("blocking_pending_items", None)
    require(all(plan[k] == value for k, value in unchanged.items() if k not in
                ("status", "independent_scope_policy_reference", "output_root", "code_sources", "blocking_pending_items")),
            "Original paired scientific plan parameters changed")
    write_new(plan_path, plan)
    stages = {"schema": "PAIRED_PREFIX_FINITE_TEST_THEN_CANDIDATE_EVALUATION_V1", "scope_key": SCOPE,
              "repair_applied": False, "pool_modified": False, "stages": [
                  {"name": "three_paired_prefix_boundary_tests", "argv": [PYTHON, "-B", "-m", "unittest",
                       "workflows.expansion.test_candidate_prefix_replay_cpu_v2", "-v"]},
                  {"name": "actual_paired10000_candidate_evaluation_not_applied", "argv": [PYTHON, "-B", "-m",
                       "workflows.expansion.candidate_prefix_replay_cpu_v2", "--plan", str(plan_path),
                       "--root-submit-intent", str(intent_path)]}]}
    write_new(stages_path, stages)
    command = [PYTHON, "-B", "-m", NAMESPACE + ".run_stages_v1", "--stages", str(stages_path),
               "--root-preflight", str(intent_path), "--receipt", str(stage_receipt)]
    write_new(argv_path, command)
    self_refs = [ref(repo / "workflows/expansion" / name) for name in
                 ("materialize_paired_prefix_replay_cpu_v1.py", "materialize_feature_candidate_checks_v1.py",
                  "materialize_feature_candidate_eval_v2.py")]
    baseline_refs = [pin for row in expansion_proof for pin in (row["baseline_reference"], row["variant_reference"])]
    sources = unique([*base_pins, *namespace_pins, *expansion_refs, *central_refs, *evidence, *full_refs, *test_evidence.values(),
                      *baseline_refs, *self_refs, ref(template_path), guide_ref, ref(policy_path), ref(decision_path),
                      ref(proof_path), ref(plan_path), ref(stages_path),
                      ref(repo / "docs/expansion/paired_prefix_candidate_replay_v1.md"),
                      ref(repo / "workflows/data_v1_final/execution/submit_reviewed.py")])
    prepare = [PYTHON, "-B", "-m", NAMESPACE + ".prepare_request_v2", "--scope", SCOPE, "--node", node,
               "--job-name", JOB, "--command-file", str(argv_path)]
    for pin in sources:
        prepare.extend(["--source", pin["path"]])
    result = small.metadata_command(prepare, repo)
    require(result["status"] == "PREPARED_NOT_SUBMITTED" and result["request"] == ref(prepared_path), "Unexpected metadata preparer result")
    request, script = load(prepared_path), read_small(script_path)
    directives = dict(re.findall(r"^#SBATCH --([\w-]+)=(\S+)$", script.decode(), flags=re.MULTILINE))
    require(request["script_reference"] == ref(script_path) and script.startswith(b"#!/bin/bash\n") and b"\r" not in script and
            directives["partition"] == "cpu" and directives["nodelist"] == node and directives["cpus-per-task"] == "16" and
            directives["mem"] == "4G" and directives["time"] == "01:00:00" and
            (NAMESPACE + ".launch_v2 --intent " + str(intent_path)).encode() in script and
            ("export PYTHONPATH=" + str(repo) + ":" + DEPS + "\n").encode() in script and
            request["execution_argv"] == command and request["scope_key"] == SCOPE and request["scope_parameters"] == PARAMETERS and
            request["memory_gib"] == 4 and request["wall_seconds"] == 3600 and
            request["estimated_peak_output_bytes"] == CAP + 32 * 1024 ** 2 and request.get("partition") in (None, "cpu"),
            "Prepared CPU17/4G1h/newnamespace/science budget differs")
    data_refs = [plan["raw_file"], plan["legacy_database"]]
    require(request.get("data_references", []) in ([], [plan["raw_file"]], data_refs), "Unexpected inherited body locator")
    original = json.loads(json.dumps(request))
    request.update(partition="cpu", data_references=data_refs)
    request["source_references"] = unique([*request["source_references"], ref(prepared_path)])
    request["cpu_partition_and_data_locator_binding_proof"] = {
        "schema": "PAIRED_PREFIX_CPU_PARTITION_DATA_LOCATOR_BINDING_V1", "prepared_request": ref(prepared_path),
        "script_reference": ref(script_path), "source_authorities": [plan["original_prefix_receipt"], plan["raw_receipt"]],
        "data_references": data_refs, "large_bodies_opened_hashed_or_stat_ed_on_login": False,
        "other_science_and_resource_fields_unchanged": all(request[k] == value for k, value in original.items()
                                                         if k not in ("partition", "source_references", "data_references"))}
    require(request["cpu_partition_and_data_locator_binding_proof"]["other_science_and_resource_fields_unchanged"], "Binder widened science/resources")
    for pin in request["source_references"]:
        verify(pin)
    write_new(bound_path, request)
    print(json.dumps({"status": "PAIRED10000_STAGES_PREPARED_NOT_RUN_NOT_SUBMITTED", "bound_request": ref(bound_path),
                      "prepared_request_preserved": ref(prepared_path), "plan": ref(plan_path), "stages": ref(stages_path),
                      "source_equivalence": ref(proof_path), "root_namespace_equivalence": ref(namespace_proof),
                      "science_output_expected": str(output), "stage_receipt_expected": str(stage_receipt),
                      "submission_entry_for_root_only": NAMESPACE + ".submit_cpu_pilot_v3",
                      "quota_feed_read_or_written": False, "large_bodies_opened_hashed_or_stat_ed": False,
                      "repair_applied": False, "pool_modified": False, "pool_release_authorized": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--reviewer", required=True, choices=["root"])
    parser.add_argument("--node", required=True, choices=["compute-0-17"])
    parser.add_argument("--namespace-proof", required=True, type=Path)
    args = parser.parse_args()
    materialize(args.repository, args.run_root, args.reviewer, args.node, args.namespace_proof)


if __name__ == "__main__":
    main()
