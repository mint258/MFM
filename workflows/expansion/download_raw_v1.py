"""Slurm-owned, 16-part official PubChem raw acquisition; no chemistry parsing.

Exactly pinned HTTP ranges, bounded network concurrency, parallel part hashing,
streamed assembly and gzip EOF/CRC validation. All partials are retained.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import datetime as dt
import gzip
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import resource
import socket
import stat
import subprocess
import time
import urllib.error
import urllib.request

from .common import ARTIFACT_ROOT, check_quota, digest, dump_new, load, reference, require, verify
from .source import URL, opener, probe
from . import common as common_source, source as network_source

CAP = 4 * 1024 ** 3
_NETWORK = _STOP = _START = None


def ranges(size, parts=16):
    require(type(size) is int and size >= parts and parts == 16, "Exactly sixteen nonempty ranges required")
    return [(i * size // parts, (i + 1) * size // parts - 1) for i in range(parts)]


def quota_from_preflight(preflight):
    raw = preflight.get("quota")
    if raw is None:
        require(preflight.get("uid") == 1278 and isinstance(preflight.get("quota_raw"), str), "Invalid Root quota intent")
        raw = {"returncode": 0, "stdout": preflight["quota_raw"]}
    stdout = raw.get("stdout", "")
    require(raw.get("returncode", raw.get("rc")) == 0, "Actual quota query failed")
    require("Disk quotas for user zixiao (uid 1278)" in stdout, "Wrong user quota output")
    import re
    rows = re.findall(r"^\s*/dev/sda1\s+(\d+)\s+(\d+)\s+(\d+)(?:\s|$)", stdout, re.MULTILINE)
    require(len(rows) == 1, "One numeric quota row required")
    used, soft, hard = map(int, rows[0])
    limits = [n for n in (soft, hard) if n > 0]
    require(limits, "Unknown/unlimited user quota cannot budget acquisition")
    when = preflight.get("observed_unix_seconds")
    if when is None:
        when = dt.datetime.fromisoformat(preflight["observed_at"]).timestamp()
    return {"schema": "expansion_user_quota_receipt_v1", "username": "zixiao", "uid": 1278,
        "basis": "login_node_quota", "returncode": 0, "observed_unix_seconds": when,
        "available_bytes": max(0, min(limits) - used) * 1024, "raw_stdout": stdout,
        "raw_stdout_sha256": hashlib.sha256(stdout.encode()).hexdigest()}


def acquire_fresh_quota(spec, evidence_path):
    mode = spec["mode"]
    if mode == "submission_preflight":
        p = verify(spec["preflight"])
        value = quota_from_preflight(load(p))
    elif mode == "published_receipt":
        p = Path(spec["path"])
        require(p.is_absolute() and p.is_file() and not p.is_symlink() and p.stat().st_uid == 1278,
                "Live quota publication missing or not a regular owned source")
        value = load(p)
    elif mode == "login_ssh":
        # No proxy, host-key override or guessed credentials. Site key access
        # must already be configured and independently verified by Root.
        require(spec.get("verified_login_host") == "sonmi", "Only the established login host is allowed")
        argv = ["ssh", "-n", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-o", "ConnectTimeout=15",
                "sonmi", "hostname; id -u; quota -v -u zixiao"]
        result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, timeout=45, check=False)
        lines = result.stdout.splitlines()
        require(result.returncode == 0 and len(lines) >= 3 and lines[0] == "sonmi" and lines[1] == "1278",
                "Fresh login quota failed or wrong login identity; do not use an old snapshot")
        raw = "\n".join(lines[2:]) + "\n"
        value = quota_from_preflight({"quota": {"returncode": 0, "stdout": raw}, "observed_unix_seconds": time.time()})
        value["supplier"] = {"argv": argv, "returncode": result.returncode, "stderr": result.stderr}
    else:
        raise ValueError("Unknown quota supplier; only verified fresh evidence is accepted")
    dump_new(evidence_path, value)
    # The whole 4-GiB peak is reserved, not just remaining download bytes.
    check_quota(evidence_path, CAP)
    return value


def owned_bytes(root):
    seen, total = set(), 0
    for folder, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(folder, name)
            s = p.lstat()
            require(s.st_uid == 1278 and not stat.S_ISLNK(s.st_mode), "Nonowned/link acquisition output refused")
            require(stat.S_ISDIR(s.st_mode) or stat.S_ISREG(s.st_mode), "Unexpected acquisition output type")
            key = (s.st_dev, s.st_ino)
            if key not in seen:
                total += s.st_size
                seen.add(key)
    require(total <= CAP, "STOP: acquisition peak exceeded 4 GiB")
    return total


def _initialize(network, stop, start):
    global _NETWORK, _STOP, _START
    _NETWORK, _STOP, _START = network, stop, start
    start.wait(timeout=120)


def validate_range(response, begin, end, pin):
    require(response.url == URL, "Changed official range URL refused")
    require(response.status == 206, "Range request needs HTTP 206; HTTP 200 is never appended")
    require(response.headers.get("Content-Range") == f"bytes {begin}-{end}/{pin['content_length']}", "Content-Range differs")
    require(response.headers.get("Last-Modified") == pin["last_modified"], "Range source snapshot changed")
    require(int(response.headers.get("Content-Length", "-1")) == end - begin + 1, "Range body length differs")
    encoding = response.headers.get("Content-Encoding")
    require(encoding in (None, "identity"), "Transparent content transformation refused")
    if pin.get("etag"):
        require(response.headers.get("ETag") == pin["etag"], "Range ETag differs")


def download_part(task):
    pin, root, number, first, last, deadline = task
    root = Path(root)
    path = root / f"part_{number:02d}.partial"
    plan_path = root / f"part_{number:02d}.ownership.json"
    plan = {"schema": "pubchem_owned_range_v1", "uid": 1278, "source_pin": pin,
            "number": number, "first": first, "last": last}
    if plan_path.exists():
        require(load(plan_path) == plan, "Part belongs to another source snapshot/range")
    else:
        require(not path.exists(), "Unowned partial range file refused")
        dump_new(plan_path, plan)
    current = path.stat().st_size if path.exists() else 0
    require(current <= last - first + 1, "Owned partial is larger than its range")
    result = {"part": number, "first": first, "last": last, "resumed_bytes": current,
              "worker_pid": os.getpid(), "started_unix_seconds": time.time()}
    began = time.monotonic()
    try:
        if current < last - first + 1:
            # An error prevents new network units. Already running requests are
            # allowed to close naturally; no process/job is forcibly terminated.
            with _NETWORK:
                require(not _STOP.is_set(), "A previous network failure stopped new requests")
                begin = first + current
                headers = {"Range": f"bytes={begin}-{last}", "If-Range": pin.get("etag") or pin["last_modified"],
                           "Accept-Encoding": "identity"}
                request = urllib.request.Request(URL, headers=headers)
                with opener().open(request, timeout=30) as response:
                    validate_range(response, begin, last, pin)
                    with path.open("ab" if current else "xb") as stream:
                        while True:
                            require(time.monotonic() <= deadline, "Range deadline reached; partial retained")
                            block = response.read(min(1 << 20, last - first + 2 - current))
                            if not block:
                                break
                            current += len(block)
                            require(current <= last - first + 1, "Range body exceeded planned bytes")
                            stream.write(block)
                        stream.flush(); os.fsync(stream.fileno())
                require(current == last - first + 1, "Truncated range; owned partial retained")
        result.update(status="COMPLETE", file=reference(path), max_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024)
    except Exception as exc:
        _STOP.set()
        result.update(status="FAILED", error_type=type(exc).__name__, error=str(exc),
                      http_status=exc.code if isinstance(exc, urllib.error.HTTPError) else None,
                      partial_bytes=path.stat().st_size if path.exists() else 0)
    result["wall_seconds"] = time.monotonic() - began
    return result


def hash_part(ref):
    p = verify(ref)
    return {"file": reference(p), "worker_pid": os.getpid(), "status": "SHA256_VERIFIED"}


def assemble_and_crc(parts, output, *, max_uncompressed_bytes=64 * 1024 ** 3):
    h = hashlib.sha256()
    size = 0
    with Path(output).open("xb") as stream:
        for item in parts:
            p = verify(item["file"])
            with p.open("rb") as source:
                for block in iter(lambda: source.read(1 << 20), b""):
                    size += len(block)
                    stream.write(block)
                    h.update(block)
        stream.flush(); os.fsync(stream.fileno())
    uncompressed = 0
    # Read gzip to actual EOF so trailer CRC/ISIZE are checked, including any
    # concatenated members. No SMILES/CID parsing or chemistry is performed.
    with gzip.open(output, "rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            uncompressed += len(block)
            require(uncompressed <= max_uncompressed_bytes, "Gzip expansion exceeded the reviewed 64-GiB read cap")
    return {"compressed_bytes": size, "sha256": h.hexdigest(), "uncompressed_bytes_read": uncompressed,
            "gzip_read_to_eof_crc_validated": True}


def validate_root_submission(submission, needed):
    request = submission["request"]
    require(submission["uid"] == 1278 and request["node"] == "compute-0-20" and request["cpus"] == 16 and
            2 <= request["memory_gib"] <= 4 and 0 < request["wall_seconds"] <= 3600 and
            request["estimated_peak_output_bytes"] >= CAP and request["root_review"]["status"] == "APPROVED" and
            request["root_review"]["reviewer"] == "root", "Root submission/resource review does not authorize this raw acquisition")
    submitted = {r["path"]: r for r in request["source_references"]}
    for source in needed:
        require(submitted.get(source["path"]) == source, "Root submission does not bind the actual raw plan/source/pin")
    return True


def run(intent_path, root_submission_path):
    intent = load(intent_path)
    require(intent.get("schema") == "pubchem_raw_acquisition_plan_v1", "Wrong raw plan schema")
    submission = load(root_submission_path)
    require(os.getuid() == 1278 and socket.gethostname().split(".")[0] == "compute-0-20", "Raw job must be zixiao on compute-0-20")
    job = os.environ.get("SLURM_JOB_ID", "")
    require(job.isdecimal() and int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16, "Real 16-CPU Slurm allocation required")
    require(intent["workers"] == 16 and 1 <= intent["network_concurrency"] <= 4 and intent["peak_output_cap_bytes"] == CAP,
            "Unreviewed download concurrency or byte budget")
    require(intent.get("chemical_screening_authorized") is False, "Raw-only scope required")
    root = Path(intent["output_root"]).absolute()
    require(root.is_relative_to(ARTIFACT_ROOT / "raw"), "Output outside the reviewed raw root")
    pin_path = verify(intent["source_pin"])
    pin = load(pin_path)
    require(pin["url"] == URL and 2 * pin["content_length"] + (16 << 20) <= CAP, "Assembly+parts cannot fit 4-GiB cap")
    for source in intent["sources"]:
        verify(source)
    actual_sources = {str(Path(p).absolute()) for p in (__file__, common_source.__file__, network_source.__file__)}
    require(actual_sources <= {source["path"] for source in intent["sources"]}, "Intent does not bind the actual imported download source chain")
    validate_root_submission(submission, [reference(intent_path), intent["source_pin"], *intent["sources"]])
    root.mkdir(parents=True, exist_ok=True)
    require(not root.is_symlink() and root.stat().st_uid == 1278, "Raw output root must be an owned ordinary directory")
    ownership = root / "ownership.json"
    own = {"schema": "pubchem_raw_output_ownership_v1", "uid": 1278, "pin": intent["source_pin"], "first_intent": reference(intent_path)}
    if ownership.exists():
        previous = load(ownership)
        require(previous["uid"] == 1278 and previous["pin"] == intent["source_pin"] and
                intent.get("resume_from_intent") == previous["first_intent"], "Existing output needs exact explicit resume lineage")
    else:
        require(not list(root.iterdir()), "Existing nonempty raw directory is not owned by this intent")
        dump_new(ownership, own)
    attempt = root / ("attempt_" + job)
    attempt.mkdir(exist_ok=False)
    owned_bytes(root)
    began = time.monotonic()
    try:
        acquire_fresh_quota(intent["quota"], attempt / "quota_start.json")
        dump_new(attempt / "root_submission.json", {"reference": reference(root_submission_path), "submission": submission,
            "submission_quota_used_as_runtime_fresh_evidence": False})
        head_before = probe(pin)
        dump_new(attempt / "head_before.json", head_before)
        context = multiprocessing.get_context("spawn")
        network, stop, barrier = context.Semaphore(intent["network_concurrency"]), context.Event(), context.Barrier(16)
        planned = ranges(pin["content_length"])
        deadline = time.monotonic() + min(intent.get("download_deadline_seconds", 2700), 2700)
        tasks = [(pin, str(root), i, first, last, deadline) for i, (first, last) in enumerate(planned)]
        with ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=_initialize, initargs=(network, stop, barrier)) as pool:
            results = list(pool.map(download_part, tasks, chunksize=1))
        dump_new(attempt / "range_results.json", results)
        owned_bytes(root)
        require(all(r["status"] == "COMPLETE" for r in results), "STOP: source/range failure; report it, retain partials, no automatic retry")
        # Every one of the sixteen parts is independently rehashed in a second
        # parallel phase after download; no claimed CPU work is a dummy tensor.
        with ProcessPoolExecutor(max_workers=16, mp_context=context) as pool:
            hashes = list(pool.map(hash_part, [r["file"] for r in results], chunksize=1))
        dump_new(attempt / "part_hashes.json", hashes)
        # For a long transfer, this MUST obtain a fresh publisher/SSH observation;
        # submission-only snapshots older than five minutes are rejected.
        acquire_fresh_quota(intent["quota"], attempt / "quota_preassembly.json")
        require(probe(pin) == head_before, "HEAD changed during range acquisition")
        assembled = root / ("CID-SMILES.gz.assembled_" + job + ".partial")
        checked = assemble_and_crc(results, assembled)
        require(checked["compressed_bytes"] == pin["content_length"], "Whole source byte count differs")
        if pin.get("sha256"):
            require(checked["sha256"] == pin["sha256"], "Whole source SHA256 differs")
        after = probe(pin)
        require(after == head_before, "HEAD changed before final publication")
        dump_new(attempt / "head_after.json", after)
        target = root / "CID-SMILES.gz"
        os.link(assembled, target)  # no overwrite; hardlink adds no extra data extent
        peak = owned_bytes(root)
        result = {"schema": "pubchem_download_complete_v1", "acquisition_schema": "pubchem_16_range_acquisition_v1",
            "status": "RAW_ACQUIRED_NO_CHEMICAL_SCREENING", "job_id": job, "hostname": socket.gethostname(), "uid": os.getuid(),
            "pin": intent["source_pin"], "plan": reference(intent_path), "root_submission": reference(root_submission_path), "file": reference(target), "parts": results,
            "gzip": checked, "source_version": pin["last_modified"], "workers": 16,
            "network_concurrency": intent["network_concurrency"], "observed_unique_inode_bytes": peak,
            "peak_cap_bytes": CAP, "wall_seconds": time.monotonic() - began, "network_bypass_attempted": False,
            "chemical_screening_performed": False, "partials_and_parts_retained": True}
        dump_new(attempt / "receipt.json", result)
        print(json.dumps({"receipt": reference(attempt / "receipt.json"), "status": result["status"]}))
    except Exception as exc:
        dump_new(attempt / "failure.json", {"status": "FAILED_RAW_ACQUISITION_STOP", "job_id": job,
            "error_type": type(exc).__name__, "error": str(exc), "wall_seconds": time.monotonic() - began,
            "no_automatic_retry_or_network_bypass": True, "partials_retained": True})
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--plan", required=True, type=Path)
    p.add_argument("--root-submit-intent", required=True, type=Path)
    args = p.parse_args()
    run(args.plan, args.root_submit_intent)


if __name__ == "__main__":
    main()
