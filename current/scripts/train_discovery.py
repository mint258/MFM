#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import numpy as np
import torch

from phychem_mfm.config import load_experiment_config
from phychem_mfm.discovery.convergence import ConvergenceGate
from phychem_mfm.discovery.engine import run_discovery_training
from phychem_mfm.discovery.identity import recipe_hash, scientific_recipe
from phychem_mfm.discovery.manifests import build_discovery_data, load_manifest
from phychem_mfm.discovery.registry import ExperimentRegistry
from phychem_mfm.discovery.schedule import DataProgressSchedule
from phychem_mfm.factory import build_model
from phychem_mfm.evaluation.fidelity import TargetFidelityRegistry
from phychem_mfm.evaluation.target_adequacy import PretrainingTargetAdequacyEvaluator
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.checkpoint import environment_fingerprint, source_provenance
from phychem_mfm.training.losses import LossWeights
from phychem_mfm.training.optim import build_adamw, build_warmup_cosine_scheduler


SCHEDULES = {
    "delayed": {
        "name": "delayed_v1",
        "descriptor_start_fraction_of_pass": 0.10,
        "descriptor_ramp_fraction_of_pass": 0.03,
        "stage1_decay_fraction_of_pass": 0.03,
        "stage1_floor": 0.3,
    },
    "joint_ramp": {
        "name": "joint_ramp_v1",
        "descriptor_start_fraction_of_pass": 0.0,
        "descriptor_ramp_fraction_of_pass": 0.13,
        "stage1_decay_fraction_of_pass": 0.13,
        "stage1_floor": 0.3,
    },
    "joint_full": {
        "name": "joint_full_v1",
        "descriptor_start_fraction_of_pass": 0.0,
        "descriptor_ramp_fraction_of_pass": 0.0,
        "stage1_decay_fraction_of_pass": 0.0,
        "stage1_floor": 0.3,
    },
}


def parse_args():
    parser = argparse.ArgumentParser("Fixed-pool, variable-pass discovery trainer")
    parser.add_argument("--config", default="configs/iclr2027/mini_archsearch_v1.yaml")
    parser.add_argument("--train-manifest", required=True)
    parser.add_argument("--validation-manifest", required=True)
    parser.add_argument(
        "--standardizer-manifest",
        default=None,
        help="Fixed reference pool for comparable target scaling across nested data-volume runs.",
    )
    parser.add_argument("--task-route", choices=("light", "expert", "hybrid_g", "hybrid_qg"), required=True)
    parser.add_argument("--descriptor-schedule", choices=tuple(SCHEDULES), required=True)
    parser.add_argument("--registry", default="registry/discovery_registry.json")
    parser.add_argument("--run-root", default="runs/discovery_v2")
    parser.add_argument("--wandb-project", default="phychem-mfm-iclr2027-discovery")
    parser.add_argument("--wandb-mode", choices=("online", "offline", "disabled"), default="offline")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--max-passes", type=int, default=None)
    parser.add_argument(
        "--stop-after-pass",
        type=int,
        default=None,
        help="Runtime-only early return used by one-pass calibration; MAX_DISCOVERY_PASSES and LR stay canonical.",
    )
    parser.add_argument("--resume-from", default=None)
    parser.add_argument("--max-val-batches", type=int, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--threshold-registry",
        default="configs/iclr2027/target_fidelity_registry_v3.json",
    )
    return parser.parse_args()


def route_label(route: str) -> str:
    return {"light": "Light-all", "expert": "Expert-all", "hybrid_g": "Hybrid-G", "hybrid_qg": "Hybrid-QG"}[route]


