import argparse
import csv
import math
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import torch
from rdkit import Chem

from common import (
    DEFAULT_TASK_WEIGHTS,
    EmbedderConfig,
    LabelScaler,
    MFMConformerEmbedder,
    MultiTaskMoE,
    RegressionHead,
    _cfg_get,
    _rdkit_conformers,
    _strip_module_prefix,
    add_shared_parser_args,
    build_feature_loader,
    compute_metrics_table,
    get_embeddings_with_global_cache,
    load_fold_split,
    masked_weighted_mse,
    parse_fold_spec,
    parse_targets_from_args,
    prepare_task_df,
    print_metrics,
    resolve_device,
    save_json,
    set_seed,
    split_train_val,
)


def _fold_cache_path(cache_dir: str, fold: int, split: str) -> Path:
    return Path(cache_dir) / f"fold_{fold}" / f"{split}_embeddings_debug.pt"


def _fold_global_cache_path(cache_dir: str, fold: int) -> Path:
    return Path(cache_dir) / f"fold_{fold}" / "global_embeddings_debug.pt"


def _sample_df(df, limit: Optional[int], seed: int):
    if limit is None or limit <= 0 or len(df) <= limit:
        return df.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    idx = np.sort(rng.choice(np.arange(len(df)), size=int(limit), replace=False))
    return df.iloc[idx].reset_index(drop=True)


def _load_pretrained_with_diagnostics(ckpt_path: str, device: torch.device) -> Tuple[MultiTaskMoE, Dict, Dict]:
    ckpt = torch.load(ckpt_path, map_location="cpu")
    cfg = ckpt.get("cfg", {})
    bb_cfg = cfg.get("backbone_config", cfg.get("backbone_cfg", {}))
    n_atom_types = int(_cfg_get(cfg, ["n_atom_types"], 95))

    model = MultiTaskMoE(
        backbone_config=bb_cfg,
        n_atom_types=n_atom_types,
        n_experts_energy=int(_cfg_get(cfg, ["n_experts_energy", "expert_number_E"], 2)),
        n_experts_charge=int(_cfg_get(cfg, ["n_experts_charge", "expert_number_Q"], 2)),
        n_experts_elem=int(_cfg_get(cfg, ["n_experts_elem", "expert_number_Z"], 1)),
        n_experts_geom=int(_cfg_get(cfg, ["n_experts_geom", "expert_number_G"], 4)),
        top_k_energy=int(_cfg_get(cfg, ["top_k_energy", "topk_energy", "topkE"], 1)),
        top_k_charge=int(_cfg_get(cfg, ["top_k_charge", "topk_charge", "topkQ"], 1)),
        top_k_elem=int(_cfg_get(cfg, ["top_k_elem", "topk_elem", "topkZ"], 1)),
        top_k_geom=int(_cfg_get(cfg, ["top_k_geom", "topk_geom", "topkG"], 1)),
        expert_real_layers=int(_cfg_get(cfg, ["expert_real_layers", "expert_layers"], 2)),
        expert_int_layers=int(_cfg_get(cfg, ["expert_int_layers"], 0)),
        expert_heads=int(_cfg_get(cfg, ["expert_heads"], 4)),
        expert_ff_mult=int(_cfg_get(cfg, ["expert_ff_mult"], 2)),
    )

    state = ckpt.get("model_state", ckpt.get("moe_state"))
    if state is None:
        raise KeyError("Checkpoint missing 'model_state' or 'moe_state'.")
    state = _strip_module_prefix(state)
    load_info = model.load_state_dict(state, strict=False)

    model_sd = model.state_dict()
    model_keys = list(model_sd.keys())
    state_keys = set(state.keys())
    loaded_keys = [k for k in model_keys if k in state_keys]
    total_params = int(sum(v.numel() for v in model_sd.values()))
    loaded_params = int(sum(model_sd[k].numel() for k in loaded_keys))

    model.to(device)
    model.eval()

    diag = {
        "checkpoint_path": ckpt_path,
        "n_model_keys": int(len(model_keys)),
        "n_state_keys": int(len(state)),
        "n_loaded_keys": int(len(loaded_keys)),
        "key_coverage_ratio": float(len(loaded_keys) / max(1, len(model_keys))),
        "param_coverage_ratio": float(loaded_params / max(1, total_params)),
        "n_missing_keys": int(len(load_info.missing_keys)),
        "n_unexpected_keys": int(len(load_info.unexpected_keys)),
        "missing_keys_head20": list(load_info.missing_keys[:20]),
        "unexpected_keys_head20": list(load_info.unexpected_keys[:20]),
        "n_atom_types": n_atom_types,
        "latent_dim": int(getattr(model, "latent_dim")),
    }
    return model, cfg, diag


