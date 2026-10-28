"""Independent synthetic math tests only; no data, registry or native physics.

FP64 is confined to small analytic/rotation oracles. Production APIs reject it.
This test source has not itself been collected or executed at source handoff.
"""
import math

import pytest
import torch

from phychem_mfm.model.v3_tensor_math import (
    SOURCE_SIX_ORDER, ROW_CONVENTION, ORTHONORMAL_COORDINATES, COMOVING_ORIGIN,
    GEOMETRY_UNITS, LOSS_UNITS, OBSERVATION_MATH_POLICY, TRAIN_SCALE_ROLE,
    source_six_to_matrix, matrix_to_source_six, source_six_to_orthonormal,
    orthonormal_to_source_six, matrix_to_orthonormal, orthonormal_to_matrix,
    rank2_rotation_operator, transform_observation_operator,
    rank2_from_invariant_coefficients, StandaloneRank2Head,
    radial_huber_observation_loss,
)


def geometry_keywords():
    return dict(origin_semantics=COMOVING_ORIGIN, coordinate_convention=ROW_CONVENTION,
                unit_semantics=GEOMETRY_UNITS)


def loss(prediction, operator, target, membership, **overrides):
    tensors = len(prediction)
    kwargs = dict(source_component_mask=torch.ones(tensors, 6, dtype=torch.bool),
                  loss_eligibility=torch.ones(tensors, dtype=torch.bool),
                  train_scale=torch.tensor(1., dtype=torch.float32), scale_role=TRAIN_SCALE_ROLE,
                  delta=1., normalization_d=torch.tensor(6., dtype=torch.float32),
                  policy=OBSERVATION_MATH_POLICY, operator_coordinates=ORTHONORMAL_COORDINATES,
                  unit_semantics=LOSS_UNITS)
    kwargs.update(overrides)
    return radial_huber_observation_loss(prediction, operator, target, membership, **kwargs)


def rotation(seed):
    # Independent Rodrigues oracle, with preregistered seeds and no rejection.
    generator = torch.Generator().manual_seed(seed)
    axis = torch.randn(3, generator=generator, dtype=torch.float64)
    axis = axis / torch.linalg.vector_norm(axis)
    angle = .7 + torch.rand((), generator=generator, dtype=torch.float64)
    x, y, z = axis.tolist()
    skew = torch.tensor([[0., -z, y], [z, 0., -x], [-y, x, 0.]], dtype=torch.float64)
    identity = torch.eye(3, dtype=torch.float64)
    result = identity + angle.sin() * skew + (1-angle.cos()) * (skew @ skew)
    return result.float(), result


def oracle_matrix(source):
    # Explicit indexing rather than either production conversion.
    return torch.stack((source[..., [0, 1, 3]], source[..., [1, 2, 4]],
                        source[..., [3, 4, 5]]), -2)


def test_source_order_preserves_zz_trace_and_every_member_without_conversion():
    assert SOURCE_SIX_ORDER == ("xx", "xy", "yy", "xz", "yz", "zz")
    source = torch.tensor([[3., 4., 5., 6., 7., 8.], [-2., .3, .9, -.1, .6, 4.]])
    matrix = source_six_to_matrix(source)
    assert torch.equal(matrix, oracle_matrix(source))
    assert torch.equal(matrix_to_source_six(matrix), source)
    assert torch.equal(matrix.diagonal(dim1=-2, dim2=-1).sum(-1), torch.tensor([16., 2.9]))
    torch.testing.assert_close(orthonormal_to_source_six(source_six_to_orthonormal(source)), source,
                               rtol=1e-7, atol=1e-7)


def test_orthonormal_coordinates_are_frobenius_isometry_and_reversible():
    generator = torch.Generator().manual_seed(508)
    source = torch.randn(7, 6, generator=generator)
    q = source_six_to_orthonormal(source)
    oracle = oracle_matrix(source.double())
    torch.testing.assert_close(q.double().square().sum(-1), oracle.square().sum((-1, -2)),
                               rtol=2e-7, atol=2e-7)
    torch.testing.assert_close(orthonormal_to_matrix(q), source_six_to_matrix(source), rtol=1e-7, atol=1e-7)
    assert torch.equal(matrix_to_orthonormal(source_six_to_matrix(source)), q)
    assert q.dtype == torch.float32


