from __future__ import annotations

from bisect import bisect_right
import hashlib
import logging
import math
import os
import random
from pathlib import Path
import time
from typing import Iterable, List

import numpy as np
import torch
from torch.utils.data import Sampler, Subset
from torch_geometric.data import Batch
from tqdm import tqdm

try:
    from ..dataset import LmdbMoleculeDataset, MoleculeDataset
    from ..dataset.descriptor_schema import (
        BOND_FAIL_REASON_FIELD,
        BOND_INDEX_FIELD,
        BOND_NEGATIVE_COUNT_FIELD,
        BOND_NEGATIVE_UPPER_IDS_FIELD,
        BOND_ORDER_FIELD,
        BOND_STATUS_FIELD,
        ELEMENT_CORRUPT_MASK_FIELD,
        GRAPH_FIELD,
        GRAPH_MASK_FIELD,
        NODE_MASK_FIELD,
        PRETRAIN_BASE_KEY_FIELD,
        PRETRAIN_RECIPE_LEVEL_FIELD,
        PRETRAIN_RECIPE_NAME_FIELD,
        PRETRAIN_RECIPE_SEED_FIELD,
        RDKIT_GRAPH_DESC_DIM,
        canonical_recipe_name,
        recipe_cache_suffix,
    )
except ImportError:
    from dataset import LmdbMoleculeDataset, MoleculeDataset
    from dataset.descriptor_schema import (
        BOND_FAIL_REASON_FIELD,
        BOND_INDEX_FIELD,
        BOND_NEGATIVE_COUNT_FIELD,
        BOND_NEGATIVE_UPPER_IDS_FIELD,
        BOND_ORDER_FIELD,
        BOND_STATUS_FIELD,
        ELEMENT_CORRUPT_MASK_FIELD,
        GRAPH_FIELD,
        GRAPH_MASK_FIELD,
        NODE_MASK_FIELD,
        PRETRAIN_BASE_KEY_FIELD,
        PRETRAIN_RECIPE_LEVEL_FIELD,
        PRETRAIN_RECIPE_NAME_FIELD,
        PRETRAIN_RECIPE_SEED_FIELD,
        RDKIT_GRAPH_DESC_DIM,
        canonical_recipe_name,
        recipe_cache_suffix,
    )

from .dataloader_debug import worker_debug_event, worker_slow_threshold_s
from .degrade_molecules import DegradeConfig, degrade_once
from .utils_debug import is_debug as get_debug_flag

LOGGER = logging.getLogger("multitask")
_TQDM_MININTERVAL = 10.0
_TQDM_MINITERS = 100
COLLATE_RENAME_FIELDS = {
    "rdkit_node_estate_index": "_rdkit_node_estate_index_value",
}
DESCRIPTOR_STD_FLOOR = 1e-3
SPLIT_CACHE_VERSION = 1
ATOM_COUNT_CACHE_VERSION = 1
SAMPLE_TYPE_TO_ID = {
    "clean": 0,
    "geom": 1,
    "topo": 2,
    "both": 3,
}
SAMPLE_TYPE_ID_TO_NAME = {value: key for key, value in SAMPLE_TYPE_TO_ID.items()}
RDKIT_NODE_LONG_FIELDS = (
    "rdkit_node_formal_charge",
    "rdkit_node_hybridization",
    "rdkit_node_min_ring_size",
    "rdkit_node_total_degree",
    "rdkit_node_total_num_Hs",
    "rdkit_node_total_valence",
    "rdkit_node_estate_type",
    "rdkit_node_chiral_tag",
    "rdkit_node_cip_code",
)
RDKIT_NODE_FLOAT_FIELDS = ("rdkit_node_estate_index",)
RDKIT_NODE_BOOL_FIELDS = (
    "rdkit_node_is_aromatic",
    "rdkit_node_is_in_ring",
    "rdkit_node_donor",
    "rdkit_node_acceptor",
    "rdkit_node_mask",
)


def _ensure_element_corrupt_mask(data) -> None:
    value = getattr(data, ELEMENT_CORRUPT_MASK_FIELD, None)
    if isinstance(value, torch.Tensor):
        setattr(data, ELEMENT_CORRUPT_MASK_FIELD, value.bool())
        return
    if hasattr(data, "x"):
        setattr(
            data,
            ELEMENT_CORRUPT_MASK_FIELD,
            torch.zeros((int(data.x.size(0)), 1), dtype=torch.bool, device=data.x.device),
        )


def _data_key_set(data) -> set[str]:
    keys = getattr(data, "keys", None)
    if callable(keys):
        return {str(key) for key in keys()}
    if isinstance(keys, (list, tuple, set)):
        return {str(key) for key in keys}
    return set()


