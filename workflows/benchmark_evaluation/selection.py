"""Pre-registered B1 decisions and scaffold folds; no fitting or result selection."""
from itertools import combinations
import math
import numpy as np

BASELINES = ("RF-ECFP4", "LightGBM-RDKit2D", "Chemprop-v2")
SEED = 20261025

class IncompleteComparison(ValueError):
    """A comparison cannot be made on unaligned or incomplete predictions."""

def align_predictions(predictions):
    """Require identical IDs, original labels, molecular groups, and references."""
    if set(predictions) != set(BASELINES):
        raise IncompleteComparison("All three pre-registered B1 baselines are required")
    indexed = {}
    for name in BASELINES:
        rows = predictions[name]
        if any(row["evaluation_id"] is None or not str(row["evaluation_id"]).strip()
               or not row["full_inchikey"] for row in rows):
            raise IncompleteComparison("Missing evaluation or complete molecule identity")
        mapping = {str(row["evaluation_id"]): row for row in rows}
        if not mapping or len(mapping) != len(rows):
            raise IncompleteComparison("Missing or duplicate evaluation IDs")
        indexed[name] = mapping
    ids = sorted(indexed[BASELINES[0]])
    first = indexed[BASELINES[0]]
    y = np.asarray([first[key]["y_true"] for key in ids], dtype=float)
    means = np.asarray([first[key]["training_mean"] for key in ids], dtype=float)
    groups = np.asarray([str(first[key]["full_inchikey"]) for key in ids])
    values = []
    if not np.isfinite(y).all() or not np.isfinite(means).all():
        raise IncompleteComparison("Nonfinite labels or TRAIN means")
    if any(not str(first[key]["full_inchikey"]) for key in ids):
        raise IncompleteComparison("Missing complete molecular identity")
    for name in BASELINES:
        mapping = indexed[name]
        if set(mapping) != set(ids):
            raise IncompleteComparison("Evaluation populations differ; do not intersect them")
        other_y = np.asarray([mapping[key]["y_true"] for key in ids], dtype=float)
        other_means = np.asarray([mapping[key]["training_mean"] for key in ids], dtype=float)
        other_groups = np.asarray([str(mapping[key]["full_inchikey"]) for key in ids])
        if not (np.array_equal(y, other_y) and np.array_equal(means, other_means)
                and np.array_equal(groups, other_groups)):
            raise IncompleteComparison("Labels, TRAIN references, or molecule groups differ")
        prediction = np.asarray([mapping[key]["prediction"] for key in ids], dtype=float)
        if not np.isfinite(prediction).all():
            raise IncompleteComparison("Missing predictions must not redefine the test population")
        values.append(prediction)
    return ids, y, means, groups, np.asarray(values)

def paired_bootstrap(predictions, draws=1000, seed=SEED):
    """Resample whole molecules identically across the three baseline predictions."""
    if draws != 1000:
        raise ValueError("The registered B1 protocol requires 1000 draws")
    ids, y, means, groups, values = align_predictions(predictions)
    unique, inverse = np.unique(groups, return_inverse=True)
    error = np.asarray([
        np.bincount(inverse, weights=np.abs(y - value), minlength=len(unique))
        for value in values
    ])
    reference = np.bincount(inverse, weights=np.abs(y - means), minlength=len(unique))
    denominator = float(reference.sum())
    if denominator <= 0:
        raise IncompleteComparison("TRAIN-mean reference has zero error")
    rae = error.sum(axis=1) / denominator
    bootstrap = np.empty((draws, len(BASELINES)), dtype=float)
    rng = np.random.default_rng(seed)
    for index in range(draws):
        sample = rng.integers(0, len(unique), size=len(unique))
        divisor = float(reference[sample].sum())
        if divisor <= 0:
            raise IncompleteComparison("A molecule-bootstrap draw has zero reference error")
        bootstrap[index] = error[:, sample].sum(axis=1) / divisor
    best_index = int(np.argmin(rae))
    worst_index = int(np.argmax(rae))
    paired_range = bootstrap[:, worst_index] - bootstrap[:, best_index]
    standard_error = float(paired_range.std(ddof=1))
    return {
        "baseline_order": list(BASELINES),
        "RAE": rae.tolist(),
        "RAE_CI95_low": np.quantile(bootstrap, .025, axis=0).tolist(),
        "RAE_CI95_high": np.quantile(bootstrap, .975, axis=0).tolist(),
        "best_baseline": BASELINES[best_index],
        "best_index": best_index,
        "worst_baseline": BASELINES[worst_index],
        "RAE_range": float(rae[worst_index] - rae[best_index]),
        "paired_best_worst_bootstrap_SE": standard_error,
        "discrimination_threshold": max(.02, 2 * standard_error),
        "molecule_bootstrap_draws": draws,
        "n_test_rows": len(ids),
        "n_test_molecules": len(unique),
    }

