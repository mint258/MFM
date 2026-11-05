"""V3 observed-field/group means, separate from frozen Phase1 loss semantics."""
from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field, replace
from typing import Mapping

import torch
import torch.nn.functional as F
from torch import Tensor

from .v3_contract import (FieldTarget, LabelRegistry, TrainNormalization, observed_rows,
                          require, selected_groups, validate_normalizations, DisabledNormalization, LOSS_DISABLED_SCALE)
from .v3_label_domains import OrderedEntryTarget, Tensor6Target, TENSOR6_COMPONENTS
from ..model.v3_rank2_targets import tensor6_radial_huber

from .v3_physical_policy import PhysicalLossPolicy, LOSS_DISABLED_PHYSICAL, NOT_TARGETED

VECTOR_LOSS_MODES = ("radial_huber_v1", "component_huber_v0")


@dataclass(frozen=True)
class V3LossResult:
    total: Tensor
    fields: dict[str, Tensor]
    groups: dict[str, Tensor]
    counts: dict[str, int]
    observed_fields: dict[str, int]
    enabled_groups: tuple[str, ...]
    audit_counts: dict[str, dict[str, int | bool]] = dataclass_field(default_factory=dict)

    @property
    def has_loss_readiness(self):
        return hasattr(self, "_target_loss_counts")

    @property
    def loss_counts(self):
        # Legacy construction/serialization has exactly its original fields.
        return getattr(self, "_target_loss_counts", self.counts)

    @property
    def loss_status(self):
        return getattr(self, "_target_loss_status", {})

    @property
    def loss_reasons(self):
        return getattr(self, "_target_loss_reasons", {})

    @property
    def physical_status(self): return getattr(self, "_physical_status", {})
    @property
    def scale_status(self): return getattr(self, "_scale_status", {})
    @property
    def scale_reasons(self): return getattr(self, "_scale_reasons", {})
    @property
    def physical_policy_sha256(self): return getattr(self, "_physical_policy_sha256", None)

    def with_loss_readiness(self, counts, statuses, reasons=None, *, physical_status=None,
                            scale_status=None, scale_reasons=None, policy_sha256=None):
        require(set(counts) == set(statuses) == set(self.counts)
                and all(type(n) is int and 0 <= n <= self.counts[k] for k, n in counts.items()),
                "Separate source/loss populations must bind the same fields")
        require(all(value in ("READY", "NO_VALID_LABELS", LOSS_DISABLED_SCALE, LOSS_DISABLED_PHYSICAL) for value in statuses.values())
                and all(counts[k] == 0 for k, value in statuses.items() if value in (LOSS_DISABLED_SCALE, LOSS_DISABLED_PHYSICAL)),
                "Invalid target-local readiness status/count")
        result = replace(self)
        object.__setattr__(result, "_target_loss_counts", dict(counts))
        object.__setattr__(result, "_target_loss_status", dict(statuses))
        object.__setattr__(result, "_target_loss_reasons", dict(reasons or {}))
        if policy_sha256 is not None:
            require(type(policy_sha256) is str and len(policy_sha256) == 64
                    and set(physical_status) == set(scale_status) == set(self.counts),
                    "Complete independent physical/scale status binding required")
            object.__setattr__(result, "_physical_status", dict(physical_status))
            object.__setattr__(result, "_scale_status", dict(scale_status))
            object.__setattr__(result, "_scale_reasons", dict(scale_reasons or {}))
            object.__setattr__(result, "_physical_policy_sha256", policy_sha256)
        return result

    def metrics(self) -> dict[str, float | int | str | None]:
        result = {"loss/total": (None if self.has_loss_readiness and not any(self.loss_counts.values())
                                 else float(self.total.detach().float()))}
        result.update({"loss/" + name: (None if self.loss_status.get(name) in (LOSS_DISABLED_SCALE, LOSS_DISABLED_PHYSICAL) else float(value.detach().float()))
                       for name, value in self.fields.items()})
        result.update({"group_loss/" + name: float(value.detach().float()) for name, value in self.groups.items()})
        result.update({"valid_count/" + name: count for name, count in self.counts.items()})
        result.update({"observed_fields/" + name: count for name, count in self.observed_fields.items()})
        result.update({"domain_audit/" + name + "/" + key: count
                       for name, values in self.audit_counts.items() for key, count in values.items()})
        if self.has_loss_readiness:
            result.update({"loss_count/" + name: count for name, count in self.loss_counts.items()})
            result.update({"loss_status/" + name: value for name, value in self.loss_status.items()})
            result.update({"loss_disabled_reason/" + name: value for name, value in self.loss_reasons.items()})
        if self.physical_policy_sha256 is not None:
            result["physical_policy_sha256"] = self.physical_policy_sha256
            result.update({"physical_status/" + name: value for name, value in self.physical_status.items()})
            result.update({"scale_status/" + name: value for name, value in self.scale_status.items()})
            result.update({"scale_disabled_reason/" + name: value for name, value in self.scale_reasons.items()})
        return result


