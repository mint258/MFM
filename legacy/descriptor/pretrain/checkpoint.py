from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import torch

from .dist_utils import unwrap_model
from .utils import write_json


CHECKPOINT_FORMAT_VERSION = 2


def _to_cpu(value: Any):
    if isinstance(value, torch.Tensor):
        return value.detach().cpu()
    if isinstance(value, dict):
        return {key: _to_cpu(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_cpu(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_to_cpu(item) for item in value)
    return value


def ensure_parent_dir(save_path: str) -> None:
    save_dir = os.path.dirname(save_path)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)


def resolve_checkpoint_paths(save_path: str, checkpoint_dir: str | None = None) -> dict[str, str]:
    best_path = str(Path(save_path).resolve())
    root_dir = str(Path(checkpoint_dir).resolve()) if checkpoint_dir else str(Path(best_path).parent.resolve())
    archive_dir = str((Path(root_dir) / "archive").resolve())

    os.makedirs(root_dir, exist_ok=True)
    os.makedirs(archive_dir, exist_ok=True)

    return {
        "root_dir": root_dir,
        "best_path": best_path,
        "latest_path": str((Path(root_dir) / "latest.pt").resolve()),
        "final_path": str((Path(root_dir) / "final.pt").resolve()),
        "archive_dir": archive_dir,
    }


def save_checkpoint(
    model,
    model_cfg,
    standardizer,
    save_path: str,
    *,
    train_cfg: dict | None = None,
    optimizer=None,
    scheduler=None,
    current_epoch: int = 1,
    epoch_step: int = 0,
    global_step: int = 0,
    current_stage: int = 0,
    stage_step: int = 0,
    best_selection_loss: float = float("inf"),
    checkpoint_kind: str = "generic",
    metadata: dict | None = None,
) -> None:
    """Save a resumable checkpoint with model, optimizer, scheduler, and runtime state."""
    ensure_parent_dir(save_path)

    state_model = unwrap_model(model)
    payload = {
        "format_version": CHECKPOINT_FORMAT_VERSION,
        "checkpoint_kind": checkpoint_kind,
        "cfg": dict(train_cfg or {}),
        "model_cfg": dict(model_cfg or {}),
        "model_state": _to_cpu(state_model.state_dict()),
        "optimizer_state": (_to_cpu(optimizer.state_dict()) if optimizer is not None else None),
        "scheduler_state": (_to_cpu(scheduler.state_dict()) if scheduler is not None else None),
        "standardizer": _to_cpu(standardizer),
        "current_epoch": int(current_epoch),
        "epoch_step": int(epoch_step),
        "global_step": int(global_step),
        "current_stage": int(current_stage),
        "stage_step": int(stage_step),
        "best_selection_loss": float(best_selection_loss),
        "metadata": _to_cpu(dict(metadata or {})),
    }
    torch.save(payload, save_path)
    sidecar_path = Path(save_path).with_suffix(Path(save_path).suffix + ".meta.json")
    write_json(
        sidecar_path,
        {
            "format_version": CHECKPOINT_FORMAT_VERSION,
            "checkpoint_kind": checkpoint_kind,
            "save_path": str(Path(save_path).resolve()),
            "current_epoch": int(current_epoch),
            "epoch_step": int(epoch_step),
            "global_step": int(global_step),
            "current_stage": int(current_stage),
            "stage_step": int(stage_step),
            "best_selection_loss": float(best_selection_loss),
            "metadata": dict(metadata or {}),
        },
    )


def load_checkpoint(checkpoint_path: str, *, map_location: str | torch.device = "cpu") -> dict:
    payload = torch.load(checkpoint_path, map_location=map_location)
    if "format_version" not in payload:
        # Backward compatibility for older minimal checkpoints.
        payload = {
            "format_version": 1,
            "checkpoint_kind": "legacy",
            "cfg": payload.get("cfg", {}),
            "model_cfg": payload.get("cfg", {}),
            "model_state": payload.get("model_state"),
            "optimizer_state": None,
            "scheduler_state": None,
            "standardizer": payload.get("standardizer"),
            "current_epoch": 1,
            "epoch_step": 0,
            "global_step": 0,
            "current_stage": 0,
            "stage_step": 0,
            "best_selection_loss": float("inf"),
        }
    return payload
