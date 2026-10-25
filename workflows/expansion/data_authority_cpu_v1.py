"""Exact reviewed node20 raw producer with a genuine CPU consumer location.

Only cross-node st_dev portability is allowed. Inode/mtime/size/UID must match
the actual prefix4520427 frame, and complete same-SHA bytes are re-read on CPU.
Current CPU before/after frames include st_dev and must remain fully identical.
"""
from pathlib import Path
import hashlib
import os
import socket

from .common import load, require, verify
from workflows.data_v1_final.execution.cpu_analysis_v1 import runtime as cpu_runtime


def allowed_cpu_node(node):
    return node in {"compute-0-2", *(f"compute-0-{i}" for i in range(8, 20))}


def file_stat(path):
    s = Path(path).stat()
    return {"device": s.st_dev, "inode": s.st_ino, "size": s.st_size, "mtime_ns": s.st_mtime_ns, "uid": s.st_uid}


def portable_frame(frame):
    return {k: frame[k] for k in ("inode", "size", "mtime_ns", "uid")}


def authorize_data(plan, submission, refs, *, node):
    actual_node = socket.gethostname().split(".")[0]
    request = submission["request"]
    require(allowed_cpu_node(actual_node) and node == actual_node and os.getuid() == 1278 and
            request["node"] == actual_node and request["pilot"] is True and request["partition"] == "cpu" and
            request["scope_key"] == "prefix_feature_three_cid" and
            request["resource_policy"] == "CPU_BOUNDED_TEST_LIVE_MEMORY_V1" and
            request["root_review"]["status"] == "APPROVED", "Real reviewed CPU-only consumer required")
    small = {r["path"]: r for r in request["source_references"]}
    raw_ref, previous_ref = plan["raw_receipt"], plan["prefix_receipt"]
    require(plan["authorized_data_pin_jobs"] == ["4520348"] and plan["data_authorization_receipts"] == [raw_ref] and
            plan["allow_small_fixture_legacy_authority"] is False and len(refs) == 1 and
            request["data_references"] == refs, "Only the same exact reviewed raw producer/body may be consumed")
    for ref in (raw_ref, previous_ref):
        require(ref["bytes"] <= 2 * 1024 ** 2 and small.get(ref["path"]) == ref,
                "Root must bind exact small raw and original-consumer evidence")
        verify(ref)
    raw, previous = load(raw_ref["path"]), load(previous_ref["path"])
    require(raw["schema"] == "pubchem_download_complete_v1" and raw["acquisition_schema"] == "pubchem_16_range_acquisition_v1" and
            raw["status"] == "RAW_ACQUIRED_NO_CHEMICAL_SCREENING" and raw["job_id"] == "4520348" and
            raw["hostname"] == "compute-0-20" and raw["uid"] == 1278 and raw["file"] == refs[0] and
            raw["gzip"]["gzip_read_to_eof_crc_validated"] is True and raw["gzip"]["sha256"] == refs[0]["sha256"] and
            raw["gzip"]["compressed_bytes"] == refs[0]["bytes"] and len(raw["parts"]) == 16 and
            all(r["status"] == "COMPLETE" for r in raw["parts"]), "Exact completed sixteen-range node20 producer required")
    require(previous["schema"] == "PUBCHEM_BOUNDED_PREFIX_PILOT_V2" and previous["job_id"] == "4520427" and
            previous["node"] == "compute-0-20" and previous["uid"] == 1278 and
            previous["status"] == "BOUNDED_INPUT_PREFIX_PILOT_NOT_DECONTAMINATED" and
            previous["source_receipt"] == raw_ref, "Exact original node20 full-SHA consumer frame required")
    old = previous["data_authority"]["files"]
    require(len(old) == 1 and old[0]["reference"] == refs[0] and old[0]["producer_job_id"] == "4520348" and
            old[0]["authority"] == raw_ref, "Original physical-stat frame refers to another source")
    historical = old[0]["expected_stat"]
    before = file_stat(refs[0]["path"])
    require(historical["uid"] == 1278 and historical["size"] == refs[0]["bytes"] and
            portable_frame(before) == portable_frame(historical), "Raw inode/mtime/size/owner differs across nodes")
    return {"kind": "EXACT_NODE20_RAW_PRODUCER_CPU_CONSUMER_PORTABLE_DEVICE_V1", "consumer_node": actual_node,
            "producer_node": "compute-0-20", "producer_job_id": "4520348", "authority": raw_ref,
            "original_consumer_frame_receipt": previous_ref, "historical_stat": historical,
            "portable_fields": ["inode", "size", "mtime_ns", "uid"], "device_portability_only": True,
            "files": [{"reference": refs[0], "expected_stat": before}]}


def verify_authorized_data(authority):
    cpu_runtime.checkpoint()
    for item in authority["files"]:
        ref = item["reference"]
        require(file_stat(ref["path"]) == item["expected_stat"], "Raw CPU frame changed before full hash")
        h = hashlib.sha256()
        with Path(ref["path"]).open("rb") as stream:
            while True:
                cpu_runtime.checkpoint()
                block = stream.read(1 << 20)
                if not block:
                    break
                h.update(block)
        require(h.hexdigest() == ref["sha256"], "Current complete raw body SHA differs")
        require(file_stat(ref["path"]) == item["expected_stat"], "Raw CPU frame changed during full hash")


def verify_final_stats(authority):
    for item in authority["files"]:
        require(file_stat(item["reference"]["path"]) == item["expected_stat"], "Raw CPU frame changed during diagnostic")
