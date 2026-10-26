"""Root-login metadata only: prepare the exact fixture plan and unreviewed base spec."""
import argparse
from pathlib import Path
import re

from ..cpu_auto_memory_queue_v2 import shared
from ..cpu_auto_memory_queue_v2.contract import validate_authority
from . import policy


def code_sources():
    """Read only explicit source directories/files, never scientific inputs."""
    directories = {policy.HERE, "workflows/data_v1_final/execution/cpu_auto_memory_queue_v2"}
    directories.update(str(Path(row["test_path"]).parent) for row in policy.SUITES)
    paths = {shared.REPO / relative for relative in (
        "workflows/data_v1_final/execution/queue_v1/__init__.py",
        "workflows/data_v1_final/execution/queue_v1/shared.py",
        "workflows/data_v1_final/execution/queue_v1/queue_contract.py",
        "workflows/expansion/cpu_auto_memory_v1/runtime.py",
        "workflows/expansion/full_queue_v1.py",
        "workflows/expansion/common.py",
        "workflows/expansion/materialize_full_sources_v2.py",
        "workflows/expansion/pubchem_full_v1/inventory_v2.py",
        policy.HERE + "/README.md")}
    for relative in directories:
        directory = shared.REPO / relative
        shared.need(directory.is_dir() and not directory.is_symlink(), "EXPECTED_SOURCE_DIRECTORY_REQUIRED")
        paths.update(directory.glob("*.py"))
    for row in policy.SUITES:
        shared.need(shared.REPO / row["test_path"] in paths, "EXACT_TEST_SOURCE_REQUIRED")
    for path in tuple(paths):
        for parent in path.parents:
            if parent == shared.REPO:
                break
            if shared.REPO not in parent.parents:
                continue
            package = parent / "__init__.py"
            if package.is_file():
                paths.add(package)
    return [shared.pin(path) for path in sorted(paths)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--reviewer", choices=["root"], required=True)
    args = parser.parse_args()
    shared.on_login()
    shared.need(Path(__file__).absolute().parent == shared.REPO / policy.HERE,
                "ROOT_INTEGRATED_METADATA_HELPER_REQUIRED")
    shared.need(re.fullmatch(r"[a-z0-9][a-z0-9_]{0,63}", args.tag), "SAFE_NEW_FIXTURE_TAG_REQUIRED")
    control = shared.ROOT / "control/incremental_secondary_checks_v1" / args.tag
    output = shared.ROOT / "artifacts/incremental_secondary_checks_v1" / args.tag
    shared.need(not control.exists() and not control.is_symlink() and not output.exists() and not output.is_symlink(),
                "NEW_METADATA_AND_OUTPUT_DESTINATIONS_REQUIRED")
    authority = shared.pin(shared.REPO / "configs/data_v1/user_cpu_auto_memory_20261026_v1.json")
    validate_authority(authority, read_small=shared.read_small)
    sources = code_sources()
    plan = {"schema": policy.PLAN_SCHEMA, "status": "READY", "scope_key": policy.SCOPE,
        "scope_parameters": policy.parameters(), "scope_mode": policy.MODE, "pilot": True,
        "wall_seconds": policy.WALL, "whole_output_cap_bytes": policy.CAP,
        "output_root": str(output), "code_sources": sources, "resource_authority_reference": authority,
        "data_references": [], "scientific_release_authorized": False,
        "metadata_prepared_by": args.reviewer, "prepared_at": shared.now(),
        "scope_review_not_implied_by_ready_plan": True}
    policy.validate_plan(plan)
    plan_path = control / "plan.json"
    plan_reference = shared.write_new(plan_path, plan)
    spec = {"schema": "ROOT_REVIEWED_CPU_AUTO_MEMORY_STAGE_SPEC_V1", "kind": "analysis", "pilot": True,
        "scope_key": policy.SCOPE, "scope_parameters": policy.parameters(),
        "scope": {"mode": policy.MODE, "review": None, "parent_profile": None},
        "source_status_stage": policy.MODE, "wall_seconds": policy.WALL,
        "estimated_peak_output_bytes": policy.CAP, "stage_output_cap_bytes": policy.CAP,
        "execution_argv": policy.execution_argv(plan_path, "__ROOT_STARTUP_PROOF__"),
        "source_references": [*sources, authority, plan_reference], "data_references": [],
        "deferred_authority_references": []}
    spec_reference = shared.write_new(control / "base_spec_not_request_ready.json", spec)
    receipt = {"schema": "INCREMENTAL_FIXTURE_METADATA_PREPARATION_V1",
        "status": "NOT_REQUEST_READY_REQUIRES_ACTUAL_ROOT_EXACT_SCOPE_REVIEW",
        "plan_reference": plan_reference, "base_spec_reference": spec_reference,
        "resource_authority_reference": authority, "expected_suites": 4, "expected_test_cases": policy.TOTAL,
        "tests_executed": 0, "scientific_data_bodies_read": 0, "network_requests": 0,
        "Slurm_submissions": 0, "future_scope_review_reference_fabricated": False,
        "required_next_action": "Root creates the exact FIXTURE_ONLY review and a new ready spec, then uses central-v2 materialize."}
    shared.write_new(control / "metadata_preparation_receipt.json", receipt)
    import json
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
