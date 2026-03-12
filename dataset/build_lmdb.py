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
import os
import pickle
import signal
import sys
from dataclasses import dataclass
from typing import Iterable, Iterator, List, Optional, Sequence, Tuple

import lmdb
import tqdm

from dataset.dataset_without_charge import (
    MoleculeDataset,
    extract_dataset_idx,
    extract_sample_key,
    parse_xyz_stable,
    read_smiles_from_input_xyz,
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
        env.set_mapsize(target)


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


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
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
    ap.add_argument("--mode", choices=["auto", "create", "update"], default="auto")
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


def main() -> None:
    args = parse_args()
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