@pytest.mark.parametrize("seed", (11, 29, 83))
def test_rotation_action_matches_independent_matrix_oracle_and_is_orthogonal(seed):
    r, oracle_r = rotation(seed)
    q = torch.tensor([.4, -1.2, .8, .3, -.9, 2.1])
    action = rank2_rotation_operator(r, coordinate_convention=ROW_CONVENTION)
    source = q.double() / torch.tensor([1., math.sqrt(2.), 1., math.sqrt(2.), math.sqrt(2.), 1.],
                                      dtype=torch.float64)
    oracle = oracle_r.T @ oracle_matrix(source) @ oracle_r
    actual = orthonormal_to_matrix(action @ q)
    torch.testing.assert_close(actual.double(), oracle, rtol=0, atol=7e-7)
    torch.testing.assert_close(action.T @ action, torch.eye(6), rtol=0, atol=5e-7)


@pytest.mark.parametrize("form", ("symmetric", "traceless"))
@pytest.mark.parametrize("seed", (11, 29, 83))
def test_head_general_rotation_and_comoving_translation_with_invariant_h0(form, seed):
    generator = torch.Generator().manual_seed(310)
    h = torch.randn(8, 4, generator=generator)
    positions = torch.randn(8, 3, generator=generator)
    origins = torch.tensor([[.4, -.3, .9], [-.7, .2, 1.1], [2., 1., -.3]])
    batch = torch.tensor([2, 0, 2, 1, 0, 1, 2, 0])
    torch.manual_seed(314)
    head = StandaloneRank2Head(4, tensor_form=form)
    r, _ = rotation(seed)
    translation = torch.tensor([.8, -1.1, .2])
    original = head(h, positions, batch, origins, **geometry_keywords())
    changed = head(h, positions @ r + translation, batch, origins @ r + translation, **geometry_keywords())
    torch.testing.assert_close(changed, r.T @ original @ r, rtol=2e-6, atol=7e-6)
    if form == "traceless":
        torch.testing.assert_close(original.diagonal(dim1=-2, dim2=-1).sum(-1),
                                   torch.zeros(3), rtol=0, atol=3e-6)
    assert changed.dtype == torch.float32


def test_compensated_head_preserves_cancellation_empty_graphs_and_explicit_graph_order():
    coefficients = torch.tensor([[1e8, 0.], [1., 0.], [-1e8, 0.], [3., .5]])
    positions = torch.tensor([[1., 0., 0.], [1., 0., 0.], [1., 0., 0.], [0., 2., 0.]])
    origins = torch.zeros(4, 3)
    batch = torch.tensor([2, 2, 2, 0])
    output = rank2_from_invariant_coefficients(coefficients, positions, batch, origins,
                                              tensor_form="symmetric", **geometry_keywords())
    expected = torch.zeros(4, 3, 3)
    expected[2, 0, 0] = 1.
    expected[0] = torch.diag(torch.tensor([.5, 12.5, .5]))
    assert torch.equal(output, expected)
    order = torch.tensor([3, 2, 0, 1])
    permuted = rank2_from_invariant_coefficients(coefficients[order], positions[order], batch[order], origins,
                                                tensor_form="symmetric", **geometry_keywords())
    assert torch.equal(permuted, expected)
    graph_order = torch.tensor([2, 0, 3, 1])
    inverse = torch.argsort(graph_order)
    remapped = rank2_from_invariant_coefficients(coefficients, positions, inverse[batch], origins[graph_order],
                                                tensor_form="symmetric", **geometry_keywords())
    assert torch.equal(remapped, output[graph_order])


