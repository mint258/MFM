from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import torch
from torch.utils.data import ConcatDataset, DataLoader, Subset

from ..training.data import (
    DistributedAtomBudgetBatchSampler,
    DistributedEvalAtomBudgetBatchSampler,
    DomainWrapperDataset,
    IndexedSubsetDataset,
    MaskedPerturbDataset,
    SampleTypeWrapperDataset,
    create_dataset,
    dataset_atom_counts,
    fast_collate,
    resolve_atom_counts,
    seed_worker,
    standardizer,
)
from ..training.datasets import PilotDataBundle
from ..training.degrade_molecules import DegradeConfig
from .identity import canonical_sha256


MANIFEST_VERSION = 1


@dataclass(frozen=True)
class Segment:
    shard: str
    start: int
    count: int

    @property
    def end(self) -> int:
        return self.start + self.count - 1

    def to_dict(self, root: Path) -> dict[str, object]:
        path = (root / self.shard).resolve()
        stat = path.stat()
        return {
            "shard": self.shard,
            "start": self.start,
            "end": self.end,
            "count": self.count,
            "source_size": stat.st_size,
            "source_mtime_ns": stat.st_mtime_ns,
        }


def allocate_segments(shards: Sequence[tuple[str, int]], *, count: int, skip: int = 0) -> list[Segment]:
    remaining = int(count)
    skip_remaining = int(skip)
    result: list[Segment] = []
    for shard, length in shards:
        length = int(length)
        if skip_remaining >= length:
            skip_remaining -= length
            continue
        start = skip_remaining
        available = length - start
        take = min(remaining, available)
        if take > 0:
            result.append(Segment(str(shard), start, take))
            remaining -= take
        skip_remaining = 0
        if remaining == 0:
            break
    if remaining:
        raise ValueError(f"Requested {count} structures but shard inventory is short by {remaining}")
    return result


def make_pool_manifest(
    *,
    pool_id: str,
    kind: str,
    data_root: str | Path,
    segments: Iterable[Segment],
    unique_molecule_count: int | None = None,
    parent_pool_hash: str | None = None,
    molecule_identity_field: str = "canonical_smiles|isomeric_smiles|smiles|sample_key",
    filter_max_atoms: int | None = None,
    selection_rule: str = "ordered_contiguous_prefix_over_declared_shards",
    raw_scanned_count: int | None = None,
    filtered_out_structure_count: int = 0,
    excluded_molecule_overlap_count: int = 0,
) -> dict[str, object]:
    root = Path(data_root).resolve()
    segment_records = [segment.to_dict(root) for segment in segments]
    payload: dict[str, object] = {
        "format_version": MANIFEST_VERSION,
        "pool_id": str(pool_id),
        "kind": str(kind),
        "data_root": str(root),
        "segments": segment_records,
        "unique_structure_count": sum(int(item["count"]) for item in segment_records),
        "unique_molecule_count": None if unique_molecule_count is None else int(unique_molecule_count),
        "molecule_identity_field": molecule_identity_field,
        "parent_pool_hash": parent_pool_hash,
        "filter_max_atoms": None if filter_max_atoms is None else int(filter_max_atoms),
        "selection_rule": str(selection_rule),
        "raw_scanned_count": None if raw_scanned_count is None else int(raw_scanned_count),
        "filtered_out_structure_count": int(filtered_out_structure_count),
        "excluded_molecule_overlap_count": int(excluded_molecule_overlap_count),
    }
    payload["pool_hash"] = canonical_sha256(payload)
    return payload


def validate_nested_manifests(manifests: Sequence[Mapping[str, object]]) -> None:
    previous: set[tuple[str, int]] = set()
    for manifest in manifests:
        current: set[tuple[str, int]] = set()
        for segment in manifest["segments"]:
            current.update((str(segment["shard"]), index) for index in range(int(segment["start"]), int(segment["end"]) + 1))
        if len(current) != int(manifest["unique_structure_count"]):
            raise RuntimeError(f"Manifest count mismatch: {manifest['pool_id']}")
        if not previous.issubset(current):
            raise RuntimeError(f"Pool is not a nested superset: {manifest['pool_id']}")
        previous = current


