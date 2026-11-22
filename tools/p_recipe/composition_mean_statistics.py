"""Only new participation ratio and registered contrast decision logic."""
import numpy as np


def participation_ratio(values, weights):
    values = np.asarray(values, np.float64)
    weights = np.asarray(weights, np.float64)
    if values.ndim != 2 or weights.shape != (len(values),):
        raise ValueError("Molecule weights must align to the original mean(H) rows")
    # A fixed translation improves covariance precision and changes no statistic.
    centered = values-values.mean(0)
    n = float(weights.sum())
    if n <= 0: return np.nan
    mean = weights@centered/n
    covariance = centered.T@(weights[:, None]*centered)/n-np.outer(mean, mean)
    trace = float(np.trace(covariance))
    square = float(np.square(covariance).sum())
    return trace*trace/square if trace > 0 and square > 0 else np.nan


def b4_decision(first, second):
    a, b = first.get("ci95"), second.get("ci95")
    if a is None or b is None: return "UNRESOLVED"
    if a[1] < 0 and b[1] < 0: return "SUPPORT"
    if a[0] >= 0 and b[0] >= 0: return "NOT_SUPPORT"
    return "UNCERTAIN"


def hcomp_decision(change, difference):
    a, b = change.get("ci95"), difference.get("ci95")
    if (a is not None and a[0] >= 0) or (b is not None and b[0] >= 0):
        return "NOT_SUPPORT"
    if a is None or b is None: return "UNRESOLVED"
    if a[1] < 0 and b[1] < 0: return "SUPPORT"
    return "UNCERTAIN"
