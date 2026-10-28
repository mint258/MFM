"""One fixed all-FP32 finalization of the three real residual terms.

The original rounded u=x+a still feeds norm2/FFN. No tail is injected there.
The sum primitive has the real linear VJP (g,g,g), including higher orders.
"""
from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import nn

from .v3_attention_projection import _context
from .v3_numeric_stability import COMPENSATED, numeric_mode, _two_sum
from .v3_ffn_projection import require_ffn_layout

LEGACY_RESIDUAL = "legacy"
TWO_SUM_RESIDUAL = "two_sum_three_term_fp32_v1"
RESIDUAL_MODES = (LEGACY_RESIDUAL, TWO_SUM_RESIDUAL)


def validate_residual_accumulation_mode(value):
    if type(value) is not str or value not in RESIDUAL_MODES:
        raise ValueError("Unknown explicit residual accumulation mode")
    return value


def residual_accumulation_mode(module):
    return validate_residual_accumulation_mode(
        getattr(module, "residual_accumulation_mode", LEGACY_RESIDUAL))


def require_residual_constructor(mode, *, dim, ff_mult, dropout, heads=None, layers=None,
        aggregation=None, projection=None, geometry=None, ffn=None, numeric=None):
    validate_residual_accumulation_mode(mode)
    if mode == LEGACY_RESIDUAL:
        return
    fixed = "blocked_k64_compensated_fp32_v1"
    if (type(dim) is not int or dim != 512 or type(ff_mult) is not int or ff_mult != 2
            or type(dropout) not in (int, float) or float(dropout) != 0.
            or (heads is not None and (type(heads) is not int or heads != 8))
            or (layers is not None and (type(layers) is not int or layers != 6))
            or (aggregation is not None and aggregation != "centered_fp32_v1")
            or (projection is not None and projection != fixed)
            or (geometry is not None and geometry != "residual_expansion_fp32_v1")
            or (ffn is not None and ffn != fixed)
            or (numeric is not None and numeric != COMPENSATED)):
        raise ValueError("Residual candidate requires six-layer512x8/ff_mult2/zero-dropout fixed FFN FP32 base")


class _ThreeTermSumFP32(torch.autograd.Function):
    @staticmethod
    def forward(ctx, original, attention, feedforward):
        if torch.compiler.is_compiling() or torch.jit.is_tracing() or torch.jit.is_scripting():
            raise ValueError("Residual candidate does not support compiled or traced execution")
        if any(not isinstance(value, torch.Tensor) for value in (original, attention, feedforward)):
            raise ValueError("Three explicit FP32 residual tensors required")
        _context(original, attention, feedforward)
        if (original.shape != attention.shape or original.shape != feedforward.shape
                or original.device != attention.device or original.device != feedforward.device):
            raise ValueError("Residual terms must have identical shape and device")
        if not torch.stack([torch.isfinite(value).all() for value in (original, attention, feedforward)]).all():
            raise ValueError("Residual candidate requires finite FP32 operands")
        first, first_tail = _two_sum(original, attention)
        second, second_tail = _two_sum(first, feedforward)
        tail = first_tail + second_tail
        result = second + tail
        if not torch.stack([torch.isfinite(value).all() for value in
                            (first, first_tail, second, second_tail, tail, result)]).all():
            raise ValueError("Residual TwoSum intermediate overflow/nonfinite is unsupported")
        return result

    @staticmethod
    def backward(ctx, gradient):
        _context(gradient)
        # The real function is x+a+b. The nonlinear b(x+a) graph is outside
        # this primitive and remains connected. Do not differentiate roundoff.
        return gradient, gradient, gradient


def two_sum_three_term_fp32(original, attention, feedforward):
    return _ThreeTermSumFP32.apply(original, attention, feedforward)


def require_residual_layer(layer):
    identity = type(layer).__module__ + "." + type(layer).__qualname__
    if (identity not in {"phychem_mfm.model.attention.RealCoordTransformerLayer",
                         "phychem_mfm.model.v3_architecture.SharedPairTransformerLayer"}
            or "forward" in layer.__dict__
            or residual_accumulation_mode(layer) != TWO_SUM_RESIDUAL
            or numeric_mode(layer) != COMPENSATED):
        raise ValueError("Residual candidate requires the original supported FP32 layer")
    attention_identity = type(layer.attn).__module__ + "." + type(layer.attn).__qualname__
    if attention_identity not in {"phychem_mfm.model.attention.DenseGeoSelfAttention",
                                  "phychem_mfm.model.v3_architecture.SharedPairAttention"}:
        raise ValueError("Residual candidate does not support a replaced/Native attention layer")
    require_ffn_layout(layer.ffn)
    for norm in (layer.norm1, layer.norm2):
        if (type(norm) is not nn.LayerNorm or tuple(norm.normalized_shape) != (512,)
                or norm.eps != 1e-5):
            raise ValueError("Original LayerNorm512/epsilon must be retained")
    if any(parameter.dtype != torch.float32 for parameter in layer.parameters()):
        raise ValueError("Residual layer parameters must already be FP32")


def require_residual_backbone(backbone, *, expected_mode=None):
    mode = residual_accumulation_mode(backbone)
    if expected_mode is not None and mode != validate_residual_accumulation_mode(expected_mode):
        raise ValueError("Declared model/backbone residual modes differ")
    if mode == LEGACY_RESIDUAL:
        if any(residual_accumulation_mode(layer) != LEGACY_RESIDUAL
               for layer in getattr(backbone, "layers", ())):
            raise ValueError("Layer residual mode is not declared by the backbone")
        return
    if torch.compiler.is_compiling() or torch.jit.is_tracing() or torch.jit.is_scripting():
        raise ValueError("Residual candidate does not support compiled or traced execution")
    identity = type(backbone).__module__ + "." + type(backbone).__qualname__
    if (identity not in {"phychem_mfm.model.backbone.RealCoordTransformerBackbone",
                         "phychem_mfm.model.v3_architecture.SharedPairBackbone"}
            or "forward" in backbone.__dict__ or getattr(backbone, "dim", None) != 512
            or not hasattr(backbone, "layers") or len(backbone.layers) != 6
            or numeric_mode(backbone) != COMPENSATED
            or getattr(backbone, "attention_aggregation_mode", None) != "centered_fp32_v1"
            or getattr(backbone, "attention_projection_mode", None) != "blocked_k64_compensated_fp32_v1"
            or getattr(backbone, "ffn_projection_mode", None) != "blocked_k64_compensated_fp32_v1"
            or getattr(backbone, "geometry_mode", None) != "residual_expansion_fp32_v1"):
        raise ValueError("Residual accumulation unsupported for replaced/compiled/Native or other backbones")
    for layer in backbone.layers:
        require_residual_layer(layer)


def residual_accumulation(layer, original, attention, feedforward):
    """Exactly one candidate finalizer per layer; all original modules stay."""
    require_residual_layer(layer)
    return two_sum_three_term_fp32(original, attention, feedforward)


def reject_residual_runtime(configuration):
    if not isinstance(configuration, Mapping):
        raise ValueError("Explicit residual configuration required")
    backbone = configuration.get("backbone", configuration.get("backbone_config", {}))
    mode = validate_residual_accumulation_mode(backbone.get("residual_accumulation_mode", LEGACY_RESIDUAL))
    if mode != LEGACY_RESIDUAL:
        raise ValueError("Residual candidate is unsupported in performance/Native/compiled paths")
