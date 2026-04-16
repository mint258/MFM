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
        BOND_INDEX_FIELD,
        BOND_NEGATIVE_COUNT_FIELD,
        BOND_NEGATIVE_UPPER_IDS_FIELD,
        BOND_ORDER_FIELD,
        BOND_ORDER_NUM_CLASSES,
        BOND_STATUS_FIELD,
        CHARGE_DESCRIPTOR_SPECS,
        ELEMENT_DESCRIPTOR_SPECS,
        GRAPH_DESCRIPTOR_NAMES,
        SAMPLE_TYPE_ID_FIELD,
        build_charge_output_layout,
        build_element_output_layout,
        build_energy_output_layout,
        graph_descriptor_indices,
        normalize_graph_descriptor_names,
    )
except ImportError:
    from dataset.descriptor_schema import (
        BOND_INDEX_FIELD,
        BOND_NEGATIVE_COUNT_FIELD,
        BOND_NEGATIVE_UPPER_IDS_FIELD,
        BOND_ORDER_FIELD,
        BOND_ORDER_NUM_CLASSES,
        BOND_STATUS_FIELD,
        CHARGE_DESCRIPTOR_SPECS,
        ELEMENT_DESCRIPTOR_SPECS,
        GRAPH_DESCRIPTOR_NAMES,
        SAMPLE_TYPE_ID_FIELD,
        build_charge_output_layout,
        build_element_output_layout,
        build_energy_output_layout,
        graph_descriptor_indices,
        normalize_graph_descriptor_names,
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


class FixedSummaryPooling(nn.Module):
    """Deterministic graph summary pooling: mean + max + std + logN."""

    def __init__(self, dim: int) -> None:
        super().__init__()
        self.output_dim = int(dim) * 3 + 1

    def forward(self, atom_embeddings: Tensor, batch: Tensor) -> Tensor:
        if batch.numel() == 0:
            return atom_embeddings.new_zeros((1, self.output_dim))

        mean_pool = global_mean_pool(atom_embeddings, batch)
        max_pool = global_max_pool(atom_embeddings, batch)
        second_moment = global_mean_pool(atom_embeddings * atom_embeddings, batch)
        var_pool = torch.clamp(second_moment - mean_pool * mean_pool, min=0.0)
        std_pool = torch.sqrt(var_pool + 1e-9)
        graph_counts = torch.bincount(batch, minlength=mean_pool.size(0)).to(dtype=atom_embeddings.dtype, device=atom_embeddings.device)
        log_counts = torch.log(graph_counts.clamp_min(1.0)).unsqueeze(-1)
        return torch.cat((mean_pool, max_pool, std_pool, log_counts), dim=-1)


class TaskSpecificGraphHead(nn.Module):
    """Per-task graph readout with its own projection, pooling mixture, and output."""

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
        pooled = torch.stack(
            (
                global_add_pool(hidden, batch),
                global_mean_pool(hidden, batch),
                global_max_pool(hidden, batch),
            ),
            dim=1,
        )
        weights = torch.softmax(self.pool_logits, dim=0)
        graph_repr = (pooled * weights.view(1, 3, 1)).sum(dim=1)
        return self.output(graph_repr)

    def weight_dict(self) -> Dict[str, float]:
        weights = torch.softmax(self.pool_logits.detach().to(dtype=torch.float32), dim=0).cpu()
        return {
            "sum": float(weights[0].item()),
            "mean": float(weights[1].item()),
            "max": float(weights[2].item()),
        }


class TaskSpecificNodeHead(nn.Module):
    """Per-task node readout with an independent projection and output layer."""

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


def _make_head_mlp(input_dim: int, output_dim: int, *, hidden_dim: Optional[int] = None) -> nn.Sequential:
    hidden = int(hidden_dim or input_dim)
    return nn.Sequential(
        Linear(input_dim, hidden),
        nn.LayerNorm(hidden),
        nn.ReLU(),
        Linear(hidden, output_dim),
    )


class MultiTaskMoE(nn.Module):
    """Multi-task MoE model with staged fused descriptor heads and bond routing."""

    def __init__(
        self,
        backbone_config: Dict,
        n_atom_types: int,
        n_experts_geom: int = 4,
        n_experts_energy: int = 2,
        n_experts_charge: int = 2,
        n_experts_elem: int = 1,
        n_experts_bond: int = 1,
        top_k_geom: int = 1,
        top_k_energy: int = 1,
        top_k_charge: int = 1,
        top_k_elem: int = 1,
        top_k_bond: int = 1,
        expert_layers: int = 2,
        expert_real_layers: Optional[int] = None,
        expert_int_layers: int = 0,
        expert_heads: int = 4,
        expert_ff_mult: int = 2,
        balance_weight: float = 1e-2,
        bond_negative_ratio: float = 1.0,
        fused_dim: Optional[int] = None,
        graph_descriptor_names: Optional[tuple[str, ...] | list[str]] = None,
        direct_linear_noexpert: bool = False,
    ) -> None:
        super().__init__()
        self.balance_weight = float(balance_weight)
        self.n_atom_types = int(n_atom_types)
        self.pad_elem_index = self.n_atom_types - 1
        self.bond_negative_ratio = max(0.0, float(bond_negative_ratio))

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
        self.direct_linear_noexpert = bool(direct_linear_noexpert)
        if self.direct_linear_noexpert and (real_layers != 0 or int_layers != 0):
            raise ValueError(
                "direct_linear_noexpert requires expert_real_layers=0 and expert_int_layers=0."
            )

        overrides_energy = backbone_config.get("expert_layers_energy", None)
        overrides_charge = backbone_config.get("expert_layers_charge", None)
        overrides_elem = backbone_config.get("expert_layers_elem", None)
        overrides_geom = backbone_config.get("expert_layers_geom", None)
        overrides_bond = backbone_config.get("expert_layers_bond", None)

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
        self.experts_bond = nn.ModuleList(
            [
                ETExpert(
                    dim,
                    resolve_task_layers(real_layers, int_layers, overrides_bond, "real"),
                    resolve_task_layers(real_layers, int_layers, overrides_bond, "int"),
                    nheads=expert_heads,
                    ff_mult=expert_ff_mult,
                    radius=bb_radius,
                )
                for _ in range(n_experts_bond)
            ]
        )

        self.gate_energy = Linear(dim, n_experts_energy)
        self.gate_charge = Linear(dim, n_experts_charge)
        self.gate_elem = Linear(dim, n_experts_elem)
        self.gate_geom = Linear(dim, n_experts_geom)
        self.gate_bond = Linear(dim, n_experts_bond)

        self.top_k_energy = int(top_k_energy)
        self.top_k_charge = int(top_k_charge)
        self.top_k_elem = int(top_k_elem)
        self.top_k_geom = int(top_k_geom)
        self.top_k_bond = int(top_k_bond)

        self.graph_descriptor_names = normalize_graph_descriptor_names(graph_descriptor_names)
        self.graph_descriptor_target_indices = graph_descriptor_indices(self.graph_descriptor_names)
        self.energy_output_layout, self.energy_output_dim = build_energy_output_layout(self.graph_descriptor_names)
        self.charge_output_layout, self.charge_output_dim = build_charge_output_layout()
        self.element_output_layout, self.element_output_dim = build_element_output_layout(self.n_atom_types)

        self.charge_descriptor_specs = CHARGE_DESCRIPTOR_SPECS
        self.element_descriptor_specs = ELEMENT_DESCRIPTOR_SPECS

        self.coord_decoder = CoordinateDecoder(atom_embedding_dim=dim, hidden_dim=dim, output_dim=3)
        self.direct_coord_head = Linear(dim, 3)
        self.charge_prime_head = Linear(dim, 1)
        self.elem_prime_head = Linear(dim, self.n_atom_types)
        self.energy_graph_pool = LearnedPoolingMixer(dim)
        self.energy_head = _make_head_mlp(dim, 1)
        self.direct_energy_graph_pool = FixedSummaryPooling(dim)
        self.direct_energy_head = Linear(self.direct_energy_graph_pool.output_dim, 1)

        self.fused_input_dim = dim * 5
        self.fused_dim = int(fused_dim or dim)
        fusion_hidden = max(self.fused_dim, dim)
        self.fusion = nn.Sequential(
            nn.LayerNorm(self.fused_input_dim),
            Linear(self.fused_input_dim, fusion_hidden),
            nn.ReLU(),
            Linear(fusion_hidden, self.fused_dim),
            nn.LayerNorm(self.fused_dim),
        )
        self.graph_descriptor_heads = nn.ModuleDict(
            {
                name: TaskSpecificGraphHead(self.fused_dim, 1)
                for name in self.graph_descriptor_names
            }
        )
        self.charge_descriptor_heads = nn.ModuleDict(
            {
                spec.name: TaskSpecificNodeHead(self.fused_dim, spec.num_outputs)
                for spec in self.charge_descriptor_specs
            }
        )
        self.element_descriptor_heads = nn.ModuleDict(
            {
                spec.name: TaskSpecificNodeHead(self.fused_dim, spec.num_outputs)
                for spec in self.element_descriptor_specs
            }
        )

        pair_input_dim = dim * 2 + 1
        self.bond_pair_trunk = nn.Sequential(
            Linear(pair_input_dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
            Linear(dim, dim),
            nn.LayerNorm(dim),
            nn.ReLU(),
        )
        self.bond_exist_head = Linear(dim, 1)
        self.bond_order_head = Linear(dim, BOND_ORDER_NUM_CLASSES)
        self.direct_bond_exist_head = Linear(pair_input_dim, 1)
        self.direct_bond_order_head = Linear(pair_input_dim, BOND_ORDER_NUM_CLASSES)
        self._runtime_task_gates = {
            "bond_enabled": True,
            "energy_desc_enabled": True,
            "charge_desc_enabled": True,
            "element_desc_enabled": True,
        }
        self._runtime_legacy_pretraining = False

    @staticmethod
    def _slice_outputs(tensor: Tensor, layout: Dict[str, slice]) -> Dict[str, Tensor]:
        return {name: tensor[..., tensor_slice] for name, tensor_slice in layout.items()}

    @staticmethod
    def _graph_ptr(batch: Tensor, num_graphs: int) -> Tensor:
        if batch.numel() == 0:
            return torch.zeros(num_graphs + 1, dtype=torch.long, device=batch.device)
        counts = torch.bincount(batch, minlength=num_graphs)
        return torch.cat(
            (
                torch.zeros(1, dtype=torch.long, device=batch.device),
                counts.cumsum(dim=0),
            ),
            dim=0,
        )

    @staticmethod
    def _graph_string_attr(data: Data, attr_name: str, num_graphs: int, *, default: str = "") -> list[str]:
        value = getattr(data, attr_name, None)
        if isinstance(value, str):
            return [value] * max(1, num_graphs)
        if isinstance(value, (list, tuple)):
            result = [str(item) if isinstance(item, str) else default for item in value]
            if len(result) >= num_graphs:
                return result[:num_graphs]
            return result + [default] * (num_graphs - len(result))
        return [default] * max(1, num_graphs)

    @staticmethod
    def _graph_long_attr(data: Data, attr_name: str, num_graphs: int, *, default: int = 0) -> list[int]:
        value = getattr(data, attr_name, None)
        if isinstance(value, Tensor):
            flat = value.view(-1).detach().cpu().tolist()
            result = [int(item) for item in flat[:num_graphs]]
            if len(result) >= num_graphs:
                return result[:num_graphs]
            return result + [int(default)] * (num_graphs - len(result))
        if isinstance(value, (list, tuple)):
            result = [int(item) for item in value[:num_graphs]]
            if len(result) >= num_graphs:
                return result[:num_graphs]
            return result + [int(default)] * (num_graphs - len(result))
        return [int(default)] * max(1, num_graphs)

    @staticmethod
    def _decode_upper_pair_ids(upper_ids: Tensor, *, num_nodes: int, start: int) -> Tensor:
        if upper_ids.numel() == 0 or num_nodes < 2:
            return upper_ids.new_zeros((0, 2), dtype=torch.long)

        row_lengths = torch.arange(num_nodes - 1, 0, -1, device=upper_ids.device, dtype=torch.long)
        row_offsets = torch.cat(
            (
                torch.zeros((1,), device=upper_ids.device, dtype=torch.long),
                row_lengths.cumsum(dim=0)[:-1],
            ),
            dim=0,
        )
        local_ids = upper_ids.to(device=upper_ids.device, dtype=torch.long).view(-1)
        row_index = torch.bucketize(local_ids, row_offsets, right=True) - 1
        col_index = row_index + 1 + (local_ids - row_offsets[row_index])
        return torch.stack((row_index + int(start), col_index + int(start)), dim=1)

    @staticmethod
    def _encode_upper_pair_ids(pair_index: Tensor, *, num_nodes: int, start: int) -> Tensor:
        if pair_index.numel() == 0 or num_nodes < 2:
            return pair_index.new_zeros((0,), dtype=torch.long)

        pair_index = pair_index.to(dtype=torch.long).view(2, -1)
        local_src = pair_index[0] - int(start)
        local_dst = pair_index[1] - int(start)
        row_lengths = torch.arange(num_nodes - 1, 0, -1, device=pair_index.device, dtype=torch.long)
        row_offsets = torch.cat(
            (
                torch.zeros((1,), device=pair_index.device, dtype=torch.long),
                row_lengths.cumsum(dim=0)[:-1],
            ),
            dim=0,
        )
        return row_offsets[local_src] + (local_dst - local_src - 1)

    def set_runtime_task_gates(
        self,
        *,
        bond_enabled: Optional[bool] = None,
        energy_desc_enabled: Optional[bool] = None,
        charge_desc_enabled: Optional[bool] = None,
        element_desc_enabled: Optional[bool] = None,
        legacy_pretraining_strategy: Optional[bool] = None,
    ) -> None:
        updates = {
            "bond_enabled": bond_enabled,
            "energy_desc_enabled": energy_desc_enabled,
            "charge_desc_enabled": charge_desc_enabled,
            "element_desc_enabled": element_desc_enabled,
        }
        for key, value in updates.items():
            if value is not None:
                self._runtime_task_gates[key] = bool(value)
        if legacy_pretraining_strategy is not None:
            self._runtime_legacy_pretraining = bool(legacy_pretraining_strategy)

    def clear_runtime_task_gates(self) -> None:
        for key in self._runtime_task_gates:
            self._runtime_task_gates[key] = True
        self._runtime_legacy_pretraining = False

    def _task_gate(self, name: str, *, default: bool = True) -> bool:
        return bool(self._runtime_task_gates.get(name, default))

    def _fuse_latents(
        self,
        latent_e: Tensor,
        latent_q: Tensor,
        latent_z: Tensor,
        latent_g: Tensor,
        latent_b: Tensor,
    ) -> Tensor:
        fused_raw = torch.cat((latent_e, latent_q, latent_z, latent_g, latent_b), dim=-1)
        return self.fusion(fused_raw)

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

    def _bond_empty_outputs(self, device: torch.device) -> Dict[str, Tensor | int]:
        return {
            "existence": torch.zeros((0, 1), device=device, dtype=torch.float32),
            "order": torch.zeros((0, BOND_ORDER_NUM_CLASSES), device=device, dtype=torch.float32),
            "pair_index": torch.zeros((2, 0), device=device, dtype=torch.long),
            "pair_graph_index": torch.zeros((0,), device=device, dtype=torch.long),
            "existence_target": torch.zeros((0, 1), device=device, dtype=torch.float32),
            "order_target": torch.zeros((0,), device=device, dtype=torch.long),
            "sampled_pair_count": 0,
            "positive_pair_count": 0,
            "valid_graph_count": 0,
        }

    def _sample_bond_pairs(
        self,
        data: Data,
        batch: Tensor,
        *,
        device: torch.device,
        num_graphs: int,
    ) -> Dict[str, Tensor | int]:
        bond_index = getattr(data, BOND_INDEX_FIELD, None)
        if isinstance(bond_index, Tensor):
            bond_index = bond_index.to(device=device, dtype=torch.long).view(2, -1)
        else:
            bond_index = torch.zeros((2, 0), device=device, dtype=torch.long)

        bond_order = getattr(data, BOND_ORDER_FIELD, None)
        if isinstance(bond_order, Tensor):
            bond_order = bond_order.to(device=device, dtype=torch.long).view(-1)
        else:
            bond_order = torch.zeros((0,), device=device, dtype=torch.long)
        if bond_order.numel() < bond_index.size(1):
            padded = torch.zeros((bond_index.size(1),), device=device, dtype=torch.long)
            if bond_order.numel() > 0:
                padded[: bond_order.numel()] = bond_order
            bond_order = padded
        elif bond_order.numel() > bond_index.size(1):
            bond_order = bond_order[: bond_index.size(1)]

        bond_status = self._graph_string_attr(data, BOND_STATUS_FIELD, num_graphs, default="")
        sample_type_ids = self._graph_long_attr(data, SAMPLE_TYPE_ID_FIELD, num_graphs, default=0)
        bond_negative_counts = self._graph_long_attr(data, BOND_NEGATIVE_COUNT_FIELD, num_graphs, default=0)
        bond_negative_upper_ids = getattr(data, BOND_NEGATIVE_UPPER_IDS_FIELD, None)
        if isinstance(bond_negative_upper_ids, Tensor):
            bond_negative_upper_ids = bond_negative_upper_ids.to(device=device, dtype=torch.long).view(-1)
        else:
            bond_negative_upper_ids = None
        ptr = self._graph_ptr(batch, num_graphs)
        edge_graph_index = batch[bond_index[0]] if bond_index.numel() > 0 else torch.zeros((0,), device=device, dtype=torch.long)

        graph_node_counts = ptr[1:] - ptr[:-1]
        sample_type_tensor = torch.tensor(sample_type_ids, device=device, dtype=torch.long)
        status_mask = torch.tensor(
            [str(status).lower() == "ok" for status in bond_status],
            device=device,
            dtype=torch.bool,
        )
        valid_graph_mask = sample_type_tensor.eq(0) & status_mask & graph_node_counts.ge(2)
        valid_graph_count = int(valid_graph_mask.sum().item())

        pair_index_parts: list[Tensor] = []
        pair_graph_parts: list[Tensor] = []
        existence_target_parts: list[Tensor] = []
        order_target_parts: list[Tensor] = []

        positive_pair_index = torch.zeros((2, 0), device=device, dtype=torch.long)
        positive_pair_graph_index = torch.zeros((0,), device=device, dtype=torch.long)
        positive_order_target = torch.zeros((0,), device=device, dtype=torch.long)
        if bond_index.numel() > 0 and edge_graph_index.numel() > 0 and bool(valid_graph_mask.any()):
            positive_edge_mask = valid_graph_mask.index_select(0, edge_graph_index)
            positive_pair_index = bond_index[:, positive_edge_mask]
            positive_pair_graph_index = edge_graph_index[positive_edge_mask]
            positive_order_target = bond_order[positive_edge_mask]
        positive_pair_count = int(positive_pair_index.size(1))
        negative_id_offset = 0

        for graph_idx in range(num_graphs):
            negative_count = max(0, int(bond_negative_counts[graph_idx]))
            if not bool(valid_graph_mask[graph_idx].item()):
                negative_id_offset += negative_count
                continue
            start = int(ptr[graph_idx].item())
            end = int(ptr[graph_idx + 1].item())
            num_nodes = end - start
            graph_positive_mask = positive_pair_graph_index.eq(graph_idx)
            positive_count = int(graph_positive_mask.sum().item())

            if bond_negative_upper_ids is not None and negative_count > 0:
                negative_upper_ids = bond_negative_upper_ids[negative_id_offset : negative_id_offset + negative_count]
            else:
                total_upper = max(0, (num_nodes * (num_nodes - 1)) // 2)
                negative_upper_ids = torch.arange(total_upper, device=device, dtype=torch.long)
                if positive_count > 0:
                    positive_upper_ids = self._encode_upper_pair_ids(
                        positive_pair_index[:, graph_positive_mask],
                        num_nodes=num_nodes,
                        start=start,
                    )
                    if positive_upper_ids.numel() > 0:
                        keep_mask = torch.ones((total_upper,), device=device, dtype=torch.bool)
                        keep_mask[positive_upper_ids.unique()] = False
                        negative_upper_ids = negative_upper_ids[keep_mask]
            negative_id_offset += negative_count

            base_negative = positive_count if positive_count > 0 else 1
            target_negative = int(round(self.bond_negative_ratio * base_negative))
            if base_negative > 0 and self.bond_negative_ratio > 0.0 and target_negative <= 0:
                target_negative = 1
            target_negative = min(target_negative, int(negative_upper_ids.numel()))
            if target_negative > 0:
                if target_negative < int(negative_upper_ids.numel()):
                    perm = torch.randperm(negative_upper_ids.numel(), device=device)[:target_negative]
                    negative_upper_ids = negative_upper_ids[perm]
            else:
                negative_upper_ids = negative_upper_ids[:0]

            negative_tensor = self._decode_upper_pair_ids(negative_upper_ids, num_nodes=num_nodes, start=start)
            if negative_tensor.numel() > 0:
                pair_index_parts.append(negative_tensor.t().contiguous())
                pair_graph_parts.append(torch.full((negative_tensor.size(0),), graph_idx, device=device, dtype=torch.long))
                existence_target_parts.append(torch.zeros((negative_tensor.size(0), 1), device=device, dtype=torch.float32))
                order_target_parts.append(torch.zeros((negative_tensor.size(0),), device=device, dtype=torch.long))

        if positive_pair_index.numel() > 0:
            pair_index_parts.insert(0, positive_pair_index)
            pair_graph_parts.insert(0, positive_pair_graph_index)
            existence_target_parts.insert(0, torch.ones((positive_pair_index.size(1), 1), device=device, dtype=torch.float32))
            order_target_parts.insert(0, positive_order_target)

        if not pair_index_parts:
            empty = self._bond_empty_outputs(device)
            empty["valid_graph_count"] = valid_graph_count
            empty["positive_pair_count"] = positive_pair_count
            return empty

        pair_index = torch.cat(pair_index_parts, dim=1)
        pair_graph_index = torch.cat(pair_graph_parts, dim=0)
        existence_target = torch.cat(existence_target_parts, dim=0)
        order_target = torch.cat(order_target_parts, dim=0)

        return {
            "pair_index": pair_index,
            "pair_graph_index": pair_graph_index,
            "existence_target": existence_target,
            "order_target": order_target,
            "sampled_pair_count": int(existence_target.size(0)),
            "positive_pair_count": int(positive_pair_count),
            "valid_graph_count": int(valid_graph_count),
        }

    def _decode_bond_outputs(
        self,
        latent_b: Tensor,
        data: Data,
        batch: Tensor,
        *,
        pos: Optional[Tensor],
    ) -> Dict[str, Tensor | int]:
        num_graphs = int(batch.max().item() + 1) if batch.numel() > 0 else 1
        sampled = self._sample_bond_pairs(
            data,
            batch,
            device=latent_b.device,
            num_graphs=num_graphs,
        )
        pair_index = sampled["pair_index"]
        if not isinstance(pair_index, Tensor) or pair_index.numel() == 0:
            empty = self._bond_empty_outputs(latent_b.device)
            empty["valid_graph_count"] = int(sampled["valid_graph_count"])
            empty["positive_pair_count"] = int(sampled["positive_pair_count"])
            return empty

        src = pair_index[0]
        dst = pair_index[1]
        pair_distance = torch.zeros((src.size(0), 1), device=latent_b.device, dtype=latent_b.dtype)
        if pos is not None:
            pair_distance = (pos[src] - pos[dst]).norm(dim=-1, keepdim=True).to(dtype=latent_b.dtype)
        pair_feature = torch.cat(
            (
                latent_b[src] + latent_b[dst],
                (latent_b[src] - latent_b[dst]).abs(),
                pair_distance,
            ),
            dim=-1,
        )
        if self.direct_linear_noexpert:
            existence = self.direct_bond_exist_head(pair_feature)
            order = self.direct_bond_order_head(pair_feature)
        else:
            pair_hidden = self.bond_pair_trunk(pair_feature)
            existence = self.bond_exist_head(pair_hidden)
            order = self.bond_order_head(pair_hidden)

        return {
            "existence": existence,
            "order": order,
            "pair_index": pair_index,
            "pair_graph_index": sampled["pair_graph_index"],
            "existence_target": sampled["existence_target"],
            "order_target": sampled["order_target"],
            "sampled_pair_count": int(sampled["sampled_pair_count"]),
            "positive_pair_count": int(sampled["positive_pair_count"]),
            "valid_graph_count": int(sampled["valid_graph_count"]),
        }

    def _decode_energy_outputs(
        self,
        latent_e: Tensor,
        h_fused: Tensor,
        batch: Tensor,
        *,
        include_graph_desc: bool = True,
    ) -> Dict[str, Tensor]:
        if include_graph_desc:
            graph_desc = self._decode_graph_descriptor_outputs(h_fused, batch)
        else:
            num_graphs = int(batch.max().item() + 1) if batch.numel() > 0 else 1
            graph_desc = h_fused.new_zeros((num_graphs, len(self.graph_descriptor_names)))
        legacy_energy_readout = bool(self._runtime_legacy_pretraining) and not self.direct_linear_noexpert
        if legacy_energy_readout:
            # Old MFM decodes node-level energy first, then mean-pools to graph level.
            energy_node = self.energy_head(latent_e)
            energy_pred = global_mean_pool(energy_node, batch)
        elif self.direct_linear_noexpert:
            energy_graph_repr = self.direct_energy_graph_pool(latent_e, batch)
            energy_pred = self.direct_energy_head(energy_graph_repr)
        else:
            energy_graph_repr = self.energy_graph_pool(latent_e, batch)
            energy_pred = self.energy_head(energy_graph_repr)
        return {
            "energy": energy_pred,
            "graph_desc": graph_desc,
        }

    def _decode_graph_descriptor_outputs(
        self,
        h_fused: Tensor,
        batch: Tensor,
    ) -> Tensor:
        if len(self.graph_descriptor_heads) == 0:
            num_graphs = int(batch.max().item() + 1) if batch.numel() > 0 else 1
            return h_fused.new_zeros((num_graphs, 0))
        return torch.cat(
            [self.graph_descriptor_heads[name](h_fused, batch) for name in self.graph_descriptor_names],
            dim=-1,
        )

    def _decode_charge_outputs(self, latent_q: Tensor, h_fused: Tensor, *, include_descriptors: bool = True) -> Tensor:
        prime = self.charge_prime_head(latent_q)
        if not include_descriptors or len(self.charge_descriptor_heads) == 0:
            return prime
        descriptor_parts = [self.charge_descriptor_heads[spec.name](h_fused) for spec in self.charge_descriptor_specs]
        return torch.cat((prime, *descriptor_parts), dim=-1)

    def _decode_element_outputs(self, latent_z: Tensor, h_fused: Tensor, *, include_descriptors: bool = True) -> Tensor:
        prime = self.elem_prime_head(latent_z)
        if not include_descriptors or len(self.element_descriptor_heads) == 0:
            return prime
        descriptor_parts = [self.element_descriptor_heads[spec.name](h_fused) for spec in self.element_descriptor_specs]
        return torch.cat((prime, *descriptor_parts), dim=-1)

    def _decode_outputs(
        self,
        latent_e: Tensor,
        latent_q: Tensor,
        latent_z: Tensor,
        latent_g: Tensor,
        latent_b: Tensor,
        h_fused: Tensor,
        data: Data,
        batch: Tensor,
        *,
        pos: Optional[Tensor],
        charge_mask_source: Optional[Tensor],
        include_energy_desc: bool = True,
        include_charge_desc: bool = True,
        include_element_desc: bool = True,
        include_bond: bool = True,
    ) -> Dict[str, Tensor | Dict[str, Tensor] | int]:
        if self.direct_linear_noexpert:
            coords_atom = self.direct_coord_head(latent_g)
        else:
            coords_atom = self.coord_decoder(latent_g)
        coords_pred, node_mask = to_dense_batch(coords_atom, batch, fill_value=0.0)

        charge_atom = self._decode_charge_outputs(latent_q, h_fused, include_descriptors=include_charge_desc)
        charge_dense, _ = to_dense_batch(charge_atom, batch, fill_value=0.0)
        charge_outputs = self._slice_outputs(charge_dense, self.charge_output_layout)

        elem_atom = self._decode_element_outputs(latent_z, h_fused, include_descriptors=include_element_desc)
        elem_dense, _ = to_dense_batch(elem_atom, batch, fill_value=0.0)
        elem_outputs = self._slice_outputs(elem_dense, self.element_output_layout)

        fused_graph_repr = global_mean_pool(h_fused, batch)
        energy_outputs = self._decode_energy_outputs(latent_e, h_fused, batch, include_graph_desc=include_energy_desc)
        bond_outputs = self._decode_bond_outputs(latent_b, data, batch, pos=pos) if include_bond else self._bond_empty_outputs(latent_b.device)

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
            "bond": bond_outputs,
            "fused_node_repr": h_fused,
            "fused_graph_repr": fused_graph_repr,
            "charge_mask": charge_mask,
            "node_mask": node_mask.unsqueeze(-1),
        }

    def _direct_stage1_latents(
        self,
        latent0: Tensor,
        *,
        bond_enabled: bool,
    ) -> Tuple[Tensor, Tensor, Tensor, Tensor, Tensor, Tensor]:
        zero = latent0.new_zeros(())
        latent_b = latent0 if bond_enabled else torch.zeros_like(latent0)
        return latent0, latent0, latent0, latent0, latent_b, zero

    def forward(self, data: Data) -> Dict[str, Tensor | Dict[str, Tensor]]:
        batch = ensure_batch_attr(data)
        if getattr(data, "pos", None) is None:
            raise ValueError("MultiTaskMoE requires data.pos")
        pos = data.pos
        bond_enabled = self._task_gate("bond_enabled")
        energy_desc_enabled = self._task_gate("energy_desc_enabled")
        charge_desc_enabled = self._task_gate("charge_desc_enabled")
        element_desc_enabled = self._task_gate("element_desc_enabled")

        latent0 = self.backbone(data)
        if self.direct_linear_noexpert:
            latent_e, latent_q, latent_z, latent_g, latent_b, balance_loss = self._direct_stage1_latents(
                latent0,
                bond_enabled=bond_enabled,
            )
        else:
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
            if bond_enabled:
                latent_b, bal_b = self._route(
                    latent0,
                    batch,
                    gate_layer=self.gate_bond,
                    experts=self.experts_bond,
                    top_k=self.top_k_bond,
                    pos=pos,
                )
            else:
                latent_b = torch.zeros_like(latent0)
                bal_b = latent0.new_zeros(())
            balance_loss = bal_e + bal_q + bal_z + bal_g + bal_b
        h_fused = self._fuse_latents(latent_e, latent_q, latent_z, latent_g, latent_b)

        outputs = self._decode_outputs(
            latent_e,
            latent_q,
            latent_z,
            latent_g,
            latent_b,
            h_fused,
            data,
            batch,
            pos=pos,
            charge_mask_source=getattr(data, "charge_mask", None),
            include_energy_desc=energy_desc_enabled,
            include_charge_desc=charge_desc_enabled,
            include_element_desc=element_desc_enabled,
            include_bond=bond_enabled,
        )
        outputs["balance_loss"] = balance_loss
        return outputs

    def get_pooling_weight_metrics(self) -> Dict[str, float]:
        metrics: Dict[str, float] = {}
        pool_modules = {
            "energy_graph": getattr(self, "energy_graph_pool", None),
        }
        for pool_name, pool_module in pool_modules.items():
            if isinstance(pool_module, LearnedPoolingMixer):
                for weight_name, weight_value in pool_module.weight_dict().items():
                    metrics[f"pooling/{pool_name}/{weight_name}"] = float(weight_value)
        for head_name, head_module in self.graph_descriptor_heads.items():
            if isinstance(head_module, TaskSpecificGraphHead):
                for weight_name, weight_value in head_module.weight_dict().items():
                    metrics[f"pooling/graph_desc/{head_name}/{weight_name}"] = float(weight_value)
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
        bond_enabled = self._task_gate("bond_enabled")
        energy_desc_enabled = self._task_gate("energy_desc_enabled")
        charge_desc_enabled = self._task_gate("charge_desc_enabled")
        element_desc_enabled = self._task_gate("element_desc_enabled")

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
                "bond": self.experts_bond,
            }
            for task_name, task_experts in expert_groups.items():
                if any(len(expert.real_layers) > 0 for expert in task_experts):
                    raise ValueError(
                        f"forward_from_latent(pos=None) requires real layers disabled for {task_name}."
                    )

        if self.direct_linear_noexpert:
            latent_e, latent_q, latent_z, latent_g, latent_b, balance_loss = self._direct_stage1_latents(
                latent0,
                bond_enabled=bond_enabled,
            )
        else:
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
            if bond_enabled:
                latent_b, bal_b = self._route(
                    latent0,
                    batch,
                    gate_layer=self.gate_bond,
                    experts=self.experts_bond,
                    top_k=self.top_k_bond,
                    pos=pos_flat,
                )
            else:
                latent_b = torch.zeros_like(latent0)
                bal_b = latent0.new_zeros(())
            balance_loss = bal_e + bal_q + bal_z + bal_g + bal_b
        h_fused = self._fuse_latents(latent_e, latent_q, latent_z, latent_g, latent_b)

        if not return_dense:
            fused_graph_repr = global_mean_pool(h_fused, batch)
            coords_out = self.direct_coord_head(latent_g) if self.direct_linear_noexpert else self.coord_decoder(latent_g)
            return {
                "coords": coords_out,
                "charge": self._slice_outputs(
                    self._decode_charge_outputs(latent_q, h_fused, include_descriptors=charge_desc_enabled),
                    self.charge_output_layout,
                ),
                "element": self._slice_outputs(
                    self._decode_element_outputs(latent_z, h_fused, include_descriptors=element_desc_enabled),
                    self.element_output_layout,
                ),
                "energy": self._decode_energy_outputs(latent_e, h_fused, batch, include_graph_desc=energy_desc_enabled),
                "bond": self._decode_bond_outputs(latent_b, data_static, batch, pos=pos_flat) if bond_enabled else self._bond_empty_outputs(latent0.device),
                "fused_node_repr": h_fused,
                "fused_graph_repr": fused_graph_repr,
                "charge_mask": torch.ones(latent0.size(0), 1, device=latent0.device, dtype=torch.bool),
                "node_mask": torch.ones(latent0.size(0), 1, device=latent0.device, dtype=torch.bool),
                "balance_loss": balance_loss,
            }

        outputs = self._decode_outputs(
            latent_e,
            latent_q,
            latent_z,
            latent_g,
            latent_b,
            h_fused,
            data_static,
            batch,
            pos=pos_flat,
            charge_mask_source=getattr(data_static, "charge_mask", None),
            include_energy_desc=energy_desc_enabled,
            include_charge_desc=charge_desc_enabled,
            include_element_desc=element_desc_enabled,
            include_bond=bond_enabled,
        )
        outputs["balance_loss"] = balance_loss
        return outputs
