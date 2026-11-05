"""Preregistered numerical gates, separate from implementation and speed claims."""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import math
from typing import Mapping

import torch


def floating_outputs(value, prefix="output"):
    """Retain every floating model output, including empty prediction tensors."""
    result = {}
    if isinstance(value, torch.Tensor):
        if value.is_floating_point():
            result[prefix] = value.detach().cpu().clone()
    elif is_dataclass(value):
        for field in fields(value):
            result.update(floating_outputs(getattr(value, field.name), prefix + "/" + field.name))
    elif isinstance(value, Mapping):
        for name, item in value.items():
            result.update(floating_outputs(item, prefix + "/" + str(name)))
    elif isinstance(value, (tuple, list)):
        for index, item in enumerate(value):
            result.update(floating_outputs(item, prefix + "/" + str(index)))
    return result


def gradients(model):
    return {name: None if parameter.grad is None else parameter.grad.detach().cpu().clone()
            for name, parameter in model.named_parameters()}


def compare_tensors(reference, candidate, *, tolerance):
    if set(reference) != set(candidate):
        raise ValueError("Reference/candidate tensor names differ")
    rows = []
    for name in sorted(reference):
        left, right = reference[name], candidate[name]
        if left is None or right is None:
            rows.append({"name": name, "pass": left is None and right is None,
                         "reason": "both_disabled" if left is right else "missing_gradient_mismatch"})
            continue
        if left.shape != right.shape:
            rows.append({"name": name, "pass": False, "reason": "shape_mismatch"})
            continue
        if not bool(torch.isfinite(left).all() and torch.isfinite(right).all()):
            rows.append({"name": name, "pass": False, "reason": "nonfinite"})
            continue
        # Accumulate the audit in fp64 to avoid losing small differences in the gate itself.
        left, right = left.double(), right.double()
        difference = right - left
        relative = float(torch.linalg.vector_norm(difference) / torch.linalg.vector_norm(left).clamp_min(1e-12))
        rows.append({"name": name, "relative_l2": relative,
                     "max_absolute": float(difference.abs().max()) if difference.numel() else 0.,
                     "pass": relative <= tolerance})
    return {"pass": all(row["pass"] for row in rows), "tolerance": tolerance, "tensors": rows}


def a_equivalence_report(reference_outputs, candidate_outputs, reference_gradients, candidate_gradients,
                         *, expected_batches=20):
    sequences = (reference_outputs, candidate_outputs, reference_gradients, candidate_gradients)
    if any(len(rows) != expected_batches for rows in sequences):
        raise ValueError("Exactly the preregistered fixed batch count is required")
    rows = []
    for index, (left, right, lg, rg) in enumerate(zip(*sequences)):
        forward = compare_tensors(left, right, tolerance=1e-5)
        gradient = compare_tensors(lg, rg, tolerance=1e-4)
        rows.append({"batch": index, "forward": forward, "gradient": gradient,
                     "pass": forward["pass"] and gradient["pass"]})
    return {"gate": "A_fixed_batch_equivalence", "batches": expected_batches,
            "pass": all(row["pass"] for row in rows), "results": rows}


def trajectory_report(reference, candidate, *, expected_updates=500):
    if set(reference) != set(candidate) or set(reference) != set(range(1, expected_updates + 1)):
        raise ValueError("Both runs must contain every preregistered optimizer update exactly once")
    rows = []
    for step in range(1, expected_updates + 1):
        left, right = float(reference[step]), float(candidate[step])
        finite = math.isfinite(left) and math.isfinite(right)
        relative = abs(right - left) / max(abs(left), 1e-12) if finite else None
        rows.append({"step": step, "relative_difference": relative,
                     "pass": finite and relative <= 1e-3})
    return {"gate": "A_500_update_loss_trajectory", "updates": expected_updates,
            "pass": all(row["pass"] for row in rows), "results": rows}


def bf16_curve_report(fp32_runs, bf16_runs, *, validation_updates, denoise_metric,
                      required_updates=20000):
    """Each bf16 seed must lie inside the fp32 two-seed envelope at every point.

    Run dictionaries have seed, optimizer_updates and validation (update ->
    metric mapping). Callers must independently verify matching data/model/run
    provenance; this routine only evaluates already bound numeric curves.
    """
    if len(fp32_runs) != 2 or len(bf16_runs) != 2:
        raise ValueError("Two actual pretraining seeds are required for each precision")
    if len({row["seed"] for row in fp32_runs}) != 2 or {row["seed"] for row in fp32_runs} != {row["seed"] for row in bf16_runs}:
        raise ValueError("Distinct paired pretraining seeds required")
    if any(row["optimizer_updates"] != required_updates for row in (*fp32_runs, *bf16_runs)):
        raise ValueError("All four precision runs must reach the exact registered endpoint")
    grid = tuple(int(value) for value in validation_updates)
    if not grid or len(set(grid)) != len(grid) or max(grid) != required_updates:
        raise ValueError("Explicit unique validation grid including the final endpoint required")
    if any(set(row["validation"]) != set(grid) for row in (*fp32_runs, *bf16_runs)):
        raise ValueError("Every run must have the same complete validation grid")
    rows = []
    for update in grid:
        field_sets = [set(run["validation"][update]) for run in (*fp32_runs, *bf16_runs)]
        if not field_sets[0] or any(names != field_sets[0] for names in field_sets) or denoise_metric not in field_sets[0]:
            raise ValueError("Identical nonempty validation fields including denoising RMSE required")
        for name in sorted(field_sets[0]):
            baseline = [float(run["validation"][update][name]) for run in fp32_runs]
            for run in bf16_runs:
                value = float(run["validation"][update][name])
                finite = all(math.isfinite(item) for item in (*baseline, value))
                low, high = min(baseline), max(baseline)
                within = finite and low <= value <= high
                paired = next(item for item in fp32_runs if item["seed"] == run["seed"])
                paired_value = float(paired["validation"][update][name])
                difference = abs(value - paired_value) / max(abs(paired_value), 1e-12) if finite else None
                rmse_pass = name != denoise_metric or finite and difference <= .02
                rows.append({"update": update, "metric": name, "bf16_seed": run["seed"],
                             "fp32_low": low if finite else None, "fp32_high": high if finite else None,
                             "bf16_value": value if finite else None, "within_fp32_seed_envelope": within,
                             "paired_fp32_value": paired_value if finite else None,
                             "relative_to_paired_fp32": difference, "denoising_2_percent": rmse_pass,
                             "pass": within and rmse_pass})
    return {"gate": "B_bf16_two_seed_validation", "required_updates": required_updates,
            "pass": all(row["pass"] for row in rows), "results": rows}
