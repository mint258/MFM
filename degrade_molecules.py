#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
degrade_molecules.py
--------------------
生成拓扑/几何负样本，并可写出 XYZ 以直观看不同 level 的劣化效果。
兼容本工程的两类数据集：
  - MoleculeDataset (dataset_without_charge.py)
  - LmdbMoleculeDataset (dataset_lmdb.py)

要点：
- 元素标签以 x[:,0] 为准（与现有管线一致）。通常为 0-based (Z-1)，pad = 最后一类。
- 拓扑劣化：按元素周期表二维相邻“8 邻域”替换（跳过稀有气体、H、Z>=87），并可随机删除部分原子。
- 几何劣化：局部扭转/键长微调/全局高斯噪声（可控强度）。
- 输出：在 main 中将正/负样本写为 .xyz 到指定文件夹，第二行包含 meta 信息。

用法示例：
  1) 无数据快速查看：
     python degrade_molecules.py --mode both --level 0.7 --out-dir ./neg_xyz

  2) 将真实数据“转换”为负样本（transform）：
     python degrade_molecules.py --data /path/to/data_or.lmdb --mode topo --level 0.6 \
            --as-transform --batch-size 4 --starts 0 --ends 50 --out-dir ./neg_xyz

  3) 为每个正样本“派生”K个负样本：
     python degrade_molecules.py --data /path/to/data_or.lmdb --mode geom --level 0.4 \
            --neg-per-sample 2 --batch-size 4 --starts 0 --ends 20 --out-dir ./neg_xyz
