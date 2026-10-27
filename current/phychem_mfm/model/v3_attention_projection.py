"""One opt-in all-FP32 attention projection; no parameter or RNG mutation.

K=64 blocks and dense row tiles=128 are method constants, not a search space.
The real function is X @ W.T + b. Its explicit linear backward uses that same
function's analytic derivatives, and remains differentiable for higher orders.
No FP64, AMP, TF32, backend mutation or output scaling occurs in this module.
"""
from __future__ import annotations

import torch
from torch import Tensor, nn
from torch.nn import functional as F

from .v3_numeric_stability import COMPENSATED, numeric_mode, _two_sum

LEGACY_PROJECTION = "legacy"
BLOCKED_PROJECTION = "blocked_k64_compensated_fp32_v1"
PROJECTION_MODES = (LEGACY_PROJECTION, BLOCKED_PROJECTION)
K_BLOCK = 64
DENSE_ROW_TILE = 128


def validate_projection_mode(value):
    if type(value) is not str or value not in PROJECTION_MODES:
        raise ValueError("Unknown explicit attention projection mode")
    return value


def projection_mode(module):
    return validate_projection_mode(getattr(module, "attention_projection_mode", LEGACY_PROJECTION))


def require_projection_constructor(mode, *, dim, heads, aggregation, dropout, layers=None, numeric=None):
    validate_projection_mode(mode)
    if mode == LEGACY_PROJECTION:
        return
    if (type(dim) is not int or dim != 512 or type(heads) is not int or heads != 8
            or (layers is not None and (type(layers) is not int or layers != 6))
            or aggregation != "centered_fp32_v1" or float(dropout) != 0.
            or (numeric is not None and numeric != COMPENSATED)):
        raise ValueError("Projection candidate requires declared six-layer 512x8 compensated/centered FP32 and zero dropout")


def _context(*values):
    for value in values:
        if value is None:
            continue
        if not isinstance(value, Tensor) or value.dtype != torch.float32 or value.device.type not in ("cpu", "cuda"):
            raise ValueError("Projection tensors must already be FP32 on CPU or CUDA")
        if torch.is_autocast_enabled(value.device.type):
            raise ValueError("Projection candidate does not support AMP/autocast")
    try:
        strict = (torch.get_float32_matmul_precision() == "highest"
                  and not torch.backends.cuda.matmul.allow_tf32
                  and not torch.backends.cudnn.allow_tf32)
    except (RuntimeError, AttributeError) as exc:
        raise ValueError("Unsupported or mixed precision-control API state") from exc
    if not strict:
        raise ValueError("Projection candidate requires highest FP32 with both TF32 flags disabled")


def _linear_inputs(inputs, weight, bias):
    _context(inputs, weight, bias)
    if (inputs.ndim < 1 or weight.ndim != 2 or weight.size(1) <= 0
            or weight.size(1) % K_BLOCK or inputs.size(-1) != weight.size(1)
            or weight.size(0) <= 0 or inputs.device != weight.device
            or (bias is not None and (bias.ndim != 1 or bias.numel() != weight.size(0)
                                      or bias.device != inputs.device))):
        raise ValueError("Aligned positive K64-block FP32 linear tensor shapes required")


def _balanced(partials):
    high = torch.stack(partials, dim=0)
    low = torch.zeros_like(high)
    while high.size(0) > 1:
        left_h, left_l = high[0::2], low[0::2]
        right_h, right_l = high[1::2], low[1::2]
        if right_h.size(0) != left_h.size(0):
            right_h = torch.cat((right_h, torch.zeros_like(left_h[-1:])), dim=0)
            right_l = torch.cat((right_l, torch.zeros_like(left_l[-1:])), dim=0)
        high, error = _two_sum(left_h, right_h)
        low = (left_l + right_l) + error
    return high[0], low[0]


