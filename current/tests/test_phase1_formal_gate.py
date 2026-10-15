"""Fail-closed preflight contracts. Site/GPU observations are synthetic mocks.

Passing fixtures do not assert that the actual cluster supports GPU isolation.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os

import pytest

from phychem_mfm.phase1 import formal_gate as gate
from tools.check_phase1_formal_gate import main as cli_main


NOW = datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)
CONFIG = "GresTypes = gpu\nTaskPlugin = task/cgroup,task/affinity\nProctrackType = proctrack/cgroup\nPreemptMode = OFF\nPrologFlags = Contain\n"
NODE = "NodeName=compute-0-20 Gres=gpu:a100:2 State=MIXED CfgTRES=cpu=64,gres/gpu=2\n"
JOB = "JobId=123 UserId=zixiao(3938) JobState=RUNNING Partition=gpu Account=research NodeList=compute-0-20 AllocTRES=cpu=4,gres/gpu=1\n"
UUID_0 = "GPU-aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
UUID_1 = "GPU-bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


def _set(document, dotted, value):
    parts = dotted.split(".")
    current = document
    for part in parts[:-1]:
        current = current[part]
    current[parts[-1]] = value


def _freeze_fixture(protocol):
    protocol["content_sha256"] = gate.canonical_sha256(protocol, omit_content_hash=True)


@pytest.fixture
def case(tmp_path):
    # One small file supplies deterministic bytes for synthetic artifact hashes.
    # Real protocols require distinct named artifacts with their actual hashes.
    blob = tmp_path / "reviewed_fixture_artifact.txt"
    blob.write_text("Synthetic gate fixture; no live cluster assertion.\n", encoding="utf-8")
    digest = hashlib.sha256(blob.read_bytes()).hexdigest()
    protocol = {
        "schema_version": gate.PROTOCOL_SCHEMA, "state": "frozen", "frozen_at": (NOW - timedelta(hours=1)).isoformat(),
        "experiment": {"questions": ["Does paired S/D/P supervision improve H0?"],
                       "main_comparisons": ["SDP vs none", "D vs none"]},
        "data": {"train_source": "decontaminated training LMDB manifest", "source_manifest_sha256": digest,
                 "split_manifest_sha256": digest, "decontamination_sha256": digest, "decontamination_complete": True,
                 "normalization_sha256": digest, "normalization_fit_split": "train", "normalization_train_ids_sha256": digest},
        "source": {"commit": "a" * 40, "source_sha256": digest},
        "encoder": {"name": "shared_light", "encode_api": "SharedBackboneMFM.encode_atoms", "representation": "H0",
                    "head_profile": "phase1", "architecture_sha256": digest},
        "tasks": {"target_manifest_sha256": digest, "label_contract_sha256": digest, "charge_target": "MOPAC NET ATOMIC CHARGES",
                  "graph_target_count": 23, "node_target_count": 6, "bond_order_only": True},
        "strategy": {"name": "joint", "loss_policy_sha256": digest, "schedule_sha256": digest,
                     "all_enabled_tasks_positive_at_step_zero": True},
        "pretraining": {"variants": list(gate.VARIANTS), "seeds": [0, 1],
                        "paired_random_initialization": {"enabled": True, "initialization_source": "random",
                                                         "same_seed_per_condition": True,
                                                         "encoder_sha256_by_seed": {"0": digest, "1": digest}},
                        "budget": {"optimizer_steps_per_condition": 1000, "structures_per_condition": 8000,
                                   "gpu_hours_per_condition": 0.5,
                                   "equivalence_rule": "Match optimizer updates and base-structure exposure across seven conditions"},
                        "checkpoint_rule": {"selection_split": "pretrain_validation", "selection_metric": "fixed weighted validation loss",
                                            "save_every_steps": 100, "keep_checkpoints": 2, "export_representation": "H0"}},
        "downstream": {"datasets": ["training-source molecular-group CV"], "readouts": ["linear", "MLP"],
                       "modes": ["frozen", "finetune"], "representation": "H0", "seeds": [0, 1],
                       "split_manifest_sha256": digest, "readout_config_sha256": digest, "final_evaluation_config_sha256": digest,
                       "main_comparisons": ["sdp_vs_none"], "final_test_usage": "once_after_freeze",
                       "budget": {"max_gpu_hours_total": 5.0, "max_trials": 10},
                       "statistics": {"method": "paired_seed_contrast_sign_flip_bootstrap_v1",
                                      "primary_metric": "per_endpoint_declared", "paired": True,
                                      "confidence_level": 0.95, "multiple_comparison_rule": "Holm"}},
        "compute": {"site": "synthetic_site", "partition": "gpu", "account": "research", "gpu_model": "NVIDIA A100",
                    "non_preemptible": True, "nodes_per_job": 1, "gpus_per_job": 1, "cpus_per_task": 4,
                    "max_concurrent_jobs": 2, "max_gpu_hours_total": 20.0, "max_walltime_hours": 2.0,
                    "min_gpu_memory_gib": 40.0, "min_free_gpu_memory_gib": 32.0},
        "storage": {"quota_bytes": 4096 * 1024**3, "available_bytes": 149 * 1024**3,
                    "reserve_bytes": 20 * 1024**3, "max_run_bytes": 10 * 1024**3, "max_total_artifact_bytes": 60 * 1024**3,
                    "checkpoint_retention": "two resumable checkpoints plus final H0", "tracker_retention": "retain until verified sync"},
        "tracking": {"provider": "wandb", "mode": "online"},
        "trial_evidence": {"summary_sha256": digest, "training_log_sha256": digest, "gradient_checks_sha256": digest,
                           "tracking_sha256": digest, "final_status": "completed", "source_sha256": digest, "data_sha256": digest},
    }
    statistics_plan = {
        "schema_version": "phase1_paired_statistics_plan_v1",
        "method": "paired_seed_contrast_sign_flip_bootstrap_v1",
        "independent_unit": "pretraining_seed", "aggregation": "fixed_cell_weighted_mean_v1",
        "alternative": "two_sided", "confidence_level": 0.95, "alpha": 0.05,
        "bootstrap": {"resamples": 1000, "rng_seed": 17, "quantile_method": "linear"},
        "sign_flip": {"exact_max_seeds": 16, "monte_carlo_resamples": 999, "rng_seed": 23},
        "multiple_comparison_rule": "Holm",
        "endpoints": {"synthetic.mae": {
            "dataset": "training-source molecular-group CV", "metric": "MAE", "units": "synthetic",
            "direction": "lower", "mode": "frozen", "readout_config_sha256": digest,
            "split_manifest_sha256": digest,
            "cells": [{"fold_id": "fold0", "readout_seed": seed, "weight": 0.5,
                       "sample_set_sha256": digest, "label_mask_sha256": digest} for seed in (0, 1)]}},
        "comparisons": [{"id": "sdp_vs_none", "endpoint": "synthetic.mae",
                         "coefficients": {"SDP": 1.0, "none": -1.0}, "pretraining_seeds": [0, 1]}],
        "families": {"primary": ["sdp_vs_none"]}, "primary_families": ["primary"],
    }
    statistics_file = tmp_path / "analysis-plan.json"
    statistics_file.write_text(json.dumps(statistics_plan, sort_keys=True) + "\n", encoding="utf-8")
    protocol["downstream"]["statistics"]["analysis_plan_sha256"] = hashlib.sha256(statistics_file.read_bytes()).hexdigest()
    _freeze_fixture(protocol)
    standard_configuration = {
        "gres": "Name=gpu Type=a100 File=/dev/nvidia[4-5]\n",
        "cgroup": "ConstrainDevices=yes\n",
        "sshd": "UsePAM yes\nKbdInteractiveAuthentication no\n",
        "pam": "account required pam_unix.so\naccount required pam_slurm_adopt.so action_adopt_failure=deny action_generic_failure=deny\n",
    }
    configuration_files = {}
    for name, text in standard_configuration.items():
        path = tmp_path / f"{name}.conf"
        path.write_text(text, encoding="utf-8")
        configuration_files[name] = path
    artifacts = {path: blob for path in gate.REQUIRED_HASH_FIELDS}
    artifacts["downstream.statistics.analysis_plan_sha256"] = statistics_file
    artifacts.update({f"pretraining.paired_random_initialization.encoder_sha256_by_seed.{seed}": blob for seed in (0, 1)})
    return {"protocol": protocol, "slurm_config_text": CONFIG, "slurm_node_text": NODE, "slurm_job_text": JOB,
            "configuration_files": configuration_files, "configuration_node": "compute-0-20",
            "artifacts": artifacts, "now": NOW}


def _observation():
    return {"captured_at": NOW.isoformat(), "hostname": "compute-0-20", "uid": 3938,
            "environment": {"SLURM_JOB_ID": "123", "SLURM_JOB_GPUS": "0", "SLURM_STEP_GPUS": "0",
                            "SLURM_GPUS_ON_NODE": "1", "CUDA_VISIBLE_DEVICES": "0", "CUDA_DEVICE_ORDER": "PCI_BUS_ID"},
            "cgroup": "0::/slurm/uid_3938/job_123/step_batch\n",
            "gpu_inventory": [{"index": 0, "device_minor": 4, "uuid": UUID_0, "name": "NVIDIA A100",
                               "memory_total_mib": 81920.0, "memory_free_mib": 70000.0}],
            "kernel_devices": [{"uuid": UUID_0, "device_minor": 4, "pci_bus_id": "0000:03:00.0"},
                               {"uuid": UUID_1, "device_minor": 5, "pci_bus_id": "0000:04:00.0"}],
            "cuda_devices": [{"cuda_index": 0, "uuid": UUID_0}],
            "gpu_device_access": {"4": True, "5": False}}


def _mock_live(monkeypatch, observation=None):
    # Synthetic files are not live /etc files. Only these unit tests bypass the
    # real-path check; production callers have no JSON/runtime override API.
    monkeypatch.setattr(gate, "_live_configuration_paths", lambda files, config: [])
    monkeypatch.setattr(gate, "_capture_local_observation", lambda: observation or _observation())


def _codes(report):
    return {issue.code for issue in report.issues}


@pytest.mark.parametrize("defect", ("unknown_method", "partial_family", "undeclared_readout_seed", "duplicate_cell"))
def test_statistics_artifact_hash_alone_cannot_replace_an_executable_complete_plan(case, defect):
    field = "downstream.statistics.analysis_plan_sha256"
    path = case["artifacts"][field]
    plan = json.loads(path.read_text(encoding="utf-8"))
    if defect == "unknown_method":
        plan["method"] = "choose_after_viewing_results"
    elif defect == "partial_family":
        plan["families"]["primary"] = []
    elif defect == "undeclared_readout_seed":
        plan["endpoints"]["synthetic.mae"]["cells"][0]["readout_seed"] = 99
    else:
        plan["endpoints"]["synthetic.mae"]["cells"].append(dict(plan["endpoints"]["synthetic.mae"]["cells"][0]))
    path.write_text(json.dumps(plan, sort_keys=True) + "\n", encoding="utf-8")
    _set(case["protocol"], field, hashlib.sha256(path.read_bytes()).hexdigest())
    _freeze_fixture(case["protocol"])
    report = gate.check_formal_gate(**case)
    assert field in report.reviewed_artifacts
    assert report.status == "BLOCKED" and not report.may_start_formal_training
    assert "artifact.statistics_plan" in _codes(report)


@pytest.mark.parametrize("raw", ('{"schema_version":"first","schema_version":"second"}', '{"alpha":NaN}'))
def test_statistics_plan_rejects_ambiguous_json_even_when_actual_bytes_match_protocol(case, raw):
    field = "downstream.statistics.analysis_plan_sha256"
    path = case["artifacts"][field]
    path.write_text(raw, encoding="utf-8")
    _set(case["protocol"], field, hashlib.sha256(path.read_bytes()).hexdigest())
    _freeze_fixture(case["protocol"])
    report = gate.check_formal_gate(**case)
    assert "artifact.statistics_plan" in _codes(report)
    assert not report.may_start_formal_training


def test_formal_preflight_requires_actual_statistics_plan_artifact(case):
    case["artifacts"].pop("downstream.statistics.analysis_plan_sha256")
    report = gate.check_formal_gate(**case)
    assert report.status == "BLOCKED" and not report.may_start_formal_training
    assert any("downstream.statistics.analysis_plan_sha256" in issue.message for issue in report.issues)


def _one_strategy_contrast(case):
    digest = case["protocol"]["strategy"]["schedule_sha256"]
    case["protocol"]["strategy"]["contrasts"] = {
        "s-first": {"variant": "SDP", "seeds": [0], "recipe_sha256": digest}}
    case["artifacts"]["strategy.contrasts.s-first.recipe_sha256"] = case["artifacts"]["strategy.schedule_sha256"]
    _freeze_fixture(case["protocol"])


def test_strategy_comparison_adds_real_artifact_without_changing_main_matrix(case):
    _one_strategy_contrast(case)
    report = gate.check_formal_gate(**case)
    assert report.status == "REVIEW_ONLY" and report.issues == []
    assert "strategy.contrasts.s-first.recipe_sha256" in report.reviewed_artifacts
    assert case["protocol"]["pretraining"]["variants"] == list(gate.VARIANTS)
    assert not report.may_start_formal_training


@pytest.mark.parametrize("defect", ("missing", "changed"))
def test_strategy_recipe_requires_actual_hash_bound_bytes(case, tmp_path, defect):
    _one_strategy_contrast(case)
    field = "strategy.contrasts.s-first.recipe_sha256"
    if defect == "missing":
        case["artifacts"].pop(field)
    else:
        changed = tmp_path / "changed-recipe.json"
        changed.write_text('{"changed_stage_boundary": true}', encoding="utf-8")
        case["artifacts"][field] = changed
    report = gate.check_formal_gate(**case)
    assert report.status == "BLOCKED" and not report.may_start_formal_training
    assert any(field in issue.message for issue in report.issues)


def test_strategy_comparison_cannot_reuse_the_main_matrix_compute_cap(case):
    _one_strategy_contrast(case)
    # 7 conditions * 2 independent seeds * 0.5h + 5h downstream = 12h.
    # An additional paired comparison adds 0.5h; it cannot fit that old cap.
    case["protocol"]["compute"]["max_gpu_hours_total"] = 12.0
    _freeze_fixture(case["protocol"])
    assert "protocol.matrix_compute_budget" in _codes(gate.check_formal_gate(**case))
    case["protocol"]["compute"]["max_gpu_hours_total"] = 12.5
    _freeze_fixture(case["protocol"])
    assert gate.check_formal_gate(**case).issues == []


def test_invalid_strategy_comparison_never_passes_partial_scope(case):
    _one_strategy_contrast(case)
    case["protocol"]["strategy"]["contrasts"]["s-first"]["seeds"] = [2]
    _freeze_fixture(case["protocol"])
    report = gate.check_formal_gate(**case)
    assert report.status == "BLOCKED" and "protocol.strategy_contrasts" in _codes(report)


def test_complete_exports_are_review_only_and_do_not_observe_hardware(case, monkeypatch):
    monkeypatch.setattr(gate, "_capture_local_observation", lambda: pytest.fail("Offline review must not probe devices"))
    report = gate.check_formal_gate(**case)
    assert report.status == "REVIEW_ONLY" and report.issues == []
    assert not report.may_start_formal_training and report.runtime_observation is None


@pytest.mark.parametrize("live", (False, True))
def test_persistent_offline_records_need_sync_plan_not_prior_sync_artifact(case, monkeypatch, live):
    protocol = case["protocol"]
    protocol["tracking"].update(mode="offline_persistent", sync_method="Run wandb sync on the retained offline directory when reachable")
    protocol["storage"]["tracker_retention"] = "Keep offline run files until synchronization or reliable archival is confirmed"
    _freeze_fixture(protocol)
    assert "sync_evidence_sha256" not in protocol["tracking"]
    assert "tracking.sync_evidence_sha256" not in case["artifacts"]
    if live:
        _mock_live(monkeypatch)
    else:
        monkeypatch.setattr(gate, "_capture_local_observation", lambda: pytest.fail("Read-only review cannot probe hardware"))
    report = gate.check_formal_gate(**case, live_allocation=live)
    assert report.issues == []
    assert report.status == ("PASS_LIVE_ALLOCATION" if live else "REVIEW_ONLY")
    assert report.may_start_formal_training is live
    assert "tracking.sync_evidence_sha256" not in report.reviewed_artifacts


@pytest.mark.parametrize("field,code", (("tracking.sync_method", "protocol.tracking_sync_method"),
                                       ("storage.tracker_retention", "protocol.tracking_retention")))
@pytest.mark.parametrize("invalid", (None, "", " ", False))
def test_persistent_offline_records_require_concrete_sync_and_retention_plans(case, field, code, invalid):
    case["protocol"]["tracking"].update(mode="offline_persistent", sync_method="Retain and sync the actual offline run directory")
    case["protocol"]["storage"]["tracker_retention"] = "Retain offline records until synchronized or reliably archived"
    _set(case["protocol"], field, invalid)
    _freeze_fixture(case["protocol"])
    report = gate.check_formal_gate(**case)
    assert report.status == "BLOCKED" and not report.may_start_formal_training
    assert code in _codes(report)


def test_disabled_tracking_is_still_rejected_with_offline_retention_plan(case):
    case["protocol"]["tracking"].update(mode="disabled", sync_method="Sync retained records")
    case["protocol"]["storage"]["tracker_retention"] = "Retain records"
    _freeze_fixture(case["protocol"])
    report = gate.check_formal_gate(**case)
    assert report.status == "BLOCKED" and "protocol.tracking" in _codes(report)


@pytest.mark.parametrize("artifact_present", (False, True))
def test_legacy_verified_offline_mode_still_verifies_its_declared_sync_artifact(case, artifact_present):
    protocol = case["protocol"]
    protocol["tracking"].update(mode="offline_with_verified_sync", sync_evidence_sha256=protocol["trial_evidence"]["tracking_sha256"])
    if artifact_present:
        case["artifacts"]["tracking.sync_evidence_sha256"] = case["artifacts"]["trial_evidence.tracking_sha256"]
    _freeze_fixture(protocol)
    report = gate.check_formal_gate(**case)
    if artifact_present:
        assert report.status == "REVIEW_ONLY" and report.issues == []
        assert "tracking.sync_evidence_sha256" in report.reviewed_artifacts
    else:
        assert report.status == "BLOCKED" and "artifact.unverified" in _codes(report)


def test_legacy_verified_offline_mode_requires_the_evidence_hash_it_declares(case):
    case["protocol"]["tracking"]["mode"] = "offline_with_verified_sync"
    _freeze_fixture(case["protocol"])
    report = gate.check_formal_gate(**case)
    assert report.status == "BLOCKED" and "protocol.tracking_sync" in _codes(report)


@pytest.mark.parametrize("cvd", ("0", UUID_0))
def test_mocked_live_allocation_preserves_numeric_or_uuid_scheduler_cvd(case, monkeypatch, cvd):
    observation = _observation()
    observation["environment"]["CUDA_VISIBLE_DEVICES"] = cvd
    _mock_live(monkeypatch, observation)
    report = gate.check_formal_gate(**case, live_allocation=True)
    assert report.status == "PASS_LIVE_ALLOCATION" and report.issues == []
    assert report.may_start_formal_training
    assert report.runtime_observation["gpu_inventory"][0]["device_minor"] == 4


def test_numeric_cvd_zero_can_legitimately_map_to_second_physical_gpu(case, monkeypatch):
    observation = _observation()
    observation["environment"].update(SLURM_JOB_GPUS="1", SLURM_STEP_GPUS="1", CUDA_VISIBLE_DEVICES="0")
    observation["cuda_devices"][0]["uuid"] = UUID_1
    observation["gpu_inventory"][0].update(index=1, device_minor=5, uuid=UUID_1)
    observation["gpu_device_access"] = {"4": False, "5": True}
    _mock_live(monkeypatch, observation)
    report = gate.check_formal_gate(**case, live_allocation=True)
    assert report.may_start_formal_training and report.issues == []


def test_config_snapshots_have_no_artificial_fifteen_minute_approval_expiry(case):
    for path in case["configuration_files"].values():
        os.utime(path, (946684800, 946684800))  # Year 2000 mtime does not grant or revoke resources.
    report = gate.check_formal_gate(**case)
    assert report.status == "REVIEW_ONLY" and report.issues == []
    assert any(key.startswith("site_config/") for key in report.reviewed_artifacts)


def test_copied_configs_cannot_substitute_for_actual_local_files_in_live_mode(case, monkeypatch):
    monkeypatch.setattr(gate, "_capture_local_observation", lambda: pytest.fail("Copied files must not trigger live probe"))
    report = gate.check_formal_gate(**case, live_allocation=True)
    assert "runtime.configuration_source" in _codes(report) and not report.may_start_formal_training


def test_standard_pam_include_chain_is_read_and_hashed(case):
    pam = case["configuration_files"]["pam"]
    included = pam.parent / "common-account"
    included.write_text("account required pam_unix.so\n", encoding="utf-8")
    pam.write_text("account include common-account\naccount required pam_slurm_adopt.so action_adopt_failure=deny action_generic_failure=deny\n", encoding="utf-8")
    report = gate.check_formal_gate(**case)
    assert report.status == "REVIEW_ONLY" and any("common-account" in key for key in report.reviewed_artifacts)


def test_json_true_cannot_replace_actual_standard_device_config(case):
    case["configuration_files"]["cgroup"].write_text('{"gpu_isolation_verified": true}', encoding="utf-8")
    report = gate.check_formal_gate(**case)
    assert "site_config.devices" in _codes(report) and not report.may_start_formal_training


def test_standard_autodetect_nvml_is_verified_from_actual_pci_kernel_mapping(case, monkeypatch):
    case["configuration_files"]["gres"].write_text("AutoDetect=nvml\n", encoding="utf-8")
    _mock_live(monkeypatch)
    report = gate.check_formal_gate(**case, live_allocation=True)
    assert report.may_start_formal_training and report.issues == []


@pytest.mark.parametrize("path,value,code", [
    ("state", "draft", "protocol.not_frozen"),
    ("frozen_at", "2026-10-01T09:00:00", "protocol.not_frozen"),
    ("frozen_at", "2030-01-01T09:00:00+00:00", "protocol.not_frozen"),
    ("experiment.questions", [], "protocol.required_list"),
    ("data.decontamination_complete", False, "protocol.semantic"),
    ("data.normalization_fit_split", "full_dataset", "protocol.semantic"),
    ("strategy.all_enabled_tasks_positive_at_step_zero", False, "protocol.semantic"),
    ("pretraining.paired_random_initialization.initialization_source", "historical_pretrained", "protocol.semantic"),
    ("pretraining.paired_random_initialization.same_seed_per_condition", False, "protocol.semantic"),
    ("pretraining.paired_random_initialization.pretrained_checkpoint", "runs/old/best.pt", "protocol.pretrained_initialization"),
    ("pretraining.budget.structures_per_condition", None, "protocol.required_budget"),
    ("pretraining.budget.gpu_hours_per_condition", 0, "protocol.required_budget"),
    ("pretraining.budget.optimizer_steps_per_condition", 2.5, "protocol.integer_budget"),
    ("pretraining.checkpoint_rule.selection_split", "final_test", "protocol.checkpoint_selection"),
    ("downstream.statistics.method", "", "protocol.required_text"),
    ("compute.max_gpu_hours_total", 1.0, "protocol.matrix_compute_budget"),
    ("compute.nodes_per_job", 2, "protocol.unsupported_multinode"),
    ("storage.max_total_artifact_bytes", 145 * 1024**3, "protocol.storage_budget"),
    ("trial_evidence.source_sha256", "b" * 64, "protocol.trial_source"),
    ("tracking.mode", "disabled", "protocol.tracking"),
])
def test_incomplete_or_conflicting_protocols_fail_closed(case, monkeypatch, path, value, code):
    _set(case["protocol"], path, value)
    _freeze_fixture(case["protocol"])
    monkeypatch.setattr(gate, "_capture_local_observation", lambda: pytest.fail("Blocked protocol must not probe hardware"))
    report = gate.check_formal_gate(**case, live_allocation=True)
    assert report.status == "BLOCKED" and not report.may_start_formal_training
    assert code in _codes(report)


def test_post_freeze_changes_and_missing_paired_seed_artifacts_are_detected(case):
    case["protocol"]["pretraining"]["seeds"].append(2)
    report = gate.check_formal_gate(**case)
    assert {"protocol.content_hash", "protocol.paired_initialization"} <= _codes(report)


@pytest.mark.parametrize("config,node,code", [
    (CONFIG.replace("GresTypes = gpu", "GresTypes = (null)"), NODE, "slurm.no_gpu_gres"),
    (CONFIG.replace("task/cgroup,task/affinity", "task/affinity"), NODE, "slurm.no_task_cgroup"),
    (CONFIG.replace("proctrack/cgroup", "proctrack/linuxproc"), NODE, "slurm.no_process_cgroup"),
    (CONFIG.replace("PreemptMode = OFF", "PreemptMode = REQUEUE"), NODE, "slurm.preemption_unknown"),
    (CONFIG, NODE.replace("Gres=gpu:a100:2", "Gres=(null)"), "slurm.node_gres"),
])
def test_current_known_cluster_failures_cannot_be_overridden_by_true_flags(case, config, node, code):
    case["slurm_config_text"], case["slurm_node_text"] = config, node
    case["protocol"]["gpu_isolation_verified"] = True
    case["protocol"]["ssh_isolation_verified"] = True
    _freeze_fixture(case["protocol"])
    report = gate.check_formal_gate(**case)
    assert report.status == "BLOCKED" and code in _codes(report)


@pytest.mark.parametrize("failure,code", [
    ("wrong_node", "site_config.node"), ("missing_config", "site_config.unverified"),
    ("devices_not_enforced", "site_config.devices"), ("unsafe_ssh", "site_config.ssh_adoption"),
    ("adopt_failure_allows", "site_config.ssh_failure"), ("missing_binding", "site_config.gres_mapping"),
    ("artifact_changed", "artifact.hash_mismatch"),
])
def test_standard_configuration_and_actual_artifacts_are_mandatory(case, tmp_path, failure, code):
    files = case["configuration_files"]
    if failure == "wrong_node":
        case["configuration_node"] = "compute-0-21"
    elif failure == "missing_config":
        del files["pam"]
    elif failure == "devices_not_enforced":
        files["cgroup"].write_text("ConstrainDevices=no\n", encoding="utf-8")
    elif failure == "unsafe_ssh":
        files["pam"].write_text("account required pam_permit.so\n", encoding="utf-8")
    elif failure == "adopt_failure_allows":
        files["pam"].write_text("account required pam_slurm_adopt.so action_adopt_failure=allow action_generic_failure=deny\n", encoding="utf-8")
    elif failure == "missing_binding":
        files["gres"].write_text("Name=gpu Flags=CountOnly Count=2\n", encoding="utf-8")
    else:
        changed = tmp_path / "changed_source.txt"
        changed.write_text("Changed after freeze", encoding="utf-8")
        case["artifacts"]["source.source_sha256"] = changed
    report = gate.check_formal_gate(**case)
    assert not report.may_start_formal_training and code in _codes(report)


@pytest.mark.parametrize("failure,code", [
    ("not_slurm", "runtime.job_id"), ("wrong_cgroup", "runtime.cgroup"),
    ("wrong_owner", "runtime.owner"), ("wrong_node", "runtime.node"),
    ("invalid_cvd", "runtime.cuda_devices"), ("wrong_uuid", "runtime.cuda_devices"),
    ("wrong_actual_cuda_uuid", "runtime.physical_mapping"),
    ("other_gpu_accessible", "runtime.device_access"), ("low_free_memory", "runtime.free_memory"),
    ("changed_minor", "runtime.device_binding"), ("missing_assigned_inventory", "runtime.inventory"),
    ("stale", "runtime.stale_observation"), ("wrong_allocated_count", "runtime.allocated_gres"),
])
def test_live_resource_mismatch_fails_even_with_complete_configuration(case, monkeypatch, failure, code):
    observation = _observation()
    if failure == "not_slurm":
        observation["environment"]["SLURM_JOB_ID"] = ""
    elif failure == "wrong_cgroup":
        observation["cgroup"] = "0::/user.slice/session.scope\n"
    elif failure == "wrong_owner":
        observation["uid"] = 42
    elif failure == "wrong_node":
        observation["hostname"] = "compute-0-21"
    elif failure == "invalid_cvd":
        observation["environment"]["CUDA_VISIBLE_DEVICES"] = "-1"
    elif failure == "wrong_uuid":
        observation["environment"]["CUDA_VISIBLE_DEVICES"] = UUID_1
    elif failure == "wrong_actual_cuda_uuid":
        observation["cuda_devices"][0]["uuid"] = UUID_1
    elif failure == "other_gpu_accessible":
        observation["gpu_device_access"]["5"] = True
    elif failure == "low_free_memory":
        observation["gpu_inventory"][0]["memory_free_mib"] = 1024.0
    elif failure == "changed_minor":
        observation["gpu_inventory"][0]["device_minor"] = 0
    elif failure == "missing_assigned_inventory":
        observation["gpu_inventory"] = []
    elif failure == "stale":
        observation["captured_at"] = (NOW - timedelta(minutes=1)).isoformat()
    else:
        case["slurm_job_text"] = JOB.replace("gres/gpu=1", "gres/gpu=0")
    _mock_live(monkeypatch, observation)
    report = gate.check_formal_gate(**case, live_allocation=True)
    assert report.status == "BLOCKED" and code in _codes(report)


def test_unknown_local_probe_cannot_be_replaced_with_json_true(case, monkeypatch):
    case["protocol"]["runtime_gpu_verified"] = True
    _freeze_fixture(case["protocol"])
    def fail_probe():
        raise RuntimeError("Actual local NVIDIA device inventory is unknown")
    _mock_live(monkeypatch)
    monkeypatch.setattr(gate, "_capture_local_observation", fail_probe)
    report = gate.check_formal_gate(**case, live_allocation=True)
    assert "runtime.unverified" in _codes(report) and not report.may_start_formal_training


def test_readonly_cli_never_calls_probe_or_returns_launch_success_for_export_review(case, tmp_path, capsys):
    paths = {}
    for key in ("protocol",):
        path = tmp_path / f"{key}.json"
        path.write_text(json.dumps(case[key]), encoding="utf-8")
        paths[key] = path
    for key in ("slurm_config_text", "slurm_node_text", "slurm_job_text"):
        path = tmp_path / f"{key}.txt"
        path.write_text(case[key], encoding="utf-8")
        paths[key] = path
    arguments = ["--protocol", str(paths["protocol"]), "--slurm-config", str(paths["slurm_config_text"]),
                 "--slurm-node", str(paths["slurm_node_text"]), "--slurm-job", str(paths["slurm_job_text"]),
                 "--configuration-node", case["configuration_node"]]
    flags = {"gres": "--gres-config", "cgroup": "--cgroup-config", "sshd": "--sshd-config", "pam": "--ssh-pam-config"}
    for name, path in case["configuration_files"].items():
        arguments.extend([flags[name], str(path)])
    for key, path in case["artifacts"].items():
        arguments.extend(["--artifact", f"{key}={path}"])
    before = {str(path): path.read_bytes() for path in tmp_path.iterdir()}
    # The fixture dates may be stale relative to the system clock. Either way,
    # exported-only review must never authorize formal training or mutate files.
    assert cli_main(arguments) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] in {"REVIEW_ONLY", "BLOCKED"}
    assert not report["may_start_formal_training"]
    assert before == {str(path): path.read_bytes() for path in tmp_path.iterdir()}


def test_cli_invalid_input_is_explicitly_blocked(tmp_path, capsys):
    missing = str(tmp_path / "missing_protocol.json")
    assert cli_main(["--protocol", missing, "--slurm-config", missing, "--slurm-node", missing]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "BLOCKED" and not report["may_start_formal_training"]
