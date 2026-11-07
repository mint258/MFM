"""CPU-default-memory official HEAD observations, never data acquisition."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import socket
import threading
import time

from workflows.data_v1_final.execution.queue_v1 import shared
from . import runtime as execution
from ..official_source_probe_v1.catalog import CAP, LIMITS, SCOPE, WALL, need, parameters, validate_catalog
from ..official_source_probe_v1.transport import probe_many


def startup(plan_path, proof_path):
    plan, proof, validation = execution.startup(plan_path, proof_path, __file__, scope=SCOPE)
    validate_plan(plan, proof["request"])
    need(proof["request"].get("data_references", []) == [], "HEADER_ONLY_NO_BODY_REFERENCES")
    return plan, proof, validation


def validate_plan(plan, request):
    need(plan["schema"] == "SB5_OFFICIAL_SOURCE_HEAD_PLAN_V1" and plan["status"] == "READY"
         and plan["scope_key"] == request.get("scope_key") == SCOPE
         and plan["scope_parameters"] == request.get("scope_parameters") == parameters(plan["catalog_reference"])
         and plan["pilot"] is False and plan["whole_output_cap_bytes"] == CAP and plan["wall_seconds"] == WALL,
         "EXACT_NEW_IMMUTABLE_NONPILOT_HEAD_PLAN_REQUIRED")
    need(plan["network_configuration_changed"] is False and plan["data_acquisition_authorized"] is False
         and plan["all_source_coverage_accepted"] is False and plan["pool_release_authorized"] is False,
         "HEAD_METADATA_CANNOT_RELEASE_SCIENTIFIC_OR_DOWNLOAD_GATES")


def write_metadata(path, value, limit):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    need(len(raw) <= limit, "NORMALIZED_METADATA_LIMIT_BEFORE_WRITE")
    ref = shared.write_new(path, value)
    # Include current directory/file allocation as well as logical bytes. No files
    # are deleted if the filesystem cannot stay within this conservative budget.
    root = Path(path).parent
    allocated = root.stat().st_blocks * 512 + sum(p.stat().st_blocks * 512 for p in root.iterdir())
    need(max(allocated, execution.owned_bytes(root)) < CAP - 8 * 1024 ** 2, "OWNED_METADATA_ALLOCATION_STOP")
    return ref


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-preflight", type=Path, required=True)
    args = parser.parse_args()
    plan, proof, startup_result = startup(args.plan, args.root_preflight)
    output = execution.fresh_output(plan["output_root"])
    stop = threading.Event()
    started = time.monotonic()
    references_by_id, overrun_references = {}, []
    reference_lock = threading.Lock()
    candidate_ids = set()
    try:
        with execution.RuntimeBudget(output, plan, proof, stop) as budget:
            from ..official_source_probe_v1.test_probe import run_boundaries
            tests = run_boundaries()
            budget.check()
            catalog = shared.load(plan["catalog_reference"]["path"])
            document = shared.read_small(plan["official_document_reference"]["path"]).decode("utf-8")
            rows = validate_catalog(catalog, document)
            candidate_ids = {row["source_id"] for row in rows}
            logical = {key: catalog[key] for key in ("tdc_admet", "moleculenet", "marcel", "coconut")}
            logical.update(schema="SB5_OFFICIAL_LOGICAL_SOURCE_NOT_INSPECTED_V1", coverage_status="PENDING",
                HEAD_zip_does_not_establish_members=True, source_record_counts_or_sha_proven=False)
            logical_ref = write_metadata(output / "logical_coverage_pending.json", logical, LIMITS["max_logical_manifest_bytes"])

            def completed(observation):
                with reference_lock:
                    budget.check()
                    source_id = observation["source_id"]
                    need(source_id in candidate_ids and source_id not in references_by_id, "ONE_DURABLE_RESULT_PER_CANDIDATE")
                    ref = write_metadata(output / (source_id + ".json"), observation, LIMITS["max_per_url_json_bytes"])
                    references_by_id[source_id] = {"source_id": source_id, "reference": ref}

            def overrun(details):
                # The worker has already stopped dispatch. Preserve bounded evidence
                # immediately without trying to bypass that STOP for more network work.
                with reference_lock:
                    need(details["source_id"] in candidate_ids, "EXACT_OVERRUN_CANDIDATE_REQUIRED")
                    ref = write_metadata(output / ("timeout_overrun_" + details["source_id"] + ".json"),
                        {"schema": "SB5_OFFICIAL_HEAD_TIMEOUT_OVERRUN_V1", "job_id": proof["job_id"], **details}, 16 * 1024)
                    overrun_references.append(ref)

            workers, observations = probe_many(rows, stop, budget.check, on_result=completed, on_overrun=overrun)
            need(set(references_by_id) == candidate_ids, "ALL_COMPLETED_HEAD_RECORDS_ALREADY_DURABLE")
            references = [references_by_id[key] for key in sorted(references_by_id)]
            budget.check(force=True)
        receipt = {"schema": "SB5_OFFICIAL_SOURCE_HEAD_RECEIPT_V1",
            "status": "HEAD_OBSERVATIONS_COMPLETE_ALL_SOURCE_COVERAGE_PENDING", "job_id": proof["job_id"],
            "node": proof["request"]["node"], "uid": os.getuid(), "plan": shared.pin(args.plan),
            "startup_proof": shared.pin(args.root_preflight), "startup": startup_result,
            "catalog_reference": plan["catalog_reference"], "official_document_reference": plan["official_document_reference"],
            "head_candidate_records": len(observations), "actual_workers": workers,
            "all_30_candidates_have_conserved_dispositions": len(observations) == 30,
            "outcome_counts": dict(Counter(r["outcome"] for r in observations)),
            "final_HTTP_status_counts": dict(Counter(str(r["http_status"]) for r in observations)),
            "observations": references, "logical_source_manifest": logical_ref, "boundary_tests": tests,
            "runtime_budget": budget.receipt(), "wall_seconds_observed": time.monotonic() - started,
            "wall_seconds_ceiling_not_forecast": WALL, "whole_output_ceiling_not_forecast": CAP,
            "coverage_status": "PENDING", "physical_SHA256_or_record_count_proven": False,
            "all_TDC44_logical_members_NOT_INSPECTED": True, "MoleculeNet17_union_preserved": True,
            "COCONUT_candidate_month_or_displayed_size_not_a_release_pin": True,
            "normal_network_environment_inherited": True, "network_configuration_changed": False,
            "unredacted_response_headers_or_stderr_persisted": False, "payload_GETs": 0,
            "partial_observations_durable_per_URL": True, "timeout_overrun_references": overrun_references,
            "curl_timeout_is_not_absolute_child_wall_guarantee": True, "signals_sent_to_children": False,
            "download_completed": False, "pool_modified": False, "pool_released": False,
            "global_decontamination_accepted": False, "formal_UFF_QM_or_training_released": False}
        write_metadata(output / "receipt.json", receipt, LIMITS["max_final_receipt_bytes"])
        need(execution.owned_bytes(output) <= CAP, "WHOLE_METADATA_OUTPUT_CAP_EXCEEDED")
        print("OFFICIAL_HEAD_OBSERVATIONS_COMPLETE_COVERAGE_PENDING", proof["job_id"], len(observations))
    except BaseException as exc:
        shared.write_new(output / "failure.json", {"schema": "SB5_OFFICIAL_SOURCE_HEAD_FAILURE_V1", "job_id": proof["job_id"],
            "exception_type": type(exc).__name__, "exception_text_sha256": hashlib.sha256(str(exc).encode()).hexdigest(),
            "durable_completed_observations": [references_by_id[key] for key in sorted(references_by_id)],
            "uncompleted_candidate_ids": sorted(candidate_ids - set(references_by_id)),
            "timeout_overrun_references": overrun_references, "wall_seconds_observed": time.monotonic() - started,
            "partial_files_preserved_no_overwrite_or_delete": True, "signals_sent_to_children": False,
            "coverage_status": "PENDING", "download_completed": False, "pool_released": False})
        raise


if __name__ == "__main__":
    main()