def _dataset_from_manifest(manifest: Mapping[str, object], seed: int, cache_dir: Path):
    root = Path(str(manifest["data_root"]))
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for segment in manifest["segments"]:
        grouped.setdefault(str(segment["shard"]), []).append(segment)
    datasets = []
    stable_sample_keys: list[str] = []
    for index, (shard, segments) in enumerate(grouped.items()):
        start = min(int(segment["start"]) for segment in segments)
        end = max(int(segment["end"]) for segment in segments)
        base = create_dataset(
            str(root / shard),
            start,
            end,
            seed=seed + index,
            filter_missing_on_init=False,
        )
        base.atom_counts = resolve_atom_counts(base, cache_dir=str(cache_dir))
        selected = [
            real_index - start
            for segment in segments
            for real_index in range(int(segment["start"]), int(segment["end"]) + 1)
        ]
        if len(selected) == len(base) and selected == list(range(len(base))):
            datasets.append(base)
        else:
            datasets.append(IndexedSubsetDataset(base, selected))
        stable_sample_keys.extend(f"{shard}:{real_index}" for real_index in (
            real_index
            for segment in segments
            for real_index in range(int(segment["start"]), int(segment["end"]) + 1)
        ))
    result = datasets[0] if len(datasets) == 1 else ConcatDataset(datasets)
    if len(stable_sample_keys) != len(result):
        raise RuntimeError("Stable sample identity count does not match manifest dataset length")
    result.stable_sample_keys = stable_sample_keys
    return result


