"""Small shared receipts and guards for A diagnostics and standalone timings."""
from __future__ import annotations

from dataclasses import asdict
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import socket
import sys

from profile_s_baseline import REPO, PUBLIC_PREREG, digest, source_bindings


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def add_arguments(parser):
    parser.add_argument("--candidate-options", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--prereg-sha", default=PUBLIC_PREREG)
    parser.add_argument("--expected-gpu", choices=("3090", "4090", "5090"), required=True)
    parser.add_argument("--input", choices=("synthetic", "native_s"), default="native_s")
    parser.add_argument("--reference-config", type=Path, default=REPO / "workflows/sprime_s/formal_s/B1_seed0_v2.json")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--max-padded-cost", type=int, default=8_000_000)
    parser.add_argument("--shard-snapshot-sha256")
    parser.add_argument("--atom-bucket-width", type=int)
    parser.add_argument("--exact-atom-sort", action="store_true")
    parser.add_argument("--deterministic-controls", action="store_true",
                        help="Opt in both roles to pre-import CUBLAS binding and strict Torch/cuDNN determinism")
    parser.add_argument("--resume", type=Path, help="Unsupported: this bounded A diagnostic requires fresh complete runs")
    parser.add_argument("--smoke", action="store_true")


def validate_arguments(args, *, paired):
    if args.resume is not None:
        raise ValueError("A diagnostics do not resume weights/optimizer/RNG/cursor; preserve partial evidence and use a fresh output")
    cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    if not os.environ.get("SLURM_JOB_ID") or cpus < 16:
        raise RuntimeError("Owned Slurm allocation with >=16 CPUs required")
    if not all(re.fullmatch(r"[a-f0-9]{40}", value) for value in (args.code_sha, args.prereg_sha)):
        raise ValueError("Full actual/public prerequisite Git commits required")
    if not (0 <= args.workers <= 16 and 0 < args.max_padded_cost <= 8_000_000):
        raise ValueError("Bounded native S loader/sampler required")
    if args.atom_bucket_width is not None and not 1 <= args.atom_bucket_width <= 64:
        raise ValueError("Bounded positive atom bucket width required")
    grouping = args.atom_bucket_width is not None or args.exact_atom_sort
    if grouping and args.input != "native_s":
        raise ValueError("Grouping experiments require native S, not a synthetic substitute")
    if paired and grouping:
        raise ValueError("Bucket/sort can regroup optimizer batches and is not admitted as an A-equivalent change; use standalone exploratory timing only")
    if args.input == "native_s" and not re.fullmatch(r"[a-f0-9]{64}", args.shard_snapshot_sha256 or ""):
        raise ValueError("Pre-job original shard snapshot SHA256 required")
    if args.output.exists() or args.output.resolve().is_relative_to(REPO.resolve()):
        raise FileExistsError("Fresh external output required")
    selected = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not re.fullmatch(r"GPU-[a-fA-F0-9-]+", selected):
        raise RuntimeError("Bind exactly one complete physical GPU UUID")
    return selected


def load_references(args):
    reference = json.loads(args.reference_config.read_text())
    a4_path = REPO / "workflows/s_denoise/configs/A4_seed0_v3.json"
    a4 = json.loads(a4_path.read_text())
    config = copy.deepcopy(a4["model"])
    config["backbone"].update(dim=512, layers=6, heads=8)
    config["expert"]["heads"] = 8
    from phychem_mfm.supervision import SupervisionConfig
    supervision = SupervisionConfig.from_variant("S")
    weights = {**reference["training"]["loss"], "denoise_sigma": .1,
               "geom_angle_std_deg": 0., "geom_bond_scale_std": 0.}
    binding = {"model": config, "optimizer": a4["optimizer"],
        "loss_policy": a4["loss_policy"], "loss_weights": weights, "supervision": supervision.to_dict(),
        "schedule": {"kind": "fixed_lr_numeric_equivalence", "lr": a4["optimizer"]["lr"]},
        "gradient_clip_norm": 1., "dynamic_balancer": False,
        "reference_configuration": {"path": str(args.reference_config), "sha256": digest(args.reference_config)},
        "a4_configuration": {"path": str(a4_path), "sha256": digest(a4_path)},
        "original_shard_snapshot_prejob_sha256": args.shard_snapshot_sha256,
        "seed": args.seed, "input": args.input, "code_sha": args.code_sha, "prereg_sha": args.prereg_sha,
        "candidate_options_sha256": digest(args.candidate_options), "job_id": os.environ["SLURM_JOB_ID"],
        "node": socket.gethostname(), "logical_python": str(Path(sys.executable).absolute()),
        "python_version": sys.version, "source_sha256": a_source_bindings()}
    if hasattr(args, "deterministic_controls_receipt"):
        binding["deterministic_controls"] = args.deterministic_controls_receipt
    return reference, a4, config, binding


def prepare_deterministic_controls(requested):
    """Bind an explicit opt-in before importing Torch; disabled changes nothing."""
    if type(requested) is not bool:
        raise ValueError("Deterministic controls require an explicit boolean")
    imported = "torch" in sys.modules
    previous = os.environ.get("CUBLAS_WORKSPACE_CONFIG")
    if requested:
        if imported:
            raise RuntimeError("Deterministic controls must bind CUBLAS before any Torch import")
        os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"
    return {"schema": "model_v3_deterministic_controls_v1", "requested": requested,
            "torch_imported_before_binding": imported, "cublas_workspace_before": previous,
            "cublas_workspace_after_preimport_binding": os.environ.get("CUBLAS_WORKSPACE_CONFIG")}


def apply_deterministic_controls(binding):
    """Run immediately after the entry point imports Torch, before CUDA init."""
    import torch
    initialized = torch.cuda.is_initialized()
    if binding["requested"]:
        if binding["torch_imported_before_binding"] or initialized:
            raise RuntimeError("Requested deterministic controls were not configured before Torch/CUDA initialization")
        if os.environ.get("CUBLAS_WORKSPACE_CONFIG") != ":4096:8":
            raise RuntimeError("Pre-import CUBLAS workspace binding changed")
        torch.use_deterministic_algorithms(True, warn_only=False)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        # Same common controls as actual diagnosis384. Existing execution_context
        # still applies the declared per-role TF32 candidate option during work.
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
    actual = {"cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG"),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "deterministic_warn_only": torch.is_deterministic_algorithms_warn_only_enabled(),
        "deterministic_debug_mode": torch.get_deterministic_debug_mode(),
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "cudnn_benchmark": torch.backends.cudnn.benchmark,
        "matmul_tf32_before_role_context": torch.backends.cuda.matmul.allow_tf32,
        "cudnn_tf32_before_role_context": torch.backends.cudnn.allow_tf32,
        "float32_matmul_precision_before_role_context": torch.get_float32_matmul_precision()}
    semantic = {"requested": binding["requested"], "actual": actual,
                "preimport_binding_satisfied": not binding["torch_imported_before_binding"],
                "cuda_uninitialized_before_apply": not initialized}
    return {**binding, "actual": actual, "cuda_initialized_before_apply": initialized,
        "execution_sha256": canonical_sha(semantic), "scope": "both_reference_and_candidate",
        "tf32_override_policy": "existing_PerformanceOptions_execution_context_remains_explicit_per_role",
        "disabled_policy": "no_environment_or_torch_flags_changed_when_not_requested"}


