from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import torch
from torch import Tensor
from torch_geometric.utils import to_dense_batch

from ..data.descriptor_schema import (
    BOND_ORDER_CLASS_NAMES,
    CHARGE_DESCRIPTOR_SPECS,
    ELEMENT_CORRUPT_MASK_FIELD,
    ELEMENT_DESCRIPTOR_SPECS,
    GRAPH_FIELD,
    GRAPH_MASK_FIELD,
    NODE_MASK_FIELD,
)
from ..model.routes import TaskRouteConfig
from ..model.shared import SharedBackboneMFM
from ..supervision import Objective, SupervisionConfig, normalize_objectives
from .fidelity import TargetFidelityRegistry
from .metrics import binary_metrics, classification_metrics, concat, regression_metrics
from .normalization import TargetTransformRegistry


ADEQUACY_VERSION = "pretraining-target-adequacy-v3.1"
ELEMENT_SYMBOLS = {
    1: "H", 6: "C", 7: "N", 8: "O", 9: "F", 15: "P", 16: "S", 17: "Cl", 35: "Br", 53: "I"
}


def formal_charges_from_smiles(batch, num_graphs: int, device: torch.device) -> tuple[Tensor, Tensor]:
    """Recover formal charge from stored SMILES for diagnostic reporting.

    Legacy ``total_charge`` is normalized to zero when absent, so it is not an
    authoritative formal charge. Values are emitted only for SMILES that RDKit
    can parse from the stored molecular identity.
    """

    from rdkit import Chem

    smiles_values = None
    for field in ("canonical_smiles", "isomeric_smiles", "smiles"):
        values = getattr(batch, field, None)
        if isinstance(values, (list, tuple)) and len(values) >= num_graphs:
            smiles_values = list(values[:num_graphs])
            break
        if isinstance(values, str) and num_graphs == 1:
            smiles_values = [values]
            break
    charges = torch.zeros(num_graphs, dtype=torch.float32, device=device)
    valid = torch.zeros(num_graphs, dtype=torch.bool, device=device)
    if smiles_values is None:
        return charges, valid
    for index, smiles in enumerate(smiles_values):
        if not isinstance(smiles, str) or not smiles.strip():
            continue
        molecule = Chem.MolFromSmiles(smiles)
        if molecule is None:
            continue
        charges[index] = float(sum(atom.GetFormalCharge() for atom in molecule.GetAtoms()))
        valid[index] = True
    return charges, valid


def model_from_checkpoint_payload(payload: Mapping[str, object]) -> SharedBackboneMFM:
    model_config = dict(payload["model_config"])
    return SharedBackboneMFM(
        model_config["backbone_config"],
        task_routes=TaskRouteConfig.from_mapping(model_config["task_route_per_task"]),
        expert_config=model_config.get("expert_config", {}),
        head_config=model_config.get("head_config", {}),
    )


def load_standardizers(payload: Mapping[str, object]) -> dict[str, object]:
    manifest = dict(payload.get("dataset_manifest", {}))
    path = manifest.get("standardizer_cache")
    if path and Path(str(path)).is_file():
        return dict(torch.load(path, map_location="cpu", weights_only=False))
    return {}


def _graph_tensor(batch, name: str, num_graphs: int) -> Tensor | None:
    value = getattr(batch, name, None)
    return value.view(num_graphs, -1) if isinstance(value, Tensor) else None


def _dense_tensor(batch, name: str, fill_value=0) -> Tensor | None:
    value = getattr(batch, name, None)
    if not isinstance(value, Tensor):
        return None
    return to_dense_batch(value, batch.batch, fill_value=fill_value)[0]


@dataclass
class _Parts:
    prediction: list[Tensor]
    target: list[Tensor]

    @classmethod
    def empty(cls) -> "_Parts":
        return cls([], [])

    def add(self, pred: Tensor, target: Tensor, mask: Tensor | None = None) -> None:
        pred, target = pred.detach().float(), target.detach().float()
        if mask is not None:
            valid = mask.detach().bool()
            pred, target = pred[valid], target[valid]
        self.prediction.append(pred.reshape(-1).cpu())
        self.target.append(target.reshape(-1).cpu())

    def tensors(self) -> tuple[Tensor, Tensor]:
        return concat(self.prediction), concat(self.target)


