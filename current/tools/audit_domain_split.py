#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from phychem_mfm.discovery.domain import (
    DOMAIN_PROTOCOL_VERSION,
    audit_leakage,
    matched_manifest,
    scan_domain_records,
)
from phychem_mfm.discovery.manifests import load_manifest


DEFAULT_PRINCIPAL = [
    "principal_00000001_00300000.lmdb", "principal_00300001_00600000.lmdb",
    "principal_00600001_00900000.lmdb",
]
DEFAULT_MOLECULE = [
    "unimol_01000001_02000000.lmdb", "unimol_02000001_03000000.lmdb",
    "unimol_03000001_04000000.lmdb", "unimol_04000001_05000000.lmdb",
    "unimol_05000001_06000000.lmdb",
]


def parse_args():
    parser = argparse.ArgumentParser("Audit/build parent-disjoint molecule/principal domain-matched v3 pools")
    parser.add_argument("--data-root", default="/share/home/zixiao/dataset/lmdb_new")
    parser.add_argument("--principal-shards", nargs="*", default=DEFAULT_PRINCIPAL)
    parser.add_argument("--molecule-shards", nargs="*", default=DEFAULT_MOLECULE)
    parser.add_argument("--pool-sizes", default="50000,100000,200000,400000")
    parser.add_argument("--principal-ratio", type=float, default=0.5)
    parser.add_argument("--validation-size", type=int, default=8192)
    parser.add_argument("--filter-max-atoms", type=int, default=196)
    parser.add_argument("--output-dir", default="manifests/discovery_v3")
    parser.add_argument("--output-json", default="artifacts/v3/domain_audit.json")
    parser.add_argument("--output-csv", default="artifacts/v3/domain_audit.csv")
    parser.add_argument(
        "--frozen-validation-manifest", default=None,
        help="Extend nested train pools while preserving an existing parent-disjoint validation pool",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    if not 0 < args.principal_ratio < 1:
        raise ValueError("--principal-ratio must be strictly between 0 and 1")
    sizes = sorted({int(item) for item in args.pool_sizes.split(",")})
    largest = max(sizes)
    principal_train = round(largest * args.principal_ratio)
    molecule_train = largest - principal_train
    principal_val = round(args.validation_size * args.principal_ratio)
    molecule_val = args.validation_size - principal_val

    frozen_validation = load_manifest(args.frozen_validation_manifest) if args.frozen_validation_manifest else None
    frozen_records = [] if frozen_validation is None else list(frozen_validation.get("records", []))
    if frozen_validation is not None and len(frozen_records) != int(frozen_validation["unique_structure_count"]):
        raise RuntimeError("Frozen validation manifest must retain its per-record parent index")
    frozen_parents = {str(item["parent_molecule_id"]) for item in frozen_records}

    principal = scan_domain_records(
        args.data_root, args.principal_shards, max_atoms=args.filter_max_atoms,
        maximum_records=principal_train + principal_val * 40,
    )
    molecule = scan_domain_records(
        args.data_root, args.molecule_shards, max_atoms=args.filter_max_atoms,
        maximum_records=molecule_train + molecule_val * 40,
    )
    scanned_records = principal + molecule
    if frozen_validation is not None:
        principal = [item for item in principal if item.parent_molecule_id not in frozen_parents]
        molecule = [item for item in molecule if item.parent_molecule_id not in frozen_parents]
    if len(principal) < principal_train or len(molecule) < molecule_train:
        raise RuntimeError("Shard scan did not find enough records after frozen-validation parent exclusion")
    combined_train = stratified_prefix(principal[:principal_train], molecule[:molecule_train], args.principal_ratio)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    manifests = []
    parent_hash = None
    largest_train_records = []
    for size in sizes:
        selected = combined_train[:size]
        manifest = matched_manifest(
            pool_id=f"DISCOVERY_POOL_{size // 1000}K_DOMAIN_MATCHED_V3", kind="train",
            data_root=args.data_root, records=selected, filter_max_atoms=args.filter_max_atoms,
            parent_pool_hash=parent_hash,
        )
        path = output_dir / f"train_{size}.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        manifests.append({"path": str(path.resolve()), **manifest})
        parent_hash = manifest["pool_hash"]
        if size == largest:
            largest_train_records = selected

    blocked = {item.parent_molecule_id for item in largest_train_records}
    if frozen_validation is None:
        val_principal = [item for item in principal[principal_train:] if item.parent_molecule_id not in blocked][:principal_val]
        val_molecule = [item for item in molecule[molecule_train:] if item.parent_molecule_id not in blocked][:molecule_val]
        if len(val_principal) != principal_val or len(val_molecule) != molecule_val:
            raise RuntimeError("Shard scan did not find enough parent-disjoint validation structures")
        validation_records = stratified_prefix(val_principal, val_molecule, args.principal_ratio)
        validation = matched_manifest(
            pool_id="DISCOVERY_VALIDATION_DOMAIN_MATCHED_V3", kind="validation",
            data_root=args.data_root, records=validation_records, filter_max_atoms=args.filter_max_atoms,
            include_record_index=True,
        )
    else:
        by_identity = {
            (item.shard, item.real_index): item for item in scanned_records
            if item.parent_molecule_id in frozen_parents
        }
        validation_records = []
        for item in frozen_records:
            key = (str(item["shard"]), int(item["real_index"]))
            if key not in by_identity:
                raise RuntimeError(f"Frozen validation record was not recovered by the domain scan: {key}")
            validation_records.append(by_identity[key])
        validation = frozen_validation
    validation_path = output_dir / "validation.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    audit = {
        "domain_protocol_version": DOMAIN_PROTOCOL_VERSION,
        "policy": {"principal_ratio": args.principal_ratio, "molecule_ratio": 1 - args.principal_ratio},
        "train_pools": [{
            "pool_id": item["pool_id"], "pool_hash": item["pool_hash"],
            "unique_structure_count": item["unique_structure_count"], "path": item["path"],
            "domain_composition": item["domain_composition"],
        } for item in manifests],
        "validation_pool": {"path": str(validation_path.resolve()), **validation},
        "largest_pool_audit": audit_leakage(largest_train_records, validation_records),
    }
    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(audit, indent=2, sort_keys=True), encoding="utf-8")
    rows = []
    for item in audit["train_pools"] + [audit["validation_pool"]]:
        for domain, count in item["domain_composition"]["structure_counts"].items():
            rows.append({"pool_id": item["pool_id"], "domain": domain, "structure_count": count,
                         "ratio": item["domain_composition"]["structure_ratios"][domain]})
    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output_csv).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    print(json.dumps(audit, indent=2, sort_keys=True))


def stratified_prefix(principal, molecule, principal_ratio: float):
    """Interleave domains so every requested prefix is nested and near its target ratio."""
    result = []
    p_index = m_index = 0
    total = len(principal) + len(molecule)
    for next_size in range(1, total + 1):
        desired_principal = round(next_size * principal_ratio)
        take_principal = p_index < desired_principal and p_index < len(principal)
        if take_principal or m_index >= len(molecule):
            result.append(principal[p_index]); p_index += 1
        else:
            result.append(molecule[m_index]); m_index += 1
    return result


if __name__ == "__main__":
    main()
