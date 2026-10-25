"""Opt-in 15-update native-S A06 diagnostic; never an A acceptance run.

Two original model paths run freely. An optimizer-only fused shadow borrows
each clipped reference gradient without feeding its parameters into a model.
All original inputs/outputs remain read-only. Root owns resource admission.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import sys
import time

CODE_SHA = "8ece64c685fe287d6863fbbe2f6f52006632a5cc"
PREREG_SHA = "61658a4c1f472de035601dbedc17809315774784"
GPU_UUID = "GPU-22e21021-e572-4562-fc51-cd8c83e74141"
UPDATES = 15
MAX_OUTPUT = 2 * 1024**3
SCALAR_FILE_CAP = 128 * 1024
REPLAY_FIELDS = ("optimizer_updates", "loss", "gradient_norm", "base_records",
                 "native_atoms", "consumed_base_records", "input_receipt_sha256", "valid_label_counts")
BIAS_RE = re.compile(r"backbone\.layers\.[0-5]\.attn\.dist_mlp\.2\.bias")


class ReplayMismatch(RuntimeError):
    pass


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def strict_json(raw):
    def illegal(value):
        raise ValueError("Nonfinite JSON literal: " + value)
    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=illegal)


def file_ref(path, *, limit=4 * 1024**2):
    path = Path(path).absolute()
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or path.is_symlink() or before.st_size > limit:
        raise ValueError("Bounded ordinary source/evidence file required: " + str(path))
    value = hashlib.sha256()
    total = 0
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            raise ValueError("Source changed while opening")
        for block in iter(lambda: stream.read(1 << 20), b""):
            total += len(block)
            if total > limit:
                raise ValueError("Source/evidence grew beyond bounded read limit")
            value.update(block)
    after = path.lstat()
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
        raise ValueError("Source changed while hashing")
    return {"path": str(path), "bytes": before.st_size, "sha256": value.hexdigest()}


def read_json(path, *, limit=SCALAR_FILE_CAP):
    file_ref(path, limit=limit)
    return strict_json(Path(path).read_bytes())


def write_new(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    if len(raw) > SCALAR_FILE_CAP:
        raise ValueError("Compact scalar artifact exceeds128KiB")
    with Path(path).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def append(path, value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    if len(raw) > SCALAR_FILE_CAP:
        raise ValueError("Scalar journal row exceeds128KiB")
    with Path(path).open("ab") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def read_original_history(path):
    file_ref(path)
    rows = {}
    with Path(path).open("rb") as stream:
        for line in stream:
            if len(line) > SCALAR_FILE_CAP or not line.endswith(b"\n"):
                raise ValueError("Oversized or uncommitted original history row")
            row = strict_json(line)
            update = row.get("optimizer_updates")
            if type(update) is not int or update in rows or update != len(rows) + 1 or update > 500:
                raise ValueError("Original history must have unique contiguous1..500 updates")
            if any(field not in row for field in REPLAY_FIELDS):
                raise ValueError("Original replay field missing")
            for key in ("loss", "gradient_norm"):
                if type(row[key]) not in (int, float) or not math.isfinite(row[key]):
                    raise ValueError("Original history loss/norm must be finite")
            if not re.fullmatch(r"[a-f0-9]{64}", row["input_receipt_sha256"]):
                raise ValueError("Original history input binding missing")
            rows[update] = row
    if set(rows) != set(range(1, 501)):
        raise ValueError("Complete original500-update evidence required")
    return rows


def replay_comparison(expected, actual):
    differences = {}
    for name in REPLAY_FIELDS:
        left, right = expected.get(name), actual.get(name)
        # No tolerance: causal interpretation is conditional on reproducing457.
        if type(left) is not type(right) or left != right:
            differences[name] = {"original": left, "diagnostic": right}
    return {"pass": not differences, "comparison": "exact_saved457_scalar_and_input_receipt", "differences": differences}


def validate_configuration(config):
    if (config["code_sha"] != CODE_SHA or config["prereg_sha"] != PREREG_SHA or config["seed"] != 0
            or config["input"] != "native_s" or config["trajectory_updates"] != 500
            or config["smoke"] is not False or config["gpu_uuid"] != GPU_UUID):
        raise ValueError("Exact native457 source/seed/GPU/scope required")
    if config["optimizer"] != {"lr": .0003, "betas": [.9, .95], "weight_decay": .01}:
        raise ValueError("Original457 AdamW recipe required")
    if config["gradient_clip_norm"] != 1. or config["dynamic_balancer"] is not False:
        raise ValueError("Original clipping/loss recipe required")
    if config["model"]["backbone"] != {"activation_checkpointing": True, "dim": 512, "dropout": 0.,
            "ff_mult": 2, "heads": 8, "layers": 6, "n_atom_types": 119, "radius": 8.,
            "use_dist_bias": True, "use_radius_mask": False}:
        raise ValueError("Original6x512 global-attention backbone required")
    ref, candidate = config["reference"], config["candidate"]
    expected = {**ref, "fused_adamw": True, "backbone_checkpointing": True}
    if (candidate != expected or ref["fused_adamw"] is not False or ref["precision"] != "fp32"
            or ref["tf32"] is not False or ref["compile_backbone"] is not False
            or ref["distance_pair_rows"] != 65536 or ref["distance_checkpointing"] is not True
            or ref["head_checkpointing"] is not True):
        raise ValueError("Only original fused option may differ; original checkpoints/precision retained")
    data = config["data_version"]
    if (data["sampler"]["max_padded_cost"] != 8_000_000 or data["loader"]["num_workers"] != 8
            or data["exact_atom_sort"] is not False or data["seed"] != 0):
        raise ValueError("Original457 sampler/loader required")
    controls = config["deterministic_controls"]
    if controls["requested"] is not True or controls["actual"]["deterministic_algorithms"] is not True:
        raise ValueError("Original457 strict deterministic controls required")


def verify_pins(pins, repo):
    refs = []
    if pins["schema"] != "A06_native_feedback_source_pins_v1" or pins["base_code_sha"] != CODE_SHA:
        raise ValueError("Wrong diagnostic source manifest")
    for entry in pins["files"]:
        got = file_ref(entry["path"], limit=entry.get("max_bytes", 4 * 1024**2))
        if got["bytes"] != entry["bytes"] or got["sha256"] != entry["sha256"]:
            raise ValueError("Pinned source/evidence bytes changed: " + entry["role"])
        refs.append({**got, "role": entry["role"]})
    roles = [entry["role"] for entry in pins["files"]]
    if len(set(roles)) != len(roles) or not {"script", "tests", "readme", "457_configuration", "457_reference_history",
            "457_candidate_history", "457_gate", "457_summary", "457_status", "485_summary", "485_script", "485_configuration"} <= set(roles):
        raise ValueError("Complete unique diagnostic and original evidence roles required")
    if Path(next(row["path"] for row in refs if row["role"] == "script")).resolve() != Path(__file__).resolve():
        raise ValueError("Executed script differs from pinned external source")
    for name, expected in pins["original_repo_source_sha256"].items():
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Relative repository source required")
        got = file_ref(repo / name)
        if got["sha256"] != expected:
            raise ValueError("Frozen8ece source changed: " + name)
        refs.append({**got, "role": "original_repo/" + name})
    return refs


def clone_shadow(torch, named_parameters):
    """Parameter-only clone: no random constructor, model or model forward."""
    return [(name, torch.nn.Parameter(parameter.detach().clone(), requires_grad=parameter.requires_grad))
            for name, parameter in named_parameters]


def gradient_hash(named_parameters):
    """Raw-byte hash online; one tensor at a time reaches host RAM, never disk."""
    import torch
    hasher = hashlib.sha256()
    none_names = []
    for name, parameter in named_parameters:
        value = parameter.grad
        descriptor = {"name": name, "none": value is None}
        if value is None:
            none_names.append(name)
        else:
            descriptor.update(dtype=str(value.dtype), shape=list(value.shape))
        raw = json.dumps(descriptor, sort_keys=True, separators=(",", ":")).encode()
        hasher.update(len(raw).to_bytes(8, "big"))
        hasher.update(raw)
        if value is not None:
            if not bool(torch.isfinite(value).all()):
                raise FloatingPointError("Nonfinite shared native gradient")
            hasher.update(value.detach().contiguous().reshape(-1).view(torch.uint8).cpu().numpy().tobytes())
    return {"sha256": hasher.hexdigest(), "none_count": len(none_names),
        "none_names_sha256": hashlib.sha256(json.dumps(none_names, separators=(",", ":")).encode()).hexdigest(),
        "parameter_tensors": len(named_parameters)}


@contextmanager
def borrow_reference_gradients(reference, shadow):
    if [name for name, _ in reference] != [name for name, _ in shadow]:
        raise ValueError("Shadow parameter order differs")
    for (_, left), (_, right) in zip(reference, shadow):
        if left.shape != right.shape or left.dtype != right.dtype or left.device != right.device:
            raise ValueError("Shadow parameter metadata differs")
        right.grad = left.grad
    try:
        before = gradient_hash(reference)
        if gradient_hash(shadow) != before:
            raise RuntimeError("Shadow received different native clipped gradients")
        receipt = {"before": before, "alias_same_tensor_and_none": all(left.grad is right.grad
                   for (_, left), (_, right) in zip(reference, shadow))}
        yield receipt
        receipt["after"] = gradient_hash(shadow)
        receipt["reference_after"] = gradient_hash(reference)
        if receipt["after"] != before or receipt["reference_after"] != before:
            raise RuntimeError("Optimizer changed borrowed native clipped gradient bytes/None pattern")
        receipt["unchanged"] = True
    finally:
        for _, parameter in shadow:
            parameter.grad = None


def compact_comparison(torch, reference, candidate, *, tolerance):
    """All parameters audited, original fp64 L2/max(norm,1e-12) retained."""
    if set(reference) != set(candidate):
        raise ValueError("Comparison parameter set differs")
    rows, global_ref2, global_error2 = [], 0., 0.
    for name in sorted(reference):
        left, right = reference[name], candidate[name]
        if left is None or right is None:
            rows.append({"name": name, "pass": None if tolerance is None else left is None and right is None,
                         "disabled": left is None and right is None, "relative_l2": None})
            continue
        if left.shape != right.shape:
            raise ValueError("Comparison tensor shape differs")
        if not bool(torch.isfinite(left).all() and torch.isfinite(right).all()):
            raise FloatingPointError("Nonfinite native diagnostic tensor")
        x, y = left.detach().double(), right.detach().double()
        difference = y - x
        norm = torch.linalg.vector_norm(x)
        error = torch.linalg.vector_norm(difference)
        relative = float(error / norm.clamp_min(1e-12))
        reference_l2, error_l2 = float(norm), float(error)
        global_ref2 += reference_l2**2
        global_error2 += error_l2**2
        rows.append({"name": name, "relative_l2": relative, "reference_l2": reference_l2,
            "difference_l2": error_l2, "max_absolute": float(difference.abs().max()) if difference.numel() else 0.,
            "exact_equal": bool(torch.equal(left, right)), "pass": None if tolerance is None else relative <= tolerance})
    numeric = [row for row in rows if row["relative_l2"] is not None]
    return {"pass": None if tolerance is None else all(row["pass"] for row in rows), "tolerance": tolerance,
        "denominator": "per_parameter_L2_max_reference_norm_1e-12", "parameters_audited": len(rows),
        "disabled_both": sum(row.get("disabled", False) for row in rows),
        "failed_parameters": None if tolerance is None else sum(not row["pass"] for row in rows),
        "max_absolute": max((row["max_absolute"] for row in numeric), default=0.),
        "max_relative_l2": max((row["relative_l2"] for row in numeric), default=0.),
        "top5_relative_l2": sorted(numeric, key=lambda row: (-row["relative_l2"], row["name"]))[:5],
        "missing_gradient_mismatches": [row["name"] for row in rows if row["relative_l2"] is None and not row.get("disabled", False)],
        "fixed_six_distance_biases": [row for row in rows if BIAS_RE.fullmatch(row["name"])],
        "global_difference_l2_diagnostic_only": math.sqrt(global_error2),
        "global_relative_l2_diagnostic_only": math.sqrt(global_error2) / max(math.sqrt(global_ref2), 1e-12)}


@contextmanager
def dispatch_observer():
    import torch.optim.adam as adam
    counts, active = Counter(), [None]
    originals = {name: getattr(adam, name) for name in ("_multi_tensor_adam", "_fused_adam", "_single_tensor_adam")}
    def wrap(name, implementation):
        def call(*args, **kwargs):
            counts[(active[0], name)] += 1
            return implementation(*args, **kwargs)
        return call
    for name, implementation in originals.items():
        setattr(adam, name, wrap(name, implementation))
    try:
        yield counts, active
    finally:
        for name, implementation in originals.items():
            setattr(adam, name, implementation)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--repo", type=Path, required=True)
    result.add_argument("--source-pins", type=Path, default=Path(__file__).with_name("source_pins_v1.json"))
    result.add_argument("--pins-sha256", required=True)
    result.add_argument("--code-sha", required=True, choices=(CODE_SHA,))
    result.add_argument("--expected-gpu", choices=("5090",), default="5090")
    result.add_argument("--updates", type=int, choices=(UPDATES,), default=UPDATES)
    result.add_argument("--wall-seconds", type=int, default=840)
    result.add_argument("--output", type=Path, required=True)
    return result


def run(args):
    if "torch" in sys.modules:
        raise RuntimeError("Fresh process required: bind CUBLAS before importing Torch")
    if not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 16:
        raise RuntimeError("Root-admitted>=16CPU single-GPU Slurm allocation required")
    if not 60 <= args.wall_seconds <= 6900 or args.updates != UPDATES:
        raise ValueError("Only bounded15-update diagnostic is implemented; no500 gate or resume")
    if file_ref(args.source_pins)["sha256"] != args.pins_sha256:
        raise ValueError("External diagnostic source-manifest pin differs")
    pins = read_json(args.source_pins)
    before = verify_pins(pins, args.repo)
    roles = {entry["role"]: Path(entry["path"]) for entry in pins["files"]}
    original = read_json(roles["457_configuration"])
    validate_configuration(original)
    if original["source_sha256"] != pins["original_repo_source_sha256"]:
        raise ValueError("Original full source-set binding differs")
    histories = {role: read_original_history(roles["457_" + role + "_history"])
                 for role in ("reference", "candidate")}
    old_gate = read_json(roles["457_gate"])
    if (old_gate["pass"] is not False or next(row["step"] for row in old_gate["results"] if not row["pass"]) != 14
            or read_json(roles["457_summary"])["full_A_numeric_acceptance"] is not False):
        raise ValueError("Original failed A06 evidence differs")
    if args.output.exists() or args.output.resolve().is_relative_to(args.repo.resolve()):
        raise FileExistsError("Fresh outside-Git output required")
    if os.environ.get("CUDA_VISIBLE_DEVICES") != GPU_UUID:
        raise RuntimeError("Same physical5090 UUID as457 required")
    cap = int(os.environ.get("MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES", "0"))
    if not 128 * 1024**2 <= cap <= MAX_OUTPUT:
        raise ValueError("Original bounded supervisor output cap required")
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(args.repo / "current"), str(args.repo / "tools/model_v3"),
                   str(args.repo / "workflows/sprime_s/scripts")]
    from a_execution_runtime import prepare_deterministic_controls
    binding = prepare_deterministic_controls(True)
    import torch
    from a_execution_runtime import (apply_deterministic_controls, bind_environment, guard_resources,
        install_termination_handler, corpus_receipt)
    from s_model_memory_v1 import build_memory_bounded_model
    from s_input_stream import SInputStream
    from phychem_mfm.model.v3_performance import (PerformanceOptions, build_performance_model,
        performance_forward_pretrain, execution_context, make_adamw)
    from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule, Phase1LossPolicy
    from phychem_mfm.supervision import SupervisionConfig
    from phychem_mfm.training.losses import LossWeights
    from phychem_mfm.training.v3_performance_acceptance import trajectory_report
    args.deterministic_controls_receipt = apply_deterministic_controls(binding)
    if args.deterministic_controls_receipt["actual"] != original["deterministic_controls"]["actual"]:
        raise RuntimeError("Original457 actual deterministic/TF32 controls differ")
    torch.set_num_threads(8)
    torch.set_num_interop_threads(1)
    install_termination_handler()
    import fcntl
    lock_root = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
    with (lock_root / (GPU_UUID + ".lock")).open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        environment = bind_environment(args, GPU_UUID)
        for name in ("torch_version", "cuda_version", "cudnn_version"):
            if environment[name] != original[name]:
                raise RuntimeError("Original457 runtime differs: " + name)
        if environment["gpu"]["driver_version"] != original["gpu"]["driver_version"]:
            raise RuntimeError("Original457 NVIDIA driver differs")
        if (sys.version != original["python_version"] or str(Path(sys.executable).absolute()) != original["logical_python"]
                or socket.gethostname() != original["node"]):
            raise RuntimeError("Original457 Python/node binding differs")
        args.output.mkdir(parents=True, mode=0o700)
        started = time.monotonic()
        stream, tracker, cleanup, failure = None, None, [], None
        completed, sdk_rows, status, foreign_risk = 0, 0, "FAILED", False
        replay_rows, trajectory, parameter_snapshots = [], {"reference": {}, "candidate": {}}, []
        def guard(phase):
            nonlocal foreign_risk
            if time.monotonic() - started > args.wall_seconds:
                raise TimeoutError("Native feedback diagnostic wall budget reached")
            observation = guard_resources(args.output, GPU_UUID)
            foreign_risk = foreign_risk or observation["foreign_gpu_risk_observed"]
            if observation["process_rss_sum_bytes"] > 28 * 1024**3:
                raise MemoryError("Native feedback diagnostic exceeded28GiB RSS")
            append(args.output / "resources.jsonl", {"phase": phase, **observation})
            return observation
        def log(row, step):
            nonlocal sdk_rows
            if step != sdk_rows:
                raise ValueError("One strictly increasing explicit SDK step per committed scalar row required")
            tracker.log(row, step=step, commit=True)
            append(args.output / "history.jsonl", {"step": step, "row": row})
            sdk_rows += 1
        try:
            os.environ.update(WANDB_MODE="offline", WANDB_CACHE_DIR=str(args.output / "cache"),
                              WANDB_DATA_DIR=str(args.output / "wandb_data"))
            import wandb
            import torch.optim.adam as adam
            import torch.optim.adamw as adamw
            optimizer_sources = [file_ref(module.__file__) for module in (adam, adamw)]
            if {item["path"]: item["sha256"] for item in optimizer_sources} != read_json(roles["485_configuration"])["optimizer_source"]:
                raise RuntimeError("Actual optimizer Python sources differ from485 environment")
            metadata = {"schema": "A06_native_gradient_feedback_diagnostic_v1", "scope": "15_native_updates_diagnostic_only",
                "code_sha": CODE_SHA, "prereg_sha": PREREG_SHA, "seed": 0, "updates": UPDATES,
                "source_pins": file_ref(args.source_pins), "original_evidence_and_sources": before,
                "original_configuration_sha256": file_ref(roles["457_configuration"])["sha256"],
                "original_options": {"reference": original["reference"], "candidate": original["candidate"]},
                "model": original["model"], "optimizer": original["optimizer"], "environment": environment,
                "optimizer_sources": optimizer_sources,
                "shadow": "parameter-only clone; independent parameters/moments; exact shared clipped reference gradient values/None; no model/forward/RNG/feedback",
                "extra_live_storage": {"parameters_bytes_fp32": 22352859 * 4, "adam_two_moments_bytes_fp32_upper": 22352859 * 8,
                    "two_raw_gradient_snapshots_bytes_fp32_upper": 22352859 * 8, "shadow_gradient_extra_storage_bytes": 0,
                    "semantics": "upper bounds over all parameters; lazy Adam states exist only for grad-enabled parameters; allocator/temporaries measured separately"},
                "host_gradient_hash": "one tensor at a time; temporary CPU raw bytes only; no gradient file",
                "timing_kind": "instrumented_three_path_diagnostic_not_standalone_speed",
                "fixed20_batch_gate_rerun": False, "original_fixed20_pass_evidence_preserved": True,
                "scientific_acceptance": False, "A06_original_gate_status": "FAILED_UNCHANGED", "resume_supported": False,
                "output_budget_bytes": cap, "wall_seconds": args.wall_seconds, "replay_policy": "exact457 input/loss/preclip_norm/counts each step or REPLAY_MISMATCH",
                "interpretation_limit": "shadow isolates optimizer evolution under exogenous reference gradients; free-minus-shadow includes gradient feedback and weight-decay interactions; no additive causal percentages"}
            tracker = wandb.init(project="mfm_model_v3_development", mode="offline", dir=str(args.output),
                name="A06_native_feedback_" + os.environ["SLURM_JOB_ID"], config=metadata)
            write_new(args.output / "configuration.json", metadata)
            log({"event": "START", "diagnostic_only": True, "requested_native_updates": UPDATES,
                 "scientific_acceptance": False}, 0)
            torch.manual_seed(0)
            reference_model = build_memory_bounded_model(original["model"]).cuda().train()
            torch.manual_seed(0)
            free_model = build_performance_model(original["model"], PerformanceOptions(**original["candidate"])).cuda().train()
            left_state, right_state = reference_model.state_dict(), free_model.state_dict()
            if set(left_state) != set(right_state) or not all(torch.equal(left_state[key], right_state[key]) for key in left_state):
                raise RuntimeError("Original model initial parameters/buffers/state keys differ")
            del left_state, right_state
            named = {"reference": list(reference_model.named_parameters()), "candidate": list(free_model.named_parameters())}
            if [name for name, _ in named["reference"]] != [name for name, _ in named["candidate"]]:
                raise RuntimeError("Original parameter keys differ")
            if sum(parameter.numel() for _, parameter in named["reference"]) != 22352859:
                raise RuntimeError("Original22,352,859 parameter layout required")
            rng = torch.get_rng_state().clone(), torch.cuda.get_rng_state().clone()
            named["shadow"] = clone_shadow(torch, named["reference"])
            if not torch.equal(torch.get_rng_state(), rng[0]) or not torch.equal(torch.cuda.get_rng_state(), rng[1]):
                raise RuntimeError("Parameter-only shadow changed original RNG")
            for role in ("candidate", "shadow"):
                if not all(torch.equal(a, b) for (_, a), (_, b) in zip(named["reference"], named[role])):
                    raise RuntimeError("Initial parameter bits differ")
            if any(p.dtype != torch.float32 or p.device.type != "cuda" for pairs in named.values() for _, p in pairs):
                raise RuntimeError("ActualCUDA fp32 parameters required in all3 paths")
            models = {"reference": reference_model, "candidate": free_model}
            options = {role: PerformanceOptions(**original[role]) for role in models}
            optimizers = {"reference": torch.optim.AdamW(reference_model.parameters(), **original["optimizer"]),
                "candidate": make_adamw(free_model, original["optimizer"], options["candidate"]),
                "shadow": torch.optim.AdamW([p for _, p in named["shadow"]], **original["optimizer"], fused=True)}
            reference_config = read_json(original["reference_configuration"]["path"])
            stream = SInputStream(reference_config, seed=0, input_kind="native_s", workers=8,
                max_padded_cost=8_000_000, snapshot_sha256=original["original_shard_snapshot_prejob_sha256"])
            # Snapshot inode/device observations legitimately differ by host/time; semantic pins must not.
            for key in ("manifest_sha256", "native_transport", "sampler", "loader", "sampler_contract_sha256", "exact_atom_sort", "seed"):
                if stream.bindings[key] != original["data_version"][key]:
                    raise ReplayMismatch("Native original stream binding differs: " + key)
            write_new(args.output / "data_binding.json", stream.bindings)
            weights = LossWeights.from_mapping(original["loss_weights"])
            policy, supervision = Phase1LossPolicy.from_mapping(original["loss_policy"]), SupervisionConfig.from_variant("S")
            consumed = 0
            guard("models_and_shadow_parameters_created")
            with dispatch_observer() as (dispatch, active):
                for update in range(1, UPDATES + 1):
                    guard("before_native_update_" + str(update))
                    corpus = stream.next()
                    receipt = corpus_receipt(corpus, stream.index)
                    batch = corpus.encoder_batch.to("cuda", non_blocking=True)
                    raw_gradients, native_rows = {}, {}
                    order = ("reference", "candidate") if update % 2 else ("candidate", "reference")
                    dispatch_before = dict(dispatch)
                    for role in order:
                        optimizers[role].zero_grad(set_to_none=True)
                        with execution_context(options[role]):
                            outputs = performance_forward_pretrain(models[role], batch, supervision.objectives)
                            loss = compute_phase1_loss(outputs, batch, None, supervision, weights,
                                                      Phase1JointSchedule(), update - 1, policy=policy)
                            if not bool(torch.isfinite(loss.total)):
                                raise FloatingPointError("Nonfinite native loss")
                            loss.total.backward()
                            raw_gradients[role] = {name: None if p.grad is None else p.grad.detach().clone() for name, p in named[role]}
                            norm = torch.nn.utils.clip_grad_norm_(models[role].parameters(), 1.)
                            if not bool(torch.isfinite(norm)):
                                raise FloatingPointError("Nonfinite native preclip norm")
                            active[0] = role
                            optimizers[role].step()
                            active[0] = None
                        torch.cuda.synchronize()
                        native_rows[role] = {"optimizer_updates": update, "loss": float(loss.total.detach().cpu()),
                            "gradient_norm": float(norm.detach().cpu()), "base_records": len(corpus.logical_indices),
                            "native_atoms": sum(corpus.native_atom_counts), "consumed_base_records": consumed + len(corpus.logical_indices),
                            "input_receipt_sha256": receipt["receipt_sha256"], "valid_label_counts": dict(loss.counts)}
                        trajectory[role][update] = native_rows[role]["loss"]
                        append(args.output / (role + "_history.jsonl"), native_rows[role])
                        del outputs, loss
                        guard("after_" + role + "_update_" + str(update))
                    replay = {role: replay_comparison(histories[role][update], native_rows[role]) for role in models}
                    replay_rows.append({"update": update, **replay})
                    if not all(row["pass"] for row in replay.values()):
                        write_new(args.output / "replay_mismatch.json", replay_rows[-1])
                        raise ReplayMismatch("457 reference/free input/loss/norm/counts failed exact reproduction at update" + str(update))
                    with borrow_reference_gradients(named["reference"], named["shadow"]) as shared:
                        active[0] = "shadow"
                        optimizers["shadow"].step()
                        active[0] = None
                        torch.cuda.synchronize()
                    delta = {role + "/" + fn: count - dispatch_before.get((role, fn), 0)
                             for (role, fn), count in dispatch.items() if count != dispatch_before.get((role, fn), 0)}
                    if delta != {"reference/_multi_tensor_adam": 1, "candidate/_fused_adam": 1, "shadow/_fused_adam": 1}:
                        raise RuntimeError("ActualCUDA foreach/fused dispatch differs: " + str(delta))
                    gradients = compact_comparison(torch, raw_gradients["reference"], raw_gradients["candidate"], tolerance=1e-4)
                    del raw_gradients
                    comparisons = {}
                    for role, left_role, right_role in (("free_vs_reference", "reference", "candidate"),
                            ("shadow_vs_reference", "reference", "shadow"), ("free_vs_shadow", "shadow", "candidate")):
                        comparisons[role] = {"parameters": compact_comparison(torch,
                            dict(named[left_role]), dict(named[right_role]), tolerance=None)}
                        for key in ("exp_avg", "exp_avg_sq", "step"):
                            maps = [{name: (None if optimizers[r].state[p].get(key) is None else
                                     optimizers[r].state[p][key].to("cuda") if key == "step" else optimizers[r].state[p][key])
                                     for name, p in named[r]} for r in (left_role, right_role)]
                            comparisons[role][key] = compact_comparison(torch, *maps, tolerance=None)
                    step_representation = {}
                    for role, pairs in named.items():
                        name, parameter = next((name, p) for name, p in pairs if "step" in optimizers[role].state[p])
                        scalar = optimizers[role].state[parameter]["step"]
                        step_representation[role] = {"representative_parameter": name, "value": float(scalar),
                                                     "device": str(scalar.device), "dtype": str(scalar.dtype)}
                    bias_scalars = {role: {name: {"first_parameter_scalar": float(p.flatten()[0]),
                        "first_clipped_gradient_scalar": None if p.grad is None else float(p.grad.flatten()[0])}
                        for name, p in pairs if BIAS_RE.fullmatch(name)} for role, pairs in named.items()}
                    point_gate = trajectory_report({1: native_rows["reference"]["loss"]},
                        {1: native_rows["candidate"]["loss"]}, expected_updates=1)["results"][0]
                    # Diagnostic point check only; helper's historical500 label is not used as a15-step gate.
                    detail = {"update": update, "execution_order": [*order, "shadow"], "replay": replay,
                        "original_trajectory_threshold_point_check": {**point_gate, "step": update, "threshold": .001},
                        "raw_native_gradient_comparison": gradients, "comparisons": comparisons,
                        "shared_clipped_reference_gradient": shared, "dispatch": delta,
                        "step_state_representation": step_representation,
                        "fixed_six_distance_bias_scalars": bias_scalars, "scientific_acceptance": False}
                    write_new(args.output / f"update_{update:02d}.json", detail)
                    stream.commit(corpus)
                    consumed += len(corpus.logical_indices)
                    append(args.output / "consumption.jsonl", {"update": update, "input_receipt_sha256": receipt["receipt_sha256"],
                        "base_records": len(corpus.logical_indices), "committed_stream": stream.state_dict()})
                    row = {"event": "NATIVE_GRADIENT_FEEDBACK_UPDATE", "native_updates": update,
                        "reference/loss": native_rows["reference"]["loss"], "free_fused/loss": native_rows["candidate"]["loss"],
                        "reference/preclip_gradient_norm": native_rows["reference"]["gradient_norm"],
                        "free_fused/preclip_gradient_norm": native_rows["candidate"]["gradient_norm"],
                        "trajectory/relative_difference": point_gate["relative_difference"], "trajectory/original_point_pass": point_gate["pass"],
                        "replay/exact457": True, "shadow/borrowed_gradients_unchanged": shared["unchanged"],
                        "gradient/free_vs_reference_max_parameter_relative_l2": gradients["max_relative_l2"],
                        "consumed_base_records": consumed, "scientific_acceptance": False}
                    for role, values in comparisons.items():
                        for key, value in values.items():
                            row[role + "/" + key + "/max_parameter_relative_l2"] = value["max_relative_l2"]
                            row[role + "/" + key + "/global_difference_l2_diagnostic_only"] = value["global_difference_l2_diagnostic_only"]
                    log(row, update)
                    completed = update
                    parameter_snapshots.append({"update": update, "loss_relative_difference": point_gate["relative_difference"],
                        "original_point_pass": point_gate["pass"], "raw_gradient_max_relative_l2": gradients["max_relative_l2"],
                        **{role: {key: value["global_difference_l2_diagnostic_only"] for key, value in values.items()}
                           for role, values in comparisons.items()}})
                    guard("after_shadow_moments_and_audits_update_" + str(update))
                    del batch, corpus
            first_failure = next((row["update"] for row in parameter_snapshots if not row["original_point_pass"]), None)
            if first_failure != 14:
                raise ReplayMismatch("Exact replay did not retain original first trajectory failure14")
            status = "DIAGNOSTIC_COMPLETED_PENDING_SDK_AND_OUTER_TERMINAL"
            write_new(args.output / "summary.json", {"status": status, "native_updates": completed,
                "consumed_base_records": consumed, "all_replay_points_exact457": True, "first_original_threshold_failure": first_failure,
                "points": parameter_snapshots, "shadow_has_model_forward": False, "scientific_acceptance": False,
                "foreign_gpu_risk_observed": foreign_risk,
                "A06_original_gate_status": "FAILED_UNCHANGED", "attribution": "EVIDENCE_ONLY_NO_AUTOMATIC_CAUSAL_CONCLUSION",
                "fixed20_rerun": False, "full500_rerun": False, "resume_supported": False})
            log({"event": "COMPLETE", "native_updates": completed, "first_original_threshold_failure": first_failure,
                "all_replay_points_exact457": True, "scientific_acceptance": False}, UPDATES + 1)
        except BaseException as exc:
            failure = {"type": type(exc).__name__, "message": str(exc)}
            status = "REPLAY_MISMATCH" if isinstance(exc, ReplayMismatch) else "FAILED"
            raise
        finally:
            for name, close in (("native_stream", None if stream is None else stream.close),
                                ("offline_SDK", None if tracker is None else lambda: tracker.finish(exit_code=1 if failure else 0))):
                if close is not None:
                    try:
                        close()
                    except BaseException as exc:
                        cleanup.append({"component": name, "type": type(exc).__name__, "message": str(exc)})
            try:
                after = verify_pins(pins, args.repo)
                if after != before or file_ref(args.source_pins)["sha256"] != args.pins_sha256:
                    raise ValueError("Frozen source/evidence changed during diagnostic")
                write_new(args.output / "source_closure.json", {"unchanged": True, "before": before, "after": after,
                    "source_pins_sha256": args.pins_sha256})
            except BaseException as exc:
                cleanup.append({"component": "source_closure", "type": type(exc).__name__, "message": str(exc)})
            try:
                guard("after_input_SDK_and_source_closure")
            except BaseException as exc:
                cleanup.append({"component": "final_resource_guard", "type": type(exc).__name__, "message": str(exc)})
            write_new(args.output / "run_status.json", {"status": "CLEANUP_FAILED" if cleanup and not failure else status,
                "failure": failure, "cleanup_errors": cleanup, "completed_native_updates": completed,
                "acknowledged_history_commits": sdk_rows, "expected_success_HISTORY_rows": UPDATES + 2,
                "SDK_native_verification": "PENDING_INDEPENDENT_READBACK_not_inferred_from_mirror",
                "sdk_run_id": None if tracker is None else tracker.id, "offline_unsynced": True,
                "input_cleanup": None if stream is None else getattr(stream, "last_cleanup", None),
                "elapsed_seconds": time.monotonic() - started, "scientific_acceptance": False,
                "foreign_gpu_risk_observed": foreign_risk,
                "resume_supported": False, "code_sha": CODE_SHA, "job_id": os.environ["SLURM_JOB_ID"]})
            if cleanup and failure is None:
                raise RuntimeError("Diagnostic cleanup failed; first cleanup error: " + str(cleanup[0]))
    return 0


if __name__ == "__main__":
    sys.exit(run(parser().parse_args()))
