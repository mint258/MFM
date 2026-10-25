"""Root metadata only: new compatibility fixtures then paired10000 evaluation.

No tests/science, node probes, quota publication or submission run here. The
registered593 STOP,320 mismatches, all old code and pools remain immutable.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
from pathlib import Path
import re
import socket

from . import materialize_paired_prefix_replay_cpu_v1 as base


ROOT, PYTHON, DEPS = base.ROOT, base.PYTHON, base.DEPS
SCOPE, PARAMETERS, CAP, NAMESPACE = base.SCOPE, base.PARAMETERS, base.CAP, base.NAMESPACE
JOB = "dv1_paired_prefix_replay_cpu_v2"
require, read_small, ref, load = base.require, base.read_small, base.ref, base.load
verify, unique, write_new = base.verify, base.unique, base.write_new
PROOF_STATUS = "COMPOSITIONAL_OLD_SUCCESS_PASSTHROUGH_EXACT_RING_KEKULIZE_FALLBACK_V2"
STRATEGY = "OLD_SUCCESS_PASSTHROUGH_EXACT_OLD_RING_KEKULIZE_ONLY"
OLD_PROOF = b'    require(source_proof == three["source_scope_proof"], "Frozen X/non-ring source proof changed")'
NEW_PROOF = b'''    require(source_proof["status"] == "COMPOSITIONAL_OLD_SUCCESS_PASSTHROUGH_EXACT_RING_KEKULIZE_FALLBACK_V2" and
            source_proof["strategy"] == "OLD_SUCCESS_PASSTHROUGH_EXACT_OLD_RING_KEKULIZE_ONLY" and
            source_proof["nested_generic_fallback_proof"] == three["source_scope_proof"] and
            source_proof["frozen_old_ring_site"]["sanitize_line"] == 70 and
            source_proof["frozen_old_ring_site"]["traceback_code_object_identity_required"] is True and
            source_proof["wrapper_AST_equals_original_features_AST"] is False and
            source_proof["repair_applied"] is False and source_proof["pool_modified"] is False,
            "Exact compositional old-success passthrough/ring-only fallback proof changed")'''
ENTRY_EDITS = (
    (b"from . import common, features_generic_candidate_v1 as candidate, screen",
     b"from . import common, features_legacy_compatible_v2 as candidate, screen"),
    (b"    for module in (screen, candidate):", b"    for module in (screen, candidate.generic_fallback_module):"),
    (OLD_PROOF, NEW_PROOF),
)


def entry_proof(repo):
    before_path = repo / "workflows/expansion/candidate_prefix_replay_cpu_v2.py"
    after_path = repo / "workflows/expansion/candidate_prefix_replay_cpu_compat_v3.py"
    before, after = read_small(before_path), read_small(after_path)
    inverse = after
    for old, new in ENTRY_EDITS:
        require(before.count(old) == after.count(new) == 1, "Expected one exact entry metadata/import edit")
        inverse = inverse.replace(new, old)
    require(inverse == before and ast.dump(ast.parse(inverse), include_attributes=False) ==
            ast.dump(ast.parse(before), include_attributes=False), "Paired entry changed outside declared import/proof admissions")
    old_functions = {n.name: ast.get_source_segment(before.decode(), n) for n in ast.parse(before).body if isinstance(n, ast.FunctionDef)}
    new_functions = {n.name: ast.get_source_segment(after.decode(), n) for n in ast.parse(after).body if isinstance(n, ast.FunctionDef)}
    require(set(old_functions) == set(new_functions) and all(old_functions[name] == new_functions[name]
                for name in old_functions if name != "authorize"), "Worker/comparison/coverage/SQL functions changed")
    return {"baseline_reference": ref(before_path), "variant_reference": ref(after_path),
            "inverse_full_file_bytes_equal": True, "normalized_inverse_AST_identical": True,
            "unchanged_function_names": sorted(name for name in old_functions if name != "authorize"),
            "authorize_changes_only": ["candidate import", "historical candidate pin points to original generic module",
                                       "compositional proof admission"],
            "feature_dispatch_changed": True, "worker_comparison_coverage_SQL_bytes_unchanged": True}


def stopped_evidence(root):
    old_outer = root / "artifacts/expansion/diagnostics/paired_prefix_cpu_v1"
    paths = {"receipt": old_outer / "candidate_evaluation/receipt.json", "failure": old_outer / "candidate_evaluation/failure.json",
             "stages": old_outer / "stage_receipt.json", "monitor": root / "artifacts/cpu_analysis_guards/dv1_paired_prefix_replay_cpu_v1/closure.json",
             "audit": root / "control/paired_prefix_mismatch_audit_v1.json"}
    pins = {key: ref(path) for key, path in paths.items()}
    receipt, failure, stages, monitor, audit = (load(paths[k]) for k in ("receipt", "failure", "stages", "monitor", "audit"))
    require(receipt["job_id"] == monitor["job_id"] == "4520593" and
            receipt["status"] == "PAIRED_PREFIX_HAS_DRIFT_OR_UNRESOLVED_ERRORS_NOT_APPLIED" and
            receipt["complete_input_and_historical_coverage"] is True and receipt["all753_confirmed_recovered"] is True and
            receipt["counts"]["input_records"] == 10000 and receipt["counts"]["classification:OLD_PASS_HAS_DRIFT"] == 320 and
            receipt["counts"]["classification:RECOVERED_CONFIRMED_GENERIC_RING_ORDER"] == 753 and
            receipt["counts"]["classification:CHEMICAL_REJECTION_UNCHANGED"] == 1049 and
            receipt["root_submission"] == stages["root_preflight"] == monitor["intent_reference"] and
            stages["stages"][0]["returncode"] == 0 and stages["stages"][1]["returncode"] == 1 and
            stages["status"] == "STAGE_FAILED_NO_RETRY" and monitor["child_returncode"] == 1 and
            monitor["first_denial"] is None and monitor["monitor_io_failure"] is None and
            monitor["durable_evidence_exported"] is True and failure["status"] == "FAILED_PAIRED_PREFIX_NOT_APPLIED",
            "Exact actual593 deliberate scientific STOP and passed3fixtures must remain preserved")
    require(audit["schema"] == "PAIRED_PREFIX_COMPLETED_MISMATCH_METADATA_AUDIT_V1" and
            audit["status"] == "READONLY_CAUSE_AUDIT_NOT_ACCEPTANCE" and audit["receipt"] == pins["receipt"] and
            audit["database"] == receipt["paired_result_database"] and
            audit["results"]["paired_difference_keys"] == [["generic_ring_systems", 320]] and
            audit["results"]["historical_difference_keys"] == [] and
            audit["results"]["original_exception_types"] == [["KekulizeException", "FEATURE_FUNCTION", 753]],
            "Root actual mismatch audit is not the observed320-ring-only/753exact-type evidence")
    for key, pin in (("plan", receipt["plan"]), ("intent", receipt["root_submission"]), ("audit_source", audit["source_reference"])):
        verify(pin)
        pins[key] = pin
    plan = load(receipt["plan"]["path"])
    return plan, receipt, audit, pins


def materialize(repository, run_root, reviewer, node, namespace_proof):
    repo, root = Path(repository), Path(run_root)
    require(os.name == "posix" and os.getuid() == 1278 and socket.gethostname().split(".")[0] == "sonmi" and
            reviewer == "root" and root == ROOT and repo == ROOT / "repository" and node == "compute-0-17" and
            Path(__file__).absolute() == repo / "workflows/expansion/materialize_paired_prefix_compat_cpu_v2.py" and
            Path(namespace_proof) == root / "control/root_cpu_prefix_namespace_equivalence_v1.json",
            "Root must merge/review and personally run exact CPU17 metadata preparation")
    policy_path, decision_path = repo / base.POLICY_REL, repo / base.DECISION_REL
    config = load(policy_path)
    scope = config["scopes"][SCOPE]
    require(set(config["scopes"]) == {SCOPE} and config["decision_reference"] == ref(decision_path) and
            scope["parameters"] == PARAMETERS and scope["memory_gib"] == 4 and scope["wall_seconds"] == 3600 and
            scope["output_cap_bytes"] == CAP, "Same independent finite4G1h/256+32 scope only")
    verify(scope["base_request_reference"])
    base_request = load(scope["base_request_reference"]["path"])
    base_refs = [scope["base_request_reference"], base_request["script_reference"], *base_request["source_references"],
                 *scope.get("authority_references", [])]
    for pin in base_refs:
        verify(pin)
    namespace_refs, central_refs = base.namespace_equivalence(repo, namespace_proof)
    inverse = entry_proof(repo)
    plan, stop, audit, stop_refs = stopped_evidence(root)
    require(inverse["baseline_reference"] in plan["code_sources"], "Newentry baseline was not the actual593 runner")
    small_refs = [value for key, value in plan.items() if key not in ("raw_file", "legacy_database") and
                  isinstance(value, dict) and set(value) == {"path", "bytes", "sha256"}]
    small_refs += list(load(plan["original_prefix_plan"]["path"])["full_gate_refs"].values())
    for pin in small_refs:
        verify(pin)
    raw, old = load(plan["raw_receipt"]["path"]), load(plan["original_prefix_receipt"]["path"])
    require(raw["file"] == plan["raw_file"] == stop["raw_current_full_SHA_and_frame"]["reference"] and
            old["database"] == plan["legacy_database"] == stop["oldDB_current_full_SHA_and_frame"]["reference"],
            "Raw/oldDB locators changed; no large-body accesses permitted during metadata preparation")
    proof = base.small.metadata_command([PYTHON, "-B", "-m", "workflows.expansion.features_legacy_compatible_v2", "--verify-source-only"], repo)
    three = load(plan["candidate_three_cid_receipt"]["path"])
    require(proof["status"] == PROOF_STATUS and proof["strategy"] == STRATEGY and
            proof["nested_generic_fallback_proof"] == three["source_scope_proof"] == stop["source_scope_proof"] and
            proof["old_success_returns_original_result_object"] is True and proof["other_exceptions_rethrown"] is True and
            proof["wrapper_AST_equals_original_features_AST"] is False and proof["repair_applied"] is False and proof["pool_modified"] is False,
            "Exact compositional source-only proof required; no tests/science executed here")
    fixtures_path = repo / "workflows/expansion/test_features_legacy_compatible_v2.py"
    tree = ast.parse(read_small(fixtures_path))
    cases = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and
                 any(isinstance(t, ast.Name) and t.id == "OLD_PASS_CASES" for t in n.targets))
    by_cid = {row["cid"]: row for row in audit["samples"]}
    require(all(cid in by_cid and (smiles, ordinal, list(rings)) ==
                (by_cid[cid]["smiles"], by_cid[cid]["ordinal"], by_cid[cid]["old_ring"])
                for cid, smiles, ordinal, rings in cases), "New oldPASS fixture literals differ from actual Root audit")
    outer = root / "artifacts/expansion/diagnostics/paired_prefix_cpu_v2"
    output, equivalence_path, feature_proof_path = outer / "candidate_evaluation", outer / "entry_source_equivalence.json", outer / "compositional_feature_proof.json"
    stage_receipt = outer / "stage_receipt.json"
    plan_path = root / "control/requests" / (JOB + "_plan.json")
    stages_path = root / "control/requests" / (JOB + "_stages.json")
    argv_path = root / "control/requests" / (JOB + "_argv.json")
    prepared_path = root / "control/requests" / (JOB + ".json")
    bound_path = root / "control/requests" / (JOB + "_bound.json")
    script_path = root / "control/scripts" / (JOB + ".sbatch")
    intent_path = root / "control/submissions" / (JOB + ".intent.json")
    for path in (outer, plan_path, stages_path, argv_path, prepared_path, bound_path, script_path, intent_path,
                 root / "control/submissions" / (JOB + ".json"), root / "artifacts/cpu_analysis_guards" / JOB):
        require(not path.exists() and not path.is_symlink(), "New immutable destination required: " + str(path))
    outer.mkdir(parents=True)
    write_new(equivalence_path, inverse)
    write_new(feature_proof_path, proof)
    runtime_paths = ("candidate_prefix_replay_cpu_compat_v3.py", "features_legacy_compatible_v2.py", "features_generic_candidate_v1.py",
                     "screen.py", "common.py", "bounded_prefix_gate_v2.py", "__init__.py", "test_features_legacy_compatible_v2.py")
    expansion_refs = [ref(repo / "workflows/expansion" / name) for name in runtime_paths]
    old_plan = json.loads(json.dumps(plan))
    plan.update(output_root=str(output), code_sources=unique([*plan["code_sources"], *expansion_refs, *central_refs]),
                namespace_source_equivalence=ref(equivalence_path), compatibility_source_proof=ref(feature_proof_path),
                compatibility_strategy=STRATEGY, prior_paired_stop_evidence=stop_refs,
                prior_paired_prefix_boundary_tests_passed_job="4520593", paired_boundary_tests_pending=False,
                compatibility_boundary_tests_pending=True, paired10000_evaluation_pending=True,
                candidate_evaluated_only=True, radical_mechanism_claimed_proven=False)
    allowed = {"output_root", "code_sources", "namespace_source_equivalence", "paired_boundary_tests_pending"}
    require(all(plan[key] == value for key, value in old_plan.items() if key not in allowed), "Scientific scope/resources/old inputs changed")
    write_new(plan_path, plan)
    stages = {"schema": "COMPAT_FIXTURES_THEN_PAIRED_PREFIX_EVALUATION_V2", "scope_key": SCOPE,
              "repair_applied": False, "pool_modified": False, "old3prefix_fixtures_rerun": False,
              "stages": [{"name": "new_compatibility_fixtures", "argv": [PYTHON, "-B", "-m", "unittest",
                              "workflows.expansion.test_features_legacy_compatible_v2", "-v"]},
                         {"name": "actual_compatible_paired10000_not_applied", "argv": [PYTHON, "-B", "-m",
                              "workflows.expansion.candidate_prefix_replay_cpu_compat_v3", "--plan", str(plan_path),
                              "--root-submit-intent", str(intent_path)]}]}
    write_new(stages_path, stages)
    command = [PYTHON, "-B", "-m", NAMESPACE + ".run_stages_v1", "--stages", str(stages_path),
               "--root-preflight", str(intent_path), "--receipt", str(stage_receipt)]
    write_new(argv_path, command)
    helper_names = ("materialize_paired_prefix_compat_cpu_v2.py", "materialize_paired_prefix_replay_cpu_v1.py",
                    "materialize_feature_candidate_checks_v1.py", "materialize_feature_candidate_eval_v2.py")
    sources = unique([*base_refs, *namespace_refs, *central_refs, *small_refs, *plan["code_sources"], *stop_refs.values(),
                      *[ref(repo / "workflows/expansion" / name) for name in helper_names],
                      ref(equivalence_path), ref(feature_proof_path), ref(plan_path), ref(stages_path),
                      ref(policy_path), ref(decision_path), ref(repo / "workflows/data_v1_final/execution/submit_reviewed.py")])
    prepare = [PYTHON, "-B", "-m", NAMESPACE + ".prepare_request_v2", "--scope", SCOPE, "--node", node,
               "--job-name", JOB, "--command-file", str(argv_path)]
    for pin in sources:
        prepare.extend(["--source", pin["path"]])
    result = base.small.metadata_command(prepare, repo)
    require(result["status"] == "PREPARED_NOT_SUBMITTED" and result["request"] == ref(prepared_path), "Unexpected metadata preparer result")
    request, script = load(prepared_path), read_small(script_path)
    directives = dict(re.findall(r"^#SBATCH --([\w-]+)=(\S+)$", script.decode(), flags=re.MULTILINE))
    require(request["script_reference"] == ref(script_path) and script.startswith(b"#!/bin/bash\n") and b"\r" not in script and
            directives["partition"] == "cpu" and directives["nodelist"] == node and directives["mem"] == "4G" and
            directives["cpus-per-task"] == "16" and directives["time"] == "01:00:00" and
            (NAMESPACE + ".launch_v2 --intent " + str(intent_path)).encode() in script and
            ("export PYTHONPATH=" + str(repo) + ":" + DEPS + "\n").encode() in script and request["execution_argv"] == command and
            request["scope_key"] == SCOPE and request["scope_parameters"] == PARAMETERS and
            request["memory_gib"] == 4 and request["wall_seconds"] == 3600 and
            request["estimated_peak_output_bytes"] == CAP + 32 * 1024 ** 2 and request.get("partition") in (None, "cpu"),
            "Prepared script/request widened the exact compatibility evaluation resources/scope")
    data_refs = [plan["raw_file"], plan["legacy_database"]]
    require(request.get("data_references", []) in ([], [plan["raw_file"]], data_refs), "Unexpected inherited data locator")
    original = json.loads(json.dumps(request))
    request.update(partition="cpu", data_references=data_refs)
    request["source_references"] = unique([*request["source_references"], ref(prepared_path)])
    request["cpu_partition_and_data_locator_binding_proof"] = {
        "schema": "PAIRED_PREFIX_COMPAT_CPU_DATA_LOCATOR_BINDING_V2", "prepared_request": ref(prepared_path),
        "script_reference": ref(script_path), "source_authorities": [plan["raw_receipt"], plan["original_prefix_receipt"]],
        "data_references": data_refs, "large_bodies_opened_hashed_or_stat_ed": False,
        "other_science_and_resource_fields_unchanged": all(request[k] == value for k, value in original.items()
                                                         if k not in ("partition", "source_references", "data_references"))}
    require(request["cpu_partition_and_data_locator_binding_proof"]["other_science_and_resource_fields_unchanged"], "Binder widened request")
    for pin in request["source_references"]:
        verify(pin)
    write_new(bound_path, request)
    print(json.dumps({"status": "COMPAT_FIXTURES_AND_PAIRED10000_PREPARED_NOT_RUN_NOT_SUBMITTED",
                      "bound_request": ref(bound_path), "prepared_request_preserved": ref(prepared_path), "plan": ref(plan_path),
                      "stages": ref(stages_path), "entry_source_equivalence": ref(equivalence_path),
                      "compositional_feature_proof": ref(feature_proof_path), "old593STOP_evidence": stop_refs,
                      "submission_entry_for_root_only": NAMESPACE + ".submit_cpu_pilot_v3",
                      "quota_feed_read_or_written": False, "large_bodies_opened_hashed_or_stat_ed": False,
                      "old3prefix_fixtures_will_be_rerun": False, "repair_applied": False, "pool_modified": False}))


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