def source_observed_rows(field, target):
    """Validate retained regression labels without fabricating a prediction."""
    require(field.kind == "regression", "Only an explicitly disabled regression may omit its prediction")
    if field.representation == "symmetric_tensor6":
        require(isinstance(target, Tensor6Target), "Typed retained tensor6 source required")
        target.__post_init__()
    elif field.level == "ordered_entry":
        require(isinstance(target, OrderedEntryTarget), "Typed retained ordered source required")
        target.__post_init__()
    else:
        require(isinstance(target, FieldTarget), "Retained field source required")
    values, mask = target.values, target.valid
    require(isinstance(values, Tensor) and values.dtype == torch.float32 and values.ndim == 2
            and values.size(1) == field.target_width and not values.requires_grad
            and isinstance(mask, Tensor) and mask.dtype == torch.bool and mask.shape == (len(values),)
            and values.device == mask.device and bool((~mask | torch.isfinite(values).all(-1)).all()),
            "Retained source dtype/shape/mask/finite values differ")
    return values[mask], int(mask.sum())


def loss_prediction_fields(registry, normalizations, *, enabled_groups, enabled_fields=None, physical_policy=None):
    """Transport/execution selection only; loss independently rechecks disposition."""
    fields = registry.enabled(enabled_groups, enabled_fields)
    validate_normalizations(registry, normalizations)
    scale_ready = tuple(f.name for f in fields if not isinstance(normalizations.get(f.name), DisabledNormalization))
    if physical_policy is not None:
        require(isinstance(physical_policy, PhysicalLossPolicy), "Typed independent physical policy required")
        physical_policy.validate_for_registry(registry, enabled_fields=scale_ready)
    return tuple(f.name for f in fields if f.name in scale_ready
                 and (physical_policy is None or not physical_policy.disabled(f.name)))


