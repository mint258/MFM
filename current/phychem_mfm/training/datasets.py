from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import torch
from torch.utils.data import ConcatDataset, DataLoader, Subset

from .data import (
    DistributedAtomBudgetBatchSampler,
    DistributedEvalAtomBudgetBatchSampler,
    DomainWrapperDataset,
    MaskedPerturbDataset,
    SampleTypeWrapperDataset,
    create_dataset,
    dataset_atom_counts,
    fast_collate,
    resolve_atom_counts,
    seed_worker,
    standardizer,
)
from .degrade_molecules import DegradeConfig


@dataclass
class PilotDataBundle:
    train_dataset: torch.utils.data.Dataset
    val_dataset: torch.utils.data.Dataset
    train_loader: DataLoader
    val_loader: DataLoader
    diagnostic_val_loader: DataLoader
    standardizers: dict[str, object]
    manifest: dict[str, object]


def _take(dataset, count: int):
    return Subset(dataset, list(range(min(len(dataset), max(0, int(count))))))


def _recipe_dataset(base, mode: str, level: float, ratio: float, seed: int):
    if mode == "clean":
        wrapped = SampleTypeWrapperDataset(base, sample_type="clean")
    else:
        config = DegradeConfig(
            mode=mode,
            level=level,
            topo_replace_frac=None,
            topo_delete_frac=0.0,
            geom_noise_std=None,
            geom_angle_std_deg=0.0,
            geom_bond_scale_std=0.0,
        )
        wrapped = MaskedPerturbDataset(base, config, seed=seed)
    return _take(wrapped, max(1, round(len(base) * ratio)))


def build_pilot_data(
    data_root: str | Path,
    *,
    train_limit: int,
    val_limit: int,
    batch_size: int,
    num_workers: int,
    seed: int,
    shard_name: str = "principal_00000001_00300000.lmdb",
    include_historical_perturb_mix: bool = True,
    standardizer_cap: int = 4096,
    atom_budget_per_batch: int | None = None,
) -> PilotDataBundle:
    root = Path(data_root).resolve()
    shard = root / shard_name
    if not shard.exists():
        raise FileNotFoundError(shard)
    if train_limit <= 0 or val_limit <= 0:
        raise ValueError("train_limit and val_limit must both be positive")

    val_base = create_dataset(str(shard), 0, val_limit - 1, seed=seed + 1)
    train_base = create_dataset(str(shard), val_limit, val_limit + train_limit - 1, seed=seed + 2)
    if len(train_base) == 0 or len(val_base) == 0:
        raise RuntimeError("Pilot split produced an empty dataset")
    if atom_budget_per_batch is not None:
        cache_dir = Path.home() / ".cache" / "phychem_mfm" / "atom_counts"
        train_base.atom_counts = resolve_atom_counts(train_base, cache_dir=str(cache_dir))
        val_base.atom_counts = resolve_atom_counts(val_base, cache_dir=str(cache_dir))

    if include_historical_perturb_mix:
        recipes = (
            ("clean", 0.0, 1.0),
            ("geom", 0.2, 0.2),
            ("geom", 0.3, 0.1),
            ("topo", 0.3, 0.2),
            ("both", 0.1, 0.1),
        )
        parts = [
            DomainWrapperDataset(_recipe_dataset(train_base, mode, level, ratio, seed + 1000 * idx), 0)
            for idx, (mode, level, ratio) in enumerate(recipes)
        ]
        train_dataset = ConcatDataset(parts)
    else:
        recipes = (("clean", 0.0, 1.0),)
        train_dataset = DomainWrapperDataset(SampleTypeWrapperDataset(train_base, sample_type="clean"), 0)
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
    if atom_budget_per_batch is not None:
        atom_budget_per_batch = int(atom_budget_per_batch)
        train_batch_sampler = DistributedAtomBudgetBatchSampler(
            dataset_atom_counts(train_dataset),
            max_atoms_per_batch=atom_budget_per_batch,
            max_samples_per_batch=batch_size,
            shuffle=True,
            seed=seed,
        )
        val_batch_sampler = DistributedEvalAtomBudgetBatchSampler(
            dataset_atom_counts(val_dataset),
            max_atoms_per_batch=atom_budget_per_batch,
            max_samples_per_batch=batch_size,
        )
        diagnostic_batch_sampler = DistributedEvalAtomBudgetBatchSampler(
            dataset_atom_counts(diagnostic_val_dataset),
            max_atoms_per_batch=atom_budget_per_batch,
            max_samples_per_batch=batch_size,
        )
        train_loader = DataLoader(train_dataset, batch_sampler=train_batch_sampler, **loader_kwargs)
        val_loader = DataLoader(val_dataset, batch_sampler=val_batch_sampler, **loader_kwargs)
        diagnostic_val_loader = DataLoader(
            diagnostic_val_dataset,
            batch_sampler=diagnostic_batch_sampler,
            **loader_kwargs,
        )
    else:
        generator = torch.Generator().manual_seed(seed)
        train_loader = DataLoader(
            train_dataset,
            batch_size=batch_size,
            shuffle=True,
            generator=generator,
            **loader_kwargs,
        )
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, **loader_kwargs)
        diagnostic_val_loader = DataLoader(
            diagnostic_val_dataset,
            batch_size=batch_size,
            shuffle=False,
            **loader_kwargs,
        )

    stats = standardizer([train_base], ratio=1.0, cap=min(int(standardizer_cap), len(train_base)), seed=seed)
    stat_summary = {}
    for key, value in stats.items():
        if isinstance(value, torch.Tensor):
            stat_summary[key] = {"shape": list(value.shape), "sha256": hashlib.sha256(value.numpy().tobytes()).hexdigest()}
        else:
            stat_summary[key] = float(value)
    manifest = {
        "data_root": str(root),
        "shard": str(shard),
        "shard_size": shard.stat().st_size,
        "shard_mtime_ns": shard.stat().st_mtime_ns,
        "train_range_inclusive": [val_limit, val_limit + train_limit - 1],
        "validation_range_inclusive": [0, val_limit - 1],
        "train_base_count": len(train_base),
        "validation_count": len(val_base),
        "diagnostic_validation_recipe": "topo:0.3@1",
        "effective_train_count": len(train_dataset),
        "recipes": [list(item) for item in recipes],
        "seed": seed,
        "batching": {
            "max_samples_per_batch": int(batch_size),
            "atom_budget_per_batch": atom_budget_per_batch,
        },
        "standardizers": stat_summary,
    }
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    manifest["manifest_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return PilotDataBundle(
        train_dataset,
        val_dataset,
        train_loader,
        val_loader,
        diagnostic_val_loader,
        stats,
        manifest,
    )