def decide_endpoint(predictions, *, n_filtered_labeled_points, scope_proof):
    """Apply the task rule once, after completeness; never use C1 or our models."""
    if (scope_proof.get("deferred_registry_full_inventory_verified") is not True
            or scope_proof.get("deferred_endpoint_count") != 5):
        raise IncompleteComparison("The complete five-endpoint scope proof is required")
    if not isinstance(n_filtered_labeled_points, int) or n_filtered_labeled_points < 0:
        raise ValueError("Provide the whole filtered endpoint's labeled point count")
    result = paired_bootstrap(predictions)
    best = result["best_index"]
    if n_filtered_labeled_points < 30:
        decision, reason = "APPENDIX", "FEWER_THAN_30_FILTERED_LABELED_POINTS"
    elif result["RAE"][best] >= .90 and result["RAE_CI95_high"][best] >= .85:
        decision, reason = "EXCLUDE", "INSUFFICIENT_SIGNAL"
    elif result["RAE_range"] < result["discrimination_threshold"]:
        decision, reason = "APPENDIX", "INSUFFICIENT_DISCRIMINATION"
    else:
        decision, reason = "RETAIN", "PASSED_REGISTERED_B1_RULE"
    return dict(result, decision=decision, reason=reason,
                n_filtered_labeled_points=n_filtered_labeled_points)

def scaffold_folds(scaffold_groups, seed=SEED):
    """Yield five repetitions of five disjoint scaffold-group folds."""
    groups = np.asarray(scaffold_groups, dtype=str)
    unique, inverse = np.unique(groups, return_inverse=True)
    if len(unique) < 5:
        raise IncompleteComparison("Fewer than five scaffolds; do not replace with a random split")
    members = [np.flatnonzero(inverse == index) for index in range(len(unique))]
    streams = np.random.SeedSequence(seed).spawn(5)
    for repetition, stream in enumerate(streams):
        rng = np.random.default_rng(stream)
        order = rng.permutation(len(unique))
        assignments = [[] for _ in range(5)]
        sizes = np.zeros(5, dtype=int)
        for index in order:
            candidates = np.flatnonzero(sizes == sizes.min())
            fold = int(rng.choice(candidates))
            assignments[fold].extend(members[index].tolist())
            sizes[fold] += len(members[index])
        for fold, selected in enumerate(assignments):
            test = np.sort(np.asarray(selected, dtype=int))
            train = np.setdiff1d(np.arange(len(groups)), test)
            if not len(train) or not len(test):
                raise IncompleteComparison("Empty scaffold fold; no split substitution allowed")
            yield repetition, fold, train, test

def tukey_cv(fold_scores):
    """Use the registered 25 scaffold-fold scores for Tukey HSD comparisons."""
    from scipy.stats import tukey_hsd
    required = {(repetition, fold) for repetition in range(5) for fold in range(5)}
    if set(fold_scores) != set(BASELINES):
        raise IncompleteComparison("All three baselines are required for Tukey HSD")
    samples = []
    for name in BASELINES:
        rows = fold_scores[name]
        if len(rows) != 25 or set(rows) != required:
            raise IncompleteComparison("Each model needs the same 25 scaffold folds")
        values = np.asarray([rows[key] for key in sorted(required)], dtype=float)
        if not np.isfinite(values).all():
            raise IncompleteComparison("Missing fold scores cannot be discarded")
        samples.append(values)
    comparison = tukey_hsd(*samples)
    return [
        {"left": BASELINES[left], "right": BASELINES[right],
         "mean_RAE_difference": float(comparison.statistic[left, right]),
         "pvalue": float(comparison.pvalue[left, right])}
        for left, right in combinations(range(len(BASELINES)), 2)
    ]
