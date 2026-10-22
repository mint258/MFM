"""Subset indices preserve parent source identities and do not copy LMDB data."""
from __future__ import annotations

from dataclasses import replace
import hashlib
from pathlib import Path

from runtime import ROOT, native_components, old_configuration, setup_imports

setup_imports()
import numpy as np
from s_native_adapter_v2 import ManifestViewsDataset, CountIndex


class SelectedIndex:
    def __init__(self, parent, rows):
        self.parent = parent
        self.rows = np.asarray(rows, dtype=np.int64)
        self.manifest, self.shards = parent.manifest, parent.shards
        self.content_sha256 = hashlib.sha256((parent.content_sha256 + hashlib.sha256(self.rows.tobytes()).hexdigest()).encode()).hexdigest()
    def __len__(self):
        return len(self.rows)
    def ref(self, logical):
        ref = self.parent.ref(int(self.rows[int(logical)]))
        return ref
    def verify_shard_stats(self):
        return self.parent.verify_shard_stats()
    def verify_unchanged(self):
        return self.parent.verify_unchanged()
    def close(self):
        self.parent.close()


class SelectedCounts:
    def __init__(self, index):
        self.index = index
        self.content_sha256 = index.content_sha256
    def __len__(self):
        return len(self.index)
    def ref(self, logical):
        from types import SimpleNamespace
        parent = self.index.parent
        parent._open()
        return SimpleNamespace(native_n_atoms=int(parent._atoms[int(self.index.rows[logical])]))
    def close(self):
        self.index.close()


class SelectedViewsDataset(ManifestViewsDataset):
    def __init__(self, *args, subset_map_close_uses_local_index=False, **kwargs):
        if type(subset_map_close_uses_local_index) is not bool:
            raise ValueError("Subset map-close option must be boolean")
        self.subset_map_close_uses_local_index = subset_map_close_uses_local_index
        super().__init__(*args, **kwargs)

    def _ensure_worker(self, source_logical_index):
        if getattr(self, "subset_map_close_uses_local_index", False):
            local = int(np.searchsorted(self.index.rows, source_logical_index))
            assert int(self.index.rows[local]) == source_logical_index
            super()._ensure_worker(local)
        else:
            super()._ensure_worker(source_logical_index)

    def __getitem__(self, logical_index):
        # Source-global logical index seeds the exact same input as the full
        # dataset. Only the consumption ledger uses the local subset ordinal.
        views = super().__getitem__(logical_index)
        return replace(views, logical_index=int(logical_index))


def selected_components(role, *, seed=0, epoch_noise=False, oracle=False, local_blocks=False):
    parent, original, _ = native_components(role, seed=seed, epoch_noise=epoch_noise)
    path = ROOT / "diagnostics/selection_v1" / ("oracle1000_rows.npy" if oracle else role + "_rows.npy")
    index = SelectedIndex(parent, np.load(path, allow_pickle=False))
    options = dict(old_configuration()["views"])
    if epoch_noise:
        options["noise_seed_includes_epoch"] = True
    dataset = SelectedViewsDataset(index, native_transport=original.native_transport,
        native_transport_binding=original.native_transport_binding, seed=seed,
        subset_map_close_uses_local_index=local_blocks, **options)
    return index, dataset, SelectedCounts(index)
