from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
import torch
from torch.utils.data import DataLoader, Dataset

from phychem_mfm.data.dataset_lmdb import LmdbMoleculeDataset as NewDataset
from phychem_mfm.training.data import DistributedAtomBudgetBatchSampler
from phychem_mfm.training.datasets import build_pilot_data
from phychem_mfm.training.engine import _resume_train_iterator


def test_real_lmdb_sample_parity(data_root):
    legacy_root = Path(
        os.environ.get(
            "PHYCHEM_LEGACY_ROOT",
            "/share/home/zixiao/descriptor_analysis/modern_ML_representation/support_scripts/MFM_descriptor",
        )
    )
    if not legacy_root.exists():
        pytest.skip(f"Legacy reference unavailable: {legacy_root}")
    sys.path.insert(0, str(legacy_root))
    try:
        from dataset.dataset_lmdb import LmdbMoleculeDataset as OldDataset
    finally:
        sys.path.pop(0)

    shard = data_root / "principal_00000001_00300000.lmdb"
    old_sample = OldDataset(shard, start_idx=0, end_idx=0)[0]
    new_sample = NewDataset(shard, start_idx=0, end_idx=0)[0]
    tensor_fields = (
        "x", "pos", "target_x", "target_pos", "y", "charge_mask",
        "rdkit_graph_desc", "rdkit_graph_desc_mask", "rdkit_node_mask",
        "bond_index", "bond_order", "element_corrupt_mask",
    )
    for field in tensor_fields:
        old_value = getattr(old_sample, field, None)
        new_value = getattr(new_sample, field, None)
        assert isinstance(old_value, torch.Tensor) == isinstance(new_value, torch.Tensor), field
        if isinstance(old_value, torch.Tensor):
            torch.testing.assert_close(new_value, old_value, rtol=0.0, atol=0.0, msg=field)
    assert float(new_sample.energy) == float(old_sample.energy)


def test_atom_budget_batching(data_root):
    bundle = build_pilot_data(
        data_root,
        train_limit=32,
        val_limit=8,
        batch_size=8,
        num_workers=0,
        seed=3,
        standardizer_cap=8,
        atom_budget_per_batch=6144,
    )
    assert isinstance(bundle.train_loader.batch_sampler, DistributedAtomBudgetBatchSampler)
    for batch in bundle.train_loader:
        assert batch.num_graphs <= 8
        assert batch.x.size(0) <= 6144
    assert bundle.manifest["batching"] == {
        "max_samples_per_batch": 8,
        "atom_budget_per_batch": 6144,
    }


class _IndexDataset(Dataset):
    def __len__(self):
        return 9

    def __getitem__(self, index):
        return index


def test_sampler_epoch_cursor_resume_is_exact():
    sampler = DistributedAtomBudgetBatchSampler(
        [1, 4, 2, 3, 1, 4, 2, 3, 1],
        max_atoms_per_batch=5,
        max_samples_per_batch=3,
        seed=17,
    )
    loader = DataLoader(_IndexDataset(), batch_sampler=sampler)
    sampler.set_epoch(3)
    complete_epoch = [batch.tolist() for batch in loader]

    resumed = _resume_train_iterator(loader, epoch=3, batch_offset=2)

    assert [batch.tolist() for batch in resumed] == complete_epoch[2:]