def test_head_matches_analytic_first_and_nonzero_mixed_second_derivatives():
    head = StandaloneRank2Head(1, tensor_form="symmetric")
    with torch.no_grad():
        head.coefficients.weight.copy_(torch.tensor([[2.], [3.]]))
        head.coefficients.bias.copy_(torch.tensor([.5, -.7]))
    h = torch.tensor([[.8]], requires_grad=True)
    positions = torch.tensor([[.6, -.4, 1.2]], requires_grad=True)
    output = head(h, positions, torch.tensor([0]), torch.zeros(1, 3), **geometry_keywords())
    qxy = output[0, 0, 1]
    dx, dh = torch.autograd.grad(qxy, (positions, h), create_graph=True)
    a = 2 * .8 + .5
    torch.testing.assert_close(dx, torch.tensor([[a * -.4, a * .6, 0.]]), rtol=0, atol=2e-7)
    torch.testing.assert_close(dh, torch.tensor([[2 * .6 * -.4]]), rtol=0, atol=1e-7)
    dxy = torch.autograd.grad(dx[0, 0], positions, retain_graph=True)[0][0, 1]
    dhx = torch.autograd.grad(dh[0, 0], positions)[0][0, 0]
    torch.testing.assert_close(dxy, torch.tensor(a), rtol=0, atol=2e-7)
    torch.testing.assert_close(dhx, torch.tensor(2 * -.4), rtol=0, atol=1e-7)
    assert dxy.abs() > 0 and dhx.abs() > 0


@pytest.mark.parametrize("seed", (11, 29, 83))
def test_transformed_partial_operator_preserves_real_observations_residual_and_loss(seed):
    r, _ = rotation(seed)
    prediction = torch.tensor([[.8, -.3, .6, 1.1, -.4, .2]])
    # Two genuine source components, xy and zz. Missing four have no target slot.
    operator = torch.tensor([[0., 1/math.sqrt(2.), 0., 0., 0., 0.], [0., 0., 0., 0., 0., 1.]])
    target = torch.tensor([.35, -.1])
    membership = torch.tensor([0, 0])
    source_mask = torch.tensor([[False, True, False, False, False, True]])
    action = rank2_rotation_operator(r, coordinate_convention=ROW_CONVENTION)
    transformed = transform_observation_operator(operator, r, coordinate_convention=ROW_CONVENTION,
                                                 operator_coordinates=ORTHONORMAL_COORDINATES)
    before = loss(prediction, operator, target, membership, source_component_mask=source_mask, delta=.1)
    after = loss(prediction @ action.T, transformed, target, membership, source_component_mask=source_mask, delta=.1)
    torch.testing.assert_close(after.residual, before.residual, rtol=0, atol=3e-7)
    torch.testing.assert_close(after.mean, before.mean, rtol=0, atol=5e-8)
    assert torch.equal(after.source_component_mask, source_mask)
    assert after.field_count.item() == 1 and after.observation_count.tolist() == [2]
    assert torch.equal(target, torch.tensor([.35, -.1]))
    # An unchanged source-axis selector is generally wrong after a rotation.
    assert not torch.allclose(operator @ (action @ prediction[0]), operator @ prediction[0], atol=1e-3)


def test_full_six_radial_formula_and_normalization_are_explicit():
    prediction = torch.tensor([[1., 2., 0., 0., 0., 0.], [3., 4., 0., 0., 0., 0.]])
    operator = torch.eye(6).repeat(2, 1)
    membership = torch.arange(2).repeat_interleave(6)
    result = loss(prediction, operator, torch.zeros(12), membership,
                  train_scale=torch.tensor([2., 1.]), normalization_d=torch.tensor([6., 9.]), delta=.5)
    radii = torch.tensor([math.sqrt(5)/2/math.sqrt(6), 5/3], dtype=torch.float64)
    expected = torch.where(radii <= .5, .5*radii.square(), .5*(radii-.25))
    torch.testing.assert_close(result.per_tensor.double(), expected, rtol=0, atol=7e-8)
    torch.testing.assert_close(result.mean.double(), expected.mean(), rtol=0, atol=7e-8)
    assert result.field_count.item() == 2 and result.observation_count.tolist() == [6, 6]


