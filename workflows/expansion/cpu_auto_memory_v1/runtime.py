"""Fresh CPU-default-memory guards; no64GiB allocation or declared85% admission."""
from __future__ import annotations

import os
from pathlib import Path
import threading
import time

from workflows.data_v1_final.execution.cpu_auto_memory_queue_v2 import runtime as central
from workflows.data_v1_final.execution.queue_v1 import shared
from .. import full_queue_v1 as helpers


# These frozen helpers contain no scheduler-memory admission. Never call the
# frozen helpers.startup or helpers.RuntimeBudget under the new resource policy.
CooperativeStop = helpers.CooperativeStop
verify_small = helpers.verify_small
frame, portable, file_pin = helpers.frame, helpers.portable, helpers.file_pin
fresh_output, owned_bytes = helpers.fresh_output, helpers.owned_bytes
memory_sample = helpers.memory_sample
RESERVE = helpers.RESERVE
SCOPES = {"sb5_identity_profile_source_roles_v4": ("identity_profile", 14400),
          "sb5_pubchem_raw_inventory_v2": ("inventory", 14400),
          "sb5_official_source_headers_v1": ("official_head", 900)}
POLICY = "SLURM_DEFAULT_UNSPECIFIED"
ALGORITHM_REFERENCE_SOFTCAP_BYTES = 48 * 1024 ** 3


def startup(plan_path, proof_path, entry_path, *, scope):
    shared.need(scope in SCOPES, "ONLY_THREE_EXACT_EXISTING_SB5_SCIENTIFIC_SCOPES")
    plan = shared.load(plan_path)
    module, wall = SCOPES[scope]
    expected_entry = shared.REPO / "workflows/expansion/cpu_auto_memory_v1" / (module + ".py")
    shared.need(Path(entry_path).absolute() == expected_entry, "EXACT_NEW_RESOURCE_VARIANT_ENTRY")
    argv = [shared.PY, "-B", "-m", "workflows.expansion.cpu_auto_memory_v1." + module,
            "--plan", str(Path(plan_path)), "--root-preflight", str(Path(proof_path))]
    plan_ref = shared.pin(Path(plan_path))
    proof = central.require_startup(proof_path, expected_scope_key=scope,
        expected_scope_parameters=plan["scope_parameters"], expected_execution_argv=argv,
        expected_source=expected_entry, expected_kind="analysis", required_references=(plan_ref,))
    request = proof["request"]
    shared.need(proof["schema"] == "FRESH_CPU_AUTO_MEMORY_EXECUTION_ADMISSION_V1" and
        request["schema"] == "CPU_AUTO_MEMORY_QUEUED_REQUEST_V1" and
        proof["memory_policy"] == request["memory_policy"] == plan["memory_policy"] == POLICY and
        "memory_gib" not in request and request["cpus"] == 16 and request["wall_seconds"] == wall,
        "REAL_NEW_CPU_DEFAULT_MEMORY_PROOF_ONLY_NO_FAKE64G")
    shared.need(plan["status"] == "READY" and plan["scope_key"] == scope and
        type(plan["pilot"]) is bool and plan["pilot"] == request["pilot"] and
        plan["whole_output_cap_bytes"] == request["estimated_peak_output_bytes"] and
        proof["account_free_bytes"] - plan["whole_output_cap_bytes"] >= RESERVE,
        "PRESERVE_EXACT_SCIENTIFIC_SCOPE_OUTPUT_AND200GB_QUOTA")
    declared = {ref["path"]: ref for ref in request["source_references"]}
    for ref in [plan_ref, shared.pin(Path(__file__)), *plan["code_sources"], *plan["authority_references"],
                plan["resource_policy_authority"], plan["resource_migration_proof"], plan["baseline_plan"]]:
        verify_small(ref, declared)
    decision = shared.load(plan["resource_policy_authority"]["path"])
    shared.need(decision["schema"] == "USER_AUTHORIZED_CPU_AUTO_MEMORY_DECISION_V1" and
                decision["status"] == "USER_AUTHORIZED", "CURRENT_USER_RESOURCE_DECISION_REQUIRED")
    migration = shared.load(plan["resource_migration_proof"]["path"])
    shared.need(migration["schema"] == "SB5_CPU_AUTO_MEMORY_SOURCE_EQUIVALENCE_V1" and migration["status"] == "PASS" and
                migration["baseline_plan"] == plan["baseline_plan"], "ACTUAL_METADATA_SOURCE_EQUIVALENCE_PROOF_REQUIRED")
    for item in migration["files"]:
        verify_small(item["baseline_reference"], declared)
        verify_small(item["variant_reference"], declared)
        shared.need(item["inverse_full_file_bytes_equal"] is True and item["scientific_functions_normalized_AST_identical"] is True,
                    "SCIENCE_OR_FROZEN_BASELINE_CHANGED")
    if scope == "sb5_official_source_headers_v1":
        verify_small(plan["catalog_reference"], declared)
        verify_small(plan["official_document_reference"], declared)
    if scope != "sb5_official_source_headers_v1":
        helpers.validate_scientific_anchors(plan)  # Scientific evidence, never old resource admission.
    return plan, proof, {"status": "REAL_CPU_DEFAULT_MEMORY_STARTUP_VERIFIED", "memory_policy": POLICY,
        "memory_admission_evaluated": False, "declared_memory_85pct_rule_applied": False,
        "scheduler_memory_requested_by_this_entry": False, "source_migration_proof": plan["resource_migration_proof"],
        "startup_freshness_checked_once_before_body": True}


