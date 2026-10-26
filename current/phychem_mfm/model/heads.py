from __future__ import annotations

from typing import Dict, Optional

import torch
import torch.nn as nn
from torch import Tensor
from torch_geometric.nn import global_add_pool, global_max_pool, global_mean_pool
from torch_geometric.utils import to_dense_batch

from .common import Linear
from .v3_numeric_stability import (COMPENSATED, numeric_mode, compensated_index_add,
    compensated_pool, compensated_norm3, compensated_squared_norm3, compensated_pairwise_norm3)


class CoordinateDecoder(nn.Module):
    """Historical geometry prediction head, now attached to a configurable task adapter."""

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.shared_decoder = nn.Sequential(
            Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
        )
        self.coord_head = Linear(dim, 3)

    def forward(self, atom_repr: Tensor) -> Tensor:
        return self.coord_head(self.shared_decoder(atom_repr))


class ResidualCoordinateDecoder(nn.Module):
    """Optional PM7-distance reconstruction head in the noisy input frame.

    Scalar pair weights use latent features and the same squared distances as
    the backbone. Relative vectors provide a coordinate update; H0 remains an
    invariant representation. This candidate does not change the training loss
    or read clean target coordinates.
    """

    def __init__(self, dim: int, *, hidden_dim: int = 32, correction_scale: float = 0.1,
                 normalization: str = "molecule", radius: float = 5.0) -> None:
        super().__init__()
        if hidden_dim < 2 or correction_scale <= 0:
            raise ValueError("Residual geometry hidden_dim must be at least 2 and correction_scale must be positive")
        self.hidden_dim = int(hidden_dim)
        self.correction_scale = float(correction_scale)
        if normalization not in {"molecule", "neighbors"} or radius <= 0:
            raise ValueError("Invalid residual normalization or radius")
        self.normalization, self.radius = normalization, float(radius)
        self.node_proj = nn.Sequential(
            Linear(dim, self.hidden_dim), nn.LayerNorm(self.hidden_dim), nn.SiLU(),
        )
        self.pair_weight = nn.Sequential(
            Linear(2, self.hidden_dim), nn.SiLU(), Linear(self.hidden_dim, 1),
        )
        # A zero final matrix would block the first-step gradient into H0.
        nn.init.normal_(self.pair_weight[-1].weight, mean=0.0, std=1e-3)
        nn.init.zeros_(self.pair_weight[-1].bias)

    def forward(self, atom_repr: Tensor, pos: Tensor, batch: Tensor) -> Tensor:
        features, mask = to_dense_batch(self.node_proj(atom_repr), batch, fill_value=0.0)
        coordinates, _ = to_dense_batch(pos.float(), batch, fill_value=0.0)
        relative = coordinates[:, :, None, :] - coordinates[:, None, :, :]
        distance2 = (compensated_squared_norm3(relative) if numeric_mode(self) == COMPENSATED
                     else relative.square().sum(dim=-1))
        affinity = torch.matmul(features, features.transpose(-1, -2)).float() / self.hidden_dim ** 0.5
        pair_input = torch.stack((affinity, distance2), dim=-1)
        weights = torch.tanh(self.pair_weight(pair_input).squeeze(-1)).float()
        pair_mask = mask[:, :, None] & mask[:, None, :]
        weights = weights * pair_mask.to(weights.dtype)
        if self.normalization == "neighbors":
            neighbors = pair_mask & (distance2 < self.radius ** 2) & (distance2 > 0)
            weights = weights * neighbors.to(weights.dtype)
            count = neighbors.sum(dim=2).clamp_min(1).to(coordinates.dtype).unsqueeze(-1)
        else:
            count = mask.sum(dim=1).clamp_min(1).to(coordinates.dtype).view(-1, 1, 1)
        if numeric_mode(self) == COMPENSATED:
            terms = weights.unsqueeze(-1) * relative
            groups, atoms = coordinates.shape[:2]
            index = torch.arange(groups * atoms, device=pos.device).repeat_interleave(atoms)
            correction = compensated_index_add(coordinates.new_zeros((groups * atoms, 3)),
                index, terms.reshape(-1, 3)).reshape(groups, atoms, 3) / count
        else:
            correction = (weights.unsqueeze(-1) * relative).sum(dim=2) / count
        decoded = coordinates + self.correction_scale * correction
        return decoded[mask]


