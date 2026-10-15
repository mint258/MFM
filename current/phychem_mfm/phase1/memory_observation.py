"""Bounded diagnostic sampling, not GPU/CPU resource isolation.

CUDA counters are asynchronous point samples in bytes; peaks are observed since
the caller last reset them (this observer never resets them). Linux VmRSS is
current process resident memory in KiB, not a quota or enforced limit.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import time

import torch


class MemoryObservationLimitError(RuntimeError):
    """A record would exceed the frozen observer count or byte budget."""


def _json_copy(value):
    """Copy only JSON primitives; reject Tensor/NumPy and non-JSON containers."""
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Observation metadata must contain finite JSON numbers")
        return value
    if type(value) is list:
        return [_json_copy(item) for item in value]
    if type(value) is dict:
        if any(type(key) is not str for key in value):
            raise TypeError("Observation metadata dictionary keys must be strings")
        return {key: _json_copy(item) for key, item in value.items()}
    raise TypeError("Observation metadata permits only JSON scalars/list/dict; no Tensor")


def _rss_kib() -> int:
    with Path("/proc/self/status").open("r", encoding="ascii") as stream:
        for line in stream:
            if line.startswith("VmRSS:"):
                fields = line.split()
                if len(fields) != 3 or fields[2] != "kB":
                    raise RuntimeError("Unexpected Linux VmRSS units")
                value = int(fields[1])
                if value < 0:
                    raise RuntimeError("Negative Linux VmRSS")
                return value  # Linux /proc 'kB' denotes 1024-byte KiB.
    raise RuntimeError("Linux /proc/self/status lacks VmRSS")


class MemoryObservation:
    """Exclusive JSONL writer; close after use, including on failed records.

    Metadata is copied into JSON-only values, with no retained caller object.
    Every successful record is flushed. A query/serialization error propagates;
    a write/flush failure also poisons this writer to prevent unsafe retries.
    """

    def __init__(self, path: str | Path, *, device: str | torch.device,
                 max_records: int = 8192, max_bytes: int = 8 * 1024**2):
        for name, value in (("max_records", max_records), ("max_bytes", max_bytes)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        self.device = torch.device(device)
        if self.device.type not in {"cpu", "cuda"}:
            raise ValueError("MemoryObservation supports only explicit CPU/CUDA devices")
        self.path = Path(path)
        if self.path.is_symlink():
            raise FileExistsError("Observation output cannot be a symlink")
        self.max_records, self.max_bytes = max_records, max_bytes
        self.records_written = self.bytes_written = 0
        self._failed = False
        self._started = time.monotonic()
        self._stream = self.path.open("xb")  # O_EXCL also rejects raced-in links/files.

    @property
    def closed(self) -> bool:
        return self._stream.closed

    def record(self, stage: str, metadata=None) -> dict:
        if self.closed:
            raise ValueError("Observation writer is closed")
        if self._failed:
            raise RuntimeError("Observation writer failed; close it rather than retry")
        if type(stage) is not str or not stage:
            raise ValueError("Observation stage must be a nonempty string")
        if self.records_written >= self.max_records:
            raise MemoryObservationLimitError("Observation record budget exceeded")
        copied = _json_copy({} if metadata is None else metadata)
        counters = dict.fromkeys(("memory_allocated_bytes", "memory_reserved_bytes",
                                  "max_memory_allocated_bytes", "max_memory_reserved_bytes"))
        if self.device.type == "cuda":
            for name in counters:
                value = getattr(torch.cuda, name.removesuffix("_bytes"))(self.device)
                if type(value) is not int or value < 0:
                    raise RuntimeError(f"Invalid CUDA memory counter: {name}")
                counters[name] = value
        row = dict(schema_version="phase1_memory_observation_v1", sequence=self.records_written,
                   stage=stage, device=str(self.device), elapsed_seconds=time.monotonic()-self._started,
                   rss_kib=_rss_kib(), rss_unit="KiB", rss_source="linux_proc_self_status_VmRSS",
                   cuda_memory_status="sampled" if self.device.type == "cuda" else "not_queried_cpu",
                   gpu_memory_unit="bytes", sampling_only=True, metadata=copied, **counters)
        payload = (json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
        if self.bytes_written + len(payload) > self.max_bytes:
            raise MemoryObservationLimitError("Observation byte budget exceeded")
        try:
            written = self._stream.write(payload)
            if written != len(payload):
                raise OSError("Short observation write")
            self._stream.flush()
        except BaseException:
            self._failed = True
            raise
        self.records_written += 1
        self.bytes_written += len(payload)
        return row

    def close(self) -> None:
        if not self.closed:
            self._stream.close()  # Close/flush errors propagate too.

    def __enter__(self):
        if self.closed:
            raise ValueError("Observation writer is closed")
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False
