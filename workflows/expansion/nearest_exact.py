"""Exact, bounded-memory RDKit BulkTanimoto nearest-v1 baseline.

Queries are distributed to spawn workers. A read-only fingerprint mmap is shared
through the node page cache; only one reference block per worker is decoded.
No approximate search, sample reference or downstream feature is substituted.
"""
from __future__ import annotations

import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
import mmap
import multiprocessing
import os
from pathlib import Path
import resource
import sqlite3
import time

from .common import check_quota, dump_new, external_output, load, reference, require, require_compute, verify, wp5_key
from .screen import rdkit_modules

RECIPE = "ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5"
WIDTH = 256
QUERY_FIELDS = {"cid", "full_key", "heavy_atoms", "element_combination", "generic_murcko", "generic_ring_systems", "ecfp4_2048_hex"}
_REF = _MAP = _DATASTRUCTS = None


def write_reference(input_manifest, output, quota_receipt, projected_bytes):
    """Pack an already validated v1-common structure/fingerprint projection.

    One row per common-population molecule is retained, even when molecular
    identities repeat. Thus scaffold frequencies are molecular frequencies.
    The projection producer, chemical fingerprint recipe and common population
    are pinned by the upstream manifest; this command does not perceive graphs.
    """
    m = load(input_manifest)
    require(m.get("schema") == "expansion_common_v1_structure_projection_v1", "Wrong v1 structure projection schema")
    require(m["fingerprint_recipe"] == RECIPE and m["targets_present"] is False, "Wrong fingerprint recipe or target-bearing input")
    require(m["population_roles"] == ["TRAIN", "VAL"] and m["one_row_per_common_molecule"] is True,
            "Reference must cover the v1 common TRAIN/VAL molecular population")
    projection = verify(m["projection"])
    verify(m["common_population_manifest"])
    verify(m["producer_source"])
    check_quota(quota_receipt, projected_bytes)
    out = external_output(output)
    out.mkdir(parents=True)
    db = sqlite3.connect(out / "counts.sqlite")
    db.executescript("CREATE TABLE ids(molecule_id TEXT PRIMARY KEY); CREATE TABLE scaffolds(key TEXT PRIMARY KEY,n INTEGER); CREATE TABLE rings(key TEXT PRIMARY KEY,n INTEGER);")
    count = 0
    try:
        with projection.open(encoding="utf-8") as stream, (out / "fingerprints.bin").open("xb") as fp, (out / "keys.ascii").open("xb") as keys:
            for line in stream:
                row = json.loads(line)
                require(set(row) == {"molecule_id", "full_key", "ecfp4_2048_hex", "generic_murcko", "generic_ring_systems"},
                        "Unexpected projection fields; targets are forbidden")
                wp5_key(row["full_key"])
                require(isinstance(row["molecule_id"], str) and row["molecule_id"], "Missing common molecular identity")
                binary = bytes.fromhex(row["ecfp4_2048_hex"])
                require(len(binary) == WIDTH, "Fingerprint is not 2048 bits")
                require(isinstance(row["generic_murcko"], str) and isinstance(row["generic_ring_systems"], list) and
                        all(isinstance(s, str) for s in row["generic_ring_systems"]), "Wrong scaffold/ring projection")
                db.execute("INSERT INTO ids VALUES(?)", (row["molecule_id"],))
                fp.write(binary)
                keys.write(row["full_key"].encode("ascii") + b"\n")
                db.execute("INSERT INTO scaffolds VALUES(?,1) ON CONFLICT(key) DO UPDATE SET n=n+1", (row["generic_murcko"],))
                for ring in sorted(set(row["generic_ring_systems"])):
                    db.execute("INSERT INTO rings VALUES(?,1) ON CONFLICT(key) DO UPDATE SET n=n+1", (ring,))
                count += 1
                if count % 10000 == 0:
                    db.commit()
                    require(sum(p.stat().st_size for p in out.iterdir()) <= projected_bytes, "STOP: fingerprint-reference byte budget exceeded")
            fp.flush(); os.fsync(fp.fileno())
            keys.flush(); os.fsync(keys.fileno())
        require(count == m["projection"]["rows"] == m["common_molecules"] > 0, "v1 reference population count differs")
        db.commit()
    finally:
        db.close()
    require(sum(p.stat().st_size for p in out.iterdir()) <= projected_bytes, "STOP: fingerprint-reference byte budget exceeded")
    dump_new(out / "manifest.json", {"schema": "expansion_exact_ecfp4_reference_v1", "status": "COMPLETE",
        "fingerprint_recipe": RECIPE, "input_manifest": reference(input_manifest), "molecules": count,
        "bytes_per_fingerprint": WIDTH, "bytes_per_identity": 28, "targets_present": False,
        "fingerprints": reference(out / "fingerprints.bin"), "keys": reference(out / "keys.ascii"),
        "counts": reference(out / "counts.sqlite")})


