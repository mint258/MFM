"""Transparent, temporary instrumentation of the byte-fixed C2 TRAIN fitter.

Only exact known closure/local names are inspected. The original scipy operator
and LSQR return tuple are passed through unchanged. Source files and the original
TRAIN CSR are never modified, and no evaluation function is called.
"""
from __future__ import annotations

from dataclasses import asdict
from contextlib import contextmanager
import hashlib
import inspect
import math
from pathlib import Path
import time

import numpy as np
from scipy.sparse.linalg import LinearOperator, lsqr
from threadpoolctl import threadpool_info, threadpool_limits

from solver_math import csr_fingerprint, lsqr_statistics, numerical_state, require


def source_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verified_blas_info():
    info = threadpool_info()
    blas = [row for row in info if row.get("user_api") == "blas"]
    require(blas and all(row.get("num_threads") == 1 for row in blas), "Actual detected BLAS pools must all be limited to one thread")
    return info


def _thread_signature(rows):
    return {row["filepath"]: row["num_threads"] for row in rows}


@contextmanager
def controlled_blas(sink, name):
    """Persist real thread restoration even when a guarded solve is censored."""
    receipt = {"schema": "model_v3_C2_diagnostic_BLAS_control_v1", "requested_blas_threads": 1,
               "threadpools_before": threadpool_info()}
    try:
        with threadpool_limits(limits=1, user_api="blas"):
            receipt["threadpools_inside_before"] = verified_blas_info()
            try:
                yield receipt
            finally:
                receipt["threadpools_inside_after"] = threadpool_info()
    finally:
        receipt["threadpools_restored"] = threadpool_info()
        receipt["original_thread_settings_restored"] = (
            _thread_signature(receipt["threadpools_before"]) == _thread_signature(receipt["threadpools_restored"]))
        sink(name, receipt)
        require(receipt["original_thread_settings_restored"], "BLAS thread state did not restore exactly")


