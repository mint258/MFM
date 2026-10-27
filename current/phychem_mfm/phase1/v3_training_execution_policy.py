"""Shared stdlib-only H0 runtime policy; safe to load before CUDA initialization.

A preinit consumer may load this exact SHA-bound leaf by its file path without
importing the model package. This module imports no Torch and performs no I/O,
CUDA, environment, RNG or global-state action. It only returns a fresh dict.
"""
from __future__ import annotations


def h0_runtime_controls_from_deterministic(deterministic: bool) -> dict:
    """The same declared policy used by training export validation and context.

    This is policy metadata, not proof of a worker's initialization history.
    The fresh worker must arrange/record CUDA CUBLAS policy before init; the
    restoring context never repairs that environment late.
    """
    if type(deterministic) is not bool:
        raise ValueError("Explicit boolean H0 deterministic policy required")
    return {
        "float32_matmul_precision": "highest",
        "matmul_tf32": False,
        "cudnn_tf32": False,
        "deterministic_algorithms": deterministic,
        "deterministic_warn_only": False,
        "cudnn_deterministic": deterministic,
        "cudnn_benchmark": False,
        "cublas_workspace_config_for_cuda": ":4096:8" if deterministic else None,
    }
