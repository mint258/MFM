"""Source/UNIT wiring controls only. Never grant an actual D3 release."""
from copy import deepcopy
import pytest

from phychem_mfm.phase1 import v3_proxy_run as proxy
from phychem_mfm.phase1 import v3_pilot_smoke as pilot
from phychem_mfm.phase1 import v3_architecture_smoke as smoke
from phychem_mfm.phase1.v3_sample_budget_events import read_bound, write_once, verify_checkpoint_record
from phychem_mfm.phase1.v3_sample_budget_experiment import SegmentPause
from test_model_v3_pilot_entry import _pilot_metadata, _metadata, _run_cli


def unit_metadata(tmp_path, name):
    request, cfg = _pilot_metadata(tmp_path)
    spec = smoke.wiring_spec(name)
    request["purpose"] = smoke.PURPOSE
    cfg["seed"] = 0
    cfg["model"]["backbone"]["distance_bias_projection_bias"] = False
    cfg["model"]["backbone"]["ff_mult"] = 2  # Canonical six-layer fixture, not the one-layer UNIT default.
    cfg["model"]["backbone"].pop("v3_architecture", None)
    if spec["distance"] != "C1-0":
        cfg["model"]["backbone"]["v3_architecture"] = {"distance_bias": spec["distance"]}
    c = cfg["proxy_contract"]
    c["groups"] = {"S": ["S"], "P": ["P"], "D": ["D"], "SDP": ["S", "D", "P"]}[spec["group"]]
    c["views"] = c["validation"]["views"] = spec["views"]
    c["heads"]["forms"] = spec["head"]
    c["heads"].pop("pooling_overrides", None)
    if spec["pooling"] == "learned_mixer":
        c["heads"]["pooling_overrides"] = {"UNIT_graph_scalar": "learned"}
    cfg[smoke.PURPOSE] = smoke.wiring_contract(name)
    return request, cfg


@pytest.mark.parametrize("name", [row["name"] for row in smoke.wiring_specs()])
def test_all20_metadata_anchors_preserve_2000_pilot_and_are_never_selected(tmp_path, name):
    request, cfg = unit_metadata(tmp_path, name)
    before = deepcopy(cfg)
    assert pilot.validate_pilot_configuration(request, cfg)["optimizer_update_cap"] == 2000
    result = smoke.validate_architecture_wiring_smoke(request, cfg)
    assert result["status"] == "NOT_SELECTED_NOT_SCIENTIFIC"
    assert smoke.wiring_update_limit(request, cfg, pilot.update_limit(request, cfg)) == 50
    assert cfg == before and cfg["pilot_smoke"]["optimizer_update_cap"] == 2000
    assert result["r674"]["loss"] == "LOSS_DISABLED" and result["r674"]["retain_prediction_head"] is True


@pytest.mark.parametrize("fault", ("missing_purpose", "missing_contract", "cap51", "float50", "seed1",
                                  "bias_true", "distance", "head", "views", "optimized", "synthetic", "full"))
def test_wiring_cannot_escape_scope_or_fixed_anchor(tmp_path, fault):
    request, cfg = unit_metadata(tmp_path, "H_H2_P")
    if fault == "missing_purpose": request.pop("purpose")
    elif fault == "missing_contract": cfg.pop(smoke.PURPOSE)
    elif fault == "cap51": cfg[smoke.PURPOSE]["optimizer_update_limit"] = 51
    elif fault == "float50": cfg[smoke.PURPOSE]["optimizer_update_limit"] = 50.0
    elif fault == "seed1": cfg["seed"] = 1
    elif fault == "bias_true": cfg["model"]["backbone"]["distance_bias_projection_bias"] = True
    elif fault == "distance": cfg["model"]["backbone"]["v3_architecture"] = {"distance_bias": "C1-a"}
    elif fault == "head": cfg["proxy_contract"]["heads"]["forms"] = "H1"
    elif fault == "views": cfg["proxy_contract"]["views"] = "two"
    elif fault == "optimized": cfg["training_execution"] = {"options": {}}
    elif fault == "synthetic": request["mode"] = "synthetic_engineering"
    else: request["mode"] = "authoritative_full_train"
    with pytest.raises(ValueError): smoke.validate_architecture_wiring_smoke(request, cfg)


