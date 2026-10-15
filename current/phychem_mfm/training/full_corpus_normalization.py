"""Full-training-view affine output conditioning without a corpus-sized ID list.

The caller supplies the closed train-only Chan population moments and compact
view binding. This verifies their internal consistency, not chemical truth.
Unavailable targets have count zero and fixed identity placeholders; this does
not turn unavailable labels into negative supervision.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import math
import re

from ..data.descriptor_schema import GRAPH_DESCRIPTOR_NAMES
from ..model.phase1_specs import PHASE1_GRAPH_DESCRIPTOR_NAMES

VERSION = "phase1_full_train_affine_output_v2"
ESTIMATOR = "phase1_train_only_fp64_chan_population_moments_v1"
SHA = re.compile(r"^[0-9a-f]{64}$")
STREAMS = ("energy", "charge", "estate_index") + tuple(
    "graph/" + name for name in PHASE1_GRAPH_DESCRIPTOR_NAMES)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def full_train_regression_normalization(moments, binding):
    """Build a sealed 26-output contract from complete retained-training moments.

    ``binding`` describes actual compact files. Hash strings are declarations
    here; the runner must additionally check their physical files and role.
    No old fit IDs or fabricated ``sampled_logical_indices`` are accepted.
    """
    moments, binding = deepcopy(moments), deepcopy(binding)
    fields = {"schema_version", "train_only", "full_coverage", "role",
              "estimator", "train_manifest_sha256", "train_view_sha256",
              "base_index_sha256", "quality_artifact_sha256", "moments_file_sha256",
              "retained_train_records", "observed_train_records", "observed_train_atoms"}
    if not isinstance(binding, dict) or set(binding) != fields:
        raise ValueError("Full-training normalization requires exactly the compact coverage binding")
    if (binding["schema_version"] != "phase1_full_train_normalization_binding_v1"
            or binding["train_only"] is not True or binding["full_coverage"] is not True
            or binding["role"] != "train" or binding["estimator"] != ESTIMATOR):
        raise ValueError("Full-training normalization lacks train-only complete-coverage evidence")
    for key in ("retained_train_records", "observed_train_records", "observed_train_atoms"):
        if type(binding[key]) is not int or binding[key] <= 0:
            raise ValueError("Full-training normalization coverage counts must be positive integers")
    if binding["retained_train_records"] != binding["observed_train_records"]:
        raise ValueError("Train-fit coverage differs from the retained training view")
    for key in fields:
        if key.endswith("sha256") and (type(binding[key]) is not str or not SHA.fullmatch(binding[key])):
            raise ValueError("Invalid normalization file/manifest SHA-256: " + key)
    if not isinstance(moments, dict) or set(moments) != set(STREAMS):
        raise ValueError("Full-training moments must contain exactly the 26 retained continuous streams")
    stats = {"graph_desc_mu": [0.0] * len(GRAPH_DESCRIPTOR_NAMES),
             "graph_desc_std": [1.0] * len(GRAPH_DESCRIPTOR_NAMES)}
    counts = {"graph_descriptor": [0] * len(GRAPH_DESCRIPTOR_NAMES)}
    for name, row in moments.items():
        if not isinstance(row, dict) or set(row) != {"count", "mean", "m2"}:
            raise ValueError("Moment fields must be count/mean/m2")
        if type(row["count"]) is not int or row["count"] < 0:
            raise ValueError("Moment count must be a nonnegative integer")
        ceiling = binding["observed_train_atoms"] if name in ("charge", "estate_index") else binding["observed_train_records"]
        if row["count"] > ceiling:
            raise ValueError("Moment count exceeds complete native training coverage")
        if any(type(row[k]) not in (int, float) or not math.isfinite(row[k]) for k in ("mean", "m2")) or row["m2"] < 0:
            raise ValueError("Moments must be finite with nonnegative M2")
        if not row["count"] and (row["mean"] != 0 or row["m2"] != 0):
            raise ValueError("Unavailable moments must retain explicit zero sufficient statistics")
        mean = float(row["mean"]) if row["count"] else 0.0
        std = max(math.sqrt(row["m2"] / row["count"]),
                  1e-6 if name in ("energy", "charge") else 1e-3) if row["count"] else 1.0
        if name == "energy":
            stats.update(muE=mean, stdE=std)
        elif name == "charge":
            stats.update(muQ=mean, stdQ=std)
        elif name == "estate_index":
            stats.update(estate_index_mu=mean, estate_index_std=std)
        else:
            index = GRAPH_DESCRIPTOR_NAMES.index(name.removeprefix("graph/"))
            stats["graph_desc_mu"][index], stats["graph_desc_std"][index] = mean, std
            counts["graph_descriptor"][index] = row["count"]
        if name in ("energy", "charge", "estate_index"):
            counts[name] = row["count"]
    provenance = {**binding, "valid_label_counts": counts,
                  "moment_snapshot_sha256": _hash(moments),
                  "statistics_hash": _hash(stats), "sampled_logical_indices_materialized": False}
    provenance["provenance_hash"] = _hash(provenance)
    # Reuse the identical scalar/F32 guards and original target-index mapping.
    from ..model.normalization import OUTPUT_TRANSFORM, _targets_from_statistics
    contract = {"version": VERSION, "transform": OUTPUT_TRANSFORM,
                "targets": _targets_from_statistics(stats, provenance),
                "training_statistics": stats, "training_provenance": provenance,
                "training_statistics_sha256": provenance["statistics_hash"],
                "provenance_sha256": provenance["provenance_hash"],
                "full_training_moments": moments}
    contract["contract_sha256"] = _hash(contract)
    return contract


def validate_full_train_regression_normalization(contract):
    if not isinstance(contract, dict):
        raise ValueError("Full-training normalization must be a JSON object")
    fields = {"version", "transform", "targets", "training_statistics", "training_provenance",
              "training_statistics_sha256", "provenance_sha256", "full_training_moments", "contract_sha256"}
    if set(contract) != fields or contract["version"] != VERSION:
        raise ValueError("Invalid full-training normalization version/fields")
    binding = deepcopy(contract["training_provenance"])
    for key in ("valid_label_counts", "moment_snapshot_sha256", "statistics_hash",
                "sampled_logical_indices_materialized", "provenance_hash"):
        if key not in binding:
            raise ValueError("Incomplete full-training normalization provenance")
        binding.pop(key)
    rebuilt = full_train_regression_normalization(contract["full_training_moments"], binding)
    if contract != rebuilt:
        raise ValueError("Full-training affine contract differs from its complete moments and coverage binding")
    return rebuilt


def validate_full_train_moment_artifact(contract, artifact):
    """Cross-check the complete QA moment artifact, without scanning native rows.

    Physical file SHA checking belongs to the caller. The QA artifact's own seal
    uses its actual ASCII JSON recipe; the affine contract has a separate seal.
    No independently verified label or chemistry claim follows from these seals.
    """
    validate_full_train_regression_normalization(contract)
    if (not isinstance(artifact, dict) or artifact.get("schema_version") != ESTIMATOR
            or artifact.get("train_only") is not True):
        raise ValueError("Moment artifact must use the actual train-only Chan estimator")
    seal = artifact.get("statistics_sha256")
    unsigned = {key: value for key, value in artifact.items() if key != "statistics_sha256"}
    actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()
    if type(seal) is not str or not SHA.fullmatch(seal) or actual != seal:
        raise ValueError("Actual sufficient-statistic artifact self-seal differs")
    binding = contract["training_provenance"]
    for key in ("observed_train_records", "observed_train_atoms"):
        if type(artifact.get(key)) is not int or artifact[key] != binding[key]:
            raise ValueError("Moment artifact complete native coverage differs from affine binding: " + key)
    if artifact.get("moments") != contract["full_training_moments"]:
        raise ValueError("Moment artifact streams differ from the affine contract")