def _ensure_training_field_placeholders(data) -> None:
    keys = _data_key_set(data)
    n_atom = _sample_atom_count(data)

    if "energy" not in keys:
        data.energy = 0.0
    if "energy_unit" not in keys or not isinstance(getattr(data, "energy_unit", None), str):
        data.energy_unit = "unknown"

    if n_atom > 0:
        if "y" not in keys:
            data.y = torch.zeros((n_atom, 1), dtype=torch.float32)
        elif isinstance(getattr(data, "y", None), torch.Tensor) and data.y.dtype != torch.float32:
            data.y = data.y.float()

        if "charge_mask" not in keys:
            data.charge_mask = torch.zeros((n_atom, 1), dtype=torch.float32)
        elif isinstance(getattr(data, "charge_mask", None), torch.Tensor) and data.charge_mask.dtype != torch.float32:
            data.charge_mask = data.charge_mask.float()

        for name in RDKIT_NODE_LONG_FIELDS:
            if name not in keys:
                setattr(data, name, torch.zeros((n_atom, 1), dtype=torch.long))
        for name in RDKIT_NODE_FLOAT_FIELDS:
            if name not in keys:
                setattr(data, name, torch.zeros((n_atom, 1), dtype=torch.float32))
        for name in RDKIT_NODE_BOOL_FIELDS:
            if name not in keys:
                setattr(data, name, torch.zeros((n_atom, 1), dtype=torch.bool))

    if GRAPH_FIELD not in keys:
        setattr(data, GRAPH_FIELD, torch.zeros((RDKIT_GRAPH_DESC_DIM,), dtype=torch.float32))
    elif isinstance(getattr(data, GRAPH_FIELD, None), torch.Tensor) and getattr(data, GRAPH_FIELD).dtype != torch.float32:
        setattr(data, GRAPH_FIELD, getattr(data, GRAPH_FIELD).float())

    if GRAPH_MASK_FIELD not in keys:
        setattr(data, GRAPH_MASK_FIELD, torch.zeros((RDKIT_GRAPH_DESC_DIM,), dtype=torch.bool))
    elif isinstance(getattr(data, GRAPH_MASK_FIELD, None), torch.Tensor) and getattr(data, GRAPH_MASK_FIELD).dtype != torch.bool:
        setattr(data, GRAPH_MASK_FIELD, getattr(data, GRAPH_MASK_FIELD).bool())

    if BOND_INDEX_FIELD not in keys:
        setattr(data, BOND_INDEX_FIELD, torch.zeros((2, 0), dtype=torch.long))
    if BOND_ORDER_FIELD not in keys:
        setattr(data, BOND_ORDER_FIELD, torch.zeros((0,), dtype=torch.long))
    if BOND_NEGATIVE_UPPER_IDS_FIELD not in keys:
        setattr(data, BOND_NEGATIVE_UPPER_IDS_FIELD, torch.zeros((0,), dtype=torch.long))
    if BOND_NEGATIVE_COUNT_FIELD not in keys:
        setattr(data, BOND_NEGATIVE_COUNT_FIELD, torch.zeros((1,), dtype=torch.long))
    if BOND_STATUS_FIELD not in keys or not isinstance(getattr(data, BOND_STATUS_FIELD, None), str):
        setattr(data, BOND_STATUS_FIELD, "")
    if BOND_FAIL_REASON_FIELD not in keys or not isinstance(getattr(data, BOND_FAIL_REASON_FIELD, None), str):
        setattr(data, BOND_FAIL_REASON_FIELD, "")


def _ensure_pretrain_recipe_metadata(data, *, sample_type: str, level: float, seed: int) -> None:
    base_key = str(getattr(data, PRETRAIN_BASE_KEY_FIELD, getattr(data, "sample_key", "")) or "")
    setattr(data, PRETRAIN_BASE_KEY_FIELD, base_key)

    recipe_name = getattr(data, PRETRAIN_RECIPE_NAME_FIELD, None)
    if not isinstance(recipe_name, str) or not recipe_name:
        setattr(data, PRETRAIN_RECIPE_NAME_FIELD, canonical_recipe_name(sample_type, level))

    recipe_level = getattr(data, PRETRAIN_RECIPE_LEVEL_FIELD, None)
    if not isinstance(recipe_level, float):
        setattr(data, PRETRAIN_RECIPE_LEVEL_FIELD, float(level))

    recipe_seed = getattr(data, PRETRAIN_RECIPE_SEED_FIELD, None)
    if not isinstance(recipe_seed, int):
        setattr(data, PRETRAIN_RECIPE_SEED_FIELD, int(seed))


class DatasetBuildError(RuntimeError):
    """Raised when a dataset root cannot be opened or initialized."""


def _unwrap_base_dataset(dataset):
    current = dataset
    seen = set()
    while True:
        ident = id(current)
        if ident in seen:
            break
        seen.add(ident)
        next_dataset = getattr(current, "base", None)
        if next_dataset is None:
            break
        current = next_dataset
    return current


def _sample_atom_count(data) -> int:
    value = getattr(data, "x", None)
    if isinstance(value, torch.Tensor) and value.dim() >= 1:
        return int(value.size(0))
    value = getattr(data, "elem", None)
    if isinstance(value, torch.Tensor) and value.dim() >= 1:
        return int(value.size(0))
    value = getattr(data, "pos", None)
    if isinstance(value, torch.Tensor) and value.dim() >= 1:
        return int(value.size(0))
    return 0


def normalize_sample_type_name(name: str) -> str:
    normalized = str(name).strip().lower()
    if normalized not in SAMPLE_TYPE_TO_ID:
        raise ValueError(f"Unknown sample type: {name}")
    return normalized


def sample_type_id_from_name(name: str) -> int:
    return int(SAMPLE_TYPE_TO_ID[normalize_sample_type_name(name)])


def resolve_precomputed_recipe_lmdb_path(lmdb_path: str, mode: str, level: float) -> str:
    root, ext = os.path.splitext(str(Path(lmdb_path).resolve()))
    return f"{root}.{recipe_cache_suffix(mode, level)}{ext or '.lmdb'}"


def _copy_common_dataset_attrs(src, dst) -> None:
    for attr_name in ("source_path", "slice_start", "slice_end", "lmdb_path"):
        if hasattr(src, attr_name):
            setattr(dst, attr_name, getattr(src, attr_name))
    atom_counts = getattr(src, "atom_counts", None)
    if atom_counts is not None:
        dst.atom_counts = np.asarray(atom_counts, dtype=np.int32)


