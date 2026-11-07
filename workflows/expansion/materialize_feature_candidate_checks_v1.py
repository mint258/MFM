"""Root metadata preparation of four candidate tests then proposed three-CID evaluation.

Runs only a source-AST metadata proof and the central request preparer. Never
runs scientific/tests/stages, refreshes quota, probes a node or submits a job.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess


ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
PYTHON = "/share/home/zixiao/.conda/envs/chemprop/bin/python"
DEPS = "/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage61_data_input_audit_v1/scan_v2/deps"
SCOPE = "prefix_feature_three_cid"
JOB = "dv1_feature_candidate_checks_v1"
SMALL_LIMIT = 2 * 1024 ** 2
CENTRAL = ("__init__.py", "policy.py", "runtime.py", "probe_memory.py", "launch.py", "submit_cpu_pilot_v1.py",
           "runtime_v2.py", "launch_v2.py", "submit_cpu_pilot_v2.py", "submit_cpu_pilot_v3.py",
           "prepare_request_v2.py", "run_stages_v1.py")
CANDIDATE = ("workflows/expansion/features_generic_candidate_v1.py", "workflows/expansion/candidate_feature_eval_v1.py",
             "workflows/expansion/test_feature_candidate_v1.py", "configs/data_v1/expansion/candidate_feature_eval_plan_template_v1.json",
             "docs/expansion/feature_generic_order_proposal_v1.md")


def require(value, message):
    if not value:
        raise ValueError(message)


def read_small(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and path.is_file() and not path.is_symlink(), "Literal small regular source required")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(before.st_size <= SMALL_LIMIT, "Small source exceeds2MiB: " + str(path))
        raw = stream.read(SMALL_LIMIT + 1)
        after = os.fstat(stream.fileno())
    frame = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns)
    require(len(raw) == before.st_size <= SMALL_LIMIT and frame(before) == frame(after), "Small source changed while read")
    return raw


def ref(path):
    raw = read_small(path)
    return {"path": str(Path(path)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path):
    return json.loads(read_small(path))


def verify(pin):
    require(set(pin) == {"path", "bytes", "sha256"} and pin["bytes"] <= SMALL_LIMIT and ref(pin["path"]) == pin,
            "Exact small source changed: " + str(pin.get("path")))


def unique(pins):
    result = {}
    for pin in pins:
        require(pin["path"] not in result or result[pin["path"]] == pin, "Conflicting source pins")
        result[pin["path"]] = pin
    return list(result.values())


def write_new(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def metadata_command(argv, repo):
    env = dict(os.environ, PYTHONPATH=str(repo) + ":" + DEPS, PYTHONDONTWRITEBYTECODE="1")
    proc = subprocess.run(argv, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                          capture_output=True, text=True, timeout=60)
    require(proc.returncode == 0, "Root metadata command failed; no automatic retry: " +
            json.dumps({"argv": argv, "rc": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}))
    return json.loads(proc.stdout)


def materialize(repository, run_root, reviewer, node):
    repo, root = Path(repository), Path(run_root)
    require(os.name == "posix" and os.getuid() == 1278 and socket.gethostname().split(".")[0] == "sonmi" and
            reviewer == "root" and root == ROOT and repo == ROOT / "repository" and
            Path(__file__).absolute() == repo / "workflows/expansion/materialize_feature_candidate_checks_v1.py",
            "Root must first merge/review and personally run metadata preparation on sonmi")
    require(node in {"compute-0-2", *(f"compute-0-{i}" for i in range(8, 20))}, "Only actual CPU2/8-19 nodes allowed, never21")
    central = repo / "workflows/data_v1_final/execution/cpu_analysis_v1"
    policy_path, decision_path = (repo / "configs/data_v1" / n for n in
                                  ("cpu_analysis_small_scopes_v1.json", "run_decisions_v4.json"))
    scope = load(policy_path)["scopes"][SCOPE]
    require(scope["parameters"] == {"target_cids": [7, 52, 53], "input_prefix_limit": 10000, "repair_or_pool_release": False} and
            scope["memory_gib"] == 4 and scope["wall_seconds"] == 3600 and scope["output_cap_bytes"] == 32 * 1024 ** 2,
            "Use the exact existing three-CID/4GiB/1h/no-applied-repair scope")
    verify(scope["base_request_reference"])
    base = load(scope["base_request_reference"]["path"])
    for pin in [base["script_reference"], *base["source_references"], *scope.get("authority_references", [])]:
        verify(pin)
    plan = load(repo / CANDIDATE[3])
    require(plan["schema"] == "pubchem_feature_candidate_evaluation_plan_v1" and plan["target_cids"] == [7, 52, 53] and
            all(plan[k] is False for k in ("repair_applied", "pool_modified", "full_10k_replay_authorized")) and
            plan["peak_output_cap_bytes"] == 32 * 1024 ** 2, "Do not widen the proposed-only candidate evaluation")
    evidence = [plan[k] for k in ("diagnostic_receipt", "diagnostic_traces", "diagnostic_monitor_closure")]
    for pin in evidence:
        verify(pin)
    diagnostic, monitor = load(evidence[0]["path"]), load(evidence[2]["path"])
    require(diagnostic["job_id"] == monitor["job_id"] == "4520484" and diagnostic["traces"] == evidence[1] and
            diagnostic["selected_cids"] == [7, 52, 53] and monitor["status"] == "COMPLETED_NO_MEMORY_DENIAL" and
            monitor["child_returncode"] == 0 and monitor["first_denial"] is None,
            "Exact successful actual diagnostic evidence required")
    candidate_refs = [ref(repo / path) for path in CANDIDATE]
    central_refs = [ref(central / name) for name in CENTRAL]
    runtime_refs = [ref(repo / path) for path in ("workflows/expansion/common.py", "workflows/expansion/screen.py",
                                                "workflows/expansion/__init__.py")]
    require(ref(repo / "workflows/expansion/screen.py") == diagnostic["registered_screen_source"], "Original screen.py changed")
    outer = root / "artifacts/expansion/diagnostics/candidate_feature_checks_v1"
    evaluation = outer / "candidate_evaluation"
    proof_path, stage_receipt = outer / "source_scope_proof.json", outer / "stage_receipt.json"
    plan_path = root / "control/requests" / (JOB + "_plan.json")
    stages_path = root / "control/requests" / (JOB + "_stages.json")
    argv_path = root / "control/requests" / (JOB + "_argv.json")
    prepared_request = root / "control/requests" / (JOB + ".json")
    bound_request = root / "control/requests" / (JOB + "_bound.json")
    script_path = root / "control/scripts" / (JOB + ".sbatch")
    intent_path = root / "control/submissions" / (JOB + ".intent.json")
    for path in (outer, plan_path, stages_path, argv_path, prepared_request, bound_request, script_path, intent_path,
                 root / "control/submissions" / (JOB + ".json"), root / "artifacts/cpu_analysis_guards" / JOB):
        require(not path.exists() and not path.is_symlink(), "Preserve existing destination and audit; no automatic retry: " + str(path))
    source_proof = metadata_command([PYTHON, "-B", "-m", "workflows.expansion.features_generic_candidate_v1", "--verify-source-only"], repo)
    require(source_proof["status"] == "ONLY_GENERIC_RING_BLOCK_DIFFERS_NON_RING_AST_IDENTICAL" and
            source_proof["repair_applied"] is False and source_proof["pool_modified"] is False,
            "Source AST proof failed; never run tests/science during metadata preparation")
    outer.mkdir(parents=True)
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    write_new(proof_path, source_proof)
    plan.update(status="READY", output_root=str(evaluation), central_runtime_references=central_refs,
                code_sources=unique([*candidate_refs[:3], *runtime_refs, *central_refs]),
                source_only_ast_proof=ref(proof_path), staged_tests_pending=True, proposed_three_cid_evaluation_pending=True)
    plan.pop("blocking_pending_items", None)
    write_new(plan_path, plan)
    stages = {"schema": "PUBCHEM_CANDIDATE_PROPOSED_ONLY_STAGES_V1", "scope_key": SCOPE,
              "repair_applied": False, "pool_modified": False, "stages": [
                  {"name": "four_candidate_boundary_tests", "argv": [PYTHON, "-B", "-m", "unittest", "workflows.expansion.test_feature_candidate_v1", "-v"]},
                  {"name": "three_actual_cids_candidate_evaluation_not_applied", "argv": [PYTHON, "-B", "-m", "workflows.expansion.candidate_feature_eval_v1",
                       "--plan", str(plan_path), "--root-submit-intent", str(intent_path)]}]}
    write_new(stages_path, stages)
    command = [PYTHON, "-B", "-m", "workflows.data_v1_final.execution.cpu_analysis_v1.run_stages_v1",
               "--stages", str(stages_path), "--root-preflight", str(intent_path), "--receipt", str(stage_receipt)]
    write_new(argv_path, command)
    sources = unique([*candidate_refs, *runtime_refs, *central_refs, *evidence, ref(policy_path), ref(decision_path),
                      ref(Path(__file__).absolute()), ref(plan_path), ref(stages_path), ref(proof_path),
                      ref(repo / "workflows/data_v1_final/execution/submit_reviewed.py")])
    prepare = [PYTHON, "-B", "-m", "workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2",
               "--scope", SCOPE, "--node", node, "--job-name", JOB, "--command-file", str(argv_path)]
    for pin in sources:
        prepare.extend(["--source", pin["path"]])
    prepare_result = metadata_command(prepare, repo)
    require(prepare_result["status"] == "PREPARED_NOT_SUBMITTED" and prepare_result["request"] == ref(prepared_request),
            "Central metadata preparer returned unexpected request")
    request = load(prepared_request)
    script = read_small(script_path)
    require(ref(script_path) == request["script_reference"] and script.startswith(b"#!/bin/bash\n") and b"\r" not in script,
            "Exact LF script proof required before adding request partition")
    directives = dict(re.findall(r"^#SBATCH --([\w-]+)=(\S+)$", script.decode(), flags=re.MULTILINE))
    require(directives["partition"] == "cpu" and directives["nodelist"] == node and directives["cpus-per-task"] == "16" and
            directives["mem"] == "4G" and directives["time"] == "01:00:00" and b"cpu_analysis_v1.launch_v2 --intent " in script and
            request["execution_argv"] == command and request["scope_key"] == SCOPE and
            request["scope_parameters"] == scope["parameters"] and request["estimated_peak_output_bytes"] == 64 * 1024 ** 2,
            "Prepared script/science/resource contract differs")
    require(request.get("partition") in (None, "cpu"), "Prepared request contradicts its actual CPU script")
    # The central preparer's original JSON stays immutable. A new small bound
    # request adds the missing partition with exact unchanged-script evidence.
    original = json.loads(json.dumps(request))
    request["partition"] = "cpu"
    request["source_references"] = unique([*request["source_references"], ref(prepared_request)])
    request["cpu_partition_binding_proof"] = {
        "schema": "CPU_PARTITION_REQUEST_BINDING_V1", "prepared_request": ref(prepared_request),
        "script_reference": ref(script_path), "script_partition": "cpu",
        "other_requested_science_and_resource_fields_unchanged": all(
            request[key] == value for key, value in original.items() if key not in ("partition", "source_references")),
    }
    require(request["cpu_partition_binding_proof"]["other_requested_science_and_resource_fields_unchanged"], "Partition binder widened request")
    for pin in request["source_references"]:
        verify(pin)
    write_new(bound_request, request)
    print(json.dumps({"status": "CANDIDATE_STAGES_PREPARED_NOT_RUN_NOT_SUBMITTED", "bound_request": ref(bound_request),
                      "prepared_request_preserved": ref(prepared_request), "plan": ref(plan_path), "stages": ref(stages_path),
                      "source_ast_proof": ref(proof_path), "stage_receipt_expected": str(stage_receipt),
                      "candidate_output_expected": str(evaluation), "source_references": request["source_references"],
                      "submission_entry_for_root_only": "workflows.data_v1_final.execution.cpu_analysis_v1.submit_cpu_pilot_v3",
                      "quota_feed_read_or_written": False, "raw_body_read_or_stat": False,
                      "repair_applied": False, "pool_modified": False}))


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