class RuntimeBudget:
    """Actual runtime observations and cooperative drain, not scheduler admission."""
    def __init__(self, output, plan, proof, stop):
        self.output, self.plan, self.proof, self.stop = Path(output), plan, proof, stop
        self.closed = threading.Event()
        self.started = time.monotonic()
        self.reason = None
        self.last_output_sample = float("-inf")
        self.peak_output_bytes = self.peak_current_rss_bytes = self.samples = 0
        self.minimum_available_bytes = None
        self.thread = threading.Thread(target=self._loop, name="sb5-default-memory-observation", daemon=False)

    def _stop(self, reason):
        self.reason = self.reason or reason
        self.stop.set()

    def _loop(self):
        try:
            while not self.closed.is_set():
                started = time.monotonic()
                value = memory_sample(os.getpid())
                self.samples += 1
                self.peak_current_rss_bytes = max(self.peak_current_rss_bytes, value["own_current_tree_rss_bytes"])
                self.minimum_available_bytes = value["available_bytes"] if self.minimum_available_bytes is None else min(
                    self.minimum_available_bytes, value["available_bytes"])
                if value["own_current_tree_rss_bytes"] >= ALGORITHM_REFERENCE_SOFTCAP_BYTES:
                    self._stop("OWN_CURRENT_RSS_AT_ALGORITHM_REFERENCE48GIB_NOT_ALLOCATION")
                if value["available_bytes"] < value["total_bytes"] * .15:
                    self._stop("CURRENT_NODE_MEMAVAILABLE_BELOW_RUNTIME15PCT_STOP_NOT_ADMISSION")
                if time.monotonic() - started > 2:
                    self._stop("CURRENT_MEMORY_SAMPLE_EXCEEDS2SECONDS")
                if time.monotonic() - self.started >= self.proof["request"]["wall_seconds"] - 120:
                    self._stop("STOP_NEW_DISPATCH_WITH120SECOND_DRAIN_MARGIN")
                self.closed.wait(1)
        except BaseException as exc:
            self._stop("CURRENT_MEMORY_MONITOR_FAILED:" + type(exc).__name__)

    def __enter__(self):
        self.thread.start()
        self.check()
        return self

    def check(self, *, force=False):
        if self.stop.is_set():
            raise CooperativeStop(self.reason or "COOPERATIVE_WORKER_STOP")
        now = time.monotonic()
        if not force and now - self.last_output_sample < .5:
            return
        self.last_output_sample = now
        value = owned_bytes(self.output)
        self.peak_output_bytes = max(self.peak_output_bytes, value)
        if value > self.plan["whole_output_cap_bytes"] - 8 * 1024 ** 2:
            self._stop("OWNED_OUTPUT_CAP_REACHED")
        if self.stop.is_set():
            raise CooperativeStop(self.reason or "COOPERATIVE_WORKER_STOP")

    def __exit__(self, *args):
        self.closed.set()
        self.thread.join(timeout=5)
        shared.need(not self.thread.is_alive(), "CURRENT_MEMORY_MONITOR_DID_NOT_CLOSE")
        if self.stop.is_set() and args[0] is None:
            raise CooperativeStop(self.reason or "Runtime STOP while naturally closing")

    def receipt(self):
        return {"samples": self.samples, "peak_sampled_current_owned_tree_rss_bytes": self.peak_current_rss_bytes,
            "minimum_sampled_node_MemAvailable_bytes": self.minimum_available_bytes,
            "peak_owned_output_bytes": self.peak_output_bytes, "first_stop_reason": self.reason,
            "memory_policy": POLICY, "scheduler_memory_requested": False, "scheduler_memory_gib_assumed": None,
            "slurm_memory_environment_observed": {key: os.environ.get(key) for key in
                ("SLURM_MEM_PER_NODE", "SLURM_MEM_PER_CPU", "SLURM_MEM_PER_GPU")},
            "algorithm_reference_softcap_bytes": ALGORITHM_REFERENCE_SOFTCAP_BYTES,
            "algorithm_reference_is_scheduler_allocation": False, "memory_admission_evaluated": False,
            "declared_memory_85pct_rule_applied": False, "runtime_low_MemAvailable_fraction": .15,
            "forced_signals_sent": False, "current_RSS_not_inherited_ru_maxrss": True,
            "startup_freshness_checked_once_not_after_hash_or_in_workers": True}