def try_build_precomputed_recipe_dataset(dataset, *, mode: str, level: float):
    if isinstance(dataset, LmdbMoleculeDataset):
        derived_path = resolve_precomputed_recipe_lmdb_path(dataset.lmdb_path, mode, level)
        if not os.path.exists(derived_path):
            return None
        mirrored = LmdbMoleculeDataset(
            derived_path,
            start_idx=getattr(dataset, "start", None),
            end_idx=getattr(dataset, "end", None),
            limit=len(dataset.idx_list) if getattr(dataset, "idx_list", None) is not None else None,
            filter_missing_on_init=True,
        )
        mirrored.source_path = derived_path
        mirrored.slice_start = getattr(dataset, "start", 0)
        mirrored.slice_end = getattr(dataset, "end", None)
        return mirrored

    if isinstance(dataset, SafeResampleDataset):
        mirrored_base = try_build_precomputed_recipe_dataset(dataset.base, mode=mode, level=level)
        if mirrored_base is None:
            return None
        mirrored = SafeResampleDataset(
            mirrored_base,
            max_retries=dataset.max_retries,
            name=dataset.name,
            seed=getattr(dataset, "seed", 0),
        )
        _copy_common_dataset_attrs(dataset, mirrored)
        return mirrored

    if isinstance(dataset, OnlyStableWrapper):
        mirrored_base = try_build_precomputed_recipe_dataset(dataset.base, mode=mode, level=level)
        if mirrored_base is None:
            return None
        mirrored = OnlyStableWrapper(mirrored_base)
        _copy_common_dataset_attrs(dataset, mirrored)
        return mirrored

    if isinstance(dataset, IndexedSubsetDataset):
        mirrored_base = try_build_precomputed_recipe_dataset(dataset.base, mode=mode, level=level)
        if mirrored_base is None:
            return None
        mirrored = IndexedSubsetDataset(mirrored_base, dataset.indices, atom_counts=getattr(dataset, "atom_counts", None))
        _copy_common_dataset_attrs(dataset, mirrored)
        return mirrored

    if isinstance(dataset, ExcludingSubsetDataset):
        mirrored_base = try_build_precomputed_recipe_dataset(dataset.base, mode=mode, level=level)
        if mirrored_base is None:
            return None
        mirrored = ExcludingSubsetDataset(mirrored_base, dataset.excluded)
        _copy_common_dataset_attrs(dataset, mirrored)
        return mirrored

    if isinstance(dataset, Subset):
        mirrored_base = try_build_precomputed_recipe_dataset(dataset.dataset, mode=mode, level=level)
        if mirrored_base is None:
            return None
        return Subset(mirrored_base, dataset.indices)

    return None


def _atom_count_cache_path(dataset, cache_dir: str) -> Path:
    source_path = str(getattr(dataset, "source_path", getattr(dataset, "lmdb_path", type(dataset).__name__)))
    slice_start = int(getattr(dataset, "slice_start", 0) or 0)
    slice_end = getattr(dataset, "slice_end", None)
    key = f"{ATOM_COUNT_CACHE_VERSION}|{Path(source_path).resolve()}|{slice_start}|{slice_end}|{len(dataset)}"
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    filename = f"{Path(source_path).stem}_s{slice_start}_e{slice_end if slice_end is not None else 'end'}_{digest}.pt"
    return Path(cache_dir).resolve() / filename


def atom_count_cache_path(dataset, cache_dir: str | None) -> Path | None:
    if not cache_dir:
        return None
    return _atom_count_cache_path(dataset, cache_dir)


def _atom_count_cache_prefix(dataset) -> str:
    source_path = str(getattr(dataset, "source_path", getattr(dataset, "lmdb_path", type(dataset).__name__)))
    slice_start = int(getattr(dataset, "slice_start", 0) or 0)
    slice_end = getattr(dataset, "slice_end", None)
    return f"{Path(source_path).stem}_s{slice_start}_e{slice_end if slice_end is not None else 'end'}"


def _legacy_atom_count_cache_paths(dataset, cache_dir: str | None) -> list[Path]:
    if not cache_dir:
        return []

    candidates: list[Path] = []
    # Backward compatibility: older runs computed atom-count cache keys from the
    # wrapper class name because wrapper datasets did not preserve source_path.
    legacy_source_path = type(dataset).__name__
    legacy_key = f"{ATOM_COUNT_CACHE_VERSION}|{Path(legacy_source_path).resolve()}|0|None|{len(dataset)}"
    legacy_digest = hashlib.sha1(legacy_key.encode("utf-8")).hexdigest()[:16]
    legacy_filename = f"{legacy_source_path}_s0_eend_{legacy_digest}.pt"
    legacy_path = Path(cache_dir).resolve() / legacy_filename

    canonical_path = atom_count_cache_path(dataset, cache_dir)
    if canonical_path is None or legacy_path != canonical_path:
        candidates.append(legacy_path)
    return candidates


def _compatible_atom_count_cache_paths(dataset, cache_dir: str | None) -> list[Path]:
    if not cache_dir:
        return []

    cache_root = Path(cache_dir).resolve()
    if not cache_root.exists():
        return []

    prefix = _atom_count_cache_prefix(dataset)
    canonical_path = atom_count_cache_path(dataset, cache_dir)
    compatible = [
        path
        for path in cache_root.glob(f"{prefix}_*.pt")
        if canonical_path is None or path != canonical_path
    ]
    compatible.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
    return compatible


def _atomic_torch_save(payload, cache_file: Path) -> None:
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = cache_file.with_name(f"{cache_file.name}.tmp.{os.getpid()}")
    try:
        torch.save(payload, tmp_file)
        os.replace(tmp_file, cache_file)
    finally:
        if tmp_file.exists():
            try:
                tmp_file.unlink()
            except OSError:
                pass


