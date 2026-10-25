"""Fixed-20-batch plus paired-500-update S execution-candidate acceptance.

Use run_supervised.py inside an owned single-GPU Slurm allocation. Synthetic or
--smoke results only validate the harness and cannot accept an A-class change.
Both models stay on one GPU; timings are diagnostic paired compute timings,
not standalone production throughput measurements.
"""
from __future__ import annotations

from dataclasses import asdict
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from profile_s_baseline import REPO, PUBLIC_PREREG, digest, save, source_bindings
from a_execution_runtime import (add_arguments, validate_arguments, load_references, bind_environment,
    stream_for, canonical_sha, corpus_receipt, append_json, guard_resources, install_termination_handler,
    prepare_deterministic_controls, apply_deterministic_controls)
from a_checkpoint_export import validate_export_destination, export_candidate_checkpoint


def main():
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    add_arguments(parser)
    parser.add_argument("--export-candidate-checkpoint", type=Path,
        help="Opt in H0-only export after full native20+500 gates and cleanup; fresh immediate child of --output")
    args = parser.parse_args()
    selected = validate_arguments(args, paired=True)
    args.export_candidate_checkpoint = validate_export_destination(args.export_candidate_checkpoint,
        output_root=args.output, repository_root=REPO)
    args.deterministic_controls_binding = prepare_deterministic_controls(args.deterministic_controls)
    import fcntl
    locks = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
    args.output.mkdir(parents=True)
    install_termination_handler()
    with (locks / (selected + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            return run(args, selected)
        except BaseException as exc:
            if not (args.output / "run_status.json").exists():
                save(args.output / "run_status.json", {"status": "STARTUP_FAILED", "code_sha": args.code_sha,
                    "failure": {"type": type(exc).__name__, "message": str(exc)}, "resume_supported": False})
            raise


def run(args, uuid):
    import torch
    args.deterministic_controls_receipt = apply_deterministic_controls(args.deterministic_controls_binding)
    import wandb
    from phychem_mfm.model.v3_performance import (PerformanceOptions, build_performance_model,
        performance_forward_pretrain, execution_context, make_adamw)
    from phychem_mfm.training.v3_performance_acceptance import floating_outputs, gradients, compare_tensors, trajectory_report
    from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule, Phase1LossPolicy
    from phychem_mfm.supervision import SupervisionConfig
    from phychem_mfm.training.losses import LossWeights
    from s_model_memory_v1 import build_memory_bounded_model
    from s_input_stream import SInputStream
    from runtime_monitor import gpu_observation, owned_output_bytes, owned_process_observation

    torch.set_num_threads(8)
    torch.set_num_interop_threads(1)
    if torch.cuda.device_count() != 1 or args.expected_gpu not in torch.cuda.get_device_name(0):
        raise RuntimeError("Actual GPU type/visibility differs")
    environment = bind_environment(args, uuid)
    gpu = environment["gpu"]
    options = PerformanceOptions(**json.loads(args.candidate_options.read_text()))
    if options.precision != "fp32":
        raise ValueError("This harness is only the A-class fp32 gate, not a B-class precision study")
    baseline_options = PerformanceOptions()
    reference, a4, config, bound_configuration = load_references(args)
    torch.manual_seed(args.seed)
    reference_model = build_memory_bounded_model(config).cuda().train()
    torch.manual_seed(args.seed)
    candidate_model = build_performance_model(config, options).cuda().train()
    left, right = reference_model.state_dict(), candidate_model.state_dict()
    if set(left) != set(right) or not all(torch.equal(left[name], right[name]) for name in left):
        raise RuntimeError("Execution candidate changed initial parameters/state keys")
    models = {"reference": reference_model, "candidate": candidate_model}
    runtime_options = {"reference": baseline_options, "candidate": options}
    weights = LossWeights.from_mapping({**reference["training"]["loss"], "denoise_sigma": .1,
                                       "geom_angle_std_deg": 0., "geom_bond_scale_std": 0.})
    policy = Phase1LossPolicy.from_mapping(a4["loss_policy"])
    supervision = SupervisionConfig.from_variant("S")
    batches, updates = (2, 2) if args.smoke else (20, 500)
    configuration = {**bound_configuration, **environment,
                     "model": config, "reference": asdict(baseline_options), "candidate": asdict(options),
                     "code_sha": args.code_sha, "prereg_sha": args.prereg_sha, "seed": args.seed,
                     "gpu": gpu, "optimizer": a4["optimizer"], "fixed_batches": batches,
                     "schedule": {"kind": "fixed_lr_numeric_equivalence", "lr": a4["optimizer"]["lr"]},
                     "trajectory_updates": updates, "smoke": args.smoke, "input": args.input,
                     "candidate_options_sha256": digest(args.candidate_options),
                     "torch_version": str(torch.__version__), "cuda_version": torch.version.cuda,
                     "logical_python": str(Path(sys.executable).absolute())}
    configuration["checkpoint_export"] = {"requested": args.export_candidate_checkpoint is not None,
        "destination": str(args.export_candidate_checkpoint) if args.export_candidate_checkpoint is not None else None,
        "scope": "H0_only_after_native20batch500update_gates_and_input_SDK_cleanup", "resume_supported": False}
    stream = None
    trackers = {}
    failure, final_status, cleanup_errors = None, "FAILED", []
    output_cap = int(os.environ.get("MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES", str(2 * 1024**3)))
    started = time.monotonic()
    science_finished = None
    checkpoint_export = None
    complete = False
    final_stream_state = None
    try:
        stream = stream_for(args, reference)
        configuration["data_version"] = stream.bindings
        canonical = json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        configuration["configuration_sha256"] = hashlib.sha256(canonical).hexdigest()
        save(args.output / "configuration.json", configuration)
        os.environ["WANDB_MODE"] = "offline"
        os.environ["WANDB_CACHE_DIR"] = str(args.output / "cache")
        os.environ["WANDB_DATA_DIR"] = str(args.output / "wandb_data")
        for name in models:
            trackers[name] = wandb.init(project="mfm_model_v3_development", mode="offline", dir=str(args.output),
                name=f"A_{name}_{os.environ['SLURM_JOB_ID']}", config={**configuration, "paired_role": name}, reinit="create_new")

        def loss_for(outputs, batch, update):
            return compute_phase1_loss(outputs, batch, None, supervision, weights,
                                       Phase1JointSchedule(), update, policy=policy)

        fixed = []
        first_receipt_sha = None
        all_input_receipts = []
        for number in range(batches):
            corpus = stream.next()
            receipt = corpus_receipt(corpus, stream.index)
            all_input_receipts.append(receipt["receipt_sha256"])
            if first_receipt_sha is None:
                first_receipt_sha = receipt["receipt_sha256"]
            batch = corpus.encoder_batch.to("cuda", non_blocking=True)
            snapshots = {}
            for name in ("reference", "candidate"):
                models[name].zero_grad(set_to_none=True)
                with execution_context(runtime_options[name]):
                    outputs = performance_forward_pretrain(models[name], batch, supervision.objectives)
                    loss = loss_for(outputs, batch, 0)
                    if not bool(torch.isfinite(loss.total)):
                        raise FloatingPointError("Nonfinite fixed-batch loss")
                    loss.total.backward()
                snapshots[name] = floating_outputs(outputs), gradients(models[name])
                del outputs, loss
            forward = compare_tensors(snapshots["reference"][0], snapshots["candidate"][0], tolerance=1e-5)
            gradient = compare_tensors(snapshots["reference"][1], snapshots["candidate"][1], tolerance=1e-4)
            fixed.append({"batch": number, "record_keys": list(corpus.record_keys), "forward": forward,
                          "input_receipt": receipt,
                          "gradient": gradient, "pass": forward["pass"] and gradient["pass"]})
            del snapshots
            stream.commit(corpus)
            append_json(args.output / "consumption.jsonl", {"phase": "fixed_batch", "batch": number,
                "input": receipt, "committed_stream": stream.state_dict()})
            append_json(args.output / "resources.jsonl", {"phase": "fixed_batch", "batch": number,
                **guard_resources(args.output, uuid)})
        fixed_gate = {"gate": "A_fixed_batch_equivalence", "batches": batches,
                      "pass": all(row["pass"] for row in fixed), "results": fixed}
        save(args.output / "fixed_batch_gate.json", fixed_gate)
        if not fixed_gate["pass"]:
            final_status = "FIXED_BATCH_GATE_FAILED"
            return 2
        stream.reset()
        first_trajectory = stream.next()
        if corpus_receipt(first_trajectory, stream.index)["receipt_sha256"] != first_receipt_sha:
            raise RuntimeError("Reset changed original first batch IDs/order/noise/input tensors")
        save(args.output / "stream_reset.json", {"same_first_input_sha256": first_receipt_sha,
            "committed_state_after_reset_before_update": stream.state_dict(), "workers_closed_before_reset": True})
        optimizers = {"reference": torch.optim.AdamW(reference_model.parameters(), **a4["optimizer"]),
                      "candidate": make_adamw(candidate_model, a4["optimizer"], options)}
        histories = {"reference": {}, "candidate": {}}
        consumed_records = 0
        for update in range(1, updates + 1):
            corpus = first_trajectory if update == 1 else stream.next()
            if update == 1:
                first_trajectory = None
            receipt = corpus_receipt(corpus, stream.index)
            batch = corpus.encoder_batch.to("cuda", non_blocking=True)
            order = ("reference", "candidate") if update % 2 else ("candidate", "reference")
            for name in order:
                torch.cuda.synchronize()
                tick = time.perf_counter()
                optimizer = optimizers[name]
                optimizer.zero_grad(set_to_none=True)
                with execution_context(runtime_options[name]):
                    outputs = performance_forward_pretrain(models[name], batch, supervision.objectives)
                    loss = loss_for(outputs, batch, update - 1)
                    if not bool(torch.isfinite(loss.total)):
                        raise FloatingPointError("Nonfinite trajectory loss")
                    loss.total.backward()
                    norm = torch.nn.utils.clip_grad_norm_(models[name].parameters(), 1.)
                    if not bool(torch.isfinite(norm)):
                        raise FloatingPointError("Nonfinite trajectory gradient")
                    optimizer.step()
                torch.cuda.synchronize()
                value = float(loss.total.detach().cpu())
                histories[name][update] = value
                row = {"optimizer_updates": update, "loss": value,
                       "gradient_norm": float(norm.detach().cpu()), "compute_seconds": time.perf_counter() - tick,
                       "base_records": len(corpus.logical_indices), "native_atoms": sum(corpus.native_atom_counts),
                       "consumed_base_records": consumed_records + len(corpus.logical_indices),
                       "input_receipt_sha256": receipt["receipt_sha256"],
                       "valid_label_counts": dict(loss.counts),
                       "peak_allocated_bytes": torch.cuda.max_memory_allocated()}
                trackers[name].log(row, step=update, commit=True)
                with (args.output / (name + "_history.jsonl")).open("a") as log:
                    log.write(json.dumps({**row, "valid_label_counts": loss.counts}, allow_nan=False) + "\n")
                    log.flush()
                    os.fsync(log.fileno())
                del outputs, loss
            stream.commit(corpus)
            consumed_records += len(corpus.logical_indices)
            append_json(args.output / "consumption.jsonl", {"phase": "trajectory", "optimizer_updates": update,
                "input": receipt, "committed_stream": stream.state_dict()})
            resource = guard_resources(args.output, uuid)
            append_json(args.output / "resources.jsonl", {"phase": "trajectory", "optimizer_updates": update, **resource})
            if update % 25 == 0 or update == updates:
                print(json.dumps({"updates": update, "consumed_base_records": consumed_records,
                    "foreign_gpu_risk_observed": resource["foreign_gpu_risk_observed"]}), flush=True)
        gate = trajectory_report(histories["reference"], histories["candidate"], expected_updates=updates)
        save(args.output / "trajectory_gate.json", gate)
        complete = args.input == "native_s" and not args.smoke and fixed_gate["pass"] and gate["pass"]
        final_status = "PAIRED_GATES_PASS" if gate["pass"] else "TRAJECTORY_GATE_FAILED"
        save(args.output / "summary.json", {"status": final_status, "full_A_numeric_acceptance": complete,
             "scope": "This execution candidate and batch stream only; all-GPU speed tables remain required",
             "configuration_sha256": configuration["configuration_sha256"], "code_sha": args.code_sha,
             "prereg_sha": args.prereg_sha, "gpu_uuid": uuid, "input": args.input, "smoke": args.smoke,
             "fixed_input_receipts_sha256": canonical_sha(all_input_receipts),
             "candidate_options_sha256": configuration["candidate_options_sha256"],
             "consumed_trajectory_base_records": consumed_records, "resume_supported": False,
             "timing_kind": "paired_two_resident_models_diagnostic_not_standalone_speed",
             "fixed_batch_pass": fixed_gate["pass"], "trajectory_pass": gate["pass"]})
        science_finished = time.monotonic()
        final_stream_state = stream.state_dict()
        return 0 if gate["pass"] else 2
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        if science_finished is None:
            science_finished = time.monotonic()
        finalization_started = time.monotonic()
        if stream is not None:
            try:
                stream.close()
            except BaseException as exc:
                cleanup_errors.append({"component": "stream", "type": type(exc).__name__, "message": str(exc)})
        for name, tracker in trackers.items():
            try:
                tracker.finish(exit_code=0 if final_status == "PAIRED_GATES_PASS" and not cleanup_errors else 1)
            except BaseException as exc:
                cleanup_errors.append({"component": name, "type": type(exc).__name__, "message": str(exc)})
        if complete and failure is None and not cleanup_errors:
            try:
                checkpoint_export = export_candidate_checkpoint(args.export_candidate_checkpoint,
                    output_root=args.output, repository_root=REPO, model=candidate_model,
                    optimizer=optimizers["candidate"], configuration=configuration, fixed_gate=fixed_gate,
                    trajectory_gate=gate, consumed_samples=consumed_records,
                    stream_state=final_stream_state, output_budget_bytes=output_cap)
            except BaseException as exc:
                cleanup_errors.append({"component": "candidate_checkpoint_export", "type": type(exc).__name__, "message": str(exc)})
        save(args.output / "run_status.json", {"status": final_status, "failure": failure,
             "cleanup_errors": cleanup_errors, "elapsed_seconds": time.monotonic() - started,
             "stream_cleanup": getattr(stream, "last_cleanup", None),
             "resume_supported": False,
             "scientific_elapsed_seconds": science_finished - started,
             "finalization_elapsed_seconds": time.monotonic() - finalization_started,
             "checkpoint_export": checkpoint_export,
             "job_id": os.environ["SLURM_JOB_ID"]})
        if cleanup_errors and failure is None:
            raise RuntimeError("Paired evidence cleanup failed; inspect run_status.json")


if __name__ == "__main__":
    raise SystemExit(main())
