"""Synthetic only: exact old builder, ridge oracle, honest schema and gates."""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
import pytest

from phychem_mfm.phase1 import v3_coordinate_lookup as core
from core_capture import CoreCapture, source_sha
from solver_math import csr_fingerprint
import coordinate_baseline_v2 as v2


def records(role="TRAIN"):
    x = np.array([[0., 0., 0.], [.4, .1, 0.], [.1, .7, .2], [.2, .2, .8]], dtype=np.float64)
    epsilon = np.array([[.01, -.03, .02], [-.02, .01, .03], [.04, -.01, -.02], [-.01, .02, .01]])
    for index in range(2 if role == "TRAIN" else 1):
        yield core.LookupRecord("synthetic_"+role+"_record_"+str(index), "synthetic_"+role+"_molecule_"+str(index), role,
            np.array([0, 1, 2, 3]), x+(index+1)*epsilon, x.copy(), "a"*64)


def config(**kwargs):
    return core.CoordinateLookupConfig(radius_A=2., bin_width_A=2., **kwargs)


def fit(**kwargs):
    return v2.fit_v2(core, records(), config=config(), expected_records=2,
                     source_request_sha256="b"*64, source_plan_sha256="c"*64, **kwargs)


def test_independent_builder_is_byte_identical_to_fixed_original_core_capture():
    cfg = config()
    with CoreCapture(core, cfg, expected_source_sha256=source_sha(core.__file__), sink=lambda *_: None) as captured:
        core.fit_coordinate_lookup(records(), config=cfg, expected_records=2, source_plan_sha256="c"*64)
    system = v2.build_train_system(core, records(), cfg, expected_records=2)
    assert csr_fingerprint(system.matrix) == csr_fingerprint(captured.matrix)
    assert np.array_equal(system.rhs_normalized, captured.rhs)
    assert np.array_equal(system.support, captured.support)
    assert system.atoms == captured.n_atoms and system.directed_edges == captured.directed_edges


