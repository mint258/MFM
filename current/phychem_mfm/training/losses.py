from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import torch
import torch.nn.functional as F
from torch import Tensor
from torch_geometric.utils import to_dense_batch

from ..data.descriptor_schema import (
    CHARGE_DESCRIPTOR_SPECS,
    ELEMENT_CORRUPT_MASK_FIELD,
    ELEMENT_DESCRIPTOR_SPECS,
    GRAPH_FIELD,
    GRAPH_MASK_FIELD,
    NODE_MASK_FIELD,
)
from ..model.outputs import PretrainOutputs
from ..supervision import DESCRIPTOR_OBJECTIVES, Objective, SupervisionConfig
from .data import SAMPLE_TYPE_TO_ID
from .geometry import angle_cos, build_local_graph, map_global_to_dense_indices, morse_energy, torsion_sin_cos


CLEAN = SAMPLE_TYPE_TO_ID["clean"]
GEOM = SAMPLE_TYPE_TO_ID["geom"]
TOPO = SAMPLE_TYPE_TO_ID["topo"]
BOTH = SAMPLE_TYPE_TO_ID["both"]


@dataclass(frozen=True)
class LossWeights:
    energy: float = 1.0
    charge: float = 1.0
    element: float = 1.0
    bond_existence: float = 0.2
    bond_order: float = 0.2
    distance: float = 1.0
    angle: float = 0.0
    torsion: float = 0.0
    graph_descriptor: float = 0.2
    charge_descriptor: float = 0.25
    element_descriptor: float = 0.25
    cutoff: float = 2.0
    morse_d: float = 1.0
    morse_a: float = 0.6
    element_label_smoothing: float = 0.1
    element_temperature: float = 1.5
    element_entropy_reg: float = 0.05
    element_logit_l2: float = 0.0001

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "LossWeights":
        known = {field_name for field_name in cls.__dataclass_fields__}
        return cls(**{key: values[key] for key in known if key in values})


@dataclass(frozen=True)
class StageSchedule:
    stage1_max_steps: int = 15000
    descriptor_ramp_steps: int = 5000
    stage1_decay_steps: int = 5000
    stage1_floor: float = 0.3

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "StageSchedule":
        known = {field_name for field_name in cls.__dataclass_fields__}
        return cls(**{key: values[key] for key in known if key in values})

    def descriptor_scale(self, exposure_step: int) -> float:
        if exposure_step < self.stage1_max_steps:
            return 0.0
        if self.descriptor_ramp_steps <= 0:
            return 1.0
        progress = (exposure_step - self.stage1_max_steps) / max(1, self.descriptor_ramp_steps)
        return float(min(1.0, max(0.0, progress)))

    def stage1_scale(self, exposure_step: int) -> float:
        if exposure_step < self.stage1_max_steps or self.stage1_decay_steps <= 0:
            return 1.0
        floor = min(1.0, max(0.0, float(self.stage1_floor)))
        progress = (exposure_step - self.stage1_max_steps) / max(1, self.stage1_decay_steps)
        return float(1.0 - min(1.0, max(0.0, progress)) * (1.0 - floor))


@dataclass
class LossResult:
    total: Tensor
    selection: Tensor
    raw: dict[str, Tensor] = field(default_factory=dict)
    weighted: dict[str, Tensor] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=dict)
    descriptor_scale: float = 0.0
    stage1_scale: float = 1.0
    groups: dict[str, Tensor] = field(default_factory=dict)
    group_weights: dict[str, float] = field(default_factory=dict)
    task_weights: dict[str, float] = field(default_factory=dict)
    valid_tasks: tuple[str, ...] = ()
    missing_tasks: tuple[str, ...] = ()

    def scalar_metrics(self, prefix: str = "") -> dict[str, float]:
        result = {
            f"{prefix}loss/total": float(self.total.detach()),
            f"{prefix}loss/selection": float(self.selection.detach()),
            f"{prefix}schedule/descriptor_scale": self.descriptor_scale,
            f"{prefix}schedule/stage1_scale": self.stage1_scale,
        }
        result.update({f"{prefix}loss/raw/{key}": float(value.detach()) for key, value in self.raw.items()})
        result.update({f"{prefix}loss/weighted/{key}": float(value.detach()) for key, value in self.weighted.items()})
        result.update({f"{prefix}count/{key}": float(value) for key, value in self.counts.items()})
        result.update({f"{prefix}loss/group/{key}": float(value.detach()) for key, value in self.groups.items()})
        result.update({f"{prefix}weight/group/{key}": float(value) for key, value in self.group_weights.items()})
        result.update({f"{prefix}weight/task/{key}": float(value) for key, value in self.task_weights.items()})
        if self.groups or self.valid_tasks or self.missing_tasks:
            result[f"{prefix}count/valid_tasks"] = float(len(self.valid_tasks))
            result[f"{prefix}count/missing_tasks"] = float(len(self.missing_tasks))
        return result


