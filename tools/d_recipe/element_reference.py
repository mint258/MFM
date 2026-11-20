"""Opt-in TRAIN-only D A1 fitting; this module never changes D4 parameters.

Callers supply the ridge alpha and fold seed explicitly. The mathematical core
supports small unit-test fixtures; the production entry requires >=100000 valid
TRAIN molecules per field. All fields share cohort fold assignments even when
their observed subsets differ.
"""
from copy import deepcopy
import math

import numpy as np


ELEMENTS = 118
FOLDS = 5
MIN_PRODUCTION_VALID = 100000


def element_design(native_atomic_numbers):
    """Native atoms including H, Z=1..118, followed by an unpenalized intercept.

    No hydrogen inference/addition or graph rewriting is done: the caller must
    supply the existing native atomic-number sequence including actual H atoms.
    """
    rows = list(native_atomic_numbers)
    design = np.zeros((len(rows), ELEMENTS + 1), dtype=np.float64)
    for index, atoms in enumerate(rows):
        atomic = np.asarray(atoms)
        if (atomic.ndim != 1 or atomic.dtype.kind not in "iu"
                or (atomic < 1).any() or (atomic > ELEMENTS).any()):
            raise ValueError("Native atomic numbers must be integers in 1..118")
        design[index, :ELEMENTS] = np.bincount(atomic, minlength=ELEMENTS + 1)[1:]
    design[:, -1] = 1.
    return design


def assign_folds(size, *, fold_seed):
    """One fixed balanced five-fold cohort assignment, independent of targets."""
    order = np.random.default_rng(fold_seed).permutation(size)
    folds = np.empty(size, dtype=np.int8)
    folds[order] = np.arange(size) % FOLDS
    return folds


def reference_policy(oof_r2):
    """Taskbook inclusive boundaries; undefined fits preserve the raw target."""
    if oof_r2 is None or not math.isfinite(oof_r2):
        return "original", "undefined_oof_r2"
    if oof_r2 < .30:
        return "original", "oof_r2_below_0.30"
    if oof_r2 >= .999:
        return "original", "oof_r2_at_least_0.999"
    return "element_reference_residual", "0.30_le_oof_r2_lt_0.999"


def _ridge(design, target, alpha):
    # Center only the slope predictors. The intercept is reconstructed after
    # the penalized solve and therefore is never penalized, even for huge alpha.
    features = design[:, :ELEMENTS]
    x_mean, y_mean = features.mean(0), target.mean(0)
    x_centered, y_centered = features - x_mean, target - y_mean
    gram = x_centered.T @ x_centered
    gram.flat[::ELEMENTS + 1] += alpha
    slopes = np.linalg.solve(gram, x_centered.T @ y_centered)
    return np.concatenate((slopes, np.atleast_1d(y_mean - x_mean @ slopes)))


def _shared_ridge_coefficients(design, targets, valid, folds, alpha):
    """Reuse each Gram solve for fields with identical observed rows.

    Target-column chunks bound temporary copies; this is an execution detail,
    not another statistical arm. Every solve stays centered F64 ridge with the
    same unpenalized intercept, five fold labels and caller-supplied alpha.
    """
    groups = {}
    for column in range(targets.shape[1]):
        groups.setdefault(np.packbits(valid[:, column]).tobytes(), []).append(column)
    result = {}
    for columns in groups.values():
        observed = valid[:, columns[0]]
        for fold in (-1, *range(FOLDS)):
            selected = observed if fold == -1 else observed & (folds != fold)
            rows = np.flatnonzero(selected)
            if not len(rows):
                continue
            x = design[rows, :ELEMENTS]
            x_mean = x.mean(0)
            x_centered = x - x_mean
            gram = x_centered.T @ x_centered
            gram.flat[::ELEMENTS + 1] += alpha
            for start in range(0, len(columns), 32):
                chunk = columns[start:start + 32]
                y = targets[np.ix_(rows, chunk)]
                y_mean = y.mean(0)
                slopes = np.linalg.solve(gram, x_centered.T @ (y - y_mean))
                coefficients = np.vstack((slopes, y_mean - x_mean @ slopes))
                for local, column in enumerate(chunk):
                    result[column, fold] = coefficients[:, local]
    return result


