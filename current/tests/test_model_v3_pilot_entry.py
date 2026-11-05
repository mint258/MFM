"""Bounded pilot entry tests; UNIT fixtures never become Data authority.

Root executes this module inside its owned CPU Slurm parent. No actual Data
release, GPU smoke, Stage5 decision or scientific acceptance is asserted here.
"""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest

from phychem_mfm.phase1 import v3_proxy_run as proxy
from phychem_mfm.phase1 import v3_pilot_smoke as pilot
from phychem_mfm.phase1.v3_sample_budget_events import binding, read_bound, write_once, verify_checkpoint_record
from phychem_mfm.phase1.v3_sample_budget_experiment import SegmentPause

BASE = "3ab3c3d403c80648e632edd53e43a85b6de97145"


def _metadata(tmp_path, **kwargs):
    reference = proxy.engineering_request(tmp_path/"metadata", code_sha=BASE, **kwargs)
    request = read_bound(reference)
    return reference, request, read_bound(request["configuration"])


def _pilot_metadata(tmp_path):
    """Bound Model metadata only. It does NOT manufacture a Data release."""
    _, request, configuration = _metadata(tmp_path)
    request["mode"], request["scope"] = pilot.PILOT_MODE, pilot.PILOT_SCOPE
    request.pop("panel_binding")
    configuration["engineering_only"] = False
    configuration["experiment_scope"] = "AUTHORITATIVE_PILOT_SMOKE"
    configuration["model"]["backbone"]["layers"] = 6
    evidence = {key: write_once(tmp_path/(key+".json"),
        {"UNIT_MODEL_METADATA_ONLY_NOT_DATA_AUTHORITY": True, "role": key})
        for key in pilot.EVIDENCE_KEYS if key != "Model_policy_config_ACK"}
    evidence["Model_policy_config_ACK"] = deepcopy(pilot.ACK)
    configuration["pilot_smoke"] = {"schema": "model_v3_pilot_smoke_contract_v1",
        "optimizer_update_cap": 2000,
        "role_index_sha256": {"TRAIN": "1"*64, "VAL": "2"*64, "TRAIN_UNSEEN_CONFORMATION": "3"*64},
        "validation_population_bindings": deepcopy(configuration["proxy_contract"]["validation"]["population_bindings"]),
        "evidence": evidence}
    return request, configuration


def test_default_request_keeps_its_original_engineering_schema_and_no_update_limit(tmp_path):
    _, request, configuration = _metadata(tmp_path)
    assert "pilot_smoke" not in configuration and "engineering_update_cap" not in configuration
    assert request["mode"] == "synthetic_engineering" and request["scope"] == "engineering"
    actual, _, registrations = proxy.validate_request(request, input_kind="synthetic", engineering_only=True)
    assert actual == configuration and registrations == {}
    assert pilot.update_limit(request, configuration) is None


def test_same_signed_ACK_is_metadata_only_and_not_Data_release_authority():
    document = pilot.verify_model_ACK(deepcopy(pilot.ACK))
    assert document["decision"]["policy_config_accepted"] is True
    assert document["decision"]["acceptance_scope"].startswith("ONLY_THE_EXACT_POLICY")
    bad = deepcopy(pilot.ACK); bad["sha256"] = "0"*64
    with pytest.raises(ValueError, match="exact actual signed"):
        pilot.verify_model_ACK(bad)
    bad = deepcopy(document); bad["status"] = "DRAFT_NOT_SIGNED"
    with pytest.raises(ValueError, match="Actual signed"):
        pilot._ack_document(bad)
    bad = deepcopy(document); bad["signature"]["signer"] = None
    with pytest.raises(ValueError, match="Actual signed"):
        pilot._ack_document(bad)


def test_metadata_contract_registers_exact_2000_and_no_future_smoke_or_D5(tmp_path):
    request, configuration = _pilot_metadata(tmp_path)
    result = pilot.validate_pilot_configuration(request, configuration)
    assert result["optimizer_update_cap"] == 2000
    assert set(result["evidence"]) == pilot.EVIDENCE_KEYS
    assert "D5" not in result["evidence"] and "three_GPU_SDP_smoke" not in result["evidence"]
    result["optimizer_update_cap"] = 1
    assert configuration["pilot_smoke"]["optimizer_update_cap"] == 2000


@pytest.mark.parametrize("change", ("1999", "bool_cap", "missing_D4", "future_smoke",
    "wrong_reader_bytes", "missing_ACK", "draft_ACK", "wrong_population", "bf16",
    "execution", "legacy_performance", "full", "grid", "engineering_cap", "panel",
    "missing_validation_population", "wrong_validation_population"))
