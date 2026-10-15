"""Native-only QA label transport and FP64 online sufficient statistics.

Candidate preparation, not a scientific protocol or chemical-truth validator.
No files are opened here. The caller must prove identity/embargo/role BEFORE
calling these functions. Invalid individual labels become unavailable; source
LMDB bytes are never modified. A future loader must use the same transport.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import math


MASK_POLICY = "phase1_native_finite_domain_mask_transport_v2"
ESTIMATOR = "phase1_train_only_fp64_chan_population_moments_v1"


def empty_moment():
    return {"count": 0, "mean": 0.0, "m2": 0.0}


def merge_moment(a, b):
    """Chan's population sufficient-statistic merge in caller-fixed order."""
    na, nb = a["count"], b["count"]
    if not nb:
        return dict(a)
    if not na:
        return dict(b)
    count = na + nb
    delta = b["mean"] - a["mean"]
    row = {"count": count, "mean": a["mean"] + delta * nb / count,
           "m2": a["m2"] + b["m2"] + delta * delta * na * nb / count}
    if not all(math.isfinite(row[k]) for k in ("mean", "m2")) or row["m2"] < 0:
        raise ValueError("Nonfinite/negative merged FP64 population moment")
    return row


def add_values(moment, values):
    import torch
    values = values.detach().reshape(-1).double()
    if not values.numel():
        return dict(moment)
    if not bool(torch.isfinite(values).all()):
        raise ValueError("Only finite observed labels enter FP64 statistics")
    mean = values.mean()
    return merge_moment(moment, {"count": values.numel(), "mean": float(mean),
                                "m2": float((values - mean).square().sum())})


def estimate(moment, floor):
    if not moment["count"]:
        return {**moment, "population_std": 1.0, "available": False,
                "empty_placeholder_mean": 0.0}
    return {**moment, "population_std": max(math.sqrt(moment["m2"] / moment["count"]), floor),
            "available": True}


def task_contract():
    from phychem_mfm.data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
    from phychem_mfm.model.phase1_specs import (
        PHASE1_GRAPH_DESCRIPTOR_NAMES, PHASE1_CHARGE_DESCRIPTOR_SPECS,
        PHASE1_ELEMENT_DESCRIPTOR_SPECS,
    )
    return (tuple(GRAPH_DESCRIPTOR_NAMES), tuple(PHASE1_GRAPH_DESCRIPTOR_NAMES),
            PHASE1_CHARGE_DESCRIPTOR_SPECS + PHASE1_ELEMENT_DESCRIPTOR_SPECS)


def empty_statistics():
    graph_all, graph_names, specs = task_contract()
    names = ("energy", "charge", "estate_index") + tuple("graph/" + n for n in graph_names)
    return {"schema_version": ESTIMATOR, "moments": {n: empty_moment() for n in names},
            "charge_by_element": {str(z): empty_moment() for z in range(1, 119)},
            "categorical_counts": {s.name: {} for s in specs if s.task_type != "regression"},
            "energy_linear_reference_sufficient_statistics": {
                "basis": "native_element_counts_Z1_to_Z118_then_intercept_v1", "count": 0,
                "xtx": [[0.0] * 119 for _ in range(119)], "xty": [0.0] * 119},
            "observed_train_records": 0, "observed_train_atoms": 0,
            "train_only": True, "formal_eligible": False, "state": "NOT_FROZEN"}


def merge_statistics(a, b):
    if set(a) != set(b) or a["schema_version"] != b["schema_version"]:
        raise ValueError("Statistics schema mismatch")
    result = deepcopy(a)
    for field in ("moments", "charge_by_element"):
        if set(a[field]) != set(b[field]):
            raise ValueError("Statistics task/element set mismatch")
        result[field] = {k: merge_moment(a[field][k], b[field][k]) for k in a[field]}
    for name in a["categorical_counts"]:
        result["categorical_counts"][name] = dict(Counter(a["categorical_counts"][name]) +
                                                 Counter(b["categorical_counts"][name]))
    for field in ("observed_train_records", "observed_train_atoms"):
        result[field] = a[field] + b[field]
    ra, rb = a["energy_linear_reference_sufficient_statistics"], b["energy_linear_reference_sufficient_statistics"]
    if ra["basis"] != rb["basis"]:
        raise ValueError("Energy-reference basis mismatch")
    rc = result["energy_linear_reference_sufficient_statistics"]
    rc["count"] = ra["count"] + rb["count"]
    rc["xty"] = [x + y for x, y in zip(ra["xty"], rb["xty"])]
    rc["xtx"] = [[x + y for x, y in zip(ar, br)] for ar, br in zip(ra["xtx"], rb["xtx"])]
    if not all(math.isfinite(v) for row in rc["xtx"] for v in row) or not all(math.isfinite(v) for v in rc["xty"]):
        raise ValueError("Nonfinite merged energy reference sufficient statistics")
    return result


