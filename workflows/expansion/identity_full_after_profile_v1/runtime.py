"""Independent full scope, actual profile authority and96min cooperative budget."""
from __future__ import annotations

import os
from pathlib import Path
import threading
import time

from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as central
from workflows.data_v1_final.execution.queue_v1 import shared
from .. import full_queue_v1 as files
from ..cpu_auto_memory_v1.runtime import RuntimeBudget as ObservedMemoryBudget
from ..materialize_full_sources_v2 import parent_from_account
from .policy import (CAP, CONSERVATIVE_SECONDS, MEMORY_POLICY, SCOPE, SOFT_SECONDS, WALL,
                     forecast, validate_full_plan, validate_profile)
from .provenance import source_proof


CooperativeStop = files.CooperativeStop
file_pin, fresh_output, owned_bytes = files.file_pin, files.fresh_output, files.owned_bytes


def startup(plan_path, proof_path, entry_path, *, scope):
    plan = shared.load(plan_path)
    validate_full_plan(plan)
    shared.need(scope == SCOPE and Path(entry_path).absolute() == Path(__file__).parent / "run.py",
                "INDEPENDENT_FULL_ENTRY_REQUIRED_PROFILE_ADAPTER_CANNOT_EXPAND")
    argv = [shared.PY, "-B", "-m", "workflows.expansion.identity_full_after_profile_v1.run",
            "--plan", str(Path(plan_path)), "--root-preflight", str(Path(proof_path))]
    plan_ref = shared.pin(Path(plan_path))
    proof = central.require_startup(proof_path, expected_scope_key=SCOPE,
        expected_scope_parameters=plan["scope_parameters"], expected_execution_argv=argv,
        expected_source=Path(entry_path), expected_kind="analysis", required_references=(plan_ref,))
    request = proof["request"]
    shared.need(proof["schema"] == "FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1" and
        request["schema"] == "CPU_AUTO_MEMORY_QUEUED_REQUEST_V1" and
        request["memory_policy"] == proof["memory_policy"] == plan["memory_policy"] == MEMORY_POLICY and
        request["pilot"] is False and request["cpus"] == 16 and request["wall_seconds"] == WALL and
        request["scope"]["mode"] == "FULL_SOURCE_AFTER_PROFILE" and
        request["scope"]["parent_profile"] == plan["accepted_profile"]["receipt"] and
        request["estimated_peak_output_bytes"] == CAP and "memory_gib" not in request and
        proof["account_free_bytes"] - CAP >= 200000000000, "REAL_CPU_DEFAULT_MEMORY_FULL_SCOPE_AND_QUOTA_REQUIRED")
    declared = {ref["path"]: ref for ref in request["source_references"]}
    for ref in [plan_ref, *plan["code_sources"], *plan["authority_references"]]:
        files.verify_small(ref, declared)
    accepted = plan["accepted_profile"]
    for key in ("receipt", "plan", "startup_proof", "accounting", "raw_sacct", "source_reference"):
        files.verify_small(accepted[key], declared)
    profile = shared.load(accepted["receipt"]["path"])
    validate_profile(profile)
    shared.need(profile["plan"] == accepted["plan"] and profile["startup_proof"] == accepted["startup_proof"],
                "EXACT_ACCEPTED_PROFILE_INPUT_REFERENCES")
    parent, raw_sacct = parent_from_account(accepted["accounting"]["path"], profile["job_id"])
    actual_core_seconds = int(parent["ElapsedRaw"]) * int(parent["AllocCPUS"])
    shared.need(parent == accepted["actual_parent"] and raw_sacct == accepted["raw_sacct"] and
        parent["NodeList"] == profile["node"] and actual_core_seconds == accepted["allocated_core_seconds"] and
        forecast(profile, profile_receipt_bytes=accepted["receipt"]["bytes"]) == plan["planning_budget"] and
        plan["planning_budget"]["planning_storage_upper_bytes"] <= CAP, "ACTUAL_PROFILE_PARENT_COST_OR_PLANNING_DIFFERS")
    for ref in (parent["receipt_reference"], plan["full_source_proof"], plan["resource_policy_authority"]):
        files.verify_small(ref, declared)
    saved = shared.load(plan["full_source_proof"]["path"])
    shared.need(saved == source_proof(accepted["source_reference"]), "FULL_BRANCH_SOURCE_AND_SCOPE_PROOF_CHANGED")
    authority = shared.load(plan["resource_policy_authority"]["path"])
    shared.need(authority["schema"] == "USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1" and
                authority["status"] == "USER_AUTHORIZED", "CURRENT_USER_CPU_MEMORY_AUTHORITY_REQUIRED")
    files.validate_scientific_anchors(plan)
    return plan, proof, {"status": "ACTUAL_PROFILE_TO_NEW_FULL_SCOPE_VERIFIED", "accepted_profile": accepted["receipt"],
        "actual_profile_allocated_core_seconds": actual_core_seconds, "memory_policy": MEMORY_POLICY,
        "memory_admission_evaluated": False, "scheduler_memory_requested": False,
        "new_full_scope_not_resource_only_profile_migration": True, "source_proof": plan["full_source_proof"],
        "soft_clock_basis": "PRODUCER_MONOTONIC_AFTER_FRESH_STARTUP", "freshness_checked_once_before_scientific_body": True,
        "full_job_parent_allocation_cost_pending_actual_accounting": True}


