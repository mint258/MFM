"""Positive, piecewise *joint* weighting of Phase 1 tasks.

This recipe changes emphasis, never introduces a previously unsupervised task.
It does not resolve the protocol's literal "staged introduction" wording.
The formal consumer may use it only through explicit hash-bound comparisons;
this module itself neither authorizes a run nor freezes/selects comparisons.
Keep Phase1JointSchedule's loss scales at one when using the returned policy.
The index is the actual, zero-based optimizer update, not an exposure counter;
stage changes do not reset the optimizer, LR schedule, or any budget.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import json
import math
import struct
from types import MappingProxyType

from ..supervision import SupervisionConfig
from .objectives import GROUP_TASKS, Phase1LossPolicy


RECIPE_NAME = "positive_piecewise_joint_v1"
INDEX_UNIT = "optimizer_update_step"
_GROUPS = ("S", "D", "P")


def _positive_integer(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be an explicit positive integer")
    return value


def _positive_weight(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite, strictly positive numeric weight")
    try:
        weight = float(value)
    except OverflowError as error:
        raise ValueError(f"{name} must be finite and strictly positive") from error
    if not math.isfinite(weight) or weight <= 0:
        raise ValueError(f"{name} must be finite and strictly positive")
    return weight


def _sha256(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class PositiveWeightStage:
    end_update_exclusive: int
    group_weight_multipliers: Mapping[str, float]

    def __post_init__(self):
        _positive_integer(self.end_update_exclusive, "end_update_exclusive")
        values = self.group_weight_multipliers
        if not isinstance(values, Mapping) or set(values) != set(_GROUPS):
            raise ValueError("Every stage must define exactly S/D/P multipliers")
        snapshot = {group: _positive_weight(values[group], f"multiplier/{group}") for group in _GROUPS}
        object.__setattr__(self, "group_weight_multipliers", MappingProxyType(snapshot))

    @classmethod
    def from_dict(cls, values):
        if not isinstance(values, Mapping) or set(values) != {"end_update_exclusive", "group_weight_multipliers"}:
            raise ValueError("Stage fields must be exactly end_update_exclusive and group_weight_multipliers")
        return cls(values["end_update_exclusive"], values["group_weight_multipliers"])

    def to_dict(self):
        return {"end_update_exclusive": self.end_update_exclusive,
                "group_weight_multipliers": dict(self.group_weight_multipliers)}


@dataclass(frozen=True)
class Phase1PolicyAtUpdate:
    """Immutable loss-policy snapshot and the coefficients actually used."""

    variant: str
    optimizer_update_step: int
    stage_id: int
    begin_update_inclusive: int
    end_update_exclusive: int
    policy: Phase1LossPolicy
    group_weight_multipliers: Mapping[str, float]
    effective_group_coefficients: Mapping[str, float]
    schedule_sha256: str

    @property
    def policy_sha256(self):
        return _sha256(self.policy.to_dict())

    def to_dict(self):
        return {"name": RECIPE_NAME, "index_unit": INDEX_UNIT, "variant": self.variant,
                "optimizer_update_step": self.optimizer_update_step, "stage_id": self.stage_id,
                "begin_update_inclusive": self.begin_update_inclusive,
                "end_update_exclusive": self.end_update_exclusive,
                "group_weight_multipliers": dict(self.group_weight_multipliers),
                "effective_group_coefficients": dict(self.effective_group_coefficients),
                "loss_policy": self.policy.to_dict(), "schedule_sha256": self.schedule_sha256,
                "policy_sha256": self.policy_sha256}


@dataclass(frozen=True)
class PositivePiecewiseJoint:
    """A condition-bound, immutable partition of optimizer updates [0, N).

    All three multipliers are explicit even for disabled groups. Only enabled
    groups enter the loss denominator. Single-group multipliers cancel exactly,
    so they cannot supply a meaningful supervision-order contrast. ``none`` has
    zero optimizer updates and cannot have a training recipe.
    """

    variant: str
    max_updates: int
    stages: tuple[PositiveWeightStage, ...]

    def __post_init__(self):
        if not isinstance(self.variant, str):
            raise ValueError("variant must be an explicit Phase 1 token")
        supervision = SupervisionConfig.from_variant(self.variant)
        if not supervision.objectives:
            raise ValueError("none has zero optimizer updates; no training stages can be arranged")
        object.__setattr__(self, "variant", supervision.variant.canonical_value)
        _positive_integer(self.max_updates, "max_updates")
        if not isinstance(self.stages, (tuple, list)) or not self.stages:
            raise ValueError("stages must be a nonempty ordered sequence")
        snapshot = tuple(self.stages)
        previous_end = 0
        for stage in snapshot:
            if not isinstance(stage, PositiveWeightStage):
                raise ValueError("Each stage must be a PositiveWeightStage")
            if not previous_end < stage.end_update_exclusive <= self.max_updates:
                raise ValueError("Stage ends must strictly increase within max_updates")
            previous_end = stage.end_update_exclusive
        if previous_end != self.max_updates:
            raise ValueError("Stages must cover the entire [0, max_updates) budget")
        object.__setattr__(self, "stages", snapshot)

    @classmethod
    def from_dict(cls, values):
        required = {"name", "index_unit", "variant", "max_updates", "stages"}
        if not isinstance(values, Mapping) or set(values) != required:
            raise ValueError("Recipe must contain exactly its versioned fields")
        if values["name"] != RECIPE_NAME or values["index_unit"] != INDEX_UNIT:
            raise ValueError("Recipe name/index_unit must specify positive optimizer-update joint weighting")
        if not isinstance(values["stages"], (list, tuple)):
            raise ValueError("stages must be an ordered sequence")
        return cls(values["variant"], values["max_updates"],
                   tuple(PositiveWeightStage.from_dict(stage) for stage in values["stages"]))

    def to_dict(self):
        return {"name": RECIPE_NAME, "index_unit": INDEX_UNIT, "variant": self.variant,
                "max_updates": self.max_updates, "stages": [stage.to_dict() for stage in self.stages]}

    @property
    def sha256(self):
        return _sha256(self.to_dict())

    def policy_at_update(self, base_policy: Phase1LossPolicy, u: int) -> Phase1PolicyAtUpdate:
        """Snapshot a policy without storing or advancing any mutable cursor.

        Supply the same frozen base policy on every call. Neither this method
        nor a stage changes task weights; policy_sha256 makes that base binding
        observable. The formal consumer binds both artifacts in its contract.
        """
        if type(u) is not int or not 0 <= u < self.max_updates:
            raise ValueError("u must be an actual optimizer update integer within [0, max_updates)")
        if not isinstance(base_policy, Phase1LossPolicy):
            raise ValueError("base_policy must be a Phase1LossPolicy")
        # Revalidate/snapshot the otherwise potentially caller-owned maps.
        if set(base_policy.group_weights) != set(_GROUPS):
            raise ValueError("base_policy must still contain exactly the S/D/P group weights")
        task_weights = {name: _positive_weight(value, f"task/{name}")
                        for name, value in base_policy.task_weights.items()}
        begin = 0
        for stage_id, stage in enumerate(self.stages):
            if u < stage.end_update_exclusive:
                break
            begin = stage.end_update_exclusive
        group_weights = {
            group: _positive_weight(_positive_weight(base_policy.group_weights[group], f"group/{group}")
                                    * stage.group_weight_multipliers[group], f"effective_group/{group}")
            for group in _GROUPS
        }
        policy = Phase1LossPolicy(MappingProxyType(group_weights), MappingProxyType(task_weights))
        enabled = tuple(group for group in _GROUPS if group in self.variant)
        denominator = sum(group_weights[group] for group in enabled)
        if not math.isfinite(denominator):
            raise ValueError("Enabled group-weight denominator must remain finite")
        coefficients = {group: group_weights[group] / denominator for group in enabled}
        for group, coefficient in coefficients.items():
            _positive_weight(coefficient, f"normalized_group/{group}")
            task_denominator = sum(task_weights[name] for name in GROUP_TASKS[group])
            if not math.isfinite(task_denominator):
                raise ValueError("Fixed task-weight denominator must remain finite")
            for name in GROUP_TASKS[group]:
                # Match objectives.py's arithmetic order as well as its
                # algebra: a subnormal intermediate must not hide a zero.
                effective = _positive_weight((task_weights[name] / task_denominator)
                                             * group_weights[group] / denominator,
                                             f"normalized_task/{name}")
                # The existing loss operates in float32. A positive Python
                # float that casts to zero would silently disable its task.
                if struct.unpack("f", struct.pack("f", effective))[0] == 0:
                    raise ValueError(f"normalized_task/{name} must remain positive in the float32 loss")
        return Phase1PolicyAtUpdate(self.variant, u, stage_id, begin, stage.end_update_exclusive,
                                    policy, stage.group_weight_multipliers,
                                    MappingProxyType(coefficients), self.sha256)
