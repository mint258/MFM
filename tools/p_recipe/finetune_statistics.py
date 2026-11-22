"""Primary F statistics on CPU: distinct seed-mean and ensemble estimands.

Consume each new prediction set once. Retain the original1000 aligned molecular
draw values for later paired algebra; never refit or independently replay a
closed producer. Frozen R3 rows are copied separately from existing results.
"""
from dataclasses import replace
import math
import numpy as np

from phychem_mfm.phase1.v3_dev_evaluation import error

SEEDS = (0, 1, 2)
TASKS = ("qm9.U0_atom", "qm9.homo", "exp.LogD", "exp.LogS")


def same_population(left, right):
    if (left.task != right.task or left.molecule_uids != right.molecule_uids
            or left.source_record_uids != right.source_record_uids
            or not np.array_equal(left.valid, right.valid)
            or not np.array_equal(left.targets, right.targets, equal_nan=True)):
        raise ValueError("Paired native records/labels/masks/molecule groups differ")
    if (right.predictions.shape != right.targets.shape or right.targets.ndim != 1
            or not np.isfinite(right.predictions).all()):
        raise ValueError("Nonfinite new predictions")


def ensemble(predictions):
    if len(predictions) != 3:
        raise ValueError("Exactly the three registered fine-tuning seeds required")
    first = predictions[0]
    for prediction in predictions:
        same_population(first, prediction)
    return replace(first, predictions=np.mean(
        np.stack([p.predictions.astype(np.float64) for p in predictions]), axis=0))


def normalized(actual, baseline):
    if (actual is None or baseline is None or not math.isfinite(actual)
            or not math.isfinite(baseline) or baseline <= 0):
        return None
    return (baseline-actual)/baseline


def interval(values):
    finite = [v for v in values if v is not None and math.isfinite(v)]
    return (np.quantile(finite, [.025, .975]).tolist() if finite else None, len(finite))


def summarize(groups, scratch, reference, *, input_identity, state=None,
              checkpoint=None, should_stop=None):
    """Return new-group table rows plus retained paired primary draw values.

    groups[group][task] and scratch[task] contain seed0/1/2 predictions in order.
    state is this SAME producer's unfinished checkpoint, not a second analysis.
    A checkpoint callback owns persistence at50-draw boundaries and on stop.
    """
    if not groups or set(scratch) != set(TASKS) or set(reference) != set(TASKS):
        raise ValueError("Registered four-task coverage and scratch/reference required")
    prepared, point_rows, populations = {}, {}, {}
    for key in sorted(groups):
        if set(groups[key]) != set(TASKS):
            raise ValueError("Each F condition requires all four registered tasks")
        for task in sorted(TASKS):
            candidates = groups[key][task]
            if len(candidates) != 3 or len(scratch[task]) != 3:
                raise ValueError("Missing fine-tuning seed")
            for value in [*candidates, *scratch[task]]:
                same_population(reference[task], value)
            if reference[task].task.task_id != task or reference[task].task.error_metric != "mae":
                raise ValueError("Only the registered native MAE tasks")
            actual = ensemble(candidates)
            base = ensemble(scratch[task])
            e_ref = error(reference[task])
            errors = [error(p) for p in candidates]
            scratch_errors = [error(p) for p in scratch[task]]
            scores = [normalized(a, b) for a, b in zip(errors, scratch_errors)]
            ref_scores = [normalized(a, e_ref) for a in errors]
            if any(x is None for x in [*scores, *ref_scores]):
                raise ValueError("Point-score denominator unavailable; do not invent a score")
            condition = key + "/" + task
            prepared[condition] = (actual, base, reference[task])
            point_rows[condition] = dict(condition=key, task=task,
                seed0_mae=errors[0], seed1_mae=errors[1], seed2_mae=errors[2],
                mae_seed_mean=float(np.mean(errors)), mae_seed_std=float(np.std(errors, ddof=1)),
                seed0_scratch_improvement=scores[0], seed1_scratch_improvement=scores[1],
                seed2_scratch_improvement=scores[2],
                scratch_improvement_seed_mean=float(np.mean(scores)),
                scratch_improvement_seed_std=float(np.std(scores, ddof=1)),
                frozen_reference_score_seed_mean=float(np.mean(ref_scores)),
                frozen_reference_score_seed_std=float(np.std(ref_scores, ddof=1)),
                frozen_random_E_ref=e_ref,
                ensemble_mae=error(actual), ensemble_scratch_mae=error(base),
                ensemble_scratch_improvement=normalized(error(actual), error(base)),
                ensemble_frozen_reference_score=normalized(error(actual), e_ref),
                bootstrap_seed=20261025, bootstrap_unit="molecule",
                ci_estimand="score_of_mean_prediction_not_mean_of_seed_scores")
            populations.setdefault(actual.task.dataset_id, set()).update(actual.molecule_uids)
    populations = {key: tuple(sorted(populations[key])) for key in sorted(populations)}
    if not isinstance(input_identity, dict) or not all(k in input_identity for k in
            ("scratch", "random_reference", "conditions")):
        raise ValueError("Bind the exact primary input files and original baselines")
    identity = dict(input_identity=input_identity, conditions=sorted(prepared),
                    groups={k:list(v) for k,v in populations.items()},
                    bootstrap_seed=20261025, samples=1000)
    if state is None:
        state = dict(identity=identity, completed_draws=0,
            draws={key:dict(mae=[], scratch_improvement=[], frozen_reference_score=[])
                   for key in prepared}, rng_state=np.random.default_rng(20261025).bit_generator.state)
    elif state["identity"] != identity:
        raise ValueError("Unfinished primary bootstrap identity changed")
    completed = state["completed_draws"]
    if (not isinstance(completed, int) or not 0 <= completed <= 1000
            or set(state["draws"]) != set(prepared)
            or any(len(values) != completed for metrics in state["draws"].values()
                   for values in metrics.values())):
        raise ValueError("Unfinished bootstrap cursor/retained values are inconsistent")
    rng = np.random.default_rng()
    rng.bit_generator.state = state["rng_state"]
    lookup = {}
    for key, (prediction, _, _) in prepared.items():
        rows = {}
        for i, uid in enumerate(prediction.molecule_uids):
            rows.setdefault(uid, []).append(i)
        lookup[key] = rows
    for draw_number in range(state["completed_draws"], 1000):
        if should_stop is not None and should_stop():
            if checkpoint is not None:
                checkpoint(state)
            return dict(status="CONTINUATION_REQUIRED", state=state)
        draws = {dataset:rng.choice(uids, len(uids), replace=True).tolist()
                 for dataset,uids in populations.items()}
        for key, (actual, base, ref) in prepared.items():
            indices = [i for uid in draws[actual.task.dataset_id] for i in lookup[key].get(uid, ())]
            a, b, r = error(actual, indices), error(base, indices), error(ref, indices)
            store = state["draws"][key]
            store["mae"].append(a)
            store["scratch_improvement"].append(normalized(a, b))
            store["frozen_reference_score"].append(normalized(a, r))
        state["completed_draws"] = draw_number+1
        state["rng_state"] = rng.bit_generator.state
        if checkpoint is not None and state["completed_draws"] % 50 == 0:
            checkpoint(state)
    for key, row in point_rows.items():
        for metric, values in state["draws"][key].items():
            bounds, defined = interval(values)
            row[metric+"_ensemble_ci_lower"] = bounds[0] if bounds else None
            row[metric+"_ensemble_ci_upper"] = bounds[1] if bounds else None
            row[metric+"_ensemble_bootstrap_defined"] = defined
    return dict(status="COMPLETE", rows=list(point_rows.values()), retained=state)


