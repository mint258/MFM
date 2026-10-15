"""Train-fitted controls in original label units; no fixed adequacy thresholds."""
from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from typing import Iterable, Mapping

import numpy as np
import torch

from ..data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES, CHARGE_DESCRIPTOR_SPECS, ELEMENT_DESCRIPTOR_SPECS


def values(record, name):
    value = getattr(record, name, None)
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy().reshape(-1)
    if isinstance(value, (int, float, np.number, np.ndarray)):
        return np.asarray(value).reshape(-1)
    return None


def valid_values(record, name, mask_name):
    target = values(record, name)
    if target is None:
        return np.empty(0)
    mask = values(record, mask_name)
    if mask is None or len(mask) != len(target):
        return np.empty(0)
    return target[np.isfinite(target) & (mask > .5)]


@dataclass
class TrainingBaselines:
    n_atom_types: int = 95
    energy_coefficients: np.ndarray | None = None
    charge_means: np.ndarray | None = None
    charge_counts: np.ndarray | None = None
    charge_global_mean: float = 0.
    element_majority: int = 0
    bond_majority: int = 1
    graph_means: dict[str, float] = field(default_factory=dict)
    node_predictions: dict[str, float] = field(default_factory=dict)
    provenance: dict = field(default_factory=dict)

    def atom_counts(self, record):
        atoms = values(record, "x")
        if atoms is None:
            raise ValueError("Missing element input")
        # x may contain additional columns; only column zero enters H0.
        atoms = record.x[:, 0].detach().cpu().numpy().astype(int)
        if np.any((atoms < 0) | (atoms >= self.n_atom_types)):
            raise ValueError("Element encoding outside frozen Z-1 vocabulary")
        return np.r_[np.bincount(atoms, minlength=self.n_atom_types), 1.].astype(np.float64)

    def fit(self, records: Iterable, *, train_manifest: Mapping, element_records: Iterable | None = None):
        if train_manifest.get("role") != "train":
            raise ValueError("Baselines must be fit exclusively on a declared training manifest")
        design, energies, graph = [], [], {name: [] for name in GRAPH_DESCRIPTOR_NAMES}
        charges = [[] for _ in range(self.n_atom_types)]
        elements, bonds = Counter(), Counter()
        specs = {spec.name: spec for spec in (*CHARGE_DESCRIPTOR_SPECS, *ELEMENT_DESCRIPTOR_SPECS)}
        nodes = {name: [] for name in ("donor", "acceptor", "estate_index", "is_aromatic", "is_in_ring", "min_ring_size")}
        record_count = 0
        for record in records:
            record_count += 1
            counts = self.atom_counts(record)
            atoms = record.x[:, 0].detach().cpu().numpy().astype(int)
            elements.update(atoms.tolist())
            energy = values(record, "energy")
            energy_mask = values(record, "energy_mask")
            if energy is not None and len(energy) == 1 and np.isfinite(energy[0]) and energy_mask is not None and energy_mask[0] > .5:
                design.append(counts)
                energies.append(energy[0])
            charge = values(record, "y")
            charge_mask = values(record, "charge_mask")
            if charge is not None and charge_mask is not None and len(charge) == len(atoms) == len(charge_mask):
                for atom, target, mask in zip(atoms, charge, charge_mask):
                    if mask > .5 and np.isfinite(target):
                        charges[atom].append(float(target))
            desc = values(record, "rdkit_graph_desc")
            desc_mask = values(record, "rdkit_graph_desc_mask")
            if desc is not None and desc_mask is not None and len(desc) == len(desc_mask) == len(GRAPH_DESCRIPTOR_NAMES):
                for name, target, mask in zip(GRAPH_DESCRIPTOR_NAMES, desc, desc_mask):
                    if mask > .5 and np.isfinite(target):
                        graph[name].append(float(target))
            for name in nodes:
                observed = valid_values(record, specs[name].field_name, "rdkit_node_mask")
                if specs[name].task_type == "binary":
                    observed = observed[np.isin(observed, [0, 1])]
                elif specs[name].task_type == "multiclass":
                    observed = observed[(observed == np.floor(observed)) & (observed >= 0) & (observed < specs[name].num_classes)]
                nodes[name].extend(observed.tolist())
            orders = values(record, "rdkit_bond_order")
            if orders is not None:
                bonds.update(int(value) for value in orders if np.isfinite(value) and 1 <= value <= 5)
        if not record_count or not design:
            raise ValueError("No valid training records/energy labels for the requested baselines")
        self.energy_coefficients = np.linalg.lstsq(np.stack(design), np.asarray(energies), rcond=None)[0]
        all_charges = [value for group in charges for value in group]
        if not all_charges:
            raise ValueError("No valid training NET ATOMIC CHARGES")
        self.charge_global_mean = float(np.mean(all_charges))
        self.charge_counts = np.asarray([len(group) for group in charges])
        self.charge_means = np.asarray([np.mean(group) if group else self.charge_global_mean for group in charges])
        self.element_majority = elements.most_common(1)[0][0]
        element_provenance = {"element_majority_source": "legacy_clean_all_atoms_compatibility_only",
                              "element_fit_labels": sum(elements.values()), "element_fit_view_records": record_count,
                              "element_rejected_corrupted_targets": 0}
        if element_records is not None:
            observed = Counter()
            view_count = rejected = 0
            for record in element_records:
                view_count += 1
                target = getattr(record, "target_x", None)
                source = getattr(record, "x", None)
                mask = values(record, "element_corrupt_mask")
                view = values(record, "sample_type_id")
                if (not isinstance(target, torch.Tensor) or not isinstance(source, torch.Tensor)
                        or target.ndim != 2 or source.ndim != 2 or target.shape != source.shape
                        or target.size(1) != 1 or mask is None or len(mask) != target.size(0)
                        or not np.isfinite(mask).all() or view is None or len(view) != 1 or view[0] not in (2, 3)):
                    raise ValueError("Element baseline requires explicit training topology views, aligned target_x and corruption masks")
                changed = source.ne(target).any(dim=1).detach().cpu().numpy()
                corrupted = mask > .5
                if not np.array_equal(changed, corrupted):
                    raise ValueError("Element baseline corruption mask does not match actual input changes")
                targets = target[:, 0].detach().cpu().numpy()
                legal = (np.isfinite(targets) & (targets == np.floor(targets))
                         & (targets >= 0) & (targets < self.n_atom_types - 1))
                rejected += int((corrupted & ~legal).sum())
                observed.update(targets[corrupted & legal].astype(int).tolist())
            if not observed:
                raise ValueError("Training topology views have no legal actually corrupted element targets for the baseline")
            self.element_majority = min(observed, key=lambda label: (-observed[label], label))
            element_provenance = {"element_majority_source": "train_topology_actual_corrupted_target_x",
                                  "element_fit_labels": sum(observed.values()), "element_fit_view_records": view_count,
                                  "element_rejected_corrupted_targets": rejected,
                                  "element_class_counts": {str(label): count for label, count in sorted(observed.items())},
                                  "element_tie_break": "smallest_class_id"}
        self.bond_majority = bonds.most_common(1)[0][0] if bonds else 1
        self.graph_means = {name: float(np.mean(group)) for name, group in graph.items() if group}
        self.node_predictions = {name: float(np.mean(group)) if name == "estate_index" else Counter(group).most_common(1)[0][0]
                                 for name, group in nodes.items() if group}
        self.provenance = {"train_manifest": dict(train_manifest), "fit_records": record_count,
                           **element_provenance,
                           "energy_fit_labels": len(energies), "charge_fit_labels": len(all_charges),
                           "energy_method": "ordinary least squares on Z-1 element counts plus intercept",
                           "unseen_charge_element": "training global mean; report unseen validation count",
                           "geometry_control": "noisy input coordinates, unchanged"}
        return self

    def energy(self, record):
        return float(self.atom_counts(record) @ self.energy_coefficients)

    def to_dict(self):
        return {"provenance": self.provenance, "energy_coefficients": self.energy_coefficients.tolist(),
                "charge_means": self.charge_means.tolist(), "charge_counts": self.charge_counts.tolist(),
                "element_majority": self.element_majority, "bond_majority": self.bond_majority,
                "graph_means": self.graph_means, "node_predictions": self.node_predictions}


