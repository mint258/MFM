#!/usr/bin/env python3
"""Build recoverable, quality-filtered, domain-matched nested manifests."""

from __future__ import annotations

import argparse
import collections
import csv
import json
import math
from pathlib import Path

import torch

from phychem_mfm.data.dataset_lmdb import LmdbMoleculeDataset
from phychem_mfm.discovery.domain import (
    DomainRecord, audit_leakage, domain_from_shard, matched_manifest, parent_molecule_identity,
)
from phychem_mfm.discovery.identity import canonical_sha256


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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", default="/share/home/zixiao/dataset/lmdb_new")
    parser.add_argument("--quality-policy", default="configs/iclr2027/data_quality_policy_v3.json")
    parser.add_argument("--pool-sizes", default="50000,100000,200000,400000,800000")
    parser.add_argument("--validation-size", type=int, default=8000)
    parser.add_argument("--principal-ratio", type=float, default=0.5)
    parser.add_argument("--filter-max-atoms", type=int, default=196)
    parser.add_argument("--principal-shards", nargs="*", default=DEFAULT_PRINCIPAL)
    parser.add_argument("--molecule-shards", nargs="*", default=DEFAULT_MOLECULE)
    parser.add_argument("--output-dir", default="manifests/discovery_v3_quality")
    parser.add_argument("--output-json", default="artifacts/v3/data_quality/quality_manifest_build.json")
    parser.add_argument("--quarantine-csv", default="artifacts/v3/data_quality/quarantine_ledger.csv")
    return parser.parse_args()


def outside_robust_band(value: float, spec: dict[str, object]) -> bool:
    return abs(float(value) - float(spec["median"])) > (
        float(spec["robust_sigma_multiplier"]) * float(spec["robust_sigma"])
    )


def quality_reasons(item, domain: str, policy: dict[str, object], max_atoms: int) -> list[str]:
    reasons = []
    x = getattr(item, "x", None); pos = getattr(item, "pos", None)
    n_atoms = int(x.size(0)) if isinstance(x, torch.Tensor) else 0
    if n_atoms <= 0 or n_atoms > max_atoms:
        reasons.append("invalid_atom_count")
    if not isinstance(x, torch.Tensor) or x.numel() != n_atoms or not torch.isfinite(x.float()).all():
        reasons.append("invalid_elements")
    if not isinstance(pos, torch.Tensor) or pos.shape != (n_atoms, 3) or not torch.isfinite(pos).all():
        reasons.append("invalid_coordinates")

    energy = float(getattr(item, "energy", math.nan))
    if not math.isfinite(energy):
        reasons.append("invalid_energy_non_finite")
    elif str(getattr(item, "energy_unit", "unknown")) != str(policy["energy"]["unit"]):
        reasons.append("invalid_energy_unit")
    else:
        domain_spec = {
            **policy["energy"]["by_domain"][domain],
            "robust_sigma_multiplier": policy["energy"]["robust_sigma_multiplier"],
        }
        if outside_robust_band(energy, domain_spec):
            reasons.append("energy_domain_robust_outlier")
        if n_atoms and outside_robust_band(energy / n_atoms, policy["energy_per_atom_diagnostic"]):
            reasons.append("energy_per_atom_robust_outlier")

    charges = getattr(item, "y", None); charge_mask = getattr(item, "charge_mask", None)
    if isinstance(charges, torch.Tensor) and isinstance(charge_mask, torch.Tensor):
        selected = charges.reshape(-1)[charge_mask.reshape(-1).bool()].float()
        if selected.numel() and not torch.isfinite(selected).all():
            reasons.append("invalid_charge_non_finite")
        elif selected.numel():
            center = float(policy["atomic_charge"]["median"])
            limit = float(policy["atomic_charge"]["robust_sigma_multiplier"]) * float(policy["atomic_charge"]["robust_sigma"])
            if bool(((selected - center).abs() > limit).any()):
                reasons.append("atomic_charge_robust_outlier")

    desc = getattr(item, "rdkit_graph_desc", None); desc_mask = getattr(item, "rdkit_graph_desc_mask", None)
    if isinstance(desc, torch.Tensor) and isinstance(desc_mask, torch.Tensor):
        selected = desc.reshape(-1)[desc_mask.reshape(-1).bool()].float()
        if selected.numel() and not torch.isfinite(selected).all():
            reasons.append("invalid_descriptor_non_finite")
    return sorted(set(reasons))


