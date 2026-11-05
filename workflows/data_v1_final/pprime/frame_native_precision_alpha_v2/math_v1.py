"""Predeclared proper-rotation tests; axes are inferred from real output coordinates."""
from __future__ import annotations

import math
import re

ROTATION = [[-2/3, 2/15, 11/15], [2/3, -1/3, 2/3], [1/3, 14/15, 2/15]]
FLOAT = r'[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][-+]?\d+)?'
EH_TO_EV = 27.211386245988
BOHR_TO_A = 0.529177210903
AU_DIPOLE_TO_DEBYE = 2.541746473


def rounding_halfwidth(token):
    parts = re.split('[eEdD]', token.strip())
    mantissa, exponent = parts[0], int(parts[1]) if len(parts) == 2 else 0
    decimals = len(mantissa.split('.', 1)[1]) if '.' in mantissa else 0
    return .5 * 10.0 ** (exponent - decimals)


def checked_rotation(matrix=ROTATION):
    import numpy as np
    r = np.asarray(matrix, dtype=float)
    if r.shape != (3, 3) or not np.allclose(r @ r.T, np.eye(3), atol=1e-14, rtol=0) or not abs(np.linalg.det(r)-1) <= 1e-14:
        raise ValueError('AUDIT_REQUIRES_PROPER_ORTHOGONAL_ROTATION')
    return r


def rotation_case(clean, record_id, task, protocol, arm, rotation=ROTATION, noisy_companion=False):
    """Keep WP5 seed/keyword/sigma; compensate only audit-arm input coordinates.

    The gradient invocation still adds its original deterministic noise. This
    function makes its FINAL rendered noisy coordinates a true rotated pair.
    """
    import hashlib
    import numpy as np
    clean = np.asarray(clean, dtype=float)
    r = checked_rotation(rotation) if arm == 'rotated' else np.eye(3)
    seed = 1 + int(hashlib.sha256((str(protocol['seed'])+'|'+record_id).encode()).hexdigest()[:16], 16) % 2147483646
    noise = np.random.default_rng(seed).normal(0, protocol['perturb_sigma_A'], clean.shape)
    base_actual = clean + noise if task.get('perturbed') or noisy_companion else clean
    target = base_actual @ r.T
    supplied = target - noise if task.get('perturbed') else target
    return {'native_coordinates_A': supplied.tolist(), 'expected_actual_coordinates_A': target.tolist(),
            'perturb_seed': seed if task.get('perturbed') or noisy_companion else None,
            'rotation_matrix': r.tolist(), 'noisy_singlepoint_companion': noisy_companion,
            'noise_precompensation_is_audit_only': bool(task.get('perturbed') and arm == 'rotated')}


def output_frame(input_A, output_A, coordinate_atol_A):
    import numpy as np
    x, y = np.asarray(input_A, float), np.asarray(output_A, float)
    if x.shape != y.shape or x.ndim != 2 or x.shape[1] != 3 or not np.isfinite(y).all():
        return {'status': 'INVALID_OUTPUT_COORDINATES', 'supports_input_axes': False}
    delta = float(np.max(np.abs(x-y)))
    xc, yc = x-x.mean(0), y-y.mean(0)
    u, singular, vt = np.linalg.svd(xc.T @ yc)
    fix = np.diag([1., 1., 1. if np.linalg.det(u @ vt) >= 0 else -1.])
    q = u @ fix @ vt
    rotation = q.T
    translation = y.mean(0)-rotation @ x.mean(0)
    residual = float(np.sqrt(np.mean(np.sum((xc @ q-yc)**2, axis=1))))
    rank = int(np.linalg.matrix_rank(xc, tol=1e-8))
    same = delta <= coordinate_atol_A
    return {'status': 'MATCHES_INPUT_COORDINATES' if same else
                     'PROPER_RIGID_REORIENTATION' if residual <= coordinate_atol_A else 'GEOMETRY_OR_ORDER_CHANGED',
            'supports_input_axes': same, 'max_abs_coordinate_difference_A': delta,
            'proper_fit_RMSD_A': residual, 'input_to_output_rotation': rotation.tolist(),
            'translation_A': translation.tolist(), 'centered_coordinate_rank': rank,
            'rotation_identifiable': rank >= 2, 'fit_determinant': float(np.linalg.det(rotation))}


def covariance(base, rotated, eps_base, eps_rotated, tolerance, rotation=ROTATION):
    import numpy as np
    x, y = np.asarray(base, float), np.asarray(rotated, float)
    if x.shape != y.shape or x.shape[-1:] != (3,) or not np.isfinite(x).all() or not np.isfinite(y).all():
        return {'status': 'INVALID_VECTOR_SHAPE_OR_NONFINITE', 'pass': False}
    r = checked_rotation(rotation)
    expected = x @ r.T
    ex, ey = np.broadcast_to(eps_base, x.shape), np.broadcast_to(eps_rotated, y.shape)
    rounding_bound = ex @ np.abs(r).T + ey
    allowance = tolerance['atol'] + tolerance['rtol'] * np.maximum(np.abs(expected), np.abs(y)) + rounding_bound
    difference = np.abs(y-expected)
    max_norm = float(max(np.max(np.linalg.norm(x.reshape(-1, 3), axis=1)),
                         np.max(np.linalg.norm(y.reshape(-1, 3), axis=1))))
    signal = max_norm >= tolerance['minimum_vector_norm']
    passed = bool(np.all(difference <= allowance))
    return {'status': 'COVARIANT' if passed and signal else 'INSUFFICIENT_VECTOR_SIGNAL' if passed else 'NOT_COVARIANT',
            'pass': passed and signal, 'within_numeric_allowance': passed,
            'sufficient_signal': signal, 'max_vector_norm': max_norm,
            'max_abs_residual': float(difference.max()), 'max_allowance': float(allowance.max()),
            'max_rounding_propagation_bound': float(rounding_bound.max()),
            'exceeding_components': int((difference > allowance).sum())}


