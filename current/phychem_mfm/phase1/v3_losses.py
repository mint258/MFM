"""V3 observed-field/group means, separate from frozen Phase1 loss semantics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import torch
import torch.nn.functional as F
from torch import Tensor

from .v3_contract import (FieldTarget, LabelRegistry, TrainNormalization, observed_rows,
                          require, selected_groups, validate_normalizations)

VECTOR_LOSS_MODES = ("radial_huber_v1", "component_huber_v0")


@dataclass(frozen=True)
class V3LossResult:
    total: Tensor
    fields: dict[str, Tensor]
    groups: dict[str, Tensor]
    counts: dict[str, int]
    observed_fields: dict[str, int]
    enabled_groups: tuple[str, ...]

    def metrics(self) -> dict[str, float | int]:
        result = {"loss/total": float(self.total.detach().float())}
        result.update({"loss/" + name: float(value.detach().float()) for name, value in self.fields.items()})
        result.update({"group_loss/" + name: float(value.detach().float()) for name, value in self.groups.items()})
        result.update({"valid_count/" + name: count for name, count in self.counts.items()})
        result.update({"observed_fields/" + name: count for name, count in self.observed_fields.items()})
        return result


def compute_v3_loss(predictions: Mapping[str, Tensor], targets: Mapping[str, FieldTarget],
                    registry: LabelRegistry, normalizations: Mapping[str, TrainNormalization],
                    *, enabled_groups, enabled_fields=None, device=None,
                    vector_loss_mode="radial_huber_v1") -> V3LossResult:
    """Mean observed fields per group, then equal mean of enabled S/D/P groups.

    An enabled group with no labels contributes detached zero but remains in
    the enabled-group denominator. An unobserved field is absent from its
    group's field denominator. Unused predictions are never touched.
    """
    require(vector_loss_mode in VECTOR_LOSS_MODES, "Unknown vector regression loss mode")
    groups = selected_groups(enabled_groups)
    fields = registry.enabled(groups, enabled_fields)
    validate_normalizations(registry, normalizations)
    require(set(predictions) <= set(registry.by_name()), "Unknown predicted field")
    require(set(targets) <= set(registry.by_name()), "Unknown target field")
    if device is None:
        first = next((predictions[field.name] for field in fields if field.name in predictions), None)
        device = first.device if first is not None else torch.device("cpu")
    zero = torch.zeros((), device=device, dtype=torch.float32)
    raw, counts = {}, {}
    by_group: dict[str, list[Tensor]] = {group: [] for group in groups}
    for field in fields:
        require(field.name in predictions and field.name in targets,
                f"{field.name}: every enabled field needs explicit prediction/target/mask")
        prediction, target, count = observed_rows(field, predictions[field.name], targets[field.name])
        require(prediction.device == zero.device, "Enabled fields must share a device")
        counts[field.name] = count
        if not count:
            raw[field.name] = zero
            continue
        with torch.autocast(device_type=prediction.device.type, enabled=False):
            if field.kind == "classification":
                value = F.cross_entropy(prediction, target[:, 0])
            elif field.kind == "binary":
                value = F.binary_cross_entropy_with_logits(prediction, target.float())
            elif field.kind == "denoise_eps_mse":
                # Target values are the explicit additive-noise vectors from
                # the view adapter; no coordinates/labels are reinterpreted.
                value = (prediction - target.float()).square().sum(-1).mean() / (3 * field.denoise_sigma ** 2)
            else:
                require(field.name in normalizations, f"{field.name}: missing TRAIN normalization")
                normalizer = normalizations[field.name]
                normalized_prediction, normalized_target = normalizer.transform(prediction), normalizer.transform(target)
                if field.representation == "vector" and vector_loss_mode == "radial_huber_v1":
                    # rho_delta(||e||_2 / sqrt(3)). Below the radial threshold,
                    # this is exactly .5 * mean(e**2), the component mean's
                    # quadratic coefficient. Clamping only the inactive linear
                    # branch avoids sqrt'(0) and zero-residual NaN gradients.
                    squared_radius = (normalized_prediction - normalized_target).square().mean(-1)
                    delta = field.huber_delta
                    radius_for_linear = squared_radius.clamp_min(delta ** 2).sqrt()
                    rows = torch.where(squared_radius <= delta ** 2, .5 * squared_radius,
                                       delta * (radius_for_linear - .5 * delta))
                    value = rows.mean()
                else:
                    # v0 remains explicit only for replaying the initial
                    # synthetic component tests; it is not the v3 vector default.
                    value = F.huber_loss(normalized_prediction, normalized_target,
                                         reduction="mean", delta=field.huber_delta)
        require(bool(torch.isfinite(value)), f"{field.name}: nonfinite loss")
        raw[field.name] = value
        by_group[field.group].append(value)
    group_losses = {group: torch.stack(values).mean() if values else zero
                    for group, values in by_group.items()}
    total = torch.stack(list(group_losses.values())).mean() if groups else zero
    return V3LossResult(total, raw, group_losses, counts,
                        {group: len(values) for group, values in by_group.items()}, groups)