class RegressionMeter:
    def __init__(self):
        self.count = 0
        self.absolute = self.squared = 0.

    def add(self, prediction, target):
        diff = np.asarray(prediction, dtype=float) - np.asarray(target, dtype=float)
        if not np.all(np.isfinite(diff)):
            raise ValueError("Non-finite prediction/target in evaluation")
        self.count += diff.size
        self.absolute += float(np.abs(diff).sum())
        self.squared += float(np.square(diff).sum())

    def result(self):
        return {"count": self.count, "mae": self.absolute / self.count if self.count else None,
                "rmse": np.sqrt(self.squared / self.count) if self.count else None}


class ClassificationMeter:
    def __init__(self, classes):
        self.confusion = np.zeros((classes, classes), dtype=np.int64)

    def add(self, prediction, target):
        prediction, target = np.asarray(prediction).astype(int).ravel(), np.asarray(target).astype(int).ravel()
        classes = len(self.confusion)
        if len(prediction) != len(target) or np.any((target < 0) | (target >= classes) | (prediction < 0) | (prediction >= classes)):
            raise ValueError("Invalid unmasked classification labels/predictions")
        np.add.at(self.confusion, (target, prediction), 1)

    def result(self):
        tp = np.diag(self.confusion)
        support = self.confusion.sum(1)
        denom = support + self.confusion.sum(0)
        active = support > 0
        f1 = np.divide(2 * tp, denom, out=np.zeros_like(tp, dtype=float), where=denom > 0)
        count = int(self.confusion.sum())
        return {"count": count, "accuracy": float(tp.sum() / count) if count else None,
                "macro_f1_present_classes": float(f1[active].mean()) if active.any() else None,
                "confusion": self.confusion.tolist()}
