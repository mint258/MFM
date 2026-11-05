"""CPU-only checks of explicit mode parsing/import order/receipts, not CUDA gates."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).absolute().parents[2]
TOOLS = ROOT / "tools/model_v3"


def runtime(monkeypatch):
    monkeypatch.syspath_prepend(str(TOOLS))
    spec = importlib.util.spec_from_file_location("model_v3_controls_test", TOOLS / "a_execution_runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def probe(source, *arguments):
    environment = dict(os.environ)
    environment.update(CUDA_VISIBLE_DEVICES="", CUBLAS_WORKSPACE_CONFIG=":16:8",
                       OMP_NUM_THREADS="8", MKL_NUM_THREADS="8", OPENBLAS_NUM_THREADS="8")
    child = subprocess.run([sys.executable, "-c", source, str(TOOLS), *arguments],
        env=environment, text=True, capture_output=True, timeout=120, check=False)
    assert child.returncode == 0, child.stdout + "\n" + child.stderr
    return json.loads(child.stdout)


def test_deterministic_mode_is_opt_in_at_cli_parse_only(monkeypatch, tmp_path):
    module = runtime(monkeypatch)
    parser = argparse.ArgumentParser()
    module.add_arguments(parser)
    required = ["--candidate-options", str(tmp_path / "options.json"), "--output", str(tmp_path / "out"),
                "--code-sha", "a" * 40, "--expected-gpu", "4090"]
    assert parser.parse_args(required).deterministic_controls is False
    assert parser.parse_args(required + ["--deterministic-controls"]).deterministic_controls is True
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("requested", [False, True])
def test_fresh_cpu_process_proves_import_timing_flags_and_configuration_receipt(requested):
    value = probe(r'''
import json, os, sys
from types import SimpleNamespace
sys.path.insert(0, sys.argv[1])
import a_execution_runtime as runtime
assert "torch" not in sys.modules
requested = sys.argv[2] == "1"
binding = runtime.prepare_deterministic_controls(requested)
assert "torch" not in sys.modules
assert binding["torch_imported_before_binding"] is False
import torch
assert not torch.cuda.is_initialized()
before = (torch.are_deterministic_algorithms_enabled(), torch.is_deterministic_algorithms_warn_only_enabled(),
    torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark,
    torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
receipt = runtime.apply_deterministic_controls(binding)
after = (torch.are_deterministic_algorithms_enabled(), torch.is_deterministic_algorithms_warn_only_enabled(),
    torch.backends.cudnn.deterministic, torch.backends.cudnn.benchmark,
    torch.backends.cuda.matmul.allow_tf32, torch.backends.cudnn.allow_tf32)
if requested:
    assert after == (True, False, True, False, False, False)
    assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":4096:8"
else:
    assert before == after
    assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":16:8"
assert not torch.cuda.is_initialized()
args = SimpleNamespace(reference_config=runtime.REPO / "workflows/sprime_s/formal_s/B1_seed0_v2.json",
    candidate_options=runtime.REPO / "current/configs/model_v3/performance/a00_control.json",
    shard_snapshot_sha256=None, seed=0, input="synthetic", code_sha="a" *40, prereg_sha="b" *40,
    deterministic_controls_receipt=receipt)
_, _, _, configuration = runtime.load_references(args)
assert configuration["deterministic_controls"] == receipt
assert len(receipt["execution_sha256"]) == 64
print(json.dumps({"receipt": receipt, "cuda_initialized": torch.cuda.is_initialized(),
                  "configuration_receipt_equal": True}))
''', "1" if requested else "0")
    assert value["cuda_initialized"] is False
    assert value["receipt"]["requested"] is requested
    assert value["receipt"]["cublas_workspace_before"] == ":16:8"
    assert value["configuration_receipt_equal"]


def test_requested_controls_reject_late_torch_import_without_mutating_environment():
    value = probe(r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import torch
import a_execution_runtime as runtime
try:
    runtime.prepare_deterministic_controls(True)
except RuntimeError as error:
    assert "before any Torch import" in str(error)
else:
    raise AssertionError("Late binding was accepted")
assert os.environ["CUBLAS_WORKSPACE_CONFIG"] == ":16:8"
assert not torch.cuda.is_initialized()
print(json.dumps({"late_binding_rejected": True}))
''')
    assert value["late_binding_rejected"]


def test_requested_controls_reject_workspace_drift_before_cuda():
    value = probe(r'''
import json, os, sys
sys.path.insert(0, sys.argv[1])
import a_execution_runtime as runtime
binding = runtime.prepare_deterministic_controls(True)
os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":16:8"
import torch
try:
    runtime.apply_deterministic_controls(binding)
except RuntimeError as error:
    assert "workspace binding changed" in str(error)
else:
    raise AssertionError("Workspace drift was accepted")
assert not torch.cuda.is_initialized()
print(json.dumps({"workspace_drift_rejected": True}))
''')
    assert value["workspace_drift_rejected"]
