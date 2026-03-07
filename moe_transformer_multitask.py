"""Backward-compatible import facade for the refactored MoE model package."""

from models.moe.attention import DenseFFN, DenseGeoSelfAttention, RealCoordTransformerLayer
from models.moe.backbone import RealCoordTransformerBackbone
from models.moe.common import Linear, MLP, ensure_batch_attr
from models.moe.expert_blocks import ETBlockInternal, ETBlockReal, ETExpert, _resolve_task_layers, resolve_task_layers
from models.moe.multitask import CoordinateDecoder, MultiTaskMoE

__all__ = [
    "ensure_batch_attr",
    "Linear",
    "MLP",
    "CoordinateDecoder",
    "DenseGeoSelfAttention",
    "DenseFFN",
    "RealCoordTransformerLayer",
    "RealCoordTransformerBackbone",
    "ETBlockReal",
    "ETBlockInternal",
    "ETExpert",
    "_resolve_task_layers",
    "resolve_task_layers",
    "MultiTaskMoE",
]