def test_external_eligibility_source_masks_and_zero_observations_are_distinct():
    q = torch.tensor([[1., 0., 0., 0., 0., 0.], [2., 0., 0., 0., 0., 0.], [3., 0., 0., 0., 0., 0.]])
    operator = torch.tensor([[1., 0., 0., 0., 0., 0.], [1., 0., 0., 0., 0., 0.]])
    mask = torch.tensor([[True, False, False, False, False, False], [True]*6, [True]*6])
    eligibility = torch.tensor([True, False, True])
    result = loss(q, operator, torch.zeros(2), torch.tensor([0, 1]),
                  source_component_mask=mask, loss_eligibility=eligibility, delta=10.)
    assert result.active.tolist() == [True, False, False]
    assert result.zero_observation.tolist() == [False, False, True]
    assert result.observation_count.tolist() == [1, 1, 0] and result.field_count.item() == 1
    torch.testing.assert_close(result.mean, torch.tensor(1/12), rtol=0, atol=1e-8)
    assert torch.equal(result.source_component_mask, mask)
    assert torch.equal(result.loss_eligibility, eligibility)
    assert result.source_component_mask.data_ptr() != mask.data_ptr()
    assert result.loss_eligibility.data_ptr() != eligibility.data_ptr()


def test_no_observations_produce_excluded_connected_zero_loss():
    q = torch.ones(2, 6, requires_grad=True)
    result = loss(q, torch.empty(0, 6), torch.empty(0), torch.empty(0, dtype=torch.long))
    assert result.field_count.item() == 0 and result.active.tolist() == [False, False]
    assert result.zero_observation.tolist() == [True, True] and result.mean.item() == 0.
    result.mean.backward()
    assert torch.equal(q.grad, torch.zeros_like(q))


def test_scalar_train_scale_broadcast_matches_explicit_per_tensor_scale():
    q = torch.tensor([[.4]*6, [.8]*6])
    operator = torch.eye(6).repeat(2, 1)
    membership = torch.arange(2).repeat_interleave(6)
    scalar = loss(q, operator, torch.zeros(12), membership, train_scale=torch.tensor(2.))
    expanded = loss(q, operator, torch.zeros(12), membership, train_scale=torch.tensor([2., 2.]))
    assert torch.equal(scalar.mean, expanded.mean) and torch.equal(scalar.per_tensor, expanded.per_tensor)


def test_packed_observation_order_and_graph_source_order_are_recoverable():
    q = torch.tensor([[.1, .2, .3, .4, .5, .6], [1., 2., 3., 4., 5., 6.], [-.1]*6])
    membership = torch.tensor([2, 0, 2, 1, 0])
    operator = torch.eye(6)[torch.tensor([5, 2, 1, 0, 4])]
    target = torch.tensor([.2, .1, -.4, 1., .6])
    before = loss(q, operator, target, membership)
    order = torch.tensor([4, 1, 3, 0, 2])
    after = loss(q, operator[order], target[order], membership[order])
    torch.testing.assert_close(after.per_tensor, before.per_tensor, rtol=0, atol=1e-7)
    assert torch.equal(after.residual[torch.argsort(order)], before.residual)
    graph_order = torch.tensor([1, 2, 0])
    inverse = torch.argsort(graph_order)
    remapped = loss(q[graph_order], operator, target, inverse[membership])
    assert torch.equal(remapped.per_tensor, before.per_tensor[graph_order])


def test_radial_linear_branch_gradient_and_nonzero_mixed_hessian_match_analytic_oracle():
    q = torch.tensor([[1.1, -.7, .4, .2, -.1, .6]], requires_grad=True)
    operator = torch.tensor([[1., .3, -.2, 0., 0., 0.], [.4, 1.2, .5, 0., 0., 0.],
                             [-.2, .4, 1.1, 0., 0., 0.]])
    target = torch.tensor([-.3, .2, .1])
    scale, dimension, delta = 1.3, 6., .2
    result = loss(q, operator, target, torch.zeros(3, dtype=torch.long),
                  train_scale=torch.tensor(scale), normalization_d=torch.tensor(dimension), delta=delta)
    grad = torch.autograd.grad(result.mean, q, create_graph=True)[0]
    hessian_row = torch.autograd.grad(grad[0, 0], q)[0][0]
    a = operator.double()
    s = torch.tensor(scale).double()
    u = (a @ q.detach()[0].double() - target.double()) / s
    norm = torch.linalg.vector_norm(u)
    radius = norm / math.sqrt(dimension)
    assert radius > delta
    at_u = a.T @ u
    expected_grad = delta * at_u / (s * dimension * radius)
    expected_hessian = delta / (s.square() * dimension * radius) * (
        a.T @ a - torch.outer(at_u, at_u) / norm.square())
    torch.testing.assert_close(grad[0].double(), expected_grad, rtol=3e-6, atol=2e-7)
    torch.testing.assert_close(hessian_row.double(), expected_hessian[0], rtol=4e-6, atol=2e-7)
    assert expected_hessian[0, 1].abs() > 1e-3 and hessian_row[1].abs() > 1e-3