class _BlockedCompensatedLinear(torch.autograd.Function):
    @staticmethod
    def forward(ctx, inputs, weight, bias):
        _linear_inputs(inputs, weight, bias)
        ctx.save_for_backward(inputs, weight)
        ctx.has_bias = bias is not None
        flat = inputs.reshape(-1, inputs.size(-1))
        output = flat.new_empty((len(flat), weight.size(0)))
        for begin in range(0, len(flat), DENSE_ROW_TILE):
            rows = flat[begin:begin + DENSE_ROW_TILE]
            partials = [
                F.linear(rows[:, start:start + K_BLOCK], weight[:, start:start + K_BLOCK], None)
                for start in range(0, weight.size(1), K_BLOCK)]
            high, low = _balanced(partials)
            if bias is not None:
                high, error = _two_sum(high, bias)
                low = low + error
            output[begin:begin + len(rows)] = high + low
        return output.reshape(*inputs.shape[:-1], weight.size(0))

    @staticmethod
    def backward(ctx, grad_output):
        inputs, weight = ctx.saved_tensors
        _context(grad_output, inputs, weight)
        flat_g = grad_output.reshape(-1, weight.size(0))
        flat_x = inputs.reshape(-1, weight.size(1))
        # Derivatives of the same real affine function, not derivatives of
        # discontinuous IEEE rounding or an artificially detached surrogate.
        grad_inputs = flat_g.matmul(weight).reshape_as(inputs) if ctx.needs_input_grad[0] else None
        grad_weight = flat_g.transpose(0, 1).matmul(flat_x) if ctx.needs_input_grad[1] else None
        grad_bias = flat_g.sum(0) if ctx.has_bias and ctx.needs_input_grad[2] else None
        return grad_inputs, grad_weight, grad_bias


def blocked_linear_fp32(inputs, weight, bias=None):
    """XW.T+b with fixed K64 leaves/Neumaier tree, including ordinary training."""
    return _BlockedCompensatedLinear.apply(inputs, weight, bias)


def require_projection_backbone(backbone, *, expected_mode=None):
    actual = projection_mode(backbone)
    if expected_mode is not None and actual != validate_projection_mode(expected_mode):
        raise ValueError("Declared model/backbone projection modes differ")
    if actual == LEGACY_PROJECTION:
        return
    known = {
        "phychem_mfm.model.backbone.RealCoordTransformerBackbone",
        "phychem_mfm.model.v3_architecture.SharedPairBackbone",
    }
    identity = type(backbone).__module__ + "." + type(backbone).__qualname__
    if (identity not in known or getattr(backbone, "dim", None) != 512
            or not hasattr(backbone, "layers") or len(backbone.layers) != 6
            or numeric_mode(backbone) != COMPENSATED
            or getattr(backbone, "attention_aggregation_mode", None) != "centered_fp32_v1"):
        raise ValueError("Projection mode requires the original supported six-layer FP32 backbone")
    from .common import Linear
    classes = {
        "phychem_mfm.model.attention.DenseGeoSelfAttention",
        "phychem_mfm.model.v3_architecture.SharedPairAttention",
    }
    for layer in backbone.layers:
        attention = layer.attn
        identity = type(attention).__module__ + "." + type(attention).__qualname__
        if (identity not in classes or projection_mode(attention) != BLOCKED_PROJECTION
                or getattr(attention, "attention_aggregation_mode", None) != "centered_fp32_v1"
                or attention.dim != 512 or attention.nheads != 8
                or type(attention.qkv) is not Linear or type(attention.proj) is not Linear
                or attention.qkv.weight.shape != (1536, 512) or attention.proj.weight.shape != (512, 512)):
            raise ValueError("All twelve original QKV/output projections must implement the declared mode")
    if any(isinstance(module, nn.modules.dropout._DropoutNd) and module.p != 0 for module in backbone.modules()):
        raise ValueError("Projection candidate supports the declared zero-dropout backbone only")


def attention_projection(module, linear, values):
    """Candidate-only entry. Legacy callers must use their direct Linear call."""
    if projection_mode(module) != BLOCKED_PROJECTION:
        raise ValueError("Explicit candidate projection mode required")
    return blocked_linear_fp32(values, linear.weight, linear.bias)
