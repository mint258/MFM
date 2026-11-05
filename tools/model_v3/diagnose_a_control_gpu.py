"""No-update GPU diagnosis of original-source repeatability versus A00 control.

Invoke default/deterministic in separate fresh Python processes. This script
never changes compare_tensors, tolerances, model implementations or gradients.
There is no optimizer, update, native input stream, checkpoint, or A acceptance.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace

REPO = Path(__file__).absolute().parents[2]
PREREG = "3441b280bc34431bf8e7596465af28be073644b6"


def require(value, message):
    if not value:
        raise ValueError(message)


def tensor_digest(value):
    import torch
    tensor = value.detach().cpu().contiguous()
    return hashlib.sha256(tensor.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()


def tensor_statistics(value):
    import torch
    if value is None:
        return {"gradient_present": False}
    data = value.detach().cpu()
    require(bool(torch.isfinite(data).all()), "Nonfinite diagnostic tensor")
    precise = data.double()
    return {"gradient_present": True, "shape": list(data.shape), "dtype": str(data.dtype),
        "numel": data.numel(), "l2_norm_fp64": float(torch.linalg.vector_norm(precise)),
        "max_absolute": float(precise.abs().max()) if data.numel() else 0.,
        "bitwise_tensor_sha256": tensor_digest(data)}


def gradient_diagnostics(reference, candidate):
    """Global norms supplement, and never replace, the per-parameter gate."""
    import torch
    require(set(reference) == set(candidate), "Diagnostic parameter keys differ")
    left_squared = right_squared = difference_squared = 0.
    missing = []
    for name in reference:
        left, right = reference[name], candidate[name]
        if left is None or right is None:
            if (left is None) != (right is None):
                missing.append(name)
            continue
        require(left.shape == right.shape, "Diagnostic gradient shape differs")
        left, right = left.double(), right.double()
        left_squared += float(left.square().sum())
        right_squared += float(right.square().sum())
        difference_squared += float((right - left).square().sum())
    reference_norm, candidate_norm, difference_norm = map(math.sqrt,
        (left_squared, right_squared, difference_squared))
    return {"reference_global_l2": reference_norm, "candidate_global_l2": candidate_norm,
        "difference_global_l2": difference_norm,
        "global_relative_l2": difference_norm / max(reference_norm, 1e-12),
        "one_sided_missing_gradients": missing, "diagnostic_only_not_an_acceptance_rule": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("default", "deterministic"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-gpu", choices=("3090", "4090", "5090"), required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--prereg-sha", default=PREREG)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--toy-ordinal", type=int, choices=(0, 1), default=0)
    parser.add_argument("--wall-seconds", type=int, default=600)
    parser.add_argument("--reference-config", type=Path,
                        default=REPO / "workflows/sprime_s/formal_s/B1_seed0_v2.json")
    args = parser.parse_args()
    require("torch" not in sys.modules, "Each mode requires a fresh process before any Torch import")
    require(all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (args.code_sha, args.prereg_sha)),
            "Full actual code/public preregistration commits required")
    require(60 <= args.wall_seconds <= 1800, "Bounded diagnostic wall limit required")
    require(os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16,
            "Owned Slurm allocation with at least16CPU required")
    selected_gpu = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    require(re.fullmatch(r"GPU-[0-9a-fA-F-]+", selected_gpu) is not None, "One explicit physical GPU UUID required")
    require(not args.output.exists() and not args.output.resolve().is_relative_to(REPO.resolve()),
            "Fresh external output required; preserve all previous diagnoses")
    workspace_before = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
    if args.mode == "deterministic":
        # Must happen before importing Torch or any project module importing it.
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    args.output.mkdir(parents=True)
    import fcntl
    lock_root = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
    from a_execution_runtime import install_termination_handler
    install_termination_handler()
    with (lock_root / (selected_gpu + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return run(args, selected_gpu, workspace_before)


def run(args, selected_gpu, workspace_before):
    from profile_s_baseline import save, synthetic_corpus, digest
    from a_execution_runtime import (bind_environment, load_references, corpus_receipt, canonical_sha,
                                     append_json, guard_resources)
    started = time.monotonic()
    status, failure = "FAILED", None
    completed = []
    try:
        import torch
        # Report/fail rather than silently claiming pre-initialization control.
        require(not torch.cuda.is_initialized(), "CUDA was initialized before diagnostic mode configuration")
        torch.set_num_threads(8)
        torch.set_num_interop_threads(1)
        deterministic = args.mode == "deterministic"
        torch.use_deterministic_algorithms(deterministic, warn_only=False)
        torch.backends.cudnn.deterministic = deterministic
        torch.backends.cudnn.benchmark = False
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        from s_model_memory_v1 import build_memory_bounded_model
        from phychem_mfm.model.v3_performance import (PerformanceOptions, build_performance_model,
            execution_context, performance_forward_pretrain)
        from phychem_mfm.training.v3_performance_acceptance import floating_outputs, gradients, compare_tensors
        from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule, Phase1LossPolicy
        from phychem_mfm.supervision import SupervisionConfig
        from phychem_mfm.training.losses import LossWeights
        environment = bind_environment(args, selected_gpu)
        options_path = REPO / "current/configs/model_v3/performance/a00_control.json"
        arguments = SimpleNamespace(**vars(args), input="synthetic", shard_snapshot_sha256=None,
                                    candidate_options=options_path)
        _reference, a4, model_config, configuration = load_references(arguments)
        options = PerformanceOptions(**json.loads(options_path.read_text()))
        require(options.precision == "fp32" and options.distance_implementation == "tiled"
            and options.distance_pair_rows == 65536 and options.distance_checkpointing
            and options.backbone_checkpointing is True and options.head_checkpointing
            and options.attention_backend == "dense" and not options.fused_adamw
            and not options.tf32 and not options.compile_backbone,
            "Diagnosis must use actual unchanged A00 control options")
        corpus = synthetic_corpus(args.seed, args.toy_ordinal)
        toy_receipt = corpus_receipt(corpus)
        package_versions = {}
        for package in ("numpy", "torch-geometric", "torch-scatter"):
            try:
                package_versions[package] = metadata.version(package)
            except metadata.PackageNotFoundError:
                package_versions[package] = None
        configuration.update(environment)
        configuration["source_sha256"]["tools/model_v3/diagnose_a_control_gpu.py"] = digest(Path(__file__))
        configuration.update(mode=args.mode, purpose="repeatability_and_control_no_update_diagnosis",
            optimizer_instantiated=False, optimizer_updates=0, native_input_stream_opened=False,
            training_acceptance=False, wandb_initialized=False,
            toy_input=toy_receipt, toy_ordinal=args.toy_ordinal,
            control_options=asdict(options), package_versions=package_versions,
            cublas_workspace_before=workspace_before,
            cublas_workspace_effective=os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
            cublas_workspace_set_before_torch_import=args.mode == "deterministic",
            torch_import_saw_cuda_uninitialized=True,
            deterministic_algorithms=torch.are_deterministic_algorithms_enabled(),
            deterministic_warn_only=torch.is_deterministic_algorithms_warn_only_enabled(),
            deterministic_debug_mode=torch.get_deterministic_debug_mode(),
            cudnn_deterministic=torch.backends.cudnn.deterministic, cudnn_benchmark=torch.backends.cudnn.benchmark,
            matmul_tf32=torch.backends.cuda.matmul.allow_tf32, cudnn_tf32=torch.backends.cudnn.allow_tf32,
            float32_matmul_precision=torch.get_float32_matmul_precision(),
            torch_default_dtype=str(torch.get_default_dtype()),
            cpu_threads=torch.get_num_threads(), interop_threads=torch.get_num_interop_threads(),
            environment_variables={name: os.environ.get(name) for name in ("CUDA_VISIBLE_DEVICES",
                "CUBLAS_WORKSPACE_CONFIG", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                "PYTHONHASHSEED", "SLURM_JOB_ID", "SLURM_CPUS_PER_TASK", "SLURM_MEM_PER_NODE", "SLURM_MEM_PER_CPU")},
            forward_relative_l2_gate=1e-5, gradient_per_parameter_relative_l2_gate=1e-4,
            relative_denominator="max(reference_parameter_gradient_l2,1e-12)",
            null_direction_note="Final distance-MLP bias adds one constant/head to every valid key logit; valid-key softmax is invariant to this shift. The -1e9 invalid-key sentinel underflows in fp32. No gradient is zeroed or excluded here.",
            deterministic_limit="Requested Torch algorithms can error on unsupported kernels; third-party CUDA extensions may not honor this flag. Actual repeats are reported.")
        configuration["configuration_sha256"] = canonical_sha(configuration)
        save(args.output / "configuration.json", configuration)
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed_all(args.seed)
        baseline = build_memory_bounded_model(model_config).cuda().train()
        require(all(parameter.dtype == torch.float32 for parameter in baseline.parameters()), "FP32 baseline parameters required")
        initial_state = {name: tensor.detach().cpu().clone() for name, tensor in baseline.state_dict().items()}
        state_receipts = {name: {"shape": list(value.shape), "dtype": str(value.dtype), "sha256": tensor_digest(value)}
                          for name, value in initial_state.items()}
        save(args.output / "initial_state_receipt.json", {"tensors": state_receipts,
            "state_sha256": canonical_sha(state_receipts), "weights_saved": False})
        second = build_memory_bounded_model(model_config)
        second.load_state_dict(initial_state, strict=True)
        second = second.cuda().train()
        candidate = build_performance_model(model_config, options)
        candidate.load_state_dict(initial_state, strict=True)
        candidate = candidate.cuda().train()
        models = {"original_repeat1": baseline, "original_repeat2": baseline, "original_repeat3": baseline,
                  "second_original_same_state": second, "a00_candidate_same_state": candidate}
        for model in (second, candidate):
            current = model.state_dict()
            require(set(current) == set(initial_state) and all(torch.equal(current[name].cpu(), value)
                    for name, value in initial_state.items()), "Initial parameter/state mismatch")
        cpu_rng = torch.get_rng_state().clone()
        cuda_rng = torch.cuda.get_rng_state(0).clone()
        weights = LossWeights.from_mapping(configuration["loss_weights"])
        policy = Phase1LossPolicy.from_mapping(a4["loss_policy"])
        supervision = SupervisionConfig.from_variant("S")
        bias_names = [name for name, _parameter in baseline.named_parameters() if name.endswith("dist_mlp.2.bias")]
        require(len(bias_names) == 6, "Expected six final distance-MLP biases")
        batch = corpus.encoder_batch.to("cuda", non_blocking=True)
        snapshots = {}
        for label, model in models.items():
            if time.monotonic() - started > args.wall_seconds - 30:
                raise TimeoutError("Diagnostic wall cap reached with finalization reserve")
            torch.set_rng_state(cpu_rng)
            torch.cuda.set_rng_state(cuda_rng, 0)
            model.zero_grad(set_to_none=True)
            torch.cuda.synchronize()
            tick = time.perf_counter()
            with execution_context(options):
                outputs = performance_forward_pretrain(model, batch, supervision.objectives)
                loss = compute_phase1_loss(outputs, batch, None, supervision, weights,
                    Phase1JointSchedule(), 0, policy=policy)
                require(bool(torch.isfinite(loss.total)), "Nonfinite diagnostic loss")
                loss.total.backward()
            torch.cuda.synchronize()
            cpu_outputs, cpu_gradients = floating_outputs(outputs), gradients(model)
            snapshots[label] = (cpu_outputs, cpu_gradients)
            statistics = {name: tensor_statistics(value) for name, value in cpu_gradients.items()}
            biases = {name: {**statistics[name], "raw_gradient_values": cpu_gradients[name].tolist(),
                "parameter_values": initial_state[name].tolist(), "analytic_null_direction": True}
                for name in bias_names}
            current = model.state_dict()
            require(all(torch.equal(current[name].cpu(), value) for name, value in initial_state.items()),
                    "A no-update diagnostic changed model state")
            row = {"label": label, "loss": float(loss.total.detach().cpu()), "valid_label_counts": dict(loss.counts),
                "elapsed_forward_backward_and_cpu_snapshot_seconds": time.perf_counter() - tick,
                "parameter_gradient_statistics": statistics, "distance_final_biases": biases,
                "floating_output_statistics": {name: tensor_statistics(value) for name, value in cpu_outputs.items()},
                "initial_state_unchanged": True, "cpu_rng_before_sha256": tensor_digest(cpu_rng),
                "cuda_rng_before_sha256": tensor_digest(cuda_rng),
                "resources": guard_resources(args.output, selected_gpu)}
            save(args.output / (label + ".json"), row)
            completed.append(label)
            append_json(args.output / "observations.jsonl", {"completed": label, "loss": row["loss"],
                "bias_norms": {name: value["l2_norm_fp64"] for name, value in biases.items()}})
            print(json.dumps({"completed": label, "mode": args.mode, "optimizer_updates": 0}), flush=True)
            del outputs, loss
        comparisons = []
        pairs = (("original_repeat1", "original_repeat2"), ("original_repeat1", "original_repeat3"),
                 ("original_repeat2", "original_repeat3"), ("original_repeat1", "second_original_same_state"),
                 ("original_repeat1", "a00_candidate_same_state"),
                 ("second_original_same_state", "a00_candidate_same_state"))
        for reference_label, candidate_label in pairs:
            left_outputs, left_gradients = snapshots[reference_label]
            right_outputs, right_gradients = snapshots[candidate_label]
            forward = compare_tensors(left_outputs, right_outputs, tolerance=1e-5)
            gradient = compare_tensors(left_gradients, right_gradients, tolerance=1e-4)
            original_gradient_rows = {row["name"]: row for row in gradient["tensors"]}
            bias_rows = {}
            for name in bias_names:
                left, right = left_gradients[name].double(), right_gradients[name].double()
                difference = right - left
                bias_rows[name] = {"reference_l2": float(torch.linalg.vector_norm(left)),
                    "candidate_l2": float(torch.linalg.vector_norm(right)),
                    "difference_l2": float(torch.linalg.vector_norm(difference)),
                    "max_absolute_difference": float(difference.abs().max()),
                    "reference_values": left.tolist(), "candidate_values": right.tolist(),
                    "raw_difference_values": difference.tolist(),
                    "original_per_parameter_gate_row": original_gradient_rows[name]}
            comparisons.append({"reference": reference_label, "candidate": candidate_label,
                "forward_original_gate": forward, "gradient_original_per_parameter_gate": gradient,
                "global_gradient_diagnostic": gradient_diagnostics(left_gradients, right_gradients),
                "distance_bias_diagnostics": bias_rows,
                "both_original_gates_pass": forward["pass"] and gradient["pass"]})
        status = "DIAGNOSTIC_COMPLETED"
        save(args.output / "diagnostic_comparisons.json", {"mode": args.mode, "comparisons": comparisons,
            "actual_A_acceptance": False, "thresholds_or_denominators_changed": False,
            "parameters_excluded_from_original_gate": [], "optimizer_updates": 0,
            "original_same_instance_repeat_all_gates_pass": all(row["both_original_gates_pass"] for row in comparisons[:3]),
            "initial_state_sha256": canonical_sha(state_receipts),
            "configuration_sha256": configuration["configuration_sha256"],
            "interpretation": "Compare original self-repeats and independent originals before attributing differences to the candidate. Tiny global errors never override a failed per-parameter gate. Analytic bias-null explanation is a hypothesis until these raw observations are reviewed."})
        return 0
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        save(args.output / "run_status.json", {"status": status, "failure": failure,
            "completed_no_update_evaluations": completed, "mode": args.mode, "optimizer_updates": 0,
            "actual_A_acceptance": False, "elapsed_seconds": time.monotonic() - started,
            "code_sha": args.code_sha, "prereg_sha": args.prereg_sha})


if __name__ == "__main__":
    raise SystemExit(main())
