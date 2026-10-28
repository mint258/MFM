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


# A v2 is opt-in. The v1 functions above keep their original numerical contract.
def a_gradient_contract_v2():
    return {
        "schema": "model_v3_A_gradient_contract_v2",
        "version": "v2",
        "reference": "b=reference; a=candidate",
        "elementwise": {"atol": 1e-8, "rtol": 1e-4,
                        "formula": "abs(a-b)<=atol+rtol*abs(b)", "all_elements": True},
        "analytic_zero": {"both_L2_norm_max": 1e-8,
                          "selection": "verified_active_module_parameter_semantics_not_observed_magnitude",
                          "both_None": "FAIL"},
        "inactive_other_parameters_both_None": "PASS",
        "single_None_names_shape_nonfinite": "FAIL",
        "audit_only_dtype": "float64",
        "forward_relative_L2_max": 1e-5,
        "trajectory_every_point_relative_loss_max": 1e-3,
    }


def a_gradient_contract_sha256_v2():
    import hashlib
    import json
    raw = json.dumps(a_gradient_contract_v2(), sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def compare_gradient_elements(reference, candidate, *, atol, rtol,
                              analytic_zero_names=(), zero_norm_tolerance=1e-8):
    """Pure audit primitive. Scientific v2 calls it only with the fixed constants.

    No gradient, Parameter, RNG, model or optimizer is changed. Inputs are detached
    audit snapshots. A both-None inactive head is legal; the declared ACTIVE
    analytic-zero parameters must actually supply both tensors and both norms.
    """
    for value in (atol, rtol, zero_norm_tolerance):
        if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
            raise ValueError("Finite nonnegative audit tolerances required")
    if set(reference) != set(candidate):
        raise ValueError("Reference/candidate tensor names differ")
    zero_names = tuple(analytic_zero_names)
    if len(set(zero_names)) != len(zero_names) or not set(zero_names) <= set(reference):
        raise ValueError("Exact unique analytic-zero names must exist in both gradient sets")
    rows = []
    for name in sorted(reference):
        left, right = reference[name], candidate[name]
        if any(value is not None and not isinstance(value, torch.Tensor) for value in (left, right)):
            raise ValueError("Gradient snapshots must be floating tensors or None")
        zero = name in zero_names
        row = {"name": name, "analytic_zero": zero, "reference_norm": None,
               "candidate_norm": None, "difference_norm": None, "violating_elements": None,
               "max_absolute": None, "maximum_combined_threshold": None,
               "minimum_combined_threshold": None, "maximum_error_to_threshold": None,
               "reference_shape": None if left is None else list(left.shape),
               "candidate_shape": None if right is None else list(right.shape)}
        if left is None or right is None:
            both_disabled = left is None and right is None
            row.update({"pass": both_disabled and not zero,
                        "reason": "analytic_zero_gradient_missing" if zero and both_disabled
                        else "both_disabled" if both_disabled else "missing_gradient_mismatch"})
            rows.append(row)
            continue
        if not isinstance(left, torch.Tensor) or not isinstance(right, torch.Tensor):
            raise ValueError("Gradient snapshots must be floating tensors or None")
        if not left.is_floating_point() or not right.is_floating_point():
            raise ValueError("Gradient snapshots must have real floating dtype")
        row["shape"] = list(left.shape)
        if left.shape != right.shape:
            row.update({"pass": False, "reason": "shape_mismatch"})
            rows.append(row)
            continue
        left = left.detach().to(device="cpu", dtype=torch.float64)
        right = right.detach().to(device="cpu", dtype=torch.float64)
        finite = bool(torch.isfinite(left).all() and torch.isfinite(right).all())
        row["finite"] = finite
        if not finite:
            row.update({"pass": False, "reason": "nonfinite",
                        "nonfinite_elements": int((~(torch.isfinite(left) & torch.isfinite(right))).sum())})
            rows.append(row)
            continue
        delta = (right - left).abs()
        threshold = float(atol) + float(rtol) * left.abs()
        reference_norm = float(torch.linalg.vector_norm(left))
        candidate_norm = float(torch.linalg.vector_norm(right))
        difference_norm = float(torch.linalg.vector_norm(delta))
        if (not bool(torch.isfinite(delta).all() and torch.isfinite(threshold).all())
                or not math.isfinite(reference_norm) or not math.isfinite(candidate_norm)
                or not math.isfinite(difference_norm)):
            row.update({"pass": False, "reason": "nonfinite_audit"})
            rows.append(row)
            continue
        violating = delta > threshold
        # At zero threshold an unequal element has an unbounded ratio. Keep
        # JSON finite: count it explicitly, with ratio=None rather than inf.
        zero_threshold_failure = bool(((threshold == 0) & (delta != 0)).any())
        ratio = torch.where(threshold > 0, delta / threshold.clamp_min(torch.finfo(torch.float64).tiny),
                            torch.zeros_like(delta))
        row.update({
            "reference_norm": reference_norm, "candidate_norm": candidate_norm,
            "difference_norm": difference_norm,
            "elements": left.numel(), "violating_elements": int(violating.sum()),
            "max_absolute": float(delta.max()) if delta.numel() else 0.,
            "maximum_combined_threshold": float(threshold.max()) if threshold.numel() else 0.,
            "minimum_combined_threshold": float(threshold.min()) if threshold.numel() else 0.,
            "maximum_error_to_threshold": None if zero_threshold_failure
                else float(ratio.max()) if ratio.numel() else 0.,
            "zero_threshold_failure": zero_threshold_failure,
            "elementwise_pass": not bool(violating.any()),
        })
        zero_pass = not zero or (reference_norm <= zero_norm_tolerance
                                 and candidate_norm <= zero_norm_tolerance)
        row["analytic_zero_norm_pass"] = zero_pass if zero else None
        row["pass"] = row["elementwise_pass"] and zero_pass
        row["reason"] = "PASS" if row["pass"] else "elementwise_and_zero_norm" if (
            not row["elementwise_pass"] and not zero_pass) else "elementwise" if not row["elementwise_pass"] else "analytic_zero_norm"
        rows.append(row)
    return {"pass": all(row["pass"] for row in rows), "atol": atol, "rtol": rtol,
            "reference": "b=reference", "zero_norm_tolerance": zero_norm_tolerance,
            "analytic_zero_names": list(zero_names), "tensors": rows}


def compare_gradients_v2(reference, candidate, *, analytic_zero_names):
    result = compare_gradient_elements(reference, candidate, atol=1e-8, rtol=1e-4,
        analytic_zero_names=analytic_zero_names, zero_norm_tolerance=1e-8)
    return {**result, "acceptance_version": "v2",
            "semantic_contract_sha256": a_gradient_contract_sha256_v2()}


def analytic_zero_gradient_parameters(model, *, expected_layers=6):
    """Identify the active per-head common-logit biases from actual modules.

    For a valid query/head, final bias c_h adds the SAME real constant to all
    valid-key logits: exp(z_j+c_h)/sum_k exp(z_k+c_h) = softmax(z)_j.
    This is a masked-domain real-formula identity, NOT a claim of exactly zero
    IEEE backward residual. The existing finite -1e9 mask is not changed.
    """
    from ..model.attention import DenseGeoSelfAttention, RealCoordTransformerLayer
    from ..model.backbone import RealCoordTransformerBackbone
    from ..model.common import Linear
    from ..model.v3_performance import RuntimeDenseAttention, ConfigurableTiledDistanceMLP
    from ..model.v3_logical_batch import LogicalBatchBackbone
    from s_model_memory_v1 import TiledDistanceMLP

    backbone = getattr(model, "backbone", None)
    if type(expected_layers) is not int or expected_layers != 6:
        raise ValueError("The registered active analytic-zero cohort has exactly six layers")
    if type(backbone) not in (RealCoordTransformerBackbone, LogicalBatchBackbone):
        raise ValueError("Unregistered backbone semantics for analytic-zero gradients")
    if len(backbone.layers) != expected_layers:
        raise ValueError("All six actual attention layers must be present")
    parameters = dict(model.named_parameters())
    rows = []
    for index, layer in enumerate(backbone.layers):
        attention = getattr(layer, "attn", None)
        if (type(layer) is not RealCoordTransformerLayer
                or type(attention) not in (DenseGeoSelfAttention, RuntimeDenseAttention)
                or "forward" in attention.__dict__):
            raise ValueError("Unregistered attention forward semantics for analytic-zero bias")
        if attention.use_dist_bias is not True or attention.use_radius_mask is not False:
            raise ValueError("Registered common-bias proof requires original global distance-bias attention")
        mlp = attention.dist_mlp
        if (type(mlp) not in (torch.nn.Sequential, TiledDistanceMLP, ConfigurableTiledDistanceMLP)
                or len(mlp) != 3 or type(mlp[0]) is not Linear
                or type(mlp[1]) is not torch.nn.SiLU or type(mlp[2]) is not Linear
                or "forward" in mlp.__dict__ or "forward" in mlp[2].__dict__):
            raise ValueError("Exact scalar-distance Linear/SiLU/head-Linear semantics required")
        final = mlp[2]
        name = f"backbone.layers.{index}.attn.dist_mlp.2.bias"
        if (mlp[0].in_features != 1 or mlp[0].out_features != attention.dim
                or final.in_features != attention.dim or final.out_features != attention.nheads
                or final.bias is None or tuple(final.bias.shape) != (attention.nheads,)
                or parameters.get(name) is not final.bias or not final.bias.requires_grad
                or final.bias.dtype != torch.float32):
            raise ValueError("Active per-head bias Parameter identity/name/shape/dtype differs")
        rows.append({
            "name": name, "shape": list(final.bias.shape), "heads": attention.nheads,
            "dimension": attention.dim, "parameter_identity_checked": True,
            "attention_class": type(attention).__module__ + "." + type(attention).__qualname__,
            "distance_mlp_class": type(mlp).__module__ + "." + type(mlp).__qualname__,
            "final_projection_class": type(final).__module__ + "." + type(final).__qualname__,
            "proof": "one real common logit constant per head before valid-key softmax",
            "mask": "original finite_-1e9 overwrite preserved; proof refers to valid-key domain",
            "exact_IEEE_zero_claimed": False,
        })
    expected = {f"backbone.layers.{i}.attn.dist_mlp.2.bias" for i in range(expected_layers)}
    actual = {name for name in parameters if name.endswith(".attn.dist_mlp.2.bias")}
    if actual != expected or {row["name"] for row in rows} != expected:
        raise ValueError("Complete exact six-Parameter analytic-zero set required")
    return rows