def _masked_mean(values: Tensor, mask: Tensor) -> Tensor:
    mask = mask.float()
    return (values * mask).sum() / mask.sum().clamp(min=1.0)


def standardized_huber(pred: Tensor, target: Tensor, mask: Tensor, *, mean, std_value, delta: float = 5.0) -> Tensor:
    mean = torch.as_tensor(mean, device=pred.device, dtype=torch.float32)
    std_value = torch.as_tensor(std_value, device=pred.device, dtype=torch.float32)
    diff = (pred.float() - mean) / std_value - (target.float() - mean) / std_value
    absolute = diff.abs()
    delta_value = torch.as_tensor(delta, device=diff.device, dtype=diff.dtype)
    quadratic = torch.minimum(absolute, delta_value)
    return _masked_mean(0.5 * quadratic.square() + delta_value * (absolute - quadratic), mask)


def masked_binary_loss(logits: Tensor, target: Tensor, mask: Tensor) -> Tensor:
    return _masked_mean(F.binary_cross_entropy_with_logits(logits.float(), target.float(), reduction="none"), mask)


def masked_multiclass_loss(logits: Tensor, target: Tensor, mask: Tensor) -> Tensor:
    classes = logits.size(-1)
    losses = F.cross_entropy(
        logits.float().reshape(-1, classes), target.long().clamp(0, classes - 1).reshape(-1), reduction="none"
    )
    flat_mask = mask.float().reshape(-1)
    return (losses * flat_mask).sum() / flat_mask.sum().clamp(min=1.0)


def _graph_attr(batch, name: str, num_graphs: int) -> Tensor | None:
    value = getattr(batch, name, None)
    return value.view(num_graphs, -1) if isinstance(value, Tensor) else None


def _dense_attr(batch, name: str, fill_value=0, dtype=None) -> Tensor | None:
    value = getattr(batch, name, None)
    if not isinstance(value, Tensor):
        return None
    if dtype is not None:
        value = value.to(dtype)
    dense, _ = to_dense_batch(value, batch.batch, fill_value=fill_value)
    return dense


def _sample_types(batch, device: torch.device, num_graphs: int) -> Tensor:
    value = getattr(batch, "sample_type_id", None)
    if not isinstance(value, Tensor):
        return torch.full((num_graphs,), CLEAN, device=device, dtype=torch.long)
    value = value.view(-1).to(device=device, dtype=torch.long)
    return value.expand(num_graphs) if value.numel() == 1 else value[:num_graphs]


def _average_groups(groups: dict[str, list[Tensor]], device: torch.device) -> Tensor:
    means = [torch.stack(values).mean() for values in groups.values() if values]
    return torch.stack(means).mean() if means else torch.zeros((), device=device)


def objectives_for_step(config: SupervisionConfig, schedule: StageSchedule, exposure_step: int):
    return config.objectives_at_descriptor_scale(schedule.descriptor_scale(exposure_step))