def transport_native_record(raw, *, real_index: int, normalizer, issues=None):
    """Owned transport consistent with observed-label loss masks, never drop a molecule.

    Existing strict normalizer casts integer descriptor fields. Validate their
    original domain first so a fractional/NaN value cannot become a valid class
    after that cast. Shape/missing failures get per-field unknown placeholders.
    """
    import torch
    graph_all, graph_names, specs = task_contract()
    x = getattr(raw, "x", None)
    if (not isinstance(x, torch.Tensor) or x.device.type != "cpu" or x.ndim != 2 or x.shape[1] != 1
            or x.dtype not in (torch.int8, torch.int16, torch.int32, torch.int64) or len(x) == 0
            or not bool(((x >= 0) & (x < 118)).all())):
        raise ValueError("Native elements must be integer zero-based Z1..118 before transport")
    n = int(x.shape[0])
    record = raw.clone()
    record.x = x.long().clone()  # Owned dtype transport; values and source row order are unchanged.
    diagnostics = Counter()

    def tensor(field, size, *, kind="regression", classes=None):
        value = getattr(raw, field, None)
        if not isinstance(value, torch.Tensor) or value.device.type != "cpu" or value.numel() != size:
            diagnostics[field + "/missing_or_shape"] += 1
            return torch.full((size,), float("nan"))
        value = value.detach().reshape(-1).double()
        finite = torch.isfinite(value) & torch.isfinite(value.float())
        good = finite
        if kind == "binary":
            good = good & (value.eq(0) | value.eq(1))
        elif kind == "multiclass":
            good = good & value.eq(value.floor()) & value.ge(0) & value.lt(classes)
        diagnostics[field + "/nonfinite_or_domain_invalid"] += int((~good).sum())
        return torch.where(good, value, value.new_full((), float("nan"))).float()

    def source_mask(field, size, *, default=False, threshold=False):
        mask = getattr(raw, field, None)
        if mask is None:
            return torch.full((size,), default, dtype=torch.bool)
        if not isinstance(mask, torch.Tensor) or mask.device.type != "cpu" or mask.numel() != size:
            diagnostics[field + "/shape"] += 1
            return torch.zeros(size, dtype=torch.bool)
        mask = mask.detach().reshape(-1)
        # Original descriptor masks use >.5; charge/energy declare binary masks.
        return torch.isfinite(mask) & (mask.gt(.5) if threshold else mask.eq(1))

    record.y = tensor("y", n).view(n, 1)
    record.charge_mask = (source_mask("charge_mask", n, default=isinstance(getattr(raw, "y", None), torch.Tensor))
                          & torch.isfinite(record.y.reshape(-1))).view(n, 1)
    record.rdkit_graph_desc = tensor("rdkit_graph_desc", len(graph_all))
    record.rdkit_graph_desc_mask = (source_mask("rdkit_graph_desc_mask", len(graph_all), threshold=True)
                                   & torch.isfinite(record.rdkit_graph_desc))
    record.rdkit_node_mask = source_mask("rdkit_node_mask", n, threshold=True).view(n, 1)
    for spec in specs:
        values = tensor(spec.field_name, n, kind=spec.task_type, classes=spec.num_classes)
        # -1 remains outside every supported multiclass domain after long cast.
        if spec.task_type == "multiclass":
            values = torch.nan_to_num(values, nan=-1.0).long()
        setattr(record, spec.field_name, values.view(n, 1))
    from phychem_mfm.data.descriptor_schema import BOND_INDEX_FIELD, BOND_ORDER_FIELD, BOND_STATUS_FIELD
    index, order = getattr(raw, BOND_INDEX_FIELD, None), getattr(raw, BOND_ORDER_FIELD, None)
    if (isinstance(index, torch.Tensor) and index.device.type == "cpu" and index.ndim == 2 and index.shape[0] == 2
            and isinstance(order, torch.Tensor) and order.device.type == "cpu" and order.numel() == index.shape[1]):
        index, order = index.detach().double(), order.detach().reshape(-1).double()
        keep = (torch.isfinite(index).all(0) & index.eq(index.floor()).all(0) & index.ge(0).all(0)
                & index.lt(n).all(0) & index[0].ne(index[1]) & torch.isfinite(order)
                & order.eq(order.floor()) & order.ge(1) & order.lt(6))
        diagnostics["bond/invalid_pairs"] += int((~keep).sum())
        setattr(record, BOND_INDEX_FIELD, index[:, keep].long())
        setattr(record, BOND_ORDER_FIELD, order[keep].long())
    else:
        diagnostics["bond/missing_or_shape"] += 1
        setattr(record, BOND_INDEX_FIELD, torch.zeros((2, 0), dtype=torch.long))
        setattr(record, BOND_ORDER_FIELD, torch.zeros(0, dtype=torch.long))
        setattr(record, BOND_STATUS_FIELD, "missing")
    energy = getattr(raw, "energy", None)
    if isinstance(energy, torch.Tensor):
        energy = float(energy) if energy.device.type == "cpu" and energy.numel() == 1 else None
    good_energy = type(energy) in (int, float) and math.isfinite(energy)
    if good_energy:
        good_energy = bool(torch.isfinite(torch.tensor(energy, dtype=torch.float32)))
    record.energy = float(energy) if good_energy else 0.0
    record.energy_mask = source_mask("energy_mask", 1, default=good_energy) & bool(good_energy)
    if type(real_index) is not int or real_index < 0 or normalizer.strict_index is not True or normalizer.normalize_samples is not True:
        raise ValueError("Transport requires exact native real index and strict source normalizer")
    record = normalizer._normalize_item(record, real_index)
    record.energy_mask &= getattr(raw, "energy_unit", None) == "kcal/mol"
    if issues is not None:
        issues.update(diagnostics)
    return record


