"""Explicit all-layer attention AV arithmetic; legacy remains the default.

This is independent of numeric_stability.numeric_mode. It creates no parameters,
buffers, random draws or backend-policy changes. Centering is an opt-in FP32
expression, not proof of whole-model equivariance or an exact-real oracle.
"""
from __future__ import annotations
from collections.abc import Mapping
import torch
from torch import Tensor, nn

LEGACY_AGGREGATION = "legacy"
CENTERED_FP32 = "centered_fp32_v1"
ATTENTION_AGGREGATION_MODES = (LEGACY_AGGREGATION, CENTERED_FP32)


def validate_aggregation_mode(value):
    if type(value) is not str or value not in ATTENTION_AGGREGATION_MODES:
        raise ValueError("backbone.attention_aggregation_mode must be legacy or centered_fp32_v1")
    return value


def aggregation_mode(module):
    return validate_aggregation_mode(getattr(module, "attention_aggregation_mode", LEGACY_AGGREGATION))


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _dropout_disabled(dropout):
    if dropout is None or type(dropout) is nn.Identity:
        return
    _require(type(dropout) is nn.Dropout and (dropout.p == 0 or not dropout.training),
             "centered_fp32_v1 requires effective attention dropout disabled")


def require_centered_f32_context(module, *floating_inputs):
    _require(bool(floating_inputs), "centered_fp32_v1 requires explicit FP32 floating inputs")
    for value in floating_inputs:
        _require(isinstance(value, Tensor) and value.dtype == torch.float32,
                 "centered_fp32_v1 requires FP32 inputs")
        _require(not torch.is_autocast_enabled(value.device.type),
                 "centered_fp32_v1 requires autocast disabled")
    _require(all(not value.is_floating_point() or value.dtype == torch.float32
                 for value in tuple(module.parameters())+tuple(module.buffers())),
             "centered_fp32_v1 requires FP32 parameters and floating buffers")


def require_centered_packed_atoms(positions):
    # Reject before PyG densification, whose empty-input error is not this
    # opt-in contract. All legacy packing behavior remains in its old path.
    _require(positions.ndim == 2 and positions.shape[1] == 3 and len(positions) > 0,
             "centered_fp32_v1 rejects empty or malformed packed atom coordinates")


def _native_mask(mask, batch_size, sequence_length, device):
    _require(batch_size > 0 and sequence_length > 0, "centered_fp32_v1 rejects empty attention")
    _require(isinstance(mask, Tensor) and mask.dtype == torch.bool and mask.device == device
             and tuple(mask.shape) == (batch_size, sequence_length),
             "centered_fp32_v1 requires the native bool key mask on the same device")
    _require(bool(mask.any(-1).all()), "centered_fp32_v1 rejects all-masked graphs")


def require_centered_attention_context(module, key_mask, *floating_inputs):
    """Call before QKV/dropout so a rejected mode does not consume dropout RNG."""
    require_centered_f32_context(module, *floating_inputs)
    first = floating_inputs[0]
    _require(first.ndim == 3, "centered_fp32_v1 requires dense [batch,nodes,channels] input")
    _native_mask(key_mask, first.shape[0], first.shape[1], first.device)
    _require(all(value.device == first.device for value in floating_inputs),
             "centered_fp32_v1 floating inputs must share one device")
    _dropout_disabled(module.attn_drop)


def centered_attention_value(probabilities, values, key_mask, *, attention_dropout=None):
    """v0+p@(V-v0), with first valid native key per graph for every head.

    p is the actual already-computed FP32 softmax tensor; it is neither cast nor
    renormalized here. Finite FP32 row sums need not equal one exactly. The
    gather remains in autograd, including its anchor contribution when sum(p)
    differs from one. Padded queries retain original masking by the caller.
    """
    for value in (probabilities, values):
        _require(isinstance(value, Tensor) and value.dtype == torch.float32,
                 "centered_fp32_v1 requires FP32 probabilities and values")
        _require(not torch.is_autocast_enabled(value.device.type),
                 "centered_fp32_v1 requires autocast disabled")
    _dropout_disabled(attention_dropout)
    _require(probabilities.ndim == values.ndim == 4 and probabilities.device == values.device,
             "centered_fp32_v1 requires coupled four-dimensional operands on one device")
    batch, heads, queries, keys = probabilities.shape
    _require(heads > 0 and values.shape[-1] > 0 and queries == keys
             and tuple(values.shape[:3]) == (batch, heads, keys),
             "centered_fp32_v1 requires self-attention [B,H,T,T] @ [B,H,T,D]")
    _native_mask(key_mask, batch, keys, values.device)
    _require(bool(torch.isfinite(probabilities).all()) and bool(torch.isfinite(values).all())
             and bool((probabilities >= 0).all()), "centered_fp32_v1 requires finite nonnegative weights and finite values")
    first = key_mask.to(torch.int64).argmax(-1)
    index = first[:, None, None, None].expand(batch, heads, 1, values.shape[-1])
    anchor = torch.gather(values, 2, index)
    return anchor+torch.matmul(probabilities, values-anchor)


def require_centered_backbone(backbone):
    """Reject silent runtime/native replacements when config still declares center."""
    from .attention import DenseGeoSelfAttention
    from .v3_architecture import SharedPairAttention
    _require(hasattr(backbone, "layers") and len(backbone.layers) > 0,
             "centered_fp32_v1 requires a nonempty coupled attention backbone")
    for layer in backbone.layers:
        _require(type(layer.attn) in (DenseGeoSelfAttention, SharedPairAttention)
                 and aggregation_mode(layer.attn) == CENTERED_FP32,
                 "centered_fp32_v1 is unsupported for replaced/NativeRuntimeDense/bf16 attention backends")


def reject_centered_runtime(module_or_configuration):
    """Performance/native paths have no centered implementation in this revision."""
    if isinstance(module_or_configuration, Mapping):
        mode = validate_aggregation_mode(module_or_configuration.get("backbone", {}).get(
            "attention_aggregation_mode", LEGACY_AGGREGATION))
    else:
        mode = aggregation_mode(module_or_configuration)
    _require(mode == LEGACY_AGGREGATION,
             "centered_fp32_v1 is unsupported by performance/NativeRuntimeDense/bf16 backends")
