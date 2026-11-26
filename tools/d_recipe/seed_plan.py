"""Plan only taskbook-authorized seed1 runs and share each control once.

This is a pure planner over completed seed0 decisions; it neither submits jobs
nor writes a ledger. The Root scheduler persists its returned registry along
with the required stage decision and performs actual storage/GPU admission.
"""
from copy import deepcopy

from phychem_mfm.phase1.p_recipe_seed_policy import fresh_seed1_configuration

from .training import ARMS, prepare_runtime
from .confirmation_plan import _EXECUTION_KEYS


def _child(parent, *, output_root, mask_seed=None):
    if (parent.get("condition") != "D" or parent.get("arm") not in ARMS
            or parent["arm"].startswith("9M-") or parent.get("samples") != 3000000
            or parent.get("seed") != 0):
        raise ValueError("Conditional seed1 belongs only to registered 3M seed0 D arms")
    child = fresh_seed1_configuration(parent, output_root=output_root)
    # A fresh seed owns a new real allocation and current resource claims.
    # Keep the original P scientific helper, then unbind all prior transports.
    for key in _EXECUTION_KEYS:
        child.pop(key, None)
    child["resource_admission_pending"] = True
    child["seed0_run"] = parent["run"]
    # Taskbook layer diagnostics are seed0-only. Their existing cache is bound
    # to that run/checkpoint and must never be reused by a fresh seed1 readout.
    child.pop("diagnostic_feature_root", None)
    options = child["d_recipe"]
    if options.get("graph_mask_enabled", False):
        if type(mask_seed) is not int or mask_seed < 0:
            raise ValueError("Masked seed1 needs its explicit preregistered dedicated mask seed")
        options["mask_seed"] = mask_seed
    binding = options.get("scientific_binding")
    if binding is not None:
        # This creates a new random-initialization run. It never loads or
        # rebinds a seed0 checkpoint; all other scientific conditions persist.
        binding["seed"] = 1
    return prepare_runtime(child)


def _same_child_condition(actual, expected):
    keys = ("condition", "arm", "seed", "samples", "source", "normalizations", "corpus",
            "training_view", "distance_bias", "components", "batch_size", "microbatch_size",
            "lr", "betas", "weight_decay", "warmup_fraction", "clip_calibration", "p_recipe",
            "d_recipe", "head_form")
    return all(actual.get(key) == expected.get(key) for key in keys)


def plan_seed1(candidate, control, comparison, registry, *, output_root, mask_seeds=None):
    """One canonical seed1 per arm, reused by every winning comparison.

    Infra resume run names may change, so the canonical arm is the registry
    key. A scientific mismatch is rejected instead of silently starting a
    second control. Non-WIN comparisons produce no new configuration.
    """
    if (comparison.get("candidate") != candidate["run"]
            or comparison.get("control") != control["run"]
            or comparison.get("seed") != 0 or comparison.get("samples") != 3000000):
        raise ValueError("Use this exact completed seed0 screening comparison")
    state = deepcopy(registry)
    if state.get("schema") != "D_CONDITIONAL_SEED1_REGISTRY_V1":
        raise ValueError("Use the D conditional-seed registry")
    requested, reused = [], []
    if comparison["R3"]["verdict"] != "WIN":
        return {"registry": state, "new_configurations": requested, "reused_arms": reused}
    mask_seeds = mask_seeds or {}
    for parent in (control, candidate):
        arm = parent["arm"]
        expected = _child(parent, output_root=output_root, mask_seed=mask_seeds.get(arm))
        existing = state["runs"].get(arm)
        if existing is not None:
            if not _same_child_condition(existing["configuration"], expected):
                raise ValueError("Stored seed1 belongs to a different scientific condition: " + arm)
            reused.append(arm)
            continue
        state["runs"][arm] = {"seed0_run": parent["run"], "configuration": expected}
        requested.append(expected)
    return {"registry": state, "new_configurations": requested, "reused_arms": reused}

