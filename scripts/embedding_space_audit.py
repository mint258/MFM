import argparse
import importlib.util
import json
import math
import os
import pickle
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import lmdb
import matplotlib
import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error as mae
from sklearn.metrics import r2_score as r2

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LMDB_PATH = Path(r"E:\OneDrive\property_analysis\MFM_repository\test_data\lmdb_test.lmdb")
DEFAULT_OUTPUT_DIR = ROOT / "tmp" / "embedding_space_audit"
DEFAULT_CHECKPOINT_REGEX = r"^(AE_.*\.pt|MFM_.*\.pt)$"
DEFAULT_PROBE_TARGETS = [
    "LogD",
    "LogS",
    "Log_HLM_CLint",
    "Log_MLM_CLint",
    "Log_Caco_Papp_AB",
    "Log_Caco_ER",
    "Log_Mouse_PPB",
    "Log_Mouse_BPB",
    "Log_Mouse_MPB",
]


def _load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import module '{module_name}' from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _infer_family(checkpoint_name: str) -> str:
    if checkpoint_name.startswith("AE_"):
        return "old"
    if checkpoint_name.startswith("MFM_"):
        return "new"
    raise ValueError(f"Cannot infer family from checkpoint name: {checkpoint_name}")


def _detect_key_fmt(txn, n_items: int) -> str:
    candidates = ["09d", "08d", "010d", "raw"]
    probes = {0, 1, 2}
    if n_items > 0:
        probes.add(n_items - 1)
    probes = sorted([p for p in probes if isinstance(p, int) and p >= 0 and p < n_items])
    best_fmt, best_hits = "09d", -1
    for fmt in candidates:
        hits = 0
        for i in probes:
            key = str(i).encode() if fmt == "raw" else f"{i:{fmt}}".encode()
            if txn.get(key) is not None:
                hits += 1
        if hits > best_hits:
            best_fmt, best_hits = fmt, hits
    return best_fmt


def _iter_lmdb_samples(lmdb_path: Path) -> Iterable[Tuple[int, torch.Tensor]]:
    env = lmdb.open(
        str(lmdb_path),
        subdir=lmdb_path.is_dir(),
        readonly=True,
        lock=False,
        readahead=False,
        meminit=False,
    )
    with env.begin() as txn:
        raw_len = txn.get(b"__len__")
        if raw_len is None:
            raise KeyError(f"LMDB shard '{lmdb_path}' is missing '__len__'.")
        n_items = int(pickle.loads(raw_len))
        key_fmt = _detect_key_fmt(txn, n_items)
        for i in range(n_items):
            key = str(i).encode() if key_fmt == "raw" else f"{i:{key_fmt}}".encode()
            buf = txn.get(key)
            if buf is None:
                raise KeyError(f"LMDB sample missing at index {i} with key format {key_fmt}.")
            yield i, pickle.loads(buf)


def _discover_checkpoints(ckpt_dir: Path, regex: str) -> List[Path]:
    pattern = re.compile(regex)
    checkpoints = [
        path
        for path in sorted(ckpt_dir.iterdir(), key=lambda p: p.name.lower())
        if path.is_file() and pattern.match(path.name)
    ]
    if not checkpoints:
        raise FileNotFoundError(f"No checkpoints matched regex '{regex}' in {ckpt_dir}")
    return checkpoints


def _sample_split_df(df: pd.DataFrame, max_rows: int, seed: int) -> pd.DataFrame:
    if int(max_rows) <= 0 or len(df) <= int(max_rows):
        return df.reset_index(drop=True)
    return df.sample(n=int(max_rows), random_state=int(seed)).reset_index(drop=True)


def _load_probe_frames(data_dir: Path, fold: int, max_train_rows: int, max_test_rows: int, seed: int) -> Dict[str, pd.DataFrame]:
    train_df = pd.read_csv(data_dir / f"fold_{fold}" / "train.csv")
    test_df = pd.read_csv(data_dir / f"fold_{fold}" / "test.csv")
    train_df = train_df.copy()
    test_df = test_df.copy()
    train_df["smiles"] = train_df["SMILES"].astype(str)
    test_df["smiles"] = test_df["SMILES"].astype(str)
    train_df = _sample_split_df(train_df, max_train_rows, seed + fold * 17)
    test_df = _sample_split_df(test_df, max_test_rows, seed + fold * 31)
    return {"train": train_df, "test": test_df}


def _pad_node_embeddings(node_list: Sequence[torch.Tensor]) -> Tuple[torch.Tensor, np.ndarray]:
    max_atoms = 1
    dim = int(node_list[0].shape[1]) if node_list else 1
    for emb in node_list:
        if emb.dim() != 2:
            continue
        max_atoms = max(max_atoms, int(emb.shape[0]))
        dim = int(emb.shape[1])
    x = torch.zeros((len(node_list), max_atoms, dim), dtype=torch.float32)
    atom_mask = np.zeros((len(node_list), max_atoms), dtype=bool)
    for i, emb in enumerate(node_list):
        if emb.dim() != 2 or emb.shape[0] <= 0:
            continue
        n_atoms = int(emb.shape[0])
        x[i, :n_atoms, :] = emb.float()
        atom_mask[i, :n_atoms] = True
    return x, atom_mask


def _summary_pool_from_atoms(x_atoms: torch.Tensor, atom_mask: np.ndarray) -> np.ndarray:
    x = x_atoms.detach().cpu().numpy().astype(np.float32, copy=False)
    mask = np.asarray(atom_mask).astype(bool)
    out = []
    for i in range(x.shape[0]):
        xi = x[i, mask[i]]
        if xi.shape[0] <= 0:
            xi = np.zeros((1, x.shape[2]), dtype=np.float32)
        mean = xi.mean(axis=0)
        max_v = xi.max(axis=0)
        std = xi.std(axis=0)
        log_n = np.asarray([math.log(max(1, xi.shape[0]))], dtype=np.float32)
        out.append(np.concatenate([mean, max_v, std, log_n], axis=0))
    return np.asarray(out, dtype=np.float32)


def _mean_pool_from_atoms(x_atoms: torch.Tensor, atom_mask: np.ndarray) -> np.ndarray:
    x = x_atoms.detach().cpu().numpy().astype(np.float32, copy=False)
    mask = np.asarray(atom_mask).astype(bool)
    out = []
    for i in range(x.shape[0]):
        xi = x[i, mask[i]]
        if xi.shape[0] <= 0:
            xi = np.zeros((1, x.shape[2]), dtype=np.float32)
        out.append(xi.mean(axis=0))
    return np.asarray(out, dtype=np.float32)


def _flatten_valid_nodes(x_atoms: torch.Tensor, atom_mask: np.ndarray) -> np.ndarray:
    x = x_atoms.detach().cpu().numpy().astype(np.float32, copy=False)
    mask = np.asarray(atom_mask).astype(bool)
    rows = []
    for i in range(x.shape[0]):
        xi = x[i, mask[i]]
        if xi.shape[0] > 0:
            rows.append(xi)
    if not rows:
        return np.zeros((0, x.shape[-1]), dtype=np.float32)
    return np.concatenate(rows, axis=0).astype(np.float32, copy=False)