def _target_stats(df, targets: Sequence[str]) -> Dict:
    out = {}
    for t in targets:
        vals = df[t].to_numpy(dtype=np.float32)
        finite = np.isfinite(vals)
        out[t] = {
            "n_total": int(vals.shape[0]),
            "n_finite": int(finite.sum()),
            "missing_ratio": float(1.0 - finite.mean()) if vals.shape[0] > 0 else float("nan"),
            "mean": float(np.nanmean(vals)) if finite.any() else float("nan"),
            "std": float(np.nanstd(vals)) if finite.any() else float("nan"),
            "min": float(np.nanmin(vals)) if finite.any() else float("nan"),
            "max": float(np.nanmax(vals)) if finite.any() else float("nan"),
        }
    return out


def _smiles_stats(df) -> Dict:
    smiles = df["smiles"].astype(str).tolist()
    uniq = len(set(smiles))
    return {
        "n_rows": int(len(smiles)),
        "n_unique_smiles": int(uniq),
        "duplicate_ratio": float(1.0 - uniq / max(1, len(smiles))),
    }

def _atom_and_conformer_diagnostics(
    smiles_list: Sequence[str],
    *,
    n_atom_types: int,
    cfg: EmbedderConfig,
    sample_size: int,
    seed: int,
) -> Dict:
    rng = np.random.default_rng(seed)
    if len(smiles_list) == 0:
        return {}
    if len(smiles_list) <= sample_size:
        sampled = list(smiles_list)
    else:
        idx = rng.choice(np.arange(len(smiles_list)), size=int(sample_size), replace=False)
        sampled = [smiles_list[int(i)] for i in idx]

    atom_min = None
    atom_max = None
    token_min = None
    token_max = None
    invalid_low = 0
    invalid_high = 0
    invalid_mol = 0
    conf_success = 0
    conf_counts: List[int] = []
    conf_fail = 0

    t0 = time.time()
    for i, smi in enumerate(sampled):
        mol = Chem.MolFromSmiles(str(smi))
        if mol is None:
            invalid_mol += 1
            conf_fail += 1
            continue
        if cfg.add_hs:
            mol = Chem.AddHs(mol)
        atom_nums = [int(a.GetAtomicNum()) for a in mol.GetAtoms()]
        if len(atom_nums) == 0:
            invalid_mol += 1
            conf_fail += 1
            continue

        local_min = min(atom_nums)
        local_max = max(atom_nums)
        atom_min = local_min if atom_min is None else min(atom_min, local_min)
        atom_max = local_max if atom_max is None else max(atom_max, local_max)

        token_ids = [a + int(cfg.atom_index_offset) for a in atom_nums]
        local_tmin = min(token_ids)
        local_tmax = max(token_ids)
        token_min = local_tmin if token_min is None else min(token_min, local_tmin)
        token_max = local_tmax if token_max is None else max(token_max, local_tmax)
        invalid_low += int(sum(1 for x in token_ids if x < 0))
        invalid_high += int(sum(1 for x in token_ids if x >= n_atom_types))

        conf_pack = _rdkit_conformers(
            smiles=str(smi),
            num_conformers=cfg.num_conformers,
            seed=seed + i,
            optimize=cfg.optimize_conformers,
            max_opt_iters=cfg.max_opt_iters,
            add_hs=cfg.add_hs,
        )
        if conf_pack is None:
            conf_fail += 1
            continue
        _, conf_ids = conf_pack
        conf_success += 1
        conf_counts.append(int(len(conf_ids)))

    dt = time.time() - t0
    conf_counts_np = np.asarray(conf_counts, dtype=np.float32) if conf_counts else np.asarray([], dtype=np.float32)
    return {
        "n_checked_smiles": int(len(sampled)),
        "invalid_smiles_count": int(invalid_mol),
        "atom_num_min": None if atom_min is None else int(atom_min),
        "atom_num_max": None if atom_max is None else int(atom_max),
        "token_min_after_offset": None if token_min is None else int(token_min),
        "token_max_after_offset": None if token_max is None else int(token_max),
        "invalid_token_low_count": int(invalid_low),
        "invalid_token_high_count": int(invalid_high),
        "conformer_success_rate": float(conf_success / max(1, len(sampled))),
        "conformer_count_mean": float(conf_counts_np.mean()) if conf_counts_np.size > 0 else float("nan"),
        "conformer_count_min": float(conf_counts_np.min()) if conf_counts_np.size > 0 else float("nan"),
        "conformer_count_max": float(conf_counts_np.max()) if conf_counts_np.size > 0 else float("nan"),
        "elapsed_sec": float(dt),
    }


