"""Metadata, immutable output, and runtime guards for the new conformer stage."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import sys
import time
from datetime import datetime

sys.dont_write_bytecode = True
ALLOWED_NODES = {f"compute-0-{i}" for i in range(14, 20)}
OUTPUT_ROOT = None
OUTPUT_CAP = None


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            value.update(block)
    return value.hexdigest()


def reference(path):
    path = Path(path).absolute()
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": digest(path)}


def require_pin(pin):
    path = Path(pin["path"])
    if not path.is_absolute() or not path.is_file() or path.is_symlink():
        raise ValueError("PIN_REQUIRES_ABSOLUTE_REGULAR_FILE:" + str(path))
    if "bytes" in pin and path.stat().st_size != pin["bytes"]:
        raise ValueError("PIN_SIZE_MISMATCH:" + str(path))
    if digest(path) != pin["sha256"]:
        raise ValueError("PIN_SHA256_MISMATCH:" + str(path))
    return path


def write_json_new(path, value):
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False,
                         indent=2).encode("utf-8") + b"\n"
    prewrite_guard(path, len(payload))
    with Path(path).open("xb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config["schema"] != "DATA_V1_SPRIME_FILL_PILOT_V1":
        raise ValueError("UNKNOWN_CONFIG_SCHEMA")
    if config["candidate_multiplier"] != 10 or config["max_candidates"] != 300:
        raise ValueError("GUIDE_REQUIRES_10N_CANDIDATES_CAPPED_AT_300")
    if config["retry_embedding_max_iterations"] <= 200:
        raise ValueError("RETRY_EMBEDDING_ATTEMPTS_MUST_EXCEED_OLD_200")
    required = {"uff_max_iterations": 2000, "uff_energy_tolerance": 1e-6,
                "uff_force_tolerance": 1e-4, "dedup_rmsd_A": 0.5}
    if any(config[name] != value for name, value in required.items()):
        raise ValueError("FROZEN_UFF_OR_RMSD_RECIPE_CHANGED")
    for pin in config["science_source_pins"]:
        require_pin(pin)
    return config


def new_output_directory(path, config):
    global OUTPUT_ROOT, OUTPUT_CAP
    root, path = Path(config["external_output_root"]), Path(path)
    if not path.is_absolute() or path == root or root not in path.parents:
        raise ValueError("OUTPUT_MUST_BE_NEW_CHILD_OF_CONFIGURED_EXTERNAL_ROOT")
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("OUTPUT_SYMLINK_ANCESTOR_REJECTED")
    path.mkdir(parents=True, exist_ok=False, mode=0o700)
    OUTPUT_ROOT, OUTPUT_CAP = path, int(config["max_output_bytes"])
    return path


def prewrite_guard(path, additional_bytes, reserve_bytes=0):
    """Bound writes before opening a new output; include all files/directories."""
    if OUTPUT_ROOT is None:
        return
    path = Path(path)
    if OUTPUT_ROOT not in path.parents:
        raise ValueError("OUTPUT_WRITE_OUTSIDE_OWN_RUN")
    present = OUTPUT_ROOT.stat().st_size
    for item in OUTPUT_ROOT.rglob("*"):
        if item.is_symlink():
            raise ValueError("UNEXPECTED_OUTPUT_SYMLINK")
        present += item.stat().st_size
    if present + int(additional_bytes) + int(reserve_bytes) > OUTPUT_CAP:
        raise RuntimeError("OUTPUT_CAP_PREWRITE_REJECTION")


def write_parquet_new(path, table):
    import pyarrow as pa
    import pyarrow.parquet as pq
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="zstd", row_group_size=4096)
    buffer = sink.getvalue()
    prewrite_guard(path, buffer.size, reserve_bytes=2 << 20)
    with Path(path).open("xb") as stream:
        stream.write(memoryview(buffer))
        stream.flush()
        os.fsync(stream.fileno())


def require_preflight(path, config_path, config):
    """Consume Root's submit_reviewed.py intent/receipt, without a second approval."""
    receipt = json.loads(Path(path).read_text(encoding="utf-8"))
    request = receipt["request"]
    pins = request["source_references"]
    if reference(config_path) not in pins:
        raise ValueError("ROOT_PREFLIGHT_CONFIG_SHA_MISMATCH")
    age = time.time() - datetime.fromisoformat(receipt["observed_at"]).timestamp()
    if not 0 <= age <= 3600:
        raise ValueError("ROOT_PREFLIGHT_OLDER_THAN_ONE_HOUR")
    if request["node"] != socket.gethostname().split(".")[0]:
        raise ValueError("ROOT_PREFLIGHT_NODE_MISMATCH")
    if not isinstance(receipt["existing_jobs_all_users"], list):
        raise ValueError("ALL_USERS_MEMORY_CHECK_REQUIRED")
    real_memory = re.search(r"(?:^|\s)RealMemory=(\d+)(?:\s|$)", receipt["node_metadata"])
    if real_memory is None:
        raise ValueError("NODE_REAL_MEMORY_MISSING")
    if receipt["committed_memory_mib"] + request["memory_gib"] * 1024 > 0.85 * int(real_memory[1]):
        raise ValueError("DECLARED_MEMORY_EXCEEDS_85_PERCENT")
    if request["estimated_peak_output_bytes"] < config["max_output_bytes"]:
        raise ValueError("ROOT_OUTPUT_ESTIMATE_SMALLER_THAN_PILOT_CAP")
    if receipt["account_free_bytes"] - config["max_output_bytes"] < config["quota_reserve_bytes"]:
        raise ValueError("QUOTA_REMAINING_WOULD_FALL_BELOW_200_GB")
    return reference(path)


def runtime_guard(workers=16, metadata_only=False):
    node = socket.gethostname().split(".")[0]
    cpus = int(os.environ.get("SLURM_CPUS_PER_TASK", "0"))
    allowed = ALLOWED_NODES | ({"compute-0-20"} if metadata_only else set())
    if not os.environ.get("SLURM_JOB_ID") or node not in allowed:
        raise RuntimeError("CONFORMER_COMPUTATION_REQUIRES_SLURM_ON_14_TO_19")
    if workers < 16 or cpus < workers:
        raise RuntimeError("AT_LEAST_16_ALLOCATED_AND_USED_CPU_WORKERS_REQUIRED")
    return {"job_id": os.environ["SLURM_JOB_ID"], "hostname": node,
            "allocated_cpus": cpus, "workers": workers}


def load_science(config):
    """Import the SHA-pinned old functions; never execute the old main/queue."""
    path = Path(config["science_source_pins"][0]["path"])
    for pin in config["science_source_pins"]:
        require_pin(pin)
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location("_data_v1_pinned_sprime_v6", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def version_tuple(value):
    parts = value.split(".")
    if not all(part.isdigit() for part in parts):
        raise ValueError("NON_NUMERIC_RDKIT_VERSION:" + value)
    return tuple(int(part) for part in parts)


def geometry_sha(numbers, coordinates):
    import numpy as np
    z = np.asarray(numbers, dtype="<i8")
    xyz = np.asarray(coordinates, dtype="<f8")
    if xyz.shape != (len(z), 3) or not np.isfinite(xyz).all():
        raise ValueError("GEOMETRY_SHAPE_OR_FINITE_CHECK_FAILED")
    return hashlib.sha256(z.tobytes() + xyz.tobytes()).hexdigest()
