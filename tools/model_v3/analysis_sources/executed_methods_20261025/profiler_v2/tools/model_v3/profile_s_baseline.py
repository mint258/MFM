"""Bounded S profiler; real TRAIN input and synthetic smoke runs are distinct.

Run only inside a root-reviewed Slurm allocation. The default is the actual old
runner's tiled distance implementation, resized to 6x512 and using the A4 head.
No frozen runner, data, manifest, normalization or checkpoint is modified.
"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
import copy
import gc
import hashlib
from importlib.machinery import ModuleSpec
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
from types import ModuleType

REPO = Path(__file__).absolute().parents[2]
sys.path.insert(0, str(REPO / "current"))
sys.path.insert(0, str(REPO / "workflows/sprime_s/scripts"))
PUBLIC_PREREG = "3441b280bc34431bf8e7596465af28be073644b6"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def query(argv):
    return subprocess.check_output(argv, stdin=subprocess.DEVNULL, text=True, timeout=20)


def synthetic_corpus(seed, ordinal):
    import torch
    from torch_geometric.data import Batch, Data
    from phychem_mfm.phase1.full_corpus_loader import CorpusBatch
    rng = torch.Generator().manual_seed(seed + ordinal)
    views = []
    counts = (8, 12, 16)
    for n in counts:
        x = torch.full((n, 1), 5, dtype=torch.long)
        pos = torch.randn(n, 3, generator=rng)
        edges = torch.stack((torch.arange(n - 1), torch.arange(1, n)))
        for view in range(3):
            changed = torch.zeros(n, 1, dtype=torch.bool)
            source_x = x.clone()
            source_pos = pos.clone()
            if view == 1:
                source_pos += .1 * torch.randn(n, 3, generator=rng)
            if view == 2:
                source_x[0] = 6
                changed[0] = True
            views.append(Data(x=source_x, pos=source_pos, target_x=x.clone(), target_pos=pos.clone(),
                              sample_type_id=torch.tensor([view]), element_corrupt_mask=changed,
                              rdkit_bond_index=edges.clone(), rdkit_bond_order=torch.ones(n - 1, dtype=torch.long),
                              rdkit_bond_status="ok"))
    return CorpusBatch(Batch.from_data_list(views), tuple(range(3)), tuple(range(3)),
                       tuple(f"synthetic-{ordinal}-{i}" for i in range(3)), counts)


EXPLICIT_SOURCES = ("tools/model_v3/profile_s_baseline.py", "current/phychem_mfm/model/v3_profiling.py",
             "tools/model_v3/profile_sampling.py",
             "current/phychem_mfm/model/v3_profiler_attribution.py", "tools/model_v3/analyze_trace_v3.py",
             "tools/model_v3/native_runtime_bindings.py", "tools/model_v3/private_runtime_storage.py",
             "tools/model_v3/run_supervised.py",
             "tools/model_v3/runtime_monitor.py", "current/phychem_mfm/factory.py",
             "current/phychem_mfm/model/backbone.py", "current/phychem_mfm/phase1/full_corpus_loader.py",
             "current/phychem_mfm/model/shared.py", "current/phychem_mfm/model/attention.py",
             "current/phychem_mfm/model/heads.py", "current/phychem_mfm/phase1/objectives.py",
             "workflows/sprime_s/scripts/prepare.py",
             "workflows/sprime_s/scripts/s_loader_recovery_v1.py",
             "workflows/sprime_s/scripts/s_loader_recovery_v2.py",
             "workflows/sprime_s/scripts/s_model_memory_v1.py",
             "workflows/sprime_s/scripts/s_native_adapter_v1.py",
             "workflows/sprime_s/scripts/s_native_adapter_v2.py")


def source_bindings():
    bindings = {}
    for name in EXPLICIT_SOURCES:
        path = REPO / name
        if path.is_symlink() or not path.is_file():
            raise FileNotFoundError("Required ordinary repository source is missing: " + name)
        bindings[name] = digest(path)
    real_root = REPO.resolve(strict=True)
    for module in tuple(sys.modules.values()):
        if not isinstance(module, ModuleType):
            continue
        # Some Torch modules synthesize arbitrary attributes via __getattr__.
        # Consult the real namespace/spec, never dynamic getattr or cwd-based
        # absolutization of a third-party relative/pseudo source name.
        namespace = vars(module)
        spec = namespace.get("__spec__")
        origins = (spec.origin if isinstance(spec, ModuleSpec) else None, namespace.get("__file__"))
        for source in origins:
            if not isinstance(source, str):
                continue
            try:
                path = Path(source)
                if not path.is_absolute() or ".." in path.parts or path.suffix != ".py" or not path.is_relative_to(REPO):
                    continue
                if path.is_symlink() or not path.is_file() or not path.resolve(strict=True).is_relative_to(real_root):
                    continue
            except (OSError, ValueError):
                continue
            name = str(path.relative_to(REPO))
            if name not in bindings:
                bindings[name] = digest(path)
            break
    return dict(sorted(bindings.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", choices=("native_s", "synthetic"), default="native_s")
    parser.add_argument("--reference-config", type=Path,
                        default=REPO / "workflows/sprime_s/formal_s/B1_seed0_v2.json")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--prereg-sha", default=PUBLIC_PREREG)
    parser.add_argument("--expected-gpu", choices=("3090", "4090", "5090"), required=True)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=2)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--shard-snapshot-sha256")
    parser.add_argument("--wall-seconds", type=int, default=1800)
    parser.add_argument("--distance", choices=("tiled", "dense"), default="tiled")
    parser.add_argument("--max-padded-cost", type=int, default=8_000_000)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--output-budget-bytes", type=int, default=2 * 1024**3)
    parser.add_argument("--rss-limit-bytes", type=int, default=56 * 1024**3)
    args = parser.parse_args()
    if "MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES" in os.environ:
        args.output_budget_bytes = min(args.output_budget_bytes, int(os.environ["MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES"]))
    if not (1 <= args.steps <= 20 and 0 <= args.warmup <= 4 and 60 <= args.wall_seconds <= 3600
            and 0 <= args.workers <= 16 and 1 <= args.max_padded_cost <= 8_000_000):
        raise ValueError("Bounded profiling steps, workers, padded cost and wall cap required")
    if not (32 * 1024**2 <= args.output_budget_bytes <= 2 * 1024**3 and 0 < args.rss_limit_bytes <= 56 * 1024**3):
        raise ValueError("Bounded complete output and host RSS budgets required")
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (args.code_sha, args.prereg_sha)):
        raise ValueError("Full actual code and public preregistration commits required")
    if not os.environ.get("SLURM_JOB_ID") or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 16:
        raise RuntimeError("An owned Slurm allocation with at least 16 CPUs is required")
    if args.output.resolve().is_relative_to(REPO.resolve()) or args.output.exists():
        raise ValueError("Use a fresh external output directory; preserve all earlier artifacts")
    args.output.mkdir(parents=True)
    def stop_owned_run(signum, _frame):
        raise RuntimeError(f"Owned supervisor requested termination via signal {signum}")
    signal.signal(signal.SIGTERM, stop_owned_run)
    print(json.dumps({"status": "IMPORTING", "input": args.input, "job_id": os.environ["SLURM_JOB_ID"]}), flush=True)
    cfg = json.loads(args.reference_config.read_text())
    a4 = json.loads((REPO / "workflows/s_denoise/configs/A4_seed0_v3.json").read_text())
    model_cfg = copy.deepcopy(a4["model"])
    model_cfg["backbone"].update(dim=512, layers=6, heads=8)
    model_cfg["expert"]["heads"] = 8
    selected = os.environ.get("CUDA_VISIBLE_DEVICES", "")
    if not re.fullmatch(r"GPU-[0-9a-fA-F-]+", selected):
        raise RuntimeError("Root must bind one complete physical GPU UUID")
    import fcntl
    lock_dir = Path("/share/home/zixiao/descriptor_analysis/docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks")
    with (lock_dir / (selected + ".lock")).open("a") as gpu_lock:
        fcntl.flock(gpu_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return run(args, cfg, a4, model_cfg, selected)


def run(args, cfg, a4, model_cfg, selected):
    import torch
    import wandb
    from torch.profiler import profile, ProfilerActivity, record_function
    from phychem_mfm.factory import build_model
    from phychem_mfm.model.v3_profiling import instrument_model, padding_statistics, profiler_rows
    from phychem_mfm.model.v3_profiler_attribution import instrument_recompute_regions
    from phychem_mfm.phase1.objectives import compute_phase1_loss, Phase1JointSchedule, Phase1LossPolicy
    from phychem_mfm.phase1.full_corpus_loader import (BlockAtomBatchSampler, make_prefetch_loader,
        close_prefetch_iterator, _load_bound_native_transport, NATIVE_TRANSPORT_POLICY)
    from phychem_mfm.supervision import SupervisionConfig
    from phychem_mfm.training.losses import LossWeights
    from s_model_memory_v1 import build_memory_bounded_model
    from s_loader_recovery_v2 import RecoveringLoaderIterator
    from runtime_monitor import (gpu_observation, owned_output_bytes, owned_process_observation, inherited_log_bytes,
                                 bounded_trace_export)
    from native_runtime_bindings import bind_original_snapshot
    from private_runtime_storage import load_storage_bindings
    from profile_sampling import representative_steps, throughput_summary
    selected_steps = representative_steps(args.steps)

    private_storage = load_storage_bindings() if os.environ.get("MODEL_V3_STORAGE_BINDINGS_PATH") else None
    if args.input == "native_s" and private_storage is None:
        raise ValueError("Native profiling requires supervisor-bound private scratch/cache accounting")
    if args.input == "native_s" and not re.fullmatch(r"[0-9a-f]{64}", args.shard_snapshot_sha256 or ""):
        raise ValueError("Native profiling requires a pre-job raw shard snapshot SHA256")

    torch.set_num_threads(8)
    torch.set_num_interop_threads(1)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    if torch.cuda.device_count() != 1 or args.expected_gpu not in torch.cuda.get_device_name(0):
        raise RuntimeError("Actual CUDA visibility/GPU type differs from the requested comparison")
    applications = query(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid", "--format=csv,noheader,nounits"])
    foreign = [row for row in applications.splitlines() if row.split(",")[0].strip() == selected
               and int(row.split(",")[1]) != os.getpid()]
    if foreign:
        raise RuntimeError("Selected physical GPU has another compute process")
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    total_memory = int(torch.cuda.get_device_properties(0).total_memory)
    initial_gpu = gpu_observation(selected, own_pids=(os.getpid(),))
    runtime = {"input": args.input, "distance_implementation": args.distance,
               "distance_tile_rows": 65536 if args.distance == "tiled" else None,
               "backbone_checkpointing": True, "geometry_checkpointing": True,
               "precision": "fp32", "tf32": False, "fused_adamw": False,
               "optimizer": a4["optimizer"], "loss_policy": a4["loss_policy"],
               "loss_weights": {**cfg["training"]["loss"], "denoise_sigma": .1,
                                "geom_angle_std_deg": 0., "geom_bond_scale_std": 0.},
               "model": model_cfg, "sampler": {**cfg["sampler"], "max_padded_cost": args.max_padded_cost},
               "loader": {**cfg["loader"], "num_workers": args.workers},
               "noise_seed_includes_epoch": True,
               "seed": args.seed, "steps": args.steps, "warmup": args.warmup,
               "profile_sampling": {"protocol": "representative_steps_v2", "relative_steps": list(selected_steps),
                                    "independent_trace_per_sample": True},
               "code_sha": args.code_sha, "prereg_sha": args.prereg_sha,
               "source_sha256": source_bindings(), "gpu_uuid": selected,
               "gpu_name": torch.cuda.get_device_name(0), "gpu_total_bytes": total_memory,
               "torch_version": str(torch.__version__), "node": socket.gethostname(),
               "cuda_version": torch.version.cuda, "cudnn_version": torch.backends.cudnn.version(),
               "driver_version": initial_gpu["driver_version"], "logical_python": str(Path(sys.executable).absolute()),
               "python_version": sys.version, "device_capability": list(torch.cuda.get_device_capability(0)),
               "reference_configuration": {"path": str(args.reference_config), "sha256": digest(args.reference_config)},
               "a4_reference_sha256": digest(REPO / "workflows/s_denoise/configs/A4_seed0_v3.json"),
               "output_budget_bytes": args.output_budget_bytes, "rss_limit_bytes": args.rss_limit_bytes,
               "private_storage_bindings": private_storage,
               "job_id": os.environ["SLURM_JOB_ID"], "real_training_data": args.input == "native_s",
               "downstream_data_read": False, "original_lmdb_written": False,
               "measurement_notes": "Primary throughput uses complete unprofiled step wall times, including tracking/monitoring and excluding separate profiler analysis/export. The full measurement loop is retained separately. Inclusive operator rows remain diagnostic; analyze each raw trace after child/workers/SDK closure."}
    iterator = dataset = index = count_index = tracking = None
    sampler = None
    rows, profile_started = [], None
    started = time.monotonic()
    status = "FAILED"
    failure = None
    try:
        if args.input == "native_s":
            from s_native_adapter_v2 import MappedRecordIndex, ManifestViewsDataset, CountIndex, identity
            data_root = Path("/share/home/zixiao/descriptor_analysis/runs/sprime_s_convergence_20261013")
            protocol_ref = cfg["frozen_protocol_reference"]
            if digest(protocol_ref["path"]) != protocol_ref["sha256"]:
                raise RuntimeError("Frozen S reference protocol changed")
            protocol = json.loads(Path(protocol_ref["path"]).read_text())
            transport = protocol["draft_provenance"]["runner_artifacts"]["native_transport"]
            binding = {"policy": NATIVE_TRANSPORT_POLICY, "source_sha256": transport["sha256"]}
            runtime["native_transport"] = dict(transport)
            native = _load_bound_native_transport(Path(transport["path"]), binding, identity(transport["path"]))
            manifest_path = data_root / "training_inputs_v1/manifest.json"
            if digest(manifest_path) != cfg["input_manifest_sha256"]:
                raise RuntimeError("Actual S input manifest differs from its frozen reference")
            runtime["data_version"] = {"manifest_path": str(manifest_path), "sha256": digest(manifest_path), "role": "train"}
            snapshot, snapshot_binding = bind_original_snapshot(
                data_root / "training_inputs_v1/shard_snapshot_v1.json", args.shard_snapshot_sha256)
            runtime["original_shard_snapshot"] = snapshot_binding
            index = MappedRecordIndex("train", binding, snapshot, verify_hashes=True)
            count_index = CountIndex(index)
            dataset = ManifestViewsDataset(index, native_transport=native, native_transport_binding=binding,
                                           seed=args.seed, noise_seed_includes_epoch=True, **cfg["views"])
            sampler = BlockAtomBatchSampler(count_index, seed=args.seed, epoch=0, **runtime["sampler"])
            iterator = RecoveringLoaderIterator(
                lambda: make_prefetch_loader(dataset, sampler, **runtime["loader"]),
                sampler, close_prefetch_iterator, torch, role="stage1_train",
                on_retry=lambda row: print(json.dumps(row), flush=True))
        else:
            runtime["data_version"] = {"kind": "synthetic_smoke_only", "seed": args.seed}
        builder = build_memory_bounded_model if args.distance == "tiled" else build_model
        model = builder(model_cfg).cuda().train()
        optimizer = torch.optim.AdamW(model.parameters(), **a4["optimizer"])
        policy = Phase1LossPolicy.from_mapping(a4["loss_policy"])
        weights = LossWeights.from_mapping({**cfg["training"]["loss"], "denoise_sigma": .1,
                                           "geom_angle_std_deg": 0., "geom_bond_scale_std": 0.})
        supervision = SupervisionConfig.from_variant("S")
        configuration = json.dumps(runtime, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        runtime["configuration_sha256"] = hashlib.sha256(configuration).hexdigest()
        save(args.output / "configuration.json", runtime)
        os.environ["WANDB_MODE"] = "offline"
        os.environ["WANDB_CACHE_DIR"] = str(args.output / "cache")
        os.environ["WANDB_DATA_DIR"] = str(args.output / "wandb_data")
        tracking = wandb.init(project="mfm_model_v3_development", mode="offline", dir=str(args.output),
                              name="stage1_" + args.expected_gpu + "_" + os.environ["SLURM_JOB_ID"],
                              config=runtime)
        print(json.dumps({"status": "READY", "configuration_sha256": runtime["configuration_sha256"]}), flush=True)

        def step(ordinal, measured, *, profiled=False):
            nonlocal profile_started
            torch.cuda.reset_peak_memory_stats()
            if time.monotonic() - started > args.wall_seconds - 60:
                raise TimeoutError("Profiling wall limit reached with finalization reserve")
            with record_function("model_v3/loader_wait"):
                wait_start = time.perf_counter()
                corpus = next(iterator) if iterator is not None else synthetic_corpus(args.seed, ordinal)
                loader_wait = time.perf_counter() - wait_start
            stats = padding_statistics(corpus.native_atom_counts)
            if index is not None:
                refs = [index.ref(i) for i in corpus.logical_indices]
                if tuple(r.record_id for r in refs) != corpus.record_keys:
                    raise RuntimeError("Actual fetched record IDs differ")
                molecule_presentations = len(set(r.molecule_id for r in refs))
            else:
                molecule_presentations = stats["base_molecules"]
            torch.cuda.synchronize()
            compute_start = time.perf_counter()
            with record_function("model_v3/host_to_device"):
                batch = corpus.encoder_batch.to("cuda", non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with record_function("model_v3/forward"):
                outputs = model.forward_pretrain(batch, supervision.objectives)
            with record_function("model_v3/loss"):
                loss = compute_phase1_loss(outputs, batch, None, supervision, weights,
                                          Phase1JointSchedule(), ordinal, policy=policy)
                if not bool(torch.isfinite(loss.total)):
                    raise FloatingPointError("Nonfinite profiling loss")
            with record_function("model_v3/backward"):
                loss.total.backward()
                gradient = torch.nn.utils.clip_grad_norm_(model.parameters(), 1.)
                if not bool(torch.isfinite(gradient)):
                    raise FloatingPointError("Nonfinite profiling gradient")
            with record_function("model_v3/optimizer"):
                optimizer.step()
            torch.cuda.synchronize()
            compute_seconds = time.perf_counter() - compute_start
            if sampler is not None:
                sampler.commit_batch(corpus.logical_indices)
            row = {"ordinal": ordinal, "measured": measured, "profiled": profiled, "loader_wait_seconds": loader_wait,
                   "compute_seconds": compute_seconds, "molecule_presentations": molecule_presentations,
                   "logical_indices": list(corpus.logical_indices), "record_keys": list(corpus.record_keys),
                   "loss": float(loss.total.detach().cpu()), "gradient_norm": float(gradient.detach().cpu()),
                   "valid_label_counts": dict(loss.counts), **stats,
                   "peak_allocated_bytes": torch.cuda.max_memory_allocated(),
                   "peak_reserved_bytes": torch.cuda.max_memory_reserved()}
            processes = owned_process_observation(os.getpid())
            row["host_rss_sum_bytes"] = processes["rss_sum_bytes"]
            row["gpu_observation"] = gpu_observation(selected, own_pids=[item["pid"] for item in processes["processes"]])
            row["foreign_gpu_risk_observed"] = bool(row["gpu_observation"]["foreign_processes"])
            row["inherited_job_log_bytes"] = inherited_log_bytes(exclude_root=args.output)
            row["output_bytes_before_log"] = owned_output_bytes(args.output) + row["inherited_job_log_bytes"]
            if row["host_rss_sum_bytes"] > args.rss_limit_bytes:
                raise MemoryError("Owned process tree exceeded the explicit host RSS cap")
            if row["output_bytes_before_log"] > args.output_budget_bytes - 16 * 1024**2:
                raise MemoryError("Run output reached the reserved finalization headroom")
            if row["peak_allocated_bytes"] > .85 * total_memory:
                raise MemoryError("Measured GPU allocation exceeded 85% of actual capacity")
            log_row = {key: value for key, value in row.items() if type(value) in (int, float, bool)}
            tracking.log(log_row, step=ordinal, commit=True)
            with (args.output / "steps.jsonl").open("a") as stream:
                stream.write(json.dumps(row, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            if measured:
                rows.append(row)
            print(json.dumps({"step": ordinal, "measured": measured, "loss": row["loss"],
                              "seconds": compute_seconds, "loader_wait": loader_wait}), flush=True)
            return row

        samples = []
        with instrument_model(model), instrument_recompute_regions(model):
            for ordinal in range(args.warmup):
                step(ordinal, False)
            torch.cuda.reset_peak_memory_stats()
            profile_started = time.perf_counter()
            for relative in range(args.steps):
                ordinal = args.warmup + relative
                if relative not in selected_steps:
                    step_started = time.perf_counter()
                    row = step(ordinal, True)
                    row['end_to_end_step_seconds'] = time.perf_counter() - step_started
                    continue
                with profile(activities=[ProfilerActivity.CPU, ProfilerActivity.CUDA],
                             record_shapes=True, profile_memory=True, with_stack=False) as prof:
                    step_started = time.perf_counter()
                    row = step(ordinal, True, profiled=True)
                    row['end_to_end_step_seconds'] = time.perf_counter() - step_started
                export_started = time.perf_counter()
                table = profiler_rows(prof)
                operator_name = f'profiler_operators_step_{ordinal:04d}.json'
                trace_name = f'trace_step_{ordinal:04d}.json'
                save(args.output / operator_name, table)
                trace_budget = bounded_trace_export(prof, args.output / trace_name, output_root=args.output,
                                                    output_budget_bytes=args.output_budget_bytes)
                samples.append({'ordinal': ordinal, 'relative_step': relative, 'trace': trace_name,
                    'operators': operator_name, 'trace_budget': trace_budget,
                    'postprocess_seconds': time.perf_counter() - export_started,
                    'regions': [item for item in table if item['name'].startswith('model_v3/')]})
                del table, prof
                gc.collect()
            elapsed = time.perf_counter() - profile_started
        save(args.output / 'step_timings.json', [{'ordinal': row['ordinal'], 'profiled': row['profiled'],
            'end_to_end_step_seconds': row['end_to_end_step_seconds']} for row in rows])
        speed = throughput_summary(rows)
        timed_rows = [row for row in rows if not row['profiled']] or rows
        wait = sum(row["loader_wait_seconds"] for row in timed_rows)
        compute = sum(row["compute_seconds"] for row in timed_rows)
        summary = {"status": "PROFILE_COMPLETED", "stage1_acceptance": False,
                   "per_gpu_measurement_complete": args.input == "native_s" and args.steps == 20,
                   "stage1_acceptance_scope": "one GPU type only; all three types and reviewed report remain required",
                   "elapsed_profile_seconds": elapsed, "loader_wait_fraction": wait / (wait + compute),
                   "measurement_loop_includes_profiler_analysis_and_export": True,
                   "loader_wait_fraction_scope": speed['throughput_scope'],
                   **speed,
                   "measured_optimizer_steps": len(rows), "profiled_relative_steps": list(selected_steps),
                   "timing_artifact": "step_timings.json", "profile_samples": samples,
                   "atom_padding_fraction": sum(row["base_atoms"] * 3 for row in rows) / sum(row["padded_atoms"] for row in rows),
                   "pair_padding_fraction": sum(row["native_pairs_including_diagonal"] for row in rows) / sum(row["padded_pairs_including_diagonal"] for row in rows),
                   "peak_allocated_bytes": max(row['peak_allocated_bytes'] for row in rows),
                   "peak_reserved_bytes": max(row['peak_reserved_bytes'] for row in rows),
                   "unprofiled_peak_allocated_bytes": max((row['peak_allocated_bytes'] for row in rows if not row['profiled']), default=None),
                   "foreign_gpu_risk_observed": any(row["foreign_gpu_risk_observed"] for row in rows),
                   "regions": [{"profile_ordinal": sample['ordinal'], **item} for sample in samples for item in sample['regions']],
                   "configuration_sha256": runtime["configuration_sha256"], "tracking_run_id": tracking.id,
                   "tracking_mode": "offline", "code_sha": args.code_sha, "prereg_sha": args.prereg_sha}
        save(args.output / "summary.json", summary)
        status = "PROFILE_COMPLETED"
        return 0
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        cleanup_errors = []
        worker_exit = []
        handles_closed = True
        original_workers = tuple(getattr(getattr(iterator, "iterator", None), "_workers", ()))
        if iterator is not None:
            try:
                iterator.close()
                worker_exit = [{"pid": worker.pid, "alive": worker.is_alive(), "exit_code": worker.exitcode}
                               for worker in original_workers]
                if any(row["alive"] or row["exit_code"] is None for row in worker_exit):
                    raise RuntimeError("A recorded loader worker has not actually exited/joined")
            except BaseException as exc:
                cleanup_errors.append({"item": "iterator", "type": type(exc).__name__, "message": str(exc)})
        input_paths = set()
        if index is not None:
            input_paths.update(str(Path(value).absolute()) for value in (index.path, index.atoms_path))
            input_paths.update(str(Path(shard["path"]).absolute()) for shard in index.shards.values())
        for item in (dataset, index, count_index):
            if item is not None:
                try:
                    item.close()
                except BaseException as exc:
                    cleanup_errors.append({"item": type(item).__name__, "type": type(exc).__name__, "message": str(exc)})
        if input_paths:
            try:
                remaining = []
                for fd in Path("/proc/self/fd").iterdir():
                    try:
                        target = os.readlink(fd)
                    except FileNotFoundError:
                        continue
                    if target in input_paths:
                        remaining.append({"fd": fd.name, "path": target})
                if remaining:
                    handles_closed = False
                    raise RuntimeError("Native index/LMDB descriptors remain open after close: " + str(remaining))
            except BaseException as exc:
                cleanup_errors.append({"item": "input_descriptors", "type": type(exc).__name__, "message": str(exc)})
        if tracking is not None:
            try:
                tracking.finish(exit_code=0 if status == "PROFILE_COMPLETED" and not cleanup_errors else 1)
            except BaseException as exc:
                cleanup_errors.append({"item": "tracking", "type": type(exc).__name__, "message": str(exc)})
        save(args.output / "run_status.json", {"status": status if not cleanup_errors else "CLEANUP_FAILED", "job_id": os.environ["SLURM_JOB_ID"],
                                               "elapsed_seconds": time.monotonic() - started,
                                               "failure": failure, "cleanup_errors": cleanup_errors,
                                               "loader_worker_exit": worker_exit, "input_descriptors_closed": handles_closed,
                                               "code_sha": args.code_sha, "prereg_sha": args.prereg_sha})
        if cleanup_errors and failure is None:
            raise RuntimeError("Profiler cleanup failed; preserve artifacts and inspect run_status.json")


if __name__ == "__main__":
    raise SystemExit(main())
