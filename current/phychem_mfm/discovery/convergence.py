from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ConvergenceDecision:
    status: str
    optimization_mature: bool
    target_adequate: bool | None
    transfer_ready: bool
    reasons: tuple[str, ...]
    total_recent_improvement: float | None
    major_recent_improvements: dict[str, float]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ConvergenceGate:
    """Protocol-v3 optimization-maturity gate.

    A pass limit is operational safety metadata, never scientific evidence of
    convergence failure. Transfer readiness additionally requires an explicit
    target-adequacy decision.
    """

    validation_window: int = 4
    total_relative_improvement_max: float = 0.03
    major_relative_improvement_max: float = 0.05
    minimum_passes: int = 1
    max_passes: int = 3  # legacy config alias; interpreted as a safety budget only
    major_metrics: tuple[str, ...] = (
        "val/loss/raw/energy",
        "val/loss/raw/charge",
        "val/loss/raw/distance",
        "val/loss/raw/graph_descriptor",
        "val/loss/raw/charge_descriptor",
        "val/loss/raw/element_descriptor",
    )

    @staticmethod
    def _recent_improvement(values: Sequence[float]) -> float:
        midpoint = len(values) // 2
        earlier = sum(values[:midpoint]) / midpoint
        later = sum(values[midpoint:]) / (len(values) - midpoint)
        return float((earlier - later) / max(abs(earlier), 1e-12))

    def evaluate(
        self,
        validation_history: Sequence[Mapping[str, float]],
        *,
        pass_count: int,
        schedule_mature: bool,
        warmup_complete: bool,
        target_adequate: bool | None = None,
    ) -> ConvergenceDecision:
        reasons: list[str] = []
        if pass_count < self.minimum_passes:
            reasons.append("minimum_passes_not_reached")
        if not schedule_mature:
            reasons.append("descriptor_schedule_not_mature")
        if not warmup_complete:
            reasons.append("warmup_not_complete")
        if len(validation_history) < self.validation_window:
            reasons.append("insufficient_validation_points")
            return ConvergenceDecision("TRAINING", False, target_adequate, False, tuple(reasons), None, {})

        recent = list(validation_history[-self.validation_window :])
        active_keys = {key for point in recent for key in point if key.startswith("val/loss/")}
        for key in sorted(active_keys):
            values = [float(point[key]) for point in recent if key in point]
            if len(values) != len(recent) or not all(math.isfinite(value) for value in values):
                reasons.append(f"non_finite_or_missing:{key}")

        total_key = "val/loss/selection"
        if total_key not in recent[0]:
            total_key = "val/loss/total"
        total_values = [float(point.get(total_key, math.nan)) for point in recent]
        total_improvement = None
        if all(math.isfinite(value) for value in total_values):
            total_improvement = self._recent_improvement(total_values)
            if total_improvement > self.total_relative_improvement_max:
                reasons.append("total_still_improving_fast")
        else:
            reasons.append("non_finite_or_missing:total")

        major_improvements: dict[str, float] = {}
        for key in self.major_metrics:
            values = [float(point[key]) for point in recent if key in point]
            if len(values) != len(recent):
                continue
            improvement = self._recent_improvement(values)
            major_improvements[key] = improvement
            if improvement > self.major_relative_improvement_max:
                reasons.append(f"major_still_improving_fast:{key}")

        non_finite = any(reason.startswith("non_finite_or_missing") for reason in reasons)
        catastrophic_worsening = total_improvement is not None and total_improvement < -0.5
        previous_worsening = False
        if len(validation_history) >= 2 * self.validation_window:
            previous = list(validation_history[-2 * self.validation_window : -self.validation_window])
            previous_values = [float(point.get(total_key, math.nan)) for point in previous]
            if all(math.isfinite(value) for value in previous_values):
                previous_worsening = self._recent_improvement(previous_values) < -self.total_relative_improvement_max
        persistent_worsening = (
            total_improvement is not None
            and total_improvement < -self.total_relative_improvement_max
            and previous_worsening
        )
        if catastrophic_worsening:
            reasons.append("catastrophic_total_worsening")
        elif persistent_worsening:
            reasons.append("persistent_total_worsening")
        still_improving = any(
            reason == "total_still_improving_fast" or reason.startswith("major_still_improving_fast")
            for reason in reasons
        )
        prerequisite_failure = any(
            reason in {"minimum_passes_not_reached", "descriptor_schedule_not_mature", "warmup_not_complete"}
            for reason in reasons
        )
        optimization_mature = not (
            non_finite or catastrophic_worsening or persistent_worsening or still_improving or prerequisite_failure
        )
        if non_finite or catastrophic_worsening:
            status = "DIVERGED"
        elif prerequisite_failure:
            status = "TRAINING"
        elif still_improving:
            status = "STILL_IMPROVING"
        elif persistent_worsening:
            status = "DIVERGED"
        elif target_adequate is True:
            status = "TRANSFER_READY"
        elif target_adequate is False:
            status = "PLATEAU_BUT_TARGET_INADEQUATE"
        else:
            status = "OPTIMIZATION_MATURE"
        transfer_ready = bool(optimization_mature and target_adequate is True)
        return ConvergenceDecision(
            status, optimization_mature, target_adequate, transfer_ready,
            tuple(reasons), total_improvement, major_improvements,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
