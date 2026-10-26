"""Explicit FP32 compensated arithmetic; legacy callers never enter this module.

No parameters, buffers, backend flags, physical constants or RNG draws are added.
The reducer uses a packed CSR balanced tree and the mathematical linear backward.
This improves numerical evaluation; it does not prove a composed error bound.
"""
from __future__ import annotations

from copy import deepcopy

import torch
from torch import Tensor, nn

LEGACY = "legacy"
COMPENSATED = "compensated_fp32_v1"
MODES = (LEGACY, COMPENSATED)
PAIR_TILE_ROWS = 65536


def validate_numeric_mode(mode):
    if type(mode) is not str or mode not in MODES:
        raise ValueError("Explicit numeric mode must be legacy or compensated_fp32_v1")
    return mode


def numeric_mode(module):
    return validate_numeric_mode(getattr(module, "numeric_mode", LEGACY))


def apply_numeric_mode(module: nn.Module, mode: str):
    """Attach non-state metadata only; do not consume RNG or create state keys."""
    validate_numeric_mode(mode)
    if mode != LEGACY:
        for child in module.modules():
            child.numeric_mode = mode
    return module


def require_fp32_context(module: nn.Module, *values):
    """Fail explicitly on AMP/half rather than silently changing this FP32 mode."""
    for value in values:
        _fp32(value, "candidate input")
        if torch.is_autocast_enabled(value.device.type):
            raise ValueError("compensated_fp32_v1 requires autocast disabled")
    if any(parameter.is_floating_point() and parameter.dtype != torch.float32
           for parameter in module.parameters()):
        raise ValueError("compensated_fp32_v1 requires FP32 parameters")


def _fp32(value, name):
    if not isinstance(value, Tensor) or value.dtype != torch.float32:
        raise ValueError(name + " must be an FP32 tensor")


def _two_sum(a, b):
    """Neumaier error for a rounded FP32 sum, with honest nonfinite propagation."""
    high = a + b
    error = torch.where(a.abs() >= b.abs(), (a - high) + b, (b - high) + a)
    valid = torch.isfinite(a) & torch.isfinite(b) & torch.isfinite(high)
    return high, torch.where(valid, error, torch.zeros_like(error))


class _CompensatedIndexAdd(torch.autograd.Function):
    @staticmethod
    def forward(ctx, base, index, source):
        _fp32(base, "base")
        _fp32(source, "source")
        if (base.ndim != 2 or source.ndim != 2 or base.size(1) != source.size(1)
                or index.dtype != torch.long or index.shape != (len(source),)
                or not (base.device == source.device == index.device)):
            raise ValueError("Packed index-add requires base[N,C], source[E,C], int64 index[E] on one device")
        if len(index) and (bool((index < 0).any()) or bool((index >= len(base)).any())):
            raise ValueError("Segment index outside the base domain")
        ctx.save_for_backward(index)
        if not len(index):
            return base.clone()
        counts = torch.bincount(index, minlength=len(base))
        nonempty = torch.where(counts > 0)[0]
        order = torch.argsort(index, stable=True)
        high = source.index_select(0, order)
        low = torch.zeros_like(high)
        # Compact only the real segment members. At each level, adjacent pairs
        # reduce into one row; odd members get an exact zero right operand.
        while int(counts.max()) > 1:
            starts = counts.cumsum(0) - counts
            next_counts = (counts + 1) // 2
            next_starts = next_counts.cumsum(0) - next_counts
            rows = int(next_counts.sum())
            segment = torch.repeat_interleave(
                torch.arange(len(base), device=index.device), next_counts, output_size=rows)
            rank = torch.arange(rows, device=index.device) - next_starts[segment]
            left = starts[segment] + 2 * rank
            paired = 2 * rank + 1 < counts[segment]
            right = torch.where(paired, left + 1, left)
            rh = torch.where(paired[:, None], high[right], torch.zeros_like(high[left]))
            rl = torch.where(paired[:, None], low[right], torch.zeros_like(low[left]))
            high, error = _two_sum(high[left], rh)
            low = (low[left] + rl) + error
            counts = next_counts
        # Nonempty segments are now exactly one row, in increasing segment ID.
        high, error = _two_sum(base[nonempty], high)
        result = base.clone()
        result.index_copy_(0, nonempty, high + (low + error))
        return result

    @staticmethod
    def backward(ctx, grad_output):
        (index,) = ctx.saved_tensors
        return grad_output, None, grad_output.index_select(0, index)


