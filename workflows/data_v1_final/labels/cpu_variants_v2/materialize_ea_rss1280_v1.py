"""Metadata-only next seven-case EA attempt with an evidence-based worker budget.

Root invocation after integration/review:
  python -B <Root>/workflows/data_v1_final/labels/cpu_variants_v2/materialize_ea_rss1280_v1.py \
    --node compute-0-17 --job-name dv1_ea_known_seven_rss1280_v1

Only worker_rss_stop_bytes changes: 1024MiB -> 1280MiB. The frozen v3 entry,
ru_maxrss guard, science, 16 workers, 32GiB allocation, 75% monitor and finite
7-case/14-context/6-source scope are unchanged. This is not a promise that later
batches fit. No scientific data, tests, scheduler query or submission runs here.
"""
from __future__ import annotations

import argparse
import copy
import importlib
import json
import os
from pathlib import Path
import re
import socket
import sys

RUN = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025")
REPO = RUN / "repository"
LABELS = REPO / "workflows/data_v1_final/labels"
HERE = LABELS / "cpu_variants_v2"
FAILED_NAME = "dv1_ea_known_seven_memory_v3"
ENTRY = LABELS / "ea_cpu_v2/bounded_probe_v3.py"
MIB = 1024**2
GIB = 1024**3
WORKER_LIMIT = 1280 * MIB


