from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor
from torch_geometric.data import Data
from torch_geometric.utils import to_dense_batch
from torch.utils.checkpoint import checkpoint

from .attention import RealCoordTransformerLayer
from .v3_distance_bias import (validate_distance_bias_projection_bias,
    require_distance_bias_constructor, require_distance_bias_backbone)
from .v3_ffn_projection import (LEGACY_FFN, validate_ffn_projection_mode,
    require_ffn_constructor, require_ffn_backbone)
from .common import ensure_batch_attr
from .v3_geometry_fp32 import (LEGACY_GEOMETRY,
    validate_geometry_mode, require_geometry_constructor, require_geometry_binding)
from .v3_attention_projection import (LEGACY_PROJECTION, BLOCKED_PROJECTION,
    validate_projection_mode, require_projection_constructor, require_projection_backbone)
from .v3_attention_numerics import (LEGACY_AGGREGATION, CENTERED_FP32, validate_aggregation_mode,
                                    require_centered_backbone, require_centered_f32_context, require_centered_packed_atoms)


class RealCoordTransformerBackbone(nn.Module):
    """Node-level backbone conditioned on real coordinates only."""

    def __init__(
        self,
        n_atom_types: int,
        dim: int,
        layers: int = 6,
        heads: int = 8,
        ff_mult: int = 4,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
        activation_checkpointing: bool = False,
        attention_aggregation_mode: str = LEGACY_AGGREGATION,
        attention_projection_mode: str = LEGACY_PROJECTION,
        geometry_mode: str = LEGACY_GEOMETRY,
        ffn_projection_mode: str = LEGACY_FFN,
        distance_bias_projection_bias: bool = True,
    ) -> None:
        super().__init__()
        self.distance_bias_projection_bias = validate_distance_bias_projection_bias(distance_bias_projection_bias)
        require_distance_bias_constructor(self.distance_bias_projection_bias,
            use_dist_bias=use_dist_bias, dim=dim, heads=heads, layers=layers)
        self.attention_aggregation_mode = validate_aggregation_mode(attention_aggregation_mode)
        self.attention_projection_mode = validate_projection_mode(attention_projection_mode)
        self.geometry_mode = validate_geometry_mode(geometry_mode)
        self.ffn_projection_mode = validate_ffn_projection_mode(ffn_projection_mode)
        require_ffn_constructor(self.ffn_projection_mode, dim=dim, ff_mult=ff_mult,
            dropout=dropout, layers=layers, heads=heads,
            aggregation=self.attention_aggregation_mode,
            projection=self.attention_projection_mode, geometry=self.geometry_mode)
        require_projection_constructor(self.attention_projection_mode, dim=dim, heads=heads,
            layers=layers, aggregation=self.attention_aggregation_mode, dropout=dropout)
        require_geometry_constructor(self.geometry_mode, dim=dim, heads=heads, layers=layers,
            aggregation=self.attention_aggregation_mode, projection=self.attention_projection_mode, dropout=dropout)
        self.n_atom_types = int(n_atom_types)
        self.dim = int(dim)
        if type(activation_checkpointing) is not bool:
            raise ValueError("activation_checkpointing must be a boolean")
        self.activation_checkpointing = activation_checkpointing

        self.atom_emb = nn.Embedding(self.n_atom_types, self.dim)
        self.layers = nn.ModuleList(
            [
                RealCoordTransformerLayer(
                    dim=self.dim,
                    nheads=heads,
                    ff_mult=ff_mult,
                    dropout=dropout,
                    use_dist_bias=use_dist_bias,
                    use_radius_mask=use_radius_mask,
                    radius=radius,
                    attention_aggregation_mode=self.attention_aggregation_mode,
                    attention_projection_mode=self.attention_projection_mode,
                    geometry_mode=self.geometry_mode,
                    ffn_projection_mode=self.ffn_projection_mode,
                    distance_bias_projection_bias=self.distance_bias_projection_bias,
                )
                for _ in range(layers)
            ]
        )
        self.out_norm = nn.LayerNorm(self.dim)

    def forward(self, data: Data) -> Tensor:
        if getattr(data, "pos", None) is None:
            raise ValueError("RealCoordTransformerBackbone requires data.pos")

        require_distance_bias_backbone(self, expected=self.distance_bias_projection_bias)
        require_ffn_backbone(self, expected_mode=self.ffn_projection_mode)
        require_geometry_binding(self, expected_mode=self.geometry_mode)
        if self.attention_projection_mode == BLOCKED_PROJECTION:
            require_projection_backbone(self, expected_mode=BLOCKED_PROJECTION)
        if self.attention_aggregation_mode == CENTERED_FP32:
            require_centered_backbone(self)
            require_centered_f32_context(self, data.pos)
            require_centered_packed_atoms(data.pos)

        batch = ensure_batch_attr(data)

        x_raw = data.x
        if x_raw.dim() == 2:
            x_raw = x_raw[:, 0]
        x_idx = x_raw.long().clamp(min=0, max=self.n_atom_types - 1)

        x = self.atom_emb(x_idx)
        x_dense, mask = to_dense_batch(x, batch, fill_value=0.0)
        pos_dense, _ = to_dense_batch(data.pos.to(torch.float32), batch, fill_value=0.0)

        for layer in self.layers:
            if self.activation_checkpointing and self.training and torch.is_grad_enabled():
                # Recompute the large distance-bias intermediates during backward.
                # Non-reentrant checkpointing also supports per-task autograd.grad probes.
                x_dense = checkpoint(layer, x_dense, pos_dense, mask, use_reentrant=False)
            else:
                x_dense = layer(x_dense, pos_dense, mask)

        x_dense = self.out_norm(x_dense) * mask.unsqueeze(-1).to(x_dense.dtype)
        return x_dense[mask]
