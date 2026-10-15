"""Small mocked observations; no GPU allocation, model or training work."""
import gc
import json
import weakref

import pytest
import torch

from phychem_mfm.phase1 import memory_observation as observation


CUDA_COUNTERS = ("memory_allocated", "memory_reserved", "max_memory_allocated", "max_memory_reserved")
CUDA_MUTATIONS = ("reset_peak_memory_stats", "reset_accumulated_memory_stats", "empty_cache",
                  "synchronize", "set_device", "init", "current_device", "is_available",
                  "manual_seed", "manual_seed_all")


def forbidden(*args, **kwargs):
    raise AssertionError("Observer must not call this CUDA API")


@pytest.fixture
def fixed_rss(monkeypatch):
    monkeypatch.setattr(observation, "_rss_kib", lambda: 12345)


def test_cpu_never_queries_cuda_and_copies_metadata(tmp_path, monkeypatch, fixed_rss):
    for name in CUDA_COUNTERS + CUDA_MUTATIONS:
        monkeypatch.setattr(torch.cuda, name, forbidden)
    rng = torch.get_rng_state().clone()
    metadata = {"update": 0, "flags": [True, None, {"loss": 1.25}], "name": "几何"}
    path = tmp_path / "memory.jsonl"
    with observation.MemoryObservation(path, device="cpu") as writer:
        row = writer.record("before_forward", metadata)
        assert writer.records_written == 1
        assert writer.bytes_written == path.stat().st_size
        metadata["flags"][2]["loss"] = 999.
        assert row["metadata"]["flags"][2]["loss"] == 1.25
        row["metadata"]["flags"].append("returned-row mutation")
        stored = json.loads(path.read_text())  # Read succeeds before close: flush.
        assert stored["metadata"]["flags"] == [True, None, {"loss": 1.25}]
        assert stored["cuda_memory_status"] == "not_queried_cpu"
        assert all(stored[name + "_bytes"] is None for name in CUDA_COUNTERS)
        assert stored["rss_kib"] == 12345 and stored["rss_unit"] == "KiB"
        assert stored["sampling_only"] is True
        assert stored["elapsed_seconds"] >= 0
    assert writer.closed
    assert torch.equal(rng, torch.get_rng_state())


def test_cuda_reads_only_four_counters_with_explicit_device(tmp_path, monkeypatch, fixed_rss):
    calls = []
    for name in CUDA_MUTATIONS:
        monkeypatch.setattr(torch.cuda, name, forbidden)
    for name, value in zip(CUDA_COUNTERS, (17, 29, 37, 41)):
        def query(device, name=name, value=value):
            calls.append((name, device))
            return value
        monkeypatch.setattr(torch.cuda, name, query)
    rng = torch.get_rng_state().clone()
    device = torch.device("cuda:0")
    with observation.MemoryObservation(tmp_path / "gpu.jsonl", device=device) as writer:
        row = writer.record("after_backward", {"base_indices": [3, 7]})
    assert calls == [(name, device) for name in CUDA_COUNTERS]
    assert [row[name + "_bytes"] for name in CUDA_COUNTERS] == [17, 29, 37, 41]
    assert row["cuda_memory_status"] == "sampled" and row["gpu_memory_unit"] == "bytes"
    assert torch.equal(rng, torch.get_rng_state())


def test_refuse_existing_file_or_symlink_without_overwriting(tmp_path):
    target = tmp_path / "old.jsonl"
    target.write_bytes(b"unique evidence\n")
    with pytest.raises(FileExistsError):
        observation.MemoryObservation(target, device="cpu")
    link = tmp_path / "link.jsonl"
    link.symlink_to(target)
    with pytest.raises(FileExistsError):
        observation.MemoryObservation(link, device="cpu")
    dangling = tmp_path / "dangling.jsonl"
    dangling.symlink_to(tmp_path / "missing.jsonl")
    with pytest.raises(FileExistsError):
        observation.MemoryObservation(dangling, device="cpu")
    assert target.read_bytes() == b"unique evidence\n"


@pytest.mark.parametrize("field,value", [("max_records", 0), ("max_bytes", -1), ("max_records", True), ("max_bytes", 1.5)])
def test_invalid_budget_does_not_create_file(tmp_path, field, value):
    path = tmp_path / "not_created.jsonl"
    with pytest.raises(ValueError):
        observation.MemoryObservation(path, device="cpu", **{field: value})
    assert not path.exists()


