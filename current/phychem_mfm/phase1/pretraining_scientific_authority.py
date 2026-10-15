"""Pretraining-only binding of frozen science, before actual metric-cell masks.

This reads metadata artifacts only. It never declares downstream execution
ready, creates mask hashes, edits a protocol, or relaxes the live GPU gate.
The same immutable pretraining protocol remains its resume authority; later
downstream bindings belong in a separate supplement referencing this science.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

AUTHORITY_FIELD = "scientific_authority_sha256"
ANALYSIS_FIELD = "downstream.statistics.analysis_plan_sha256"
PRETRAINING_SCOPE = "pretraining_only"
RESOURCE_POLICY = "user_requested_16cpu_64g_v1"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
MAX_METADATA_BYTES = 16 << 20


class ScientificAuthorityError(ValueError):
    pass


def _require(ok, message):
    if not ok:
        raise ScientificAuthorityError(message)


def _get(document, dotted):
    for key in dotted.split("."):
        _require(type(document) is dict and key in document, "Missing science projection field: " + dotted)
        document = document[key]
    return document


def _optional(document, dotted):
    for key in dotted.split("."):
        if type(document) is not dict or key not in document:
            return None
        document = document[key]
    return document


def _sha(value):
    _require(type(value) is str and _SHA.fullmatch(value), "Invalid actual scientific artifact SHA256")
    return value


def _canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()


def pretraining_only(protocol):
    return protocol.get("execution_scope") == PRETRAINING_SCOPE


def resource_projection_overrides(protocol):
    """Explicit host-resource revision; no scientific or LIVE allocation proof.

    The original authority remains unchanged. Only this concrete CPU/RAM
    request may differ, under the already explicit shared-GPU execution scope.
    Session authorization is recorded by the immutable execution producer;
    this function adds no approval token or fabricated isolation claim.
    """
    policy = _optional(protocol, "compute.resource_policy")
    if policy is None:
        return {}
    _require(type(policy) is str and policy == RESOURCE_POLICY, "Unknown host-resource execution policy")
    _require(pretraining_only(protocol)
             and _optional(protocol, "compute.gpu_isolation_policy") == "user_accepted_shared_gpu",
             "Host-resource override requires explicit shared-GPU pretraining_only execution")
    overrides = {"compute.cpus_per_task": 16, "compute.requested_cpu_memory_gib": 64}
    for field, expected in overrides.items():
        actual = _get(protocol, field)
        _require(type(actual) is int and actual == expected, "Host-resource override differs from CPU16/RAM64GiB: " + field)
    return overrides


def validate_scope_declaration(protocol):
    scope = protocol.get("execution_scope", "full")
    _require(type(scope) is str and scope in (PRETRAINING_SCOPE, "full", "downstream"), "Unknown execution scope")
    pending = _optional(protocol, "downstream.execution_bindings_state")
    if scope == PRETRAINING_SCOPE:
        _require(pending == "PENDING", "Pretraining-only scope must explicitly preserve pending downstream bindings")
        _require(_optional(protocol, ANALYSIS_FIELD) is None, "Pending execution cannot contain an invented or partial analysis-plan hash")
        _sha(protocol.get(AUTHORITY_FIELD))
    else:
        _require(pending in (None, "COMPLETE"), "Full/downstream scope cannot use pending metric-cell bindings")
    resource_projection_overrides(protocol)
    return scope


def _read_json(path, digest, *, size=None):
    path = Path(path)
    _require(path.is_file() and 0 < path.stat().st_size <= MAX_METADATA_BYTES, "Absent or oversized science metadata")
    with path.open("rb") as stream:
        raw = stream.read(MAX_METADATA_BYTES + 1)
    _require(len(raw) <= MAX_METADATA_BYTES and hashlib.sha256(raw).hexdigest() == _sha(digest)
             and (size is None or type(size) is int and len(raw) == size), "Actual scientific artifact bytes differ")
    def pairs(values):
        result = {}
        for key, value in values:
            _require(key not in result, "Duplicate scientific JSON key")
            result[key] = value
        return result
    def floating(text):
        value = float(text)
        _require(math.isfinite(value), "Nonfinite scientific JSON number")
        return value
    def constant(_text):
        raise ScientificAuthorityError("Nonfinite scientific JSON constant")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_float=floating,
                      parse_constant=constant), raw


def _match(protocol, field, expected):
    actual = _get(protocol, field)
    if isinstance(expected, bool) or isinstance(actual, bool):
        _require(type(actual) is type(expected), "Boolean science projection type drift: " + field)
    _require(actual == expected, "Frozen science projection drift: " + field)


def _artifact_match(protocol, artifacts, field, ref):
    _require(type(ref) is dict and set(ref) == {"path", "bytes", "sha256"}, "Invalid frozen scientific reference")
    _match(protocol, field, ref["sha256"])
    _require(field in artifacts, "Missing actual science projection artifact: " + field)
    value, raw = _read_json(artifacts[field], ref["sha256"], size=ref["bytes"])
    return value, raw


def verify_pretraining_scientific_authority(protocol, artifacts, *, now=None):
    """Check the complete frozen rule authority and its executable projection.

    Downstream rules live in the actual authority bytes, not a caller-created
    replacement plan. Only derived split/sample/missing-mask execution hashes
    are deferred; downstream statistics keep their existing complete-plan API.
    """
    try:
        _require(validate_scope_declaration(protocol) == PRETRAINING_SCOPE, "This verifier is pretraining-only")
        science, raw = _read_json(artifacts[AUTHORITY_FIELD], protocol[AUTHORITY_FIELD])
        _require(science.get("schema_version") == "phase1_scientific_protocol_v1" and science.get("state") == "frozen"
                 and science.get("scientific_choices_complete") is True, "Scientific choices are not completely frozen")
        frozen = datetime.fromisoformat(science["frozen_at"].replace("Z", "+00:00"))
        now = now or datetime.now(timezone.utc)
        _require(frozen.tzinfo is not None and frozen <= now, "Scientific authority timestamp is invalid or future")
        _require(science.get("content_sha256") == _canonical({key: value for key, value in science.items()
                 if key != "content_sha256"}), "Scientific authority canonical seal differs")
        _match(protocol, "trial_evidence.source_sha256", science["source"]["producer_source_sha256"])
        if _optional(protocol, "trial_evidence.producer_consumer_bridge_sha256") is None:
            _match(protocol, "source.commit", science["source"]["producer_commit"])
        _match(protocol, "downstream.final_evaluation_config_sha256", protocol[AUTHORITY_FIELD])
        _, rules_raw = _read_json(artifacts["downstream.final_evaluation_config_sha256"], protocol[AUTHORITY_FIELD], size=len(raw))
        _require(rules_raw == raw,
                 "Final rules artifact is not the identical complete scientific authority")
        bridge_field = "trial_evidence.producer_consumer_bridge_sha256"
        if _optional(protocol, bridge_field) is not None:
            bridge, _ = _read_json(artifacts[bridge_field], _get(protocol, bridge_field))
            _require(bridge["scientific_authority"]["sha256"] == protocol[AUTHORITY_FIELD],
                     "Trial source bridge and pretraining refer to different scientific authorities")
        refs = {"data.source_manifest_sha256": science["data"]["train_manifest"],
                "data.decontamination_sha256": science["data"]["decontamination"],
                "data.normalization_sha256": science["data"]["fitted_controls"],
                "data.normalization_train_ids_sha256": science["data"]["normalization_fit_ids"],
                "encoder.architecture_sha256": science["encoder"]["architecture"],
                "tasks.target_manifest_sha256": science["tasks"]["targets"],
                "tasks.label_contract_sha256": science["tasks"]["labels"],
                "strategy.loss_policy_sha256": science["pretraining"]["loss_policy"]}
        for field, ref in refs.items():
            _artifact_match(protocol, artifacts, field, ref)
        split, _ = _read_json(artifacts["data.split_manifest_sha256"], _get(protocol, "data.split_manifest_sha256"))
        train_ref, val_ref = science["data"]["train_manifest"], science["data"]["validation_manifest"]
        train, _ = _read_json(artifacts["data.source_manifest_sha256"], train_ref["sha256"], size=train_ref["bytes"])
        validation, _ = _read_json(val_ref["path"], val_ref["sha256"], size=val_ref["bytes"])
        _require(type(split) is dict and set(split) == {"schema_version", "train", "validation"}
                 and split["schema_version"] == "phase1_split_v1" and split["train"] == train
                 and split["validation"] == validation, "Pretraining split changes frozen train/validation membership")
        execution, _ = _artifact_match(protocol, artifacts, "strategy.schedule_sha256",
                                      science["pretraining"]["actual_execution_artifact"])
        readout, _ = _artifact_match(protocol, artifacts, "downstream.readout_config_sha256",
                                    science["downstream"]["actual_readout_configs"])
        _require(type(execution) is dict and type(execution.get("config")) is dict and type(readout) is dict,
                 "Frozen actual execution/readout config is incomplete")
        _match(protocol, "pretraining.variants", science["pretraining"]["variants"])
        _match(protocol, "pretraining.seeds", science["pretraining"]["seeds"])
        init = {seed: ref["sha256"] for seed, ref in science["encoder"]["paired_random_initialization_by_seed"].items()}
        _match(protocol, "pretraining.paired_random_initialization.encoder_sha256_by_seed", init)
        choices = science["pretraining"]["choices"]
        _match(protocol, "pretraining.budget.optimizer_steps_per_condition", choices["optimizer_updates_per_trained_condition"])
        _match(protocol, "pretraining.budget.structures_per_condition", choices["base_structure_exposures_per_trained_condition"])
        _match(protocol, "pretraining.budget.equivalence_rule", choices["budget_equivalence_rule"])
        _match(protocol, "pretraining.checkpoint_rule.selection_split", "fixed_budget")
        _match(protocol, "pretraining.checkpoint_rule.selection_metric", choices["checkpoint_rule"]["scientific_selection"])
        _match(protocol, "pretraining.checkpoint_rule.save_every_steps", choices["checkpoint_rule"]["save_every_updates"])
        _match(protocol, "pretraining.checkpoint_rule.keep_checkpoints", choices["checkpoint_rule"]["keep_rolling_checkpoints"])
        config = execution["config"]
        _require(config["training"]["base_molecules_per_batch"] == choices["base_molecules_per_update"]
                 and config["schedule"]["max_steps"] == choices["optimizer_updates_per_trained_condition"]
                 and config["schedule"]["warmup_steps"] == choices["schedule"]["warmup_steps"]
                 and config["schedule"]["min_lr_ratio"] == choices["schedule"]["minimum_lr_ratio"]
                 and execution["evaluation"]["every_updates"] == choices["validation_rule"]["every_updates"],
                 "Frozen execution config contradicts its scientific choices")
        _require(all(config["phase1"][key] == choices[key] for key in
                 ("max_atoms_per_molecule", "max_atoms_per_batch")), "Frozen execution atom caps differ")
        main = science["strategy"]["main"]
        _require(main == "direct_joint_from_step_zero", "Unsupported frozen main strategy")
        auxiliary = science["strategy"]["auxiliary"]
        _match(protocol, "strategy.contrasts", {auxiliary["id"]: {"variant": auxiliary["variant"],
               "seeds": auxiliary["seeds"], "recipe_sha256": auxiliary["recipe"]["sha256"]}})
        _match(protocol, "experiment.questions", science["experiment"]["questions"])
        _match(protocol, "experiment.main_comparisons", science["experiment"]["primary_comparisons"])
        downstream = science["downstream"]
        _require(all(key in downstream for key in ("optimization_policy", "split_policy", "metric_policy",
                 "geometry_and_mapping_policy", "dataset_definitions", "readout_policy", "analysis_rules",
                 "descriptive_rules", "statistics_limitations")), "Incomplete frozen downstream scientific rules")
        _match(protocol, "downstream.datasets", [row["dataset_id"] for row in downstream["dataset_definitions"]])
        policy = downstream["readout_policy"]
        _match(protocol, "downstream.readouts", [policy["main_class"], policy["complement_class"]])
        _match(protocol, "downstream.modes", [policy["main_encoder_mode"]])
        _match(protocol, "downstream.seeds", downstream["readout_seeds"])
        rules = downstream["analysis_rules"]
        _require(rules["schema_version"] == "phase1_scientific_analysis_rules_v1"
                 and "actual_hash_binding_rule" in rules and rules["independent_unit"] == "pretraining_seed"
                 and type(rules["endpoints"]) is dict and rules["endpoints"], "Frozen complete downstream statistics rules required")
        for endpoint in rules["endpoints"].values():
            _require(type(endpoint) is dict and set(endpoint) == {"dataset", "metric", "units", "direction", "mode",
                     "readout_config_sha256", "cells"}, "Scientific endpoint has missing rules or premature execution hashes")
            _require(type(endpoint["cells"]) is list and endpoint["cells"], "Scientific endpoint cells must be explicit")
            for cell in endpoint["cells"]:
                _require(type(cell) is dict and set(cell) == {"fold_id", "readout_seed", "weight"},
                         "Scientific cell has missing rules or premature mask/member hashes")
        primary = {comparison for family in rules["primary_families"] for comparison in rules["families"][family]}
        ids = [row["id"] for row in rules["comparisons"] if row["id"] in primary]
        _require(len(ids) == len(primary), "Frozen primary family/comparison scope is incomplete")
        _match(protocol, "downstream.main_comparisons", ids)
        _require(set(protocol["downstream"]["statistics"]) <= {"method", "primary_metric", "paired",
                 "confidence_level", "multiple_comparison_rule", "analysis_plan_sha256"}, "Runtime cannot override frozen statistical rules")
        for key in ("method", "confidence_level", "multiple_comparison_rule"):
            _match(protocol, "downstream.statistics." + key, rules[key])
        _require(downstream["metric_policy"]["primary_inference_endpoints"] == len(rules["endpoints"])
                 and downstream["metric_policy"]["all_output_tasks_reported"] == sum(len(row["tasks"])
                     for row in downstream["dataset_definitions"]), "Frozen task/endpoint inventory is inconsistent")
        compute, storage = science["resources"]["compute"], science["resources"]["storage"]
        fields = {"pretraining.budget.gpu_hours_per_condition": "maximum_gpu_hours_per_pretraining_job",
                  "compute.max_walltime_hours": "maximum_wall_hours_per_pretraining_job",
                  "compute.max_gpu_hours_total": "maximum_overall_gpu_hours_total",
                  "compute.max_concurrent_jobs": "max_concurrent_jobs", "compute.gpus_per_job": "gpus_per_job",
                  "compute.cpus_per_task": "cpus_per_task", "compute.partition": "partition",
                  "compute.allowed_nodes": "allowed_nodes", "compute.min_gpu_memory_gib": "min_gpu_memory_gib",
                  "compute.min_free_gpu_memory_gib": "min_free_gpu_memory_gib",
                  "compute.requested_cpu_memory_gib": "requested_cpu_memory_gib",
                  "downstream.budget.max_gpu_hours_total": "maximum_downstream_gpu_hours_total"}
        resource_overrides = resource_projection_overrides(protocol)
        for field, name in fields.items():
            _match(protocol, field, resource_overrides.get(field, compute[name]))
        _match(protocol, "downstream.budget.max_trials", downstream["maximum_training_trials"]["maximum_readout_training_runs"])
        for field, name in (("storage.max_run_bytes", "max_pretraining_run_gib"),
                            ("storage.max_total_artifact_bytes", "max_total_artifacts_gib"), ("storage.reserve_bytes", "reserve_gib")):
            _match(protocol, field, storage[name] * (1 << 30))
        _match(protocol, "tracking.provider", science["tracking"]["provider"])
        _match(protocol, "tracking.mode", science["tracking"]["mode"])
        pairing = choices["numerical_and_device_pairing"]
        environments = [row for row in pairing["supported_environments"]
                        if row["model"] == _get(protocol, "compute.gpu_model")]
        _require(len(environments) == 1, "GPU model has no unique frozen supported environment")
        _match(protocol, "compute.runtime_environment", environments[0])
        _match(protocol, "compute.precision", pairing["precision"])
        _match(protocol, "compute.paired_device_rule", pairing["paired_device_rule"])
        _require(pairing["precision"] == "FP32", "The current pretraining runner supports FP32 only")
        return {"status": "FROZEN_PRETRAINING_SCIENCE_BOUND_DOWNSTREAM_EXECUTION_PENDING",
                "scientific_authority_sha256": protocol[AUTHORITY_FIELD], "scientific_content_sha256": science["content_sha256"],
                "execution_scope": PRETRAINING_SCOPE, "downstream_execution_ready": False,
                "actual_downstream_label_masks_verified": False, "downstream_analysis_rules_sha256": _canonical(rules),
                "actual_execution_config_sha256": _canonical(config), "actual_readout_config_sha256": _canonical(readout),
                "cpu_memory_scope": "frozen sbatch request only; no actual RSS/cgroup-limit proof",
                "host_resource_projection_override": {"policy": _optional(protocol, "compute.resource_policy"),
                    "fields": resource_overrides, "changes_scientific_model_or_data": False,
                    "actual_allocation_verified": False},
                "scope": "frozen rules and pretraining projection only; no downstream cell hashes, scores, chemistry or GPU proof"}
    except ScientificAuthorityError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as error:
        raise ScientificAuthorityError("Incomplete or malformed frozen scientific authority/projection") from error
