"""Root metadata helper: bind existing small sources, never approve/submit/probe."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

from workflows.data_v1_final.execution.queue_v1 import shared
from .. import full_queue_v1 as execution
from .catalog import CAP, SCOPE, WALL, parameters, validate_catalog


def materialize(tag, goal_authority, reviewer):
    shared.on_login()
    shared.need(reviewer == "root" and re.fullmatch(r"[a-z0-9_]+", tag), "ROOT_METADATA_REVIEWER_AND_NEW_TAG_REQUIRED")
    shared.need(Path(__file__).absolute() == shared.REPO / "workflows/expansion/official_source_probe_v1/materialize.py",
                "ROOT_INTEGRATED_METADATA_HELPER_REQUIRED")
    catalog_path = shared.REPO / "configs/data_v1/expansion/official_source_head_catalog_v1.json"
    catalog_ref = shared.pin(catalog_path)
    catalog = shared.load(catalog_path)
    document = shared.REPO / catalog["source_document"]
    document_ref = shared.pin(document)
    validate_catalog(catalog, shared.read_small(document).decode("utf-8"))
    authority = [shared.pin(shared.PROJECT / "数据线工作流程：v1 定稿与数据扩充（Codex B）.md"),
                 shared.pin(goal_authority), document_ref]
    paths = [*Path(__file__).parent.glob("*.py"), shared.REPO / "workflows/expansion/full_queue_v1.py",
             shared.REPO / "workflows/expansion/common.py", shared.REPO / "workflows/expansion/__init__.py",
             shared.REPO / "workflows/data_v1_final/execution/queue_v1/__init__.py",
             shared.REPO / "workflows/data_v1_final/execution/queue_v1/shared.py",
             shared.REPO / "workflows/data_v1_final/execution/queue_v1/queue_contract.py",
             shared.REPO / "workflows/data_v1_final/execution/queue_v3/__init__.py",
             shared.REPO / "workflows/data_v1_final/execution/queue_v3/contract.py"]
    code = [shared.pin(path) for path in paths]
    stem = SCOPE + "_" + tag
    plan_path = shared.ROOT / "control/queue_specs" / (stem + "_plan.json")
    spec_path = shared.ROOT / "control/queue_specs" / (stem + "_base_spec.json")
    output = shared.ROOT / "artifacts/expansion/official_sources" / stem
    for path in (plan_path, spec_path, output):
        shared.need(not path.exists() and not path.is_symlink(), "NEW_METADATA_AND_OUTPUT_DESTINATIONS_REQUIRED")
    plan = {"schema": "SB5_OFFICIAL_SOURCE_HEAD_PLAN_V1", "status": "READY", "scope_key": SCOPE,
            "scope_parameters": parameters(catalog_ref), "pilot": False, "wall_seconds": WALL,
            "whole_output_cap_bytes": CAP, "output_root": str(output), "catalog_reference": catalog_ref,
            "official_document_reference": document_ref, "code_sources": code, "authority_references": authority,
            "network_configuration_changed": False, "data_acquisition_authorized": False,
            "all_source_coverage_accepted": False, "pool_release_authorized": False,
            "READY_plan_is_source_binding_not_Root_scope_approval": True}
    for ref in [*code, *authority, catalog_ref]:
        execution.verify_small(ref)
    shared.write_new(plan_path, plan)
    refs = {ref["path"]: ref for ref in [*code, *authority, catalog_ref, shared.pin(plan_path)]}
    spec = {"schema": "ROOT_REVIEWED_QUEUED_STAGE_SPEC_V1", "kind": "analysis", "pilot": False,
            "scope_key": SCOPE, "scope_parameters": parameters(catalog_ref), "wall_seconds": WALL,
            "estimated_peak_output_bytes": CAP, "stage_output_cap_bytes": CAP,
            "resources": {"cpus": 16, "memory_gib": 64, "exclusive_user": True},
            "source_references": list(refs.values()), "data_references": [], "deferred_authority_references": [],
            "execution_argv": [shared.PY, "-B", "-m", "workflows.expansion.official_source_probe_v1.run",
                               "--plan", str(plan_path), "--root-preflight", "__ROOT_STARTUP_PROOF__"],
            "proposed_scope_mode": "BOUNDED_METADATA_PREPARATION",
            "metadata_preparation_status": "NOT_REQUEST_READY_ROOT_V3_SCOPE_REVIEW_MISSING",
            "no_requests_probes_quota_or_science_executed": True}
    # Deliberately no scope.review or fabricated future pin. Root must create its
    # exact scope review and reviewed spec before queue_v3 can materialize a request.
    shared.write_new(spec_path, spec)
    print(__import__("json").dumps({"status": "SOURCE_BOUND_BASE_SPEC_NOT_REQUEST_READY", "plan": shared.pin(plan_path),
        "base_spec": shared.pin(spec_path), "submitted": False, "network_probe_run": False, "large_data_read_or_stat": False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--goal-authority", type=Path, required=True)
    parser.add_argument("--reviewer", choices=["root"], required=True)
    args = parser.parse_args()
    materialize(args.tag, args.goal_authority, args.reviewer)


if __name__ == "__main__":
    main()
