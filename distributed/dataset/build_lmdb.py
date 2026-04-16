#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build LMDB from optimized xyz files and matched raw xyz files that carry SMILES.

Preferred CLI:
    python build_lmdb.py --raw_roots <raw_dir> --stable_roots <stable_dir>

Backward-compatible CLI:
    python build_lmdb.py --data_roots <dataset_root>
"""

import argparse
import contextlib
import math
import os
import pickle
import signal
import sys
import time
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

import lmdb
import numpy as np
import torch
import tqdm
from torch_geometric.data import Data

if __package__ in (None, ""):
    _REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _REPO_ROOT not in sys.path:
        sys.path.insert(0, _REPO_ROOT)

from dataset.dataset_without_charge import (
    MoleculeDataset,
    extract_dataset_idx,
    extract_sample_key,
    parse_xyz_stable,
    read_smiles_from_input_xyz,
)
from dataset.descriptor_schema import (
    BOND_FAIL_REASON_FIELD,
    BOND_INDEX_FIELD,
    BOND_NEGATIVE_COUNT_FIELD,
    BOND_NEGATIVE_UPPER_IDS_FIELD,
    BOND_ORDER_FIELD,
    BOND_STATUS_FIELD,
    ELEMENT_CORRUPT_MASK_FIELD,
    PRETRAIN_BASE_KEY_FIELD,
    PRETRAIN_RECIPE_LEVEL_FIELD,
    PRETRAIN_RECIPE_NAME_FIELD,
    PRETRAIN_RECIPE_SEED_FIELD,
    SAMPLE_TYPE_ID_FIELD,
    TARGET_POS_FIELD,
    TARGET_X_FIELD,
    canonical_recipe_name,
    recipe_cache_suffix,
)


LEN_KEY = b"__len__"


class SampleBuildTimeoutError(TimeoutError):
    pass


@dataclass
class SkipStats:
    skipped_total: int = 0
    skipped_timeout: int = 0
    skipped_error: int = 0


def platform_supports_sample_timeout() -> bool:
    return os.name != "nt" and hasattr(signal, "SIGALRM") and hasattr(signal, "setitimer")


@contextlib.contextmanager
def sample_timeout(seconds: Optional[float]):
    if seconds is None or seconds <= 0:
        yield
        return
    if not platform_supports_sample_timeout():
        yield
        return

    def _handle_timeout(signum, frame):
        raise SampleBuildTimeoutError(f"sample build exceeded {seconds:.3f}s")

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def log_skipped_sample(
    stable_path: str,
    sample_key: Optional[str],
    exc: Exception,
    skip_log_path: Optional[str],
    skip_stats: Optional[SkipStats],
) -> None:
    sample_label = sample_key or os.path.basename(stable_path)
    category = "timeout" if isinstance(exc, SampleBuildTimeoutError) else "error"
    message = (
        f"[skip:{category}] sample={sample_label} path={stable_path} "
        f"reason={type(exc).__name__}: {exc}"
    )
    print(message, file=sys.stderr, flush=True)
    if skip_log_path:
        with open(skip_log_path, "a", encoding="utf-8") as f:
            f.write(message + "\n")

    if skip_stats is not None:
        skip_stats.skipped_total += 1
        if isinstance(exc, SampleBuildTimeoutError):
            skip_stats.skipped_timeout += 1
        else:
            skip_stats.skipped_error += 1


def print_skip_summary(skip_stats: Optional[SkipStats]) -> None:
    if skip_stats is None:
        return
    print(
        "[skip] total="
        f"{skip_stats.skipped_total} timeout={skip_stats.skipped_timeout} "
        f"error={skip_stats.skipped_error}",
        flush=True,
    )


def maybe_make_rdkit_descriptor_generator(enabled: bool):
    if not enabled:
        return None
    from dataset.rdkit_descriptor_generator import make_rdkit_descriptor_generator

    return make_rdkit_descriptor_generator()


def parse_property_packs(spec: str | Sequence[str] | None) -> tuple[str, ...]:
    if spec is None:
        return ()
    if isinstance(spec, str):
        raw_tokens = [token.strip() for token in spec.split(",")]
    else:
        raw_tokens = [str(token).strip() for token in spec]

    supported = {"rdkit_descriptors", "rdkit_bonds", "bond_negative_pool", "pretrain_recipe"}
    all_default = {"rdkit_descriptors", "rdkit_bonds", "bond_negative_pool"}
    out: list[str] = []
    for token in raw_tokens:
        if not token or token.lower() == "none":
            continue
        if token.lower() == "all":
            for name in sorted(all_default):
                if name not in out:
                    out.append(name)
            continue
        if token not in supported:
            raise ValueError(f"Unsupported property pack: {token}")
        if token not in out:
            out.append(token)
    return tuple(out)


def parse_augment_recipe(spec: str | None) -> tuple[str, float] | None:
    if spec is None:
        return None
    token = str(spec).strip()
    if not token:
        return None
    if ":" not in token:
        raise ValueError("--augment_recipe must look like 'geom:0.2' or 'topo:0.3'.")
    mode, level_str = token.split(":", 1)
    mode = str(mode).strip().lower()
    if mode not in {"geom", "topo", "both"}:
        raise ValueError("--augment_recipe mode must be one of geom/topo/both.")
    return mode, float(level_str)


def validate_augment_ratio(value: float) -> float:
    ratio = float(value)
    if not (0.0 < ratio <= 1.0):
        raise ValueError(f"--augment_ratio must be within (0, 1], got {value}")
    return ratio


def _clone_sample(item):
    return pickle.loads(pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL))


def _remove_attr_if_present(data, attr_name: str) -> None:
    if hasattr(data, attr_name):
        delattr(data, attr_name)


def _local_negative_upper_ids(bond_index: torch.Tensor, num_atoms: int) -> torch.Tensor:
    positive_set: set[tuple[int, int]] = set()
    if isinstance(bond_index, torch.Tensor) and bond_index.numel() > 0:
        index = bond_index.detach().cpu().view(2, -1).long()
        for edge_idx in range(index.size(1)):
            left = int(index[0, edge_idx].item())
            right = int(index[1, edge_idx].item())
            if left == right:
                continue
            if left > right:
                left, right = right, left
            if left < 0 or right >= int(num_atoms):
                continue
            positive_set.add((left, right))

    negative_ids: list[int] = []
    pair_id = 0
    for left in range(max(int(num_atoms) - 1, 0)):
        for right in range(left + 1, int(num_atoms)):
            if (left, right) not in positive_set:
                negative_ids.append(pair_id)
            pair_id += 1
    max_pair_id = max(pair_id - 1, 0)
    if max_pair_id <= torch.iinfo(torch.int16).max:
        dtype = torch.int16
    elif max_pair_id <= torch.iinfo(torch.int32).max:
        dtype = torch.int32
    else:
        dtype = torch.int64
    return torch.tensor(negative_ids, dtype=dtype)


def _ensure_bond_negative_pool(data) -> None:
    if hasattr(data, BOND_NEGATIVE_UPPER_IDS_FIELD) and hasattr(data, BOND_NEGATIVE_COUNT_FIELD):
        return
    bond_index = getattr(data, BOND_INDEX_FIELD, None)
    pos = getattr(data, "pos", None)
    num_atoms = int(pos.size(0)) if isinstance(pos, torch.Tensor) else 0
    negative_ids = _local_negative_upper_ids(
        bond_index if isinstance(bond_index, torch.Tensor) else torch.zeros((2, 0), dtype=torch.long),
        num_atoms,
    )
    setattr(data, BOND_NEGATIVE_UPPER_IDS_FIELD, negative_ids)
    setattr(data, BOND_NEGATIVE_COUNT_FIELD, torch.tensor([int(negative_ids.numel())], dtype=torch.long))


def _make_pretrain_recipe_sample(item, *, mode: str, level: float, sample_seed: int):
    from pretrain.degrade_molecules import DegradeConfig, degrade_once

    clean_x = item.x.clone() if hasattr(item, "x") else None
    clean_pos = item.pos.clone() if hasattr(item, "pos") else None
    cfg = DegradeConfig(mode=mode, level=level).finalize()
    gen = torch.Generator(device="cpu").manual_seed(int(sample_seed))
    data = degrade_once(_clone_sample(item), cfg, gen)

    if clean_x is not None:
        setattr(data, TARGET_X_FIELD, clean_x)
    if clean_pos is not None:
        setattr(data, TARGET_POS_FIELD, clean_pos)

    setattr(data, SAMPLE_TYPE_ID_FIELD, torch.tensor([{"clean": 0, "geom": 1, "topo": 2, "both": 3}[mode]], dtype=torch.long))
    setattr(data, PRETRAIN_RECIPE_NAME_FIELD, canonical_recipe_name(mode, level))
    setattr(data, PRETRAIN_RECIPE_LEVEL_FIELD, float(level))
    setattr(data, PRETRAIN_RECIPE_SEED_FIELD, int(sample_seed))
    setattr(data, PRETRAIN_BASE_KEY_FIELD, str(getattr(item, "sample_key", "")))

    # Derived perturb shards only keep the fields needed during training.
    for attr_name in (
        "energy",
        "energy_unit",
        "y",
        "charge_mask",
        "is_feasible",
        "neg_type",
        "rdkit_schema_version",
        "rdkit_build_mode",
        "rdkit_status",
        "rdkit_fail_reason",
        "rdkit_graph_desc",
        "rdkit_graph_desc_mask",
        "canonical_smiles",
        "isomeric_smiles",
        "canonical_smiles_from_rdkit",
        "registration_hash",
        "match_is_unique",
        "total_charge",
        "rdkit_node_formal_charge",
        "rdkit_node_hybridization",
        "rdkit_node_is_aromatic",
        "rdkit_node_is_in_ring",
        "rdkit_node_min_ring_size",
        "rdkit_node_total_degree",
        "rdkit_node_total_num_Hs",
        "rdkit_node_total_valence",
        "rdkit_node_donor",
        "rdkit_node_acceptor",
        "rdkit_node_estate_type",
        "rdkit_node_estate_index",
        "rdkit_node_chiral_tag",
        "rdkit_node_cip_code",
        "rdkit_node_mask",
    ):
        _remove_attr_if_present(data, attr_name)

    if not hasattr(data, ELEMENT_CORRUPT_MASK_FIELD) and clean_x is not None:
        setattr(data, ELEMENT_CORRUPT_MASK_FIELD, torch.zeros((int(clean_x.size(0)), 1), dtype=torch.bool))

    # Perturbed recipe shards should not carry clean bond supervision targets.
    for attr_name in (
        BOND_INDEX_FIELD,
        BOND_ORDER_FIELD,
        BOND_STATUS_FIELD,
        BOND_FAIL_REASON_FIELD,
        BOND_NEGATIVE_UPPER_IDS_FIELD,
        BOND_NEGATIVE_COUNT_FIELD,
    ):
        _remove_attr_if_present(data, attr_name)
    return data


def lmdb_storage_size_bytes(path: str) -> int:
    if os.path.isdir(path):
        total = 0
        for name in ("data.mdb", "lock.mdb"):
            file_path = os.path.join(path, name)
            if os.path.exists(file_path):
                total += os.path.getsize(file_path)
        return total
    if os.path.exists(path):
        return os.path.getsize(path)
    return 0


def build_stream_item(
    stable_path: str,
    raw_path: str,
    sample_key: str,
    descriptor_generator=None,
):
    item = parse_xyz_stable(stable_path)
    smiles = read_smiles_from_input_xyz(raw_path)
    if not smiles:
        raise ValueError(f"Raw xyz is missing SMILES: {raw_path}")

    item.sample_key = sample_key
    item.smiles = smiles
    if descriptor_generator is not None:
        item = descriptor_generator.annotate(item)
    return item


def env_open(path: str, initial_map_gb: float, lock: bool) -> lmdb.Environment:
    return lmdb.open(
        path,
        map_size=max(int(initial_map_gb * 1024 ** 3), 1 << 20),
        subdir=False,
        lock=lock,
        readahead=False,
        meminit=False,
        max_dbs=1,
    )


def env_len(env: lmdb.Environment) -> int:
    with env.begin(write=False) as txn:
        raw = txn.get(LEN_KEY)
        return pickle.loads(raw) if raw is not None else 0


def set_len(env: lmdb.Environment, n: int) -> None:
    with env.begin(write=True) as txn:
        txn.put(LEN_KEY, pickle.dumps(n, protocol=pickle.HIGHEST_PROTOCOL))


def ensure_mapsize(env: lmdb.Environment, extra_need_bytes: int, growth_gb: float) -> None:
    info = env.info()
    stat = env.stat()
    used_bytes = (int(info["last_pgno"]) + 1) * int(stat["psize"])
    free_bytes = int(info["map_size"]) - used_bytes
    if free_bytes >= extra_need_bytes:
        return

    growth_bytes = max(int(growth_gb * 1024 ** 3), extra_need_bytes, 1 << 20)
    env.set_mapsize(int(info["map_size"]) + growth_bytes)


def compact_mapsize(env: lmdb.Environment, headroom_mb: int) -> None:
    if headroom_mb < 0:
        raise ValueError("headroom_mb must be >= 0")
    if headroom_mb == 0:
        return

    info = env.info()
    stat = env.stat()
    page_size = int(stat["psize"])
    used_bytes = (int(info["last_pgno"]) + 1) * page_size
    target = used_bytes + headroom_mb * 1024 ** 2
    target = max(target, 1 << 20)
    target = ((target + page_size - 1) // page_size) * page_size
    if target < int(info["map_size"]):
        try:
            env.set_mapsize(target)
        except lmdb.Error as exc:
            print(
                f"[warn] failed to compact LMDB map_size to {target} bytes: {exc}",
                flush=True,
            )


def safe_batch_put(
    env: lmdb.Environment,
    items: Sequence[Tuple[bytes, bytes]],
    growth_gb: float,
    total_len: int,
) -> int:
    pending = list(items)
    growth_bytes = max(int(growth_gb * 1024 ** 3), 1 << 20)
    while True:
        try:
            with env.begin(write=True) as txn:
                for key, value in pending:
                    txn.put(key, value)
                txn.put(LEN_KEY, pickle.dumps(total_len, protocol=pickle.HIGHEST_PROTOCOL))
            return len(pending)
        except lmdb.MapFullError:
            env.set_mapsize(int(env.info()["map_size"]) + growth_bytes)


def resolve_data_dirs(
    root: Optional[str],
    raw_root: Optional[str],
    stable_root: Optional[str],
    stable_folder: str,
    raw_folder: str,
) -> Tuple[str, str]:
    if stable_root is not None:
        stable_dir = os.path.abspath(stable_root)
    elif root is not None:
        stable_dir = os.path.join(root, stable_folder)
    else:
        raise ValueError("Missing stable directory. Provide --stable_roots or --data_roots.")

    if raw_root is not None:
        raw_dir = os.path.abspath(raw_root)
    elif root is not None:
        raw_dir = os.path.join(root, raw_folder)
    else:
        raise ValueError("Missing raw directory. Provide --raw_roots or --data_roots.")

    if not os.path.isdir(stable_dir):
        raise FileNotFoundError(f"Stable xyz directory does not exist: {stable_dir}")
    if not os.path.isdir(raw_dir):
        raise FileNotFoundError(f"Raw xyz directory does not exist: {raw_dir}")
    return raw_dir, stable_dir


def iter_stable_paths(stable_dir: str, sort_files: bool) -> Iterator[str]:
    if sort_files:
        names = []
        with os.scandir(stable_dir) as it:
            for entry in it:
                if entry.is_file() and entry.name.endswith(".xyz"):
                    names.append(entry.name)
        for name in sorted(names):
            yield os.path.join(stable_dir, name)
        return

    with os.scandir(stable_dir) as it:
        for entry in it:
            if entry.is_file() and entry.name.endswith(".xyz"):
                yield entry.path


def iter_samples_streaming(
    raw_dir: str,
    stable_dir: str,
    start_idx: Optional[int],
    end_idx: Optional[int],
    sort_files: bool,
    skip_count: int = 0,
    descriptor_generator=None,
    skip_bad_samples: bool = False,
    sample_timeout_sec: Optional[float] = None,
    skip_log_path: Optional[str] = None,
    skip_stats: Optional[SkipStats] = None,
) -> Iterator[object]:
    skipped = 0
    for stable_path in iter_stable_paths(stable_dir, sort_files=sort_files):
        stable_name = os.path.basename(stable_path)
        sample_key = extract_sample_key(stable_name)
        if sample_key is None:
            continue

        mol_idx = extract_dataset_idx(sample_key)
        if start_idx is not None and mol_idx < start_idx:
            continue
        if end_idx is not None and mol_idx > end_idx:
            continue

        if skipped < skip_count:
            skipped += 1
            continue

        raw_path = os.path.join(raw_dir, sample_key + ".xyz")
        try:
            with sample_timeout(sample_timeout_sec):
                if not os.path.exists(raw_path):
                    raise FileNotFoundError(
                        f"Missing raw xyz for sample '{sample_key}': {raw_path}"
                    )
                item = build_stream_item(
                    stable_path=stable_path,
                    raw_path=raw_path,
                    sample_key=sample_key,
                    descriptor_generator=descriptor_generator,
                )
        except Exception as exc:
            if not skip_bad_samples:
                raise
            log_skipped_sample(
                stable_path=stable_path,
                sample_key=sample_key,
                exc=exc,
                skip_log_path=skip_log_path,
                skip_stats=skip_stats,
            )
            continue
        yield item


def write_item_stream(
    items: Iterable[object],
    env: lmdb.Environment,
    start_key_idx: int,
    batch_size: int,
    growth_gb: float,
    progress_desc: str,
) -> int:
    write_idx = start_key_idx
    written = 0
    batch: List[Tuple[bytes, bytes]] = []
    batch_bytes = 0

    for item in tqdm.tqdm(items, desc=progress_desc, unit="mol"):
        key = f"{write_idx:09d}".encode("ascii")
        value = pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL)
        batch.append((key, value))
        batch_bytes += len(key) + len(value) + 128
        write_idx += 1

        if len(batch) >= batch_size:
            ensure_mapsize(env, batch_bytes, growth_gb)
            written += safe_batch_put(env, batch, growth_gb, write_idx)
            batch.clear()
            batch_bytes = 0

    if batch:
        ensure_mapsize(env, batch_bytes, growth_gb)
        written += safe_batch_put(env, batch, growth_gb, write_idx)

    return written


def estimate_avg_payload(ds: MoleculeDataset, probe: int) -> int:
    if probe <= 0 or len(ds) == 0:
        return 4096

    step = max(len(ds) // probe, 1)
    sizes: List[int] = []
    for i in range(0, len(ds), step):
        try:
            item = ds[i]
        except Exception:
            continue
        sizes.append(len(pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL)))
        if len(sizes) >= probe:
            break

    if not sizes:
        return 4096
    return max(int(sum(sizes) / len(sizes)), 1024)


def write_dataset(
    ds: MoleculeDataset,
    env: lmdb.Environment,
    start_key_idx: int,
    start_ds_idx: int,
    batch_size: int,
    growth_gb: float,
    avg_payload_bytes: int,
    descriptor_generator=None,
    sample_timeout_sec: Optional[float] = None,
    skip_log_path: Optional[str] = None,
    skip_stats: Optional[SkipStats] = None,
) -> int:
    write_idx = start_key_idx
    written = 0
    batch: List[Tuple[bytes, bytes]] = []

    for ds_idx in tqdm.tqdm(range(start_ds_idx, len(ds)), desc="write", unit="mol"):
        item = None
        try:
            with sample_timeout(sample_timeout_sec):
                item = ds[ds_idx]
                if descriptor_generator is not None:
                    item = descriptor_generator.annotate(item)
            key = f"{write_idx:09d}".encode("ascii")
            value = pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception as exc:
            stable_path = f"dataset_idx={ds_idx}"
            sample_key = getattr(item, "sample_key", None)
            if hasattr(ds, "samples") and ds_idx < len(ds.samples):
                sample = ds.samples[ds_idx]
                stable_path = sample.get("stable_path", stable_path)
                sample_key = sample_key or sample.get("key")
            log_skipped_sample(
                stable_path=stable_path or f"dataset_idx={ds_idx}",
                sample_key=sample_key,
                exc=exc,
                skip_log_path=skip_log_path,
                skip_stats=skip_stats,
            )
            continue

        batch.append((key, value))
        write_idx += 1

        if len(batch) >= batch_size:
            ensure_mapsize(env, len(batch) * avg_payload_bytes, growth_gb)
            written += safe_batch_put(env, batch, growth_gb, write_idx)
            batch.clear()

    if batch:
        ensure_mapsize(env, len(batch) * avg_payload_bytes, growth_gb)
        written += safe_batch_put(env, batch, growth_gb, write_idx)

    return written


def make_dataset(
    root: Optional[str],
    raw_root: Optional[str],
    stable_root: Optional[str],
    start_idx: Optional[int],
    end_idx: Optional[int],
    stable_folder: str,
    raw_folder: str,
) -> MoleculeDataset:
    return MoleculeDataset(
        root=root,
        raw_root=raw_root,
        stable_root=stable_root,
        stable_folder=stable_folder,
        raw_folder=raw_folder,
        start_idx=start_idx,
        end_idx=end_idx,
        include_smiles=True,
        require_smiles=True,
        include_trajectory=False,
    )


def create_lmdb(
    root: Optional[str],
    raw_root: Optional[str],
    stable_root: Optional[str],
    start_idx: Optional[int],
    end_idx: Optional[int],
    out_path: str,
    map_size_gb: float,
    growth_gb: float,
    batch_size: int,
    probe: int,
    compact_headroom_mb: int,
    lock: bool,
    stable_folder: str,
    raw_folder: str,
    sort_files: bool,
    with_rdkit_descriptors: bool,
    skip_bad_samples: bool,
    sample_timeout_sec: Optional[float],
    skip_log_path: Optional[str],
) -> None:
    raw_dir, stable_dir = resolve_data_dirs(root, raw_root, stable_root, stable_folder, raw_folder)
    print(
        f"[create] raw={raw_dir} stable={stable_dir} -> {out_path} "
        f"(streaming, batch={batch_size}, sort_files={sort_files}, "
        f"rdkit_descriptors={with_rdkit_descriptors}, skip_bad_samples={skip_bad_samples}, "
        f"sample_timeout_sec={sample_timeout_sec})",
        flush=True,
    )
    if sample_timeout_sec and not platform_supports_sample_timeout():
        print(
            "[warn] sample timeout is only supported on POSIX platforms with SIGALRM; "
            "ignoring --sample_timeout_sec on this platform.",
            flush=True,
        )
    descriptor_generator = maybe_make_rdkit_descriptor_generator(with_rdkit_descriptors)
    skip_stats = SkipStats() if skip_bad_samples or skip_log_path or sample_timeout_sec else None
    env = env_open(out_path, map_size_gb, lock=lock)
    try:
        set_len(env, 0)
        item_iter = iter_samples_streaming(
            raw_dir=raw_dir,
            stable_dir=stable_dir,
            start_idx=start_idx,
            end_idx=end_idx,
            sort_files=sort_files,
            skip_count=0,
            descriptor_generator=descriptor_generator,
            skip_bad_samples=skip_bad_samples,
            sample_timeout_sec=sample_timeout_sec,
            skip_log_path=skip_log_path,
            skip_stats=skip_stats,
        )
        written = write_item_stream(
            items=item_iter,
            env=env,
            start_key_idx=0,
            batch_size=batch_size,
            growth_gb=growth_gb,
            progress_desc="write",
        )
        compact_mapsize(env, compact_headroom_mb)
        total = env_len(env)
    finally:
        env.sync()
        env.close()
    print(f"created {out_path} with {written} samples, total={total}", flush=True)
    print_skip_summary(skip_stats)
    if descriptor_generator is not None:
        for line in descriptor_generator.summary_lines():
            print(line, flush=True)


def update_lmdb(
    root: Optional[str],
    raw_root: Optional[str],
    stable_root: Optional[str],
    start_idx: Optional[int],
    end_idx: Optional[int],
    out_path: str,
    map_size_gb: float,
    growth_gb: float,
    batch_size: int,
    probe: int,
    compact_headroom_mb: int,
    lock: bool,
    stable_folder: str,
    raw_folder: str,
    sort_files: bool,
    with_rdkit_descriptors: bool,
    sample_timeout_sec: Optional[float],
    skip_log_path: Optional[str],
) -> None:
    raw_dir, stable_dir = resolve_data_dirs(root, raw_root, stable_root, stable_folder, raw_folder)
    if not sort_files:
        print("[update] forcing sort_files=True to keep append order stable", flush=True)
        sort_files = True

    print(
        f"[update] raw={raw_dir} stable={stable_dir} -> {out_path} "
        f"(batch={batch_size}, sort_files={sort_files}, "
        f"rdkit_descriptors={with_rdkit_descriptors}, sample_timeout_sec={sample_timeout_sec})",
        flush=True,
    )
    if sample_timeout_sec and not platform_supports_sample_timeout():
        print(
            "[warn] sample timeout is only supported on POSIX platforms with SIGALRM; "
            "ignoring --sample_timeout_sec on this platform.",
            flush=True,
        )
    descriptor_generator = maybe_make_rdkit_descriptor_generator(with_rdkit_descriptors)
    skip_stats = SkipStats() if skip_log_path or sample_timeout_sec else None
    env = env_open(out_path, map_size_gb, lock=lock)
    try:
        current = env_len(env)

        # Keep the legacy update path for predictable append semantics.
        ds = make_dataset(root, raw_root, stable_root, start_idx, end_idx, stable_folder, raw_folder)
        avg_payload = estimate_avg_payload(ds, probe=probe)
        written = write_dataset(
            ds,
            env,
            start_key_idx=current,
            start_ds_idx=current,
            batch_size=batch_size,
            growth_gb=growth_gb,
            avg_payload_bytes=avg_payload,
            descriptor_generator=descriptor_generator,
            sample_timeout_sec=sample_timeout_sec,
            skip_log_path=skip_log_path,
            skip_stats=skip_stats,
        )

        compact_mapsize(env, compact_headroom_mb)
        total = env_len(env)
    finally:
        env.sync()
        env.close()
    print(f"updated {out_path} with {written} new samples, total={total}", flush=True)
    print_skip_summary(skip_stats)
    if descriptor_generator is not None:
        for line in descriptor_generator.summary_lines():
            print(line, flush=True)


def augment_lmdb(
    in_path: str | Sequence[str],
    out_path: str,
    *,
    property_packs: Sequence[str],
    augment_recipe: tuple[str, float] | None,
    augment_recipe_seed: int,
    augment_ratio: float,
    augment_ratio_seed: int,
    map_size_gb: float,
    growth_gb: float,
    batch_size: int,
    compact_headroom_mb: int,
    lock: bool,
    probe: int,
) -> None:
    from dataset.dataset_lmdb import LmdbMoleculeDataset
    from dataset.rdkit_descriptor_generator import detect_property_packs, make_rdkit_descriptor_generator

    if isinstance(in_path, str):
        in_paths = [os.path.abspath(in_path)]
    else:
        in_paths = [os.path.abspath(path) for path in in_path]
    out_path = os.path.abspath(out_path)
    if any(path == out_path for path in in_paths):
        raise ValueError("augment mode requires out_path different from every source LMDB path.")

    packs = parse_property_packs(property_packs)
    if augment_recipe is not None and "pretrain_recipe" not in packs:
        packs = tuple(list(packs) + ["pretrain_recipe"])
    if not packs:
        raise ValueError("augment mode requires at least one property pack.")
    if "pretrain_recipe" in packs and augment_recipe is None:
        raise ValueError("augmenting pretrain_recipe requires --augment_recipe.")

    requested_recipe_name = None
    recipe_mode = None
    recipe_level = None
    if augment_recipe is not None:
        recipe_mode, recipe_level = augment_recipe
        requested_recipe_name = canonical_recipe_name(recipe_mode, recipe_level)

    print(
        f"[augment] source_count={len(in_paths)} -> {out_path} "
        f"(packs={','.join(packs)}, batch={batch_size}, "
        f"recipe={requested_recipe_name or '<none>'}, recipe_seed={int(augment_recipe_seed)}, "
        f"augment_ratio={float(augment_ratio):.6f}, augment_ratio_seed={int(augment_ratio_seed)})",
        flush=True,
    )

    datasets = [LmdbMoleculeDataset(path, filter_missing_on_init=True, normalize_samples=False) for path in in_paths]
    lengths = [len(ds) for ds in datasets]
    total_input = int(sum(lengths))
    if total_input <= 0:
        raise RuntimeError(f"augment sources are empty: {in_paths}")

    ratio = validate_augment_ratio(augment_ratio)
    target_count = total_input if ratio >= 1.0 else max(1, int(total_input * ratio))
    target_count = min(target_count, total_input)

    if target_count >= total_input:
        selected_global = np.arange(total_input, dtype=np.int64)
    else:
        rng = np.random.default_rng(int(augment_ratio_seed))
        selected_global = np.sort(rng.choice(total_input, size=target_count, replace=False).astype(np.int64))

    selected_by_source: list[np.ndarray] = []
    selected_counts_by_source: list[int] = []
    offset = 0
    for length in lengths:
        left = int(np.searchsorted(selected_global, offset, side="left"))
        right = int(np.searchsorted(selected_global, offset + int(length), side="left"))
        local = selected_global[left:right] - offset
        local = np.asarray(local, dtype=np.int64)
        selected_by_source.append(local)
        selected_counts_by_source.append(int(local.shape[0]))
        offset += int(length)

    generator = make_rdkit_descriptor_generator()
    env = env_open(out_path, map_size_gb, lock=lock)
    set_len(env, 0)

    payload_probe_before: list[int] = []
    payload_probe_after: list[int] = []
    detected_before = Counter()
    added_counter = Counter()
    sample_probe_limit = max(int(probe), 1)

    started = time.perf_counter()
    batch: list[tuple[bytes, bytes]] = []
    batch_bytes = 0
    written = 0

    try:
        progress = tqdm.tqdm(total=target_count, desc="augment", unit="mol")
        global_selected_rank = 0
        for source_idx, (ds, local_indices) in enumerate(zip(datasets, selected_by_source)):
            for idx in local_indices.tolist():
                item = ds[int(idx)]
                if len(payload_probe_before) < sample_probe_limit:
                    payload_probe_before.append(len(pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL)))

                for pack_name in detect_property_packs(item):
                    detected_before[pack_name] += 1

                rdkit_packs = tuple(pack_name for pack_name in packs if pack_name in {"rdkit_descriptors", "rdkit_bonds"})
                if rdkit_packs:
                    item, added = generator.augment_missing(item, rdkit_packs)
                    for pack_name in added:
                        added_counter[pack_name] += 1

                if "bond_negative_pool" in packs:
                    item, added = generator.augment_missing(item, ("rdkit_bonds",))
                    for pack_name in added:
                        added_counter[pack_name] += 1

                if "bond_negative_pool" in packs:
                    before_has_pool = hasattr(item, BOND_NEGATIVE_UPPER_IDS_FIELD) and hasattr(item, BOND_NEGATIVE_COUNT_FIELD)
                    _ensure_bond_negative_pool(item)
                    if not before_has_pool:
                        added_counter["bond_negative_pool"] += 1

                if "pretrain_recipe" in packs:
                    current_recipe_name = str(getattr(item, PRETRAIN_RECIPE_NAME_FIELD, "") or "")
                    if current_recipe_name != requested_recipe_name:
                        recipe_sample_seed = int(augment_recipe_seed) + int(global_selected_rank)
                        item = _make_pretrain_recipe_sample(
                            item,
                            mode=str(recipe_mode),
                            level=float(recipe_level),
                            sample_seed=recipe_sample_seed,
                        )
                        added_counter["pretrain_recipe"] += 1

                value = pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL)
                if len(payload_probe_after) < sample_probe_limit:
                    payload_probe_after.append(len(value))

                key = f"{written:09d}".encode("ascii")
                batch.append((key, value))
                batch_bytes += len(key) + len(value) + 128
                written += 1
                global_selected_rank += 1
                progress.update(1)

                if len(batch) >= batch_size:
                    ensure_mapsize(env, batch_bytes, growth_gb)
                    safe_batch_put(env, batch, growth_gb, written)
                    batch.clear()
                    batch_bytes = 0

            if int(local_indices.shape[0]) > 0:
                print(
                    f"[augment] source[{source_idx}] path={in_paths[source_idx]} "
                    f"selected={int(local_indices.shape[0])}/{lengths[source_idx]}",
                    flush=True,
                )

        if batch:
            ensure_mapsize(env, batch_bytes, growth_gb)
            safe_batch_put(env, batch, growth_gb, written)

        compact_mapsize(env, compact_headroom_mb)
    finally:
        if "progress" in locals():
            progress.close()
        env.sync()
        env.close()

    elapsed = max(time.perf_counter() - started, 1e-9)
    input_bytes = sum(lmdb_storage_size_bytes(path) for path in in_paths)
    output_bytes = lmdb_storage_size_bytes(out_path)
    avg_before = (sum(payload_probe_before) / len(payload_probe_before)) if payload_probe_before else 0.0
    avg_after = (sum(payload_probe_after) / len(payload_probe_after)) if payload_probe_after else 0.0
    avg_delta = avg_after - avg_before

    print(
        f"[augment] written={written} elapsed_s={elapsed:.3f} "
        f"samples_per_s={written / elapsed:.3f} target_count={target_count} total_input={total_input}",
        flush=True,
    )
    print(
        f"[augment] input_bytes={input_bytes} output_bytes={output_bytes} "
        f"delta_bytes={output_bytes - input_bytes} delta_per_sample={((output_bytes - input_bytes) / max(written, 1)):.3f}",
        flush=True,
    )
    print(
        f"[augment] payload_probe_avg_before={avg_before:.3f} "
        f"payload_probe_avg_after={avg_after:.3f} payload_probe_delta={avg_delta:.3f}",
        flush=True,
    )
    print(
        f"[augment] detected_before={dict(sorted(detected_before.items()))} "
        f"added={dict(sorted(added_counter.items()))}",
        flush=True,
    )
    for line in generator.summary_lines():
        print(line, flush=True)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--lmdb_paths",
        nargs="+",
        default=None,
        help="existing LMDB paths for --mode augment",
    )
    ap.add_argument(
        "--raw_roots",
        nargs="+",
        default=None,
        help="one or more raw xyz directories that contain SMILES",
    )
    ap.add_argument(
        "--stable_roots",
        nargs="+",
        default=None,
        help="one or more optimized xyz directories",
    )
    ap.add_argument(
        "--data_roots",
        nargs="+",
        default=None,
        help="backward-compatible dataset roots that contain both raw and optimized subfolders",
    )
    ap.add_argument(
        "--starts",
        nargs="*",
        type=int,
        default=[],
        help="start dataset indices aligned with the chosen roots",
    )
    ap.add_argument(
        "--ends",
        nargs="*",
        type=int,
        default=[],
        help="end dataset indices aligned with the chosen roots",
    )
    ap.add_argument(
        "--out_suffix",
        default="lmdb",
        help="output file suffix for auto-generated output paths",
    )
    ap.add_argument(
        "--out_path",
        type=str,
        default=None,
        help="explicit output path, only valid for a single root pair",
    )
    ap.add_argument("--mode", choices=["auto", "create", "update", "augment"], default="auto")
    ap.add_argument("--map_size", type=float, default=4.0, help="initial LMDB map size in GiB")
    ap.add_argument("--growth_gb", type=float, default=1.0, help="map growth step in GiB")
    ap.add_argument("--batch_size", type=int, default=512, help="samples per write transaction")
    ap.add_argument(
        "--probe",
        type=int,
        default=16,
        help="sample count used to estimate payload size for update mode",
    )
    ap.add_argument("--lock", action="store_true", help="enable LMDB file locking")
    ap.add_argument(
        "--compact_headroom_mb",
        type=int,
        default=256,
        help="final LMDB map_size will be shrunk to used_size + this headroom",
    )
    ap.add_argument(
        "--stable_folder",
        type=str,
        default="train_result_geometric_optimization",
        help="optimized xyz subfolder name for legacy --data_roots mode",
    )
    ap.add_argument(
        "--raw_folder",
        type=str,
        default="train_data",
        help="raw xyz subfolder name for legacy --data_roots mode",
    )
    ap.add_argument(
        "--sort_files",
        action="store_true",
        help="sort stable filenames before processing; slower startup but deterministic order",
    )
    ap.add_argument(
        "--with_rdkit_descriptors",
        action="store_true",
        help="optionally generate RDKit graph/node descriptors during LMDB construction",
    )
    ap.add_argument(
        "--skip_bad_samples",
        action="store_true",
        help="skip malformed or unreadable samples during create mode instead of aborting",
    )
    ap.add_argument(
        "--sample_timeout_sec",
        type=float,
        default=None,
        help="optional per-sample timeout in seconds; on Linux this skips hung samples",
    )
    ap.add_argument(
        "--skip_log_path",
        type=str,
        default=None,
        help="optional path to append skipped-sample diagnostics",
    )
    ap.add_argument(
        "--augment_properties",
        type=str,
        default="rdkit_bonds",
        help='comma-separated property packs to add in augment mode, e.g. "rdkit_bonds", "bond_negative_pool", or "all"',
    )
    ap.add_argument(
        "--augment_recipe",
        type=str,
        default=None,
        help="optional perturb recipe for augment mode, e.g. 'geom:0.2', 'topo:0.3', or 'both:0.1'",
    )
    ap.add_argument(
        "--augment_recipe_seed",
        type=int,
        default=114,
        help="base seed used to materialize pretrain_recipe samples in augment mode",
    )
    ap.add_argument(
        "--augment_ratio",
        type=float,
        default=1.0,
        help="optional sampling ratio in augment mode; samples are selected over the union of all input LMDBs",
    )
    ap.add_argument(
        "--augment_ratio_seed",
        type=int,
        default=0,
        help="random seed used to choose the sampled subset for --augment_ratio",
    )
    return ap.parse_args()


def fill_optional(values: Sequence[Optional[int]], n: int) -> List[Optional[int]]:
    return list(values) + [None] * (n - len(values))


def resolve_jobs(args: argparse.Namespace) -> List[Tuple[Optional[str], Optional[str], Optional[str], str]]:
    if args.raw_roots or args.stable_roots:
        if args.data_roots:
            raise ValueError("Use either --data_roots or --raw_roots/--stable_roots, not both.")
        if not args.raw_roots or not args.stable_roots:
            raise ValueError("--raw_roots and --stable_roots must be provided together.")
        if len(args.raw_roots) != len(args.stable_roots):
            raise ValueError("--raw_roots and --stable_roots must have the same length.")

        jobs = []
        for raw_root, stable_root in zip(args.raw_roots, args.stable_roots):
            raw_abs = os.path.abspath(raw_root)
            stable_abs = os.path.abspath(stable_root)
            out_base = stable_abs
            jobs.append((None, raw_abs, stable_abs, out_base))
        return jobs

    if not args.data_roots:
        raise ValueError("Provide either --data_roots or paired --raw_roots/--stable_roots.")

    jobs = []
    for root in args.data_roots:
        root_abs = os.path.abspath(root)
        jobs.append((root_abs, None, None, root_abs))
    return jobs


def resolve_augment_jobs(args: argparse.Namespace) -> list[str]:
    if not args.lmdb_paths:
        raise ValueError("--mode augment requires --lmdb_paths.")
    return [os.path.abspath(path) for path in args.lmdb_paths]


def main() -> None:
    args = parse_args()
    if args.mode == "augment":
        jobs = resolve_augment_jobs(args)
        augment_recipe = parse_augment_recipe(args.augment_recipe)
        augment_ratio = validate_augment_ratio(args.augment_ratio)

        for in_path in jobs:
            if not os.path.exists(in_path):
                raise FileNotFoundError(f"augment source does not exist: {in_path}")

        if not args.out_path and augment_ratio >= 1.0:
            for in_path in jobs:
                root, ext = os.path.splitext(in_path)
                if augment_recipe is not None:
                    mode, level = augment_recipe
                    default_out = f"{root}.{recipe_cache_suffix(mode, level)}{ext or '.lmdb'}"
                else:
                    default_out = f"{root}.augmented{ext or '.lmdb'}"
                out_path = default_out
                if os.path.exists(out_path):
                    raise FileExistsError(f"{out_path} already exists; choose a new --out_path.")
                augment_lmdb(
                    in_path,
                    out_path,
                    property_packs=parse_property_packs(args.augment_properties),
                    augment_recipe=augment_recipe,
                    augment_recipe_seed=args.augment_recipe_seed,
                    augment_ratio=augment_ratio,
                    augment_ratio_seed=args.augment_ratio_seed,
                    map_size_gb=args.map_size,
                    growth_gb=args.growth_gb,
                    batch_size=args.batch_size,
                    compact_headroom_mb=args.compact_headroom_mb,
                    lock=args.lock,
                    probe=args.probe,
                )
            return

        if not args.out_path:
            raise ValueError("global subset sampling with --augment_ratio < 1 over one or more LMDBs requires --out_path.")
        out_path = os.path.abspath(args.out_path)
        if os.path.exists(out_path):
            raise FileExistsError(f"{out_path} already exists; choose a new --out_path.")
        augment_lmdb(
            jobs,
            out_path,
            property_packs=parse_property_packs(args.augment_properties),
            augment_recipe=augment_recipe,
            augment_recipe_seed=args.augment_recipe_seed,
            augment_ratio=augment_ratio,
            augment_ratio_seed=args.augment_ratio_seed,
            map_size_gb=args.map_size,
            growth_gb=args.growth_gb,
            batch_size=args.batch_size,
            compact_headroom_mb=args.compact_headroom_mb,
            lock=args.lock,
            probe=args.probe,
        )
        return

    jobs = resolve_jobs(args)
    if len(jobs) > 1 and args.out_path:
        raise ValueError("--out_path is only valid for a single root pair.")

    starts = fill_optional(args.starts, len(jobs))
    ends = fill_optional(args.ends, len(jobs))

    for (root, raw_root, stable_root, out_base), start_idx, end_idx in zip(jobs, starts, ends):
        out_path = args.out_path or f"{out_base.rstrip(os.sep)}.{args.out_suffix}"
        exists = os.path.exists(out_path)

        if args.mode == "create" or (args.mode == "auto" and not exists):
            if exists:
                raise FileExistsError(f"{out_path} already exists; use --mode update instead.")
            create_lmdb(
                root,
                raw_root,
                stable_root,
                start_idx,
                end_idx,
                out_path,
                args.map_size,
                args.growth_gb,
                args.batch_size,
                args.probe,
                args.compact_headroom_mb,
                args.lock,
                args.stable_folder,
                args.raw_folder,
                args.sort_files,
                args.with_rdkit_descriptors,
                args.skip_bad_samples,
                args.sample_timeout_sec,
                args.skip_log_path,
            )
        else:
            if not exists:
                raise FileNotFoundError(f"{out_path} does not exist; use --mode create instead.")
            update_lmdb(
                root,
                raw_root,
                stable_root,
                start_idx,
                end_idx,
                out_path,
                args.map_size,
                args.growth_gb,
                args.batch_size,
                args.probe,
                args.compact_headroom_mb,
                args.lock,
                args.stable_folder,
                args.raw_folder,
                args.sort_files,
                args.with_rdkit_descriptors,
                args.sample_timeout_sec,
                args.skip_log_path,
            )


if __name__ == "__main__":
    main()
