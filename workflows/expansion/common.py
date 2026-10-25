"""Small provenance helpers. No implicit network, package installation or cleanup."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time

SCHEMA = "pubchem_expansion_preparation_v1"
ARTIFACT_ROOT = Path("/share/home/zixiao/descriptor_analysis/runs/data_v1_20261025/artifacts/expansion")
KEY_RE = re.compile(r"[A-Z]{14}-[A-Z]{10}-[A-Z]\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def reference(path):
    p = Path(path)
    return {"path": str(p.absolute()), "bytes": p.stat().st_size, "sha256": digest(p)}


def verify(ref):
    p = Path(ref["path"])
    require(p.is_absolute() and p.is_file(), "Missing absolute input reference: " + str(p))
    require(type(ref["bytes"]) is int and p.stat().st_size == ref["bytes"], "Input byte count differs: " + str(p))
    require(SHA_RE.fullmatch(ref["sha256"]) is not None and digest(p) == ref["sha256"], "Input SHA256 differs: " + str(p))
    return p


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_new(path, value):
    """Never overwrite an existing result or remove a partial failure artifact."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def external_output(path):
    p = Path(path).absolute()
    require(p.is_relative_to(ARTIFACT_ROOT), "Production output must be under the external expansion artifact root")
    require(not p.exists(), "Output exists; preserve it and use a new path")
    return p


def stable_hash(domain, seed, identity):
    return hashlib.sha256(json.dumps([domain, int(seed), identity], separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def wp5_key(key):
    require(isinstance(key, str) and KEY_RE.fullmatch(key) is not None, "Invalid full InChIKey")
    return key[:14] + ":" + key[-1]


def check_quota(receipt_path, projected_new_bytes, reserve=200_000_000_000):
    """A fresh login-node user-quota observation is required; df is insufficient."""
    q = load(receipt_path)
    require(q.get("schema") == "expansion_user_quota_receipt_v1", "Wrong quota receipt schema")
    require(q.get("username") == "zixiao" and q.get("uid") == 1278, "Wrong quota owner")
    require(q.get("basis") == "login_node_quota" and q.get("returncode") == 0, "Actual login-node quota required")
    require(0 <= time.time() - q["observed_unix_seconds"] <= 300, "Quota observation older than five minutes")
    require(type(q["available_bytes"]) is int and type(projected_new_bytes) is int and projected_new_bytes >= 0, "Invalid byte budgets")
    require(q["available_bytes"] - projected_new_bytes >= reserve, "STOP: projected user-quota reserve below 200 GB")
    require(SHA_RE.fullmatch(q.get("raw_stdout_sha256", "")) is not None, "Unpinned raw quota output")
    require(hashlib.sha256(q["raw_stdout"].encode()).hexdigest() == q["raw_stdout_sha256"], "Quota raw-output digest differs")
    rows = re.findall(r"^\s*/dev/sda1\s+(\d+)\s+(\d+)\s+(\d+)(?:\s|$)", q["raw_stdout"], re.MULTILINE)
    require(len(rows) == 1, "Expected one numeric quota -v /dev/sda1 row in KiB")
    used, soft, hard = map(int, rows[0])
    limits = [value for value in (soft, hard) if value > 0]
    require(limits and q["available_bytes"] == max(0, min(limits) - used) * 1024,
            "Available quota differs from real positive soft/hard limits")
    return q


def require_compute(workers=1):
    import socket
    node = socket.gethostname().split(".")[0]
    require(node.startswith("compute-0-"), "No dataset computation on the login node")
    if workers > 1:
        require(os.environ.get("SLURM_JOB_ID") and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= workers >= 16,
                "Scientific screening requires a Slurm allocation with >=16 active workers")
    return node
