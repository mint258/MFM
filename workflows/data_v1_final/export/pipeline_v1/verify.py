"""Re-read original Parquet for random fieldwise checks; spawn-owned LMDB handles."""
from __future__ import annotations
import argparse
import concurrent.futures
import hashlib
import json
import multiprocessing as mp
import os
from pathlib import Path
import time
import numpy as np
from .export import resolve
from .io import (batches, check_allocation, connect, manifest, rank_hash, read_json,
                 scalar, verify, write_json)
from .source import geometry_arrays, source_columns, target_arrays
from .masks import decode_row
from .granular_store import GranularFamilyReader as FamilyReader
from wire_v1.codec import canonical_json
from wire_v1.mapping import preflight_registry
from wire_v1.store import file_ref


def compare(expected, actual):
    if set(expected) != set(actual):
        raise ValueError("ROUNDTRIP_ARRAY_SET_DIFFERS")
    digest = hashlib.sha256()
    for name, value in sorted(expected.items()):
        converted = value.astype("<f4") if value.dtype.kind == "f" else value
        result = actual[name]
        if result.shape != converted.shape or result.dtype != converted.dtype or not np.array_equal(result, converted, equal_nan=True):
            raise ValueError("ROUNDTRIP_SOURCE_FIELD_DIFFERS_BEYOND_FLOAT32:" + name)
        # Signed zero and exact float32 representation must also agree. NaN
        # payload bits are not physical values; mask/reason is compared exactly.
        finite = np.isfinite(converted) if converted.dtype.kind == "f" else np.ones(converted.shape, bool)
        if result[finite].tobytes() != converted[finite].tobytes():
            raise ValueError("ROUNDTRIP_FLOAT32_BYTES_OR_SIGNED_ZERO_DIFFERS")
        digest.update(name.encode()); digest.update(result[finite].tobytes())
    return digest.hexdigest()


def check_source_group(task):
    stage_path, output, specs, compiled, source_index, rg, requests = task
    db = connect(stage_path, readonly=True)
    readers = {}
    checked, components = 0, 0
    digest = hashlib.sha256()
    try:
        by_row = {}
        for request in requests:
            by_row.setdefault(request["row_number"], []).append(request)
        number = 0
        spec = specs[source_index]
        verify(spec["file"])
        for batch in batches(spec["file"], row_groups=[rg], columns=source_columns(spec), batch_size=16, hash_input=False):
            for row in batch.to_pylist():
                jobs = by_row.get(number, [])
                number += 1
                if not jobs:
                    continue
                geometry = resolve(db, row, spec)
                if geometry is None:
                    raise ValueError("ROUNDTRIP_CANONICAL_SOURCE_IDENTITY_NO_LONGER_RESOLVES")
                for job in jobs:
                    if geometry["geometry_id"] != job["geometry_id"]:
                        raise ValueError("ROUNDTRIP_SOURCE_LOCATOR_IDENTITY_DIFFERS")
                    store = job["store_name"]
                    if store not in readers:
                        readers[store] = FamilyReader(Path(output) / store)
                    metadata, actual = readers[store].get(job["geometry_id"])
                    if any(metadata[k] != geometry[k] for k in ("molecule_id", "geometry_source", "effective_role", "source_role", "n_atoms", "parent_geometry_id", "view_id")):
                        raise ValueError("ROUNDTRIP_METADATA_IDENTITY_ROLE_OR_SHAPE_DIFFERS")
                    part = job["part"]
                    annotations = {}
                    def loader(cs):
                        if "column" in cs:
                            from .source import extract
                            return extract(row, cs)
                        code = row[cs["task_code_column"]] if "task_code_column" in cs else cs["task_code"]
                        mask = db.execute("SELECT payload FROM compact_masks WHERE geometry_id=? AND task_code=?", (geometry["geometry_id"], code)).fetchone()
                        if mask is None:
                            raise ValueError("ROUNDTRIP_COMPACT_MASK_BINDING_MISSING")
                        return decode_row(mask[0])
                    expected = geometry_arrays(row, spec, geometry["n_atoms"]) if part == "__geometry__" else target_arrays(row, spec, compiled["physical_targets"][part], geometry["n_atoms"], compact_loader=loader, annotations=annotations)
                    for tid, annotation in annotations.items():
                        if tid == "_source_null_fields":
                            if not set(annotation) <= set(metadata.get("source_null_fields_with_masked_nan_placeholder", [])):
                                raise ValueError("ROUNDTRIP_SOURCE_NULL_PLACEHOLDER_ANNOTATION_DIFFERS")
                            continue
                        if metadata.get("reason_granularity", {}).get(tid) != annotation:
                            raise ValueError("ROUNDTRIP_REASON_GRANULARITY_HEADER_DIFFERS")
                    subset = {name: actual[name] for name in expected}
                    digest.update(compare(expected, subset).encode())
                    checked += 1; components += len(expected)
        if checked != len(requests):
            raise ValueError("SOURCE_ROUNDTRIP_REQUEST_COUNT_DIFFERS")
    finally:
        for reader in readers.values():
            reader.close()
        db.close()
    return {"source_index": source_index, "row_group": rg, "pieces_checked": checked,
            "arrays_checked": components, "sha256": digest.hexdigest(), "pid": os.getpid(), "all_handles_closed": True}


_BARRIER = None


def read_initializer(barrier):
    global _BARRIER
    _BARRIER = barrier
    _BARRIER.wait(timeout=300)


