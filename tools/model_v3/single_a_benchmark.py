"""One standalone A timing member; invoke in A/B/B/A order via root scheduling.

No torch.profiler or second resident model. Every run starts with seed weights
and its own optimizer. Timing evidence alone never grants numeric acceptance.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import time

from profile_s_baseline import REPO, save
from a_execution_runtime import (add_arguments, validate_arguments, load_references, bind_environment,
    stream_for, canonical_sha, corpus_receipt, append_json, guard_resources, install_termination_handler,
    compiler_counters, prepare_deterministic_controls, apply_deterministic_controls)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument("--role", choices=("reference", "candidate"), required=True)
    parser.add_argument("--abba-position", type=int, choices=(1, 2, 3, 4), required=True)
    parser.add_argument("--series-id", required=True)
    args = parser.parse_args()
    uuid = validate_arguments(args, paired=False)
    expected_role = ("reference", "candidate", "candidate", "reference")[args.abba_position - 1]
    if args.role != expected_role or not args.series_id or len(args.series_id) > 128:
        raise ValueError("Explicit A/B/B/A member order and bounded series ID required")
    if args.role == "reference" and (args.atom_bucket_width is not None or args.exact_atom_sort):
        raise ValueError("Reference timing must retain the original S sampler")
    args.deterministic_controls_binding = prepare_deterministic_controls(args.deterministic_controls)
    import fcntl
    locks = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
    args.output.mkdir(parents=True)
    install_termination_handler()
    with (locks / (uuid + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            return run(args, uuid)
        except BaseException as exc:
            if not (args.output / "run_status.json").exists():
                save(args.output / "run_status.json", {"status": "STARTUP_FAILED", "code_sha": args.code_sha,
                    "failure": {"type": type(exc).__name__, "message": str(exc)}, "resume_supported": False})
            raise


def run(args, uuid):
    import torch
    args.deterministic_controls_receipt = apply_deterministic_controls(args.deterministic_controls_binding)
    import wandb
    from s_model_memory_v1 import build_memory_bounded_model
    from phychem_mfm.model.v3_performance import (PerformanceOptions, build_performance_model,
        execution_context, make_adamw, performance_forward_pretrain)
    from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule, Phase1LossPolicy
    from phychem_mfm.supervision import SupervisionConfig
    from phychem_mfm.training.losses import LossWeights

    torch.set_num_threads(8)
    torch.set_num_interop_threads(1)
    environment = bind_environment(args, uuid)
    reference, a4, model_config, configuration = load_references(args)
    options = PerformanceOptions(**json.loads(args.candidate_options.read_text()))
    if options.precision != "fp32":
        raise ValueError("Standalone A timing accepts fp32 options only; B requires its own proxy study")
    selected = PerformanceOptions() if args.role == "reference" else options
    warmup, steps = (1, 2) if args.smoke else (2, 20)
    grouping = args.atom_bucket_width is not None or args.exact_atom_sort
    configuration.update(environment)
    configuration.update(role=args.role, candidate=asdict(options), effective_options=asdict(selected),
        series_id=args.series_id, abba_position=args.abba_position, warmup_updates=warmup,
        measured_updates=steps, smoke=args.smoke, torch_profiler_enabled=False,
        padding_exploration=grouping, numeric_acceptance=False,
        timing_semantics="standalone monitored wall includes loader, receipt, SDK and resource overhead;2warmup does not guarantee recompilation-free window")
    stream = tracker = None
    failure, status, cleanup_errors = None, "FAILED", []
    started = time.monotonic()
    measured_receipts, rows, foreign = [], [], False
    try:
        stream = stream_for(args, reference, candidate=args.role == "candidate")
        configuration["data_version"] = stream.bindings
        configuration["configuration_sha256"] = canonical_sha(configuration)
        save(args.output / "configuration.json", configuration)
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
        model = (build_memory_bounded_model(model_config) if args.role == "reference"
                 else build_performance_model(model_config, options)).cuda().train()
        optimizer = (torch.optim.AdamW(model.parameters(), **a4["optimizer"]) if args.role == "reference"
                     else make_adamw(model, a4["optimizer"], options))
        weights = LossWeights.from_mapping(configuration["loss_weights"])
        policy = Phase1LossPolicy.from_mapping(a4["loss_policy"])
        supervision = SupervisionConfig.from_variant("S")
        os.environ["WANDB_MODE"] = "offline"
        os.environ["WANDB_CACHE_DIR"] = str(args.output / "cache")
        os.environ["WANDB_DATA_DIR"] = str(args.output / "wandb_data")
        tracker = wandb.init(project="mfm_model_v3_development", mode="offline", dir=str(args.output),
            name=f"A_speed_{args.role}_{os.environ['SLURM_JOB_ID']}", config=configuration)
        print(json.dumps({"status": "READY", "role": args.role, "series_id": args.series_id}), flush=True)
        window_started = None
        compile_before = compiler_counters(selected.compile_backbone)
        compile_after_warmup = None
        for ordinal in range(warmup + steps):
            if ordinal == warmup:
                torch.cuda.synchronize()
                torch.cuda.reset_peak_memory_stats()
                compile_after_warmup = compiler_counters(selected.compile_backbone)
                window_started = time.perf_counter()
            tick = time.perf_counter()
            corpus = stream.next()
            loader_seconds = time.perf_counter() - tick
            receipt = corpus_receipt(corpus, stream.index)
            batch = corpus.encoder_batch.to("cuda", non_blocking=True)
            torch.cuda.synchronize()
            compute_tick = time.perf_counter()
            optimizer.zero_grad(set_to_none=True)
            with execution_context(selected):
                outputs = performance_forward_pretrain(model, batch, supervision.objectives)
                loss = compute_phase1_loss(outputs, batch, None, supervision, weights,
                                          Phase1JointSchedule(), ordinal, policy=policy)
                if not bool(torch.isfinite(loss.total)):
                    raise FloatingPointError("Nonfinite standalone timing loss")
                loss.total.backward()
                norm = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
                if not bool(torch.isfinite(norm)):
                    raise FloatingPointError("Nonfinite standalone timing gradient")
                optimizer.step()
            torch.cuda.synchronize()
            compute_seconds = time.perf_counter() - compute_tick
            stream.commit(corpus)
            resource = guard_resources(args.output, uuid)
            foreign |= resource["foreign_gpu_risk_observed"]
            row = {"optimizer_updates": ordinal + 1, "measured": ordinal >= warmup,
                "loss": float(loss.total.detach().cpu()), "gradient_norm": float(norm.detach().cpu()),
                "loader_seconds": loader_seconds, "compute_seconds": compute_seconds,
                "consumed_base_records": stream.committed_base_samples,
                "valid_label_counts": dict(loss.counts), "input": receipt,
                "committed_stream": stream.state_dict(), "resources": resource}
            tracker.log({"optimizer_updates": ordinal + 1, "loss": row["loss"],
                "compute_seconds": compute_seconds, "loader_seconds": loader_seconds,
                "base_records": receipt["base_records"], "native_atoms": receipt["native_atoms"],
                "consumed_base_records": stream.committed_base_samples,
                **{"valid_label_count/" + key: value for key, value in loss.counts.items()}}, step=ordinal + 1, commit=True)
            append_json(args.output / "steps.jsonl", row)
            if ordinal >= warmup:
                rows.append(row)
                measured_receipts.append(receipt["receipt_sha256"])
            del outputs, loss, batch, corpus
            print(json.dumps({"optimizer_updates": ordinal + 1, "measured": ordinal >= warmup,
                              "compute_seconds": compute_seconds}), flush=True)
        elapsed = time.perf_counter() - window_started
        base = sum(row["input"]["base_records"] for row in rows)
        atoms = sum(row["input"]["native_atoms"] for row in rows)
        molecules = sum(row["input"]["molecule_presentations"] for row in rows)
        status = "STANDALONE_TIMING_COMPLETED"
        save(args.output / "summary.json", {"status": status, "numeric_acceptance": False,
            "adoption_eligible": False, "role": args.role, "series_id": args.series_id,
            "abba_position": args.abba_position, "code_sha": args.code_sha, "prereg_sha": args.prereg_sha,
            "gpu_uuid": uuid, "gpu_name": configuration["gpu_name"], "input": args.input, "smoke": args.smoke,
            "seed": args.seed, "candidate_options_sha256": configuration["candidate_options_sha256"],
            "configuration_sha256": configuration["configuration_sha256"],
            "measured_updates": len(rows), "warmup_updates": warmup,
            "input_receipts_sha256": canonical_sha(measured_receipts), "measured_base_records": base,
            "measured_native_atoms": atoms, "elapsed_window_seconds": elapsed,
            "measured_molecule_presentations": molecules, "molecule_presentations_per_second": molecules / elapsed,
            "base_records_per_second": base / elapsed, "native_atoms_per_second": atoms / elapsed,
            "peak_allocated_bytes": torch.cuda.max_memory_allocated(), "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            "foreign_gpu_risk_observed": foreign, "padding_exploration": grouping,
            "timing_includes_monitoring_and_input_receipts": True,
            "cold_start_wall_seconds_before_window": time.monotonic() - started - elapsed,
            "compile_window_may_include_recompilation": bool(selected.compile_backbone),
            "compiler_counters_before_warmup": compile_before,
            "compiler_counters_after_warmup": compile_after_warmup,
            "compiler_counters_after_window": compiler_counters(selected.compile_backbone),
            "tracking_run_id": tracker.id, "tracking_mode": "offline", "resume_supported": False})
        return 0
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        if stream is not None:
            try:
                stream.close()
            except BaseException as exc:
                cleanup_errors.append({"component": "stream", "type": type(exc).__name__, "message": str(exc)})
        if tracker is not None:
            try:
                tracker.finish(exit_code=0 if status == "STANDALONE_TIMING_COMPLETED" and not cleanup_errors else 1)
            except BaseException as exc:
                cleanup_errors.append({"component": "tracking", "type": type(exc).__name__, "message": str(exc)})
        save(args.output / "run_status.json", {"status": status if not cleanup_errors else "CLEANUP_FAILED",
            "failure": failure, "cleanup_errors": cleanup_errors,
            "stream_cleanup": getattr(stream, "last_cleanup", None), "resume_supported": False,
            "elapsed_seconds": time.monotonic() - started})
        if cleanup_errors and failure is None:
            raise RuntimeError("Standalone timing cleanup failed")


if __name__ == "__main__":
    raise SystemExit(main())