def test_v2_matches_small_dense_original_ridge_and_does_not_call_old_solver(monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("Old 500 solver is not the v2 algorithm")
    monkeypatch.setattr(core, "lsqr", forbidden)
    model = fit()
    system = v2.build_train_system(core, records(), config(), expected_records=2)
    active = np.flatnonzero(system.support)
    a = system.matrix[:, active].toarray()  # tiny TEST oracle only.
    ridge = np.linalg.solve(a.T@a/system.atoms+1e-4*np.eye(len(active)),
                           a.T@system.rhs_normalized/math.sqrt(system.atoms))
    assert np.allclose(model.coefficients[active], ridge, rtol=2e-6, atol=1e-8)
    assert np.equal(model.coefficients[system.support == 0], 0).all()
    receipt = model.fit_receipt
    assert "solver" not in receipt and receipt["actual_solver_configuration_v2"]["maximum_iterations"] == 2000
    assert receipt["actual_solver_configuration_v2"]["damp"] == 0 and not receipt["KKT_acceptance_threshold_applied"]
    assert receipt["original_v1_job_4520482_remains_FAILED"]


def test_honest_v2_serialization_and_restore_preserve_original_predictions():
    model = fit()
    document = json.loads(json.dumps(model.document(), allow_nan=False))
    assert document["schema"] == "model_v3_C2_coordinate_lookup_v2"
    assert document["source_feature_resource_configuration_v1"]["maximum_iterations"] == 500
    assert document["actual_solver_configuration_v2"]["maximum_iterations"] == 2000
    restored = v2.restore_v2(core, document)
    record = next(records("PRETRAIN_VAL"))
    a, coverage_a = model.predict_noise(record.elements, record.noisy)
    b, coverage_b = restored.predict_noise(record.elements, record.noisy)
    assert np.array_equal(a, b) and coverage_a == coverage_b
    with pytest.raises(ValueError): core.CoordinateLookup.from_document(document)


@pytest.mark.parametrize("change", ["same_shape_feature_change", "old_solver_disguise", "nonfinite", "duplicate_code", "bad_stop"])
def test_restore_refuses_source_semantic_and_solver_table_drift(change):
    document = fit().document()
    if change == "same_shape_feature_change":
        document["source_feature_resource_configuration_v1"]["radius_A"] = 4.
        document["source_feature_resource_configuration_v1"]["bin_width_A"] = 4.
    elif change == "old_solver_disguise":
        document["actual_solver_configuration_v2"] = {**v2.SOLVER, "maximum_iterations": 500}
    elif change == "nonfinite": document["coefficients"][0] = math.nan
    elif change == "duplicate_code": document["codes"][1] = document["codes"][0]
    else: document["fit_receipt_v2"]["augmented_operator_statistics"]["stop_code"] = 7
    with pytest.raises(ValueError): v2.restore_v2(core, document)


def test_original_evaluator_keeps_unknown_bins_and_all_component_denominators():
    model = fit()
    clean = np.array([[0., 0., 0.], [.5, 0., 0.]])
    noisy = clean+np.array([[.1, -.2, .3], [-.2, .1, -.1]])
    record = core.LookupRecord("synthetic_unknown_record", "synthetic_unknown_molecule", "PRETRAIN_VAL",
        np.array([110, 111]), noisy, clean, "d"*64)
    prediction, coverage = model.predict_noise(record.elements, noisy)
    assert np.equal(prediction, 0).all() and coverage["unknown_directed_edges"] == coverage["directed_edges"]
    metrics = core.evaluate_coordinate_lookup(model, [record], expected_records=1)
    squared = np.square(noisy-clean).sum()
    assert metrics["atoms"] == 2 and metrics["all_atoms_in_coordinate_denominator"]
    assert metrics["coordinate_vector_RMSE_A"] == pytest.approx(math.sqrt(squared/2))
    assert metrics["coordinate_component_RMSE_A"] == pytest.approx(math.sqrt(squared/6))
    assert metrics["explicit_sigma_normalized_component_MSE"] == pytest.approx(squared/(6*.1**2))


class Source:
    def __init__(self): self.native_reads = 0; self.roles = []
    def records(self, role, plan):
        self.roles.append(role)
        for record in records(role):
            self.native_reads += 1; yield record


def test_synthetic_fit_then_original_eval_calls_val_only_after_successful_fit():
    source = Source()
    fitted = []
    model, metrics = v2.fit_then_evaluate(core, source, {}, config=config(), train_records=2, validation_records=1,
        request_sha256="b"*64, plan_sha256="c"*64, on_fit=lambda m: fitted.append(source.native_reads))
    assert fitted == [2] and source.roles == ["TRAIN", "PRETRAIN_VAL"] and source.native_reads == 3
    assert metrics["records"] == 1 and model.fit_receipt["validation_used_for_fit_or_tuning"] is False


@pytest.mark.parametrize("failure", ["stop", "nonfinite"])
def test_failed_fit_never_enters_validation_source(monkeypatch, failure):
    def injected(system, **kwargs):
        full = np.zeros(system.original_columns)
        if failure == "nonfinite": full[system.active_columns[0]] = np.nan
        return full, {"solver_called": True, "stop_code": 7 if failure == "stop" else 2,
                      "iterations": 2000, "coefficients_finite": failure != "nonfinite"}
    monkeypatch.setattr(v2, "solve_augmented", injected)
    source = Source()
    with pytest.raises(ValueError, match="stop/finite"):
        v2.fit_then_evaluate(core, source, {}, config=config(), train_records=2, validation_records=1,
                            request_sha256="b"*64, plan_sha256="c"*64)
    assert source.roles == ["TRAIN"] and source.native_reads == 2


def test_role_and_original_sparse_budget_refusal_do_not_truncate_or_evaluate():
    with pytest.raises(ValueError, match="Only TRAIN"):
        v2.build_train_system(core, records("PRETRAIN_VAL"), config(), expected_records=1)
    with pytest.raises(ValueError, match="budget exceeded"):
        v2.build_train_system(core, records(), config(max_train_atoms=1), expected_records=2)
    with pytest.raises(ValueError, match="before its exact"):
        v2.build_train_system(core, records(), config(), expected_records=3)


def bound(path, value):
    path.write_text(json.dumps(value, allow_nan=False, sort_keys=True)+"\n")
    return v2.support_runtime.binding(path)


@pytest.mark.parametrize("gate", ["prepared_only", "original_500_succeeded", "wrong_plan", "eligible"])
def test_real_git_adoption_gate_does_not_precommit_to_v2_or_read_native_data(tmp_path, gate):
    request, plan = {"sha256": "b"*64}, {"sha256": "c"*64}
    diagnostic = {"status": "DIAGNOSTIC_ONLY_COMPLETED_NO_BASELINE_ACCEPTANCE", "native_PRETRAIN_VAL_records_decoded": 0,
        "source": {"baseline": {"stop_code": 2 if gate == "original_500_succeeded" else 7, "coefficients_finite": True}},
        "candidate": {"solver": {"stop_code": 2, "coefficients_finite": True}}}
    diagnostic_ref = bound(tmp_path/"synthetic_diagnostic.json", diagnostic)
    diagnostic_inputs_ref = bound(tmp_path/"synthetic_diagnostic_inputs.json", {"source_request": request,
        "selection_plan": plan, "protocol_registration": {"commit": v2.DIAGNOSTIC_PREREGISTRATION}})
    binding_ref = bound(tmp_path/"synthetic_input_binding.json", {"inputs": diagnostic_inputs_ref,
        "source_request": request, "selection_plan": {"sha256": "0"*64} if gate == "wrong_plan" else plan,
        "native_PRETRAIN_VAL_records_decoded": 0})
    done_ref = bound(tmp_path/"synthetic_done.json", {"result": diagnostic_ref, "status": diagnostic["status"],
        "inputs": diagnostic_inputs_ref, "native_PRETRAIN_VAL_records_decoded": 0})
    protocol = {"schema": "model_v3_C2_coordinate_baseline_v2_protocol_v1",
        "adoption_status": "PREPARED_CONDITIONAL_NOT_ADOPTED" if gate == "prepared_only" else "ADOPTED_AFTER_TRAIN_ONLY_DIAGNOSTIC",
        "solver": v2.SOLVER, "caps": v2.CAPS, "source_inventory_sha256": v2.support_runtime.canonical(v2.executed_sources()),
        "source_request_raw_sha256": request["sha256"], "selection_plan_raw_sha256": plan["sha256"],
        "TRAIN_diagnostic_result_raw_sha256": diagnostic_ref["sha256"], "TRAIN_diagnostic_done_raw_sha256": done_ref["sha256"],
        "TRAIN_diagnostic_input_binding_raw_sha256": binding_ref["sha256"]}
    protocol_ref = bound(tmp_path/"protocol.json", protocol)
    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
    git("init"); git("add", "protocol.json")
    git("-c", "user.name=Synthetic Test", "-c", "user.email=fixture@example.invalid", "commit", "-m", "synthetic protocol")
    registration = {"repository": str(tmp_path), "commit": git("rev-parse", "HEAD"), "path": "protocol.json", "sha256": protocol_ref["sha256"]}
    if gate == "eligible":
        assert v2.adopted_protocol(registration, request, plan, diagnostic_ref, done_ref, binding_ref) == protocol
    else:
        with pytest.raises(ValueError): v2.adopted_protocol(registration, request, plan, diagnostic_ref, done_ref, binding_ref)
