from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn
from torch import Tensor
from torch_geometric.data import Data
from torch_geometric.nn import global_add_pool, global_max_pool, global_mean_pool
from torch_geometric.utils import to_dense_batch

try:
    from ...dataset.descriptor_schema import (
        CHARGE_DESCRIPTOR_SPECS,
        ELEMENT_DESCRIPTOR_SPECS,
        GRAPH_DESCRIPTOR_NAMES,
        GRAPH_GEOMETRY_DESCRIPTOR_INDICES,
        build_charge_output_layout,
        build_element_output_layout,
        build_energy_output_layout,
    )
except ImportError:
    from dataset.descriptor_schema import (
        CHARGE_DESCRIPTOR_SPECS,
        ELEMENT_DESCRIPTOR_SPECS,
        GRAPH_DESCRIPTOR_NAMES,
        GRAPH_GEOMETRY_DESCRIPTOR_INDICES,
        build_charge_output_layout,
        build_element_output_layout,
        build_energy_output_layout,
    )

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


class LearnedPoolingMixer(nn.Module):
    """Learn a task-family-specific mixture over sum/mean/max graph pooling."""

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.sum_proj = Linear(dim, dim)
        self.mean_proj = Linear(dim, dim)
        self.max_proj = Linear(dim, dim)
        self.pool_logits = nn.Parameter(torch.zeros(3))

    def forward(self, atom_embeddings: Tensor, batch: Tensor) -> Tensor:
        pooled = torch.stack(
            (
                self.sum_proj(global_add_pool(atom_embeddings, batch)),
                self.mean_proj(global_mean_pool(atom_embeddings, batch)),
                self.max_proj(global_max_pool(atom_embeddings, batch)),
            ),
            dim=1,
        )
        weights = torch.softmax(self.pool_logits, dim=0)
        return (pooled * weights.view(1, 3, 1)).sum(dim=1)

    def weight_dict(self) -> Dict[str, float]:
        weights = torch.softmax(self.pool_logits.detach().to(dtype=torch.float32), dim=0).cpu()
        return {
            "sum": float(weights[0].item()),
            "mean": float(weights[1].item()),
            "max": float(weights[2].item()),
        }


def _make_head_mlp(input_dim: int, output_dim: int) -> nn.Sequential:
    return nn.Sequential(
        Linear(input_dim, input_dim),
        nn.LayerNorm(input_dim),
        nn.ReLU(),
        Linear(input_dim, output_dim),
    )


