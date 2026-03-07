from __future__ import annotations

import os

import torch


def save_checkpoint(model, cfg, std, save_path: str) -> None:
    """Save unified checkpoint with config, weights, and normalization stats."""
    save_dir = os.path.dirname(save_path)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)

    torch.save(
        {
            "cfg": cfg,
            "model_state": {k: v.cpu() for k, v in model.state_dict().items()},
            "standardizer": std,
        },
        save_path,
    )
