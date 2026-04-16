#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dataset_infer.py
--------------------------------
Inference-only dataloader for `structure_predict.py`.

特点
~~~~
* **递归扫描** root 目录下所有 `.xyz` 文件；文件名/层级任意。
* 仅解析必需信息：元素 + 坐标。
* 若 `.xyz` 第二行或原子行附带能量 / 电荷，自动写入可选字段：
    - `data.energy` : float
    - `data.y`      : (N,1) 电荷；并给 `data.charge_mask`
* `Data.x` 采用 **0-based** 元素索引，映射与训练版保持一致。
"""

from __future__ import annotations
import os, glob, logging
from typing import List, Optional

import torch
from torch_geometric.data import Dataset, Data

# ---------------------------------------------------------------------
# 元素 ↔ 索引映射（优先使用 periodictable；无则退到内置列表）
# ---------------------------------------------------------------------
try:
    import periodictable as _pt
    _ELEMENT_TO_IDX = {element.symbol: idx for idx, element in enumerate(_pt.elements)}
    _SHIFT = 0                                       # 0-based 与训练保持一致
except ModuleNotFoundError:
    _EL_LIST = (
        'H He Li Be B  C  N  O  F  Ne '
        'Na Mg Al Si P  S  Cl Ar K  Ca '
        'Sc Ti V  Cr Mn Fe Co Ni Cu Zn '
        'Ga Ge As Se Br Kr'
    ).split()
    _ELEMENT_TO_IDX = {s: i for i, s in enumerate(_EL_LIST)}
    _SHIFT = 0


# ---------------------------------------------------------------------
# 单文件解析
# ---------------------------------------------------------------------
def _parse_xyz(path: str,
               allow_unknown: bool = False) -> Data:
    """
    只取元素和坐标；能量/电荷若存在一并记录。
    支持三种可选电荷/能量写法：
      1) 第二行形如 'Energy: -123.456'
      2) 原子行第五列为电荷
      3) 第二行任意位置出现可解析 float 的最后一个 token
    """
    with open(path, 'r') as f:
        lines = [ln.rstrip() for ln in f]

    if len(lines) < 3:
        raise ValueError(f'{path}: 文件内容不足')

    n_atom = int(lines[0].strip())
    comment = lines[1].strip()

    # ---------- 可选能量 ----------
    energy: Optional[float] = None
    for tk in reversed(comment.replace('*^', 'e').split()):
        try:
            energy = float(tk)
            break
        except ValueError:
            continue

    atoms, coords, charges = [], [], []
    for ln in lines[2: 2 + n_atom]:
        parts = ln.split()
        if len(parts) < 4:
            continue
        sym = parts[0]
        if sym not in _ELEMENT_TO_IDX:
            if allow_unknown:
                continue
            raise KeyError(f'未知元素: {sym} @ {path}')
        atoms.append(sym)
        coords.append([float(x.replace('*^', 'e')) for x in parts[1:4]])
        if len(parts) >= 5:
            try:
                charges.append(float(parts[4].replace('*^', 'e')))
            except ValueError:
                charges.append(0.0)

    z = torch.tensor([_ELEMENT_TO_IDX[a] - _SHIFT for a in atoms],
                     dtype=torch.long).view(-1, 1)
    pos = torch.tensor(coords, dtype=torch.float)

    data = Data(x=z, pos=pos, filename=os.path.basename(path))
    if energy is not None:
        data.energy = torch.tensor(energy, dtype=torch.float)
    if charges:
        data.y = torch.tensor(charges, dtype=torch.float).view(-1, 1)
        data.charge_mask = torch.ones_like(data.y, dtype=torch.bool)
    else:
        data.charge_mask = torch.zeros(pos.size(0), 1, dtype=torch.bool)

    return data


# ---------------------------------------------------------------------
# 推理-版 Dataset
# ---------------------------------------------------------------------
class MoleculeDataset(Dataset):
    """
    推理阶段专用数据集。

    参数
    ----
    root : str
        目录，递归查找所有 .xyz 文件。
    start_idx / end_idx : int, 可选
        用于子集分割（与训练脚本保持一致接口）。
    allow_unknown : bool
        True 时遇到未知元素跳过该原子；False 时抛出异常。
    """
    def __init__(self,
                 root: str,
                 transform=None,
                 pre_transform=None,
                 *,
                 start_idx: int = 0,
                 end_idx: Optional[int] = None,
                 allow_unknown: bool = False):
        super().__init__(root, transform, pre_transform)
        self.file_paths: List[str] = sorted(
            glob.glob(os.path.join(root, '**', '*.xyz'),
                      recursive=True))
        if not self.file_paths:
            raise FileNotFoundError(f'在 {root} 未发现任何 .xyz 文件')
        self.file_paths = self.file_paths[start_idx:end_idx]
        self.allow_unknown = allow_unknown
        logging.info("InferenceDataset | 载入 %d 个 xyz", len(self.file_paths))

    # 以下三函数为 PyG Dataset 必需
    def len(self) -> int:                      # type: ignore[override]
        return len(self.file_paths)

    def get(self, idx: int) -> Data:           # type: ignore[override]
        path = self.file_paths[idx]
        return _parse_xyz(path, self.allow_unknown)

    def raw_file_names(self):                  # 兼容 PyG <2.4
        return []

    def processed_file_names(self):
        return []
