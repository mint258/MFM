from __future__ import annotations

import math
from typing import Optional

import torch
import torch.nn as nn
from torch import Tensor
from torch_geometric.data import Batch, Data


def ensure_batch_attr(data: Data) -> Tensor:
    """Return a 1D `batch` vector for node-to-graph assignment."""
    if isinstance(data, Batch):
        return data.batch
    if getattr(data, "batch", None) is None:
        return torch.zeros(data.num_nodes, dtype=torch.long, device=data.x.device)
    return data.batch


def _init_linear(w: Tensor, b: Optional[Tensor] = None, initializer: str = "xavier_uniform") -> None:
    """Self-contained linear initialization helper."""
    if initializer in {"glorot", "xavier_uniform"}:
        nn.init.xavier_uniform_(w)
    elif initializer == "xavier_normal":
        nn.init.xavier_normal_(w)
    elif initializer == "kaiming_uniform":
        nn.init.kaiming_uniform_(w, a=math.sqrt(5))
    else:
        nn.init.xavier_uniform_(w)
    if b is not None:
        nn.init.zeros_(b)


class Linear(nn.Linear):
    """`nn.Linear` with explicit and local initialization policy."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        bias: bool = True,
        weight_initializer: str = "xavier_uniform",
    ) -> None:
        self.weight_initializer = weight_initializer
        super().__init__(in_channels, out_channels, bias=bias)

    def reset_parameters(self) -> None:
        _init_linear(self.weight, self.bias, initializer=self.weight_initializer)


class MLP(nn.Module):
    """Simple SiLU MLP used by model components."""

    def __init__(
        self,
        in_dim: int,
        hidden_dim: int,
        out_dim: int,
        num_layers: int = 3,
        dropout: float = 0.0,
    ) -> None:
        super().__init__()
        if num_layers < 1:
            raise ValueError("num_layers must be >= 1")

        layers: list[nn.Module] = []
        if num_layers == 1:
            layers.append(Linear(in_dim, out_dim))
        else:
            layers.append(Linear(in_dim, hidden_dim))
            layers.append(nn.SiLU())
            for _ in range(num_layers - 2):
                layers.append(Linear(hidden_dim, hidden_dim))
                layers.append(nn.SiLU())
                if dropout > 0:
                    layers.append(nn.Dropout(dropout))
            layers.append(Linear(hidden_dim, out_dim))

        self.net = nn.Sequential(*layers)

    def forward(self, x: Tensor) -> Tensor:
        return self.net(x)
