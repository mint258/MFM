"""Synthetic metadata scope tests; no actual labels or live GPU assertions."""
from copy import deepcopy
from datetime import timedelta
import hashlib
import json
from pathlib import Path
import random

import pytest

from phychem_mfm.phase1 import formal_gate as gate
from phychem_mfm.phase1 import pretraining_scientific_authority as authority
from phychem_mfm.phase1 import trial_source_bridge
from phychem_mfm.phase1.paired_statistics import validate_analysis_plan
from test_phase1_formal_gate import case as legacy_case, NOW, _mock_live, _observation


def put(root, name, value):
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    path = root / name
    path.write_bytes(raw)
    return {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def seal(state):
    science = state["science"]
    science["content_sha256"] = authority._canonical({key: value for key, value in science.items() if key != "content_sha256"})
    ref = put(state["root"], "scientific-authority.json", science)
    protocol, artifacts = state["case"]["protocol"], state["case"]["artifacts"]
    protocol[authority.AUTHORITY_FIELD] = ref["sha256"]
    protocol["downstream"]["final_evaluation_config_sha256"] = ref["sha256"]
    artifacts[authority.AUTHORITY_FIELD] = Path(ref["path"])
    artifacts["downstream.final_evaluation_config_sha256"] = Path(ref["path"])
    protocol["content_sha256"] = gate.canonical_sha256(protocol, omit_content_hash=True)


@pytest.fixture
def prepared(tmp_path):
    case = legacy_case.__wrapped__(tmp_path)
    protocol, artifacts = case["protocol"], case["artifacts"]
    protocol["execution_scope"] = "pretraining_only"
    protocol["downstream"]["execution_bindings_state"] = "PENDING"
    protocol["downstream"]["statistics"]["analysis_plan_sha256"] = None
    artifacts.pop(authority.ANALYSIS_FIELD)
    metadata = put(tmp_path, "synthetic-static-contract.json", {"synthetic_metadata_only": True})
    refs = {}
    for field, name in (("data.source_manifest_sha256", "train_manifest"),
                        ("data.decontamination_sha256", "decontamination"),
                        ("data.normalization_sha256", "fitted_controls"),
                        ("data.normalization_train_ids_sha256", "normalization_fit_ids"),
                        ("encoder.architecture_sha256", "architecture"),
                        ("tasks.target_manifest_sha256", "targets"),
                        ("tasks.label_contract_sha256", "labels"), ("strategy.loss_policy_sha256", "loss_policy")):
        parts, cursor = field.split("."), protocol
        for part in parts[:-1]:
            cursor = cursor[part]
        cursor[parts[-1]] = metadata["sha256"]
        artifacts[field] = Path(metadata["path"])
        refs[name] = metadata
    validation_ref = put(tmp_path, "synthetic-validation-manifest.json", {"synthetic_metadata_only": True, "role": "validation"})
    split_ref = put(tmp_path, "synthetic-pretraining-split.json", {"schema_version": "phase1_split_v1",
                    "train": {"synthetic_metadata_only": True},
                    "validation": {"synthetic_metadata_only": True, "role": "validation"}})
    protocol["data"]["split_manifest_sha256"] = split_ref["sha256"]
    artifacts["data.split_manifest_sha256"] = Path(split_ref["path"])
    protocol["trial_evidence"]["data_sha256"] = metadata["sha256"]
    execution = {"schema_version": "phase1_execution_v1", "world_size": 1, "strategy": "direct_joint",
                 "config": {"training": {"base_molecules_per_batch": 2},
                            "schedule": {"max_steps": 1000, "warmup_steps": 10, "min_lr_ratio": 0.05},
                            "phase1": {"max_atoms_per_molecule": 224, "max_atoms_per_batch": 1344}},
                 "evaluation": {"every_updates": 100}}
    execution_ref = put(tmp_path, "execution.json", execution)
    readout_ref = put(tmp_path, "readout.json", {"synthetic_readout_rules": {"main": "MLP", "complement": "linear"}})
    for field, ref in (("strategy.schedule_sha256", execution_ref), ("downstream.readout_config_sha256", readout_ref)):
        section, key = field.split(".")
        protocol[section][key] = ref["sha256"]
        artifacts[field] = Path(ref["path"])
    protocol["pretraining"]["budget"]["structures_per_condition"] = 2000
    protocol["pretraining"]["checkpoint_rule"]["selection_split"] = "fixed_budget"
    protocol["pretraining"]["checkpoint_rule"]["selection_metric"] = "fixed_budget_endpoint"
    protocol["downstream"]["readouts"] = ["SourceAlignedH0Readout", "SourceAlignedLinearGraphReadout"]
    protocol["downstream"]["modes"] = ["frozen"]
    protocol["tracking"]["mode"] = "offline_persistent"
    protocol["tracking"]["sync_method"] = "Retain synthetic offline records, later wandb sync"
    protocol["tracking"]["offline_retention"] = "Retain until verified sync or reliable archive"
    protocol["compute"].update({"allowed_nodes": ["compute-0-20", "compute-0-21", "compute-0-22"],
        "requested_cpu_memory_gib": 12, "precision": "FP32",
        "paired_device_rule": "Same GPU model and environment for every condition of a seed",
        "runtime_environment": {"model": "NVIDIA A100", "python": "/synthetic/python",
                                "torch": "synthetic-torch", "cuda": "synthetic-cuda"}})
    recipe = put(tmp_path, "recipe.json", {"synthetic_recipe": True})
    protocol["strategy"]["contrasts"] = {"sdp_emphasis": {"variant": "SDP", "seeds": [0, 1], "recipe_sha256": recipe["sha256"]}}
    artifacts["strategy.contrasts.sdp_emphasis.recipe_sha256"] = Path(recipe["path"])
    primary = "sdp_vs_none"
    rules = {"schema_version": "phase1_scientific_analysis_rules_v1", "actual_hash_binding_rule": "derive only missing-mask/member hashes",
             "independent_unit": "pretraining_seed", "method": "paired_seed_contrast_sign_flip_bootstrap_v1",
             "confidence_level": 0.95, "multiple_comparison_rule": "Holm",
             "endpoints": {"toy.mae": {"dataset": protocol["downstream"]["datasets"][0], "metric": "MAE", "units": "toy",
                 "direction": "lower", "mode": "frozen", "readout_config_sha256": readout_ref["sha256"],
                 "cells": [{"fold_id": "0", "readout_seed": 0, "weight": 1.0}]}},
             "comparisons": [{"id": primary, "endpoint": "toy.mae", "coefficients": {"SDP": 1.0, "none": -1.0}, "pretraining_seeds": [0, 1]}],
             "families": {"main": [primary]}, "primary_families": ["main"]}
    choices = {"optimizer_updates_per_trained_condition": 1000, "base_structure_exposures_per_trained_condition": 2000,
               "budget_equivalence_rule": protocol["pretraining"]["budget"]["equivalence_rule"], "base_molecules_per_update": 2,
               "max_atoms_per_molecule": 224, "max_atoms_per_batch": 1344,
               "schedule": {"warmup_steps": 10, "minimum_lr_ratio": 0.05}, "validation_rule": {"every_updates": 100},
               "checkpoint_rule": {"scientific_selection": "fixed_budget_endpoint", "save_every_updates": 100, "keep_rolling_checkpoints": 2},
               "numerical_and_device_pairing": {"precision": "FP32",
                   "paired_device_rule": protocol["compute"]["paired_device_rule"],
                   "supported_environments": [deepcopy(protocol["compute"]["runtime_environment"])]}}
    science = {"schema_version": "phase1_scientific_protocol_v1", "state": "frozen", "scientific_choices_complete": True,
               "frozen_at": (NOW - timedelta(hours=1)).isoformat(),
               "source": {"producer_commit": protocol["source"]["commit"],
                          "producer_source_sha256": protocol["trial_evidence"]["source_sha256"]},
               "data": {**{name: refs[name] for name in ("train_manifest", "decontamination", "fitted_controls", "normalization_fit_ids")},
                        "validation_manifest": validation_ref},
               "encoder": {"architecture": refs["architecture"], "paired_random_initialization_by_seed": {
                   seed: {"path": "synthetic-init-reference", "bytes": 1, "sha256": digest}
                   for seed, digest in protocol["pretraining"]["paired_random_initialization"]["encoder_sha256_by_seed"].items()}},
               "tasks": {"targets": refs["targets"], "labels": refs["labels"]},
               "pretraining": {"actual_execution_artifact": execution_ref, "loss_policy": refs["loss_policy"],
                              "variants": protocol["pretraining"]["variants"], "seeds": [0, 1], "choices": choices},
               "strategy": {"main": "direct_joint_from_step_zero", "auxiliary": {"id": "sdp_emphasis", "variant": "SDP", "seeds": [0, 1], "recipe": recipe}},
               "experiment": deepcopy(protocol["experiment"]),
               "downstream": {"actual_readout_configs": readout_ref, "readout_seeds": [0, 1],
                   "dataset_definitions": [{"dataset_id": protocol["downstream"]["datasets"][0], "tasks": [{"task_id": "toy"}]}],
                   "readout_policy": {"main_class": "SourceAlignedH0Readout", "complement_class": "SourceAlignedLinearGraphReadout", "main_encoder_mode": "frozen"},
                   "analysis_rules": rules, "metric_policy": {"primary_inference_endpoints": 1, "all_output_tasks_reported": 1},
                   "optimization_policy": {"fixed": True}, "split_policy": {"fixed": True}, "geometry_and_mapping_policy": {"fixed": True},
                   "descriptive_rules": {"fixed": True}, "statistics_limitations": "synthetic metadata only",
                   "maximum_training_trials": {"maximum_readout_training_runs": 10}},
               "resources": {"compute": {"maximum_gpu_hours_per_pretraining_job": 0.5, "maximum_wall_hours_per_pretraining_job": 2.0,
                   "maximum_overall_gpu_hours_total": 20.0, "max_concurrent_jobs": 2, "gpus_per_job": 1, "cpus_per_task": 4,
                   "partition": "gpu", "maximum_downstream_gpu_hours_total": 5.0,
                   "allowed_nodes": protocol["compute"]["allowed_nodes"], "requested_cpu_memory_gib": 12,
                   "min_gpu_memory_gib": 40.0, "min_free_gpu_memory_gib": 32.0},
                   "storage": {"max_pretraining_run_gib": 10, "max_total_artifacts_gib": 60, "reserve_gib": 20}},
               "tracking": {"provider": "wandb", "mode": "offline_persistent"}}
    # Runtime names differ from scientific authority names, but meanings must match.
    science["experiment"] = {"questions": protocol["experiment"]["questions"],
                              "primary_comparisons": protocol["experiment"]["main_comparisons"]}
    state = {"case": case, "science": science, "root": tmp_path}
    seal(state)
    return state


def review(prepared):
    return gate.check_formal_gate(**prepared["case"])


def codes(report):
    return {issue.code for issue in report.issues}


def test_pending_pretraining_uses_actual_complete_science_not_fake_cell_hashes(prepared):
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in prepared["root"].iterdir()}
    rng = random.getstate()
    report = review(prepared)
    assert not report.issues
    assert not report.may_start_formal_training  # Read-only synthetic exports cannot prove a live allocation.
    proof = authority.verify_pretraining_scientific_authority(prepared["case"]["protocol"], prepared["case"]["artifacts"], now=NOW)
    assert proof["downstream_execution_ready"] is False
    assert proof["actual_downstream_label_masks_verified"] is False
    assert authority.ANALYSIS_FIELD not in prepared["case"]["artifacts"]
    assert random.getstate() == rng
    assert {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in prepared["root"].iterdir()} == before


