"""Stdlib source proof for an independently authorized, synthetic export fixture scope.

Run from the actual Root repository after Root creates and freezes the new
scope/decision. This program never runs fixtures, science or scheduler commands.
Fixture count is read from matching policy/decision parameters, never fixed here.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import stat

REPO = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/repository")
OLD = REPO / "workflows/data_v1_final/execution/cpu_prefix_replay_v1"
NEW = REPO / "workflows/data_v1_final/execution/cpu_export_fixture_v1"
POLICY = REPO / "configs/data_v1/cpu_export_fixture_scopes_v1.json"
DECISION = REPO / "configs/data_v1/cpu_export_fixture_decision_v1.json"
SCOPE = "sampling_index_adapter_fixtures"
FILES = ("__init__.py", "policy.py", "probe_memory.py", "runtime.py", "runtime_v2.py",
         "launch.py", "launch_v2.py", "submit_cpu_pilot_v1.py", "submit_cpu_pilot_v3.py",
         "prepare_request_v2.py", "run_stages_v1.py")
EDITS = (("cpu_prefix_replay_v1", "cpu_export_fixture_v1"),
         ("configs/data_v1/cpu_prefix_replay_scopes_v1.json", "configs/data_v1/cpu_export_fixture_scopes_v1.json"),
         ("configs/data_v1/cpu_prefix_replay_decision_v1.json", "configs/data_v1/cpu_export_fixture_decision_v1.json"))


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def read_small(path):
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), "LITERAL_SMALL_SOURCE_REQUIRED")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_uid == 1278 and before.st_size <= 2 * 1024**2,
                "SMALL_CODE_METADATA_OWNER_TYPE_OR_2MIB_LIMIT")
        raw = stream.read(2 * 1024**2 + 1)
        after = os.fstat(stream.fileno())
    require(len(raw) == before.st_size and
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "SMALL_SOURCE_CHANGED")
    return raw


def pin(path, raw):
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path):
    raw = read_small(path)
    return json.loads(raw), pin(path, raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    require(Path(__file__).absolute() == NEW / "verify_namespace_v1.py", "ACTUAL_ROOT_PROOF_ENTRY_REQUIRED")
    rows = []
    for name in FILES:
        before, after = read_small(OLD / name), read_small(NEW / name)
        expected = before
        for old, new in EDITS:
            expected = expected.replace(old.encode(), new.encode())
        require(expected == after, "UNDECLARED_NON_NAMESPACE_SOURCE_EDIT:" + name)
        inverse = after
        for old, new in reversed(EDITS):
            inverse = inverse.replace(new.encode(), old.encode())
        require(inverse == before, "INVERSE_FULL_FILE_BYTES_DIFFER:" + name)
        require(ast.dump(ast.parse(inverse), include_attributes=False) ==
                ast.dump(ast.parse(before), include_attributes=False), "NORMALIZED_MODULE_AST_DIFFERS:" + name)
        rows.append({"filename": name, "baseline_reference": pin(OLD / name, before),
                     "variant_reference": pin(NEW / name, after),
                     "inverse_full_file_bytes_equal": True, "normalized_AST_identical": True})
    cfg, policy_pin = load(POLICY)
    decision, decision_pin = load(DECISION)
    require(cfg["decision_reference"] == decision_pin, "ACTUAL_INDEPENDENT_DECISION_PIN_REQUIRED")
    require(set(cfg["scopes"]) == {SCOPE} and cfg["formal_generation_authorized"] is False and
            cfg["resource_policy"] == "CPU_BOUNDED_TEST_LIVE_MEMORY_V1", "ONLY_NEW_SYNTHETIC_FIXTURE_SCOPE_ALLOWED")
    scope = cfg["scopes"][SCOPE]
    parameters = scope["parameters"]
    require(isinstance(parameters, dict) and parameters and parameters == decision["scope_parameters"] and
            decision["authorized_scope_key"] == SCOPE, "FIXTURE_PARAMETERS_MUST_EQUAL_INDEPENDENT_ROOT_DECISION")
    require(type(parameters.get("fixture_tests")) is int and parameters["fixture_tests"] > 0 and
            isinstance(parameters.get("test_module"), str) and parameters["test_module"] and
            type(parameters.get("input_corpus_records")) is int and parameters["input_corpus_records"] == 0 and
            type(parameters.get("new_UFF_QM_calls")) is int and parameters["new_UFF_QM_calls"] == 0 and
            parameters.get("real_export_release") is False, "CONCRETE_SYNTHETIC_TEST_COUNT_WITHOUT_CORPUS_QM_OR_RELEASE_REQUIRED")
    require(scope["memory_gib"] == 4 and type(scope["wall_seconds"]) is int and 0 < scope["wall_seconds"] <= 3600 and
            scope["output_cap_bytes"] == 64 * 1024**2, "FIXTURE_4G_LE1H_64MIB_BUDGET_REQUIRED")
    resources = decision["resources"]
    require(resources["cpus"] == 16 and resources["memory_gib"] == 4 and
            resources["wall_seconds"] == scope["wall_seconds"] and resources["science_cap_bytes"] == 64 * 1024**2,
            "DECISION_AND_SCOPE_RESOURCE_VALUES_DIFFER")
    require(decision.get("formal_generation_authorized", False) is False and
            decision.get("automatic_submission_or_retry", False) is False, "NO_FORMAL_OR_AUTOMATIC_SUBMISSION_AUTHORITY")
    # The inherited10k policy/data locators are not a fixture authorization.
    # Verify the new metadata-only base rather than inheriting a real raw corpus.
    base_reference = scope["base_request_reference"]
    base, base_pin = load(Path(base_reference["path"]))
    require(base_pin == {k: base_reference[k] for k in ("path", "bytes", "sha256")} and
            base.get("data_references", []) == [], "FIXTURES_MUST_NOT_INHERIT_REAL_CORPUS_DATA_LOCATORS")
    result = {"schema": "CPU_EXPORT_FIXTURE_NAMESPACE_EQUIVALENCE_V1", "status": "PASS",
        "namespace": str(NEW), "baseline_namespace": str(OLD), "declared_edits": EDITS, "files": rows,
        "scope_policy_reference": policy_pin, "decision_reference": decision_pin, "base_request_reference": base_pin,
        "scope_key": SCOPE, "parameters_equal_to_root_decision": parameters,
        "fixture_count_hardcoded_in_proof": False, "resource_guards_unchanged": True,
        "changes_restricted_to_namespace_and_policy_paths": True, "cpus": 16, "memory_gib": 4,
        "wall_seconds": scope["wall_seconds"], "scientific_output_cap_bytes": 64 * 1024**2,
        "real_corpus_data_locators_inherited": False, "formal_generation_authorized": False,
        "proof_source_reference": pin(Path(__file__).absolute(), read_small(Path(__file__).absolute())),
        "science_or_tests_executed": False,
        "tests_or_science_or_scheduler_commands_executed": False,
        "limits": "Source/authorization binding only. Exact fixture count comes from the independent Root decision; actual fixtures require a separately prepared monitored CPU allocation."}
    require(args.output.is_absolute() and not args.output.exists() and
            not any(p.is_symlink() for p in (args.output, *args.output.parents)), "NEW_LITERAL_PROOF_OUTPUT_REQUIRED")
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps({"status": "PASS_SOURCE_ONLY_NOT_TESTS", "files": len(rows), "output": str(args.output)}))


if __name__ == "__main__":
    main()
