"""SOURCE-only FP32 rank-2 mathematics; no registry/provider or physics authority.

Six source values are xx,xy,yy,xz,yz,zz.  Orthonormal coordinates multiply
only xy,xz,yz by sqrt(2).  Row coordinates use X'=XR+t and Q'=R^T Q R.
Every origin, unit-consistency assertion and loss policy is caller supplied.
This module neither enables r674 nor selects a jointly pending data policy.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import torch
from torch import Tensor, nn

from .v3_numeric_stability import (
    compensated_index_add, compensated_squared_norm3, require_fp32_context,
)

SOURCE_SIX_ORDER = ("xx", "xy", "yy", "xz", "yz", "zz")
ROW_CONVENTION = "row_XR_plus_t"
ORTHONORMAL_COORDINATES = "frobenius_orthonormal_source_order"
COMOVING_ORIGIN = "explicit_comoving"
GEOMETRY_UNITS = "caller_consistent_no_conversion"
LOSS_UNITS = "prediction_target_scale_consistent_no_conversion"
OBSERVATION_MATH_POLICY = "caller_eligibility_observation_math_only"
TRAIN_SCALE_ROLE = "TRAIN"


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _fp32(value, name):
    _require(isinstance(value, Tensor) and value.dtype == torch.float32
             and value.layout == torch.strided, name + " must be a strided FP32 tensor")
    _require(not torch.is_autocast_enabled(value.device.type), "Tensor math requires autocast disabled")
    _require(bool(torch.isfinite(value).all()), name + " must be finite")


def _convention(coordinate_convention):
    _require(coordinate_convention == ROW_CONVENTION, "Explicit row_XR_plus_t convention required")


def _last_six(value, name):
    _fp32(value, name)
    _require(value.ndim >= 1 and value.size(-1) == 6, name + " must have last dimension six")


def source_six_to_matrix(value: Tensor) -> Tensor:
    """Preserve all source values, including zz and any nonzero trace."""
    _last_six(value, "source six")
    xx, xy, yy, xz, yz, zz = value.unbind(-1)
    return torch.stack((xx, xy, xz, xy, yy, yz, xz, yz, zz), -1).reshape(*value.shape[:-1], 3, 3)


def matrix_to_source_six(value: Tensor) -> Tensor:
    """Read the named upper components; reject nonsymmetric input (FP32 atol 1e-5).

    No averaging, trace projection, unit conversion or missing-value repair occurs.
    The tolerance permits roundoff from a matrix conjugation, not a new physics rule.
    """
    _fp32(value, "symmetric matrix")
    _require(value.ndim >= 2 and value.shape[-2:] == (3, 3), "Matrix must end in 3x3")
    _require(torch.allclose(value, value.transpose(-1, -2), rtol=0, atol=1e-5),
             "Matrix is not symmetric within the explicit FP32 tolerance")
    return torch.stack((value[..., 0, 0], value[..., 0, 1], value[..., 1, 1],
                        value[..., 0, 2], value[..., 1, 2], value[..., 2, 2]), -1)


def _six_weights(value):
    return value.new_tensor((1., math.sqrt(2.), 1., math.sqrt(2.), math.sqrt(2.), 1.))


def source_six_to_orthonormal(value: Tensor) -> Tensor:
    _last_six(value, "source six")
    return value * _six_weights(value)


def orthonormal_to_source_six(value: Tensor) -> Tensor:
    _last_six(value, "orthonormal six")
    return value / _six_weights(value)


def matrix_to_orthonormal(value: Tensor) -> Tensor:
    return source_six_to_orthonormal(matrix_to_source_six(value))


def orthonormal_to_matrix(value: Tensor) -> Tensor:
    return source_six_to_matrix(orthonormal_to_source_six(value))


def _rotation(rotation, coordinate_convention):
    _convention(coordinate_convention)
    _fp32(rotation, "rotation")
    _require(rotation.shape == (3, 3), "One explicit rotation [3,3] required")
    identity = torch.eye(3, dtype=torch.float32, device=rotation.device)
    _require(torch.allclose(rotation.transpose(0, 1) @ rotation, identity, rtol=0, atol=2e-5)
             and bool((torch.linalg.det(rotation) - 1).abs() <= 2e-5),
             "Rotation must be proper orthogonal (FP32 atol 2e-5)")


def rank2_rotation_operator(rotation: Tensor, *, coordinate_convention: str) -> Tensor:
    """Return D[6,6] with column q'=Dq, for q in orthonormal coordinates.

    R is one proper rotation.  This is a mathematical action, not a claim about
    the native source origin, units, sign or fixed-origin translation law.
    """
    _rotation(rotation, coordinate_convention)
    basis = orthonormal_to_matrix(torch.eye(6, dtype=torch.float32, device=rotation.device))
    changed = rotation.transpose(0, 1) @ basis @ rotation
    return matrix_to_orthonormal(changed).transpose(0, 1)


def transform_observation_operator(operator: Tensor, rotation: Tensor, *,
                                   coordinate_convention: str, operator_coordinates: str) -> Tensor:
    """A'=A D(R)^T, retaining the same packed observed y and source identities.

    operator is [K,6], in orthonormal tensor coordinates.  A may describe full
    six, partial source components, or another explicitly supplied linear map.
    A repeated six-bool mask cannot replace this transformation.
    """
    _require(operator_coordinates == ORTHONORMAL_COORDINATES, "Unknown observation coordinate system")
    _fp32(operator, "observation operator")
    _require(operator.ndim == 2 and operator.size(1) == 6, "Observation operator must be [K,6]")
    action = rank2_rotation_operator(rotation, coordinate_convention=coordinate_convention)
    _require(operator.device == rotation.device, "Operator and rotation must share a device")
    return operator @ action.transpose(0, 1)


def _geometry(coefficients, positions, batch, origins, *, tensor_form, origin_semantics,
              coordinate_convention, unit_semantics):
    _convention(coordinate_convention)
    _require(origin_semantics == COMOVING_ORIGIN, "Only explicit comoving origins are supported")
    _require(unit_semantics == GEOMETRY_UNITS, "Explicit consistent geometry units; no conversion inferred")
    _require(tensor_form in ("symmetric", "traceless"), "Explicit symmetric or traceless tensor form required")
    _fp32(coefficients, "invariant coefficients")
    _fp32(positions, "positions")
    _fp32(origins, "explicit per-graph origins")
    width = 2 if tensor_form == "symmetric" else 1
    _require(coefficients.ndim == 2 and coefficients.size(1) == width,
             "Invariant coefficients must be [N,2] symmetric or [N,1] traceless")
    _require(positions.shape == (len(coefficients), 3) and origins.ndim == 2 and origins.size(1) == 3,
             "Positions [N,3] and caller origins [G,3] required")
    _require(isinstance(batch, Tensor) and batch.dtype == torch.long
             and batch.shape == (len(coefficients),), "Source atom graph IDs must be int64 [N]")
    _require(coefficients.device == positions.device == batch.device == origins.device,
             "Geometry, coefficients and graph IDs must share a device")
    _require(not len(batch) or bool(((batch >= 0) & (batch < len(origins))).all()),
             "Atom graph ID outside explicit origin domain")


def rank2_from_invariant_coefficients(coefficients: Tensor, positions: Tensor, batch: Tensor,
                                      origins: Tensor, *, tensor_form: str, origin_semantics: str,
                                      coordinate_convention: str, unit_semantics: str) -> Tensor:
    """Compensated graph sum of a_i u_i u_i^T + b_i I, u_i=X_i-O_graph.

    The explicit traceless form is a_i(u_i u_i^T-|u_i|^2 I/3), with one
    coefficient per atom.  It does not project or modify any source label.
    Empty graph IDs are retained as zero matrices. Atom rows are never dropped.
    Only comoving O'=OR+t gives the stated rotation/translation equivariance.
    """
    _geometry(coefficients, positions, batch, origins, tensor_form=tensor_form,
              origin_semantics=origin_semantics, coordinate_convention=coordinate_convention,
              unit_semantics=unit_semantics)
    relative = positions - origins[batch]
    outer = relative.unsqueeze(-1) * relative.unsqueeze(-2)
    identity = torch.eye(3, dtype=torch.float32, device=positions.device)
    if tensor_form == "traceless":
        outer = outer - (compensated_squared_norm3(relative) / 3)[:, None, None] * identity
        atom = coefficients[:, 0, None, None] * outer
    else:
        atom = (coefficients[:, 0, None, None] * outer
                + coefficients[:, 1, None, None] * identity)
    summed = compensated_index_add(positions.new_zeros((len(origins), 6)), batch,
                                   matrix_to_source_six(atom))
    result = source_six_to_matrix(summed)
    _fp32(result, "rank-2 output")
    return result


class StandaloneRank2Head(nn.Module):
    """Invariant H0 coefficients plus an explicit relative-geometry tensor basis.

    This head has no registry/factory integration and does not infer a native
    quadrupole origin or coefficient. Caller H0 must already be invariant.
    """
    def __init__(self, dim: int, *, tensor_form: str):
        super().__init__()
        _require(type(dim) is int and dim > 0, "Positive invariant feature dimension required")
        _require(tensor_form in ("symmetric", "traceless"), "Explicit tensor form required")
        self.dim, self.tensor_form = dim, tensor_form
        self.coefficients = nn.Linear(dim, 2 if tensor_form == "symmetric" else 1, dtype=torch.float32)

    def forward(self, h0: Tensor, positions: Tensor, batch: Tensor, origins: Tensor, *,
                origin_semantics: str, coordinate_convention: str, unit_semantics: str) -> Tensor:
        _fp32(h0, "invariant H0")
        _require(h0.ndim == 2 and h0.size(1) == self.dim, "Invariant H0 must be [N,dim]")
        require_fp32_context(self, h0, positions, origins)
        return rank2_from_invariant_coefficients(
            self.coefficients(h0), positions, batch, origins, tensor_form=self.tensor_form,
            origin_semantics=origin_semantics, coordinate_convention=coordinate_convention,
            unit_semantics=unit_semantics)


def _positive_per_tensor(value, tensors, device, name):
    _fp32(value, name)
    _require(value.device == device and (value.ndim == 0 or value.shape == (tensors,)),
             name + " must be scalar or [T] on the prediction device")
    _require(bool((value > 0).all()), name + " must be strictly positive")
    return value.expand(tensors) if value.ndim == 0 else value


def _sum_last(value):
    rows, width = value.shape
    row = torch.arange(rows, device=value.device).repeat_interleave(width)
    return compensated_index_add(value.new_zeros((rows, 1)), row, value.reshape(-1, 1))[:, 0]


@dataclass(frozen=True)
class TensorObservationLoss:
    """One active tensor is one field observation, independently of its row count.

    Mask and eligibility are exact clones of caller inputs, never rewritten to
    active/complete status. Zero-observation tensors are separately identified.
    All floating outputs use FP32; counts and memberships use int64/bool.
    """
    mean: Tensor
    total: Tensor
    per_tensor: Tensor
    field_count: Tensor
    active: Tensor
    observation_count: Tensor
    zero_observation: Tensor
    source_component_mask: Tensor
    loss_eligibility: Tensor
    residual: Tensor


def radial_huber_observation_loss(prediction: Tensor, operator: Tensor, target: Tensor,
                                   observation_tensor: Tensor, *, source_component_mask: Tensor,
                                   loss_eligibility: Tensor, train_scale: Tensor, scale_role: str,
                                   delta: float, normalization_d: Tensor, policy: str,
                                   operator_coordinates: str, unit_semantics: str) -> TensorObservationLoss:
    """Low-level rho_delta(||(Aq-y)/s||_2 / sqrt(d)), one caller tensor at a time.

    q[T,6] uses Frobenius orthonormal coordinates; packed A[K,6], y[K], and
    int64 observation_tensor[K] contain ONLY real observed rows, in source order.
    s and d are explicit positive FP32 scalar/[T]; no D4 statistics are chosen.
    rho_delta(r)=r^2/2 for r<=delta, delta*(r-delta/2) otherwise.

    source_component_mask[T,6] is retained for provenance and is not applied as
    six scalar losses. Caller loss_eligibility[T] carries an external policy.
    The mandatory math-only policy token is not approval of either complete-only
    or partial-observation population selection. m=0 is always excluded, with a
    connected zero mean if nothing is active. Missing target components do not
    exist in this packed API and cannot be silently zero-filled by it.
    """
    _require(policy == OBSERVATION_MATH_POLICY, "Explicit external-eligibility math-only policy required")
    _require(operator_coordinates == ORTHONORMAL_COORDINATES, "Unknown observation coordinates")
    _require(unit_semantics == LOSS_UNITS, "Explicit prediction/target/scale unit consistency required")
    _require(scale_role == TRAIN_SCALE_ROLE, "Scale must be explicitly supplied as TRAIN-only")
    _last_six(prediction, "orthonormal tensor predictions")
    _fp32(operator, "packed observation operator")
    _fp32(target, "packed observed targets")
    _require(prediction.ndim == 2 and operator.ndim == 2 and operator.size(1) == 6
             and target.shape == (len(operator),), "Expected q[T,6], A[K,6], y[K]")
    tensors, observations = len(prediction), len(operator)
    _require(isinstance(observation_tensor, Tensor) and observation_tensor.dtype == torch.long
             and observation_tensor.shape == (observations,), "Observation tensor IDs must be int64 [K]")
    _require(isinstance(source_component_mask, Tensor) and source_component_mask.dtype == torch.bool
             and source_component_mask.shape == (tensors, 6), "Unmodified source component mask [T,6] required")
    _require(isinstance(loss_eligibility, Tensor) and loss_eligibility.dtype == torch.bool
             and loss_eligibility.shape == (tensors,), "Explicit external loss eligibility bool[T] required")
    _require(all(value.device == prediction.device for value in
                 (operator, target, observation_tensor, source_component_mask, loss_eligibility)),
             "All observation inputs must share a device")
    _require(not observations or bool(((observation_tensor >= 0) & (observation_tensor < tensors)).all()),
             "Observation tensor ID outside prediction domain")
    _require(type(delta) in (int, float) and math.isfinite(delta) and delta > 0,
             "Explicit finite positive radial Huber delta required")
    delta_value = prediction.new_tensor(delta)
    _require(bool(torch.isfinite(delta_value)) and bool(delta_value > 0),
             "Huber delta must remain finite and positive in FP32")
    scale = _positive_per_tensor(train_scale, tensors, prediction.device, "positive TRAIN scale")
    dimension = _positive_per_tensor(normalization_d, tensors, prediction.device, "normalization d")
    predicted_observation = _sum_last(operator * prediction[observation_tensor])
    residual = (predicted_observation - target) / scale[observation_tensor]
    _fp32(residual, "normalized observation residual")
    squared = compensated_index_add(prediction.new_zeros((tensors, 1)), observation_tensor,
                                    residual.square()[:, None])[:, 0] / dimension
    _fp32(squared, "normalized radial squared residual")
    # Avoid sqrt'(0) in the inactive linear branch; the quadratic branch gives
    # the exact smooth zero-residual Hessian instead of a detached zero norm.
    safe_radius = torch.sqrt(torch.where(squared > 0, squared, torch.ones_like(squared)))
    raw = torch.where((squared == 0) | (safe_radius <= delta_value), .5 * squared,
                      delta_value * (safe_radius - .5 * delta_value))
    counts = torch.bincount(observation_tensor, minlength=tensors)
    active = loss_eligibility & (counts > 0)
    per_tensor = torch.where(active, raw, torch.zeros_like(raw))
    total = compensated_index_add(prediction.new_zeros((1, 1)),
                                   torch.zeros(tensors, dtype=torch.long, device=prediction.device),
                                   per_tensor[:, None])[0, 0]
    field_count = active.sum()
    mean = total / field_count.clamp_min(1).to(torch.float32)
    _fp32(mean, "radial Huber loss")
    return TensorObservationLoss(mean, total, per_tensor, field_count, active, counts, counts == 0,
                                 source_component_mask.clone(), loss_eligibility.clone(), residual)
