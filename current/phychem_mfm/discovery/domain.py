from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

from ..data.dataset_lmdb import LmdbMoleculeDataset
from .identity import canonical_sha256
from .manifests import Segment, make_pool_manifest


DOMAIN_PROTOCOL_VERSION = "domain-matched-v3.1"


def domain_from_shard(shard: str) -> str:
    name = Path(shard).name.lower()
    if name.startswith("principal_"):
        return "principal"
    if name.startswith(("unimol_", "molecule_")):
        return "molecule"
    raise ValueError(f"Cannot infer molecule/principal domain from shard: {shard}")


def parent_molecule_identity(item, shard: str, real_index: int) -> str:
    for field in ("canonical_smiles", "isomeric_smiles", "smiles", "registration_hash"):
        value = getattr(item, field, None)
        if isinstance(value, str) and value.strip():
            return f"{field}:{value.strip()}"
    sample_key = str(getattr(item, "sample_key", "")).strip()
    # A final fallback can identify structures but cannot prove parent-level
    # disjointness. Prefix it explicitly so the audit reports this limitation.
    return f"UNRESOLVED_PARENT:{Path(shard).name}:{sample_key or real_index}"


@dataclass(frozen=True)
class DomainRecord:
    shard: str
    real_index: int
    domain: str
    parent_molecule_id: str
    structure_id: str
    atom_count: int

    def to_dict(self) -> dict[str, object]:
        return dict(self.__dict__)


def scan_domain_records(
    data_root: str | Path,
    shard_names: Iterable[str],
    *,
    max_atoms: int,
    maximum_records: int | None = None,
) -> list[DomainRecord]:
    root = Path(data_root)
    records: list[DomainRecord] = []
    for shard in shard_names:
        probe = LmdbMoleculeDataset(str(root / shard), start_idx=0, end_idx=0, filter_missing_on_init=False)
        dataset = LmdbMoleculeDataset(
            str(root / shard), start_idx=0, end_idx=int(probe._len) - 1, filter_missing_on_init=False
        )
        domain = domain_from_shard(shard)
        for local_index in range(len(dataset)):
            real_index = int(dataset.idx_list[local_index])
            item = dataset[local_index]
            atom_count = int(item.x.size(0))
            if atom_count > max_atoms:
                continue
            sample_key = str(getattr(item, "sample_key", "")).strip() or f"{Path(shard).name}:{real_index}"
            records.append(DomainRecord(
                shard=str(shard), real_index=real_index, domain=domain,
                parent_molecule_id=parent_molecule_identity(item, shard, real_index),
                structure_id=sample_key, atom_count=atom_count,
            ))
            if maximum_records is not None and len(records) >= maximum_records:
                return records
    return records


def records_to_segments(records: Iterable[DomainRecord]) -> list[Segment]:
    # Selection order is scientifically meaningful for producing stratified
    # prefixes, but storage order is not. Group/sort here so alternating
    # domains do not create one JSON segment per structure.
    ordered = sorted(records, key=lambda item: (item.shard, item.real_index))
    segments: list[Segment] = []
    for record in ordered:
        if segments and segments[-1].shard == record.shard and segments[-1].end + 1 == record.real_index:
            previous = segments[-1]
            segments[-1] = Segment(previous.shard, previous.start, previous.count + 1)
        else:
            segments.append(Segment(record.shard, record.real_index, 1))
    return segments


def domain_composition(records: Iterable[DomainRecord]) -> dict[str, object]:
    materialized = list(records)
    counts: dict[str, int] = {}
    parent_counts: dict[str, set[str]] = {}
    unresolved = 0
    for record in materialized:
        counts[record.domain] = counts.get(record.domain, 0) + 1
        parent_counts.setdefault(record.domain, set()).add(record.parent_molecule_id)
        unresolved += int(record.parent_molecule_id.startswith("UNRESOLVED_PARENT:"))
    total = max(1, len(materialized))
    return {
        "structure_counts": counts,
        "structure_ratios": {key: value / total for key, value in counts.items()},
        "unique_parent_molecule_counts": {key: len(value) for key, value in parent_counts.items()},
        "unresolved_parent_structure_count": unresolved,
    }


def matched_manifest(
    *, pool_id: str, kind: str, data_root: str | Path, records: list[DomainRecord],
    filter_max_atoms: int, parent_pool_hash: str | None = None, include_record_index: bool = False,
) -> dict[str, object]:
    manifest = make_pool_manifest(
        pool_id=pool_id, kind=kind, data_root=data_root, segments=records_to_segments(records),
        unique_molecule_count=len({item.parent_molecule_id for item in records}),
        parent_pool_hash=parent_pool_hash, filter_max_atoms=filter_max_atoms,
        molecule_identity_field="canonical_smiles|isomeric_smiles|smiles|registration_hash",
        selection_rule="domain_stratified_parent_disjoint_v3",
    )
    manifest.pop("pool_hash")
    manifest["domain_protocol_version"] = DOMAIN_PROTOCOL_VERSION
    manifest["domain_composition"] = domain_composition(records)
    manifest["parent_molecule_hash"] = canonical_sha256({
        "parents": sorted({item.parent_molecule_id for item in records})
    })
    if include_record_index:
        manifest["records"] = [item.to_dict() for item in records]
    manifest["pool_hash"] = canonical_sha256(manifest)
    return manifest


def audit_leakage(train_records: Iterable[DomainRecord], validation_records: Iterable[DomainRecord]) -> dict[str, object]:
    train = list(train_records)
    val = list(validation_records)
    train_parents = {item.parent_molecule_id for item in train}
    val_parents = {item.parent_molecule_id for item in val}
    overlap = train_parents & val_parents
    return {
        "train_domain_composition": domain_composition(train),
        "validation_domain_composition": domain_composition(val),
        "parent_molecule_overlap_count": len(overlap),
        "parent_molecule_overlap_examples": sorted(overlap)[:20],
        "domain_ratio_absolute_difference": {
            domain: abs(
                float(domain_composition(train)["structure_ratios"].get(domain, 0.0))
                - float(domain_composition(val)["structure_ratios"].get(domain, 0.0))
            )
            for domain in {item.domain for item in train + val}
        },
        "domain_matched": not overlap and domain_composition(train)["structure_ratios"] == domain_composition(val)["structure_ratios"],
    }