def _load_atom_count_cache_payload(cache_file: Path, *, expected_length: int) -> dict | None:
    try:
        payload = torch.load(cache_file, map_location="cpu")
    except Exception as exc:
        LOGGER.warning("Failed to load atom-count cache %s; will recompute. Error: %s", cache_file, exc)
        return None

    try:
        counts = np.asarray(payload.get("atom_counts"), dtype=np.int32)
    except Exception as exc:
        LOGGER.warning("Atom-count cache %s is malformed; will recompute. Error: %s", cache_file, exc)
        return None

    if int(payload.get("version", -1)) != ATOM_COUNT_CACHE_VERSION:
        LOGGER.warning("Atom-count cache %s has version mismatch; will recompute.", cache_file)
        return None
    if int(payload.get("length", -1)) != int(expected_length):
        LOGGER.warning("Atom-count cache %s has length mismatch; will recompute.", cache_file)
        return None
    if counts.shape[0] != int(expected_length):
        LOGGER.warning("Atom-count cache %s has truncated contents; will recompute.", cache_file)
        return None
    payload["atom_counts"] = counts
    return payload


def _load_atom_count_cache(cache_file: Path, *, expected_length: int) -> np.ndarray | None:
    payload = _load_atom_count_cache_payload(cache_file, expected_length=expected_length)
    if payload is None:
        return None
    return np.asarray(payload["atom_counts"], dtype=np.int32)


def _canonical_atom_count_payload(dataset, counts: np.ndarray, payload: dict | None = None) -> dict:
    return {
        "version": ATOM_COUNT_CACHE_VERSION,
        "length": int(len(dataset)),
        "source_path": str(getattr(dataset, "source_path", getattr(dataset, "lmdb_path", ""))),
        "slice_start": int(getattr(dataset, "slice_start", 0) or 0),
        "slice_end": getattr(dataset, "slice_end", None),
        "atom_counts": np.asarray(counts, dtype=np.int16),
        "invalid_count": int((payload or {}).get("invalid_count", 0)),
    }


def _load_or_migrate_atom_count_cache(dataset, *, cache_dir: str | None = None) -> tuple[np.ndarray | None, Path | None]:
    canonical_path = atom_count_cache_path(dataset, cache_dir)
    candidate_paths: list[Path] = []
    if canonical_path is not None:
        candidate_paths.append(canonical_path)
    candidate_paths.extend(_legacy_atom_count_cache_paths(dataset, cache_dir))
    candidate_paths.extend(_compatible_atom_count_cache_paths(dataset, cache_dir))

    for cache_file in candidate_paths:
        if not cache_file.exists():
            continue
        payload = _load_atom_count_cache_payload(cache_file, expected_length=len(dataset))
        if payload is None:
            continue

        counts = np.asarray(payload["atom_counts"], dtype=np.int32)
        if canonical_path is not None and cache_file != canonical_path:
            _atomic_torch_save(_canonical_atom_count_payload(dataset, counts, payload), canonical_path)
            LOGGER.info("Reused atom-count cache %s -> %s", cache_file, canonical_path)
            return counts, canonical_path
        return counts, cache_file

    return None, canonical_path


def try_load_atom_count_cache(dataset, *, cache_dir: str | None = None) -> np.ndarray | None:
    counts, _ = _load_or_migrate_atom_count_cache(dataset, cache_dir=cache_dir)
    return counts


def resolve_atom_counts(dataset, *, cache_dir: str | None = None, force_recompute: bool = False) -> np.ndarray:
    cache_file = _atom_count_cache_path(dataset, cache_dir) if cache_dir else None
    if cache_dir and not force_recompute:
        cached, used_cache_file = _load_or_migrate_atom_count_cache(dataset, cache_dir=cache_dir)
        if cached is not None:
            if used_cache_file is not None:
                LOGGER.info("Loaded atom-count cache from %s", used_cache_file)
            return cached

    raw_dataset = _unwrap_base_dataset(dataset)
    counts = np.zeros(len(dataset), dtype=np.int32)
    invalid = 0
    iterator = range(len(dataset))
    desc = f"AtomCount[{Path(str(getattr(dataset, 'source_path', 'dataset'))).name}]"
    for idx in tqdm(iterator, desc=desc, mininterval=_TQDM_MININTERVAL, miniters=_TQDM_MINITERS):
        try:
            counts[idx] = max(0, _sample_atom_count(raw_dataset[idx]))
        except Exception as exc:
            invalid += 1
            counts[idx] = 0
            LOGGER.warning("Atom-count scan failed at idx=%d for %s: %s", idx, desc, exc)

    if cache_file:
        _atomic_torch_save(
            _canonical_atom_count_payload(
                dataset,
                counts,
                {"invalid_count": int(invalid)},
            ),
            cache_file,
        )
        LOGGER.info("Saved atom-count cache to %s (invalid=%d)", cache_file, invalid)

    return counts


def seed_worker(worker_id: int) -> None:
    worker_seed = torch.initial_seed() % (2**32)
    np.random.seed(worker_seed)
    random.seed(worker_seed)
    worker_debug_event("worker_init", worker_id=int(worker_id), worker_seed=int(worker_seed))


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


def _stable_dataset_seed(path: str, start_idx: int | None, end_idx: int | None) -> int:
    key = f"{Path(path).resolve()}|{0 if start_idx is None else int(start_idx)}|{end_idx}"
    return int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:8], 16)


