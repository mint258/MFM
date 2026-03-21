from __future__ import annotations

import torch
import torch.nn as nn
from torch import Tensor
from torch_geometric.data import Data
from torch_geometric.utils import to_dense_batch

from .attention import RealCoordTransformerLayer
from .common import ensure_batch_attr


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
    ) -> None:
        super().__init__()
        self.n_atom_types = int(n_atom_types)
        self.dim = int(dim)

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
                )
                for _ in range(layers)
            ]
        )
        self.out_norm = nn.LayerNorm(self.dim)

    def forward(self, data: Data) -> Tensor:
        if getattr(data, "pos", None) is None:
            raise ValueError("RealCoordTransformerBackbone requires data.pos")

        batch = ensure_batch_attr(data)

        x_raw = data.x
        if x_raw.dim() == 2:
            x_raw = x_raw[:, 0]
        x_idx = x_raw.long().clamp(min=0, max=self.n_atom_types - 1)

        x = self.atom_emb(x_idx)
        x_dense, mask = to_dense_batch(x, batch, fill_value=0.0)
        pos_dense, _ = to_dense_batch(data.pos.to(torch.float32), batch, fill_value=0.0)

        for layer in self.layers:
            x_dense = layer(x_dense, pos_dense, mask)

        x_dense = self.out_norm(x_dense) * mask.unsqueeze(-1).to(x_dense.dtype)
        return x_dense[mask]