def _embedding_diagnostics(
    embedder: MFMConformerEmbedder,
    smiles_list: Sequence[str],
    *,
    seed: int,
    sample_size: int,
    xyz_root: Optional[Path] = None,
) -> Dict:
    rng = np.random.default_rng(seed)
    if len(smiles_list) == 0:
        return {}
    if len(smiles_list) <= sample_size:
        sampled = list(smiles_list)
    else:
        idx = rng.choice(np.arange(len(smiles_list)), size=int(sample_size), replace=False)
        sampled = [smiles_list[int(i)] for i in idx]

    sample_xyz_root = None if xyz_root is None else (xyz_root / "sample")
    x, valid = embedder.embed_smiles_list(
        sampled,
        seed=seed,
        desc="Debug-embed-sample",
        xyz_root=sample_xyz_root,
    )
    x_np = x.numpy()
    norms = np.linalg.norm(x_np, axis=1)
    per_dim_std = np.std(x_np, axis=0)

    # Same seed should produce almost identical embedding (determinism check).
    det_count = min(8, len(sampled))
    det_diffs = []
    for i in range(det_count):
        det_xyz_root = None if xyz_root is None else (xyz_root / "determinism")
        a, _ = embedder.embed_smiles_with_xyz(
            sampled[i],
            seed=seed + i,
            xyz_root=det_xyz_root,
            row_tag=f"det_{i:03d}_a",
        )
        b, _ = embedder.embed_smiles_with_xyz(
            sampled[i],
            seed=seed + i,
            xyz_root=det_xyz_root,
            row_tag=f"det_{i:03d}_b",
        )
        det_diffs.append(float(torch.norm(a - b, p=2).item()))

    # Different seed should usually produce some difference for 3D conformer tokenization.
    var_count = min(8, len(sampled))
    var_diffs = []
    for i in range(var_count):
        var_xyz_root = None if xyz_root is None else (xyz_root / "seed_variation")
        a, _ = embedder.embed_smiles_with_xyz(
            sampled[i],
            seed=seed + i,
            xyz_root=var_xyz_root,
            row_tag=f"var_{i:03d}_seed_a",
        )
        b, _ = embedder.embed_smiles_with_xyz(
            sampled[i],
            seed=seed + 10000 + i,
            xyz_root=var_xyz_root,
            row_tag=f"var_{i:03d}_seed_b",
        )
        var_diffs.append(float(torch.norm(a - b, p=2).item()))

    return {
        "n_checked_smiles": int(len(sampled)),
        "latent_dim": int(x_np.shape[1]),
        "valid_rate": float(valid.mean()) if len(valid) > 0 else float("nan"),
        "nan_count": int(np.isnan(x_np).sum()),
        "inf_count": int(np.isinf(x_np).sum()),
        "embedding_mean": float(np.mean(x_np)),
        "embedding_std": float(np.std(x_np)),
        "norm_mean": float(np.mean(norms)),
        "norm_std": float(np.std(norms)),
        "norm_min": float(np.min(norms)),
        "norm_max": float(np.max(norms)),
        "per_dim_std_mean": float(np.mean(per_dim_std)),
        "determinism_l2_diff_mean": float(np.mean(det_diffs)) if det_diffs else float("nan"),
        "different_seed_l2_diff_mean": float(np.mean(var_diffs)) if var_diffs else float("nan"),
    }