def create_dataset(path: str, start_idx: int | None, end_idx: int | None, *, seed: int | None = None):
    """Create and wrap a dataset with resilient sample fetching."""
    start_idx = start_idx if start_idx is not None else 0
    end_idx = end_idx if end_idx not in (None, -1) else None

    try:
        if path.endswith(".lmdb") or (os.path.isfile(path) and path.lower().endswith(".lmdb")) or os.path.isdir(path):
            dataset = LmdbMoleculeDataset(path, start_idx=start_idx, end_idx=end_idx, filter_missing_on_init=True)
        else:
            dataset = MoleculeDataset(path, start_idx=start_idx, end_idx=end_idx)
    except Exception as exc:
        raise DatasetBuildError(
            f"Failed to initialize dataset root '{path}' (start={start_idx}, end={end_idx}): {exc}"
        ) from exc

    wrapped = SafeResampleDataset(
        dataset,
        max_retries=32,
        name=os.path.basename(path),
        seed=_stable_dataset_seed(path, start_idx, end_idx) if seed is None else int(seed),
    )
    wrapped.source_path = path
    wrapped.slice_start = start_idx
    wrapped.slice_end = end_idx
    return wrapped


def create_dataset_or_none(path: str, start_idx: int | None, end_idx: int | None, *, role: str, seed: int | None = None) -> torch.utils.data.Dataset | None:
    try:
        return create_dataset(path, start_idx, end_idx, seed=seed)
    except DatasetBuildError as exc:
        LOGGER.error("Skipping %s dataset root due to load failure: %s", role, exc)
        return None


class SafeResampleDataset(torch.utils.data.Dataset):
    """Resample on invalid examples without changing dataset length."""

    def __init__(self, base, max_retries: int = 32, name: str = "", seed: int = 0):
        self.base = base
        self.max_retries = int(max_retries)
        self.name = name or type(base).__name__
        self.seed = int(seed)

    def __len__(self):
        return len(self.base)

    def _fallback_index(self, logical_idx: int, try_index: int) -> int:
        if len(self.base) <= 1:
            return 0
        key = f"{self.seed}|{int(logical_idx)}|{int(try_index)}|{len(self.base)}"
        fallback_seed = int(hashlib.sha1(key.encode("utf-8")).hexdigest()[:16], 16)
        return int(np.random.default_rng(fallback_seed).integers(0, len(self.base)))

    def __getitem__(self, idx):
        tries = 0
        cur_idx = idx
        slow_threshold = worker_slow_threshold_s()
        while tries < self.max_retries:
            fetch_start = time.perf_counter()
            try:
                data = self.base[cur_idx]
                if hasattr(data, "pos"):
                    pos = data.pos
                    if pos.numel() == 0 or (not torch.isfinite(pos).all()):
                        raise ValueError("invalid pos")
                if hasattr(data, "x") and data.x.numel() == 0:
                    raise ValueError("empty x")
                elapsed = time.perf_counter() - fetch_start
                if elapsed >= slow_threshold:
                    worker_debug_event(
                        "slow_sample_fetch",
                        dataset=self.name,
                        logical_index=int(idx),
                        resolved_index=int(cur_idx),
                        elapsed_s=round(float(elapsed), 3),
                        retries=int(tries),
                    )
                return data
            except Exception as exc:
                worker_debug_event(
                    "sample_fetch_error",
                    dataset=self.name,
                    logical_index=int(idx),
                    resolved_index=int(cur_idx),
                    try_index=int(tries),
                    error=repr(exc),
                )
                tries += 1
                cur_idx = self._fallback_index(int(idx), tries)

        worker_debug_event(
            "sample_fetch_failed",
            dataset=self.name,
            logical_index=int(idx),
            retries=int(self.max_retries),
        )
        raise IndexError(f"[SafeResampleDataset:{self.name}] too many invalid samples (idx={idx})")


class OnlyStableWrapper(torch.utils.data.Dataset):
    """Drop trajectory fields and keep stable-structure data only."""

    def __init__(self, base):
        self.base = base
        for attr_name in ("source_path", "slice_start", "slice_end", "lmdb_path"):
            if hasattr(base, attr_name):
                setattr(self, attr_name, getattr(base, attr_name))
        atom_counts = getattr(base, "atom_counts", None)
        if atom_counts is not None:
            self.atom_counts = np.asarray(atom_counts, dtype=np.int32)

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
        atom_counts = getattr(base, "atom_counts", None)
        if atom_counts is None:
            try:
                atom_counts = dataset_atom_counts(base)
            except ValueError:
                atom_counts = None
        if atom_counts is not None:
            self.atom_counts = np.asarray(atom_counts, dtype=np.int32)

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        data = self.base[idx]
        data.domain_id = torch.tensor([self.domain_id], dtype=torch.long)
        return data


class SampleTypeWrapperDataset(torch.utils.data.Dataset):
    """Attach a per-graph sample type for downstream loss routing."""

    def __init__(self, base, sample_type: str):
        self.base = base
        self.sample_type = normalize_sample_type_name(sample_type)
        self.sample_type_id = sample_type_id_from_name(self.sample_type)
        for attr_name in ("source_path", "slice_start", "slice_end", "lmdb_path"):
            if hasattr(base, attr_name):
                setattr(self, attr_name, getattr(base, attr_name))
        atom_counts = getattr(base, "atom_counts", None)
        if atom_counts is not None:
            self.atom_counts = np.asarray(atom_counts, dtype=np.int32)

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        data = self.base[idx]
        if hasattr(data, "x") and "target_x" not in _data_key_set(data):
            data.target_x = data.x.clone()
        if hasattr(data, "pos") and "target_pos" not in _data_key_set(data):
            data.target_pos = data.pos.clone()
        _ensure_training_field_placeholders(data)
        _ensure_element_corrupt_mask(data)
        data.sample_type_id = torch.tensor([self.sample_type_id], dtype=torch.long)
        _ensure_pretrain_recipe_metadata(
            data,
            sample_type=self.sample_type,
            level=0.0,
            seed=0,
        )
        return data


