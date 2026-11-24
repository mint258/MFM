"""Prepare only the taskbook's cold seed0 confirmations after recipe freeze.

Pure configuration planning: no files, weights, feature tensors, fitting or job
submission. The scheduler must bind and admit new runtime resources before use.
"""
from copy import deepcopy
from pathlib import Path

from .training import ARMS, prepare_runtime


_EXECUTION_KEYS = (
    "resume", "resume_samples", "resume_from_output", "attempt", "handoff_request",
    "handoff_ack", "required_gpu_uuid", "recovery_reason", "replaces_run",
    "source_last_samples", "rollback_samples", "infrastructure_continuation",
    "seed0_run", "diagnostic_feature_root", "checkpoint", "features",
    "persist_features", "recipe_preparation_only", "node", "local_node",
    "gpu_uuid", "execution", "local_storage", "storage_peak_bytes",
    "share_storage_peak_bytes", "root_joint_future_bytes", "lustre_other_future_bytes",
    "output_filesystem", "model_budget_root", "storage_forecast_basis",
    "minimum_free_gpu_mib", "cleanup_seconds", "speed_calibration",
    "calibration_training", "benchmark_updates", "speed_board",
)


def _screening(parent):
    if (parent.get("condition") != "D" or parent.get("arm") not in ARMS
            or parent["arm"].startswith("9M-") or parent.get("seed") != 0
            or parent.get("samples") != 3_000_000):
        raise ValueError("Confirmation uses a registered seed0 3M D condition")
    return prepare_runtime(parent)


def _cold(parent, arm, *, output_root, run_prefix, retain_h0):
    c = deepcopy(parent)
    for key in _EXECUTION_KEYS:
        c.pop(key, None)
    c.update(arm=arm, run=run_prefix + arm.replace("-", "_") + "_seed0",
        seed=0, samples=9_000_000, round=0, stage=4,
        output=str(Path(output_root) / arm / "training"),
        evaluation_samples=[9_000_000], statistics_backend="slurm_cpu",
        persist_final_features=retain_h0, resource_admission_pending=True,
        confirmation_source_run=parent["run"])
    # A cold run measures its own window; no fitted screening state survives.
    c["clip_calibration"] = dict(calibration_samples=150000,
        window_start_samples=60000, initial_clip=281.7, quantile=.99,
        sample_axis="optimizer_step_start")
    binding = c["d_recipe"].setdefault("scientific_binding", {})
    for key in ("arm", "seed", "samples"):
        binding.pop(key, None)
    return prepare_runtime(c)


def plan_confirmation(best, baseline, selected=None, *, output_root, run_prefix):
    """Return R0 always, and final only when it differs; no seed1 confirmation.

    Selected is the final scientific configuration frozen after all gates,
    including any adopted mask or 3D decision. No recipe selection happens here.
    Existing TRAIN parameters and all model settings stay unchanged.
    Output resources and target hardware are deliberately unbound in this plan.
    """
    if best.get("status") != "FROZEN" or best.get("recipe_frozen") is not True:
        raise ValueError("All D decisions and the final recipe freeze precede confirmation")
    baseline = _screening(baseline)
    if (baseline["arm"] != "D-R0" or baseline.get("components")
            or not baseline["d_recipe"].get("include_3d", True)
            or baseline["d_recipe"].get("graph_mask_enabled", False)):
        raise ValueError("The confirmation baseline is the original D-R0 condition")
    if best.get("arm") == "D-R0":
        selected = baseline
    elif selected is None:
        raise ValueError("The frozen selected scientific configuration is required")
    else:
        selected = _screening(selected)
    if (selected["arm"] != best.get("arm")
            or selected["d_recipe"]["library"] != best.get("library")):
        raise ValueError("Selected condition differs from the frozen D recipe")
    if "components" in best and set(selected.get("components", ())) != set(best["components"]):
        raise ValueError("Selected components differ from the frozen D recipe")
    same = best["arm"] == "D-R0"
    configurations = [_cold(baseline, "9M-D-R0", output_root=output_root,
        run_prefix=run_prefix, retain_h0=same)]
    if not same:
        configurations.append(_cold(selected, "9M-D-final", output_root=output_root,
            run_prefix=run_prefix, retain_h0=True))
    return dict(schema="D_COLD_CONFIRMATION_PLAN_V1",
        status="SCIENTIFIC_CONFIGURATIONS_REQUIRE_RUNTIME_RESOURCE_ADMISSION",
        frozen_arm=best["arm"], frozen_library=best["library"],
        selected_readout_arm="9M-D-R0" if same else "9M-D-final",
        configurations=configurations, jobs_submitted=False)