def compensated_index_add(base: Tensor, index: Tensor, source: Tensor):
    """Mathematical base + segment_sum(source), all arithmetic/output FP32."""
    return _CompensatedIndexAdd.apply(base, index, source)


def compensated_pool(h: Tensor, batch: Tensor, graphs: int, mode: str):
    if type(graphs) is not int or graphs < 0 or mode not in ("sum", "mean"):
        raise ValueError("Explicit nonnegative graph count and sum/mean pooling required")
    result = compensated_index_add(h.new_zeros((graphs, h.size(-1))), batch, h)
    if mode == "mean":
        result = result / torch.bincount(batch, minlength=graphs).to(h.dtype).clamp_min(1)[:, None]
    return result


def _square_sum3(value):
    square = value * value
    high, low = _two_sum(square[..., 0], square[..., 1])
    high, residual = _two_sum(high, square[..., 2])
    return high + (low + residual)


class _SquaredNorm3(torch.autograd.Function):
    @staticmethod
    def forward(ctx, value):
        _fp32(value, "coordinates")
        if value.ndim < 1 or value.size(-1) != 3:
            raise ValueError("Last coordinate dimension must be three")
        ctx.save_for_backward(value)
        return _square_sum3(value)

    @staticmethod
    def backward(ctx, gradient):
        (value,) = ctx.saved_tensors
        return (2 * value) * gradient.unsqueeze(-1)


class _Norm3(torch.autograd.Function):
    @staticmethod
    def forward(ctx, value):
        _fp32(value, "coordinates")
        if value.ndim < 1 or value.size(-1) != 3:
            raise ValueError("Last coordinate dimension must be three")
        norm = torch.sqrt(_square_sum3(value))
        ctx.save_for_backward(value, norm)
        return norm

    @staticmethod
    def backward(ctx, gradient):
        value, norm = ctx.saved_tensors
        # Reconnect the norm for force/gradient losses that request create_graph.
        # The cached forward tensor alone would give an incorrect Hessian.
        if torch.is_grad_enabled():
            norm = _Norm3.apply(value)
        zero = norm == 0
        safe = torch.where(zero, torch.ones_like(norm), norm)
        derivative = value / safe.unsqueeze(-1) * gradient.unsqueeze(-1)
        return torch.where(zero.unsqueeze(-1), torch.zeros_like(derivative), derivative)


def compensated_squared_norm3(value: Tensor):
    return _SquaredNorm3.apply(value)


def compensated_norm3(value: Tensor, *, keepdim=False):
    result = _Norm3.apply(value)
    return result.unsqueeze(-1) if keepdim else result


def compensated_pairwise_norm3(left: Tensor, right: Tensor, *, squared=False):
    """Direct dense pair distances in bounded tiles; never a padded E x C tree."""
    _fp32(left, "left coordinates")
    _fp32(right, "right coordinates")
    if (left.ndim != 3 or right.ndim != 3 or left.size(-1) != 3 or right.size(-1) != 3
            or len(left) != len(right) or left.device != right.device):
        raise ValueError("Pair coordinates require matching batches [B,P,3]/[B,R,3]")
    batches, p, r = len(left), left.size(1), right.size(1)
    if batches * p * r == 0:
        # Preserve autograd connectivity, including empty inputs.
        return left[..., :1].sum() * right.new_zeros((batches, p, r)) + right.sum() * 0
    parts = []
    operation = compensated_squared_norm3 if squared else compensated_norm3
    for start in range(0, batches * p * r, PAIR_TILE_ROWS):
        rows = torch.arange(start, min(start + PAIR_TILE_ROWS, batches * p * r), device=left.device)
        graph = rows // (p * r)
        i, j = (rows // r) % p, rows % r
        parts.append(operation(left[graph, i] - right[graph, j]))
    return torch.cat(parts).reshape(batches, p, r)


def numeric_checkpoint_contract(model):
    """Bind mode through existing model config; raw tensor keys are unchanged."""
    if not callable(getattr(model, "config_dict", None)):
        raise ValueError("A model with explicit config_dict is required")
    return {"schema": "model_v3_numeric_checkpoint_contract_v1",
            "numeric_mode": numeric_mode(model), "model_config": deepcopy(model.config_dict())}


def load_numeric_bound_state_dict(model, state, contract):
    if contract != numeric_checkpoint_contract(model):
        raise ValueError("Checkpoint numeric mode/model configuration differs")
    return model.load_state_dict(state, strict=True)