def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    config = load_experiment_config(project_root / args.config).to_dict()
    train_manifest = load_manifest(args.train_manifest)
    validation_manifest = load_manifest(args.validation_manifest)
    standardizer_manifest = load_manifest(args.standardizer_manifest) if args.standardizer_manifest else train_manifest
    structures_per_pass = int(train_manifest["unique_structure_count"])
    domain_valid = str(train_manifest.get("domain_protocol_version", "")).startswith("domain-matched-v3")
    quality_valid = str(train_manifest.get("data_quality_protocol_version", "")).startswith("data-quality-v3")
    v3_validity = "VALID" if domain_valid and quality_valid else (
        "UNREVIEWED_DATA_QUALITY" if domain_valid else "UNREVIEWED"
    )

    config["architecture"]["preset"] = args.task_route
    config["architecture"]["task_route"] = args.task_route
    config["schedule"] = {"candidate": args.descriptor_schedule, **SCHEDULES[args.descriptor_schedule]}
    max_passes = int(args.max_passes or config["training"]["max_passes"])
    config["training"]["max_passes"] = max_passes
    config["dataset"] = {
        "train_pool_id": train_manifest["pool_id"],
        "train_pool_hash": train_manifest["pool_hash"],
        "validation_pool_id": validation_manifest["pool_id"],
        "validation_pool_hash": validation_manifest["pool_hash"],
        "domain_protocol_version": train_manifest.get("domain_protocol_version", "unknown"),
        "data_quality_protocol_version": train_manifest.get("data_quality_protocol_version", "unknown"),
        "data_quality_policy_hash": train_manifest.get("data_quality_policy_hash"),
        "validation_manifest_hash": validation_manifest["pool_hash"],
        "target_adequacy_version": "pretraining-target-adequacy-v3.1",
        "downstream_protocol_version": None,
        "v3_validity": v3_validity,
        "standardizer_reference_pool_hash": standardizer_manifest["pool_hash"],
    }
    schedule = DataProgressSchedule.from_mapping(config["schedule"], structures_per_pass=structures_per_pass)
    config["schedule"] = schedule.to_dict()

    if args.seed is not None:
        config["training"]["seed"] = int(args.seed)
    seed = int(config["training"]["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    model = build_model(config, preset=args.task_route)
    config["architecture"]["task_route_per_task"] = model.task_route_config.to_dict()
    recipe = recipe_hash(
        config,
        train_pool_hash=str(train_manifest["pool_hash"]),
        validation_pool_hash=str(validation_manifest["pool_hash"]),
    )
    experiment_id = f"{train_manifest['pool_id'].lower()}-{args.task_route}-{args.descriptor_schedule}-{recipe[:10]}"
    provenance = source_provenance(project_root)
    run_manifest = {
        "experiment_id": experiment_id,
        "recipe_hash": recipe,
        "recipe": scientific_recipe(
            config,
            train_pool_hash=str(train_manifest["pool_hash"]),
            validation_pool_hash=str(validation_manifest["pool_hash"]),
        ),
        "architecture_type": model.architecture_type,
        "model_scale": config["training"]["model_scale"],
        "hidden_dim": config["backbone"]["dim"],
        "backbone_layers": config["backbone"]["layers"],
        "backbone_heads": config["backbone"]["heads"],
        "task_route": route_label(args.task_route),
        "per_task_route": model.task_route_config.to_dict(),
        "expert_layers": config["expert"]["real_layers"],
        "expert_heads": config["expert"]["heads"],
        "supervision_variant": "SPD",
        "descriptor_schedule": schedule.to_dict(),
        "loss_weights": config["loss"],
        "optimizer": config["optimizer"]["name"],
        "learning_rate": config["optimizer"]["lr"],
        "warmup": config["training"]["warmup_fraction"],
        "min_lr_ratio": config["optimizer"]["min_lr_ratio"],
        "dataset_root": train_manifest["data_root"],
        "dataset_manifest_hash": f"{train_manifest['pool_hash']}:{validation_manifest['pool_hash']}",
        "train_pool_id": train_manifest["pool_id"],
        "validation_pool_id": validation_manifest["pool_id"],
        "train_pool_hash": train_manifest["pool_hash"],
        "validation_pool_hash": validation_manifest["pool_hash"],
        "domain_protocol_version": train_manifest.get("domain_protocol_version", "unknown"),
        "data_quality_protocol_version": train_manifest.get("data_quality_protocol_version", "unknown"),
        "data_quality_policy_hash": train_manifest.get("data_quality_policy_hash"),
        "validation_manifest_hash": validation_manifest["pool_hash"],
        "target_adequacy_version": "pretraining-target-adequacy-v3.1",
        "downstream_protocol_version": None,
        "v3_validity": v3_validity,
        "unique_structure_count": train_manifest["unique_structure_count"],
        "unique_molecule_count": train_manifest["unique_molecule_count"],
        "pass_count": 0,
        "cumulative_structure_exposure": 0,
        "atom_exposure": 0,
        "optimizer_update_step": 0,
        "perturbation_config": config["perturbation"],
        "seed": seed,
        "source_commit": provenance["git_commit"],
        "source_dirty": provenance["git_dirty"],
        "source_sha256": provenance["source_sha256"],
        "environment": environment_fingerprint(),
        "checkpoint_exposure": None,
        "checkpoint_pass": None,
        "checkpoint_sha256": None,
        "convergence_status": "NOT_STARTED",
        "transfer_ready_status": False,
        "downstream_evaluated": False,
        "result_paths": {},
    }
    registry = ExperimentRegistry(args.registry)
    ready_matches = registry.query_reusable(recipe, "transfer_ready")
    if ready_matches:
        print(json.dumps({"status": "EXACT_REUSABLE", "checkpoints": ready_matches}, indent=2, sort_keys=True))
        return
    same_recipe_checkpoints = [
        item
        for item in registry.payload["checkpoints"].values()
        if item.get("recipe_hash") == recipe and Path(str(item.get("path", ""))).is_file()
    ]
    if not args.resume_from and same_recipe_checkpoints:
        completed = [item for item in same_recipe_checkpoints if item.get("checkpoint_state") == "pass_end"]
        if completed:
            latest_completed = max(completed, key=lambda item: int(item.get("checkpoint_pass", 0)))
            if args.stop_after_pass and int(latest_completed.get("checkpoint_pass", 0)) >= int(args.stop_after_pass):
                print(json.dumps({"status": "EXACT_REUSABLE_FIRST_PASS", "checkpoint": latest_completed}, indent=2, sort_keys=True))
                return
            if (
                int(latest_completed.get("checkpoint_pass", 0)) >= max_passes
                and (
                    latest_completed.get("budget_status") == "BUDGET_LIMIT_REACHED"
                    or latest_completed.get("convergence_status") == "CONVERGENCE_FAILED"
                )
            ):
                print(json.dumps({"status": "EXACT_COMPLETE_NOT_READY", "checkpoint": latest_completed}, indent=2, sort_keys=True))
                return
        args.resume_from = str(max(same_recipe_checkpoints, key=lambda item: int(item.get("optimizer_update_step", 0)))["path"])
    if experiment_id not in registry.payload["experiments"]:
        registry.register_experiment(run_manifest)

    data = build_discovery_data(
        train_manifest,
        validation_manifest,
        batch_size=int(config["training"]["batch_size"]),
        atom_budget_per_batch=int(config["training"]["atom_budget_per_batch"]),
        num_workers=int(config["training"]["num_workers"]),
        seed=seed,
        standardizer_reference_manifest=standardizer_manifest,
    )
    adequacy_evaluator = PretrainingTargetAdequacyEvaluator(
        model=model,
        active_objectives=SupervisionConfig.from_variant("SPD").objectives,
        standardizers=data.standardizers,
        threshold_registry=TargetFidelityRegistry.load(project_root / args.threshold_registry),
        device=torch.device(args.device),
        geometry_local_cutoff=float(config["loss"]["cutoff"]),
    )
    total_steps = len(data.train_loader) * max_passes
    warmup_steps = round(total_steps * float(config["training"]["warmup_fraction"]))
    config["training"]["steps_per_pass"] = len(data.train_loader)
    config["training"]["warmup_steps"] = warmup_steps
    config["training"]["total_scheduler_steps"] = total_steps
    optimizer = build_adamw(
        model,
        lr=float(config["optimizer"]["lr"]),
        weight_decay=float(config["optimizer"]["weight_decay"]),
        betas=config["optimizer"]["betas"],
    )
    scheduler = build_warmup_cosine_scheduler(
        optimizer,
        total_steps=total_steps,
        warmup_steps=warmup_steps,
        min_lr_ratio=float(config["optimizer"]["min_lr_ratio"]),
    )
    gate = ConvergenceGate(**config["convergence_gate"])
    run_dir = Path(args.run_root).resolve() / experiment_id
    wandb_run = None
    if args.wandb_mode != "disabled":
        import wandb

        wandb_run = wandb.init(
            project=args.wandb_project,
            name=experiment_id,
            mode=args.wandb_mode,
            dir=str(run_dir),
            config=run_manifest,
            tags=["iclr2027", "pre-ablation-discovery", args.task_route, args.descriptor_schedule, train_manifest["pool_id"]],
        )
    try:
        summary = run_discovery_training(
            model=model,
            data_bundle=data,
            optimizer=optimizer,
            scheduler=scheduler,
            config=config,
            supervision=SupervisionConfig.from_variant("SPD"),
            weights=LossWeights.from_mapping(config["loss"]),
            schedule=schedule,
            convergence_gate=gate,
            device=torch.device(args.device),
            max_passes=max_passes,
            stop_after_pass=args.stop_after_pass,
            validation_points_per_pass=int(config["training"]["validation_points_per_pass"]),
            max_val_batches=int(args.max_val_batches or config["training"]["max_val_batches"]),
            run_dir=run_dir,
            project_root=project_root,
            run_manifest=run_manifest,
            registry=registry,
            target_adequacy_evaluator=adequacy_evaluator,
            wandb_run=wandb_run,
            resume_from=args.resume_from,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
    finally:
        if wandb_run is not None:
            wandb_run.finish()


if __name__ == "__main__":
    main()
