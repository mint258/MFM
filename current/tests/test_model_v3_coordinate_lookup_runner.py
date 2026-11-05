"""C2 orchestration fixtures: no native source reads or W&B durability claim."""
from dataclasses import asdict, replace
import hashlib
import importlib.util
import json
import os
import builtins
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from test_model_v3_coordinate_lookup import record
from phychem_mfm.phase1.v3_coordinate_lookup import CoordinateLookupConfig
import phychem_mfm.phase1.v3_coordinate_lookup_source as source_module


ROOT = Path(__file__).absolute().parents[2]


@pytest.fixture(autouse=True)
def preserve_tracking_environment():
    keys = ("WANDB_DIR", "WANDB_CACHE_DIR", "WANDB_DATA_DIR", "WANDB_CONFIG_DIR", "WANDB_MODE")
    original = {key: os.environ.get(key) for key in keys}
    try:
        yield
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def runner_module():
    path = ROOT / "tools/model_v3/run_coordinate_lookup.py"
    spec = importlib.util.spec_from_file_location("unit_C2_runner", path)
    value = importlib.util.module_from_spec(spec); spec.loader.exec_module(value)
    return value


def document(path, value):
    raw = (json.dumps(value, sort_keys=True, indent=2)+"\n").encode()
    path.write_bytes(raw)
    return str(path), hashlib.sha256(raw).hexdigest()


class UnitSource:
    """Only a fixture for ordering; production constructor is separately strict."""
    instances = []
    def __init__(self, request, check):
        self.request, self.check = request, check
        self.native_reads, self.closed, self.verified = 0, 0, 0
        self.seen_roles = []
        self.__class__.instances.append(self)
    def plan(self):
        return {"schema": "unit_metadata_selection_only", "role_evidence": {"unit_fixture": True}, "members": ["r1", "r2", "v1"]}
    def records(self, role, selected):
        self.seen_roles.append(role)
        if role == "TRAIN":
            assert not self.seen_roles[:-1]
            values = [record(name="r1"), record(name="r2")]
        else:
            assert self.seen_roles == ["TRAIN", "PRETRAIN_VAL"]
            values = [record(name="v1", role="PRETRAIN_VAL")]
        for value in values:
            self.native_reads += 1
            yield value
    def verify(self):
        self.verified += 1
    def close(self):
        self.closed += 1


class UnitSDKRun:
    """The fixture verifies explicit commit/finish; it is not a real SDK run."""
    disabled, id = False, "UNIT_NOT_PERSISTENT_TRACKING"
    def __init__(self, output):
        self.rows, self.finished, self.output = [], [], output
    def log(self, row, *, step, commit):
        assert step == len(self.rows) and commit is True
        self.rows.append(row)
    def finish(self, exit_code=0):
        assert not (self.output / "COMPLETE.json").exists()
        self.finished.append(exit_code)


@pytest.fixture
def bound_unit(tmp_path, monkeypatch):
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    request = {"schema": "unit_request_not_a_native_delivery", "code_sha": "c"*40,
        "preregistration_sha": "d"*40, "method": asdict(CoordinateLookupConfig()),
        "selection": {"train_records": 2, "validation_records": 1}}
    request_path, request_sha = document(tmp_path / "request.json", request)
    selected = UnitSource(request, lambda: None).plan()
    UnitSource.instances = []
    plan_path, plan_sha = document(tmp_path / "selection.json", selected)
    monkeypatch.setattr(source_module, "ExistingSLookupSource", UnitSource)
    return request_path, request_sha, plan_path, plan_sha


def test_prepare_closes_source_before_publishing_and_never_decodes_geometry(tmp_path, monkeypatch, bound_unit):
    request_path, request_sha, _, _ = bound_unit
    output = tmp_path / "prepare_output"
    monkeypatch.setattr(sys, "argv", ["run_coordinate_lookup.py", "--mode", "prepare", "--output-root", str(output),
        "--request", request_path, "--request-sha256", request_sha])
    runner_module().main()
    source = UnitSource.instances[-1]
    assert source.native_reads == 0 and not source.seen_roles and source.closed >= 1 and source.verified == 1
    result = json.loads((output / "preparation_result.json").read_text())
    assert result["native_geometry_records_decoded"] == 0 and (output / "selection_plan.json").exists()
    assert not (output / "coordinate_lookup.json").exists()


def test_run_fits_train_then_validates_and_writes_complete_only_after_sdk_finish(tmp_path, monkeypatch, bound_unit):
    request_path, request_sha, plan_path, plan_sha = bound_unit
    output = tmp_path / "run_output"
    tracker = UnitSDKRun(output)
    monkeypatch.setitem(sys.modules, "wandb", SimpleNamespace(init=lambda **kwargs: tracker))
    monkeypatch.setattr(sys, "argv", ["run_coordinate_lookup.py", "--mode", "run", "--output-root", str(output),
        "--request", request_path, "--request-sha256", request_sha,
        "--selection-plan", plan_path, "--selection-plan-sha256", plan_sha])
    runner_module().main()
    source = UnitSource.instances[-1]
    assert source.seen_roles == ["TRAIN", "PRETRAIN_VAL"] and source.native_reads == 3
    assert source.closed >= 1 and source.verified == 1
    assert tracker.finished == [0] and len(tracker.rows) == 2
    complete = json.loads((output / "COMPLETE.json").read_text())
    assert complete["lookup"]["sha256"] == hashlib.sha256((output / "coordinate_lookup.json").read_bytes()).hexdigest()
    result = json.loads((output / "result.json").read_text())
    assert result["status"] == "ANALYSIS_COMPLETE_NOT_MODEL_SELECTION"
    assert result["native_geometry_records_decoded"] == 3 and not result["online_sync_claimed"]


