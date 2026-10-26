"""Mathematically bounded original-byte sharding with a streamed JSONL index."""
from __future__ import annotations

import argparse
import codecs
from collections import Counter, deque
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import itertools
import json
import multiprocessing
import os
from pathlib import Path
import threading
import time

from . import runtime as execution
from ..common import require
from workflows.data_v1_final.execution.queue_v1 import shared


SCOPE = "sb5_pubchem_raw_inventory_v2"
PART_META_CAP = 4096
METADATA_RESERVE = 256 * 1024 ** 2
WHOLE_CAP = 10 * 1024 ** 3


def source_budget(source_bytes, shard_rows, shard_bytes):
    require(type(source_bytes) is int and source_bytes > 0 and shard_rows > 0 and shard_bytes > 0, "Positive inventory bounds required")
    # Nonfinal valid rows need CIDdigit+TAB+LF; final row may omit LF. Empty
    # source SMILES is preserved, so no chemically motivated minimum is assumed.
    max_records = (source_bytes + 1) // 3
    max_parts = max_records // shard_rows + source_bytes // shard_bytes + 1
    payload = source_bytes + 2 * max_parts * PART_META_CAP  # one per-part receipt plus one index line
    return {"source_bytes": source_bytes, "max_records_from_framing": max_records, "max_parts": max_parts,
            "per_part_metadata_cap_bytes": PART_META_CAP, "payload_and_index_upper_bytes": payload,
            "directory_allocation_final_failure_metadata_reserve_bytes": METADATA_RESERVE,
            "whole_mathematical_upper_bytes": payload + METADATA_RESERVE}