class EquivariantDenoisingHead(nn.Module):
    """Invariant H0 and scalar pair coefficients predict an equivariant noise vector.

    Edges are generated within molecules without torch-cluster. Pair MLPs are
    checkpointed in bounded chunks, including feature gathering, so full-width
    pair representations are not all retained for backward. No targets enter
    this module. Optional scalar messages preserve the same symmetries.
    """

    def __init__(self, dim: int, *, radius: float = 5.0, rbf_count: int = 32,
                 hidden_dim: int = 64, normalization: str = "none",
                 message_layers: int = 0, pair_chunk_size: int = 8192) -> None:
        super().__init__()
        if radius <= 0 or rbf_count < 2 or hidden_dim < 2 or pair_chunk_size < 1:
            raise ValueError("Invalid equivariant head dimensions/radius")
        if normalization not in {"none", "sqrt_neighbors"} or message_layers not in {0, 1, 2}:
            raise ValueError("Invalid equivariant normalization/message layers")
        self.radius, self.normalization = float(radius), normalization
        self.message_layers, self.pair_chunk_size = int(message_layers), int(pair_chunk_size)
        self.register_buffer("rbf_centers", torch.linspace(0.0, self.radius, rbf_count))
        self.rbf_gamma = ((rbf_count - 1) / self.radius) ** 2
        self.pair_mlp = nn.Sequential(Linear(2 * dim + rbf_count, hidden_dim), nn.SiLU(),
                                      Linear(hidden_dim, hidden_dim), nn.SiLU(), Linear(hidden_dim, 1))
        nn.init.normal_(self.pair_mlp[-1].weight, std=1e-3)
        nn.init.zeros_(self.pair_mlp[-1].bias)
        self.messages = nn.ModuleList([
            nn.Sequential(Linear(2 * dim + rbf_count, hidden_dim), nn.SiLU(), Linear(hidden_dim, dim))
            for _ in range(message_layers)
        ])

    def _edges(self, pos: Tensor, batch: Tensor) -> tuple[Tensor, Tensor]:
        # Stable sorting also accepts permutations across molecule boundaries.
        order = torch.argsort(batch, stable=True)
        sorted_batch = batch[order]
        _, dense_batch = torch.unique_consecutive(sorted_batch, return_inverse=True)
        coordinates, mask = to_dense_batch(pos[order], dense_batch)
        distance = (compensated_pairwise_norm3(coordinates, coordinates)
                    if numeric_mode(self) == COMPENSATED else torch.cdist(coordinates, coordinates))
        valid = mask[:, :, None] & mask[:, None, :]
        eye = torch.eye(distance.size(-1), dtype=torch.bool, device=pos.device)
        graph, src, dst = torch.where(valid & ~eye & (distance < self.radius) & (distance > 1e-8))
        offsets = torch.cat((batch.new_zeros(1), mask.sum(1).cumsum(0)[:-1]))
        return order[offsets[graph] + src], order[offsets[graph] + dst]

    def _features(self, h: Tensor, pos: Tensor, src: Tensor, dst: Tensor):
        relative = pos[src] - pos[dst]
        distance = (compensated_norm3(relative) if numeric_mode(self) == COMPENSATED
                    else relative.norm(dim=-1)).clamp_min(1e-8)
        rbf = torch.exp(-self.rbf_gamma * (distance[:, None] - self.rbf_centers) ** 2)
        rbf = rbf * (0.5 * (1.0 + torch.cos(torch.pi * distance / self.radius)))[:, None]
        return torch.cat((h[src], h[dst], rbf.to(h.dtype)), dim=-1), relative / distance[:, None]

    def _predict_chunk(self, h, pos, src, dst):
        feature, direction = self._features(h, pos, src, dst)
        return self.pair_mlp(feature) * direction

    def forward(self, atom_repr: Tensor, pos: Tensor, batch: Tensor) -> Tensor:
        from torch.utils.checkpoint import checkpoint
        if pos.ndim != 2 or pos.size(-1) != 3 or len(atom_repr) != len(pos) or len(batch) != len(pos):
            raise ValueError("Head expects packed atoms, coordinates and molecule IDs")
        if not len(pos):
            return pos.clone()
        src, dst = self._edges(pos, batch)
        h = atom_repr
        degree = torch.bincount(src, minlength=len(pos)).clamp_min(1).to(pos.dtype).sqrt()[:, None]
        for layer in self.messages:
            def message_chunk(features, coordinates, i, j, module=layer):
                return module(self._features(features, coordinates, i, j)[0])
            aggregated = torch.zeros_like(h)
            for start in range(0, len(src), self.pair_chunk_size):
                i, j = src[start:start + self.pair_chunk_size], dst[start:start + self.pair_chunk_size]
                value = checkpoint(message_chunk, h, pos, i, j, use_reentrant=False) if torch.is_grad_enabled() else message_chunk(h, pos, i, j)
                aggregated = (compensated_index_add(aggregated, i, value)
                              if numeric_mode(self) == COMPENSATED else aggregated.index_add(0, i, value))
            h = h + aggregated / degree.to(h.dtype)
        noise = torch.zeros_like(pos)
        for start in range(0, len(src), self.pair_chunk_size):
            i, j = src[start:start + self.pair_chunk_size], dst[start:start + self.pair_chunk_size]
            value = checkpoint(self._predict_chunk, h, pos, i, j, use_reentrant=False) if torch.is_grad_enabled() else self._predict_chunk(h, pos, i, j)
            noise = (compensated_index_add(noise, i, value.to(pos.dtype))
                     if numeric_mode(self) == COMPENSATED else noise.index_add(0, i, value.to(pos.dtype)))
        return noise / degree if self.normalization == "sqrt_neighbors" else noise


