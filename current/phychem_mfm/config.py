from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml


@dataclass(frozen=True)
class ExperimentConfig:
    raw: dict[str, Any]
    source: Path

    def section(self, name: str) -> dict[str, Any]:
        value = self.raw.get(name, {})
        if not isinstance(value, Mapping):
            raise TypeError(f"Config section '{name}' must be a mapping")
        return deepcopy(dict(value))

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.raw)


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(dict(merged[key]), value)
        else:
            merged[key] = deepcopy(value)
    return merged


def load_experiment_config(path: str | Path, overrides: Mapping[str, Any] | None = None) -> ExperimentConfig:
    source = Path(path).resolve()
    with source.open("r", encoding="utf-8") as handle:
        payload = yaml.safe_load(handle)
    if not isinstance(payload, dict):
        raise TypeError(f"Top-level config must be a mapping: {source}")
    if overrides:
        payload = _deep_merge(payload, overrides)
    return ExperimentConfig(raw=payload, source=source)
