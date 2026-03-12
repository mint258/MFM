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

from dataset import LmdbMoleculeDataset, MoleculeDataset
from dataset.descriptor_schema import GRAPH_FIELD, GRAPH_MASK_FIELD, NODE_MASK_FIELD, RDKIT_GRAPH_DESC_DIM

from .degrade_molecules import DegradeConfig, degrade_once
from .utils_debug import is_debug as get_debug_flag

LOGGER = logging.getLogger("multitask")
COLLATE_RENAME_FIELDS = {
    "rdkit_node_estate_index": "_rdkit_node_estate_index_value",
}
DESCRIPTOR_STD_FLOOR = 1.0


def _finalize_scalar_stats(sum_value: float, sum_sq_value: float, count_value: float) -> tuple[float, float]:
    if count_value <= 0:
        return 0.0, 1.0
    mean = sum_value / count_value
    std = math.sqrt(max(sum_sq_value / count_value - mean**2, 1e-12))
    return mean, std


def _finalize_vector_stats(sum_value: torch.Tensor, sum_sq_value: torch.Tensor, count_value: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    safe_count = count_value.clamp(min=1.0)
    mean = sum_value / safe_count
    std = torch.sqrt(torch.clamp(sum_sq_value / safe_count - mean.square(), min=1e-12))
    mean = torch.where(count_value > 0, mean, torch.zeros_like(mean))
    std = torch.where(count_value > 0, std, torch.ones_like(std))
    return mean.float(), std.float()


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
    """Estimate mean/std for regression targets used during pretraining."""
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
    graph_sum = torch.zeros(RDKIT_GRAPH_DESC_DIM, dtype=torch.float64)
    graph_sq = torch.zeros(RDKIT_GRAPH_DESC_DIM, dtype=torch.float64)
    graph_count = torch.zeros(RDKIT_GRAPH_DESC_DIM, dtype=torch.float64)
    scalar_regression_fields = {
        "formal_charge": {
            "field_name": "rdkit_node_formal_charge",
            "sum": 0.0,
            "sum_sq": 0.0,
            "count": 0.0,
        },
        "estate_index": {
            "field_name": "rdkit_node_estate_index",
            "sum": 0.0,
            "sum_sq": 0.0,
            "count": 0.0,
        },
    }

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

        graph_desc = getattr(data, GRAPH_FIELD, None)
        graph_mask = getattr(data, GRAPH_MASK_FIELD, None)
        if isinstance(graph_desc, torch.Tensor):
            values = graph_desc.view(-1).double()
            if isinstance(graph_mask, torch.Tensor):
                valid = graph_mask.view(-1).bool()
            else:
                valid = torch.ones_like(values, dtype=torch.bool)
            if valid.any():
                graph_sum[valid] += values[valid]
                graph_sq[valid] += values[valid].square()
                graph_count[valid] += 1.0

        node_mask = getattr(data, NODE_MASK_FIELD, None)
        if isinstance(node_mask, torch.Tensor):
            valid_nodes = node_mask.view(-1).bool()
            if valid_nodes.any():
                for stats_key, field_stats in scalar_regression_fields.items():
                    value = getattr(data, field_stats["field_name"], None)
                    if not isinstance(value, torch.Tensor):
                        continue
                    values = value.view(-1).double()
                    values = values[valid_nodes]
                    if values.numel() == 0:
                        continue
                    field_stats["sum"] += values.sum().item()
                    field_stats["sum_sq"] += values.square().sum().item()
                    field_stats["count"] += float(values.numel())

    if c_e <= 0:
        raise ValueError("standardizer: no valid samples for energy stats")

    mu_e = s_e / c_e
    std_e = math.sqrt(max(s2_e / c_e - mu_e**2, 1e-12))

    if c_q > 0:
        mu_q, std_q = _finalize_scalar_stats(s_q, s2_q, c_q)
    else:
        mu_q, std_q = 0.0, 1.0
        LOGGER.warning("standardizer: no charge targets found; fallback muQ=0 stdQ=1")

    graph_desc_mu, graph_desc_std = _finalize_vector_stats(graph_sum, graph_sq, graph_count)
    graph_desc_std = graph_desc_std.clamp(min=DESCRIPTOR_STD_FLOOR)

    reg_stats = {}
    for stats_key, field_stats in scalar_regression_fields.items():
        mean, std_value = _finalize_scalar_stats(
            field_stats["sum"],
            field_stats["sum_sq"],
            field_stats["count"],
        )
        reg_stats[f"{stats_key}_mu"] = mean
        reg_stats[f"{stats_key}_std"] = max(std_value, DESCRIPTOR_STD_FLOOR)

    LOGGER.info(
        "Energy mu=%.3f std=%.3f | Charge mu=%+.2e std=%.2e | GraphDesc active=%d/%d",
        mu_e,
        std_e,
        mu_q,
        std_q,
        int((graph_count > 0).sum().item()),
        RDKIT_GRAPH_DESC_DIM,
    )
    return {
        "muE": mu_e,
        "stdE": std_e,
        "muQ": mu_q,
        "stdQ": std_q,
        "graph_desc_mu": graph_desc_mu,
        "graph_desc_std": graph_desc_std,
        **reg_stats,
    }


def fast_collate(data_list):
    """Drop large precomputed angle/torsion tensors before batch merge."""
    renamed = []
    for data in data_list:
        if hasattr(data, "angle_triplet"):
            delattr(data, "angle_triplet")
        if hasattr(data, "dihed_quad"):
            delattr(data, "dihed_quad")
        for source_name, temp_name in COLLATE_RENAME_FIELDS.items():
            if hasattr(data, source_name):
                setattr(data, temp_name, getattr(data, source_name))
                delattr(data, source_name)
                renamed.append((data, source_name, temp_name))

    try:
        batch = Batch.from_data_list(data_list)
    finally:
        for data, source_name, temp_name in renamed:
            if hasattr(data, temp_name):
                setattr(data, source_name, getattr(data, temp_name))
                delattr(data, temp_name)

    for source_name, temp_name in COLLATE_RENAME_FIELDS.items():
        if hasattr(batch, temp_name):
            setattr(batch, source_name, getattr(batch, temp_name))
            delattr(batch, temp_name)
    return batch