def a_source_bindings():
    bound = source_bindings()
    for name in ("tools/model_v3/a_execution_runtime.py", "tools/model_v3/paired_a_acceptance.py",
                 "tools/model_v3/a_checkpoint_export.py", "current/phychem_mfm/training/checkpoint.py",
                 "current/phychem_mfm/phase1/v3_encoder_bridge.py", "current/phychem_mfm/phase1/v3_dev_panel.py",
                 "current/phychem_mfm/phase1/v3_dev_store.py", "current/phychem_mfm/phase1/v3_h0_runtime.py",
                 "current/phychem_mfm/phase1/v3_h0_packing.py",
                 "tools/model_v3/single_a_benchmark.py", "tools/model_v3/a_speed_report.py",
                 "tools/model_v3/s_input_stream.py", "current/phychem_mfm/model/v3_performance.py",
                 "current/phychem_mfm/training/v3_performance_acceptance.py",
                 "current/phychem_mfm/phase1/v3_padding.py"):
        path = REPO / name
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError("Required A runtime source missing: " + name)
        bound[name] = digest(path)
    return dict(sorted(bound.items()))


def bind_environment(args, uuid):
    import torch
    from private_runtime_storage import load_storage_bindings
    from runtime_monitor import gpu_observation
    if torch.cuda.device_count() != 1 or args.expected_gpu not in torch.cuda.get_device_name(0):
        raise RuntimeError("Actual GPU type/visibility differs")
    storage = load_storage_bindings()
    gpu = gpu_observation(uuid, own_pids=(os.getpid(),))
    if gpu["foreign_processes"]:
        raise RuntimeError("Selected GPU already has another compute process")
    result = {"gpu": gpu, "gpu_uuid": uuid, "gpu_name": torch.cuda.get_device_name(0),
            "gpu_total_bytes": int(torch.cuda.get_device_properties(0).total_memory),
            "torch_version": str(torch.__version__), "cuda_version": torch.version.cuda,
            "cudnn_version": torch.backends.cudnn.version(), "private_storage_bindings": storage,
            "tracking_mode": "offline", "original_lmdb_written": False, "downstream_data_read": False}
    if hasattr(args, "deterministic_controls_receipt"):
        result["deterministic_controls"] = args.deterministic_controls_receipt
    return result


