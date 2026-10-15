"""Explicit additional strategy comparisons in a frozen Phase 1 protocol.

This standard-library-only contract does not select comparisons, create a
protocol, read recipe files, or relax the canonical eight-condition matrix.
Every contrast uses a subset of the same independent pretraining seeds and
the same per-condition budget. Its recipe bytes are separately hash-bound.
"""
from __future__ import annotations

from collections.abc import Mapping
import re


DIRECT_RECIPE = "direct_joint"
CONTRAST_VARIANTS = ("SD", "SP", "DP", "SDP")
_ID = re.compile(r"[a-z][a-z0-9_-]{0,63}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _seeds(values, name):
    if (not isinstance(values, list) or not values
            or any(type(value) is not int or value < 0 for value in values)
            or len(set(values)) != len(values)):
        raise ValueError(f"{name} must be a nonempty list of unique nonnegative integer seeds")
    return list(values)


def validated_contrasts(protocol):
    """Return detached, explicit contrast entries or reject the declaration.

    Missing ``contrasts`` preserves the direct-joint-only protocol. A present
    value must be a map, even when no additional comparisons are declared.
    Names are safe dotted-path tokens; duplicate recipe/condition/seed runs
    cannot be hidden behind different names. No stage or seed is inferred.
    """
    strategy = protocol.get("strategy", {})
    if not isinstance(strategy, Mapping):
        raise ValueError("strategy must be a mapping")
    if "contrasts" not in strategy:
        return {}
    values = strategy["contrasts"]
    if not isinstance(values, Mapping):
        raise ValueError("strategy.contrasts must be an explicit map")
    if not values:
        return {}
    pretraining = protocol.get("pretraining", {})
    if not isinstance(pretraining, Mapping):
        raise ValueError("pretraining must bind the main-matrix seeds")
    main_seeds = set(_seeds(pretraining.get("seeds"), "pretraining.seeds"))
    result, unique_runs = {}, set()
    for name, entry in values.items():
        if (not isinstance(name, str) or not _ID.fullmatch(name)
                or name == DIRECT_RECIPE):
            raise ValueError("Contrast id must be a safe lowercase token distinct from direct_joint")
        if not isinstance(entry, Mapping) or set(entry) != {"variant", "seeds", "recipe_sha256"}:
            raise ValueError(f"Contrast {name} must define exactly variant, seeds, recipe_sha256")
        variant = entry["variant"]
        if not isinstance(variant, str) or variant not in CONTRAST_VARIANTS:
            raise ValueError("Positive weighting contrasts require an explicit multi-group condition")
        seeds = _seeds(entry["seeds"], f"strategy.contrasts.{name}.seeds")
        if not set(seeds) <= main_seeds:
            raise ValueError("Contrast seeds must be a subset of the paired main-matrix pretraining seeds")
        digest = entry["recipe_sha256"]
        if not isinstance(digest, str) or not _SHA.fullmatch(digest):
            raise ValueError("Each contrast must pin its actual recipe artifact SHA-256")
        for seed in seeds:
            identity = (variant, digest, seed)
            if identity in unique_runs:
                raise ValueError("Duplicate recipe/condition/seed comparison declared under different ids")
            unique_runs.add(identity)
        result[name] = {"variant": variant, "seeds": seeds, "recipe_sha256": digest}
    return result


def contrast_hash_fields(protocol):
    return tuple(f"strategy.contrasts.{name}.recipe_sha256" for name in validated_contrasts(protocol))


def contrast_run_count(protocol):
    return sum(len(entry["seeds"]) for entry in validated_contrasts(protocol).values())
