"""Verify existing identity parts and reuse the exact frozen global coverage function.

No write_unit, task_stream, cohort preparation, graph projection or RDKit call
is dispatched. Failed parent4521152 remains FAILED; this is an independent job.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import csv
import io
import os
from pathlib import Path
import threading
import time
import unittest

from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as central
from workflows.data_v1_final.execution.queue_v1 import shared
from .. import full_queue_v1 as files
from ..cpu_auto_memory_v1.runtime import ALGORITHM_REFERENCE_SOFTCAP_BYTES
from ..identity_full_after_profile_v1 import run as frozen
from ..identity_full_after_profile_v1.runtime import RuntimeBudget as OriginalBudget
from ..identity_full_after_profile_v1.policy import EXPECTED_DATASETS, validate_full_plan, validate_profile
from ..materialize_full_sources_v2 import parent_from_account
from ..identity_v3 import input_authority


SCOPE = "sb5_identity_full_closed_units_coverage_v1"
MODULE = "workflows.expansion.identity_full_closure_v1.close"
CAP, WALL = 16 * 1024 ** 3, 14400
PRIOR_JOB = "4521152"
ERROR = "CURRENT_MEMORY_SAMPLE_EXCEEDS2SECONDS"
OLD_ROOT = shared.ROOT / "artifacts/expansion/identity/sb5_identity_full_source_roles_after_profile_v1_v1"
TOTAL = 11398552
GLOBAL_COVERAGE = frozen.global_coverage
OUTPUT_SCHEMA = frozen.output_schema


def expected_units():
    return {**{f"formal_rg_{i:03d}": "formal" for i in range(86)}, "embargo_all4900": "embargo",
        **{f"small_identity_{i:05d}": "already_projected" for i in range(19)},
        **{f"graph_identity_{i:06d}": "graph" for i in range(298)}}


def parameters(manifest_ref, cost_decision_ref):
    return {"stage": "READ_ONLY_CLOSED_UNIT_COVERAGE", "failed_parent": PRIOR_JOB,
        "prior_failed_parent_not_upgraded": True, "recompute_closed_units": False,
        "original_unit_count": 404, "formal_row_groups": list(range(86)), "records": TOTAL,
        "existing_part_authority": {"manifest_reference": manifest_ref, "owned_root": str(OLD_ROOT / "parts"),
            "derive_only_exact_canonical_receipt_part_refs": True, "extra_directory_scan_allowed": False,
            "receipt_claimed_SHA_is_not_a_current_body_hash": True},
        "actual_source_and_part_hash_threads": 16, "whole_output_cap_bytes": CAP,
        "old_parts_are_existing_readonly_disk_use": True, "source_input_policy_unchanged": True,
        "geometry_role_projection_changed": False, "original_global_coverage_function_object_reused": True,
        "slow_memory_sample_is_lag_observation_only": True, "invalid_memory_values_stop": True,
        "current_owned_RSS_algorithm_reference_bytes": ALGORITHM_REFERENCE_SOFTCAP_BYTES,
        "runtime_node_MemAvailable_min_fraction": .15, "scheduler_memory_requested": False,
        "cost_decision_reference": cost_decision_ref, "cost_overrun_action": "DURABLE_REPORT_AND_CONTINUE",
        "conservative_comparison_seconds": 64 * 60, "overrun_comparison_seconds": 96 * 60,
        "cost_comparison_alone_stops_dispatch": False,
        "all_source_decontamination_or_pool_release": False, "new_UFF_QM_or_training": False}


def validate_cost_decision(reference):
    files.verify_small(reference)
    decision = shared.load(reference["path"])
    shared.need(reference["path"] == str(shared.REPO / "configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json") and
        decision.get("schema") == "USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1" and
        decision.get("status") == "USER_AUTHORIZED" and decision.get("on_overrun") == "REPORT_AND_CONTINUE" and
        decision.get("original_threshold_multiplier") == 1.5 and
        all(decision.get(key) is True for key in ("only_cost_stop_rule_changed", "scientific_quality_thresholds_unchanged",
            "retain_actual_accounting_including_failures_and_startup", "preserve_historical_requests_sources_and_results",
            "no_forced_termination")),
        "ACTUAL_ROOT_COST_REPORT_CONTINUE_DECISION_REQUIRED")


def validate_unit_rows(units):
    wanted = expected_units()
    shared.need(len(units) == len(wanted) and len({u["unit_id"] for u in units}) == len(wanted) and
                {u["unit_id"] for u in units} == set(wanted), "EXACT_404_ORIGINAL_CLOSED_UNITS_REQUIRED")
    counts, datasets, roles, workers, classes = Counter(), Counter(), Counter(), Counter(), Counter()
    for unit in units:
        name, reference = unit["unit_id"], unit["file"]
        shared.need(unit["kind"] == wanted[name] and reference["path"] == str(OLD_ROOT / "parts" / (name + ".parquet")) and
            type(reference["bytes"]) is int and reference["bytes"] > 0 and len(reference["sha256"]) == 64 and
            set(reference["sha256"]) <= set("0123456789abcdef"), "CANONICAL_EXISTING_UNIT_REFERENCE_REQUIRED")
        for mapping in (unit["counts"], unit["datasets"], unit["roles"], unit["embargo_classes"]):
            shared.need(all(type(n) is int and n >= 0 for n in mapping.values()), "INTEGER_UNIT_COUNT_REQUIRED")
        shared.need(unit["counts"]["records"] > 0 and sum(unit["roles"].values()) ==
            sum(unit["datasets"].values()) == unit["counts"]["records"], "UNIT_ROW_ROLE_DATASET_CONSERVATION")
        counts.update(unit["counts"]); datasets.update(unit["datasets"]); roles.update(unit["roles"])
        classes.update(unit["embargo_classes"]); workers[str(unit["worker_pid"])] += unit["counts"]["records"]
    shared.need(counts["records"] == TOTAL and datasets == Counter(EXPECTED_DATASETS) and len(workers) == 16 and
        min(workers.values()) > 0 and classes == {"known_fullkey_embargo": 4100, "unknown_non_h_composition_embargo": 800},
        "WHOLE_ORIGINAL_RECORD_COHORT_AND_WORKER_COUNTS_REQUIRED")
    return {"counts": dict(counts), "datasets": dict(datasets), "roles": dict(roles),
        "original_worker_records": dict(workers), "embargo_classes": dict(classes)}


def lag_and_memory_decision(sample, seconds):
    for key in ("own_current_tree_rss_bytes", "available_bytes", "total_bytes"):
        shared.need(type(sample.get(key)) is int and sample[key] >= 0, "INVALID_CURRENT_MEMORY_VALUE")
    shared.need(sample["total_bytes"] > 0 and sample["available_bytes"] <= sample["total_bytes"] and
        type(seconds) in (int, float) and 0 <= seconds < float("inf"), "INVALID_CURRENT_MEMORY_SAMPLE")
    reason = None
    if sample["own_current_tree_rss_bytes"] >= ALGORITHM_REFERENCE_SOFTCAP_BYTES:
        reason = "OWN_CURRENT_RSS_AT_ALGORITHM_REFERENCE48GIB_NOT_ALLOCATION"
    if sample["available_bytes"] < sample["total_bytes"] * .15:
        reason = reason or "CURRENT_NODE_MEMAVAILABLE_BELOW_RUNTIME15PCT_STOP_NOT_ADMISSION"
    return {"stop_reason": reason, "sample_elapsed_seconds": seconds, "sample_lag_exceeds2seconds": seconds > 2}


class ClosureMetadataBoundaries(unittest.TestCase):
    def test_exact_unit_namespace_rejects_a_missing_or_duplicate_original_unit(self):
        names = expected_units()
        self.assertEqual(len(names), 404)
        self.assertEqual(sum(kind == "formal" for kind in names.values()), 86)
        for broken in ([], [{"unit_id": "formal_rg_000"}] * 404):
            with self.assertRaisesRegex(ValueError, "EXACT_404"):
                validate_unit_rows(broken)

    def test_lag_is_observed_but_actual_bad_memory_or_invalid_values_are_not_ignored(self):
        sample = {"own_current_tree_rss_bytes": 1024, "available_bytes": 900, "total_bytes": 1000}
        observed = lag_and_memory_decision(sample, 3.5)
        self.assertTrue(observed["sample_lag_exceeds2seconds"])
        self.assertIsNone(observed["stop_reason"])
        self.assertIsNotNone(lag_and_memory_decision(dict(sample, available_bytes=100), .1)["stop_reason"])
        self.assertIsNotNone(lag_and_memory_decision(dict(sample,
            own_current_tree_rss_bytes=ALGORITHM_REFERENCE_SOFTCAP_BYTES), .1)["stop_reason"])
        with self.assertRaisesRegex(ValueError, "INVALID_CURRENT_MEMORY_VALUE"):
            lag_and_memory_decision(dict(sample, available_bytes=-1), .1)


class ClosureBudget(OriginalBudget):
    """Keep quality/resource stops; report the64/96min comparison and continue."""
    def __init__(self, *args):
        super().__init__(*args)
        self.maximum_sample_seconds = 0.
        self.slow_sample_count = 0

    def _cost_check(self):
        elapsed = time.monotonic() - self.started
        if elapsed < self.plan["planning_budget"]["soft_limit_seconds"] or self.soft_limit_reached:
            return
        with self.cost_lock:
            if self.soft_limit_reached:
                return
            try:
                shared.write_new(self.output / "cost_overrun_report_continue.json", {
                    "schema": "FULL_IDENTITY_COST_COMPARISON_REPORT_CONTINUE_V1", "job_id": self.proof["job_id"],
                    "cost_decision_reference": self.plan["cost_decision_reference"],
                    "observed_producer_monotonic_seconds": elapsed, "conservative_comparison_seconds": 64 * 60,
                    "overrun_comparison_seconds": 96 * 60, "comparison_multiplier": 1.5,
                    "comparison_clock_basis": "PRODUCER_MONOTONIC_AFTER_FRESH_STARTUP",
                    "prior_failed_parent": PRIOR_JOB, "prior_failed_parent_allocated_core_seconds": 323 * 16,
                    "actual_new_parent_allocation_cost_requires_later_accounting": True,
                    "action": "REPORT_AND_CONTINUE", "cost_comparison_stops_dispatch": False,
                    "quality_thresholds_unchanged": True, "resource_and_invalid_metric_stops_unchanged": True,
                    "forced_signals_sent": False, "hard_wall_ceiling_seconds": WALL})
                self.soft_limit_reached = True
            except Exception:
                self.soft_notice_export_failed = True
                # A failed evidence write is an I/O failure, never a cost-limit stop.
                self._stop("COST_COMPARISON_DURABLE_REPORT_IO_FAILED")

    def _loop(self):
        try:
            while not self.closed.is_set():
                started = time.monotonic()
                sample = files.memory_sample(os.getpid())
                decision = lag_and_memory_decision(sample, time.monotonic() - started)
                self.samples += 1
                self.maximum_sample_seconds = max(self.maximum_sample_seconds, decision["sample_elapsed_seconds"])
                self.slow_sample_count += int(decision["sample_lag_exceeds2seconds"])
                self.peak_current_rss_bytes = max(self.peak_current_rss_bytes, sample["own_current_tree_rss_bytes"])
                self.minimum_available_bytes = sample["available_bytes"] if self.minimum_available_bytes is None else min(
                    self.minimum_available_bytes, sample["available_bytes"])
                if decision["stop_reason"]:
                    self._stop(decision["stop_reason"])
                if time.monotonic() - self.started >= self.proof["request"]["wall_seconds"] - 120:
                    self._stop("STOP_NEW_DISPATCH_WITH120SECOND_DRAIN_MARGIN")
                self.closed.wait(1)
        except BaseException as exc:
            self._stop("CURRENT_MEMORY_MONITOR_FAILED:" + type(exc).__name__)

    def receipt(self):
        return {**super().receipt(), "maximum_sample_elapsed_seconds": self.maximum_sample_seconds,
            "sample_lag_over2seconds_count": self.slow_sample_count, "slow_sample_alone_asserts_memory_shortage": False,
            "cost_decision_reference": self.plan["cost_decision_reference"],
            "cost_overrun_action": "DURABLE_REPORT_AND_CONTINUE", "cost_comparison_stops_dispatch": False,
            "overrun_report_published": self.soft_limit_reached}


def failed_parent(account_path):
    account = shared.load(account_path)
    shared.need(account["schema"] == "DATA_V1_OWNED_ACCOUNTING_POINT_IN_TIME_V2" and account["query_returncode"] == 0,
                "ACTUAL_FAILED_PARENT_ACCOUNTING_REQUIRED")
    raw_ref = account["raw_sacct_reference"]
    files.verify_small(raw_ref)
    parents = [row for row in account["actual_parents"] if row["JobIDRaw"] == PRIOR_JOB]
    raw = [row for row in csv.DictReader(io.StringIO(shared.read_small(raw_ref["path"]).decode()), delimiter="|")
           if row["JobIDRaw"] == PRIOR_JOB]
    expected = {"State": "FAILED", "ExitCode": "1:0", "ElapsedRaw": "323", "AllocCPUS": "16",
                "NodeList": "compute-0-15", "Partition": "cpu"}
    shared.need(len(parents) == len(raw) == 1 and all(parents[0][key] == raw[0][key] == value
                for key, value in expected.items()), "EXACT_TERMINAL_FAILED4521152_REQUIRED_NOT_COMPLETED")
    files.verify_small(parents[0]["receipt_reference"])
    submission = shared.load(parents[0]["receipt_reference"]["path"])
    shared.need(submission["job_id"] == PRIOR_JOB and submission["sbatch_returncode"] == 0,
                "ORIGINAL_FAILED_PARENT_SUBMISSION_REQUIRED")
    return parents[0], raw_ref


def function_proof(reference):
    files.verify_small(reference)
    shared.need(Path(frozen.__file__).absolute() == Path(reference["path"]) and
        GLOBAL_COVERAGE is frozen.global_coverage and OUTPUT_SCHEMA is frozen.output_schema and
        GLOBAL_COVERAGE.__code__.co_filename == reference["path"], "EXACT_FROZEN_FUNCTION_OBJECT_REQUIRED")
    tree = ast.parse(shared.read_small(reference["path"]))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "global_coverage")
    return {"original_source_reference": reference, "original_global_function_object_reused": True,
        "original_global_AST_sha256": __import__("hashlib").sha256(ast.dump(node, include_attributes=False).encode()).hexdigest(),
        "SQL_math_scope_or_projection_edits": False}


def existing_units(plan):
    manifest = shared.load(plan["unit_manifest"]["path"])
    shared.need(manifest["schema"] == "FAILED_IDENTITY_CLOSED_UNIT_LOCATORS_V1" and
        manifest["failed_parent"] == PRIOR_JOB and manifest["current_part_body_hashes_claimed"] is False and
        manifest["part_root"] == str(OLD_ROOT / "parts"), "EXACT_EXISTING_UNIT_MANIFEST_REQUIRED")
    units = []
    for row in manifest["units"]:
        files.verify_small(row["receipt_reference"])
        unit = shared.load(row["receipt_reference"]["path"])
        shared.need(row["receipt_reference"]["path"] == str(OLD_ROOT / (unit["unit_id"] + ".receipt.json")) and
                    row["part_reference_claimed_by_original_unit"] == unit["file"], "EXACT_ORIGINAL_UNIT_RECEIPT_BINDING")
        units.append(unit)
    summary = validate_unit_rows(units)
    failure = shared.load(plan["prior_failure"]["path"])
    shared.need(failure["status"] == "IDENTITY_EXPORT_FAILED_NO_RELEASE" and failure["error"] == ERROR and
        failure["closed_units"] == 404 and failure["actual_worker_records_so_far"] == summary["original_worker_records"] and
        failure["runtime_budget"]["first_stop_reason"] == ERROR and
        failure["runtime_budget"]["cost_soft_limit_reached"] is False, "EXACT_ORIGINAL_COMPLETE_UNITS_FAILURE_REQUIRED")
    return units, summary


def verify_parts(units, stop, budget):
    barrier = threading.Barrier(16)
    def one(unit):
        if stop.is_set():
            raise files.CooperativeStop("STOP_BEFORE_NEXT_EXISTING_PART")
        path = Path(unit["file"]["path"])
        shared.need(not any(p.is_symlink() for p in (path, *path.parents)), "LITERAL_OLD_PART_REQUIRED")
        before = files.frame(path)
        files.file_pin(path, expected=unit["file"], expected_frame=before, stop=stop)
        import pyarrow.parquet as pq
        parquet = pq.ParquetFile(path)
        shared.need(parquet.schema_arrow.equals(OUTPUT_SCHEMA()) and parquet.metadata.num_rows == unit["counts"]["records"] and
                    files.frame(path) == before, "PART_CURRENT_SHA_FOOTER_SCHEMA_ROWCOUNT_OR_FRAME_DIFFERS")
        return {"unit_id": unit["unit_id"], "reference": unit["file"], "frame": before,
                "rows": parquet.metadata.num_rows, "hash_footer_thread_id": threading.get_native_id()}
    with ThreadPoolExecutor(max_workers=16, initializer=lambda: barrier.wait(timeout=180)) as pool:
        results = list(pool.map(one, units))
    shared.need(len(results) == 404 and len({row["hash_footer_thread_id"] for row in results}) == 16,
                "ACTUAL16_THREAD_404_CURRENT_PART_HASHES_REQUIRED")
    budget.check()
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-preflight", type=Path, required=True)
    args = parser.parse_args()
    plan = shared.load(args.plan)
    shared.need(plan["schema"] == "FULL_IDENTITY_READONLY_CLOSURE_PLAN_V1" and plan["status"] == "READY" and
        plan["scope_key"] == SCOPE and plan["scope_parameters"] == parameters(plan["unit_manifest"], plan["cost_decision_reference"]),
        "EXACT_NEW_CLOSURE_PLAN")
    argv = [shared.PY, "-B", "-m", MODULE, "--plan", str(args.plan), "--root-preflight", str(args.root_preflight)]
    proof = central.require_startup(args.root_preflight, expected_scope_key=SCOPE,
        expected_scope_parameters=plan["scope_parameters"], expected_execution_argv=argv,
        expected_source=Path(__file__), expected_kind="analysis", required_references=(shared.pin(args.plan),))
    request = proof["request"]
    shared.need(request["pilot"] is False and request["scope"]["mode"] == "FULL_SOURCE_AFTER_PROFILE" and
        request["scope"]["parent_profile"] == plan["accepted_profile"] and request["wall_seconds"] == WALL and
        request["estimated_peak_output_bytes"] == CAP and proof["account_free_bytes"] - CAP >= 200000000000,
        "NEW_FULL_READONLY_SCOPE_DEFAULT_MEMORY_4H16GIB200GB_REQUIRED")
    declared = {r["path"]: r for r in request["source_references"]}
    for reference in [*plan["bound_small_references"], shared.pin(args.plan)]:
        files.verify_small(reference, declared)
    validate_cost_decision(plan["cost_decision_reference"])
    original = shared.load(plan["prior_plan"]["path"])
    validate_full_plan(original)
    files.validate_scientific_anchors(original)
    shared.need(original["output_root"] == str(OLD_ROOT) and original["apply_common_filter"] is False and
        original["whole_output_cap_bytes"] == CAP and plan["planning_budget"] == original["planning_budget"] and
        original["accepted_profile"]["receipt"] == plan["accepted_profile"], "ORIGINAL_FULL_SCOPE_NOT_REPROJECTED")
    profile = shared.load(plan["accepted_profile"]["path"])
    validate_profile(profile)
    profile_parent, profile_raw = parent_from_account(original["accepted_profile"]["accounting"]["path"], profile["job_id"])
    shared.need(profile_parent == original["accepted_profile"]["actual_parent"] and
        profile_raw == original["accepted_profile"]["raw_sacct"], "ACTUAL1092_PROFILE_PARENT_REVALIDATION")
    previous_request = shared.load(plan["prior_request"]["path"])
    previous_proof = shared.load(plan["prior_startup"]["path"])
    shared.need(previous_proof["job_id"] == PRIOR_JOB and previous_proof["request"] == previous_request and
        previous_proof["request_reference"] == plan["prior_request"] and
        previous_request["data_references"] == request["data_references"] and
        previous_request["execution_argv"][-4:-2] == ["--plan", plan["prior_plan"]["path"]],
        "EXACT_PRIOR_FAILED_REQUEST_PLAN_INPUT_LOCATORS_REQUIRED")
    parent, raw_accounting = failed_parent(plan["prior_accounting"]["path"])
    shared.need(parent == plan["prior_actual_parent"] and raw_accounting == plan["prior_raw_accounting"],
                "ORIGINAL_FAILED_PARENT_COST_BINDING_CHANGED")
    out = Path(plan["output_root"])
    shared.need(out.parent == shared.ROOT / "artifacts/expansion/identity" and out != OLD_ROOT and not out.exists() and
        not any(p.is_symlink() for p in (out, *out.parents)), "NEW_CLOSURE_OUTPUT_ONLY")
    out.mkdir()
    stop = threading.Event()
    budget = ClosureBudget(out, plan, proof, stop)
    started = time.monotonic()
    try:
        with budget:
            suite = unittest.defaultTestLoader.loadTestsFromTestCase(ClosureMetadataBoundaries)
            shared.need(suite.countTestCases() == 2, "EXACT_TWO_METADATA_FIXTURES_REQUIRED")
            result = unittest.TextTestRunner(verbosity=2).run(suite)
            tests = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                     "skips": len(result.skipped), "before_any_body_IO": True}
            shared.write_new(out / "metadata_fixtures.json", tests)
            shared.need(result.wasSuccessful() and result.testsRun == 2 and not result.skipped,
                        "NEW_METADATA_FIXTURES_MUST_PASS_BEFORE_BODY_IO")
            unchanged = function_proof(plan["original_global_source"])
            units, summary = existing_units(plan)
            # Only original73 body refs enter this unchanged547 authority function.
            # Existing parts are separately derived from the exact Root-bound404-receipt manifest.
            tickets, authority = input_authority.authorize(original, proof)
            hash_began = time.monotonic()
            body_hashes = input_authority.verify_bodies(tickets, stop)
            part_hashes = verify_parts(units, stop, budget)
            hash_seconds = time.monotonic() - hash_began
            shared.write_new(out / "current_part_verification.json", {"schema": "CURRENT_CLOSED_IDENTITY_PARTS_VERIFIED_V1",
                "job_id": proof["job_id"], "parts": part_hashes, "records": TOTAL})
            budget.check()
            sql_began = time.monotonic()
            coverage = GLOBAL_COVERAGE(out, original, units, budget)
            sql_seconds = time.monotonic() - sql_began
            shared.need(coverage["records"] == coverage["globally_unique_source_ids"] == summary["counts"]["records"] == TOTAL,
                        "FULL_ORIGINAL_RECORD_UNIQUE_SQL_CONSERVATION")
            input_authority.verify_final(tickets)
            for row in part_hashes:
                shared.need(files.frame(row["reference"]["path"]) == row["frame"], "EXISTING_PART_CHANGED_DURING_GLOBAL_SQL")
            budget.check(force=True)
            receipt = {"schema": "FULL_IDENTITY_READONLY_CLOSURE_RECEIPT_V1",
                "status": "LOCAL_ORIGINAL_IDENTITIES_CLOSED_FROM_FAILED_PARENT_PARTS_EXTERNAL_PENDING",
                "job_id": proof["job_id"], "node": request["node"], "uid": os.getuid(), "mode": "full",
                "plan": shared.pin(args.plan), "startup_proof": shared.pin(args.root_preflight),
                "cost_decision_reference": plan["cost_decision_reference"], "cost_overrun_action": "REPORT_AND_CONTINUE",
                "prior_failed_parent": parent, "prior_failed_parent_allocated_core_seconds": 323 * 16,
                "original_failed_parent_upgraded_to_COMPLETED": False, "old_outputs_modified_or_deleted": False,
                "source_authority": authority, "original_source_body_hashes": body_hashes,
                "metadata_fixtures": tests, "unit_summary": summary, "coverage": coverage, "source_scope_proof": unchanged,
                "current_part_verification": shared.pin(out / "current_part_verification.json"),
                "closed_units": [{"unit_id": u["unit_id"], "file": u["file"]} for u in units],
                "role_semantics": original["role_semantics"], "effective_training_roles_applied": False,
                "apply_common_filter": False, "all_source_all_split_decontamination_accepted": False,
                "external_pending": frozen.coverage.external_pending_manifest(shared.load(original["source_catalog"]["path"])),
                "pool_UFF_QM_training_release_authorized": False, "closed_units_recomputed": 0,
                "new_RDKIT_UFF_QM_calls": 0, "phase_seconds": {"source_and_part_hash_footer": hash_seconds,
                    "original_global_SQL": sql_seconds}, "elapsed_seconds": time.monotonic() - started,
                "runtime_budget": budget.receipt(), "new_parent_actual_allocation_cost_pending_accounting": True}
        # Only publish success after the monitor and cost thread naturally close.
        shared.write_new(out / "receipt.json", receipt)
    except BaseException as exc:
        stop.set()
        shared.write_new(out / "failure.json", {"status": "READONLY_IDENTITY_CLOSURE_FAILED_NO_RELEASE",
            "type": type(exc).__name__, "error": str(exc), "prior_failed_parent": PRIOR_JOB,
            "old_outputs_preserved": True, "forced_signals_sent": False, "runtime_budget": budget.receipt()})
        raise


if __name__ == "__main__":
    main()
