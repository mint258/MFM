from __future__ import annotations

import json
import math
import os
import platform
import random
import socket
import subprocess
import sys
from pathlib import Path

import numpy as np
import torch
from torch.optim.lr_scheduler import LambdaLR


def set_seed(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def apply_runtime_stability_settings(
    *,
    seed: int,
    deterministic_algorithms: bool = False,
    cudnn_deterministic: bool = False,
    disable_cudnn_benchmark: bool = False,
    disable_tf32: bool = False,
    float32_matmul_precision: str | None = None,
) -> dict[str, object]:
    set_seed(seed)

    if deterministic_algorithms:
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True)

    if cudnn_deterministic and hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.deterministic = True

    if disable_cudnn_benchmark and hasattr(torch.backends, "cudnn"):
        torch.backends.cudnn.benchmark = False

    if disable_tf32:
        if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
            torch.backends.cuda.matmul.allow_tf32 = False
        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.allow_tf32 = False

    if float32_matmul_precision and hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision(str(float32_matmul_precision))

    cuda_matmul_allow_tf32 = False
    if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
        cuda_matmul_allow_tf32 = bool(torch.backends.cuda.matmul.allow_tf32)

    cudnn_allow_tf32 = False
    cudnn_deterministic_state = False
    cudnn_benchmark_state = False
    if hasattr(torch.backends, "cudnn"):
        cudnn_allow_tf32 = bool(getattr(torch.backends.cudnn, "allow_tf32", False))
        cudnn_deterministic_state = bool(getattr(torch.backends.cudnn, "deterministic", False))
        cudnn_benchmark_state = bool(getattr(torch.backends.cudnn, "benchmark", False))

    return {
        "seed": int(seed),
        "deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "cudnn_deterministic": cudnn_deterministic_state,
        "cudnn_benchmark": cudnn_benchmark_state,
        "cuda_matmul_allow_tf32": cuda_matmul_allow_tf32,
        "cudnn_allow_tf32": cudnn_allow_tf32,
        "float32_matmul_precision": getattr(torch, "get_float32_matmul_precision", lambda: None)(),
        "cublas_workspace_config": os.environ.get("CUBLAS_WORKSPACE_CONFIG", ""),
    }


def _try_nvidia_smi_driver_version() -> str | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return None

    if result.returncode != 0:
        return None

    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return lines[0] if lines else None


def collect_environment_fingerprint(
    *,
    device: torch.device,
    world_size: int,
    rank: int,
    local_rank: int,
    num_workers: int,
    val_num_workers: int,
) -> dict[str, object]:
    gpu_names = []
    gpu_count = 0
    if torch.cuda.is_available():
        gpu_count = int(torch.cuda.device_count())
        gpu_names = [torch.cuda.get_device_name(index) for index in range(gpu_count)]

    cuda_matmul_allow_tf32 = False
    if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
        cuda_matmul_allow_tf32 = bool(torch.backends.cuda.matmul.allow_tf32)

    cudnn_allow_tf32 = False
    cudnn_deterministic_state = False
    cudnn_benchmark_state = False
    cudnn_version = None
    if hasattr(torch.backends, "cudnn"):
        cudnn_allow_tf32 = bool(getattr(torch.backends.cudnn, "allow_tf32", False))
        cudnn_deterministic_state = bool(getattr(torch.backends.cudnn, "deterministic", False))
        cudnn_benchmark_state = bool(getattr(torch.backends.cudnn, "benchmark", False))
        cudnn_version = torch.backends.cudnn.version()

    return {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "python_version": sys.version.replace("\n", " "),
        "python_executable": sys.executable,
        "pytorch_version": torch.__version__,
        "cuda_version": torch.version.cuda,
        "cudnn_version": cudnn_version,
        "driver_version": _try_nvidia_smi_driver_version(),
        "device": str(device),
        "gpu_count": gpu_count,
        "gpu_names": gpu_names,
        "cuda_available": bool(torch.cuda.is_available()),
        "world_size": int(world_size),
        "rank": int(rank),
        "local_rank": int(local_rank),
        "num_workers": int(num_workers),
        "val_num_workers": int(val_num_workers),
        "deterministic_algorithms": bool(torch.are_deterministic_algorithms_enabled()),
        "cudnn_deterministic": cudnn_deterministic_state,
        "cudnn_benchmark": cudnn_benchmark_state,
        "cuda_matmul_allow_tf32": cuda_matmul_allow_tf32,
        "cudnn_allow_tf32": cudnn_allow_tf32,
        "float32_matmul_precision": getattr(torch, "get_float32_matmul_precision", lambda: None)(),
    }


def sanitize_for_json(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, torch.Tensor):
        if value.numel() == 1:
            return value.detach().cpu().item()
        return value.detach().cpu().tolist()
    return str(value)


def write_json(path: str | Path, payload) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(sanitize_for_json(payload), indent=2, sort_keys=True),
        encoding="utf-8",
    )


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
