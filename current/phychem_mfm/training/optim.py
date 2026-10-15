from __future__ import annotations

import math

import torch
import torch.nn as nn


class ExposureWarmupCosineScheduler:
    """Warmup/cosine LR indexed by data exposure, not optimizer updates.

    Descriptor-only training intentionally has no optimizer updates before the
    descriptor objective is enabled.  A standard PyTorch scheduler warns (and
    conceptually keys itself to optimizer steps) in that case, so this small
    scheduler makes the intended exposure-step clock explicit.
    """

    def __init__(self, optimizer, *, total_steps: int, warmup_steps: int, min_lr_ratio: float = 0.0):
        self.optimizer = optimizer
        self.total_steps = max(1, int(total_steps))
        self.warmup_steps = max(0, min(int(warmup_steps), self.total_steps))
        self.min_lr_ratio = float(min_lr_ratio)
        if not 0.0 <= self.min_lr_ratio <= 1.0:
            raise ValueError("min_lr_ratio must be in [0, 1]")
        self.base_lrs = [float(group["lr"]) for group in optimizer.param_groups]
        self.last_epoch = 0
        self._last_lr: list[float] = []
        self._apply(self.last_epoch)

    def _factor(self, step: int) -> float:
        if self.warmup_steps > 0 and step < self.warmup_steps:
            return float(step + 1) / float(self.warmup_steps)
        progress = (step - self.warmup_steps) / max(1, self.total_steps - self.warmup_steps)
        cosine = 0.5 * (1.0 + math.cos(math.pi * min(1.0, max(0.0, progress))))
        return self.min_lr_ratio + (1.0 - self.min_lr_ratio) * cosine

    def _apply(self, step: int) -> None:
        factor = self._factor(step)
        self._last_lr = []
        for base_lr, group in zip(self.base_lrs, self.optimizer.param_groups):
            lr = base_lr * factor
            group["lr"] = lr
            self._last_lr.append(lr)

    def step(self) -> None:
        self.last_epoch += 1
        self._apply(self.last_epoch)

    def get_last_lr(self) -> list[float]:
        return list(self._last_lr)

    def state_dict(self) -> dict[str, object]:
        return {
            "total_steps": self.total_steps,
            "warmup_steps": self.warmup_steps,
            "min_lr_ratio": self.min_lr_ratio,
            "base_lrs": list(self.base_lrs),
            "last_epoch": self.last_epoch,
            "_last_lr": list(self._last_lr),
        }

    def load_state_dict(self, state_dict: dict[str, object]) -> None:
        if int(state_dict["total_steps"]) != self.total_steps or int(state_dict["warmup_steps"]) != self.warmup_steps:
            raise ValueError("Scheduler configuration does not match checkpoint")
        if float(state_dict.get("min_lr_ratio", 0.0)) != self.min_lr_ratio:
            raise ValueError("Scheduler min_lr_ratio does not match checkpoint")
        self.base_lrs = [float(value) for value in state_dict["base_lrs"]]
        if len(self.base_lrs) != len(self.optimizer.param_groups):
            raise ValueError("Scheduler optimizer group count does not match checkpoint")
        self.last_epoch = int(state_dict["last_epoch"])
        self._apply(self.last_epoch)


def build_adamw(model: nn.Module, *, lr: float, weight_decay: float, betas=(0.9, 0.95)) -> torch.optim.AdamW:
    decay = []
    no_decay = []
    for name, parameter in model.named_parameters():
        if not parameter.requires_grad:
            continue
        if parameter.ndim <= 1 or name.endswith(".bias") or "norm" in name.lower():
            no_decay.append(parameter)
        else:
            decay.append(parameter)
    return torch.optim.AdamW(
        [
            {"params": decay, "weight_decay": float(weight_decay), "group_name": "decay"},
            {"params": no_decay, "weight_decay": 0.0, "group_name": "no_decay"},
        ],
        lr=float(lr),
        betas=tuple(float(value) for value in betas),
    )


def build_warmup_cosine_scheduler(optimizer, *, total_steps: int, warmup_steps: int, min_lr_ratio: float = 0.0):
    return ExposureWarmupCosineScheduler(
        optimizer,
        total_steps=total_steps,
        warmup_steps=warmup_steps,
        min_lr_ratio=min_lr_ratio,
    )
