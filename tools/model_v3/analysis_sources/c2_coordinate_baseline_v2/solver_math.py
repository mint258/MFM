"""TRAIN-only sparse ridge conditioning diagnostics, never a new C2 baseline.

Original coordinates: J(c)=||A c-b||^2/n_atoms + ridge*||c||^2.
The RHS supplied here is already b/sqrt(n_atoms), as in the fixed C2 core.
No dense coefficient Gram matrix is constructed by this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math

import numpy as np
from scipy import sparse
from scipy.sparse.linalg import lsqr


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _integer(value, minimum=0):
    require(type(value) is int and value >= minimum, "Explicit bounded integer required")
    return value


def csr_fingerprint(matrix, *, check=lambda: None):
    require(sparse.isspmatrix_csr(matrix) and matrix.dtype == np.float64, "Original float64 CSR required")
    result = {"shape": list(matrix.shape), "nnz": int(matrix.nnz), "dtype": str(matrix.dtype)}
    for name in ("data", "indices", "indptr"):
        array = getattr(matrix, name)
        require(array.flags.c_contiguous, "Contiguous original CSR buffers required")
        raw = memoryview(array).cast("B")
        sha = hashlib.sha256()
        for start in range(0, len(raw), 8*1024**2):
            check(); sha.update(raw[start:start+8*1024**2])
        result[name+"_sha256"] = sha.hexdigest()
        result[name+"_bytes"] = int(array.nbytes)
    return result


def column_norm_squared(matrix, *, check=lambda: None, chunk=1024**2):
    """Bounded temporary storage; never forms A.T@A or copies all squared data."""
    require(sparse.isspmatrix_csr(matrix) and matrix.dtype == np.float64, "Original float64 CSR required")
    _integer(chunk, 1)
    values = np.zeros(matrix.shape[1], dtype=np.float64)
    for start in range(0, matrix.nnz, chunk):
        check()
        data = matrix.data[start:start+chunk]
        require(np.isfinite(data).all(), "Finite TRAIN design entries required")
        values += np.bincount(matrix.indices[start:start+chunk], weights=np.square(data), minlength=matrix.shape[1])
    require(np.isfinite(values).all() and (values >= 0).all(), "Finite nonnegative column norms required")
    return values


def numerical_state(matrix, rhs_normalized, coefficient, *, n_atoms, ridge, check=lambda: None):
    _integer(n_atoms, 1)
    require(matrix.shape[0] == 3*n_atoms and ridge > 0 and math.isfinite(ridge), "Original atom-based ridge normalization required")
    rhs = np.asarray(rhs_normalized, dtype=np.float64)
    coefficient = np.asarray(coefficient, dtype=np.float64)
    require(rhs.shape == (matrix.shape[0],) and coefficient.shape == (matrix.shape[1],)
            and np.isfinite(rhs).all() and np.isfinite(coefficient).all(), "Finite original-coordinate vectors required")
    check()
    root = math.sqrt(n_atoms)
    residual = matrix @ coefficient/root-rhs
    normal = matrix.T @ residual/root+ridge*coefficient
    reference = matrix.T @ rhs/root
    check()
    data_term = float(residual @ residual)
    ridge_term = float(ridge*(coefficient @ coefficient))
    absolute = float(np.linalg.norm(normal))
    reference_norm = float(np.linalg.norm(reference))
    return {"TRAIN_mean_atom_squared_vector_error_A2": data_term,
        "TRAIN_component_MSE_A2": data_term/3, "ridge_penalty": ridge_term,
        "original_objective": data_term+ridge_term, "original_normal_residual_norm": absolute,
        "original_rhs_gradient_norm": reference_norm,
        "relative_original_normal_residual": absolute/reference_norm if reference_norm > 0 else None,
        "relative_normal_residual_defined": reference_norm > 0,
        "normal_equation": "A.T@(A@c-b)/n_atoms + ridge*c", "acceptance_threshold_applied": False}


def lsqr_statistics(solved):
    """Persist even a failed solver's stop/iteration fields without hiding inf."""
    require(len(solved) >= 9, "Known scipy LSQR result tuple required")
    names = ("rnorm", "damped_rnorm", "anorm", "acond", "arnorm", "xnorm")
    result = {"stop_code": int(solved[1]), "iterations": int(solved[2]), "nonfinite_fields": []}
    for name, value in zip(names, solved[3:9]):
        value = float(value)
        result[name] = value if math.isfinite(value) else None
        if not math.isfinite(value): result["nonfinite_fields"].append(name)
    result["coefficients_finite"] = bool(np.isfinite(solved[0]).all())
    return result


@dataclass
class AugmentedSystem:
    matrix: object
    rhs: np.ndarray
    active_columns: np.ndarray
    scale: np.ndarray
    original_columns: int
    metadata: dict

    def original_coefficient(self, z):
        z = np.asarray(z, dtype=np.float64)
        require(z.shape == self.scale.shape and np.isfinite(z).all(), "Finite active scaled coefficient required")
        full = np.zeros(self.original_columns, dtype=np.float64)
        full[self.active_columns] = z/self.scale
        return full