def test_metadata_missing_or_cross_scope_admission_is_rejected(tmp_path, change):
    request, cfg = _pilot_metadata(tmp_path)
    contract = cfg["pilot_smoke"]
    if change == "1999": contract["optimizer_update_cap"] = 1999
    elif change == "bool_cap": contract["optimizer_update_cap"] = True
    elif change == "missing_D4": del contract["evidence"]["D4"]
    elif change == "future_smoke": contract["evidence"]["three_GPU_SDP_smoke"] = contract["evidence"]["D3"]
    elif change == "wrong_reader_bytes": contract["evidence"]["reader"]["bytes"] += 1
    elif change == "missing_ACK": del contract["evidence"]["Model_policy_config_ACK"]
    elif change == "draft_ACK":
        contract["evidence"]["Model_policy_config_ACK"] = write_once(tmp_path/"draft_ack.json",
            {"status": "DRAFT_NOT_SIGNED", "decision": {"policy_config_accepted": True}})
    elif change == "wrong_population": contract["role_index_sha256"]["VAL"] = "symbol_not_resolved"
    elif change == "bf16": cfg["proxy_contract"]["precision"]["mode"] = "bf16"
    elif change == "execution": cfg["training_execution"] = {"options": {}}
    elif change == "legacy_performance": cfg["model"]["performance_execution_v1"] = {}
    elif change == "full": cfg["full_train_contract"] = {}
    elif change == "grid": cfg["grid_train_contract"] = {}
    elif change == "engineering_cap": cfg["engineering_update_cap"] = 2
    elif change == "panel": request["panel_binding"] = {"not_a_pilot_authority": True}
    elif change == "missing_validation_population": del contract["validation_population_bindings"]["VAL"]
    elif change == "wrong_validation_population": contract["validation_population_bindings"]["VAL"] = "f"*64
    with pytest.raises((ValueError, KeyError, TypeError)):
        pilot.validate_pilot_configuration(request, cfg)


@pytest.mark.parametrize("mode,scope", (("authoritative_proxy", "comparison"),
    ("authoritative_full_train", "full_convergence"), ("authoritative_grid_train", "grid_cell"),
    ("synthetic_engineering", "engineering")))
def test_pilot_contract_cannot_unlock_original_proxy_full_grid_or_engineering(tmp_path, mode, scope):
    request, cfg = _pilot_metadata(tmp_path)
    request["mode"], request["scope"] = mode, scope
    with pytest.raises(ValueError, match="nonpilot"):
        pilot.validate_pilot_configuration(request, cfg)
    request["scope"] = pilot.PILOT_SCOPE
    with pytest.raises(ValueError, match="cannot cross"):
        pilot.validate_pilot_configuration(request, cfg)



def _alias_metadata(tmp_path):
    # These are explicitly NON-authoritative metadata files. No actual-release
    # qualifier or provider is mocked, called or acquired by this join test.
    references = {key: write_once(tmp_path/(key+".json"),
        {"UNIT_MODEL_METADATA_ONLY_NOT_DATA_AUTHORITY": True, "source": key})
        for key in ("contract", "registry", "release", "statistics", "reader", "unrelated")}
    joint = write_once(tmp_path/"joint.json",
        {"UNIT_MODEL_METADATA_ONLY_NOT_DATA_AUTHORITY": True,
         "contract_reference": references["contract"], "model_ack_reference": deepcopy(pilot.ACK)})
    source_evidence = {"joint_contract": joint, "registry": references["registry"],
        "release": references["release"], "d4_statistics": references["statistics"]}
    projection = {"reader_source": references["reader"]}
    declared = {"D1": references["contract"], "D2": references["registry"], "D3": references["release"],
        "D4": references["statistics"], "Model_policy_config_ACK": deepcopy(pilot.ACK),
        "Data_release": references["release"], "reader": references["reader"]}
    return declared, source_evidence, projection, references["unrelated"]


def test_pure_metadata_alias_join_uses_original_fields_but_does_not_grant_release(tmp_path):
    declared, evidence, projection, _ = _alias_metadata(tmp_path)
    assert pilot.verify_pilot_evidence_aliases(declared, evidence, projection) is None
    assert read_bound(evidence["release"])["UNIT_MODEL_METADATA_ONLY_NOT_DATA_AUTHORITY"] is True
    assert read_bound(evidence["joint_contract"])["UNIT_MODEL_METADATA_ONLY_NOT_DATA_AUTHORITY"] is True