class ExcludingSubsetDataset(torch.utils.data.Dataset):
    """View of a dataset with a small excluded index set removed."""

    def __init__(self, base, excluded_indices):
        self.base = base
        self.excluded = sorted({int(i) for i in excluded_indices})
        if any(i < 0 or i >= len(base) for i in self.excluded):
            raise IndexError("Excluded indices are out of range for the base dataset.")
        self._shifted = [value - pos for pos, value in enumerate(self.excluded)]
        self.length = len(base) - len(self.excluded)
        if self.length <= 0:
            raise ValueError("ExcludingSubsetDataset would be empty after exclusions.")
        atom_counts = getattr(base, "atom_counts", None)
        if atom_counts is not None:
            base_counts = np.asarray(atom_counts, dtype=np.int32)
            keep_mask = np.ones(len(base_counts), dtype=bool)
            keep_mask[self.excluded] = False
            self.atom_counts = base_counts[keep_mask]

    def __len__(self):
        return self.length

    def _map_index(self, idx: int) -> int:
        if idx < 0:
            idx += self.length
        if idx < 0 or idx >= self.length:
            raise IndexError(idx)

        actual = idx
        shift = bisect_right(self._shifted, actual)
        return actual + shift

    def __getitem__(self, idx):
        return self.base[self._map_index(int(idx))]


class IndexedSubsetDataset(torch.utils.data.Dataset):
    """Subset view that preserves explicit per-sample atom counts."""

    def __init__(self, base, indices, atom_counts=None):
        self.base = base
        self.indices = np.asarray(list(indices), dtype=np.int64)
        if self.indices.ndim != 1:
            raise ValueError("indices must be a flat sequence")
        if len(self.indices) == 0:
            raise ValueError("IndexedSubsetDataset cannot be empty")
        if atom_counts is None:
            base_counts = getattr(base, "atom_counts", None)
            if base_counts is not None:
                atom_counts = np.asarray(base_counts, dtype=np.int32)[self.indices]
        if atom_counts is not None:
            self.atom_counts = np.asarray(atom_counts, dtype=np.int32)

    def __len__(self):
        return int(self.indices.shape[0])

    def __getitem__(self, idx):
        return self.base[int(self.indices[int(idx)])]


class DistributedEvalSampler(Sampler[int]):
    """Distributed evaluation sampler without padding, duplication, or dropping."""

    def __init__(self, dataset, *, num_replicas: int, rank: int):
        self.dataset = dataset
        self.num_replicas = int(num_replicas)
        self.rank = int(rank)
        if self.num_replicas <= 0:
            raise ValueError("num_replicas must be positive")
        if self.rank < 0 or self.rank >= self.num_replicas:
            raise ValueError("rank must be within [0, num_replicas)")

    def __iter__(self):
        return iter(range(self.rank, len(self.dataset), self.num_replicas))

    def __len__(self):
        total = len(self.dataset)
        if total <= self.rank:
            return 0
        return 1 + (total - 1 - self.rank) // self.num_replicas


class DistributedEvalAtomBudgetBatchSampler(Sampler[list[int]]):
    """Distributed evaluation batch sampler without padding or duplication."""

    def __init__(
        self,
        atom_counts,
        *,
        max_atoms_per_batch: int,
        max_samples_per_batch: int,
        num_replicas: int = 1,
        rank: int = 0,
    ):
        self.atom_counts = np.asarray(atom_counts, dtype=np.int32)
        self.max_atoms_per_batch = int(max_atoms_per_batch)
        self.max_samples_per_batch = int(max_samples_per_batch)
        self.num_replicas = int(num_replicas)
        self.rank = int(rank)

        if self.max_atoms_per_batch <= 0:
            raise ValueError("max_atoms_per_batch must be positive")
        if self.max_samples_per_batch <= 0:
            raise ValueError("max_samples_per_batch must be positive")
        if self.num_replicas <= 0:
            raise ValueError("num_replicas must be positive")
        if self.rank < 0 or self.rank >= self.num_replicas:
            raise ValueError("rank must be within [0, num_replicas)")

    def _local_indices(self) -> list[int]:
        return list(range(self.rank, len(self.atom_counts), self.num_replicas))

    def __iter__(self):
        batch: list[int] = []
        batch_atoms = 0
        for idx in self._local_indices():
            atom_count = int(self.atom_counts[idx])
            if atom_count <= 0:
                continue
            would_exceed_atoms = batch_atoms + atom_count > self.max_atoms_per_batch
            would_exceed_samples = len(batch) >= self.max_samples_per_batch
            if batch and (would_exceed_atoms or would_exceed_samples):
                yield batch
                batch = []
                batch_atoms = 0
            batch.append(int(idx))
            batch_atoms += atom_count

        if batch:
            yield batch

    def __len__(self):
        batches = 0
        batch_atoms = 0
        batch_size = 0
        for idx in self._local_indices():
            atom_count = int(self.atom_counts[idx])
            if atom_count <= 0:
                continue
            would_exceed_atoms = batch_atoms + atom_count > self.max_atoms_per_batch
            would_exceed_samples = batch_size >= self.max_samples_per_batch
            if batch_size > 0 and (would_exceed_atoms or would_exceed_samples):
                batches += 1
                batch_atoms = 0
                batch_size = 0
            batch_atoms += atom_count
            batch_size += 1
        if batch_size > 0:
            batches += 1
        return batches


