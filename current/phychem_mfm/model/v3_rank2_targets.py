"""Native symmetric-tensor targets and explicit-origin equivariant heads.

D1 all-A: source order xx,xy,yy,xz,yz,zz; one complete tensor is one target.
These ordinary dtype-preserving operations are not numerical-compensation
candidates. Original values, masks, trace, units and origins remain explicit.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import torch
from torch import Tensor, nn
from ..phase1.v3_contract import require

SIX_ORDER = ("xx", "xy", "yy", "xz", "yz", "zz")
FROBENIUS_WEIGHTS = (1., 2., 1., 2., 2., 1.)
ORIGIN_POLICY = "explicit_comoving"
NORMALIZATION_POLICY = "TRAIN_Frobenius_winsorized_std_ddof0_no_center"
LOSS_POLICY = "Frobenius_radial_Huber_d9_delta1_one_target"


def _floating(value, name):
    require(isinstance(value, Tensor) and value.dtype in (torch.float32, torch.float64)
            and value.layout == torch.strided, name + ": strided FP32 or FP64 required")


def six_to_matrix(value: Tensor) -> Tensor:
    _floating(value, "tensor6")
    require(value.ndim >= 1 and value.shape[-1] == 6, "Source tensor width/order differs")
    require(bool(torch.isfinite(value).all()), "Finite complete tensor components required")
    xx, xy, yy, xz, yz, zz = value.unbind(-1)
    return torch.stack((xx, xy, xz, xy, yy, yz, xz, yz, zz), -1).reshape(*value.shape[:-1], 3, 3)


def matrix_to_six(value: Tensor) -> Tensor:
    _floating(value, "matrix")
    require(value.ndim >= 2 and value.shape[-2:] == (3, 3), "Symmetric 3x3 tensor required")
    require(bool(torch.isfinite(value).all()), "Finite tensor matrix required")
    tolerance = 32 * torch.finfo(value.dtype).eps * max(1., float(value.detach().abs().max())) if value.numel() else 0.
    require(bool(torch.all((value-value.transpose(-1, -2)).abs() <= tolerance)),
            "Matrix is not symmetric within native arithmetic roundoff")
    return torch.stack((value[..., 0, 0], value[..., 0, 1], value[..., 1, 1],
                        value[..., 0, 2], value[..., 1, 2], value[..., 2, 2]), -1)


def rotate_six(value: Tensor, rotation: Tensor) -> Tensor:
    _floating(rotation, "rotation")
    require(rotation.shape == (3, 3) and rotation.dtype == value.dtype
            and rotation.device == value.device and bool(torch.isfinite(rotation).all()),
            "Same-dtype finite row-coordinate rotation required")
    identity = torch.eye(3, dtype=rotation.dtype, device=rotation.device)
    require(torch.allclose(rotation.T @ rotation, identity, rtol=0,
                           atol=64*torch.finfo(rotation.dtype).eps),
            "Rigid orthogonal rotation required; no rotation repair is performed")
    with torch.autocast(device_type=value.device.type, enabled=False):
        matrix = six_to_matrix(value)
        return matrix_to_six(rotation.T @ matrix @ rotation)


@dataclass(frozen=True)
class Tensor6Loss:
    loss: Tensor | None
    eligible_count: int
    excluded_count: int
    component_valid_counts: Tensor
    eligible: Tensor


def tensor6_radial_huber(prediction: Tensor, target: Tensor, component_valid: Tensor,
                         geometry_valid: Tensor, scale: Tensor | float) -> Tensor6Loss:
    """Raw-unit predictions/targets, Qnorm=Q/s, d=9, delta=1; no fitting.

    Select complete observations before arithmetic. With no eligible tensor,
    loss=None and the caller excludes this target from group averaging.
    """
    _floating(prediction, "prediction"); _floating(target, "target")
    require(prediction.ndim == 2 and prediction.shape[-1] == 6
            and target.shape == prediction.shape and target.dtype == prediction.dtype
            and target.device == prediction.device and not target.requires_grad,
            "Corresponding detached raw tensor labels required")
    require(component_valid.dtype == torch.bool and component_valid.shape == target.shape
            and geometry_valid.dtype == torch.bool and geometry_valid.shape == target.shape[:1]
            and component_valid.device == geometry_valid.device == target.device,
            "Original component masks and explicit geometry eligibility required")
    require(bool((~component_valid | torch.isfinite(target)).all()),
            "A component marked valid cannot have a nonfinite source value")
    scalar = torch.as_tensor(scale, dtype=target.dtype, device=target.device)
    require(scalar.numel() == 1 and not scalar.requires_grad
            and bool(torch.isfinite(scalar).all()) and bool((scalar > 0).all()),
            "One actual positive detached TRAIN scale required; no epsilon or per-component scale")
    eligible = component_valid.all(-1) & geometry_valid
    count = int(eligible.sum())
    counts = component_valid.sum(0)
    if count == 0:
        return Tensor6Loss(None, 0, len(target), counts, eligible)
    require(bool(torch.isfinite(prediction[eligible]).all()), "Finite eligible predictions required")
    error = (prediction[eligible] - target[eligible]) / scalar.reshape(())
    squared = (error.square() * error.new_tensor(FROBENIUS_WEIGHTS)).sum(-1) / 9.
    require(bool(torch.isfinite(squared).all()), "Nonfinite normalized tensor loss")
    # This is exactly radial Huber. Clamp only its unused outer branch to
    # the analytic join r=1, preserving finite first/second derivatives at 0.
    outer = torch.sqrt(squared.clamp_min(1.)) - .5
    losses = torch.where(squared <= 1., .5*squared, outer)
    return Tensor6Loss(losses.mean(), count, len(target)-count, counts, eligible)


class SymmetricTensor6Head(nn.Module):
    """Sum a_i I + b_i (r_i-O)(r_i-O)^T, preserving an independent trace.

    H0 is invariant. O is supplied geometry metadata, never a target value,
    learned origin, or inferred centroid. Under X'=XR+t, O'=OR+t and
    Q'=R^TQR. Source labels are never projected to a traceless tensor.
    """
    def __init__(self, dim: int, hidden_dim: int = 64, *, origin_policy: str):
        super().__init__()
        require(type(dim) is int and dim > 0 and type(hidden_dim) is int and hidden_dim > 1,
                "Positive explicit head dimensions required")
        require(origin_policy == ORIGIN_POLICY, "Explicit comoving origin policy required")
        self.dim, self.hidden_dim, self.origin_policy = dim, hidden_dim, origin_policy
        self.coefficients = nn.Sequential(nn.Linear(dim, hidden_dim), nn.SiLU(), nn.Linear(hidden_dim, 2))

    def forward(self, h0: Tensor, pos: Tensor, batch: Tensor, graphs: int, origin: Tensor):
        dtype = self.coefficients[0].weight.dtype
        require(dtype in (torch.float32, torch.float64) and h0.ndim == 2
                and h0.shape[1] == self.dim and pos.shape == (len(h0), 3)
                and type(graphs) is int and graphs >= 0
                and batch.dtype == torch.long and batch.shape == (len(h0),)
                and origin.shape == (graphs, 3), "Tensor head input dimensions differ")
        require(pos.dtype == origin.dtype == dtype
                and (h0.dtype == dtype or (h0.dtype == torch.bfloat16 and dtype == torch.float32)),
                "Coordinates/origin and head must retain the declared floating precision")
        require(h0.device == pos.device == origin.device == batch.device
                and bool(torch.isfinite(h0).all()) and bool(torch.isfinite(pos).all())
                and bool(torch.isfinite(origin).all()), "Finite same-device tensor head inputs required")
        require(not origin.requires_grad, "Origin is detached source geometry metadata")
        require((len(batch) == 0 and graphs == 0) or
                (len(batch) > 0 and graphs > 0 and int(batch.min()) >= 0
                 and int(batch.max()) < graphs
                 and bool((torch.bincount(batch, minlength=graphs) > 0).all())),
                "Every declared graph needs its original atom membership")
        with torch.autocast(device_type=pos.device.type, enabled=False):
            scalar = self.coefficients(h0.to(dtype=dtype))
            relative = pos - origin[batch]
            anisotropic = scalar[:, 1, None, None] * relative[:, :, None] * relative[:, None, :]
            matrix = pos.new_zeros((graphs, 3, 3)).index_add(0, batch, anisotropic)
            isotropic = pos.new_zeros((graphs,)).index_add(0, batch, scalar[:, 0])
            matrix = matrix + isotropic[:, None, None] * torch.eye(3, dtype=dtype, device=pos.device)
            return matrix_to_six(matrix)
