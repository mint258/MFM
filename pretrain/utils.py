from __future__ import annotations

import math
import random

import numpy as np
import torch
from torch.optim.lr_scheduler import LambdaLR


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def pad_list(values, target_len: int, fill=0):
    return values + [fill] * max(0, target_len - len(values))


def build_lr_scheduler(optimizer, total_steps: int, warmup_steps: int):
    def lr_lambda(step: int):
        if step < warmup_steps:
            return step / max(1, warmup_steps)
        progress = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        progress = min(progress, 1.0)
        return 0.5 * (1.0 + math.cos(math.pi * progress))

    return LambdaLR(optimizer, lr_lambda)
