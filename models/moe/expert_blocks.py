from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
from torch import Tensor
from torch_geometric.utils import to_dense_batch

from .attention import DenseFFN, DenseGeoSelfAttention
from .common import Linear


class ETBlockReal(nn.Module):
    """Expert block with read-only real coordinates."""

    def __init__(
        self,
        dim: int,
        nheads: int = 4,
        ff_mult: int = 2,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
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
        )
        self.norm2 = nn.LayerNorm(dim)
        self.ffn = DenseFFN(dim=dim, ff_mult=ff_mult, dropout=dropout)

    def forward(self, x: Tensor, pos: Tensor, batch: Tensor) -> Tensor:
        x_dense, mask = to_dense_batch(x, batch, fill_value=0.0)
        pos_dense, _ = to_dense_batch(pos.to(torch.float32), batch, fill_value=0.0)

        attn_out, _ = self.attn(self.norm1(x_dense), pos_dense, mask)
        x_dense = x_dense + attn_out
        x_dense = x_dense + self.ffn(self.norm2(x_dense))
        x_dense = x_dense * mask.unsqueeze(-1).to(x_dense.dtype)
        return x_dense[mask]


class ETBlockInternal(nn.Module):
    """Expert block with learnable internal coordinates."""

    def __init__(
        self,
        dim: int,
        nheads: int = 4,
        ff_mult: int = 2,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
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
        )
        self.norm2 = nn.LayerNorm(dim)
        self.ffn = DenseFFN(dim=dim, ff_mult=ff_mult, dropout=dropout)
        self.coord_gate = nn.Sequential(Linear(dim, 1), nn.Sigmoid())

    def forward(self, x: Tensor, r: Tensor, batch: Tensor) -> Tuple[Tensor, Tensor]:
        x_dense, mask = to_dense_batch(x, batch, fill_value=0.0)
        r_dense, _ = to_dense_batch(r.to(torch.float32), batch, fill_value=0.0)

        attn_out, attn = self.attn(self.norm1(x_dense), r_dense, mask)
        x_dense = x_dense + attn_out
        x_dense = x_dense + self.ffn(self.norm2(x_dense))
        x_dense = x_dense * mask.unsqueeze(-1).to(x_dense.dtype)

        # Internal coordinate update with no real-position access.
        attn_mean = attn.mean(dim=1)
        diff = r_dense[:, :, None, :] - r_dense[:, None, :, :]
        delta = (attn_mean.unsqueeze(-1) * diff).sum(dim=2)
        gate = self.coord_gate(x_dense)
        r_dense = (r_dense + gate * delta) * mask.unsqueeze(-1).to(r_dense.dtype)

        return x_dense[mask], r_dense[mask]


class ETExpert(nn.Module):
    """Expert with independent real and internal stacks."""

    def __init__(
        self,
        dim: int,
        real_layers: int,
        int_layers: int,
        nheads: int = 4,
        ff_mult: int = 2,
        dropout: float = 0.0,
        use_dist_bias: bool = True,
        use_radius_mask: bool = False,
        radius: float = 8.0,
    ) -> None:
        super().__init__()
        self.real_layers = nn.ModuleList(
            [
                ETBlockReal(
                    dim,
                    nheads=nheads,
                    ff_mult=ff_mult,
                    dropout=dropout,
                    use_dist_bias=use_dist_bias,
                    use_radius_mask=use_radius_mask,
                    radius=radius,
                )
                for _ in range(int(real_layers))
            ]
        )
        self.int_layers = nn.ModuleList(
            [
                ETBlockInternal(
                    dim,
                    nheads=nheads,
                    ff_mult=ff_mult,
                    dropout=dropout,
                    use_dist_bias=use_dist_bias,
                    use_radius_mask=use_radius_mask,
                    radius=radius,
                )
                for _ in range(int(int_layers))
            ]
        )

        self.pos_mlp: Optional[nn.Module]
        if len(self.int_layers) > 0:
            self.pos_mlp = nn.Sequential(Linear(dim, dim), nn.SiLU(), Linear(dim, 3))
        else:
            self.pos_mlp = None

        self.out_norm = nn.LayerNorm(dim)

    def forward(self, x: Tensor, *, batch: Tensor, pos: Optional[Tensor] = None) -> Tensor:
        if len(self.real_layers) > 0:
            if pos is None:
                raise ValueError("ETExpert with real_layers requires `pos`.")
            for block in self.real_layers:
                x = block(x, pos, batch)

        if len(self.int_layers) > 0:
            if self.pos_mlp is None:
                raise RuntimeError("pos_mlp is required when internal layers are enabled.")
            r = self.pos_mlp(x)
            for block in self.int_layers:
                x, r = block(x, r, batch)

        return self.out_norm(x)


def resolve_task_layers(
    base_real: int,
    base_int: int,
    overrides: Optional[Dict[str, int]],
    key: str,
) -> int:
    """Resolve per-task real/int layer overrides."""
    if overrides is None:
        return base_real if key == "real" else base_int
    default = base_real if key == "real" else base_int
    return int(overrides.get(key, default))


def _resolve_task_layers(
    base_real: int,
    base_int: int,
    overrides: Optional[Dict[str, int]],
    key: str,
) -> int:
    """Backward-compatible alias kept for existing imports."""
    return resolve_task_layers(base_real, base_int, overrides, key)