"""
import os, math, argparse, logging, random
from dataclasses import dataclass
from typing import Optional, List, Tuple

import torch
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

# 可选依赖：若环境没有 periodictable，我们用内置表即可
try:
    import periodictable  # noqa
    HAVE_PT = True
except Exception:
    HAVE_PT = False

LOGGER = logging.getLogger("degrade")

# ----------------------------- 基础工具 -----------------------------

# Z→Symbol（1..86），索引 0 位置占位
Z2SYM = [
    None,
    'H','He','Li','Be','B','C','N','O','F','Ne',
    'Na','Mg','Al','Si','P','S','Cl','Ar',
    'K','Ca','Sc','Ti','V','Cr','Mn','Fe','Co','Ni','Cu','Zn',
    'Ga','Ge','As','Se','Br','Kr',
    'Rb','Sr','Y','Zr','Nb','Mo','Tc','Ru','Rh','Pd','Ag','Cd',
    'In','Sn','Sb','Te','I','Xe',
    'Cs','Ba','La','Ce','Pr','Nd','Pm','Sm','Eu','Gd','Tb','Dy','Ho','Er','Tm','Yb','Lu',
    'Hf','Ta','W','Re','Os','Ir','Pt','Au','Hg','Tl','Pb','Bi','Po','At','Rn'
]

NOBLE_GASES = {2,10,18,36,54,86}
FORBIDDEN_Z  = NOBLE_GASES | {1}  # 不允许作为替换目标；H 也不作为目标
Z_MAX_ALLOWED = 86                # 避免第七周期元素(>=87)

# 构造“周期×族”的二维表（period 1..6, group 1..18），None 代表空位
# 说明：第 6 周期 group3 处放置 La(57)，f 区不纳入二维邻域；该邻域定义满足主族+过渡族 8 邻域直观需求。
PTABLE = {
    (1,1):1, (1,18):2,
    (2,1):3,(2,2):4,(2,13):5,(2,14):6,(2,15):7,(2,16):8,(2,17):9,(2,18):10,
    (3,1):11,(3,2):12,(3,13):13,(3,14):14,(3,15):15,(3,16):16,(3,17):17,(3,18):18,
    (4,1):19,(4,2):20,(4,3):21,(4,4):22,(4,5):23,(4,6):24,(4,7):25,(4,8):26,(4,9):27,(4,10):28,(4,11):29,(4,12):30,(4,13):31,(4,14):32,(4,15):33,(4,16):34,(4,17):35,(4,18):36,
    (5,1):37,(5,2):38,(5,3):39,(5,4):40,(5,5):41,(5,6):42,(5,7):43,(5,8):44,(5,9):45,(5,10):46,(5,11):47,(5,12):48,(5,13):49,(5,14):50,(5,15):51,(5,16):52,(5,17):53,(5,18):54,
    (6,1):55,(6,2):56,(6,3):57,(6,4):72,(6,5):73,(6,6):74,(6,7):75,(6,8):76,(6,9):77,(6,10):78,(6,11):79,(6,12):80,(6,13):81,(6,14):82,(6,15):83,(6,16):84,(6,17):85,(6,18):86,
}
Z2POS = {z: pos for pos, z in PTABLE.items()}

def z_to_symbol(z:int) -> str:
    if 1 <= z <= 86:
        return Z2SYM[z]
    if HAVE_PT:
        try:
            return periodictable.elements[z].symbol
        except Exception:
            pass
    return f"X{z}"

def elemcol_to_atomic_numbers(elem_col: torch.Tensor) -> torch.Tensor:
    """把 x[:,0] 转为原子序数 Z（尽量兼容 0-based(Z-1) 与直接 Z 两种风格）"""
    z_guess = elem_col.long()
    # heuristic: 若最小>=1 且最大<=Z_MAX_ALLOWED，则认为已经是 Z
    if int(z_guess.min()) >= 1 and int(z_guess.max()) <= Z_MAX_ALLOWED:
        return z_guess
    # 否则按 Z-1 处理
    z = z_guess + 1
    return z.clamp(min=1, max=Z_MAX_ALLOWED)

def atomic_numbers_to_elemcol(z: torch.Tensor) -> torch.Tensor:
    """把原子序数 Z 映射回 x[:,0] 的编码（默认 0-based Z-1）"""
    return (z - 1).clamp(min=0)

def periodic_neighbors_8(z:int) -> List[int]:
    """返回元素在二维周期表 8 邻域内的可选替换 Z（排除稀有气体/H/>=87），不含自身"""
    if z not in Z2POS:
        return []
    p,g = Z2POS[z]
    candidates = []
    for dp in (-1,0,1):
        for dg in (-1,0,1):
            if dp==0 and dg==0:
                continue
            key = (p+dp, g+dg)
            nz  = PTABLE.get(key, None)
            if nz is None:
                continue
            if nz == z:
                continue
            if nz in FORBIDDEN_Z:
                continue
            if nz > Z_MAX_ALLOWED:
                continue
            candidates.append(nz)
    # 去重
    return sorted(list(set(candidates)))

# 受限随机：兼容旧版 torch 无 generator 的 API
def _rand(shape, device, dtype, rng: Optional[torch.Generator] = None):
    if rng is not None:
        try:
            return torch.rand(shape, device=device, dtype=dtype, generator=rng)
        except TypeError:
            pass
    return torch.rand(shape, device=device, dtype=dtype)

def _randn(shape, device, dtype, rng: Optional[torch.Generator] = None):
    if rng is not None:
        try:
            return torch.randn(shape, device=device, dtype=dtype, generator=rng)
        except TypeError:
            pass
    return torch.randn(shape, device=device, dtype=dtype)

# 旋转工具：罗德里格斯
def _rotate_points(points: torch.Tensor, axis: torch.Tensor, angle_rad: float):
    # points: (M,3)  axis: (3,) 已单位化
    k = axis / (axis.norm() + 1e-9)
    K = torch.tensor([[0, -k[2], k[1]],
                      [k[2], 0, -k[0]],
                      [-k[1], k[0], 0]], dtype=points.dtype, device=points.device)
    I = torch.eye(3, dtype=points.dtype, device=points.device)
    R = I + math.sin(angle_rad) * K + (1-math.cos(angle_rad)) * (K @ K)
    return (points @ R.T)

@dataclass
class DegradeConfig:
    mode: str = "topo"           # "topo" | "geom" | "both"
    level: float = 0.5           # 0..1
    topo_replace_frac: Optional[float] = None
    topo_delete_frac: Optional[float]  = None
    geom_noise_std: Optional[float]    = None  # Å
    geom_angle_std_deg: Optional[float]= None  # degree
    geom_radius: Optional[float]       = None  # Å
    geom_bond_scale_std: Optional[float]=None  # 键长缩放 std

    def finalize(self):
        L = float(self.level)
        if self.topo_replace_frac is None:
            self.topo_replace_frac = 0.30 * L
        if self.topo_delete_frac is None:
            self.topo_delete_frac  = 0.15 * L
        if self.geom_noise_std is None:
            self.geom_noise_std    = 0.05 + 0.25 * L
        if self.geom_angle_std_deg is None:
            self.geom_angle_std_deg = 10.0 + 35.0 * L
        if self.geom_radius is None:
            self.geom_radius       = 2.0 + 2.0 * L
        if self.geom_bond_scale_std is None:
            self.geom_bond_scale_std = 0.03 + 0.10 * L
        # 合法范围
        self.topo_replace_frac = max(0.0, min(1.0, self.topo_replace_frac))
        self.topo_delete_frac  = max(0.0, min(0.9, self.topo_delete_frac))  # 至多删 90%
        self.geom_noise_std    = max(0.0, float(self.geom_noise_std))
        self.geom_angle_std_deg= max(0.0, float(self.geom_angle_std_deg))
        self.geom_radius       = max(0.1, float(self.geom_radius))
        self.geom_bond_scale_std = max(0.0, float(self.geom_bond_scale_std))
        return self

# ----------------------------- 劣化核心 -----------------------------

def _topology_degrade(data: Data, cfg: DegradeConfig, rng: Optional[torch.Generator]) -> Data:
    x   = data.x.clone()
    pos = data.pos.clone()
    N   = x.size(0)
    device = x.device

    z = elemcol_to_atomic_numbers(x[:,0])
    heavy_mask = (z > 1) & (z <= Z_MAX_ALLOWED)

    # 1) 元素替换（近邻 8 邻域）
    n_heavy = int(heavy_mask.sum().item())
    n_replace = int(round(cfg.topo_replace_frac * max(0, n_heavy)))
    if n_replace > 0 and n_heavy > 0:
        idx_heavy = torch.nonzero(heavy_mask, as_tuple=False).view(-1)
        # 随机选择要替换的 heavy atom
        # 兼容旧 torch 的 generator
        perm = torch.randperm(idx_heavy.numel(), device=device)
        if rng is not None:
            try:
                perm = torch.randperm(idx_heavy.numel(), device=device, generator=rng)
            except TypeError:
                # fallback: 使用 _rand 产生打乱索引
                scores = _rand(idx_heavy.shape, device=device, dtype=torch.float32, rng=rng)
                perm = torch.argsort(scores)
        chosen = idx_heavy[perm[:n_replace]]
        for i in chosen.tolist():
            zi = int(z[i].item())
            neigh = periodic_neighbors_8(zi)
            # 避开无候选/异常
            if len(neigh) == 0:
                continue
            # 从候选中随机选一个
            k = int((_rand((), device=device, dtype=torch.float32, rng=rng).item()) * len(neigh))
            k = max(0, min(len(neigh)-1, k))
            z_new = neigh[k]
            z[i]  = z_new

    # 2) 随机删除原子（全体可删，但保留至少 2 个原子）
    # n_delete = int(round(cfg.topo_delete_frac * N))
    n_delete = 0 # 已经关闭随机删除原子方法
    if n_delete > 0 and N - n_delete >= 2:
        # 生成随机删除索引
        try:
            perm = torch.randperm(N, device=device, generator=rng) if rng is not None else torch.randperm(N, device=device)
        except TypeError:
            perm = torch.randperm(N, device=device)
        del_idx = perm[:n_delete]
        keep_mask = torch.ones(N, dtype=torch.bool, device=device)
        keep_mask[del_idx] = False

        # 应用于所有以 N 为第一维的张量属性
        new_data = Data()
        for k, v in data:
            if isinstance(v, torch.Tensor) and v.size(0) == N:
                new_data[k] = v[keep_mask]
            else:
                # trajectory 等非对齐维度的复杂字段不复制，避免维度不一致
                if k in ("trajectory",):
                    continue
                new_data[k] = v
        # 覆盖修改后的 x/pos/元素列
        new_data.x = new_data.x.clone()
        z_kept = elemcol_to_atomic_numbers(new_data.x[:,0])
        # 将替换过的 z 写回（但需按 keep_mask 过滤）
        new_data.x[:,0] = atomic_numbers_to_elemcol(z[keep_mask])
        out = new_data
    else:
        # 未删除时，直接在原 data 上写回元素替换
        out = data.clone()
        out.x = x.clone()
        out.x[:,0] = atomic_numbers_to_elemcol(z)

    out.is_feasible = torch.tensor([0], dtype=torch.long)  # 负样本
    out.neg_type    = torch.tensor([1], dtype=torch.long)  # 1 = topo
    # 清理 batch，让 DataLoader 重新生成
    if hasattr(out, "batch"):
        del out.batch
    # 轨迹字段不在负样本中使用
    if hasattr(out, "trajectory"):
        delattr(out, "trajectory")
    return out

def _geometry_degrade(data: Data, cfg: DegradeConfig, rng: Optional[torch.Generator]) -> Data:
    out = data.clone()
    pos = out.pos.clone()
    N   = pos.size(0)
    device = pos.device
    dtype  = pos.dtype

    # 1) 局部扭转：随机选一个中心，半径球内的点绕随机轴旋转小角度
    center_idx = int((_rand((), device=device, dtype=dtype, rng=rng).item()) * N)
    center_idx = max(0, min(N-1, center_idx))
    center = pos[center_idx]

    d = torch.cdist(pos, center[None, :]).view(-1)  # (N,)
    neighborhood = (d <= cfg.geom_radius)
    if int(neighborhood.sum()) >= 2:
        # 随机轴 + 角度
        axis = _randn((3,), device=device, dtype=dtype, rng=rng)
        if float(axis.norm()) < 1e-6:
            axis = torch.tensor([1.0, 0.0, 0.0], device=device, dtype=dtype)
        angle = (_randn((), device=device, dtype=dtype, rng=rng).item()) * (math.pi/180.0) * cfg.geom_angle_std_deg

        pts = pos[neighborhood] - center
        pts_rot = _rotate_points(pts, axis, angle)
        pos[neighborhood] = pts_rot + center

    # 2) 近邻对键长轻度缩放（通过近邻半径选择若干对）
    # 简单做法：取与 center 邻域内若干点 pair = (center, j)
    nb_idx = torch.nonzero(neighborhood, as_tuple=False).view(-1).tolist()
    if len(nb_idx) >= 2:
        for j in nb_idx[:max(1, len(nb_idx)//3)]:
            if j == center_idx:
                continue
            v = pos[j] - pos[center_idx]
            r = v.norm() + 1e-9
            scale = 1.0 + (_randn((), device=device, dtype=dtype, rng=rng).item()) * cfg.geom_bond_scale_std
            scale = float(max(0.7, min(1.3, scale)))  # 安全夹紧
            pos[j] = pos[center_idx] + v * (scale)

    # 3) 全局轻度高斯噪声
    noise = _randn(pos.shape, device=device, dtype=dtype, rng=rng) * cfg.geom_noise_std
    pos = pos + noise

    out.pos = pos
    out.is_feasible = torch.tensor([0], dtype=torch.long)  # 负样本
    out.neg_type    = torch.tensor([2], dtype=torch.long)  # 2 = geom
    if hasattr(out, "batch"):
        del out.batch
    if hasattr(out, "trajectory"):
        delattr(out, "trajectory")
    return out

def degrade_once(data: Data, cfg: DegradeConfig, rng: Optional[torch.Generator] = None) -> Data:
    cfg = cfg.finalize()
    if cfg.mode == "topo":
        return _topology_degrade(data, cfg, rng)
    elif cfg.mode == "geom":
        return _geometry_degrade(data, cfg, rng)
    elif cfg.mode == "both":
        tmp = _topology_degrade(data, cfg, rng)
        return _geometry_degrade(tmp, cfg, rng)
    else:
        raise ValueError(f"Unknown mode: {cfg.mode}")

# ----------------------------- 数据集封装 -----------------------------

class NegativeTransform:
    """将样本直接转换为负样本（transform 接口）"""
    def __init__(self, cfg: DegradeConfig, p_neg: float = 1.0, seed: int = 114):
        self.cfg = cfg
        self.p_neg = float(p_neg)
        self.seed = int(seed)

    def __call__(self, data: Data) -> Data:
        if self.p_neg >= 1.0 or random.random() < self.p_neg:
            g = torch.Generator(device=data.x.device if data.x.is_cuda else 'cpu').manual_seed(self.seed + int(random.random()*10**6))
            return degrade_once(data, self.cfg, g)
        return data

class NegativeSampleDataset(torch.utils.data.Dataset):
    """从 base_dataset 派生固定数量的负样本"""
    def __init__(self, base_dataset, cfg: DegradeConfig, neg_per_sample: int = 1, seed: int = 114):
        self.base = base_dataset
        self.cfg  = cfg.finalize()
        self.K    = int(neg_per_sample)
        self.seed = int(seed)

    def __len__(self):
        return len(self.base)

    def __getitem__(self, idx: int) -> Data:
        pos_data = self.base[idx]
        # 为可追溯性，基于 idx 的种子
        g = torch.Generator(device=pos_data.x.device if pos_data.x.is_cuda else 'cpu').manual_seed(self.seed + idx)
        neg_data = degrade_once(pos_data, self.cfg, g)
        return neg_data

def create_dataset(path: Optional[str] = None, start_idx: Optional[int] = None, end_idx: Optional[int] = None):
    """
    与 pretrain_multitask.py 风格保持一致：
      - 路径以 .lmdb 结尾 -> LmdbMoleculeDataset
      - 否则 -> MoleculeDataset
    优先尝试向底层数据集传入 start_idx/end_idx；若不支持则回退为 Subset。
    """
    if path is None:
        return None
    s = 0 if start_idx in (None,) else int(start_idx)
    e = None if end_idx in (None, -1) else int(end_idx)

    if path.endswith(".lmdb"):
        from dataset_lmdb import LmdbMoleculeDataset
        try:
            ds = LmdbMoleculeDataset(path, start_idx=s, end_idx=e, filter_missing_on_init=True)
        except TypeError:
            ds = LmdbMoleculeDataset(path, filter_missing_on_init=True)
            if s != 0 or e is not None:
                from torch.utils.data import Subset
                stop = len(ds) if e is None else min(e, len(ds))
                ds = Subset(ds, list(range(s, stop)))
    else:
        from dataset_without_charge import MoleculeDataset
        try:
            ds = MoleculeDataset(path, start_idx=s, end_idx=e)
        except TypeError:
            ds = MoleculeDataset(path)
            if s != 0 or e is not None:
                from torch.utils.data import Subset
                stop = len(ds) if e is None else min(e, len(ds))
                ds = Subset(ds, list(range(s, stop)))
    return ds

# ----------------------------- XYZ 写入 -----------------------------

def write_xyz(path: str, Z: torch.Tensor, pos: torch.Tensor, title: str = ""):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Z = Z.detach().cpu().long().tolist()
    pos = pos.detach().cpu().tolist()
    with open(path, "w") as f:
        f.write(f"{len(Z)}\n")
        f.write((title or "").strip() + "\n")
        for z, (x,y,zpos) in zip(Z, pos):
            sym = z_to_symbol(int(z))
            f.write(f"{sym:2s} {x:.6f} {y:.6f} {zpos:.6f}\n")

def data_to_xyz(path: str, data: Data, note: str = ""):
    z = elemcol_to_atomic_numbers(data.x[:,0])
    energy = None
    if hasattr(data, "energy") and isinstance(data.energy, torch.Tensor):
        try:
            energy = float(data.energy.squeeze().detach().cpu().item())
        except Exception:
            pass
    title = (f"{'NEG' if getattr(data, 'is_feasible', torch.tensor([1])).item()==0 else 'POS'} "
             f"{note}  Energy={energy if energy is not None else 'NA'}")
    write_xyz(path, z, data.pos, title)

# ----------------------------- CLI / main -----------------------------

def build_argparser():
    p = argparse.ArgumentParser()
    p.add_argument("--data", type=str, default=None, help="数据路径（文件夹或 .lmdb）；为空时用合成示例")
    p.add_argument("--mode", type=str, choices=["topo","geom","both"], default="topo")
    p.add_argument("--level", type=float, default=0.5)
    p.add_argument("--as-transform", action="store_true", help="将数据直接转换为负样本（所有样本）")
    p.add_argument("--neg-per-sample", type=int, default=1, help="每个正样本派生的负样本数（用于 derived 模式）")
    p.add_argument("--batch-size", type=int, default=4)
    # 与 pretrain_multitask 对齐的索引选择方式
    p.add_argument("--starts", nargs='*', type=int, default=[], help="与 data 对齐的起始索引（单数据路径传 1 个值）")
    p.add_argument("--ends",   nargs='*', type=int, default=[], help="与 data 对齐的结束索引（-1 或缺省表示到末尾）")
    p.add_argument("--out-dir", type=str, default="./neg_xyz")
    p.add_argument("--seed", type=int, default=114)
    return p

def _first_or(default, lst):
    return (lst[0] if (isinstance(lst, list) and len(lst)>0) else default)

def synthetic_example() -> Data:
    # 10 原子链，交替 C(6)/N(7)/O(8)/S(16)/P(15) 等
    Z = torch.tensor([6,7,8,16,15,6,7,8,16,15], dtype=torch.long)
    x0 = atomic_numbers_to_elemcol(Z).float().unsqueeze(-1)  # 只放元素列即可
    t = torch.linspace(0, 9, steps=10)
    pos = torch.stack([t*1.2, torch.zeros_like(t), torch.sin(t)*0.1], dim=-1).to(torch.float32)
    data = Data(x=x0, pos=pos)
    data.is_feasible = torch.tensor([1], dtype=torch.long)
    data.neg_type    = torch.tensor([0], dtype=torch.long)
    return data

def main():
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    args = build_argparser().parse_args()
    cfg = DegradeConfig(mode=args.mode, level=args.level).finalize()

    if args.data is None:
        # 合成示例：输出原/负各 1 个
        base = synthetic_example()
        data_to_xyz(os.path.join(args.out_dir, f"{args.mode}_L{cfg.level:.2f}", "synthetic_pos.xyz"), base, note=f"mode={cfg.mode} level={cfg.level}")
        g = torch.Generator().manual_seed(args.seed)
        neg = degrade_once(base, cfg, g)
        data_to_xyz(os.path.join(args.out_dir, f"{args.mode}_L{cfg.level:.2f}", "synthetic_neg.xyz"), neg, note=f"mode={cfg.mode} level={cfg.level}")
        print(f"Saved to {os.path.join(args.out_dir, f'{args.mode}_L{cfg.level:.2f}')}")
        return

    # 真实数据：使用 starts/ends（与 pretrain_multitask 对齐）
    start_idx = _first_or(0, args.starts)
    end_idx   = _first_or(None, args.ends)
    if isinstance(end_idx, int) and end_idx == -1:
        end_idx = None

    dataset = create_dataset(args.data, start_idx=start_idx, end_idx=end_idx)

    if args.as_transform:
        # 直接转换为负样本
        trans = NegativeTransform(cfg, p_neg=1.0, seed=args.seed)
        if hasattr(dataset, "transform") and getattr(dataset, "transform", None) is None:
            dataset.transform = trans
        else:
            # 若是 Subset 或不支持 transform，则包装一下
            class _Wrap(torch.utils.data.Dataset):
                def __init__(self, base, t):
                    self.base=base; self.t=t
                def __len__(self): return len(self.base)
                def __getitem__(self, i): return self.t(self.base[i])
            dataset = _Wrap(dataset, trans)
        loader = DataLoader(dataset, batch_size=args.batch_size, shuffle=False)
        out_subdir = os.path.join(args.out_dir, f"{args.mode}_L{cfg.level:.2f}_transform")
        idx_global = 0
        for batch in loader:
            # 拆成单图并写出
            data_list = batch.to_data_list()
            for d in data_list:
                path = os.path.join(out_subdir, f"idx_{idx_global:06d}_neg.xyz")
                data_to_xyz(path, d, note=f"mode={cfg.mode} level={cfg.level}")
                idx_global += 1
        print(f"Saved {idx_global} files to {out_subdir}")
    else:
        # 派生负样本：保留正样本并为每个生成 K 份负样本
        loader = DataLoader(dataset, batch_size=1, shuffle=False)
        out_subdir = os.path.join(args.out_dir, f"{args.mode}_L{cfg.level:.2f}_derived")
        idx_global = 0
        for batch in loader:
            d = batch.to_data_list()[0]
            data_to_xyz(os.path.join(out_subdir, f"idx_{idx_global:06d}_pos.xyz"), d, note="POS")
            # 负样本
            for k in range(args.neg_per_sample):
                g = torch.Generator().manual_seed(args.seed + idx_global*1000 + k)
                neg = degrade_once(d, cfg, g)
                data_to_xyz(os.path.join(out_subdir, f"idx_{idx_global:06d}_neg{k}.xyz"), neg, note=f"mode={cfg.mode} level={cfg.level}")
            idx_global += 1
        print(f"Saved {idx_global*(1+args.neg_per_sample)} files to {out_subdir}")

if __name__ == "__main__":
    main()