def observed_values(record):
    import torch
    graph_all, graph_names, specs = task_contract()
    n = len(record.x)
    result = {}
    energy = torch.tensor([record.energy], dtype=torch.float32).double()
    result["energy"] = (energy, record.energy_mask.reshape(-1).bool() & torch.isfinite(energy))
    values = record.y.reshape(-1)
    result["charge"] = (values, record.charge_mask.reshape(-1).bool() & torch.isfinite(values))
    for name in graph_names:
        index = graph_all.index(name)
        values = record.rdkit_graph_desc.reshape(-1)[index:index + 1]
        result["graph/" + name] = (values, record.rdkit_graph_desc_mask.reshape(-1)[index:index + 1].bool() & torch.isfinite(values))
    for spec in specs:
        values = getattr(record, spec.field_name).reshape(-1)
        mask = record.rdkit_node_mask.reshape(-1).bool() & torch.isfinite(values)
        if spec.task_type == "binary":
            mask &= values.eq(0) | values.eq(1)
        elif spec.task_type == "multiclass":
            mask &= values.eq(values.float().floor()) & values.ge(0) & values.lt(spec.num_classes)
        if len(values) != n:
            raise ValueError("Native label shape changed during transport")
        result["node/" + spec.name] = (values, mask)
    return result


def accumulate_statistics(stats, record, observed):
    """Caller-certified training role only; no validation values enter here."""
    import torch
    stats["observed_train_records"] += 1
    stats["observed_train_atoms"] += len(record.x)
    for name in stats["moments"]:
        key = "node/estate_index" if name == "estate_index" else name
        values, mask = observed[key]
        stats["moments"][name] = add_values(stats["moments"][name], values[mask])
    charges, valid = observed["charge"]
    z = record.x.reshape(-1).long() + 1
    for element in z[valid].unique().tolist():
        key = str(element)
        stats["charge_by_element"][key] = add_values(stats["charge_by_element"][key], charges[valid & z.eq(element)])
    for name, counts in stats["categorical_counts"].items():
        values, mask = observed["node/" + name]
        counts.update({str(k): counts.get(str(k), 0) + v for k, v in Counter(values[mask].long().tolist()).items()})
    energy, mask = observed["energy"]
    if bool(mask.any()):
        target = float(energy[0])
        counts = Counter(int(v) for v in z.tolist())
        basis = [(element - 1, count) for element, count in counts.items()] + [(118, 1)]
        reference = stats["energy_linear_reference_sufficient_statistics"]
        reference["count"] += 1
        for i, value in basis:
            reference["xty"][i] += value * target
            for j, other in basis:
                reference["xtx"][i][j] += value * other


def export_estimates(stats):
    result = {name: estimate(row, 1e-6 if name in ("energy", "charge") else 1e-3)
              for name, row in stats["moments"].items()}
    return {"schema_version": ESTIMATOR + "_estimates", "train_only": True,
            "population_variance_denominator": "valid_label_count", "estimates": result,
            "full_train_cap": None, "old_58k_statistics_reused": False,
            "state": "NOT_FROZEN", "formal_eligible": False,
            "empty_tasks_are_unavailable_not_proven_zero_targets": True}