class PretrainingTargetAdequacyEvaluator:
    def __init__(
        self,
        *,
        model: SharedBackboneMFM,
        active_objectives: Iterable[Objective | str],
        standardizers: Mapping[str, object],
        threshold_registry: TargetFidelityRegistry,
        device: torch.device,
        geometry_local_cutoff: float = 2.0,
    ):
        self.model = model.to(device).eval()
        self.active = normalize_objectives(active_objectives)
        self.standardizers = dict(standardizers)
        self.transforms = TargetTransformRegistry(standardizers)
        self.thresholds = threshold_registry
        self.device = device
        self.geometry_local_cutoff = float(geometry_local_cutoff)

    @torch.no_grad()
    def evaluate_loaders(self, clean_loader, *, element_loader=None, max_batches: int | None = None) -> dict[str, object]:
        regression = {name: _Parts.empty() for name in (
            "energy", "charge", "distance_all", "distance_bonded", "distance_local_nonbonded",
            "distance_long", "charge_sum"
        )}
        energy_per_atom = _Parts.empty()
        charge_by_element = {symbol: _Parts.empty() for symbol in ELEMENT_SYMBOLS.values()}
        element_pred: list[Tensor] = []
        element_true: list[Tensor] = []
        bond_score: list[Tensor] = []
        bond_true: list[Tensor] = []
        bond_order_pred: list[Tensor] = []
        bond_order_true: list[Tensor] = []
        graph_parts: dict[str, _Parts] = {name: _Parts.empty() for name in self.model.graph_descriptor_names}
        node_regression: dict[str, _Parts] = {}
        node_classification: dict[str, tuple[list[Tensor], list[Tensor], int]] = {}

        for batch_index, batch in enumerate(clean_loader):
            if max_batches is not None and batch_index >= max_batches:
                break
            batch = batch.to(self.device)
            outputs = self.model.forward_pretrain(batch, self.active)
            num_graphs = int(batch.num_graphs)

            if Objective.ENERGY in self.active and outputs.energy_pred is not None:
                target = batch.energy.view(-1, 1).float()
                pred = self.transforms.inverse_transform_prediction("energy", outputs.energy_pred.float())
                regression["energy"].add(pred, target)
                atom_count = torch.bincount(batch.batch, minlength=num_graphs).view(-1, 1).clamp_min(1)
                energy_per_atom.add((pred - target).abs() / atom_count, torch.zeros_like(target))

            if Objective.CHARGE in self.active and outputs.charge_pred is not None:
                target = to_dense_batch(batch.y.float(), batch.batch, fill_value=0.0)[0]
                mask = outputs.charge_mask.bool()
                pred = self.transforms.inverse_transform_prediction("charge", outputs.charge_pred.float())
                regression["charge"].add(pred, target, mask)
                dense_elements = to_dense_batch(batch.x[:, 0].long(), batch.batch, fill_value=-1)[0]
                for atomic_number, symbol in ELEMENT_SYMBOLS.items():
                    charge_by_element[symbol].add(pred.squeeze(-1), target.squeeze(-1), mask.squeeze(-1) & dense_elements.eq(atomic_number))
                pred_sum = (pred * mask).sum((1, 2))
                formal_target, formal_mask = formal_charges_from_smiles(batch, num_graphs, self.device)
                regression["charge_sum"].add(pred_sum, formal_target, formal_mask)

            if Objective.GEOMETRY in self.active and outputs.coordinate_pred is not None:
                target_pos = batch.target_pos if hasattr(batch, "target_pos") else batch.pos
                target_dense, node_mask = to_dense_batch(target_pos.float(), batch.batch, fill_value=0.0)
                pred_dist = torch.cdist(outputs.coordinate_pred.float(), outputs.coordinate_pred.float())
                true_dist = torch.cdist(target_dense, target_dense)
                nmax = target_dense.size(1)
                upper = torch.triu(torch.ones((nmax, nmax), device=self.device, dtype=torch.bool), diagonal=1)
                valid = node_mask[:, :, None] & node_mask[:, None, :] & upper
                bonded = torch.zeros_like(valid)
                bond_index = getattr(batch, "rdkit_bond_index", None)
                if isinstance(bond_index, Tensor) and bond_index.numel():
                    source, destination = bond_index.long()
                    ptr = torch.cat((batch.batch.new_zeros(1), torch.bincount(batch.batch, minlength=num_graphs).cumsum(0)))
                    graph_ids = batch.batch[source]
                    source_local = source - ptr[graph_ids]
                    destination_local = destination - ptr[graph_ids]
                    bonded[graph_ids, source_local, destination_local] = True
                    bonded[graph_ids, destination_local, source_local] = True
                    bonded &= upper
                local_nonbonded = valid & ~bonded & (true_dist <= self.geometry_local_cutoff)
                long_range = valid & ~bonded & (true_dist > self.geometry_local_cutoff)
                regression["distance_all"].add(pred_dist, true_dist, valid)
                regression["distance_bonded"].add(pred_dist, true_dist, bonded)
                regression["distance_local_nonbonded"].add(pred_dist, true_dist, local_nonbonded)
                regression["distance_long"].add(pred_dist, true_dist, long_range)

            if Objective.BOND in self.active and outputs.bond is not None and outputs.bond.sampled_pair_count:
                bond_score.append(torch.sigmoid(outputs.bond.existence.float()).reshape(-1).cpu())
                bond_true.append(outputs.bond.existence_target.reshape(-1).cpu())
                positive = outputs.bond.existence_target.reshape(-1) > 0.5
                if positive.any():
                    bond_order_pred.append(outputs.bond.order.argmax(-1)[positive].cpu())
                    bond_order_true.append(outputs.bond.order_target[positive].cpu())

            if Objective.GRAPH_DESCRIPTOR in self.active and outputs.graph_descriptor_pred is not None:
                target = _graph_tensor(batch, GRAPH_FIELD, num_graphs)
                mask = _graph_tensor(batch, GRAPH_MASK_FIELD, num_graphs)
                if target is not None and mask is not None:
                    for output_idx, (name, target_idx) in enumerate(
                        zip(self.model.graph_descriptor_names, self.model.graph_descriptor_target_indices)
                    ):
                        graph_parts[name].add(
                            outputs.graph_descriptor_pred[:, output_idx], target[:, target_idx], mask[:, target_idx]
                        )

            node_mask = _dense_tensor(batch, NODE_MASK_FIELD, fill_value=0)
            if node_mask is not None:
                valid_node = node_mask.bool()
                for spec in CHARGE_DESCRIPTOR_SPECS:
                    if Objective.CHARGE_DESCRIPTOR not in self.active or spec.name not in outputs.charge_descriptor_pred:
                        continue
                    target = _dense_tensor(batch, spec.field_name, fill_value=0)
                    if target is None:
                        continue
                    pred = outputs.charge_descriptor_pred[spec.name]
                    if spec.task_type == "regression":
                        node_regression.setdefault(spec.name, _Parts.empty()).add(pred, target, valid_node)
                    else:
                        parts = node_classification.setdefault(spec.name, ([], [], 2))
                        parts[0].append((torch.sigmoid(pred[valid_node]) >= 0.5).long().cpu())
                        parts[1].append(target[valid_node].long().cpu())
                for spec in ELEMENT_DESCRIPTOR_SPECS:
                    if Objective.ELEMENT_DESCRIPTOR not in self.active or spec.name not in outputs.element_descriptor_pred:
                        continue
                    target = _dense_tensor(batch, spec.field_name, fill_value=0)
                    if target is None:
                        continue
                    pred = outputs.element_descriptor_pred[spec.name]
                    parts = node_classification.setdefault(spec.name, ([], [], int(spec.num_classes or 2)))
                    predicted = (torch.sigmoid(pred) >= 0.5).long() if spec.task_type == "binary" else pred.argmax(-1, keepdim=True)
                    parts[0].append(predicted[valid_node].long().cpu())
                    parts[1].append(target[valid_node].long().cpu())

        if Objective.ELEMENT in self.active and element_loader is not None:
            for batch_index, batch in enumerate(element_loader):
                if max_batches is not None and batch_index >= max_batches:
                    break
                batch = batch.to(self.device)
                outputs = self.model.forward_pretrain(batch, (Objective.ELEMENT,))
                target_source = batch.target_x if hasattr(batch, "target_x") else batch.x
                target = to_dense_batch(target_source[:, 0].long(), batch.batch, fill_value=-1)[0]
                corrupt = _dense_tensor(batch, ELEMENT_CORRUPT_MASK_FIELD, fill_value=0)
                mask = outputs.node_mask.squeeze(-1).bool() if corrupt is None else outputs.node_mask.squeeze(-1).bool() & corrupt.squeeze(-1).bool()
                element_pred.append(outputs.element_logits.argmax(-1)[mask].cpu())
                element_true.append(target[mask].cpu())

        return self._build_report(
            regression, energy_per_atom, charge_by_element, element_pred, element_true, bond_score, bond_true,
            bond_order_pred, bond_order_true, graph_parts, node_regression, node_classification,
        )

    def _build_report(
        self, regression, energy_per_atom, charge_by_element, element_pred, element_true, bond_score, bond_true,
        bond_order_pred, bond_order_true, graph_parts, node_regression, node_classification,
    ) -> dict[str, object]:
        metrics: dict[str, dict[str, object]] = {}
        if Objective.ENERGY in self.active:
            metrics["energy"] = regression_metrics(*regression["energy"].tensors())
            metrics["energy"]["unit"] = "kcal/mol"
            metrics["energy"]["absolute_error_per_atom"] = regression_metrics(*energy_per_atom.tensors())
        if Objective.CHARGE in self.active:
            metrics["charge"] = regression_metrics(*regression["charge"].tensors())
            metrics["charge"]["unit"] = "e"
            per_element_mae = {}
            for symbol, parts in charge_by_element.items():
                result = regression_metrics(*parts.tensors())
                if math.isfinite(result["mae"]):
                    per_element_mae[symbol] = result["mae"]
            metrics["charge"]["per_element_mae"] = per_element_mae
            metrics["charge"]["charge_sum_vs_formal_charge"] = regression_metrics(*regression["charge_sum"].tensors())
        if Objective.GEOMETRY in self.active:
            metrics["geometry"] = {
                "unit": "angstrom",
                "all_pairs": regression_metrics(*regression["distance_all"].tensors()),
                "bonded_pairs": regression_metrics(*regression["distance_bonded"].tensors()),
                "local_nonbonded_pairs": regression_metrics(*regression["distance_local_nonbonded"].tensors()),
                "long_range_pairs": regression_metrics(*regression["distance_long"].tensors()),
            }
            local_values = [
                metrics["geometry"]["bonded_pairs"]["mae"],
                metrics["geometry"]["local_nonbonded_pairs"]["mae"],
            ]
            finite_local = [value for value in local_values if math.isfinite(value)]
            metrics["geometry"]["local_pair_mae"] = max(finite_local) if finite_local else math.nan
        if Objective.ELEMENT in self.active:
            result = classification_metrics(concat(element_pred), concat(element_true), self.model.n_atom_types)
            result["per_element_recall"] = {
                ELEMENT_SYMBOLS[z]: result["per_class_recall"][str(z)]
                for z in ELEMENT_SYMBOLS if str(z) in result["per_class_recall"]
            }
            metrics["element"] = result
        if Objective.BOND in self.active:
            existence = binary_metrics(concat(bond_score), concat(bond_true))
            order = classification_metrics(concat(bond_order_pred), concat(bond_order_true), len(BOND_ORDER_CLASS_NAMES))
            order["per_class_recall_named"] = {
                name: order["per_class_recall"].get(str(index), math.nan)
                for index, name in enumerate(BOND_ORDER_CLASS_NAMES)
            }
            metrics["bond"] = {"existence": existence, "order": order, "existence_f1": existence["f1"], "order_macro_f1": order["macro_f1"]}
        if Objective.GRAPH_DESCRIPTOR in self.active:
            per_descriptor = {}
            normalized_mae = []
            stds = torch.as_tensor(self.standardizers.get("graph_desc_std", torch.ones(31))).float()
            for name, target_idx in zip(self.model.graph_descriptor_names, self.model.graph_descriptor_target_indices):
                result = regression_metrics(*graph_parts[name].tensors())
                scale = max(float(stds[target_idx]), 1e-12)
                result["normalized_mae"] = result["mae"] / scale
                result["normalized_rmse"] = result["rmse"] / scale
                normalized_mae.append(result["normalized_mae"])
                per_descriptor[name] = result
            metrics["graph_descriptor"] = {
                "per_descriptor": per_descriptor,
                "mean_normalized_mae": float(sum(normalized_mae) / len(normalized_mae)) if normalized_mae else math.nan,
            }
        if Objective.CHARGE_DESCRIPTOR in self.active:
            metrics["charge_descriptor"] = self._node_descriptor_metrics(node_regression, node_classification, charge_only=True)
        if Objective.ELEMENT_DESCRIPTOR in self.active:
            metrics["element_descriptor"] = self._node_descriptor_metrics(node_regression, node_classification, charge_only=False)

        per_task = {task: self.thresholds.evaluate(task, values) for task, values in metrics.items()}
        active_names = sorted(item.value for item in self.active)
        target_adequate = self.thresholds.active_objectives_adequate(active_names, per_task)
        return {
            "target_adequacy_version": ADEQUACY_VERSION,
            "active_objectives": active_names,
            "normalization_metadata": self.transforms.to_dict(),
            "per_task_metrics": metrics,
            "per_task_fidelity": per_task,
            "target_adequate": target_adequate,
            "target_adequacy_status": "ADEQUATE" if target_adequate else "INADEQUATE",
        }

    def _node_descriptor_metrics(self, regression, classification, *, charge_only: bool) -> dict[str, object]:
        allowed = {spec.name for spec in (CHARGE_DESCRIPTOR_SPECS if charge_only else ELEMENT_DESCRIPTOR_SPECS)}
        per_descriptor: dict[str, object] = {}
        errors = []
        for name, parts in regression.items():
            if name not in allowed:
                continue
            result = regression_metrics(*parts.tensors())
            std_key = "formal_charge_std" if name == "formal_charge" else "estate_index_std"
            result["normalized_mae"] = result["mae"] / max(float(self.standardizers.get(std_key, 1.0)), 1e-12)
            errors.append(result["normalized_mae"])
            per_descriptor[name] = result
        for name, (pred_parts, true_parts, classes) in classification.items():
            if name not in allowed:
                continue
            result = classification_metrics(concat(pred_parts), concat(true_parts), classes)
            result["classification_error"] = 1.0 - result["macro_f1"]
            errors.append(result["classification_error"])
            per_descriptor[name] = result
        return {"per_descriptor": per_descriptor, "worst_group_error": max(errors) if errors else math.nan}


def write_adequacy_report(report: Mapping[str, object], output_json: str | Path, output_csv: str | Path) -> None:
    output_json = Path(output_json)
    output_csv = Path(output_csv)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    rows = []
    for task, task_report in report.get("per_task_fidelity", {}).items():
        for item in task_report.get("metrics", []):
            rows.append({
                "task": task, "metric": item["metric"], "value": item["value"], "unit": item["unit"],
                "fidelity_level": item["fidelity_level"], "pass": item["pass"],
                "threshold_source": item["threshold"]["source"],
                "threshold_source_type": item["threshold"]["source_type"],
            })
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["task", "metric"])
        writer.writeheader()
        writer.writerows(rows)