def test_record_and_byte_budgets_fail_before_growth(tmp_path, fixed_rss):
    path = tmp_path / "one.jsonl"
    with observation.MemoryObservation(path, device="cpu", max_records=1) as writer:
        writer.record("initial")
        old = path.read_bytes()
        with pytest.raises(observation.MemoryObservationLimitError, match="record budget"):
            writer.record("forbidden")
        assert path.read_bytes() == old
    small = tmp_path / "small.jsonl"
    with observation.MemoryObservation(small, device="cpu", max_bytes=1024) as writer:
        writer.record("initial")
        old = small.read_bytes()
        with pytest.raises(observation.MemoryObservationLimitError, match="byte budget"):
            writer.record("oversized", {"padding": "x" * 1024})
        assert small.read_bytes() == old and small.stat().st_size <= 1024


@pytest.mark.parametrize("metadata", [(1, 2), {1: "bad key"}, {"number": float("nan")}, {"value": object()}])
def test_reject_non_json_metadata_before_query_or_write(tmp_path, monkeypatch, metadata):
    monkeypatch.setattr(observation, "_rss_kib", forbidden)
    with observation.MemoryObservation(tmp_path / "invalid.jsonl", device="cpu") as writer:
        with pytest.raises((TypeError, ValueError)):
            writer.record("invalid", metadata)
        assert writer.records_written == writer.bytes_written == 0


def test_reject_tensor_without_retaining_it(tmp_path, fixed_rss):
    tensor = torch.tensor([1.])
    ref = weakref.ref(tensor)
    with observation.MemoryObservation(tmp_path / "tensor.jsonl", device="cpu") as writer:
        with pytest.raises(TypeError, match="no Tensor"):
            writer.record("invalid", {"nested": [{"tensor": tensor}]})
        del tensor
        gc.collect()
        assert ref() is None
        assert writer.records_written == 0 and writer.bytes_written == 0


def test_query_error_propagates_and_context_closes(tmp_path, monkeypatch, fixed_rss):
    def failed(device):
        raise RuntimeError("CUDA query failure")
    monkeypatch.setattr(torch.cuda, "memory_allocated", failed)
    writer = observation.MemoryObservation(tmp_path / "failed.jsonl", device="cuda:0")
    with pytest.raises(RuntimeError, match="CUDA query failure"):
        with writer:
            writer.record("query")
    assert writer.closed and writer.path.stat().st_size == 0


class FailingStream:
    def __init__(self, stream, fail_at):
        self.stream, self.fail_at = stream, fail_at
    @property
    def closed(self):
        return self.stream.closed
    def write(self, payload):
        if self.fail_at == "write":
            raise OSError("write failure")
        if self.fail_at == "short":
            return self.stream.write(payload[:7])
        return self.stream.write(payload)
    def flush(self):
        if self.fail_at == "flush":
            raise OSError("flush failure")
        return self.stream.flush()
    def close(self):
        self.stream.close()
        if self.fail_at == "close":
            raise OSError("close failure")


@pytest.mark.parametrize("failure", ["write", "flush", "short"])
def test_io_failure_propagates_and_prevents_retry(tmp_path, fixed_rss, failure):
    writer = observation.MemoryObservation(tmp_path / "io.jsonl", device="cpu", max_bytes=2048)
    writer._stream = FailingStream(writer._stream, failure)
    with pytest.raises(OSError):
        writer.record("failure")
    with pytest.raises(RuntimeError, match="rather than retry"):
        writer.record("retry")
    writer.close()
    writer.close()
    assert writer.closed and writer.path.stat().st_size <= writer.max_bytes
    with pytest.raises(ValueError, match="closed"):
        writer.record("after_close")


def test_close_failure_is_not_swallowed(tmp_path, fixed_rss):
    writer = observation.MemoryObservation(tmp_path / "close.jsonl", device="cpu")
    writer._stream = FailingStream(writer._stream, "close")
    with pytest.raises(OSError, match="close failure"):
        with writer:
            writer.record("sample")
    assert writer.closed
