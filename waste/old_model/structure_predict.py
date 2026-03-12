#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
structure_predict.py
====================

Single-molecule / dataset inference script for the *refactored* MultiTaskMoE (no EGNN, no TS mode).

This script is aligned with:
- `pretrain_multitask.py` checkpoint format: {'cfg', 'model_state', 'standardizer'} (best/per-epoch/stage ckpts)
- `moe_transformer_multitask.py` forward signature:
    (coords_pred, charge_pred, elem_pred, energy_pred, charge_mask, balance_loss)

Key points vs older EGNN-era scripts
-----------------------------------
1) Load weights from `ckpt['model_state']` (fallbacks supported).
2) Instantiate `MultiTaskMoE` from `ckpt['cfg']` (backbone_config + MoE hyperparams).
3) Use a *node mask reconstructed from `data.x` + pad_idx* (NOT `charge_mask`) to avoid accidentally dropping atoms
   when `data.charge_mask` is sparse.

Outputs
-------
- XYZ export of predicted coordinates (and predicted element types if available).
- Optional metrics if ground truth is present (element accuracy, energy/charge errors, pairwise-distance MAE, RMSD).

Perturbation
------------
You can optionally degrade inputs using `degrade_molecules.degrade_once` to test robustness.
"""

from __future__ import annotations

import argparse
import logging
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
from torch.cuda.amp import autocast
from torch_geometric.data import Data
from torch_geometric.utils import to_dense_batch
from tqdm import tqdm

# ---- project imports ----
from moe_transformer_multitask import MultiTaskMoE
from dataset_infer import MoleculeDataset
from dataset_lmdb import LmdbMoleculeDataset
from degrade_molecules import DegradeConfig, degrade_once

LOGGER = logging.getLogger("structure_predict")


# ------------------------------ element mapping ------------------------------

# 0-based (Z-1) symbols; index 0 -> H. (pad is usually the last class index)
_ZMINUS1_SYMBOLS: List[str] = [
    "H","He","Li","Be","B","C","N","O","F","Ne",
    "Na","Mg","Al","Si","P","S","Cl","Ar","K","Ca",
    "Sc","Ti","V","Cr","Mn","Fe","Co","Ni","Cu","Zn",
    "Ga","Ge","As","Se","Br","Kr","Rb","Sr","Y","Zr",
    "Nb","Mo","Tc","Ru","Rh","Pd","Ag","Cd","In","Sn",
    "Sb","Te","I","Xe","Cs","Ba","La","Ce","Pr","Nd",
    "Pm","Sm","Eu","Gd","Tb","Dy","Ho","Er","Tm","Yb",
    "Lu","Hf","Ta","W","Re","Os","Ir","Pt","Au","Hg",
    "Tl","Pb","Bi","Po","At","Rn","Fr","Ra","Ac","Th",
    "Pa","U","Np","Pu","Am","Cm","Bk","Cf","Es","Fm",
    "Md","No","Lr","Rf","Db","Sg","Bh","Hs","Mt","Ds",
    "Rg","Cn","Nh","Fl","Mc","Lv","Ts","Og",
]


def idx_to_symbol(idx: int, pad_idx: Optional[int] = None) -> str:
    if pad_idx is not None and idx == int(pad_idx):
        return "X"
    if idx < 0:
        return "X"
    if idx < len(_ZMINUS1_SYMBOLS):
        return _ZMINUS1_SYMBOLS[idx]
    return "X"


# ------------------------------ dataset ------------------------------

def create_dataset(path: str, start_idx: int = 0, end_idx: Optional[int] = None):
    """Mirror training-side dataset selection: directory dataset vs .lmdb dataset."""
    if path.endswith(".lmdb") and os.path.isfile(path):
        return LmdbMoleculeDataset(path, start_idx=start_idx, end_idx=end_idx)
    return MoleculeDataset(path, start_idx=start_idx, end_idx=end_idx)


def ensure_batch(data: Data, device: torch.device) -> None:
    """Ensure data.batch exists (1D LongTensor), otherwise set all nodes to batch=0."""
    if not hasattr(data, "batch") or data.batch is None:
        data.batch = torch.zeros(data.num_nodes, dtype=torch.long, device=device)
        return
    if not isinstance(data.batch, torch.Tensor):
        data.batch = torch.as_tensor(data.batch, dtype=torch.long, device=device)
        return
    data.batch = data.batch.to(device).long().view(-1)


# ------------------------------ ckpt loading ------------------------------

def _cfg_get(cfg: Dict, *keys, default=None):
    for k in keys:
        if k in cfg:
            return cfg[k]
    return default


def load_model_from_ckpt(ckpt_path: str, device: torch.device) -> Tuple[MultiTaskMoE, Dict]:
    """
    Load MultiTaskMoE from checkpoint created by pretrain_multitask.py.

    Supports:
      - new unified format:  {'cfg':..., 'model_state':..., 'standardizer':...}
      - fallback keys:       'state_dict', 'moe_state' (best-effort)
    """
    ckpt = torch.load(ckpt_path, map_location="cpu")
    if not isinstance(ckpt, dict):
        raise ValueError(f"Unsupported ckpt type: {type(ckpt)}")

    cfg = ckpt.get("cfg", {})
    if not isinstance(cfg, dict) or not cfg:
        LOGGER.warning("Checkpoint has no/empty cfg; using minimal defaults (may not match weights).")
        cfg = {}

    bb_cfg = _cfg_get(cfg, "backbone_config", "backbone_cfg", "bb_cfg", default={})
    if not isinstance(bb_cfg, dict):
        bb_cfg = {}

    n_atom_types = int(_cfg_get(cfg, "n_atom_types", default=95))

    model = MultiTaskMoE(
        backbone_config=bb_cfg,
        n_atom_types=n_atom_types,
        n_experts_geom=int(_cfg_get(cfg, "n_experts_geom", "expert_number_G", default=4)),
        n_experts_energy=int(_cfg_get(cfg, "n_experts_energy", "expert_number_E", default=2)),
        n_experts_charge=int(_cfg_get(cfg, "n_experts_charge", "expert_number_Q", default=2)),
        n_experts_elem=int(_cfg_get(cfg, "n_experts_elem", "expert_number_Z", default=2)),
        top_k_geom=int(_cfg_get(cfg, "top_k_geom", "topk_geom", "topkG", default=2)),
        top_k_energy=int(_cfg_get(cfg, "top_k_energy", "topk_energy", "topkE", default=1)),
        top_k_charge=int(_cfg_get(cfg, "top_k_charge", "topk_charge", "topkQ", default=1)),
        top_k_elem=int(_cfg_get(cfg, "top_k_elem", "topk_elem", "topkZ", default=1)),
        expert_real_layers=int(_cfg_get(cfg, "expert_real_layers", "expert_layers", default=2)),
        expert_int_layers=int(_cfg_get(cfg, "expert_int_layers", default=0)),
        expert_heads=int(_cfg_get(cfg, "expert_heads", default=4)),
        expert_ff_mult=int(_cfg_get(cfg, "expert_ff_mult", default=2)),
        balance_weight=float(_cfg_get(cfg, "balance_weight", "lambda_balance", default=1e-2)),
    ).to(device)

    # ---- state dict ----
    state = None
    for k in ("model_state", "state_dict", "moe_state", "model"):
        if k in ckpt and isinstance(ckpt[k], dict):
            state = ckpt[k]
            break
    if state is None:
        # Sometimes people save raw state_dict directly.
        if all(isinstance(v, torch.Tensor) for v in ckpt.values()):
            state = ckpt
        else:
            raise ValueError("Checkpoint does not contain a recognizable model state dict.")

    incompatible = model.load_state_dict(state, strict=False)
    if getattr(incompatible, "missing_keys", None):
        if incompatible.missing_keys:
            LOGGER.warning("Missing keys when loading ckpt (strict=False): %d", len(incompatible.missing_keys))
    if getattr(incompatible, "unexpected_keys", None):
        if incompatible.unexpected_keys:
            LOGGER.warning("Unexpected keys when loading ckpt (strict=False): %d", len(incompatible.unexpected_keys))

    model.eval()
    return model, cfg


# ------------------------------ inference helpers ------------------------------

def _infer_node_mask(data: Data, batch_vec: torch.Tensor, pad_idx: int) -> torch.Tensor:
    """Reconstruct dense node mask (B,N) using data.x padding convention."""
    x_raw = data.x
    if x_raw.dim() == 2:
        x_raw = x_raw[:, 0]
    x_dense, _ = to_dense_batch(x_raw.long(), batch_vec, fill_value=int(pad_idx))
    return x_dense != int(pad_idx)


@torch.no_grad()
def infer_single(
    model: MultiTaskMoE,
    data: Data,
    *,
    device: torch.device,
    fp16: bool = False,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, float, torch.Tensor, int]:
    """
    Forward one molecule and return:
      elem_idx_pred (N,),
      coords_pred   (N,3),
      charges_pred  (N,),
      energy_pred   (float),
      node_mask     (N,)  (valid atoms),
      pad_idx       (int)
    """
    data = data.to(device)
    ensure_batch(data, device)

    # pad_idx convention used by training-side element loss
    n_atom_types = int(getattr(model, "n_atom_types", model.elem_head.out_features))
    pad_idx = int(getattr(model, "pad_elem_index", n_atom_types - 1))

    with autocast(enabled=fp16):
        coords_pred, charge_pred, elem_pred, energy_pred, _charge_mask, _bal = model(data)

    node_mask_dense = _infer_node_mask(data, data.batch, pad_idx)  # (B,Nmax)
    m = node_mask_dense[0].bool()

    coords = coords_pred[0, m].detach().cpu()                 # (N,3)
    charges = charge_pred[0, m, 0].detach().cpu()             # (N,)
    energy = float(energy_pred[0, 0, 0].detach().cpu())        # scalar

    logits = elem_pred[0, m].detach().cpu()                    # (N,C)
    elem_idx_pred = logits.argmax(dim=-1).to(torch.long)       # (N,)

    return elem_idx_pred, coords, charges, energy, m.cpu(), pad_idx


def kabsch_rmsd(P: torch.Tensor, Q: torch.Tensor) -> float:
    """RMSD after optimal rigid alignment (Kabsch). P,Q: (N,3) float tensors on CPU."""
    if P.numel() == 0:
        return float("nan")
    P = P.to(torch.float64)
    Q = Q.to(torch.float64)
    Pc = P - P.mean(dim=0, keepdim=True)
    Qc = Q - Q.mean(dim=0, keepdim=True)
    C = Pc.T @ Qc
    V, S, Wt = torch.linalg.svd(C)
    d = torch.det(V @ Wt)
    D = torch.diag(torch.tensor([1.0, 1.0, float(d)], dtype=torch.float64))
    U = V @ D @ Wt
    P_aligned = Pc @ U
    diff = P_aligned - Qc
    return float(torch.sqrt((diff * diff).sum(dim=1).mean()).cpu())


def pairwise_dist_mae(P: torch.Tensor, Q: torch.Tensor) -> float:
    """MAE over all pairwise distances (upper triangle). P,Q: (N,3) CPU tensors."""
    if P.size(0) <= 1:
        return 0.0
    Pd = torch.cdist(P, P)
    Qd = torch.cdist(Q, Q)
    iu = torch.triu_indices(P.size(0), P.size(0), offset=1)
    return float((Pd[iu[0], iu[1]] - Qd[iu[0], iu[1]]).abs().mean().cpu())


def evaluate_prediction(
    elem_idx_pred: torch.Tensor,
    coords_pred: torch.Tensor,
    charges_pred: torch.Tensor,
    energy_pred: float,
    data_true: Data,
    *,
    pad_idx: int,
) -> Dict[str, float]:
    """Compute a small set of practical metrics when ground truth is available."""
    N = int(data_true.pos.size(0))
    out: Dict[str, float] = {}

    # element accuracy
    x_true = data_true.x
    if x_true.dim() == 2:
        x_true = x_true[:, 0]
    x_true = x_true.long().cpu()[:N]
    elem_idx_pred = elem_idx_pred.cpu()[:N]
    valid = (x_true != pad_idx)
    if valid.any():
        out["Acc_z"] = float((elem_idx_pred[valid] == x_true[valid]).float().mean().item())
    else:
        out["Acc_z"] = float("nan")

    # charges
    if hasattr(data_true, "y"):
        q_true = data_true.y.view(-1).cpu()[:N]
        if hasattr(data_true, "charge_mask"):
            cm = data_true.charge_mask.view(-1).cpu()[:N].bool()
        else:
            cm = torch.ones_like(q_true, dtype=torch.bool)
        if cm.any():
            out["MAE_q"] = float((charges_pred[:N][cm] - q_true[cm]).abs().mean().item())
        else:
            out["MAE_q"] = float("nan")

    # energy
    if hasattr(data_true, "energy"):
        e_true = float(torch.as_tensor(data_true.energy).view(-1)[0].cpu())
        out["MAE_e"] = float(abs(energy_pred - e_true))

    # geometry invariants
    pos_true = data_true.pos.to(torch.float32).cpu()[:N]
    pos_pred = coords_pred.to(torch.float32).cpu()[:N]
    if pos_true.shape == pos_pred.shape:
        out["RMSD_kabsch"] = kabsch_rmsd(pos_pred, pos_true)
        out["MAE_pairdist"] = pairwise_dist_mae(pos_pred, pos_true)

    return out


def write_xyz(path: str, symbols: Sequence[str], coords: torch.Tensor, comment: str = "") -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    coords = coords.to(torch.float64).cpu()
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{coords.size(0)}\n")
        f.write((comment.strip() + "\n") if comment else "\n")
        for s, (x, y, z) in zip(symbols, coords.tolist()):
            f.write(f"{s:>2s} {x: .8f} {y: .8f} {z: .8f}\n")


# ------------------------------ perturbation ------------------------------

@dataclass
class MixItem:
    cfg: DegradeConfig
    weight: float


def parse_perturb_mix(spec: str) -> List[MixItem]:
    """
    Parse a mix spec like:
      "topo:0.3@0.2,geom:0.5@0.5,both:0.7@1.0"
    meaning: (mode:level@weight, ...)
    """
    spec = (spec or "").strip()
    if spec.lower() in ("", "none", "off"):
        return []
    items: List[MixItem] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            mode_level, w_str = part.split("@", 1)
            mode, level_str = mode_level.split(":", 1)
            cfg = DegradeConfig(mode=mode.strip(), level=float(level_str))
            items.append(MixItem(cfg=cfg, weight=float(w_str)))
        except Exception as e:
            raise ValueError(f"Bad perturb_mix item: {part!r} ({e})") from e
    # normalize weights
    s = sum(max(0.0, it.weight) for it in items)
    if s <= 0:
        return []
    for it in items:
        it.weight = max(0.0, it.weight) / s
    return items


def apply_perturb(
    data: Data,
    *,
    mix: List[MixItem],
    mode: str,
    level: float,
    replace_frac: Optional[float],
    delete_frac: Optional[float],
    noise_std: Optional[float],
    angle_std_deg: Optional[float],
    rng: torch.Generator,
) -> Data:
    if mix:
        probs = torch.tensor([it.weight for it in mix], dtype=torch.float32)
        idx = int(torch.multinomial(probs, 1, generator=rng).item())
        cfg = mix[idx].cfg
        return degrade_once(data, cfg, rng)

    if mode == "none":
        return data

    cfg = DegradeConfig(
        mode=mode,
        level=float(level),
        topo_replace_frac=replace_frac,
        topo_delete_frac=delete_frac,
        geom_noise_std=noise_std,
        geom_angle_std_deg=angle_std_deg,
    )
    return degrade_once(data, cfg, rng)


# ------------------------------ main ------------------------------

def build_logger(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def main() -> None:
    ap = argparse.ArgumentParser("Structure prediction → XYZ / metrics (refactored MultiTaskMoE)")
    ap.add_argument("--ckpt", required=True, help="Checkpoint path (.pt)")
    ap.add_argument("--data_root", required=True, help="Dataset path (directory or .lmdb)")
    ap.add_argument("--sample_idx", type=int, default=None, help="If set, run a single sample")
    ap.add_argument("--start_idx", type=int, default=0, help="Dataset slice start")
    ap.add_argument("--end_idx", type=int, default=None, help="Dataset slice end")
    ap.add_argument("--out_path", required=True, help="XYZ output path (single) or output directory (dataset)")

    ap.add_argument("--device", default=None, help="cuda / cpu; default auto")
    ap.add_argument("--fp16", action="store_true", help="Enable autocast fp16 for inference (cuda only)")
    ap.add_argument("--eval", action="store_true", help="Compute metrics if ground truth exists")
    ap.add_argument("--use_true_types", action="store_true", help="Write XYZ using ground-truth types (debug)")

    # perturbation
    ap.add_argument("--perturb_mix", type=str, default="none",
                    help='Mix spec like "topo:0.3@0.2,geom:0.5@0.5" (overrides perturb_mode/level)')
    ap.add_argument("--perturb_mode", type=str, default="none", choices=["none", "topo", "geom", "both"])
    ap.add_argument("--perturb_level", type=float, default=0.5)
    ap.add_argument("--perturb_replace_frac", type=float, default=None)
    ap.add_argument("--perturb_delete_frac", type=float, default=None)
    ap.add_argument("--perturb_noise_std", type=float, default=None)
    ap.add_argument("--perturb_angle_std_deg", type=float, default=None)

    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    build_logger(args.verbose)

    device = torch.device(args.device) if args.device else torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if args.fp16 and device.type != "cuda":
        LOGGER.warning("--fp16 is set but device is not cuda; disabling fp16.")
        args.fp16 = False

    model, cfg = load_model_from_ckpt(args.ckpt, device)
    LOGGER.info("Loaded ckpt: %s", args.ckpt)
    LOGGER.info("Model n_atom_types=%s | cfg keys=%d", getattr(model, "n_atom_types", None), len(cfg))

    ds = create_dataset(args.data_root, start_idx=args.start_idx, end_idx=args.end_idx)
    LOGGER.info("Dataset size: %d", len(ds))

    mix = parse_perturb_mix(args.perturb_mix)
    rng = torch.Generator(device="cpu").manual_seed(int(args.seed))

    def _symbols_from_idx(idx: torch.Tensor, pad_idx: int) -> List[str]:
        return [idx_to_symbol(int(i), pad_idx) for i in idx.tolist()]

    # -------------- single sample --------------
    if args.sample_idx is not None:
        data_true: Data = ds[int(args.sample_idx)]
        data_in = data_true.clone()
        data_in = apply_perturb(
            data_in,
            mix=mix,
            mode=args.perturb_mode,
            level=args.perturb_level,
            replace_frac=args.perturb_replace_frac,
            delete_frac=args.perturb_delete_frac,
            noise_std=args.perturb_noise_std,
            angle_std_deg=args.perturb_angle_std_deg,
            rng=rng,
        )

        elem_idx_pred, coords_pred, charges_pred, energy_pred, _mask, pad_idx = infer_single(
            model, data_in, device=device, fp16=args.fp16
        )

        if args.use_true_types:
            x_true = data_true.x
            if x_true.dim() == 2:
                x_true = x_true[:, 0]
            symbols = _symbols_from_idx(x_true.long().cpu(), pad_idx)
        else:
            symbols = _symbols_from_idx(elem_idx_pred, pad_idx)

        comment = f"idx={args.sample_idx} | E_pred={energy_pred:.6f}"
        write_xyz(args.out_path, symbols, coords_pred, comment=comment)
        LOGGER.info("Wrote XYZ: %s", args.out_path)

        if args.eval:
            metrics = evaluate_prediction(elem_idx_pred, coords_pred, charges_pred, energy_pred, data_true, pad_idx=pad_idx)
            for k, v in metrics.items():
                LOGGER.info("Metric %-12s : %s", k, f"{v:.6g}" if isinstance(v, (int, float)) else v)
        return

    # -------------- dataset mode --------------
    out_dir = args.out_path
    os.makedirs(out_dir, exist_ok=True)

    all_metrics: List[Dict[str, float]] = []
    for i in tqdm(range(len(ds)), desc="Infer"):
        data_true: Data = ds[i]
        data_in = data_true.clone()
        data_in = apply_perturb(
            data_in,
            mix=mix,
            mode=args.perturb_mode,
            level=args.perturb_level,
            replace_frac=args.perturb_replace_frac,
            delete_frac=args.perturb_delete_frac,
            noise_std=args.perturb_noise_std,
            angle_std_deg=args.perturb_angle_std_deg,
            rng=rng,
        )

        elem_idx_pred, coords_pred, charges_pred, energy_pred, _mask, pad_idx = infer_single(
            model, data_in, device=device, fp16=args.fp16
        )

        if args.use_true_types:
            x_true = data_true.x
            if x_true.dim() == 2:
                x_true = x_true[:, 0]
            symbols = _symbols_from_idx(x_true.long().cpu(), pad_idx)
        else:
            symbols = _symbols_from_idx(elem_idx_pred, pad_idx)

        xyz_path = os.path.join(out_dir, f"sample_{i:06d}.xyz")
        write_xyz(xyz_path, symbols, coords_pred, comment=f"idx={i} | E_pred={energy_pred:.6f}")

        if args.eval:
            m = evaluate_prediction(elem_idx_pred, coords_pred, charges_pred, energy_pred, data_true, pad_idx=pad_idx)
            m["idx"] = float(i)
            all_metrics.append(m)

    if args.eval and all_metrics:
        # print aggregate summary
        keys = sorted({k for d in all_metrics for k in d.keys() if k != "idx"})
        for k in keys:
            vals = [d.get(k, float("nan")) for d in all_metrics]
            vals = [v for v in vals if isinstance(v, (int, float)) and math.isfinite(v)]
            if vals:
                LOGGER.info("AVG %-12s : %.6g (n=%d)", k, float(np.mean(vals)), len(vals))
        # write csv
        csv_path = os.path.join(out_dir, "metrics.csv")
        with open(csv_path, "w", encoding="utf-8") as f:
            header = ["idx"] + keys
            f.write(",".join(header) + "\n")
            for d in all_metrics:
                row = [str(int(d.get("idx", -1)))]
                for k in keys:
                    v = d.get(k, float("nan"))
                    row.append("" if not (isinstance(v, (int, float)) and math.isfinite(v)) else f"{float(v):.8g}")
                f.write(",".join(row) + "\n")
        LOGGER.info("Wrote metrics CSV: %s", csv_path)


if __name__ == "__main__":
    main()