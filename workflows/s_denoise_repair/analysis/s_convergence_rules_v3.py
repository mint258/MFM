"""Predeclared directional convergence rules; no epoch extrapolation."""
from __future__ import annotations

import math


S_RULES = {
    "noise_mse_normalized": ("lower", "relative", 0.02),
    "local_rmse_A": ("lower", "relative", 0.02),
    "masked_element_nll": ("lower", "relative", 0.02),
    "bond_order_accuracy": ("higher", "absolute", 0.001),
}


def seed_pair(values):
    if values is None or len(values) != 2 or any(v is None for v in values):
        return None
    values = [float(v) for v in values]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Non-finite seed metric")
    return {"values": values, "mean": sum(values) / 2.0, "spread": abs(values[0] - values[1])}


def task_comparison(name, B1, B3):
    direction, comparison, threshold = S_RULES[name]
    a, b = seed_pair(B1), seed_pair(B3)
    if a is None or b is None:
        return {"metric": name, "status": "MISSING", "converged_under_rule": None}
    if any(v < 0 for v in a["values"] + b["values"]):
        raise ValueError("Physical S metric must be nonnegative")
    if name == "bond_order_accuracy" and any(v > 1 for v in a["values"] + b["values"]):
        raise ValueError("Accuracy must be within [0,1]")
    improvement = (a["mean"] - b["mean"]) if direction == "lower" else (b["mean"] - a["mean"])
    if comparison == "relative":
        value = improvement / a["mean"] if a["mean"] else (0.0 if improvement <= 0 else math.inf)
    else:
        value = improvement
    return {"metric": name, "status": "EVALUATED", "B1": a, "B3": b,
            "B3_improvement_original_units": improvement, "comparison_value": value,
            "comparison": comparison, "strict_threshold": threshold,
            "converged_under_rule": value < threshold,
            "interpretation": "B3 improvements only; worse B3 passes the no-improvement rule"}


def probe_comparison(identifier, B1, B3, *, higher_is_better, primary=True, category="unspecified"):
    a, b = seed_pair(B1), seed_pair(B3)
    if a is None or b is None:
        return {"id": identifier, "status": "MISSING", "primary": primary, "category": category, "unconverged": None}
    improvement = b["mean"] - a["mean"] if higher_is_better else a["mean"] - b["mean"]
    unconverged = improvement > 0 and improvement > a["spread"] and improvement > b["spread"]
    return {"id": identifier, "status": "EVALUATED", "primary": primary, "category": category,
            "B1": a, "B3": b, "higher_is_better": bool(higher_is_better),
            "B3_improvement_original_units": improvement, "unconverged": unconverged,
            "statistical_significance_claimed": False}


def joint_judgment(s_comparisons, probe_comparisons, *, expected_primary=32):
    if set(row["metric"] for row in s_comparisons) != set(S_RULES):
        raise ValueError("Exactly four predefined S metrics are required")
    primary = [row for row in probe_comparisons if row["primary"]]
    if len({row["id"] for row in primary}) != len(primary) or len(primary) != expected_primary:
        raise ValueError("Primary tasks must have unique IDs and the frozen count")
    failed_s = [row["metric"] for row in s_comparisons if row["converged_under_rule"] is False]
    failed_probes = [row["id"] for row in primary if row["unconverged"] is True]
    missing = any(row["converged_under_rule"] is None for row in s_comparisons) or any(row["unconverged"] is None for row in primary)
    if failed_s or failed_probes:
        status = "ONE_EPOCH_INSUFFICIENT_UNDER_V3_DIRECTIONAL_RULE"
    elif missing:
        status = "NOT_YET_EVALUABLE"
    else:
        status = "ONE_EPOCH_SUFFICIENT_UNDER_V3_DIRECTIONAL_RULE"
    return {"status": status, "S_metrics_with_material_B3_improvement": failed_s,
            "primary_probes_with_material_B3_improvement": failed_probes,
            "unconverged_primary_probe_count": len(failed_probes), "missing_metrics_present": missing,
            "required_epoch_count_extrapolated": False,
            "scope": "B1 one epoch versus B3 three epochs, means of two seeds each; no proof about untrained later epochs"}
