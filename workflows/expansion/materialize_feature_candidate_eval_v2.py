"""Root metadata only: evaluate the same three CIDs after the actual four tests.

Preserves failed job4520545 and its quota evidence. Does not execute scientific
code/tests, refresh quota, probe nodes or submit. Root personally invokes the
central metadata preparer, then reviews the new immutable request separately.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import socket

from . import materialize_feature_candidate_checks_v1 as previous


ROOT = previous.ROOT
PYTHON = previous.PYTHON
SCOPE = previous.SCOPE
JOB = "dv1_feature_candidate_eval_v2"
PRIOR_JOB = "dv1_feature_candidate_checks_v1"
require, read_small, ref, load = previous.require, previous.read_small, previous.ref, previous.load
verify, unique, write_new = previous.verify, previous.unique, previous.write_new


def prior_evidence(root):
    """Require the actual passed test stage and exact pre-CID quota failure."""
    old_outer = root / "artifacts/expansion/diagnostics/candidate_feature_checks_v1"
    paths = {
        "prior_plan": root / "control/requests" / (PRIOR_JOB + "_plan.json"),
        "prior_stages": root / "control/requests" / (PRIOR_JOB + "_stages.json"),
        "prior_intent": root / "control/submissions" / (PRIOR_JOB + ".intent.json"),
        "prior_submission": root / "control/submissions" / (PRIOR_JOB + ".json"),
        "actual_stage_receipt": old_outer / "stage_receipt.json",
        "actual_tests_stdout": root / "control/dv1_feature_candidate_checks_v1_4520545.out",
        "actual_monitor_closure": root / "artifacts/cpu_analysis_guards" / PRIOR_JOB / "closure.json",
        "actual_evaluation_failure": old_outer / "candidate_evaluation/failure.json",
        "actual_stale_quota_snapshot": old_outer / "candidate_evaluation/quota_start.json",
    }
    pins = {name: ref(path) for name, path in paths.items()}
    old_plan, stages, intent, submission, receipt, monitor, failure = (
        load(paths[k]) for k in ("prior_plan", "prior_stages", "prior_intent", "prior_submission",
                                "actual_stage_receipt", "actual_monitor_closure", "actual_evaluation_failure"))
    require(submission["job_id"] == monitor["job_id"] == "4520545" and
            submission["sbatch_returncode"] == 0 and submission["request"] == intent["request"] and
            receipt["root_preflight"] == monitor["intent_reference"] == pins["prior_intent"] and
            receipt["stages_reference"] == pins["prior_stages"], "Only actual bound4520545 evidence is accepted")
    expected_test_argv = [PYTHON, "-B", "-m", "unittest", "workflows.expansion.test_feature_candidate_v1", "-v"]
    expected_eval_argv = [PYTHON, "-B", "-m", "workflows.expansion.candidate_feature_eval_v1", "--plan",
                          str(paths["prior_plan"]), "--root-submit-intent", str(paths["prior_intent"])]
    require(receipt["schema"] == "FINITE_CPU_STAGE_SEQUENCE_V1" and receipt["scope_key"] == SCOPE and
            receipt["status"] == "STAGE_FAILED_NO_RETRY" and len(receipt["stages"]) == 2 and
            len(stages["stages"]) == 2 and
            receipt["stages"][0]["argv"] == stages["stages"][0]["argv"] == expected_test_argv and
            receipt["stages"][0]["returncode"] == 0 and
            receipt["stages"][1]["argv"] == stages["stages"][1]["argv"] == expected_eval_argv and
            receipt["stages"][1]["returncode"] == 1 and receipt["forced_signals_sent"] is False,
            "Require the completed original test stage; do not rerun tests or call failed evaluation successful")
    stdout = read_small(paths["actual_tests_stdout"]).decode()
    passed_lines = re.findall(r"^test_\S+ \(workflows\.expansion\.test_feature_candidate_v1\.[^\n]+\) \.\.\. ok$",
                             stdout, flags=re.MULTILINE)
    require(len(passed_lines) == 4 and re.search(r"\nRan 4 tests in [0-9.]+s\n\nOK\n", stdout) and
            failure == {"status": "CANDIDATE_EVALUATION_FAILED_NOT_APPLIED", "type": "ValueError",
                        "error": "Quota observation older than five minutes"} and
            monitor["schema"] == "CPU_BOUNDED_TEST_MONITOR_CLOSURE_V1" and
            monitor["child_returncode"] == 1 and monitor["first_denial"] is None and
            monitor["monitor_io_failure"] is None and monitor["signals_sent"] is False and
            monitor["durable_evidence_exported"] is True,
            "Require four actual passes plus preserved pre-CID stale-quota failure, not a science acceptance")
    declared = {p["path"]: p for p in intent["request"]["source_references"]}
    require(declared.get(str(paths["prior_plan"])) == pins["prior_plan"] and
            declared.get(str(paths["prior_stages"])) == pins["prior_stages"], "Prior plan/stages were not bound")
    for pin in [*old_plan["code_sources"], *old_plan["central_runtime_references"], old_plan["source_only_ast_proof"]]:
        require(declared.get(pin["path"]) == pin, "Prior exact code/AST proof authority missing")
        verify(pin)
    return old_plan, pins


def materialize(repository, run_root, reviewer, node):
    repo, root = Path(repository), Path(run_root)
    require(os.name == "posix" and os.getuid() == 1278 and socket.gethostname().split(".")[0] == "sonmi" and
            reviewer == "root" and root == ROOT and repo == ROOT / "repository" and
            Path(__file__).absolute() == repo / "workflows/expansion/materialize_feature_candidate_eval_v2.py",
            "Root must merge/review then personally run metadata preparation on sonmi")
    require(node in {"compute-0-2", *(f"compute-0-{i}" for i in range(8, 20))}, "Only CPU2/8-19 allowed")
    central = repo / "workflows/data_v1_final/execution/cpu_analysis_v1"
    policy_path = repo / "configs/data_v1/cpu_analysis_small_scopes_v1.json"
    scope = load(policy_path)["scopes"][SCOPE]
    require(scope["parameters"] == {"target_cids": [7, 52, 53], "input_prefix_limit": 10000, "repair_or_pool_release": False} and
            scope["memory_gib"] == 4 and scope["wall_seconds"] == 3600 and scope["output_cap_bytes"] == 32 * 1024 ** 2,
            "Exact existing three-CID/4G/1h scope only; full10k is not authorized")
    verify(scope["base_request_reference"])
    base = load(scope["base_request_reference"]["path"])
    for pin in [base["script_reference"], *base["source_references"], *scope.get("authority_references", [])]:
        verify(pin)
    plan, prior = prior_evidence(root)
    require(plan["schema"] == "pubchem_feature_candidate_evaluation_plan_v1" and plan["status"] == "READY" and
            plan["target_cids"] == [7, 52, 53] and plan["peak_output_cap_bytes"] == 32 * 1024 ** 2 and
            all(plan[k] is False for k in ("repair_applied", "pool_modified", "full_10k_replay_authorized")),
            "Frozen original proposed-only scientific plan required")
    evidence = [plan[k] for k in ("diagnostic_receipt", "diagnostic_traces", "diagnostic_monitor_closure")]
    for pin in evidence:
        verify(pin)
    plan_path = root / "control/requests" / (JOB + "_plan.json")
    argv_path = root / "control/requests" / (JOB + "_argv.json")
    prepared_path = root / "control/requests" / (JOB + ".json")
    bound_path = root / "control/requests" / (JOB + "_bound.json")
    script_path = root / "control/scripts" / (JOB + ".sbatch")
    intent_path = root / "control/submissions" / (JOB + ".intent.json")
    output = root / "artifacts/expansion/diagnostics/candidate_feature_eval_v2"
    for path in (plan_path, argv_path, prepared_path, bound_path, script_path, intent_path, output,
                 root / "control/submissions" / (JOB + ".json"), root / "artifacts/cpu_analysis_guards" / JOB):
        require(not path.exists() and not path.is_symlink(), "New immutable destination required: " + str(path))
    old_plan = json.loads(json.dumps(plan))
    plan.update(output_root=str(output), staged_tests_pending=False,
                prior_four_tests_actual_pass={"job_id": "4520545", "passed_tests": 4, "test_stage_returncode": 0,
                                             "tests_rerun_by_this_request": False, "references": prior},
                prior_failed_evaluation_retained=True)
    require(all(plan[k] == value for k, value in old_plan.items() if k not in ("output_root", "staged_tests_pending")),
            "Scientific sources, CID set, algorithms or resources changed")
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    write_new(plan_path, plan)
    command = [PYTHON, "-B", "-m", "workflows.expansion.candidate_feature_eval_v1", "--plan", str(plan_path),
               "--root-submit-intent", str(intent_path)]
    write_new(argv_path, command)
    sources = unique([*plan["code_sources"], *plan["central_runtime_references"], *evidence,
                      plan["source_only_ast_proof"], *prior.values(), ref(plan_path), ref(Path(__file__).absolute()),
                      ref(repo / "workflows/expansion/materialize_feature_candidate_checks_v1.py"),
                      ref(central / "submit_cpu_pilot_v3.py"),
                      ref(repo / "workflows/data_v1_final/execution/submit_reviewed.py")])
    prepare = [PYTHON, "-B", "-m", "workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2",
               "--scope", SCOPE, "--node", node, "--job-name", JOB, "--command-file", str(argv_path)]
    for pin in sources:
        prepare.extend(["--source", pin["path"]])
    prepared = previous.metadata_command(prepare, repo)
    require(prepared["status"] == "PREPARED_NOT_SUBMITTED" and prepared["request"] == ref(prepared_path),
            "Unexpected central metadata preparer result")
    request, script = load(prepared_path), read_small(script_path)
    directives = dict(re.findall(r"^#SBATCH --([\w-]+)=(\S+)$", script.decode(), flags=re.MULTILINE))
    require(request["script_reference"] == ref(script_path) and script.startswith(b"#!/bin/bash\n") and b"\r" not in script and
            directives["partition"] == "cpu" and directives["nodelist"] == node and
            directives["cpus-per-task"] == "16" and directives["mem"] == "4G" and directives["time"] == "01:00:00" and
            b"cpu_analysis_v1.launch_v2 --intent " in script and request["execution_argv"] == command and
            request["scope_key"] == SCOPE and request["scope_parameters"] == scope["parameters"] and
            request["estimated_peak_output_bytes"] == 64 * 1024 ** 2 and request.get("partition") in (None, "cpu"),
            "Exact single-evaluation CPU script/resource proof failed")
    original = json.loads(json.dumps(request))
    request["partition"] = "cpu"
    request["source_references"] = unique([*request["source_references"], ref(prepared_path)])
    request["cpu_partition_binding_proof"] = {
        "schema": "CPU_PARTITION_REQUEST_BINDING_V1", "prepared_request": ref(prepared_path),
        "script_reference": ref(script_path), "script_partition": "cpu",
        "other_requested_science_and_resource_fields_unchanged": all(
            request[key] == value for key, value in original.items() if key not in ("partition", "source_references")),
    }
    require(request["cpu_partition_binding_proof"]["other_requested_science_and_resource_fields_unchanged"], "Scope changed")
    for pin in request["source_references"]:
        verify(pin)
    write_new(bound_path, request)
    print(json.dumps({"status": "THREE_CID_EVALUATION_PREPARED_NOT_RUN_NOT_SUBMITTED", "bound_request": ref(bound_path),
                      "prepared_request_preserved": ref(prepared_path), "plan": ref(plan_path), "prior_actual_test_job": "4520545",
                      "prior_four_tests_pass": True, "tests_will_be_rerun": False, "candidate_receipt_expected": str(output / "receipt.json"),
                      "submission_entry_for_root_only": "workflows.data_v1_final.execution.cpu_analysis_v1.submit_cpu_pilot_v3",
                      "quota_feed_read_or_written": False, "raw_body_read_or_stat": False,
                      "repair_applied": False, "pool_modified": False, "full_10k_authorized": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", required=True, type=Path)
    parser.add_argument("--run-root", required=True, type=Path)
    parser.add_argument("--reviewer", required=True, choices=["root"])
    parser.add_argument("--node", required=True)
    args = parser.parse_args()
    materialize(args.repository, args.run_root, args.reviewer, args.node)


if __name__ == "__main__":
    main()
