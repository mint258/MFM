#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from phychem_mfm.discovery.manifests import (
    Segment,
    allocate_segments,
    make_pool_manifest,
    validate_nested_manifests,
)
from phychem_mfm.training.data import create_dataset
from phychem_mfm.data.dataset_lmdb import LmdbMoleculeDataset


DEFAULT_TRAIN_SHARDS = (
    "principal_00000001_00300000.lmdb",
    "principal_00300001_00600000.lmdb",
    "principal_00600001_00900000.lmdb",
)
DEFAULT_VALIDATION_SHARD = "unimol_05000001_06000000.lmdb"


def parse_args():
    parser = argparse.ArgumentParser("Build immutable nested discovery-pool manifests")
    parser.add_argument("--data-root", default="/share/home/zixiao/dataset/lmdb_new")
    parser.add_argument("--output-dir", default="manifests/discovery_v2")
    parser.add_argument("--pool-sizes", default="50000,100000,200000,400000")
    parser.add_argument("--validation-size", type=int, default=8192)
    parser.add_argument("--train-shards", nargs="*", default=list(DEFAULT_TRAIN_SHARDS))
    parser.add_argument("--validation-shard", default=DEFAULT_VALIDATION_SHARD)
    parser.add_argument("--filter-max-atoms", type=int, default=196)
    return parser.parse_args()


def molecule_identity(item, shard: str) -> str:
    for field in ("canonical_smiles", "isomeric_smiles", "smiles", "registration_hash"):
        value = getattr(item, field, None)
        if isinstance(value, str) and value.strip():
            return f"{field}:{value.strip()}"
    return f"sample:{shard}:{getattr(item, 'sample_key', '')}"


def scan_segments(data_root: Path, segments, boundaries: set[int], filter_max_atoms: int):
    molecules: set[str] = set()
    boundary_counts: dict[int, int] = {}
    identities: set[str] = set()
    scanned = 0
    over_limit = 0
    for segment_number, segment in enumerate(segments):
        dataset = create_dataset(
            str(data_root / segment.shard),
            segment.start,
            segment.end,
            seed=31000 + segment_number,
        )
        for local_index in range(len(dataset)):
            item = dataset[local_index]
            atom_count = int(item.x.size(0))
            if atom_count > filter_max_atoms:
                over_limit += 1
            identity = molecule_identity(item, segment.shard)
            molecules.add(identity)
            identities.add(identity)
            scanned += 1
            if scanned in boundaries:
                boundary_counts[scanned] = len(molecules)
    return boundary_counts, identities, over_limit


def _append_index(segments: list[Segment], shard: str, real_index: int) -> None:
    if segments and segments[-1].shard == shard and segments[-1].end + 1 == real_index:
        previous = segments[-1]
        segments[-1] = Segment(previous.shard, previous.start, previous.count + 1)
    else:
        segments.append(Segment(shard, int(real_index), 1))