class DistributedAtomBudgetBatchSampler(Sampler[list[int]]):
    """DDP-aware train batch sampler that caps total atoms per batch."""

    def __init__(
        self,
        atom_counts,
        *,
        max_atoms_per_batch: int,
        max_samples_per_batch: int,
        num_replicas: int = 1,
        rank: int = 0,
        shuffle: bool = True,
        seed: int = 0,
        drop_last: bool = False,
    ):
        self.atom_counts = np.asarray(atom_counts, dtype=np.int32)
        self.max_atoms_per_batch = int(max_atoms_per_batch)
        self.max_samples_per_batch = int(max_samples_per_batch)
        self.num_replicas = int(num_replicas)
        self.rank = int(rank)
        self.shuffle = bool(shuffle)
        self.seed = int(seed)
        self.drop_last = bool(drop_last)
        self.epoch = 0
        self.bucket_size = max(self.max_samples_per_batch * 32, self.max_samples_per_batch)

        if self.max_atoms_per_batch <= 0:
            raise ValueError("max_atoms_per_batch must be positive")
        if self.max_samples_per_batch <= 0:
            raise ValueError("max_samples_per_batch must be positive")
        if self.num_replicas <= 0:
            raise ValueError("num_replicas must be positive")
        if self.rank < 0 or self.rank >= self.num_replicas:
            raise ValueError("rank must be within [0, num_replicas)")

    def set_epoch(self, epoch: int) -> None:
        self.epoch = int(epoch)

    def _local_indices(self) -> list[int]:
        total_size = len(self.atom_counts)
        indices = list(range(total_size))
        rng = np.random.default_rng(self.seed + self.epoch)
        if self.shuffle:
            rng.shuffle(indices)

        if self.drop_last:
            indices = indices[: total_size - (total_size % self.num_replicas)]
        else:
            padding = (-len(indices)) % self.num_replicas
            if padding > 0 and indices:
                indices.extend(indices[:padding])

        local = indices[self.rank :: self.num_replicas]
        if not self.shuffle or len(local) <= 1:
            return local

        # Keep similarly sized molecules near each other without creating a
        # single monotonic small->large curriculum across the whole epoch.
        local.sort(key=lambda idx: int(self.atom_counts[idx]))
        buckets = [
            local[start : start + self.bucket_size]
            for start in range(0, len(local), self.bucket_size)
        ]
        bucket_order = list(rng.permutation(len(buckets)))
        shuffled_local: list[int] = []
        for bucket_idx in bucket_order:
            bucket = list(buckets[int(bucket_idx)])
            rng.shuffle(bucket)
            shuffled_local.extend(bucket)
        return shuffled_local

    def __iter__(self):
        batch: list[int] = []
        batch_atoms = 0
        for idx in self._local_indices():
            atom_count = int(self.atom_counts[idx])
            if atom_count <= 0:
                continue
            would_exceed_atoms = batch_atoms + atom_count > self.max_atoms_per_batch
            would_exceed_samples = len(batch) >= self.max_samples_per_batch
            if batch and (would_exceed_atoms or would_exceed_samples):
                yield batch
                batch = []
                batch_atoms = 0
            batch.append(int(idx))
            batch_atoms += atom_count

        if batch and not self.drop_last:
            yield batch

    def __len__(self):
        batches = 0
        batch_atoms = 0
        batch_size = 0
        for idx in self._local_indices():
            atom_count = int(self.atom_counts[idx])
            if atom_count <= 0:
                continue
            would_exceed_atoms = batch_atoms + atom_count > self.max_atoms_per_batch
            would_exceed_samples = batch_size >= self.max_samples_per_batch
            if batch_size > 0 and (would_exceed_atoms or would_exceed_samples):
                batches += 1
                batch_atoms = 0
                batch_size = 0
            batch_atoms += atom_count
            batch_size += 1
        if batch_size > 0 and not self.drop_last:
            batches += 1
        return batches


class MaskedPerturbDataset(torch.utils.data.Dataset):
    """Apply degradation while keeping clean targets for denoising supervision."""

    def __init__(self, base, cfg: DegradeConfig, seed: int = 114):
        self.base = base
        self.cfg = cfg.finalize()
        self.seed = int(seed)
        self.sample_type = normalize_sample_type_name(self.cfg.mode)
        self.sample_type_id = sample_type_id_from_name(self.sample_type)
        atom_counts = getattr(base, "atom_counts", None)
        if atom_counts is not None:
            self.atom_counts = np.asarray(atom_counts, dtype=np.int32)

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx):
        d0 = self.base[idx]

        clean_x = d0.x.clone() if hasattr(d0, "x") else None
        clean_pos = d0.pos.clone() if hasattr(d0, "pos") else None

        gen = torch.Generator(device=d0.x.device if d0.x.is_cuda else "cpu").manual_seed(self.seed + idx)
        degrade_start = time.perf_counter()
        data = degrade_once(d0, self.cfg, gen)
        degrade_elapsed = time.perf_counter() - degrade_start
        if degrade_elapsed >= worker_slow_threshold_s():
            worker_debug_event(
                "slow_degrade_once",
                index=int(idx),
                elapsed_s=round(float(degrade_elapsed), 3),
                mode=self.cfg.mode,
                level=float(self.cfg.level),
            )

        if clean_x is not None:
            data.target_x = clean_x
        if clean_pos is not None:
            data.target_pos = clean_pos
        _ensure_training_field_placeholders(data)
        _ensure_element_corrupt_mask(data)
        data.sample_type_id = torch.tensor([self.sample_type_id], dtype=torch.long)
        _ensure_pretrain_recipe_metadata(
            data,
            sample_type=self.sample_type,
            level=float(self.cfg.level),
            seed=self.seed + int(idx),
        )

        for attr in ("is_feasible", "neg_type"):
            if hasattr(data, attr):
                delattr(data, attr)

        return data


