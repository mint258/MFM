"""Freeze one complete four-pytest parent using the tested v4 control functions.

Metadata/Git/source freeze only. No test, model, submission or monitoring loop.
The candidate must have a real clean local commit; public registration may follow
full regression. Original two-stage enrollment and fixture/supervisor code remain.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from identity_revision_v4 import file_ref, load_fixed_control, require, verify_source_pins

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-pins", type=Path, required=True)
    parser.add_argument("--source-pins-sha256", required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--spec-sha256", required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--label", required=True)
    args = parser.parse_args()
    pins = verify_source_pins(args.source_pins, args.source_pins_sha256)
    require(file_ref(Path(__file__).resolve()) in pins["runtime_sources"], "Metadata freeze source is not bound")
    require(file_ref(args.spec) in pins["runtime_sources"], "Exact complete-suite spec is not source-bound")
    control = load_fixed_control(pins)
    spec = control.json_file(args.spec, args.spec_sha256)
    require(spec["schema"] == "model_v3_numeric_single_parent_spec_v1"
            and spec["parent_count"] == 1 and spec["pytest_children"] == 4,
            "Only the complete one-parent/four-child spec is admitted")
    require(re.fullmatch("[A-Za-z0-9_]{1,64}", args.label)
            and control.COMMIT.fullmatch(args.code_commit), "Fresh simple label and actual commit required")
    root = Path(spec["tree"]).absolute()
    actual_git = control.git_clean_snapshot(root)
    require(actual_git["head"] == args.code_commit, "Local clean snapshot differs from Root's machine commit")
    scope = control.source_scope(spec["source_scope"]["external_python"],
                                 spec["source_scope"]["workflow_config_files"])
    require(scope == spec["source_scope"], "Exact already tested v4 runtime scope required")
    sources = control.capture_sources(root, scope, args.code_commit)
    test_hashes = {name: sha for name, sha in sources["runtime"]["project_source_sha256"].items()
                   if Path(name).parent == Path("current/tests") and Path(name).name.startswith("test_")}
    recursive_tests = {str(path.relative_to(root)) for path in (root/"current/tests").rglob("test_*.py")}
    require(test_hashes == spec["all_test_file_sha256"] and set(test_hashes) == recursive_tests
            and len(test_hashes) == spec["test_file_count"] == 113,
            "Added, deleted, changed or nested test module; do not omit optional tests")
    for ref in spec["candidate_frozen_sources"]:
        require(control.file_sha(ref["path"]) == ref["sha256"], "Candidate frozen source drift")
    names = sorted(test_hashes)
    assignment = {"schema": control.ASSIGNMENT_SCHEMA, "code_sha": args.code_commit,
        "partitions": 1, "all_test_file_sha256": test_hashes,
        "assignments": [{"index": 0, "files": names}],
        "per_job_output_budget_bytes": 2*1024**3,
        "planning_only_expected_collection": spec["planning_only_expected_collection"],
        "historic_full_certificate": spec["historic_full_certificate"],
        "skip_scope": "All ordinary/optional tests selected; actual skips are recorded, not historical reader acceptance",
        "capacity_is_a_conservative_plan_not_peak_proof": True}
    control.validate_assignment(assignment, args.code_commit)
    runs = control.RUNS
    assignment_path = runs/(args.label+"_assignment_v1.json")
    plan_path = runs/(args.label+"_control_v1.json")
    binding_path = runs/(args.label+"_part0_bindings_v1.json")
    launch_path = runs/(args.label+"_part0_launch_v1.json")
    receipt_path = runs/(args.label+"_part0_submission_v1.json")
    require(not any(path.exists() for path in (assignment_path, plan_path, binding_path, launch_path, receipt_path)),
            "Fresh label required; keep previous partial evidence")
    assignment_sha = control.write_exclusive(assignment_path, assignment)
    controls = {ref["path"]: ref["sha256"] for ref in pins["runtime_sources"]}
    controls.update({ref["path"]: ref["sha256"] for ref in spec["candidate_frozen_sources"]})
    controls[str(args.source_pins.absolute())] = args.source_pins_sha256
    controls[str(args.spec.absolute())] = args.spec_sha256
    contract = {"tree": str(root), "code_sha": args.code_commit, "runs": str(runs),
        "control_root": str(control.CONTROL), "plan_path": str(plan_path),
        "python": "/share/home/zixiao/.conda/envs/chemprop/bin/python", "runtime": sources["runtime"],
        "assignment": {"path": str(assignment_path), "sha256": assignment_sha},
        "runner": {"path": str(HERE/"run_regression_worker_identity_v4.py"),
                   "sha256": control.file_sha(HERE/"run_regression_worker_identity_v4.py")},
        "scheduler_script": {"path": str(HERE/"run_numeric_full_regression_v1.sbatch"),
                             "sha256": control.file_sha(HERE/"run_numeric_full_regression_v1.sbatch")},
        "control_files": [{"path": path, "sha256": sha} for path, sha in sorted(controls.items())],
        "binding_paths": [str(binding_path)], "receipt_paths": [str(receipt_path)],
        "capacity_is_a_conservative_plan_not_peak_proof": True}
    values = control.base_bindings(contract, 0)
    binding_sha = control.write_exclusive(binding_path, values)
    plan = {"schema": control.PLAN_SCHEMA, "contract": contract,
        "contract_sha256": control.digest_bytes(control.canonical(contract)),
        "bindings": [{"path": str(binding_path), "sha256": binding_sha, "values": values}]}
    plan_sha = control.write_exclusive(plan_path, plan)
    control.verify_frozen_plan(plan_path, plan_sha)
    launch = control.launch_bindings(plan, plan_sha, 0)
    launch_sha = control.write_exclusive(launch_path, launch)
    control.require(control.json_file(launch_path, launch_sha) == launch, "Fresh launch binding differs")
    import json
    print(json.dumps({"status": "FROZEN_NOT_EXECUTED", "plan": str(plan_path), "plan_sha256": plan_sha,
        "code_commit": args.code_commit, "source_scope": scope["schema"], "test_file_count": len(names),
        "parent_count": 1, "workers": 4, "planning_only_expected_collection": spec["planning_only_expected_collection"],
        "launch_bindings": str(launch_path), "launch_bindings_sha256": launch_sha,
        "scheduler_script": contract["scheduler_script"], "submission_receipt": str(receipt_path)}, sort_keys=True))


if __name__ == "__main__":
    main()