def _initialize_worker(path, expected_stat, n, block_size, barrier=None):
    global _REF, _MAP, _DATASTRUCTS
    _, DataStructs, *_ = rdkit_modules()
    _REF = open(path, "rb")
    s = os.fstat(_REF.fileno())
    observed = [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]
    require(observed == expected_stat and s.st_size == n * WIDTH, "Worker reference file identity changed")
    _MAP = mmap.mmap(_REF.fileno(), 0, access=mmap.ACCESS_READ)
    _DATASTRUCTS = (DataStructs, n, block_size)
    if barrier is not None:
        barrier.wait(timeout=180)


def _nearest_batch(queries):
    DataStructs, n, block_size = _DATASTRUCTS
    prepared = []
    for row in queries:
        require(set(row) == QUERY_FIELDS, "Unexpected query fields; downstream information forbidden")
        wp5_key(row["full_key"])
        raw = bytes.fromhex(row["ecfp4_2048_hex"])
        require(len(raw) == WIDTH, "Query fingerprint is not 2048 bits")
        prepared.append(DataStructs.CreateFromBinaryText(raw))
    best = [(-1.0, -1) for _ in queries]
    began = time.monotonic()
    for start in range(0, n, block_size):
        stop = min(n, start + block_size)
        block = [DataStructs.CreateFromBinaryText(_MAP[i * WIDTH:(i + 1) * WIDTH]) for i in range(start, stop)]
        for i, query in enumerate(prepared):
            similarities = DataStructs.BulkTanimotoSimilarity(query, block)
            value = max(similarities)
            index = start + similarities.index(value)
            if value > best[i][0]:
                best[i] = (float(value), index)
    return {"queries": queries, "nearest": best, "worker_pid": os.getpid(),
            "wall_seconds": time.monotonic() - began, "comparisons": n * len(queries),
            "max_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024}


def exact_query_batches(reference_path, batches, workers, block_size=8192):
    m = load(reference_path)
    require(m.get("schema") == "expansion_exact_ecfp4_reference_v1" and m["status"] == "COMPLETE" and
            m["fingerprint_recipe"] == RECIPE and m["targets_present"] is False, "Invalid exact reference")
    p = verify(m["fingerprints"])
    require(p.stat().st_size == m["molecules"] * WIDTH and m["molecules"] > 0, "Reference fingerprint count differs")
    s = p.stat()
    stamp = [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns]
    require(1 <= block_size <= 65536 and 1 <= workers <= 192, "Unbounded fingerprint block or worker count")
    context = multiprocessing.get_context("spawn")
    barrier = context.Barrier(workers)
    with ProcessPoolExecutor(max_workers=workers, mp_context=context,
        initializer=_initialize_worker, initargs=(str(p), stamp, m["molecules"], block_size, barrier)) as pool:
        waiting = deque()
        for batch in batches:
            waiting.append(pool.submit(_nearest_batch, batch))
            if len(waiting) >= workers * 2:
                yield waiting.popleft().result(timeout=7200)
        while waiting:
            yield waiting.popleft().result(timeout=7200)
    require([p.stat().st_dev, p.stat().st_ino, p.stat().st_size, p.stat().st_mtime_ns] == stamp,
            "Reference fingerprint file changed during query")


def run_queries(reference_path, query_manifest, output, quota_receipt, projected_bytes,
                *, workers=16, max_queries=512, query_batch=8, reference_block=8192, max_comparisons=1_000_000_000):
    require_compute(workers)
    q = load(query_manifest)
    cost_pilot = q.get("schema") == "expansion_exact_query_cost_pilot_v1"
    require((q.get("schema") == "expansion_decontaminated_query_projection_v1" or cost_pilot) and q["fingerprint_recipe"] == RECIPE,
            "Query projection schema/recipe differs")
    require(q["targets_present"] is False and q["downstream_features_present"] is False, "No downstream features/targets in queries")
    query_file = verify(q["projection"])
    if cost_pilot:
        require(q.get("candidate_release_authorized") is False and q.get("source_kind") == "v1_common_structure_projection",
                "Cost-only pilots use pinned v1 structures and authorize no candidate release")
        verify(q["source_projection_manifest"])
    else:
        filtered = load(verify(q["filtered_pool_receipt"]))
        require(filtered.get("schema") == "expansion_filtered_pool_v1" and filtered.get("status") == "COMPLETE" and
                filtered.get("all_sources_all_splits_verified") is True, "Decontaminated query pool required")
    m = load(reference_path)
    keys_path, counts_path = verify(m["keys"]), verify(m["counts"])
    require(keys_path.stat().st_size == m["molecules"] * 28, "Reference key count differs")
    require(type(max_queries) is int and workers <= max_queries <= q["projection"]["rows"], "Explicit query cap >= worker count required")
    require(max_queries * m["molecules"] <= max_comparisons, "Exact-comparison budget exceeded before launch")
    require(1 <= query_batch <= max(1, max_queries // workers), "Query batches must exercise all workers")
    check_quota(quota_receipt, projected_bytes)
    out = external_output(output)
    out.mkdir(parents=True)
    worker_receipts = []
    rows = 0
    began = time.monotonic()
    ref_sha = reference(reference_path)["sha256"]
    counts_db = sqlite3.connect(counts_path.as_uri() + "?mode=ro", uri=True)

    def batches():
        batch = []
        with query_file.open(encoding="utf-8") as stream:
            for ordinal, line in enumerate(stream):
                if ordinal >= max_queries:
                    break
                row = json.loads(line)
                require(set(row) == QUERY_FIELDS, "Unexpected query projection fields")
                batch.append(row)
                if len(batch) == query_batch:
                    yield batch
                    batch = []
            if batch:
                yield batch

    try:
        with (out / "novelty_projection.jsonl").open("x", encoding="utf-8", newline="\n") as stream, \
             (out / "nearest_identity_audit.jsonl").open("x", encoding="utf-8", newline="\n") as audit, keys_path.open("rb") as key_file:
            for result in exact_query_batches(reference_path, batches(), workers, reference_block):
                worker_receipts.append({k: v for k, v in result.items() if k not in ("queries", "nearest")})
                for row, (similarity, index) in zip(result["queries"], result["nearest"]):
                    require(0 <= similarity <= 1 and 0 <= index < m["molecules"], "Invalid nearest neighbor result")
                    key_file.seek(index * 28)
                    nearest_key = key_file.read(28).decode("ascii").rstrip("\n")
                    wp5_key(nearest_key)
                    scaffold_count = counts_db.execute("SELECT n FROM scaffolds WHERE key=?", (row["generic_murcko"],)).fetchone()
                    ring_counts = [counts_db.execute("SELECT n FROM rings WHERE key=?", (ring,)).fetchone() for ring in set(row["generic_ring_systems"])]
                    score = {k: v for k, v in row.items() if k != "ecfp4_2048_hex"}
                    score.update(nearest_v1_tanimoto=similarity, v1_scaffold_count=scaffold_count[0] if scaffold_count else 0,
                        v1_ring_system_count=min((r[0] if r else 0 for r in ring_counts), default=m["molecules"]),
                        v1_reference_sha256=ref_sha)
                    # Nearest full identity is diagnostic only, outside ranking columns.
                    audit.write(json.dumps({"cid": row["cid"], "query_key": row["full_key"], "nearest_v1_key": nearest_key,
                        "reference_ordinal": index, "tanimoto": similarity}, separators=(",", ":")) + "\n")
                    stream.write(json.dumps(score, separators=(",", ":"), allow_nan=False) + "\n")
                    rows += 1
                require(sum(p.stat().st_size for p in out.iterdir()) <= projected_bytes, "STOP: exact-query output budget exceeded")
            stream.flush(); os.fsync(stream.fileno())
            audit.flush(); os.fsync(audit.fileno())
    finally:
        counts_db.close()
    require(rows == max_queries, "Query projection shorter than its declared count")
    require(sum(p.stat().st_size for p in out.iterdir()) <= projected_bytes, "STOP: exact-query output budget exceeded")
    elapsed = time.monotonic() - began
    dump_new(out / "receipt.json", {"schema": "expansion_exact_novelty_v1", "status": "COMPLETE" if not cost_pilot and rows == q["projection"]["rows"] else "BOUNDED_COST_PILOT",
        "nearest_similarity_exact": True, "downstream_features_used": False, "fingerprint_recipe": RECIPE,
        "reference": reference(reference_path), "query_manifest": reference(query_manifest),
        "filtered_pool_receipt": q.get("filtered_pool_receipt"), "queries": rows, "reference_molecules": m["molecules"],
        "comparisons": rows * m["molecules"], "wall_seconds": elapsed, "worker_count_requested": workers,
        "worker_pids_observed": sorted(set(r["worker_pid"] for r in worker_receipts)), "worker_batches": worker_receipts,
        "reference_block": reference_block, "query_batch": query_batch,
        "projection": {**reference(out / "novelty_projection.jsonl"), "rows": rows},
        "nearest_identity_audit": reference(out / "nearest_identity_audit.jsonl"),
        "performance_is_a_measured_prefix_not_a_full_pool_cost": True})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("action", choices=("pack-reference", "query"))
    p.add_argument("--input-manifest", required=True, type=Path)
    p.add_argument("--reference", type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--quota-receipt", required=True, type=Path)
    p.add_argument("--projected-output-bytes", required=True, type=int)
    p.add_argument("--workers", default=16, type=int)
    p.add_argument("--max-queries", default=512, type=int)
    p.add_argument("--query-batch", default=8, type=int)
    p.add_argument("--reference-block", default=8192, type=int)
    p.add_argument("--max-comparisons", default=1_000_000_000, type=int)
    a = p.parse_args()
    require_compute(a.workers)
    if a.action == "pack-reference":
        write_reference(a.input_manifest, a.output, a.quota_receipt, a.projected_output_bytes)
    else:
        require(a.reference, "Reference manifest required")
        run_queries(a.reference, a.input_manifest, a.output, a.quota_receipt, a.projected_output_bytes,
            workers=a.workers, max_queries=a.max_queries, query_batch=a.query_batch,
            reference_block=a.reference_block, max_comparisons=a.max_comparisons)


if __name__ == "__main__":
    main()
