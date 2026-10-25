"""Synthetic integration and real Git preregistration; never native data/VAL."""
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import subprocess

import numpy as np
import pytest

from phychem_mfm.phase1 import v3_coordinate_lookup as core
import diagnose_coordinate_lookup as runner
from core_capture import source_sha
from test_core_capture import records


class SyntheticSource:
    def __init__(self):
        self.native_reads = 0
        self.roles = []
    def records(self, role, plan):
        assert role == "TRAIN", "No validation source may be consumed"
        self.roles.append(role)
        for record in records():
            self.native_reads += 1
            yield record


class SyntheticGuard:
    stage = "TRAIN_ORIGINAL_BUILD_AND_CONTROLLED_SOURCE_500"
    def __call__(self): pass


def request(iterations=500):
    config = core.CoordinateLookupConfig(radius_A=2., bin_width_A=2., maximum_iterations=iterations)
    return {"method": asdict(config), "selection": {"train_records": 2},
        "source_files": {"current/phychem_mfm/phase1/v3_coordinate_lookup.py": source_sha(core.__file__)},
        "diagnostic_selection_plan_raw_sha256": "a"*64}


@pytest.mark.parametrize("iterations", [1, 500])
def test_same_train_system_candidate_never_calls_validation_even_if_old_fit_returns(tmp_path, monkeypatch, iterations):
    def forbidden(*args, **kwargs):
        raise AssertionError("The old validation function must never run")
    monkeypatch.setattr(core, "evaluate_coordinate_lookup", forbidden)
    source, guard = SyntheticSource(), SyntheticGuard()
    def sink(name, value): runner.save(tmp_path/(name+".json"), value)
    result, arrays = runner.run_train_only(core, source, request(iterations), {}, sink=sink, check=guard)
    assert source.roles == ["TRAIN"] and source.native_reads == 2
    assert result["native_PRETRAIN_VAL_records_decoded"] == 0 and not result["model_selection_gate"]
    assert result["original_v1_job_4520482_remains_FAILED"] and not result["original_v1_stop_or_iteration_count_inferred"]
    assert result["candidate"]["preprocessing"]["damp"] == 0
    assert not result["candidate"]["preprocessing"]["warm_start_used"]
    assert len(arrays["active_columns"]) < result["original_TRAIN_CSR"]["shape"][1]
    assert not any("matrix" in name or "coordinate" in name or "record" in name for name in arrays)
    assert (tmp_path/"controlled_source_solver_return.json").is_file()
    assert (tmp_path/"active_jacobi_candidate_return.json").is_file()


def test_candidate_censor_preserves_controlled_source_stop_without_reading_val(tmp_path):
    class Deadline(SyntheticGuard):
        def __call__(self):
            if self.stage == "TRAIN_ACTIVE_JACOBI_LSQR": raise runner.WorkDeadline("synthetic declared work deadline")
    original_solver, original_operator = core.lsqr, core.LinearOperator
    source = SyntheticSource()
    with pytest.raises(runner.WorkDeadline):
        runner.run_train_only(core, source, request(), {}, sink=lambda name, value: runner.save(tmp_path/(name+".json"), value), check=Deadline())
    assert source.roles == ["TRAIN"] and source.native_reads == 2
    receipt = json.loads((tmp_path/"controlled_source_solver_return.json").read_text())
    assert type(receipt["stop_code"]) is int and type(receipt["iterations"]) is int
    assert not (tmp_path/"active_jacobi_candidate_return.json").exists()
    restored = json.loads((tmp_path/"active_jacobi_thread_control.json").read_text())
    assert restored["original_thread_settings_restored"]
    assert restored["threadpools_before"] == restored["threadpools_restored"]
    assert core.lsqr is original_solver and core.LinearOperator is original_operator


def test_cpu_admission_requires_actual_cpu_host_and_owned_allocation(monkeypatch):
    monkeypatch.setattr(runner.socket, "gethostname", lambda: "compute-0-8.cluster")
    for key, value in {"SLURMD_NODENAME": "compute-0-8", "SLURM_JOB_ID": "999999",
                       "SLURM_CPUS_PER_TASK": "16", "CUDA_VISIBLE_DEVICES": ""}.items(): monkeypatch.setenv(key, value)
    runner.cpu_admission("compute-0-8")
    with pytest.raises(ValueError, match="CPU node"): runner.cpu_admission("compute-0-20")
    monkeypatch.setattr(runner.socket, "gethostname", lambda: "login")
    with pytest.raises(ValueError, match="Slurm allocation"): runner.cpu_admission("compute-0-8")


def protocol():
    return {"schema": "model_v3_C2_train_solver_diagnostic_protocol_v1", "scope": "TRAIN_ONLY_DIAGNOSTIC_NOT_BASELINE_ACCEPTANCE",
        "caps": runner.CAPS, "blas_threads": 1, "controlled_source_max_iterations": 500,
        "candidate_max_iterations": 2000, "atol": 1e-8, "btol": 1e-8, "condition_limit": 1e8,
        "ridge": 1e-4, "warm_start_used": False, "source_inventory_sha256": runner.canonical(runner.executed_sources())}


def test_real_git_blob_must_bind_actual_executed_source_and_fixed_diagnostic_rules(tmp_path):
    path = tmp_path/"protocol.json"
    raw = (json.dumps(protocol(), sort_keys=True)+"\n").encode(); path.write_bytes(raw)
    def git(*args):
        return subprocess.run(["git", "-C", str(tmp_path), *args], check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.decode().strip()
    git("init"); git("add", "protocol.json")
    git("-c", "user.name=Synthetic Test", "-c", "user.email=fixture@example.invalid", "commit", "-m", "synthetic preregistration")
    ref = {"repository": str(tmp_path), "commit": git("rev-parse", "HEAD"), "path": "protocol.json", "sha256": hashlib.sha256(raw).hexdigest()}
    assert runner.registered_protocol(ref) == protocol()
    path.write_text("working-tree replacement is not the registered blob")
    assert runner.registered_protocol(ref) == protocol()
    with pytest.raises(ValueError, match="blob differs"): runner.registered_protocol({**ref, "sha256": "0"*64})


def test_optional_array_budget_never_writes_csr_or_silently_increases_output_cap(tmp_path):
    class Guard:
        output_cap = 128*1024**2
        census = staticmethod(lambda _: 0)
        def __call__(self): pass
    arrays = {"active_columns": np.arange(4), "observed_support": np.ones(4, dtype=np.int64),
              "candidate_coefficient": np.arange(4, dtype=np.float64)}
    artifact = runner.write_arrays(arrays, tmp_path, Guard())
    assert artifact["saved"] and not artifact["CSR_saved"] and not artifact["member_IDs_or_coordinates_saved"]
    with np.load(artifact["binding"]["path"], allow_pickle=False) as saved:
        assert set(saved.files) == set(arrays)
    other = tmp_path/"small_cap"; other.mkdir()
    guard = Guard(); guard.output_cap = 1024
    refusal = runner.write_arrays(arrays, other, guard)
    assert not refusal["saved"] and not list(other.iterdir())


def test_bound_metadata_rejects_duplicate_keys_and_byte_drift_before_any_data(tmp_path):
    for raw in (b'{"a":1,"a":2}', b'{"a":NaN}'):
        path = tmp_path/"bad.json"; path.write_bytes(raw)
        ref = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        with pytest.raises(ValueError): runner.bound_json(ref)
    path.write_bytes(b'{"a":1}')
    with pytest.raises(ValueError, match="SHA/bytes"): runner.bound_json(ref)
