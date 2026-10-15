#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import logging
import random
from pathlib import Path

import numpy as np
import torch

from phychem_mfm.config import load_experiment_config
from phychem_mfm.factory import build_model
from phychem_mfm.supervision import SupervisionConfig
from phychem_mfm.training.datasets import build_pilot_data
from phychem_mfm.training.engine import run_training
from phychem_mfm.training.losses import LossWeights, StageSchedule
from phychem_mfm.training.optim import build_adamw, build_warmup_cosine_scheduler


def parse_args():
    parser = argparse.ArgumentParser("Shared-backbone PhyChem-MFM pilot trainer")
    parser.add_argument("--config", default="configs/iclr2027/base.yaml")
    parser.add_argument("--task-route", choices=("light", "expert"), required=True)
    parser.add_argument("--supervision-variant", choices=("S", "P", "D", "SP", "SD", "SPD"), default="SPD")
    parser.add_argument("--data-root", default=None)
    parser.add_argument("--train-limit", type=int, default=4096)
    parser.add_argument("--val-limit", type=int, default=512)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--num-workers", type=int, default=None)
    parser.add_argument("--max-steps", type=int, required=True)
    parser.add_argument("--validate-every", type=int, default=500)
    parser.add_argument("--max-val-batches", type=int, default=16)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--run-name", required=True)
    parser.add_argument("--wandb-project", default="phychem-mfm-iclr2027")
    parser.add_argument("--wandb-mode", choices=("online", "offline", "disabled"), default="offline")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--resume-from", default=None)
    parser.add_argument("--tiny-schedule", action="store_true", help="Level-A only: expose descriptors immediately")
    parser.add_argument("--clean-only", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    project_root = Path(__file__).resolve().parents[1]
    experiment = load_experiment_config(project_root / args.config)
    config = experiment.to_dict()
    config["architecture"]["preset"] = f"shared_{args.task_route}"
    config["architecture"]["task_route"] = args.task_route
    config["supervision"]["variant"] = args.supervision_variant
    if args.data_root:
        config["dataset"]["root"] = args.data_root
    if args.batch_size is not None:
        config["training"]["batch_size"] = args.batch_size
    if args.num_workers is not None:
        config["training"]["num_workers"] = args.num_workers
    config["pilot"] = {
        "max_steps": args.max_steps,
        "train_limit": args.train_limit,
        "val_limit": args.val_limit,
        "validate_every": args.validate_every,
        "max_val_batches": args.max_val_batches,
        "tiny_schedule": bool(args.tiny_schedule),
        "clean_only": bool(args.clean_only),
    }
    if args.tiny_schedule:
        config["schedule"].update(
            {
                "stage1_max_steps": 0,
                "descriptor_ramp_steps": 1,
                "stage1_decay_steps": 0,
                "stage1_floor": 1.0,
                "max_steps": args.max_steps,
                "warmup_fraction": 0.0,
            }
        )

    seed = int(config["training"]["seed"])
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    device = torch.device(args.device)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")

    model = build_model(config, preset=args.task_route)
    config["architecture"]["task_route_per_task"] = model.task_route_config.to_dict()
    supervision = SupervisionConfig.from_variant(args.supervision_variant)
    weights = LossWeights.from_mapping(config["loss"])
    schedule = StageSchedule.from_mapping(config["schedule"])
    data = build_pilot_data(
        config["dataset"]["root"],
        train_limit=args.train_limit,
        val_limit=args.val_limit,
        batch_size=int(config["training"]["batch_size"]),
        num_workers=int(config["training"]["num_workers"]),
        seed=seed,
        include_historical_perturb_mix=not args.clean_only,
        atom_budget_per_batch=int(config["training"]["atom_budget_per_batch"]),
    )
    optimizer = build_adamw(
        model,
        lr=float(config["optimizer"]["lr"]),
        weight_decay=float(config["optimizer"]["weight_decay"]),
        betas=config["optimizer"]["betas"],
    )
    scheduler = build_warmup_cosine_scheduler(
        optimizer,
        total_steps=int(config["schedule"]["max_steps"]),
        warmup_steps=round(int(config["schedule"]["max_steps"]) * float(config["schedule"]["warmup_fraction"])),
    )

    wandb_run = None
    if args.wandb_mode != "disabled":
        import wandb

        wandb_run = wandb.init(
            project=args.wandb_project,
            name=args.run_name,
            mode=args.wandb_mode,
            dir=str(Path(args.run_dir).resolve()),
            config={**config, "dataset_manifest": data.manifest},
            tags=["iclr2027", "shared-backbone", args.task_route, args.supervision_variant],
        )
    try:
        summary = run_training(
            model=model,
            data_bundle=data,
            optimizer=optimizer,
            scheduler=scheduler,
            config=config,
            supervision=supervision,
            weights=weights,
            schedule=schedule,
            device=device,
            max_steps=args.max_steps,
            validate_every=args.validate_every,
            max_val_batches=args.max_val_batches,
            run_dir=args.run_dir,
            project_root=project_root,
            wandb_run=wandb_run,
            resume_from=args.resume_from,
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
    finally:
        if wandb_run is not None:
            wandb_run.finish()


if __name__ == "__main__":
    main()
