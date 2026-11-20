"""Describe an existing D forward cache using the frozen P composition code.

No encoder, probe fit, checkpoint search, scheduler or peer output is invoked.
The caller supplies the already produced mean(H) and first-conformer atom
moments. PR follows the existing P point statistic; CEV/CVF use its paired
1000-molecule bootstrap and unchanged nested ridge implementation.
"""
import importlib.util
from pathlib import Path

import numpy as np


COMPOSITION_SOURCE = Path("/share/home/zixiao/descriptor_analysis/MFM_p_followup_20261117/tools/p_followup/composition_statistics.py")


def existing_statistics(path=COMPOSITION_SOURCE):
    # Import the pure numerical module alone. Importing the peer command would
    # bind its CONTROL/RESULTS and a different unqualified resources module.
    specification = importlib.util.spec_from_file_location("d_existing_composition_statistics", path)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def participation_ratio(count, total, outer):
    """The P diagnostic's F64 population covariance and spectral PR."""
    total, outer = np.asarray(total, np.float64), np.asarray(outer, np.float64)
    mean = total / count
    covariance = outer / count - np.outer(mean, mean)
    spectrum = np.linalg.eigvalsh(covariance)[::-1]
    denominator = spectrum @ spectrum
    return dict(observations=int(count), participation_ratio=(
        float(spectrum.sum() ** 2 / denominator) if denominator > 0 else None),
        eigenvalues=spectrum.tolist(), bootstrap=False)


def describe(layers, *, owners, first, composition, statistics=None, guard=lambda: None):
    """Consume one cache, retaining the existing P statistic and fold choices.

    `layers` maps the registered layer numbers to `means` (one row per allowed
    conformer) and `first_atom_moments` (`count`, `total`, `outer`). `first` is
    the producer's first-allowed-conformer row for each molecule. Atom PR and
    mean PR both use that same first-conformer panel, as in P's PR diagnostic.
    The caller owns frozen 5000-VAL membership and endpoint selection.
    """
    statistics = existing_statistics() if statistics is None else statistics
    composition = np.asarray(composition, np.float64)
    owners, first = np.asarray(owners), np.asarray(first)
    if set(map(str, layers)) != {"3", "4", "5", "6"}:
        raise ValueError("Reuse only the registered encoder layers 3-6")
    if len(first) != len(composition) or not np.array_equal(owners[first], np.arange(len(first))):
        raise ValueError("Producer's first-conformer rows must retain molecule order")
    guard()
    weights = np.vstack([np.ones((1, len(first))), statistics.bootstrap_weights(len(first))])
    results, draws = {}, {}
    for layer, cache in layers.items():
        guard()
        means = np.asarray(cache["means"], np.float64)
        y = means[first]
        prediction, alphas = statistics.ridge_oof(composition, y)
        cev = statistics.cev_values(y, prediction, weights)
        cvf, residual = statistics.cvf_values(means, owners, prediction, weights)
        atom = cache["first_atom_moments"]
        metrics = dict(CEV=statistics.summary(cev), CVF=statistics.summary(cvf),
            CVF_res=statistics.summary(residual), selected_alphas=alphas,
            atom_PR=participation_ratio(atom["count"], atom["total"], atom["outer"]),
            mean_PR=participation_ratio(len(y), y.sum(0), y.T @ y))
        results[str(layer)] = metrics
        for name, values in (("CEV", cev), ("CVF", cvf), ("CVF_res", residual)):
            draws[str(layer) + "_" + name] = values
    return dict(layers=results, molecules=len(first), conformers=len(owners),
        statistics_dtype="float64", bootstrap=dict(repetitions=1000,
            seed=20261025, unit="molecule", paired=True, refit=False),
        forward_reused=True, downstream_probes_fitted=False,
        PR_uncertainty="Existing P point statistic; no PR confidence interval"), draws
