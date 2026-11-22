"""ExpansionRx leaderboard reporting, separate from registered TRAIN-mean B1 screening."""
import numpy as np
from .selection import BASELINES, IncompleteComparison, align_predictions
ENDPOINTS = (
    "LogD", "KSOL", "HLM CLint", "MLM CLint",
    "Caco-2 Permeability Papp A>B", "Caco-2 Permeability Efflux",
    "MPPB", "MBPB", "MGMB",
)
OFFICIAL_SOURCE = (
    "https://huggingface.co/spaces/openadmet/OpenADMET-ExpansionRx-Challenge/"
    "blob/b52c9475126776c38edf3c6d6ab2ff671683c90d/utils.py"
)

def leaderboard_scale(values, endpoint):
    if endpoint not in ENDPOINTS:
        raise ValueError("Unknown official challenge endpoint")
    values = np.asarray(values, dtype=float)
    if not np.isfinite(values).all():
        raise IncompleteComparison("Missing predictions must not change the blind TEST population")
    return values.copy() if endpoint == "LogD" else np.log10(np.maximum(values, 0.) + 1.)

def leaderboard_point(y, prediction, endpoint):
    """Official log/TEST-mean point metric; does not implement the B1 task rule."""
    y = leaderboard_scale(y, endpoint)
    prediction = leaderboard_scale(prediction, endpoint)
    if y.ndim != 1 or prediction.shape != y.shape or not len(y):
        raise IncompleteComparison("Unaligned official endpoint")
    error = float(np.abs(y - prediction).sum())
    reference = float(np.abs(y - y.mean()).sum())
    if reference <= 0:
        raise IncompleteComparison("Official TEST-mean reference has zero error")
    return {"leaderboard_MAE": error / len(y), "leaderboard_RAE": error / reference}

def leaderboard_report(predictions_by_endpoint, draws=1000, seed=20261025):
    """Report all nine endpoints and paired molecule-bootstrap MA-RAE, without decisions."""
    if set(predictions_by_endpoint) != set(ENDPOINTS) or draws != 1000:
        raise IncompleteComparison("All nine original endpoints and 1000 draws are required")
    cache = {}
    all_groups = set()
    for endpoint in ENDPOINTS:
        ids, y, means, groups, predictions = align_predictions(predictions_by_endpoint[endpoint])
        # align_predictions requires exact IDs, labels, full keys and TRAIN references across models.
        y = leaderboard_scale(y, endpoint)
        predictions = np.asarray([leaderboard_scale(p, endpoint) for p in predictions])
        cache[endpoint] = (ids, y, groups, predictions)
        all_groups.update(groups.tolist())
    unique = np.asarray(sorted(all_groups))
    group_index = {group: index for index, group in enumerate(unique)}
    endpoint_rows = []
    macro = np.zeros(len(BASELINES), dtype=float)
    prepared = []
    for endpoint in ENDPOINTS:
        ids, y, groups, predictions = cache[endpoint]
        reference = float(np.abs(y - y.mean()).sum())
        if reference <= 0:
            raise IncompleteComparison("Official TEST-mean reference has zero error")
        errors = np.abs(predictions - y)
        rae = errors.sum(axis=1) / reference
        macro += rae / len(ENDPOINTS)
        index = np.asarray([group_index[g] for g in groups], dtype=np.int64)
        prepared.append((y, errors, index))
        for model, value, mae in zip(BASELINES, rae, errors.mean(axis=1)):
            endpoint_rows.append({
                "endpoint": endpoint, "model": model,
                "leaderboard_RAE": float(value), "leaderboard_MAE": float(mae),
                "n_test_rows": len(ids), "n_test_molecules": len(set(groups)),
            })
    rng = np.random.default_rng(seed)
    bootstrap = np.empty((draws, len(BASELINES)), dtype=float)
    for draw in range(draws):
        sample = rng.integers(0, len(unique), size=len(unique))
        molecule_weights = np.bincount(sample, minlength=len(unique))
        total = np.zeros(len(BASELINES), dtype=float)
        for y, errors, index in prepared:
            weights = molecule_weights[index]
            count = int(weights.sum())
            if count == 0:
                raise IncompleteComparison("Molecule bootstrap left an endpoint without observations")
            test_mean = float(np.dot(weights, y) / count)
            reference = float(np.dot(weights, np.abs(y - test_mean)))
            if reference <= 0:
                raise IncompleteComparison("Molecule bootstrap has an undefined official RAE")
            total += (errors @ weights) / reference / len(ENDPOINTS)
        bootstrap[draw] = total
    low, high = np.quantile(bootstrap, [.025, .975], axis=0)
    return {
        "official_metric_source": OFFICIAL_SOURCE,
        "metric": "Official endpoint scale and TEST-mean RAE; macro average over nine endpoints",
        "bootstrap": "1000 paired whole-molecule draws over the union of official TEST full keys",
        "bootstrap_differs_from_organizer_IID_rows": True,
        "endpoint_results": endpoint_rows,
        "macro_results": [
            {"model": model, "leaderboard_MA_RAE": float(value),
             "leaderboard_MA_RAE_CI95_low": float(lo),
             "leaderboard_MA_RAE_CI95_high": float(hi)}
            for model, value, lo, hi in zip(BASELINES, macro, low, high)
        ],
        "B1_task_decisions_produced": False,
        "B1_screening_metric": "Separate original-unit RAE relative to the fit TRAIN mean",
    }
