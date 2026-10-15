#!/usr/bin/env python3
"""Losslessly compact v3 manifest segments and refresh their hash chain."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

from phychem_mfm.discovery.identity import canonical_sha256
from phychem_mfm.discovery.manifests import validate_nested_manifests


def parse_args():
    parser = argparse.ArgumentParser("Compact equivalent adjacent LMDB ranges in domain manifests")
    parser.add_argument("--manifest-dir", default="manifests/discovery_v3")
    parser.add_argument("--audit-json", default="artifacts/v3/domain_audit.json")
    return parser.parse_args()


def atomic_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name, suffix=".tmp", dir=path.parent)
    os.close(handle)
    try:
        Path(temporary).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def compact_segments(segments):
    indices = []
    metadata = {}
    for segment in segments:
        shard = str(segment["shard"])
        metadata[shard] = {
            "source_size": int(segment["source_size"]),
            "source_mtime_ns": int(segment["source_mtime_ns"]),
        }
        indices.extend((shard, index) for index in range(int(segment["start"]), int(segment["end"]) + 1))
    ordered = sorted(set(indices))
    compacted = []
    for shard, index in ordered:
        if compacted and compacted[-1]["shard"] == shard and compacted[-1]["end"] + 1 == index:
            compacted[-1]["end"] = index
            compacted[-1]["count"] += 1
        else:
            compacted.append({
                "shard": shard, "start": index, "end": index, "count": 1, **metadata[shard],
            })
    return compacted


def refresh_hash(manifest, parent_hash=None):
    payload = dict(manifest)
    payload.pop("pool_hash", None)
    payload["segments"] = compact_segments(payload["segments"])
    if payload["kind"] == "train":
        payload["parent_pool_hash"] = parent_hash
    payload["pool_hash"] = canonical_sha256(payload)
    return payload


def main():
    args = parse_args()
    root = Path(args.manifest_dir)
    train_paths = sorted(root.glob("train_*.json"), key=lambda path: int(path.stem.split("_")[-1]))
    parent_hash = None
    trains = []
    for path in train_paths:
        manifest = refresh_hash(json.loads(path.read_text(encoding="utf-8")), parent_hash)
        parent_hash = manifest["pool_hash"]
        atomic_json(path, manifest)
        trains.append(manifest)
    validate_nested_manifests(trains)
    validation_path = root / "validation.json"
    validation = refresh_hash(json.loads(validation_path.read_text(encoding="utf-8")))
    atomic_json(validation_path, validation)

    audit_path = Path(args.audit_json)
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    audit["train_pools"] = [{
        "pool_id": item["pool_id"], "pool_hash": item["pool_hash"],
        "unique_structure_count": item["unique_structure_count"],
        "path": str(path.resolve()), "domain_composition": item["domain_composition"],
    } for path, item in zip(train_paths, trains)]
    audit["validation_pool"] = {"path": str(validation_path.resolve()), **validation}
    audit["manifest_storage"] = "shard_sorted_adjacent_range_compaction_v3.1"
    atomic_json(audit_path, audit)
    print(json.dumps({
        "train_segment_counts": {item["pool_id"]: len(item["segments"]) for item in trains},
        "validation_segment_count": len(validation["segments"]),
        "largest_train_hash": trains[-1]["pool_hash"],
        "validation_hash": validation["pool_hash"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
