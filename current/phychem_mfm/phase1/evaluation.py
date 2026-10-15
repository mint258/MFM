"""Label-count-weighted original-unit metrics alongside train-only baselines."""
from __future__ import annotations

import numpy as np
import torch
import hashlib
import json
import math
from collections.abc import Mapping
from torch_geometric.utils import to_dense_batch

from ..data.descriptor_schema import CHARGE_DESCRIPTOR_SPECS, ELEMENT_DESCRIPTOR_SPECS
from ..training.data import SAMPLE_TYPE_TO_ID
from .baselines import RegressionMeter, ClassificationMeter


def array(value):
    return value.detach().float().cpu().numpy()


def _builtin(value):
    if isinstance(value, np.ndarray):
        return _builtin(value.tolist())
    if isinstance(value, np.generic):
        return _builtin(value.item())
    if isinstance(value, Mapping):
        return {key: _builtin(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_builtin(item) for item in value]
    if value is None or type(value) in (bool, str, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    raise ValueError("Original-unit metric state must contain finite JSON builtins")


def _state_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def _finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _owned_state(value):
    # This validates builtin ownership before any NumPy candidate allocation.
    active, visits = set(), [0]
    def walk(item, depth):
        visits[0] += 1
        if depth > 24 or visits[0] > 100000:
            raise ValueError("Original-unit metric state exceeds structural bounds")
        if type(item) in (dict, list):
            if id(item) in active:
                raise ValueError("Cyclic original-unit metric state")
            active.add(id(item))
            if type(item) is dict:
                if any(type(key) is not str for key in item):
                    raise ValueError("Metric state object keys must be strings")
                for key, child in item.items():
                    walk(key, depth + 1)
                    walk(child, depth + 1)
            else:
                for child in item:
                    walk(child, depth + 1)
            active.remove(id(item))
        elif type(item) is str:
            if len(item) > 1048576:
                raise ValueError("Metric state string exceeds bound")
        elif item is not None and type(item) not in (bool, int, float):
            raise ValueError("Metric state must contain only JSON builtins")
        elif type(item) is float and not math.isfinite(item):
            raise ValueError("Nonfinite metric state")
    walk(value, 0)
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                             allow_nan=False).encode("ascii")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("Invalid original-unit metric state") from exc
    if len(encoded) > 1048576:
        raise ValueError("Original-unit metric state exceeds 1 MiB")
    return json.loads(encoded)


class OriginalUnitEvaluator:
    def __init__(self, model, baselines, cutoff=2.):
        self.model, self.baselines, self.cutoff = model, baselines, cutoff
        self.meters = {}
        self.unavailable_baselines = set()
        self.unseen_charge_atoms = 0

    def _contract(self):
        """Only fixed evaluation semantics; never capture model weights/references."""
        if type(self.cutoff) not in (int, float) or not math.isfinite(self.cutoff) or self.cutoff <= 0:
            raise ValueError("Original-unit local geometry cutoff must be positive finite")
        controls = {key: _builtin(getattr(self.baselines, key)) for key in (
            "n_atom_types", "energy_coefficients", "charge_means", "charge_counts", "charge_global_mean",
            "element_majority", "bond_majority", "graph_means", "node_predictions")}
        unavailable = getattr(self.baselines, "unavailable", {})
        controls["unavailable"] = {name: dict(row) for name, row in unavailable.items()}
        # Include the fullprep/normalization binding without importing model state.
        if hasattr(self.baselines, "to_dict") and hasattr(self.baselines, "unavailable"):
            controls["full_corpus_controls"] = self.baselines.to_dict()
        element_classes = getattr(self.model, "n_atom_types", None)
        if element_classes is None:
            element_classes = self.baselines.n_atom_types + int(hasattr(self.baselines, "unavailable"))
        if type(element_classes) is not int or not 2 <= element_classes <= 4096:
            raise ValueError("Invalid fixed element evaluation vocabulary")
        names = list(getattr(self.model, "graph_descriptor_names", ()))
        indices = list(getattr(self.model, "graph_descriptor_target_indices", ()))
        if (len(names) != len(indices) or len(set(names)) != len(names)
                or any(type(name) is not str for name in names)
                or any(type(i) is not int or i < 0 for i in indices)):
            raise ValueError("Invalid graph evaluation target mapping")
        return {"cutoff": float(self.cutoff), "element_classes": element_classes,
                "graph_descriptor_names": names, "graph_descriptor_target_indices": indices,
                "controls_semantic_sha256": _state_hash(_builtin(controls)),
                "units": "heads output original units; no second inverse",
                "bond_population": "positive legal order targets on clean graphs only"}

    def _target_kind(self, name, contract):
        if name in ("energy_kcal_per_mol", "net_atomic_charge_e", "geometry_all_pair_A", "geometry_local_pair_A"):
            return "regression", None
        if name == "element":
            return "classification", contract["element_classes"]
        if name == "bond_order_positive":
            return "classification", 5
        if name.startswith("D/"):
            target = name[2:]
            if target in contract["graph_descriptor_names"]:
                return "regression", None
            specs = {spec.name: spec for spec in (*CHARGE_DESCRIPTOR_SPECS, *ELEMENT_DESCRIPTOR_SPECS)}
            if target in specs:
                spec = specs[target]
                return ("regression", None) if spec.task_type == "regression" else (
                    "classification", 2 if spec.task_type == "binary" else spec.num_classes)
        raise ValueError("Metric state contains an undeclared evaluation target")

    def _baseline_available(self, name):
        if name == "energy_kcal_per_mol":
            return self.baselines.energy_coefficients is not None
        if name == "net_atomic_charge_e":
            return self.baselines.charge_means is not None
        if name == "element":
            return self.baselines.element_majority is not None
        if name == "bond_order_positive":
            return self.baselines.bond_majority is not None
        if name.startswith("geometry_"):
            return True
        return name[2:] in self.baselines.graph_means or name[2:] in self.baselines.node_predictions

    def state_dict(self):
        """Owned builtin accumulators for exact continuation on the same contract."""
        records = []
        for (name, label), meter in sorted(self.meters.items()):
            if isinstance(meter, RegressionMeter):
                records.append({"target": name, "estimate": label, "kind": "regression",
                                "count": int(meter.count), "absolute": float(meter.absolute), "squared": float(meter.squared)})
            elif isinstance(meter, ClassificationMeter):
                records.append({"target": name, "estimate": label, "kind": "classification",
                                "classes": int(len(meter.confusion)), "confusion": meter.confusion.tolist()})
            else:
                raise ValueError("Unsupported original-unit meter")
        state = {"schema_version": "phase1_original_unit_evaluator_state_v1", "contract": self._contract(),
                 "meters": records, "unavailable_baselines": sorted(self.unavailable_baselines),
                 "unseen_charge_atoms": int(self.unseen_charge_atoms)}
        state = _owned_state(state)
        state["state_sha256"] = _state_hash(state)
        return state

    def load_state_dict(self, payload):
        """Validate all candidates before replacing any live accumulator."""
        state = _owned_state(payload)
        required = {"schema_version", "contract", "meters", "unavailable_baselines", "unseen_charge_atoms", "state_sha256"}
        if (type(state) is not dict or set(state) != required
                or state["schema_version"] != "phase1_original_unit_evaluator_state_v1"
                or state["state_sha256"] != _state_hash({k: v for k, v in state.items() if k != "state_sha256"})
                or state["contract"] != self._contract()
                or _state_hash(state["contract"]) != _state_hash(self._contract())):
            raise ValueError("Original-unit metric state seal/contract differs")
        if type(state["meters"]) is not list or len(state["meters"]) > 256:
            raise ValueError("Invalid original-unit meter list")
        candidates, last_key = {}, None
        for row in state["meters"]:
            if type(row) is not dict or type(row.get("target")) is not str or row.get("estimate") not in ("model", "baseline"):
                raise ValueError("Invalid metric target/estimate")
            key = row["target"], row["estimate"]
            if last_key is not None and key <= last_key:
                raise ValueError("Metric records must be unique canonical sorted targets")
            last_key = key
            kind, classes = self._target_kind(key[0], state["contract"])
            if row.get("kind") != kind:
                raise ValueError("Metric kind differs from declared target")
            if kind == "regression":
                if set(row) != {"target", "estimate", "kind", "count", "absolute", "squared"}:
                    raise ValueError("Invalid regression accumulator fields")
                n, a, s = row["count"], row["absolute"], row["squared"]
                if (type(n) is not int or not 0 <= n <= (1 << 63) - 1
                        or any(not _finite_number(v) or v < 0 for v in (a, s))
                        or (n == 0 and (a != 0 or s != 0))):
                    raise ValueError("Invalid regression accumulators")
                # Cauchy-Schwarz is required for real absolute/squared errors.
                if n and a / n > math.sqrt(s / n) + 1e-12 * max(1., a / n, math.sqrt(s / n)):
                    raise ValueError("Regression absolute/squared accumulators disagree")
                meter = RegressionMeter()
                meter.count, meter.absolute, meter.squared = n, float(a), float(s)
            else:
                if set(row) != {"target", "estimate", "kind", "classes", "confusion"} or type(row["classes"]) is not int or row["classes"] != classes:
                    raise ValueError("Classification vocabulary differs")
                confusion = row["confusion"]
                if (type(confusion) is not list or len(confusion) != classes
                        or any(type(values) is not list or len(values) != classes for values in confusion)
                        or any(type(v) is not int or not 0 <= v <= (1 << 63) - 1 for values in confusion for v in values)
                        or sum(v for values in confusion for v in values) > (1 << 63) - 1):
                    raise ValueError("Invalid classification confusion accumulators")
                meter = ClassificationMeter(classes)
                meter.confusion = np.asarray(confusion, dtype=np.int64).copy()
            candidates[key] = meter
        missing = state["unavailable_baselines"]
        if type(missing) is not list or any(type(name) is not str for name in missing) or missing != sorted(set(missing)):
            raise ValueError("Invalid unavailable-baseline target set")
        for name in missing:
            self._target_kind(name, state["contract"])
            if self._baseline_available(name) or (name, "baseline") in candidates or (name, "model") not in candidates:
                raise ValueError("Unavailable baseline conflicts with actual meter state")
        for (name, label), meter in candidates.items():
            if label == "baseline":
                if not self._baseline_available(name):
                    raise ValueError("Metric state supplies an unavailable baseline")
                other = candidates.get((name, "model"))
                count = meter.count if isinstance(meter, RegressionMeter) else int(meter.confusion.sum())
                other_count = None if other is None else (other.count if isinstance(other, RegressionMeter) else int(other.confusion.sum()))
                if count != other_count:
                    raise ValueError("Baseline and model label populations differ")
            elif (name, "baseline") not in candidates and name not in missing:
                raise ValueError("Model metric lacks baseline availability evidence")
        unseen = state["unseen_charge_atoms"]
        qmeter = candidates.get(("net_atomic_charge_e", "model"))
        if type(unseen) is not int or not 0 <= unseen <= (qmeter.count if qmeter is not None else 0):
            raise ValueError("Unseen charge count exceeds evaluated atoms")
        self.meters, self.unavailable_baselines, self.unseen_charge_atoms = candidates, set(missing), unseen

    def regression(self, name, prediction, target, baseline):
        if not np.asarray(target).size:
            return
        estimates = [("model", prediction)]
        if baseline is None:
            self.unavailable_baselines.add(name)
        else:
            estimates.append(("baseline", baseline))
        for label, value in estimates:
            meter = self.meters.setdefault((name, label), RegressionMeter())
            meter.add(value, target)

    def classification(self, name, prediction, target, baseline, classes):
        if not np.asarray(target).size:
            return
        estimates = [("model", prediction)]
        if baseline is None:
            self.unavailable_baselines.add(name)
        else:
            estimates.append(("baseline", baseline))
        for label, value in estimates:
            meter = self.meters.setdefault((name, label), ClassificationMeter(classes))
            meter.add(value, target)

    @torch.no_grad()
    def add(self, batch, outputs):
        device = batch.pos.device
        types = getattr(batch, "sample_type_id", torch.zeros(batch.num_graphs, device=device, dtype=torch.long)).view(-1)
        clean = types == SAMPLE_TYPE_TO_ID["clean"]
        geom = (types == SAMPLE_TYPE_TO_ID["geom"]) | (types == SAMPLE_TYPE_TO_ID["both"])
        topo = (types == SAMPLE_TYPE_TO_ID["topo"]) | (types == SAMPLE_TYPE_TO_ID["both"])
        x, real = to_dense_batch(batch.x[:, 0], batch.batch)
        if outputs.energy_pred is not None:
            target = batch.energy.view(-1)
            energy_mask = batch.energy_mask.view(-1)
            valid = clean & torch.isfinite(energy_mask) & energy_mask.eq(1) & torch.isfinite(target)
            # fast_collate temporarily renames PyG index-like fields; its batch
            # slice metadata cannot safely be fed back to to_data_list().
            baseline = None
            if self.baselines.energy_coefficients is not None:
                predictions = []
                # Excluded topology views can contain the input padding/mask
                # class. They never enter this physical-element design.
                for index in valid.nonzero(as_tuple=False).view(-1).tolist():
                    atoms = array(x[index][real[index]]).astype(int)
                    if np.any((atoms < 0) | (atoms >= self.baselines.n_atom_types)):
                        raise ValueError("Energy control input is outside its physical element domain")
                    design = np.r_[np.bincount(atoms, minlength=self.baselines.n_atom_types), 1.]
                    predictions.append(float(design @ self.baselines.energy_coefficients))
                baseline = np.asarray(predictions, dtype=np.float64)
            self.regression("energy_kcal_per_mol", array(outputs.energy_pred.view(-1)[valid]), array(target[valid]),
                            baseline)
        if outputs.charge_pred is not None:
            target, _ = to_dense_batch(batch.y.view(-1), batch.batch)
            cmask, _ = to_dense_batch(batch.charge_mask.view(-1), batch.batch)
            valid = real & clean[:, None] & (cmask > .5) & torch.isfinite(target)
            if outputs.charge_mask is not None:
                valid = real & clean[:, None] & outputs.charge_mask.reshape(real.shape).bool() & torch.isfinite(target)
            if outputs.node_mask is not None:
                valid &= outputs.node_mask.reshape(real.shape).bool()
            pred = outputs.charge_pred.squeeze(-1)
            atomic = array(x[valid]).astype(int)
            if self.baselines.charge_counts is not None:
                self.unseen_charge_atoms += int((self.baselines.charge_counts[atomic] == 0).sum())
            self.regression("net_atomic_charge_e", array(pred[valid]), array(target[valid]),
                            None if self.baselines.charge_means is None else self.baselines.charge_means[atomic])
        if outputs.element_logits is not None:
            target, _ = to_dense_batch(batch.target_x[:, 0], batch.batch)
            corrupt, _ = to_dense_batch(batch.element_corrupt_mask.view(-1), batch.batch)
            valid = real & topo[:, None] & (corrupt > .5)
            if outputs.node_mask is not None:
                valid &= outputs.node_mask.reshape(real.shape).bool()
            # Match the loss contract: the final class is reserved padding and
            # cannot be an element recovery target. A padding *prediction* on
            # a legal target remains an error and must still be scored.
            valid &= torch.isfinite(target) & target.eq(target.float().floor())
            valid &= (target >= 0) & (target < outputs.element_logits.size(-1) - 1)
            labels = array(target[valid]).astype(int)
            self.classification("element", array(outputs.element_logits.argmax(-1)[valid]), labels,
                                None if self.baselines.element_majority is None else np.full(len(labels), self.baselines.element_majority), outputs.element_logits.size(-1))
        if outputs.coordinate_pred is not None:
            target, _ = to_dense_batch(batch.target_pos, batch.batch)
            noisy, _ = to_dense_batch(batch.pos, batch.batch)
            td = torch.cdist(target.float(), target.float())
            md = torch.cdist(outputs.coordinate_pred.float(), outputs.coordinate_pred.float())
            bd = torch.cdist(noisy.float(), noisy.float())
            valid_node = real & torch.isfinite(target).all(-1)
            if outputs.node_mask is not None:
                valid_node &= outputs.node_mask.reshape(real.shape).bool()
            valid = valid_node[:, :, None] & valid_node[:, None, :] & geom[:, None, None]
            # Distances are symmetric: report each unordered atom pair once,
            # consistent with the training distance_pairs count.
            valid &= torch.triu(torch.ones((real.size(1), real.size(1)), device=device, dtype=torch.bool), diagonal=1)[None]
            self.regression("geometry_all_pair_A", array(md[valid]), array(td[valid]), array(bd[valid]))
            local = valid & (td < self.cutoff)
            self.regression("geometry_local_pair_A", array(md[local]), array(td[local]), array(bd[local]))
        if outputs.bond is not None and outputs.bond.order_target.numel():
            bond = outputs.bond
            ids = bond.pair_graph_index
            if (ids.dtype != torch.long or ids.ndim != 1 or ids.numel() != bond.order_target.numel()
                    or bond.order.shape != (ids.numel(), 5) or bool(((ids < 0) | (ids >= batch.num_graphs)).any())):
                raise ValueError("Positive bond metadata must identify its actual source graph")
            if bond.existence.numel() or (bond.existence_target.numel() and not bool(bond.existence_target.eq(1).all())):
                raise ValueError("Original-unit bond metric requires positive-only five-class outputs")
            labels = bond.order_target.view(-1)
            keep = clean[ids] & torch.isfinite(labels) & labels.eq(labels.float().floor()) & labels.ge(0) & labels.lt(5)
            target = array(labels[keep]).astype(int)
            # Phase 1 positive-only head uses 0..4 for legacy bond labels 1..5.
            self.classification("bond_order_positive", array(bond.order.argmax(-1)[keep]), target,
                                None if self.baselines.bond_majority is None else np.full(len(target), self.baselines.bond_majority - 1), 5)
        if outputs.graph_descriptor_pred is not None:
            targets = batch.rdkit_graph_desc.view(batch.num_graphs, -1)
            masks = batch.rdkit_graph_desc_mask.view(batch.num_graphs, -1)
            for column, (name, source_idx) in enumerate(zip(self.model.graph_descriptor_names, self.model.graph_descriptor_target_indices)):
                valid = clean & (masks[:, source_idx] > .5) & torch.isfinite(targets[:, source_idx])
                labels = array(targets[:, source_idx][valid])
                baseline = np.full(len(labels), self.baselines.graph_means[name]) if name in self.baselines.graph_means else None
                self.regression("D/" + name, array(outputs.graph_descriptor_pred[:, column][valid]), labels, baseline)
        all_preds = {**outputs.charge_descriptor_pred, **outputs.element_descriptor_pred}
        specs = {spec.name: spec for spec in (*CHARGE_DESCRIPTOR_SPECS, *ELEMENT_DESCRIPTOR_SPECS)}
        if not all_preds:
            return
        node_mask, _ = to_dense_batch(batch.rdkit_node_mask.view(-1), batch.batch)
        for name, pred in all_preds.items():
            spec = specs[name]
            target, _ = to_dense_batch(getattr(batch, spec.field_name).view(-1), batch.batch)
            valid = real & clean[:, None] & (node_mask > .5) & torch.isfinite(target)
            if outputs.node_mask is not None:
                valid &= outputs.node_mask.reshape(real.shape).bool()
            if spec.task_type == "regression":
                labels = array(target[valid])
                self.regression("D/" + name, array(pred.squeeze(-1)[valid]), labels,
                                np.full(len(labels), self.baselines.node_predictions[name]) if name in self.baselines.node_predictions else None)
            else:
                classes = 2 if spec.task_type == "binary" else spec.num_classes
                valid &= target.eq(target.floor()) & (target >= 0) & (target < classes)
                predicted = (pred.squeeze(-1) >= 0).long() if classes == 2 else pred.argmax(-1)
                labels = array(target[valid]).astype(int)
                self.classification("D/" + name, array(predicted[valid]), labels,
                                    np.full(len(labels), int(self.baselines.node_predictions[name])) if name in self.baselines.node_predictions else None, classes)

    def result(self):
        report = {}
        for (name, label), meter in sorted(self.meters.items()):
            report.setdefault(name, {})[label] = meter.result()
        for name in sorted(self.unavailable_baselines):
            evidence = getattr(self.baselines, "unavailable", {}).get(name)
            report.setdefault(name, {})["baseline"] = ({"status": "unavailable", "available": False,
                "evidence_state": evidence["status"], "reason": evidence["reason"]} if evidence is not None
                else {"status": "unavailable: no valid training labels"})
        return _builtin({"targets": report, "unseen_charge_element_atoms": self.unseen_charge_atoms,
                "geometry_pair_count_semantics": "unique unordered atom pairs (i < j); each valid pair counted once",
                "normalization": "heads already output original units; no second inverse transform",
                "status": "diagnostic evidence; no fixed adequacy threshold or automated scientific conclusion"})
