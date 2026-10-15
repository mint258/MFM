from __future__ import annotations

from datetime import timedelta
import os
from dataclasses import dataclass
from typing import Any

import torch
import torch.distributed as dist
from torch.nn.parallel import DistributedDataParallel as DDP


@dataclass(frozen=True)
class DistributedContext:
    enabled: bool
    backend: str | None
    rank: int
    local_rank: int
    world_size: int
    device: torch.device
    is_main_process: bool


def is_distributed_ready() -> bool:
    return dist.is_available() and dist.is_initialized()


def unwrap_model(model):
    return model.module if hasattr(model, "module") else model


def init_distributed(args) -> DistributedContext:
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    rank = int(os.environ.get("RANK", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    requested = bool(getattr(args, "distributed", False)) or world_size > 1

    device_arg = str(getattr(args, "device", "auto")).lower()
    if device_arg == "cpu":
        device = torch.device("cpu")
    elif device_arg == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError("--device cuda was requested, but CUDA is not available.")
        device = torch.device("cuda", local_rank if requested else 0)
    else:
        if torch.cuda.is_available():
            device = torch.device("cuda", local_rank if requested else 0)
        else:
            device = torch.device("cpu")

    enabled = requested and world_size > 1
    backend = getattr(args, "backend", None) or ("nccl" if device.type == "cuda" else "gloo")
    timeout_minutes = max(1, int(getattr(args, "dist_timeout_minutes", 180)))

    if enabled and not is_distributed_ready():
        if device.type == "cuda":
            torch.cuda.set_device(device)
        dist.init_process_group(
            backend=backend,
            init_method="env://",
            timeout=timedelta(minutes=timeout_minutes),
        )

    return DistributedContext(
        enabled=enabled,
        backend=backend if enabled else None,
        rank=rank,
        local_rank=local_rank,
        world_size=world_size,
        device=device,
        is_main_process=(rank == 0),
    )


def cleanup_distributed() -> None:
    if is_distributed_ready():
        dist.destroy_process_group()


def barrier() -> None:
    if is_distributed_ready():
        dist.barrier()


def broadcast_object(value: Any, *, src: int = 0):
    if not is_distributed_ready():
        return value
    payload = [value]
    dist.broadcast_object_list(payload, src=src)
    return payload[0]


def wrap_ddp(model, ctx: DistributedContext, *, find_unused_parameters: bool, broadcast_buffers: bool, static_graph: bool):
    if not ctx.enabled:
        return model

    ddp_kwargs = {
        "find_unused_parameters": bool(find_unused_parameters),
        "broadcast_buffers": bool(broadcast_buffers),
    }
    if ctx.device.type == "cuda":
        ddp_kwargs["device_ids"] = [ctx.local_rank]
        ddp_kwargs["output_device"] = ctx.local_rank

    wrapped = DDP(model, **ddp_kwargs)
    if static_graph:
        wrapped._set_static_graph()
    return wrapped