def _inputs(design, targets, valid, ridge_alpha):
    if not math.isfinite(ridge_alpha) or ridge_alpha <= 0:
        raise ValueError("Caller must explicitly supply a finite positive ridge_alpha")
    design = np.asarray(design, dtype=np.float64)
    targets = np.asarray(targets, dtype=np.float64)
    valid = np.asarray(valid)
    if targets.ndim == 1:
        targets = targets[:, None]
    if valid.ndim == 1:
        valid = valid[:, None]
    if (design.ndim != 2 or design.shape[1] != ELEMENTS + 1
            or targets.ndim != 2 or valid.shape != targets.shape
            or targets.shape[0] != design.shape[0] or valid.dtype != np.bool_):
        raise ValueError("Expected design[N,119], targets[N,F], boolean valid[N,F]")
    if not np.isfinite(design).all() or not (design[:, -1] == 1.).all():
        raise ValueError("Finite native element counts and intercept=1 are required")
    if not np.isfinite(targets[valid]).all():
        raise ValueError("An observed target is nonfinite; preserve its producer missing/event mask")
    return design, targets, valid


def fit_element_reference_core(design, targets, valid, *, ridge_alpha, fold_seed,
                               field_names=None, shared_mask_solve=True):
    """Five-fold OOF scores followed by frozen full-observed-TRAIN coefficients.

    There is no alpha selection or sweep. Fields with constant targets, empty
    validation folds, or too few observed rows retain their original target
    with an explicit reason. Inference targets are not used anywhere here.
    """
    design, targets, valid = _inputs(design, targets, valid, ridge_alpha)
    names = tuple(field_names if field_names is not None else
                  (str(index) for index in range(targets.shape[1])))
    if len(names) != targets.shape[1] or len(set(names)) != len(names):
        raise ValueError("Field names must align uniquely with target columns")
    folds = assign_folds(design.shape[0], fold_seed=fold_seed)
    shared = (_shared_ridge_coefficients(design, targets, valid, folds, ridge_alpha)
              if shared_mask_solve else None)
    results = []
    for column, name in enumerate(names):
        observed = valid[:, column]
        n_valid = int(observed.sum())
        y = targets[:, column]
        fold_counts = [int((observed & (folds == fold)).sum()) for fold in range(FOLDS)]
        coefficients = ((shared[column, -1] if shared is not None else
                         _ridge(design[observed], y[observed], ridge_alpha)) if n_valid else None)
        r2 = None
        reason = None
        if n_valid < FOLDS or not all(fold_counts):
            reason = "insufficient_observed_five_fold_support"
        elif np.ptp(y[observed]) == 0:
            reason = "constant_target_oof_r2_undefined"
        else:
            oof = np.empty(n_valid, dtype=np.float64)
            observed_folds = folds[observed]
            x_observed, y_observed = design[observed], y[observed]
            for fold in range(FOLDS):
                train = observed_folds != fold
                held_out = ~train
                fit = (shared[column, fold] if shared is not None else
                       _ridge(x_observed[train], y_observed[train], ridge_alpha))
                oof[held_out] = x_observed[held_out] @ fit
            residual_ss = np.square(y_observed - oof).sum(dtype=np.float64)
            total_ss = np.square(y_observed - y_observed.mean()).sum(dtype=np.float64)
            r2 = float(1. - residual_ss / total_ss)
            if not math.isfinite(r2):
                r2, reason = None, "nonfinite_oof_r2"
        policy, band_reason = reference_policy(r2)
        results.append({"field_name": name, "oof_r2": r2, "target_policy": policy,
                        "reason": reason or band_reason, "n_valid": n_valid,
                        "valid_by_fold": fold_counts,
                        "coefficients": None if coefficients is None else coefficients.tolist()})
    return {"schema": "D_ELEMENT_REFERENCE_V1", "status": "FROZEN_FIT",
            "fit_role": "TRAIN", "folds": FOLDS, "fold_seed": fold_seed,
            "ridge_alpha": float(ridge_alpha), "cohort_rows": design.shape[0],
            "basis_atomic_numbers": list(range(1, ELEMENTS + 1)),
            "coefficient_order": "Z1..Z118,intercept", "intercept_penalized": False,
            "original_D4_modified": False, "fields": results}


def fit_element_reference(design, targets, valid, *, roles, ridge_alpha,
                          fold_seed, field_names=None):
    """Production-only entry: all TRAIN and >=100000 observed rows per field."""
    design, targets, valid = _inputs(design, targets, valid, ridge_alpha)
    if len(roles) != design.shape[0] or any(role != "TRAIN" for role in roles):
        raise ValueError("Element-reference fitting accepts TRAIN molecules only")
    if (valid.sum(axis=0) < MIN_PRODUCTION_VALID).any():
        raise ValueError("Each field needs at least 100000 valid TRAIN molecules")
    return fit_element_reference_core(design, targets, valid, ridge_alpha=ridge_alpha,
                                      fold_seed=fold_seed, field_names=field_names)