def random_reader(task):
    index, root, records = task
    readers = {}
    digest, count = hashlib.sha256(), 0
    start = time.monotonic()
    try:
        _BARRIER.wait(timeout=300)
        for store, geometry_id in records:
            if store not in readers:
                readers[store] = FamilyReader(Path(root) / store)
            metadata, arrays = readers[store].get(geometry_id)
            digest.update(canonical_json(metadata))
            for name, value in sorted(arrays.items()):
                digest.update(name.encode()); digest.update(value.tobytes())
            count += 1
    finally:
        for reader in readers.values():
            reader.close()
    return {"index": index, "pid": os.getpid(), "records": count, "sha256": digest.hexdigest(),
            "all_handles_closed": True, "seconds": time.monotonic() - start}


def run(export_manifest, output, *, fixture=False, sample_records=10000, seed=20261025):
    check_allocation(fixture)
    if not fixture and sample_records != 10000:
        raise ValueError("PRODUCTION_REQUIRES_10000_RANDOM_SOURCE_RECORDS")
    if sample_records <= 0 or Path(output).exists():
        raise ValueError("FRESH_RECEIPT_AND_POSITIVE_COUNT_REQUIRED")
    release, release_ref = manifest(export_manifest)
    stage = verify(release["stage"])
    config_refs = release["config_sources"]
    source = read_json(verify(config_refs["source_manifest"]))
    compiled = preflight_registry(read_json(verify(config_refs["registry"])), read_json(verify(config_refs["mapping"])), require_final=not release["candidate"])
    root = Path(export_manifest).parent
    for store in release["stores"]:
        verify(store["manifest"]); verify(store["data"])
        with FamilyReader(store["path"]) as reader:
            if reader.count != store["records"] or reader.molecule_count != store["molecules"]:
                raise ValueError("ACTUAL_LMDB_COUNTS_DIFFER_FROM_MANIFEST")
    db = connect(stage, readonly=True)
    try:
        db.create_function("sample_rank", 2, lambda store, gid: rank_hash(seed, store, gid), deterministic=True)
        # 10k is the bounded requested validation set, never the whole corpus.
        samples = [dict(r) for r in db.execute("SELECT * FROM exported ORDER BY sample_rank(store_name,geometry_id),store_name,geometry_id LIMIT ?", (sample_records,))]
        if len(samples) != sample_records:
            raise ValueError("EXPORT_TOO_SMALL_FOR_10000_RECORD_ROUNDTRIP_NO_DOWNGRADE")
        groups = {}
        for row in samples:
            for part in json.loads(row["parts_json"]):
                locator = db.execute("SELECT source_index,row_group,row_number FROM pieces WHERE geometry_id=? AND part=?", (row["geometry_id"], part)).fetchone()
                if locator is None:
                    raise ValueError("SOURCE_LOCATOR_MISSING")
                key = locator["source_index"], locator["row_group"]
                groups.setdefault(key, []).append({"store_name": row["store_name"], "geometry_id": row["geometry_id"], "part": part, "row_number": locator["row_number"]})
        source_results = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=16, mp_context=mp.get_context("spawn")) as pool:
            tasks = [(str(stage), str(root), source["files"], compiled, i, rg, requests) for (i, rg), requests in sorted(groups.items())]
            source_results = list(pool.map(check_source_group, tasks, chunksize=1))
        if sum(r["pieces_checked"] for r in source_results) != sum(len(json.loads(r["parts_json"])) for r in samples):
            raise ValueError("TOTAL_SOURCE_COMPARISON_COUNT_DIFFERS")
        ctx = mp.get_context("spawn")
        barrier = ctx.Barrier(16)
        queues = [[] for _ in range(16)]
        # Every worker owns at least one handle/read even for small fixtures.
        for index in range(max(16, len(samples))):
            row = samples[index % len(samples)]
            queues[index % 16].append((row["store_name"], row["geometry_id"]))
        start = time.monotonic()
        with concurrent.futures.ProcessPoolExecutor(max_workers=16, mp_context=ctx, initializer=read_initializer, initargs=(barrier,)) as pool:
            spawn_results = list(pool.map(random_reader, [(i, str(root), q) for i, q in enumerate(queues)], chunksize=1))
        seconds = time.monotonic() - start
        if len({r["pid"] for r in spawn_results}) != 16 or not all(r["all_handles_closed"] for r in spawn_results):
            raise ValueError("SIXTEEN_DISTINCT_SPAWN_READERS_NOT_CLOSED")
        result = {"status": "FIXTURE_ONLY" if fixture else "SOURCE_FIELDWISE_ROUNDTRIP_AND_SPAWN_READBACK_PASS", "export_manifest": release_ref,
            "records_checked_against_original_parquet": len(samples), "random_seed": seed, "sampling_algorithm": "SHA256-uniform-order-v1 over store+geometry IDs", "allowed_difference": "exact source float64 -> float32 once; integer/mask/reason exact", "source_results": source_results,
            "source_readback_groups_disjoint": True, "spawn_start_method": "spawn", "spawn_workers": spawn_results,
            "spawn_workers_all_joined": True, "spawn_reads": sum(r["records"] for r in spawn_results),
            "spawn_elapsed_including_startup_seconds": seconds, "spawn_records_per_second_including_startup": sum(r["records"] for r in spawn_results) / seconds,
            "node": os.uname().nodename, "gpu_node_local_disk_benchmark": False, "contract_finalized": False, "d3_accepted": False}
        write_json(output, result)
        return result
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fixture", action="store_true")
    parser.add_argument("--sample-records", type=int, default=10000)
    args = parser.parse_args()
    run(args.export_manifest, args.output, fixture=args.fixture, sample_records=args.sample_records)


if __name__ == "__main__":
    main()