def test_default_paths_return_original_limits_and_result_object(tmp_path):
    _, request, cfg = _metadata(tmp_path)
    assert smoke.wiring_update_limit(request, cfg, None) is None
    row = {"unchanged": "original"}
    assert smoke.wiring_result(request, cfg, row) is row
    request, cfg = _pilot_metadata(tmp_path / "ordinary")
    assert smoke.wiring_update_limit(request, cfg, 2000) == 2000
    assert smoke.wiring_result(request, cfg, row) is row


def test_fifty_means_effective_updates_and_result_cannot_claim_2000_or_selection(tmp_path):
    request, cfg = unit_metadata(tmp_path, "C1_0_S")
    with pytest.raises(SegmentPause):
        pilot.check_update_limit("STEP", {"optimizer_updates": 50, "samples_consumed": 1}, 50)
    pilot.check_update_limit("STEP", {"optimizer_updates": 49, "samples_consumed": 999999}, 50)
    result = smoke.wiring_result(request, cfg, {"optimizer_update_cap": 50, "actual_optimizer_updates": 50})
    assert result["status"] == "ARCHITECTURE_WIRING_50_COMPLETE_NOT_SELECTION_NOT_PILOT_2000"
    assert result["pilot_2000_complete"] is False and result["architecture_selected"] is False
    assert result["scientific_acceptance"] is False
    partial = smoke.wiring_result(request, cfg, {"optimizer_update_cap": 50, "actual_optimizer_updates": 3})
    assert partial["status"] == "ARCHITECTURE_WIRING_PAUSED_NOT_COMPLETE"


def test_readable_UNIT_metadata_does_not_grant_actual_D3_or_write_a_prepared_request(tmp_path):
    request, cfg = unit_metadata(tmp_path, "C1_0_S")
    cfg.pop(smoke.PURPOSE)  # Ordinary UNIT base still has no real D3/Root authority.
    cfg_ref = write_once(tmp_path / "UNIT_config.json", cfg)
    request["configuration"] = cfg_ref
    request["purpose"] = None  # prepare requires an ordinary real pilot base.
    request_ref = write_once(tmp_path / "UNIT_request.json", request)
    with pytest.raises(ValueError):
        smoke.prepare_wiring_request(request_ref, "C1_0_S", tmp_path / "must_not_exist")
    assert not (tmp_path / "must_not_exist").exists()
    with pytest.raises(ValueError):
        proxy.validate_request(request, input_kind="authoritative_pilot")


def test_original_UNIT_provider_50_update_cap_safe_checkpoint_resume_and_SDK(tmp_path):
    # This proves only the reused stop/CP mechanism; it is NOT actual D3 or a C model run.
    _, request, cfg = _metadata(tmp_path, budget=120, engineering_update_cap=50)
    # UNIT-only cadence prevents 50 large recovery files; production policy is untouched.
    cfg["proxy_contract"]["sample_plan"]["recovery_interval_samples"] = 120
    request["configuration"] = write_once(tmp_path / "UNIT_cap50_configuration.json", cfg)
    reference = write_once(tmp_path / "UNIT_cap50_request.json", request)
    first, row1, _ = _run_cli(tmp_path, reference, name="first", endpoint=2)
    assert first.returncode == 0, first.stdout + first.stderr
    parent = row1["outcome"]["last_checkpoint"]
    second, row2, _ = _run_cli(tmp_path, reference, name="resume_to_50", endpoint=120, parent=parent)
    assert second.returncode == 0, second.stdout + second.stderr
    limited = read_bound(row2["outcome"]["optimizer_update_limit_result"])
    assert limited["actual_optimizer_updates"] == 50
    assert limited["status"] == "ENGINEERING_UPDATE_LIMIT_COMPLETE_NOT_DATA_AUTHORITY"
    _, state = verify_checkpoint_record(limited["final_checkpoint"])
    assert state["optimizer_updates"] == 50 and state["pending_log"] is False
    assert {read_bound(ref)["role"] for ref in limited["validation"]} == set(pilot.ROLES)
    assert row2["cleanup_errors"] == [] and row2["first_failure"] is None