def test_zero_residual_quadratic_hessian_remains_connected_and_correct():
    q = torch.zeros(1, 6, requires_grad=True)
    a = torch.tensor([[1., 2., 0., 0., 0., 0.], [0., 1., 0., 0., 0., 0.]])
    result = loss(q, a, torch.zeros(2), torch.tensor([0, 0]), train_scale=torch.tensor(2.), delta=.5)
    gradient = torch.autograd.grad(result.mean, q, create_graph=True)[0]
    row = torch.autograd.grad(gradient[0, 0], q)[0][0]
    assert torch.equal(gradient, torch.zeros_like(q))
    torch.testing.assert_close(row, (a.T @ a)[0] / 24, rtol=0, atol=1e-8)
    assert row[1] > 0


@pytest.mark.parametrize("fault", ("zero", "negative", "nan", "inf", "axis_scale", "wrong_role", "fp64"))
def test_invalid_or_non_train_scale_is_rejected(fault):
    scale = torch.tensor(1.)
    role = TRAIN_SCALE_ROLE
    if fault == "zero": scale = torch.tensor(0.)
    elif fault == "negative": scale = torch.tensor(-1.)
    elif fault == "nan": scale = torch.tensor(float("nan"))
    elif fault == "inf": scale = torch.tensor(float("inf"))
    elif fault == "axis_scale": scale = torch.ones(1, 6)
    elif fault == "wrong_role": role = "ROUTINE_VAL"
    else: scale = scale.double()
    with pytest.raises(ValueError):
        loss(torch.zeros(1, 6), torch.eye(6), torch.zeros(6), torch.zeros(6, dtype=torch.long),
             train_scale=scale, scale_role=role)


@pytest.mark.parametrize("fault", ("origin_semantics", "unit_semantics", "coordinate_convention", "origin_shape",
                                   "origin_nan", "bad_graph", "fp64_positions", "unknown_form"))
def test_unknown_geometry_or_physics_semantics_are_not_inferred(fault):
    kwargs = geometry_keywords()
    positions = torch.ones(2, 3)
    origins = torch.zeros(1, 3)
    batch = torch.tensor([0, 0])
    form = "symmetric"
    if fault == "origin_semantics": kwargs["origin_semantics"] = "infer_COM_or_fixed_native"
    elif fault == "unit_semantics": kwargs["unit_semantics"] = "auto_angstrom_to_bohr"
    elif fault == "coordinate_convention": kwargs["coordinate_convention"] = "column_Rx"
    elif fault == "origin_shape": origins = torch.zeros(3)
    elif fault == "origin_nan": origins[0, 0] = float("nan")
    elif fault == "bad_graph": batch[1] = 1
    elif fault == "fp64_positions": positions = positions.double()
    else: form = "guess_from_registry_name"
    with pytest.raises(ValueError):
        rank2_from_invariant_coefficients(torch.ones(2, 2), positions, batch, origins,
                                         tensor_form=form, **kwargs)


@pytest.mark.parametrize("fault", ("shape", "nan", "reflection", "nonorthogonal", "convention", "coordinates"))
def test_invalid_rotation_or_observation_convention_is_rejected(fault):
    r = torch.eye(3)
    convention, coordinates = ROW_CONVENTION, ORTHONORMAL_COORDINATES
    if fault == "shape": r = torch.eye(2)
    elif fault == "nan": r[0, 0] = float("nan")
    elif fault == "reflection": r[0, 0] = -1
    elif fault == "nonorthogonal": r[0, 0] = 2
    elif fault == "convention": convention = "column_Rx"
    else: coordinates = "unweighted_source_six"
    with pytest.raises(ValueError):
        transform_observation_operator(torch.eye(6), r, coordinate_convention=convention,
                                       operator_coordinates=coordinates)


