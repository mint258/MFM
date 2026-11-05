"""Small synthetic dense oracles verify the TRAIN-only sparse transformation."""
import math

import numpy as np
import pytest
from scipy import sparse
from scipy.sparse.linalg import lsqr

from solver_math import (augmented_active_jacobi, column_norm_squared,
    csr_fingerprint, lsqr_statistics, numerical_state, solve_augmented)


def system():
    # Deliberately unequal column scales, a correlated column, and one unknown.
    a = np.array([[1e-3, 10., 1., 0.], [2e-3, -3., 2., 0.],
                  [-1e-3, 7., -1., 0.], [3e-3, 4., 1., 0.],
                  [2e-3, -2., 3., 0.], [-2e-3, 8., 2., 0.]], dtype=np.float64)
    b = np.array([.3, -.1, .2, .4, -.2, .1])
    return a, b, 2, 1e-4, np.array([6, 6, 6, 0], dtype=np.int64)


def test_active_jacobi_matches_full_dense_ridge_oracle_in_original_coordinates():
    a, b, n, ridge, support = system()
    matrix = sparse.csr_matrix(a)
    before = csr_fingerprint(matrix)
    transformed = augmented_active_jacobi(matrix, b/math.sqrt(n), support, n_atoms=n, ridge=ridge)
    coefficient, stats = solve_augmented(transformed)
    oracle = np.linalg.solve(a.T@a/n+ridge*np.eye(a.shape[1]), a.T@b/n)
    assert np.allclose(coefficient, oracle, rtol=2e-7, atol=1e-9)
    assert coefficient[-1] == 0. and len(transformed.active_columns) == 3
    assert csr_fingerprint(matrix) == before and sparse.isspmatrix_csr(transformed.matrix)
    assert transformed.metadata["damp"] == 0. and not transformed.metadata["warm_start_used"]
    assert stats["solver_called"] and stats["stop_code"] in (0, 1, 2, 4, 5)
    state = numerical_state(matrix, b/math.sqrt(n), coefficient, n_atoms=n, ridge=ridge)
    assert state["relative_original_normal_residual"] < 1e-8
    assert state["original_objective"] == pytest.approx(np.square(a@oracle-b).sum()/n+ridge*(oracle@oracle), rel=1e-10)


def test_jacobi_augmented_objective_is_identical_for_any_trial_vector():
    a, b, n, ridge, support = system()
    transformed = augmented_active_jacobi(sparse.csr_matrix(a), b/math.sqrt(n), support, n_atoms=n, ridge=ridge)
    z = np.array([.2, -.4, .7])
    c = transformed.original_coefficient(z)
    residual = transformed.matrix@z-transformed.rhs
    assert residual@residual == pytest.approx(np.square(a@c-b).sum()/n+ridge*(c@c), rel=1e-12)
    # The columns of the augmented operator have unit diagonal normal curvature.
    assert np.allclose(column_norm_squared(transformed.matrix), 1., rtol=1e-12, atol=1e-12)
    wrong_ridge_after_scaling = np.square((a@c-b)/math.sqrt(n)).sum()+ridge*(z@z)
    assert abs((residual@residual)-wrong_ridge_after_scaling) > 1e-5


def test_atom_and_component_denominators_and_unscaled_ridge_are_distinct():
    a, b, n, ridge, support = system()
    matrix = sparse.csr_matrix(a)
    transformed = augmented_active_jacobi(matrix, b/math.sqrt(n), support, n_atoms=n, ridge=ridge)
    c, _ = solve_augmented(transformed)
    state = numerical_state(matrix, b/math.sqrt(n), c, n_atoms=n, ridge=ridge)
    assert state["TRAIN_mean_atom_squared_vector_error_A2"] == pytest.approx(np.square(a@c-b).sum()/n)
    assert state["TRAIN_component_MSE_A2"] == pytest.approx(np.square(a@c-b).sum()/(3*n))
    unscaled = lsqr(matrix, b, damp=math.sqrt(ridge*n), atol=1e-12, btol=1e-12, iter_lim=2000)[0]
    assert np.allclose(c, unscaled, rtol=2e-7, atol=1e-8)
    wrong = np.linalg.solve(a.T@a/(3*n)+ridge*np.eye(a.shape[1]), a.T@b/(3*n))
    assert np.linalg.norm(c-wrong) > 1e-3