@pytest.mark.parametrize("scope", ["full", "downstream", "unknown", "pretraining", True])
def test_pending_never_satisfies_full_downstream_or_unknown_scope(prepared, scope):
    protocol = prepared["case"]["protocol"]
    protocol["execution_scope"] = scope
    protocol["content_sha256"] = gate.canonical_sha256(protocol, omit_content_hash=True)
    report = review(prepared)
    assert report.issues and not report.may_start_formal_training
    if scope in ("full", "downstream"):
        assert "protocol.required_hash" in codes(report)


@pytest.mark.parametrize("defect", ["fake_plan_hash", "missing_pending", "missing_authority", "authority_raw_tamper", "future_time", "bad_canonical_seal"])
def test_pending_requires_intact_actual_timestamped_science(prepared, defect):
    protocol, artifacts = prepared["case"]["protocol"], prepared["case"]["artifacts"]
    if defect == "fake_plan_hash":
        protocol["downstream"]["statistics"]["analysis_plan_sha256"] = "0" * 64
    elif defect == "missing_pending":
        protocol["downstream"].pop("execution_bindings_state")
    elif defect == "missing_authority":
        artifacts.pop(authority.AUTHORITY_FIELD)
    elif defect == "authority_raw_tamper":
        artifacts[authority.AUTHORITY_FIELD].write_bytes(b"{}")
    elif defect == "future_time":
        prepared["science"]["frozen_at"] = (NOW + timedelta(hours=1)).isoformat()
        seal(prepared)
    else:
        ref = put(prepared["root"], "scientific-authority.json", {**prepared["science"], "content_sha256": "0" * 64})
        protocol[authority.AUTHORITY_FIELD] = protocol["downstream"]["final_evaluation_config_sha256"] = ref["sha256"]
    protocol["content_sha256"] = gate.canonical_sha256(protocol, omit_content_hash=True)
    assert review(prepared).issues