class LearnedPoolingMixer(nn.Module):
    def __init__(self, dim: int) -> None:
        super().__init__()
        self.sum_proj = Linear(dim, dim)
        self.mean_proj = Linear(dim, dim)
        self.max_proj = Linear(dim, dim)
        self.pool_logits = nn.Parameter(torch.zeros(3))

    def forward(self, atom_repr: Tensor, batch: Tensor) -> Tensor:
        if numeric_mode(self) == COMPENSATED:
            graphs = int(batch.max()) + 1 if len(batch) else 0
            pooled = torch.stack((
                self.sum_proj(compensated_pool(atom_repr, batch, graphs, "sum")),
                self.mean_proj(compensated_pool(atom_repr, batch, graphs, "mean")),
                self.max_proj(global_max_pool(atom_repr, batch)),
            ), dim=1)
        else:
            pooled = torch.stack(
                (
                    self.sum_proj(global_add_pool(atom_repr, batch)),
                    self.mean_proj(global_mean_pool(atom_repr, batch)),
                    self.max_proj(global_max_pool(atom_repr, batch)),
                ),
                dim=1,
            )
        weights = torch.softmax(self.pool_logits, dim=0)
        return (pooled * weights.view(1, 3, 1)).sum(dim=1)

    def weight_dict(self) -> Dict[str, float]:
        weights = torch.softmax(self.pool_logits.detach().float(), dim=0).cpu()
        return {"sum": float(weights[0]), "mean": float(weights[1]), "max": float(weights[2])}


class UnifiedGraphPooling(nn.Module):
    """Single pooling implementation shared by pretraining and downstream APIs."""

    SUPPORTED = ("mean", "sum", "max", "summary")

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.dim = int(dim)

    def output_dim(self, pooling: str) -> int:
        return self.dim * 3 + 1 if pooling == "summary" else self.dim

    def forward(self, atom_repr: Tensor, batch: Tensor, pooling: str = "mean") -> Tensor:
        pooling = str(pooling).lower()
        if numeric_mode(self) == COMPENSATED:
            graphs = int(batch.max()) + 1 if len(batch) else 0
            if pooling in ('mean', 'sum'):
                return compensated_pool(atom_repr, batch, graphs, pooling)
            if pooling == 'summary':
                mean = compensated_pool(atom_repr, batch, graphs, 'mean')
                maximum = global_max_pool(atom_repr, batch)
                second = compensated_pool(atom_repr.square(), batch, graphs, 'mean')
                std = torch.sqrt(torch.clamp(second - mean.square(), min=0.0) + 1e-9)
                counts = torch.bincount(batch, minlength=graphs).to(atom_repr.dtype).clamp_min(1.0)
                return torch.cat((mean, maximum, std, counts.log().unsqueeze(-1)), dim=-1)
        if pooling == "mean":
            return global_mean_pool(atom_repr, batch)
        if pooling == "sum":
            return global_add_pool(atom_repr, batch)
        if pooling == "max":
            return global_max_pool(atom_repr, batch)
        if pooling == "summary":
            mean = global_mean_pool(atom_repr, batch)
            maximum = global_max_pool(atom_repr, batch)
            second = global_mean_pool(atom_repr.square(), batch)
            std = torch.sqrt(torch.clamp(second - mean.square(), min=0.0) + 1e-9)
            counts = torch.bincount(batch, minlength=mean.size(0)).to(atom_repr.dtype).clamp_min(1.0)
            return torch.cat((mean, maximum, std, counts.log().unsqueeze(-1)), dim=-1)
        raise ValueError(f"Unsupported pooling '{pooling}', choose from {self.SUPPORTED}")


