"""Explicit Phase 1 train-fitted output conditioning; H0 never uses these data.

The network predicts dimensionless z, and the public prediction is mu + std*z.
The loss still receives original units and divides its residual by that same
training std. This module does not import phase1, avoiding a model/package cycle.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
import math
import re

import torch
from torch import nn

from ..data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
from .phase1_specs import PHASE1_GRAPH_DESCRIPTOR_NAMES


OUTPUT_NORMALIZATION_VERSION = "phase1_train_affine_output_v1"
OUTPUT_TRANSFORM = "mean_plus_std_times_raw"
REGRESSION_TARGETS = ("energy", "charge") + tuple(
    "graph_descriptor/" + name for name in PHASE1_GRAPH_DESCRIPTOR_NAMES
) + ("node_descriptor/estate_index",)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _json_values(value):
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().tolist()
    if isinstance(value, Mapping):
        return {key: _json_values(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_values(item) for item in value]
    return value


def _hash(value):
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _scalar(value, name, *, positive=False):
    if isinstance(value, bool):
        raise ValueError(f"Output normalization {name} must be a finite scalar")
    try:
        tensor = torch.as_tensor(value, dtype=torch.float64)
    except (TypeError, ValueError, RuntimeError):
        raise ValueError(f"Output normalization {name} must be a finite scalar") from None
    if tensor.numel() != 1:
        raise ValueError(f"Output normalization {name} must be a finite scalar")
    result = float(tensor.item())
    represented = torch.tensor(result, dtype=torch.float32)
    if not math.isfinite(result) or not torch.isfinite(represented).item() or (positive and (result <= 0 or represented.item() <= 0)):
        raise ValueError(f"Output normalization {name} must be finite{' and positive' if positive else ''} in float32")
    return result


def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"Output normalization valid-label count must be a nonnegative integer: {name}")
    return value


def _targets_from_statistics(stats, provenance):
    required = {"muE", "stdE", "muQ", "stdQ", "graph_desc_mu", "graph_desc_std", "estate_index_mu", "estate_index_std"}
    if not isinstance(stats, Mapping) or not required.issubset(stats):
        raise ValueError("Output normalization requires all train-fitted means and standard deviations")
    counts = provenance.get("valid_label_counts")
    if not isinstance(counts, Mapping) or not {"energy", "charge", "estate_index", "graph_descriptor"}.issubset(counts):
        raise ValueError("Output normalization requires original train valid_label_counts")
    graph_mu, graph_std, graph_counts = stats["graph_desc_mu"], stats["graph_desc_std"], counts["graph_descriptor"]
    if not all(isinstance(value, list) and len(value) == len(GRAPH_DESCRIPTOR_NAMES) for value in (graph_mu, graph_std, graph_counts)):
        raise ValueError("Output normalization graph statistics/counts must follow the full original descriptor schema")

    def target(mean, std, count, name):
        return {"mean": _scalar(mean, name + ".mean"), "std": _scalar(std, name + ".std", positive=True),
                "count": _count(count, name)}

    targets = {
        "energy": target(stats["muE"], stats["stdE"], counts["energy"], "energy"),
        "charge": target(stats["muQ"], stats["stdQ"], counts["charge"], "charge"),
    }
    for name in PHASE1_GRAPH_DESCRIPTOR_NAMES:
        index = GRAPH_DESCRIPTOR_NAMES.index(name)
        key = "graph_descriptor/" + name
        targets[key] = target(graph_mu[index], graph_std[index], graph_counts[index], key)
    targets["node_descriptor/estate_index"] = target(
        stats["estate_index_mu"], stats["estate_index_std"], counts["estate_index"], "node_descriptor/estate_index"
    )
    return targets


def _validate_training_provenance(stats, provenance):
    if not isinstance(provenance, Mapping) or provenance.get("train_only") is not True:
        raise ValueError("Output normalization requires explicitly train-only provenance")
    required = {"train_pool_hash", "train_view_hash", "statistics_hash", "provenance_hash",
                "sampled_record_keys_hash", "estimator_version", "seed", "cap", "sampled_structure_count",
                "sampled_logical_indices", "valid_label_counts"}
    if not required.issubset(provenance):
        raise ValueError("Output normalization lacks complete fitted-training provenance")
    for field in ("train_pool_hash", "train_view_hash", "statistics_hash", "provenance_hash", "sampled_record_keys_hash"):
        if not isinstance(provenance[field], str) or not SHA256_PATTERN.fullmatch(provenance[field]):
            raise ValueError(f"Output normalization provenance lacks a valid SHA-256: {field}")
    if _hash(stats) != provenance["statistics_hash"]:
        raise ValueError("Output normalization training statistics_hash mismatch")
    unsigned = {key: value for key, value in provenance.items() if key != "provenance_hash"}
    if _hash(unsigned) != provenance["provenance_hash"]:
        raise ValueError("Output normalization training provenance_hash mismatch")


def train_regression_normalization(stats, provenance):
    """Return a JSON contract for precisely the 26 Phase 1 continuous outputs.

    Counts and provenance are taken exclusively from fit_train_statistics.
    The complete original statistical snapshot is retained for hash verification;
    excluded/legacy fields in that snapshot never create prediction transforms.
    """
    stats, provenance = _json_values(stats), _json_values(provenance)
    _validate_training_provenance(stats, provenance)
    targets = _targets_from_statistics(stats, provenance)
    contract = {
        "version": OUTPUT_NORMALIZATION_VERSION, "transform": OUTPUT_TRANSFORM,
        "targets": targets, "training_statistics": stats, "training_provenance": provenance,
        "training_statistics_sha256": provenance["statistics_hash"],
        "provenance_sha256": provenance["provenance_hash"],
    }
    contract["contract_sha256"] = _hash(contract)
    return contract


def validate_regression_normalization(contract):
    if not isinstance(contract, Mapping):
        raise ValueError("regression_output_normalization must be a complete training contract")
    if contract.get("version") == "phase1_full_train_affine_output_v2":
        from ..training.full_corpus_normalization import validate_full_train_regression_normalization
        return validate_full_train_regression_normalization(deepcopy(dict(contract)))
    contract = deepcopy(dict(contract))
    expected_fields = {"version", "transform", "targets", "training_statistics", "training_provenance",
                       "training_statistics_sha256", "provenance_sha256", "contract_sha256"}
    if set(contract) != expected_fields or contract.get("version") != OUTPUT_NORMALIZATION_VERSION or contract.get("transform") != OUTPUT_TRANSFORM:
        raise ValueError("Unsupported or incomplete Phase 1 output normalization contract")
    if not isinstance(contract["targets"], Mapping) or set(contract["targets"]) != set(REGRESSION_TARGETS):
        raise ValueError("Output normalization must contain exactly the retained Phase 1 continuous heads")
    rebuilt = train_regression_normalization(contract["training_statistics"], contract["training_provenance"])
    if contract != rebuilt:
        raise ValueError("Output normalization contract differs from its train-fitted statistics/provenance")
    return contract


class Phase1RegressionNormalization(nn.Module):
    """Fixed output buffers; no learned parameters, RNG use or H0 inputs."""
    def __init__(self, contract):
        super().__init__()
        self.contract = validate_regression_normalization(contract)
        self.target_indices = {name: index for index, name in enumerate(REGRESSION_TARGETS)}
        targets = self.contract["targets"]
        self.register_buffer("mean", torch.tensor([targets[name]["mean"] for name in REGRESSION_TARGETS], dtype=torch.float32))
        self.register_buffer("std", torch.tensor([targets[name]["std"] for name in REGRESSION_TARGETS], dtype=torch.float32))

    def forward(self, name, raw):
        index = self.target_indices[name]
        # Keep physical values/residuals in float32 under autocast as well.
        return self.mean[index].float() + self.std[index].float() * raw.float()