def evidence_review(h):
    output = RUN / "artifacts/labels/ea_diagnostic_v1" / FAILED_NAME
    paths = sorted(output.glob("worker_memory_v3_*.failure.json"))
    if len(paths) != 16:
        raise ValueError("EXACT_SIXTEEN_PRIOR_COMPACT_WORKER_FAILURES_REQUIRED")
    workers = []
    for path in paths:
        row = h.load(path)
        peak = row["metadata"]["observed_maxima_bytes"]
        if (row["schema"] != "EA_WORKER_MEMORY_DIAGNOSTIC_V3" or row["kind"] != "failure"
                or row["worker_rss_stop_bytes_unchanged"] != 1024 * MIB
                or row["extra"]["original_rss_guard_raised"] is not True
                or not 1024 * MIB < peak["ru_maxrss_bytes"] < WORKER_LIMIT
                or peak["current_mm_VmHWM_bytes"] != peak["ru_maxrss_bytes"]
                or not 1024 * MIB < peak["current_status_VmRSS_bytes"] <= peak["ru_maxrss_bytes"]
                or row["metadata"]["latest_pre_batch"]["context"]["batch_index"] != 0):
            raise ValueError("ACTUAL_WORKER_FAILURES_DO_NOT_SUPPORT_THIS_FINITE_BUDGET")
        workers.append({"reference_observed_now": h.small(path), "pid": row["pid"],
            "ru_maxrss_bytes": peak["ru_maxrss_bytes"], "VmHWM_bytes": peak["current_mm_VmHWM_bytes"],
            "current_status_RSS_bytes": peak["current_status_VmRSS_bytes"],
            "current_statm_RSS_bytes": peak["current_statm_RSS_bytes"]})
    if len({r["pid"] for r in workers}) != 16:
        raise ValueError("SIXTEEN_DISTINCT_ACTUAL_WORKER_FAILURES_REQUIRED")
    guard = RUN / "artifacts/cpu_analysis_guards" / FAILED_NAME
    closure = h.load(guard / "closure.json")
    if (closure["job_id"] != "4520560" or closure["child_returncode"] != 1
            or closure["first_denial"] is not None or closure["monitor_io_failure"] is not None
            or closure["monitor_thread_closed"] is not True or closure["durable_evidence_exported"] is not True):
        raise ValueError("PRIOR_JOB_MONITOR_FAILURE_OR_CLOSURE_DIFFERS")
    for pin in closure["evidence_exports"]:
        h.small(pin["path"], pin)
    samples_path = guard / "samples.jsonl"
    samples = [json.loads(line) for line in h.RAW[samples_path].splitlines() if line]
    if (len(samples) != closure["samples"] or not samples
            or any(r["state"] != "ALLOW" or r["job_id"] != "4520560" for r in samples)):
        raise ValueError("ACTUAL_MONITOR_SAMPLE_SET_NOT_ALL_ALLOW_OR_IDENTICAL_JOB")
    maximum_tree = max(r["own_tree_rss_bytes"] for r in samples)
    pre_pool = [r["own_tree_rss_bytes"] for r in samples if r["own_processes"] <= 3]
    # This is a nominal budget, not an OS RSS limit or a bound on future batches.
    # Reserve 2GiB for parent/IPC/monitor; keep another 2GiB below global 75%.
    worker_nominal = 16 * WORKER_LIMIT
    other_reserve = 2 * GIB
    global_stop = 32 * GIB * 3 // 4
    if (not pre_pool or max(pre_pool) >= GIB or maximum_tree >= global_stop
            or worker_nominal + other_reserve >= global_stop):
        raise ValueError("OBSERVED_OR_CONSERVATIVE_TOTAL_DOES_NOT_FIT_UNCHANGED_32G_75PCT")
    return {"schema": "EA_RSS1280_PRIOR_ACTUAL_BUDGET_REVIEW_V1", "prior_job_id": "4520560",
        "workers": workers, "workers_count": 16,
        "worker_peak_max_bytes": max(r["ru_maxrss_bytes"] for r in workers),
        "worker_peak_sum_bytes_not_concurrent_measurement": sum(r["ru_maxrss_bytes"] for r in workers),
        "monitor_closure": h.small(guard / "closure.json"), "monitor_samples": h.small(samples_path),
        "monitor_sample_count": len(samples), "monitor_tree_RSS_max_bytes": maximum_tree,
        "observed_pre_full_pool_tree_RSS_max_bytes": max(pre_pool),
        "proposed_worker_limit_bytes": WORKER_LIMIT, "nominal_16_worker_budget_bytes": worker_nominal,
        "conservative_parent_IPC_monitor_reserve_bytes": other_reserve,
        "nominal_total_with_reserve_bytes": worker_nominal + other_reserve,
        "unchanged_32GiB_75pct_stop_bytes": global_stop,
        "remaining_nominal_margin_bytes": global_stop - worker_nominal - other_reserve,
        "first_batch_only_not_later_source_pass_peak_proof": True,
        "per_worker_guard_checked_after_batch_not_OS_enforced": True,
        "root_authorized_small_pilot_internal_budget_only": True,
        "formal_generation_or_global_envelope_relaxed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", required=True)
    parser.add_argument("--job-name", required=True)
    args = parser.parse_args()
    if (os.getuid() != 1278 or socket.gethostname().split(".")[0] != "sonmi"
            or Path(__file__).absolute() != HERE / "materialize_ea_rss1280_v1.py"
            or not re.fullmatch(r"dv1_[A-Za-z0-9_]+", args.job_name)):
        raise ValueError("ACTUAL_ROOT_METADATA_ENTRY_AND_SAFE_FRESH_NAME_REQUIRED")
    sys.path.insert(0, str(REPO))
    prior = importlib.import_module("workflows.data_v1_final.labels.cpu_variants_v2.materialize_ea_memory_v3")
    if Path(prior.__file__).absolute() != HERE / "materialize_ea_memory_v3.py":
        raise ValueError("PRIOR_STDLIB_METADATA_HELPER_NOT_ROOT_ACTUAL")
    h, _ = prior.metadata_helper()
    h.small(Path(__file__).absolute())
    _, scope, base, template, old_cfg, old_proof = h.collect("EA_known_seven", args.node)
    previous_receipt = h.load(RUN / f"control/{FAILED_NAME}.materialization.json")
    source_proof_pin = previous_receipt["source_proof"]
    source_proof = h.load(source_proof_pin["path"], source_proof_pin)
    if (source_proof["schema"] != "EA_WORKER_MEMORY_DIAGNOSTIC_SOURCE_PROOF_V3"
            or source_proof["status"] != "PASS"
            or source_proof["original_ru_maxrss_guard_literal_bytes_unchanged"] is not True
            or source_proof["variant_actual_root_reference"]["path"] != str(ENTRY)):
        raise ValueError("PRIOR_ACTUAL_ROOT_V3_SOURCE_PROOF_REQUIRED")
    h.small(ENTRY, source_proof["variant_actual_root_reference"])
    h.small(source_proof["source_ledger_actual_root_reference"]["path"], source_proof["source_ledger_actual_root_reference"])
    if (old_cfg["worker_rss_stop_bytes"] != 1024 * MIB or old_cfg["source_batch_records"] != 16
            or old_cfg["workers"] != 16 or old_cfg["memory_gib"] != 32):
        raise ValueError("ORIGINAL_WORKER_AND_ALLOCATION_CONFIG_DIFFERS")
    review = evidence_review(h)
    cfg = copy.deepcopy(old_cfg)
    cfg["worker_rss_stop_bytes"] = WORKER_LIMIT
    if (set(cfg) != set(old_cfg) or {k for k in cfg if cfg[k] != old_cfg[k]} != {"worker_rss_stop_bytes"}
            or {**cfg, "worker_rss_stop_bytes": old_cfg["worker_rss_stop_bytes"]} != old_cfg):
        raise ValueError("CONFIG_CHANGE_NOT_STRICTLY_ONE_INTERNAL_RESOURCE_KEY")
    name = args.job_name
    output = Path(cfg["external_output_root"]) / name
    config = RUN / f"control/requests/{name}.run_actual.json"
    command_file = RUN / f"control/{name}.command.json"
    review_file = RUN / f"control/{name}.worker_budget_review.json"
    request = RUN / f"control/requests/{name}.json"
    bound = RUN / f"control/requests/{name}.bound.json"
    script = RUN / f"control/scripts/{name}.sbatch"
    receipt_file = RUN / f"control/{name}.materialization.json"
    intent = RUN / f"control/submissions/{name}.intent.json"
    destinations = (output, config, command_file, review_file, request, bound, script, receipt_file, intent,
                    RUN / f"control/submissions/{name}.json", RUN / "artifacts/cpu_analysis_guards" / name)
    if any(p.exists() or p.is_symlink() for p in destinations) or any(p.is_symlink() for p in output.parents):
        raise FileExistsError("FRESH_NAME_AND_OUTPUT_REQUIRED_NO_OLD_ARTIFACT_CHANGE_OR_RETRY")
    h.new_file(config, h.encoded(cfg))
    config_pin = h.small(config)
    # Read back the actual fresh bytes and independently check the exact key diff.
    actual_cfg = h.load(config)
    if actual_cfg != cfg or {k for k in old_cfg if old_cfg[k] != actual_cfg[k]} != {"worker_rss_stop_bytes"}:
        raise ValueError("ACTUAL_WRITTEN_CONFIG_SINGLE_KEY_PROOF_FAILED")
    command = [h.PYTHON, "-B", str(ENTRY), "--config", str(config), "--root-preflight", str(intent), "--output", str(output)]
    h.new_file(command_file, h.encoded(command))
    command_pin = h.small(command_file)
    review.update({"source_entry_unchanged_reference": source_proof["variant_actual_root_reference"],
        "prior_source_proof_for_unchanged_code": source_proof_pin, "original_root_v2_bindings": old_proof,
        "original_template_reference": h.small(template), "new_config_reference": config_pin,
        "config_changed_keys": ["worker_rss_stop_bytes"], "old_worker_limit_bytes": 1024 * MIB,
        "new_worker_limit_bytes": WORKER_LIMIT, "all_other_config_JSON_values_identical": True,
        "scientific_scope_masks_QM_and_entry_unchanged": True,
        "legacy_worker_metadata_limit_field_reports_active_config_value": True,
        "output_directory": str(output), "command_reference": command_pin})
    h.new_file(review_file, h.encoded(review))
    review_pin = h.small(review_file)
    expected_sources = dict(h.SOURCES)
    central = importlib.import_module("workflows.data_v1_final.execution.cpu_analysis_v1.prepare_request_v2")
    if Path(central.__file__).absolute() != h.CENTRAL / "prepare_request_v2.py":
        raise ValueError("CENTRAL_PREPARE_NOT_ROOT_ACTUAL")
    argv = [str(h.CENTRAL / "prepare_request_v2.py"), "--scope", "EA_known_seven", "--node", args.node,
            "--job-name", name, "--command-file", str(command_file)]
    for path in sorted(expected_sources, key=str):
        argv += ["--source", str(path)]
    saved = sys.argv
    try:
        sys.argv = argv
        central.main()
    finally:
        sys.argv = saved
    prepared = h.load(request)
    original_raw = h.RAW[request]
    sources = h.by_path(prepared["source_references"])
    if (prepared["execution_argv"] != command or prepared["memory_gib"] != 32 or prepared["cpus"] != 16
            or prepared["scope_parameters"] != scope["parameters"] or prepared["data_references"] != base["data_references"]
            or any(sources.get(pin["path"]) != pin for pin in expected_sources.values())):
        raise ValueError("CENTRAL_FINITE_REQUEST_OR_SOURCE_CLOSURE_DIFFERS")
    h.small(script)
    if re.findall(rb"(?m)^#SBATCH --partition=(\S+)$", h.RAW[script]) != [b"cpu"]:
        raise ValueError("ACTUAL_SCRIPT_CPU_PARTITION_REQUIRED")
    additions = {"ea_worker_budget_1280_v1": {"actual_prior_evidence_and_single_key_proof": review_pin,
                 "output_directory": str(output), "internal_resource_budget_only": True}}
    if "partition" not in prepared:
        additions["partition"] = "cpu"
    if prepared.get("partition", "cpu") != "cpu" or set(additions) & set(prepared):
        raise ValueError("ADDITIVE_BOUND_KEYS_CONFLICT")
    value = {**copy.deepcopy(prepared), **additions}
    h.new_file(bound, h.encoded(value))
    if request.read_bytes() != original_raw or any(value[k] != v for k, v in prepared.items()):
        raise ValueError("ORIGINAL_CENTRAL_REQUEST_CHANGED")
    receipt = {"schema": "EA_RSS1280_PREPARATION_RECEIPT_V1", "status": "PREPARED_NOT_SUBMITTED_NOT_EXECUTED",
        "central_request_original": h.small(request), "bound_request_to_submit": h.small(bound), "script": h.small(script),
        "worker_budget_evidence_and_single_key_proof": review_pin, "new_config": config_pin,
        "source_entry_unchanged": source_proof["variant_actual_root_reference"], "bound_only_additive_keys": sorted(additions),
        "prepared_submitter_argv_only": [h.PYTHON, "-B", "-m", "workflows.data_v1_final.execution.cpu_analysis_v1.submit_cpu_pilot_v3",
                                         "--request", str(bound)],
        "submitter_pinned": h.small(h.CENTRAL / "submit_cpu_pilot_v3.py"), "scheduler_commands_run": [],
        "science_executed": False, "scientific_data_bodies_or_stat_opened": False, "output_directory": str(output)}
    h.new_file(receipt_file, h.encoded(receipt))
    print(json.dumps({"status": receipt["status"], "bound_request": str(bound), "receipt": str(receipt_file), "output": str(output)}))


if __name__ == "__main__":
    main()
