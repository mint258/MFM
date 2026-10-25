"""Summarize three completed native-S profiles and nine immutable attributions.

Run on a compute allocation. Only small JSON/JSONL metadata is read; raw trace
hashes are inherited from the completed analysis receipts, not recomputed here.
No model, data loader, CUDA context, or training job is started.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

GPU_TYPES = ("3090", "4090", "5090")
OLD_JOBS = ("4520352", "4520353", "4520354")
NEW_JOBS = ("4520365", "4520366", "4520367")
PHASES = ("forward", "backward_forward_replay_scope", "backward")
CSV_REQUIRED = ("run_id", "stage", "config_sha256", "code_sha", "data_version", "seed",
                "gpu_model", "elapsed_seconds", "status", "preregistration_sha")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def finite(value, *, nonnegative=True):
    require(type(value) in (float, int) and math.isfinite(value) and (value >= 0 or not nonnegative),
            "Finite typed numeric observation required")
    return value


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def read_metadata(path, *, lines=False):
    path = Path(path).absolute()
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_size <= 16 * 1024**2,
            "Owned bounded ordinary metadata required: " + str(path))
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(16 * 1024**2 + 1)
        after = os.fstat(stream.fileno())
    require((info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns) ==
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) and len(raw) == info.st_size,
            "Metadata changed during read: " + str(path))
    def unique(items):
        result = {}
        for name, value in items:
            require(name not in result, "Duplicate metadata JSON key")
            result[name] = value
        return result
    def parse(value):
        return json.loads(value, object_pairs_hook=unique,
            parse_constant=lambda token: (_ for _ in ()).throw(ValueError("Nonfinite JSON: " + token)))
    value = [parse(line) for line in raw.splitlines() if line.strip()] if lines else parse(raw)
    return value, {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def reduce_attribution(value, *, expected_trace):
    require(value["schema"] == "model_v3_unique_kernel_attribution_v1", "Unknown attribution schema")
    require(value["gpu_categories_in_primary_union"] == ["kernel"] and len(value["devices"]) == 1,
            "One-device unique-kernel attribution required")
    require(value["invalid_kernel_events"] == 0 and value["invalid_duration_spans"] == 0,
            "Invalid trace durations cannot enter the report")
    trace = value["trace_binding"]
    require(Path(trace["path"]).absolute() == expected_trace.absolute(), "Attribution refers to another raw trace")
    require(re.fullmatch(r"[0-9a-f]{64}", trace["sha256"]) is not None, "Bound original trace SHA required")
    info = expected_trace.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid() and info.st_size == trace["bytes"],
            "Original trace path/size changed after analysis")
    device = next(iter(value["devices"].values()))
    busy = finite(device["kernel_busy_union_us"])
    rows = device["exclusive_busy_us"]
    require(device["exclusive_busy_reconciles"] is True and busy > 0, "Exclusive kernel union does not reconcile")
    total = sum(finite(row["microseconds"]) for row in rows)
    require(math.isclose(total, busy, abs_tol=1e-5, rel_tol=1e-9), "Exclusive categories do not partition busy union")
    cpu = value["cpu_thread_self_us"]
    for row in cpu:
        finite(row["microseconds"])
    peaks = list(value["allocator_trace_peaks"].values())
    require(len(peaks) == 1 and peaks[0]["not_a_causal_peak_decomposition"] is True,
            "One allocator inventory with explicit noncausal semantics required")
    peak = peaks[0]
    known = sum(finite(amount) for amount in peak["observed_live_bytes_by_allocation_site"].values())
    residual = finite(peak["untraced_or_unreconciled_residual_bytes"], nonnegative=False)
    require(known + residual == peak["total_allocated_bytes"], "Allocator observed sites/residual do not reconcile")
    return {"trace_binding": trace, "raw_trace_sha_recomputed_in_summary": False,
        "unique_kernels": value["unique_kernel_events"], "duplicates_removed": value["duplicate_kernel_events_removed"],
        "gpu_busy_union_us": busy, "exclusive_gpu_busy_us": rows,
        "cpu_thread_self_wall_us": cpu, "allocator_observed_inventory_at_trace_peak": peak,
        "unknown_kernel_examples": device["unknown_kernel_examples"],
        "diagnostics": {key: value[key] for key in ("cpu_crossing_spans", "negative_cpu_self_spans",
            "zero_duration_kernel_events", "ignored_non_kernel_gpu_event_counts", "analysis_source_sha256")}}


def combine_samples(samples):
    gpu, cpu = defaultdict(float), defaultdict(float)
    for sample in samples:
        for source, destination in (("exclusive_gpu_busy_us", gpu), ("cpu_thread_self_wall_us", cpu)):
            for row in sample[source]:
                destination[(row["component"], row["phase"])] += row["microseconds"]
    busy = sum(sample["gpu_busy_union_us"] for sample in samples)
    rows = [{"component": component, "phase": phase, "microseconds": amount,
             "fraction_of_three_trace_busy_union": amount / busy}
            for (component, phase), amount in sorted(gpu.items())]
    components = defaultdict(float)
    for (component, _phase), amount in gpu.items():
        components[component] += amount
    dist = sum(value for (component, _phase), value in gpu.items() if component == "dist_mlp")
    highest_peak = max(samples, key=lambda sample: sample["allocator_observed_inventory_at_trace_peak"]["total_allocated_bytes"])
    return {"representative_trace_count": len(samples), "gpu_busy_union_us": busy,
        "exclusive_gpu_busy_us": rows,
        "cpu_thread_self_wall_us": [{"component": key[0], "phase": key[1], "microseconds": amount}
                                     for key, amount in sorted(cpu.items())],
        "dist_mlp_gpu_fraction": dist / busy, "largest_observed_gpu_component": max(components, key=components.get),
        "dist_mlp_gpu_by_phase_us": {phase: gpu[("dist_mlp", phase)] for phase in PHASES},
        "unknown_gpu_busy_us": sum(amount for (component, _phase), amount in gpu.items() if component == "unknown"),
        "concurrent_gpu_busy_us": sum(amount for (component, _phase), amount in gpu.items() if component == "concurrent_multiple_components"),
        "highest_sample_allocator_peak": highest_peak["allocator_observed_inventory_at_trace_peak"],
        "highest_sample_allocator_ordinal": highest_peak["ordinal"],
        "scope": "duration-weighted pool of three representative traces; not a20-step exclusive-time census"}


def load_run(summary_path, attribution_paths, ledger, analysis_records, bindings):
    require(summary_path.name == "summary.json", "Explicit native summary.json paths required")
    root = summary_path.absolute().parent
    def read(name, *, lines=False):
        value, binding = read_metadata(root / name, lines=lines)
        bindings.append(binding)
        return value
    summary, config, status = read("summary.json"), read("configuration.json"), read("run_status.json")
    steps, timings = read("steps.jsonl", lines=True), read("step_timings.json")
    job = str(config["job_id"])
    require(job in NEW_JOBS and job in ledger, "Expected registered native v2 job missing")
    gpu_type = GPU_TYPES[NEW_JOBS.index(job)]
    require(gpu_type in config["gpu_name"], "Expected GPU model differs")
    supervisor_path = root.parent / ("native_supervisor_v2_" + job + ".json")
    supervisor, binding = read_metadata(supervisor_path)
    bindings.append(binding)
    monitor, binding = read_metadata(supervisor_path.with_suffix(".json.jsonl"), lines=True)
    bindings.append(binding)
    require(ledger[job]["State"] == "COMPLETED" and ledger[job]["ExitCode"] == "0:0",
            "Actual native Slurm parent did not complete")
    require(summary["status"] == status["status"] == "PROFILE_COMPLETED" and status["failure"] is None
            and not status["cleanup_errors"] and status["input_descriptors_closed"] is True,
            "Native child/input/SDK closure not complete")
    require(supervisor["status"] == "COMPLETED" and supervisor["exit_code"] == 0
            and supervisor["first_failure"] is None and not supervisor["remaining_recorded_processes_before_retirement"],
            "Supervisor did not complete")
    require(config["configuration_sha256"] == summary["configuration_sha256"] ==
            canonical_sha({key: value for key, value in config.items() if key != "configuration_sha256"}),
            "Configuration content hash mismatch")
    require(config["input"] == "native_s" and config["precision"] == "fp32" and config["distance_implementation"] == "tiled"
            and config["distance_tile_rows"] == 65536 and config["backbone_checkpointing"] is True
            and config["geometry_checkpointing"] is True and not config["tf32"] and not config["fused_adamw"],
            "This is not the actual tiled/checkpointed fp32 S baseline")
    require(config["profile_sampling"]["relative_steps"] == [0, 10, 19]
            and config["steps"] == summary["measured_optimizer_steps"] == 20 and config["warmup"] == 2,
            "Expected2warmup+20step representative protocol required")
    require(config["model"]["backbone"]["dim"] == 512 and config["model"]["backbone"]["layers"] == 6
            and config["model"]["backbone"]["heads"] == 8 and config["model"]["backbone"]["ff_mult"] == 2,
            "Expected6x512/8heads/FF2 backbone required")
    measured = [row for row in steps if row["measured"]]
    require([row["ordinal"] for row in measured] == list(range(2, 22)), "Measured update coverage differs")
    receipt = [{key: row[key] for key in ("ordinal", "logical_indices", "record_keys")} for row in measured]
    require([row["ordinal"] for row in timings] == list(range(2, 22)), "Complete-step timing coverage differs")
    selected = [row for row in timings if not row["profiled"]]
    require(len(selected) == 17 and [row["ordinal"] for row in selected] == summary["throughput_step_ordinals"],
            "Exactly17 unprofiled measured steps required")
    duration = sum(finite(row["end_to_end_step_seconds"]) for row in selected)
    require(math.isclose(duration, summary["throughput_elapsed_seconds"], rel_tol=1e-10), "Unprofiled timing total differs")
    indexed = {row["ordinal"]: row for row in measured}
    selected_steps = [indexed[row["ordinal"]] for row in selected]
    for metric, source in (("base_structures_per_second", "base_molecules"), ("molecule_presentations_per_second", "molecule_presentations"),
                           ("native_atoms_per_second", "base_atoms"), ("encoder_atoms_per_second", "encoder_atoms")):
        require(math.isclose(sum(row[source] for row in selected_steps) / duration, summary[metric], rel_tol=1e-9),
                "Raw consumed samples do not reproduce17-step throughput: " + metric)
    samples = []
    for ordinal in (2, 12, 21):
        expected = root / f"trace_step_{ordinal:04d}.attribution_v1.json"
        require(expected in attribution_paths, "Missing explicit attribution input: " + str(expected))
        require(str(expected) in analysis_records, "Attribution absent from completed9/9 analysis manifest")
        value, binding = read_metadata(expected)
        bindings.append(binding)
        sample = reduce_attribution(value, expected_trace=root / f"trace_step_{ordinal:04d}.json")
        sample.update(ordinal=ordinal, relative_step=ordinal - 2)
        samples.append(sample)
    report = {"gpu_type": gpu_type, "job_id": job, "slurm": ledger[job],
        "runtime_environment": {key: config[key] for key in ("gpu_name", "gpu_uuid", "gpu_total_bytes", "node",
            "torch_version", "cuda_version", "driver_version", "logical_python", "python_version")},
        "configuration_sha256": config["configuration_sha256"], "code_sha": config["code_sha"],
        "prereg_sha": config["prereg_sha"], "seed": config["seed"], "data_version": config["data_version"],
        "original_shard_snapshot": config["original_shard_snapshot"],
        "scientific_configuration": {key: config[key] for key in ("model", "optimizer", "loss_policy", "loss_weights", "sampler", "loader")},
        "source_bindings_sha256": canonical_sha(config["source_sha256"]),
        "measured_input_receipt_sha256": canonical_sha(receipt), "samples": samples,
        "throughput_17_steps": {key: summary[key] for key in ("throughput_elapsed_seconds", "base_structures_per_second",
            "molecule_presentations_per_second", "native_atoms_per_second", "encoder_atoms_per_second", "loader_wait_fraction")},
        "padding_20_steps": {"native_atom_fraction": summary["atom_padding_fraction"],
                             "native_pair_fraction": summary["pair_padding_fraction"]},
        "peak_20_steps": {"allocated_bytes": summary["peak_allocated_bytes"], "reserved_bytes": summary["peak_reserved_bytes"]},
        "measurement_loop_seconds_including_trace_export": summary["elapsed_profile_seconds"],
        "foreign_gpu_risk_observed": summary["foreign_gpu_risk_observed"],
        "whole_child_monitor_sampled_max": {
            "rss_sum_bytes": max(row["processes"]["rss_sum_bytes"] for row in monitor),
            "own_gpu_process_bytes": max(sum(item["used_memory_bytes"] or 0 for item in row["gpu"]["compute_processes"] if item["own"]) for row in monitor),
            "output_bytes": max(row["output_bytes"] for row in monitor), "exact_peak": False},
        "private_storage_sampled_max_bytes": supervisor["private_storage_final"]["sampled_max_bytes"],
        "private_storage_exact_peak": False, "tracking_run_id": summary["tracking_run_id"], "tracking_mode": summary["tracking_mode"]}
    wait = sum(row["loader_wait_seconds"] for row in selected_steps)
    compute = sum(row["compute_seconds"] for row in selected_steps)
    report["throughput_17_steps"].update(loader_wait_seconds=wait, compute_seconds=compute,
        loader_wait_fraction_denominator="loader_wait_plus_compute_not_end_to_end_wall",
        loader_wait_fraction_of_end_to_end_wall=wait / duration)
    report["padding_17_steps"] = {
        "native_atom_fraction": sum(row["base_atoms"] * 3 for row in selected_steps) / sum(row["padded_atoms"] for row in selected_steps),
        "native_pair_fraction": sum(row["native_pairs_including_diagonal"] for row in selected_steps) / sum(row["padded_pairs_including_diagonal"] for row in selected_steps)}
    require(math.isclose(wait / (wait + compute), summary["loader_wait_fraction"], rel_tol=1e-9),
            "17-step wait/compute fraction differs")
    report["representative_attribution"] = combine_samples(samples)
    return report


def result_csv(runs):
    rows = []
    for run in runs:
        metrics = run["throughput_17_steps"]
        attr = run["representative_attribution"]
        row = dict(run_id="profile_" + run["job_id"], stage="1", config_sha256=run["configuration_sha256"],
            code_sha=run["code_sha"], data_version="S_train_manifest_" + run["data_version"]["sha256"],
            seed=run["seed"], gpu_model=run["runtime_environment"]["gpu_name"],
            elapsed_seconds=run["slurm"]["elapsed_seconds"], status="COMPLETED", preregistration_sha=run["prereg_sha"],
            gpu_uuid=run["runtime_environment"]["gpu_uuid"], throughput_molecules_s=metrics["molecule_presentations_per_second"],
            peak_memory_bytes=run["peak_20_steps"]["allocated_bytes"], allocated_cpu_seconds=run["slurm"]["allocated_cpu_seconds"])
        extra = {"unprofiled_steps": 17, "measured_optimizer_steps": 20, "representative_traces": 3,
            "throughput_base_structures_s": metrics["base_structures_per_second"], "throughput_native_atoms_s": metrics["native_atoms_per_second"],
            "throughput_encoder_atoms_s": metrics["encoder_atoms_per_second"], "unprofiled_elapsed_seconds": metrics["throughput_elapsed_seconds"],
            "loader_wait_fraction": metrics["loader_wait_fraction"], "native_atom_fraction": run["padding_20_steps"]["native_atom_fraction"],
            "native_pair_fraction": run["padding_20_steps"]["native_pair_fraction"], "peak_reserved_bytes": run["peak_20_steps"]["reserved_bytes"],
            "native_atom_fraction_17_steps": run["padding_17_steps"]["native_atom_fraction"],
            "native_pair_fraction_17_steps": run["padding_17_steps"]["native_pair_fraction"],
            "loader_wait_fraction_of_end_to_end_wall": metrics["loader_wait_fraction_of_end_to_end_wall"],
            "actual_torch_gpu_capacity_bytes": run["runtime_environment"]["gpu_total_bytes"],
            "representative_gpu_busy_union_ms": attr["gpu_busy_union_us"] / 1000,
            "dist_mlp_representative_gpu_fraction": attr["dist_mlp_gpu_fraction"],
            "representative_unknown_gpu_ms": attr["unknown_gpu_busy_us"] / 1000,
            "representative_concurrent_gpu_ms": attr["concurrent_gpu_busy_us"] / 1000,
            "private_storage_sampled_max_bytes": run["private_storage_sampled_max_bytes"],
            "single_gpu_job_allocation_wall_seconds": run["slurm"]["elapsed_seconds"]}
        extra.update({"dist_mlp_" + phase + "_gpu_ms": amount / 1000 for phase, amount in attr["dist_mlp_gpu_by_phase_us"].items()})
        for phase in PHASES:
            extra["dist_mlp_" + phase + "_cpu_thread_self_ms"] = sum(item["microseconds"] for item in
                attr["cpu_thread_self_wall_us"] if item["component"] == "dist_mlp" and item["phase"] == phase) / 1000
        row.update({"metric__" + key: value for key, value in extra.items()})
        rows.append(row)
    return rows


def plots(runs, output):
    os.environ["MPLCONFIGDIR"] = str(output / "plot_cache")
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"dist_forward": "#3366aa", "dist_replay": "#668fbd", "dist_backward": "#9db6d1",
              "denoising_head": "#dd9f4b", "ffn": "#74a389", "attention_qk": "#906caa", "attention_softmax": "#b9a7c8",
              "attention_av": "#c6818b", "other_attention": "#cebb8a", "other_heads": "#b3cc9c", "loss": "#cfadbd",
              "optimizer": "#9cacbf", "other": "#c9c9c9", "unknown": "#666666", "concurrent": "#222222"}
    labels = [run["gpu_type"] for run in runs]
    fig, axes = plt.subplots(1, 3, figsize=(10.5, 3.3), constrained_layout=True)
    for axis, key, title in ((axes[0], "base_structures_per_second", "Base structures/s (17 steps)"),
                              (axes[1], "native_atoms_per_second", "Native atoms/s (17 steps)")):
        axis.bar(labels, [run["throughput_17_steps"][key] for run in runs], color="#4f799d")
        axis.set_title(title, fontsize=10)
        axis.set_ylim(bottom=0)
    positions = list(range(3))
    axes[2].bar([value - .16 for value in positions], [run["peak_20_steps"]["allocated_bytes"] / 1024**3 for run in runs], width=.32, label="allocated")
    axes[2].bar([value + .16 for value in positions], [run["peak_20_steps"]["reserved_bytes"] / 1024**3 for run in runs], width=.32, label="reserved")
    axes[2].set_xticks(positions, labels)
    axes[2].set_title("20-step CUDA peak (GiB)", fontsize=10)
    axes[2].legend(fontsize=8)
    fig.suptitle("Native S, tiled65536 + checkpoints; environments differ; n=1 run/GPU", fontsize=10)
    fig.savefig(output / "baseline_throughput.png", dpi=160)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    values = []
    for run in runs:
        groups = defaultdict(float)
        for row in run["representative_attribution"]["exclusive_gpu_busy_us"]:
            component = row["component"]
            if component == "dist_mlp":
                category = {"forward": "dist_forward", "backward_forward_replay_scope": "dist_replay", "backward": "dist_backward"}.get(row["phase"], "other")
            elif component in {"denoising_head", "ffn", "attention_qk", "attention_softmax", "attention_av", "other_heads", "loss", "optimizer", "unknown"}:
                category = component
            elif component.startswith("attention_"):
                category = "other_attention"
            else:
                category = "concurrent" if component == "concurrent_multiple_components" else "other"
            groups[category] += row["fraction_of_three_trace_busy_union"] * 100
        values.append(groups)
    left = [0.] * 3
    for category, color in colors.items():
        widths = [value.get(category, 0.) for value in values]
        if any(widths):
            axis.barh(labels, widths, left=left, label=category, color=color)
            left = [x + y for x, y in zip(left, widths)]
    axis.set_xlim(0, 100)
    axis.set_xlabel("Exclusive share of pooled unique-kernel busy union (%)")
    axis.set_title("Three sampled updates only; replay separated; unknown retained", fontsize=11)
    axis.legend(loc="upper center", bbox_to_anchor=(.5, -.2), ncol=4, fontsize=8)
    fig.savefig(output / "baseline_gpu_components.png", dpi=160)
    plt.close(fig)
    fig, axis = plt.subplots(figsize=(9, 4.8), constrained_layout=True)
    categories = sorted({site for run in runs for site in run["representative_attribution"]["highest_sample_allocator_peak"]["observed_live_bytes_by_allocation_site"]})
    left = [0.] * 3
    palette = plt.get_cmap("tab20")
    for index, category in enumerate(categories + ["untraced_residual"]):
        widths = []
        for run in runs:
            peak = run["representative_attribution"]["highest_sample_allocator_peak"]
            amount = (peak["untraced_or_unreconciled_residual_bytes"] if category == "untraced_residual" else
                      peak["observed_live_bytes_by_allocation_site"].get(category, 0))
            widths.append(amount / 1024**3)
        axis.barh(labels, widths, left=left, label=category, color="#444444" if category == "untraced_residual" else palette(index % 20))
        left = [x + y for x, y in zip(left, widths)]
    axis.set_xlabel("Observed live allocation-site inventory + untraced residual (GiB)")
    axis.set_title("Highest allocator peak among3 sampled traces; NOT causal peak contributions", fontsize=10)
    axis.legend(loc="upper center", bbox_to_anchor=(.5, -.2), ncol=4, fontsize=7)
    fig.savefig(output / "baseline_allocator_observation.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summaries", nargs=3, type=Path, required=True)
    parser.add_argument("--attributions", nargs=9, type=Path, required=True)
    parser.add_argument("--analysis-summary", type=Path, required=True)
    parser.add_argument("--job-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--no-plots", action="store_true")
    args = parser.parse_args()
    require(not args.output.exists(), "Fresh external report output required")
    require(not args.output.absolute().is_relative_to(Path(__file__).absolute().parents[2]), "Report artifacts must be generated outside the repository")
    bindings = []
    ledger_value, binding = read_metadata(args.job_ledger)
    bindings.append(binding)
    ledger = {str(row["job_id"]): row for row in ledger_value["jobs"]}
    require(len(ledger) == len(ledger_value["jobs"]), "Duplicate parent Slurm job IDs")
    for job in (*OLD_JOBS, *NEW_JOBS):
        require(job in ledger and str(ledger[job]["JobID"]) == job, "Explicit expected parent job absent")
        row = ledger[job]
        require(row["allocated_cpu_seconds"] == int(row["ElapsedRaw"]) * int(row["AllocCPUS"]), "Slurm CPU accounting mismatch")
    analysis, binding = read_metadata(args.analysis_summary)
    bindings.append(binding)
    records = analysis["analyses"]
    require(analysis["status"] == "PASS" and len(records) == 9 and all(row["returncode"] == 0 for row in records), "Actual9/9 completed trace analyses required")
    analysis_outputs = {row["output"] for row in records}
    attribution_paths = {path.absolute() for path in args.attributions}
    require(len(attribution_paths) == 9, "Nine distinct explicit attribution files required")
    runs = [load_run(path, attribution_paths, ledger, analysis_outputs, bindings) for path in args.summaries]
    runs.sort(key=lambda run: GPU_TYPES.index(run["gpu_type"]))
    require([run["gpu_type"] for run in runs] == list(GPU_TYPES), "Exactly one successful profile per GPU type required")
    require(len({run["measured_input_receipt_sha256"] for run in runs}) == 1, "Three GPUs did not consume identical20-step IDs/order")
    require(len({canonical_sha(run["scientific_configuration"]) for run in runs}) == 1
            and len({run["code_sha"] for run in runs}) == 1, "Scientific config/code differs across GPU types")
    require(len({run["data_version"]["sha256"] for run in runs}) == 1
            and len({run["original_shard_snapshot"]["sha256"] for run in runs}) == 1,
            "Input manifest/original shard snapshot rawSHA differs across GPU types")
    prior = []
    for job in OLD_JOBS:
        supervisor_path = args.job_ledger.absolute().parent / ("native_supervisor_" + job + ".json")
        observation, binding = read_metadata(supervisor_path)
        bindings.append(binding)
        row = {**ledger[job], "retained_failure": True, "supervisor_first_failure": observation["first_failure"],
               "supervisor_exit_code": observation["exit_code"], "last_observed_output_bytes": observation["last_output_bytes"]}
        command = observation["command"]
        child_output = Path(command[command.index("--output") + 1])
        require(child_output.parent == args.job_ledger.absolute().parent, "Old child output escaped this task's evidence root")
        if (child_output / "run_status.json").exists():
            child_status, binding = read_metadata(child_output / "run_status.json")
            bindings.append(binding)
            row["child_status"] = {key: child_status.get(key) for key in
                ("status", "failure", "cleanup_errors", "input_descriptors_closed")}
        else:
            row["child_status"] = None
        require(row["State"] == "FAILED", "Do not rewrite the retained original native failures")
        prior.append(row)
    result = {"schema": "model_v3_stage1_baseline_summary_v1", "review_status": "READY_FOR_ROOT_REVIEW_NOT_AUTOMATIC_STAGE_ACCEPTANCE",
        "runs": runs, "previous_native_failed_jobs": prior, "input_file_bindings": bindings,
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "cost_scope": "only native v1 jobs352-354 plus v2 jobs365-367; not full stage1/task costs",
        "costs": {name: {"parent_jobs": list(ids),
            "allocated_cpu_seconds": sum(ledger[job]["allocated_cpu_seconds"] for job in ids),
            "single_gpu_task_allocation_wall_seconds": sum(ledger[job]["elapsed_seconds"] for job in ids),
            "gpu_registered_or_reserved_by_Slurm": False, "gpu_utilization_seconds": None}
            for name, ids in (("successful_v2", NEW_JOBS), ("retained_failed_v1", OLD_JOBS), ("six_job_subset", OLD_JOBS + NEW_JOBS))},
        "findings": {"sampled_dist_mlp_is_largest_gpu_component_on_each_gpu": all(run["representative_attribution"]["largest_observed_gpu_component"] == "dist_mlp" for run in runs),
            "sampled_dist_mlp_exceeds_half_gpu_busy_union_on_each_gpu": all(run["representative_attribution"]["dist_mlp_gpu_fraction"] > .5 for run in runs),
            "memory_causal_dominance": "NOT_ESTABLISHED; allocation churn and observed-live sites are not causal peak contributions"},
        "limitations": ["Three sampled updates are not a20-step GPU component census.",
            "CPU self spans include blocking and sum threads; do not add them to GPU busy union.",
            "Primary GPU union contains kernels only; memcpy/memset are recorded separately in attribution diagnostics.",
            "CUDA allocated/reserved peaks cover all20 measured updates; allocator inventories cover sampled traces only.",
            "Actual GPU capacities, drivers and5090 CUDA environment differ; these are observations, not controlled architecture speedups.",
            "17-step monitored throughput includes loader/tracking/guard overhead, excluding separate profiler analysis/export.",
            "Private-storage sampled maximum can miss short-lived peaks.",
            "No original dense uncheckpointed hidden-tensor formula is used as a tiled-path measurement."]}
    args.output.mkdir(parents=True)
    text = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    require(len(text.encode()) <= 2 * 1024**2, "Compact baseline summary exceeds source-sized artifact cap")
    (args.output / "baseline_summary.json").write_text(text)
    rows = result_csv(runs)
    fields = list(CSV_REQUIRED) + sorted(set(rows[0]) - set(CSV_REQUIRED))
    with (args.output / "baseline_runs.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    require((args.output / "baseline_runs.csv").stat().st_size <= 128 * 1024, "Training-summary CSV exceeds checker cap")
    if not args.no_plots:
        plots(runs, args.output)
    artifacts = [path for path in args.output.rglob("*") if path.is_file()]
    require(all(not path.is_symlink() and path.stat().st_size <= 2 * 1024**2 for path in artifacts)
            and sum(path.stat().st_size for path in artifacts) <= 16 * 1024**2,
            "Compact output exceeded explicit per-file/total bounds")
    print(json.dumps({"status": "SUMMARY_READY_FOR_REVIEW", "output": str(args.output), "runs": [run["job_id"] for run in runs]}))


if __name__ == "__main__":
    main()
