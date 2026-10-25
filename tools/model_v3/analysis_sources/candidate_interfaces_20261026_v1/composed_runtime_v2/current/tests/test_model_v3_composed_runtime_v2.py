"""CPU-only UUID/parser and mocked admission checks, not actual CUDA evidence."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

import pytest
import torch


ROOT = Path(__file__).absolute().parents[2]
specification = importlib.util.spec_from_file_location("composed_eq_runtime_v2_cli",
    ROOT/"tools/model_v3/check_composed_equivariance.py")
cli = importlib.util.module_from_spec(specification)
specification.loader.exec_module(cli)
IDENTITY = uuid.UUID("12345678-90ab-cdef-1234-567890abcdef")
CANONICAL = "GPU-"+str(IDENTITY)
OTHER = uuid.UUID("87654321-90ab-cdef-1234-567890abcdef")


@pytest.mark.parametrize("value", (IDENTITY, str(IDENTITY), CANONICAL,
    CANONICAL.upper(), "gpu-"+str(IDENTITY), IDENTITY.bytes, bytearray(IDENTITY.bytes)))
def test_standard_representations_preserve_all128_identity_bits(value):
    assert cli.canonical_gpu_uuid(value) == CANONICAL
    observation = cli.gpu_uuid_observation(value)
    assert observation["raw_type"] == type(value).__module__+"."+type(value).__qualname__
    assert observation["raw_repr"] == repr(value) and observation["canonical"] == CANONICAL
    json.dumps(observation, allow_nan=False)


class StringableImpostor:
    def __str__(self):
        raise AssertionError("Unknown objects must not be converted to strings to authorize a GPU")


@pytest.mark.parametrize("value", (None, 0, True, "", "GPU-1234", IDENTITY.hex,
    " "+CANONICAL, CANONICAL+"\n", "{"+str(IDENTITY)+"}", "urn:uuid:"+str(IDENTITY),
    "MIG-"+str(IDENTITY), CANONICAL+","+CANONICAL, "GPU-"+"-"*36,
    "GPU-12345678-90ab-cdef-1234-567890abcdeg", b"x"*15, b"x"*17,
    str(IDENTITY).encode(), StringableImpostor()))
def test_partial_invalid_and_unregistered_representations_are_rejected(value):
    with pytest.raises(ValueError): cli.canonical_gpu_uuid(value)
    with pytest.raises(ValueError, match="raw_type"):
        cli.gpu_uuid_observation(value)


def mocked_gpu_runtime(monkeypatch, actual_uuid=IDENTITY):
    monkeypatch.setattr(cli.socket, "gethostname", lambda: "compute-0-20")
    monkeypatch.setenv("SLURMD_NODENAME", "compute-0-20")
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "16")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", CANONICAL)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: True)
    monkeypatch.setattr(torch.cuda, "device_count", lambda: 1)
    monkeypatch.setattr(torch.cuda, "get_device_properties", lambda index:
        SimpleNamespace(uuid=actual_uuid, name="CPU_MOCK_NOT_A_REAL_CUDA_MEASUREMENT"))
    return {"expected_node": "compute-0-20", "gpu_uuid": CANONICAL, "device": "cuda:0"}


@pytest.mark.parametrize("actual", (IDENTITY, str(IDENTITY), CANONICAL, IDENTITY.bytes))
def test_mocked_admission_accepts_equivalent_full_uuid_formats_but_is_not_cuda_evidence(monkeypatch, actual):
    before = torch.cuda.is_initialized()
    request = mocked_gpu_runtime(monkeypatch, actual)
    result = cli.admit_runtime(request)
    assert result["gpu_uuid"] == result["request_gpu_uuid_canonical"] == CANONICAL
    assert result["gpu_uuid_observation"]["raw_repr"] == repr(actual)
    assert result["gpu_name"] == "CPU_MOCK_NOT_A_REAL_CUDA_MEASUREMENT"
    assert torch.cuda.is_initialized() == before


@pytest.mark.parametrize("actual", (OTHER, str(OTHER), OTHER.bytes, IDENTITY.bytes_le))
def test_mocked_admission_rejects_other_physical_uuid_and_wrong_byte_order(monkeypatch, actual):
    request = mocked_gpu_runtime(monkeypatch, actual)
    with pytest.raises(ValueError, match="physical UUID differs") as error:
        cli.admit_runtime(request)
    assert "raw_type" in str(error.value) and "canonical" in str(error.value)
    assert CANONICAL in str(error.value)


@pytest.mark.parametrize("guard", ("cvd", "count", "availability", "node", "cpus", "job"))
def test_existing_scheduler_and_single_visible_device_guards_remain_strict(monkeypatch, guard):
    request = mocked_gpu_runtime(monkeypatch)
    if guard == "cvd": monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "GPU-"+str(OTHER))
    elif guard == "count": monkeypatch.setattr(torch.cuda, "device_count", lambda: 2)
    elif guard == "availability": monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    elif guard == "node": monkeypatch.setenv("SLURMD_NODENAME", "compute-0-21")
    elif guard == "cpus": monkeypatch.setenv("SLURM_CPUS_PER_TASK", "8")
    else: monkeypatch.delenv("SLURM_JOB_ID")
    with pytest.raises(ValueError): cli.admit_runtime(request)


def test_cpu_admission_never_queries_cuda_and_does_not_claim_gpu_execution(monkeypatch):
    monkeypatch.setattr(cli.socket, "gethostname", lambda: "compute-0-12")
    monkeypatch.setenv("SLURMD_NODENAME", "compute-0-12")
    monkeypatch.setenv("SLURM_JOB_ID", "123456")
    monkeypatch.setenv("SLURM_CPUS_PER_TASK", "16")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    def forbidden(*args): raise AssertionError("CPU admission must not query/init CUDA")
    for name in ("is_available", "device_count", "get_device_properties"):
        monkeypatch.setattr(torch.cuda, name, forbidden)
    result = cli.admit_runtime({"expected_node": "compute-0-12", "device": "cpu", "gpu_uuid": None})
    assert result["device"] == "cpu" and result["gpu_uuid"] is None


def test_new_request_binds_runtime_policy_new_sources_and_rejects_old_uuid_shape():
    before = torch.cuda.is_initialized()
    request = cli.source_request("cuda:0", "compute-0-20", gpu_uuid=CANONICAL)
    assert request["gpu_uuid"] == request["gpu_uuid_canonical"] == CANONICAL
    assert request["runtime_uuid_policy"] == cli.RUNTIME_UUID_POLICY
    assert all(name in request["source_files"] for name in cli.RUNTIME_SOURCE_FILES)
    with pytest.raises(ValueError): cli.source_request("cuda:0", "compute-0-20", gpu_uuid="GPU-"+"-"*36)
    assert torch.cuda.is_initialized() == before