def scan_domain(
    *, data_root: Path, shards: list[str], train_count: int, validation_count: int,
    policy: dict[str, object], max_atoms: int,
):
    train: list[DomainRecord] = []; validation: list[DomainRecord] = []
    quarantine = []; counters = collections.Counter(); train_parents: set[str] = set()
    for shard in shards:
        probe = LmdbMoleculeDataset(str(data_root / shard), start_idx=0, end_idx=0, filter_missing_on_init=False)
        dataset = LmdbMoleculeDataset(
            str(data_root / shard), start_idx=0, end_idx=int(probe._len) - 1, filter_missing_on_init=False,
        )
        domain = domain_from_shard(shard)
        for local_index in range(len(dataset)):
            real_index = int(dataset.idx_list[local_index]); item = dataset[local_index]
            counters["raw_scanned"] += 1
            reasons = quality_reasons(item, domain, policy, max_atoms)
            parent = parent_molecule_identity(item, shard, real_index)
            sample_key = str(getattr(item, "sample_key", "")).strip() or f"{Path(shard).name}:{real_index}"
            if reasons:
                counters["quality_quarantined"] += 1
                for reason in reasons:
                    counters[f"reason:{reason}"] += 1
                quarantine.append({
                    "domain": domain, "shard": shard, "real_index": real_index,
                    "sample_key": sample_key, "parent_molecule_id": parent,
                    "reasons": ";".join(reasons), "recoverable": True,
                })
                continue
            record = DomainRecord(
                shard=shard, real_index=real_index, domain=domain, parent_molecule_id=parent,
                structure_id=sample_key, atom_count=int(item.x.size(0)),
            )
            if len(train) < train_count:
                train.append(record); train_parents.add(parent); counters["train_selected"] += 1
            elif len(validation) < validation_count:
                if parent in train_parents:
                    counters["validation_parent_excluded"] += 1
                    continue
                validation.append(record); counters["validation_selected"] += 1
            if len(train) == train_count and len(validation) == validation_count:
                return train, validation, quarantine, counters
    raise RuntimeError(
        f"Shard inventory exhausted: train={len(train)}/{train_count}, validation={len(validation)}/{validation_count}"
    )


def stratified_prefix(principal, molecule, principal_ratio: float):
    result = []; p_index = m_index = 0
    for next_size in range(1, len(principal) + len(molecule) + 1):
        desired_principal = round(next_size * principal_ratio)
        take_principal = p_index < desired_principal and p_index < len(principal)
        if take_principal or m_index >= len(molecule):
            result.append(principal[p_index]); p_index += 1
        else:
            result.append(molecule[m_index]); m_index += 1
    return result


def attach_quality_metadata(manifest, policy, quarantine_counts):
    manifest.pop("pool_hash")
    manifest["data_quality_protocol_version"] = policy["version"]
    manifest["data_quality_policy_hash"] = canonical_sha256(policy)
    manifest["quality_scan_counts_for_build"] = dict(quarantine_counts)
    manifest["pool_hash"] = canonical_sha256(manifest)
    return manifest