@pytest.mark.parametrize("key", ("D1", "D2", "D3", "D4", "Model_policy_config_ACK", "Data_release", "reader"))
def test_readable_unrelated_metadata_cannot_replace_an_actual_evidence_alias(tmp_path, key):
    declared, evidence, projection, unrelated = _alias_metadata(tmp_path)
    declared[key] = unrelated
    assert read_bound(unrelated)["UNIT_MODEL_METADATA_ONLY_NOT_DATA_AUTHORITY"] is True
    with pytest.raises(ValueError, match="do not join"):
        pilot.verify_pilot_evidence_aliases(declared, evidence, projection)


def test_pilot_mode_cannot_use_old_final_scope_or_unregistered_update_cap(tmp_path):
    request, cfg = _pilot_metadata(tmp_path)
    request["scope"] = "comparison"
    with pytest.raises(ValueError, match="cannot cross"):
        pilot.validate_pilot_configuration(request, cfg)
    _, engineering, normal = _metadata(tmp_path/"normal")
    normal["engineering_update_cap"] = 2
    engineering["mode"] = "authoritative_proxy"
    with pytest.raises(ValueError, match="synthetic-only"):
        pilot.update_limit(engineering, normal)


def test_original_UNIT_release_reverify_cannot_be_promoted_to_actual_pilot(tmp_path):
    # Real original metadata verifier, not a mocked actual Data qualification.
    from test_model_v3_data_adapter import metadata_case
    from phychem_mfm.phase1.v3_data_adapter import verify_release_binding
    unit_root = tmp_path/"unit"; unit_root.mkdir()
    evidence, request, projection, interpreter = metadata_case(unit_root)
    request["mode"] = projection["scope"] = pilot.PILOT_MODE
    projection["TRAIN_population"] = "versioned_provisional_pilot_TRAIN"
    release = verify_release_binding(request, evidence=evidence, verifier=interpreter(projection))
    assert release.is_actual_data_release is False
    release.reverify()
    model_request, cfg = _pilot_metadata(tmp_path/"model")
    with pytest.raises(ValueError, match="exact actual bounded release"):
        pilot.verify_pilot_inputs(SimpleNamespace(provider=SimpleNamespace(release=release)), model_request, cfg)
    forged = replace(release, authority_family="actual_final_release_v1")
    with pytest.raises(ValueError, match="family/projection authority"):
        forged.reverify()


def test_pinned_hook_header_without_original_verified_Data_release_is_rejected(tmp_path):
    request, cfg = _pilot_metadata(tmp_path)
    inputs = SimpleNamespace(provider=SimpleNamespace())
    with pytest.raises(ValueError, match="actual verified Data release"):
        pilot.verify_pilot_inputs(inputs, request, cfg)


@pytest.mark.parametrize("updates,paused", ((0, False), (1999, False), (2000, True)))
def test_update_cap_uses_effective_optimizer_updates_only(updates, paused):
    context = {"optimizer_updates": updates, "samples_consumed": 9000000}
    if paused:
        with pytest.raises(SegmentPause):
            pilot.check_update_limit("STEP", context, 2000)
    else:
        pilot.check_update_limit("STEP", context, 2000)
    pilot.check_update_limit("CHECKPOINT", context, 2000)


@pytest.mark.parametrize("updates", (True, -1, 2001))
def test_invalid_or_over_cap_cursor_is_not_silently_clamped(updates):
    with pytest.raises(ValueError):
        pilot.check_update_limit("STEP", {"optimizer_updates": updates}, 2000)


@pytest.mark.parametrize("cap", (True, 0, 2001))
def test_engineering_cap_is_bounded_and_never_adds_real_authority(tmp_path, cap):
    with pytest.raises(ValueError, match="synthetic-only"):
        _metadata(tmp_path, engineering_update_cap=cap)


