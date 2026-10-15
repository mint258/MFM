#!/usr/bin/env python3
"""Execute one frozen Phase 1 condition inside a verified single-GPU Slurm job.

This command neither submits jobs nor prepares/freezes protocols. It has no
scientific/budget overrides and rejects unfinished evidence or live GPU gates.
Fresh offline_persistent W&B runs stay under output-dir and are not claimed to
be visible online. Strict resume currently supports online runs only: merging
offline SDK segments is a technical capability that has not been verified.
No additional approval or credential artifact is inferred from that limitation.
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import time

import numpy as np
import torch
import wandb

from phychem_mfm.factory import build_model
from phychem_mfm.phase1.data import StrictManifestDataset, Phase1ViewDataset
from phychem_mfm.phase1.evaluation import OriginalUnitEvaluator
from phychem_mfm.phase1.formal_runtime import (
    FORMAL_RUN_SCHEMA, BudgetClock, artifact_paths, check_atom_caps, cyclic_batch_indices,
    backbone_state_hash, file_sha256, finalize_endpoint, frozen_execution, get_path, label_contract, live_gate, load_fitted_controls,
    formal_policy_at_update, formal_weighting_metrics, formal_weighting_state, select_formal_recipe,
    read_artifact, read_json, single_gpu_environment, target_contract, validate_formal_resume,
    verify_architecture, verify_decontamination, verify_paired_initialization, verify_source, verify_tracker_lineage, write_json,
)
from phychem_mfm.phase1.objectives import PHASE1_VARIANTS, Phase1JointSchedule, step_runtime_metrics
from phychem_mfm.phase1.strategy_contract import DIRECT_RECIPE
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.checkpoint import (
    contract_hash, load_training_checkpoint, save_training_checkpoint, source_provenance,
)
from phychem_mfm.training.data import fast_collate
from phychem_mfm.training.losses import LossWeights, compute_pretrain_loss
from phychem_mfm.training.optim import build_adamw, build_warmup_cosine_scheduler


def parse_args(argv=None):
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--artifacts", required=True, help="JSON mapping frozen dotted hash fields to actual file paths")
    parser.add_argument("--variant", choices=PHASE1_VARIANTS, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--recipe", default=DIRECT_RECIPE, help="direct_joint or an explicit frozen strategy.contrasts id")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--resume", help="This run directory's latest.pt only; budgets/config/lineage cannot change")
    return parser.parse_args(argv)


def _link_checkpoint(source, destination):
    if destination.exists():
        raise FileExistsError(f"Refusing to replace retained checkpoint: {destination}")
    try:
        os.link(source, destination)
    except OSError:
        shutil.copy2(source, destination)


def _run_bytes(output):
    # Count unique inodes so retained hard links do not inflate quota usage.
    seen, total = set(), 0
    for path in output.rglob("*"):
        if path.is_symlink():
            # W&B makes latest-run/debug symlinks inside its persistent folder.
            # Never follow links outside this owned run or count linked files
            # twice; retention still operates only on real named checkpoints.
            if not path.is_relative_to(output / "wandb") or not path.resolve().is_relative_to(output) or not path.exists():
                raise RuntimeError("Formal output symlink escapes this owned run")
            continue
        if path.is_file():
            stat = path.stat()
            identity = (stat.st_dev, stat.st_ino)
            if identity not in seen:
                total += stat.st_size
                seen.add(identity)
    return total


def formal_weighted_forward(model, batch, stats, supervision, weights, schedule, step,
                            base_policy, *, recipe=None, recipe_binding=None):
    """The same loss path for CPU tests and the formal loop; no state advance.

    All enabled tasks stay active. A selected recipe supplies only the policy,
    while Phase1JointSchedule's scales, model, LR and optimizer stay unchanged.
    """
    if (recipe is None) != (recipe_binding is None):
        raise ValueError("A formal recipe and its binding must be supplied together")
    snapshot = formal_policy_at_update(recipe_binding, base_policy, step, recipe=recipe) if recipe is not None else None
    if snapshot is not None and snapshot.variant != supervision.variant.canonical_value:
        raise ValueError("Selected joint-weighting recipe differs from actual supervision")
    outputs = model.forward_pretrain(batch, supervision.objectives)
    loss = compute_pretrain_loss(outputs, batch, stats, supervision, weights, schedule, step,
        graph_descriptor_indices=model.graph_descriptor_target_indices, phase1_mode=True,
        phase1_policy=snapshot.policy if snapshot is not None else base_policy)
    return outputs, loss, snapshot


def main(argv=None):
    args = parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    output = Path(args.output_dir).resolve()
    if output.is_relative_to(root):
        raise ValueError("Formal outputs must live outside the source tree to preserve its frozen byte fingerprint")
    checkpoint_path = output / "latest.pt"
    if args.resume and Path(args.resume).resolve() != checkpoint_path:
        raise ValueError("Strict formal resume accepts only output-dir/latest.pt; no older or foreign weights")
    if args.resume:
        if not output.is_dir() or not checkpoint_path.is_file():
            raise FileNotFoundError("Formal resume requires this run's existing latest checkpoint")
        if (output / "fixed_endpoint.pt").exists() or (output / "fixed_endpoint.pt").is_symlink():
            raise RuntimeError("An exported fixed endpoint cannot resume; preserve the existing formal result")
    else:
        output.mkdir(parents=True, exist_ok=False)
    attempt = f"{time.time_ns()}-{os.getpid()}"
    attempt_dir = output / "attempts" / attempt
    attempt_dir.mkdir(parents=True, exist_ok=False)
    lock = output / ".formal_active"
    lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(lock_fd, "w", encoding="utf-8") as handle:
        handle.write(attempt)
    began = time.perf_counter()
    run, clock, model, optimizer, scheduler = None, None, None, None, None
    status, updates, base_exposure, run_id = "failed", 0, 0, None
    cumulative, history = Counter(), []
    journal, manifest, config, source = None, None, None, None
    resume_verified, initialized_journal, tracker_finished, initial_hash, last = False, False, False, None, {}
    latest_sha, tracker_next_step, tracker_run_path, endpoint_owned, endpoint_prepared = None, None, None, False, False
    recipe, recipe_binding = None, None
    try:
        protocol = read_json(args.protocol)
        artifacts = artifact_paths(args.artifacts)
        preserved_cvd = single_gpu_environment(protocol)
        gate = live_gate(protocol, artifacts)
        write_json(attempt_dir / "live_gate.json", gate.to_dict())
        if not gate.may_start_formal_training:
            raise RuntimeError("Formal live allocation gate blocked: " + "; ".join(f"{issue.code}: {issue.message}" for issue in gate.issues))
        execution = read_artifact(protocol, artifacts, "strategy.schedule_sha256")
        config, policy = frozen_execution(protocol, execution, variant=args.variant, seed=args.seed)
        if read_artifact(protocol, artifacts, "strategy.loss_policy_sha256") != policy.to_dict():
            raise ValueError("Frozen loss-policy artifact differs from execution's fixed group/task policy")
        config, recipe, recipe_binding = select_formal_recipe(protocol, artifacts, variant=args.variant, seed=args.seed,
            recipe_id=args.recipe, config=config, base_policy=policy)
        if read_artifact(protocol, artifacts, "tasks.target_manifest_sha256") != target_contract():
            raise ValueError("Frozen task/head manifest differs from the exact Phase 1 targets")
        if read_artifact(protocol, artifacts, "tasks.label_contract_sha256") != label_contract():
            raise ValueError("Frozen label fields/units/masks/views differ from the Phase 1 loss contract")
        source = source_provenance(root)
        verify_source(protocol, artifacts, source)
        split = read_artifact(protocol, artifacts, "data.split_manifest_sha256")
        if split.get("schema_version") != "phase1_split_v1" or set(split) != {"schema_version", "train", "validation"}:
            raise ValueError("Formal split artifact must contain both complete frozen manifests")
        train = StrictManifestDataset(split["train"], atom_encoding="zero_based")
        validation = StrictManifestDataset(split["validation"], atom_encoding="zero_based")
        if train.kind != "train" or validation.kind != "validation" or train.diagnostic_only or validation.diagnostic_only:
            raise ValueError("Formal execution requires full declared train/validation views")
        identity_proof = verify_decontamination(protocol,
            read_artifact(protocol, artifacts, "data.decontamination_sha256"), train, validation,
            read_artifact(protocol, artifacts, "downstream.split_manifest_sha256"),
            artifact_directory=artifacts["data.decontamination_sha256"].parent,
            downstream_directory=artifacts["downstream.split_manifest_sha256"].parent)
        stats, baselines, controls_proof = load_fitted_controls(
            read_artifact(protocol, artifacts, "data.normalization_sha256"),
            read_artifact(protocol, artifacts, "data.normalization_train_ids_sha256"), train, config)
        seed = args.seed
        p, n = config["phase1"], config["schedule"]["max_steps"]
        batch_size = config["training"]["base_molecules_per_batch"]
        manifest = {"purpose": FORMAL_RUN_SCHEMA, "protocol_sha256": protocol["content_sha256"],
            "artifact_sha256": {field: get_path(protocol, field) for field in sorted(artifacts) if not field.startswith("site_")},
            "train": train.summary(), "validation": validation.summary(), "decontamination": identity_proof,
            "controls": controls_proof, "loss_policy": policy.to_dict(), "execution": deepcopy(execution),
            "variant": args.variant, "seed": seed, "checkpoint_selection": "fixed_budget_endpoint",
            "downstream_representation": "SharedBackboneMFM.encode_atoms/H0"}
        if recipe_binding is not None:
            manifest["joint_weighting"] = recipe_binding
        # Every condition is constructed on CPU from the same fresh condition
        # seed. Tracker/data preparation cannot consume its initialization RNG.
        torch.manual_seed(seed)
        model = build_model(config)
        verify_architecture(model, config, read_artifact(protocol, artifacts, "encoder.architecture_sha256"))
        initial_hash = verify_paired_initialization(model,
            read_artifact(protocol, artifacts, f"pretraining.paired_random_initialization.encoder_sha256_by_seed.{seed}"), seed)
        carried_wall = 0.
        if args.resume:
            journal = read_json(output / "budget_journal.json")
            run_id = (output / "wandb_run_id.txt").read_text(encoding="utf-8").strip()
            payload = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
            latest_sha = file_sha256(checkpoint_path)
            carried_wall = validate_formal_resume(payload, expected_manifest=manifest, expected_config=config,
                expected_run_id=run_id, expected_init_hash=initial_hash, journal=journal, checkpoint_sha256=latest_sha)
            updates, base_exposure = payload["optimizer_update_step"], payload["extra"]["base_molecule_exposure"]
            cumulative.update(payload["extra"].get("cumulative_counts", {}))
            tracker_next_step, tracker_run_path = journal["tracker_next_step"], journal["tracker_run_path"]
            del payload
        clock = BudgetClock.from_protocol(protocol, carried_wall_seconds=carried_wall, began=began)
        if not run_id:
            run_id = wandb.util.generate_id()
        def write_journal(state):
            nonlocal journal, initialized_journal
            journal = {"schema_version": FORMAL_RUN_SCHEMA, "status": state, "wandb_run_id": run_id,
                "manifest_sha256": contract_hash(manifest), "paired_initial_H0_sha256": initial_hash,
                "optimizer_update_step": updates, "base_molecule_exposure": base_exposure,
                "latest_checkpoint_sha256": latest_sha, "budget_usage": clock.usage(), "last_attempt": attempt,
                "tracker_next_step": tracker_next_step, "tracker_run_path": tracker_run_path}
            if recipe_binding is not None:
                journal["joint_weighting_state"] = formal_weighting_state(recipe_binding, policy, updates)
            write_json(output / "budget_journal.json", journal)
            initialized_journal = True
        # Bind the validated resume's budget before tracker init, CUDA copies,
        # optimizer construction or strict restore can fail. Such retries must
        # charge allocation time even if no effective optimizer step happened.
        write_journal("starting")
        if args.resume:
            history = read_json(output / "evaluations.json")["evaluations"] if (output / "evaluations.json").is_file() else []
            if not isinstance(history, list) or any(entry["optimizer_update_step"] > updates for entry in history):
                raise RuntimeError("Saved evaluation history is ahead of the latest checkpoint or has an invalid format")
        if clock.exhausted():
            raise RuntimeError("Cumulative wall/GPU-hour budget is exhausted; resume cannot extend it")
        verify_source(protocol, artifacts, source_provenance(root))
        fresh_gate = live_gate(protocol, artifacts)
        write_json(attempt_dir / "prelaunch_live_gate.json", fresh_gate.to_dict())
        if not fresh_gate.may_start_formal_training:
            raise RuntimeError("Formal prelaunch allocation gate blocked after artifact preparation: " + "; ".join(issue.message for issue in fresh_gate.issues))
        torch.set_num_threads(int(get_path(protocol, "compute.cpus_per_task")))
        if os.environ.get("CUDA_VISIBLE_DEVICES") != preserved_cvd or torch.cuda.device_count() != 1 or not torch.cuda.is_available():
            raise RuntimeError("The verified scheduler GPU view changed; one CUDA device is required")
        mode = "online" if get_path(protocol, "tracking.mode") == "online" else "offline"
        if str(get_path(protocol, "tracking.provider")).lower() not in {"wandb", "w&b"}:
            raise ValueError("This runner implements actual W&B tracking only")
        if args.resume and mode != "online":
            raise RuntimeError("Offline W&B resume is unsupported until segment append/sync behavior is verified; no fresh segment fallback")
        run = wandb.init(project=protocol["tracking"].get("project", "phychem-mfm-phase1-formal"),
            entity=protocol["tracking"].get("entity"), mode=mode, dir=str(output), id=run_id,
            resume="must" if args.resume and mode == "online" else None,
            config={"execution": config, "protocol_sha256": protocol["content_sha256"], "manifest_sha256": contract_hash(manifest),
                    "source": source, "slurm_job_id": os.environ["SLURM_JOB_ID"], "attempt": attempt, "resumed_from": args.resume,
                    "recipe_id": args.recipe,
                    "paired_initial_H0_sha256": initial_hash, "scope": "frozen single-GPU formal condition"})
        tracker_next_step, tracker_run_path = verify_tracker_lineage(run, run_id=run_id, mode=mode, resume=bool(args.resume),
            expected_next_step=tracker_next_step, expected_run_path=tracker_run_path)
        actual_tracker_directory = Path(run.dir).resolve()
        if not actual_tracker_directory.is_relative_to(output) or not actual_tracker_directory.is_dir():
            raise RuntimeError("Actual W&B persistent run directory must exist inside this owned output directory")
        run.define_metric("formal/optimizer_update_step")
        run.define_metric("*", step_metric="formal/optimizer_update_step")
        def log(value):
            nonlocal tracker_next_step
            run.log({"formal/optimizer_update_step": updates, **value})
            next_step = run.step
            if next_step != tracker_next_step + 1:
                raise RuntimeError("W&B history did not advance exactly once for a committed log event")
            tracker_next_step = next_step
            write_journal("running")
        (output / "wandb_run_id.txt").write_text(run_id, encoding="utf-8")
        log({"startup/live_gate_pass": 1, "startup/paired_initialization_pass": 1,
             "budget/carried_wall_seconds": carried_wall})
        device = torch.device("cuda:0")
        model.to(device)
        optimizer = build_adamw(model, **{name: config["optimizer"][name] for name in ("lr", "weight_decay", "betas")})
        scheduler = build_warmup_cosine_scheduler(optimizer, total_steps=n, warmup_steps=config["schedule"]["warmup_steps"],
                                                  min_lr_ratio=config["schedule"]["min_lr_ratio"])
        if args.resume:
            load_training_checkpoint(checkpoint_path, model=model, optimizer=optimizer, scheduler=scheduler,
                expected_config=config, expected_dataset_manifest=manifest, expected_source_sha256=source["source_sha256"], strict_semantics=True)
            resume_verified = True
        supervision, evaluation_supervision = SupervisionConfig.from_variant(args.variant), SupervisionConfig.from_variant("SDP")
        schedule, weights = Phase1JointSchedule(), LossWeights.from_mapping(config["loss"])
        torch.cuda.reset_peak_memory_stats(device)
        def views(base):
            return [Phase1ViewDataset(base, mode=name, level=p["geometry_level"] if name == "geom" else p["topology_level"], seed=seed)
                    for name in p["views"]]
        training_views, validation_views = views(train), views(validation)
        permutation = np.random.default_rng(seed).permutation(len(train))
        write_json(attempt_dir / "startup.json", {"manifest_sha256": contract_hash(manifest), "paired_initial_H0_sha256": initial_hash,
                   "order_sha256": contract_hash({"logical_indices": permutation.tolist()}), "resume_verified": resume_verified,
                   "CUDA_VISIBLE_DEVICES": preserved_cvd, "wandb_run_id": run_id, "wandb_directory": run.dir})
        for name, value in (("manifest.json", manifest), ("config.json", config)):
            path = output / name
            if args.resume and read_json(path) != value:
                raise RuntimeError(f"Existing formal run evidence changed: {name}")
            if not args.resume:
                write_json(path, value)
        def storage_check():
            actual = _run_bytes(output)
            if actual >= get_path(protocol, "storage.max_run_bytes"):
                raise RuntimeError("Frozen per-run storage cap reached")
            free = shutil.disk_usage(output).free
            if free <= get_path(protocol, "storage.reserve_bytes"):
                raise RuntimeError("Filesystem reserve reached; formal output cannot grow")
            return actual
        def save(kind, *, periodic=False):
            nonlocal latest_sha
            storage_check()
            extra = {"formal_run_schema": FORMAL_RUN_SCHEMA, "wandb_run_id": run_id, "paired_initial_H0_sha256": initial_hash,
                     "base_molecule_exposure": base_exposure, "cumulative_counts": dict(cumulative), "budget_usage": clock.usage(),
                     "status": status, "evaluation_completion": history[-1]["completion"] if history else "not_evaluated",
                     "attempt": attempt, "resume_verified": resume_verified,
                     "tracker_next_step": tracker_next_step, "tracker_run_path": tracker_run_path}
            if recipe_binding is not None:
                extra["joint_weighting_state"] = formal_weighting_state(recipe_binding, policy, updates)
            save_training_checkpoint(checkpoint_path, model=model, optimizer=optimizer, scheduler=scheduler,
                config=config, supervision=supervision.to_dict(), dataset_manifest=manifest, exposure_step=updates,
                optimizer_update_step=updates, checkpoint_type=kind, project_root=root, source_metadata=source,
                extra=extra)
            latest_sha = file_sha256(checkpoint_path)
            if periodic:
                destination = output / f"periodic_{updates:09d}.pt"
                _link_checkpoint(checkpoint_path, destination)
                retained = sorted(output.glob("periodic_*.pt"))
                for old in retained[:-get_path(protocol, "pretraining.checkpoint_rule.keep_checkpoints")]:
                    # Only this owned run's strictly named retained checkpoints.
                    if old.is_symlink() or old.resolve().parent != output or not old.stem.removeprefix("periodic_").isdigit():
                        raise RuntimeError("Refusing ambiguous checkpoint retention path")
                    with (output / "checkpoint_retention.jsonl").open("a", encoding="utf-8") as stream:
                        stream.write(json.dumps({"path": str(old.resolve()), "bytes": old.stat().st_size,
                            "sha256": file_sha256(old), "reason": "owned periodic checkpoint beyond frozen keep_checkpoints",
                            "optimizer_update_step": updates}, allow_nan=False) + "\n")
                    old.unlink()
            write_journal(status)
            storage_check()
        def make_batch(viewsets, indices):
            records = [view[index] for index in indices for view in viewsets]
            atom_counts = [int(record.x.size(0)) for record in records]
            if any(len(set(atom_counts[first:first + 3])) != 1 for first in range(0, len(atom_counts), 3)):
                raise RuntimeError("Frozen three views changed base molecule atom correspondence")
            check_atom_caps(atom_counts, per_molecule=p["max_atoms_per_molecule"], per_batch=p["max_atoms_per_batch"])
            return fast_collate(records).to(device)
        def evaluate(label):
            model.eval()
            evaluator = OriginalUnitEvaluator(model, baselines, cutoff=weights.cutoff)
            evaluated, started = 0, time.perf_counter()
            for first in range(0, len(validation), batch_size):
                if clock.exhausted():
                    break
                selected = range(first, min(first + batch_size, len(validation)))
                batch = make_batch(validation_views, selected)
                if clock.exhausted():
                    break
                with torch.no_grad():
                    outputs = model.forward_pretrain(batch, evaluation_supervision.objectives)
                    evaluator.add(batch, outputs)
                evaluated += len(selected)
                write_journal("running")
            torch.cuda.synchronize(device)
            complete = evaluated == len(validation) and not clock.exhausted()
            result = {"label": label, "optimizer_update_step": updates, "base_molecule_exposure": base_exposure,
                "completion": "complete" if complete else "incomplete_budget", "evaluated_base_molecules": evaluated,
                "expected_base_molecules": len(validation), "all_heads_evaluated": True,
                "head_training_condition": args.variant, "evaluation_seconds": time.perf_counter() - started, **evaluator.result()}
            # Evaluator's scientific caution is retained; the scope below
            # identifies this frozen run without asserting convergence.
            result["scope"] = "full frozen pretrain validation; no model selection or final-test performance"
            history.append(result)
            write_json(output / "evaluations.json", {"evaluations": history})
            logged = {f"validation/{target}/{estimate}/{metric}": value for target, estimates in result["targets"].items()
                      for estimate, metrics in estimates.items() for metric, value in metrics.items() if isinstance(value, (float, int))}
            logged.update({"validation/complete": int(complete), "validation/base_molecules": evaluated, **{"budget/" + key: value for key, value in clock.usage().items()}})
            log(logged)
            model.train()
            return complete
        status = "running"
        write_journal(status)
        if not args.resume:
            save("initial_random_state")
        initial_complete = evaluate("resume_full_validation" if args.resume else "paired_initialization_full_validation")
        if not initial_complete:
            status = "budget_stop"
        elif args.variant == "none":
            # No backward/optimizer/scheduler step on the random H0 control.
            status = "complete" if evaluate("fixed_budget_endpoint") else "budget_stop"
        else:
            for step in range(updates, n):
                if clock.exhausted():
                    status = "budget_stop"
                    break
                started = time.perf_counter()
                indices = cyclic_batch_indices(permutation, step, batch_size)
                batch = make_batch(training_views, indices)
                fetch_seconds = time.perf_counter() - started
                if clock.exhausted():
                    status = "budget_stop"
                    break
                optimizer.zero_grad(set_to_none=True)
                lr_used = optimizer.param_groups[0]["lr"]
                with torch.random.fork_rng(devices=[0]):
                    torch.manual_seed(seed + step)
                    outputs, loss, policy_snapshot = formal_weighted_forward(model, batch, stats, supervision, weights, schedule,
                        step, policy, recipe=recipe, recipe_binding=recipe_binding)
                    if not loss.total.requires_grad:
                        raise RuntimeError("Enabled condition has no valid labels; no fictitious effective update/exposure is allowed")
                    if not torch.isfinite(loss.total):
                        raise FloatingPointError("Nonfinite formal training loss")
                    loss.total.backward()
                grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), config["optimizer"]["grad_clip_norm"])
                if not torch.isfinite(grad_norm):
                    raise FloatingPointError("Nonfinite formal training gradient")
                if clock.exhausted():
                    optimizer.zero_grad(set_to_none=True)
                    status = "budget_stop"
                    break
                optimizer.step()
                scheduler.step()
                updates += 1
                base_exposure += len(indices)
                cumulative.update(loss.counts)
                torch.cuda.synchronize(device)
                elapsed = time.perf_counter() - started
                last = {**loss.scalar_metrics("train/"), **step_runtime_metrics(optimizer, lr_used=lr_used,
                    exposure_step=updates, optimizer_update_step=updates), "train/base_molecule_exposure": base_exposure,
                    **formal_weighting_metrics(policy_snapshot, recipe_binding),
                    "train/grad_norm": float(grad_norm), "performance/fetch_seconds": fetch_seconds,
                    "performance/full_step_seconds": elapsed, "performance/base_molecules_per_second": len(indices) / max(elapsed, 1e-12),
                    "resources/gpu_allocated_bytes": torch.cuda.memory_allocated(device),
                    "resources/gpu_reserved_bytes": torch.cuda.memory_reserved(device),
                    "resources/peak_gpu_allocated_bytes": torch.cuda.max_memory_allocated(device),
                    **{"budget/" + key: value for key, value in clock.usage().items()}}
                log(last)
                with (attempt_dir / "steps.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps({"step": updates, **last}, allow_nan=False) + "\n")
                write_journal("running")
                if updates % get_path(protocol, "pretraining.checkpoint_rule.save_every_steps") == 0:
                    save("periodic", periodic=True)
                if updates % execution["evaluation"]["every_updates"] == 0 and updates < n:
                    if not evaluate("fixed_update_interval"):
                        status = "budget_stop"
                        break
            if status == "running":
                expected_exposures = get_path(protocol, "pretraining.budget.structures_per_condition")
                if updates != n or base_exposure != expected_exposures:
                    raise RuntimeError("Fixed-budget counters did not reach the frozen endpoint")
                status = "complete" if evaluate("fixed_budget_endpoint") else "budget_stop"
        if clock.exhausted():
            status = "budget_stop"
        candidate_complete = status == "complete"
        if args.variant == "none" and backbone_state_hash(model) != initial_hash:
            raise RuntimeError("None control's final shared H0 differs from its paired random initialization")
        status = "finalizing" if candidate_complete else "budget_stop"
        if not candidate_complete:
            save("budget_stop")
        summary = {"schema_version": FORMAL_RUN_SCHEMA, "status": status, "variant": args.variant, "seed": seed,
            "recipe_id": args.recipe,
            "optimizer_update_step": updates, "base_molecule_exposure": base_exposure, "budget_usage": clock.usage(),
            "cumulative_counts": dict(cumulative), "paired_initial_H0_sha256": initial_hash, "wandb_run_id": run_id,
            "wandb_mode": mode, "wandb_directory": run.dir, "source": source, "manifest_sha256": contract_hash(manifest),
            "latest_checkpoint": str(checkpoint_path), "fixed_endpoint_checkpoint": None,
            "selection_rule": "fixed_budget_endpoint; no validation-best selection", "resume_verified": resume_verified,
            "tracker_next_step": tracker_next_step, "tracker_run_path": tracker_run_path,
            "peak_gpu_allocated_bytes": torch.cuda.max_memory_allocated(device), "run_storage_bytes": _run_bytes(output), "last_step": last}
        if recipe_binding is not None:
            summary["joint_weighting"] = recipe_binding
        try:
            import resource
            summary["peak_process_rss_KiB"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        except ImportError:
            summary["peak_process_rss_KiB"] = None
        write_json(output / "summary.json", summary)
        run.summary.update({key: value for key, value in summary.items() if isinstance(value, (str, int, float, bool))})
        run.summary.update({"scientific_endpoint_complete": candidate_complete,
                            "final_endpoint_publication": "after successful tracker finish and final local budget/storage checks"})
        def finish_tracker():
            nonlocal tracker_finished
            # Mark the call attempted first: a failed finish must not silently
            # retry/close another segment. The outer failure path preserves it.
            finish_status = "complete" if candidate_complete and not clock.exhausted() else "budget_stop"
            run.summary.update({"status": finish_status, "budget_wall_seconds": clock.usage()["wall_seconds"],
                                "final_endpoint_publication": "prepared; atomic publish after successful tracker finish" if finish_status == "complete" else "not eligible"})
            tracker_finished = True
            run.finish(exit_code=0 if finish_status == "complete" else 1)
        def revoke_endpoint():
            endpoint = output / "fixed_endpoint.pt"
            if endpoint_owned and endpoint.is_file() and not endpoint.is_symlink():
                endpoint.unlink()
            prepared = output / "endpoint.pending.pt"
            if endpoint_prepared and prepared.is_file() and not prepared.is_symlink():
                prepared.unlink()
        def publish_endpoint():
            nonlocal endpoint_owned
            endpoint = output / "fixed_endpoint.pt"
            if endpoint.exists() or endpoint.is_symlink():
                raise FileExistsError("Refusing to replace an existing formal endpoint")
            endpoint_owned = True
            (output / "endpoint.pending.pt").replace(endpoint)
        def save_endpoint():
            nonlocal endpoint_prepared
            save("fixed_budget_endpoint")
            prepared = output / "endpoint.pending.pt"
            if prepared.exists() or prepared.is_symlink():
                raise FileExistsError("Refusing to replace unexpected pending endpoint evidence")
            endpoint_prepared = True
            _link_checkpoint(checkpoint_path, prepared)
            storage_check()
        status = finalize_endpoint(candidate_complete=candidate_complete, finish_tracker=finish_tracker,
            save_endpoint=save_endpoint, publish_endpoint=publish_endpoint,
            revoke_endpoint=revoke_endpoint, clock=clock)
        storage_check()
        summary.update(status=status, budget_usage=clock.usage(), run_storage_bytes=_run_bytes(output),
                       fixed_endpoint_checkpoint=str(output / "fixed_endpoint.pt") if status == "complete" else None)
        write_json(output / "summary.json", summary)
        write_journal(status)
    except BaseException as error:
        status = "failed"
        failure = {"schema_version": FORMAL_RUN_SCHEMA, "status": "failed", "type": type(error).__name__, "reason": str(error),
            "recipe_id": args.recipe,
            "optimizer_update_step": updates, "base_molecule_exposure": base_exposure, "attempt_seconds": time.perf_counter() - began,
            "resume_verified": resume_verified, "resumed_from": args.resume, "wandb_run_id": run_id}
        if clock is not None:
            failure["budget_usage"] = clock.usage()
        write_json(attempt_dir / "failure.json", failure)
        if initialized_journal:
            journal.update(status="failed", optimizer_update_step=updates, base_molecule_exposure=base_exposure, budget_usage=clock.usage())
            if recipe_binding is not None:
                journal["joint_weighting_state"] = formal_weighting_state(recipe_binding, policy, updates)
            write_json(output / "budget_journal.json", journal)
        endpoint = output / "fixed_endpoint.pt"
        if endpoint_owned and endpoint.is_file() and not endpoint.is_symlink():
            endpoint.unlink()
        prepared = output / "endpoint.pending.pt"
        if endpoint_prepared and prepared.is_file() and not prepared.is_symlink():
            prepared.unlink()
        if (output / "summary.json").is_file() and initialized_journal:
            summary = read_json(output / "summary.json")
            summary.update(status="failed", fixed_endpoint_checkpoint=None, failure_reason=str(error))
            write_json(output / "summary.json", summary)
        if run is not None and not tracker_finished:
            run.summary.update({"status": "failed", "failure_type": type(error).__name__, "failure_reason": str(error), "attempt": attempt})
        raise
    finally:
        try:
            if run is not None and not tracker_finished:
                tracker_finished = True
                run.finish(exit_code=0 if status == "complete" else 1)
        except BaseException as error:
            status = "failed"
            endpoint = output / "fixed_endpoint.pt"
            if endpoint_owned and endpoint.is_file() and not endpoint.is_symlink():
                endpoint.unlink()
            prepared = output / "endpoint.pending.pt"
            if endpoint_prepared and prepared.is_file() and not prepared.is_symlink():
                prepared.unlink()
            write_json(attempt_dir / "tracker_finish_failure.json", {"schema_version": FORMAL_RUN_SCHEMA,
                       "status": status, "recipe_id": args.recipe, "type": type(error).__name__, "reason": str(error)})
            raise
        finally:
            # Charge tracker/checkpoint finalization too. This journal is the
            # budget authority on resume; its usage can exceed a checkpoint's.
            if initialized_journal and clock is not None:
                journal.update(status=status, budget_usage=clock.usage())
                if clock.exhausted() and status == "complete":
                    status = "budget_stop"
                    journal["status"] = "budget_stop"
                    endpoint = output / "fixed_endpoint.pt"
                    if endpoint_owned and endpoint.is_file() and not endpoint.is_symlink():
                        endpoint.unlink()
                if (output / "summary.json").is_file():
                    summary = read_json(output / "summary.json")
                    summary.update(status=status, budget_usage=clock.usage(),
                                   fixed_endpoint_checkpoint=str(output / "fixed_endpoint.pt") if status == "complete" else None)
                    write_json(output / "summary.json", summary)
                write_json(output / "budget_journal.json", journal)
            if lock.exists() and lock.read_text(encoding="utf-8") == attempt:
                lock.unlink()
    print(json.dumps(read_json(output / "summary.json"), indent=2, allow_nan=False))
    return 0 if status == "complete" and not clock.exhausted() else 2


if __name__ == "__main__":
    raise SystemExit(main())
