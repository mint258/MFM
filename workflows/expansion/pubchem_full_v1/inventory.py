"""Count and shard the exact official gzip through EOF/CRC; no chemistry."""
from __future__ import annotations

import argparse
import codecs
from concurrent.futures import ThreadPoolExecutor
import gzip
import hashlib
import multiprocessing
import os
from pathlib import Path
import threading
import time

from .. import full_queue_v1 as execution
from ..common import require
from workflows.data_v1_final.execution.queue_v1 import shared


SCOPE = "sb5_pubchem_raw_inventory_v1"


def inventory_stream(stream, output, *, expected_bytes, shard_rows, shard_bytes, stop, checkpoint):
    """Bounded1MiB line segments; no whole giant SMILES is held in memory."""
    output = Path(output)
    parts, current = [], None
    total_bytes = records = longest = 0
    previous_cid = None
    increasing = True
    header = bytearray()
    tabs = line_bytes = 0
    header_done = False
    decoder = codecs.getincrementaldecoder("utf-8")("strict")

    def begin_part():
        index = len(parts)
        partial = output / f"source_{index:06d}.partial.tsv"
        final = output / f"source_{index:06d}.tsv"
        require(not partial.exists() and not final.exists(), "Preserve all owned old/partial parts")
        return {"index": index, "partial": partial, "final": final, "stream": partial.open("xb"), "digest": hashlib.sha256(),
                "first_ordinal": records + 1, "records": 0, "bytes": 0, "first_cid": None, "last_cid": None}

    def close_part():
        nonlocal current
        current["stream"].flush(); os.fsync(current["stream"].fileno()); current["stream"].close()
        os.rename(current["partial"], current["final"])
        value = {key: current[key] for key in ("index", "first_ordinal", "records", "bytes", "first_cid", "last_cid")}
        value.update(last_ordinal=records, reference={"path": str(current["final"]), "bytes": current["bytes"],
                                                     "sha256": current["digest"].hexdigest()})
        parts.append(value)
        shared.write_new(output / f"source_{value['index']:06d}.receipt.json", value)
        current = None

    def finish_line():
        nonlocal records, previous_cid, increasing, longest, header, tabs, line_bytes, header_done, decoder
        decoder.decode(b"", final=True)
        require(tabs == 1 and bytes(header).isascii() and bytes(header).isdigit() and int(header) > 0,
                "Malformed official CID/SMILES framing at ordinal" + str(records + 1))
        cid = int(header)
        if previous_cid is not None and cid <= previous_cid:
            increasing = False
        previous_cid = cid
        records += 1
        current["records"] += 1
        current["first_cid"] = cid if current["first_cid"] is None else current["first_cid"]
        current["last_cid"] = cid
        longest = max(longest, line_bytes)
        header, tabs, line_bytes, header_done = bytearray(), 0, 0, False
        decoder = codecs.getincrementaldecoder("utf-8")("strict")
        if current["records"] >= shard_rows or current["bytes"] >= shard_bytes:
            close_part()

    try:
        while True:
            if stop.is_set():
                raise execution.CooperativeStop("Stop before next bounded inventory read")
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
                header.extend(first)
                header_done = bool(found)
            tabs += piece.count(b"\t")
            line_bytes += len(piece)
            total_bytes += len(piece)
            require(total_bytes <= expected_bytes, "Decompressed byte count exceeded original actual producer")
            current["stream"].write(piece)
            current["digest"].update(piece)
            current["bytes"] += len(piece)
            if piece.endswith(b"\n"):
                finish_line()
            checkpoint()
        if current is not None:
            require(current["records"] > 0, "Empty trailing source part")
            close_part()
    finally:
        if current is not None and not current["stream"].closed:
            current["stream"].flush(); current["stream"].close()
    require(total_bytes == expected_bytes and sum(p["records"] for p in parts) == records and
            sum(p["bytes"] for p in parts) == total_bytes and records > 0 and
            all(part["first_ordinal"] == (1 if i == 0 else parts[i - 1]["last_ordinal"] + 1)
                and part["last_ordinal"] - part["first_ordinal"] + 1 == part["records"] for i, part in enumerate(parts)),
            "EOF byte/row/ordinal/shard conservation failed")
    return parts, {"records": records, "cid_records": records, "uncompressed_bytes": total_bytes,
                   "maximum_source_line_bytes": longest, "strictly_increasing_cids": increasing,
                   "global_unique_cids_proven": increasing,
                   "cid_uniqueness_basis": "observed strictly increasing positive official CID" if increasing else "PENDING_EXTERNAL_UNIQUENESS_CHECK_NO_ROWS_DROPPED"}