class RuntimeBudget(ObservedMemoryBudget):
    """Reuse observed-memory STOP; add a separate cooperative cost timer."""
    def __init__(self, output, plan, proof, stop):
        super().__init__(output, plan, proof, stop)
        self.soft_limit_reached = False
        self.soft_notice_export_failed = False
        self.cost_lock = threading.Lock()
        self.cost_thread = threading.Thread(target=self._cost_loop, name="identity-full-cost-soft-limit", daemon=False)

    def _cost_check(self):
        elapsed = time.monotonic() - self.started
        if elapsed < SOFT_SECONDS or self.soft_limit_reached:
            return
        with self.cost_lock:
            if self.soft_limit_reached:
                return
            self.soft_limit_reached = True
            self._stop("COST_SOFT_LIMIT96MIN_1P5_OF_CONSERVATIVE64MIN_STOP_NEW_WORK_DRAIN")
        try:
            shared.write_new(self.output / "cost_soft_deadline_notice.json", {
                "schema": "SB5_FULL_IDENTITY_COST_SOFT_STOP_V1", "job_id": self.proof["job_id"],
                "observed_producer_monotonic_seconds": elapsed, "conservative_estimate_seconds": CONSERVATIVE_SECONDS,
                "soft_limit_seconds": SOFT_SECONDS, "estimate_multiplier": 1.5,
                "clock_basis": "PRODUCER_MONOTONIC_AFTER_FRESH_STARTUP", "parent_allocation_cost_separate": True,
                "no_new_dispatch": True, "running_work_naturally_drains": True, "forced_signals_sent": False,
                "hard_wall_ceiling_seconds": WALL, "export_or_decontamination_acceptance_granted": False})
        except Exception:
            self.soft_notice_export_failed = True

    def _cost_loop(self):
        while not self.closed.is_set():
            self._cost_check()
            self.closed.wait(1)

    def __enter__(self):
        try:
            super().__enter__()
            self.cost_thread.start()
            self._cost_check()
            return self
        except BaseException:
            self.closed.set()
            self.thread.join(timeout=5)
            raise

    def check(self, *, force=False):
        self._cost_check()
        return super().check(force=force)

    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.closed.set()
            self.cost_thread.join(timeout=5)
            shared.need(not self.cost_thread.is_alive(), "COST_SOFT_MONITOR_DID_NOT_NATURALLY_CLOSE")

    def receipt(self):
        return {**super().receipt(), "planning_budget": self.plan["planning_budget"],
            "producer_monotonic_seconds_observed": time.monotonic() - self.started,
            "cost_soft_limit_reached": self.soft_limit_reached, "soft_notice_export_failed": self.soft_notice_export_failed,
            "soft_deadline_sends_no_signal_or_library_interrupt": True,
            "parent_startup_wait_validation_and_drain_costs_not_omitted_from_actual_accounting": True,
            "96min_is_not_absolute_process_or_Slurm_wall_guarantee": True}
