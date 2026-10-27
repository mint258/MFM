from __future__ import annotations

from contextlib import nullcontext
from copy import deepcopy
from typing import Iterable, Mapping

import torch
import torch.nn as nn
from torch import Tensor
from torch_geometric.data import Data
from torch_geometric.utils import to_dense_batch

from ..data.descriptor_schema import (
    BOND_INDEX_FIELD,
    BOND_NEGATIVE_COUNT_FIELD,
    BOND_NEGATIVE_UPPER_IDS_FIELD,
    BOND_ORDER_FIELD,
    BOND_ORDER_CLASS_NAMES,
    BOND_ORDER_NUM_CLASSES,
    BOND_STATUS_FIELD,
    SAMPLE_TYPE_ID_FIELD,
    graph_descriptor_indices,
    normalize_graph_descriptor_names,
)
from ..supervision import Objective, normalize_objectives
from .backbone import RealCoordTransformerBackbone
from .v3_attention_numerics import (LEGACY_AGGREGATION, CENTERED_FP32, validate_aggregation_mode,
                                    require_centered_backbone, require_centered_f32_context)
from .common import Linear, ensure_batch_attr
from .v3_geometry_fp32 import (LEGACY_GEOMETRY,
    validate_geometry_mode, require_geometry_constructor, require_geometry_binding)
from .v3_attention_projection import (LEGACY_PROJECTION, BLOCKED_PROJECTION,
    validate_projection_mode, require_projection_constructor, require_projection_backbone)
from .v3_numeric_stability import (LEGACY, COMPENSATED, apply_numeric_mode, validate_numeric_mode,
                                   numeric_mode, require_fp32_context)
from .heads import (
    BondPairHead,
    CoordinateDecoder,
    ResidualCoordinateDecoder,
    EquivariantDenoisingHead,
    EnergyHead,
    TaskSpecificGraphHead,
    TaskSpecificNodeHead,
    UnifiedGraphPooling,
)
from .outputs import BondOutputs, PretrainOutputs
from .normalization import Phase1RegressionNormalization
from .phase1_specs import (
    PHASE1_BOND_ORDER_CLASS_NAMES,
    PHASE1_BOND_ORDER_NUM_CLASSES,
    PHASE1_GRAPH_DESCRIPTOR_NAMES,
    descriptor_specs_for_profile,
)
from .routes import MAIN_TASKS, TaskRouteConfig, build_task_adapter


OBJECTIVE_TO_ROUTE = {
    Objective.ENERGY: "energy",
    Objective.CHARGE: "charge",
    Objective.ELEMENT: "element",
    Objective.GEOMETRY: "geometry",
    Objective.BOND: "bond",
}


