"""Parallel DuckDB external R/N sorting, identical to the bounded reference.

All score features come from the pinned exact-v1 novelty projection. Full-key
pool membership is checked against the physically verified filtered SQLite DB.
The ranking input has no downstream labels/features. Nothing is submitted here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time

from .common import check_quota, dump_new, external_output, load, reference, require, require_compute, stable_hash, verify
from .nearest_exact import RECIPE
from .ranking import RANK_FIELDS, release_gate

SCALE = 10 ** 24
MAX_POOL = 1_000_000_000


def identity_digest(rows):
    h = hashlib.sha256()
    count = 0
    for full_key, cid in rows:
        h.update(json.dumps([full_key, int(cid)], separators=(",", ":"), ensure_ascii=True).encode() + b"\n")
        count += 1
    return count, h.hexdigest()


def create_queues(db, *, seed, queue_size):
    """Input table pool contains exactly RANK_FIELDS; result queues has no data labels."""
    require(set(r[0] for r in db.execute("DESCRIBE pool").fetchall()) == RANK_FIELDS, "Wrong ranking projection columns")
    n, distinct = db.execute("SELECT count(*),count(DISTINCT full_key) FROM pool").fetchone()
    require(0 < queue_size and 2 * queue_size <= n <= MAX_POOL and n == distinct,
            "Insufficient or duplicated candidate pool, or unreviewed >1B pool")
    bad = db.execute("""SELECT count(*) FROM pool WHERE cid IS NULL OR cid<=0 OR heavy_atoms IS NULL OR heavy_atoms<0
        OR NOT regexp_full_match(full_key,'[A-Z]{14}-[A-Z]{10}-[A-Z]')
        OR v1_scaffold_count IS NULL OR v1_scaffold_count<0 OR v1_ring_system_count IS NULL OR v1_ring_system_count<0
        OR nearest_v1_tanimoto IS NULL OR NOT isfinite(nearest_v1_tanimoto) OR nearest_v1_tanimoto<0 OR nearest_v1_tanimoto>1
        OR element_combination IS NULL OR NOT regexp_full_match(element_combination,'[0-9]+(,[0-9]+)*')
        OR generic_murcko IS NULL OR generic_ring_systems IS NULL
        OR v1_reference_sha256 IS NULL OR NOT regexp_full_match(v1_reference_sha256,'[0-9a-f]{64}')""").fetchone()[0]
    require(bad == 0, "Invalid ranking row")
    require(db.execute("SELECT count(DISTINCT v1_reference_sha256) FROM pool").fetchone()[0] == 1, "Mixed v1 references")
    db.create_function("r_hash", lambda key: stable_hash("R-uniform", seed, key), ["VARCHAR"], "VARCHAR")
    db.create_function("n_hash", lambda key: stable_hash("N-tie", seed, key), ["VARCHAR"], "VARCHAR")
    db.execute("CREATE TABLE r_order AS SELECT cid,full_key,row_number() OVER(ORDER BY r_hash(full_key),full_key,cid)::BIGINT AS stream_rank FROM pool")
    db.execute("CREATE TABLE r_queue AS SELECT 'R' AS stream,cid,full_key,stream_rank FROM r_order WHERE stream_rank<=?", [queue_size])
    db.execute("""CREATE TABLE n_candidates AS SELECT p.*,
        CASE WHEN heavy_atoms<=10 THEN '10' WHEN heavy_atoms<=20 THEN '20' WHEN heavy_atoms<=30 THEN '30'
             WHEN heavy_atoms<=50 THEN '50' WHEN heavy_atoms<=75 THEN '75' WHEN heavy_atoms<=100 THEN '100'
             ELSE 'above_100' END AS heavy_stratum
        FROM pool p ANTI JOIN r_queue r USING(full_key)""")
    db.execute("""CREATE TABLE n_within AS SELECT cid,full_key,heavy_stratum,element_combination,
        row_number() OVER(PARTITION BY heavy_stratum,element_combination ORDER BY
            (v1_scaffold_count=0) DESC,(v1_ring_system_count=0) DESC,nearest_v1_tanimoto ASC,
            v1_scaffold_count ASC,v1_ring_system_count ASC,n_hash(full_key) DESC)::BIGINT AS within_rank,
        count(*) OVER(PARTITION BY heavy_stratum,element_combination)::BIGINT AS stratum_n FROM n_candidates""")
    # floor((2*i-1)*SCALE/(2*n)) preserves exact rational order: with n<=1B,
    # distinct fractions differ by >=1/(2*1B^2), far greater than 1/SCALE.
    # HUGEINT multiplication stays below 2e33, inside signed 128-bit range.
    db.execute(f"""CREATE TABLE n_order AS SELECT 'N' AS stream,cid,full_key,
        row_number() OVER(ORDER BY
            ((2*within_rank-1)::HUGEINT*{SCALE}::HUGEINT)//(2*stratum_n)::HUGEINT,
            heavy_stratum,element_combination)::BIGINT AS stream_rank FROM n_within""")
    db.execute("CREATE TABLE queues AS SELECT * FROM r_queue UNION ALL SELECT * FROM n_order WHERE stream_rank<=?", [queue_size])
    count, unique = db.execute("SELECT count(*),count(DISTINCT full_key) FROM queues").fetchone()
    require(count == unique == 2 * queue_size, "R/N queues overlap or have wrong size")
    return n


def run(novelty_path, output, quota_receipt, projected_bytes, *, workers=16, seed=20261025,
        queue_size=5_000_000, first_batch_each=1_250_000, memory_gb=16, temporary_gb=64):
    require_compute(workers)
    novelty = load(novelty_path)
    require(novelty.get("schema") == "expansion_exact_novelty_v1" and novelty.get("status") == "COMPLETE" and
            novelty.get("fingerprint_recipe") == RECIPE, "A bounded nearest-neighbor cost pilot cannot release a full pool")
    query = load(verify(novelty["query_manifest"]))
    filtered_path = verify(novelty["filtered_pool_receipt"])
    require(query["filtered_pool_receipt"] == novelty["filtered_pool_receipt"], "Novelty/query pool binding differs")
    filtered = load(filtered_path)
    screen = load(verify(filtered["screen"]))
    regression = load(verify(filtered["regression"]))
    release_gate(screen_receipt=screen, regression_receipt=regression, decontamination_receipt=filtered, novelty_receipt=novelty)
    require(0 < first_batch_each <= queue_size and memory_gb >= 1 and temporary_gb >= 1, "Invalid explicit sort budgets")
    require(projected_bytes >= temporary_gb * 1_000_000_000, "Quota budget must include the entire declared spill allowance")
    check_quota(quota_receipt, projected_bytes)
    projection = verify(novelty["projection"])
    pool_path = verify(filtered["database"])
    out = external_output(output)
    out.mkdir(parents=True)
    spill = out / "spill"
    spill.mkdir()
    import duckdb
    db = duckdb.connect(str(out / "ranking.duckdb"))
    started = time.monotonic()
    try:
        db.execute(f"SET threads={workers}")
        db.execute(f"SET memory_limit='{memory_gb}GB'")
        db.execute(f"SET max_temp_directory_size='{temporary_gb}GB'")
        db.execute("SET temp_directory=?", [str(spill)])
        db.execute("SET preserve_insertion_order=false")
        db.execute("CREATE TABLE pool AS SELECT * FROM read_json_auto(?,format='newline_delimited',maximum_object_size=1048576)", [str(projection)])
        require(db.execute("SELECT count(*) FROM pool").fetchone()[0] == novelty["projection"]["rows"] == novelty["queries"], "Novelty row count differs")
        cursor = db.execute("SELECT full_key,cid FROM pool ORDER BY full_key,cid")
        observed = identity_digest(iter(lambda: cursor.fetchone(), None))
        source = sqlite3.connect(pool_path.as_uri() + "?mode=ro", uri=True)
        try:
            expected = identity_digest(source.execute("SELECT full_key,cid FROM candidates ORDER BY full_key,cid"))
        finally:
            source.close()
        require(expected == observed, "Ranking projection is not the full exactly filtered candidate pool")
        n = create_queues(db, seed=seed, queue_size=queue_size)
        db.execute("COPY (SELECT * FROM queues ORDER BY stream,stream_rank) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)", [str(out / "queues.parquet")])
        # DuckDB 1.5.6 COPY misidentifies the filename parameter when a bound
        # parameter also appears inside its SELECT. Bind the selection first.
        db.execute("CREATE TABLE batch1 AS SELECT * FROM queues WHERE stream_rank<=?", [first_batch_each])
        db.execute("COPY (SELECT * FROM batch1 ORDER BY stream,stream_rank) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)",
                   [str(out / "batch1.parquet")])
        db.execute("COPY (SELECT heavy_stratum,element_combination,count(*) AS remaining_pubchem_population FROM n_candidates GROUP BY ALL ORDER BY ALL) TO ? (FORMAT PARQUET,COMPRESSION ZSTD)",
                   [str(out / "novelty_strata.parquet")])
        db.execute("CHECKPOINT")
    finally:
        db.close()
    total_bytes = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    require(total_bytes <= projected_bytes, "STOP: external-sort output/spill exceeded quota-reviewed budget")
    dump_new(out / "receipt.json", {"schema": "expansion_nested_queues_v1", "status": "CANDIDATE_ORDER_COMPLETE_NO_CONFORMERS_COMPUTED",
        "novelty_receipt": reference(novelty_path), "filtered_pool": reference(filtered_path),
        "pool_identity_sha256": observed[1], "pool_molecules": n, "workers": workers,
        "seed": seed, "queue_molecules_each": queue_size, "first_batch_molecules_each": first_batch_each,
        "R_rule": "uniform_sha256_full_identity", "N_rule": "v1_only_lexicographic_novelty_with_exact_size_element_proportional_interleaving",
        "exact_rational_finish_scale": str(SCALE), "maximum_supported_pool": MAX_POOL,
        "wall_seconds": time.monotonic() - started, "observed_total_bytes": total_bytes,
        "queues": reference(out / "queues.parquet"), "batch1": reference(out / "batch1.parquet"),
        "strata": reference(out / "novelty_strata.parquet"), "downstream_features_used": False})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--novelty-receipt", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--quota-receipt", required=True, type=Path)
    p.add_argument("--projected-output-bytes", required=True, type=int)
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--seed", type=int, default=20261025)
    p.add_argument("--queue-size", type=int, default=5_000_000)
    p.add_argument("--first-batch-each", type=int, default=1_250_000)
    p.add_argument("--memory-gb", type=int, default=16)
    p.add_argument("--temporary-gb", type=int, default=64)
    a = p.parse_args()
    run(a.novelty_receipt, a.output, a.quota_receipt, a.projected_output_bytes, workers=a.workers,
        seed=a.seed, queue_size=a.queue_size, first_batch_each=a.first_batch_each,
        memory_gb=a.memory_gb, temporary_gb=a.temporary_gb)


if __name__ == "__main__":
    main()
