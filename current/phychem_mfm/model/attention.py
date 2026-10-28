from __future__ import annotations

import math
from typing import Tuple

import torch
import torch.nn as nn
from torch import Tensor

from .common import Linear
from .v3_residual_accumulation import (LEGACY_RESIDUAL, TWO_SUM_RESIDUAL,
    validate_residual_accumulation_mode, residual_accumulation_mode,
    require_residual_constructor, require_residual_layer, residual_accumulation)
from .v3_ffn_projection import (LEGACY_FFN, BLOCKED_FFN, validate_ffn_projection_mode,
    ffn_projection_mode, require_ffn_constructor, require_ffn_layout, ffn_projection)
from .v3_geometry_fp32 import (LEGACY_GEOMETRY, RESIDUAL_GEOMETRY,
    validate_geometry_mode, require_geometry_constructor, residual_pairwise_distance_fp32)
from .v3_attention_projection import (LEGACY_PROJECTION, BLOCKED_PROJECTION,
    validate_projection_mode, require_projection_constructor, attention_projection)
from .v3_attention_numerics import (LEGACY_AGGREGATION, CENTERED_FP32, validate_aggregation_mode,
                                    require_centered_attention_context, centered_attention_value)
from .v3_numeric_stability import COMPENSATED, numeric_mode, compensated_pairwise_norm3


class DenseGeoSelfAttention(nn.Module):
    """Dense self-attention with optional distance bias and radius mask."""

    def __init__(
        self,
        dim: int,
        nheads: int,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
        attention_aggregation_mode: str = LEGACY_AGGREGATION,
        attention_projection_mode: str = LEGACY_PROJECTION,
        geometry_mode: str = LEGACY_GEOMETRY,
    ) -> None:
        super().__init__()
        if dim % nheads != 0:
            raise ValueError("dim must be divisible by nheads")

        self.attention_aggregation_mode = validate_aggregation_mode(attention_aggregation_mode)
        self.attention_projection_mode = validate_projection_mode(attention_projection_mode)
        self.geometry_mode = validate_geometry_mode(geometry_mode)
        require_projection_constructor(self.attention_projection_mode, dim=dim, heads=nheads,
            aggregation=self.attention_aggregation_mode, dropout=dropout)
        require_geometry_constructor(self.geometry_mode, dim=dim, heads=nheads,
            aggregation=self.attention_aggregation_mode, projection=self.attention_projection_mode, dropout=dropout)
        self.dim = dim
        self.nheads = nheads
        self.d_head = dim // nheads

        self.qkv = Linear(dim, 3 * dim)
        self.proj = Linear(dim, dim)

        self.use_dist_bias = use_dist_bias
        self.use_radius_mask = use_radius_mask
        self.radius = float(radius)

        if use_dist_bias:
            self.dist_mlp = nn.Sequential(
                Linear(1, dim),
                nn.SiLU(),
                Linear(dim, nheads),
            )
        else:
            self.dist_mlp = None

        self.attn_drop = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x: Tensor, pos: Tensor, mask: Tensor) -> Tuple[Tensor, Tensor]:
        if self.attention_aggregation_mode == CENTERED_FP32:
            require_centered_attention_context(self, mask, x, pos)
        bsz, seqlen, _ = x.shape
        qkv = (attention_projection(self, self.qkv, x)
               if self.attention_projection_mode == BLOCKED_PROJECTION else self.qkv(x))
        qkv = qkv.view(bsz, seqlen, 3, self.nheads, self.d_head)
        q, k, v = qkv.unbind(dim=2)

        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        logits = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.d_head)

        if self.geometry_mode == RESIDUAL_GEOMETRY:
            dist2 = residual_pairwise_distance_fp32(pos, pos, squared=True)
        elif numeric_mode(self) == COMPENSATED:
            dist2 = compensated_pairwise_norm3(pos, pos, squared=True)
        else:
            diff = pos[:, :, None, :] - pos[:, None, :, :]
            dist2 = (diff * diff).sum(dim=-1)

        if self.use_dist_bias and self.dist_mlp is not None:
            bias = self.dist_mlp(dist2.unsqueeze(-1))
            bias = bias.permute(0, 3, 1, 2).contiguous()
            logits = logits + bias

        key_invalid = ~mask
        logits = logits.masked_fill(key_invalid[:, None, None, :], -1e9)

        if self.use_radius_mask:
            rad2 = self.radius * self.radius
            logits = logits.masked_fill(dist2[:, None, :, :] > rad2, -1e9)

        attn = torch.softmax(logits, dim=-1)
        attn = self.attn_drop(attn)

        if self.attention_aggregation_mode == CENTERED_FP32:
            ctx = centered_attention_value(attn, v, mask, attention_dropout=self.attn_drop)
        else:
            ctx = torch.matmul(attn, v)
        ctx = ctx.transpose(1, 2).contiguous().view(bsz, seqlen, self.dim)

        out = (attention_projection(self, self.proj, ctx)
               if self.attention_projection_mode == BLOCKED_PROJECTION else self.proj(ctx))
        out = out * mask.unsqueeze(-1).to(out.dtype)
        return out, attn


