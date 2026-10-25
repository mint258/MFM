"""Actual16-worker official raw prefix pilot, gated by completed full X replay."""
from __future__ import annotations

import argparse
from collections import Counter, deque
from concurrent.futures import ProcessPoolExecutor
import json
import multiprocessing
import os
from pathlib import Path
import socket
import sqlite3
import time

from . import common, data_authority_v1 as authority, screen, bounded_prefix_gate_v2 as gate
from .common import ARTIFACT_ROOT, check_quota, dump_new, load, reference, require, verify


def _initialize(barrier):
    screen.rdkit_modules()
    barrier.wait(timeout=180)


def screen_batch(batch):
    return {"worker_pid": os.getpid(), "rows": screen.screen_batch(batch)}


def ordered_results(batches):
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(max_workers=16, mp_context=context, initializer=_initialize,
                             initargs=(context.Barrier(16),)) as pool:
        waiting = deque()
        for batch in batches:
            waiting.append(pool.submit(screen_batch, batch))
            if len(waiting) >= 32:
                yield waiting.popleft().result(timeout=3600)
        while waiting:
            yield waiting.popleft().result(timeout=3600)


def run(plan_path, intent_path):
    node = socket.gethostname().split(".")[0]
    require(os.getuid() == 1278 and node == "compute-0-20" and os.environ.get("SLURM_JOB_ID", "").isdecimal() and
            int(os.environ.get("SLURM_CPUS_PER_TASK", "0")) >= 16, "Actual zixiao16CPU compute20 Slurm job required")
    plan, intent = load(plan_path), load(intent_path)
    authorization = gate.authorize_full_gate(plan, intent)
    declared = {r["path"]: r for r in intent["request"]["source_references"]}
    needed = [reference(plan_path), plan["raw_receipt"], *plan["code_sources"], *plan["data_authorization_receipts"], plan["quota_publisher_source"]]
    require(all(declared.get(r["path"]) == r for r in needed), "Root did not pin actual prefix code/plan/raw authority/quota source")
    for ref in [*plan["code_sources"], plan["quota_publisher_source"], plan["raw_receipt"]]:
        verify(ref)
    actual = {str(Path(p).absolute()) for p in (__file__, gate.__file__, common.__file__, authority.__file__, screen.__file__)}
    require(actual <= {r["path"] for r in plan["code_sources"]}, "Actual prefix runtime import chain is not pinned")
    raw = load(plan["raw_receipt"]["path"])
    require(raw["schema"] == "pubchem_download_complete_v1" and raw["status"] == "RAW_ACQUIRED_NO_CHEMICAL_SCREENING" and
            raw["job_id"] == "4520348" and raw["file"] == plan["root_data_reference"] and
            intent["request"]["data_references"] == [raw["file"]], "Only the exact completed official raw file may be read")
    data = authority.authorize_data(plan, intent, [raw["file"]], node=node)
    out = Path(plan["output_root"]).absolute()
    require(out.is_relative_to(ARTIFACT_ROOT / "screening") and not out.exists(), "Fresh isolated external prefix output required")
    out.mkdir(parents=True)
    began = time.monotonic()
    counts, workers = Counter(), Counter()
    db = None
    try:
        dump_new(out / "bounded_authorization.json", authorization)
        feed = Path(plan["quota_feed"])
        require(feed.is_absolute() and feed.is_file() and not feed.is_symlink() and feed.stat().st_uid == 1278,
                "Task-owned fresh quota publication required")
        dump_new(out / "quota_start.json", load(feed))
        check_quota(out / "quota_start.json", plan["peak_output_cap_bytes"])
        authority.verify_authorized_data(data)
        raw_hash_seconds = time.monotonic() - began
        database = out / "unreleased_prefix_candidates.sqlite"
        db = sqlite3.connect(database)
        db.execute("PRAGMA journal_mode=DELETE")
        db.execute("CREATE TABLE candidates(full_key TEXT PRIMARY KEY,cid INTEGER UNIQUE,wp5_key TEXT,features TEXT NOT NULL)")
        db.execute("CREATE TABLE aliases(cid INTEGER PRIMARY KEY,full_key TEXT NOT NULL,source_ordinal INTEGER NOT NULL)")
        compute_started = time.monotonic()
        with (out / "all_prefix_rejections.jsonl").open("x", encoding="utf-8", newline="\n") as rejected:
            for batch in ordered_results(screen.cid_batches(raw["file"]["path"], max_rows=10000, batch_size=256)):
                workers[batch["worker_pid"]] += len(batch["rows"])
                for row in batch["rows"]:
                    counts["input_records"] += 1
                    require(row["ordinal"] == counts["input_records"], "Prefix ordinals are missing, duplicated or reordered")
                    if row["reasons"]:
                        counts["first:" + row["reasons"][0]] += 1
                        counts.update({"overlap:" + reason: 1 for reason in row["reasons"]})
                        rejected.write(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n")
                        continue
                    counts["after_X_and_identity"] += 1
                    db.execute("INSERT INTO aliases VALUES(?,?,?)", (row["cid"], row["full_key"], row["ordinal"]))
                    old = db.execute("SELECT cid FROM candidates WHERE full_key=?", (row["full_key"],)).fetchone()
                    counts["pubchem_duplicate_full_key"] += int(old is not None)
                    if old is None or row["cid"] < old[0]:
                        db.execute("INSERT OR REPLACE INTO candidates VALUES(?,?,?,?)", (row["full_key"], row["cid"], row["wp5_key"],
                                   json.dumps(row, separators=(",", ":"), allow_nan=False)))
                db.commit()
                require(sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) <= plan["peak_output_cap_bytes"] - 1024 ** 2,
                        "STOP: bounded prefix output budget reached")
            rejected.flush(); os.fsync(rejected.fileno())
        unique = db.execute("SELECT count(*) FROM candidates").fetchone()[0]
        aliases = db.execute("SELECT count(*) FROM aliases").fetchone()[0]
        db.close(); db = None
        require(counts["input_records"] == 10000 and len(workers) == 16 and all(v > 0 for v in workers.values()) and
                sum(workers.values()) == 10000 and aliases == counts["after_X_and_identity"], "Actual prefix/worker/alias coverage differs")
        authority.verify_final_stats(data)
        size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
        report = {"schema": "PUBCHEM_BOUNDED_PREFIX_PILOT_V2", "status": "BOUNDED_INPUT_PREFIX_PILOT_NOT_DECONTAMINATED",
                  "job_id": os.environ["SLURM_JOB_ID"], "node": node, "uid": os.getuid(), "plan": reference(plan_path),
                  "root_submission": reference(intent_path), "full_rule_authorization": authorization,
                  "source_receipt": plan["raw_receipt"], "data_authority": data, "input_prefix_records": 10000,
                  "prefix_start_ordinal": 1, "counts": dict(counts), "unique_full_keys": unique,
                  "successful_cid_aliases": aliases, "actual_worker_records": dict(workers), "worker_pids_observed": sorted(workers),
                  "rdkit_version": screen.RDKIT, "heavy_atom_upper_bound": None, "isotope_policy": "preserve",
                  "stereo_policy": "preserve_source", "database": reference(database),
                  "all_rejections": reference(out / "all_prefix_rejections.jsonl"), "observed_output_bytes_before_receipt": size,
                  "raw_full_SHA_and_proof_seconds": raw_hash_seconds, "worker_and_write_seconds": time.monotonic() - compute_started,
                  "total_wall_seconds": time.monotonic() - began, "complete_source": False,
                  "prefix_is_not_a_representative_pubchem_sample": True, "common_scope_pending": True,
                  "all_downstream_decontamination_not_claimed": True, "molecular_generation_or_training_performed": False,
                  **{k: False for k in gate.FORBIDDEN_RELEASES}}
        dump_new(out / "receipt.json", report)
        require(sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) <= plan["peak_output_cap_bytes"], "Final prefix output cap exceeded")
        print(json.dumps({"receipt": reference(out / "receipt.json"), "status": report["status"]}))
    except Exception as exc:
        dump_new(out / "failure.json", {"status": "FAILED_BOUNDED_PREFIX_PILOT", "error_type": type(exc).__name__,
                 "error": str(exc), "counts_so_far": dict(counts), "wall_seconds": time.monotonic() - began,
                 "no_pool_decontamination_UFF_or_training_gate_released": True})
        raise
    finally:
        if db is not None:
            db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--root-submit-intent", type=Path, required=True)
    args = parser.parse_args()
    run(args.plan, args.root_submit_intent)


if __name__ == "__main__":
    main()
