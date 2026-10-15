"""Chemical identity for Phase 1, independent of descriptor annotation success."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import csv
import gzip
from pathlib import Path
import re
from typing import Iterable

from rdkit import Chem, rdBase


IDENTITY_POLICY = "standard_full_inchikey_v1"
_KEY = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


class MoleculeIdentityError(ValueError):
    """A record cannot supply a trustworthy standard full InChIKey."""


class SplitOverlapError(ValueError):
    """Existing split identities overlap; no reassignment is attempted."""


@dataclass(frozen=True)
class IdentityResult:
    inchikey: str
    canonical_isomeric_smiles: str
    policy: str = IDENTITY_POLICY
    source_field: str = "smiles"

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def canonical_hash(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def molecule_identity(smiles: str, *, source_field: str = "smiles") -> IdentityResult:
    """Use the complete standard InChIKey, including stereo/protonation layers.

    Identity never contains a source-field prefix. No largest-fragment removal,
    charge neutralization or user-defined tautomer canonicalization is applied.
    Missing/unparseable structures fail explicitly; they are not record IDs.
    """
    if not isinstance(smiles, str) or not smiles.strip():
        raise MoleculeIdentityError("Missing molecular structure string")
    with rdBase.BlockLogs():
        mol = Chem.MolFromSmiles(smiles.strip())
        if mol is None:
            raise MoleculeIdentityError("Molecular structure string cannot be parsed")
        try:
            key = Chem.MolToInchiKey(mol)
            canonical = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
        except Exception as exc:
            raise MoleculeIdentityError(f"InChI generation failed: {type(exc).__name__}") from exc
    if not _KEY.fullmatch(key or ""):
        raise MoleculeIdentityError("Standard full InChIKey generation returned no valid key")
    return IdentityResult(key, canonical, source_field=source_field)


def identity_from_record(record) -> IdentityResult:
    # Prefer the original structure string so a non-isomeric canonical field
    # cannot erase stereochemistry when descriptor reconstruction succeeds.
    for field in ("smiles", "isomeric_smiles", "canonical_smiles"):
        value = getattr(record, field, None)
        if isinstance(value, str) and value.strip():
            return molecule_identity(value, source_field=field)
    raise MoleculeIdentityError("Record has no parseable molecular identity source")


def assert_disjoint_identities(
    train_keys: Iterable[str | IdentityResult],
    other_keys: Iterable[str | IdentityResult],
    *,
    other_label: str = "validation",
) -> dict[str, object]:
    def keys(values):
        result = {value.inchikey if isinstance(value, IdentityResult) else str(value) for value in values}
        if any(not _KEY.fullmatch(value) for value in result):
            raise MoleculeIdentityError("Split audit requires full InChIKeys")
        return result

    train, other = keys(train_keys), keys(other_keys)
    overlap = sorted(train & other)
    if overlap:
        raise SplitOverlapError(
            f"Existing train/{other_label} split overlaps on {len(overlap)} full InChIKeys; "
            "preserve the split and report this defect before any reassignment"
        )
    return {
        "identity_policy": IDENTITY_POLICY,
        "train_unique_molecules": len(train),
        f"{other_label}_unique_molecules": len(other),
        "overlap_count": 0,
        "train_identity_hash": canonical_hash(sorted(train)),
        "other_identity_hash": canonical_hash(sorted(other)),
    }


def frozen_test_identities(specification: dict) -> tuple[set[str], dict]:
    """Read only molecular identities from an explicit frozen downstream list.

    The caller must settle the final test datasets first. This function cannot
    infer a list from whatever CSV files happen to be available. Source file
    hashes are mandatory; target columns are neither inspected nor exported.
    """
    if specification.get("frozen") is not True or not specification.get("test_files"):
        raise ValueError("A nonempty explicitly frozen final downstream test specification is required")
    keys: set[str] = set()
    files = []
    for entry in specification["test_files"]:
        if entry.get("role") != "test" or not entry.get("smiles_column") or not entry.get("sha256"):
            raise ValueError("Every frozen test source must declare test role, SMILES column and SHA-256")
        path = Path(str(entry["path"]))
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != str(entry["sha256"]):
            raise ValueError("Frozen downstream test source hash mismatch")
        opener = gzip.open if path.suffix == ".gz" else open
        before, rows = len(keys), 0
        with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            column = str(entry["smiles_column"])
            if column not in (reader.fieldnames or []):
                raise ValueError("Frozen downstream source lacks the declared SMILES column")
            for row in reader:
                keys.add(molecule_identity(row[column]).inchikey)
                rows += 1
        files.append({
            "path": str(path.resolve()), "sha256": digest.hexdigest(),
            "smiles_column": column, "rows": rows, "additional_unique_keys": len(keys) - before,
        })
    return keys, {
        "identity_policy": IDENTITY_POLICY, "frozen_specification_hash": canonical_hash(specification),
        "test_identity_hash": canonical_hash(sorted(keys)), "unique_test_molecules": len(keys),
        "test_files": files,
    }


def build_identity_decontamination_plan(
    train, validation, *, frozen_downstream_specification: dict, output_directory: str | Path,
    on_unresolved: str = "fail",
) -> dict:
    """Explicit full-pool audit/plan builder; does not modify existing splits.

    This is deliberately separate from the bounded inspection tool. Execute
    only as an appropriately budgeted task after the downstream list is frozen.
    Emits identity/quarantine/exclusion ledgers, never reassigns records. Any
    train/validation overlap is reported and fails, even if the same identity
    would later be removed by downstream decontamination.
    """
    if train.kind != "train" or validation.kind != "validation":
        raise ValueError("Complete declared train and validation views are required")
    if train.diagnostic_only or validation.diagnostic_only:
        raise ValueError("Diagnostic subsets cannot establish full-pool decontamination")
    if on_unresolved not in {"fail", "quarantine"}:
        raise ValueError("Unresolved identities must fail or be explicitly quarantined")
    test_keys, test_evidence = frozen_test_identities(frozen_downstream_specification)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    all_keys: dict[str, set[str]] = {"train": set(), "validation": set()}
    unresolved, excluded = [], {"train": 0, "validation": 0}
    ledger_hashes = {}
    for dataset in (train, validation):
        path = output / f"{dataset.kind}_identity_ledger.jsonl"
        hasher = hashlib.sha256()
        with path.open("wb") as handle:
            for index in range(len(dataset)):
                shard, real_index = dataset.record_ref(index)
                record = {"shard": shard, "real_index": real_index, "pool_hash": dataset.pool_hash}
                try:
                    identity = identity_from_record(dataset.raw_record(index))
                    all_keys[dataset.kind].add(identity.inchikey)
                    record.update({"inchikey": identity.inchikey, "identity_source_field": identity.source_field})
                    record["exclude_for_downstream_test_overlap"] = identity.inchikey in test_keys
                    excluded[dataset.kind] += int(record["exclude_for_downstream_test_overlap"])
                except MoleculeIdentityError as exc:
                    record.update({"quarantine": True, "reason": str(exc)})
                    unresolved.append({"kind": dataset.kind, **record})
                encoded = (json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
                handle.write(encoded)
                hasher.update(encoded)
        ledger_hashes[dataset.kind] = {"path": str(path.resolve()), "sha256": hasher.hexdigest()}
    overlap = all_keys["train"] & all_keys["validation"]
    result = {
        "identity_policy": IDENTITY_POLICY,
        "train_pool_hash": train.pool_hash, "validation_pool_hash": validation.pool_hash,
        "scope": "complete_declared_manifests", "test_sources": test_evidence,
        "identity_ledgers": ledger_hashes, "quarantined_identity_records": unresolved,
        "downstream_overlap_structure_counts": excluded,
        "train_validation_overlap_count": len(overlap),
        "train_validation_overlap_keys": sorted(overlap),
        "source_lmdb_unchanged": True, "split_unchanged": True,
        "status": "REQUIRES_SPLIT_CORRECTION" if overlap else (
            "UNRESOLVED_IDENTITIES" if unresolved and on_unresolved == "fail" else "AUDITED_EXCLUSION_PLAN"
        ),
        "implementation_note": "Ledgers propose only exclusions; applying a revised split requires an explicit recorded decision.",
    }
    result["plan_hash"] = canonical_hash(result)
    (output / "decontamination_plan.json").write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    if overlap:
        raise SplitOverlapError(f"Existing full-pool split has {len(overlap)} overlapping full InChIKeys; see the preserved audit plan")
    if unresolved and on_unresolved == "fail":
        raise MoleculeIdentityError(f"Full-pool audit has {len(unresolved)} unresolved identity records; see the quarantine ledger")
    return result