def _run_cli(tmp_path, request_ref, *, name, endpoint, parent=None):
    assert os.environ.get("SLURM_JOB_ID"), "Root must execute under actual owned CPU Slurm"
    assert int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16
    cli = proxy.REPOSITORY/"tools/model_v3/run_proxy_experiment.py"
    output = tmp_path/name
    command = [sys.executable, str(cli), "run", "--input", "synthetic", "--engineering-only",
        "--request", request_ref["path"], "--request-sha256", request_ref["sha256"],
        "--output", str(output), "--lineage-root", str(tmp_path/"ledger"), "--lineage", "pilot-cap-engineering",
        "--segment-id", name, "--until-samples", str(endpoint)]
    if parent is not None: command += ["--resume-complete", parent["path"]]
    environment = {**os.environ, "CUDA_VISIBLE_DEVICES": "", "WANDB_MODE": "offline", "WANDB_SILENT": "true",
        "MODEL_V3_CHILD_OUTPUT_BUDGET_BYTES": str((2 << 30)-(16 << 20)-(96 << 20))}
    completed = subprocess.run(command, env=environment, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
    (tmp_path/(name+"_stdout.txt")).write_text(completed.stdout, encoding="utf-8")
    (tmp_path/(name+"_stderr.txt")).write_text(completed.stderr, encoding="utf-8")
    receipt = read_bound(binding(output/"CHILD_RECEIPT.json"))
    return completed, receipt, output


def test_original_provider_two_fresh_CLI_processes_stop_save_resume_and_finish_SDK(tmp_path):
    reference, _, _ = _metadata(tmp_path, budget=6, engineering_update_cap=2)
    first, row1, output1 = _run_cli(tmp_path, reference, name="part1", endpoint=2)
    assert first.returncode == 0, first.stdout+"\n"+first.stderr
    assert row1["outcome"]["optimizer_updates"] == 1
    limit1 = read_bound(row1["outcome"]["optimizer_update_limit_result"])
    assert limit1["status"] == "UPDATE_LIMIT_SEGMENT_PAUSED_NOT_COMPLETE"
    parent = row1["outcome"]["last_checkpoint"]
    second, row2, output2 = _run_cli(tmp_path, reference, name="part2", endpoint=6, parent=parent)
    assert second.returncode == 0, second.stdout+"\n"+second.stderr
    limit2 = read_bound(row2["outcome"]["optimizer_update_limit_result"])
    assert limit2["status"] == "ENGINEERING_UPDATE_LIMIT_COMPLETE_NOT_DATA_AUTHORITY"
    assert limit2["actual_optimizer_updates"] == 2 and limit2["samples_consumed"] == 4
    assert limit2["scientific_acceptance"] is False and limit2["actual_Data_acceptance"] is False
    assert row2["outcome"]["last_checkpoint"] == limit2["final_checkpoint"]
    _, state = verify_checkpoint_record(limit2["final_checkpoint"])
    assert state["optimizer_updates"] == 2 and state["samples_consumed"] == 4
    assert state["validation"] == limit2["validation"] and state["pending_log"] is False
    assert state["contract"]["model_configuration"]["sha256"]
    validations = [read_bound(ref) for ref in limit2["validation"]]
    assert {row["role"] for row in validations} == set(pilot.ROLES)
    assert all(row["optimizer_updates"] == 2 for row in validations)
    assert row1["native_sdk_run_id"] != row2["native_sdk_run_id"]
    for row, output in ((row1, output1), (row2, output2)):
        assert row["first_failure"] is None and row["cleanup_errors"] == []
        assert row["status"] == "CHILD_FINISHED_PENDING_ROOT_CLOSURE"
        assert len(list((output/"wandb").glob("offline-run-*/run-*.wandb"))) == 1
        history = [json.loads(line) for line in (output/"history.jsonl").read_text().splitlines()]
        assert history and all(entry["commit"] is True for entry in history)
        assert {entry["row"]["role"] for entry in history if entry["row"].get("event") == "VALIDATION"} == set(pilot.ROLES)
    # The controller rejects a changed sealed cap before restoring trainer state.
    before = binding(parent["path"])
    drift_ref, _, cfg = _metadata(tmp_path/"drift", budget=6, engineering_update_cap=3)
    assert cfg["engineering_update_cap"] == 3
    changed, rejected, _ = _run_cli(tmp_path, drift_ref, name="cap_drift", endpoint=6, parent=parent)
    assert changed.returncode != 0 and rejected["first_failure"] is not None
    assert rejected["outcome"] is None
    assert binding(parent["path"]) == before
    _, old_state = verify_checkpoint_record(parent)
    assert old_state["optimizer_updates"] == 1 and old_state["samples_consumed"] == 2


def test_early_exhausted_sample_budget_is_HOLD_after_original_safe_checkpoint_and_SDK_finish(tmp_path):
    reference, _, _ = _metadata(tmp_path, budget=1, engineering_update_cap=2)
    completed, receipt, output = _run_cli(tmp_path, reference, name="early", endpoint=1)
    assert completed.returncode != 0
    assert "sample budget exhausted" in completed.stderr
    assert receipt["first_failure"] is not None and receipt["cleanup_errors"] == []
    assert receipt["outcome"]["optimizer_updates"] == 1
    _, state = verify_checkpoint_record(receipt["outcome"]["last_checkpoint"])
    assert state["optimizer_updates"] == 1 and state["samples_consumed"] == 1
    assert not (output/"UPDATE_LIMIT_RESULT.json").exists()
    assert len(list((output/"wandb").glob("offline-run-*/run-*.wandb"))) == 1
