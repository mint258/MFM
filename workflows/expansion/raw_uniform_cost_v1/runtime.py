"""Exact central-v2 startup and measured-memory cooperative budget, no cost stop."""
import os
from pathlib import Path
import time

from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as central
from workflows.data_v1_final.execution.queue_v1 import shared
from .. import full_queue_v1 as files
from ..cpu_auto_memory_v1.runtime import RuntimeBudget as ObservedMemoryBudget, ALGORITHM_REFERENCE_SOFTCAP_BYTES
from . import policy


def validate_cost(reference):
    files.verify_small(reference)
    value = shared.load(reference["path"])
    shared.need(reference["path"] == str(shared.REPO / "configs/data_v1/user_allocation_overrun_report_continue_20261026_v1.json") and
        value.get("schema") == "USER_AUTHORIZED_ALLOCATION_OVERRUN_REPORT_CONTINUE_V1" and value.get("status") == "USER_AUTHORIZED" and
        value.get("on_overrun") == "REPORT_AND_CONTINUE" and value.get("original_threshold_multiplier") == 1.5 and
        all(value.get(key) is True for key in ("scientific_quality_thresholds_unchanged", "only_cost_stop_rule_changed",
            "retain_actual_accounting_including_failures_and_startup", "preserve_historical_requests_sources_and_results",
            "no_forced_termination")), "ACTUAL_COST_REPORT_CONTINUE_AUTHORITY_REQUIRED")


def startup(plan_path, proof_path):
    plan = shared.load(plan_path)
    shared.need(plan["schema"] == "PUBCHEM_RAW_UNIFORM_COST_PLAN_V1" and plan["status"] == "READY" and
        plan["scope_key"] == policy.SCOPE and plan["pilot"] is True and
        plan["whole_output_cap_bytes"] == policy.CAP, "EXACT_BOUNDED_RAW_UNIFORM_PLAN_REQUIRED")
    main = Path(__file__).parent / "run.py"
    argv = [shared.PY, "-B", "-m", "workflows.expansion.raw_uniform_cost_v1.run",
        "--plan", str(plan_path), "--root-preflight", str(proof_path)]
    proof = central.require_startup(proof_path, expected_scope_key=policy.SCOPE,
        expected_scope_parameters=plan["scope_parameters"], expected_execution_argv=argv,
        expected_source=main, expected_kind="analysis", required_references=(shared.pin(plan_path),))
    request = proof["request"]
    shared.need(request["pilot"] is True and request["scope"]["mode"] == "BOUNDED_PERFORMANCE_BATCH" and
        request["wall_seconds"] == policy.WALL and request["estimated_peak_output_bytes"] == policy.CAP and
        request["cpus"] == 16 and request["memory_policy"] == "SLURM_DEFAULT_UNSPECIFIED" and
        "memory_gib" not in request and proof["account_free_bytes"] - policy.CAP >= 200000000000,
        "ACTUAL_CPU16_NO_REQUESTED_MEMORY_4H2GIB200GB_REQUIRED")
    declared = {row["path"]: row for row in request["source_references"]}
    for reference in [*plan["code_sources"], *plan["authority_references"], shared.pin(plan_path)]:
        files.verify_small(reference, declared)
    validate_cost(plan["cost_decision_reference"])
    files.validate_scientific_anchors(plan)
    inventory = policy.authority(plan, proof)
    policy.verify_compatible_source(plan)
    return plan, proof, inventory


def memory_decision(value, elapsed):
    shared.need(all(type(value.get(key)) is int and value[key] >= 0 for key in
        ("own_current_tree_rss_bytes", "available_bytes", "total_bytes")) and
        value["total_bytes"] > 0 and value["available_bytes"] <= value["total_bytes"] and
        type(elapsed) in (int, float) and 0 <= elapsed < float("inf"), "INVALID_ACTUAL_MEMORY_SAMPLE")
    reason = None
    if value["own_current_tree_rss_bytes"] >= ALGORITHM_REFERENCE_SOFTCAP_BYTES:
        reason = "OWN_CURRENT_RSS_AT_ALGORITHM_REFERENCE48GIB_NOT_ALLOCATION"
    if value["available_bytes"] < value["total_bytes"] * .15:
        reason = reason or "CURRENT_NODE_MEMAVAILABLE_BELOW_RUNTIME15PCT_STOP_NOT_ADMISSION"
    return reason


class RuntimeBudget(ObservedMemoryBudget):
    """Lag is recorded; invalid values/RSS/availability/output/wall still stop."""
    def __init__(self, *args):
        super().__init__(*args)
        self.slow_samples, self.maximum_sample_seconds = 0, 0.

    def _loop(self):
        try:
            while not self.closed.is_set():
                started = time.monotonic()
                value = files.memory_sample(os.getpid())
                elapsed = time.monotonic() - started
                reason = memory_decision(value, elapsed)
                self.samples += 1
                self.slow_samples += int(elapsed > 2)
                self.maximum_sample_seconds = max(self.maximum_sample_seconds, elapsed)
                self.peak_current_rss_bytes = max(self.peak_current_rss_bytes, value["own_current_tree_rss_bytes"])
                self.minimum_available_bytes = value["available_bytes"] if self.minimum_available_bytes is None else min(
                    self.minimum_available_bytes, value["available_bytes"])
                if reason:
                    self._stop(reason)
                if time.monotonic() - self.started >= self.proof["request"]["wall_seconds"] - 120:
                    self._stop("STOP_NEW_DISPATCH_WITH120SECOND_DRAIN_MARGIN")
                self.closed.wait(1)
        except BaseException as exc:
            self._stop("CURRENT_MEMORY_MONITOR_FAILED:" + type(exc).__name__)

    def receipt(self):
        return {**super().receipt(), "slow_sample_count": self.slow_samples,
            "maximum_sample_elapsed_seconds": self.maximum_sample_seconds, "slow_sample_alone_is_memory_denial": False,
            "cost_decision_reference": self.plan["cost_decision_reference"], "cost_action": "REPORT_AND_CONTINUE",
            "cost_threshold_dispatch_stop_enabled": False, "allocation_ceiling_is_not_cost_forecast": True,
            "uniform_chemical_profile_forecast_available_before_this_job": False,
            "actual_parent_cost_must_be_bound_after_job_including_startup_hash_and_drain": True}