class SharedBackboneMFM(nn.Module):
    """Shared H0 with independent task prediction routes and no cross-task fusion."""

    architecture_type = "shared_multitask"

    def __init__(
        self,
        backbone_config: Mapping[str, object],
        *,
        task_routes: TaskRouteConfig,
        expert_config: Mapping[str, object] | None = None,
        head_config: Mapping[str, object] | None = None,
    ) -> None:
        super().__init__()
        expert_config = dict(expert_config or {})
        head_config = dict(head_config or {})
        mode = validate_numeric_mode(backbone_config.get('numeric_mode', LEGACY))
        if validate_numeric_mode(head_config.get('numeric_mode', LEGACY)) != mode:
            raise ValueError('Backbone/head numeric modes must agree')
        self.attention_aggregation_mode = validate_aggregation_mode(backbone_config.get(
            'attention_aggregation_mode', LEGACY_AGGREGATION))
        self.attention_projection_mode = validate_projection_mode(backbone_config.get(
            "attention_projection_mode", LEGACY_PROJECTION))
        require_projection_constructor(self.attention_projection_mode,
            dim=backbone_config.get("dim", 512), heads=backbone_config.get("heads", 8),
            layers=backbone_config.get("layers", 6), dropout=backbone_config.get("dropout", 0.),
            aggregation=self.attention_aggregation_mode, numeric=mode)
        self.geometry_mode = validate_geometry_mode(backbone_config.get("geometry_mode", LEGACY_GEOMETRY))
        require_geometry_constructor(self.geometry_mode,
            dim=backbone_config.get("dim", 512), heads=backbone_config.get("heads", 8),
            layers=backbone_config.get("layers", 6), dropout=backbone_config.get("dropout", 0.),
            aggregation=self.attention_aggregation_mode, projection=self.attention_projection_mode, numeric=mode)
        self.backbone_config = dict(backbone_config)
        self.expert_config = expert_config
        self.head_config = deepcopy(head_config)
        self.task_route_config = task_routes
        self.head_profile = str(head_config.get("profile", "legacy")).strip().lower()
        self.charge_descriptor_specs, self.element_descriptor_specs = descriptor_specs_for_profile(self.head_profile)
        self.regression_output_normalizer = None
        if "regression_output_normalization" in head_config:
            if self.head_profile != "phase1":
                raise ValueError("regression_output_normalization is an explicit Phase 1-only option")
            self.regression_output_normalizer = Phase1RegressionNormalization(head_config["regression_output_normalization"])
            self.head_config["regression_output_normalization"] = deepcopy(self.regression_output_normalizer.contract)
        self.geometry_head_mode = str(head_config.get("geometry_head", "legacy")).strip().lower()
        if self.geometry_head_mode not in {"legacy", "residual", "equivariant_noise"}:
            raise ValueError(f"Unsupported geometry_head: {self.geometry_head_mode}")
        self.bond_order_only = self.head_profile == "phase1"
        self.bond_order_class_names = PHASE1_BOND_ORDER_CLASS_NAMES if self.bond_order_only else BOND_ORDER_CLASS_NAMES
        self.bond_order_num_classes = PHASE1_BOND_ORDER_NUM_CLASSES if self.bond_order_only else BOND_ORDER_NUM_CLASSES

        self.n_atom_types = int(backbone_config.get("n_atom_types", 119))
        self.pad_elem_index = self.n_atom_types - 1
        self.latent_dim = int(backbone_config.get("dim", 512))
        self.bond_negative_ratio = 0.0 if self.bond_order_only else max(0.0, float(head_config.get("bond_negative_ratio", 1.0)))

        self.backbone = RealCoordTransformerBackbone(
            n_atom_types=self.n_atom_types,
            dim=self.latent_dim,
            layers=int(backbone_config.get("layers", 6)),
            heads=int(backbone_config.get("heads", 8)),
            ff_mult=int(backbone_config.get("ff_mult", 2)),
            dropout=float(backbone_config.get("dropout", 0.0)),
            use_dist_bias=bool(backbone_config.get("use_dist_bias", True)),
            use_radius_mask=bool(backbone_config.get("use_radius_mask", False)),
            radius=float(backbone_config.get("radius", 8.0)),
            activation_checkpointing=backbone_config.get("activation_checkpointing", False),
            attention_aggregation_mode=self.attention_aggregation_mode,
            attention_projection_mode=self.attention_projection_mode,
            geometry_mode=self.geometry_mode,
        )
        self.graph_pool = UnifiedGraphPooling(self.latent_dim)

        self.energy_head = EnergyHead(self.latent_dim)
        self.charge_head = Linear(self.latent_dim, 1)
        self.element_head = Linear(self.latent_dim, self.n_atom_types)
        # Phase 1 models are initialized on CPU before moving to their device.
        # Geometry candidates must not shift initialization of subsequent
        # common heads or fixed Expert adapters. Keep legacy-profile RNG use.
        geometry_rng = torch.random.fork_rng(devices=[]) if self.head_profile == "phase1" else nullcontext()
        with geometry_rng:
            if self.geometry_head_mode == "residual":
                self.geometry_head = ResidualCoordinateDecoder(
                    self.latent_dim,
                    hidden_dim=int(head_config.get("geometry_residual_hidden_dim", 32)),
                    correction_scale=float(head_config.get("geometry_residual_scale", 0.1)),
                    normalization=str(head_config.get("geometry_residual_normalization", "molecule")),
                    radius=float(head_config.get("geometry_radius", 5.0)),
                )
            elif self.geometry_head_mode == "equivariant_noise":
                self.geometry_head = EquivariantDenoisingHead(
                    self.latent_dim, radius=float(head_config.get("geometry_radius", 5.0)),
                    rbf_count=int(head_config.get("geometry_rbf_count", 32)),
                    hidden_dim=int(head_config.get("geometry_hidden_dim", 64)),
                    normalization=str(head_config.get("geometry_normalization", "none")),
                    message_layers=int(head_config.get("geometry_message_layers", 0)),
                    pair_chunk_size=int(head_config.get("geometry_pair_chunk_size", 8192)),
                )
            else:
                self.geometry_head = CoordinateDecoder(self.latent_dim)
        self.bond_head = BondPairHead(
            self.latent_dim, self.bond_order_num_classes, include_existence=not self.bond_order_only,
        )

        graph_selection = head_config.get("graph_descriptor_names")
        if self.head_profile == "phase1":
            if graph_selection is not None and normalize_graph_descriptor_names(graph_selection) != PHASE1_GRAPH_DESCRIPTOR_NAMES:
                raise ValueError("Phase 1 graph_descriptor_names must match the fixed 23-target label manifest")
            graph_selection = PHASE1_GRAPH_DESCRIPTOR_NAMES
        self.graph_descriptor_names = normalize_graph_descriptor_names(graph_selection)
        self.graph_descriptor_target_indices = graph_descriptor_indices(self.graph_descriptor_names)
        self.graph_descriptor_heads = nn.ModuleDict(
            {name: TaskSpecificGraphHead(self.latent_dim, 1) for name in self.graph_descriptor_names}
        )
        self.charge_descriptor_heads = nn.ModuleDict(
            {spec.name: TaskSpecificNodeHead(self.latent_dim, spec.num_outputs) for spec in self.charge_descriptor_specs}
        )
        self.element_descriptor_heads = nn.ModuleDict(
            {spec.name: TaskSpecificNodeHead(self.latent_dim, spec.num_outputs) for spec in self.element_descriptor_specs}
        )

        # Build route-specific modules after every shared/common component. With a
        # common seed, Light and Expert presets therefore receive bit-identical
        # backbone and head initialization; only Expert adapters consume extra RNG.
        expert_with_radius = dict(expert_config)
        expert_with_radius.setdefault("radius", float(backbone_config.get("radius", 8.0)))
        self.task_adapters = nn.ModuleDict(
            {
                task: build_task_adapter(task_routes.route_for(task), self.latent_dim, expert_with_radius)
                for task in MAIN_TASKS
            }
        )

        apply_numeric_mode(self, mode)

    def encode_atoms(self, batch: Data) -> Tensor:
        """Return canonical shared representation H0 with shape [N_atom, D]."""
        declared_geometry = validate_geometry_mode(self.backbone_config.get("geometry_mode", LEGACY_GEOMETRY))
        if self.geometry_mode != declared_geometry:
            raise ValueError("Model configuration/geometry runtime identity differs")
        require_geometry_binding(self.backbone, expected_mode=declared_geometry)
        declared_projection = validate_projection_mode(self.backbone_config.get(
            "attention_projection_mode", LEGACY_PROJECTION))
        if self.attention_projection_mode != declared_projection:
            raise ValueError("Model configuration/projection runtime identity differs")
        if declared_projection == BLOCKED_PROJECTION:
            require_projection_backbone(self.backbone, expected_mode=BLOCKED_PROJECTION)
        if self.attention_aggregation_mode == CENTERED_FP32:
            require_centered_backbone(self.backbone)
            require_centered_f32_context(self.backbone, batch.pos)
        if numeric_mode(self) == COMPENSATED:
            require_fp32_context(self, batch.pos)
        return self.backbone(batch)

    def encode_graph(self, batch: Data, pooling: str = "mean") -> Tensor:
        h0 = self.encode_atoms(batch)
        return self.graph_pool(h0, ensure_batch_attr(batch), pooling=pooling)

    def task_adapter(self, task_name: str, h0: Tensor, batch: Data) -> Tensor:
        if task_name not in self.task_adapters:
            raise KeyError(f"No task adapter named '{task_name}'")
        if getattr(batch, "pos", None) is None:
            raise ValueError("Task adapters require batch.pos")
        return self.task_adapters[task_name](h0, batch=ensure_batch_attr(batch), pos=batch.pos)

    def forward_pretrain(
        self,
        batch: Data,
        objectives: Iterable[Objective | str],
        *,
        include_task_repr: bool = False,
    ) -> PretrainOutputs:
        active = normalize_objectives(objectives)
        batch_index = ensure_batch_attr(batch)
        if getattr(batch, "pos", None) is None:
            raise ValueError("SharedBackboneMFM requires batch.pos")

        h0 = self.encode_atoms(batch)
        h_graph = self.graph_pool(h0, batch_index, pooling="mean")
        outputs = PretrainOutputs(atom_repr=h0, graph_repr=h_graph)

        _, node_mask_2d = to_dense_batch(h0[:, 0], batch_index, fill_value=0.0)
        outputs.node_mask = node_mask_2d.unsqueeze(-1)
        outputs.charge_mask = self._build_charge_mask(batch, batch_index, node_mask_2d)

        for objective, task_name in OBJECTIVE_TO_ROUTE.items():
            if objective not in active:
                continue
            task_repr = self.task_adapter(task_name, h0, batch)
            if include_task_repr:
                outputs.task_repr[task_name] = task_repr
            if objective == Objective.ENERGY:
                outputs.energy_pred = self._original_regression_units("energy", self.energy_head(task_repr, batch_index))
            elif objective == Objective.CHARGE:
                charge_atom = self._original_regression_units("charge", self.charge_head(task_repr))
                outputs.charge_pred, _ = to_dense_batch(charge_atom, batch_index, fill_value=0.0)
            elif objective == Objective.ELEMENT:
                element_atom = self.element_head(task_repr)
                outputs.element_logits, _ = to_dense_batch(element_atom, batch_index, fill_value=0.0)
            elif objective == Objective.GEOMETRY:
                if self.geometry_head_mode == "equivariant_noise":
                    noise_atom = self.geometry_head(h0, batch.pos, batch_index)
                    outputs.noise_pred, _ = to_dense_batch(noise_atom, batch_index, fill_value=0.0)
                    coordinate_atom = batch.pos - noise_atom
                elif self.geometry_head_mode == "residual":
                    coordinate_atom = self.geometry_head(task_repr, batch.pos, batch_index)
                else:
                    coordinate_atom = self.geometry_head(task_repr)
                outputs.coordinate_pred, _ = to_dense_batch(coordinate_atom, batch_index, fill_value=0.0)
            elif objective == Objective.BOND:
                outputs.bond = self._forward_bond(task_repr, batch, batch_index)

        if Objective.GRAPH_DESCRIPTOR in active:
            outputs.graph_descriptor_by_name = {
                name: self._original_regression_units("graph_descriptor/" + name, self.graph_descriptor_heads[name](h0, batch_index))
                for name in self.graph_descriptor_names
            }
            if outputs.graph_descriptor_by_name:
                outputs.graph_descriptor_pred = torch.cat(
                    list(outputs.graph_descriptor_by_name.values()), dim=-1
                )
            else:
                num_graphs = int(batch_index.max().item() + 1) if batch_index.numel() else 1
                outputs.graph_descriptor_pred = h0.new_zeros((num_graphs, 0))
        if Objective.CHARGE_DESCRIPTOR in active:
            outputs.charge_descriptor_pred = self._forward_node_descriptors(
                h0, batch_index, self.charge_descriptor_specs, self.charge_descriptor_heads
            )
        if Objective.ELEMENT_DESCRIPTOR in active:
            outputs.element_descriptor_pred = self._forward_node_descriptors(
                h0, batch_index, self.element_descriptor_specs, self.element_descriptor_heads
            )
        return outputs

    def forward(self, batch: Data) -> PretrainOutputs:
        return self.forward_pretrain(batch, Objective)

    def _forward_graph_descriptors(self, h0: Tensor, batch_index: Tensor) -> Tensor:
        if not self.graph_descriptor_names:
            num_graphs = int(batch_index.max().item() + 1) if batch_index.numel() else 1
            return h0.new_zeros((num_graphs, 0))
        return torch.cat(
            [self._original_regression_units("graph_descriptor/" + name, self.graph_descriptor_heads[name](h0, batch_index))
             for name in self.graph_descriptor_names], dim=-1
        )

    def _original_regression_units(self, name: str, raw: Tensor) -> Tensor:
        if self.regression_output_normalizer is None:
            return raw
        return self.regression_output_normalizer(name, raw)

    def _forward_node_descriptors(self, h0: Tensor, batch_index: Tensor, specs, heads: nn.ModuleDict) -> dict[str, Tensor]:
        result: dict[str, Tensor] = {}
        for spec in specs:
            atom_pred = heads[spec.name](h0)
            if spec.task_type == "regression":
                atom_pred = self._original_regression_units("node_descriptor/" + spec.name, atom_pred)
            # Transform real nodes before densification; padding remains zero.
            result[spec.name], _ = to_dense_batch(atom_pred, batch_index, fill_value=0.0)
        return result

    @staticmethod
    def _build_charge_mask(batch: Data, batch_index: Tensor, node_mask: Tensor) -> Tensor:
        source = getattr(batch, "charge_mask", None)
        if isinstance(source, Tensor) and source.size(0) == batch_index.numel():
            if source.dim() == 1:
                source = source.unsqueeze(-1)
            dense, _ = to_dense_batch(source.float(), batch_index, fill_value=0.0)
            return (dense > 0.5) & node_mask.unsqueeze(-1)
        return node_mask.unsqueeze(-1)

    def _empty_bond_outputs(self, device: torch.device) -> BondOutputs:
        return BondOutputs(
            existence=torch.zeros((0, 0 if self.bond_order_only else 1), device=device),
            order=torch.zeros((0, self.bond_order_num_classes), device=device),
            pair_index=torch.zeros((2, 0), device=device, dtype=torch.long),
            pair_graph_index=torch.zeros((0,), device=device, dtype=torch.long),
            existence_target=torch.zeros((0, 1), device=device),
            order_target=torch.zeros((0,), device=device, dtype=torch.long),
        )

    @staticmethod
    def _graph_ptr(batch_index: Tensor, num_graphs: int) -> Tensor:
        counts = torch.bincount(batch_index, minlength=num_graphs) if batch_index.numel() else batch_index.new_zeros(num_graphs)
        return torch.cat((batch_index.new_zeros(1), counts.cumsum(0)), dim=0)

    @staticmethod
    def _graph_string_attr(data: Data, name: str, num_graphs: int, default: str = "") -> list[str]:
        value = getattr(data, name, None)
        if isinstance(value, str):
            return [value] * num_graphs
        if isinstance(value, (list, tuple)):
            result = [str(item) if isinstance(item, str) else default for item in value[:num_graphs]]
            return result + [default] * (num_graphs - len(result))
        return [default] * num_graphs

    @staticmethod
    def _graph_long_attr(data: Data, name: str, num_graphs: int, default: int = 0) -> list[int]:
        value = getattr(data, name, None)
        if isinstance(value, Tensor):
            result = [int(item) for item in value.view(-1).detach().cpu().tolist()[:num_graphs]]
        elif isinstance(value, (list, tuple)):
            result = [int(item) for item in value[:num_graphs]]
        else:
            result = []
        return result + [int(default)] * (num_graphs - len(result))

    @staticmethod
    def _decode_upper_pair_ids(upper_ids: Tensor, num_nodes: int, start: int) -> Tensor:
        if upper_ids.numel() == 0 or num_nodes < 2:
            return upper_ids.new_zeros((0, 2), dtype=torch.long)
        row_lengths = torch.arange(num_nodes - 1, 0, -1, device=upper_ids.device)
        row_offsets = torch.cat((upper_ids.new_zeros(1), row_lengths.cumsum(0)[:-1]), dim=0)
        local_ids = upper_ids.long().view(-1)
        row = torch.bucketize(local_ids, row_offsets, right=True) - 1
        col = row + 1 + (local_ids - row_offsets[row])
        return torch.stack((row + start, col + start), dim=1)

    @staticmethod
    def _encode_upper_pair_ids(pair_index: Tensor, num_nodes: int, start: int) -> Tensor:
        if pair_index.numel() == 0 or num_nodes < 2:
            return pair_index.new_zeros((0,), dtype=torch.long)
        pair_index = pair_index.long().view(2, -1)
        src = pair_index[0] - start
        dst = pair_index[1] - start
        row_lengths = torch.arange(num_nodes - 1, 0, -1, device=pair_index.device)
        row_offsets = torch.cat((pair_index.new_zeros(1), row_lengths.cumsum(0)[:-1]), dim=0)
        return row_offsets[src] + (dst - src - 1)

    def _sample_bond_pairs(self, data: Data, batch_index: Tensor) -> BondOutputs:
        if self.bond_order_only:
            return self._phase1_positive_bond_pairs(data, batch_index)
        device = batch_index.device
        num_graphs = int(batch_index.max().item() + 1) if batch_index.numel() else 1
        bond_index = getattr(data, BOND_INDEX_FIELD, None)
        bond_index = (
            bond_index.to(device=device, dtype=torch.long).view(2, -1)
            if isinstance(bond_index, Tensor)
            else torch.zeros((2, 0), device=device, dtype=torch.long)
        )
        bond_order = getattr(data, BOND_ORDER_FIELD, None)
        bond_order = (
            bond_order.to(device=device, dtype=torch.long).view(-1)
            if isinstance(bond_order, Tensor)
            else torch.zeros((0,), device=device, dtype=torch.long)
        )
        if bond_order.numel() < bond_index.size(1):
            padded = torch.zeros((bond_index.size(1),), device=device, dtype=torch.long)
            padded[: bond_order.numel()] = bond_order
            bond_order = padded
        else:
            bond_order = bond_order[: bond_index.size(1)]

        statuses = self._graph_string_attr(data, BOND_STATUS_FIELD, num_graphs)
        sample_types = self._graph_long_attr(data, SAMPLE_TYPE_ID_FIELD, num_graphs)
        negative_counts = self._graph_long_attr(data, BOND_NEGATIVE_COUNT_FIELD, num_graphs)
        negative_ids = getattr(data, BOND_NEGATIVE_UPPER_IDS_FIELD, None)
        negative_ids = negative_ids.to(device=device, dtype=torch.long).view(-1) if isinstance(negative_ids, Tensor) else None
        ptr = self._graph_ptr(batch_index, num_graphs)
        graph_counts = ptr[1:] - ptr[:-1]
        valid = (
            torch.tensor(sample_types, device=device).eq(0)
            & torch.tensor([status.lower() == "ok" for status in statuses], device=device)
            & graph_counts.ge(2)
        )
        edge_graph = batch_index[bond_index[0]] if bond_index.numel() else torch.zeros((0,), device=device, dtype=torch.long)
        positive_mask = valid.index_select(0, edge_graph) if edge_graph.numel() else torch.zeros((0,), device=device, dtype=torch.bool)
        positive_index = bond_index[:, positive_mask]
        positive_graph = edge_graph[positive_mask]
        positive_order = bond_order[positive_mask]

        pair_parts: list[Tensor] = []
        graph_parts: list[Tensor] = []
        existence_parts: list[Tensor] = []
        order_parts: list[Tensor] = []
        if positive_index.numel():
            pair_parts.append(positive_index)
            graph_parts.append(positive_graph)
            existence_parts.append(torch.ones((positive_index.size(1), 1), device=device))
            order_parts.append(positive_order)

        negative_offset = 0
        for graph_idx in range(num_graphs):
            supplied_count = max(0, negative_counts[graph_idx])
            if not bool(valid[graph_idx]):
                negative_offset += supplied_count
                continue
            start, end = int(ptr[graph_idx]), int(ptr[graph_idx + 1])
            num_nodes = end - start
            graph_positive_mask = positive_graph.eq(graph_idx)
            positive_count = int(graph_positive_mask.sum())
            if negative_ids is not None and supplied_count > 0:
                candidates = negative_ids[negative_offset : negative_offset + supplied_count]
            else:
                total = num_nodes * (num_nodes - 1) // 2
                candidates = torch.arange(total, device=device)
                if positive_count:
                    positive_ids = self._encode_upper_pair_ids(
                        positive_index[:, graph_positive_mask], num_nodes, start
                    )
                    keep = torch.ones((total,), device=device, dtype=torch.bool)
                    keep[positive_ids.unique()] = False
                    candidates = candidates[keep]
            negative_offset += supplied_count
            target_count = min(int(candidates.numel()), max(1, int(round(self.bond_negative_ratio * max(1, positive_count)))))
            if target_count < candidates.numel():
                candidates = candidates[torch.randperm(candidates.numel(), device=device)[:target_count]]
            else:
                candidates = candidates[:target_count]
            decoded = self._decode_upper_pair_ids(candidates, num_nodes, start)
            if decoded.numel():
                pair_parts.append(decoded.t().contiguous())
                graph_parts.append(torch.full((decoded.size(0),), graph_idx, device=device, dtype=torch.long))
                existence_parts.append(torch.zeros((decoded.size(0), 1), device=device))
                order_parts.append(torch.zeros((decoded.size(0),), device=device, dtype=torch.long))

        if not pair_parts:
            empty = self._empty_bond_outputs(device)
            empty.valid_graph_count = int(valid.sum())
            return empty
        return BondOutputs(
            existence=torch.empty((0, 1), device=device),
            order=torch.empty((0, BOND_ORDER_NUM_CLASSES), device=device),
            pair_index=torch.cat(pair_parts, dim=1),
            pair_graph_index=torch.cat(graph_parts),
            existence_target=torch.cat(existence_parts),
            order_target=torch.cat(order_parts),
            sampled_pair_count=sum(part.size(0) for part in existence_parts),
            positive_pair_count=int(positive_index.size(1)),
            valid_graph_count=int(valid.sum()),
        )

    def _phase1_positive_bond_pairs(self, data: Data, batch_index: Tensor) -> BondOutputs:
        """Select labeled clean positive edges; never sample or classify nonedges."""
        device = batch_index.device
        num_graphs = int(batch_index.max().item() + 1) if batch_index.numel() else 1
        statuses = self._graph_string_attr(data, BOND_STATUS_FIELD, num_graphs)
        sample_types = self._graph_long_attr(data, SAMPLE_TYPE_ID_FIELD, num_graphs)
        counts = torch.bincount(batch_index, minlength=num_graphs)
        valid_graphs = (
            torch.tensor(sample_types, device=device).eq(0)
            & torch.tensor([status.lower() == "ok" for status in statuses], device=device)
            & counts.ge(2)
        )
        empty = self._empty_bond_outputs(device)
        empty.valid_graph_count = int(valid_graphs.sum())
        index = getattr(data, BOND_INDEX_FIELD, None)
        order = getattr(data, BOND_ORDER_FIELD, None)
        if not isinstance(index, Tensor) or not isinstance(order, Tensor) or index.numel() == 0 or batch_index.numel() == 0:
            return empty
        index = index.to(device=device, dtype=torch.long).view(2, -1)
        order = order.to(device=device, dtype=torch.long).view(-1)
        labeled_count = min(index.size(1), order.numel())
        index, order = index[:, :labeled_count], order[:labeled_count]
        valid_index = index.ge(0).all(dim=0) & index.lt(batch_index.numel()).all(dim=0)
        safe_index = index.clamp(min=0, max=batch_index.numel() - 1)
        graph_index = batch_index[safe_index[0]]
        keep = (
            valid_index & valid_graphs[graph_index]
            & batch_index[safe_index[1]].eq(graph_index)
            & index[0].ne(index[1]) & order.ge(1) & order.lt(BOND_ORDER_NUM_CLASSES)
        )
        index, order, graph_index = index[:, keep], order[keep], graph_index[keep]
        pair_count = int(order.numel())
        return BondOutputs(
            existence=torch.zeros((pair_count, 0), device=device),
            order=torch.empty((0, self.bond_order_num_classes), device=device),
            pair_index=index,
            pair_graph_index=graph_index,
            existence_target=torch.ones((pair_count, 1), device=device),
            # Existing LMDB IDs 1..5 become CE class IDs 0..4; class 'none' is absent.
            order_target=order - 1,
            sampled_pair_count=pair_count,
            positive_pair_count=pair_count,
            valid_graph_count=int(valid_graphs.sum()),
        )

    def _forward_bond(self, atom_repr: Tensor, data: Data, batch_index: Tensor) -> BondOutputs:
        sampled = self._sample_bond_pairs(data, batch_index)
        sampled.existence, sampled.order = self.bond_head(atom_repr, sampled.pair_index, getattr(data, "pos", None))
        return sampled

    def pretraining_head_parameters(self):
        modules = (
            self.energy_head,
            self.charge_head,
            self.element_head,
            self.geometry_head,
            self.bond_head,
            self.graph_descriptor_heads,
            self.charge_descriptor_heads,
            self.element_descriptor_heads,
        )
        for module in modules:
            yield from module.parameters()

    def config_dict(self) -> dict[str, object]:
        return {
            "architecture_type": self.architecture_type,
            "backbone_config": dict(self.backbone_config),
            "expert_config": dict(self.expert_config),
            "head_config": deepcopy(self.head_config),
            "task_route_per_task": self.task_route_config.to_dict(),
        }