def run(plan_path, proof_path):
    plan, proof, startup = execution.startup(plan_path, proof_path, __file__, scope=SCOPE)
    require(plan["schema"] == "SB5_PUBCHEM_RAW_INVENTORY_PLAN_V1" and plan["pilot"] is False and
            plan["chemical_screening_performed"] is False and plan["pool_release_authorized"] is False and
            plan["whole_output_cap_bytes"] == 10 * 1024 ** 3 and plan["shard_max_bytes"] == 64 * 1024 ** 2 and
            plan["shard_max_records"] == 250000, "Full raw inventory only; no chemical screening/pool release")
    declared = {pin["path"]: pin for pin in proof["request"]["source_references"]}
    execution.verify_small(plan["raw_receipt"], declared)
    execution.verify_small(plan["original_prefix_receipt"], declared)
    raw = shared.load(plan["raw_receipt"]["path"])
    prefix = shared.load(plan["original_prefix_receipt"]["path"])
    require(raw["schema"] == "pubchem_download_complete_v1" and raw["job_id"] == "4520348" and
            raw["status"] == "RAW_ACQUIRED_NO_CHEMICAL_SCREENING" and raw["hostname"] == "compute-0-20" and
            raw["file"] == plan["raw_file"] and raw["gzip"]["gzip_read_to_eof_crc_validated"] is True and
            proof["request"]["data_references"] == [plan["raw_file"]] and prefix["job_id"] == "4520427" and
            prefix["source_receipt"] == plan["raw_receipt"], "Only exact official producer/prefix-authorized raw")
    expected = raw["gzip"]["uncompressed_bytes_read"]
    require(expected == plan["expected_uncompressed_bytes"] and expected + 64 * 1024 ** 2 < plan["whole_output_cap_bytes"],
            "Actual decoded byte bound or metadata reserve differs")
    out = execution.fresh_output(plan["output_root"])
    stop = multiprocessing.get_context("spawn").Event()
    budget = execution.RuntimeBudget(out, plan, proof, stop)
    began = time.monotonic()
    try:
        with budget:
            boundary_tests = None
            if plan["run_boundary_tests"]:
                from ..test_full_sources_v1 import run_boundaries
                boundary_tests = run_boundaries()
            before = execution.frame(plan["raw_file"]["path"])
            historical = prefix["data_authority"]["files"][0]
            require(historical["reference"] == plan["raw_file"] and execution.portable(before) ==
                    execution.portable(historical["expected_stat"]), "Only cross-node device portability is allowed")
            execution.file_pin(plan["raw_file"]["path"], expected=plan["raw_file"], expected_frame=before, stop=stop)
            hash_seconds = time.monotonic() - began
            with gzip.open(plan["raw_file"]["path"], "rb") as stream:
                parts, counts = inventory_stream(stream, out, expected_bytes=expected, shard_rows=plan["shard_max_records"],
                                                 shard_bytes=plan["shard_max_bytes"], stop=stop, checkpoint=budget.check)
            require(execution.frame(plan["raw_file"]["path"]) == before, "Raw changed during EOF/CRC scan")
            workers = min(16, len(parts))
            barrier = threading.Barrier(workers)
            def verify_part(part):
                execution.file_pin(part["reference"]["path"], expected=part["reference"], stop=stop)
                return threading.get_native_id()
            with ThreadPoolExecutor(max_workers=workers, initializer=lambda: barrier.wait(timeout=180)) as pool:
                ids = list(pool.map(verify_part, parts))
            require(len(set(ids)) == workers, "Independent final source-part SHA worker coverage differs")
            budget.check(force=True)
            receipt = {"schema": "SB5_PUBCHEM_RAW_INVENTORY_RECEIPT_V1", "status": "RAW_FULL_EOF_INVENTORY_COMPLETE_NO_CHEMICAL_SCREENING",
                "job_id": proof["job_id"], "node": proof["request"]["node"], "uid": os.getuid(),
                "plan": shared.pin(Path(plan_path)), "startup_proof": shared.pin(Path(proof_path)), "startup_validation": startup,
                "raw_source": plan["raw_file"], "raw_current_frame": before, "raw_complete_SHA_verified": True,
                "gzip_EOF_CRC_revalidated": True, "counts": counts, "closed_source_shards": parts,
                "part_hash_worker_thread_ids": sorted(set(ids)), "actual_part_hash_workers": workers,
                "hash_seconds": hash_seconds, "wall_seconds": time.monotonic() - began,
                "runtime_budget": budget.receipt(), "source_rows_not_chemically_filtered": True,
                "new_boundary_tests": boundary_tests,
                "chemical_screening_performed": False, "full_source_pool_release_authorized": False,
                "decontamination_or_novelty_or_UFF_or_QM_or_training_performed": False}
            shared.write_new(out / "receipt.json", receipt)
    except BaseException as exc:
        stop.set()
        shared.write_new(out / "failure.json", {"status": "RAW_INVENTORY_FAILED_PARTIALS_RETAINED", "type": type(exc).__name__,
            "error": str(exc), "runtime_budget": budget.receipt(), "forced_signals_sent": False,
            "chemical_screening_performed": False})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-preflight", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.root_preflight)


if __name__ == "__main__":
    main()
