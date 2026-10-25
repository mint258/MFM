"""Exercise the actual frozen C2 fitter on small synthetic TRAIN geometries."""
import json
import math
from pathlib import Path

import numpy as np
import pytest

from phychem_mfm.phase1 import v3_coordinate_lookup as core
from core_capture import CoreCapture, source_sha
from solver_math import augmented_active_jacobi, csr_fingerprint, solve_augmented


def records(role="TRAIN"):
    clean = np.array([[0., 0., 0.], [.4, .1, .0], [.1, .7, .2], [.2, .2, .8]], dtype=np.float64)
    delta = np.array([[.01, -.03, .02], [-.02, .01, .03], [.04, -.01, -.02], [-.01, .02, .01]])
    for index in range(2):
        yield core.LookupRecord("synthetic_record_"+str(index), "synthetic_molecule_"+str(index), role,
            np.array([0, 1, 2, 3]), clean+(index+1)*delta, clean.copy(), "a"*64)


@pytest.mark.parametrize("iteration_limit", [1, 500])
def test_real_core_stop_receipt_exists_before_original_require_and_csr_is_unchanged(tmp_path, monkeypatch, iteration_limit):
    config = core.CoordinateLookupConfig(radius_A=2., bin_width_A=2., maximum_iterations=iteration_limit)
    events = {}
    def sink(name, value):
        events[name] = json.loads(json.dumps(value, allow_nan=False))
        (tmp_path/(name+".json")).write_text(json.dumps(value, allow_nan=False))
    original_require, original_lsqr, original_operator = core.require, core.lsqr, core.LinearOperator
    def observe_require(condition, message):
        if message.startswith("Sparse LSQR did not"):
            assert (tmp_path/"controlled_source_solver_return.json").is_file()
            assert "stop_code" in events["controlled_source_solver_return"]
        return original_require(condition, message)
    monkeypatch.setattr(core, "require", observe_require)
    with CoreCapture(core, config, expected_source_sha256=source_sha(core.__file__), sink=sink) as capture:
        try:
            model = core.fit_coordinate_lookup(records(), config=config, expected_records=2, source_plan_sha256="b"*64)
        except ValueError as exc:
            assert str(exc) == "Sparse LSQR did not satisfy the preregistered stopping condition"
            assert capture.baseline["stop_code"] not in (0, 1, 2, 4, 5) or not capture.baseline["coefficients_finite"]
        else:
            assert model.fit_receipt["TRAIN_records"] == 2
        assert capture.n_atoms == 8 and capture.rhs.shape == (24,)
        assert capture.baseline["configured_iteration_limit"] == iteration_limit
        assert capture.baseline["native_PRETRAIN_VAL_records_read"] == 0
        assert not capture.baseline["old_job_4520482_stop_inferred"]
        assert csr_fingerprint(capture.matrix) == capture.pre_fingerprint
        transformed = augmented_active_jacobi(capture.matrix, capture.rhs, capture.support,
            n_atoms=capture.n_atoms, ridge=config.ridge)
        candidate, _ = solve_augmented(transformed)
        active = transformed.active_columns
        a = capture.matrix[:, active].toarray()  # tiny TEST oracle only, never production.
        oracle = np.linalg.solve(a.T@a/capture.n_atoms+config.ridge*np.eye(len(active)),
                                 a.T@capture.rhs/math.sqrt(capture.n_atoms))
        assert np.allclose(candidate[active], oracle, rtol=2e-6, atol=1e-8)
        assert np.equal(candidate[capture.support == 0], 0).all()
        assert csr_fingerprint(capture.matrix) == capture.pre_fingerprint
    assert core.lsqr is original_lsqr and core.LinearOperator is original_operator
    assert capture.baseline["threadpools_before"] == capture.baseline["threadpools_restored"]


def test_early_failure_restores_original_symbols_and_never_reaches_solver():
    config = core.CoordinateLookupConfig(radius_A=2., bin_width_A=2.)
    original_lsqr, original_operator = core.lsqr, core.LinearOperator
    def failure():
        raise RuntimeError("synthetic pre-solver guard failure")
    with pytest.raises(RuntimeError, match="pre-solver guard"):
        with CoreCapture(core, config, expected_source_sha256=source_sha(core.__file__), sink=lambda *_: None) as capture:
            core.fit_coordinate_lookup(records(), config=config, expected_records=2,
                source_plan_sha256="b"*64, check=failure)
    assert capture.baseline is None and core.lsqr is original_lsqr and core.LinearOperator is original_operator


def test_source_drift_and_non_train_role_are_rejected_without_solver():
    config = core.CoordinateLookupConfig(radius_A=2., bin_width_A=2.)
    with pytest.raises(ValueError, match="source SHA"):
        with CoreCapture(core, config, expected_source_sha256="0"*64, sink=lambda *_: None):
            raise AssertionError("unbound source must not enter")
    with CoreCapture(core, config, expected_source_sha256=source_sha(core.__file__), sink=lambda *_: None) as capture:
        with pytest.raises(ValueError, match="Only TRAIN records"):
            core.fit_coordinate_lookup(records("PRETRAIN_VAL"), config=config,
                expected_records=2, source_plan_sha256="b"*64)
        assert capture.baseline is None
