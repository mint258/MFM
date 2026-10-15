"""Consume closed train-only sufficient-statistic controls in physical units.

This performs no fitting, file IO or target transformation. The caller verifies
physical artifact bytes; seals here establish internal consistency, not label
truth. Clean-element population counts never become a corrupted-S baseline.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from types import MappingProxyType

import numpy as np

from ..model.phase1_specs import (PHASE1_GRAPH_DESCRIPTOR_NAMES,
    PHASE1_CHARGE_DESCRIPTOR_SPECS, PHASE1_ELEMENT_DESCRIPTOR_SPECS)
from ..training.full_corpus_normalization import validate_full_train_regression_normalization

SCHEMA = "phase1_full_train_sufficient_statistic_controls_v1"
BASIS = "native_element_counts_Z1_to_Z118_then_intercept_v1"
BINDING_FIELDS = frozenset(("schema_version", "train_only", "full_coverage", "role", "estimator",
    "train_manifest_sha256", "train_view_sha256", "base_index_sha256", "quality_artifact_sha256",
    "moments_file_sha256", "retained_train_records", "observed_train_records", "observed_train_atoms"))


class FullCorpusControlsError(ValueError):
    pass


def _require(value, message):
    if not value:
        raise FullCorpusControlsError(message)


def _number(value, name, *, nonnegative=False):
    try:
        valid = type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        valid = False
    _require(valid, name + " must be finite numeric")
    _require(not nonnegative or value >= 0, name + " must be nonnegative")
    return float(value)


def _integer(value, name, *, maximum=None):
    _require(type(value) is int and value >= 0, name + " must be a nonnegative integer")
    _require(maximum is None or value <= maximum, name + " exceeds native training coverage")
    return value


def _owned_json(value):
    # Reject non-JSON objects before serialization, including NumPy scalars,
    # ambiguous int object keys and caller-owned cyclic containers.
    active, count = set(), [0]
    def walk(item, depth):
        count[0] += 1
        _require(depth <= 32 and count[0] <= 100000, "Controls metadata exceeds structural bounds")
        if type(item) is dict or type(item) is list:
            _require(id(item) not in active, "Cyclic controls metadata")
            active.add(id(item))
            if type(item) is dict:
                _require(all(type(key) is str for key in item), "Controls object keys must be strings")
                for key, child in item.items():
                    walk(key, depth + 1)
                    walk(child, depth + 1)
            else:
                for child in item:
                    walk(child, depth + 1)
            active.remove(id(item))
        elif type(item) is str:
            _require(len(item) <= 1048576, "Controls string exceeds metadata bound")
        else:
            _require(item is None or type(item) in (bool, int, float), "Controls must contain only JSON builtins")
            if type(item) is float:
                _require(math.isfinite(item), "Nonfinite controls metadata")
    walk(value, 0)
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                             allow_nan=False).encode("ascii")
    except (ValueError, TypeError, OverflowError) as exc:
        raise FullCorpusControlsError("Invalid controls JSON") from exc
    _require(len(encoded) <= 1048576, "Controls metadata exceeds 1 MiB")
    return json.loads(encoded)


def _hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def _freeze(value):
    if type(value) is dict:
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value


def _array(values, dtype):
    # A bytes-backed array cannot be made writeable by the receiving caller.
    return np.frombuffer(np.asarray(values, dtype=dtype).tobytes(), dtype=dtype)


@dataclass(frozen=True)
class FullCorpusControls:
    n_atom_types: int
    energy_coefficients: np.ndarray | None
    charge_means: np.ndarray | None
    charge_counts: np.ndarray
    charge_global_mean: float
    element_majority: None
    bond_majority: None
    graph_means: object
    node_predictions: object
    unavailable: object
    provenance: object
    _json_text: str

    def to_dict(self):
        """Return owned JSON; mutation cannot change these controls."""
        return json.loads(self._json_text)


def load_full_corpus_controls(controls, normalization):
    """Validate the actual fullprep controls against its complete normalization.

    Energy coefficients have 118 physical Z-count columns plus one intercept,
    not 119 model classes plus an intercept. Padding is never a physical atom.
    """
    row = _owned_json(controls)
    _require(type(row) is dict, "Controls must be an object")
    fields = {"schema_version", "state", "formal_eligible", "training_binding", "energy", "charge",
        "continuous", "categorical", "native_clean_element_control", "topology_element_control",
        "bond_control", "baseline_predictions_change_training_targets", "validation_or_downstream_labels_used_for_fit",
        "chemical_or_negative_label_truth_independently_verified", "controls_sha256"}
    _require(set(row) == fields and row["schema_version"] == SCHEMA, "Controls schema/fields differ")
    _require(row["controls_sha256"] == _hash({k: v for k, v in row.items() if k != "controls_sha256"}),
             "Controls self-seal differs")
    _require(row["state"] == "NOT_FROZEN", "Controls evidence state differs")
    for name in ("formal_eligible", "baseline_predictions_change_training_targets",
                 "validation_or_downstream_labels_used_for_fit", "chemical_or_negative_label_truth_independently_verified"):
        _require(row[name] is False, "Controls may not claim " + name)
    try:
        norm = validate_full_train_regression_normalization(normalization)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise FullCorpusControlsError("Invalid full-training normalization") from exc
    binding = row["training_binding"]
    _require(type(binding) is dict and set(binding) == BINDING_FIELDS,
             "Controls require the exact 13-field complete training binding")
    expected_binding = {key: norm["training_provenance"][key] for key in BINDING_FIELDS}
    _require(binding == expected_binding and all(type(binding[key]) is type(expected_binding[key]) for key in BINDING_FIELDS)
             and _hash(binding) == _hash(expected_binding),
             "Controls training binding differs from normalization")
    moments, atoms = norm["full_training_moments"], binding["observed_train_atoms"]
    unavailable = {}
    def missing(name, status, reason):
        unavailable[name] = {"available": False, "status": status, "reason": reason}

    energy = row["energy"]
    common = {"available", "valid_labels", "basis", "physical_element_count", "intercept_index",
        "model_atom_classes_including_padding", "padding_class", "training_application", "units",
        "gram_minimum_eigenvalue", "gram_psd_roundoff_tolerance", "coefficients"}
    extra = {"gram_rank", "gram_singular_values", "normal_equation_residual_l2", "solver", "numerical_scope"}
    available = moments["energy"]["count"] > 0
    _require(type(energy) is dict and set(energy) == common | (extra if available else set()), "Energy control fields differ")
    _require(energy["available"] is available and type(energy["valid_labels"]) is int
             and energy["valid_labels"] == moments["energy"]["count"], "Energy coverage differs")
    _require(energy["basis"] == BASIS and all(type(energy[k]) is int and energy[k] == v for k, v in
        (("physical_element_count", 118), ("intercept_index", 118), ("model_atom_classes_including_padding", 119), ("padding_class", 118))),
        "Energy control must use physical118 plus intercept, not model119 plus intercept")
    _require(energy["training_application"] == "NONE" and energy["units"] == "kcal/mol", "Energy targets may not be baseline-subtracted")
    tolerance = _number(energy["gram_psd_roundoff_tolerance"], "Gram tolerance", nonnegative=True)
    _require(_number(energy["gram_minimum_eigenvalue"], "Gram minimum eigenvalue") >= -tolerance, "Energy Gram diagnostics are inconsistent")
    coefficients = None
    if available:
        _require(type(energy["coefficients"]) is list and len(energy["coefficients"]) == 119, "Energy coefficient width must be 119")
        coefficients = _array([_number(v, "Energy coefficient") for v in energy["coefficients"]], np.float64)
        _integer(energy["gram_rank"], "Gram rank", maximum=119)
        _require(energy["gram_rank"] > 0 and type(energy["gram_singular_values"]) is list
                 and len(energy["gram_singular_values"]) == 119, "Energy Gram rank/singular values differ")
        for value in energy["gram_singular_values"]:
            _number(value, "Gram singular value", nonnegative=True)
        _number(energy["normal_equation_residual_l2"], "Gram residual", nonnegative=True)
        _require(energy["solver"] == "numpy.linalg.lstsq(float64 XTX, float64 XTy, rcond=None)"
            and energy["numerical_scope"] == "Moore-Penrose Gram-space solve; conditioning is squared; not old direct-design SVD byte equivalence",
            "Energy control solve recipe differs")
    else:
        _require(energy["coefficients"] is None, "Unavailable energy control must be None")
        missing("energy_kcal_per_mol", "NO_OBSERVED_TRAINING_LABELS", "No observed training energy labels")

    charge = row["charge"]
    _require(type(charge) is dict and set(charge) == {"available", "means_Z1_to_Z118", "counts_Z1_to_Z118", "global_mean", "units", "definition", "unseen_element"}, "Charge control fields differ")
    _require(type(charge["counts_Z1_to_Z118"]) is list and len(charge["counts_Z1_to_Z118"]) == 118, "Charge count width must be 118")
    counts = [_integer(v, "Element charge count", maximum=atoms) for v in charge["counts_Z1_to_Z118"]]
    qcount = moments["charge"]["count"]
    _require(sum(counts) == qcount and charge["available"] is (qcount > 0), "Charge coverage differs")
    global_mean = _number(charge["global_mean"], "Global charge mean")
    _require(global_mean == moments["charge"]["mean"] and charge["units"] == "e"
        and charge["definition"] == "MOPAC NET ATOMIC CHARGES"
        and charge["unseen_element"] == "observed training global mean; count unseen validation explicitly", "Charge source/units/mean recipe differs")
    means = None
    if qcount:
        _require(type(charge["means_Z1_to_Z118"]) is list and len(charge["means_Z1_to_Z118"]) == 118, "Charge mean width must be 118")
        values = [_number(v, "Element charge mean") for v in charge["means_Z1_to_Z118"]]
        _require(all(counts[i] or values[i] == global_mean for i in range(118)), "Unseen element must use training global mean")
        means = _array(values, np.float64)
    else:
        _require(charge["means_Z1_to_Z118"] is None, "Unavailable charge control must be None")
        missing("net_atomic_charge_e", "NO_OBSERVED_TRAINING_LABELS", "No observed training NET ATOMIC CHARGES")

    continuous = row["continuous"]
    expected = {"estate_index"} | {"graph/" + name for name in PHASE1_GRAPH_DESCRIPTOR_NAMES}
    _require(type(continuous) is dict and set(continuous) == expected, "Continuous control streams differ")
    graph_means, node_predictions = {}, {}
    for name, item in continuous.items():
        _require(type(item) is dict and set(item) == {"available", "valid_labels", "prediction"}, "Continuous control fields differ")
        observed = moments[name]["count"]
        _require(item["available"] is (observed > 0) and type(item["valid_labels"]) is int
                 and item["valid_labels"] == observed, "Continuous control coverage differs")
        target_name = name.removeprefix("graph/")
        if observed:
            prediction = _number(item["prediction"], "Continuous prediction")
            _require(prediction == moments[name]["mean"], "Continuous prediction differs from train-only mean")
            (node_predictions if name == "estate_index" else graph_means)[target_name] = prediction
        else:
            _require(item["prediction"] is None, "Unavailable continuous prediction must be None")
            missing("D/" + target_name, "NO_OBSERVED_TRAINING_LABELS", "No observed training labels")
    categories = {spec.name: spec for spec in PHASE1_CHARGE_DESCRIPTOR_SPECS + PHASE1_ELEMENT_DESCRIPTOR_SPECS if spec.task_type != "regression"}
    _require(type(row["categorical"]) is dict and set(row["categorical"]) == set(categories), "Categorical control tasks differ")
    for name, item in row["categorical"].items():
        _require(type(item) is dict and set(item) == {"available", "valid_labels", "prediction", "class_counts", "tie_break"}, "Categorical control fields differ")
        limit = 2 if categories[name].task_type == "binary" else categories[name].num_classes
        histogram = item["class_counts"]
        _require(type(histogram) is dict and all(k.isascii() and k.isdecimal() and str(int(k)) == k and int(k) < limit for k in histogram), "Categorical class domain differs")
        for value in histogram.values():
            _require(_integer(value, "Categorical class count", maximum=atoms) > 0, "Categorical counts must be positive")
        total = sum(histogram.values())
        _require(type(item["valid_labels"]) is int and item["valid_labels"] == total <= atoms
                 and item["available"] is bool(total) and item["tie_break"] == "smallest_class_id", "Categorical coverage/tie recipe differs")
        if total:
            winner = min(histogram, key=lambda k: (-histogram[k], int(k)))
            _require(type(item["prediction"]) is int and item["prediction"] == int(winner), "Categorical prediction differs from training majority")
            node_predictions[name] = item["prediction"]
        else:
            _require(item["prediction"] is None, "Unavailable category prediction must be None")
            missing("D/" + name, "NO_OBSERVED_TRAINING_LABELS", "No observed training labels")
    native = row["native_clean_element_control"]
    complete = qcount == atoms
    _require(type(native) is dict and set(native) == {"available", "prediction_zero_based", "class_counts_Z1_to_Z118", "basis", "same_as_corrupted_topology_majority"}
        and native["available"] is complete and native["same_as_corrupted_topology_majority"] is False
        and native["basis"] == "all retained native clean atoms, inferred only from proved full charge coverage", "Native clean population control differs")
    _require(native["class_counts_Z1_to_Z118"] == (counts if complete else None)
        and (type(native["prediction_zero_based"]) is int if complete else native["prediction_zero_based"] is None)
        and native["prediction_zero_based"] == (min(range(118), key=lambda i: (-counts[i], i)) if complete else None), "Native clean majority/counts differ")
    for key, target, status in (("topology_element_control", "element", "PENDING_ACTUAL_TRAIN_SOURCE_CORRUPTION_FIT"),
                                ("bond_control", "bond_order_positive", "PENDING_ACTUAL_TRAIN_SOURCE_BOND_FIT")):
        item = row[key]
        _require(type(item) is dict and set(item) == {"available", "status", "reason"} and item["available"] is False
                 and item["status"] == status and type(item["reason"]) is str and bool(item["reason"]), "Corrupted-S/bond controls require explicit pending evidence")
        missing(target, status, item["reason"])
    provenance = {"controls_sha256": row["controls_sha256"], "normalization_contract_sha256": norm["contract_sha256"],
                  "training_binding": binding, "physical_artifact_bytes_independently_verified": False,
                  "baseline_predictions_change_training_targets": False}
    return FullCorpusControls(118, coefficients, means, _array(counts, np.int64), global_mean, None, None,
        _freeze(graph_means), _freeze(node_predictions), _freeze(unavailable), _freeze(provenance),
        json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False))