def paired_contrast(primary, left, right, task, *, right_primary=None):
    """Only algebra on this primary producer's matched retained draws."""
    other = primary if right_primary is None else right_primary
    if primary["status"] != "COMPLETE" or other["status"] != "COMPLETE":
        raise ValueError("Only closed primary statistics can be contrasted")
    ai, bi = primary["retained"]["identity"], other["retained"]["identity"]
    if (any(ai[k] != bi[k] for k in ("groups", "bootstrap_seed", "samples"))
            or any(ai["input_identity"][k] != bi["input_identity"][k]
                   for k in ("scratch", "random_reference"))):
        raise ValueError("Paired retained draws/baseline bindings differ")
    rows = {(r["condition"], r["task"]):r for r in primary["rows"]}
    other_rows = {(r["condition"], r["task"]):r for r in other["rows"]}
    a, b = rows[(left, task)], other_rows[(right, task)]
    av = primary["retained"]["draws"][left+"/"+task]["scratch_improvement"]
    bv = other["retained"]["draws"][right+"/"+task]["scratch_improvement"]
    if len(av) != 1000 or len(bv) != 1000:
        raise ValueError("Original1000 paired draws required")
    differences = [x-y if x is not None and y is not None else None for x,y in zip(av,bv)]
    bounds, defined = interval(differences)
    seed_delta = a["scratch_improvement_seed_mean"]-b["scratch_improvement_seed_mean"]
    return dict(left=left, right=right, task=task,
        delta_seed_mean=seed_delta,
        tau=max(.01,.05*max(a["scratch_improvement_seed_mean"],b["scratch_improvement_seed_mean"])),
        delta_ensemble=a["ensemble_scratch_improvement"]-b["ensemble_scratch_improvement"],
        ensemble_ci_lower=bounds[0] if bounds else None,
        ensemble_ci_upper=bounds[1] if bounds else None,
        bootstrap_defined=defined, ci_estimand="difference_of_scores_of_mean_predictions",
        interpretation="Descriptive; seed-mean decision point and ensemble CI are distinct")