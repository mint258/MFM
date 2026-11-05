"""New immutable per-molecule packets with durable no-retry scientific events.

The allocation runner must supply resource guards and work claiming. This file
never submits a job, retries a molecule or changes an existing output directory.
"""
from __future__ import annotations

import gzip
import io
import hashlib
import json
import os
import time
from pathlib import Path
from .core import canonical, create_cache, export_cache, recipe_sha, source_identity, validate_cache
from .call_timing import CallTimings, TimedKernel


def reference(path):
    path = Path(path).absolute()
    return {"path": str(path), "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def read_json(path):
    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            return json.load(stream)
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_new(path, value, maximum_directory_bytes=None):
    path = Path(path)
    data = canonical(value) + b"\n"
    if path.suffix == ".gz":
        buffer = io.BytesIO()
        with gzip.GzipFile(filename="", mode="wb", fileobj=buffer, mtime=0) as packed:
            packed.write(data)
        data = buffer.getvalue()
    if maximum_directory_bytes is not None:
        used = sum(p.stat().st_size for p in path.parent.iterdir() if p.is_file())
        if used + len(data) > maximum_directory_bytes:
            raise RuntimeError('MOLECULE_OUTPUT_CAP_RETAINED_NO_RETRY')
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return reference(path)

class Journal:
    def __init__(self, path, maximum_directory_bytes=None):
        self.path = Path(path)
        self.maximum_directory_bytes = maximum_directory_bytes
        self.stream = Path(path).open("xb")
        self.timing = None
        self.ordinal = 0
        self.previous = "0" * 64

    def emit(self, event):
        if self.timing is not None:event = self.timing.annotate(event)
        record = {"ordinal": self.ordinal, "previous_sha256": self.previous, "event": event}
        raw = canonical(record)
        if self.maximum_directory_bytes is not None:
            other = sum(p.stat().st_size for p in self.path.parent.iterdir() if p.is_file() and p != self.path)
            if other + self.stream.tell() + len(raw) + 1 > self.maximum_directory_bytes:
                raise RuntimeError('MOLECULE_OUTPUT_CAP_RETAINED_NO_RETRY')
        self.stream.write(raw + b"\n")
        self.stream.flush()
        os.fsync(self.stream.fileno())
        self.previous = hashlib.sha256(raw).hexdigest()
        self.ordinal += 1

    def close(self):
        self.stream.close()


def read_events(path):
    """Whole closed journal proof. Partial original journals remain untouched."""
    previous = "0" * 64
    events = []
    with Path(path).open("rb") as stream:
        for ordinal, raw in enumerate(stream):
            if not raw.endswith(b"\n"):
                raise ValueError("INTERRUPTED_JOURNAL_NO_AUTOMATIC_SCIENCE_RETRY")
            record = json.loads(raw)
            if (record["ordinal"] != ordinal or record["previous_sha256"] != previous
                    or canonical(record) + b"\n" != raw):
                raise ValueError("JOURNAL_CHAIN_CHANGED")
            previous = hashlib.sha256(raw[:-1]).hexdigest()
            events.append(record["event"])
    return events


def run_one(source, output, *, kernel=None, prior_cache_path=None,
            previous_packet_path=None, export_limit=3, allow_future_extension=False,
            checkpoint=lambda: None, maximum_molecule_output_bytes=64<<20):
    """Current caller uses export_limit=3. Extension only consumes saved cache.

    An interrupted directory is never deleted or reopened. Reusing its work
    requires an independently validated closed cache; absent that cache, the
    source remains explicit UNKNOWN, not silently tried again.
    """
    began=time.monotonic();cpu_began=time.process_time()
    if export_limit > 3 and not allow_future_extension:
        raise ValueError("INITIAL_EXPORT_MAXIMUM_THREE")
    if previous_packet_path is not None and prior_cache_path is None:
        raise ValueError("PRIOR_PACKET_REQUIRES_ITS_CLOSED_CANDIDATE_CACHE")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    if kernel is None:
        from .native import NativeKernel
        kernel = NativeKernel()
    journal = Journal(output / "events.jsonl", maximum_molecule_output_bytes)
    journal.timing = CallTimings()
    kernel = TimedKernel(kernel, journal.timing)
    try:
        if prior_cache_path is None:
            cache = create_cache(source, kernel, journal.emit, checkpoint)
            cache_reference = write_new(output / "candidate_cache.json.gz", cache, maximum_molecule_output_bytes)
        else:
            cache = validate_cache(read_json(prior_cache_path), source)
            cache_reference = reference(prior_cache_path)
            journal.emit({"phase": "closed_cache_adopted_without_native_calls", "reference": cache_reference,
                          "cache_content_sha256": cache["cache_content_sha256"]})
        previous = None if previous_packet_path is None else read_json(previous_packet_path)
        packet = export_cache(cache, source, kernel, limit=export_limit,
            previous_packet=previous, allow_future_extension=allow_future_extension, emit=journal.emit)
        packet_reference = write_new(output / "selected_packet.json.gz", packet, maximum_molecule_output_bytes)
    finally:
        journal.close()
    events = read_events(output / "events.jsonl")
    manifest = {"schema": "PUBCHEM_UFF3_MOLECULE_OUTPUT_MANIFEST_V1",
        "source_identity_sha256": source_identity(source), "recipe_sha256": recipe_sha(),
        "dataset_version": "v2_candidate", "training_eligible": False,
        "candidate_cache": cache_reference, "selected_packet": packet_reference,
        "events": reference(output / "events.jsonl"), "event_count": len(events),
        "export_limit": export_limit, "actual_conformers": packet["actual_conformers"],
        "insufficient_conformers": packet["insufficient_conformers"],
        "closed_cache_reused_without_UFF": prior_cache_path is not None,
        "state": packet["state"], "new_QM_calls": 0,
        "error": cache.get('error'), "source_contract_hold": cache.get('source_contract_hold',False),
        "producer_job_id": os.environ.get('SLURM_JOB_ID'),
        "embedding_calls": cache['embedding_calls'], "optimizer_calls": cache['optimizer_calls'],
        "native_candidate_successes": len(cache['valid_candidates']),
        "native_generation_wall_seconds": cache['elapsed_seconds'],
        "worker_wall_seconds": time.monotonic()-began,
        "worker_CPU_seconds": time.process_time()-cpu_began}
    write_new(output / "manifest.json", manifest, maximum_molecule_output_bytes)
    return manifest