def stream_for(args, reference, *, candidate=False):
    from s_input_stream import SInputStream
    return SInputStream(reference, seed=args.seed, input_kind=args.input, workers=args.workers,
        max_padded_cost=args.max_padded_cost, snapshot_sha256=args.shard_snapshot_sha256,
        atom_bucket_width=args.atom_bucket_width if candidate else None,
        exact_atom_sort=args.exact_atom_sort if candidate else False)


def corpus_receipt(corpus, record_index=None):
    import torch
    def encode(value):
        if isinstance(value, torch.Tensor):
            tensor = value.detach().cpu().contiguous()
            return {"dtype": str(tensor.dtype), "shape": list(tensor.shape),
                    "sha256": hashlib.sha256(tensor.reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()}
        if isinstance(value, dict):
            return {str(key): encode(item) for key, item in sorted(value.items())}
        if isinstance(value, (tuple, list)):
            return [encode(item) for item in value]
        if value is None or type(value) in (str, int, float, bool):
            return value
        raise TypeError("Unexpected encoder input receipt value: " + str(type(value)))
    atoms = list(map(int, corpus.native_atom_counts))
    molecule_ids = (list(corpus.record_keys) if record_index is None else
                    [record_index.ref(index).molecule_id for index in corpus.logical_indices])
    value = {"logical_indices": list(corpus.logical_indices), "record_keys": list(corpus.record_keys),
             "molecule_ids": molecule_ids, "molecule_presentations": len(set(molecule_ids)),
             "native_atom_counts": atoms, "base_records": len(atoms), "native_atoms": sum(atoms),
             "padded_pairs": 3 * len(atoms) * max(atoms)**2,
             "encoder_fields_sha256": canonical_sha(encode(corpus.encoder_batch.to_dict()))}
    return {**value, "receipt_sha256": canonical_sha(value)}


def append_json(path, row):
    with Path(path).open("a") as stream:
        stream.write(json.dumps(row, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def install_termination_handler():
    def stop(signum, _frame):
        raise RuntimeError("Owned supervisor requested A diagnostic termination: " + str(signum))
    signal.signal(signal.SIGTERM, stop)


def compiler_counters(enabled):
    if not enabled:
        return {"enabled": False}
    from torch._dynamo.utils import counters
    return {"enabled": True, "torch_dynamo_counters": {str(group): {
        str(name): int(count) for name, count in rows.items()} for group, rows in counters.items()},
        "semantics": "framework counters, including graph breaks/unique graphs; not GPU kernel time"}


def guard_resources(output, uuid):
    import torch
    from runtime_monitor import gpu_observation, owned_output_bytes, owned_process_observation
    process = owned_process_observation(os.getpid())
    gpu = gpu_observation(uuid, own_pids=[item["pid"] for item in process["processes"]])
    own = sum(item["used_memory_bytes"] or 0 for item in gpu["compute_processes"] if item["own"])
    cap = int(os.environ["MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES"])
    row = {"process_rss_sum_bytes": process["rss_sum_bytes"], "gpu_observation": gpu,
           "output_bytes": owned_output_bytes(output), "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
           "peak_reserved_bytes": torch.cuda.max_memory_reserved(),
           "foreign_gpu_risk_observed": bool(gpu["foreign_processes"])}
    if row["process_rss_sum_bytes"] > 56 * 1024**3 or row["output_bytes"] > cap - 32 * 1024**2:
        raise MemoryError("A diagnostic exceeded explicit RSS/output reserve")
    if max(own, row["peak_allocated_bytes"], row["peak_reserved_bytes"]) > .85 * gpu["total_bytes"]:
        raise MemoryError("A diagnostic exceeded85% of physical GPU capacity")
    return row
