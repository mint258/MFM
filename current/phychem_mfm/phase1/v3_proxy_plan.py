"""Reviewable experiment dependencies; this module never submits or trains.

These are model-owned plans, not a data-line format or an executable training
configuration. Selection gates remain unresolved until independent evidence
exists. A different seed is a new run, never a retry of a failed attempt.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import hashlib
import json
import math
import re


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class Evidence:
    path: str
    sha256: str

    def __post_init__(self):
        if not self.path or not re.fullmatch(r"[a-f0-9]{64}", self.sha256):
            raise ValueError("Explicit evidence path and SHA256 required")


@dataclass(frozen=True)
class PlannedTrial:
    name: str
    stage: int
    condition: str
    pretraining_seed: int
    sample_budget: int
    parameters: tuple[tuple[str, object], ...]
    requires: tuple[str, ...]

    def __post_init__(self):
        if (not re.fullmatch(r"[A-Za-z0-9_-]{1,96}", self.name)
                or self.stage not in (5, 6) or self.condition not in ("S", "P", "D", "SDP")
                or type(self.pretraining_seed) is not int or self.pretraining_seed < 0
                or type(self.sample_budget) is not int or self.sample_budget <= 0):
            raise ValueError("Bounded trial identity, condition, seed and sample budget required")
        keys = [key for key, _ in self.parameters]
        if len(keys) != len(set(keys)) or tuple(sorted(self.parameters)) != self.parameters:
            raise ValueError("Unique, sorted parameter names required")
        if len(self.requires) != len(set(self.requires)):
            raise ValueError("Dependency identities must be unique")
        canonical_sha(asdict(self))

    @property
    def scientific_identity(self):
        # A repeat must keep every scientific parameter and budget; bookkeeping
        # identity/seed are excluded explicitly rather than deleting arbitrary
        # request keys that might contain scientifically relevant settings.
        return canonical_sha({"stage": self.stage, "condition": self.condition,
            "sample_budget": self.sample_budget, "parameters": self.parameters})


COMMON = ("data_line_D1_D2_D3_D4_D5_bound", "proxy_budget_plateau_confirmed",
          "performance_and_capacity_accepted", "panel_and_decision_rules_preregistered")


def _trial(name, stage, condition, budget, parameters, requires=COMMON):
    return PlannedTrial(name, stage, condition, 0, budget,
                        tuple(sorted(parameters.items())), tuple(requires))


def architecture_plan(*, sample_budget, batch_base_samples, budget_evidence: Evidence,
                      rules_evidence: Evidence):
    """Six C1, four C3, nine H and one pooling run; repeats are adaptive."""
    if type(batch_base_samples) is not int or batch_base_samples <= 0:
        raise ValueError("Explicit positive B0 in base molecule draws required")
    common = {"num_layers": 6, "embedding_dim": 512, "denoising_head": "A4",
        "distance_bias_projection_bias": False,
        "geometry": "PM7", "conformers": "all_authorized_D5",
        "proxy_molecules": 240000, "batch_base_samples": batch_base_samples,
        "learning_rate": 3e-4, "adamw_betas": [0.9, 0.95], "clip_norm": 1.0,
        "schedule": "cosine", "warmup_fraction": .02,
        "budget_evidence": asdict(budget_evidence), "rules_evidence": asdict(rules_evidence)}
    trials = []
    for candidate in ("C1-0", "C1-a", "C1-b"):
        for condition in ("S", "P"):
            trials.append(_trial(f"C1_{candidate[3:]}_{condition}", 5, condition, sample_budget,
                {**common, "distance_bias": candidate, "views": 3,
                 "head": "preregistered_common_head", "pooling": "registry_fixed"}))
    for views in (2, 3):
        for condition in ("S", "SDP"):
            trials.append(_trial(f"C3_v{views}_{condition}", 5, condition, sample_budget,
                {**common, "distance_bias": "$selected_C1", "views": views,
                 "head": "preregistered_common_head", "pooling": "registry_fixed"},
                (*COMMON, "C1_selection_closed")))
    for head in ("H1", "H2", "H3"):
        for condition in ("P", "D", "SDP"):
            trials.append(_trial(f"H_{head}_{condition}", 5, condition, sample_budget,
                {**common, "distance_bias": "$selected_C1", "views": "$selected_C3",
                 "head": head, "pooling": "registry_fixed"},
                (*COMMON, "C1_selection_closed", "C3_selection_closed")))
    trials.append(_trial("H_H1_P_learned_pooling", 5, "P", sample_budget,
        {**common, "distance_bias": "$selected_C1", "views": "$selected_C3",
         "head": "H1", "pooling": "learned_mixer"},
        (*COMMON, "C1_selection_closed", "C3_selection_closed")))
    return tuple(trials)


def recipe_plan(*, sample_budget, batch_base_samples, selected_backbone: Evidence,
                budget_evidence: Evidence, rules_evidence: Evidence):
    """Ten LR, four doubled-batch, four schedule and one SDP confirmation."""
    if type(batch_base_samples) is not int or batch_base_samples <= 0:
        raise ValueError("Explicit positive B0 required")
    shared = {"num_layers": 6, "embedding_dim": 512,
        "selected_backbone": asdict(selected_backbone), "geometry": "PM7",
        "conformers": "all_authorized_D5", "proxy_molecules": 240000,
        "budget_evidence": asdict(budget_evidence), "rules_evidence": asdict(rules_evidence)}
    deps = (*COMMON, "architecture_and_heads_selected")
    trials = []
    for lr in (1e-4, 3e-4, 6e-4, 1e-3, 2e-3):
        for condition in ("S", "P"):
            trials.append(_trial(f"LR_{lr:.0e}_{condition}".replace("-", "m"), 6, condition,
                sample_budget, {**shared, "learning_rate": lr, "batch_base_samples": batch_base_samples,
                                "schedule": "cosine"}, deps))
    for rank in (1, 2):
        for condition in ("S", "P"):
            trials.append(_trial(f"B2_lr_rank{rank}_{condition}", 6, condition, sample_budget,
                {**shared, "learning_rate": f"$top_two_LR_rank{rank}",
                 "batch_base_samples": 2*batch_base_samples, "schedule": "cosine"},
                (*deps, "LR_first_scan_closed")))
    for schedule in ("cosine", "WSD"):
        for condition in ("S", "P"):
            trials.append(_trial(f"Schedule_{schedule}_{condition}", 6, condition, sample_budget,
                {**shared, "learning_rate": "$common_selected_LR", "batch_base_samples": "$selected_batch",
                 "schedule": schedule}, (*deps, "LR_and_batch_consensus_closed", "schedule_policy_preregistered")))
    trials.append(_trial("SDP_recipe_confirmation", 6, "SDP", sample_budget,
        {**shared, "learning_rate": "$common_selected_LR", "batch_base_samples": "$selected_batch",
         "schedule": "$selected_schedule", "clip_norm": "$TRAIN_preclip_p99"},
        (*deps, "LR_and_batch_consensus_closed", "schedule_selection_closed", "TRAIN_preclip_p99_closed")))
    return tuple(trials)


def second_seed(trials, *, selected_names, selection_evidence: Evidence):
    """Materialize exactly two selected repeats, preserving scientific identity."""
    if len(selected_names) != 2 or len(set(selected_names)) != 2:
        raise ValueError("Exactly two distinct top configurations must be bound by selection evidence")
    indexed = {trial.name: trial for trial in trials}
    if len(indexed) != len(trials):
        raise ValueError("Trial names must be unique")
    repeated = []
    for name in selected_names:
        if name not in indexed or indexed[name].pretraining_seed != 0:
            raise ValueError("Repeat a registered first-seed configuration")
        trial = indexed[name]
        # Evidence is carried separately so it does not change the scientific
        # identity relative to seed0.
        repeated.append({"trial": asdict(replace(trial, name=name+"_seed1", pretraining_seed=1)),
            "first_seed_scientific_identity": trial.scientific_identity,
            "selection_evidence": asdict(selection_evidence)})
    return tuple(repeated)


def plan_document(trials, *, public_preregistration_sha):
    if not re.fullmatch(r"[a-f0-9]{40}", public_preregistration_sha):
        raise ValueError("Actual full public preregistration commit required")
    names = [trial.name for trial in trials]
    if not names or len(set(names)) != len(names):
        raise ValueError("A nonempty unique plan required")
    return {"schema": "model_v3_symbolic_proxy_plan_v1", "status": "NOT_ADMITTED",
        "public_preregistration_sha": public_preregistration_sha,
        "trial_count": len(trials), "trials": [asdict(trial) for trial in trials],
        "plan_sha256": canonical_sha([asdict(trial) for trial in trials]),
        "starts_training": False, "provides_data_line_authority": False,
        "requires_separate_source_bound_runner": True,
        "adaptive_repeats_are_additional_trials": True}


def stage_gpu_budget(*, stage, allocated_gpu_job_seconds, all_costs_registered):
    """Failed attempts count; allocation time is not measured GPU utilization."""
    if (stage not in (5, 6) or type(allocated_gpu_job_seconds) not in (float, int)
            or not math.isfinite(allocated_gpu_job_seconds) or allocated_gpu_job_seconds < 0):
        raise ValueError("Finite nonnegative registered stage allocation time required")
    estimate_upper_hours = {5: 150, 6: 250}[stage]
    limit = 2 * estimate_upper_hours * 3600
    return {"stage": stage, "allocated_gpu_job_seconds": allocated_gpu_job_seconds,
        "estimated_upper_GPU_hours": estimate_upper_hours, "twice_estimate_seconds": limit,
        "all_failed_attempts_included": all_costs_registered is True,
        "status": ("INCOMPLETE_ACCOUNTING" if all_costs_registered is not True else
                   "STOP_REPORT_USER" if allocated_gpu_job_seconds > limit else "WITHIN_LIMIT"),
        "gpu_time_is_utilization": False}