class DenseFFN(nn.Module):
    def __init__(self, dim: int, ff_mult: int, dropout: float = 0.0,
                 ffn_projection_mode: str = LEGACY_FFN) -> None:
        super().__init__()
        self.ffn_projection_mode = validate_ffn_projection_mode(ffn_projection_mode)
        require_ffn_constructor(self.ffn_projection_mode, dim=dim, ff_mult=ff_mult, dropout=dropout)
        hidden = int(dim * ff_mult)
        self.net = nn.Sequential(
            Linear(dim, hidden),
            nn.SiLU(),
            nn.Dropout(dropout) if dropout > 0 else nn.Identity(),
            Linear(hidden, dim),
        )

    def forward(self, x: Tensor) -> Tensor:
        if ffn_projection_mode(self) == LEGACY_FFN:
            return self.net(x)
        require_ffn_layout(self)
        hidden = ffn_projection(self, self.net[0], x)
        hidden = self.net[2](self.net[1](hidden))
        return ffn_projection(self, self.net[3], hidden)


class RealCoordTransformerLayer(nn.Module):
    def __init__(
        self,
        dim: int,
        nheads: int,
        ff_mult: int,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
        attention_aggregation_mode: str = LEGACY_AGGREGATION,
        attention_projection_mode: str = LEGACY_PROJECTION,
        geometry_mode: str = LEGACY_GEOMETRY,
        ffn_projection_mode: str = LEGACY_FFN,
        residual_accumulation_mode: str = LEGACY_RESIDUAL,
    ) -> None:
        super().__init__()
        self.residual_accumulation_mode = validate_residual_accumulation_mode(residual_accumulation_mode)
        require_residual_constructor(self.residual_accumulation_mode, dim=dim, ff_mult=ff_mult,
            dropout=dropout, heads=nheads, aggregation=attention_aggregation_mode,
            projection=attention_projection_mode, geometry=geometry_mode, ffn=ffn_projection_mode)
        require_ffn_constructor(ffn_projection_mode, dim=dim, ff_mult=ff_mult, dropout=dropout,
            heads=nheads, aggregation=attention_aggregation_mode,
            projection=attention_projection_mode, geometry=geometry_mode)
        self.norm1 = nn.LayerNorm(dim)
        self.attn = DenseGeoSelfAttention(
            dim=dim,
            nheads=nheads,
            dropout=dropout,
            use_dist_bias=use_dist_bias,
            use_radius_mask=use_radius_mask,
            radius=radius,
            attention_aggregation_mode=attention_aggregation_mode,
            attention_projection_mode=attention_projection_mode,
            geometry_mode=geometry_mode,
        )
        self.norm2 = nn.LayerNorm(dim)
        self.ffn = DenseFFN(dim=dim, ff_mult=ff_mult, dropout=dropout,
                            ffn_projection_mode=ffn_projection_mode)

    def forward(self, x: Tensor, pos: Tensor, mask: Tensor) -> Tensor:
        if residual_accumulation_mode(self) == LEGACY_RESIDUAL:
            attn_out, _ = self.attn(self.norm1(x), pos, mask)
            x = x + attn_out
            x = x + self.ffn(self.norm2(x))
            x = x * mask.unsqueeze(-1).to(x.dtype)
            return x
        require_residual_layer(self)
        original = x
        attn_out, _ = self.attn(self.norm1(original), pos, mask)
        intermediate = original + attn_out  # Original rounded u, no tail injection.
        feedforward = self.ffn(self.norm2(intermediate))
        result = residual_accumulation(self, original, attn_out, feedforward)
        return result * mask.unsqueeze(-1).to(result.dtype)