@pytest.mark.parametrize("field,value", [("pretraining.seeds", [0]), ("pretraining.variants", ["none", "SDP"]),
    ("pretraining.budget.optimizer_steps_per_condition", 1001), ("pretraining.checkpoint_rule.save_every_steps", 101),
    ("downstream.seeds", [0]), ("downstream.modes", ["finetune"]), ("downstream.readouts", ["linear"]),
    ("downstream.statistics.confidence_level", 0.9), ("downstream.main_comparisons", ["new_posthoc_comparison"]),
    ("downstream.budget.max_trials", 11), ("compute.max_walltime_hours", 3.0), ("storage.max_run_bytes", 11 << 30),
    ("compute.allowed_nodes", ["compute-0-20", "unapproved-node"]), ("compute.min_gpu_memory_gib", 1),
    ("compute.min_free_gpu_memory_gib", 1), ("compute.requested_cpu_memory_gib", 1),
    ("compute.runtime_environment", {"model": "NVIDIA A100", "python": "/other/python", "torch": "other", "cuda": "other"}),
    ("compute.precision", "AMP"), ("compute.paired_device_rule", "different hardware allowed")])
def test_resealed_runtime_scientific_projection_drift_is_rejected(prepared, field, value):
    protocol = prepared["case"]["protocol"]
    cursor, parts = protocol, field.split(".")
    for part in parts[:-1]:
        cursor = cursor[part]
    cursor[parts[-1]] = value
    protocol["content_sha256"] = gate.canonical_sha256(protocol, omit_content_hash=True)
    assert "artifact.scientific_authority" in codes(review(prepared))


