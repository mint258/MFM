#!/usr/bin/env python3
"""Extend a quality-filtered nested pool while freezing canonical validation."""

from __future__ import annotations

import argparse
import collections
import csv
import json
from pathlib import Path

from phychem_mfm.data.dataset_lmdb import LmdbMoleculeDataset
from phychem_mfm.discovery.domain import (
    DomainRecord,
    audit_leakage,
    domain_from_shard,
    matched_manifest,
    parent_molecule_identity,
    records_to_segments,
)
from phychem_mfm.discovery.identity import canonical_sha256
from tools.build_quality_filtered_manifests import (
    DEFAULT_MOLECULE,
    DEFAULT_PRINCIPAL,
    attach_quality_metadata,
    quality_reasons,
    stratified_prefix,
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="/share/home/zixiao/dataset/lmdb_new")
    parser.add_argument("--quality-policy", default="configs/iclr2027/data_quality_policy_v3.json")
    parser.add_argument("--fixed-validation-manifest", required=True)
    parser.add_argument("--parent-train-manifest", required=True)
    parser.add_argument("--target-size", type=int, required=True)
    parser.add_argument("--principal-ratio", type=float, default=0.5)
    parser.add_argument("--filter-max-atoms", type=int, default=196)
    parser.add_argument("--principal-shards", nargs="*", default=DEFAULT_PRINCIPAL)
    parser.add_argument("--molecule-shards", nargs="*", default=DEFAULT_MOLECULE)
    parser.add_argument("--output-manifest", required=True)
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--quarantine-csv", required=True)
    return parser.parse_args()


def validation_records(manifest: dict) -> list[DomainRecord]:
    records = manifest.get("records", [])
    if not records:
        raise ValueError("Fixed validation manifest must embed its record index")
    return [DomainRecord(**item) for item in records]


def scan_training_domain(*, root, shards, count, blocked_parents, policy, max_atoms):
    selected = []
    quarantine = []
    counters = collections.Counter()
    for shard in shards:
        probe = LmdbMoleculeDataset(str(root / shard), start_idx=0, end_idx=0, filter_missing_on_init=False)
        dataset = LmdbMoleculeDataset(
            str(root / shard), start_idx=0, end_idx=int(probe._len) - 1, filter_missing_on_init=False,
        )
        domain = domain_from_shard(shard)
        for local_index in range(len(dataset)):
            real_index = int(dataset.idx_list[local_index])
            item = dataset[local_index]
            counters["raw_scanned"] += 1
            parent = parent_molecule_identity(item, shard, real_index)
            if parent in blocked_parents:
                counters["fixed_validation_parent_excluded"] += 1
                continue
            reasons = quality_reasons(item, domain, policy, max_atoms)
            sample_key = str(getattr(item, "sample_key", "")).strip() or f"{Path(shard).name}:{real_index}"
            if reasons:
                counters["quality_quarantined"] += 1
                for reason in reasons:
                    counters[f"reason:{reason}"] += 1
                quarantine.append({
                    "domain": domain,
                    "shard": shard,
                    "real_index": real_index,
                    "sample_key": sample_key,
                    "parent_molecule_id": parent,
                    "reasons": ";".join(reasons),
                    "recoverable": True,
                })
                continue
            selected.append(DomainRecord(
                shard=shard,
                real_index=real_index,
                domain=domain,
                parent_molecule_id=parent,
                structure_id=sample_key,
                atom_count=int(item.x.size(0)),
            ))
            counters["train_selected"] += 1
            if len(selected) == count:
                return selected, quarantine, counters
    raise RuntimeError(f"Shard inventory exhausted: selected={len(selected)}/{count} for {shards}")


def segment_identity(segments):
    return [(item["shard"], int(item["start"]), int(item["end"]), int(item["count"])) for item in segments]


def main():
    args = parse_args()
    if not 0 < args.principal_ratio < 1:
        raise ValueError("--principal-ratio must be strictly between zero and one")
    validation = json.loads(Path(args.fixed_validation_manifest).read_text(encoding="utf-8"))
    parent_manifest = json.loads(Path(args.parent_train_manifest).read_text(encoding="utf-8"))
    if args.target_size <= int(parent_manifest["unique_structure_count"]):
        raise ValueError("--target-size must exceed the parent train manifest size")
    fixed_records = validation_records(validation)
    blocked = {item.parent_molecule_id for item in fixed_records}
    policy = json.loads(Path(args.quality_policy).read_text(encoding="utf-8"))
    root = Path(args.data_root).resolve()
    p_count = round(args.target_size * args.principal_ratio)
    m_count = args.target_size - p_count
    principal, p_quarantine, p_counts = scan_training_domain(
        root=root, shards=args.principal_shards, count=p_count, blocked_parents=blocked,
        policy=policy, max_atoms=args.filter_max_atoms,
    )
    molecule, m_quarantine, m_counts = scan_training_domain(
        root=root, shards=args.molecule_shards, count=m_count, blocked_parents=blocked,
        policy=policy, max_atoms=args.filter_max_atoms,
    )
    combined = stratified_prefix(principal, molecule, args.principal_ratio)
    parent_size = int(parent_manifest["unique_structure_count"])
    prefix_segments = [item.to_dict(root) for item in records_to_segments(combined[:parent_size])]
    if segment_identity(prefix_segments) != segment_identity(parent_manifest["segments"]):
        raise RuntimeError("Extended selection does not preserve the declared parent pool exactly")
    leakage = audit_leakage(combined, fixed_records)
    if not leakage["domain_matched"]:
        raise RuntimeError(f"Extended split failed fixed-validation audit: {leakage}")
    total_counts = collections.Counter(p_counts); total_counts.update(m_counts)
    manifest = matched_manifest(
        pool_id=f"DISCOVERY_POOL_{args.target_size // 1000}K_DOMAIN_MATCHED_QUALITY_V3",
        kind="train",
        data_root=root,
        records=combined,
        filter_max_atoms=args.filter_max_atoms,
        parent_pool_hash=parent_manifest["pool_hash"],
    )
    manifest = attach_quality_metadata(manifest, policy, total_counts)
    manifest.pop("pool_hash")
    manifest["fixed_validation_manifest_hash"] = validation["pool_hash"]
    manifest["extension_parent_pool_hash"] = parent_manifest["pool_hash"]
    manifest["pool_hash"] = canonical_sha256(manifest)
    output_manifest = Path(args.output_manifest)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")

    quarantine = p_quarantine + m_quarantine
    quarantine_path = Path(args.quarantine_csv)
    quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["domain", "shard", "real_index", "sample_key", "parent_molecule_id", "reasons", "recoverable"]
    with quarantine_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(quarantine)
    report = {
        "report_type": "QualityFilteredPoolExtension",
        "data_quality_protocol_version": policy["version"],
        "data_quality_policy_hash": canonical_sha256(policy),
        "no_source_lmdb_modification": True,
        "target_size": args.target_size,
        "parent_train_manifest": str(Path(args.parent_train_manifest).resolve()),
        "parent_pool_hash": parent_manifest["pool_hash"],
        "parent_prefix_preserved": True,
        "fixed_validation_manifest": str(Path(args.fixed_validation_manifest).resolve()),
        "fixed_validation_manifest_hash": validation["pool_hash"],
        "leakage_audit": leakage,
        "scan_counts": dict(sorted(total_counts.items())),
        "quarantine_count": len(quarantine),
        "quarantine_ledger": str(quarantine_path.resolve()),
        "output_manifest": str(output_manifest.resolve()),
        "output_pool_hash": manifest["pool_hash"],
    }
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
