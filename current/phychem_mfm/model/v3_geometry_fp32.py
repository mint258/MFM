"""One encoder-only FP32 residual-expansion geometry candidate.

All floating tensors and forward/backward arithmetic remain FP32. Raw two-point
coordinates enter the primitive before subtraction rounds. Parameters, buffers,
initialization, head geometry and existing numeric-mode meanings are unchanged.
The real function is sum((left-right)**2) or its Euclidean square root. Backward
uses those analytic derivatives, not AD through error-recovery cancellations.
No universal correctly-rounded or all-real-domain equivariance claim is made.
"""
from __future__ import annotations

import torch
from torch import Tensor

from .v3_numeric_stability import COMPENSATED, numeric_mode, _two_sum

LEGACY_GEOMETRY = "legacy"
RESIDUAL_GEOMETRY = "residual_expansion_fp32_v1"
GEOMETRY_MODES = (LEGACY_GEOMETRY, RESIDUAL_GEOMETRY)
GEOMETRY_TILE_ROWS = 65536
SPLITTER = 4097.0


def validate_geometry_mode(value):
    if type(value) is not str or value not in GEOMETRY_MODES:
        raise ValueError("Unknown explicit encoder geometry mode")
    return value


def geometry_mode(module):
    return validate_geometry_mode(getattr(module, "geometry_mode", LEGACY_GEOMETRY))


def require_geometry_constructor(mode, *, dim, heads, aggregation, projection,
                                 dropout, layers=None, numeric=None):
    validate_geometry_mode(mode)
    if mode == LEGACY_GEOMETRY:
        return
    if (type(dim) is not int or dim != 512 or type(heads) is not int or heads != 8
            or (layers is not None and (type(layers) is not int or layers != 6))
            or aggregation != "centered_fp32_v1"
            or projection != "blocked_k64_compensated_fp32_v1"
            or float(dropout) != 0.
            or (numeric is not None and numeric != COMPENSATED)):
        raise ValueError("Residual geometry requires the unchanged six-layer512x8 compensated/centered/blocked FP32 base")


def require_geometry_backbone(backbone, *, expected_mode=RESIDUAL_GEOMETRY):
    validate_geometry_mode(expected_mode)
    if expected_mode == LEGACY_GEOMETRY:
        return
    if (type(backbone).__name__ not in ("RealCoordTransformerBackbone", "SharedPairBackbone")
            or geometry_mode(backbone) != expected_mode or len(backbone.layers) != 6
            or int(backbone.dim) != 512):
        raise ValueError("Unsupported or replaced residual-geometry backbone")
    _no_compile()
    shared = type(backbone).__name__ == "SharedPairBackbone"
    expected = "SharedPairAttention" if shared else "DenseGeoSelfAttention"
    for layer in backbone.layers:
        if type(layer.attn).__name__ != expected or geometry_mode(layer.attn) != expected_mode:
            raise ValueError("All six original attention geometry modes must match")
    if shared and (type(backbone.pair_encoder).__name__ != "SharedGaussianPairEncoder"
                   or geometry_mode(backbone.pair_encoder) != expected_mode):
        raise ValueError("Shared pair encoder geometry mode differs")
    if numeric_mode(backbone) != COMPENSATED:
        raise ValueError("Residual geometry requires unchanged compensated numeric mode")


def require_geometry_binding(backbone, *, expected_mode):
    validate_geometry_mode(expected_mode)
    modules = [backbone]
    modules += [getattr(layer, "attn", layer) for layer in getattr(backbone, "layers", ())]
    pair = getattr(backbone, "pair_encoder", None)
    if pair is not None:
        modules.append(pair)
    if any(geometry_mode(module) != expected_mode for module in modules):
        raise ValueError("Configuration and all runtime geometry mode bindings must agree")
    if expected_mode == RESIDUAL_GEOMETRY:
        require_geometry_backbone(backbone)


def _no_compile():
    compiler = getattr(torch, "compiler", None)
    compiling = compiler is not None and compiler.is_compiling()
    if compiling or torch.jit.is_tracing() or torch.jit.is_scripting():
        raise ValueError("Residual geometry requires eager separate FP32 operations; compile/trace unsupported")


def _context(left, right):
    _no_compile()
    if (not isinstance(left, Tensor) or not isinstance(right, Tensor)
            or left.dtype != torch.float32 or right.dtype != torch.float32
            or left.device != right.device or left.device.type not in ("cpu", "cuda")
            or left.shape != right.shape or left.ndim < 1 or left.size(-1) != 3):
        raise ValueError("Raw same-shaped FP32 coordinate triples required")
    if torch.is_autocast_enabled(left.device.type):
        raise ValueError("Residual geometry does not support AMP/autocast")
    if not bool(torch.isfinite(left).all() and torch.isfinite(right).all()):
        raise ValueError("Residual geometry requires finite coordinates")


def _product(a, b):
    """FP32 split-product residual; normalized arguments avoid splitter overflow."""
    product = a * b
    ac, bc = SPLITTER * a, SPLITTER * b
    ah, bh = ac - (ac - a), bc - (bc - b)
    al, bl = a - ah, b - bh
    residual = ((ah * bh - product) + ah * bl + al * bh) + al * bl
    return product, residual


