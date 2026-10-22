"""Phase 1 supervision with fixed within-group and between-group denominators.

Legacy schedules and losses remain in ``training.losses``. Predictions are in
target units; standard deviations scale residuals only. A target with zero valid
labels contributes detached zero, is counted as missing, and does not create a
gradient for its head. Its fixed task weight still remains in the denominator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Mapping

import torch
import torch.nn.functional as F
from torch import Tensor
from torch_geometric.utils import to_dense_batch

from ..data.descriptor_schema import (
    ELEMENT_CORRUPT_MASK_FIELD, GRAPH_DESCRIPTOR_NAMES, GRAPH_FIELD,
    GRAPH_MASK_FIELD, NODE_MASK_FIELD,
)
from ..model.phase1_specs import (
    PHASE1_BOND_ORDER_NUM_CLASSES, PHASE1_CHARGE_DESCRIPTOR_SPECS,
    PHASE1_ELEMENT_DESCRIPTOR_SPECS, PHASE1_GRAPH_DESCRIPTOR_NAMES,
)
from ..supervision import Objective, SupervisionConfig
from ..training.data import SAMPLE_TYPE_TO_ID
from ..training.geometry import morse_energy


PHASE1_VARIANTS = ("none", "S", "D", "P", "SD", "SP", "DP", "SDP")
STRUCTURAL_TASKS = ("element", "distance", "bond_order")
PHYSICS_TASKS = ("energy", "charge")
DESCRIPTOR_TASKS = tuple(f"graph_descriptor/{name}" for name in PHASE1_GRAPH_DESCRIPTOR_NAMES) + tuple(
    f"node_descriptor/{spec.name}" for spec in PHASE1_CHARGE_DESCRIPTOR_SPECS + PHASE1_ELEMENT_DESCRIPTOR_SPECS
)
GROUP_TASKS = {"S": STRUCTURAL_TASKS, "D": DESCRIPTOR_TASKS, "P": PHYSICS_TASKS}


@dataclass(frozen=True)
class Phase1JointSchedule:
    """All enabled tasks receive full supervision starting at exposure zero."""

    name: str = "phase1_joint_v1"

    def descriptor_scale(self, exposure_step: int) -> float:
        if exposure_step < 0:
            raise ValueError("exposure_step cannot be negative")
        return 1.0

    def stage1_scale(self, exposure_step: int) -> float:
        if exposure_step < 0:
            raise ValueError("exposure_step cannot be negative")
        return 1.0

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "descriptor_scale": 1.0, "stage1_scale": 1.0, "index_unit": "structure_exposure"}


def canonical_variant(value: str) -> str:
    return SupervisionConfig.from_variant(value).variant.canonical_value


@dataclass(frozen=True)
class Phase1LossPolicy:
    group_weights: Mapping[str, float] = field(default_factory=lambda: {"S": 1.0, "D": 1.0, "P": 1.0})
    task_weights: Mapping[str, float] = field(default_factory=lambda: {
        name: 1.0 for tasks in GROUP_TASKS.values() for name in tasks
    })
    # Preserve both original positional arguments. New options are keyword-only.
    geometry_task: str = field(default="distance", kw_only=True)
    structural_tasks: tuple[str, ...] | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        expected_tasks = {name for tasks in GROUP_TASKS.values() for name in tasks}
        if self.geometry_task not in {"distance", "denoise_eps_mse"}:
            raise ValueError("Unknown geometry task")
        if self.geometry_task == "denoise_eps_mse":
            expected_tasks.add("denoise_eps_mse")
        available = {"element", self.geometry_task, "bond_order"}
        if self.structural_tasks is not None and (not self.structural_tasks or
                len(set(self.structural_tasks)) != len(self.structural_tasks) or
                not set(self.structural_tasks) <= available):
            raise ValueError("Invalid explicit structural task selection")
        if set(self.group_weights) != set(GROUP_TASKS) or set(self.task_weights) != expected_tasks:
            raise ValueError("Phase1LossPolicy must define exactly all Phase 1 groups and retained tasks")
        for name, weight in list(self.group_weights.items()) + list(self.task_weights.items()):
            if not math.isfinite(float(weight)) or float(weight) <= 0:
                raise ValueError(f"Phase 1 enabled weights must be finite and strictly positive: {name}={weight}")

    @classmethod
    def from_mapping(cls, values: Mapping[str, object]) -> "Phase1LossPolicy":
        defaults = cls()
        geometry_task = str(values.get("geometry_task", "distance"))
        task_defaults = dict(defaults.task_weights)
        if geometry_task == "denoise_eps_mse":
            task_defaults["denoise_eps_mse"] = 1.0
        return cls(
            geometry_task=geometry_task,
            structural_tasks=tuple(values["structural_tasks"]) if values.get("structural_tasks") is not None else None,
            group_weights={**defaults.group_weights, **dict(values.get("group_weights", {}))},
            task_weights={**task_defaults, **dict(values.get("task_weights", {}))},
        )

    def to_dict(self) -> dict[str, object]:
        return {
            **({"geometry_task": self.geometry_task, "structural_tasks": self.structural_tasks}
               if self.geometry_task != "distance" or self.structural_tasks is not None else {}),
            "version": "phase1_loss_policy_v1",
            "group_weights": dict(self.group_weights), "task_weights": dict(self.task_weights),
            "normalization": "valid_labels_mean_then_fixed_task_weight_mean_then_enabled_group_weight_mean",
            "missing_task_rule": "detached_zero_with_fixed_denominator_and_explicit_zero_count",
            "charge_target": "MOPAC NET ATOMIC CHARGES",
        }


def step_runtime_metrics(optimizer, *, lr_used: float, exposure_step: int, optimizer_update_step: int) -> dict[str, float]:
    """Capture LR before the update; ``lr_next`` is read after scheduler.step()."""
    return {
        "train/lr_used": float(lr_used), "train/lr_next": float(optimizer.param_groups[0]["lr"]),
        "train/exposure_step": float(exposure_step),
        "train/optimizer_update_step": float(optimizer_update_step),
    }


def _dense(batch, name: str, *, device, fill_value=0):
    value = getattr(batch, name, None)
    if not isinstance(value, Tensor):
        return None
    return to_dense_batch(value.to(device), batch.batch.to(device), fill_value=fill_value)[0]


def _graph(batch, name: str, *, graphs: int, device):
    value = getattr(batch, name, None)
    return value.to(device).view(graphs, -1) if isinstance(value, Tensor) else None


def _regression(pred: Tensor, target: Tensor, mask: Tensor, std_value) -> Tensor:
    # Index before arithmetic: masked NaN labels must never leak through NaN*0.
    scale = torch.as_tensor(std_value, device=pred.device, dtype=torch.float32)
    if not bool(torch.isfinite(scale).all()) or not bool((scale > 0).all()):
        raise ValueError("Training standard deviations must be finite and positive")
    residual = (pred.float()[mask] - target.float()[mask]) / scale
    absolute = residual.abs()
    quadratic = absolute.clamp(max=5.0)
    return (0.5 * quadratic.square() + 5.0 * (absolute - quadratic)).mean()


def denoise_eps_mse(predicted_noise: Tensor, noisy_pos: Tensor, target_pos: Tensor,
                    atom_mask: Tensor, *, sigma: float = 0.1,
                    geom_angle_std_deg: float = 0.0, geom_bond_scale_std: float = 0.0) -> Tensor:
    """Mean squared vector error / (3 sigma²), on explicitly selected atoms."""
    if geom_angle_std_deg != 0 or geom_bond_scale_std != 0:
        raise ValueError("denoise_eps_mse requires additive Gaussian noise only")
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("A finite positive Gaussian sigma is required")
    if predicted_noise.shape != noisy_pos.shape or noisy_pos.shape != target_pos.shape or noisy_pos.size(-1) != 3:
        raise ValueError("Noise and coordinate shapes differ")
    mask = atom_mask.bool() & torch.isfinite(noisy_pos).all(-1) & torch.isfinite(target_pos).all(-1)
    if not bool(mask.any()):
        return predicted_noise.new_zeros(())
    residual = predicted_noise[mask].float() - (noisy_pos[mask].float() - target_pos[mask].float())
    return residual.square().sum(-1).mean() / (3.0 * sigma ** 2)


def compute_phase1_loss(
    outputs, batch, standardizers, supervision: SupervisionConfig, weights, schedule, exposure_step: int,
    *, graph_descriptor_indices=None, policy: Phase1LossPolicy | Mapping[str, object] | None = None,
):
    # Import here to avoid a cycle through the public legacy-compatible wrapper.
    from ..training.losses import LossResult

    if policy is None:
        policy = Phase1LossPolicy()
    elif isinstance(policy, Mapping):
        policy = Phase1LossPolicy.from_mapping(policy)
    if not isinstance(policy, Phase1LossPolicy):
        raise TypeError("phase1_policy must be a Phase1LossPolicy or mapping")
    if weights.angle != 0 or weights.torsion != 0:
        raise ValueError("Phase 1 keeps the existing distance objective; angle/torsion are not enabled")
    schedule = schedule or Phase1JointSchedule()
    descriptor_scale = float(schedule.descriptor_scale(exposure_step))
    stage1_scale = float(schedule.stage1_scale(exposure_step))
    if not math.isfinite(descriptor_scale) or not math.isfinite(stage1_scale):
        raise ValueError("Phase 1 schedule scales must be finite")
    if supervision.descriptor and descriptor_scale <= 0:
        raise ValueError("Phase 1 descriptors must receive positive supervision from step zero")
    if (supervision.structural or supervision.physics) and stage1_scale <= 0:
        raise ValueError("Phase 1 enabled S/P objectives must receive positive supervision")
    if (supervision.descriptor and descriptor_scale != 1.0) or (
        (supervision.structural or supervision.physics) and stage1_scale != 1.0
    ):
        raise ValueError("Phase 1 joint supervision requires fixed full-strength group scales of 1.0")
    active = supervision.objectives
    device = outputs.atom_repr.device
    zero = outputs.atom_repr.new_zeros((), dtype=torch.float32)
    graphs = int(batch.num_graphs)
    sample_types = _graph(batch, "sample_type_id", graphs=graphs, device=device)
    if sample_types is None or sample_types.numel() != graphs:
        raise ValueError("Phase 1 requires one explicit sample_type_id per graph")
    if not bool((torch.isfinite(sample_types) & sample_types.eq(sample_types.float().floor())).all()):
        raise ValueError("Phase 1 sample_type_id must contain finite integer view identifiers")
    sample_types = sample_types.reshape(-1).long()
    valid_view_ids = tuple(SAMPLE_TYPE_TO_ID.values())
    if not bool(torch.isin(sample_types, sample_types.new_tensor(valid_view_ids)).all()):
        raise ValueError("Phase 1 sample_type_id contains an unknown input view")
    clean_graph = sample_types.eq(SAMPLE_TYPE_TO_ID["clean"])
    geom_graph = sample_types.eq(SAMPLE_TYPE_TO_ID["geom"]) | sample_types.eq(SAMPLE_TYPE_TO_ID["both"])
    topo_graph = sample_types.eq(SAMPLE_TYPE_TO_ID["topo"]) | sample_types.eq(SAMPLE_TYPE_TO_ID["both"])
    counts = {"graphs": graphs, "atoms": int(batch.x.size(0))}
    counts.update({f"view/{name}": int(sample_types.eq(view_id).sum()) for name, view_id in SAMPLE_TYPE_TO_ID.items()})
    enabled_groups = [group for group, enabled in (("S", supervision.structural), ("D", supervision.descriptor), ("P", supervision.physics)) if enabled]
    if not enabled_groups:
        return LossResult(zero, zero, counts=counts, descriptor_scale=descriptor_scale, stage1_scale=stage1_scale)
    if outputs.node_mask is None:
        raise ValueError("Phase 1 outputs require node_mask")
    node_mask = outputs.node_mask.to(device).bool()
    if node_mask.ndim == 2:
        node_mask = node_mask.unsqueeze(-1)
    clean_node = node_mask & clean_graph.view(-1, 1, 1)
    raw: dict[str, Tensor] = {}
    valid_tasks: list[str] = []

    def add_task(name: str, pred, target, mask, *, kind: str, scale=None, smoothing=0.0):
        if pred is None:
            raise RuntimeError(f"Enabled Phase 1 target has no prediction head: {name}")
        if target is None:
            counts[name] = 0
            raw[name] = zero
            return
        target = target.to(device)
        mask = mask.to(device).bool() & torch.isfinite(target)
        if kind == "binary":
            mask &= target.eq(0) | target.eq(1)
        elif kind == "multiclass":
            mask &= target.eq(target.float().floor()) & target.ge(0) & target.lt(pred.size(-1))
        counts[name] = int(mask.sum())
        if counts[name] == 0:
            raw[name] = zero
            return
        valid_tasks.append(name)
        if kind == "regression":
            raw[name] = _regression(pred, target, mask, scale)
        elif kind == "binary":
            raw[name] = F.binary_cross_entropy_with_logits(pred.float()[mask], target.float()[mask])
        else:
            raw[name] = F.cross_entropy(pred.float()[mask], target[mask].long(), label_smoothing=float(smoothing))

    if Objective.ENERGY in active:
        target = _graph(batch, "energy", graphs=graphs, device=device)
        energy_mask = _graph(batch, "energy_mask", graphs=graphs, device=device)
        valid_energy = torch.zeros((graphs, 1), device=device, dtype=torch.bool) if energy_mask is None else (
            torch.isfinite(energy_mask) & energy_mask.eq(1)
        )
        add_task("energy", outputs.energy_pred, target, clean_graph.view(-1, 1) & valid_energy,
                 kind="regression", scale=standardizers["stdE"])
    if Objective.CHARGE in active:
        charge_mask = outputs.charge_mask.to(device).bool() if outputs.charge_mask is not None else torch.zeros_like(node_mask)
        add_task("charge", outputs.charge_pred, _dense(batch, "y", device=device), clean_node & charge_mask,
                 kind="regression", scale=standardizers["stdQ"])
    if Objective.ELEMENT in active:
        corrupt = _dense(batch, ELEMENT_CORRUPT_MASK_FIELD, device=device)
        mask = torch.zeros_like(node_mask) if corrupt is None else node_mask & topo_graph.view(-1, 1, 1) & corrupt.gt(0.5)
        element_source = "target_x" if isinstance(getattr(batch, "target_x", None), Tensor) else "x"
        target = _dense(batch, element_source, device=device)
        target = target[:, :, 0] if target is not None else None
        logits = outputs.element_logits
        if logits is None:
            raise RuntimeError("Enabled Phase 1 element objective has no head")
        # Padding is a reserved class, not a recoverable element.
        if target is not None:
            legal_element = torch.isfinite(target) & target.eq(target.float().floor()) & target.ge(0) & target.lt(logits.size(-1) - 1)
            mask = mask & legal_element.unsqueeze(-1)
        add_task("element", logits / max(1.0, float(weights.element_temperature)), target, mask.squeeze(-1),
                 kind="multiclass", smoothing=weights.element_label_smoothing)
        if counts["element"] > 0:
            selected = logits[mask.squeeze(-1)]
            if weights.element_entropy_reg > 0:
                with torch.no_grad():
                    probabilities = F.softmax(selected.float() / max(1.0, float(weights.element_temperature)), dim=-1)
                    entropy = -(probabilities * probabilities.clamp_min(1e-12).log()).sum(-1).mean()
                raw["element"] = raw["element"] - float(weights.element_entropy_reg) * entropy
            if weights.element_logit_l2 > 0:
                raw["element"] = raw["element"] + float(weights.element_logit_l2) * selected.float().square().mean()
    if Objective.GEOMETRY in active:
        if outputs.coordinate_pred is None:
            raise RuntimeError("Enabled Phase 1 geometry objective has no head")
        target = _dense(batch, "target_pos", device=device)
        if target is None:
            raise ValueError("Phase 1 geometry requires an explicit clean target_pos")
        valid_node = node_mask.squeeze(-1) & torch.isfinite(target).all(-1) & geom_graph.view(-1, 1)
        per_atom_terms = []
        distance_atoms = distance_pairs = 0
        for graph_index in range(graphs):
            keep = valid_node[graph_index]
            atom_count = int(keep.sum())
            if atom_count < 2:
                continue
            coordinate_prediction = outputs.coordinate_pred if policy.geometry_task == "distance" else outputs.coordinate_pred.detach()
            predicted = coordinate_prediction[graph_index, keep].float()
            expected = target[graph_index, keep].float()
            morse = morse_energy(torch.cdist(predicted, predicted), torch.cdist(expected, expected), weights.morse_d, weights.morse_a)
            per_atom_terms.append(torch.log1p(morse.sum(-1).clamp(min=0.0)))
            distance_atoms += atom_count
            distance_pairs += atom_count * (atom_count - 1) // 2
        counts["distance"] = distance_atoms
        counts["distance_pairs"] = distance_pairs
        raw["distance"] = torch.cat(per_atom_terms).mean() if per_atom_terms else zero
        if distance_atoms:
            valid_tasks.append("distance")
        if policy.geometry_task == "denoise_eps_mse":
            if outputs.noise_pred is None:
                raise RuntimeError("denoise_eps_mse requires an explicit equivariant noise prediction")
            noisy = _dense(batch, "pos", device=device)
            raw["denoise_eps_mse"] = denoise_eps_mse(
                outputs.noise_pred, noisy, target, valid_node,
                sigma=weights.denoise_sigma, geom_angle_std_deg=weights.geom_angle_std_deg,
                geom_bond_scale_std=weights.geom_bond_scale_std,
            )
            counts["denoise_eps_mse"] = int(valid_node.sum())
            if counts["denoise_eps_mse"]:
                valid_tasks.append("denoise_eps_mse")
    if Objective.BOND in active:
        bond = outputs.bond
        if bond is None:
            raise RuntimeError("Enabled Phase 1 bond-order objective has no head")
        if bond.order.size(-1) != PHASE1_BOND_ORDER_NUM_CLASSES or bond.existence.numel() != 0:
            raise ValueError("Phase 1 requires positive-only five-class bond order and no existence logits")
        if bond.existence_target.numel() and not bool(bond.existence_target.eq(1).all()):
            raise ValueError("Phase 1 bond metadata contains non-positive pairs")
        keep = clean_graph[bond.pair_graph_index.long()] if bond.pair_graph_index.numel() else torch.zeros(0, device=device, dtype=torch.bool)
        add_task("bond_order", bond.order, bond.order_target, keep, kind="multiclass")

    if supervision.descriptor:
        rdkit_node = _dense(batch, NODE_MASK_FIELD, device=device)
        descriptor_node = torch.zeros_like(node_mask) if rdkit_node is None else clean_node & rdkit_node.gt(0.5)
        allowed_charge = {spec.name for spec in PHASE1_CHARGE_DESCRIPTOR_SPECS}
        allowed_element = {spec.name for spec in PHASE1_ELEMENT_DESCRIPTOR_SPECS}
        if set(outputs.charge_descriptor_pred) != allowed_charge or set(outputs.element_descriptor_pred) != allowed_element:
            raise ValueError("Phase 1 descriptor predictions must contain exactly the six retained node heads")
        if outputs.graph_descriptor_pred is None or outputs.graph_descriptor_pred.size(-1) != len(PHASE1_GRAPH_DESCRIPTOR_NAMES):
            raise ValueError("Phase 1 requires exactly the 23 retained graph descriptor heads")
        graph_predictions = getattr(outputs, "graph_descriptor_by_name", {})
        if set(graph_predictions) != set(PHASE1_GRAPH_DESCRIPTOR_NAMES):
            raise ValueError("Phase 1 requires independent graph_descriptor_by_name predictions to avoid missing-head drift")
        expected_indices = tuple(GRAPH_DESCRIPTOR_NAMES.index(name) for name in PHASE1_GRAPH_DESCRIPTOR_NAMES)
        indices = expected_indices if graph_descriptor_indices is None else tuple(int(index) for index in graph_descriptor_indices)
        if indices != expected_indices:
            raise ValueError("Phase 1 graph descriptor target indices do not match the frozen retained targets")
        graph_target = _graph(batch, GRAPH_FIELD, graphs=graphs, device=device)
        graph_mask = _graph(batch, GRAPH_MASK_FIELD, graphs=graphs, device=device)
        graph_stds = torch.as_tensor(standardizers["graph_desc_std"], device=device).reshape(-1)
        for name, target_index in zip(PHASE1_GRAPH_DESCRIPTOR_NAMES, indices):
            target = graph_target[:, target_index:target_index + 1] if graph_target is not None else None
            mask = clean_graph.view(-1, 1) & graph_mask[:, target_index:target_index + 1].gt(0.5) if graph_mask is not None else torch.zeros((graphs, 1), device=device, dtype=torch.bool)
            add_task(f"graph_descriptor/{name}", graph_predictions[name], target, mask,
                     kind="regression", scale=graph_stds[target_index])
        for specs, predictions in ((PHASE1_CHARGE_DESCRIPTOR_SPECS, outputs.charge_descriptor_pred),
                                   (PHASE1_ELEMENT_DESCRIPTOR_SPECS, outputs.element_descriptor_pred)):
            for spec in specs:
                target = _dense(batch, spec.field_name, device=device)
                pred = predictions[spec.name]
                if spec.task_type == "regression":
                    add_task(f"node_descriptor/{spec.name}", pred, target, descriptor_node,
                             kind="regression", scale=standardizers["estate_index_std"])
                elif spec.task_type == "binary":
                    add_task(f"node_descriptor/{spec.name}", pred, target, descriptor_node, kind="binary")
                else:
                    add_task(f"node_descriptor/{spec.name}", pred, target.squeeze(-1) if target is not None else None,
                             descriptor_node.squeeze(-1), kind="multiclass")

    group_losses = {}
    group_weights = {}
    task_weights = {}
    weighted = {}
    enabled_group_denominator = sum(float(policy.group_weights[group]) for group in enabled_groups)
    for group in enabled_groups:
        tasks = GROUP_TASKS[group]
        if group == "S" and (policy.geometry_task != "distance" or policy.structural_tasks is not None):
            tasks = policy.structural_tasks or ("element", policy.geometry_task, "bond_order")
        task_denominator = sum(float(policy.task_weights[name]) for name in tasks)
        group_scale = descriptor_scale if group == "D" else stage1_scale
        group_weights[group] = float(policy.group_weights[group]) * group_scale
        terms = []
        for name in tasks:
            raw.setdefault(name, zero)
            counts.setdefault(name, 0)
            within_weight = float(policy.task_weights[name]) / task_denominator
            effective_weight = within_weight * group_weights[group] / enabled_group_denominator
            task_weights[name] = effective_weight
            weighted[name] = raw[name] * effective_weight
            terms.append(raw[name] * within_weight)
        group_losses[group] = torch.stack(terms).sum()
        counts[f"valid_tasks/{group}"] = sum(counts[name] > 0 for name in tasks)
        counts[f"missing_tasks/{group}"] = sum(counts[name] == 0 for name in tasks)
    total = torch.stack(list(weighted.values())).sum()
    if not bool(torch.isfinite(total)):
        raise FloatingPointError(f"Non-finite Phase 1 loss at exposure_step={exposure_step}")
    return LossResult(
        total=total, selection=total, raw=raw, weighted=weighted, counts=counts,
        descriptor_scale=descriptor_scale, stage1_scale=stage1_scale,
        groups=group_losses, group_weights=group_weights, task_weights=task_weights,
        valid_tasks=tuple(valid_tasks), missing_tasks=tuple(name for name in raw if counts[name] == 0),
    )
