from __future__ import annotations

import json
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Iterable, Mapping


class FidelityLevel(IntEnum):
    INADEQUATE = 0
    USABLE = 1
    HIGH_FIDELITY = 2


@dataclass(frozen=True)
class FidelityThreshold:
    task: str
    metric: str
    unit: str
    high_fidelity_threshold: float
    usable_threshold: float
    higher_is_better: bool
    source: str
    source_type: str
    rationale: str
    hard_gate_or_diagnostic: str
    version: str

    @classmethod
    def from_mapping(cls, payload: Mapping[str, object]) -> "FidelityThreshold":
        return cls(
            task=str(payload["task"]),
            metric=str(payload["metric"]),
            unit=str(payload["unit"]),
            high_fidelity_threshold=float(payload["high_fidelity_threshold"]),
            usable_threshold=float(payload["usable_threshold"]),
            higher_is_better=bool(payload.get("higher_is_better", False)),
            source=str(payload["source"]),
            source_type=str(payload["source_type"]),
            rationale=str(payload["rationale"]),
            hard_gate_or_diagnostic=str(payload["hard_gate_or_diagnostic"]),
            version=str(payload["version"]),
        )

    def classify(self, value: float) -> FidelityLevel:
        if self.higher_is_better:
            if value >= self.high_fidelity_threshold:
                return FidelityLevel.HIGH_FIDELITY
            if value >= self.usable_threshold:
                return FidelityLevel.USABLE
        else:
            if value <= self.high_fidelity_threshold:
                return FidelityLevel.HIGH_FIDELITY
            if value <= self.usable_threshold:
                return FidelityLevel.USABLE
        return FidelityLevel.INADEQUATE

    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


class TargetFidelityRegistry:
    """Versioned, source-bearing thresholds used by the v3 adequacy gate."""

    def __init__(self, payload: Mapping[str, object]):
        self.version = str(payload["version"])
        entries = [FidelityThreshold.from_mapping(item) for item in payload.get("thresholds", [])]
        self._entries = {(item.task, item.metric): item for item in entries}
        if len(self._entries) != len(entries):
            raise ValueError("Duplicate task/metric entries in fidelity registry")

    @classmethod
    def load(cls, path: str | Path) -> "TargetFidelityRegistry":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def threshold(self, task: str, metric: str) -> FidelityThreshold:
        key = (str(task), str(metric))
        if key not in self._entries:
            raise KeyError(f"No fidelity threshold registered for {key}")
        return self._entries[key]

    def evaluate(self, task: str, metrics: Mapping[str, float]) -> dict[str, object]:
        candidates = [entry for key, entry in self._entries.items() if key[0] == task]
        hard = [entry for entry in candidates if entry.hard_gate_or_diagnostic == "hard_gate"]
        results = []
        for entry in candidates:
            if entry.metric not in metrics:
                continue
            value = float(metrics[entry.metric])
            level = entry.classify(value)
            results.append({
                "metric": entry.metric,
                "value": value,
                "unit": entry.unit,
                "fidelity_level": level.name,
                "pass": level >= FidelityLevel.USABLE,
                "threshold": entry.to_dict(),
            })
        hard_results = [item for item in results if (task, item["metric"]) in {(e.task, e.metric) for e in hard}]
        if hard and len(hard_results) != len(hard):
            level = FidelityLevel.INADEQUATE
            status = "MISSING_HARD_GATE_METRIC"
        elif hard_results:
            level = min(FidelityLevel[item["fidelity_level"]] for item in hard_results)
            status = "ADEQUATE" if level >= FidelityLevel.USABLE else "INADEQUATE"
        else:
            level = FidelityLevel.USABLE
            status = "DIAGNOSTIC_ONLY"
        return {
            "task": task,
            "fidelity_level": level.name,
            "status": status,
            "pass": level >= FidelityLevel.USABLE,
            "metrics": results,
        }

    def active_objectives_adequate(
        self,
        active_objectives: Iterable[str],
        per_task: Mapping[str, Mapping[str, object]],
    ) -> bool:
        return all(bool(per_task.get(str(task), {}).get("pass", False)) for task in active_objectives)

    def to_dict(self) -> dict[str, object]:
        return {
            "version": self.version,
            "thresholds": [entry.to_dict() for entry in self._entries.values()],
        }
