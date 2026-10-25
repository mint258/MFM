"""Deterministic disjoint R/N queues; no downstream information in scores.

This bounded reference implementation is for ranking pilots and parity tests.
Full-pool sorting must use the same keys in a parallel external sorter after a
cost/storage pilot; it must not load 10 million Python dictionaries into RAM.
"""
from __future__ import annotations

from collections import defaultdict
from fractions import Fraction
import heapq
import math

from .common import require, stable_hash

RANK_FIELDS = {"cid", "full_key", "heavy_atoms", "element_combination", "generic_murcko", "generic_ring_systems",
               "nearest_v1_tanimoto", "v1_scaffold_count", "v1_ring_system_count", "v1_reference_sha256"}


def heavy_bin(n):
    for edge in (10, 20, 30, 50, 75, 100):
        if n <= edge:
            return str(edge)
    return "above_100"  # A stratum, never an exclusion or implicit upper bound.


def projected_row(row):
    require(set(row) == RANK_FIELDS, "Ranking projection must contain exactly the reviewed v1/candidate-only fields")
    require(type(row["cid"]) is int and row["cid"] > 0 and type(row["heavy_atoms"]) is int and row["heavy_atoms"] > 0, "Invalid candidate identity/size")
    require(type(row["v1_scaffold_count"]) is int and row["v1_scaffold_count"] >= 0 and
            type(row["v1_ring_system_count"]) is int and row["v1_ring_system_count"] >= 0, "Invalid v1 counts")
    require(type(row["nearest_v1_tanimoto"]) in (int, float) and 0 <= row["nearest_v1_tanimoto"] <= 1, "Exact nearest-v1 Tanimoto required")
    require(isinstance(row["v1_reference_sha256"], str) and len(row["v1_reference_sha256"]) == 64, "Missing v1 reference pin")
    return row


def novelty_key(row, seed):
    """Lexicographic recipe. Counts/distances depend exclusively on v1/PubChem."""
    return (row["v1_scaffold_count"] == 0, row["v1_ring_system_count"] == 0,
            1 - row["nearest_v1_tanimoto"], -math.log1p(row["v1_scaffold_count"]),
            -math.log1p(row["v1_ring_system_count"]), stable_hash("N-tie", seed, row["full_key"]))


def queues(rows, *, seed=20261025, queue_size=5_000_000, max_rows=100_000):
    """Uniform R followed by size/element-proportional novelty N.

    N weighted-fair finish times use exact rational arithmetic; no float rounding
    can reorder strata. Ties use stratum text and full key. Prefixes are nested.
    """
    pool = []
    identities = set()
    references = set()
    for raw in rows:
        require(len(pool) < max_rows, "Bounded reference ranker cap reached; use reviewed external sorting")
        row = projected_row(raw)
        require(row["full_key"] not in identities, "PubChem full-key deduplication required before ranking")
        identities.add(row["full_key"])
        references.add(row["v1_reference_sha256"])
        pool.append(row)
    require(len(references) == 1, "Mixed v1 novelty references")
    require(len(pool) >= 2 * queue_size and queue_size > 0, "Insufficient disjoint R/N pool")
    pool.sort(key=lambda r: (stable_hash("R-uniform", seed, r["full_key"]), r["full_key"], r["cid"]))
    r_queue, remainder = pool[:queue_size], pool[queue_size:]
    strata = defaultdict(list)
    for row in remainder:
        strata[(heavy_bin(row["heavy_atoms"]), row["element_combination"])].append(row)
    for group in strata.values():
        group.sort(key=lambda r: novelty_key(r, seed), reverse=True)
    heap = []
    for stratum, group in strata.items():
        heapq.heappush(heap, (Fraction(1, 2 * len(group)), stratum, 0))
    n_queue = []
    while len(n_queue) < queue_size:
        _, stratum, index = heapq.heappop(heap)
        group = strata[stratum]
        n_queue.append(group[index])
        index += 1
        if index < len(group):
            heapq.heappush(heap, (Fraction(2 * index + 1, 2 * len(group)), stratum, index))
    return {stream: [{"stream": stream, "stream_rank": rank, "cid": row["cid"], "full_key": row["full_key"]}
                     for rank, row in enumerate(group, 1)] for stream, group in (("R", r_queue), ("N", n_queue))}


def release_gate(*, screen_receipt, regression_receipt, decontamination_receipt, novelty_receipt):
    require(screen_receipt.get("status") == "COMPLETE" and screen_receipt.get("complete_source") is True,
            "No final ranking from a bounded prefix screening pilot")
    require(regression_receipt.get("status") == "PASS" and regression_receipt.get("agreement", 0) >= .999 and
            regression_receipt.get("unexplained_mismatches") == 0 and regression_receipt.get("full_v1_selection_regression_passed") is True,
            "Full original-input v1 selection regression has not closed")
    require(decontamination_receipt.get("schema") == "expansion_filtered_pool_v1" and decontamination_receipt.get("status") == "COMPLETE" and
            decontamination_receipt.get("all_sources_all_splits_verified") is True,
            "All-source identity index alone does not prove that the candidate pool was filtered")
    require(novelty_receipt.get("nearest_similarity_exact") is True and novelty_receipt.get("downstream_features_used") is False and
            novelty_receipt.get("fingerprint_recipe") == "ECFP4_2048_radius2_chiralityFalse_rdkit2025.09.5",
            "Missing exact v1-only novelty evidence")
    return True