def test_changed_frozen_selection_is_refused_before_fit_or_sdk_initialization(tmp_path, monkeypatch, bound_unit):
    request_path, request_sha, _, _ = bound_unit
    changed_path, changed_sha = document(tmp_path / "changed.json", {"members": ["different"]})
    output = tmp_path / "wrong_selection"
    monkeypatch.setattr(sys, "argv", ["run_coordinate_lookup.py", "--mode", "run", "--output-root", str(output),
        "--request", request_path, "--request-sha256", request_sha,
        "--selection-plan", changed_path, "--selection-plan-sha256", changed_sha])
    with pytest.raises(ValueError, match="do not reselect"):
        runner_module().main()
    source = UnitSource.instances[-1]
    assert source.native_reads == 0 and source.closed >= 1
    assert (output / "FAILED.json").exists() and not (output / "COMPLETE.json").exists()


def test_source_postcheck_failure_preserves_failed_evidence_and_no_complete_marker(tmp_path, monkeypatch, bound_unit):
    request_path, request_sha, plan_path, plan_sha = bound_unit
    output = tmp_path / "postcheck_failed"
    tracker = UnitSDKRun(output)
    monkeypatch.setitem(sys.modules, "wandb", SimpleNamespace(init=lambda **kwargs: tracker))
    def changed(self):
        raise ValueError("source changed after fitting")
    monkeypatch.setattr(UnitSource, "verify", changed)
    monkeypatch.setattr(sys, "argv", ["run_coordinate_lookup.py", "--mode", "run", "--output-root", str(output),
        "--request", request_path, "--request-sha256", request_sha,
        "--selection-plan", plan_path, "--selection-plan-sha256", plan_sha])
    with pytest.raises(ValueError, match="source changed"):
        runner_module().main()
    assert tracker.finished == [1] and UnitSource.instances[-1].closed >= 1
    failure = json.loads((output / "FAILED.json").read_text())
    assert failure["native_geometry_records_decoded"] == 3
    assert not (output / "COMPLETE.json").exists()


def test_cli_refuses_missing_allocation_visible_cuda_or_reused_output(tmp_path, monkeypatch):
    output = tmp_path / "no_job"
    monkeypatch.setattr(sys, "argv", ["run_coordinate_lookup.py", "--mode", "prepare", "--output-root", str(output)])
    monkeypatch.delenv("SLURM_JOB_ID", raising=False)
    with pytest.raises(RuntimeError, match="owned 16-CPU"):
        runner_module().main()
    monkeypatch.setenv("SLURM_JOB_ID", "unit_metadata_only")
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "16")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-unit")
    with pytest.raises(RuntimeError, match="CPU-only"):
        runner_module().main()
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    output.mkdir()
    with pytest.raises(ValueError, match="Fresh external"):
        runner_module().main()


def test_canonical_layout_is_bound_before_the_runner_imports_sdk(tmp_path, monkeypatch, bound_unit):
    request_path, request_sha, plan_path, plan_sha = bound_unit
    output = tmp_path / "canonical_paths"
    tracker = UnitSDKRun(output)
    monkeypatch.setitem(sys.modules, "wandb", SimpleNamespace(init=lambda **kwargs: tracker))
    original_import, import_observations = builtins.__import__, []
    def observed_import(name, *args, **kwargs):
        if name == "wandb":
            expected = {"WANDB_DIR": output, "WANDB_CACHE_DIR": output / "cache",
                "WANDB_DATA_DIR": output / "wandb_data", "WANDB_CONFIG_DIR": output / "wandb_config"}
            assert all(os.environ[key] == str(path) and path.is_dir() for key, path in expected.items())
            assert os.environ["WANDB_MODE"] == "offline"
            import_observations.append(name)
        return original_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", observed_import)
    monkeypatch.setattr(sys, "argv", ["run_coordinate_lookup.py", "--mode", "run", "--output-root", str(output),
        "--request", request_path, "--request-sha256", request_sha,
        "--selection-plan", plan_path, "--selection-plan-sha256", plan_sha])
    runner_module().main()
    assert import_observations == ["wandb"]
    result = json.loads((output / "result.json").read_text())
    assert result["tracking_layout"]["WANDB_CACHE_DIR"] == str(output / "cache")


@pytest.mark.parametrize("name", ("cache", "wandb_data", "wandb_config"))
def test_canonical_sdk_layout_refuses_symlinked_directories(tmp_path, name):
    output, outside = tmp_path / "owned", tmp_path / "outside"
    output.mkdir(); outside.mkdir()
    (output / name).symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="ordinary directories"):
        runner_module().configure_wandb_layout(output)