def make_label_parameters(fitted, design, targets, valid, base_normalizations, *,
                          roles, model_name, field_names=None):
    """Build independent DRecipeDataset parameters; never overwrite base D4.

    The supplied observations must be the same full TRAIN cohort used for the
    frozen reference coefficients. Only fields in the residual band get a new
    residual-scale specification. All original-band and untouched fields retain
    exactly their supplied base specification values, including provenance.
    """
    design, targets, valid = _inputs(design, targets, valid, fitted["ridge_alpha"])
    if fitted.get("fit_role") != "TRAIN" or len(roles) != len(design) or any(role != "TRAIN" for role in roles):
        raise ValueError("Derived residual parameters accept TRAIN observations only")
    if not isinstance(model_name, str) or not model_name:
        raise ValueError("An explicit frozen model_name is required")
    fields = fitted["fields"]
    names = tuple(field_names if field_names is not None else [field["field_name"] for field in fields])
    if (names != tuple(field["field_name"] for field in fields)
            or targets.shape[1] != len(names) or fitted["cohort_rows"] != len(design)):
        raise ValueError("Frozen fit field order/cohort does not match normalization inputs")
    parameters = deepcopy(base_normalizations)
    report = []
    for column, field in enumerate(fields):
        name = field["field_name"]
        if name not in parameters:
            raise ValueError("Missing original frozen normalization for " + name)
        observed = valid[:, column]
        if int(observed.sum()) != field["n_valid"]:
            raise ValueError("Frozen valid population differs for " + name)
        value = targets[observed, column]
        policy, _ = reference_policy(field["oof_r2"])
        if policy != field["target_policy"]:
            raise ValueError("Frozen R2 policy differs from taskbook thresholds for " + name)
        if policy == "element_reference_residual":
            coefficients = np.asarray(field["coefficients"], dtype=np.float64)
            if coefficients.shape != (ELEMENTS + 1,) or not np.isfinite(coefficients).all():
                raise ValueError("Invalid frozen elemental coefficients for " + name)
            residual = value - design[observed] @ coefficients
            low, high = np.quantile(residual, [.001, .999], method="linear")
            winsor = np.clip(residual, low, high)
            center, scale = float(winsor.mean()), float(winsor.std(ddof=0))
            if not math.isfinite(scale) or scale <= 0:
                raise ValueError("Degenerate derived residual scale for " + name)
            parameters[name] = {
                "fit_role": "TRAIN", "p_recipe_fitted": True,
                "center": [center], "scale": [scale],
                "element_reference": {"basis": list(range(1, ELEMENTS + 1)),
                                      "coefficients": coefficients[:-1].tolist(),
                                      "intercept": float(coefficients[-1])},
                "winsor_quantiles": {"q0.001": float(low), "q0.999": float(high)},
                "quantile_method": "linear_type7", "std_ddof": 0,
                "n_valid": field["n_valid"], "frozen_model_name": model_name,
                "base_D4_preserved": True, "stored_target_clipped": False,
            }
            standardized = (residual - center) / scale
        else:
            spec = parameters[name]
            center = float(np.asarray(spec["center"]).reshape(-1)[0])
            scale = float(np.asarray(spec["scale"]).reshape(-1)[0])
            if not math.isfinite(center) or not math.isfinite(scale) or scale <= 0:
                raise ValueError("Invalid supplied base normalization for " + name)
            reference = spec.get("element_reference")
            if reference is not None:
                offset = np.full(len(value), reference.get("intercept", 0.), dtype=np.float64)
                for z, coefficient in zip(reference["basis"], reference["coefficients"]):
                    offset += design[observed, int(z) - 1] * coefficient
                value = value - offset
            standardized = (value - center) / scale
        report.append({"field_name": name, "target_policy": policy, "oof_r2": field["oof_r2"],
                       "n_valid": field["n_valid"],
                       "clipped_TRAIN_count": int((np.abs(standardized) > 6.).sum()),
                       "clipping_fraction": float((np.abs(standardized) > 6.).mean())
                       if len(standardized) else None})
    return {"normalizations": parameters, "fit": {
        "schema": "D_ELEMENT_REFERENCE_LABEL_PARAMETERS_V1", "status": "FROZEN_FIT",
        "fit_role": "TRAIN", "model_name": model_name, "field_names": list(names),
        "cohort_rows": len(design), "ridge_alpha": fitted["ridge_alpha"],
        "fold_seed": fitted["fold_seed"], "folds": FOLDS,
        "original_D4_modified": False, "fields": report,
        "reference_fit": deepcopy(fitted)}}