def compute_v3_loss(predictions: Mapping[str, Tensor], targets: Mapping[str, FieldTarget | OrderedEntryTarget | Tensor6Target],
                    registry: LabelRegistry, normalizations: Mapping[str, TrainNormalization],
                    *, enabled_groups, enabled_fields=None, device=None,
                    vector_loss_mode="radial_huber_v1", physical_policy=None) -> V3LossResult:
    """Mean observed fields per group, then equal mean of enabled S/D/P groups.

    An enabled group with no labels contributes detached zero but remains in
    the enabled-group denominator. An unobserved field is absent from its
    group's field denominator. Unused predictions are never touched.
    """
    require(vector_loss_mode in VECTOR_LOSS_MODES, "Unknown vector regression loss mode")
    groups = selected_groups(enabled_groups)
    fields = registry.enabled(groups, enabled_fields)
    prediction_fields = loss_prediction_fields(registry, normalizations, enabled_groups=groups,
        enabled_fields=enabled_fields, physical_policy=physical_policy)
    require(set(predictions) <= set(registry.by_name()), "Unknown predicted field")
    require(set(targets) <= set(registry.by_name()), "Unknown target field")
    if device is None:
        first = next((predictions[field.name] for field in fields if field.name in predictions), None)
        source = next((targets[f.name].values for f in fields if f.name in targets), None)
        device = first.device if first is not None else source.device if source is not None else torch.device("cpu")
    zero = torch.zeros((), device=device, dtype=torch.float32)
    raw, counts, audits = {}, {}, {}
    loss_counts, statuses, reasons = {}, {}, {}
    has_readiness = physical_policy is not None or any(isinstance(normalizations.get(f.name), DisabledNormalization) for f in fields)
    physical_status, scale_status, scale_reasons = {}, {}, {}
    by_group: dict[str, list[Tensor]] = {group: [] for group in groups}
    for field in fields:
        require(field.name in targets and (field.name in predictions or field.name not in prediction_fields),
                f"{field.name}: ready field needs a real prediction and every field its original target/mask")
        if field.name in predictions:
            prediction, target, count = observed_rows(field, predictions[field.name], targets[field.name])
        else:
            target, count = source_observed_rows(field, targets[field.name])
            prediction = None
        require(target.device == zero.device, "Enabled fields must share a device")
        counts[field.name] = count
        source_target = targets[field.name]
        if isinstance(source_target, (OrderedEntryTarget, Tensor6Target)):
            audits[field.name] = source_target.audit_counts()
            if isinstance(source_target, Tensor6Target):
                audits[field.name].update({"source_valid_" + component: int(source_target.component_valid[:, index].sum())
                    for index, component in enumerate(TENSOR6_COMPONENTS)})
        normalizer = normalizations.get(field.name)
        if physical_policy is not None:
            if field.kind == "regression":
                require(isinstance(normalizer, (TrainNormalization, DisabledNormalization)),
                        "Explicit TRAIN scale/disposition required even when physical loss is disabled")
                if isinstance(normalizer, TrainNormalization):
                    scale = torch.tensor(normalizer.scale, dtype=torch.float32)
                    require(bool(torch.isfinite(scale).all() and (scale > 0).all()),
                            "Unusable F32 scale requires actual D4 disposition, never a physical-policy fallback")
                scale_status[field.name] = normalizer.status if isinstance(normalizer, DisabledNormalization) else "READY"
            else:
                scale_status[field.name] = "NOT_APPLICABLE_NONREGRESSION"
            if isinstance(normalizer, DisabledNormalization): scale_reasons[field.name] = normalizer.reason
            disabled = physical_policy.disabled(field.name)
            physical_status[field.name] = LOSS_DISABLED_PHYSICAL if disabled else NOT_TARGETED
            if disabled:
                raw[field.name] = zero
                loss_counts[field.name], statuses[field.name] = 0, LOSS_DISABLED_PHYSICAL
                reasons[field.name] = physical_policy.reason(field.name)
                if isinstance(source_target, Tensor6Target):
                    audit = audits[field.name]
                    audit["pre_physical_policy_loss_eligible_tensors"] = audit["loss_eligible_tensors"]
                    audit["excluded_physical_policy_tensors"] = count
                    audit["loss_eligible_tensors"] = 0
                    audit["loss_excluded_tensors"] = audit["retained_tensors"]
                continue
        if isinstance(normalizer, DisabledNormalization):
            raw[field.name] = zero  # Internal absence marker; public loss is None.
            loss_counts[field.name], statuses[field.name] = 0, normalizer.status
            reasons[field.name] = normalizer.reason
            if isinstance(source_target, Tensor6Target):
                audit = audits[field.name]
                audit["pre_scale_eligible_tensors"] = audit["loss_eligible_tensors"]
                audit["pre_scale_excluded_tensors"] = audit["loss_excluded_tensors"]
                audit["excluded_scale_unready_tensors"] = count
                audit["loss_eligible_tensors"] = 0
                audit["loss_excluded_tensors"] = audit["retained_tensors"]
            elif isinstance(source_target, OrderedEntryTarget):
                audit = audits[field.name]
                audit["pre_scale_eligible_entries"] = audit["loss_eligible_entries"]
                audit["excluded_scale_unready_entries"] = count
                audit["loss_eligible_entries"] = 0
            continue
        loss_counts[field.name] = count
        statuses[field.name] = "READY" if count else "NO_VALID_LABELS"
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
                if field.representation == "symmetric_tensor6":
                    # A raw six-tuple is one tensor target. Keep the original
                    # component masks for audit; recipe exposure is an
                    # additional loss qualification, never source validity.
                    geometry = source_target.geometry_valid
                    if source_target.exposure_valid is not None:
                        geometry = geometry & source_target.exposure_valid
                    tensor_loss = tensor6_radial_huber(predictions[field.name].float(), source_target.values,
                        source_target.component_valid, geometry, normalizer.scale[0])
                    require(tensor_loss.eligible_count == count and tensor_loss.loss is not None,
                            f"{field.name}: inconsistent complete-tensor eligibility")
                    value = tensor_loss.loss
                else:
                    normalized_prediction = normalizer.transform(prediction)
                    normalized_target = normalizer.transform(target)
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
                elif field.representation != "symmetric_tensor6":
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
    result = V3LossResult(total, raw, group_losses, counts,
                         {group: len(values) for group, values in by_group.items()}, groups, audits)
    if physical_policy is not None:
        return result.with_loss_readiness(loss_counts, statuses, reasons, physical_status=physical_status,
            scale_status=scale_status, scale_reasons=scale_reasons, policy_sha256=physical_policy.sha256)
    return result.with_loss_readiness(loss_counts, statuses, reasons) if has_readiness else result
