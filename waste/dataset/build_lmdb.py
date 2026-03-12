#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_lmdb.py  ·  支持 create / update
--------------------------------------
示例 1 · 首次生成
    python build_lmdb.py --data_roots /data/qm9 --map_size 300

示例 2 · 追加新样本（append-only）
    # 往 /data/qm9.lmdb 里追加目录中新产生的 xyz
    python build_lmdb.py --data_roots /data/qm9 --mode update

示例 3 · 自动判断（文件不存在→create，存在→update）
    python build_lmdb.py --data_roots /data/qm9 --mode auto

⚠️ 追加模式假设数据集“只增不删”。  
若对 **已存在分子** 做了改动，请删除旧库后用 `--mode create` 重建。
"""
import argparse
import os
import pickle
import sys
import tqdm
import lmdb

from dataset_without_charge import MoleculeDataset

# ---------- 核心函数 ----------
def write_dataset(ds, env, start_idx):
    """
    Write dataset to LMDB, skipping samples that cause errors.
    Keys are assigned contiguously starting from start_idx.
    __len__ reflects number of written molecules.
    """
    with env.begin(write=True) as txn:
        write_idx = start_idx
        for orig_idx in tqdm.tqdm(range(start_idx, len(ds)),
                                  desc='⟹  add', unit='mol'):
            try:
                data = ds[orig_idx]
            except Exception as e:
                print(f"⚠️  跳过 idx {orig_idx}，原因: {e}", file=sys.stderr)
                continue
            key = f'{write_idx:09d}'.encode()
            txn.put(key, pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL))
            write_idx += 1
        # 写入最终长度
        txn.put(b'__len__', pickle.dumps(write_idx))


def create_lmdb(root, s, e, out_path, mapsize):
    ds  = MoleculeDataset(root, start_idx=s, end_idx=e)
    env = lmdb.open(out_path, map_size=mapsize, subdir=False,
                    lock=False, readahead=False, meminit=False)
    write_dataset(ds, env, 0)
    env.sync(); env.close()
    print(f'✓ 生成 {out_path}  (共写入 {pickle.loads(env.begin(write=False).get(b"__len__"))} 分子，跳过错误)')


def update_lmdb(root, s, e, out_path, mapsize):
    ds  = MoleculeDataset(root, start_idx=s, end_idx=e)
    env = lmdb.open(out_path, subdir=False, lock=False,
                    readahead=False, meminit=False)
    if mapsize:  # 支持扩容
        env.set_mapsize(mapsize)

    # # 读取原有长度
    # with env.begin(write=False) as txn:
    #     old_len = pickle.loads(txn.get(b'__len__'))

    added = 0
    with env.begin(write=True) as txn:
        for orig_idx in tqdm.tqdm(range(len(ds)), desc='⟹  sync', unit='mol'):
            try:
                data = ds[orig_idx]
            except Exception as e:
                print(f"⚠️  跳过 idx {orig_idx}，原因: {e}", file=sys.stderr)
                continue
            key = f'{orig_idx:09d}'.encode()
            if txn.get(key) is None:
                txn.put(key, pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL))
                added += 1
        # 重新计算总分子数
        cursor = txn.cursor()
        total = sum(1 for key, _ in cursor if key != b'__len__')
        txn.put(b'__len__', pickle.dumps(total))

    env.sync(); env.close()
    print(f'✓ {out_path}: 追加 {added} / 共 {total} 分子 (跳过错误)')

# ---------- CLI ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data_roots', required=True, nargs='+',
                    help='一个或多个数据目录（与 MoleculeDataset 兼容）')
    ap.add_argument('--starts',  nargs='*', type=int, default=[],
                    help='与 data_roots 对齐的起始 8 位编号 (可选)')
    ap.add_argument('--ends',    nargs='*', type=int, default=[],
                    help='与 data_roots 对齐的结束 8 位编号 (可选)')
    ap.add_argument('--out_suffix', default='lmdb',
                    help='输出文件后缀，默认 *.lmdb*')
    ap.add_argument('--map_size', type=float, default=1.0,
                    help='单库预留 GiB；update 时亦可用于扩容')
    ap.add_argument('--mode', choices=['auto', 'create', 'update'],
                    default='auto')
    ap.add_argument('--out_path', type=str,
                    default=None)
    args = ap.parse_args()

    def _fill(lst, n): return lst + [None] * (n - len(lst))
    roots, starts, ends = (
        args.data_roots,
        _fill(args.starts, len(args.data_roots)),
        _fill(args.ends,   len(args.data_roots)),
    )
    mapsize = int(args.map_size * 1e9)

    for root, s, e in zip(roots, starts, ends):
        out_path = args.out_path if args.out_path else f'{root.rstrip("/")}.{args.out_suffix}'
        exists   = os.path.exists(out_path)

        if args.mode == 'create' or (args.mode == 'auto' and not exists):
            if exists:
                raise FileExistsError(f'{out_path} 已存在，可改用 --mode update')
            create_lmdb(root, s, e, out_path, mapsize)

        elif args.mode == 'update' or (args.mode == 'auto' and exists):
            if not exists:
                raise FileNotFoundError(f'{out_path} 不存在，改用 --mode create')
            update_lmdb(root, s, e, out_path, mapsize)

if __name__ == '__main__':
    main()