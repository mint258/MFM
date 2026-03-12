#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_lmdb_streaming.py — 边读边写（Streaming）构建 LMDB，快速启动版
-------------------------------------------------------------------
改进点：
1) 边读取样本边写 LMDB：不用预先遍历/统计全部数据，启动更快；
2) 分批事务提交（默认每 1000 条）避免巨事务卡顿；
3) map_size 小起步 + 自动扩容（捕获 MapFullError）；
4) 修正 start_idx 用法：只作为 key 偏移，不偏移数据集索引；
5) 关闭 env 前完成统计，避免 close 后访问；
6) 可选“无长度探测”(--no_len_probe)：不调用 len(ds)，顺序索引直到越界，进一步减少启动等待；
7) 可选“轻量预估”(--probe N)：抽样 N 条估计平均体积，合理设置初始 map_size，减少扩容次数。

注：
- 默认仍按你项目中的 MoleculeDataset 读取样本，保持下游兼容：value = pickle.dumps(item)。
- 若在本地 SSD 构建，可把 lock=True 以提升安全性；在 NFS/Lustre 上建议 lock=False。

用法：
    # 自动判断 create/update；初始 4GB；每批 1000；无长度探测（立即开始）
    python build_lmdb_streaming.py --data_root /data/qm9 --mode auto --no_len_probe

    # 指定初始 8GB，扩容步长 2GB，每批 2000，抽样 200 条估计体积
    python build_lmdb_streaming.py --data_root /data/qm9 --map_size 8 --growth_gb 2 --batch_size 2000 --probe 200
