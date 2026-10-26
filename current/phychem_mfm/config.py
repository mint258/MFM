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


def numeric_stability_configuration(config: Mapping[str, Any]) -> dict[str, Any]:
    """Canonical opt-in mode; omitted legacy configs keep their original identity."""
    from .model.v3_numeric_stability import LEGACY, COMPENSATED, validate_numeric_mode
    result = deepcopy(dict(config))
    section = result.get("numeric_stability")
    backbone, head = dict(result.get("backbone", {})), dict(result.get("head", {}))
    declared = [value["numeric_mode"] for value in (backbone, head) if "numeric_mode" in value]
    for mode in declared:
        validate_numeric_mode(mode)
    if "numeric_stability" not in result:
        if not declared:
            return result
        if len(declared) != 2 or declared[0] != declared[1]:
            raise ValueError("Both backbone/head must bind the same numeric mode")
        mode = declared[0]
    else:
        if not isinstance(section, Mapping) or set(section) != {"mode"}:
            raise ValueError("numeric_stability requires exactly one explicit mode")
        mode = validate_numeric_mode(section["mode"])
        if any(value != mode for value in declared):
            raise ValueError("Top-level/backbone/head numeric mode conflict")
    if mode == COMPENSATED:
        backbone["numeric_mode"] = head["numeric_mode"] = mode
        result["backbone"], result["head"] = backbone, head
    elif mode == LEGACY and declared:
        # Explicit legacy declarations are permitted but never added implicitly.
        result["backbone"], result["head"] = backbone, head
    return result
