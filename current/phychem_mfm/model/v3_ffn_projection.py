"""One all-six-layer FFN affine evaluation; legacy retains the original net.

This module reuses the unchanged fixed K64/row128 FP32 affine primitive.
It adds no parameters, buffers, random draws, global mutations or FP64 path.
"""
from __future__ import annotations

from collections.abc import Mapping

import torch
from torch import nn

from .common import Linear
from .v3_attention_projection import BLOCKED_PROJECTION, blocked_linear_fp32
from .v3_numeric_stability import COMPENSATED, numeric_mode

LEGACY_FFN = "legacy"
BLOCKED_FFN = "blocked_k64_compensated_fp32_v1"
FFN_MODES = (LEGACY_FFN, BLOCKED_FFN)


def validate_ffn_projection_mode(value):
    if type(value) is not str or value not in FFN_MODES:
        raise ValueError("Unknown explicit FFN projection mode")
    return value


def ffn_projection_mode(module):
    return validate_ffn_projection_mode(getattr(module, "ffn_projection_mode", LEGACY_FFN))


def require_ffn_constructor(mode, *, dim, ff_mult, dropout, layers=None, heads=None,
                            aggregation=None, projection=None, geometry=None, numeric=None):
    validate_ffn_projection_mode(mode)
    if mode == LEGACY_FFN:
        return
    if (type(dim) is not int or dim != 512 or type(ff_mult) is not int or ff_mult != 2
            or type(dropout) not in (int, float) or float(dropout) != 0.
            or (layers is not None and (type(layers) is not int or layers != 6))
            or (heads is not None and (type(heads) is not int or heads != 8))
            or (aggregation is not None and aggregation != "centered_fp32_v1")
            or (projection is not None and projection != BLOCKED_PROJECTION)
            or (geometry is not None and geometry != "residual_expansion_fp32_v1")
            or (numeric is not None and numeric != COMPENSATED)):
        raise ValueError("FFN candidate requires six-layer 512x8, ff_mult2, zero-dropout compensated/centered/blocked/residual FP32")


def require_ffn_layout(module):
    # Lazy only to avoid the attention -> helper -> attention import cycle.
    from .attention import DenseFFN
    if (type(module) is not DenseFFN or "forward" in module.__dict__
            or ffn_projection_mode(module) != BLOCKED_FFN
            or type(module.net) is not nn.Sequential or len(module.net) != 4
            or type(module.net[0]) is not Linear or type(module.net[3]) is not Linear
            or type(module.net[1]) is not nn.SiLU or module.net[1].inplace
            or type(module.net[2]) is not nn.Identity
            or tuple(module.net[0].weight.shape) != (1024, 512)
            or tuple(module.net[3].weight.shape) != (512, 1024)
            or module.net[0].bias is None or tuple(module.net[0].bias.shape) != (1024,)
            or module.net[3].bias is None or tuple(module.net[3].bias.shape) != (512,)):
        raise ValueError("All twelve FFN affines must retain the original supported DenseFFN layout")
    if any(value.dtype != torch.float32 for value in module.parameters()):
        raise ValueError("FFN candidate parameters must already be FP32")


def require_ffn_backbone(backbone, *, expected_mode=None):
    mode = ffn_projection_mode(backbone)
    if expected_mode is not None and mode != validate_ffn_projection_mode(expected_mode):
        raise ValueError("Declared model/backbone FFN projection modes differ")
    if mode == LEGACY_FFN:
        if any(ffn_projection_mode(layer.ffn) != LEGACY_FFN
               for layer in getattr(backbone, "layers", ()) if hasattr(layer, "ffn")):
            raise ValueError("FFN runtime projection mode is not declared by the backbone")
        return
    identity = type(backbone).__module__ + "." + type(backbone).__qualname__
    if (identity not in {"phychem_mfm.model.backbone.RealCoordTransformerBackbone",
                         "phychem_mfm.model.v3_architecture.SharedPairBackbone"}
            or "forward" in backbone.__dict__ or getattr(backbone, "dim", None) != 512
            or not hasattr(backbone, "layers") or len(backbone.layers) != 6
            or numeric_mode(backbone) != COMPENSATED
            or getattr(backbone, "attention_aggregation_mode", None) != "centered_fp32_v1"
            or getattr(backbone, "attention_projection_mode", None) != BLOCKED_PROJECTION
            or getattr(backbone, "geometry_mode", None) != "residual_expansion_fp32_v1"):
        raise ValueError("FFN projection is unsupported for replaced, compiled, Native or other backbones")
    for layer in backbone.layers:
        require_ffn_layout(layer.ffn)


def ffn_projection(module, linear, values):
    """One real affine call. The original Linear Parameters stay in the net."""
    require_ffn_layout(module)
    if linear is not module.net[0] and linear is not module.net[3]:
        raise ValueError("Only the two declared FFN affine sites may use this entry")
    return blocked_linear_fp32(values, linear.weight, linear.bias)


def reject_ffn_runtime(module_or_configuration):
    """No performance, Native or compiled FFN implementation is declared here."""
    if isinstance(module_or_configuration, Mapping):
        configuration = module_or_configuration
        backbone = configuration.get("backbone", configuration.get("backbone_config", {}))
        mode = validate_ffn_projection_mode(backbone.get("ffn_projection_mode", LEGACY_FFN))
    else:
        mode = ffn_projection_mode(module_or_configuration)
    if mode != LEGACY_FFN:
        raise ValueError("FFN projection candidate is unsupported in performance/Native/compiled paths")
