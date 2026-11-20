"""D-taskbook policy over existing P bootstrap draws; no new resampling."""
import numpy as np


BLOCKS = ("graph_2d", "molecule_3d", "atom_sasa")


def native_block_anchor(fields):
    """Freeze original equal-enabled-field totals, including atomic SASA once.

    The caller supplies the actual resolved native training view. This does
    not count atoms as fields, infer a new scale, or change source policies.
    """
    enabled = [field for field in fields if field.get("source_group", field["group"]) == "D"
               and field.get("loss_enabled", True)]
    if not enabled or len({field["name"] for field in enabled}) != len(enabled):
        raise ValueError("A unique resolved native D-R0 field list is required")
    names = {block: [] for block in BLOCKS}
    for field in enabled:
        name = field["name"]
        if field["level"] == "atom":
            block = "atom_sasa"
        elif field["level"] in ("molecule", "graph") and name.startswith("D3."):
            block = "molecule_3d"
        elif field["level"] in ("molecule", "graph") and name.startswith("D20."):
            block = "graph_2d"
        else:
            raise ValueError("Unregistered native D scalar/atomic field: " + name)
        names[block].append(name)
    if len(names["molecule_3d"]) != 6 or len(names["atom_sasa"]) != 1:
        raise ValueError("The source D3 anchor must contain six scalars and one atomic SASA field")
    return {"anchor": "resolved_native_D-R0_equal_enabled_fields",
            "enabled_fields": names, "total_enabled_fields": len(enabled),
            "block_weights": {block: len(names[block]) / len(enabled) for block in BLOCKS}}


def decide(candidate, control, candidate_draws, control_draws):
    """Reuse P paired CI math with D 4.6's explicit asymmetric LOSS rule.

    The legacy P helper also requires a minimum negative effect for LOSS. D's
    taskbook states only upper CI < 0; that explicit text takes precedence.
    Inputs are the existing matched molecule-bootstrap outputs, not new draws.
    """
    from phychem_mfm.phase1.p_recipe import paired_decision
    a, b = np.asarray(candidate_draws, dtype=np.float64), np.asarray(control_draws, dtype=np.float64)
    if a.shape != (1000,) or b.shape != (1000,) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Use all 1000 aligned finite existing molecule-bootstrap draws")
    if not np.isfinite([candidate, control]).all():
        raise ValueError("Completed finite primary R3 scores required")
    result = paired_decision(candidate, control, a, b)
    threshold = max(.01, .05 * max(candidate, control))
    lower, upper, delta = result["ci_lower"], result["ci_upper"], result["delta"]
    verdict = "WIN" if lower > 0 and delta >= threshold else "LOSS" if upper < 0 else "TIE"
    return {**result, "verdict": verdict, "tau": threshold,
            "seed1_required": verdict == "WIN", "bootstrap_draws": 1000,
            "bootstrap_seed": 20261025, "confidence": .95,
            "authority": "docs/d_recipe/TASKBOOK.md:4.6"}


def confirmed_win(per_seed):
    """D requires both seeds individually WIN; no pooled-seed override."""
    if set(per_seed) not in ({0}, {0, 1}):
        raise ValueError("Only seed0 and its conditional seed1 are registered")
    first = per_seed[0]
    if first["verdict"] != "WIN":
        if 1 in per_seed:
            raise ValueError("A non-WIN seed0 does not authorize ordinary seed1")
        return False
    return 1 in per_seed and per_seed[1]["verdict"] == "WIN"


def select_library(l1, l2, *, l2_against_l1=None):
    """Only completed per-seed decisions select a wide library."""
    win1, win2 = confirmed_win(l1), confirmed_win(l2)
    if win1 and win2:
        if l2_against_l1 is None:
            return {"status": "WAITING_PAIRED_LIBRARY_COMPARISON", "library": None}
        if l2_against_l1[0]["verdict"] == "WIN" and 1 not in l2_against_l1:
            return {"status": "WAITING_PAIRED_LIBRARY_COMPARISON", "library": None}
        winner = "L2" if confirmed_win(l2_against_l1) else "L1"
    else:
        winner = "L1" if win1 else "L2" if win2 else "D20"
    pending = any(arm[0]["verdict"] == "WIN" and 1 not in arm for arm in (l1, l2))
    if pending:
        return {"status": "WAITING_CONDITIONAL_SEED1", "library": None}
    return {"status": "DECIDED", "library": winner, "K1_eligible": winner != "D20"}


def deletion_eligible(decision):
    """Literal D-G1 rule: only a CI crossing zero authorizes deleting D3.

    A wholly positive interval is reported as such, but is not silently
    reinterpreted as the taskbook's distinct deletion acceptance condition.
    """
    lower, upper = decision["ci_lower"], decision["ci_upper"]
    return bool(lower <= 0 <= upper)