def scan_filtered_prefixes(
    data_root: Path,
    shard_inventory,
    *,
    boundaries: set[int],
    filter_max_atoms: int,
    excluded_molecules: set[str] | None = None,
):
    target = max(boundaries)
    selected = 0
    raw_scanned = 0
    atom_filtered = 0
    molecule_filtered = 0
    molecules: set[str] = set()
    segments: list[Segment] = []
    snapshots = {}
    stats = {}
    excluded_molecules = excluded_molecules or set()
    for shard_number, (shard, length) in enumerate(shard_inventory):
        dataset = LmdbMoleculeDataset(
            str(data_root / shard),
            start_idx=0,
            end_idx=int(length) - 1,
            filter_missing_on_init=False,
        )
        for local_index in range(len(dataset)):
            real_index = int(dataset.idx_list[local_index])
            item = dataset[local_index]
            raw_scanned += 1
            if int(item.x.size(0)) > filter_max_atoms:
                atom_filtered += 1
                continue
            identity = molecule_identity(item, shard)
            if identity in excluded_molecules:
                molecule_filtered += 1
                continue
            _append_index(segments, shard, real_index)
            molecules.add(identity)
            selected += 1
            if selected in boundaries:
                snapshots[selected] = list(segments)
                stats[selected] = {
                    "unique_molecule_count": len(molecules),
                    "raw_scanned_count": raw_scanned,
                    "filtered_out_structure_count": atom_filtered,
                    "excluded_molecule_overlap_count": molecule_filtered,
                }
            if selected == target:
                return snapshots, stats, molecules
    raise RuntimeError(f"Shard inventory ended after {selected} valid structures; required {target}")


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def main():
    args = parse_args()
    data_root = Path(args.data_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    pool_sizes = sorted({int(value) for value in args.pool_sizes.split(",")})
    if not pool_sizes or pool_sizes[0] <= 0:
        raise ValueError("pool sizes must be positive")

    shard_inventory = []
    for shard in args.train_shards:
        probe = LmdbMoleculeDataset(
            str(data_root / shard),
            start_idx=0,
            end_idx=0,
            filter_missing_on_init=False,
        )
        shard_inventory.append((shard, int(probe._len)))
    segment_snapshots, pool_stats, train_molecules = scan_filtered_prefixes(
        data_root,
        shard_inventory,
        boundaries=set(pool_sizes),
        filter_max_atoms=args.filter_max_atoms,
    )

    manifests = []
    parent_hash = None
    for size in pool_sizes:
        manifest = make_pool_manifest(
            pool_id=f"DISCOVERY_POOL_{size // 1000}K_V1",
            kind="train",
            data_root=data_root,
            segments=segment_snapshots[size],
            unique_molecule_count=pool_stats[size]["unique_molecule_count"],
            parent_pool_hash=parent_hash,
            filter_max_atoms=args.filter_max_atoms,
            selection_rule="ordered_filtered_prefix_over_declared_shards",
            raw_scanned_count=pool_stats[size]["raw_scanned_count"],
            filtered_out_structure_count=pool_stats[size]["filtered_out_structure_count"],
        )
        manifests.append(manifest)
        parent_hash = str(manifest["pool_hash"])
        write_manifest(output_dir / f"train_{size}.json", manifest)
    validate_nested_manifests(manifests)

    validation_probe = LmdbMoleculeDataset(
        str(data_root / args.validation_shard),
        start_idx=0,
        end_idx=0,
        filter_missing_on_init=False,
    )
    validation_segments, validation_stats, validation_molecules = scan_filtered_prefixes(
        data_root,
        [(args.validation_shard, int(validation_probe._len))],
        boundaries={args.validation_size},
        filter_max_atoms=args.filter_max_atoms,
        excluded_molecules=train_molecules,
    )
    val_stats = validation_stats[args.validation_size]
    validation_manifest = make_pool_manifest(
        pool_id="DISCOVERY_VALIDATION_8K_V1",
        kind="validation",
        data_root=data_root,
        segments=validation_segments[args.validation_size],
        unique_molecule_count=len(validation_molecules),
        filter_max_atoms=args.filter_max_atoms,
        selection_rule="ordered_filtered_molecule_disjoint_prefix",
        raw_scanned_count=val_stats["raw_scanned_count"],
        filtered_out_structure_count=val_stats["filtered_out_structure_count"],
        excluded_molecule_overlap_count=val_stats["excluded_molecule_overlap_count"],
    )
    write_manifest(output_dir / "validation.json", validation_manifest)
    index = {
        "format_version": 1,
        "train_pools": [
            {
                "pool_id": item["pool_id"],
                "path": str(output_dir / f"train_{item['unique_structure_count']}.json"),
                "pool_hash": item["pool_hash"],
                "unique_structure_count": item["unique_structure_count"],
                "unique_molecule_count": item["unique_molecule_count"],
            }
            for item in manifests
        ],
        "validation_pool": {
            "pool_id": validation_manifest["pool_id"],
            "path": str(output_dir / "validation.json"),
            "pool_hash": validation_manifest["pool_hash"],
            "unique_structure_count": validation_manifest["unique_structure_count"],
            "unique_molecule_count": validation_manifest["unique_molecule_count"],
        },
    }
    write_manifest(output_dir / "index.json", index)
    print(json.dumps(index, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
