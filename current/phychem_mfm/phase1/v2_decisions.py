"""Numerical taskbook rules; callers supply actual complete TRAIN-dev results."""
from __future__ import annotations

import math
import statistics


def seed_standard_deviation(scores):
    values = tuple(scores)
    if len(values) < 2 or not all(math.isfinite(x) for x in values):
        raise ValueError('At least two actual pretraining seeds are required')
    return statistics.stdev(values)


def condition_aggregates(rows, conditions):
    """Equal condition means per candidate/seed, with no partial-condition ranking."""
    conditions = tuple(conditions)
    values = {}
    for row in rows:
        if row['condition'] not in conditions:
            continue
        key = (row['candidate'], row['seed'])
        result = values.setdefault(key, {})
        if row['condition'] in result or not math.isfinite(row['score']):
            raise ValueError('Duplicate or nonfinite actual dev result')
        result[row['condition']] = row['score']
    complete, pending = {}, []
    for (candidate, seed), result in values.items():
        missing = sorted(set(conditions) - set(result))
        if missing:
            pending.append(dict(candidate=candidate, seed=seed, missing_conditions=missing))
        else:
            complete.setdefault(candidate, {})[seed] = statistics.mean(result.values())
    return complete, pending


def choose_within_seed_sd(scores, *, seed_sd, simplicity_order):
    """Higher dev improvement is better; use predeclared simplicity for ties.

    Hardware-independent simplicity is the default when elapsed times come
    from different GPU types. No training loss substitutes for these scores.
    """
    if not scores or not math.isfinite(seed_sd) or seed_sd < 0:
        raise ValueError('Actual finite dev scores and nonnegative seed SD required')
    if not set(scores) <= set(simplicity_order) or not all(math.isfinite(x) for x in scores.values()):
        raise ValueError('Every candidate needs a predeclared simplicity rank and finite score')
    best = max(scores, key=scores.get)
    eligible = [name for name, score in scores.items() if scores[best] - score <= seed_sd]
    rank = {name: i for i, name in enumerate(simplicity_order)}
    selected = min(eligible, key=rank.get)
    return dict(best_dev_candidate=best, selected=selected, eligible=sorted(eligible, key=rank.get),
                best_dev_score=scores[best], selected_dev_score=scores[selected], seed_sd=seed_sd)


def convergence_budget(curve, *, seed_sd, ceiling=64_000_000):
    """Earliest observed doubling with gain below seed SD uses the larger endpoint."""
    if not math.isfinite(seed_sd) or seed_sd < 0:
        raise ValueError('An actual seed SD is required, not bootstrap/readout noise')
    if not all(type(n) is int and n > 0 and math.isfinite(v) for n, v in curve.items()):
        raise ValueError('Finite actual checkpoint scores keyed by sample count required')
    for samples in sorted(curve):
        if samples // 2 in curve and samples % 2 == 0:
            previous = samples // 2
            gain = curve[samples] - curve[previous]
            if gain < seed_sd:
                return dict(status='OBSERVED_PLATEAU', budget=samples, previous_samples=previous,
                            dev_gain=gain, seed_sd=seed_sd)
    if ceiling in curve:
        return dict(status='CEILING_REACHED_WITHOUT_OBSERVED_PLATEAU', budget=None,
                    tested_limit=ceiling, seed_sd=seed_sd)
    return dict(status='MORE_CHECKPOINTS_REQUIRED', budget=None, seed_sd=seed_sd)


def shared_training_budget(s_result, p_result):
    if s_result['budget'] is None or p_result['budget'] is None:
        return None
    return max(s_result['budget'], p_result['budget'])
