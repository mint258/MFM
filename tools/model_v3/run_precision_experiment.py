"""Bound B-precision members and four-member numeric audit; no job submission.

Use an owned Slurm allocation and run_supervised.py for CUDA. Real data require
a separately pinned authority adapter; synthetic runs are harness tests only.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

REPO = Path(__file__).absolute().parents[2]


class PersistentOfflineTracker:
    """SDK commits plus a durable local mirror, with a fresh SDK per segment."""
    def __init__(self, run, path):
        self.run, self.history = run, path
        self.id, self.path, self.settings, self.disabled = run.id, run.path, run.settings, False

    @property
    def step(self):
        return self.run.step

    def log(self, row, *, step, commit):
        self.run.log(row, step=step, commit=commit)
        with self.history.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"step": step, "commit": commit, "row": row}, allow_nan=False) + "\n")
            stream.flush(); os.fsync(stream.fileno())


def collect_sources():
    names = [*sorted((REPO / "current/phychem_mfm").rglob("*.py")),
             *sorted((REPO / "current/configs/model_v3/performance").glob("b*.json")),
             *[REPO / "tools/model_v3" / name for name in ("run_precision_experiment.py", "a_execution_runtime.py",
                "profile_s_baseline.py", "runtime_monitor.py", "private_runtime_storage.py", "run_supervised.py")]]
    return {path.relative_to(REPO).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in names}


def load_adapter(path, expected):
    if path is None or not re.fullmatch(r"[0-9a-f]{64}", expected or ""):
        raise ValueError("Awaiting authoritative D5 adapter file and exact source SHA; no old S prefix fallback")
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Authority adapter source differs")
    spec = importlib.util.spec_from_file_location("model_v3_B_authority_" + expected[:16], path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest="command", required=True)
    report = commands.add_parser("report")
    report.add_argument("--members", nargs=4, type=Path, required=True)
    report.add_argument("--output", type=Path, required=True)
    member = commands.add_parser("member")
    member.add_argument("--input", choices=("synthetic", "authoritative_proxy"), default="authoritative_proxy")
    member.add_argument("--precision", choices=("fp32", "bf16"), required=True)
    member.add_argument("--seed", type=int, choices=(0, 1), required=True)
    member.add_argument("--output", type=Path, required=True)
    member.add_argument("--code-sha", required=True)
    member.add_argument("--prereg-sha", required=True)
    member.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    member.add_argument("--expected-gpu", choices=("3090", "4090", "5090"))
    member.add_argument("--updates", type=int, default=20000)
    member.add_argument("--validation-every", type=int)
    member.add_argument("--max-batch-samples", type=int)
    member.add_argument("--sample-budget", type=int)
    member.add_argument("--until-update", type=int)
    member.add_argument("--resume-checkpoint", type=Path)
    member.add_argument("--resume-output-root", type=Path)
    member.add_argument("--provider-adapter", type=Path)
    member.add_argument("--provider-adapter-sha256")
    member.add_argument("--deterministic-controls", action="store_true")
    member.add_argument("--wall-seconds", type=int, default=6900)
    return result


def run_member(args):
    if not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 16:
        raise ValueError("Owned Slurm allocation with>=16 CPUs required")
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (args.code_sha, args.prereg_sha)):
        raise ValueError("Full actual and public prereg code SHAs required")
    if args.output.exists() or args.output.resolve().is_relative_to(REPO.resolve()):
        raise ValueError("Fresh outside-Git segment output required")
    if (args.resume_checkpoint is None) != (args.resume_output_root is None):
        raise ValueError("Resume requires both original checkpoint and original output root")
    if not 60 <= args.wall_seconds <= 6900 or args.input == "authoritative_proxy" and (args.updates != 20000 or args.device != "cuda"):
        raise ValueError("Bounded segments and real20000-update CUDA members required")
    # A missing D5 hook fails before any model, SDK or output is created.
    if args.input == "authoritative_proxy" and args.provider_adapter is None:
        raise ValueError("Awaiting authoritative D5 TRAIN molecule/conformer and two-validation adapter; no proxy was constructed")
    from a_execution_runtime import prepare_deterministic_controls, apply_deterministic_controls
    preimport = prepare_deterministic_controls(args.deterministic_controls)
    import torch
    torch.set_num_threads(8); torch.set_num_interop_threads(1)
    deterministic = apply_deterministic_controls(preimport)
    import wandb
    from phychem_mfm.phase1.v3_precision_experiment import (PrecisionPlan, bind_authoritative_inputs,
        write_new_json, canonical_hash)
    from phychem_mfm.phase1.v3_precision_synthetic import synthetic_inputs, build_precision_member
    from runtime_monitor import owned_output_bytes, owned_process_observation
    uuid = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    locks = None
    if args.device == "cuda":
        if (not re.fullmatch(r"GPU-[a-fA-F0-9-]+", uuid) or torch.cuda.device_count() != 1
                or args.expected_gpu is None or args.expected_gpu not in torch.cuda.get_device_name(0)):
            raise ValueError("Exactly one declared physical GPU UUID/type required")
        import fcntl
        lock_root = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
        locks = (lock_root / (uuid + ".lock")).open("a")
        fcntl.flock(locks, fcntl.LOCK_EX | fcntl.LOCK_NB)
        from private_runtime_storage import load_storage_bindings
        storage = load_storage_bindings()
        from runtime_monitor import gpu_observation
        if gpu_observation(uuid, own_pids=(os.getpid(),))["foreign_processes"]:
            raise RuntimeError("Selected GPU was occupied; no member started")
    else:
        if torch.cuda.is_available():
            raise ValueError("CPU harness requires GPU visibility hidden")
        storage = {"scope": "CPU_synthetic_no_CUDA_cache"}
    batch = args.max_batch_samples if args.max_batch_samples is not None else (2 if args.input == "synthetic" else 512)
    interval = args.validation_every if args.validation_every is not None else (1 if args.input == "synthetic" else 500)
    if interval < 1:
        raise ValueError("Positive fixed validation interval required")
    grid = tuple(sorted(set([*range(0, args.updates + 1, interval), args.updates])))
    checkpoints = tuple(v for v in (10000, args.updates) if v <= args.updates)
    plan = PrecisionPlan(args.input, args.updates, grid, tuple(sorted(set(checkpoints))), batch,
                         args.sample_budget if args.sample_budget is not None else args.updates * batch)
    adapter_binding = {}
    if args.input == "synthetic":
        inputs = synthetic_inputs()
    else:
        adapter = load_adapter(args.provider_adapter, args.provider_adapter_sha256)
        source_pin = {**collect_sources(), "external_D5_adapter": args.provider_adapter_sha256}
        inputs = bind_authoritative_inputs(adapter, {"plan": asdict(plan), "roles": ["TRAIN", "VAL", "TRAIN_UNSEEN_CONFORMATION"],
            "input_scope": "authoritative_D5_proxy_only", "node_local_read_only": True,
            "execution_binding": {"actual_code_sha": args.code_sha, "prereg_sha": args.prereg_sha,
                "source_inventory_sha256": canonical_hash(source_pin), "gpu_uuid": uuid,
                "gpu_name": torch.cuda.get_device_name(0), "torch_version": str(torch.__version__),
                "cuda_runtime": torch.version.cuda, "logical_python": sys.executable,
                "deterministic_controls": deterministic}})
        adapter_binding = {"external_D5_adapter": args.provider_adapter_sha256}
    sources = {**collect_sources(), **adapter_binding}
    args.output.mkdir(mode=0o700, parents=True)
    os.environ.update(WANDB_MODE="offline", WANDB_CACHE_DIR=str(args.output / "cache"),
                      WANDB_DATA_DIR=str(args.output / "wandb_data"))
    cap = int(os.environ.get("MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES", str(2 * 1024**3)))
    if not 128 * 1024**2 <= cap <= 2 * 1024**3:
        raise ValueError("Original bounded output budget required")
    os.environ["MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES"] = str(cap)
    started, failure, cleanup, run, experiment, outcome = time.monotonic(), None, [], None, None, None
    def guard():
        if time.monotonic() - started > args.wall_seconds:
            raise TimeoutError("Bounded precision segment wall limit reached")
        if args.device == "cuda":
            from a_execution_runtime import guard_resources
            resource = guard_resources(args.output, uuid)
        else:
            process = owned_process_observation(os.getpid())
            resource = {"process_rss_sum_bytes": process["rss_sum_bytes"], "output_bytes": owned_output_bytes(args.output)}
            if resource["process_rss_sum_bytes"] > 56 * 1024**3 or resource["output_bytes"] > cap - 32 * 1024**2:
                raise MemoryError("CPU harness exceeded bounded RSS/output reserve")
        with (args.output / "resources.jsonl").open("a") as stream:
            stream.write(json.dumps(resource, allow_nan=False) + "\n")
    try:
        run = wandb.init(project="mfm_model_v3_development", mode="offline", dir=str(args.output),
            name=f"B_{args.precision}_seed{args.seed}_{os.environ['SLURM_JOB_ID']}",
            config={"plan": asdict(plan), "seed": args.seed, "precision": args.precision,
                "code_sha": args.code_sha, "prereg_sha": args.prereg_sha, "input_kind": args.input,
                "deterministic_controls": deterministic, "source_sha256": sources})
        tracker = PersistentOfflineTracker(run, args.output / "history.jsonl")
        experiment = build_precision_member(inputs, plan, seed=args.seed, precision=args.precision, tracker=tracker,
            source_bindings=sources, code_sha=args.code_sha, device=args.device,
            run_bindings={"prereg_sha": args.prereg_sha, "deterministic_controls": deterministic,
                          "gpu_uuid": uuid, "logical_python": sys.executable})
        write_new_json(args.output / "configuration.json", {"contract": experiment.contract, "tracker": experiment.trainer.tracker_identity,
            "job_id": os.environ["SLURM_JOB_ID"], "logical_python": sys.executable, "storage": storage, "gpu_uuid": uuid})
        if args.resume_checkpoint is not None:
            experiment.load(args.resume_checkpoint.absolute(), output_root=args.resume_output_root.absolute())
        guard()
        outcome = experiment.run(args.output, until_update=args.until_update, resource_guard=guard)
        actual_adapter = {"external_D5_adapter": hashlib.sha256(args.provider_adapter.read_bytes()).hexdigest()} if adapter_binding else {}
        if {**collect_sources(), **actual_adapter} != sources:
            raise RuntimeError("Runtime source bytes changed")
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        # No speculative emergency snapshot of a partially executed optimizer.
        # Recovery uses only previously published complete member checkpoints.
        raise
    finally:
        try:
            inputs.provider.close()
        except BaseException as exc:
            cleanup.append({"component": "provider", "type": type(exc).__name__, "message": str(exc)})
        if run is not None:
            try:
                run.finish(exit_code=0 if failure is None and not cleanup else 1)
            except BaseException as exc:
                cleanup.append({"component": "wandb", "type": type(exc).__name__, "message": str(exc)})
        final_bytes = None
        try:
            final_bytes = owned_output_bytes(args.output)
            if final_bytes > cap - 16 * 1024**2:
                raise MemoryError("Offline SDK finalization consumed output reserve")
        except BaseException as exc:
            cleanup.append({"component": "final_output_census", "type": type(exc).__name__, "message": str(exc)})
        write_new_json(args.output / "run_status.json", {"failure": failure, "cleanup_errors": cleanup,
            "elapsed_seconds": time.monotonic() - started, "online_sync": False,
            "status": "CHILD_COMPLETED_PENDING_OUTER_TERMINAL" if failure is None and not cleanup else "FAILED",
            "member_result_sha256": canonical_hash(outcome) if outcome else None,
            "tracker_id": run.id if run is not None else None,
            "output_bytes_before_status": final_bytes,
            "retained_complete_checkpoints_only": True, "scientific_acceptance": False})
        if locks is not None:
            locks.close()
        if cleanup and failure is None:
            raise RuntimeError("Precision cleanup failed; inspect run_status.json")


def main():
    args = parser().parse_args()
    if args.command == "member":
        return run_member(args)
    from phychem_mfm.phase1.v3_precision_experiment import compare_precision_members, write_new_json
    members = [json.loads(path.read_text()) for path in args.members]
    if args.output.resolve().is_relative_to(REPO.resolve()):
        raise ValueError("Fresh outside-Git audit output required")
    write_new_json(args.output, compare_precision_members(members))


if __name__ == "__main__":
    main()
