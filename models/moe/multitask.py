from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
from torch import Tensor
from torch_geometric.data import Data
from torch_geometric.nn import global_mean_pool
from torch_geometric.utils import to_dense_batch

from .backbone import RealCoordTransformerBackbone
from .common import Linear, ensure_batch_attr
from .expert_blocks import ETExpert, resolve_task_layers


class CoordinateDecoder(nn.Module):
    """Task head that predicts Cartesian coordinates from latent node embeddings."""

    def __init__(self, atom_embedding_dim: int, hidden_dim: int, output_dim: int = 3) -> None:
        super().__init__()
        self.shared_decoder = nn.Sequential(
            Linear(atom_embedding_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
        )
        self.coord_head = Linear(hidden_dim, output_dim)

    def forward(self, atom_embeddings: Tensor) -> Tensor:
        hidden = self.shared_decoder(atom_embeddings)
        return self.coord_head(hidden)


class MultiTaskMoE(nn.Module):
    """Multi-task MoE model.

    Returns:
        coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, balance_loss
    """

    def __init__(
        self,
        backbone_config: Dict,
        n_atom_types: int,
        n_experts_geom: int = 4,
        n_experts_energy: int = 2,
        n_experts_charge: int = 2,
        n_experts_elem: int = 1,
        top_k_geom: int = 1,
        top_k_energy: int = 1,
        top_k_charge: int = 1,
        top_k_elem: int = 1,
        expert_layers: int = 2,
        expert_real_layers: Optional[int] = None,
        expert_int_layers: int = 0,
        expert_heads: int = 4,
        expert_ff_mult: int = 2,
        balance_weight: float = 1e-2,
    ) -> None:
        super().__init__()
        self.balance_weight = float(balance_weight)
        self.n_atom_types = int(n_atom_types)

        dim = int(backbone_config.get("atom_embedding_dim", backbone_config.get("hidden_channels", 512)))
        bb_layers = int(backbone_config.get("bb_layers", backbone_config.get("num_layers", 6)))
        bb_heads = int(backbone_config.get("bb_heads", 8))
        bb_ff_mult = int(backbone_config.get("bb_ff_mult", 4))
        bb_dropout = float(backbone_config.get("bb_dropout", 0.0))
        bb_use_dist_bias = bool(backbone_config.get("bb_use_dist_bias", True))
        bb_use_radius_mask = bool(backbone_config.get("bb_use_radius_mask", False))
        bb_radius = float(backbone_config.get("bb_radius", backbone_config.get("cutoff", 8.0)))

        self.backbone = RealCoordTransformerBackbone(
            n_atom_types=self.n_atom_types,
            dim=dim,
            layers=bb_layers,
            heads=bb_heads,
            ff_mult=bb_ff_mult,
            dropout=bb_dropout,
            use_dist_bias=bb_use_dist_bias,
            use_radius_mask=bb_use_radius_mask,
            radius=bb_radius,
        )
        self.latent_dim = dim

        real_layers = int(expert_layers if expert_real_layers is None else expert_real_layers)
        int_layers = int(expert_int_layers)

        overrides_energy = backbone_config.get("expert_layers_energy", None)
        overrides_charge = backbone_config.get("expert_layers_charge", None)
        overrides_elem = backbone_config.get("expert_layers_elem", None)
        overrides_geom = backbone_config.get("expert_layers_geom", None)

        self.experts_energy = nn.ModuleList(
            [
                ETExpert(
                    dim,
                    resolve_task_layers(real_layers, int_layers, overrides_energy, "real"),
                    resolve_task_layers(real_layers, int_layers, overrides_energy, "int"),
                    nheads=expert_heads,
                    ff_mult=expert_ff_mult,
                    radius=bb_radius,
                )
                for _ in range(n_experts_energy)
            ]
        )
        self.experts_charge = nn.ModuleList(
            [
                ETExpert(
                    dim,
                    resolve_task_layers(real_layers, int_layers, overrides_charge, "real"),
                    resolve_task_layers(real_layers, int_layers, overrides_charge, "int"),
                    nheads=expert_heads,
                    ff_mult=expert_ff_mult,
                    radius=bb_radius,
                )
                for _ in range(n_experts_charge)
            ]
        )
        self.experts_elem = nn.ModuleList(
            [
                ETExpert(
                    dim,
                    resolve_task_layers(real_layers, int_layers, overrides_elem, "real"),
                    resolve_task_layers(real_layers, int_layers, overrides_elem, "int"),
                    nheads=expert_heads,
                    ff_mult=expert_ff_mult,
                    radius=bb_radius,
                )
                for _ in range(n_experts_elem)
            ]
        )
        self.experts_geom = nn.ModuleList(
            [
                ETExpert(
                    dim,
                    resolve_task_layers(real_layers, int_layers, overrides_geom, "real"),
                    resolve_task_layers(real_layers, int_layers, overrides_geom, "int"),
                    nheads=expert_heads,
                    ff_mult=expert_ff_mult,
                    radius=bb_radius,
                )
                for _ in range(n_experts_geom)
            ]
        )

        self.gate_energy = Linear(dim, n_experts_energy)
        self.gate_charge = Linear(dim, n_experts_charge)
        self.gate_elem = Linear(dim, n_experts_elem)
        self.gate_geom = Linear(dim, n_experts_geom)

        self.top_k_energy = int(top_k_energy)
        self.top_k_charge = int(top_k_charge)
        self.top_k_elem = int(top_k_elem)
        self.top_k_geom = int(top_k_geom)

        self.coord_decoder = CoordinateDecoder(atom_embedding_dim=dim, hidden_dim=dim, output_dim=3)
        self.charge_head = Linear(dim, 1)
        self.elem_head = Linear(dim, n_atom_types)

        self.energy_pool = global_mean_pool
        self.energy_head = nn.Sequential(
            Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            Linear(dim, 1),
        )

    def _route(
        self,
        latent_base: Tensor,
        batch: Tensor,
        *,
        gate_layer: nn.Module,
        experts: nn.ModuleList,
        top_k: int,
        pos: Optional[Tensor],
    ) -> Tuple[Tensor, Tensor]:
        graph_repr = global_mean_pool(latent_base, batch)
        gate_logits = gate_layer(graph_repr)
        gate_probs = torch.softmax(gate_logits, dim=-1)

        top_k = min(int(top_k), gate_probs.size(1))
        topk_vals, topk_idx = torch.topk(gate_probs, k=top_k, dim=-1)
        sparse = torch.zeros_like(gate_probs).scatter_(1, topk_idx, topk_vals)
        gate_probs = sparse / (sparse.sum(dim=-1, keepdim=True) + 1e-9)

        gate_node = gate_probs[batch]
        out = torch.zeros_like(latent_base)

        for expert_idx, expert in enumerate(experts):
            if gate_probs[:, expert_idx].max() < 1e-6:
                continue
            emb = expert(latent_base, batch=batch, pos=pos)
            out = out + gate_node[:, expert_idx : expert_idx + 1] * emb

        mean_prob = gate_probs.mean(dim=0)
        coverage = (gate_probs > 0).float().mean(dim=0)
        bal_loss = (mean_prob * coverage).sum() * float(self.balance_weight)
        return out, bal_loss

    def forward(self, data: Data) -> Tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        batch = ensure_batch_attr(data)
        if getattr(data, "pos", None) is None:
            raise ValueError("MultiTaskMoE requires data.pos")
        pos = data.pos

        latent0 = self.backbone(data)

        latent_e, bal_e = self._route(latent0, batch, gate_layer=self.gate_energy, experts=self.experts_energy, top_k=self.top_k_energy, pos=pos)
        latent_q, bal_q = self._route(latent0, batch, gate_layer=self.gate_charge, experts=self.experts_charge, top_k=self.top_k_charge, pos=pos)
        latent_z, bal_z = self._route(latent0, batch, gate_layer=self.gate_elem, experts=self.experts_elem, top_k=self.top_k_elem, pos=pos)
        latent_g, bal_g = self._route(latent0, batch, gate_layer=self.gate_geom, experts=self.experts_geom, top_k=self.top_k_geom, pos=pos)

        balance_loss = bal_e + bal_q + bal_z + bal_g

        coords_atom = self.coord_decoder(latent_g)
        coords_pred, mask = to_dense_batch(coords_atom, batch, fill_value=0.0)

        charge_atom = self.charge_head(latent_q)
        charge_pred, _ = to_dense_batch(charge_atom, batch, fill_value=0.0)

        elem_atom = self.elem_head(latent_z)
        elem_pred, _ = to_dense_batch(elem_atom, batch, fill_value=0.0)

        energy_node = self.energy_head(latent_e)
        energy_pred = self.energy_pool(energy_node, batch).unsqueeze(-1)

        cm = getattr(data, "charge_mask", None)
        if cm is not None and isinstance(cm, Tensor) and cm.dim() == 1 and cm.numel() == latent0.size(0):
            cm_dense, _ = to_dense_batch(cm.to(torch.float32).unsqueeze(-1), batch, fill_value=0.0)
            charge_mask = (cm_dense > 0.5) & mask.unsqueeze(-1)
        else:
            charge_mask = mask.unsqueeze(-1)

        return coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, balance_loss

    @torch.no_grad()
    def forward_from_latent(
        self,
        latent: Tensor,
        data_static: Data,
        *,
        node_mask: Optional[Tensor] = None,
        return_dense: bool = True,
        pos: Optional[Tensor] = None,
    ) -> Tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        batch = ensure_batch_attr(data_static)

        if latent.dim() == 3:
            if node_mask is None:
                raise ValueError("node_mask is required when latent is dense (B, N, D).")
            nm = node_mask.squeeze(-1) if node_mask.dim() == 3 else node_mask
            latent0 = latent[nm]
        else:
            latent0 = latent

        if pos is None and getattr(data_static, "pos", None) is not None:
            pos = data_static.pos

        if pos is not None and pos.dim() == 3:
            if node_mask is None:
                raise ValueError("node_mask is required when pos is dense (B, N, 3).")
            nm = node_mask.squeeze(-1) if node_mask.dim() == 3 else node_mask
            pos_flat = pos[nm]
        else:
            pos_flat = pos

        if pos_flat is None:
            expert_groups = {
                "energy": self.experts_energy,
                "charge": self.experts_charge,
                "elem": self.experts_elem,
                "geom": self.experts_geom,
            }
            for task_name, task_experts in expert_groups.items():
                if any(len(expert.real_layers) > 0 for expert in task_experts):
                    raise ValueError(
                        f"forward_from_latent(pos=None) requires real layers disabled for {task_name}."
                    )

        latent_e, bal_e = self._route(latent0, batch, gate_layer=self.gate_energy, experts=self.experts_energy, top_k=self.top_k_energy, pos=pos_flat)
        latent_q, bal_q = self._route(latent0, batch, gate_layer=self.gate_charge, experts=self.experts_charge, top_k=self.top_k_charge, pos=pos_flat)
        latent_z, bal_z = self._route(latent0, batch, gate_layer=self.gate_elem, experts=self.experts_elem, top_k=self.top_k_elem, pos=pos_flat)
        latent_g, bal_g = self._route(latent0, batch, gate_layer=self.gate_geom, experts=self.experts_geom, top_k=self.top_k_geom, pos=pos_flat)

        balance_loss = bal_e + bal_q + bal_z + bal_g

        coords_atom = self.coord_decoder(latent_g)
        charge_atom = self.charge_head(latent_q)
        elem_atom = self.elem_head(latent_z)
        energy_node = self.energy_head(latent_e)

        if not return_dense:
            ones = torch.ones(latent0.size(0), 1, device=latent0.device, dtype=torch.bool)
            return coords_atom, charge_atom, elem_atom, energy_node, ones, balance_loss

        coords_pred, mask = to_dense_batch(coords_atom, batch, fill_value=0.0)
        charge_pred, _ = to_dense_batch(charge_atom, batch, fill_value=0.0)
        elem_pred, _ = to_dense_batch(elem_atom, batch, fill_value=0.0)
        energy_pred = global_mean_pool(energy_node, batch).unsqueeze(-1)
        charge_mask = mask.unsqueeze(-1)
        return coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, balance_loss
