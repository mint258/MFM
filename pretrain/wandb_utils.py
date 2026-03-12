from __future__ import annotations

import os
from typing import Any, Mapping

try:
    import wandb
except ImportError:  # pragma: no cover - handled at runtime when W&B is requested.
    wandb = None


def is_wandb_enabled(args) -> bool:
    return bool(getattr(args, "use_wandb", False)) and getattr(args, "wandb_mode", "disabled") != "disabled"


def _require_wandb():
    if wandb is None:
        raise ImportError("wandb is not installed. Install it or disable --use_wandb.")
    return wandb


def _coerce_scalar(value: Any):
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str)):
        return value
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def init_wandb_run(args, *, model, device: str, train_size: int, val_size: int):
    if not is_wandb_enabled(args):
        return None

    wb = _require_wandb()
    config = dict(vars(args))
    config.update(
        {
            "device": device,
            "train_size": int(train_size),
            "val_size": int(val_size),
            "retired_losses": ["lambda_coord", "lambda_planar"],
            "retired_metrics": ["RMSD"],
        }
    )

    run = wb.init(
        project=args.wandb_project,
        entity=args.wandb_entity or None,
        name=args.wandb_run_name or None,
        group=args.wandb_group or None,
        tags=args.wandb_tags or None,
        notes=args.wandb_notes or None,
        dir=args.wandb_dir or None,
        job_type="pretrain",
        config=config,
        mode=args.wandb_mode,
        save_code=True,
    )
    run.define_metric("epoch")
    run.define_metric("global_step")
    run.define_metric("train/batch/*", step_metric="global_step")
    run.define_metric("train/epoch/*", step_metric="epoch")
    run.define_metric("val/*", step_metric="epoch")
    run.define_metric("meta/*", step_metric="epoch")

    if getattr(args, "wandb_watch", "none") != "none":
        wb.watch(model, log=args.wandb_watch, log_freq=args.wandb_watch_log_freq)

    return run


def log_metrics(run, prefix: str, metrics: Mapping[str, Any], *, epoch: int | None = None, global_step: int | None = None) -> None:
    if run is None:
        return

    payload = {}
    if epoch is not None:
        payload["epoch"] = int(epoch)
    if global_step is not None:
        payload["global_step"] = int(global_step)

    for key, value in metrics.items():
        scalar = _coerce_scalar(value)
        if scalar is None:
            continue
        payload[f"{prefix}/{key}"] = scalar

    if payload:
        run.log(payload)


def update_summary(run, metrics: Mapping[str, Any]) -> None:
    if run is None:
        return

    for key, value in metrics.items():
        scalar = _coerce_scalar(value)
        if scalar is None:
            continue
        run.summary[key] = scalar


def log_checkpoint_artifact(run, checkpoint_path: str, *, label: str, aliases=None, metadata=None) -> None:
    if run is None or not os.path.exists(checkpoint_path):
        return

    wb = _require_wandb()
    artifact = wb.Artifact(
        name=f"checkpoint-{run.id}",
        type="model",
        metadata={"label": label, **(metadata or {})},
    )
    artifact.add_file(checkpoint_path, name=os.path.basename(checkpoint_path))
    run.log_artifact(artifact, aliases=list(aliases or []))


def finish_run(run) -> None:
    if run is not None:
        run.finish()
