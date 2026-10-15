"""Frozen five-dataset fit inventory; stdlib metadata, never target access."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re

SCHEMA = "phase1_full_downstream_fit_plan_v1"
MAIN = "atom_mlp64"
AUX = "raw_mean_h0_linear"
DATASETS = ("qm7", "qm9", "cyp_isoform", "az_exactsom", "expansionrx")
SHA = re.compile(r"[0-9a-f]{64}\Z")


class FormalReadoutError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise FormalReadoutError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def sealed(value, field):
    require(type(value) is dict and value.get(field) == digest(
        {key: item for key, item in value.items() if key != field}), "Invalid self seal: " + field)
    return value


def task_spec(dataset, analysis_endpoints):
    tasks = dataset["tasks"]
    if dataset["dataset_id"] in ("qm7", "qm9"):
        return [(row["task_id"], row["endpoint_id"], row["unit"], row["primary_inference"])
                for row in tasks]
    return [(task, endpoint, analysis_endpoints[endpoint]["units"], True) for task, endpoint
            in zip(tasks, dataset["endpoint_ids"], strict=True)]


def compile_plan(protocol, *, protocol_file_sha256):
    """All 62 groups for every actual declared encoder, with no mask filtering."""
    require(type(protocol_file_sha256) is str and SHA.fullmatch(protocol_file_sha256), "Raw protocol SHA required")
    sealed(protocol, "content_sha256")
    require(protocol.get("state") == "frozen" and protocol.get("seeds") == [0, 1, 2], "Frozen three-seed authority required")
    downstream = protocol["downstream"]
    definitions = downstream["dataset_definitions"]
    require(tuple(row["dataset_id"] for row in definitions) == DATASETS, "Complete five-dataset ordered definition required")
    require(downstream["input_dimension"] == 384 and downstream["readout_seeds"] == [0], "Frozen native384/readout-seed0 required")
    policy = downstream["optimization_policy"]
    require(policy["batch_graphs"] == 32 and policy["epochs"] == 20
            and policy["gradient_clip_norm"] is None
            and policy["reduction"] == "task_then_observed_label_mean", "Fixed readout recipe differs")
    require(downstream["readout_policy"]["atom_hidden_dim"] == 64
            and downstream["readout_policy"]["atom_layers"] == 1
            and downstream["readout_policy"]["main_encoder_mode"] == "frozen"
            and downstream["readout_policy"]["complement_graph_pooling"] == "mean", "Readout capacity/encoder policy differs")
    main_variants = ["none", "S", "D", "P", "SD", "SP", "DP", "SDP"]
    require(protocol["variants"] == main_variants, "Complete main encoder matrix required")
    strategies = protocol["strategies"]
    require(set(strategies) == {"joint", "sdp_positive_nominal_equal_integral_v2"}, "Frozen strategy matrix differs")
    require(strategies["joint"]["variants"] == main_variants and strategies["joint"]["seeds"] == [0, 1, 2]
            and strategies["sdp_positive_nominal_equal_integral_v2"]["variants"] == ["SDP"]
            and strategies["sdp_positive_nominal_equal_integral_v2"]["seeds"] == [0, 1, 2], "Strategy coverage differs")
    encoders = [{"strategy": strategy, "variant": variant, "pretraining_seed": seed}
                for strategy, entry in strategies.items() for seed in entry["seeds"] for variant in entry["variants"]]
    groups = []
    for definition in definitions:
        dataset_id, level = definition["dataset_id"], definition["output_level"]
        specification = task_spec(definition, downstream["analysis_rules"]["endpoints"])
        for fold_id in (["official"] if dataset_id == "expansionrx" else list(map(str, range(10)))):
            for readout in ([MAIN, AUX] if level == "graph" else [MAIN]):
                groups.append({"group_id": dataset_id + "." + fold_id + "." + readout,
                    "dataset_id": dataset_id, "fold_id": fold_id, "readout": readout,
                    "readout_seed": 0, "output_level": level,
                    "tasks": [row[0] for row in specification],
                    "endpoints": [row[1] for row in specification],
                    "units": [row[2] for row in specification],
                    "primary_inference": [row[3] for row in specification],
                    "batch_graphs": 32, "epochs": 20, "checkpoint_selection": "FIXED_20_EPOCH_FINAL"})
    fits = [{**deepcopy(group), **encoder,
             "protocol_content_sha256": protocol["content_sha256"],
             "fit_id": encoder["strategy"] + "." + encoder["variant"] + ".seed" + str(encoder["pretraining_seed"]) + "." + group["group_id"]}
            for encoder in encoders for group in groups]
    main_groups = [row for row in groups if row["readout"] == MAIN]
    primary_cells = sum(sum(row["primary_inference"]) for row in main_groups)
    all_cells = sum(len(row["tasks"]) for row in main_groups)
    require(len(encoders) == 27 and len(main_groups) == 41 and len(groups) - len(main_groups) == 21
            and len(fits) == 1674 and primary_cells == 239 and all_cells == 269, "Frozen fit/report scope accounting differs")
    result = {"schema_version": SCHEMA, "state": "EXECUTION_BINDINGS_PENDING", "formal_eligible": False,
        "protocol_file_sha256": protocol_file_sha256, "protocol_content_sha256": protocol["content_sha256"],
        "encoders": encoders, "groups": groups, "fits": fits,
        "counts": {"encoders": 27, "main_groups": 41, "auxiliary_groups": 21, "maximum_fits": 1674,
                   "all_output_tasks": 35, "primary_endpoints": 32, "primary_cells": 239, "all_task_cells": 269},
        "endpoint_rule": "trained=actual complete three-epoch FINAL; none=fresh paired initialization",
        "statistics_envelope": "PENDING actual complete cell grid; existing fixed-optimizer-step v1 is not reused"}
    result["plan_sha256"] = digest(result)
    return result


def select_fit(plan, fit_id):
    sealed(plan, "plan_sha256")
    matches = [row for row in plan["fits"] if row["fit_id"] == fit_id]
    require(len(matches) == 1, "Exactly one predeclared complete-matrix fit required")
    return deepcopy(matches[0])


def verify_wire_payload(actual, expected):
    """Restore source scalar types, then require exact finite numeric equality."""
    require(type(actual) is dict and type(expected) is dict, "History row dictionaries required")
    require({key for key in actual if not key.startswith("_")} == set(expected), "Unknown/missing scientific history key")
    restored = {}
    for key, value in expected.items():
        observed = actual[key]
        if type(value) is float:
            require(type(observed) in (int, float) and float(observed) == value, "History float differs: " + key)
            restored[key] = float(observed)
        elif type(value) is int:
            require(type(observed) in (int, float) and type(observed) is not bool
                    and observed == value and int(observed) == value, "History integer differs: " + key)
            restored[key] = int(observed)
        else:
            require(type(observed) is type(value) and observed == value, "History scalar type/value differs: " + key)
            restored[key] = observed
    require(canonical(restored) == canonical(expected), "History source-typed payload differs")
    return restored
