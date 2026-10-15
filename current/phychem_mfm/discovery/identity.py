from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


RECIPE_SCHEMA_VERSION = 1
SCIENTIFIC_SECTIONS = (
    "architecture",
    "backbone",
    "expert",
    "head",
    "supervision",
    "loss",
    "schedule",
    "optimizer",
    "training",
    "perturbation",
    "convergence_gate",
)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(value[key]) for key in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item") and callable(value.item):
        try:
            return value.item()
        except (ValueError, TypeError):
            pass
    return value


def canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(_jsonable(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def scientific_recipe(config: Mapping[str, Any], *, train_pool_hash: str, validation_pool_hash: str) -> dict[str, Any]:
    """Return only fields that determine the scientific meaning of a run.

    Runtime-only settings (paths for logs, worker count, W&B mode and device) are
    intentionally excluded.  Pool identities are mandatory and therefore two
    equally sized but differently sampled pools can never share a recipe hash.
    """

    payload: dict[str, Any] = {
        "recipe_schema_version": RECIPE_SCHEMA_VERSION,
        "train_pool_hash": str(train_pool_hash),
        "validation_pool_hash": str(validation_pool_hash),
    }
    for section in SCIENTIFIC_SECTIONS:
        if section in config:
            payload[section] = _jsonable(config[section])
    return payload


def recipe_hash(config: Mapping[str, Any], *, train_pool_hash: str, validation_pool_hash: str) -> str:
    return canonical_sha256(
        scientific_recipe(
            config,
            train_pool_hash=train_pool_hash,
            validation_pool_hash=validation_pool_hash,
        )
    )
