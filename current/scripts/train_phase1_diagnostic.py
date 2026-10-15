#!/usr/bin/env python3
"""Bounded real-data diagnostics. This entry point never launches formal work."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import resource
import sys
import time

import numpy as np
import torch
import wandb

from phychem_mfm.config import load_experiment_config
from phychem_mfm.factory import build_model
from phychem_mfm.model.normalization import train_regression_normalization
from phychem_mfm.phase1.baselines import TrainingBaselines
from phychem_mfm.phase1.data import StrictManifestDataset, Phase1ViewDataset, fit_train_statistics, audit_manifest_identities
from phychem_mfm.phase1.evaluation import OriginalUnitEvaluator
from phychem_mfm.phase1.memory_observation import MemoryObservation
from phychem_mfm.phase1.objectives import PHASE1_VARIANTS, Phase1JointSchedule, Phase1LossPolicy, canonical_variant, step_runtime_metrics
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.checkpoint import save_training_checkpoint, load_training_checkpoint, source_provenance, contract_hash
from phychem_mfm.training.data import fast_collate
from phychem_mfm.training.losses import LossWeights, compute_pretrain_loss
from phychem_mfm.training.optim import build_adamw, build_warmup_cosine_scheduler


def json_dump(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def assert_state_equal(actual, expected, path="state"):
    """Check optimizer/scheduler values, including tensor-valued Adam moments."""
    if isinstance(actual, torch.Tensor):
        torch.testing.assert_close(actual, expected, rtol=0, atol=0, msg=path)
    elif isinstance(actual, dict):
        if actual.keys() != expected.keys():
            raise RuntimeError(f"{path} keys differ after checkpoint restore")
        for key in actual:
            assert_state_equal(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(actual, (list, tuple)):
        if len(actual) != len(expected):
            raise RuntimeError(f"{path} length differs after checkpoint restore")
        for index, (left, right) in enumerate(zip(actual, expected)):
            assert_state_equal(left, right, f"{path}[{index}]")
    elif actual != expected:
        raise RuntimeError(f"{path} differs after checkpoint restore")


def backbone_state_hash(model):
    digest = hashlib.sha256()
    for name, value in sorted(model.backbone.state_dict().items()):
        tensor = value.detach().cpu().contiguous()
        digest.update(f"{name}:{tensor.dtype}:{tuple(tensor.shape)}\n".encode())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--config", default="configs/phase1/diagnostic.yaml")
    parser.add_argument("--variant", choices=PHASE1_VARIANTS, default="SDP")
    parser.add_argument("--preset", choices=("light", "expert"), default="light")
    parser.add_argument("--geometry", choices=("legacy", "residual"), default="legacy")
    parser.add_argument("--regression-output", choices=("raw", "train_affine"), default="train_affine")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cuda")
    parser.add_argument("--wandb-mode", choices=("offline", "online"), default="offline")
    parser.add_argument("--resume")
    parser.add_argument("--observe-memory", action="store_true",
                        help="Record bounded allocator snapshots without changing training or clearing caches")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    config = load_experiment_config(args.config).to_dict()
    config["architecture"] = {"type": "shared_multitask", "preset": args.preset, "task_route": args.preset}
    config["supervision"]["variant"] = canonical_variant(args.variant)
    config["head"].update(profile="phase1", geometry_head=args.geometry)
    if args.max_steps is not None:
        config["schedule"]["max_steps"] = args.max_steps
    p = config["phase1"]
    steps, wall_limit = int(config["schedule"]["max_steps"]), float(p["max_wall_seconds"])
    finalization_limit = float(p.setdefault("max_finalization_seconds", 30.))
    if p.get("status") != "diagnostic_only" or not 1 <= steps <= 1024 or not 0 < wall_limit <= 600:
        raise ValueError("This runner is restricted to declared small bounded diagnostics")
    if int(p["train_limit"]) > 4096 or int(p["validation_limit"]) > 1024:
        raise ValueError("Diagnostic data limits exceeded")
    if not 0 < finalization_limit <= 60:
        raise ValueError("Diagnostic finalization must be bounded to at most 60 seconds")
    validation_every = p.setdefault("validation_every_steps", 0)
    if type(validation_every) is not int or not 0 <= validation_every <= steps:
        raise ValueError("Diagnostic validation interval must be zero or a bounded positive step count")
    if p["atom_encoding"] != "zero_based" or p["views"] != ["clean", "geom", "topo"]:
        raise ValueError("Diagnostic view/encoding protocol changed")
    output = Path(args.output_dir).resolve()
    if output.exists() and any(output.iterdir()) and not args.resume:
        raise FileExistsError("Refusing to overwrite a previous diagnostic")
    output.mkdir(parents=True, exist_ok=True)
    seed = int(config["training"]["seed"])
    torch.manual_seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(2)
    device = torch.device(args.device)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats()
    source = source_provenance(root)
    began = time.perf_counter()
    run_id_path = output / "wandb_run_id.txt"
    attempt_id = f"{time.time_ns()}-{os.getpid()}"
    run = None
    status, updates, exposure, last, evaluation_history = "failed", 0, 0, {}, []
    memory_observation = None
    cumulative = Counter()
    resume_verified = False
    try:
        if args.observe_memory:
            memory_observation = MemoryObservation(output / "memory_observations.jsonl", device=device)
        if args.resume:
            # Read the lineage before starting a tracker. A new output directory
            # can continue the saved run; an unrelated existing run must fail.
            lineage = torch.load(args.resume, map_location="cpu", weights_only=False)
            checkpoint_run_id = lineage.get("extra", {}).get("wandb_run_id")
            if not isinstance(checkpoint_run_id, str) or not checkpoint_run_id:
                raise RuntimeError("Resume checkpoint has no tracker lineage")
            if run_id_path.exists() and run_id_path.read_text().strip() != checkpoint_run_id:
                raise RuntimeError("Resume tracker lineage mismatch")
            run_id = checkpoint_run_id
            del lineage
        else:
            run_id = wandb.util.generate_id()
        # Initialize the actual tracker before fitting baselines or training.
        run = wandb.init(project="phychem-mfm-phase1-diagnostics", mode=args.wandb_mode, dir=str(output), id=run_id,
                         resume="allow" if args.resume and args.wandb_mode == "online" else None,
                         config={**config, "source": source, "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
                                 "purpose": "bounded diagnostic, not formal matrix", "resumed_from": args.resume,
                                 "resume_attempt_id": attempt_id if args.resume else None})
        if run is None:
            raise RuntimeError("Experiment tracker initialization failed")
        if run.id != run_id:
            raise RuntimeError("Experiment tracker did not preserve the requested lineage")
        if memory_observation is not None:
            run.config.update({"diagnostic_memory_observation": {
                "enabled": True, "path": str(output / "memory_observations.jsonl"),
                "max_records": 8192, "max_bytes": 8 * 1024 ** 2,
                "sampling": "unsynchronized allocator gauges; no peak reset or cache clearing",
            }}, allow_val_change=False)
        if not args.resume:
            run_id_path.write_text(run.id, encoding="utf-8")
        train = StrictManifestDataset(root / p["train_manifest"], atom_encoding="zero_based", diagnostic_limit=p["train_limit"])
        validation = StrictManifestDataset(root / p["validation_manifest"], atom_encoding="zero_based", diagnostic_limit=p["validation_limit"])
        split = audit_manifest_identities(train, validation)
        stats, statistics_provenance = fit_train_statistics(train, cap=len(train), seed=seed)
        serial_stats = {key: value.tolist() if isinstance(value, torch.Tensor) else value for key, value in stats.items()}
        config["phase1"]["regression_output_mode"] = args.regression_output
        if args.regression_output == "train_affine":
            config["head"]["regression_output_normalization"] = train_regression_normalization(stats, statistics_provenance)
        else:
            config["head"].pop("regression_output_normalization", None)
        run.config.update({"head": config["head"], "phase1": config["phase1"]}, allow_val_change=True)
        element_baseline_view = Phase1ViewDataset(train, mode="topo", level=p["topology_level"], seed=seed)
        baselines = TrainingBaselines(int(config["backbone"]["n_atom_types"])).fit(
            (train[index] for index in range(len(train))), train_manifest={"role": "train", **train.summary()},
            element_records=(element_baseline_view[index] for index in range(len(train))))
        policy = Phase1LossPolicy.from_mapping(p)
        manifest = {"purpose": "bounded_diagnostic_only", "train": train.summary(), "validation": validation.summary(),
                    "split_identity_audit": split, "statistics": statistics_provenance, "label_profile": "phase1_23_graph_6_node_positive_bond_v1",
                    "loss_policy": policy.to_dict(), "view_protocol": {"views": p["views"], "geometry_level": p["geometry_level"],
                                                                           "topology_level": p["topology_level"], "seed": seed},
                    "downstream_decontamination": "NOT COMPLETE; cannot use this diagnostic as formal matrix evidence"}
        manifest["continuous_output_contract"] = {
            "mode": args.regression_output,
            "contract_sha256": config["head"].get("regression_output_normalization", {}).get("contract_sha256"),
            "statistics_hash": statistics_provenance["statistics_hash"],
        }
        manifest["diagnostic_contract_sha256"] = contract_hash(manifest)
        # Pair initialization independently of any dataset/tracker RNG use.
        torch.manual_seed(seed)
        model = build_model(config, preset=args.preset).to(device)
        initialization_hash = backbone_state_hash(model)
        optimizer = build_adamw(model, **{name: config["optimizer"][name] for name in ("lr", "weight_decay", "betas")})
        scheduler = build_warmup_cosine_scheduler(optimizer, total_steps=steps,
                    warmup_steps=min(int(config["schedule"]["warmup_steps"]), steps), min_lr_ratio=config["schedule"]["min_lr_ratio"])
        supervision = SupervisionConfig.from_variant(args.variant)
        schedule, weights = Phase1JointSchedule(), LossWeights.from_mapping(config["loss"])
        if args.resume:
            payload = load_training_checkpoint(args.resume, model=model, optimizer=optimizer, scheduler=scheduler,
                expected_config=config, expected_dataset_manifest=manifest, expected_source_sha256=source["source_sha256"], strict_semantics=True)
            exposure, updates = payload["global_exposure_step"], payload["optimizer_update_step"]
            cumulative.update(payload["extra"].get("cumulative_counts", {}))
            if payload["extra"].get("wandb_run_id") != run_id:
                raise RuntimeError("Resume tracker lineage mismatch")
            resume_verified = True
        artifacts = {"manifest.json": manifest,
                     "statistics.json": {"values": serial_stats, "provenance": statistics_provenance},
                     "baselines.json": baselines.to_dict(), "config.json": config}
        if args.resume:
            # Check all existing evidence before replacing any contract file.
            for filename, proposed in artifacts.items():
                path = output / filename
                if path.exists() and contract_hash(json.loads(path.read_text(encoding="utf-8"))) != contract_hash(proposed):
                    raise RuntimeError(f"Resume output evidence mismatch: {filename}")
            history_path = output / "evaluations.json"
            if not history_path.exists():
                history_path = Path(args.resume).resolve().parent / "evaluations.json"
            if history_path.exists():
                evaluation_history = json.loads(history_path.read_text(encoding="utf-8"))
                if not isinstance(evaluation_history, list):
                    raise RuntimeError("Resume evaluation history is not a list")
                if any(int(entry.get("exposure_step", 0)) > exposure for entry in evaluation_history):
                    raise RuntimeError("Resume checkpoint precedes recorded evaluations; a separate lineage is required")
            previous_steps = Path(args.resume).resolve().parent / "steps.jsonl"
            active_steps = output / "steps.jsonl" if (output / "steps.jsonl").exists() else previous_steps
            if active_steps.exists():
                with active_steps.open(encoding="utf-8") as handle:
                    if any(int(json.loads(line).get("step", 0)) > exposure for line in handle if line.strip()):
                        raise RuntimeError("Resume checkpoint precedes recorded updates; a separate lineage is required")
            if not (output / "steps.jsonl").exists() and previous_steps.exists():
                (output / "steps.jsonl").write_bytes(previous_steps.read_bytes())
        for filename, value in artifacts.items():
            json_dump(output / filename, value)
        if memory_observation is not None:
            json_dump(output / "memory_observation_metadata.json", {
                "purpose": "allocator capacity diagnostic only; not a new maturity experiment",
                "enabled": True, "source": source,
                "path": str(output / "memory_observations.jsonl"),
                "max_records": 8192, "max_bytes": 8 * 1024 ** 2,
                "config_contract_sha256": contract_hash(config),
                "diagnostic_contract_sha256": manifest["diagnostic_contract_sha256"],
                "paired_initial_H0_sha256": initialization_hash,
                "measurement_scope": "CUDA allocator gauges without additional synchronization",
                "cuda_cache_or_peak_mutation": False,
            })
            memory_observation.record("model_and_optimizer_ready", {
                "scope": "setup", "optimizer_updates_completed": updates,
                "paired_initial_H0_sha256": initialization_hash,
            })
        run_id_path.write_text(run.id, encoding="utf-8")
        def views(base):
            return [Phase1ViewDataset(base, mode=mode, level=p["geometry_level"] if mode == "geom" else p["topology_level"], seed=seed)
                    for mode in p["views"]]
        training_views, validation_views = views(train), views(validation)
        batch_size = int(config["training"]["base_molecules_per_batch"])
        batch_observation = {}
        def observe(stage):
            if memory_observation is not None:
                memory_observation.record(stage, {**batch_observation,
                    "optimizer_updates_completed": updates, "exposure_step": exposure})
        def make_batch(viewsets, selected, *, scope="restore", forward_1based=None):
            nonlocal batch_observation
            if memory_observation is None:
                return fast_collate([viewset[index] for index in selected for viewset in viewsets]).to(device)
            selected = [int(index) for index in selected]
            records = [viewset[index] for index in selected for viewset in viewsets]
            # Inspect already loaded CPU view records; no extra reads or CUDA
            # transfers, and no tensor reference escapes into the observer.
            batch_observation = {
                "scope": scope, "forward_1based": forward_1based,
                "optimizer_updates_completed": updates, "exposure_step": exposure,
                "selected_base_indices": selected,
                "graphs": [{"view": p["views"][ordinal % len(viewsets)],
                            "record_key": str(record.pretrain_base_key),
                            "natoms": int(record.x.shape[0])}
                           for ordinal, record in enumerate(records)],
            }
            observe("before_transfer")
            batch = fast_collate(records).to(device)
            observe("after_transfer")
            return batch
        def evaluate(label):
            model.eval()
            evaluator = OriginalUnitEvaluator(model, baselines, cutoff=weights.cutoff)
            evaluated = 0
            for first in range(0, len(validation), batch_size):
                if time.perf_counter() - began >= wall_limit:
                    break
                batch = make_batch(validation_views, range(first, min(first + batch_size, len(validation))),
                                   scope=f"validation:{label}")
                with torch.no_grad():
                    observe("before_forward")
                    predictions = model.forward_pretrain(batch, supervision.objectives)
                    observe("after_forward")
                    evaluator.add(batch, predictions)
                    observe("after_evaluator")
                evaluated += min(batch_size, len(validation) - first)
            complete = evaluated == len(validation)
            result = {"label": label, "exposure_step": exposure, "optimizer_update_step": updates,
                      "completion": "complete" if complete else "incomplete_wall_budget",
                      "evaluated_base_molecules": evaluated, "expected_base_molecules": len(validation),
                      **evaluator.result()}
            evaluation_history.append(result)
            json_dump(output / "evaluations.json", evaluation_history)
            flat = {f"validation/{target}/{which}/{key}": value for target, estimates in result["targets"].items()
                     for which, metrics in estimates.items() for key, value in metrics.items()
                     if isinstance(value, (int, float))}
            flat.update({"validation/evaluation_complete": int(complete), "validation/evaluated_base_molecules": evaluated})
            run.log(flat, step=exposure)
            model.train()
            return complete
        initial_complete = evaluate("resume_validation" if args.resume else "paired_initialization")
        order = np.random.default_rng(seed).permutation(len(train))
        if args.variant == "none":
            status = "random_initialization_control" if initial_complete else "wall_budget_reached"
        else:
            for step in range(exposure, steps):
                if time.perf_counter() - began >= wall_limit:
                    status = "wall_budget_reached"
                    break
                start = time.perf_counter()
                positions = [(step * batch_size + offset) % len(order) for offset in range(batch_size)]
                batch = make_batch(training_views, [int(order[position]) for position in positions],
                                   scope="training", forward_1based=step + 1)
                fetch_seconds = time.perf_counter() - start
                optimizer.zero_grad(set_to_none=True)
                observe("after_zero_grad")
                lr_used = optimizer.param_groups[0]["lr"]
                with torch.random.fork_rng(devices=[device.index or 0] if device.type == "cuda" else []):
                    torch.manual_seed(seed + step)
                    observe("before_forward")
                    predictions = model.forward_pretrain(batch, supervision.objectives)
                    observe("after_forward")
                    result = compute_pretrain_loss(predictions, batch, stats, supervision, weights, schedule, step,
                             graph_descriptor_indices=model.graph_descriptor_target_indices, phase1_mode=True, phase1_policy=policy)
                    observe("after_loss")
                    if not result.total.requires_grad:
                        raise RuntimeError("Enabled condition has no effective labels; not an optimizer update")
                    result.total.backward()
                    observe("after_backward")
                grad = torch.nn.utils.clip_grad_norm_(model.parameters(), config["optimizer"]["grad_clip_norm"])
                if not torch.isfinite(grad):
                    raise FloatingPointError("Non-finite gradient")
                optimizer.step()
                scheduler.step()
                updates += 1
                exposure = step + 1
                observe("after_optimizer")
                cumulative.update(result.counts)
                if device.type == "cuda":
                    torch.cuda.synchronize()
                last = {**result.scalar_metrics("train/"), **step_runtime_metrics(optimizer, lr_used=lr_used,
                         exposure_step=exposure, optimizer_update_step=updates), "train/grad_norm": float(grad),
                         "performance/fetch_seconds": fetch_seconds, "performance/full_step_seconds": time.perf_counter()-start}
                run.log(last, step=exposure)
                with (output / "steps.jsonl").open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps({"step": exposure, **last}, allow_nan=False) + "\n")
                observe("after_step_logging")
                if validation_every and exposure % validation_every == 0 and exposure < steps:
                    if not evaluate("fixed_diagnostic_interval"):
                        status = "wall_budget_reached"
                        break
            else:
                status = "step_budget_reached"
            if not evaluate("fixed_diagnostic_endpoint"):
                status = "wall_budget_reached"
        finalization_began = time.perf_counter()
        finalization_deadline = finalization_began + finalization_limit
        checkpoint_type = "budget_stop" if status == "wall_budget_reached" else "fixed_diagnostic_endpoint"
        save_training_checkpoint(output / "checkpoint.pt", model=model, optimizer=optimizer, scheduler=scheduler,
            config=config, supervision=supervision.to_dict(), dataset_manifest=manifest, exposure_step=exposure,
            optimizer_update_step=updates, checkpoint_type=checkpoint_type, project_root=root,
            source_metadata=source, extra={"wandb_run_id": run.id, "cumulative_counts": dict(cumulative), "status": status,
                                          "paired_initial_H0_sha256": initialization_hash,
                                          "evaluation_completion": evaluation_history[-1]["completion"]})
        # A real strict round-trip verifies H0 exports, optimizer and schedule.
        roundtrip_status = "incomplete_finalization_budget"
        roundtrip_evidence = {}
        if time.perf_counter() < finalization_deadline:
            restored = build_model(config, preset=args.preset).to(device)
            restored_optimizer = build_adamw(restored, **{name: config["optimizer"][name] for name in ("lr", "weight_decay", "betas")})
            restored_scheduler = build_warmup_cosine_scheduler(restored_optimizer, total_steps=steps,
                warmup_steps=min(int(config["schedule"]["warmup_steps"]), steps), min_lr_ratio=config["schedule"]["min_lr_ratio"])
            if time.perf_counter() < finalization_deadline:
                load_training_checkpoint(output / "checkpoint.pt", model=restored, optimizer=restored_optimizer, scheduler=restored_scheduler,
                    expected_config=config, expected_dataset_manifest=manifest, expected_source_sha256=source["source_sha256"], strict_semantics=True)
                assert_state_equal(model.state_dict(), restored.state_dict(), "model")
                assert_state_equal(optimizer.state_dict(), restored_optimizer.state_dict(), "optimizer")
                assert_state_equal(scheduler.state_dict(), restored_scheduler.state_dict(), "scheduler")
                if time.perf_counter() < finalization_deadline:
                    model.eval()
                    restored.eval()
                    test_batch = make_batch(validation_views, [0])
                    with torch.no_grad():
                        original_atoms = model.encode_atoms(test_batch)
                        restored_atoms = restored.encode_atoms(test_batch)
                        torch.testing.assert_close(original_atoms, restored_atoms, rtol=0, atol=0)
                        # Verify pooling exactly on CPU as well. CUDA scatter
                        # reductions may sum identical atom states in a different
                        # order, so their API outputs get a recorded float32
                        # tolerance rather than a bitwise requirement.
                        cpu_batch = test_batch.batch.cpu()
                        torch.testing.assert_close(model.graph_pool(original_atoms.cpu(), cpu_batch),
                                                   restored.graph_pool(restored_atoms.cpu(), cpu_batch), rtol=0, atol=0)
                        original_graph = model.encode_graph(test_batch)
                        repeated_graph = model.encode_graph(test_batch)
                        restored_graph = restored.encode_graph(test_batch)
                        graph_atol, graph_rtol = ((1e-6, 1e-5) if device.type == "cuda" else (0., 0.))
                        torch.testing.assert_close(original_graph, repeated_graph, rtol=graph_rtol, atol=graph_atol)
                        torch.testing.assert_close(original_graph, restored_graph, rtol=graph_rtol, atol=graph_atol)
                        roundtrip_evidence = {"model_state": "bitwise_equal", "optimizer_scheduler": "bitwise_equal",
                                              "H0_atoms": "bitwise_equal", "H0_graph_cpu_pool": "bitwise_equal",
                                              "graph_atol": graph_atol, "graph_rtol": graph_rtol,
                                              "graph_repeat_max_abs": float((original_graph-repeated_graph).abs().max()),
                                              "graph_restore_max_abs": float((original_graph-restored_graph).abs().max())}
                    roundtrip_status = "passed"
        summary = {"status": status, "diagnostic_only": True, "variant": args.variant, "preset": args.preset,
                   "geometry_head": args.geometry, "exposure_step": exposure, "optimizer_update_step": updates,
                   "regression_output_mode": args.regression_output,
                   "cumulative_counts": dict(cumulative), "wall_seconds": time.perf_counter()-began,
                   "max_rss_KiB": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                   "peak_gpu_allocated_bytes": torch.cuda.max_memory_allocated() if device.type == "cuda" else 0,
                   "wandb_run_id": run.id, "wandb_mode": args.wandb_mode, "wandb_directory": run.dir,
                   "source": source, "checkpoint": str(output / "checkpoint.pt"), "checkpoint_type": checkpoint_type,
                    "paired_initial_H0_sha256": initialization_hash,
                    "resume_export_roundtrip": roundtrip_status, "endpoint_evaluation_completion": evaluation_history[-1]["completion"],
                    "resume_export_roundtrip_evidence": roundtrip_evidence,
                    "finalization_seconds": time.perf_counter() - finalization_began,
                    "max_finalization_seconds": finalization_limit,
                   "maturity": "training insufficient: bounded diagnostic is not a convergence claim",
                   "last_step": last}
        if memory_observation is not None:
            summary["memory_observation"] = {
                "path": str(output / "memory_observations.jsonl"),
                "metadata_path": str(output / "memory_observation_metadata.json"),
                "sampling_is_gpu_reservation": False,
            }
        json_dump(output / "summary.json", summary)
        run.summary.update({key: value for key, value in summary.items() if isinstance(value, (str, int, float, bool))})
        print(json.dumps(summary, indent=2))
    except BaseException as error:
        status = "failed"
        failure_path = output / "failure.json"
        if args.resume:
            failure_path = output / "resume_attempts" / f"failure_{attempt_id}.json"
            failure_path.parent.mkdir(parents=True, exist_ok=True)
        json_dump(failure_path, {"type": type(error).__name__, "reason": str(error), "exposure_step": exposure,
                                "optimizer_update_step": updates, "wall_seconds": time.perf_counter()-began,
                                "resume_verified": resume_verified, "resumed_from": args.resume})
        if run is not None:
            if args.resume:
                run.summary.update({"resume_attempt_status": "failed", "resume_attempt_id": attempt_id,
                                    "resume_failure_type": type(error).__name__, "resume_failure_reason": str(error)})
            else:
                run.summary.update({"status": "failed", "failure_type": type(error).__name__, "failure_reason": str(error)})
        raise
    finally:
        primary_error = sys.exc_info()[1]
        try:
            if memory_observation is not None:
                memory_observation.close()
        except BaseException as close_error:
            status = "failed"
            close_failure = {"type": type(close_error).__name__, "reason": str(close_error),
                "context": "memory_observation_close", "exposure_step": exposure,
                "optimizer_update_step": updates,
                "primary_failure_type": type(primary_error).__name__ if primary_error else None}
            try:
                json_dump(output / "memory_observation_close_failure.json", close_failure)
                if primary_error is None:
                    json_dump(output / "failure.json", close_failure)
                    summary_path = output / "summary.json"
                    if summary_path.exists():
                        saved_summary = json.loads(summary_path.read_text(encoding="utf-8"))
                        saved_summary.update(status="failed", memory_observation_close="failed")
                        json_dump(summary_path, saved_summary)
                if run is not None:
                    run.summary.update({"status": "failed", "memory_observation_close": "failed"})
            except BaseException as recording_error:
                if hasattr(close_error, "add_note"):
                    close_error.add_note(f"Close diagnostic persistence also failed: {type(recording_error).__name__}")
            if primary_error is None:
                raise
            if hasattr(primary_error, "add_note"):
                primary_error.add_note(f"Memory observation close also failed: {type(close_error).__name__}")
        finally:
            if run is not None:
                run.finish(exit_code=1 if status == "failed" else 0)


if __name__ == "__main__":
    main()
