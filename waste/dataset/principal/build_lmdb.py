#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_lmdb_fast.py — 快速启动、稳健扩容版
---------------------------------------
特性：
- 小 map_size 起步 + 自动按需扩容（捕获 MapFullError 并 set_mapsize 增长）
- 分批事务提交（默认每 1000 条提交一次）
- 正确处理 start_idx：仅用于 key 偏移，不偏移数据集访问
- 关闭 env 前读取/缓存统计，避免 close 后访问
- 在网络盘友好配置（readahead=False, meminit=False, lock=False；本地盘可改 True）

用法示例：
    # 自动判断 create/update
    python build_lmdb_fast.py --data_roots /data/qm9 --mode auto

    # 指定初始映射大小 8GB，增长步长 2GB，每批 2000 条
    python build_lmdb_fast.py --data_roots /data/qm9 --map_size 8 --growth_gb 2 --batch_size 2000
"""
import os
import sys
import argparse
import pickle
import lmdb
from pathlib import Path
from typing import Iterable, Tuple, Optional

# === 你项目内的数据集导入（保持与原脚本一致）===
# 如需调整请在此处修改为你的数据集实现
try:
    from dataset_without_charge import MoleculeDataset
except Exception:
    # 兼容另一个名字
    try:
        from dataset import MoleculeDataset  # type: ignore
    except Exception as e:
        raise ImportError("无法导入 MoleculeDataset。请确认数据集模块路径。") from e

# ------------------------- 工具函数 ------------------------- #

def human(n_bytes: int) -> str:
    units = ['B','KB','MB','GB','TB']
    x = float(n_bytes)
    for u in units:
        if x < 1024 or u == units[-1]:
            return f"{x:.1f}{u}"
        x /= 1024.0
    return f"{x:.1f}B"

def env_open(path: str, initial_map_gb: int) -> lmdb.Environment:
    return lmdb.open(
        path,
        map_size=int(initial_map_gb * 1e9),
        subdir=False,
        lock=False,         # 本地盘可改 True
        readahead=False,    # 网络盘友好
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
    """如果剩余空间不足，扩容 map_size。"""
    info = env.info()
    stat = env.stat()
    used_bytes = stat['psize'] * info['last_pgno']
    free_bytes = info['map_size'] - used_bytes
    if free_bytes < extra_need_bytes:
        new_size = info['map_size'] + int(growth_gb * 1e9)
        env.set_mapsize(new_size)

def safe_batch_put(env: lmdb.Environment, items: Iterable[Tuple[bytes, bytes]], growth_gb: int) -> int:
    """
    把一批 (key, value) 放入 LMDB。遇 MapFull 自动扩容并重试。
    返回成功写入的条目数。
    """
    pending = list(items)
    n = 0
    while pending:
        try:
            with env.begin(write=True) as txn:
                for k, v in pending:
                    txn.put(k, v)
            n += len(pending)
            pending.clear()
        except lmdb.MapFullError:
            # 增长映射，再重试
            curr = env.info()['map_size']
            env.set_mapsize(curr + int(growth_gb * 1e9))
    return n

# ------------------------- 写入主流程 ------------------------- #

def write_dataset(ds, env: lmdb.Environment, key_start_idx: int,
                  batch_size: int, growth_gb: int) -> int:
    """
    将数据集写入 LMDB。
    - ds[i] 的结果会被 pickle 序列化作为 value
    - key 为 8 位零填充序号：b'%08d'
    - 仅 key 偏移使用 key_start_idx，不偏移 ds 的访问范围
    返回新增写入条目数。
    """
    N = len(ds)
    n_written_total = 0
    write_idx = key_start_idx

    def kv_range(i0: int, i1: int):
        nonlocal write_idx
        for i in range(i0, i1):
            try:
                item = ds[i]
                key = f"{write_idx:08d}".encode('ascii')
                val = pickle.dumps(item, protocol=pickle.HIGHEST_PROTOCOL)
                write_idx += 1
                yield key, val
            except Exception as e:
                # 跳过坏样本
                # 可在此打印日志：print(f"skip {i}: {e}")
                continue

    for beg in range(0, N, batch_size):
        end = min(beg + batch_size, N)
        # 估计本批所需空间（粗估：每条 2KB 起步；让 MapFullError 驱动扩容更稳）
        # 更优：可先对前 100 个样本做抽样估计平均大小，再计算 need_bytes
        need_bytes = (end - beg) * 2048
        ensure_mapsize(env, need_bytes, growth_gb)
        n_ok = safe_batch_put(env, kv_range(beg, end), growth_gb)
        n_written_total += n_ok
        # 更新 __len__
        set_len(env, write_idx - key_start_idx)

    return n_written_total

# ------------------------- 模式封装 ------------------------- #

def create_lmdb(data_root: str, s: Optional[int], e: Optional[int],
                out_path: str, map_size_gb: int, growth_gb: int, batch_size: int) -> None:
    ds  = MoleculeDataset(data_root, start_idx=s, end_idx=e)
    env = env_open(out_path, map_size_gb)
    try:
        n_before = 0
        set_len(env, 0)
        n_new = write_dataset(ds, env, key_start_idx=0, batch_size=batch_size, growth_gb=growth_gb)
    finally:
        # 统计必须在 close 之前读取
        total_len = env_len(env)
        env.sync()
        env.close()
    print(f"✓ 生成 {out_path}  (写入 {n_new} 分子，总计 {total_len})")

def update_lmdb(data_root: str, s: Optional[int], e: Optional[int],
                out_path: str, map_size_gb: int, growth_gb: int, batch_size: int) -> None:
    ds  = MoleculeDataset(data_root, start_idx=s, end_idx=e)
    env = env_open(out_path, map_size_gb)
    try:
        curr = env_len(env)
        n_new = write_dataset(ds, env, key_start_idx=curr, batch_size=batch_size, growth_gb=growth_gb)
    finally:
        total_len = env_len(env)
        env.sync()
        env.close()
    print(f"✓ 追加完成：新增 {n_new} 分子，总计 {total_len}")

# ------------------------- CLI ------------------------- #

def parse_args():
    p = argparse.ArgumentParser(description="快速稳定构建 LMDB（分批 + 自动扩容）")
    p.add_argument('--data_roots', type=str, nargs='+', required=True,
                   help='数据根目录（可给多个，将依次构建/追加）')
    p.add_argument('--mode', type=str, default='auto', choices=['create','update','auto'],
                   help='create: 新建；update: 追加；auto: 自动判断是否已存在')
    p.add_argument('--out_path', type=str, default=None,
                   help='输出 lmdb 路径（默认：<data_root>.lmdb）')
    p.add_argument('--map_size', type=int, default=4,
                   help='初始映射大小，单位 GB（默认 4）')
    p.add_argument('--growth_gb', type=int, default=2,
                   help='空间不足时每次扩容大小，单位 GB（默认 2）')
    p.add_argument('--batch_size', type=int, default=1000,
                   help='写事务批大小（默认 1000）')
    p.add_argument('--starts', type=int, default=None,
                   help='传给 MoleculeDataset 的 start_idx（可选）')
    p.add_argument('--ends', type=int, default=None,
                   help='传给 MoleculeDataset 的 end_idx（可选）')
    return p.parse_args()

def main():
    args = parse_args()
    roots = args.data_roots
    for root in roots:
        root = os.path.abspath(root)
        out_path = args.out_path or (root.rstrip(os.sep) + '.lmdb')
        exists = os.path.exists(out_path)

        if args.mode == 'create' or (args.mode == 'auto' and not exists):
            print(f"[create] {root} -> {out_path}  (init {args.map_size}GB, growth {args.growth_gb}GB, batch {args.batch_size})")
            create_lmdb(root, args.starts, args.ends,
                        out_path, args.map_size, args.growth_gb, args.batch_size)
        else:
            print(f"[update] {root} -> {out_path}  (init {args.map_size}GB, growth {args.growth_gb}GB, batch {args.batch_size})")
            update_lmdb(root, args.starts, args.ends,
                        out_path, args.map_size, args.growth_gb, args.batch_size)

if __name__ == '__main__':
    main()