"""TRAIN-only filtering and new-field statistics for the frozen D taskbook.

Missing placeholders and numerical failures have independent masks.  Existing
D20/D3 normalization objects are returned unchanged, never fitted here.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


L1_DISABLED = frozenset(("NumBridgeheadAtoms", "NumSpiroAtoms", "MolMR"))
D20_SHARED_NAMES = frozenset((
    "MolLogP", "MolMR", "TPSA", "LabuteASA", "ExactMolWt",
    "NumValenceElectrons", "HeavyAtomCount", "NumHeteroatoms", "NumHAcceptors",
    "NumHDonors", "FractionCSP3", "RingCount", "NumAromaticRings",
    "NumAliphaticRings", "NumSaturatedRings", "NumHeterocycles",
    "NumBridgeheadAtoms", "NumSpiroAtoms", "BertzCT", "HallKierAlpha",
))


def winsorized_parameters(values: np.ndarray) -> dict:
    """Exact linear/type-7 quantiles and population moments of finite F64 data."""
    values = np.asarray(values, dtype=np.float64)
    if values.ndim != 1 or not values.size or not np.isfinite(values).all():
        raise ValueError("FINITE_NONEMPTY_ONE_DIMENSIONAL_VALUES_REQUIRED")
    low, high = np.quantile(values, (0.001, 0.999), method="linear")
    winsorized = np.clip(values, low, high)
    mean = np.mean(winsorized, dtype=np.float64)
    std = np.std(winsorized, ddof=0, dtype=np.float64)
    if not np.isfinite((low, high, mean, std)).all():
        raise ValueError("F64_NORMALIZATION_OVERFLOW")
    return {
        "fit_role": "TRAIN",
        "valid_values": int(values.size),
        "q001": float(low),
        "q999": float(high),
        "quantile_method": "linear type-7",
        "mean": float(mean),
        "std_population": float(std),
        "ddof": 0,
        "stored_targets_clipped": False,
    }


def _location_scale(parameters: Mapping) -> tuple[float, float]:
    def choose(keys):
        for key in keys:
            if key in parameters:
                return float(parameters[key])
        raise ValueError("EXISTING_NORMALIZATION_LOCATION_SCALE_REQUIRED")

    mean = choose(("mean", "location", "center"))
    std = choose(("std_population", "std_ddof0", "std", "scale"))
    if not np.isfinite((mean, std)).all() or std < 0:
        raise ValueError("INVALID_NORMALIZATION_LOCATION_SCALE")
    return mean, std


def _boolean_mask(value, shape, name):
    result = np.asarray(value)
    if result.dtype != np.dtype(bool) or result.shape != shape:
        raise ValueError(name + "_BOOLEAN_SHAPE_REQUIRED")
    return result


def summarize_library(
    values,
    observed_valid,
    numeric_nonfinite,
    numeric_overflow,
    *,
    field_names: Sequence[str],
    library: str,
    roles: Sequence[str],
    existing_parameters: Mapping[str, Mapping] | None = None,
) -> dict:
    """Filter one ordered library and fit only retained, genuinely new fields.

    ``values`` is [molecules, fields] F64. Missing values may use NaN storage,
    but only explicit numerical-event masks (or a nonfinite observed value)
    trigger the nonfinite/overflow exclusion. All roles must be TRAIN; callers
    must select TRAIN before invoking this function.

    For L1, the caller supplies existing D20 parameters by matching field name.
    D3/D20 libraries also support explicit existing parameters. L2 does not map
    names across libraries and rejects nonempty ``existing_parameters``.
    Existing parameter objects are preserved by identity and contents.
    """
    raw = np.asarray(values)
    if raw.dtype != np.dtype(np.float64) or raw.ndim != 2 or not raw.shape[0]:
        raise ValueError("NONEMPTY_F64_MATRIX_REQUIRED")
    names = list(field_names)
    if (len(names) != raw.shape[1] or len(set(names)) != len(names)
            or any(not isinstance(name, str) or not name for name in names)):
        raise ValueError("UNIQUE_ORDERED_FIELD_NAMES_REQUIRED")
    roles = list(roles)
    if len(roles) != raw.shape[0] or any(role != "TRAIN" for role in roles):
        raise ValueError("TRAIN_ONLY_STATISTICS_REQUIRED")
    if library not in ("L1", "L2", "D20", "D3"):
        raise ValueError("UNKNOWN_DESCRIPTOR_LIBRARY")
    existing = {} if existing_parameters is None else existing_parameters
    if library == "L2" and existing:
        raise ValueError("L2_CROSS_LIBRARY_NORMALIZATION_MAPPING_FORBIDDEN")
    observed = _boolean_mask(observed_valid, raw.shape, "OBSERVED_VALID")
    nonfinite = _boolean_mask(numeric_nonfinite, raw.shape, "NUMERIC_NONFINITE")
    overflow = _boolean_mask(numeric_overflow, raw.shape, "NUMERIC_OVERFLOW")
    finite = np.isfinite(raw)
    valid = observed & finite & ~nonfinite & ~overflow
    fields = []
    for column, name in enumerate(names):
        selected = raw[valid[:, column], column]
        count = selected.size
        reasons = []
        nonfinite_count = int(np.count_nonzero(
            nonfinite[:, column] | (observed[:, column] & ~finite[:, column])))
        overflow_count = int(np.count_nonzero(overflow[:, column]))
        if nonfinite_count:
            reasons.append("nonfinite_numeric_event")
        if overflow_count:
            reasons.append("numeric_overflow_event")
        # An integer comparison preserves the exact 95% boundary.
        if 100 * count < 95 * raw.shape[0]:
            reasons.append("valid_fraction_below_0.95")
        constant = bool(count and np.all(selected == selected[0]))
        if constant:
            reasons.append("finite_constant")
        if library == "L1" and name in L1_DISABLED:
            reasons.append("inherited_D20_loss_disabled")
        inherited = name in existing
        original_field = library in ("D20", "D3") or (
            library == "L1" and name in D20_SHARED_NAMES)
        if original_field and not inherited and not reasons:
            raise ValueError("EXISTING_D20_D3_PARAMETERS_REQUIRED:" + name)
        parameters = existing[name] if inherited else (
            winsorized_parameters(selected) if not reasons else None)
        clip_fraction = None
        clip_count = None
        normalization_status = "NOT_USED_FILTERED"
        if parameters is not None:
            mean, std = _location_scale(parameters)
            if std == 0:
                normalization_status = "ZERO_SCALE_NOT_DIVIDABLE"
            else:
                # Compare in raw space: avoids standardization overflow and
                # does not modify stored values or refit existing parameters.
                with np.errstate(over="ignore", invalid="ignore"):
                    clipped = np.abs(selected - mean) > 6.0 * std
                clip_count = int(np.count_nonzero(clipped))
                clip_fraction = clip_count / count if count else None
                normalization_status = "REUSED_UNCHANGED" if inherited else "FITTED_TRAIN_ONCE"
        fields.append({
            "name": name,
            "enabled": not reasons,
            "removal_reasons": reasons,
            "train_molecules": int(raw.shape[0]),
            "valid_values": int(count),
            "valid_fraction": count / raw.shape[0],
            "true_zero_count": int(np.count_nonzero(selected == 0)),
            "missing_count": int(np.count_nonzero(~observed[:, column]
                & ~nonfinite[:, column] & ~overflow[:, column])),
            "nonfinite_numeric_events": nonfinite_count,
            "overflow_events": overflow_count,
            "finite_constant": constant,
            "parameters": parameters,
            "normalization_status": normalization_status,
            "train_loss_abs_standardized_gt6_count": clip_count,
            "train_loss_abs_standardized_gt6_fraction": clip_fraction,
        })
    return {
        "library": library,
        "fit_role": "TRAIN",
        "field_order": names,
        "enabled_field_order": [field["name"] for field in fields if field["enabled"]],
        "fields": fields,
        "stored_targets_clipped": False,
    }
