"""Vector robust losses must preserve rotations in both value and gradient."""
import math

import pytest
import torch

from phychem_mfm.phase1.v3_contract import FieldSpec, FieldTarget, LabelRegistry, TrainNormalization
from phychem_mfm.phase1.v3_losses import compute_v3_loss


def evaluate(prediction, target, *, representation="vector", kind="regression", mode="radial_huber_v1"):
    group = "S" if kind == "denoise_eps_mse" else "P"
    field = FieldSpec("v", group, "vector_fixture", "atom" if representation == "vector" else "graph",
                      representation=representation, kind=kind)
    registry = LabelRegistry((field,), "synthetic-vector-loss-v1", "a" * 64)
    norm = TrainNormalization((0.,), (1.,), "b" * 64, "synthetic-vector-loss-v1")
    labels = FieldTarget(target.detach(), torch.ones(len(target), dtype=torch.bool))
    return compute_v3_loss({"v": prediction}, {"v": labels}, registry, {"v": norm},
                            enabled_groups=(group,), vector_loss_mode=mode).total


def test_radial_huber_value_and_gradient_covary_under_joint_rotation_beyond_delta():
    angle = math.pi / 4
    rotation = torch.tensor([[math.cos(angle), -math.sin(angle), 0.],
                             [math.sin(angle), math.cos(angle), 0.], [0., 0., 1.]])
    target = torch.tensor([[.1, .2, -.3], [.4, .3, .2]])
    prediction = (target + torch.tensor([[2., 0., 0.], [.2, 3., -1.]])).requires_grad_()
    loss = evaluate(prediction, target)
    gradient, = torch.autograd.grad(loss, prediction)
    moved = (prediction.detach() @ rotation).requires_grad_()
    moved_loss = evaluate(moved, target @ rotation)
    moved_gradient, = torch.autograd.grad(moved_loss, moved)
    torch.testing.assert_close(moved_loss, loss, atol=2e-7, rtol=1e-6)
    torch.testing.assert_close(moved_gradient, gradient @ rotation, atol=2e-7, rtol=1e-6)


def test_small_vector_residuals_retain_component_mean_quadratic_coefficient():
    prediction = torch.tensor([[.2, .3, -.1], [.1, -.1, .4]], requires_grad=True)
    target = torch.zeros_like(prediction)
    loss = evaluate(prediction, target)
    expected = .5 * prediction.square().mean()
    torch.testing.assert_close(loss, expected, atol=1e-8, rtol=1e-7)
    actual_grad, = torch.autograd.grad(loss, prediction, retain_graph=True)
    expected_grad, = torch.autograd.grad(expected, prediction)
    torch.testing.assert_close(actual_grad, expected_grad, atol=1e-8, rtol=1e-7)


def test_zero_vector_residual_has_finite_exact_zero_gradient():
    prediction = torch.zeros(2, 3, requires_grad=True)
    loss = evaluate(prediction, torch.zeros_like(prediction))
    loss.backward()
    assert loss.item() == 0 and torch.equal(prediction.grad, torch.zeros_like(prediction))


def test_component_v0_is_explicit_and_rotation_dependent_not_the_default():
    prediction = torch.tensor([[2., 0., 0.]])
    rotated = torch.tensor([[math.sqrt(2.), math.sqrt(2.), 0.]])
    a = evaluate(prediction, torch.zeros_like(prediction), mode="component_huber_v0")
    b = evaluate(rotated, torch.zeros_like(rotated), mode="component_huber_v0")
    assert abs(float(a - b)) > .1
    torch.testing.assert_close(evaluate(prediction, torch.zeros_like(prediction)),
                               evaluate(rotated, torch.zeros_like(rotated)), atol=1e-7, rtol=1e-6)


def test_s_eps_mse_and_scalar_huber_do_not_change_with_vector_mode():
    vector = torch.tensor([[.1, .2, .3]])
    for kind, representation, value in (("denoise_eps_mse", "vector", vector),
                                         ("regression", "scalar", torch.tensor([[2.]]))):
        default = evaluate(value, torch.zeros_like(value), kind=kind, representation=representation)
        replay = evaluate(value, torch.zeros_like(value), kind=kind, representation=representation,
                           mode="component_huber_v0")
        assert torch.equal(default, replay)
    with pytest.raises(ValueError, match="Unknown vector"):
        evaluate(vector, torch.zeros_like(vector), mode="misspelled_mode")