def test_damped_x0_changes_the_regularization_center_but_augmented_damp0_does_not():
    matrix = sparse.csr_matrix(np.array([[1.], [0.], [0.]]))
    rhs = np.zeros(3)
    naive = lsqr(matrix, rhs, damp=1., x0=np.array([2.]), atol=1e-12, btol=1e-12)[0]
    assert naive[0] == pytest.approx(1.)  # minimizes x^2+(x-2)^2, not x^2+x^2.
    transformed = augmented_active_jacobi(matrix, rhs, np.array([1]), n_atoms=1, ridge=1.)
    z = lsqr(transformed.matrix, transformed.rhs, damp=0., x0=2*transformed.scale,
             atol=1e-12, btol=1e-12)[0]
    assert transformed.original_coefficient(z)[0] == pytest.approx(0., abs=1e-12)


def test_unknown_columns_are_exact_zero_and_nonzero_unobserved_column_is_rejected():
    a, b, n, ridge, support = system()
    support[0] = 0
    with pytest.raises(ValueError, match="not mathematically zero"):
        augmented_active_jacobi(sparse.csr_matrix(a), b/math.sqrt(n), support, n_atoms=n, ridge=ridge)


@pytest.mark.parametrize("support", [np.zeros(4, dtype=np.int64), np.array([1, 0, 0, 0], dtype=np.int64)])
def test_zero_design_observed_or_unknown_columns_have_unique_zero_solution(support):
    matrix = sparse.csr_matrix((6, 4), dtype=np.float64)
    rhs = np.arange(6, dtype=np.float64)
    transformed = augmented_active_jacobi(matrix, rhs, support, n_atoms=2, ridge=1e-4)
    c, _ = solve_augmented(transformed)
    assert np.equal(c, 0).all()
    state = numerical_state(matrix, rhs, c, n_atoms=2, ridge=1e-4)
    assert state["original_normal_residual_norm"] == 0
    assert state["relative_original_normal_residual"] is None and not state["relative_normal_residual_defined"]


def test_sparse_transformation_never_requests_a_dense_matrix(monkeypatch):
    a, b, n, ridge, support = system()
    def forbidden(*args, **kwargs):
        raise AssertionError("No dense matrix export or coefficient Gram is allowed")
    monkeypatch.setattr(sparse.csr_matrix, "toarray", forbidden)
    monkeypatch.setattr(sparse.csr_matrix, "todense", forbidden)
    transformed = augmented_active_jacobi(sparse.csr_matrix(a), b/math.sqrt(n), support, n_atoms=n, ridge=ridge)
    c, _ = solve_augmented(transformed)
    assert np.isfinite(c).all() and not transformed.metadata["dense_gram_constructed"]


def test_budget_refusal_and_nonfinite_solver_statistics_preserve_stop_reason():
    a, b, n, ridge, support = system()
    with pytest.raises(ValueError, match="numeric bound"):
        augmented_active_jacobi(sparse.csr_matrix(a), b/math.sqrt(n), support, n_atoms=n, ridge=ridge, numeric_budget_bytes=1024)
    result = (np.ones(2), 7, 500, 1., 2., math.inf, math.inf, .1, .2)
    stats = lsqr_statistics(result)
    assert stats["stop_code"] == 7 and stats["iterations"] == 500
    assert stats["anorm"] is None and stats["acond"] is None
    assert stats["nonfinite_fields"] == ["anorm", "acond"]