def main() -> None:
    args = parse_args()
    if not 0 < args.principal_ratio < 1:
        raise ValueError("--principal-ratio must be strictly between zero and one")
    sizes = sorted({int(item) for item in args.pool_sizes.split(",")})
    largest = max(sizes); principal_train = round(largest * args.principal_ratio)
    molecule_train = largest - principal_train
    principal_val = round(args.validation_size * args.principal_ratio)
    molecule_val = args.validation_size - principal_val
    policy = json.loads(Path(args.quality_policy).read_text(encoding="utf-8"))
    root = Path(args.data_root).resolve()
    p_train, p_val, p_quarantine, p_counts = scan_domain(
        data_root=root, shards=args.principal_shards, train_count=principal_train,
        validation_count=principal_val * 20, policy=policy, max_atoms=args.filter_max_atoms,
    )
    m_train, m_val, m_quarantine, m_counts = scan_domain(
        data_root=root, shards=args.molecule_shards, train_count=molecule_train,
        validation_count=molecule_val * 20, policy=policy, max_atoms=args.filter_max_atoms,
    )
    combined_train = stratified_prefix(p_train, m_train, args.principal_ratio)
    blocked_parents = {item.parent_molecule_id for item in combined_train}
    p_val = [item for item in p_val if item.parent_molecule_id not in blocked_parents][:principal_val]
    m_val = [item for item in m_val if item.parent_molecule_id not in blocked_parents][:molecule_val]
    if len(p_val) != principal_val or len(m_val) != molecule_val:
        raise RuntimeError("Validation candidate scan did not recover enough globally parent-disjoint records")
    validation_records = stratified_prefix(p_val, m_val, args.principal_ratio)
    output_dir = Path(args.output_dir); output_dir.mkdir(parents=True, exist_ok=True)
    manifests = []; parent_hash = None
    total_counts = collections.Counter(p_counts); total_counts.update(m_counts)
    for size in sizes:
        manifest = matched_manifest(
            pool_id=f"DISCOVERY_POOL_{size // 1000}K_DOMAIN_MATCHED_QUALITY_V3", kind="train",
            data_root=root, records=combined_train[:size], filter_max_atoms=args.filter_max_atoms,
            parent_pool_hash=parent_hash,
        )
        manifest = attach_quality_metadata(manifest, policy, total_counts)
        path = output_dir / f"train_{size}.json"
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        manifests.append({"path": str(path.resolve()), **manifest}); parent_hash = manifest["pool_hash"]
    validation = matched_manifest(
        pool_id="DISCOVERY_VALIDATION_DOMAIN_MATCHED_QUALITY_V3", kind="validation",
        data_root=root, records=validation_records, filter_max_atoms=args.filter_max_atoms,
        include_record_index=True,
    )
    validation = attach_quality_metadata(validation, policy, total_counts)
    validation_path = output_dir / "validation.json"
    validation_path.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    leakage = audit_leakage(combined_train, validation_records)
    if not leakage["domain_matched"]:
        raise RuntimeError(f"Quality-filtered split failed domain/leakage audit: {leakage}")

    quarantine = p_quarantine + m_quarantine
    quarantine_path = Path(args.quarantine_csv); quarantine_path.parent.mkdir(parents=True, exist_ok=True)
    with quarantine_path.open("w", newline="", encoding="utf-8") as handle:
        fields = ["domain", "shard", "real_index", "sample_key", "parent_molecule_id", "reasons", "recoverable"]
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(quarantine)
    report = {
        "data_quality_protocol_version": policy["version"], "data_quality_policy": policy,
        "data_quality_policy_hash": canonical_sha256(policy), "no_source_lmdb_modification": True,
        "quarantine_ledger": str(quarantine_path.resolve()), "quarantine_count": len(quarantine),
        "scan_counts": dict(sorted(total_counts.items())), "train_pools": [{
            key: item[key] for key in ("path", "pool_id", "pool_hash", "unique_structure_count", "unique_molecule_count", "domain_composition")
        } for item in manifests],
        "validation_pool": {
            "path": str(validation_path.resolve()), "pool_id": validation["pool_id"],
            "pool_hash": validation["pool_hash"], "unique_structure_count": validation["unique_structure_count"],
            "unique_molecule_count": validation["unique_molecule_count"], "domain_composition": validation["domain_composition"],
        },
        "leakage_audit": leakage,
    }
    output_json = Path(args.output_json); output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"quarantine_count": len(quarantine), "output_json": str(output_json), "validation_hash": validation["pool_hash"]}, sort_keys=True))


if __name__ == "__main__":
    main()