class CoreCapture:
    def __init__(self, core, config, *, expected_source_sha256, sink, check=lambda: None, expected_path=None):
        self.core, self.config, self.expected_sha = core, config, expected_source_sha256
        self.sink, self.check, self.expected_path = sink, check, expected_path
        self.matrix = self.rhs = self.support = self.baseline_coefficient = None
        self.baseline = self.operator = self.pre_fingerprint = None
        self.original_lsqr, self.original_operator = core.lsqr, core.LinearOperator
        self.entered = False

    def __enter__(self):
        require(not self.entered and self.original_lsqr is lsqr and self.original_operator is LinearOperator,
                "Fresh unmodified original SciPy bindings required")
        require(source_sha(self.core.__file__) == self.expected_sha, "Original C2 core source SHA differs")
        if self.expected_path is not None:
            require(Path(self.core.__file__).resolve() == Path(self.expected_path).resolve(), "Original C2 core imported from a different tree")
        self.entered = True
        self.core.LinearOperator = self._operator
        self.core.lsqr = self._lsqr
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.core.LinearOperator = self.original_operator
        self.core.lsqr = self.original_lsqr
        self.entered = False
        require(source_sha(self.core.__file__) == self.expected_sha, "Original C2 source changed during instrumentation")
        return False

    def _operator(self, *args, **kwargs):
        require(self.operator is None and set(kwargs) == {"matvec", "rmatvec", "dtype"}, "Exactly one known original operator construction required")
        directions = [inspect.getclosurevars(kwargs[name]).nonlocals for name in ("matvec", "rmatvec")]
        require(all(set(d) == {"check", "matrix", "root_atoms"} for d in directions), "Fixed original matvec closure names differ")
        a, b = directions
        require(a["matrix"] is b["matrix"] and a["root_atoms"] == b["root_atoms"] and a["check"] is b["check"],
                "Original forward/transpose operators do not share the same TRAIN system")
        frame = inspect.currentframe().f_back
        try:
            require(frame.f_code is self.core.fit_coordinate_lookup.__code__, "Operator caller is not the fixed original TRAIN fitter")
            self.n_atoms, self.directed_edges = int(frame.f_locals["atoms"]), int(frame.f_locals["edges"])
            support = frame.f_locals["support"]
        finally:
            del frame
        require(self.n_atoms > 0 and a["root_atoms"] == math.sqrt(self.n_atoms)
                and a["matrix"].shape[0] == 3*self.n_atoms, "Original atom/normalization dimensions differ")
        self.matrix, self.root_atoms, self.support = a["matrix"], a["root_atoms"], support
        require(self.support.shape == (self.matrix.shape[1],) and np.issubdtype(self.support.dtype, np.integer),
                "Original support-vector shape/type differs")
        self.pre_fingerprint = csr_fingerprint(self.matrix, check=self.check)
        self.operator = self.original_operator(*args, **kwargs)
        return self.operator

    def _lsqr(self, operator, rhs, **kwargs):
        expected = {"damp": math.sqrt(self.config.ridge), "atol": self.config.atol,
            "btol": self.config.btol, "conlim": self.config.condition_limit,
            "iter_lim": self.config.maximum_iterations, "show": False}
        require(operator is self.operator and kwargs == expected and self.baseline is None,
                "Transparent original LSQR options/operator differ; x0 is not allowed")
        self.rhs = np.asarray(rhs, dtype=np.float64).copy()
        require(self.rhs.shape == (self.matrix.shape[0],) and np.isfinite(self.rhs).all(), "Finite original normalized TRAIN RHS required")
        if hasattr(self.check, "stage"): self.check.stage = "TRAIN_CONTROLLED_SOURCE_LSQR"
        self.check()
        with controlled_blas(self.sink, "controlled_source_thread_control") as threads:
            before, inside = threads["threadpools_before"], threads["threadpools_inside_before"]
            started = time.perf_counter()
            solved = self.original_lsqr(operator, rhs, **kwargs)
            elapsed = time.perf_counter()-started
            # Commit stop fields BEFORE leaving this wrapper or reaching the
            # original require. Expensive KKT/checks happen only after this write.
            self.baseline = {"schema": "model_v3_C2_controlled_source_solver_return_v1",
                "status": "DIAGNOSTIC_ONLY_NOT_BASELINE_ACCEPTANCE", **lsqr_statistics(solved),
                "configured_iteration_limit": self.config.maximum_iterations,
                "solver_wall_seconds": elapsed, "matrix_shape": list(self.matrix.shape),
                "matrix_nnz": int(self.matrix.nnz), "TRAIN_atoms": self.n_atoms,
                "TRAIN_directed_edges": self.directed_edges,
                "observed_support_columns": int((self.support > 0).sum()),
                "original_configuration": asdict(self.config), "original_lsqr_options": kwargs,
                "threadpools_before": before, "threadpools_inside_before": inside,
                "old_job_4520482_stop_inferred": False, "native_PRETRAIN_VAL_records_read": 0}
            self.sink("controlled_source_solver_return", self.baseline)
            self.baseline_coefficient = np.asarray(solved[0], dtype=np.float64).copy()
            after_inside = verified_blas_info()
        restored = threads["threadpools_restored"]
        self.baseline["threadpools_inside_after"] = after_inside
        self.baseline["threadpools_restored"] = restored
        require(csr_fingerprint(self.matrix, check=self.check) == self.pre_fingerprint, "Original TRAIN CSR changed during source LSQR")
        if self.baseline["coefficients_finite"]:
            if hasattr(self.check, "stage"): self.check.stage = "TRAIN_CONTROLLED_SOURCE_KKT"
            self.baseline["original_coordinate_diagnostics"] = numerical_state(self.matrix, self.rhs,
                self.baseline_coefficient, n_atoms=self.n_atoms, ridge=self.config.ridge, check=self.check)
        self.sink("controlled_source_solver_diagnostics", self.baseline)
        return solved
