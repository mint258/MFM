"""C-only removal of the final per-head constant, with an exact parameter map.

The shared C1-a/b per-head projection was already bias-free. Pair-feature
MLP biases are not covered: a cutoff envelope can make them nonconstant.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy

import torch
from torch import nn

from .common import Linear
from .v3_attention_projection import _context

KEY = "distance_bias_projection_bias"
S_MEMORY_MODULE = "model_v3_architecture_s_memory_170a7752bad1812d"


def validate_distance_bias_projection_bias(value):
    if type(value) is not bool:
        raise ValueError("distance_bias_projection_bias must be an explicit boolean")
    return value


def distance_bias_projection_bias(module):
    return validate_distance_bias_projection_bias(getattr(module, KEY, True))


def require_distance_bias_constructor(bias, *, use_dist_bias, dim=None, heads=None, layers=None):
    validate_distance_bias_projection_bias(bias)
    if bias:
        return
    if use_dist_bias is not True or any(value is not None and
            (type(value) is not int or value != expected)
            for value, expected in ((dim,512),(heads,8),(layers,6))):
        raise ValueError("Bias-free C backbone requires enabled distance bias and six layers512x8")
    if torch.get_default_dtype() != torch.float32:
        raise ValueError("Bias-free C construction requires the original FP32 parameter dtype")


def remove_initialized_head_bias(projection, *, heads):
    """Construct with the old initializer first; remove only this Parameter."""
    if (type(projection) is not Linear or projection.out_features != heads
            or not isinstance(projection.bias, nn.Parameter)
            or tuple(projection.bias.shape) != (heads,)):
        raise ValueError("Original initialized per-head Linear bias required")
    projection.register_parameter("bias", None)


def _distance_mlp_supported(mlp):
    standard = type(mlp) is nn.Sequential
    frozen_tiled = (type(mlp).__module__ == S_MEMORY_MODULE
        and type(mlp).__qualname__ == "TiledDistanceMLP"
        and getattr(mlp,"pair_rows",None) == 65536)
    return ((standard or frozen_tiled) and "forward" not in mlp.__dict__
        and len(mlp) == 3 and type(mlp[0]) is Linear
        and type(mlp[1]) is nn.SiLU and not mlp[1].inplace
        and type(mlp[2]) is Linear and all("forward" not in child.__dict__ for child in mlp))


def require_bias_free_attention(module, *values):
    if distance_bias_projection_bias(module):
        return
    if torch.compiler.is_compiling() or torch.jit.is_tracing() or torch.jit.is_scripting():
        raise ValueError("Bias-free C attention does not support compiled/traced execution")
    identity = type(module).__module__+"."+type(module).__qualname__
    if "forward" in module.__dict__:
        raise ValueError("Bias-free C attention cannot use a replaced forward")
    if identity == "phychem_mfm.model.attention.DenseGeoSelfAttention":
        mlp = module.dist_mlp
        if (module.use_dist_bias is not True or mlp is None or not _distance_mlp_supported(mlp)
                or mlp[0].in_features != 1 or mlp[0].out_features != module.dim
                or mlp[2].in_features != module.dim or mlp[2].out_features != module.nheads
                or mlp[2].bias is not None):
            raise ValueError("All six Dense distance projections must have bias=None")
    elif identity == "phychem_mfm.model.v3_architecture.SharedPairAttention":
        if (type(module.pair_projection) is not Linear
                or module.pair_projection.out_features != module.nheads
                or module.pair_projection.bias is not None
                or "forward" in module.pair_projection.__dict__):
            raise ValueError("Shared C1-a/b per-head projection must remain bias-free")
    else:
        raise ValueError("Bias-free C does not support Native/performance or unknown attention")
    _context(*values, *module.parameters())


def require_distance_bias_backbone(backbone, *, expected=None):
    bias = distance_bias_projection_bias(backbone)
    if expected is not None and bias != validate_distance_bias_projection_bias(expected):
        raise ValueError("Declared model/backbone distance projection bias differs")
    layers = getattr(backbone,"layers",())
    if bias:
        if any(not distance_bias_projection_bias(getattr(layer,"attn",None)) for layer in layers):
            raise ValueError("Bias-free layer is not declared by its backbone")
        return
    identity = type(backbone).__module__+"."+type(backbone).__qualname__
    if (identity not in {"phychem_mfm.model.backbone.RealCoordTransformerBackbone",
                         "phychem_mfm.model.v3_architecture.SharedPairBackbone"}
            or "forward" in backbone.__dict__ or getattr(backbone,"dim",None) != 512
            or len(layers) != 6):
        raise ValueError("Bias-free C requires the original six-layer512 backbone")
    for layer in layers:
        identity = type(layer).__module__+"."+type(layer).__qualname__
        attention = getattr(layer,"attn",None)
        if (identity not in {"phychem_mfm.model.attention.RealCoordTransformerLayer",
                             "phychem_mfm.model.v3_architecture.SharedPairTransformerLayer"}
                or "forward" in layer.__dict__ or attention is None
                or distance_bias_projection_bias(attention) is not False
                or getattr(attention,"nheads",None) != 8):
            raise ValueError("All six C distance projection declarations must agree")
        require_bias_free_attention(attention)


def reject_distance_bias_runtime(value):
    if isinstance(value, Mapping):
        backbone = value.get("backbone",value.get("backbone_config",{}))
        bias = validate_distance_bias_projection_bias(backbone.get(KEY,True))
    else:
        bias = distance_bias_projection_bias(value)
    if not bias:
        raise ValueError("Bias-free C is unsupported in A/performance/Native/compiled paths")


def common_parameter_mapping(source, target):
    """Structural map only; callers still verify every actual common raw value.

    Full-model prefixes, including encoder., are preserved exactly. This is
    not a learned checkpoint converter or a new source/acceptance certificate.
    """
    source_encoder = getattr(source,"encoder",source)
    target_encoder = getattr(target,"encoder",target)
    if not all(callable(getattr(value,"config_dict",None)) and hasattr(value,"backbone")
               for value in (source_encoder,target_encoder)):
        raise ValueError("Two explicitly configured C encoders required")
    left,right = deepcopy(source_encoder.config_dict()),deepcopy(target_encoder.config_dict())
    if (validate_distance_bias_projection_bias(left["backbone_config"].pop(KEY,True)) is not True
            or validate_distance_bias_projection_bias(right["backbone_config"].pop(KEY,True)) is not False
            or left != right):
        raise ValueError("Only the explicit C distance-head bias flag may differ")
    require_distance_bias_backbone(source_encoder.backbone,expected=True)
    require_distance_bias_backbone(target_encoder.backbone,expected=False)
    if type(source_encoder.backbone) is not type(target_encoder.backbone):
        raise ValueError("C1 source/target backbone classes differ")
    prefixes = [name for name,module in target.named_modules() if module is target_encoder.backbone]
    if len(prefixes) != 1:
        raise ValueError("One canonical backbone parameter namespace required")
    prefix = prefixes[0]+"." if prefixes[0] else ""
    dense = type(target_encoder.backbone).__qualname__ == "RealCoordTransformerBackbone"
    removed = {prefix+"layers.%d.attn.dist_mlp.2.bias"%i for i in range(6)} if dense else set()
    before,after = dict(source.named_parameters()),dict(target.named_parameters())
    if set(before)-set(after) != removed or not set(after).issubset(before):
        raise ValueError("Parameter difference is not exactly the six redundant Dense head biases")
    for name,parameter in after.items():
        original = before[name]
        if (parameter.shape != original.shape or parameter.dtype != original.dtype
                or parameter.requires_grad != original.requires_grad):
            raise ValueError("Common parameter shape/dtype/gradient mapping differs")
    if any(before[name].shape != (8,) for name in removed):
        raise ValueError("Only eight-head terminal bias vectors may be removed")
    return {"common":{name:name for name in sorted(after)},
            "removed":sorted(removed),"removed_scalar_count":sum(before[name].numel() for name in removed),
            "scope":"C1-0 removes48; C1-a/b per-head projections were already bias-free",
            "common_raw_values_verified_by_this_mapping":False}
