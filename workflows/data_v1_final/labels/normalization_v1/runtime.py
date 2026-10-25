"""Isolated final-fit runtime. Registered streaming sources are never modified."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

STREAM = Path(__file__).resolve().parents[1] / "streaming_v1"
sys.path.insert(0, str(STREAM))
from support import (budget, digest, identity, legacy, load, new_root, ref, require,
                     root_guard, save, sqlstr, path_list, write_blob, unique_bytes)
from calibration import (RadixCounts, TSQR, advance, initial_queries, merge_qr,
                         WinsorMoments)
from compact import encode, restore_mask


def canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode()


def semantic_sha(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def read_tables(pins, columns=None):
    import pyarrow.parquet as pq
    for pin in pins:
        path = require(pin)
        for batch in pq.ParquetFile(path).iter_batches(batch_size=4096, columns=columns,
                                                     use_threads=False):
            yield from batch.to_pylist()


def connect(root, memory="12GB", spill="16GiB"):
    import duckdb
    db = duckdb.connect()
    db.execute("SET threads=16")
    db.execute("SET memory_limit=" + sqlstr(memory))
    temporary = Path(root) / "duckdb_spill"
    temporary.mkdir()
    db.execute("SET temp_directory=" + sqlstr(temporary))
    db.execute("SET max_temp_directory_size=" + sqlstr(spill))
    return db


def guard(config_path, intent_path):
    cfg = load(config_path)
    if cfg["schema"] != "FINAL_NORMALIZATION_CONFIG_V1" or cfg["workers"] != 16:
        raise ValueError("UNKNOWN_FINAL_FIT_CONFIGURATION")
    proof = root_guard(intent_path, config_path, cfg["output_cap_bytes"],
                       cfg["wall_seconds"])
    assert_final_allocation(cfg, proof)
    if os.environ.get("CUDA_VISIBLE_DEVICES") != "":
        raise ValueError("FINAL_FIT_REQUIRES_EXPLICIT_CPU_ONLY_ENVIRONMENT")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS"):
        if os.environ.get(name) != "1":
            raise ValueError("SINGLE_THREAD_WORKER_ENVIRONMENT_REQUIRED:" + name)
    return cfg, proof


def assert_final_allocation(cfg, proof):
    """The shared streaming guard's 32GiB minimum is only a generic baseline."""
    requested = proof["request"]
    minimum = max(64, int(cfg["memory_gib"]))
    if (requested["memory_gib"] < minimum or int(os.environ.get("SLURM_MEM_PER_NODE", "0")) < minimum * 1024
            or requested["cpus"] < 16 or int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) < 16):
        raise ValueError("FINAL_FIT_REQUIRES_REQUEST_AND_ACTUAL_64_GIB_16_CPU_ALLOCATION")


def fail(root, exc):
    save(Path(root) / "failure.json", {
        "status": "FINAL_FIT_FAILED_PARTIAL_EVIDENCE_PRESERVED_NO_AUTORETRY",
        "type": type(exc).__name__, "error": str(exc), "normalization_completed": False})