def compact_line(value):
    raw = (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    require(len(raw) <= PART_META_CAP, "Part metadata exceeds4KiB; do not write or truncate it")
    return raw


def cid_summary(canonical):
    # Complete official CID stays in TSV. Summary size never scales with its
    # number of digits; no new integer-range or chemical exclusion is imposed.
    return {"decimal_digits": len(canonical), "decimal_prefix": canonical[:32].decode("ascii"),
            "complete_decimal": canonical.decode("ascii") if len(canonical) <= 32 else None,
            "decimal_sha256": hashlib.sha256(canonical).hexdigest()}


class InventoryStorage:
    def __init__(self, root, math_bound, cap):
        self.root, self.math_bound, self.cap = Path(root), math_bound, cap
        require(math_bound["whole_mathematical_upper_bytes"] <= cap, "10GiB bound cannot hold before any source write")
        self.logical_bytes = self.max_sampled_allocated_bytes = 0
        self.last_sample = float("-inf")

    def write(self, stream, raw):
        require(self.logical_bytes + len(raw) <= self.math_bound["payload_and_index_upper_bytes"], "Exact source+metadata payload bound reached")
        result = stream.write(raw)
        require(result == len(raw), "Short owned inventory write")
        self.logical_bytes += result

    def sample_allocation(self, *, force=False):
        now = time.monotonic()
        if not force and now - self.last_sample < 1:
            return
        self.last_sample = now
        allocated = logical = 0
        seen = set()
        for path in itertools.chain((self.root,), self.root.iterdir()):
            info = path.stat()
            require(not path.is_symlink() and info.st_uid == 1278, "Owned inventory file/directory identity differs")
            inode = (info.st_dev, info.st_ino)
            if inode in seen:
                continue
            seen.add(inode)
            allocated += info.st_blocks * 512
            if path.is_file():
                logical += info.st_size
        self.max_sampled_allocated_bytes = max(self.max_sampled_allocated_bytes, allocated)
        require(allocated <= self.cap - 8 * 1024 ** 2 and max(0, allocated - logical) <= METADATA_RESERVE - 8 * 1024 ** 2,
                "Observed allocation/directory overhead exhausted reserved budget; STOP with all files retained")


def iter_index(path):
    with Path(path).open("rb") as stream:
        while True:
            line = stream.readline(PART_META_CAP + 1)
            if not line:
                break
            require(line.endswith(b"\n") and len(line) <= PART_META_CAP, "Index entry is truncated or above4KiB")
            yield json.loads(line)


def inventory_stream(stream, output, *, expected_bytes, shard_rows, shard_bytes, stop, checkpoint, whole_cap=WHOLE_CAP):
    output = Path(output)
    bounds = source_budget(expected_bytes, shard_rows, shard_bytes)
    storage = InventoryStorage(output, bounds, whole_cap)
    index_partial, index_final = output / "source_index.partial.jsonl", output / "source_index.jsonl"
    require(not index_partial.exists() and not index_final.exists(), "Preserve every old index/partial")
    index = index_partial.open("xb")
    index_digest = hashlib.sha256()
    index_bytes = part_count = part_records = part_bytes = total_bytes = records = longest = 0
    current, previous_cid = None, None
    increasing = True
    header, tabs, line_bytes, header_done = bytearray(), 0, 0, False
    decoder = codecs.getincrementaldecoder("utf-8")("strict")

    def begin_part():
        partial, final = output / f"source_{part_count:06d}.partial.tsv", output / f"source_{part_count:06d}.tsv"
        require(not partial.exists() and not final.exists(), "New part path required; never overwrite")
        return {"partial": partial, "final": final, "stream": partial.open("xb"), "digest": hashlib.sha256(),
                "first_ordinal": records + 1, "records": 0, "bytes": 0, "first_cid": None, "last_cid": None}

    def close_part():
        nonlocal current, part_count, part_records, part_bytes, index_bytes
        current["stream"].flush(); os.fsync(current["stream"].fileno()); current["stream"].close()
        os.rename(current["partial"], current["final"])
        value = {key: current[key] for key in ("first_ordinal", "records", "bytes", "first_cid", "last_cid")}
        value.update(index=part_count, last_ordinal=records,
                     reference={"path": str(current["final"]), "bytes": current["bytes"], "sha256": current["digest"].hexdigest()})
        raw = compact_line(value)
        require(part_count < bounds["max_parts"] and current["first_ordinal"] == part_records + 1 and
                records - current["first_ordinal"] + 1 == current["records"], "Part count/ordinal conservation exceeds mathematical bound")
        with (output / f"source_{part_count:06d}.receipt.json").open("xb") as receipt:
            storage.write(receipt, raw); receipt.flush(); os.fsync(receipt.fileno())
        storage.write(index, raw); index.flush()
        index_digest.update(raw); index_bytes += len(raw)
        part_count += 1; part_records += current["records"]; part_bytes += current["bytes"]
        current = None
        storage.sample_allocation()

    def finish_line():
        nonlocal records, previous_cid, increasing, longest, header, tabs, line_bytes, header_done, decoder
        decoder.decode(b"", final=True)
        token = bytes(header)
        canonical = token.lstrip(b"0")
        require(tabs == 1 and token.isascii() and token.isdigit() and canonical,
                "Malformed official CID/SMILES framing at ordinal" + str(records + 1))
        key = (len(canonical), canonical)
        increasing = increasing and (previous_cid is None or key > previous_cid)
        previous_cid = key
        records += 1; current["records"] += 1
        value = cid_summary(canonical)
        current["first_cid"] = value if current["first_cid"] is None else current["first_cid"]
        current["last_cid"] = value
        longest = max(longest, line_bytes)
        header, tabs, line_bytes, header_done = bytearray(), 0, 0, False
        decoder = codecs.getincrementaldecoder("utf-8")("strict")
        if current["records"] >= shard_rows or current["bytes"] >= shard_bytes:
            close_part()

    try:
        while True:
            if stop.is_set():
                raise execution.CooperativeStop("Stop before next inventory segment")
            piece = stream.readline(1 << 20)
            if not piece:
                if line_bytes:
                    finish_line()
                break
            if current is None:
                current = begin_part()
            decoder.decode(piece, final=False)
            if not header_done:
                first, found, _ = piece.partition(b"\t")
                header.extend(first); header_done = bool(found)
            tabs += piece.count(b"\t"); line_bytes += len(piece); total_bytes += len(piece)
            require(total_bytes <= expected_bytes, "Decoded bytes exceed original producer")
            storage.write(current["stream"], piece)
            current["digest"].update(piece); current["bytes"] += len(piece)
            if piece.endswith(b"\n"):
                finish_line()
            checkpoint()
        if current is not None:
            require(current["records"] > 0, "Empty trailing source part")
            close_part()
        index.flush(); os.fsync(index.fileno()); index.close()
        os.rename(index_partial, index_final)
        require(total_bytes == part_bytes == expected_bytes and records == part_records and
                0 < records <= bounds["max_records_from_framing"], "Source byte/row/ordinal/part conservation failed")
        storage.sample_allocation(force=True)
    finally:
        if current is not None and not current["stream"].closed:
            current["stream"].flush(); current["stream"].close()
        if not index.closed:
            index.flush(); index.close()
    index_ref = {"path": str(index_final), "bytes": index_bytes, "sha256": index_digest.hexdigest()}
    return {"reference": index_ref, "part_count": part_count}, {
        "records": records, "cid_records": records, "uncompressed_bytes": total_bytes, "maximum_source_line_bytes": longest,
        "strictly_increasing_cids": increasing, "global_unique_cids_proven": increasing,
        "cid_uniqueness_basis": "observed strictly increasing positive decimal IDs" if increasing else "PENDING_EXTERNAL_UNIQUENESS_NO_ROWS_DROPPED",
        "storage_bound": bounds, "observed_payload_and_index_bytes": storage.logical_bytes,
        "peak_sampled_allocated_file_and_directory_bytes": storage.max_sampled_allocated_bytes,
        "whole_index_never_loaded_as_JSON": True}


def run(plan_path, proof_path):
    plan, proof, startup = execution.startup(plan_path, proof_path, __file__, scope=SCOPE)
    require(plan["schema"] == "SB5_PUBCHEM_RAW_INVENTORY_PLAN_V2" and plan["pilot"] is False and
            plan["chemical_screening_performed"] is False and plan["pool_release_authorized"] is False and
            plan["whole_output_cap_bytes"] == WHOLE_CAP and plan["metadata_reserve_bytes"] == METADATA_RESERVE and
            plan["shard_max_bytes"] == 64 * 1024 ** 2 and plan["shard_max_records"] == 250000, "Raw inventory v2 only")
    declared = {pin["path"]: pin for pin in proof["request"]["source_references"]}
    execution.verify_small(plan["raw_receipt"], declared)
    execution.verify_small(plan["original_prefix_receipt"], declared)
    raw = shared.load(plan["raw_receipt"]["path"])
    prefix = shared.load(plan["original_prefix_receipt"]["path"])
    require(raw["job_id"] == "4520348" and raw["file"] == plan["raw_file"] and
            raw["gzip"]["gzip_read_to_eof_crc_validated"] is True and prefix["job_id"] == "4520427" and
            prefix["source_receipt"] == plan["raw_receipt"] and proof["request"]["data_references"] == [plan["raw_file"]], "Exact raw authority required")
    expected = raw["gzip"]["uncompressed_bytes_read"]
    computed_bound = source_budget(expected, 250000, 64 * 1024 ** 2)
    require(expected == plan["expected_uncompressed_bytes"] and plan["mathematical_storage_bound"] == computed_bound and
            computed_bound["whole_mathematical_upper_bytes"] <= WHOLE_CAP,
            "Real-source byte bound cannot fit10GiB")
    out = execution.fresh_output(plan["output_root"])
    stop = multiprocessing.get_context("spawn").Event()
    budget = execution.RuntimeBudget(out, plan, proof, stop)
    began = time.monotonic()
    try:
        with budget:
            from ..test_full_sources_v2 import run_boundaries
            boundaries = run_boundaries() if plan["run_boundary_tests"] else None
            before = execution.frame(plan["raw_file"]["path"])
            historical = prefix["data_authority"]["files"][0]
            require(historical["reference"] == plan["raw_file"] and execution.portable(before) == execution.portable(historical["expected_stat"]),
                    "Only producer/consumer device may differ")
            execution.file_pin(plan["raw_file"]["path"], expected=plan["raw_file"], expected_frame=before, stop=stop)
            with gzip.open(plan["raw_file"]["path"], "rb") as stream:
                index, counts = inventory_stream(stream, out, expected_bytes=expected, shard_rows=250000, shard_bytes=64 * 1024 ** 2,
                                                 stop=stop, checkpoint=budget.check, whole_cap=WHOLE_CAP)
            require(execution.frame(plan["raw_file"]["path"]) == before, "Raw changed during EOF/CRC")
            execution.file_pin(index["reference"]["path"], expected=index["reference"], stop=stop)
            workers = min(16, index["part_count"])
            barrier = threading.Barrier(workers)
            def verify_part(part):
                execution.file_pin(part["reference"]["path"], expected=part["reference"], stop=stop)
                return threading.get_native_id(), part["records"], part["bytes"]
            pids, verified_records, verified_bytes, verified_parts = set(), 0, 0, 0
            with ThreadPoolExecutor(max_workers=workers, initializer=lambda: barrier.wait(timeout=180)) as pool:
                pending = deque()
                def collect():
                    nonlocal verified_parts, verified_records, verified_bytes
                    pid, rows, size = pending.popleft().result(timeout=7200)
                    pids.add(pid); verified_parts += 1; verified_records += rows; verified_bytes += size
                    budget.check()
                for part in iter_index(index["reference"]["path"]):
                    budget.check(); pending.append(pool.submit(verify_part, part))
                    if len(pending) >= 32:
                        collect()
                while pending:
                    collect()
            require(len(pids) == workers and verified_parts == index["part_count"] and
                    verified_records == counts["records"] and verified_bytes == expected, "Independent part SHA/row/byte verification differs")
            execution.file_pin(index["reference"]["path"], expected=index["reference"], stop=stop)
            budget.check(force=True)
            receipt = {"schema": "SB5_PUBCHEM_RAW_INVENTORY_RECEIPT_V2", "status": "RAW_FULL_EOF_INVENTORY_COMPLETE_NO_CHEMICAL_SCREENING",
                "job_id": proof["job_id"], "node": proof["request"]["node"], "uid": os.getuid(),
                "plan": shared.pin(Path(plan_path)), "startup_proof": shared.pin(Path(proof_path)), "startup_validation": startup,
                "raw_source": plan["raw_file"], "raw_current_frame": before, "raw_complete_SHA_verified": True,
                "gzip_EOF_CRC_revalidated": True, "counts": counts, "source_index": index,
                "part_hash_worker_thread_ids": sorted(pids), "actual_part_hash_workers": workers,
                "new_boundary_tests": boundaries, "runtime_budget": budget.receipt(), "wall_seconds": time.monotonic() - began,
                "chemical_screening_performed": False, "full_source_pool_release_authorized": False,
                "decontamination_or_novelty_or_UFF_or_QM_or_training_performed": False}
            require(len((json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode()) < 1024 * 1024, "Final receipt must stay small, not inline shard list")
            shared.write_new(out / "receipt.json", receipt)
    except BaseException as exc:
        stop.set()
        shared.write_new(out / "failure.json", {"status": "RAW_INVENTORY_V2_FAILED_PARTIALS_RETAINED", "type": type(exc).__name__,
            "error": str(exc), "runtime_budget": budget.receipt(), "forced_signals_sent": False, "chemical_screening_performed": False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-preflight", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.root_preflight)


if __name__ == "__main__":
    main()