@pytest.mark.parametrize("fault", ("policy", "units", "dimension", "dimension_nan", "dimension_shape", "delta",
                                   "delta_underflow", "delta_overflow", "target_nan", "operator_nan",
                                   "operator_shape", "membership", "source_mask", "eligibility"))
def test_invalid_loss_contracts_fail_instead_of_repairing_masks_or_targets(fault):
    q, a, y, ids = torch.zeros(1, 6), torch.eye(6), torch.zeros(6), torch.zeros(6, dtype=torch.long)
    overrides = {}
    if fault == "policy": overrides["policy"] = "infer_complete_from_coverage"
    elif fault == "units": overrides["unit_semantics"] = "auto_rescale"
    elif fault == "dimension": overrides["normalization_d"] = torch.tensor(0.)
    elif fault == "dimension_nan": overrides["normalization_d"] = torch.tensor(float("nan"))
    elif fault == "dimension_shape": overrides["normalization_d"] = torch.ones(1, 6)
    elif fault == "delta": overrides["delta"] = float("nan")
    elif fault == "delta_underflow": overrides["delta"] = 1e-100
    elif fault == "delta_overflow": overrides["delta"] = 1e100
    elif fault == "target_nan": y[0] = float("nan")
    elif fault == "operator_nan": a[0, 0] = float("nan")
    elif fault == "operator_shape": a = a[:, :5]
    elif fault == "membership": ids[0] = 1
    elif fault == "source_mask": overrides["source_component_mask"] = torch.ones(1, 6)
    else: overrides["loss_eligibility"] = torch.ones(1)
    with pytest.raises(ValueError): loss(q, a, y, ids, **overrides)


def test_nonsymmetric_matrix_wrong_six_width_and_fp64_are_rejected():
    matrix = torch.eye(3)
    matrix[0, 1] = .1
    with pytest.raises(ValueError): matrix_to_source_six(matrix)
    with pytest.raises(ValueError): source_six_to_matrix(torch.zeros(5))
    with pytest.raises(ValueError): source_six_to_orthonormal(torch.zeros(6, dtype=torch.float64))


def test_production_forward_backward_never_create_fp64_or_mutate_backend_flags():
    from torch.utils._python_dispatch import TorchDispatchMode
    from torch.utils._pytree import tree_leaves
    class ForbidFP64(TorchDispatchMode):
        def __torch_dispatch__(self, func, types, args=(), kwargs=None):
            output = func(*args, **(kwargs or {}))
            assert not any(isinstance(value, torch.Tensor) and value.dtype == torch.float64
                           for value in tree_leaves(output))
            return output
    before = (torch.are_deterministic_algorithms_enabled(), torch.get_float32_matmul_precision(),
              torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
    head = StandaloneRank2Head(2, tensor_form="symmetric")
    h = torch.tensor([[.2, .4], [-.3, .1]], requires_grad=True)
    positions = torch.tensor([[.5, -.2, 1.], [-.1, .6, -.4]], requires_grad=True)
    with ForbidFP64():
        matrix = head(h, positions, torch.tensor([0, 0]), torch.zeros(1, 3), **geometry_keywords())
        q = matrix_to_orthonormal(matrix)
        r = torch.eye(3)
        transformed = transform_observation_operator(torch.eye(6), r, coordinate_convention=ROW_CONVENTION,
                                                     operator_coordinates=ORTHONORMAL_COORDINATES)
        result = loss(q, transformed, torch.zeros(6), torch.zeros(6, dtype=torch.long))
        first = torch.autograd.grad(result.mean, (h, positions), create_graph=True)
        torch.autograd.grad(sum(value.square().sum() for value in first), (h, positions))
    assert before == (torch.are_deterministic_algorithms_enabled(), torch.get_float32_matmul_precision(),
                      torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