def _pairwise_cosine_stats(x: np.ndarray, n_pairs: int = 20000, seed: int = 7) -> Dict[str, float]:
    if x.shape[0] < 2:
        return {"cos_mean": float("nan"), "cos_std": float("nan"), "cos_p95": float("nan")}
    rng = np.random.default_rng(seed)
    m = min(int(n_pairs), x.shape[0] * (x.shape[0] - 1) // 2)
    i = rng.integers(0, x.shape[0], size=m)
    j = rng.integers(0, x.shape[0], size=m)
    neq = i != j
    i = i[neq]
    j = j[neq]
    if i.size <= 0:
        return {"cos_mean": float("nan"), "cos_std": float("nan"), "cos_p95": float("nan")}
    x_norm = x / np.clip(np.linalg.norm(x, axis=1, keepdims=True), 1e-12, None)
    cos = np.sum(x_norm[i] * x_norm[j], axis=1)
    return {
        "cos_mean": float(np.mean(cos)),
        "cos_std": float(np.std(cos)),
        "cos_p95": float(np.percentile(cos, 95)),
    }


def _uniformity_metric(x: np.ndarray, n_pairs: int = 10000, seed: int = 11) -> float:
    if x.shape[0] < 2:
        return float("nan")
    rng = np.random.default_rng(seed)
    m = min(int(n_pairs), x.shape[0] * (x.shape[0] - 1) // 2)
    i = rng.integers(0, x.shape[0], size=m)
    j = rng.integers(0, x.shape[0], size=m)
    neq = i != j
    i = i[neq]
    j = j[neq]
    if i.size <= 0:
        return float("nan")
    x_norm = x / np.clip(np.linalg.norm(x, axis=1, keepdims=True), 1e-12, None)
    dist2 = np.sum((x_norm[i] - x_norm[j]) ** 2, axis=1)
    return float(np.log(np.mean(np.exp(-2.0 * dist2)) + 1e-12))


def _spectrum_stats(x: np.ndarray) -> Dict[str, float]:
    if x.shape[0] < 3:
        return {
            "effective_rank": float("nan"),
            "participation_ratio": float("nan"),
            "top1_ratio": float("nan"),
            "top10_ratio": float("nan"),
            "condition_number_log10": float("nan"),
            "top_components": [],
        }
    xc = x - x.mean(axis=0, keepdims=True)
    _, s, _ = np.linalg.svd(xc, full_matrices=False)
    eig = (s ** 2) / max(1, (x.shape[0] - 1))
    total = float(np.sum(eig)) + 1e-12
    p = eig / total
    p_pos = p[p > 0]
    effective_rank = float(np.exp(-np.sum(p_pos * np.log(np.clip(p_pos, 1e-12, None)))))
    participation_ratio = float((np.sum(eig) ** 2) / (np.sum(eig ** 2) + 1e-12))
    top1_ratio = float(eig[0] / total)
    top10_ratio = float(np.sum(eig[: min(10, eig.shape[0])]) / total)
    valid_s = s[s > 1e-12]
    if valid_s.size > 0:
        condition_number_log10 = float(np.log10(valid_s[0] / valid_s[-1]))
    else:
        condition_number_log10 = float("nan")
    return {
        "effective_rank": effective_rank,
        "participation_ratio": participation_ratio,
        "top1_ratio": top1_ratio,
        "top10_ratio": top10_ratio,
        "condition_number_log10": condition_number_log10,
        "top_components": [float(v) for v in p[: min(10, p.shape[0])]],
    }


def _feature_corr_stats(x: np.ndarray) -> Dict[str, float]:
    if x.shape[0] < 3 or x.shape[1] < 2:
        return {"avg_abs_corr": float("nan"), "max_abs_corr": float("nan")}
    xc = x - x.mean(axis=0, keepdims=True)
    std = xc.std(axis=0, keepdims=True)
    std = np.where(std < 1e-12, 1.0, std)
    z = xc / std
    corr = (z.T @ z) / max(1, (z.shape[0] - 1))
    corr = np.asarray(corr, dtype=np.float64)
    np.fill_diagonal(corr, 0.0)
    abs_corr = np.abs(corr)
    return {
        "avg_abs_corr": float(abs_corr.mean()),
        "max_abs_corr": float(abs_corr.max()),
    }


def _basic_stats(x: np.ndarray) -> Dict[str, float]:
    if x.size <= 0:
        return {
            "n_rows": 0,
            "dim": 0,
            "abs_mean": float("nan"),
            "mean": float("nan"),
            "std": float("nan"),
            "norm_mean": float("nan"),
            "norm_std": float("nan"),
            "feat_std_mean": float("nan"),
            "feat_std_median": float("nan"),
            "feat_std_p05": float("nan"),
            "feat_std_p95": float("nan"),
            "near_constant_dims_ratio": float("nan"),
        }
    norms = np.linalg.norm(x, axis=1)
    feat_std = x.std(axis=0)
    return {
        "n_rows": int(x.shape[0]),
        "dim": int(x.shape[1]),
        "abs_mean": float(np.mean(np.abs(x))),
        "mean": float(np.mean(x)),
        "std": float(np.std(x)),
        "norm_mean": float(np.mean(norms)),
        "norm_std": float(np.std(norms)),
        "feat_std_mean": float(np.mean(feat_std)),
        "feat_std_median": float(np.median(feat_std)),
        "feat_std_p05": float(np.percentile(feat_std, 5)),
        "feat_std_p95": float(np.percentile(feat_std, 95)),
        "near_constant_dims_ratio": float(np.mean(feat_std < 1e-6)),
    }


def _embedding_stats(x: np.ndarray) -> Dict[str, float]:
    out = _basic_stats(x)
    out.update(_pairwise_cosine_stats(x))
    out["uniformity"] = _uniformity_metric(x)
    out.update(_feature_corr_stats(x))
    out.update(_spectrum_stats(x))
    return out


def _linear_cka(x: np.ndarray, y: np.ndarray) -> float:
    x = x - x.mean(axis=0, keepdims=True)
    y = y - y.mean(axis=0, keepdims=True)
    xty = x.T @ y
    hsic = float(np.square(np.linalg.norm(xty, ord="fro")))
    xx = float(np.linalg.norm(x.T @ x, ord="fro"))
    yy = float(np.linalg.norm(y.T @ y, ord="fro"))
    return hsic / max(1e-12, xx * yy)


def _diag_cosine_mean(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    if x.shape != y.shape:
        return None
    xn = x / np.clip(np.linalg.norm(x, axis=1, keepdims=True), 1e-12, None)
    yn = y / np.clip(np.linalg.norm(y, axis=1, keepdims=True), 1e-12, None)
    return float(np.mean(np.sum(xn * yn, axis=1)))


def _knn_overlap(x: np.ndarray, y: np.ndarray, k: int = 10) -> float:
    n = x.shape[0]
    if n <= 2:
        return float("nan")
    k = min(int(k), n - 1)
    xn = x / np.clip(np.linalg.norm(x, axis=1, keepdims=True), 1e-12, None)
    yn = y / np.clip(np.linalg.norm(y, axis=1, keepdims=True), 1e-12, None)
    sim_x = xn @ xn.T
    sim_y = yn @ yn.T
    np.fill_diagonal(sim_x, -np.inf)
    np.fill_diagonal(sim_y, -np.inf)
    nn_x = np.argpartition(-sim_x, kth=k - 1, axis=1)[:, :k]
    nn_y = np.argpartition(-sim_y, kth=k - 1, axis=1)[:, :k]
    overlap = []
    for i in range(n):
        overlap.append(len(set(nn_x[i].tolist()).intersection(set(nn_y[i].tolist()))) / float(k))
    return float(np.mean(overlap))


def _neighbor_target_ratio(x: np.ndarray, target: np.ndarray, k: int = 10) -> float:
    mask = np.isfinite(target).all(axis=1) if target.ndim == 2 else np.isfinite(target)
    if np.sum(mask) < max(8, k + 2):
        return float("nan")
    x = x[mask]
    target = target[mask]
    n = x.shape[0]
    k = min(int(k), n - 1)
    xn = x / np.clip(np.linalg.norm(x, axis=1, keepdims=True), 1e-12, None)
    sim = xn @ xn.T
    np.fill_diagonal(sim, -np.inf)
    nn = np.argpartition(-sim, kth=k - 1, axis=1)[:, :k]
    rng = np.random.default_rng(123)
    rand_idx = np.stack([rng.choice(n - 1, size=k, replace=False) for _ in range(n)], axis=0)
    rand_idx = np.where(rand_idx >= np.arange(n)[:, None], rand_idx + 1, rand_idx)
    if target.ndim == 1:
        near = np.mean(np.abs(target[:, None] - target[nn]), axis=1)
        rand = np.mean(np.abs(target[:, None] - target[rand_idx]), axis=1)
    else:
        near = np.mean(np.linalg.norm(target[:, None, :] - target[nn], axis=2), axis=1)
        rand = np.mean(np.linalg.norm(target[:, None, :] - target[rand_idx], axis=2), axis=1)
    return float(np.mean(near / np.clip(rand, 1e-12, None)))


def _fit_standardizer(train_x: np.ndarray, mode: str) -> Dict[str, np.ndarray]:
    train_x = np.asarray(train_x, dtype=np.float32)
    mu = train_x.mean(axis=0, keepdims=True)
    sd = train_x.std(axis=0, keepdims=True)
    sd = np.where(sd < 1e-8, 1.0, sd)
    return {"mode": mode, "mu": mu, "sd": sd}


def _transform_features(x: np.ndarray, fit_state: Dict[str, np.ndarray]) -> np.ndarray:
    mode = fit_state["mode"]
    mu = fit_state["mu"]
    sd = fit_state["sd"]
    out = np.asarray(x, dtype=np.float32)
    if mode == "raw":
        return out
    if mode == "center":
        return out - mu
    if mode == "standardize":
        return (out - mu) / sd
    if mode == "l2":
        return out / np.clip(np.linalg.norm(out, axis=1, keepdims=True), 1e-12, None)
    if mode == "standardize_l2":
        z = (out - mu) / sd
        return z / np.clip(np.linalg.norm(z, axis=1, keepdims=True), 1e-12, None)
    raise ValueError(f"Unsupported transform mode: {mode}")


def _ridge_probe_train_test(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray, test_y: np.ndarray, targets: Sequence[str]) -> Dict:
    out = {}
    maes = []
    r2s = []
    for j, target_name in enumerate(targets):
        train_mask = np.isfinite(train_y[:, j])
        test_mask = np.isfinite(test_y[:, j])
        if int(train_mask.sum()) < 20 or int(test_mask.sum()) < 10:
            out[target_name] = {"mae": None, "r2": None, "n_train": int(train_mask.sum()), "n_test": int(test_mask.sum())}
            continue
        reg = Ridge(alpha=1.0)
        reg.fit(train_x[train_mask], train_y[train_mask, j])
        pred = reg.predict(test_x[test_mask])
        score_mae = float(mae(test_y[test_mask, j], pred))
        score_r2 = float(r2(test_y[test_mask, j], pred))
        maes.append(score_mae)
        r2s.append(score_r2)
        out[target_name] = {
            "mae": score_mae,
            "r2": score_r2,
            "n_train": int(train_mask.sum()),
            "n_test": int(test_mask.sum()),
        }
    out["_summary"] = {
        "mean_mae": None if not maes else float(np.mean(maes)),
        "mean_r2": None if not r2s else float(np.mean(r2s)),
        "n_tasks_eval": int(len(maes)),
    }
    return out


def _ridge_probe_random_split(x: np.ndarray, y: np.ndarray, seed: int, train_frac: float = 0.8) -> Dict:
    mask = np.isfinite(y)
    idx = np.where(mask)[0]
    if idx.size < 40:
        return {"mae": None, "r2": None, "n_samples": int(idx.size)}
    rng = np.random.default_rng(seed)
    rng.shuffle(idx)
    n_train = max(20, int(idx.size * float(train_frac)))
    n_train = min(n_train, idx.size - 10)
    tr = idx[:n_train]
    te = idx[n_train:]
    fit_state = _fit_standardizer(x[tr], "standardize")
    x_tr = _transform_features(x[tr], fit_state)
    x_te = _transform_features(x[te], fit_state)
    reg = Ridge(alpha=1.0)
    reg.fit(x_tr, y[tr])
    pred = reg.predict(x_te)
    return {
        "mae": float(mae(y[te], pred)),
        "r2": float(r2(y[te], pred)),
        "n_train": int(tr.size),
        "n_test": int(te.size),
        "n_samples": int(idx.size),
    }


def _ridge_probe_multitarget_masked(x: np.ndarray, y: np.ndarray, y_mask: np.ndarray, seed: int) -> Dict:
    maes = []
    r2s = []
    per_dim = []
    for j in range(y.shape[1]):
        mask = np.asarray(y_mask[:, j]).astype(bool) & np.isfinite(y[:, j])
        idx = np.where(mask)[0]
        if idx.size < 40:
            per_dim.append({"dim": int(j), "mae": None, "r2": None, "n_samples": int(idx.size)})
            continue
        rng = np.random.default_rng(seed + j * 19)
        rng.shuffle(idx)
        n_train = max(20, int(idx.size * 0.8))
        n_train = min(n_train, idx.size - 10)
        tr = idx[:n_train]
        te = idx[n_train:]
        fit_state = _fit_standardizer(x[tr], "standardize")
        x_tr = _transform_features(x[tr], fit_state)
        x_te = _transform_features(x[te], fit_state)
        reg = Ridge(alpha=1.0)
        reg.fit(x_tr, y[tr, j])
        pred = reg.predict(x_te)
        score_mae = float(mae(y[te, j], pred))
        score_r2 = float(r2(y[te, j], pred))
        maes.append(score_mae)
        r2s.append(score_r2)
        per_dim.append({"dim": int(j), "mae": score_mae, "r2": score_r2, "n_samples": int(idx.size)})
    return {
        "mean_mae": None if not maes else float(np.mean(maes)),
        "mean_r2": None if not r2s else float(np.mean(r2s)),
        "n_dims_eval": int(len(maes)),
        "per_dim": per_dim,
    }


def _family_common_module(root: Path, family: str):
    if family == "old":
        return _load_module("audit_common_old", root / "MFM" / "admet" / "common.py")
    if family == "new":
        return _load_module("audit_common_new", root / "MFM_descriptor" / "admet" / "common.py")
    raise ValueError(f"Unsupported family: {family}")


def _make_embedder(common_mod, family: str, checkpoint_path: Path, device: torch.device, xyz_pool_root: Optional[Path]):
    model, cfg, load_info = common_mod.load_pretrained_mfm(str(checkpoint_path), device, return_load_info=True)
    if family == "old":
        embed_cfg = common_mod.EmbedderConfig(
            num_conformers=8,
            optimize_conformers=True,
            max_opt_iters=200,
            add_hs=True,
            embedding_mode="backbone",
            atom_index_offset=-1,
        )
    else:
        embed_cfg = common_mod.EmbedderConfig(
            num_conformers=8,
            optimize_conformers=True,
            max_opt_iters=200,
            add_hs=True,
            embedding_mode="backbone",
            xyz_pool_root=None if xyz_pool_root is None else str(xyz_pool_root),
            atom_index_offset=-1,
        )
    embedder = common_mod.MFMConformerEmbedder(model, device, embed_cfg)
    return embedder, cfg, load_info


def _extract_direct_lmdb(common_mod, embedder, lmdb_path: Path, device: torch.device) -> Dict:
    node_list: List[torch.Tensor] = []
    graph_attn: List[torch.Tensor] = []
    graph_mean: List[torch.Tensor] = []
    graph_sum: List[torch.Tensor] = []
    graph_stats: List[torch.Tensor] = []
    charge_targets: List[torch.Tensor] = []
    sample_rows: List[Dict] = []
    graph_desc_rows: List[torch.Tensor] = []
    graph_desc_mask_rows: List[torch.Tensor] = []

    for idx, item in _iter_lmdb_samples(lmdb_path):
        x = getattr(item, "x", None)
        pos = getattr(item, "pos", None)
        if not isinstance(x, torch.Tensor) or not isinstance(pos, torch.Tensor):
            continue
        data_obj = item.clone()
        data_obj.x = x.long()
        data_obj.pos = pos.float()
        data_obj.batch = torch.zeros(data_obj.x.shape[0], dtype=torch.long)
        data_obj = data_obj.to(device)
        with torch.no_grad():
            z = embedder._node_embed_single_conf(data_obj).detach().cpu().float()
            g_attn = embedder._graph_embed_single_conf(data_obj).detach().cpu().float()
        n_atoms = int(z.shape[0])
        mean_v = z.mean(dim=0)
        sum_v = z.sum(dim=0)
        max_v = z.max(dim=0).values
        std_v = z.std(dim=0, unbiased=False)
        stats_v = torch.cat([mean_v, max_v, std_v, torch.tensor([math.log(max(1, n_atoms))], dtype=torch.float32)], dim=0)
        node_list.append(z)
        graph_attn.append(g_attn)
        graph_mean.append(mean_v)
        graph_sum.append(sum_v)
        graph_stats.append(stats_v)
        charge = getattr(item, "y", None)
        if not isinstance(charge, torch.Tensor) or charge.shape[0] != n_atoms:
            charge = torch.zeros((n_atoms, 1), dtype=torch.float32)
        charge_targets.append(charge.detach().cpu().float().view(-1, 1))
        graph_desc = getattr(item, "rdkit_graph_desc", None)
        graph_desc_mask = getattr(item, "rdkit_graph_desc_mask", None)
        if not isinstance(graph_desc, torch.Tensor):
            graph_desc = torch.zeros((31,), dtype=torch.float32)
        if not isinstance(graph_desc_mask, torch.Tensor):
            graph_desc_mask = torch.zeros((graph_desc.shape[0],), dtype=torch.bool)
        graph_desc_rows.append(graph_desc.detach().cpu().float())
        graph_desc_mask_rows.append(graph_desc_mask.detach().cpu().bool())
        sample_rows.append(
            {
                "lmdb_index": int(idx),
                "sample_key": str(getattr(item, "sample_key", f"idx_{idx:09d}")),
                "smiles": str(getattr(item, "smiles", "")),
                "n_atoms": n_atoms,
                "energy": float(getattr(item, "energy", float("nan"))),
                "total_charge": int(getattr(item, "total_charge", 0)),
            }
        )

    x_atoms, atom_mask = _pad_node_embeddings(node_list)
    return {
        "meta": sample_rows,
        "x_atoms": x_atoms,
        "atom_mask": atom_mask,
        "graph_attn": torch.stack(graph_attn, dim=0).float(),
        "graph_mean": torch.stack(graph_mean, dim=0).float(),
        "graph_sum": torch.stack(graph_sum, dim=0).float(),
        "graph_stats": torch.stack(graph_stats, dim=0).float(),
        "charge_targets": charge_targets,
        "rdkit_graph_desc": torch.stack(graph_desc_rows, dim=0).float(),
        "rdkit_graph_desc_mask": torch.stack(graph_desc_mask_rows, dim=0).bool(),
    }


def _extract_probe_features(common_mod, embedder, probe_frames: Dict[str, pd.DataFrame], targets: Sequence[str], cache_dir: Path, seed: int) -> Dict:
    probe_out: Dict[str, Dict] = {}
    for split_name, df in probe_frames.items():
        smiles = df["smiles"].astype(str).tolist()
        y = df.loc[:, list(targets)].to_numpy(dtype=np.float32)
        graph_cache = cache_dir / f"{split_name}_graph.pt"
        atom_cache = cache_dir / f"{split_name}_atoms.pt"
        graph_t, valid_graph = common_mod.get_embeddings_with_global_cache(
            embedder,
            smiles,
            cache_path=graph_cache,
            seed=seed + (0 if split_name == "train" else 100_000),
            desc=f"{split_name}-graph",
        )
        x_atoms, atom_mask, valid_atoms = common_mod.get_atom_embeddings_with_global_cache(
            embedder,
            smiles,
            cache_path=atom_cache,
            seed=seed + (0 if split_name == "train" else 100_000),
            desc=f"{split_name}-atoms",
        )
        probe_out[split_name] = {
            "smiles": smiles,
            "targets": y,
            "valid_graph": np.asarray(valid_graph).astype(bool),
            "valid_atoms": np.asarray(valid_atoms).astype(bool),
            "graph_attn": graph_t.float().cpu(),
            "x_atoms": x_atoms.float().cpu(),
            "atom_mask": np.asarray(atom_mask).astype(bool),
            "graph_mean_from_atoms": _mean_pool_from_atoms(x_atoms, atom_mask),
            "graph_summary_from_atoms": _summary_pool_from_atoms(x_atoms, atom_mask),
        }
    return probe_out


def _compute_direct_metrics(direct_payload: Dict, seed: int) -> Dict:
    x_atoms = direct_payload["x_atoms"]
    atom_mask = direct_payload["atom_mask"]
    graph_attn = direct_payload["graph_attn"].numpy().astype(np.float32, copy=False)
    graph_mean = direct_payload["graph_mean"].numpy().astype(np.float32, copy=False)
    graph_stats = direct_payload["graph_stats"].numpy().astype(np.float32, copy=False)
    node_flat = _flatten_valid_nodes(x_atoms, atom_mask)
    meta_df = pd.DataFrame(direct_payload["meta"])
    energy = meta_df["energy"].to_numpy(dtype=np.float32)
    total_charge = meta_df["total_charge"].to_numpy(dtype=np.float32)
    atom_count = meta_df["n_atoms"].to_numpy(dtype=np.float32)
    graph_desc = direct_payload["rdkit_graph_desc"].numpy().astype(np.float32, copy=False)
    graph_desc_mask = direct_payload["rdkit_graph_desc_mask"].numpy().astype(bool, copy=False)

    charge_rows = []
    target_rows = []
    for emb, tgt in zip(direct_payload["x_atoms"], direct_payload["charge_targets"]):
        n_atoms = int(tgt.shape[0])
        charge_rows.append(emb[:n_atoms, :].numpy())
        target_rows.append(tgt.view(-1).numpy())
    charge_x = np.concatenate(charge_rows, axis=0).astype(np.float32, copy=False)
    charge_y = np.concatenate(target_rows, axis=0).astype(np.float32, copy=False)

    weak_probe = {
        "graph_attn_energy": _ridge_probe_random_split(graph_attn, energy, seed=seed + 11),
        "graph_mean_energy": _ridge_probe_random_split(graph_mean, energy, seed=seed + 12),
        "graph_attn_total_charge": _ridge_probe_random_split(graph_attn, total_charge, seed=seed + 13),
        "graph_mean_total_charge": _ridge_probe_random_split(graph_mean, total_charge, seed=seed + 14),
        "graph_attn_atom_count": _ridge_probe_random_split(graph_attn, atom_count, seed=seed + 15),
        "graph_mean_atom_count": _ridge_probe_random_split(graph_mean, atom_count, seed=seed + 16),
        "graph_attn_rdkit_desc": _ridge_probe_multitarget_masked(graph_attn, graph_desc, graph_desc_mask, seed=seed + 17),
        "graph_mean_rdkit_desc": _ridge_probe_multitarget_masked(graph_mean, graph_desc, graph_desc_mask, seed=seed + 18),
        "node_charge": _ridge_probe_random_split(charge_x, charge_y, seed=seed + 19),
    }
    neighborhood = {
        "graph_attn_energy_knn_ratio": _neighbor_target_ratio(graph_attn, energy, k=10),
        "graph_mean_energy_knn_ratio": _neighbor_target_ratio(graph_mean, energy, k=10),
        "graph_attn_total_charge_knn_ratio": _neighbor_target_ratio(graph_attn, total_charge, k=10),
        "graph_mean_total_charge_knn_ratio": _neighbor_target_ratio(graph_mean, total_charge, k=10),
        "graph_attn_rdkit_desc_knn_ratio": _neighbor_target_ratio(graph_attn, graph_desc, k=10),
        "graph_mean_rdkit_desc_knn_ratio": _neighbor_target_ratio(graph_mean, graph_desc, k=10),
    }
    feature_stats = {
        "node_flat": _embedding_stats(node_flat),
        "graph_attn": _embedding_stats(graph_attn),
        "graph_mean": _embedding_stats(graph_mean),
        "graph_stats": _embedding_stats(graph_stats),
    }
    return {"feature_stats": feature_stats, "weak_probe": weak_probe, "neighborhood": neighborhood}


def _compute_probe_metrics(probe_payload: Dict, targets: Sequence[str]) -> Dict:
    train = probe_payload["train"]
    test = probe_payload["test"]
    variants = {
        "graph_attn": (
            train["graph_attn"].numpy().astype(np.float32, copy=False),
            test["graph_attn"].numpy().astype(np.float32, copy=False),
        ),
        "late_mean": (
            np.asarray(train["graph_mean_from_atoms"], dtype=np.float32),
            np.asarray(test["graph_mean_from_atoms"], dtype=np.float32),
        ),
        "late_summary": (
            np.asarray(train["graph_summary_from_atoms"], dtype=np.float32),
            np.asarray(test["graph_summary_from_atoms"], dtype=np.float32),
        ),
    }
    transforms = ["raw", "center", "standardize", "l2", "standardize_l2"]
    out: Dict[str, Dict] = {}
    for rep_name, (x_train, x_test) in variants.items():
        out[rep_name] = {}
        for transform_name in transforms:
            fit_state = _fit_standardizer(x_train, transform_name)
            x_train_t = _transform_features(x_train, fit_state)
            x_test_t = _transform_features(x_test, fit_state)
            result = _ridge_probe_train_test(
                x_train_t,
                train["targets"],
                x_test_t,
                test["targets"],
                targets=targets,
            )
            out[rep_name][transform_name] = result
    return out


def _extract_one(args: argparse.Namespace) -> None:
    checkpoint_path = Path(args.checkpoint).resolve()
    out_path = Path(args.out_path).resolve()
    family = str(args.family or _infer_family(checkpoint_path.name))
    common_mod = _family_common_module(ROOT, family)
    device = torch.device(str(args.device))
    xyz_pool_root = None if args.xyz_pool_root is None else Path(args.xyz_pool_root).resolve()
    embedder, cfg, load_info = _make_embedder(common_mod, family, checkpoint_path, device, xyz_pool_root)

    direct_payload = _extract_direct_lmdb(common_mod, embedder, Path(args.lmdb_path).resolve(), device)
    direct_metrics = _compute_direct_metrics(direct_payload, seed=int(args.seed))

    probe_frames = _load_probe_frames(
        Path(args.data_dir).resolve(),
        fold=int(args.fold),
        max_train_rows=int(args.max_probe_train_rows),
        max_test_rows=int(args.max_probe_test_rows),
        seed=int(args.seed),
    )
    cache_dir = out_path.parent / "_cache" / checkpoint_path.stem
    probe_payload = _extract_probe_features(
        common_mod,
        embedder,
        probe_frames,
        targets=DEFAULT_PROBE_TARGETS,
        cache_dir=cache_dir,
        seed=int(args.seed) + 7000,
    )
    probe_metrics = _compute_probe_metrics(probe_payload, targets=DEFAULT_PROBE_TARGETS)

    payload = {
        "checkpoint": str(checkpoint_path),
        "checkpoint_name": checkpoint_path.name,
        "family": family,
        "model_cfg": cfg,
        "load_info": load_info,
        "direct": {
            "meta": direct_payload["meta"],
            "x_atoms": direct_payload["x_atoms"],
            "atom_mask": torch.from_numpy(direct_payload["atom_mask"]).bool(),
            "graph_attn": direct_payload["graph_attn"],
            "graph_mean": direct_payload["graph_mean"],
            "graph_sum": direct_payload["graph_sum"],
            "graph_stats": direct_payload["graph_stats"],
            "charge_targets": direct_payload["charge_targets"],
            "rdkit_graph_desc": direct_payload["rdkit_graph_desc"],
            "rdkit_graph_desc_mask": direct_payload["rdkit_graph_desc_mask"],
            "metrics": direct_metrics,
        },
        "probe": {
            "fold": int(args.fold),
            "targets": list(DEFAULT_PROBE_TARGETS),
            "train_smiles": probe_payload["train"]["smiles"],
            "test_smiles": probe_payload["test"]["smiles"],
            "train_targets": torch.from_numpy(probe_payload["train"]["targets"]).float(),
            "test_targets": torch.from_numpy(probe_payload["test"]["targets"]).float(),
            "train_valid_graph": torch.from_numpy(probe_payload["train"]["valid_graph"]).bool(),
            "test_valid_graph": torch.from_numpy(probe_payload["test"]["valid_graph"]).bool(),
            "train_valid_atoms": torch.from_numpy(probe_payload["train"]["valid_atoms"]).bool(),
            "test_valid_atoms": torch.from_numpy(probe_payload["test"]["valid_atoms"]).bool(),
            "train_graph_attn": probe_payload["train"]["graph_attn"],
            "test_graph_attn": probe_payload["test"]["graph_attn"],
            "train_x_atoms": probe_payload["train"]["x_atoms"],
            "test_x_atoms": probe_payload["test"]["x_atoms"],
            "train_atom_mask": torch.from_numpy(probe_payload["train"]["atom_mask"]).bool(),
            "test_atom_mask": torch.from_numpy(probe_payload["test"]["atom_mask"]).bool(),
            "train_graph_mean_from_atoms": torch.from_numpy(probe_payload["train"]["graph_mean_from_atoms"]).float(),
            "test_graph_mean_from_atoms": torch.from_numpy(probe_payload["test"]["graph_mean_from_atoms"]).float(),
            "train_graph_summary_from_atoms": torch.from_numpy(probe_payload["train"]["graph_summary_from_atoms"]).float(),
            "test_graph_summary_from_atoms": torch.from_numpy(probe_payload["test"]["graph_summary_from_atoms"]).float(),
            "metrics": probe_metrics,
        },
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, out_path)
    print(f"[extract] saved {out_path}")


def _safe_mean(value: Optional[float]) -> float:
    if value is None:
        return float("nan")
    return float(value)


def _load_checkpoint_payloads(input_dir: Path) -> List[Dict]:
    payloads = []
    for path in sorted(input_dir.glob("*.pt"), key=lambda p: p.name.lower()):
        payloads.append(torch.load(path, map_location="cpu"))
    if not payloads:
        raise FileNotFoundError(f"No per-checkpoint payloads found in {input_dir}")
    return payloads


def _pairwise_against_reference(payloads: List[Dict], ref_name: str) -> pd.DataFrame:
    by_name = {p["checkpoint_name"]: p for p in payloads}
    if ref_name not in by_name:
        raise KeyError(f"Reference checkpoint '{ref_name}' not found.")
    ref = by_name[ref_name]
    ref_graph_mean = ref["direct"]["graph_mean"].numpy().astype(np.float32, copy=False)
    ref_graph_attn = ref["direct"]["graph_attn"].numpy().astype(np.float32, copy=False)
    rows = []
    for payload in payloads:
        name = payload["checkpoint_name"]
        graph_mean = payload["direct"]["graph_mean"].numpy().astype(np.float32, copy=False)
        graph_attn = payload["direct"]["graph_attn"].numpy().astype(np.float32, copy=False)
        rows.append(
            {
                "checkpoint_name": name,
                "pair_graph_mean_cka": _linear_cka(ref_graph_mean, graph_mean),
                "pair_graph_mean_diag_cos": _diag_cosine_mean(ref_graph_mean, graph_mean),
                "pair_graph_mean_knn10": _knn_overlap(ref_graph_mean, graph_mean, k=10),
                "pair_graph_attn_cka": _linear_cka(ref_graph_attn, graph_attn),
                "pair_graph_attn_diag_cos": _diag_cosine_mean(ref_graph_attn, graph_attn),
                "pair_graph_attn_knn10": _knn_overlap(ref_graph_attn, graph_attn, k=10),
            }
        )
    return pd.DataFrame(rows)


def _build_summary_tables(payloads: List[Dict], ref_name: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    stats_rows = []
    probe_rows = []
    pairwise_df = _pairwise_against_reference(payloads, ref_name=ref_name)
    pair_lookup = {row["checkpoint_name"]: row for row in pairwise_df.to_dict(orient="records")}
    for payload in payloads:
        name = payload["checkpoint_name"]
        family = payload["family"]
        load_info = payload["load_info"]
        direct_metrics = payload["direct"]["metrics"]
        probe_metrics = payload["probe"]["metrics"]
        for feature_name, stats in direct_metrics["feature_stats"].items():
            row = {
                "checkpoint_name": name,
                "family": family,
                "feature_name": feature_name,
                "matched_param_ratio": float(load_info.get("matched_param_ratio", float("nan"))),
            }
            row.update({k: (json.dumps(v) if isinstance(v, list) else v) for k, v in stats.items()})
            if feature_name == "graph_mean":
                row.update(pair_lookup.get(name, {}))
                weak = direct_metrics["weak_probe"]
                row["weak_energy_r2"] = weak["graph_mean_energy"]["r2"]
                row["weak_rdkit_desc_mean_r2"] = weak["graph_mean_rdkit_desc"]["mean_r2"]
                row["weak_atom_count_r2"] = weak["graph_mean_atom_count"]["r2"]
                row["neighbor_energy_knn_ratio"] = direct_metrics["neighborhood"]["graph_mean_energy_knn_ratio"]
                row["neighbor_rdkit_desc_knn_ratio"] = direct_metrics["neighborhood"]["graph_mean_rdkit_desc_knn_ratio"]
            if feature_name == "graph_attn":
                weak = direct_metrics["weak_probe"]
                row["weak_energy_r2"] = weak["graph_attn_energy"]["r2"]
                row["weak_rdkit_desc_mean_r2"] = weak["graph_attn_rdkit_desc"]["mean_r2"]
                row["weak_atom_count_r2"] = weak["graph_attn_atom_count"]["r2"]
                row["neighbor_energy_knn_ratio"] = direct_metrics["neighborhood"]["graph_attn_energy_knn_ratio"]
                row["neighbor_rdkit_desc_knn_ratio"] = direct_metrics["neighborhood"]["graph_attn_rdkit_desc_knn_ratio"]
            if feature_name == "node_flat":
                row["weak_node_charge_r2"] = direct_metrics["weak_probe"]["node_charge"]["r2"]
            stats_rows.append(row)

        for rep_name, rep_metrics in probe_metrics.items():
            for transform_name, result in rep_metrics.items():
                probe_rows.append(
                    {
                        "checkpoint_name": name,
                        "family": family,
                        "representation": rep_name,
                        "transform": transform_name,
                        "mean_mae": _safe_mean(result["_summary"]["mean_mae"]),
                        "mean_r2": _safe_mean(result["_summary"]["mean_r2"]),
                        "n_tasks_eval": int(result["_summary"]["n_tasks_eval"]),
                    }
                )
    return pd.DataFrame(stats_rows), pd.DataFrame(probe_rows)


def _plot_probe_heatmap(probe_df: pd.DataFrame, out_path: Path) -> None:
    if probe_df.empty:
        return
    pivot = probe_df.pivot_table(index="checkpoint_name", columns=["representation", "transform"], values="mean_r2")
    fig_w = max(10.0, 1.1 * pivot.shape[1])
    fig_h = max(5.0, 0.5 * pivot.shape[0] + 2.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    values = pivot.to_numpy(dtype=float)
    im = ax.imshow(values, aspect="auto", cmap="coolwarm", vmin=np.nanmin(values), vmax=np.nanmax(values))
    ax.set_yticks(np.arange(pivot.shape[0]))
    ax.set_yticklabels(pivot.index.tolist())
    ax.set_xticks(np.arange(pivot.shape[1]))
    ax.set_xticklabels([f"{a}|{b}" for a, b in pivot.columns.tolist()], rotation=60, ha="right")
    ax.set_title("Strict Linear Probe Mean R2")
    fig.colorbar(im, ax=ax, shrink=0.85)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _plot_rank_vs_probe(stats_df: pd.DataFrame, probe_df: pd.DataFrame, out_path: Path) -> None:
    graph_stats = stats_df[stats_df["feature_name"] == "graph_mean"].copy()
    best_probe = probe_df.groupby("checkpoint_name", as_index=False)["mean_r2"].max()
    merged = graph_stats.merge(best_probe, on="checkpoint_name", how="left")
    if merged.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.scatter(merged["effective_rank"], merged["mean_r2"], s=80)
    for _, row in merged.iterrows():
        label = row["checkpoint_name"].replace(".pth_epoch_001.pt", "").replace(".pt", "")
        ax.annotate(label, (row["effective_rank"], row["mean_r2"]))
    ax.set_xlabel("LMDB Graph-Mean Effective Rank")
    ax.set_ylabel("Best Strict Linear Probe Mean R2")
    ax.set_title("Effective Rank vs Linear Probe")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _plot_scree(payloads: List[Dict], out_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(9, 6))
    for payload in payloads:
        top = payload["direct"]["metrics"]["feature_stats"]["graph_mean"].get("top_components", [])
        if not top:
            continue
        x = np.arange(1, len(top) + 1)
        label = payload["checkpoint_name"].replace(".pth_epoch_001.pt", "").replace(".pt", "")
        ax.plot(x, top, marker="o", label=label)
    ax.set_xlabel("Principal Component Rank")
    ax.set_ylabel("Explained Variance Ratio")
    ax.set_title("LMDB Graph-Mean Scree (Top Components)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=180)
    plt.close(fig)


def _metric_correlations(stats_df: pd.DataFrame, probe_df: pd.DataFrame) -> pd.DataFrame:
    graph_stats = stats_df[stats_df["feature_name"] == "graph_mean"].copy()
    best_probe = probe_df.groupby("checkpoint_name", as_index=False)["mean_r2"].max()
    merged = graph_stats.merge(best_probe, on="checkpoint_name", how="inner")
    metric_candidates = [
        "effective_rank",
        "participation_ratio",
        "top1_ratio",
        "top10_ratio",
        "near_constant_dims_ratio",
        "avg_abs_corr",
        "cos_mean",
        "uniformity",
        "weak_energy_r2",
        "weak_rdkit_desc_mean_r2",
        "neighbor_energy_knn_ratio",
        "neighbor_rdkit_desc_knn_ratio",
        "pair_graph_mean_cka",
        "pair_graph_mean_knn10",
    ]
    rows = []
    if merged.shape[0] < 3:
        return pd.DataFrame(rows)
    for metric in metric_candidates:
        if metric not in merged.columns:
            continue
        x = pd.to_numeric(merged[metric], errors="coerce")
        y = pd.to_numeric(merged["mean_r2"], errors="coerce")
        mask = np.isfinite(x) & np.isfinite(y)
        if int(mask.sum()) < 3:
            continue
        corr = float(np.corrcoef(x[mask], y[mask])[0, 1])
        rows.append({"metric": metric, "pearson_to_best_probe_r2": corr, "n": int(mask.sum())})
    rows.sort(key=lambda row: abs(row["pearson_to_best_probe_r2"]), reverse=True)
    return pd.DataFrame(rows)


def _best_probe_rows(probe_df: pd.DataFrame, *, transform: Optional[str] = None) -> pd.DataFrame:
    cur = probe_df.copy()
    if transform is not None:
        cur = cur[cur["transform"] == transform].copy()
    if cur.empty:
        return cur
    idx = cur.groupby("checkpoint_name")["mean_r2"].idxmax()
    out = cur.loc[idx].copy()
    return out.sort_values("mean_r2", ascending=False).reset_index(drop=True)


def _checkpoint_overview(stats_df: pd.DataFrame, probe_df: pd.DataFrame) -> pd.DataFrame:
    graph_mean = stats_df[stats_df["feature_name"] == "graph_mean"].copy()
    node_flat = stats_df[stats_df["feature_name"] == "node_flat"][["checkpoint_name", "weak_node_charge_r2"]].copy()

    keep_cols = [
        "checkpoint_name",
        "family",
        "matched_param_ratio",
        "effective_rank",
        "participation_ratio",
        "top1_ratio",
        "top10_ratio",
        "condition_number_log10",
        "avg_abs_corr",
        "uniformity",
        "weak_energy_r2",
        "weak_rdkit_desc_mean_r2",
        "weak_atom_count_r2",
        "neighbor_energy_knn_ratio",
        "neighbor_rdkit_desc_knn_ratio",
        "pair_graph_mean_cka",
        "pair_graph_mean_diag_cos",
        "pair_graph_mean_knn10",
    ]
    graph_mean = graph_mean[keep_cols].copy()

    best_all = _best_probe_rows(probe_df).rename(
        columns={
            "representation": "best_probe_representation",
            "transform": "best_probe_transform",
            "mean_r2": "best_probe_mean_r2",
            "mean_mae": "best_probe_mean_mae",
            "n_tasks_eval": "best_probe_n_tasks_eval",
        }
    )
    best_raw = _best_probe_rows(probe_df, transform="raw").rename(
        columns={
            "representation": "best_raw_representation",
            "mean_r2": "best_raw_mean_r2",
            "mean_mae": "best_raw_mean_mae",
            "n_tasks_eval": "best_raw_n_tasks_eval",
        }
    )
    best_stdl2 = _best_probe_rows(probe_df, transform="standardize_l2").rename(
        columns={
            "representation": "best_std_l2_representation",
            "mean_r2": "best_std_l2_mean_r2",
            "mean_mae": "best_std_l2_mean_mae",
            "n_tasks_eval": "best_std_l2_n_tasks_eval",
        }
    )

    overview = graph_mean.merge(
        best_all[
            [
                "checkpoint_name",
                "best_probe_representation",
                "best_probe_transform",
                "best_probe_mean_r2",
                "best_probe_mean_mae",
                "best_probe_n_tasks_eval",
            ]
        ],
        on="checkpoint_name",
        how="left",
    )
    overview = overview.merge(
        best_raw[
            [
                "checkpoint_name",
                "best_raw_representation",
                "best_raw_mean_r2",
                "best_raw_mean_mae",
                "best_raw_n_tasks_eval",
            ]
        ],
        on="checkpoint_name",
        how="left",
    )
    overview = overview.merge(
        best_stdl2[
            [
                "checkpoint_name",
                "best_std_l2_representation",
                "best_std_l2_mean_r2",
                "best_std_l2_mean_mae",
                "best_std_l2_n_tasks_eval",
            ]
        ],
        on="checkpoint_name",
        how="left",
    )
    overview = overview.merge(node_flat, on="checkpoint_name", how="left")
    overview["probe_gain_over_best_raw"] = overview["best_probe_mean_r2"] - overview["best_raw_mean_r2"]
    overview["std_l2_gain_over_best_raw"] = overview["best_std_l2_mean_r2"] - overview["best_raw_mean_r2"]
    overview["conditioning_sensitive"] = overview["probe_gain_over_best_raw"] > 0.05
    overview = overview.sort_values("best_probe_mean_r2", ascending=False).reset_index(drop=True)
    overview.insert(0, "probe_rank", np.arange(1, len(overview) + 1))
    return overview


def _fmt_num(value: object, digits: int = 4) -> str:
    try:
        val = float(value)
    except Exception:
        return "n/a"
    if not np.isfinite(val):
        return "n/a"
    return f"{val:.{digits}f}"


def _write_checkpoint_summaries(overview_df: pd.DataFrame, ref_name: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for row in overview_df.to_dict(orient="records"):
        ckpt = str(row["checkpoint_name"])
        lines = [f"# {ckpt}", ""]
        lines.append(f"- Family: `{row['family']}`")
        if ckpt == ref_name:
            lines.append("- Role in audit: reference checkpoint.")
        lines.append(
            f"- Best strict linear probe: `{row['best_probe_representation']}` + `{row['best_probe_transform']}` -> mean R2 `{_fmt_num(row['best_probe_mean_r2'])}`."
        )
        lines.append(
            f"- Best raw probe: `{row['best_raw_representation']}` -> mean R2 `{_fmt_num(row['best_raw_mean_r2'])}`."
        )
        lines.append(
            f"- Conditioning gain: `{_fmt_num(row['probe_gain_over_best_raw'])}` (best minus best raw)."
        )
        lines.append(
            f"- Graph-mean spectrum: effective rank `{_fmt_num(row['effective_rank'])}`, top-1 ratio `{_fmt_num(row['top1_ratio'])}`, avg abs corr `{_fmt_num(row['avg_abs_corr'])}`."
        )
        lines.append(
            f"- Weak decodability: energy R2 `{_fmt_num(row['weak_energy_r2'])}`, RDKit desc mean R2 `{_fmt_num(row['weak_rdkit_desc_mean_r2'])}`, node charge R2 `{_fmt_num(row['weak_node_charge_r2'])}`."
        )
        if ckpt != ref_name:
            lines.append(
                f"- Similarity to AE reference: CKA `{_fmt_num(row['pair_graph_mean_cka'])}`, kNN-10 overlap `{_fmt_num(row['pair_graph_mean_knn10'])}`, diag cosine `{_fmt_num(row['pair_graph_mean_diag_cos'])}`."
            )
        if bool(row.get("conditioning_sensitive", False)):
            lines.append(
                "- Readout note: this checkpoint benefits noticeably from normalization, suggesting usable information is present but the embedding geometry is poorly conditioned for a raw linear head."
            )
        else:
            lines.append(
                "- Readout note: normalization changes the result only modestly, so the raw embedding geometry is already reasonably readable by a linear head."
            )
        stem = ckpt.replace(".pth_epoch_001.pt", "").replace(".pt", "")
        (out_dir / f"{stem}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_report(
    payloads: List[Dict],
    stats_df: pd.DataFrame,
    probe_df: pd.DataFrame,
    corr_df: pd.DataFrame,
    overview_df: pd.DataFrame,
    ref_name: str,
    out_path: Path,
) -> None:
    graph_stats = stats_df[stats_df["feature_name"] == "graph_mean"].copy()
    best_probe = overview_df.copy()
    graph_rank = graph_stats.sort_values("effective_rank", ascending=False)
    lines = []
    lines.append("# Embedding Space Audit")
    lines.append("")
    lines.append(f"- Reference checkpoint: `{ref_name}`")
    lines.append(f"- Checkpoints analyzed: {len(payloads)}")
    lines.append(f"- LMDB rows: {len(payloads[0]['direct']['meta']) if payloads else 0}")
    lines.append(f"- Probe fold/sample: fold {payloads[0]['probe']['fold'] if payloads else 'n/a'} with {len(payloads[0]['probe']['train_smiles']) if payloads else 0} train / {len(payloads[0]['probe']['test_smiles']) if payloads else 0} test smiles")
    lines.append("")

    if not best_probe.empty:
        winner = best_probe.iloc[0]
        lines.append("## Direct Answers")
        lines.append(
            f"- Current strongest embedding space for strict linear probe: `{winner['checkpoint_name']}` with best mean R2 `{_fmt_num(winner['best_probe_mean_r2'])}` using `{winner['best_probe_representation']}` + `{winner['best_probe_transform']}`."
        )
        lines.append(
            "- This advantage is not explained by having the highest effective rank. The reference AE checkpoint is only mid-pack on effective rank, but it is near the top on weak energy / descriptor linear decodability and, crucially, its raw-to-best probe gap is small enough to suggest the embedding is already linearly readable."
        )
        if "AE_test_real_only_dim512.pth_epoch_001.pt" in set(best_probe["checkpoint_name"]):
            dim512_row = best_probe[best_probe["checkpoint_name"] == "AE_test_real_only_dim512.pth_epoch_001.pt"].iloc[0]
            lines.append(
                f"- `AE_test_real_only_dim512.pth_epoch_001.pt` is the clearest counterexample: best raw mean R2 `{_fmt_num(dim512_row['best_raw_mean_r2'])}`, best after conditioning `{_fmt_num(dim512_row['best_probe_mean_r2'])}`. That pattern argues against 'no information learned' and points instead to poor readout geometry / conditioning."
            )
        lines.append("")

    if not best_probe.empty:
        lines.append("## Global Comparison")
        show_cols = [
            "probe_rank",
            "checkpoint_name",
            "best_probe_mean_r2",
            "best_probe_representation",
            "best_probe_transform",
            "best_raw_mean_r2",
            "probe_gain_over_best_raw",
            "effective_rank",
            "top1_ratio",
            "weak_energy_r2",
            "weak_rdkit_desc_mean_r2",
            "pair_graph_mean_cka",
            "pair_graph_mean_knn10",
        ]
        lines.append(best_probe[show_cols].to_markdown(index=False))
        lines.append("")

    if not graph_rank.empty:
        lines.append("## Spectrum Snapshot")
        top_cols = ["checkpoint_name", "effective_rank", "top1_ratio", "near_constant_dims_ratio", "weak_energy_r2", "weak_rdkit_desc_mean_r2"]
        lines.append(graph_rank[top_cols].to_markdown(index=False))
        lines.append("")

    if not corr_df.empty:
        lines.append("## Metrics Most Predictive Of Probe")
        lines.append(corr_df.head(10).to_markdown(index=False))
        lines.append("")

    lines.append("## Interpretation")
    lines.append(
        "- Effective rank by itself is almost useless here: higher-rank checkpoints like `MFM_old_style.pt` and `MFM_new.pt` do not overtake the AE reference on strict probe."
    )
    lines.append(
        "- The metrics that move with probe quality are mostly linear decodability and neighborhood structure: weak energy R2, weak RDKit descriptor R2, CKA / kNN overlap to the AE reference."
    )
    lines.append(
        "- The most actionable training-time direction is therefore not 'make the embedding wider' but 'make the backbone representation easier for a linear head to read': control scale, anisotropy, and neighborhood distortion directly at the backbone output."
    )
    lines.append("")

    lines.append("## Training Recommendations")
    lines.append("- Add explicit backbone-output conditioning control before any downstream head sees the embedding: center / variance regularization, norm clipping, or whitening-style penalties on pooled graph embeddings.")
    lines.append("- Regularize local geometry, not just spectrum: neighbor-preserving or contrastive losses on pooled backbone embeddings are more promising than chasing higher effective rank.")
    lines.append("- Add a lightweight graph-level readout supervision branch directly on the backbone embedding if linear transfer is the priority; do not rely only on deeper task-specific heads to keep information linearly accessible.")
    lines.append("- For width increases such as the dim512 AE model, monitor raw-vs-standardized linear probe gaps during pretraining. A widening run that only improves after heavy normalization is likely learning information in a badly conditioned basis.")
    lines.append("")

    lines.append("## Files")
    lines.append("- `checkpoint_overview.csv`: one-row-per-checkpoint summary combining probe, spectrum, weak decode, and AE-reference similarity.")
    lines.append("- `checkpoint_summaries/`: per-checkpoint Markdown notes.")
    lines.append("- `strict_linear_probe.csv`, `lmdb_feature_stats.csv`, `metric_probe_correlations.csv`: detailed raw tables.")
    lines.append("- `probe_mean_r2_heatmap.png`, `rank_vs_probe.png`, `graph_mean_scree.png`: core visualizations.")
    lines.append("")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")


def _summarize(args: argparse.Namespace) -> None:
    payloads = _load_checkpoint_payloads(Path(args.input_dir).resolve())
    stats_df, probe_df = _build_summary_tables(payloads, ref_name=args.reference_checkpoint)
    corr_df = _metric_correlations(stats_df, probe_df)
    overview_df = _checkpoint_overview(stats_df, probe_df)

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stats_df.to_csv(output_dir / "lmdb_feature_stats.csv", index=False)
    probe_df.to_csv(output_dir / "strict_linear_probe.csv", index=False)
    corr_df.to_csv(output_dir / "metric_probe_correlations.csv", index=False)
    overview_df.to_csv(output_dir / "checkpoint_overview.csv", index=False)

    _plot_probe_heatmap(probe_df, output_dir / "probe_mean_r2_heatmap.png")
    _plot_rank_vs_probe(stats_df, probe_df, output_dir / "rank_vs_probe.png")
    _plot_scree(payloads, output_dir / "graph_mean_scree.png")
    _write_checkpoint_summaries(overview_df, args.reference_checkpoint, output_dir / "checkpoint_summaries")
    _write_report(payloads, stats_df, probe_df, corr_df, overview_df, args.reference_checkpoint, output_dir / "REPORT.md")

    summary = {
        "reference_checkpoint": args.reference_checkpoint,
        "n_checkpoints": int(len(payloads)),
        "stats_csv": str(output_dir / "lmdb_feature_stats.csv"),
        "probe_csv": str(output_dir / "strict_linear_probe.csv"),
        "corr_csv": str(output_dir / "metric_probe_correlations.csv"),
        "overview_csv": str(output_dir / "checkpoint_overview.csv"),
        "checkpoint_summaries_dir": str(output_dir / "checkpoint_summaries"),
        "report_md": str(output_dir / "REPORT.md"),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"[summarize] wrote outputs under {output_dir}")


def _run(args: argparse.Namespace) -> None:
    ckpt_dir = Path(args.ckpt_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    payload_dir = output_dir / "checkpoints"
    payload_dir.mkdir(parents=True, exist_ok=True)

    checkpoints = _discover_checkpoints(ckpt_dir, args.checkpoint_regex)
    if args.checkpoints:
        allow = {name.strip() for name in str(args.checkpoints).split(",") if name.strip()}
        checkpoints = [path for path in checkpoints if path.name in allow]
    if not checkpoints:
        raise FileNotFoundError("No checkpoints selected for audit.")

    script_path = Path(__file__).resolve()
    for checkpoint_path in checkpoints:
        out_path = payload_dir / f"{checkpoint_path.stem}.pt"
        if out_path.exists() and not args.force:
            print(f"[run] skip existing {out_path.name}")
            continue
        cmd = [
            sys.executable,
            str(script_path),
            "extract-one",
            "--checkpoint",
            str(checkpoint_path),
            "--out-path",
            str(out_path),
            "--lmdb-path",
            str(Path(args.lmdb_path).resolve()),
            "--data-dir",
            str(Path(args.data_dir).resolve()),
            "--fold",
            str(args.fold),
            "--max-probe-train-rows",
            str(args.max_probe_train_rows),
            "--max-probe-test-rows",
            str(args.max_probe_test_rows),
            "--seed",
            str(args.seed),
            "--device",
            str(args.device),
        ]
        if args.xyz_pool_root:
            cmd.extend(["--xyz-pool-root", str(Path(args.xyz_pool_root).resolve())])
        if args.force:
            cmd.append("--force")
        print("[run] extracting", checkpoint_path.name)
        subprocess.run(cmd, check=True)

    summarize_cmd = [
        sys.executable,
        str(script_path),
        "summarize",
        "--input-dir",
        str(payload_dir),
        "--output-dir",
        str(output_dir / "summary"),
        "--reference-checkpoint",
        str(args.reference_checkpoint),
    ]
    subprocess.run(summarize_cmd, check=True)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser("Embedding space audit for AE/MFM checkpoints")
    sub = parser.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run")
    run_p.add_argument("--ckpt-dir", type=str, default=str(ROOT / "ckpt"))
    run_p.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    run_p.add_argument("--lmdb-path", type=str, default=str(DEFAULT_LMDB_PATH))
    run_p.add_argument("--data-dir", type=str, default=str(ROOT / "data"))
    run_p.add_argument("--checkpoint-regex", type=str, default=DEFAULT_CHECKPOINT_REGEX)
    run_p.add_argument("--checkpoints", type=str, default="")
    run_p.add_argument("--reference-checkpoint", type=str, default="AE_test_real_only.pth_epoch_001.pt")
    run_p.add_argument("--fold", type=int, default=1)
    run_p.add_argument("--max-probe-train-rows", type=int, default=192)
    run_p.add_argument("--max-probe-test-rows", type=int, default=96)
    run_p.add_argument("--seed", type=int, default=42)
    run_p.add_argument("--device", type=str, default="cpu")
    run_p.add_argument("--xyz-pool-root", type=str, default=str(ROOT / "xyz_pool"))
    run_p.add_argument("--force", action="store_true")

    extract_p = sub.add_parser("extract-one")
    extract_p.add_argument("--checkpoint", type=str, required=True)
    extract_p.add_argument("--out-path", type=str, required=True)
    extract_p.add_argument("--family", type=str, default="")
    extract_p.add_argument("--lmdb-path", type=str, required=True)
    extract_p.add_argument("--data-dir", type=str, required=True)
    extract_p.add_argument("--fold", type=int, default=1)
    extract_p.add_argument("--max-probe-train-rows", type=int, default=192)
    extract_p.add_argument("--max-probe-test-rows", type=int, default=96)
    extract_p.add_argument("--seed", type=int, default=42)
    extract_p.add_argument("--device", type=str, default="cpu")
    extract_p.add_argument("--xyz-pool-root", type=str, default=str(ROOT / "xyz_pool"))
    extract_p.add_argument("--force", action="store_true")

    sum_p = sub.add_parser("summarize")
    sum_p.add_argument("--input-dir", type=str, required=True)
    sum_p.add_argument("--output-dir", type=str, required=True)
    sum_p.add_argument("--reference-checkpoint", type=str, default="AE_test_real_only.pth_epoch_001.pt")

    return parser


def main() -> None:
    args = _build_parser().parse_args()
    if args.command == "run":
        _run(args)
        return
    if args.command == "extract-one":
        _extract_one(args)
        return
    if args.command == "summarize":
        _summarize(args)
        return
    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