def _feature_stats(name: str, x: np.ndarray) -> Dict:
    norms = np.linalg.norm(x, axis=1) if x.size > 0 else np.asarray([], dtype=np.float32)
    return {
        "name": name,
        "shape": [int(x.shape[0]), int(x.shape[1])],
        "nan_count": int(np.isnan(x).sum()),
        "inf_count": int(np.isinf(x).sum()),
        "mean": float(np.mean(x)) if x.size > 0 else float("nan"),
        "std": float(np.std(x)) if x.size > 0 else float("nan"),
        "norm_mean": float(np.mean(norms)) if norms.size > 0 else float("nan"),
        "norm_std": float(np.std(norms)) if norms.size > 0 else float("nan"),
    }


def _global_grad_norm(model: torch.nn.Module) -> float:
    sq = 0.0
    for p in model.parameters():
        if p.grad is None:
            continue
        val = float(p.grad.detach().data.norm(2).item())
        sq += val * val
    return math.sqrt(sq) if sq > 0 else 0.0

def _epoch_debug_train(
    model: torch.nn.Module,
    loader,
    *,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
    task_weights_t: Optional[torch.Tensor],
) -> Dict:
    model.train(True)
    total_loss = 0.0
    n_batches = 0
    grad_norms = []
    pred_stds = []
    nan_pred_batches = 0
    for xb, yb, mb in loader:
        xb = xb.to(device)
        yb = yb.to(device)
        mb = mb.to(device)
        optimizer.zero_grad(set_to_none=True)
        pred = model(xb)
        if not torch.isfinite(pred).all():
            nan_pred_batches += 1
        loss = masked_weighted_mse(pred, yb, mb, task_weights_t)
        loss.backward()
        grad_norms.append(_global_grad_norm(model))
        optimizer.step()

        total_loss += float(loss.item())
        n_batches += 1
        pred_stds.append(float(pred.detach().std().item()))
    return {
        "loss": float(total_loss / max(1, n_batches)),
        "grad_norm_mean": float(np.mean(grad_norms)) if grad_norms else float("nan"),
        "grad_norm_max": float(np.max(grad_norms)) if grad_norms else float("nan"),
        "pred_std_mean": float(np.mean(pred_stds)) if pred_stds else float("nan"),
        "nan_pred_batches": int(nan_pred_batches),
    }


@torch.no_grad()
def _epoch_debug_eval(
    model: torch.nn.Module,
    loader,
    *,
    device: torch.device,
    task_weights_t: Optional[torch.Tensor],
) -> Dict:
    model.train(False)
    total_loss = 0.0
    n_batches = 0
    pred_stds = []
    nan_pred_batches = 0
    for xb, yb, mb in loader:
        xb = xb.to(device)
        yb = yb.to(device)
        mb = mb.to(device)
        pred = model(xb)
        if not torch.isfinite(pred).all():
            nan_pred_batches += 1
        loss = masked_weighted_mse(pred, yb, mb, task_weights_t)
        total_loss += float(loss.item())
        n_batches += 1
        pred_stds.append(float(pred.detach().std().item()))
    return {
        "loss": float(total_loss / max(1, n_batches)),
        "pred_std_mean": float(np.mean(pred_stds)) if pred_stds else float("nan"),
        "nan_pred_batches": int(nan_pred_batches),
    }


def _predict_numpy(model: torch.nn.Module, x_np: np.ndarray, device: torch.device, batch_size: int = 1024) -> np.ndarray:
    model.eval()
    out = []
    for i in range(0, x_np.shape[0], batch_size):
        xb = torch.from_numpy(x_np[i : i + batch_size]).float().to(device)
        with torch.no_grad():
            out.append(model(xb).cpu().numpy())
    return np.concatenate(out, axis=0) if out else np.zeros((0, 0), dtype=np.float32)


def _mean_baseline_from_train(y_train: np.ndarray, y_eval: np.ndarray) -> np.ndarray:
    train_mean = np.nanmean(y_train, axis=0)
    train_mean[~np.isfinite(train_mean)] = 0.0
    pred = np.repeat(train_mean[None, :], y_eval.shape[0], axis=0)
    return pred.astype(np.float32)