def _recipe_index_for_key(sample_key: str, seed: int, cumulative_ratios: Sequence[float]) -> int:
    digest = hashlib.sha256(f"{int(seed)}|{sample_key}".encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") / float(2**64)
    for index, boundary in enumerate(cumulative_ratios):
        if value < boundary:
            return index
    return len(cumulative_ratios) - 1


def _partitioned_perturbation_dataset(base, seed: int):
    """Exactly one deterministic view per unique structure in every pass."""

    size = len(base)
    specs = (
        ("clean", 0.0, 0.625),
        ("geom", 0.2, 0.125),
        ("geom", 0.3, 0.0625),
        ("topo", 0.3, 0.125),
        ("both", 0.1, 0.0625),
    )
    stable_keys = getattr(base, "stable_sample_keys", None)
    if not isinstance(stable_keys, list) or len(stable_keys) != size:
        stable_keys = [f"logical-index:{index}" for index in range(size)]
    cumulative = []
    running = 0.0
    for _, _, ratio in specs:
        running += ratio
        cumulative.append(running)
    assignments = [[] for _ in specs]
    for logical_index, sample_key in enumerate(stable_keys):
        assignments[_recipe_index_for_key(sample_key, seed + 7001, cumulative)].append(logical_index)
    parts = []
    for idx, (mode, level, ratio) in enumerate(specs):
        subset = Subset(base, assignments[idx])
        if mode == "clean":
            wrapped = SampleTypeWrapperDataset(subset, sample_type="clean")
        else:
            wrapped = MaskedPerturbDataset(
                subset,
                DegradeConfig(
                    mode=mode,
                    level=level,
                    topo_replace_frac=None,
                    topo_delete_frac=0.0,
                    geom_noise_std=None,
                    geom_angle_std_deg=0.0,
                    geom_bond_scale_std=0.0,
                ),
                seed=seed + 1000 * (idx + 1),
            )
        wrapped.atom_counts = dataset_atom_counts(subset)
        parts.append(DomainWrapperDataset(wrapped, 0))
    return ConcatDataset(parts), [list(spec) for spec in specs]


def build_discovery_data(
    train_manifest: Mapping[str, object],
    validation_manifest: Mapping[str, object],
    *,
    batch_size: int,
    atom_budget_per_batch: int,
    num_workers: int,
    seed: int,
    standardizer_cap: int = 100000,
    standardizer_reference_manifest: Mapping[str, object] | None = None,
) -> PilotDataBundle:
    cache_dir = Path.home() / ".cache" / "phychem_mfm" / "atom_counts"
    train_base = _dataset_from_manifest(train_manifest, seed + 10, cache_dir)
    val_base = _dataset_from_manifest(validation_manifest, seed + 20, cache_dir)
    train_leaves = list(train_base.datasets) if isinstance(train_base, ConcatDataset) else [train_base]
    val_leaves = list(val_base.datasets) if isinstance(val_base, ConcatDataset) else [val_base]

    train_dataset, perturbation_specs = _partitioned_perturbation_dataset(train_base, seed)
    val_dataset = DomainWrapperDataset(SampleTypeWrapperDataset(val_base, sample_type="clean"), 0)
    diagnostic_val_dataset = DomainWrapperDataset(
        MaskedPerturbDataset(
            val_base,
            DegradeConfig(
                mode="topo",
                level=0.3,
                topo_replace_frac=None,
                topo_delete_frac=0.0,
                geom_noise_std=None,
                geom_angle_std_deg=0.0,
                geom_bond_scale_std=0.0,
            ),
            seed=seed + 90000,
        ),
        0,
    )
    loader_kwargs = {
        "num_workers": int(num_workers),
        "pin_memory": True,
        "collate_fn": fast_collate,
        "worker_init_fn": seed_worker,
        "persistent_workers": bool(num_workers > 0),
    }
    train_loader = DataLoader(
        train_dataset,
        batch_sampler=DistributedAtomBudgetBatchSampler(
            dataset_atom_counts(train_dataset),
            max_atoms_per_batch=int(atom_budget_per_batch),
            max_samples_per_batch=int(batch_size),
            shuffle=True,
            seed=int(seed),
        ),
        **loader_kwargs,
    )
    val_loader = DataLoader(
        val_dataset,
        batch_sampler=DistributedEvalAtomBudgetBatchSampler(
            dataset_atom_counts(val_dataset),
            max_atoms_per_batch=int(atom_budget_per_batch),
            max_samples_per_batch=int(batch_size),
        ),
        **loader_kwargs,
    )
    diagnostic_loader = DataLoader(
        diagnostic_val_dataset,
        batch_sampler=DistributedEvalAtomBudgetBatchSampler(
            dataset_atom_counts(diagnostic_val_dataset),
            max_atoms_per_batch=int(atom_budget_per_batch),
            max_samples_per_batch=int(batch_size),
        ),
        **loader_kwargs,
    )
    standardizer_manifest = standardizer_reference_manifest or train_manifest
    if str(standardizer_manifest["pool_hash"]) == str(train_manifest["pool_hash"]):
        standardizer_base = train_base
        standardizer_leaves = train_leaves
    else:
        standardizer_base = _dataset_from_manifest(standardizer_manifest, seed + 30, cache_dir)
        standardizer_leaves = list(standardizer_base.datasets) if isinstance(standardizer_base, ConcatDataset) else [standardizer_base]
    standardizer_dir = Path.home() / ".cache" / "phychem_mfm" / "standardizers"
    standardizer_path = standardizer_dir / f"{standardizer_manifest['pool_hash']}.pt"
    if standardizer_path.exists():
        stats = torch.load(standardizer_path, map_location="cpu", weights_only=False)
    else:
        stats = standardizer(
            standardizer_leaves, ratio=1.0,
            cap=min(int(standardizer_cap), len(standardizer_base)), seed=seed,
        )
        standardizer_dir.mkdir(parents=True, exist_ok=True)
        temporary = standardizer_path.with_name(f"{standardizer_path.name}.tmp.{os.getpid()}")
        try:
            torch.save(stats, temporary)
            os.replace(temporary, standardizer_path)
        finally:
            if temporary.exists():
                temporary.unlink()
    bundle_manifest = {
        "train_pool": dict(train_manifest),
        "validation_pool": dict(validation_manifest),
        "train_pool_hash": str(train_manifest["pool_hash"]),
        "validation_pool_hash": str(validation_manifest["pool_hash"]),
        "unique_structure_count": int(train_manifest["unique_structure_count"]),
        "unique_molecule_count": train_manifest.get("unique_molecule_count"),
        "effective_structures_per_pass": len(train_dataset),
        "perturbation_assignment": "sha256_stable_sample_identity_v3",
        "perturbation_specs": perturbation_specs,
        "seed": int(seed),
        "batching": {
            "max_samples_per_batch": int(batch_size),
            "atom_budget_per_batch": int(atom_budget_per_batch),
        },
        "standardizer_cache": str(standardizer_path),
        "standardizer_reference_pool_id": standardizer_manifest["pool_id"],
        "standardizer_reference_pool_hash": standardizer_manifest["pool_hash"],
        "standardizer_reference_pool": dict(standardizer_manifest),
    }
    bundle_manifest["manifest_sha256"] = canonical_sha256(bundle_manifest)
    return PilotDataBundle(
        train_dataset,
        val_dataset,
        train_loader,
        val_loader,
        diagnostic_loader,
        stats,
        bundle_manifest,
    )


def load_manifest(path: str | Path) -> dict[str, object]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = str(payload.pop("pool_hash"))
    actual = canonical_sha256(payload)
    payload["pool_hash"] = expected
    if actual != expected:
        raise RuntimeError(f"Manifest hash mismatch for {path}: expected {expected}, computed {actual}")
    return payload