def augmented_active_jacobi(matrix, rhs_normalized, support, *, n_atoms, ridge,
                            numeric_budget_bytes=8*1024**3, check=lambda: None):
    """Build [A_active/(sqrt(n)*D); sqrt(ridge)/D], with damp=0.

    D_k=sqrt(||A[:,k]||^2/n+ridge). Omitting zero-support columns is exact
    because those columns are zero and positive ridge uniquely gives c_k=0.
    All writes are to new sparse matrices/arrays, never the captured TRAIN CSR.
    """
    _integer(n_atoms, 1); _integer(numeric_budget_bytes, 1)
    require(sparse.isspmatrix_csr(matrix) and matrix.dtype == np.float64 and matrix.shape[0] == 3*n_atoms,
            "Original float64 three-component TRAIN CSR required")
    require(type(ridge) in (int, float) and math.isfinite(ridge) and ridge > 0, "Positive original ridge required")
    rhs = np.asarray(rhs_normalized, dtype=np.float64)
    support = np.asarray(support)
    require(rhs.shape == (matrix.shape[0],) and np.isfinite(rhs).all()
            and support.shape == (matrix.shape[1],) and np.issubdtype(support.dtype, np.integer)
            and (support >= 0).all(), "Bound original RHS/support dimensions required")
    k, rows = int(np.count_nonzero(support)), matrix.shape[0]
    source_bytes = int(matrix.data.nbytes+matrix.indices.nbytes+matrix.indptr.nbytes)
    # Conservative phase-local bound: captured A, sliced/scaled A, final B,
    # sparse stacking copy, dense work/coefficient vectors and bounded norm chunk.
    numeric_upper = 4*source_bytes + 8*(14*rows+24*matrix.shape[1]+24*k) + 32*1024**2
    require(numeric_upper <= numeric_budget_bytes, "Diagnostic sparse numeric bound exceeds declared budget")
    before = csr_fingerprint(matrix, check=check)
    norms = column_norm_squared(matrix, check=check)
    require(np.equal(norms[support == 0], 0).all(), "Unobserved support column is not mathematically zero")
    active = np.flatnonzero(support > 0)
    scale = np.sqrt(norms[active]/n_atoms+ridge)
    check()
    scaled = matrix[:, active].astype(np.float64, copy=True)
    if scaled.nnz:
        scaled.data *= 1/(math.sqrt(n_atoms)*scale[scaled.indices])
    lower = sparse.diags(math.sqrt(ridge)/scale, offsets=0, shape=(k, k), format="csr") if k else sparse.csr_matrix((0, 0))
    augmented = sparse.vstack((scaled, lower), format="csr")
    target = np.concatenate((rhs, np.zeros(k, dtype=np.float64)))
    require(csr_fingerprint(matrix, check=check) == before, "Original TRAIN CSR changed during preconditioning")
    return AugmentedSystem(augmented, target, active, scale, matrix.shape[1], {
        "status": "DIAGNOSTIC_ONLY_NOT_BASELINE_ACCEPTANCE", "original_shape": list(matrix.shape),
        "original_nnz": int(matrix.nnz), "observed_support_columns": k,
        "observed_zero_norm_columns": int((norms[active] == 0).sum()),
        "inactive_zero_columns": matrix.shape[1]-k, "augmented_shape": list(augmented.shape),
        "augmented_nnz": int(augmented.nnz), "numeric_upper_bytes": numeric_upper,
        "dense_gram_constructed": False, "original_CSR_unchanged": True,
        "scale": "sqrt(column_squared_norm/n_atoms + ridge)",
        "operator": "[A_active/(sqrt(n_atoms)*D); sqrt(ridge)/D]", "damp": 0.,
        "warm_start_used": False, "ridge_center": "zero in original coefficient coordinates"})


def solve_augmented(system, *, atol=1e-8, btol=1e-8, condition_limit=1e8,
                    maximum_iterations=2000, check=lambda: None):
    from scipy.sparse.linalg import LinearOperator
    _integer(maximum_iterations, 1)
    require(atol == btol == 1e-8 and condition_limit == 1e8 and maximum_iterations <= 2000,
            "Preregistered diagnostic stopping limits required")
    if system.matrix.shape[1] == 0:
        return system.original_coefficient(np.empty(0)), {"solver_called": False,
            "stop_code": None, "iterations": 0, "reason": "no active columns; exact ridge solution is zero"}
    def matvec(z):
        check(); return system.matrix @ z
    def rmatvec(v):
        check(); return system.matrix.T @ v
    operator = LinearOperator(system.matrix.shape, matvec=matvec, rmatvec=rmatvec, dtype=np.float64)
    solved = lsqr(operator, system.rhs, damp=0., atol=atol, btol=btol, conlim=condition_limit,
                  iter_lim=maximum_iterations, show=False, x0=None)
    check()
    require(np.isfinite(solved[0]).all(), "Diagnostic solver produced nonfinite coefficients")
    return system.original_coefficient(solved[0]), {"solver_called": True, **lsqr_statistics(solved)}