def compute_pretrain_loss(
    outputs: PretrainOutputs,
    batch,
    standardizers: Mapping[str, object],
    supervision: SupervisionConfig,
    weights: LossWeights,
    schedule: StageSchedule,
    exposure_step: int,
    graph_descriptor_indices: list[int] | tuple[int, ...] | None = None,
    *,
    phase1_mode: bool = False,
    phase1_policy=None,
) -> LossResult:
    if phase1_mode:
        # A separate explicit path preserves the archived scientific recipe.
        from ..phase1.objectives import compute_phase1_loss

        return compute_phase1_loss(
            outputs, batch, standardizers, supervision, weights, schedule,
            exposure_step, graph_descriptor_indices=graph_descriptor_indices,
            policy=phase1_policy,
        )
    device = outputs.atom_repr.device
    descriptor_scale = schedule.descriptor_scale(exposure_step)
    stage1_scale = schedule.stage1_scale(exposure_step)
    active = supervision.objectives_at_descriptor_scale(descriptor_scale)
    num_graphs = int(batch.num_graphs)
    node_mask = outputs.node_mask.float()
    node_mask_2d = node_mask.squeeze(-1)
    sample_types = _sample_types(batch, device, num_graphs)
    clean_graph = sample_types.eq(CLEAN).float()
    geom_graph = (sample_types.eq(CLEAN) | sample_types.eq(GEOM) | sample_types.eq(BOTH)).float()
    topo_graph = (sample_types.eq(TOPO) | sample_types.eq(BOTH)).float()
    clean_node = node_mask * clean_graph.view(-1, 1, 1)
    topo_node = node_mask * topo_graph.view(-1, 1, 1)
    geom_node = node_mask * geom_graph.view(-1, 1, 1)

    raw: dict[str, Tensor] = {}
    counts: dict[str, int] = {}
    stage1_terms: list[tuple[str, Tensor, float]] = []
    descriptor_terms: list[tuple[str, Tensor, float]] = []

    if Objective.ENERGY in active:
        if outputs.energy_pred is None:
            raise RuntimeError("Energy objective is active but energy_pred is missing")
        target = batch.energy.view(-1, 1).to(device=device, dtype=torch.float32)
        raw["energy"] = standardized_huber(
            outputs.energy_pred, target, clean_graph.view(-1, 1),
            mean=standardizers["muE"], std_value=standardizers["stdE"],
        )
        stage1_terms.append(("energy", raw["energy"], weights.energy))
        counts["energy_graphs"] = int(clean_graph.sum())

    if Objective.CHARGE in active:
        if outputs.charge_pred is None:
            raise RuntimeError("Charge objective is active but charge_pred is missing")
        target, _ = to_dense_batch(batch.y, batch.batch, fill_value=0.0)
        mask = outputs.charge_mask.float() * clean_node
        raw["charge"] = standardized_huber(
            outputs.charge_pred, target.to(device=device, dtype=torch.float32), mask,
            mean=standardizers["muQ"], std_value=standardizers["stdQ"],
        )
        stage1_terms.append(("charge", raw["charge"], weights.charge))
        counts["charge_atoms"] = int(mask.sum())

    if Objective.ELEMENT in active:
        if outputs.element_logits is None:
            raise RuntimeError("Element objective is active but element_logits is missing")
        elem_source = batch.target_x if hasattr(batch, "target_x") else batch.x
        target, _ = to_dense_batch(elem_source[:, 0].long(), batch.batch, fill_value=outputs.element_logits.size(-1) - 1)
        corrupt = _dense_attr(batch, ELEMENT_CORRUPT_MASK_FIELD, fill_value=0, dtype=torch.float32)
        mask = torch.zeros_like(node_mask) if corrupt is None else (corrupt > 0.5).float() * topo_node
        logits = outputs.element_logits.float().reshape(-1, outputs.element_logits.size(-1))
        logits_t = logits / max(1.0, float(weights.element_temperature))
        losses = F.cross_entropy(
            logits_t,
            target.reshape(-1),
            ignore_index=outputs.element_logits.size(-1) - 1,
            reduction="none",
            label_smoothing=weights.element_label_smoothing,
        )
        flat_mask = mask.squeeze(-1).reshape(-1)
        raw["element"] = (losses * flat_mask).sum() / flat_mask.sum().clamp(min=1.0)
        if weights.element_entropy_reg > 0:
            # Preserve the canonical checkpoint's detached diagnostic regularizer exactly.
            with torch.no_grad():
                probabilities = F.softmax(logits_t, dim=-1)
                entropy = -(probabilities * probabilities.clamp_min(1e-12).log()).sum(-1)
            raw["element"] = raw["element"] + float(weights.element_entropy_reg) * (
                (-entropy * flat_mask).sum() / flat_mask.sum().clamp(min=1.0)
            )
        if weights.element_logit_l2 > 0 and flat_mask.bool().any():
            raw["element"] = raw["element"] + float(weights.element_logit_l2) * logits[flat_mask.bool()].square().mean()
        stage1_terms.append(("element", raw["element"], weights.element))
        counts["element_atoms"] = int(flat_mask.sum())

    if Objective.GEOMETRY in active:
        if outputs.coordinate_pred is None:
            raise RuntimeError("Geometry objective is active but coordinate_pred is missing")
        target_pos = batch.target_pos if hasattr(batch, "target_pos") else batch.pos
        target_dense, _ = to_dense_batch(target_pos, batch.batch, fill_value=0.0)
        geom_mask = geom_node.squeeze(-1)
        dist_pred = torch.cdist(outputs.coordinate_pred.float(), outputs.coordinate_pred.float())
        dist_true = torch.cdist(target_dense.float(), target_dense.float())
        pair_mask = geom_mask[:, :, None] * geom_mask[:, None, :]
        morse = morse_energy(dist_pred, dist_true, weights.morse_d, weights.morse_a) * pair_mask
        per_atom = torch.log1p(morse.sum(-1).clamp(min=0.0)) * geom_mask
        raw["distance"] = per_atom.sum() / geom_mask.sum().clamp(min=1.0)
        raw["angle"] = torch.zeros((), device=device)
        raw["torsion"] = torch.zeros((), device=device)
        if (weights.angle > 0 or weights.torsion > 0) and bool(geom_graph.any()):
            _, triplets, quads, _ = build_local_graph(target_pos, batch.batch, weights.cutoff)
            nmax = outputs.coordinate_pred.size(1)
            geom_graph_bool = geom_graph.bool()
            if weights.angle > 0 and triplets.numel():
                i, j, k = triplets.t()
                keep = geom_graph_bool[batch.batch[i]]
                keep &= (target_pos[i] - target_pos[j]).norm(dim=-1) < weights.cutoff
                keep &= (target_pos[j] - target_pos[k]).norm(dim=-1) < weights.cutoff
                if keep.any():
                    selected = triplets[keep]
                    dense_idx = map_global_to_dense_indices(selected, batch.batch, nmax, num_graphs=num_graphs, num_frames=1)
                    raw["angle"] = F.smooth_l1_loss(
                        angle_cos(outputs.coordinate_pred.reshape(-1, 3), dense_idx), angle_cos(target_pos, selected)
                    )
            if weights.torsion > 0 and quads.numel():
                i, j, k, l = quads.t()
                keep = geom_graph_bool[batch.batch[i]]
                keep &= (target_pos[i] - target_pos[j]).norm(dim=-1) < weights.cutoff
                keep &= (target_pos[j] - target_pos[k]).norm(dim=-1) < weights.cutoff
                keep &= (target_pos[k] - target_pos[l]).norm(dim=-1) < weights.cutoff
                if keep.any():
                    selected = quads[keep]
                    dense_idx = map_global_to_dense_indices(selected, batch.batch, nmax, num_graphs=num_graphs, num_frames=1)
                    sp, cp = torsion_sin_cos(outputs.coordinate_pred.reshape(-1, 3), dense_idx)
                    st, ct = torsion_sin_cos(target_pos, selected)
                    raw["torsion"] = F.smooth_l1_loss(sp, st) + F.smooth_l1_loss(cp, ct)
        stage1_terms.extend(
            [
                ("distance", raw["distance"], weights.distance),
                ("angle", raw["angle"], weights.angle),
                ("torsion", raw["torsion"], weights.torsion),
            ]
        )
        counts["geometry_atoms"] = int(geom_mask.sum())

    if Objective.BOND in active:
        if outputs.bond is None:
            raise RuntimeError("Bond objective is active but bond outputs are missing")
        bond = outputs.bond
        if bond.sampled_pair_count > 0:
            raw["bond_existence"] = masked_binary_loss(
                bond.existence, bond.existence_target, torch.ones_like(bond.existence_target)
            )
            raw["bond_order"] = masked_multiclass_loss(
                bond.order, bond.order_target, torch.ones_like(bond.order_target, dtype=torch.float32)
            )
        else:
            raw["bond_existence"] = outputs.atom_repr.new_zeros(())
            raw["bond_order"] = outputs.atom_repr.new_zeros(())
        stage1_terms.extend(
            [
                ("bond_existence", raw["bond_existence"], weights.bond_existence),
                ("bond_order", raw["bond_order"], weights.bond_order),
            ]
        )
        counts["bond_pairs"] = bond.sampled_pair_count

    rdkit_node = _dense_attr(batch, NODE_MASK_FIELD, fill_value=0, dtype=torch.float32)
    rdkit_node = torch.zeros_like(node_mask) if rdkit_node is None else (rdkit_node > 0.5).float() * node_mask
    descriptor_node_mask = rdkit_node * clean_node

    if Objective.GRAPH_DESCRIPTOR in active:
        if outputs.graph_descriptor_pred is None:
            raise RuntimeError("Graph descriptor objective is active but predictions are missing")
        target = _graph_attr(batch, GRAPH_FIELD, num_graphs)
        mask = _graph_attr(batch, GRAPH_MASK_FIELD, num_graphs)
        losses: list[Tensor] = []
        if target is not None and mask is not None:
            indices = torch.tensor(graph_descriptor_indices or (), device=device, dtype=torch.long)
            if indices.numel() == 0:
                indices = torch.arange(outputs.graph_descriptor_pred.size(1), device=device)
            target = target.to(device=device, dtype=torch.float32).index_select(1, indices)
            mask = mask.to(device=device, dtype=torch.float32).index_select(1, indices) * clean_graph.view(-1, 1)
            means = torch.as_tensor(standardizers["graph_desc_mu"], device=device).view(1, -1).index_select(1, indices)
            stds = torch.as_tensor(standardizers["graph_desc_std"], device=device).view(1, -1).index_select(1, indices)
            for idx in range(outputs.graph_descriptor_pred.size(1)):
                losses.append(
                    standardized_huber(
                        outputs.graph_descriptor_pred[:, idx : idx + 1],
                        target[:, idx : idx + 1], mask[:, idx : idx + 1],
                        mean=means[:, idx : idx + 1], std_value=stds[:, idx : idx + 1],
                    )
                )
        raw["graph_descriptor"] = torch.stack(losses).mean() if losses else outputs.atom_repr.new_zeros(())
        descriptor_terms.append(("graph_descriptor", raw["graph_descriptor"], weights.graph_descriptor))
        counts["descriptor_graphs"] = int(clean_graph.sum())

    if Objective.CHARGE_DESCRIPTOR in active:
        groups: dict[str, list[Tensor]] = {"regression": [], "binary": []}
        for spec in CHARGE_DESCRIPTOR_SPECS:
            target = _dense_attr(batch, spec.field_name, fill_value=0)
            if target is None or spec.name not in outputs.charge_descriptor_pred:
                continue
            pred = outputs.charge_descriptor_pred[spec.name]
            if spec.task_type == "regression":
                prefix = "formal_charge" if spec.name == "formal_charge" else "estate_index"
                loss = standardized_huber(
                    pred, target.to(device).float(), descriptor_node_mask,
                    mean=standardizers[f"{prefix}_mu"], std_value=standardizers[f"{prefix}_std"],
                )
            else:
                loss = masked_binary_loss(pred, target.to(device).float(), descriptor_node_mask)
            groups[spec.task_type].append(loss)
        raw["charge_descriptor"] = _average_groups(groups, device)
        descriptor_terms.append(("charge_descriptor", raw["charge_descriptor"], weights.charge_descriptor))

    if Objective.ELEMENT_DESCRIPTOR in active:
        groups = {"binary": [], "multiclass": []}
        for spec in ELEMENT_DESCRIPTOR_SPECS:
            target = _dense_attr(batch, spec.field_name, fill_value=0)
            if target is None or spec.name not in outputs.element_descriptor_pred:
                continue
            pred = outputs.element_descriptor_pred[spec.name]
            if spec.task_type == "binary":
                loss = masked_binary_loss(pred, target.to(device).float(), descriptor_node_mask)
            else:
                loss = masked_multiclass_loss(
                    pred, target.to(device).squeeze(-1).long(), descriptor_node_mask.squeeze(-1)
                )
            groups[spec.task_type].append(loss)
        raw["element_descriptor"] = _average_groups(groups, device)
        descriptor_terms.append(("element_descriptor", raw["element_descriptor"], weights.element_descriptor))

    weighted: dict[str, Tensor] = {}
    selection_terms: list[Tensor] = []
    for name, loss, weight in stage1_terms:
        if weight <= 0:
            continue
        weighted[name] = loss * float(weight) * stage1_scale
        selection_terms.append(weighted[name])
    for name, loss, weight in descriptor_terms:
        if weight <= 0 or descriptor_scale <= 0:
            continue
        weighted[name] = loss * float(weight) * descriptor_scale
        selection_terms.append(weighted[name])

    selection = torch.stack(selection_terms).sum() if selection_terms else outputs.atom_repr.new_zeros(())
    if not torch.isfinite(selection):
        raise FloatingPointError(f"Non-finite pretraining loss at exposure_step={exposure_step}")
    return LossResult(
        total=selection,
        selection=selection,
        raw=raw,
        weighted=weighted,
        counts=counts,
        descriptor_scale=descriptor_scale,
        stage1_scale=stage1_scale,
    )