class TaskSpecificGraphHead(nn.Module):
    def __init__(self, input_dim: int, output_dim: int = 1) -> None:
        super().__init__()
        self.node_proj = nn.Sequential(
            Linear(input_dim, input_dim),
            nn.LayerNorm(input_dim),
            nn.ReLU(),
        )
        self.pool_logits = nn.Parameter(torch.zeros(3))
        self.output = Linear(input_dim, output_dim)

    def forward(self, node_repr: Tensor, batch: Tensor) -> Tensor:
        hidden = self.node_proj(node_repr)
        if numeric_mode(self) == COMPENSATED:
            graphs = int(batch.max()) + 1 if len(batch) else 0
            pooled = torch.stack((compensated_pool(hidden, batch, graphs, "sum"),
                                  compensated_pool(hidden, batch, graphs, "mean"),
                                  global_max_pool(hidden, batch)), dim=1)
        else:
            pooled = torch.stack(
                (
                    global_add_pool(hidden, batch),
                    global_mean_pool(hidden, batch),
                    global_max_pool(hidden, batch),
                ),
                dim=1,
            )
        weights = torch.softmax(self.pool_logits, dim=0)
        return self.output((pooled * weights.view(1, 3, 1)).sum(dim=1))


class TaskSpecificNodeHead(nn.Module):
    def __init__(self, input_dim: int, output_dim: int) -> None:
        super().__init__()
        self.node_proj = nn.Sequential(
            Linear(input_dim, input_dim),
            nn.LayerNorm(input_dim),
            nn.ReLU(),
        )
        self.output = Linear(input_dim, output_dim)

    def forward(self, node_repr: Tensor) -> Tensor:
        return self.output(self.node_proj(node_repr))


def make_prediction_mlp(input_dim: int, output_dim: int, *, hidden_dim: Optional[int] = None) -> nn.Sequential:
    hidden = int(hidden_dim or input_dim)
    return nn.Sequential(
        Linear(input_dim, hidden),
        nn.LayerNorm(hidden),
        nn.ReLU(),
        Linear(hidden, output_dim),
    )


class EnergyHead(nn.Module):
    def __init__(self, dim: int) -> None:
        super().__init__()
        self.pool = LearnedPoolingMixer(dim)
        self.predict = make_prediction_mlp(dim, 1)

    def forward(self, atom_repr: Tensor, batch: Tensor) -> Tensor:
        return self.predict(self.pool(atom_repr, batch))


class BondPairHead(nn.Module):
    def __init__(self, dim: int, order_classes: int, *, include_existence: bool = True) -> None:
        super().__init__()
        pair_dim = dim * 2 + 1
        self.trunk = nn.Sequential(
            Linear(pair_dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
        )
        if include_existence:
            self.existence = Linear(dim, 1)
        self.order = Linear(dim, order_classes)

    def forward(self, atom_repr: Tensor, pair_index: Tensor, pos: Tensor | None) -> tuple[Tensor, Tensor]:
        if pair_index.numel() == 0:
            return (
                atom_repr.new_zeros((0, 1 if hasattr(self, "existence") else 0)),
                atom_repr.new_zeros((0, self.order.out_features)),
            )
        src, dst = pair_index[0], pair_index[1]
        distance = atom_repr.new_zeros((src.numel(), 1))
        if pos is not None:
            distance = (pos[src] - pos[dst]).norm(dim=-1, keepdim=True).to(atom_repr.dtype)
        pair_feature = torch.cat(
            (atom_repr[src] + atom_repr[dst], (atom_repr[src] - atom_repr[dst]).abs(), distance),
            dim=-1,
        )
        hidden = self.trunk(pair_feature)
        existence = self.existence(hidden) if hasattr(self, "existence") else hidden.new_zeros((hidden.size(0), 0))
        return existence, self.order(hidden)