def _mae_dict(y_true: np.ndarray, y_pred: np.ndarray, targets: Sequence[str]) -> Dict[str, float]:
    out = {}
    for i, t in enumerate(targets):
        mask = np.isfinite(y_true[:, i])
        out[t] = float(np.mean(np.abs(y_true[mask, i] - y_pred[mask, i]))) if mask.sum() > 0 else float("nan")
    return out


def _build_red_flags(report: Dict) -> List[str]:
    flags: List[str] = []
    ckpt = report["pretrained_debug"]
    if ckpt["param_coverage_ratio"] < 0.99:
        flags.append(f"pretrained param coverage too low: {ckpt['param_coverage_ratio']:.4f}")
    if ckpt["n_missing_keys"] > 0:
        flags.append(f"pretrained missing keys: {ckpt['n_missing_keys']}")

    atom = report["atom_conformer_debug"]
    if atom.get("invalid_token_low_count", 0) > 0 or atom.get("invalid_token_high_count", 0) > 0:
        flags.append(
            "atom token out-of-range detected "
            f"(low={atom.get('invalid_token_low_count', 0)}, high={atom.get('invalid_token_high_count', 0)})"
        )
    emb = report["embedding_debug"]
    if emb.get("valid_rate", 1.0) < 0.98:
        flags.append(f"embedding valid rate low: {emb['valid_rate']:.4f}")
    if emb.get("per_dim_std_mean", 1.0) < 1e-4:
        flags.append(f"embedding may be collapsed: per_dim_std_mean={emb['per_dim_std_mean']:.6e}")

    learning = report["learning_debug"]
    if learning.get("train_loss_drop_ratio", 1.0) < 1.05:
        flags.append(f"train loss drop is weak: ratio={learning['train_loss_drop_ratio']:.4f}")
    if learning.get("train_mae_gain_mean", 1.0) < 0:
        flags.append(f"model MAE worse than mean baseline on train: gain={learning['train_mae_gain_mean']:.6f}")
    return flags


