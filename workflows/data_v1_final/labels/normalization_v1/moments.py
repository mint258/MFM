"""Deterministic group-order Chan reductions and joint physical moments."""
from __future__ import annotations

import math


def state(moment):
    return {"n": moment.n, "mean": str(moment.mean), "M2": str(moment.M2)}


def combine(states):
    import numpy as np
    n = 0; mean = np.longdouble(0); m2 = np.longdouble(0)
    for s in states:
        k = int(s["n"])
        if not k:
            continue
        x, v = np.longdouble(s["mean"]), np.longdouble(s["M2"])
        total = n + k; delta = x - mean
        m2 += v + delta * delta * n * k / total
        mean += delta * k / total; n = total
    if not n:
        return {"n": 0, "mean": None, "std_ddof0": None, "status": "NO_VALID_TRAIN_VALUE"}
    if m2 < 0 or not np.isfinite(mean) or not np.isfinite(m2):
        raise ValueError("FINAL_MOMENT_REDUCTION_NONFINITE_OR_NEGATIVE_VARIANCE")
    sd = np.sqrt(m2 / n)
    if not math.isfinite(float(mean)) or not math.isfinite(float(sd)):
        raise ValueError("FINAL_STATISTIC_EXCEEDS_FLOAT64_RANGE")
    return {"n": n, "mean": float(mean), "std_ddof0": float(sd),
            "status": "CONSTANT_ZERO_STD_NO_INVENTED_SCALE" if sd == 0 else "DEFINED"}


class JointMoments:
    """Raw complete-vector covariance for audit; no anisotropic normalization choice."""
    def __init__(self, width):
        import numpy as np
        self.n = 0; self.mean = np.zeros(width, dtype=np.longdouble)
        self.M2 = np.zeros((width, width), dtype=np.longdouble)

    def add(self, rows):
        import numpy as np
        if not rows:
            return
        a = np.asarray(rows, dtype=np.longdouble)
        if a.ndim != 2 or a.shape[1] != len(self.mean) or not np.isfinite(a).all():
            raise ValueError("INVALID_COMPLETE_PHYSICAL_VECTOR")
        k = len(a); avg = np.mean(a, axis=0, dtype=np.longdouble); d = a - avg
        m2 = d.T @ d; delta = avg - self.mean; total = self.n + k
        self.M2 += m2 + np.outer(delta, delta) * self.n * k / total
        self.mean += delta * k / total; self.n = total

    def state(self):
        return {"n": self.n, "mean": [str(v) for v in self.mean],
                "M2": [[str(v) for v in row] for row in self.M2]}


def combine_joint(states):
    import numpy as np
    active = [s for s in states if s["n"]]
    if not active:
        return {"n": 0, "mean_vector": None, "covariance_ddof0": None, "status": "NO_COMPLETE_VALID_VECTOR"}
    out = JointMoments(len(active[0]["mean"]))
    for s in active:
        k = s["n"]; mean = np.asarray(s["mean"], dtype=np.longdouble)
        m2 = np.asarray(s["M2"], dtype=np.longdouble)
        delta = mean - out.mean; total = out.n + k
        out.M2 += m2 + np.outer(delta, delta) * out.n * k / total
        out.mean += delta * k / total; out.n = total
    cov = out.M2 / out.n
    if not np.isfinite(cov).all() or not np.isfinite(out.mean).all():
        raise ValueError("PHYSICAL_GROUP_COVARIANCE_NONFINITE")
    result = {"n": out.n, "mean_vector": [float(x) for x in out.mean],
              "covariance_ddof0": [[float(v) for v in row] for row in cov],
              "status": "RAW_COMPLETE_VECTOR_AUDIT_ONLY_NO_COMPONENT_NORMALIZATION_DECISION"}
    if any(not math.isfinite(v) for v in result["mean_vector"]) or any(not math.isfinite(v) for row in result["covariance_ddof0"] for v in row):
        raise ValueError("PHYSICAL_GROUP_STATISTIC_EXCEEDS_FLOAT64_RANGE")
    return result
