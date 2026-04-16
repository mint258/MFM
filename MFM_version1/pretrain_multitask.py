# ================= pretrain_multitask.py =================
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified multi-task pre-training  —  Energy + Charge + Geometry
· 三任务专家 MoE (see moe_transformer_multitask.py)
· 功能 = pretrain_supervised_lmdb + pretrain_unsupervised_morse + bad-batch guard
"""

# ────────────────────────── imports ──────────────────────────
import argparse, logging, os, math, random, warnings
import numpy as np
import torch, torch.nn.functional as F
from torch_geometric.utils   import to_dense_batch
from torch_cluster           import radius_graph
from degrade_molecules import DegradeConfig, degrade_once
from torch.cuda.amp          import GradScaler, autocast
from torch.utils.data        import ConcatDataset, DataLoader, Subset
from torch.optim.lr_scheduler import LambdaLR
from tqdm import tqdm
import sys
from sklearn.metrics import r2_score
from torch_geometric.data import Batch

from moe_transformer_multitask import MultiTaskMoE
from dataset_lmdb           import LmdbMoleculeDataset
from dataset_without_charge import MoleculeDataset
from utils_debug            import set_debug as set_debug_flag, is_debug as get_debug_flag, safe_exp

warnings.filterwarnings('ignore', category=UserWarning)
logging.basicConfig(level=logging.INFO,
                    format='[%(asctime)s] %(levelname)s: %(message)s')
LOGGER = logging.getLogger('multitask')

LEGACY_COLLATE_DROP_FIELDS = {
    "sample_key",
    "smiles",
    "sample_type_id",
    "pretrain_recipe_name",
    "pretrain_recipe_level",
    "pretrain_recipe_seed",
    "element_corrupt_mask",
}
LEGACY_COLLATE_DROP_PREFIXES = ("rdkit_",)

# ─────────────────────────── CLI ────────────────────────────
def get_args():
    p = argparse.ArgumentParser()
    # --- 数据路径 ---
    p.add_argument('--data_roots',       nargs='+', required=True,
                   help='训练数据路径列表（支持文件夹或 .lmdb）')
    p.add_argument('--val_data_roots',   nargs='+', default=[],
                   help='验证数据路径列表')
    p.add_argument('--starts',           nargs='*', type=int, default=[],
                   help='与 data_roots 对齐的起始索引')
    p.add_argument('--ends',             nargs='*', type=int, default=[],
                   help='与 data_roots 对齐的结束索引')
    p.add_argument('--val_starts',       nargs='*', type=int, default=[],
                   help='验证数据起始索引')
    p.add_argument('--val_ends',         nargs='*', type=int, default=[],
                   help='验证数据结束索引')
    # --- 破坏性扰动（Masked Modeling） ---
    p.add_argument('--perturb_mix', type=str, default='none',
                   help='多规格扰动混合串，如 "topo:0.3@0.2,geom:0.5@0.5,both:0.7@1.0"；none 关闭')
    p.add_argument('--perturb_mode', type=str, default='both', choices=['topo', 'geom', 'both'],
                   help='输入扰动模式：拓扑替换/几何噪声/两者并用')
    p.add_argument('--perturb_level', type=float, default=0.5,
                   help='扰动强度(0-1)：用于控制替换比例与噪声幅度')
    p.add_argument('--perturb_replace_frac', type=float, default=None,
                   help='可选：指定原子替换比例，默认随 perturb_level 自动计算')
    p.add_argument('--perturb_noise_std', type=float, default=None,
                   help='可选：指定高斯噪声标准差(Å)，默认随 perturb_level 自动计算')
    p.add_argument('--perturb_seed', type=int, default=114,
                   help='扰动随机种子（对所有样本生效）')
    # --- DataLoader ---
    p.add_argument('--batch_size', type=int, default=4)
    p.add_argument('--num_workers', type=int, default=0)
    # --- Transformer backbone ---
    p.add_argument('--hidden_channels', type=int, default=512)
    p.add_argument('--bb_layers', type=int, default=6)
    p.add_argument('--bb_heads', type=int, default=8)
    p.add_argument('--bb_ff_mult', type=int, default=4)
    p.add_argument('--bb_use_dist_bias', dest='bb_use_dist_bias', action='store_true')
    p.add_argument('--no_bb_use_dist_bias', dest='bb_use_dist_bias', action='store_false')
    p.set_defaults(bb_use_dist_bias=True)
    p.add_argument('--bb_use_radius_mask', action='store_true')
    p.add_argument('--bb_radius', type=float, default=8.0)
    # --- Experts & gate ---
    p.add_argument('--expert_number_E', type=int, default=2)
    p.add_argument('--expert_number_Q', type=int, default=2)
    p.add_argument('--expert_number_Z', type=int, default=1)
    p.add_argument('--expert_number_G', type=int, default=4)
    p.add_argument('--topkE', type=int, default=1)
    p.add_argument('--topkQ', type=int, default=1)
    p.add_argument('--topkZ', type=int, default=1)
    p.add_argument('--topkG', type=int, default=1)
    p.add_argument('--n_atom_types', type=int, default=95,
                    help='元素类别总数(含pad); 数据集元素标签为0-based(Z-1); pad将使用最后一类')
    # --- Loss λ ---
    p.add_argument('--lambda_e', type=float, default=1.0)
    p.add_argument('--lambda_q', type=float, default=1.0)
    p.add_argument('--lambda_z', type=float, default=1.0)
    p.add_argument('--lambda_coord', type=float, default=1.0)
    p.add_argument('--lambda_dist', type=float, default=0.0)
    p.add_argument('--lambda_angle', type=float, default=0.0)
    p.add_argument('--lambda_torsion', type=float, default=0.0)
    p.add_argument('--lambda_planar', type=float, default=1.0, help="新增：平面性损失的权重")
    # --- Expert block config (real/internal parallel stack) ---
    p.add_argument('--expert_real_layers', type=int, default=2)
    p.add_argument('--expert_int_layers', type=int, default=0)
    p.add_argument('--expert_heads', type=int, default=4)
    p.add_argument('--expert_ff_mult', type=int, default=2)
    # --- Optim & sched ---
    p.add_argument('--lr',       type=float, default=3e-4)
    p.add_argument('--epochs',   type=int,   default=10)
    p.add_argument('--warmup_pct', type=float, default=0.06,
                   help='warm-up ratio (0-1)')
    p.add_argument('--fp16', action='store_true')
    p.add_argument('--seed', type=int, default=0)
    # --- RMSD 阶段门限 & 每阶段最多 epoch ---
    p.add_argument('--stage1_loss', type=float, default=0.3)
    p.add_argument('--stage2_loss', type=float, default=0.1)
    p.add_argument('--stage1_max_epochs', type=int, default=101)
    # --- 其它损失相关参数 ---
    p.add_argument('--loss_cutoff', type=float, default=2.0, help="过滤角度/二面角/平面性损失的键长阈值")
    p.add_argument('--morse_D', type=float, default=1.0)
    p.add_argument('--morse_a', type=float, default=1.0)
    # --- Element-Z 额外正则 ---
    p.add_argument('--z_label_smooth', type=float, default=0.10,
                   help='元素分类的 label-smoothing 系数 ε (0-0.2 合理)')
    p.add_argument('--z_focal_gamma', type=float, default=0.0,
                   help='>0 时启用 focal-loss 并设 γ；=0 关闭')
    p.add_argument('--z_temp', type=float, default=1.5,
               help='训练时对 z logits 施加 T>1 的温度（除以 T），软化分布，缓解过度自信')
    p.add_argument('--z_entropy_reg', type=float, default=0.05,
                   help='置信度惩罚系数β：loss += β * (−entropy)，鼓励较高熵，抑制极端 logits')
    p.add_argument('--z_logit_l2', type=float, default=1e-4,
                   help='对 z 的 logits 做 L2 正则，限制绝对值爆炸；0 关闭')
    p.add_argument('--z_class_balance', type=str, default='none',
                   choices=['none','batch_inv','effective'],
                   help='类别不均衡修正：无 / 按当前 batch 的逆频率 / Effective Number of Samples')
    # --- misc ---
    p.add_argument('--save_path', default='ckpt_multitask.pt')
    p.add_argument('--save_every_epoch', action='store_true',
                   help='如果启用，则在每个 epoch 结束时都保存一次模型检查点')
    return p.parse_args()

# ──────────────────────── helpers ──────────────────────────
def set_seed(s):
    random.seed(s); np.random.seed(s)
    torch.manual_seed(s); torch.cuda.manual_seed_all(s)

def pad_list(lst, tgt_len, fill=0):
    return lst + [fill] * max(0, tgt_len - len(lst))

def create_dataset(path, start_idx, end_idx):
    start_idx = start_idx if start_idx is not None else 0
    end_idx   = end_idx   if end_idx   not in (None, -1) else None
    if path.endswith('.lmdb') or (os.path.isfile(path) and path.lower().endswith('.lmdb')):
        # 对 LMDB 启用启动期预过滤，减少运行期缺失命中
        ds = LmdbMoleculeDataset(path, start_idx=start_idx, end_idx=end_idx, filter_missing_on_init=True)
    else:
        ds = MoleculeDataset(path, start_idx=start_idx, end_idx=end_idx)
    # 统一套上安全包装器，保证长度稳定
    wrapped = SafeResampleDataset(ds, max_retries=32, name=os.path.basename(path))
    wrapped.source_path = path
    return wrapped

class SafeResampleDataset(torch.utils.data.Dataset):
    """
    保证数据集“长度稳定”的安全包装器。
    - base[i] 出错（IndexError/ValueError/KeyError/解析失败/NaN 等）时不会缩短长度，
      而是随机重采样其它索引再试，最多重试 max_retries 次。
    """
    def __init__(self, base, max_retries: int = 32, name: str = ""):
        self.base = base
        self.max_retries = int(max_retries)
        self.name = name or type(base).__name__
        self._rng = np.random.default_rng()
    def __len__(self): return len(self.base)
    def __getitem__(self, idx):
        tries = 0
        i = idx
        while tries < self.max_retries:
            try:
                d = self.base[i]
                # 轻量健壮性检查（避免把明显坏样本送进模型）
                if hasattr(d, "pos"):
                    p = d.pos
                    if p.numel() == 0 or (not torch.isfinite(p).all()):
                        raise ValueError("invalid pos")
                if hasattr(d, "x") and d.x.numel() == 0:
                    raise ValueError("empty x")
                return d
            except Exception:
                tries += 1
                i = int(self._rng.integers(0, len(self.base)))
        raise IndexError(f"[SafeResampleDataset:{self.name}] too many invalid samples (idx={idx})")

def detect_nan_inf(tensor):
    """检查一个 Tensor 是否包含 NaN 或 ±Inf"""
    return torch.isnan(tensor).any() or torch.isinf(tensor).any()

def analyze_and_abort(model, batch, intermediates):
    """
    一旦发现 NaN/Inf，打印详细信息并停止训练
    - model: 当前模型
    - batch: 当前 batch 数据
    - intermediates: dict, key→名字, value→对应 Tensor
    """
    LOGGER.error("🔍 Detected NaN/Inf, aborting training and dumping diagnostics...")

    # 1) 打印 batch 数据中非有限值情况
    for name in ['pos', 'x']:
        if hasattr(batch, name):
            data = getattr(batch, name)
            if isinstance(data, torch.Tensor):
                cnt = int((~torch.isfinite(data)).sum().item())
                LOGGER.error(f" Batch.{name} non-finite count: {cnt}")

    # 2) 打印模型参数中非有限值
    for n, p in model.named_parameters():
        if p is None: continue
        cnt = int((~torch.isfinite(p.data)).sum().item())
        if cnt:
            LOGGER.error(f" PARAM {n} non-finite elements: {cnt}")

    # 3) 打印中间张量
    for n, t in intermediates.items():
        if isinstance(t, torch.Tensor):
            cnt = int((~torch.isfinite(t)).sum().item())
            LOGGER.error(f" Intermediate '{n}' non-finite elements: {cnt}")

    # 直接退出
    sys.exit(1)

class OnlyStableWrapper(torch.utils.data.Dataset):
    """去掉 trajectory，只保留稳定构象数据。"""
    def __init__(self, base): self.base = base
    def __len__(self):  return len(self.base)
    def __getitem__(self, i):
        d = self.base[i]
        if hasattr(d, 'trajectory'): delattr(d, 'trajectory')
        return d

class EnergyFilteredDataset(Subset):
    """仅保留 energy ≤ 0 的样本（可按需修改阈值）"""
    def __init__(self, base):
        kept = [i for i in range(len(base)) if base[i].energy <= 0]
        super().__init__(base, kept)
        if get_debug_flag():
            LOGGER.debug("Filtered energy ≤0: kept %d / %d", len(kept), len(base))

class DomainWrapperDataset(torch.utils.data.Dataset):
    """向 Data 对象附加 domain_id 张量，供下游 MoE 路由（若需要）"""
    def __init__(self, base, domain_id:int):
        self.base = base; self.did = int(domain_id)
    def __len__(self): return len(self.base)
    def __getitem__(self, idx):
        d = self.base[idx]
        d.domain_id = torch.tensor([self.did], dtype=torch.long)
        return d


class MaskedPerturbDataset(torch.utils.data.Dataset):
    """对所有样本做破坏性扰动，同时保留原始目标用于去噪学习。"""
    def __init__(self, base, cfg: DegradeConfig, seed: int = 114):
        self.base = base
        self.cfg = cfg.finalize()
        self.seed = int(seed)
    def __len__(self): return len(self.base)
    def __getitem__(self, idx):
        d0 = self.base[idx]
        # 记录原始目标（干净样本）
        clean_x = d0.x.clone() if hasattr(d0, 'x') else None
        clean_pos = d0.pos.clone() if hasattr(d0, 'pos') else None
        # 扰动输入（用于 Encoder）
        g = torch.Generator(device=d0.x.device if d0.x.is_cuda else 'cpu').manual_seed(self.seed + idx)
        d = degrade_once(d0, self.cfg, g)
        if clean_x is not None:
            d.target_x = clean_x
        if clean_pos is not None:
            d.target_pos = clean_pos
        # print('clean_x:',clean_x,'clean_pos:',clean_pos)
        # 清理与旧可行性/负样本相关的字段（不再使用）
        for attr in ("is_feasible", "neg_type"):
            if hasattr(d, attr):
                delattr(d, attr)
        return d

def standardizer(ds_list, ratio=0.01, cap=50000, seed=0):
    rng = np.random.default_rng(seed)
    pool = []
    for ds in ds_list:
        n = len(ds)
        if n <= 0:
            LOGGER.warning(
                "standardizer: skip empty dataset (%s)",
                getattr(ds, 'source_path', type(ds).__name__)
            )
            continue
        # ratio 可能 > 1 或 <= 0；这里做一次稳健裁剪
        if ratio <= 0:
            k = 0
        else:
            k = max(1, int(n * ratio))
        k = min(k, n)
        if k <= 0:
            continue
        idx = rng.choice(n, k, replace=False)
        pool.extend((ds, int(i)) for i in idx)
    if not pool:
        raise ValueError(
            "standardizer got zero samples: all datasets are empty after filtering, "
            "or ratio/cap is too small."
        )
    rng.shuffle(pool)
    pool = pool[:cap]
    sE=sQ=s2E=s2Q=cE=cQ=0.
    for ds,i in tqdm(pool, desc='Std'):
        d=ds[i]; sE+=d.energy; s2E+=d.energy**2; cE+=1
        if hasattr(d,'y'):
            q=d.y.view(-1); m=torch.ones_like(q)
            if hasattr(d,'charge_mask'): m=d.charge_mask.view(-1)
            q=q[m>0]
            sQ+=q.sum().item(); s2Q+=(q**2).sum().item(); cQ+=len(q)
    if cE <= 0:
        raise ValueError("standardizer: no valid samples collected for energy stats")
    muE=sE/cE; stdE=math.sqrt(max(s2E/cE-muE**2,1e-12))
    if cQ > 0:
        muQ=sQ/cQ; stdQ=math.sqrt(max(s2Q/cQ-muQ**2,1e-12))
    else:
        muQ=0.0; stdQ=1.0
        LOGGER.warning("standardizer: no charge targets found; fallback muQ=0 stdQ=1")

    LOGGER.info("Energy μ=%.3f σ=%.3f | Charge μ=%+.2e σ=%.2e",
                muE,stdE,muQ,stdQ)
    return dict(muE=muE, stdE=stdE, muQ=muQ, stdQ=stdQ)

# ───── 局部几何索引 (边 / 角 / 二面角) ───────────────────────────────
def build_local_graph(pos, batch_vec, cutoff, angle_sum_tolerance=10.0):
    e_idx = radius_graph(pos, r=cutoff, batch=batch_vec, loop=False)
    if e_idx.numel()==0:
        Z = pos.new_zeros((0,), dtype=torch.long)
        return (e_idx, Z.view(0,3), Z.view(0,4), Z.view(0,4))

    adj=[[] for _ in range(pos.size(0))]
    i,j=e_idx
    for a,b in zip(i.tolist(), j.tolist()):
        adj[a].append(b); adj[b].append(a)

    ang=[]
    for j_, nb in enumerate(adj):
        if len(nb)<2: continue
        for x in range(len(nb)):
            for y in range(x+1,len(nb)):
                ang.append([nb[x], j_, nb[y]])
    angle_triplet = (pos.new_tensor(ang,dtype=torch.long)
                     if ang else pos.new_empty((0,3),dtype=torch.long))
    
    dih=[]
    for i_, j_, k_ in angle_triplet.tolist():
        for l_ in adj[k_]:
            if l_!=j_ and l_!=i_:
                dih.append([i_, j_, k_, l_])
    dihed_quad = (pos.new_tensor(dih,dtype=torch.long)
                  if dih else pos.new_empty((0,4),dtype=torch.long))

    improper = []
    if angle_triplet.numel() > 0:
        all_angles_cos = angle_cos(pos, angle_triplet)
        center_to_angles_map = {}
        for idx, triplet in enumerate(angle_triplet.tolist()):
            center_node = triplet[1]
            if center_node not in center_to_angles_map:
                center_to_angles_map[center_node] = []
            center_to_angles_map[center_node].append(all_angles_cos[idx])

        for j_center, neighbors in enumerate(adj):
            if len(neighbors) == 3:
                if j_center in center_to_angles_map:
                    cos_vals = center_to_angles_map[j_center]
                    if len(cos_vals) == 3:
                        angles_rad = [torch.acos(c.clamp(-1.0, 1.0)) for c in cos_vals]
                        angle_sum_deg = torch.rad2deg(sum(angles_rad))
                        
                        if abs(angle_sum_deg - 360.0) < angle_sum_tolerance:
                            i_nb, k_nb, l_nb = neighbors[0], neighbors[1], neighbors[2]
                            improper.append([i_nb, k_nb, j_center, l_nb])
                            improper.append([k_nb, l_nb, j_center, i_nb])
                
    improper_quad = (pos.new_tensor(improper, dtype=torch.long)
                     if improper else pos.new_empty((0,4), dtype=torch.long))

    return e_idx, angle_triplet, dihed_quad, improper_quad

def planar_loss(coords_pred, coords_true, idx):
    """
    计算伪扭转角的监督学习损失。
    比较预测结构和真实结构下，伪扭转角的sin值。
    """
    sin_pred, _ = torsion_sin_cos(coords_pred, idx)
    sin_true, _ = torsion_sin_cos(coords_true, idx)
    
    # 使用Smooth L1 Loss，它对异常值更不敏感，更稳健
    return F.smooth_l1_loss(sin_pred, sin_true)

def angle_cos(coords, idx):
    v1 = coords[idx[:,0]] - coords[idx[:,1]]
    v2 = coords[idx[:,2]] - coords[idx[:,1]]
    return F.cosine_similarity(v1, v2, dim=-1)

def torsion_sin_cos(coords, idx):
    i,j,k,l = idx.t()
    b0 = coords[i]-coords[j]
    b1 = coords[k]-coords[j]
    b2 = coords[l]-coords[k]
    b1n = F.normalize(b1, dim=-1)
    v = b0 - (b0*b1n).sum(-1,keepdim=True)*b1n
    w = b2 - (b2*b1n).sum(-1,keepdim=True)*b1n
    x = (v*w).sum(-1)
    y = (torch.cross(b1n,v)*w).sum(-1)
    r = (x**2 + y**2 + 1e-9).sqrt()
    return y/r, x/r    # sinφ, cosφ

def _kabsch_torch(P: torch.Tensor, Q: torch.Tensor):
    """
    rigid-body optimal rotation  —  torch 版 Kabsch
    P,Q : (N,3) already centered
    """
    dtype = P.dtype
    with torch.cuda.amp.autocast(enabled=False):
        P, Q = P.float(), Q.float()
        C = P.T @ Q
        U, _, Vt = torch.linalg.svd(C, full_matrices=False)
        R = Vt.T @ U.T
        if torch.det(R) < 0:            # reflection correction
            Vt[-1] *= -1
            R = Vt.T @ U.T
        return R.to(dtype)

def _rmsd_pair(P: torch.Tensor, Q: torch.Tensor) -> torch.Tensor:
    """
    minimal RMSD between two point sets (mask 已经筛好)
    """
    Pc, Qc = P.mean(0, keepdim=True), Q.mean(0, keepdim=True)
    P0, Q0 = P - Pc, Q - Qc
    R = _kabsch_torch(P0, Q0)
    diff = P0 @ R - Q0
    return diff.pow(2).mean().sqrt()    # scalar tensor

# ───── 索引映射：flat (全局拼接) -> dense (B[*T], Nmax) ─────────────────────────
def _map_global_to_dense_indices(idx: torch.Tensor,
                                 batch_vec: torch.Tensor,
                                 Nmax: int,
                                 num_graphs: int,
                                 num_frames: int = 1) -> torch.Tensor:
    """
    把 build_local_graph 返回的“全局节点索引” (idx: [M, k]) 映射到
    coords_pred.view(-1, 3) 可用的“密排索引”（(B[*T], Nmax) 展平）上。

    参数
    ----
    idx        : LongTensor [M, k]，例如三元组/四元组
    batch_vec  : LongTensor [ΣN]，PyG 的 batch 向量，指出每个全局节点属于哪个图 b∈[0,B)
    Nmax       : int，to_dense_batch 得到的最大节点数
    num_graphs : int，B
    num_frames : int，若是 TS 模型则等于 T，否则为 1

    返回
    ----
    dense_idx  : LongTensor [M' = M * num_frames, k]，可安全用于 coords_pred.view(-1,3)
    """
    device = batch_vec.device
    idx = idx.to(device)
    flat = idx.reshape(-1)  # [M*k]
    # 每个图的节点数（按 PyG Batch 拼接顺序）
    counts = torch.bincount(batch_vec, minlength=num_graphs)  # [B]
    offsets = torch.cumsum(
        torch.cat([counts.new_zeros(1), counts[:-1]]), dim=0
    )  # [B]
    b = batch_vec[flat]                 # [M*k]
    local = flat - offsets[b]           # [M*k]，每个图内的局部下标
    dense = (b * Nmax + local).view_as(idx)  # [M, k]，对应于 frame=0

    if num_frames == 1:
        return dense

    # TS：把每一帧的偏移量叠加后拼接
    per_frame_stride = num_graphs * Nmax
    dense_list = [dense + t * per_frame_stride for t in range(num_frames)]
    return torch.cat(dense_list, dim=0)  # [M*T, k]


# ───── 纯预测/真实“索引空间不同”的平面性损失（伪扭转角） ─────────────────────────
def planar_loss_mixed(coords_pred_dense: torch.Tensor,
                      coords_true_flat: torch.Tensor,
                      idx_dense: torch.Tensor,
                      idx_global: torch.Tensor) -> torch.Tensor:
    """
    预测端 coords_pred_dense 走 dense 索引；真实端 coords_true_flat 走 global 索引。
    避免把 global 索引误用在 (B[*T], Nmax) 密排的预测张量上。
    """
    sin_pred, _ = torsion_sin_cos(coords_pred_dense, idx_dense)
    sin_true, _ = torsion_sin_cos(coords_true_flat, idx_global)
    return F.smooth_l1_loss(sin_pred, sin_true)

def batch_rmsd(pred, true, mask, *, sample_ratio: float = 1.0):
    """
    pred/true : (B,N,3) ; mask : (B,N) bool / float
    返回 (rmsd_sum, n_sample) 方便后续加权平均
    """
    rmsd_sum = 0.0
    n_sample = 0
    B = pred.size(0)
    rand = torch.rand(B, device=pred.device)
    for b in range(B):
        if sample_ratio < 1.0 and rand[b] > sample_ratio:
            continue
        m = mask[b] > 0
        if m.sum() < 3:
            continue
        rmsd_val = _rmsd_pair(pred[b, m], true[b, m])
        rmsd_sum += rmsd_val.item()
        n_sample += 1
    return rmsd_sum, n_sample

def morse_energy(d_pred, d_true, D=1.0, a=1.0, clip=20.0):
    diff = (d_pred - d_true).clamp(-clip, clip)
    return D * (1 - safe_exp(-a * diff / (d_true + 1e-4)))**2
# ――――――――――――――――― LR scheduler ―――――――――――――――――
def build_lr_scheduler(optim, total_steps, warmup_steps):
    def lr_lambda(step):
        if step < warmup_steps:
            return step / max(1, warmup_steps)
        prog = (step - warmup_steps) / max(1, total_steps - warmup_steps)
        prog = min(prog, 1.0)
        return 0.5 * (1.0 + math.cos(math.pi * prog))
    return LambdaLR(optim, lr_lambda)

def fast_collate(data_list):
    """
      把 Data 合并成 Batch 后，去掉 angle/dihed tensor，主进程再即时重算
      可把单分子 5-20 MB 的 int64 索引降到 <1 MB
    """
    for d in data_list:
        keys = list(d.keys()) if hasattr(d, "keys") else []
        if hasattr(d, "angle_triplet"): delattr(d, "angle_triplet")
        if hasattr(d, "dihed_quad"):    delattr(d, "dihed_quad")
        for key in keys:
            if key in LEGACY_COLLATE_DROP_FIELDS or key.startswith(LEGACY_COLLATE_DROP_PREFIXES):
                delattr(d, key)
    return Batch.from_data_list(data_list)

# DummyScaler (当未启用 fp16 时复用接口)
class DummyScaler:
    def scale(self, loss):   return loss
    def unscale_(self, opt): pass
    def step(self, opt):     opt.step()
    def update(self):        pass

# ─────────────────────── train / val ───────────────────────
# ==============================================================================
#  run_epoch 函数
# ==============================================================================
def run_epoch(model, loader, device, std, scaler, *,
              loss_cutoff, n_atom_types,
              lam_c, lam_d, lam_a, lam_t, lam_p,
              lam_e, lam_q, lam_z,
              z_label_smooth,
              z_focal_gamma,
              z_temp, z_class_balance, z_entropy_reg, z_logit_l2,
              morse_D, morse_a,
              graph_cutoff=2.0,
              optim=None, fp16=False,
              desc='Train', scheduler=None):
    train = optim is not None
    model.train(train)

    stats = dict(
        E=0., Q=0., Z=0.,
        Geom=0., Geom_c=0., Geom_d=0., Geom_a=0., Geom_t=0., Geom_p=0.,
        RMSD=0., RMSD_n=0,          # ← 新增
        Bal=0., B=0, bad=0,
        R2_e=0., R2_q=0., R2_z=0., Acc_z=0.
    )

    for batch in tqdm(loader, desc=desc, leave=False):
        batch = batch.to(device)
        if train:
            optim.zero_grad(set_to_none=True)

        with autocast(enabled=fp16):
            coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, bal = model(batch)
            B, Nmax, _ = coords_pred.shape
            charge_mask_f = charge_mask.squeeze(-1)
            if stats['B'] == 0:
                LOGGER.info(
                    "First batch outputs: coords=%s charge=%s elem=%s energy=%s mask=%s",
                    tuple(coords_pred.shape), tuple(charge_pred.shape), tuple(elem_pred.shape),
                    tuple(energy_pred.shape), tuple(charge_mask.shape),
                )
            # ----- Z / 元素分类 -----
            pad_idx = getattr(model, 'pad_elem_index', getattr(model, 'n_elem_classes', n_atom_types) - 1)
            elem_source = batch.target_x if hasattr(batch, 'target_x') else batch.x
            elem_true_pad, _ = to_dense_batch(elem_source[:, 0].long(), batch.batch, fill_value=pad_idx)
            C = elem_pred.size(-1)
            elem_logits_flat = elem_pred.reshape(-1, C)
            elem_true_flat   = elem_true_pad.view(-1)

            # a) 温度：用更“软”的 logits 参与损失，缓解过度自信
            T = max(1.0, float(z_temp))
            logits_T = elem_logits_flat / T

            # b) 类别权重（可选）
            weights = None
            if z_class_balance != 'none':
                with torch.no_grad():
                    valid = (elem_true_flat != pad_idx)
                    yv = elem_true_flat[valid]
                    hist = torch.bincount(yv, minlength=C).float()
                    if z_class_balance == 'batch_inv':
                        w = 1.0 / (hist + 1e-6)
                    else:  # effective number of samples
                        beta = 0.999
                        eff = (1.0 - torch.pow(beta, hist)) / (1.0 - beta)
                        w = 1.0 / (eff + 1e-6)
                    w[pad_idx] = 0.0
                    w = (w / (w.sum() + 1e-6)) * C    # 归一到均值≈1
                    weights = w.to(elem_logits_flat.device)

            # c) 主 CE（保留你原有的三分支）
            if z_label_smooth > 0:
                ce_all = F.cross_entropy(
                    logits_T, elem_true_flat, weight=weights,
                    ignore_index=pad_idx, reduction='none',
                    label_smoothing=z_label_smooth)
            elif z_focal_gamma > 0:
                ce_raw = F.cross_entropy(
                    logits_T, elem_true_flat, weight=weights,
                    ignore_index=pad_idx, reduction='none')
                p_t = torch.exp(-ce_raw)
                ce_all = (1 - p_t) ** z_focal_gamma * ce_raw
            else:
                ce_all = F.cross_entropy(
                    logits_T, elem_true_flat, weight=weights,
                    ignore_index=pad_idx, reduction='none')

            mask_f = (elem_true_flat != pad_idx).float()
            loss_z = (ce_all * mask_f).sum() / mask_f.sum().clamp(min=1.)

            # d) 置信度惩罚：鼓励较高熵（防止 logits 过度尖锐）
            if z_entropy_reg > 0:
                with torch.no_grad():  # 只用于分布计算，不阻断梯度
                    p_T = F.softmax(logits_T, dim=-1)
                entropy = -(p_T * (p_T.clamp_min(1e-12)).log()).sum(-1)
                loss_conf = (-entropy * mask_f).sum() / mask_f.sum().clamp(min=1.)
                loss_z = loss_z + z_entropy_reg * loss_conf

            # e) Logit-L2：直接限制 logits 的幅值
            if z_logit_l2 > 0:
                loss_z = loss_z + z_logit_l2 * ( (elem_logits_flat[mask_f.bool()]**2).mean() )


            y_e = ((batch.energy.view(-1, 1, 1) - std['muE']) / std['stdE']).to(device)
            p_e = (energy_pred - std['muE']) / std['stdE']
            if lam_e > 0:
                loss_e = F.mse_loss(p_e, y_e, reduction='none')
                loss_e = loss_e.mean()
            else:
                loss_e = torch.tensor(0., device=device)

            if hasattr(batch, 'y'):
                charge_true_pad, _ = to_dense_batch(batch.y, batch.batch, fill_value=0.)
                charge_true_std = ((charge_true_pad - std['muQ']) / std['stdQ']).to(device)
                charge_pred_std = (charge_pred - std['muQ']) / std['stdQ']
                loss_q = F.mse_loss(charge_pred_std * charge_mask, charge_true_std * charge_mask, reduction='none')
                loss_q = loss_q.sum() / charge_mask.sum().clamp(min=1.)
            else:
                loss_q = torch.tensor(0., device=device)
            
            pos_source = batch.target_pos if hasattr(batch, 'target_pos') else batch.pos
            true_xyz_pad, _ = to_dense_batch(pos_source, batch.batch)
            geom_mask = charge_mask_f.float()
            
            loss_c = torch.tensor(0., device=device)
            loss_d = torch.tensor(0., device=device)
            loss_a = torch.tensor(0., device=device)
            loss_t = torch.tensor(0., device=device)
            loss_p = torch.tensor(0., device=device)

            if lam_c > 0:
                coord_se = ((coords_pred - true_xyz_pad)**2).sum(-1) * geom_mask
                loss_c = coord_se.sum() / geom_mask.sum().clamp(min=1.)

            if lam_d > 0:
                dp = torch.cdist(coords_pred, coords_pred)
                dt = torch.cdist(true_xyz_pad, true_xyz_pad)
                pm = geom_mask[:, :, None] * geom_mask[:, None, :]
                V = morse_energy(dp, dt, morse_D, morse_a) * pm
                morse_per_atom = torch.log1p(V.sum(-1).clamp(min=0.)) * geom_mask
                loss_d = morse_per_atom.sum() / geom_mask.sum().clamp(min=1.)

            if (lam_a > 0 or lam_t > 0 or lam_p > 0):
                flat_pos_true = pos_source
                batch_vec = batch.batch
                _, angle_triplet, dihed_quad, improper_quad = build_local_graph(flat_pos_true, batch_vec, graph_cutoff)

                # ─── 预测张量的形状信息（兼容普通与 TS 模型）
                BT, Nmax, _ = coords_pred.shape                      # coords_pred: (B[*T], Nmax, 3)
                B = int(batch_vec.max().item() + 1)
                T = max(1, BT // B)                                  # 若 TS，BT = B*T；否则 T=1

                # 仅当需要这些项时再做映射与计算
                if lam_a > 0 and angle_triplet.numel():
                    # 只基于“真实坐标”做 cutoff 过滤（仍在 global 空间）
                    i, j, k = angle_triplet.t()
                    dij = (flat_pos_true[i] - flat_pos_true[j]).norm(dim=-1)
                    djk = (flat_pos_true[j] - flat_pos_true[k]).norm(dim=-1)
                    keep = (dij < loss_cutoff) & (djk < loss_cutoff)
                    if keep.any():
                        ang_idx_global = angle_triplet[keep]  # [M,3], global 空间
                        # 把 global -> dense；若 TS，则复制到每一帧并加上帧偏移
                        ang_idx_dense  = _map_global_to_dense_indices(
                            ang_idx_global, batch_vec, Nmax, num_graphs=B, num_frames=T
                        )  # [M*T,3] 或 [M,3]
                        # 预测端用 dense 索引；真实端用 global 索引
                        cp = angle_cos(coords_pred.view(-1, 3), ang_idx_dense)        # [M*T] or [M]
                        ct = angle_cos(flat_pos_true,           ang_idx_global)       # [M]
                        if T > 1:
                            ct = ct.repeat(T)  # 真实角复制 T 份，与预测逐帧对齐
                        loss_a = F.smooth_l1_loss(cp, ct)

                if lam_t > 0 and dihed_quad.numel():
                    i, j, k, l = dihed_quad.t()
                    # 用真实坐标做邻近性过滤（可按你的偏好改成 1-3/1-4 等更细规则）
                    dij = (flat_pos_true[i] - flat_pos_true[j]).norm(dim=-1)
                    djk = (flat_pos_true[j] - flat_pos_true[k]).norm(dim=-1)
                    dkl = (flat_pos_true[k] - flat_pos_true[l]).norm(dim=-1)
                    keep = (dij < loss_cutoff) & (djk < loss_cutoff) & (dkl < loss_cutoff)
                    if keep.any():
                        dih_idx_global = dihed_quad[keep]  # [M,4]
                        dih_idx_dense  = _map_global_to_dense_indices(
                            dih_idx_global, batch_vec, Nmax, num_graphs=B, num_frames=T
                        )  # [M*T,4] or [M,4]
                        # 预测端（dense）
                        sp, cp = torsion_sin_cos(coords_pred.view(-1, 3), dih_idx_dense)
                        # 真实端（global）
                        st, ct = torsion_sin_cos(flat_pos_true,              dih_idx_global)
                        if T > 1:
                            st = st.repeat(T); ct = ct.repeat(T)
                        loss_t = F.smooth_l1_loss(sp, st) + F.smooth_l1_loss(cp, ct)

                if lam_p > 0 and improper_quad.numel():
                    i, k, j, l = improper_quad.t()  # 你原始实现的顺序
                    dist_ij = (flat_pos_true[i] - flat_pos_true[j]).norm(dim=-1)
                    dist_kj = (flat_pos_true[k] - flat_pos_true[j]).norm(dim=-1)
                    dist_lj = (flat_pos_true[l] - flat_pos_true[j]).norm(dim=-1)
                    keep = (dist_ij < loss_cutoff) & (dist_kj < loss_cutoff) & (dist_lj < loss_cutoff)
                    if keep.any():
                        imp_idx_global = improper_quad[keep]  # [M,4]
                        imp_idx_dense  = _map_global_to_dense_indices(
                            imp_idx_global, batch_vec, Nmax, num_graphs=B, num_frames=T
                        )  # [M*T,4] or [M,4]
                        loss_p = planar_loss_mixed(
                            coords_pred.view(-1, 3),  # dense 空间
                            flat_pos_true,            # global 空间
                            imp_idx_dense,            # dense 索引
                            imp_idx_global            # global 索引
                        )

            loss_geom = lam_c * loss_c + lam_d * loss_d + lam_a * loss_a + lam_t * loss_t + lam_p * loss_p

            if detect_nan_inf(loss_geom) or detect_nan_inf(loss_e) or detect_nan_inf(loss_q) or detect_nan_inf(loss_z):
                analyze_and_abort(model, batch, dict(loss_geom=loss_geom, loss_e=loss_e, loss_q=loss_q, loss_z=loss_z))
            
            loss_tot = lam_e * loss_e + lam_q * loss_q + lam_z * loss_z + loss_geom + bal

        if torch.isnan(loss_tot) or torch.isinf(loss_tot):
            raise ValueError('NaN/Inf loss')

        if train:
            scaler.scale(loss_tot).backward()
            scaler.unscale_(optim)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(optim)
            scaler.update()
            if scheduler is not None:
                scheduler.step()

        g = batch.num_graphs
        with torch.no_grad():
            et = batch.energy.view(-1).cpu().numpy()
            ep = energy_pred.view(-1).detach().cpu().numpy()
            mask_e = np.isfinite(et) & np.isfinite(ep)
            r2_energy = r2_score(et[mask_e], ep[mask_e]) if mask_e.sum() > 1 else float('nan')

            qt = charge_true_pad.view(-1).cpu().numpy()
            qp = charge_pred.view(-1).detach().cpu().numpy()
            qm = charge_mask_f.view(-1).cpu().numpy().astype(bool)
            mask_q = np.isfinite(qt) & np.isfinite(qp) & qm
            r2_charge = r2_score(qt[mask_q], qp[mask_q]) if mask_q.sum() > 1 else float('nan')
            
            zt = elem_true_pad.view(-1).cpu().numpy()
            zp = elem_pred.argmax(-1).view(-1).detach().cpu().numpy()
            mask_z = (zt != pad_idx)
            if mask_z.sum() > 1:
                r2_elem  = r2_score(zt[mask_z], zp[mask_z])
                acc_elem = float((zp[mask_z] == zt[mask_z]).mean())
            else:
                r2_elem, acc_elem = float('nan'), float('nan')

            # --- RMSD 统计 ---
            sample_ratio = 0.1 if train else 1.0    # 训练抽 1% ，验证全算
            rmsd_sum, rmsd_cnt = batch_rmsd(
                    coords_pred.detach(), true_xyz_pad.detach(),
                    geom_mask.detach(), sample_ratio=sample_ratio)
            
            stats['RMSD']   += rmsd_sum
            stats['RMSD_n'] += rmsd_cnt
            stats['B']    += g
            stats['E']    += loss_e.item() * g
            stats['Q']    += loss_q.item() * g
            stats['Z']    += loss_z.item() * g
            stats['Bal']  += bal.item() * g
            stats['Geom']   += loss_geom.item() * g
            stats['Geom_c'] += loss_c.item() * g
            stats['Geom_d'] += loss_d.item() * g
            stats['Geom_a'] += loss_a.item() * g
            stats['Geom_t'] += loss_t.item() * g
            stats['Geom_p'] += loss_p.item() * g
            
            stats['R2_e'] += (0.0 if math.isnan(r2_energy) else r2_energy) * g
            stats['R2_q'] += (0.0 if math.isnan(r2_charge) else r2_charge) * g
            stats['R2_z'] += (0.0 if math.isnan(r2_elem) else r2_elem) * g
            stats['Acc_z']+= (0.0 if math.isnan(acc_elem) else acc_elem) * g
            
    if stats['RMSD_n'] > 0:
        stats['RMSD'] /= stats['RMSD_n']
    else:
        stats['RMSD'] = float('nan')
    denom = max(1, stats['B'])
    for k in ['E', 'Q', 'Z', 'Geom', 'Geom_c', 'Geom_d', 'Geom_a', 'Geom_t', 'Geom_p', 'Bal', 'R2_e', 'R2_q', 'R2_z', 'Acc_z']:
        stats[k] /= denom

    return stats

def save_checkpoint(model, cfg, std, save_path):
    """Save unified checkpoint for the refactored MultiTaskMoE."""
    save_dir = os.path.dirname(save_path)
    if save_dir:
        os.makedirs(save_dir, exist_ok=True)
    torch.save(
        {
            'cfg': cfg,
            'model_state': {k: v.cpu() for k, v in model.state_dict().items()},
            'standardizer': std,
        },
        save_path,
    )

# ─────────────────────────── main ──────────────────────────
def main():
    args = get_args(); set_seed(args.seed)
    device = 'cuda' if torch.cuda.is_available() else 'cpu'

    # ----- 填充索引 -----
    starts     = pad_list(args.starts,     len(args.data_roots), 0)
    ends       = pad_list(args.ends,       len(args.data_roots), None)
    val_starts = pad_list(args.val_starts, len(args.val_data_roots), 0)
    val_ends   = pad_list(args.val_ends,   len(args.val_data_roots), None)

    # ----- 构建数据集 ------------------------------------------------
    train_list, val_list = [], []
    std_bases = []

    def _build_cfg(mode: str, level: float) -> DegradeConfig:
        return DegradeConfig(
            mode=mode,
            level=level,
            topo_replace_frac=args.perturb_replace_frac,
            topo_delete_frac=0.0,
            geom_noise_std=args.perturb_noise_std,
            geom_angle_std_deg=0.0,
            geom_bond_scale_std=0.0,
        )

    def parse_perturb_mix(spec: str, base_len: int, base_seed: int):
        """
        解析格式： "topo:0.3@0.2,geom:0.5@0.5,both:0.7@1.0"
          - mode ∈ {topo, geom, both}
          - level ∈ [0,1]
          - ratio >= 0  表示相对正样本数量的比例
        返回: List[(mode, level, ratio, seed)]
        """
        out = []
        for j, seg in enumerate([s for s in spec.split(",") if s.strip()]):
            if seg.lower() == "none":
                continue
            if ":" not in seg or "@" not in seg:
                continue
            mode, rest = seg.split(":", 1)
            lvl_str, rat_str = rest.split("@", 1)
            mode = mode.strip().lower()
            if mode not in ("topo", "geom", "both"):
                continue
            level = float(lvl_str)
            ratio = float(rat_str)
            out.append((mode, level, ratio, base_seed + 10000 * j))
        return out

    def build_perturb_parts(base_dataset, mix_specs, seed_base):
        parts = []
        for mode, level, ratio, seed in mix_specs:
            cfg = _build_cfg(mode, level)
            pert_base = MaskedPerturbDataset(base_dataset, cfg, seed=seed_base + seed)
            K = int(ratio)
            R = float(ratio) - K
            parts.extend([pert_base] * K)
            if R > 1e-8:
                take = max(1, int(len(base_dataset) * R))
                parts.append(Subset(pert_base, list(range(take))))
        return parts
    
    for did, (pth, s, e) in enumerate(zip(args.data_roots, starts, ends)):
        base_raw = OnlyStableWrapper(create_dataset(pth, s, e))
        if len(base_raw) == 0:
            LOGGER.warning("Skip empty dataset root: %s (start=%s end=%s)", pth, s, e)
            continue
        std_bases.append(base_raw)
        if getattr(args, "perturb_mix", "none") not in (None, "none"):
            specs = parse_perturb_mix(args.perturb_mix, len(base_raw), args.perturb_seed + did * 100000)
            parts = build_perturb_parts(base_raw, specs, args.perturb_seed + did * 100000)
            if not parts:
                cfg = _build_cfg(args.perturb_mode, args.perturb_level)
                parts = [MaskedPerturbDataset(base_raw, cfg, seed=args.perturb_seed + did * 100000)]
        else:
            cfg = _build_cfg(args.perturb_mode, args.perturb_level)
            parts = [MaskedPerturbDataset(base_raw, cfg, seed=args.perturb_seed + did * 100000)]
        for part in parts:
            train_list.append(DomainWrapperDataset(part, did))

    for did, (pth, s, e) in enumerate(zip(args.val_data_roots, val_starts, val_ends), start=len(train_list)):
        base = OnlyStableWrapper(create_dataset(pth, s, e))
        if len(base) == 0:
            LOGGER.warning("Skip empty val dataset root: %s (start=%s end=%s)", pth, s, e)
            continue
        std_bases.append(base)
        if getattr(args, "perturb_mix", "none") not in (None, "none"):
            specs = parse_perturb_mix(args.perturb_mix, len(base), args.perturb_seed + 1000000 + did * 100000)
            parts = build_perturb_parts(base, specs, args.perturb_seed + 1000000 + did * 100000)
            if not parts:
                cfg = _build_cfg(args.perturb_mode, args.perturb_level)
                parts = [MaskedPerturbDataset(base, cfg, seed=args.perturb_seed + 1000000 + did * 100000)]
        else:
            cfg = _build_cfg(args.perturb_mode, args.perturb_level)
            parts = [MaskedPerturbDataset(base, cfg, seed=args.perturb_seed + 1000000 + did * 100000)]
        for part in parts:
            val_list.append(DomainWrapperDataset(part, did))

    # 训练集 = 扰动后的真实样本（Masked Modeling）
    train_ds = ConcatDataset(train_list)
    val_ds   = ConcatDataset(val_list) if val_list else None
    
    # ----- DataLoader -------------------------------------------------
    def build_dataloader(dataset, shuffle, collate_fn=None):
        prefetch = 2 if args.num_workers > 0 else None
        return DataLoader(
            dataset,
            batch_size=args.batch_size,
            shuffle=shuffle,
            num_workers=args.num_workers,
            pin_memory=True,
            persistent_workers=False,   # 防止长期泄漏
            prefetch_factor=prefetch,
            collate_fn=collate_fn,      # <── 新增
        )

    train_loader = build_dataloader(train_ds, shuffle=True,  collate_fn=fast_collate)
    val_loader = None
    if val_ds:
        val_loader = build_dataloader(val_ds,   shuffle=False, collate_fn=fast_collate)

    # ----- 标准化抽样比例 --------------------------------------------
    # 取首个子数据集的大小 (DomainWrapperDataset -> .base -> EnergyFilteredDataset)
    first_base_len = len(std_bases[0])
    ratio = 1.0 if first_base_len < 10000 else (0.1 if first_base_len < 100000 else 0.01)
    std = standardizer(std_bases, ratio=ratio, cap=10000, seed=args.seed)

    # ----- 构建模型 -----
    bb_cfg = dict(
        hidden_channels=args.hidden_channels,
        atom_embedding_dim=args.hidden_channels,
        bb_layers=args.bb_layers,
        bb_heads=args.bb_heads,
        bb_ff_mult=args.bb_ff_mult,
        bb_use_dist_bias=args.bb_use_dist_bias,
        bb_use_radius_mask=args.bb_use_radius_mask,
        bb_radius=args.bb_radius,
    )
    LOGGER.info('启用稳态模型MultiTaskMoE (TS模式已移除)')
    model = MultiTaskMoE(
        bb_cfg,
        n_atom_types=args.n_atom_types,
        n_experts_energy=args.expert_number_E,
        n_experts_charge=args.expert_number_Q,
        n_experts_geom=args.expert_number_G,
        n_experts_elem=args.expert_number_Z,
        top_k_energy=args.topkE,
        top_k_charge=args.topkQ,
        top_k_geom=args.topkG,
        top_k_elem=args.topkZ,
        expert_real_layers=args.expert_real_layers,
        expert_int_layers=args.expert_int_layers,
        expert_heads=args.expert_heads,
        expert_ff_mult=args.expert_ff_mult,
    ).to(device)

    decay, no_decay = [], []
    for n, p in model.named_parameters():
        (no_decay if n.endswith('bias') or 'norm' in n.lower() else decay).append(p)
    optimizer = torch.optim.AdamW(
        [{'params': decay, 'weight_decay': 0.01}, {'params': no_decay, 'weight_decay': 0.0}],
        lr=args.lr,
        betas=(0.9, 0.95),
        eps=1e-8,
    )
    scaler = GradScaler(init_scale=2**8) if args.fp16 else DummyScaler()

    total_steps  = len(train_loader) * args.epochs
    warm_steps   = int(total_steps * args.warmup_pct)
    scheduler    = build_lr_scheduler(optimizer, total_steps, warm_steps)

    autoλ  =  {'coord': args.lambda_coord, 
            'dist' : args.lambda_dist,
            'angle': args.lambda_angle,
            'torsion': args.lambda_torsion}

    # ----- 训练循环 -----
    best_loss = float('inf')
    stage = 0
    stage_ep = 0
    LOGGER.info("训练开始：Stage-0 (仅键长损失)")

    for ep in range(1, args.epochs + 1):
        # 课程学习：分阶段激活不同的几何损失
        if stage == 0:
            active = ('dist',)
        elif stage == 1:
            active = ('dist', 'angle', 'torsion', 'planar')

        def λ(name):
            return getattr(args, f'lambda_{name}', 0.0) if name in active else 0.0

        lam_c = λ('coord')
        lam_d = λ('dist')
        lam_a = λ('angle')
        lam_t = λ('torsion')
        lam_p = λ('planar') # 获取 lam_p

        LOGGER.info(f"Epoch {ep}, Stage {stage}: lam_c={lam_c}, lam_d={lam_d}, lam_a={lam_a}, lam_t={lam_t}, lam_p={lam_p}")
        
        tr = run_epoch(
            model, train_loader, device, std, scaler,
            loss_cutoff=args.loss_cutoff, n_atom_types=args.n_atom_types,
            lam_c=lam_c, lam_d=lam_d, lam_a=lam_a, lam_t=lam_t, lam_p=lam_p,
            lam_e=args.lambda_e, lam_q=args.lambda_q, lam_z=args.lambda_z,
            z_label_smooth=args.z_label_smooth,
            z_focal_gamma=args.z_focal_gamma,
            z_temp=args.z_temp, z_class_balance=args.z_class_balance, z_entropy_reg=args.z_entropy_reg, z_logit_l2=args.z_logit_l2,
            morse_D=args.morse_D, morse_a=args.morse_a,
            optim=optimizer, fp16=args.fp16,
            desc=f"Train{ep:03d}",
            scheduler=scheduler)
        
        # 更新训练日志打印
        print(
          f"Train E={tr['E']:.3f} Q={tr['Q']:.3f} Z={tr['Z']:.3f} | "
          f"Geom={tr['Geom']:.3f} (Coord={tr['Geom_c']:.4f} Morse={tr['Geom_d']:.4f} Ang={tr['Geom_a']:.4f} Tor={tr['Geom_t']:.4f} Planar={tr['Geom_p']:.4f})"
        )
        print(
          f"      R²(E={tr['R2_e']:.3f}, Q={tr['R2_q']:.3f}, Z={tr['R2_z']:.3f}), RMSD={tr['RMSD']:.3f} | "
          f"Acc(Z)={tr['Acc_z']:.3f} | Bad={tr['bad']}"
        )
        
        cfg = dict(
            backbone_config=bb_cfg, n_atom_types=args.n_atom_types,
                        n_experts_energy=args.expert_number_E, n_experts_charge=args.expert_number_Q,
            n_experts_elem=args.expert_number_Z, n_experts_geom=args.expert_number_G,
            top_k_energy=args.topkE, top_k_charge=args.topkQ,
            top_k_elem=args.topkZ, top_k_geom=args.topkG,
            expert_real_layers=args.expert_real_layers,
            expert_int_layers=args.expert_int_layers,
            expert_heads=args.expert_heads,
            expert_ff_mult=args.expert_ff_mult
        )

        if args.save_every_epoch:
            epoch_save_path = f'{args.save_path}_epoch_{ep:03d}.pt'
            save_checkpoint(model, cfg, std, epoch_save_path)
            LOGGER.info("Saved per-epoch ckpt to %s", epoch_save_path)

        torch.cuda.empty_cache()
        
        if val_loader:
            va = run_epoch(
                model, val_loader, device, std, scaler,
                loss_cutoff=args.loss_cutoff, n_atom_types=args.n_atom_types,
                lam_c=lam_c, lam_d=lam_d, lam_a=lam_a, lam_t=lam_t, lam_p=lam_p,
                lam_e=args.lambda_e, lam_q=args.lambda_q, lam_z=args.lambda_z,
                z_label_smooth=args.z_label_smooth,
                z_focal_gamma=args.z_focal_gamma,
                z_temp=args.z_temp, z_class_balance=args.z_class_balance, z_entropy_reg=args.z_entropy_reg, z_logit_l2=args.z_logit_l2,
                morse_D=args.morse_D, morse_a=args.morse_a,
                optim=None, fp16=args.fp16,
                desc=f"Val{ep:03d}",
                scheduler=None)
            
            # 更新验证日志打印
            print(
              f"Val   E={va['E']:.3f} Q={va['Q']:.3f} Z={va['Z']:.3f} | "
              f"Geom={va['Geom']:.3f} (Coord={va['Geom_c']:.4f} Morse={va['Geom_d']:.4f} Ang={va['Geom_a']:.4f} Tor={va['Geom_t']:.4f} Planar={va['Geom_p']:.4f})"
            )
            print(
              f"      R²(E={va['R2_e']:.3f}, Q={va['R2_q']:.3f}, Z={va['R2_z']:.3f}), RMSD={va['RMSD']:.3f} | "
              f"Acc(Z)={va['Acc_z']:.3f} | Bad={va['bad']}"
            )
            cur_loss = va['E'] + va['Q'] + va['Geom']
        else:
            cur_loss = tr['E'] + tr['Q'] + tr['Geom']

        if cur_loss < best_loss:
            best_loss = cur_loss
            save_checkpoint(model, cfg, std, args.save_path)
            LOGGER.info("↳ Saved best ckpt for stage %d to %s (loss=%.4f)",
                        stage, args.save_path, best_loss)

        stage_ep += 1
        stage_transition = False
        next_stage_log = ""
        
        # 更新阶段切换逻辑
        if stage == 0:
            cond = (tr['Geom'] < args.stage1_loss) or (stage_ep >= args.stage1_max_epochs)
            if cond:
                stage_transition = True
                next_stage = 1
                next_stage_log = f"→ 进入 Stage-1 (全部几何损失，包括平面性)"
        
        if stage_transition:
            LOGGER.info("Stage-%d finished at epoch %d.", stage, ep)
            stage_save_path = f'stage_{stage}_end_epoch_{ep}.pt'
            save_checkpoint(model, cfg, std, stage_save_path)
            LOGGER.info("Saved final model for stage %d to %s", stage, stage_save_path)
            
            best_loss = float('inf')
            LOGGER.info("Best loss reset to infinity for next stage.")
            
            stage = next_stage
            stage_ep = 0
            LOGGER.info(next_stage_log)

        
        torch.cuda.empty_cache()
        
if __name__ == '__main__':
    main()