"""
import os
import argparse
import pickle
from typing import Optional, Tuple
from pathlib import Path

import lmdb

# === 请按你项目实际路径导入 ===
try:
    from dataset_without_charge import MoleculeDataset
except Exception:
    try:
        from dataset import MoleculeDataset  # 备选名
    except Exception as e:
        raise ImportError("无法导入 MoleculeDataset。请检查数据集模块路径。") from e


def human(n_bytes: int) -> str:
    units = ['B','KB','MB','GB','TB']
    x = float(n_bytes)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.1f}{u}"
        x /= 1024.0
    return f"{x:.1f}B"


def env_open(path: str, initial_map_gb: int, lock: bool) -> lmdb.Environment:
    return lmdb.open(
        path,
        map_size=int(initial_map_gb * 1e9),
        subdir=False,
        lock=lock,          # 本地盘 True；网络盘 False
        readahead=False,    # 网络盘更友好
        meminit=False,
        max_dbs=1
    )


def env_len(env: lmdb.Environment) -> int:
    with env.begin(write=False) as rtxn:
        raw = rtxn.get(b'__len__')
        return pickle.loads(raw) if raw is not None else 0


def set_len(env: lmdb.Environment, n: int) -> None:
    with env.begin(write=True) as wtxn:
        wtxn.put(b'__len__', pickle.dumps(n))


def ensure_mapsize(env: lmdb.Environment, extra_need_bytes: int, growth_gb: int) -> None:
    """若剩余空间不足，扩容 map_size。"""
    info = env.info()
    stat = env.stat()
    used_bytes = stat['psize'] * info['last_pgno']
    free_bytes = info['map_size'] - used_bytes
    if free_bytes < extra_need_bytes:
        new_size = info['map_size'] + int(growth_gb * 1e9)
        env.set_mapsize(new_size)


def safe_batch_put(env: lmdb.Environment, keys_vals, growth_gb: int) -> int:
    """写入一批 (k, v)；若遇 MapFull 自动扩容并重试。返回成功数。"""
    pending = list(keys_vals)
    n_ok = 0
    while pending:
        try:
            with env.begin(write=True) as txn:
                for k, v in pending:
                    txn.put(k, v)
            n_ok += len(pending)
            pending.clear()
        except lmdb.MapFullError:
            curr = env.info()['map_size']
            env.set_mapsize(curr + int(growth_gb * 1e9))
    return n_ok


def probe_avg_size(ds, n: int, start_idx: Optional[int], end_idx: Optional[int]) -> int:
    """抽样 n 条，估计平均序列化体积（bytes）。"""
    if n <= 0:
        return 2048  # 兜底 2KB
    # 尽量采样均匀
    try:
        total = len(ds)
        if end_idx is not None:
            total = min(total, end_idx)
        if start_idx is not None:
            total = max(0, total - start_idx)
    except Exception:
        # 无法获取长度，则从 0 往后取 n 条
        total = n
    step = max(1, total // n)
    picked = 0
    sizes = []
    i = start_idx or 0
    while picked < n:
        try:
            item = ds[i]
        except Exception:
            break
        sizes.append(len(pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL)))
        picked += 1
        i += step
    if not sizes:
        return 2048
    return max(256, int(sum(sizes) / len(sizes)))  # 至少 256B


def iter_dataset_streaming(ds, begin: int = 0, end: Optional[int] = None):
    """不依赖 len(ds) 的顺序访问：从 begin 起依次 __getitem__，直到越界或达 end。"""
    i = begin
    while True:
        if end is not None and i >= end:
            break
        try:
            item = ds[i]
        except Exception:
            break
        yield i, item
        i += 1


def write_streaming(ds,
                    env: lmdb.Environment,
                    key_start_idx: int,
                    batch_size: int,
                    growth_gb: int,
                    begin: int = 0,
                    end: Optional[int] = None,
                    avg_bytes_hint: int = 2048) -> int:
    """
    边读边写：每批 size 条写一次事务。
    仅 key 偏移用 key_start_idx，不偏移 ds 访问索引。
    返回新增写入条目数。
    """
    write_idx = key_start_idx
    n_written_total = 0

    buf_kv = []  # 当前批次缓冲
    def flush():
        nonlocal buf_kv, n_written_total
        if not buf_kv:
            return
        # 估算需求并确保 map 空间
        need_bytes = len(buf_kv) * avg_bytes_hint
        ensure_mapsize(env, need_bytes, growth_gb)
        n_ok = safe_batch_put(env, buf_kv, growth_gb)
        n_written_total += n_ok
        buf_kv.clear()
        # 更新 __len__
        set_len(env, write_idx - key_start_idx)

    for _, item in iter_dataset_streaming(ds, begin, end):
        try:
            key = f"{write_idx:08d}".encode("ascii")
            val = pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL)
        except Exception:
            # 坏样本跳过
            continue
        write_idx += 1
        buf_kv.append((key, val))
        if len(buf_kv) >= batch_size:
            flush()

    # 尾批
    flush()
    return n_written_total


def create_lmdb(data_root: str,
                s: Optional[int],
                e: Optional[int],
                out_path: str,
                map_size_gb: int,
                growth_gb: int,
                batch_size: int,
                no_len_probe: bool,
                probe_n: int,
                lock: bool) -> None:
    ds = MoleculeDataset(data_root, start_idx=s, end_idx=e)
    env = env_open(out_path, map_size_gb, lock=lock)

    try:
        # 初始化长度元数据
        set_len(env, 0)

        # 估算平均体积（可选）
        avg_bytes = 2048
        if probe_n > 0:
            try:
                avg_bytes = probe_avg_size(ds, probe_n, s, e)
            except Exception:
                avg_bytes = 2048

        # 选择访问范围
        if no_len_probe:
            begin = s or 0
            end   = e
        else:
            # 使用 len(ds) 但不会预读全部；只是为了确定索引范围
            try:
                total = len(ds)
                begin = s or 0
                end   = e if e is not None else total
            except Exception:
                begin = s or 0
                end   = e

        n_new = write_streaming(ds, env, key_start_idx=0, batch_size=batch_size,
                                growth_gb=growth_gb, begin=begin, end=end,
                                avg_bytes_hint=avg_bytes)
    finally:
        total_len = env_len(env)
        env.sync()
        env.close()

    print(f"✓ 生成 {out_path}  (新增 {n_new} 条，总计 {total_len} 条)")


def update_lmdb(data_root: str,
                s: Optional[int],
                e: Optional[int],
                out_path: str,
                map_size_gb: int,
                growth_gb: int,
                batch_size: int,
                no_len_probe: bool,
                probe_n: int,
                lock: bool) -> None:
    ds = MoleculeDataset(data_root, start_idx=s, end_idx=e)
    env = env_open(out_path, map_size_gb, lock=lock)

    try:
        curr = env_len(env)

        avg_bytes = 2048
        if probe_n > 0:
            try:
                avg_bytes = probe_avg_size(ds, probe_n, s, e)
            except Exception:
                avg_bytes = 2048

        if no_len_probe:
            begin = s or 0
            end   = e
        else:
            try:
                total = len(ds)
                begin = s or 0
                end   = e if e is not None else total
            except Exception:
                begin = s or 0
                end   = e

        n_new = write_streaming(ds, env, key_start_idx=curr, batch_size=batch_size,
                                growth_gb=growth_gb, begin=begin, end=end,
                                avg_bytes_hint=avg_bytes)
    finally:
        total_len = env_len(env)
        env.sync()
        env.close()

    print(f"✓ 追加完成：新增 {n_new} 条，总计 {total_len} 条")


def parse_args():
    p = argparse.ArgumentParser(description="Streaming 边读边写构建 LMDB（快速启动）")
    p.add_argument('--data_root', type=str, required=True, help='数据根目录（传给 MoleculeDataset）')
    p.add_argument('--mode', type=str, default='auto', choices=['create','update','auto'],
                   help='create: 新建；update: 追加；auto: 根据是否存在自动选择')
    p.add_argument('--out_path', type=str, default=None, help='输出 lmdb 路径（默认：<data_root>.lmdb）')
    p.add_argument('--map_size', type=int, default=4, help='初始映射大小，GB（默认 4）')
    p.add_argument('--growth_gb', type=int, default=2, help='空间不足时扩容步长，GB（默认 2）')
    p.add_argument('--batch_size', type=int, default=1000, help='每批提交条数（默认 1000）')
    p.add_argument('--starts', type=int, default=None, help='传给 MoleculeDataset 的 start_idx（可选）')
    p.add_argument('--ends', type=int, default=None, help='传给 MoleculeDataset 的 end_idx（可选）')
    p.add_argument('--no_len_probe', action='store_true',
                   help='不调用 len(ds)，直接顺序 __getitem__ 直到越界（立即开始）')
    p.add_argument('--probe', type=int, default=0,
                   help='抽样 N 条估算平均体积（bytes），用于更合理的空间预估（默认 0=禁用）')
    p.add_argument('--lock', action='store_true',
                   help='打开 LMDB 文件锁（本地 SSD 建议开；网络盘建议关）')
    return p.parse_args()


def main():
    args = parse_args()
    root = os.path.abspath(args.data_root)
    out_path = args.out_path or (root.rstrip(os.sep) + '.lmdb')
    exists = os.path.exists(out_path)

    banner = f"(init {args.map_size}GB, growth {args.growth_gb}GB, batch {args.batch_size}," \
             f" {'no-len-probe' if args.no_len_probe else 'len-probe'}, probe={args.probe})"

    if args.mode == 'create' or (args.mode == 'auto' and not exists):
        print(f"[create] {root} -> {out_path} {banner}")
        create_lmdb(root, args.starts, args.ends, out_path,
                    args.map_size, args.growth_gb, args.batch_size,
                    args.no_len_probe, args.probe, args.lock)
    else:
        print(f"[update] {root} -> {out_path} {banner}")
        update_lmdb(root, args.starts, args.ends, out_path,
                    args.map_size, args.growth_gb, args.batch_size,
                    args.no_len_probe, args.probe, args.lock)


if __name__ == '__main__':
    main()