def _normalize_spec_payload(path: str, start_idx: int | None, end_idx: int | None, length: int) -> dict:
    return {
        "path": str(Path(path).resolve()),
        "start": int(start_idx) if start_idx is not None else 0,
        "end": None if end_idx is None else int(end_idx),
        "length": int(length),
    }


def _validate_split_cache(payload: dict, dataset_specs: list[dict], *, val_size: int, seed: int) -> None:
    if int(payload.get("version", -1)) != SPLIT_CACHE_VERSION:
        raise ValueError("Split cache version mismatch.")
    if int(payload.get("val_size", -1)) != int(val_size):
        raise ValueError("Split cache val_size mismatch.")
    if int(payload.get("seed", -1)) != int(seed):
        raise ValueError("Split cache seed mismatch.")

    cached_specs = payload.get("datasets", [])
    if len(cached_specs) != len(dataset_specs):
        raise ValueError("Split cache dataset count mismatch.")

    for cached, current in zip(cached_specs, dataset_specs):
        current_view = {key: current[key] for key in ("path", "start", "end", "length")}
        cached_view = {key: cached.get(key) for key in ("path", "start", "end", "length")}
        if cached_view != current_view:
            raise ValueError("Split cache dataset specification mismatch.")


def resolve_random_val_split(
    dataset_specs: list[dict],
    *,
    val_size: int,
    seed: int,
    cache_path: str | None = None,
    force_recompute: bool = False,
) -> list[list[int]]:
    """Generate or load a random validation split over the union of all dataset roots."""
    total_size = sum(int(spec["length"]) for spec in dataset_specs)
    if total_size <= 1:
        raise ValueError("Random train/val split requires at least two samples in total.")

    requested_val_size = max(0, int(val_size))
    effective_val_size = min(requested_val_size, total_size - 1)
    if effective_val_size <= 0:
        return [[] for _ in dataset_specs]

    cache_file = Path(cache_path).resolve() if cache_path else None
    if cache_file and cache_file.exists() and not force_recompute:
        try:
            payload = torch.load(cache_file, map_location="cpu")
            _validate_split_cache(payload, dataset_specs, val_size=effective_val_size, seed=seed)
            return [list(map(int, item.get("val_indices", []))) for item in payload.get("datasets", [])]
        except Exception as exc:
            LOGGER.warning("Failed to load split cache %s; will recompute. Error: %s", cache_file, exc)

    rng = np.random.default_rng(seed)
    global_val = np.sort(rng.choice(total_size, size=effective_val_size, replace=False))

    per_dataset_indices: list[list[int]] = []
    start_offset = 0
    for spec in dataset_specs:
        end_offset = start_offset + int(spec["length"])
        left = int(np.searchsorted(global_val, start_offset, side="left"))
        right = int(np.searchsorted(global_val, end_offset, side="left"))
        local = (global_val[left:right] - start_offset).astype(np.int64).tolist()
        per_dataset_indices.append(local)
        start_offset = end_offset

    if cache_file:
        payload = {
            "version": SPLIT_CACHE_VERSION,
            "seed": int(seed),
            "val_size": int(effective_val_size),
            "total_size": int(total_size),
            "datasets": [
                {
                    **spec,
                    "val_indices": list(map(int, local_indices)),
                }
                for spec, local_indices in zip(dataset_specs, per_dataset_indices)
            ],
        }
        _atomic_torch_save(payload, cache_file)
        LOGGER.info("Saved random val split cache to %s", cache_file)

    return per_dataset_indices


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

    for dataset, i in tqdm(sample_pool, desc="Std", mininterval=_TQDM_MININTERVAL, miniters=_TQDM_MINITERS):
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


def dataset_atom_counts(dataset) -> np.ndarray:
    if hasattr(dataset, "atom_counts"):
        return np.asarray(getattr(dataset, "atom_counts"), dtype=np.int32)
    if isinstance(dataset, torch.utils.data.ConcatDataset):
        parts = [dataset_atom_counts(part) for part in dataset.datasets]
        if not parts:
            return np.zeros(0, dtype=np.int32)
        return np.concatenate(parts, axis=0)
    if isinstance(dataset, Subset):
        base_counts = dataset_atom_counts(dataset.dataset)
        return np.asarray(base_counts[np.asarray(dataset.indices, dtype=np.int64)], dtype=np.int32)
    raise ValueError(f"Dataset {type(dataset).__name__} does not expose atom_counts.")


def fast_collate(data_list):
    """Drop large precomputed angle/torsion tensors before batch merge."""
    collate_start = time.perf_counter()
    renamed = []
    for data in data_list:
        data_keys = _data_key_set(data)
        if "angle_triplet" in data_keys:
            delattr(data, "angle_triplet")
        if "dihed_quad" in data_keys:
            delattr(data, "dihed_quad")
        for source_name, temp_name in COLLATE_RENAME_FIELDS.items():
            if source_name in data_keys:
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
    collate_elapsed = time.perf_counter() - collate_start
    if collate_elapsed >= worker_slow_threshold_s():
        worker_debug_event(
            "slow_collate",
            batch_items=len(data_list),
            elapsed_s=round(float(collate_elapsed), 3),
        )
    return batch