def force_relation(gradient_Eh_bohr, forces_eV_A, tolerance=2e-12):
    import numpy as np
    g, f = np.asarray(gradient_Eh_bohr, float), np.asarray(forces_eV_A, float)
    if g.shape != f.shape or g.ndim != 2 or g.shape[1] != 3:
        return {'pass': False, 'status': 'GRADIENT_FORCE_SHAPE_MISMATCH'}
    residual = f + g * EH_TO_EV / BOHR_TO_A
    allowed = tolerance * (1 + np.abs(f))
    return {'pass': bool(np.all(np.abs(residual) <= allowed)),
            'max_abs_residual_eV_A': float(np.abs(residual).max()),
            'definition': 'force_eV_A = -gradient_Eh_bohr * 27.211386245988 / 0.529177210903'}


def mechanical_diagnostics(coordinates_A, gradient_Eh_bohr):
    import numpy as np
    x, g = np.asarray(coordinates_A, float)/BOHR_TO_A, np.asarray(gradient_Eh_bohr, float)
    if x.shape != g.shape:
        return {'status': 'SHAPE_UNAVAILABLE'}
    return {'status': 'DIAGNOSTIC_ONLY_NOT_A_FINITE_DIFFERENCE_VALIDATION',
            'sum_gradient_Eh_bohr': g.sum(0).tolist(),
            'net_gradient_norm_Eh_bohr': float(np.linalg.norm(g.sum(0))),
            'torque_Eh': np.cross(x-x.mean(0), g).sum(0).tolist(),
            'torque_norm_Eh': float(np.linalg.norm(np.cross(x-x.mean(0), g).sum(0)))}


def tensor_matrix(six):
    import numpy as np
    q = np.asarray(six, float)
    if q.shape != (6,) or not np.isfinite(q).all():
        raise ValueError('KEEP_ALL_SIX_QUADRUPOLE_COMPONENTS')
    xx, xy, yy, xz, yz, zz = q
    return np.asarray([[xx, xy, xz], [xy, yy, yz], [xz, yz, zz]])


def tensor_checks(six, eps_six):
    import numpy as np
    q, eps = tensor_matrix(six), tensor_matrix(eps_six)
    bound = float(np.trace(eps)) + 1e-10
    return {'component_order': ['xx', 'xy', 'yy', 'xz', 'yz', 'zz'],
            'all_six_components_retained': True,
            'symmetry': 'implied by six-component encoding; no independent yx/zx/zy measurements',
            'trace': float(np.trace(q)), 'trace_rounding_bound': bound,
            'trace_within_rounding': bool(abs(np.trace(q)) <= bound)}


def tensor_covariance(base, rotated, eps_base, eps_rotated, tolerance, rotation=ROTATION):
    import numpy as np
    q, qr = tensor_matrix(base), tensor_matrix(rotated)
    e0, e1 = tensor_matrix(eps_base), tensor_matrix(eps_rotated)
    r = checked_rotation(rotation)
    expected = r @ q @ r.T
    rounding = np.abs(r) @ e0 @ np.abs(r).T + e1
    allowance = tolerance['atol'] + tolerance['rtol'] * np.maximum(np.abs(expected), np.abs(qr)) + rounding
    error = np.abs(qr-expected)
    signal = max(float(np.linalg.norm(q)), float(np.linalg.norm(qr))) >= tolerance['minimum_tensor_norm']
    passed = bool(np.all(error <= allowance))
    return {'pass': passed and signal, 'within_numeric_allowance': passed,
            'sufficient_signal': signal, 'max_abs_residual_au': float(error.max()),
            'max_allowance_au': float(allowance.max()), 'rounding_bound_au': float(rounding.max()),
            'rule': 'Q_rotated = R @ Q_base @ R.T; same origin, all six storage components retained'}


def tensor_translation(base, translated, dipole_au, translation_A, eps_base,
                       eps_translated, eps_dipole_au, tolerance, total_charge=0.):
    """Active geometry shift r -> r+a for xTB's 3/2 traceless convention."""
    import numpy as np
    q, qt = tensor_matrix(base), tensor_matrix(translated)
    a = np.asarray(translation_A, float)/BOHR_TO_A
    mu = np.asarray(dipole_au, float)
    expected = q + 1.5*(np.outer(a, mu)+np.outer(mu, a))-np.dot(a, mu)*np.eye(3)
    expected += .5*total_charge*(3*np.outer(a, a)-np.dot(a, a)*np.eye(3))
    em = np.asarray(eps_dipole_au, float)
    rounding = tensor_matrix(eps_base)+tensor_matrix(eps_translated)
    rounding += 1.5*(np.outer(np.abs(a), em)+np.outer(em, np.abs(a)))
    rounding += np.dot(np.abs(a), em)*np.eye(3)
    allowance = tolerance['atol']+tolerance['rtol']*np.maximum(np.abs(expected), np.abs(qt))+rounding
    error = np.abs(qt-expected)
    return {'pass': bool(np.all(error <= allowance)), 'max_abs_residual_au': float(error.max()),
            'max_allowance_au': float(allowance.max()), 'translation_A': list(translation_A),
            'total_charge': total_charge,
            'origin': 'program Cartesian origin; no recentering/projection in this audit',
            'rule': 'Q(r+a)=Q(r)+3/2(a*mu.T+mu*a.T)-(a.dot(mu))*I+q/2(3*a*a.T-|a|^2*I)'}
