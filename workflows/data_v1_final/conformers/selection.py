"""Deterministic 0.5 A selection, explicit fallback, and conformer order."""
from __future__ import annotations

import hashlib
import math


def stable_key(seed, molecule_id, source, conformer_id):
    text = f"data-v1-conformer-order:{seed}:{molecule_id}:{source}:{conformer_id}"
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def select_fill(existing, candidates, target, distance, threshold=0.5):
    """Keep accepted old rows; add distinct optimized candidates, never copy rows."""
    if target < 1 or len(existing) > target:
        raise ValueError("INVALID_TARGET_OR_EXISTING_COUNT")
    all_rows = list(existing) + list(candidates)
    keys = [row["candidate_key"] for row in all_rows]
    if len(keys) != len(set(keys)):
        raise ValueError("DUPLICATE_CANDIDATE_ID")
    selected = []
    for row in existing:
        selected.append(dict(row, below_dedup_threshold=False,
                             min_rmsd_to_previously_selected_A=None))
    pending = sorted(candidates, key=lambda row: (row["energy"], row["candidate_key"]))
    for row in list(pending):
        if len(selected) == target:
            break
        closest = min((distance(row, old) for old in selected), default=math.inf)
        if not math.isfinite(closest) and selected:
            raise ValueError("NONFINITE_RMSD")
        if closest >= threshold:
            selected.append(dict(row, below_dedup_threshold=False,
                                 min_rmsd_to_previously_selected_A=None if not selected else closest))
            pending = [item for item in pending if item["candidate_key"] != row["candidate_key"]]
    while pending and len(selected) < target:
        scored = [(min(distance(row, old) for old in selected), row) for row in pending]
        if not all(math.isfinite(item[0]) for item in scored):
            raise ValueError("NONFINITE_RMSD")
        closest, row = min(scored, key=lambda item: (-item[0], item[1]["energy"],
                                                    item[1]["candidate_key"]))
        selected.append(dict(row, below_dedup_threshold=closest < threshold,
                             min_rmsd_to_previously_selected_A=closest))
        pending = [item for item in pending if item["candidate_key"] != row["candidate_key"]]
    return selected


def conformer_orders(rows, distance, molecule_id, source, seed):
    """All order fields are permutations of the supplied valid conformer IDs."""
    if not rows:
        return {"fixed_random": [], "energy": [], "diversity": []}
    by_id = {row["conformer_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("DUPLICATE_CONFORMER_ID")
    energy = sorted(by_id, key=lambda key: (by_id[key]["energy"], str(key)))
    random_order = sorted(by_id, key=lambda key: (stable_key(seed, molecule_id, source, key), str(key)))
    diversity = [energy[0]]
    remaining = set(energy[1:])
    while remaining:
        def score(key):
            nearest = min(distance(by_id[key], by_id[old]) for old in diversity)
            if not math.isfinite(nearest):
                raise ValueError("NONFINITE_RMSD")
            return -nearest, by_id[key]["energy"], str(key)
        best = min(remaining, key=score)
        diversity.append(best)
        remaining.remove(best)
    return {"fixed_random": random_order, "energy": energy, "diversity": diversity}