@pytest.mark.parametrize("field", ["strategy.schedule_sha256", "downstream.readout_config_sha256", "tasks.label_contract_sha256"])
def test_actual_artifact_byte_drift_is_rejected(prepared, field):
    prepared["case"]["artifacts"][field].write_bytes(b'{"changed":true}\n')
    assert "artifact.hash_mismatch" in codes(review(prepared))


def test_complete_downstream_rule_authority_cannot_be_replaced_by_partial_plan(prepared):
    prepared["science"]["downstream"].pop("geometry_and_mapping_policy")
    seal(prepared)
    assert "artifact.scientific_authority" in codes(review(prepared))


def test_pending_scope_does_not_skip_live_gpu_configuration_or_wandb(prepared):
    prepared["case"]["slurm_config_text"] = "GresTypes=(null)\nTaskPlugin=task/affinity\n"
    report = review(prepared)
    assert {"slurm.no_gpu_gres", "slurm.no_task_cgroup"} <= codes(report)
    assert not report.may_start_formal_training
    protocol = prepared["case"]["protocol"]
    protocol["tracking"]["mode"] = "disabled"
    protocol["content_sha256"] = gate.canonical_sha256(protocol, omit_content_hash=True)
    assert "artifact.scientific_authority" in codes(review(prepared))


def test_pending_protocol_cannot_be_used_by_existing_paired_statistics(prepared):
    with pytest.raises(ValueError):
        validate_analysis_plan({}, prepared["case"]["protocol"])


@pytest.mark.parametrize("defect", [None, "node", "python", "torch", "cuda", "dtype", "cpus"])
def test_pretraining_live_scope_preserves_frozen_node_and_environment(prepared, monkeypatch, defect):
    observation = _observation()
    observation["runtime_environment"] = {"python": "/synthetic/python", "torch": "synthetic-torch",
                                          "cuda": "synthetic-cuda", "default_dtype": "torch.float32"}
    _mock_live(monkeypatch, observation)
    if defect == "node":
        observation["hostname"] = "unapproved-node"
    elif defect == "dtype":
        observation["runtime_environment"]["default_dtype"] = "torch.float64"
    elif defect == "cpus":
        prepared["case"]["slurm_job_text"] = prepared["case"]["slurm_job_text"].replace("cpu=4", "cpu=1")
    elif defect is not None:
        observation["runtime_environment"][defect] = "different-runtime"
    report = gate.check_formal_gate(**prepared["case"], live_allocation=True)
    if defect is None:
        assert not report.issues and report.may_start_formal_training
    else:
        expected = "runtime.scientific_node" if defect == "node" else (
            "runtime.scientific_cpus" if defect == "cpus" else "runtime.scientific_environment")
        assert expected in codes(report) and not report.may_start_formal_training


def test_legacy_complete_gate_remains_unchanged(tmp_path):
    case = legacy_case.__wrapped__(tmp_path)
    report = gate.check_formal_gate(**case)
    assert not report.issues and not report.may_start_formal_training
    case["artifacts"].pop(authority.ANALYSIS_FIELD)
    assert any(authority.ANALYSIS_FIELD in issue.message for issue in gate.check_formal_gate(**case).issues)


def test_bridge_allowlist_contains_only_explicit_execution_interface_paths():
    assert trial_source_bridge.INTERFACE_PATHS == {
        "phychem_mfm/phase1/formal_gate.py", "phychem_mfm/phase1/formal_runtime.py",
        "phychem_mfm/phase1/decontamination_v2.py", "phychem_mfm/phase1/trial_source_bridge.py",
        "tests/test_phase1_runtime_compatibility.py", "tests/test_phase1_trial_source_bridge.py",
        "phychem_mfm/phase1/pretraining_scientific_authority.py", "tests/test_phase1_pretraining_scope.py",
        "tests/test_phase1_shared_gpu_policy.py", "tests/test_phase1_host_resource_policy.py"}