def _balanced(terms):
    high = torch.stack(terms, dim=0)
    low = torch.zeros_like(high)
    while high.size(0) > 1:
        lh, ll, rh, rl = high[0::2], low[0::2], high[1::2], low[1::2]
        if rh.size(0) != lh.size(0):
            rh = torch.cat((rh, torch.zeros_like(lh[-1:])), dim=0)
            rl = torch.cat((rl, torch.zeros_like(ll[-1:])), dim=0)
        high, error = _two_sum(lh, rh)
        low = (ll + rl) + error
    return high[0], low[0]


def _forward(left, right, squared):
    high, low = _two_sum(left, -right)
    if not bool(torch.isfinite(high).all() and torch.isfinite(low).all()):
        raise ValueError("Raw coordinate difference is outside finite FP32 range")
    largest = high.abs().amax(dim=-1)
    nonzero = (left != right).any(dim=-1)
    if bool((nonzero & largest.eq(0)).any()):
        raise ValueError("Nonzero raw difference was flushed to zero; unsupported geometry domain")
    _, exponent = torch.frexp(largest)
    # Power-of-two scaling changes no real Euclidean function. Every float stays FP32.
    h = torch.ldexp(high, -exponent.unsqueeze(-1))
    l = torch.ldexp(low, -exponent.unsqueeze(-1))
    hh, hh_error = _product(h, h)
    hl, hl_error = _product(h, l)
    ll, ll_error = _product(l, l)
    terms = []
    for component in range(3):
        terms.extend((hh[..., component], hh_error[..., component],
                      2 * hl[..., component], 2 * hl_error[..., component],
                      ll[..., component], ll_error[..., component]))
    sum_high, sum_low = _balanced(terms)
    if squared:
        result = torch.ldexp(sum_high + sum_low, 2 * exponent)
    else:
        safe = torch.where(nonzero, sum_high, torch.ones_like(sum_high))
        if bool((nonzero & safe.le(0)).any()):
            raise ValueError("Nonpositive expanded squared norm for a nonzero difference")
        root = torch.sqrt(safe)
        root_square, root_error = _product(root, root)
        remainder_high, remainder_low = _balanced((sum_high, sum_low, -root_square, -root_error))
        correction = (remainder_high + remainder_low) / (2 * root)
        result = torch.ldexp(root + correction, exponent)
        result = torch.where(nonzero, result, torch.zeros_like(result))
        if bool((nonzero & result.eq(0)).any()):
            raise ValueError("Nonzero norm is outside the supported nonflushed FP32 output range")
    if result.dtype != torch.float32 or not bool(torch.isfinite(result).all()):
        raise ValueError("Residual geometry output is outside finite FP32 range")
    return result


class _ResidualDistance(torch.autograd.Function):
    @staticmethod
    def forward(ctx, left, right, squared):
        _context(left, right)
        if type(squared) is not bool:
            raise ValueError("Explicit squared-distance switch required")
        result = _forward(left, right, squared)
        ctx.squared = squared
        ctx.save_for_backward(left, right, result)
        return result

    @staticmethod
    def backward(ctx, gradient):
        left, right, saved = ctx.saved_tensors
        if gradient.dtype != torch.float32:
            raise ValueError("Residual geometry gradient must remain FP32")
        # Analytic real-function gradients. Do NOT differentiate split/recovery cancellations.
        difference = left - right
        if ctx.squared:
            value = (2 * difference) * gradient.unsqueeze(-1)
        else:
            # Reconnect the real norm for Hessians/force losses requesting create_graph.
            norm = _ResidualDistance.apply(left, right, False) if torch.is_grad_enabled() else saved
            zero = norm == 0
            denominator = torch.where(zero, torch.ones_like(norm), norm)
            value = (difference / denominator.unsqueeze(-1)) * gradient.unsqueeze(-1)
            value = torch.where(zero.unsqueeze(-1), torch.zeros_like(value), value)
        return value, -value, None


def residual_distance_fp32(left: Tensor, right: Tensor, *, squared=False):
    """Aligned raw coordinate triples, including noncontiguous and empty rows."""
    return _ResidualDistance.apply(left, right, squared)


def residual_pairwise_distance_fp32(left: Tensor, right: Tensor, *, squared=False):
    """Bounded dense pair tiling; no E-by512 padding and no variable tile search."""
    if (not isinstance(left, Tensor) or not isinstance(right, Tensor)
            or left.dtype != torch.float32 or right.dtype != torch.float32
            or left.ndim != 3 or right.ndim != 3 or left.size(-1) != 3 or right.size(-1) != 3
            or len(left) != len(right) or left.device != right.device
            or left.device.type not in ("cpu", "cuda")):
        raise ValueError("Batched raw FP32 coordinates [B,P,3]/[B,R,3] required")
    if type(squared) is not bool:
        raise ValueError("Explicit squared-distance switch required")
    if torch.is_autocast_enabled(left.device.type):
        raise ValueError("Residual geometry does not support AMP/autocast")
    _no_compile()
    batches, p, r = len(left), left.size(1), right.size(1)
    if batches * p * r == 0:
        return left[..., :1].sum() * right.new_zeros((batches, p, r)) + right.sum() * 0
    parts = []
    for start in range(0, batches * p * r, GEOMETRY_TILE_ROWS):
        rows = torch.arange(start, min(start + GEOMETRY_TILE_ROWS, batches * p * r), device=left.device)
        graph, i, j = rows // (p * r), (rows // r) % p, rows % r
        parts.append(residual_distance_fp32(left[graph, i], right[graph, j], squared=squared))
    return torch.cat(parts).reshape(batches, p, r)
