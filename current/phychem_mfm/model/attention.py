from __future__ import annotations

import math
from typing import Tuple

import torch
import torch.nn as nn
from torch import Tensor

from .common import Linear
from .precision import fp32_island, island_tensor, matmul
from .v3_distance_bias import (validate_distance_bias_projection_bias,
    require_distance_bias_constructor,remove_initialized_head_bias,require_bias_free_attention)


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
        distance_bias_projection_bias: bool = True,
    ) -> None:
        super().__init__()
        self.distance_bias_projection_bias=validate_distance_bias_projection_bias(distance_bias_projection_bias)
        require_distance_bias_constructor(self.distance_bias_projection_bias,use_dist_bias=use_dist_bias)
        if dim % nheads != 0:
            raise ValueError("dim must be divisible by nheads")

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

        if not self.distance_bias_projection_bias:
            remove_initialized_head_bias(self.dist_mlp[2],heads=self.nheads)
        self.attn_drop = nn.Dropout(dropout) if dropout > 0 else nn.Identity()

    def forward(self, x: Tensor, pos: Tensor, mask: Tensor) -> Tuple[Tensor, Tensor]:
        require_bias_free_attention(self,x,pos)
        bsz, seqlen, _ = x.shape
        qkv = self.qkv(x).view(bsz, seqlen, 3, self.nheads, self.d_head)
        q, k, v = qkv.unbind(dim=2)

        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        precision = getattr(self, 'precision', 'fp32')
        logits = matmul(q, k.transpose(-2, -1), precision) / math.sqrt(self.d_head)

        with fp32_island(pos):
            diff = island_tensor('coordinate_subtraction', pos.float()[:, :, None, :] - pos.float()[:, None, :, :])
            dist2 = island_tensor('distance_squared', (diff * diff).sum(dim=-1))

        if self.use_dist_bias and self.dist_mlp is not None:
            bias = self.dist_mlp(dist2.unsqueeze(-1))
            bias = bias.permute(0, 3, 1, 2).contiguous()
            with fp32_island(logits):
                logits = island_tensor('attention_bias_add', logits.float() + bias.float())

        key_invalid = ~mask
        logits = logits.masked_fill(key_invalid[:, None, None, :], -1e9)

        if self.use_radius_mask:
            rad2 = self.radius * self.radius
            logits = logits.masked_fill(dist2[:, None, :, :] > rad2, -1e9)

        with fp32_island(logits):
            attn = island_tensor('attention_softmax', torch.softmax(logits.float(), dim=-1))
        attn = self.attn_drop(attn)

        ctx = matmul(attn, v, precision)
        ctx = ctx.transpose(1, 2).contiguous().view(bsz, seqlen, self.dim)

        out = self.proj(ctx)
        out = out * mask.unsqueeze(-1).to(out.dtype)
        return out, attn


class DenseFFN(nn.Module):
    def __init__(self, dim: int, ff_mult: int, dropout: float = 0.0) -> None:
        super().__init__()
        hidden = int(dim * ff_mult)
        self.net = nn.Sequential(
            Linear(dim, hidden),
            nn.SiLU(),
            nn.Dropout(dropout) if dropout > 0 else nn.Identity(),
            Linear(hidden, dim),
        )

    def forward(self, x: Tensor) -> Tensor:
        return self.net(x)


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
        distance_bias_projection_bias: bool = True,
    ) -> None:
        super().__init__()
        self.norm1 = nn.LayerNorm(dim)
        self.attn = DenseGeoSelfAttention(
            dim=dim,
            nheads=nheads,
            dropout=dropout,
            use_dist_bias=use_dist_bias,
            use_radius_mask=use_radius_mask,
            radius=radius,
            distance_bias_projection_bias=distance_bias_projection_bias,
        )
        self.norm2 = nn.LayerNorm(dim)
        self.ffn = DenseFFN(dim=dim, ff_mult=ff_mult, dropout=dropout)

    def forward(self, x: Tensor, pos: Tensor, mask: Tensor) -> Tensor:
        with fp32_island(x):
            normalized = island_tensor('layer_norm', self.norm1(x.float()))
        attn_out, _ = self.attn(normalized, pos, mask)
        x = x + attn_out
        with fp32_island(x):
            normalized = island_tensor('layer_norm', self.norm2(x.float()))
        x = x + self.ffn(normalized)
        x = x * mask.unsqueeze(-1).to(x.dtype)
        return x
