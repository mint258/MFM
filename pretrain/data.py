from __future__ import annotations

import logging
import math
import os
from typing import Iterable, List

import numpy as np
import torch
from torch.utils.data import Subset
from torch_geometric.data import Batch
from tqdm import tqdm

from dataset_lmdb import LmdbMoleculeDataset
from dataset_without_charge import MoleculeDataset
from degrade_molecules import DegradeConfig, degrade_once
from utils_debug import is_debug as get_debug_flag

LOGGER = logging.getLogger("multitask")


def create_dataset(path: str, start_idx: int | None, end_idx: int | None):
    """Create and wrap a dataset with resilient sample fetching."""
    start_idx = start_idx if start_idx is not None else 0
    end_idx = end_idx if end_idx not in (None, -1) else None

    if path.endswith(".lmdb") or (os.path.isfile(path) and path.lower().endswith(".lmdb")):
        dataset = LmdbMoleculeDataset(path, start_idx=start_idx, end_idx=end_idx, filter_missing_on_init=True)
    else:
        dataset = MoleculeDataset(path, start_idx=start_idx, end_idx=end_idx)

    wrapped = SafeResampleDataset(dataset, max_retries=32, name=os.path.basename(path))
    wrapped.source_path = path
    return wrapped


class SafeResampleDataset(torch.utils.data.Dataset):
    """Resample on invalid examples without changing dataset length."""

    def __init__(self, base, max_retries: int = 32, name: str = ""):
        self.base = base
        self.max_retries = int(max_retries)
        self.name = name or type(base).__name__
        self._rng = np.random.default_rng()

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        tries = 0
        cur_idx = idx
        while tries < self.max_retries:
            try:
                data = self.base[cur_idx]
                if hasattr(data, "pos"):
                    pos = data.pos
                    if pos.numel() == 0 or (not torch.isfinite(pos).all()):
                        raise ValueError("invalid pos")
                if hasattr(data, "x") and data.x.numel() == 0:
                    raise ValueError("empty x")
                return data
            except Exception:
                tries += 1
                cur_idx = int(self._rng.integers(0, len(self.base)))

        raise IndexError(f"[SafeResampleDataset:{self.name}] too many invalid samples (idx={idx})")


class OnlyStableWrapper(torch.utils.data.Dataset):
    """Drop trajectory fields and keep stable-structure data only."""

    def __init__(self, base):
        self.base = base

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        data = self.base[idx]
        if hasattr(data, "trajectory"):
            delattr(data, "trajectory")
        return data


class EnergyFilteredDataset(Subset):
    """Keep only samples with non-positive energy (optional helper)."""

    def __init__(self, base):
        kept = [i for i in range(len(base)) if base[i].energy <= 0]
        super().__init__(base, kept)
        if get_debug_flag():
            LOGGER.debug("Filtered energy <= 0: kept %d / %d", len(kept), len(base))


class DomainWrapperDataset(torch.utils.data.Dataset):
    """Attach `domain_id` to each data sample for downstream routing."""

    def __init__(self, base, domain_id: int):
        self.base = base
        self.domain_id = int(domain_id)

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        data = self.base[idx]
        data.domain_id = torch.tensor([self.domain_id], dtype=torch.long)
        return data


class MaskedPerturbDataset(torch.utils.data.Dataset):
    """Apply degradation while keeping clean targets for denoising supervision."""

    def __init__(self, base, cfg: DegradeConfig, seed: int = 114):
        self.base = base
        self.cfg = cfg.finalize()
        self.seed = int(seed)

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        d0 = self.base[idx]

        clean_x = d0.x.clone() if hasattr(d0, "x") else None
        clean_pos = d0.pos.clone() if hasattr(d0, "pos") else None

        gen = torch.Generator(device=d0.x.device if d0.x.is_cuda else "cpu").manual_seed(self.seed + idx)
        data = degrade_once(d0, self.cfg, gen)

        if clean_x is not None:
            data.target_x = clean_x
        if clean_pos is not None:
            data.target_pos = clean_pos

        for attr in ("is_feasible", "neg_type"):
            if hasattr(data, attr):
                delattr(data, attr)

        return data


def standardizer(ds_list: Iterable, ratio: float = 0.01, cap: int = 50000, seed: int = 0):
    """Estimate mean/std for energy and charge from sampled data."""
    rng = np.random.default_rng(seed)

    sample_pool: List[tuple] = []
    for dataset in ds_list:
        n = len(dataset)
        if n <= 0:
            LOGGER.warning(
                "standardizer: skip empty dataset (%s)",
                getattr(dataset, "source_path", type(dataset).__name__),
            )
            continue

        if ratio <= 0:
            k = 0
        else:
            k = max(1, int(n * ratio))
        k = min(k, n)
        if k <= 0:
            continue

        idx = rng.choice(n, k, replace=False)
        sample_pool.extend((dataset, int(i)) for i in idx)

    if not sample_pool:
        raise ValueError("standardizer got zero samples; datasets may be empty or ratio/cap too small")

    rng.shuffle(sample_pool)
    sample_pool = sample_pool[:cap]

    s_e = s_q = s2_e = s2_q = c_e = c_q = 0.0
    for dataset, i in tqdm(sample_pool, desc="Std"):
        data = dataset[i]
        s_e += data.energy
        s2_e += data.energy**2
        c_e += 1

        if hasattr(data, "y"):
            q = data.y.view(-1)
            mask = torch.ones_like(q)
            if hasattr(data, "charge_mask"):
                mask = data.charge_mask.view(-1)
            q = q[mask > 0]
            s_q += q.sum().item()
            s2_q += (q**2).sum().item()
            c_q += len(q)

    if c_e <= 0:
        raise ValueError("standardizer: no valid samples for energy stats")

    mu_e = s_e / c_e
    std_e = math.sqrt(max(s2_e / c_e - mu_e**2, 1e-12))

    if c_q > 0:
        mu_q = s_q / c_q
        std_q = math.sqrt(max(s2_q / c_q - mu_q**2, 1e-12))
    else:
        mu_q = 0.0
        std_q = 1.0
        LOGGER.warning("standardizer: no charge targets found; fallback muQ=0 stdQ=1")

    LOGGER.info("Energy mu=%.3f std=%.3f | Charge mu=%+.2e std=%.2e", mu_e, std_e, mu_q, std_q)
    return {"muE": mu_e, "stdE": std_e, "muQ": mu_q, "stdQ": std_q}


def fast_collate(data_list):
    """Drop large precomputed angle/torsion tensors before batch merge."""
    for data in data_list:
        if hasattr(data, "angle_triplet"):
            delattr(data, "angle_triplet")
        if hasattr(data, "dihed_quad"):
            delattr(data, "dihed_quad")
    return Batch.from_data_list(data_list)