class MultiTaskMoE(nn.Module):
    """Multi-task MoE model with descriptor-augmented task heads."""

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
        self.pad_elem_index = self.n_atom_types - 1

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

        self.energy_output_layout, self.energy_output_dim = build_energy_output_layout()
        self.charge_output_layout, self.charge_output_dim = build_charge_output_layout()
        self.element_output_layout, self.element_output_dim = build_element_output_layout(self.n_atom_types)

        self.graph_descriptor_names = GRAPH_DESCRIPTOR_NAMES
        self.charge_descriptor_specs = CHARGE_DESCRIPTOR_SPECS
        self.element_descriptor_specs = ELEMENT_DESCRIPTOR_SPECS

        self.coord_decoder = CoordinateDecoder(atom_embedding_dim=dim, hidden_dim=dim, output_dim=3)
        self.charge_head = Linear(dim, self.charge_output_dim)
        self.elem_head = Linear(dim, self.element_output_dim)
        self.register_buffer(
            "graph_geometry_descriptor_indices",
            torch.tensor(GRAPH_GEOMETRY_DESCRIPTOR_INDICES, dtype=torch.long),
            persistent=False,
        )
        non_geometry_indices = [
            idx for idx, _ in enumerate(self.graph_descriptor_names)
            if idx not in set(GRAPH_GEOMETRY_DESCRIPTOR_INDICES)
        ]
        self.register_buffer(
            "graph_non_geometry_descriptor_indices",
            torch.tensor(non_geometry_indices, dtype=torch.long),
            persistent=False,
        )
        self.energy_graph_pool = LearnedPoolingMixer(dim)
        self.geometry_graph_pool = LearnedPoolingMixer(dim)
        self.energy_graph_head = _make_head_mlp(dim, 1 + int(self.graph_non_geometry_descriptor_indices.numel()))
        self.geometry_graph_head = _make_head_mlp(dim, int(self.graph_geometry_descriptor_indices.numel()))

    @staticmethod
    def _slice_outputs(tensor: Tensor, layout: Dict[str, slice]) -> Dict[str, Tensor]:
        return {name: tensor[..., tensor_slice] for name, tensor_slice in layout.items()}

    def _decode_energy_outputs(
        self,
        latent_e: Tensor,
        latent_g: Tensor,
        batch: Tensor,
    ) -> Dict[str, Tensor]:
        energy_graph_repr = self.energy_graph_pool(latent_e, batch)
        energy_outputs = self.energy_graph_head(energy_graph_repr)
        energy_pred = energy_outputs[:, :1]
        num_graphs = int(energy_pred.size(0))
        graph_desc = energy_pred.new_zeros((num_graphs, len(self.graph_descriptor_names)))

        if self.graph_non_geometry_descriptor_indices.numel() > 0:
            graph_desc.index_copy_(1, self.graph_non_geometry_descriptor_indices, energy_outputs[:, 1:])

        if self.graph_geometry_descriptor_indices.numel() > 0:
            geom_graph_repr = self.geometry_graph_pool(latent_g, batch)
            geom_pred = self.geometry_graph_head(geom_graph_repr)
            graph_desc.index_copy_(1, self.graph_geometry_descriptor_indices, geom_pred)

        return {
            "energy": energy_pred,
            "graph_desc": graph_desc,
        }

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

    def _decode_outputs(
        self,
        latent_e: Tensor,
        latent_q: Tensor,
        latent_z: Tensor,
        latent_g: Tensor,
        batch: Tensor,
        *,
        charge_mask_source: Optional[Tensor],
    ) -> Dict[str, Tensor | Dict[str, Tensor]]:
        coords_atom = self.coord_decoder(latent_g)
        coords_pred, node_mask = to_dense_batch(coords_atom, batch, fill_value=0.0)

        charge_atom = self.charge_head(latent_q)
        charge_dense, _ = to_dense_batch(charge_atom, batch, fill_value=0.0)
        charge_outputs = self._slice_outputs(charge_dense, self.charge_output_layout)

        elem_atom = self.elem_head(latent_z)
        elem_dense, _ = to_dense_batch(elem_atom, batch, fill_value=0.0)
        elem_outputs = self._slice_outputs(elem_dense, self.element_output_layout)

        energy_outputs = self._decode_energy_outputs(latent_e, latent_g, batch)

        if (
            charge_mask_source is not None
            and isinstance(charge_mask_source, Tensor)
            and charge_mask_source.dim() == 1
            and charge_mask_source.numel() == latent_e.size(0)
        ):
            cm_dense, _ = to_dense_batch(
                charge_mask_source.to(torch.float32).unsqueeze(-1),
                batch,
                fill_value=0.0,
            )
            charge_mask = (cm_dense > 0.5) & node_mask.unsqueeze(-1)
        elif (
            charge_mask_source is not None
            and isinstance(charge_mask_source, Tensor)
            and charge_mask_source.dim() == 2
            and charge_mask_source.size(0) == latent_e.size(0)
        ):
            cm_dense, _ = to_dense_batch(charge_mask_source.to(torch.float32), batch, fill_value=0.0)
            charge_mask = (cm_dense > 0.5) & node_mask.unsqueeze(-1)
        else:
            charge_mask = node_mask.unsqueeze(-1)

        return {
            "coords": coords_pred,
            "charge": charge_outputs,
            "element": elem_outputs,
            "energy": energy_outputs,
            "charge_mask": charge_mask,
            "node_mask": node_mask.unsqueeze(-1),
        }

    def forward(self, data: Data) -> Dict[str, Tensor | Dict[str, Tensor]]:
        batch = ensure_batch_attr(data)
        if getattr(data, "pos", None) is None:
            raise ValueError("MultiTaskMoE requires data.pos")
        pos = data.pos

        latent0 = self.backbone(data)

        latent_e, bal_e = self._route(
            latent0,
            batch,
            gate_layer=self.gate_energy,
            experts=self.experts_energy,
            top_k=self.top_k_energy,
            pos=pos,
        )
        latent_q, bal_q = self._route(
            latent0,
            batch,
            gate_layer=self.gate_charge,
            experts=self.experts_charge,
            top_k=self.top_k_charge,
            pos=pos,
        )
        latent_z, bal_z = self._route(
            latent0,
            batch,
            gate_layer=self.gate_elem,
            experts=self.experts_elem,
            top_k=self.top_k_elem,
            pos=pos,
        )
        latent_g, bal_g = self._route(
            latent0,
            batch,
            gate_layer=self.gate_geom,
            experts=self.experts_geom,
            top_k=self.top_k_geom,
            pos=pos,
        )

        outputs = self._decode_outputs(
            latent_e,
            latent_q,
            latent_z,
            latent_g,
            batch,
            charge_mask_source=getattr(data, "charge_mask", None),
        )
        outputs["balance_loss"] = bal_e + bal_q + bal_z + bal_g
        return outputs

    def get_pooling_weight_metrics(self) -> Dict[str, float]:
        metrics: Dict[str, float] = {}
        pool_modules = {
            "energy_graph": getattr(self, "energy_graph_pool", None),
            "geometry_graph": getattr(self, "geometry_graph_pool", None),
        }
        for pool_name, pool_module in pool_modules.items():
            if isinstance(pool_module, LearnedPoolingMixer):
                for weight_name, weight_value in pool_module.weight_dict().items():
                    metrics[f"pooling/{pool_name}/{weight_name}"] = float(weight_value)
        return metrics

    @torch.no_grad()
    def forward_from_latent(
        self,
        latent: Tensor,
        data_static: Data,
        *,
        node_mask: Optional[Tensor] = None,
        return_dense: bool = True,
        pos: Optional[Tensor] = None,
    ) -> Dict[str, Tensor | Dict[str, Tensor]]:
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

        latent_e, bal_e = self._route(
            latent0,
            batch,
            gate_layer=self.gate_energy,
            experts=self.experts_energy,
            top_k=self.top_k_energy,
            pos=pos_flat,
        )
        latent_q, bal_q = self._route(
            latent0,
            batch,
            gate_layer=self.gate_charge,
            experts=self.experts_charge,
            top_k=self.top_k_charge,
            pos=pos_flat,
        )
        latent_z, bal_z = self._route(
            latent0,
            batch,
            gate_layer=self.gate_elem,
            experts=self.experts_elem,
            top_k=self.top_k_elem,
            pos=pos_flat,
        )
        latent_g, bal_g = self._route(
            latent0,
            batch,
            gate_layer=self.gate_geom,
            experts=self.experts_geom,
            top_k=self.top_k_geom,
            pos=pos_flat,
        )

        if not return_dense:
            return {
                "coords": self.coord_decoder(latent_g),
                "charge": self._slice_outputs(self.charge_head(latent_q), self.charge_output_layout),
                "element": self._slice_outputs(self.elem_head(latent_z), self.element_output_layout),
                "energy": self._decode_energy_outputs(latent_e, latent_g, batch),
                "charge_mask": torch.ones(latent0.size(0), 1, device=latent0.device, dtype=torch.bool),
                "node_mask": torch.ones(latent0.size(0), 1, device=latent0.device, dtype=torch.bool),
                "balance_loss": bal_e + bal_q + bal_z + bal_g,
            }

        outputs = self._decode_outputs(
            latent_e,
            latent_q,
            latent_z,
            latent_g,
            batch,
            charge_mask_source=getattr(data_static, "charge_mask", None),
        )
        outputs["balance_loss"] = bal_e + bal_q + bal_z + bal_g
        return outputs
