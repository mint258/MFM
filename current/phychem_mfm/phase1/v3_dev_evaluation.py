"""Frozen-H0 probes using only molecular inner training/validation roles."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

import numpy as np

from .v3_dev_panel import ALLOWED_ROLES, canonical, molecule_folds


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    dataset_id: str
    field: str
    output_level: str
    error_metric: str
    pooling: str = "mean"

    def __post_init__(self):
        if self.output_level not in ("graph", "atom") or self.error_metric not in (
                "mae", "one_minus_auroc", "one_minus_hit1"):
            raise ValueError("Explicit native output level and lower-is-better error required")
        if self.pooling not in ("mean", "sum"):
            raise ValueError("Development graph pooling must be explicit mean or sum")
        if self.error_metric == "one_minus_hit1" and self.output_level != "atom":
            raise ValueError("Site ranking requires source-aligned atom predictions")


@dataclass(frozen=True)
class TaskMolecule:
    molecule_uid: str
    h0: object
    source_atom_ids: object
    targets: object
    candidate_mask: object
    supervision_mask: object
    source_member_uid: str = ""


@dataclass(frozen=True)
class TaskPrediction:
    task: TaskSpec
    molecule_uids: tuple[str, ...]
    targets: np.ndarray
    predictions: np.ndarray
    valid: np.ndarray
    source_record_uids: tuple[str, ...] = ()


def _validate_molecules(rows, task):
    import torch
    rows = tuple(rows)
    if not rows or len({r.source_member_uid or r.molecule_uid for r in rows}) != len(rows):
        raise ValueError("A nonempty, unique native-record sequence is required")
    dim = rows[0].h0.shape[1]
    for row in rows:
        h, ids = row.h0, row.source_atom_ids
        n = len(h); expected = 1 if task.output_level == "graph" else n
        if (h.ndim != 2 or h.dtype != torch.float32 or h.shape[1] != dim or n < 1
                or not bool(torch.isfinite(h).all()) or h.requires_grad
                or ids.dtype != torch.long or not torch.equal(ids.cpu().sort().values, torch.arange(n))):
            raise ValueError("Frozen H0/native atom identity contract differs")
        if any(tuple(value.shape) != (expected,) for value in (
                row.targets, row.candidate_mask, row.supervision_mask)):
            raise ValueError("One task must have exactly one native target/mask per output row")
        if row.candidate_mask.dtype != torch.bool or row.supervision_mask.dtype != torch.bool:
            raise ValueError("Explicit boolean masks are required")
        if bool((row.supervision_mask & ~row.candidate_mask).any()):
            raise ValueError("Supervision lies outside the candidate population")
        observed = row.targets[row.supervision_mask]
        if not bool(torch.isfinite(observed).all()):
            raise ValueError("Observed TRAIN targets must be finite")
        if task.error_metric != "mae" and not bool(((observed == 0) | (observed == 1)).all()):
            raise ValueError("Native classification targets must already be binary")
    return rows


def task_rows(view, cached_h0, task, *, role):
    """Decode labels only after both the member and role have passed the guard."""
    if role not in ALLOWED_ROLES or task.dataset_id != view.dataset_id or task.field not in view.tasks:
        raise ValueError("Task source or TRAIN role differs from the guarded provider")
    if not callable(getattr(view, "molecule_group", None)):
        raise ValueError("Explicit full-molecule identity metadata is required; source UIDs cannot substitute")
    cached = {row.member_index: row for row in cached_h0}
    column = view.tasks.index(task.field)
    output = []
    for index in view.view(role):
        sample = view.get(index, role=role)
        if not sample.geometry_ready:
            continue  # retained in source inventory; unavailable geometry is not rebuilt here
        row = cached[index]
        if row.molecule_uid != sample.member_uid or not np.array_equal(
                row.source_atom_ids.cpu().numpy(), sample.source_atom_ids.cpu().numpy()):
            raise ValueError("H0 and source target atom identities differ")
        output.append(TaskMolecule(view.molecule_group(index), row.h0,
            row.source_atom_ids, sample.targets[:, column].clone(),
            sample.candidate_mask[:, column].clone(), sample.supervision_mask[:, column].clone(), sample.member_uid))
    return _validate_molecules(output, task)


def _arrays(rows, task):
    features, targets, valid, groups = [], [], [], []
    for row in rows:
        atom = row.h0.detach().cpu().numpy().astype(np.float64)
        x = (atom.mean(0, keepdims=True) if task.pooling == "mean" else atom.sum(0, keepdims=True)) if task.output_level == "graph" else atom
        features.append(x); targets.append(row.targets.cpu().numpy().astype(np.float64))
        valid.append((row.candidate_mask & row.supervision_mask).cpu().numpy())
        groups.extend([row.molecule_uid] * len(x))
    return np.concatenate(features), np.concatenate(targets), np.concatenate(valid), tuple(groups)


def _prediction(task, rows, values):
    _, targets, valid, groups = _arrays(rows, task)
    values = np.asarray(values, dtype=np.float64).reshape(-1)
    if values.shape != targets.shape or not np.isfinite(values).all():
        raise ValueError("Prediction rows/finiteness differ")
    records = tuple(uid for row in rows for uid in
                    [row.source_member_uid or row.molecule_uid] * (1 if task.output_level == "graph" else len(row.h0)))
    return TaskPrediction(task, groups, targets, values, valid, records)


def error(prediction, row_indices=None):
    """Metric in native label units, with explicit unavailable populations."""
    if row_indices is None:
        row_indices = np.arange(len(prediction.targets))
    indices = np.asarray(row_indices, dtype=np.int64)
    mask = prediction.valid[indices]
    selected = indices[mask]
    if not len(selected):
        return None
    y, p = prediction.targets[selected], prediction.predictions[selected]
    if prediction.task.error_metric == "mae":
        return float(np.abs(y-p).mean())
    if prediction.task.error_metric == "one_minus_auroc":
        positives = y == 1; npos = int(positives.sum()); nneg = len(y)-npos
        if not npos or not nneg:
            return None
        order = np.argsort(p, kind="stable")
        ranks = np.empty(len(p), dtype=np.float64)
        start = 0
        while start < len(order):
            stop = start+1
            while stop < len(order) and p[order[stop]] == p[order[start]]:
                stop += 1
            ranks[order[start:stop]] = (start+1+stop)/2
            start = stop
        auc = (float(ranks[positives].sum())-npos*(npos+1)/2)/(npos*nneg)
        return 1.0-auc
    # Repeated molecule bootstrap draws need separate occurrences so that
    # each molecule draw contributes once, rather than being deduplicated.
    hits = []
    native_records = prediction.source_record_uids or prediction.molecule_uids
    cursor = 0
    while cursor < len(indices):
        uid = native_records[int(indices[cursor])]
        stop = cursor+1
        while (stop < len(indices) and native_records[int(indices[stop])] == uid
               and indices[stop] > indices[stop-1]):
            stop += 1
        block = indices[cursor:stop]
        keep = block[prediction.valid[block]]
        if len(keep) and bool((prediction.targets[keep] == 1).any()):
            # Stable native atom order resolves exact prediction ties.
            top = keep[int(np.argmax(prediction.predictions[keep]))]
            hits.append(float(prediction.targets[top] == 1))
        cursor = stop
    return 1.0-float(np.mean(hits)) if hits else None


class _Ridge:
    def __init__(self, x, y):
        if not len(x):
            raise ValueError("No observed optimization labels")
        self.mean = x.mean(0); self.scale = x.std(0)
        self.scale[self.scale < 1e-12] = 1.0
        self.ymean = float(y.mean()); self.yscale = float(y.std()) or 1.0
        x = (x-self.mean)/self.scale
        self.u, self.s, self.vh = np.linalg.svd(x, full_matrices=False)
        self.projected = self.u.T @ ((y-self.ymean)/self.yscale)

    def predict(self, x, alpha):
        coefficient = self.vh.T @ ((self.s/(self.s*self.s+alpha))*self.projected)
        return (((x-self.mean)/self.scale) @ coefficient)*self.yscale+self.ymean


def ridge_probe(train, validation, task, *, alphas=(1e-6, 1e-4, 1e-2, 1., 100.), folds=5, seed=20261025):
    train, validation = _validate_molecules(train, task), _validate_molecules(validation, task)
    if {r.molecule_uid for r in train} & {r.molecule_uid for r in validation}:
        raise ValueError("Optimization and inner-validation molecules overlap")
    alphas = tuple(sorted(set(float(a) for a in alphas)))
    if not alphas or any(not math.isfinite(a) or a <= 0 for a in alphas):
        raise ValueError("Positive, preregistered ridge alphas required")
    assignment = molecule_folds([r.molecule_uid for r in train], folds=folds, seed=seed)
    scores = {alpha: [] for alpha in alphas}
    for fold in range(folds):
        fit = tuple(r for r in train if assignment[r.molecule_uid] != fold)
        held = tuple(r for r in train if assignment[r.molecule_uid] == fold)
        x, y, mask, _ = _arrays(fit, task)
        model = _Ridge(x[mask], y[mask])
        held_x = _arrays(held, task)[0]
        for alpha in alphas:
            scores[alpha].append(error(_prediction(task, held, model.predict(held_x, alpha))))
    usable = {alpha: float(np.mean(values)) for alpha, values in scores.items()
              if all(value is not None for value in values)}
    if not usable:
        raise ValueError("Ridge selection unavailable: at least one molecular fold lacks its metric population")
    chosen = min(usable, key=lambda a: (usable[a], a))
    x, y, mask, _ = _arrays(train, task)
    model = _Ridge(x[mask], y[mask])
    prediction = _prediction(task, validation, model.predict(_arrays(validation, task)[0], chosen))
    return prediction, {"selected_alpha": chosen, "inner_cv_errors": {str(a): scores[a] for a in alphas},
                        "fold_assignment_sha256": canonical(assignment), "fit_scope": "train",
                        "validation_role": ALLOWED_ROLES[1], "normalization_fit_scope": "train"}


def nonlinear_probe(train, validation, task, *, seed=0, device="cpu", tracker):
    """Existing source-aligned Linear64/ReLU; fixed 20 epochs and B32.

    The supplied tracker must be a functional W&B run for experiments. A unit
    fixture may provide a small bound log implementation and is not evidence
    that a real W&B run was persisted.
    """
    import torch
    from .downstream_readout import SourceAlignedH0Readout
    train, validation = _validate_molecules(train, task), _validate_molecules(validation, task)
    if {r.molecule_uid for r in train} & {r.molecule_uid for r in validation}:
        raise ValueError("Optimization and inner-validation molecules overlap")
    if not callable(getattr(tracker, "log", None)) or getattr(tracker, "disabled", False):
        raise ValueError("Functional explicit tracking required")
    device = torch.device(device)
    if device.type not in ("cpu", "cuda"):
        raise ValueError("A single CPU or CUDA device is required")
    observed = torch.cat([r.targets[r.supervision_mask & r.candidate_mask].float() for r in train])
    if not len(observed):
        raise ValueError("No observed TRAIN labels")
    mean = float(observed.mean()) if task.error_metric == "mae" else 0.
    scale = float(observed.std(unbiased=False)) if task.error_metric == "mae" else 1.
    scale = scale if scale > 1e-12 else 1.
    devices = [device.index or 0] if device.type == "cuda" else []
    history = []
    with torch.random.fork_rng(devices=devices):
        torch.manual_seed(seed)
        if device.type == "cuda":
            torch.cuda.manual_seed_all(seed)
        model = SourceAlignedH0Readout(train[0].h0.shape[1], 1, output_level=task.output_level,
            hidden_dim=64, atom_layers=1, pooling=task.pooling if task.output_level == "graph" else None).to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=.001, betas=(.9, .999),
            eps=1e-8, weight_decay=.01, foreach=False, fused=False)
        rng = torch.Generator(device="cpu").manual_seed(seed)

        def batch_values(rows):
            h0 = torch.cat([r.h0 for r in rows]).to(device)
            ids = torch.cat([r.source_atom_ids for r in rows]).to(device)
            lengths = torch.tensor([len(r.h0) for r in rows], device=device)
            ptr = torch.cat((lengths.new_zeros(1), lengths.cumsum(0)))
            values = model(h0, source_atom_ids=ids, ptr=ptr).predictions[:, 0]
            targets = torch.cat([r.targets for r in rows]).to(device).float()
            mask = torch.cat([r.supervision_mask & r.candidate_mask for r in rows]).to(device)
            return values, targets, mask

        step = 0
        retained = tuple(r for r in train if bool((r.supervision_mask & r.candidate_mask).any()))
        for epoch in range(20):
            model.train()
            order = torch.randperm(len(retained), generator=rng).tolist()
            for start in range(0, len(order), 32):
                rows = tuple(retained[i] for i in order[start:start+32])
                prediction, target, mask = batch_values(rows)
                # Index before arithmetic so unknown NaN labels do not enter
                # either losses or gradients, even in otherwise valid batches.
                y = target[mask]
                loss = (torch.nn.functional.mse_loss(prediction[mask], (y-mean)/scale)
                        if task.error_metric == "mae" else
                        torch.nn.functional.binary_cross_entropy_with_logits(prediction[mask], y))
                if not bool(torch.isfinite(loss)):
                    raise FloatingPointError("Nonfinite development readout loss")
                optimizer.zero_grad(set_to_none=True); loss.backward(); optimizer.step()
                row = {"readout/loss": float(loss.detach()), "readout/epoch": epoch,
                       "readout/observed_labels": int(mask.sum()), "readout/update": step}
                tracker.log(row, step=step, commit=True); history.append(row); step += 1
        model.eval()
        values = []
        with torch.no_grad():
            for start in range(0, len(validation), 32):
                prediction, _, _ = batch_values(validation[start:start+32])
                values.extend((prediction*scale+mean).cpu().numpy().tolist())
    return _prediction(task, validation, values), {"epochs": 20, "batch_graphs": 32,
        "updates": step, "normalization_fit_scope": "train", "target_mean": mean,
        "target_scale": scale, "history": history, "encoder_updated": False,
        "readout": "SourceAlignedH0Readout/Linear64/ReLU"}


def compare_panel(candidate: Mapping[str, TaskPrediction], reference: Mapping[str, TaskPrediction],
                  *, architecture_sha256, reference_architecture_sha256, bootstrap_samples=1000,
                  confidence=.95, seed=20261025):
    """Paired, molecule-cluster bootstrap; one common draw per dataset/task set."""
    if architecture_sha256 != reference_architecture_sha256:
        raise ValueError("Random reference must use the same architecture")
    if set(candidate) != set(reference) or not candidate:
        raise ValueError("Exact configured task coverage is required")
    if bootstrap_samples < 1 or not 0 < confidence < 1:
        raise ValueError("Explicit positive bootstrap count and confidence required")
    groups, per_task = {}, {}
    for key in sorted(candidate):
        actual, ref = candidate[key], reference[key]
        if (actual.task != ref.task or actual.molecule_uids != ref.molecule_uids
                or actual.source_record_uids != ref.source_record_uids
                or not np.array_equal(actual.valid, ref.valid)
                or not np.array_equal(actual.targets, ref.targets, equal_nan=True)):
            raise ValueError("Reference and candidate source labels/masks/molecules differ")
        actual_error, reference_error = error(actual), error(ref)
        improvement = ((reference_error-actual_error)/reference_error
                       if actual_error is not None and reference_error is not None and reference_error > 0 else None)
        per_task[key] = {"error": actual_error, "reference_error": reference_error,
                         "normalized_improvement": improvement,
                         "observed_labels": int(actual.valid.sum()),
                         "observed_molecules": len({uid for uid, mask in zip(actual.molecule_uids, actual.valid) if mask})}
        groups.setdefault(actual.task.dataset_id, set()).update(actual.molecule_uids)
    groups = {key: tuple(sorted(values)) for key, values in groups.items()}
    rng = np.random.default_rng(seed)
    task_boot = {key: [] for key in candidate}; summary_boot = []
    for _ in range(bootstrap_samples):
        draws = {dataset: rng.choice(uids, len(uids), replace=True).tolist() for dataset, uids in groups.items()}
        values = []
        for key in sorted(candidate):
            actual, ref = candidate[key], reference[key]
            rows = {uid: [] for uid in set(actual.molecule_uids)}
            for index, uid in enumerate(actual.molecule_uids):
                rows[uid].append(index)
            indices = [i for uid in draws[actual.task.dataset_id] for i in rows.get(uid, ())]
            a, r = error(actual, indices), error(ref, indices)
            value = (r-a)/r if a is not None and r is not None and r > 0 else None
            if value is not None:
                task_boot[key].append(value)
                values.append(value)
        if len(values) == len(candidate):
            summary_boot.append(float(np.mean(values)))
    quantiles = [(1-confidence)/2, (1+confidence)/2]
    for key, values in task_boot.items():
        per_task[key]["bootstrap_ci"] = np.quantile(values, quantiles).tolist() if values else None
        per_task[key]["bootstrap_defined"] = len(values)
    complete = all(row["normalized_improvement"] is not None for row in per_task.values())
    return {"tasks": per_task, "complete": complete,
            "mean_normalized_improvement": float(np.mean([r["normalized_improvement"] for r in per_task.values()])) if complete else None,
            "bootstrap_ci": np.quantile(summary_boot, quantiles).tolist() if summary_boot and complete else None,
            "bootstrap_samples": bootstrap_samples, "bootstrap_defined": len(summary_boot),
            "bootstrap_unit": "molecule", "bootstrap_seed": seed,
            "architecture_sha256": architecture_sha256}


def seed_standard_deviation(scores, *, scientific_configuration_hashes):
    if len(scores) != 2 or len(scientific_configuration_hashes) != 2:
        raise ValueError("Exactly two pretraining seeds are required")
    if len(set(scientific_configuration_hashes)) != 1 or not all(math.isfinite(v) for v in scores):
        raise ValueError("Finite scores from the same seed-excluded configuration required")
    return float(np.std(scores, ddof=1))