def _write_epoch_csv(path: Path, rows: List[Dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    keys = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def _np_targets(df, targets):
    return df.loc[:, targets].to_numpy(dtype=np.float32)

def run_fold_debug(
    args,
    fold: int,
    *,
    targets: List[str],
    embedder: MFMConformerEmbedder,
    ckpt_debug: Dict,
    n_atom_types: int,
    device: torch.device,
) -> Dict:
    raw_train = load_fold_split(args.data_dir, fold, "train")
    raw_test = load_fold_split(args.data_dir, fold, "test")
    train_df = prepare_task_df(raw_train, targets)
    test_df = prepare_task_df(raw_test, targets)

    train_df = _sample_df(train_df, args.max_train_rows, args.seed + fold * 11)
    test_df = _sample_df(test_df, args.max_test_rows, args.seed + fold * 13)

    tr_idx, va_idx = split_train_val(len(train_df), args.val_frac, args.seed + fold)
    train_sub = train_df.iloc[tr_idx].reset_index(drop=True)
    val_sub = train_df.iloc[va_idx].reset_index(drop=True)
    val_sub = _sample_df(val_sub, args.max_val_rows, args.seed + fold * 17)

    atom_diag = _atom_and_conformer_diagnostics(
        train_sub["smiles"].tolist(),
        n_atom_types=n_atom_types,
        cfg=embedder.cfg,
        sample_size=args.debug_smiles_samples,
        seed=args.seed + fold * 100,
    )
    diag_xyz_root = None
    if args.cache_dir:
        diag_xyz_root = Path(args.cache_dir) / f"fold_{fold}" / "xyz" / "embedding_diagnostics"

    emb_diag = _embedding_diagnostics(
        embedder,
        train_sub["smiles"].tolist(),
        seed=args.seed + fold * 1000,
        sample_size=args.debug_smiles_samples,
        xyz_root=diag_xyz_root,
    )

    train_cache = None
    val_cache = None
    test_cache = None
    global_cache = None
    if args.cache_dir:
        global_cache = _fold_global_cache_path(args.cache_dir, fold)
        if args.cache_mode == "split":
            train_cache = _fold_cache_path(args.cache_dir, fold, "train")
            val_cache = _fold_cache_path(args.cache_dir, fold, "val")
            test_cache = _fold_cache_path(args.cache_dir, fold, "test")

    if args.cache_mode == "global":
        x_train_t, valid_train = get_embeddings_with_global_cache(
            embedder, train_sub["smiles"].tolist(), cache_path=global_cache, seed=args.seed + fold * 1000, desc=f"F{fold}-dbg-tr"
        )
        x_val_t, valid_val = get_embeddings_with_global_cache(
            embedder, val_sub["smiles"].tolist(), cache_path=global_cache, seed=args.seed + fold * 1000 + 100_000, desc=f"F{fold}-dbg-va"
        )
        x_test_t, valid_test = get_embeddings_with_global_cache(
            embedder, test_df["smiles"].tolist(), cache_path=global_cache, seed=args.seed + fold * 1000 + 200_000, desc=f"F{fold}-dbg-te"
        )
    else:
        x_train_t, valid_train = get_embeddings_with_global_cache(
            embedder, train_sub["smiles"].tolist(), cache_path=train_cache, seed=args.seed + fold * 1000, desc=f"F{fold}-dbg-tr"
        )
        x_val_t, valid_val = get_embeddings_with_global_cache(
            embedder, val_sub["smiles"].tolist(), cache_path=val_cache, seed=args.seed + fold * 1000 + 100_000, desc=f"F{fold}-dbg-va"
        )
        x_test_t, valid_test = get_embeddings_with_global_cache(
            embedder, test_df["smiles"].tolist(), cache_path=test_cache, seed=args.seed + fold * 1000 + 200_000, desc=f"F{fold}-dbg-te"
        )

    x_train = x_train_t.numpy()
    x_val = x_val_t.numpy()
    x_test = x_test_t.numpy()
    y_train = _np_targets(train_sub, targets)
    y_val = _np_targets(val_sub, targets)
    y_test = _np_targets(test_df, targets)
    mask_train = np.isfinite(y_train)
    mask_val = np.isfinite(y_val)

    scaler = LabelScaler.fit(y_train)
    y_train_scaled = scaler.transform(y_train)
    y_val_scaled = scaler.transform(y_val)
    train_loader = build_feature_loader(x_train, y_train_scaled, mask_train, batch_size=args.batch_size, shuffle=True)
    val_loader = build_feature_loader(x_val, y_val_scaled, mask_val, batch_size=args.batch_size, shuffle=False)

    model = RegressionHead(
        in_dim=x_train.shape[1],
        out_dim=len(targets),
        hidden_dim=args.hidden_dim,
        n_layers=args.head_layers,
        dropout=args.dropout,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)

    if args.mode == "mt":
        if args.task_weights:
            task_weights = np.asarray([float(x) for x in args.task_weights.split(",")], dtype=np.float32)
            if task_weights.shape[0] != len(targets):
                raise ValueError("task_weights length must match number of targets.")
        else:
            task_weights = np.asarray(DEFAULT_TASK_WEIGHTS[: len(targets)], dtype=np.float32)
        task_weights_t = torch.from_numpy(task_weights).float().to(device)
    else:
        task_weights_t = None

    fold_dir = Path(args.output_dir) / f"fold_{fold}"
    model_dir = fold_dir / "model_files"
    model_dir.mkdir(parents=True, exist_ok=True)

    best_val = float("inf")
    best_payload = None
    bad_epochs = 0
    epoch_rows: List[Dict] = []
    first_train_loss = None
    for epoch in range(1, args.epochs + 1):
        train_dbg = _epoch_debug_train(model, train_loader, optimizer=optimizer, device=device, task_weights_t=task_weights_t)
        val_dbg = _epoch_debug_eval(model, val_loader, device=device, task_weights_t=task_weights_t)
        if first_train_loss is None:
            first_train_loss = train_dbg["loss"]
        lr = float(optimizer.param_groups[0]["lr"])
        print(
            f"[Debug Fold {fold}] epoch={epoch:03d} train_loss={train_dbg['loss']:.6f} "
            f"val_loss={val_dbg['loss']:.6f} grad_norm={train_dbg['grad_norm_mean']:.6f} lr={lr:.6g}"
        )
        epoch_rows.append(
            {
                "epoch": int(epoch),
                "train_loss": float(train_dbg["loss"]),
                "val_loss": float(val_dbg["loss"]),
                "lr": lr,
                "grad_norm_mean": float(train_dbg["grad_norm_mean"]),
                "grad_norm_max": float(train_dbg["grad_norm_max"]),
                "train_pred_std_mean": float(train_dbg["pred_std_mean"]),
                "val_pred_std_mean": float(val_dbg["pred_std_mean"]),
                "train_nan_pred_batches": int(train_dbg["nan_pred_batches"]),
                "val_nan_pred_batches": int(val_dbg["nan_pred_batches"]),
            }
        )

        payload = {
            "head_state": model.state_dict(),
            "targets": targets,
            "mode": args.mode,
            "target_scaler": scaler.to_dict(),
            "embedding_dim": int(x_train.shape[1]),
            "head_cfg": {"hidden_dim": int(args.hidden_dim), "head_layers": int(args.head_layers), "dropout": float(args.dropout)},
            "feature_cfg": {
                "num_conformers": int(args.num_conformers),
                "optimize_conformers": bool(args.optimize_conformers),
                "max_opt_iters": int(args.max_opt_iters),
                "add_hs": bool(args.add_hs),
                "embedding_mode": str(args.embedding_mode),
                "atom_index_offset": int(args.atom_index_offset),
            },
            "pretrained_ckpt": args.pretrained_ckpt,
            "epoch": int(epoch),
            "train_loss": float(train_dbg["loss"]),
            "val_loss": float(val_dbg["loss"]),
        }
        torch.save(payload, model_dir / "last.pt")
        if val_dbg["loss"] < best_val:
            best_val = float(val_dbg["loss"])
            best_payload = payload
            bad_epochs = 0
            torch.save(payload, model_dir / "best.pt")
        else:
            bad_epochs += 1
            if bad_epochs >= args.patience:
                print(f"[Debug Fold {fold}] early stop at epoch {epoch}")
                break

    _write_epoch_csv(fold_dir / "epoch_debug.csv", epoch_rows)
    if best_payload is None:
        raise RuntimeError("No checkpoint saved during debug training.")
    model.load_state_dict(best_payload["head_state"])
    model.eval()

    y_train_pred = scaler.inverse(_predict_numpy(model, x_train, device))
    y_val_pred = scaler.inverse(_predict_numpy(model, x_val, device))
    y_test_pred = scaler.inverse(_predict_numpy(model, x_test, device))

    train_metrics = compute_metrics_table(y_train, y_train_pred, targets)
    val_metrics = compute_metrics_table(y_val, y_val_pred, targets)
    test_metrics = compute_metrics_table(y_test, y_test_pred, targets)

    print(f"[Debug Fold {fold}] train metrics")
    print_metrics(train_metrics)
    print(f"[Debug Fold {fold}] val metrics")
    print_metrics(val_metrics)
    print(f"[Debug Fold {fold}] test metrics")
    print_metrics(test_metrics)

    train_base_pred = _mean_baseline_from_train(y_train, y_train)
    train_base_mae = _mae_dict(y_train, train_base_pred, targets)
    train_model_mae = {t: train_metrics[t]["mae"] for t in targets}
    train_gain = {t: float(train_base_mae[t] - train_model_mae[t]) for t in targets}

    train_loss_drop_ratio = float(first_train_loss / max(1e-12, epoch_rows[-1]["train_loss"])) if epoch_rows else float("nan")
    learning_debug = {
        "best_val_loss": float(best_val),
        "first_train_loss": float(first_train_loss) if first_train_loss is not None else float("nan"),
        "last_train_loss": float(epoch_rows[-1]["train_loss"]) if epoch_rows else float("nan"),
        "train_loss_drop_ratio": train_loss_drop_ratio,
        "n_epochs_run": int(len(epoch_rows)),
        "train_baseline_mae": train_base_mae,
        "train_model_mae": train_model_mae,
        "train_mae_gain_vs_baseline": train_gain,
        "train_mae_gain_mean": float(np.nanmean(list(train_gain.values()))) if train_gain else float("nan"),
    }

    report = {
        "fold": int(fold),
        "mode": args.mode,
        "targets": targets,
        "pretrained_debug": ckpt_debug,
        "data_debug": {
            "train_stats": _smiles_stats(train_sub),
            "val_stats": _smiles_stats(val_sub),
            "test_stats": _smiles_stats(test_df),
            "train_targets": _target_stats(train_sub, targets),
            "val_targets": _target_stats(val_sub, targets),
            "test_targets": _target_stats(test_df, targets),
        },
        "atom_conformer_debug": atom_diag,
        "embedding_debug": emb_diag,
        "feature_debug": {
            "train": _feature_stats("train", x_train),
            "val": _feature_stats("val", x_val),
            "test": _feature_stats("test", x_test),
            "embed_valid_train": int(valid_train.sum()),
            "embed_valid_val": int(valid_val.sum()),
            "embed_valid_test": int(valid_test.sum()),
        },
        "learning_debug": learning_debug,
        "metrics_train": train_metrics,
        "metrics_val": val_metrics,
        "metrics_test": test_metrics,
    }
    report["red_flags"] = _build_red_flags(report)
    save_json(fold_dir / "debug_report.json", report)
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("Debug train/validate script for MFM ADMET")
    add_shared_parser_args(p)
    p.add_argument("--output_dir", type=str, required=True)
    p.add_argument("--val_frac", type=float, default=0.1)
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--patience", type=int, default=10)
    p.add_argument("--batch_size", type=int, default=32)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--weight_decay", type=float, default=1e-4)
    p.add_argument("--hidden_dim", type=int, default=512)
    p.add_argument("--head_layers", type=int, default=2)
    p.add_argument("--dropout", type=float, default=0.1)
    p.add_argument("--task_weights", type=str, default=None)
    p.add_argument("--cache_mode", type=str, choices=["global", "split"], default="global")
    p.add_argument("--max_train_rows", type=int, default=0)
    p.add_argument("--max_val_rows", type=int, default=0)
    p.add_argument("--max_test_rows", type=int, default=0)
    p.add_argument("--debug_smiles_samples", type=int, default=200)
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    set_seed(args.seed)
    if not args.pretrained_ckpt:
        raise ValueError("train_debug.py requires --pretrained_ckpt.")
    print("Debug args:", vars(args))

    targets = parse_targets_from_args(args.mode, args.target, args.targets)
    folds = parse_fold_spec(args.folds)
    device = resolve_device(args.device)

    model, cfg, ckpt_diag = _load_pretrained_with_diagnostics(args.pretrained_ckpt, device)
    n_atom_types = int(ckpt_diag["n_atom_types"])
    embedder_cfg = EmbedderConfig(
        num_conformers=args.num_conformers,
        optimize_conformers=bool(args.optimize_conformers),
        max_opt_iters=args.max_opt_iters,
        add_hs=bool(args.add_hs),
        embedding_mode=str(args.embedding_mode),
        atom_index_offset=args.atom_index_offset,
    )
    embedder = MFMConformerEmbedder(model, device, embedder_cfg)

    all_reports = []
    for fold in folds:
        all_reports.append(
            run_fold_debug(
                args,
                fold=fold,
                targets=targets,
                embedder=embedder,
                ckpt_debug=ckpt_diag,
                n_atom_types=n_atom_types,
                device=device,
            )
        )

    overview = {
        "mode": args.mode,
        "folds": folds,
        "targets": targets,
        "n_folds": int(len(folds)),
        "pretrained_debug": ckpt_diag,
        "red_flags_total": int(sum(len(r["red_flags"]) for r in all_reports)),
        "fold_red_flags": {f"fold_{r['fold']}": r["red_flags"] for r in all_reports},
        "cfg_backbone_keys": sorted(list(cfg.get("backbone_config", cfg.get("backbone_cfg", {})).keys())),
    }
    save_json(Path(args.output_dir) / "debug_overview.json", overview)
    print("Debug run complete.")


if __name__ == "__main__":
    main()
