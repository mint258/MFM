import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gc
import math
import multiprocessing as mp
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch

from common import (
    AtomwiseLatePoolRegressionHead,
    DEFAULT_TASK_WEIGHTS,
    EmbedderConfig,
    EmbeddingTransform,
    LabelScaler,
    MFMConformerEmbedder,
    RegressionHead,
    add_shared_parser_args,
    build_atom_feature_loader,
    build_feature_loader,
    compute_metrics_table,
    get_atom_embeddings_with_global_cache,
    get_embeddings_with_global_cache,
    load_fold_split,
    load_pretrained_mfm,
    parse_fold_spec,
    parse_targets_from_args,
    prepare_task_df,
    print_metrics,
    resolve_device,
    resolve_embedding_and_pooling,
    run_epoch,
    save_json,
    select_best_checkpoint,
    set_seed,
    split_train_val,
)


def _fold_cache_path(cache_dir: str, fold: int, split: str) -> Path:
    return Path(cache_dir) / f"fold_{fold}" / f"{split}_embeddings.pt"


def _fold_conf_atom_cache_path(cache_dir: str, fold: int, split: str) -> Path:
    return Path(cache_dir) / f"fold_{fold}" / f"{split}_conf_atom_embeddings.pt"


def _fold_global_cache_path(cache_dir: str, fold: int, *, use_late_pooling: bool) -> Path:
    cache_name = "global_conf_atom_embeddings.pt" if use_late_pooling else "global_embeddings.pt"
    return Path(cache_dir) / f"fold_{fold}" / cache_name


def _shared_global_cache_path(cache_dir: str, *, use_late_pooling: bool) -> Path:
    cache_name = "global_conf_atom_embeddings.pt" if use_late_pooling else "global_embeddings.pt"
    return Path(cache_dir) / cache_name


def _resolve_global_cache_path(
    cache_dir: str,
    *,
    fold: int,
    use_late_pooling: bool,
    scope: str,
) -> Path:
    scope_l = str(scope).lower()
    if scope_l == "fold":
        return _fold_global_cache_path(cache_dir, fold, use_late_pooling=use_late_pooling)
    return _shared_global_cache_path(cache_dir, use_late_pooling=use_late_pooling)


def _effective_cache_dir(args) -> str:
    return str(args.cache_dir) if args.cache_dir else str(Path(args.output_dir) / "_embedding_cache")


DEFAULT_FINETUNE_FEATURE_DEVICE_LIMIT_MB = 1024.0
AUTO_FINETUNE_FEATURE_CUDA_HEADROOM_MB = 2048.0
AUTO_FINETUNE_FEATURE_CUDA_MAX_FRACTION = 0.6


def _feature_dir(output_dir: str, fold: int) -> Path:
    return Path(output_dir) / f"fold_{fold}" / "features"


def _np_targets(df, targets):
    return df.loc[:, targets].to_numpy(dtype=np.float32)


def _sample_df(df, max_rows: int, seed: int):
    if max_rows is None or int(max_rows) <= 0 or len(df) <= int(max_rows):
        return df
    return df.sample(n=int(max_rows), random_state=int(seed)).reset_index(drop=True)


def _save_feature_tensor(
    path: Path,
    x: np.ndarray,
    y: np.ndarray,
    mask: np.ndarray,
    *,
    smiles: List[str],
    valid: np.ndarray,
    feature_signature: Dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "X": torch.from_numpy(x).float(),
            "Y": torch.from_numpy(y).float(),
            "mask": torch.from_numpy(mask).bool(),
            "smiles": list(smiles),
            "valid": torch.from_numpy(valid).bool(),
            "feature_signature": dict(feature_signature),
        },
        path,
    )


def _save_atom_feature_tensor(
    path: Path,
    x_atoms: torch.Tensor,
    atom_mask: np.ndarray,
    y: np.ndarray,
    mask: np.ndarray,
    *,
    smiles: List[str],
    valid: np.ndarray,
    feature_signature: Dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "X_atoms": x_atoms.float().cpu(),
            "atom_mask": torch.from_numpy(atom_mask).bool(),
            "Y": torch.from_numpy(y).float(),
            "mask": torch.from_numpy(mask).bool(),
            "smiles": list(smiles),
            "valid": torch.from_numpy(valid).bool(),
            "feature_signature": dict(feature_signature),
        },
        path,
    )


def _checkpoint_fingerprint(checkpoint_path: str) -> Dict[str, object]:
    p = Path(checkpoint_path).expanduser().resolve()
    stat = p.stat()
    return {
        "path": str(p),
        "size_bytes": int(stat.st_size),
        "mtime_ns": int(stat.st_mtime_ns),
    }


def _feature_signature(
    *,
    args,
    targets: List[str],
    base_embedding_mode: str,
    pooling_timing: str,
    effective_pretrained_ckpt: str,
) -> Dict[str, object]:
    return {
        "arch": str(args.arch),
        "mode": str(args.mode),
        "targets": list(targets),
        "embedding_mode": str(base_embedding_mode),
        "embedding_mode_arg": str(args.embedding_mode),
        "pooling_timing": str(pooling_timing),
        "num_conformers": int(args.num_conformers),
        "optimize_conformers": bool(args.optimize_conformers),
        "max_opt_iters": int(args.max_opt_iters),
        "add_hs": bool(args.add_hs),
        "atom_index_offset": int(args.atom_index_offset),
        "pretrained_ckpt": _checkpoint_fingerprint(effective_pretrained_ckpt),
    }


def _to_numpy_bool(value) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy().astype(bool)
    return np.asarray(value).astype(bool)


def _to_numpy_float32(value) -> np.ndarray:
    if isinstance(value, torch.Tensor):
        return value.detach().cpu().numpy().astype(np.float32)
    return np.asarray(value, dtype=np.float32)


def _sample_fit_rows(x_2d: torch.Tensor, *, max_rows: int, seed: int) -> np.ndarray:
    if x_2d.dim() != 2:
        raise ValueError(f"x_2d must be [N, D], got shape={tuple(x_2d.shape)}")
    n = int(x_2d.shape[0])
    if n <= 0:
        return np.zeros((0, int(x_2d.shape[1])), dtype=np.float32)
    if max_rows is None or int(max_rows) <= 0 or n <= int(max_rows):
        return x_2d.detach().cpu().numpy().astype(np.float32, copy=False)
    rng = np.random.default_rng(int(seed))
    idx = rng.choice(n, size=int(max_rows), replace=False)
    idx_t = torch.as_tensor(idx, dtype=torch.long)
    return x_2d.index_select(0, idx_t).detach().cpu().numpy().astype(np.float32, copy=False)


def _fit_embedding_transform_early(
    *,
    x_train_t: torch.Tensor,
    valid_train: np.ndarray,
    pca_dim: int,
    max_fit_rows: int,
    standardize: bool,
    eps: float,
    seed: int,
) -> Optional[EmbeddingTransform]:
    valid_mask = _to_numpy_bool(valid_train).reshape(-1)
    if valid_mask.shape[0] != int(x_train_t.shape[0]):
        valid_mask = np.ones((int(x_train_t.shape[0]),), dtype=bool)
    if int(valid_mask.sum()) <= 0:
        valid_mask = np.ones((int(x_train_t.shape[0]),), dtype=bool)
    fit_rows = x_train_t[torch.from_numpy(valid_mask).bool()]
    fit_np = _sample_fit_rows(fit_rows, max_rows=int(max_fit_rows), seed=int(seed))
    if fit_np.shape[0] <= 0:
        return None
    return EmbeddingTransform.fit(
        fit_np,
        standardize=bool(standardize),
        pca_dim=int(pca_dim),
        eps=float(eps),
    )


def _fit_embedding_transform_late_atomwise(
    *,
    x_train_atoms_t: torch.Tensor,
    atom_mask_train: np.ndarray,
    valid_train: np.ndarray,
    pca_dim: int,
    max_fit_rows: int,
    standardize: bool,
    eps: float,
    seed: int,
) -> Optional[EmbeddingTransform]:
    if x_train_atoms_t.dim() != 3:
        raise ValueError(f"x_train_atoms_t must be [B, N, D], got shape={tuple(x_train_atoms_t.shape)}")
    bsz = int(x_train_atoms_t.shape[0])
    atom_mask_t = torch.as_tensor(atom_mask_train, dtype=torch.bool)
    if atom_mask_t.shape[0] != bsz:
        raise ValueError(
            f"atom_mask_train shape mismatch: expected first dim {bsz}, got {int(atom_mask_t.shape[0])}"
        )
    valid_mask = _to_numpy_bool(valid_train).reshape(-1)
    if valid_mask.shape[0] != bsz:
        valid_mask = np.ones((bsz,), dtype=bool)
    valid_mask_t = torch.from_numpy(valid_mask).bool().unsqueeze(1)
    fit_mask_t = atom_mask_t & valid_mask_t
    if int(fit_mask_t.sum().item()) <= 0:
        fit_mask_t = atom_mask_t
    if int(fit_mask_t.sum().item()) <= 0:
        return None
    fit_rows = x_train_atoms_t[fit_mask_t]
    fit_np = _sample_fit_rows(fit_rows, max_rows=int(max_fit_rows), seed=int(seed))
    if fit_np.shape[0] <= 0:
        return None
    return EmbeddingTransform.fit(
        fit_np,
        standardize=bool(standardize),
        pca_dim=int(pca_dim),
        eps=float(eps),
    )


def _values_match(saved, current, *, is_bool: bool) -> bool:
    saved_np = _to_numpy_bool(saved) if is_bool else _to_numpy_float32(saved)
    current_np = _to_numpy_bool(current) if is_bool else _to_numpy_float32(current)
    if saved_np.shape != current_np.shape:
        return False
    if is_bool:
        return bool(np.array_equal(saved_np, current_np))
    return bool(np.allclose(saved_np, current_np, equal_nan=True))


def _feature_payload_matches(
    payload: Dict,
    *,
    x_key: str,
    smiles: List[str],
    y: np.ndarray,
    mask: np.ndarray,
    signature: Dict[str, object],
) -> bool:
    if not isinstance(payload, dict) or x_key not in payload or "Y" not in payload or "mask" not in payload:
        return False
    payload_sig = payload.get("feature_signature")
    if payload_sig != signature:
        return False
    payload_smiles = payload.get("smiles")
    if payload_smiles is None or list(payload_smiles) != list(smiles):
        return False
    if not _values_match(payload["Y"], y, is_bool=False):
        return False
    if not _values_match(payload["mask"], mask, is_bool=True):
        return False
    return True


def _try_load_saved_features(
    *,
    output_dir: str,
    fold: int,
    use_late_pooling: bool,
    train_smiles: List[str],
    val_smiles: List[str],
    test_smiles: List[str],
    y_train: np.ndarray,
    y_val: np.ndarray,
    y_test: np.ndarray,
    mask_train: np.ndarray,
    mask_val: np.ndarray,
    mask_test: np.ndarray,
    signature: Dict[str, object],
):
    feature_dir = _feature_dir(output_dir, fold)
    train_path = feature_dir / "train.pt"
    val_path = feature_dir / "val.pt"
    test_path = feature_dir / "test.pt"
    if not train_path.exists() or not val_path.exists() or not test_path.exists():
        return None

    train_payload = torch.load(train_path, map_location="cpu")
    val_payload = torch.load(val_path, map_location="cpu")
    test_payload = torch.load(test_path, map_location="cpu")
    x_key = "X_atoms" if use_late_pooling else "X"
    if not _feature_payload_matches(
        train_payload,
        x_key=x_key,
        smiles=train_smiles,
        y=y_train,
        mask=mask_train,
        signature=signature,
    ):
        return None
    if not _feature_payload_matches(
        val_payload,
        x_key=x_key,
        smiles=val_smiles,
        y=y_val,
        mask=mask_val,
        signature=signature,
    ):
        return None
    if not _feature_payload_matches(
        test_payload,
        x_key=x_key,
        smiles=test_smiles,
        y=y_test,
        mask=mask_test,
        signature=signature,
    ):
        return None

    if use_late_pooling:
        atom_mask_train = _to_numpy_bool(train_payload["atom_mask"])
        atom_mask_val = _to_numpy_bool(val_payload["atom_mask"])
        atom_mask_test = _to_numpy_bool(test_payload["atom_mask"])
        valid_train = _to_numpy_bool(train_payload.get("valid", atom_mask_train.any(axis=1)))
        valid_val = _to_numpy_bool(val_payload.get("valid", atom_mask_val.any(axis=1)))
        valid_test = _to_numpy_bool(test_payload.get("valid", atom_mask_test.any(axis=1)))
        return {
            "x_train_atoms_t": torch.as_tensor(train_payload["X_atoms"]).float(),
            "x_val_atoms_t": torch.as_tensor(val_payload["X_atoms"]).float(),
            "x_test_atoms_t": torch.as_tensor(test_payload["X_atoms"]).float(),
            "atom_mask_train": atom_mask_train,
            "atom_mask_val": atom_mask_val,
            "atom_mask_test": atom_mask_test,
            "valid_train": valid_train,
            "valid_val": valid_val,
            "valid_test": valid_test,
        }

    x_train_t = torch.as_tensor(train_payload["X"]).float()
    x_val_t = torch.as_tensor(val_payload["X"]).float()
    x_test_t = torch.as_tensor(test_payload["X"]).float()
    valid_train = _to_numpy_bool(train_payload.get("valid", np.ones((x_train_t.shape[0],), dtype=bool)))
    valid_val = _to_numpy_bool(val_payload.get("valid", np.ones((x_val_t.shape[0],), dtype=bool)))
    valid_test = _to_numpy_bool(test_payload.get("valid", np.ones((x_test_t.shape[0],), dtype=bool)))
    return {
        "x_train_t": x_train_t,
        "x_val_t": x_val_t,
        "x_test_t": x_test_t,
        "valid_train": valid_train,
        "valid_val": valid_val,
        "valid_test": valid_test,
    }


def _save_conformer_atom_feature_tensor(
    path: Path,
    x_conf_atoms: torch.Tensor,
    atom_mask: np.ndarray,
    conf_mask: np.ndarray,
    y: np.ndarray,
    mask: np.ndarray,
    *,
    smiles: List[str],
    valid: np.ndarray,
    feature_signature: Dict[str, object],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "X_conf_atoms": x_conf_atoms.float().cpu(),
            "atom_mask": torch.from_numpy(atom_mask).bool(),
            "conf_mask": torch.from_numpy(conf_mask).bool(),
            "Y": torch.from_numpy(y).float(),
            "mask": torch.from_numpy(mask).bool(),
            "smiles": list(smiles),
            "valid": torch.from_numpy(valid).bool(),
            "feature_signature": dict(feature_signature),
        },
        path,
    )


def _resolve_embedding_setup(args) -> Tuple[str, str, str]:
    base_mode, pooling_timing = resolve_embedding_and_pooling(args.embedding_mode, args.pooling_timing)
    mode_for_cache = str(args.embedding_mode)
    if pooling_timing == "late" and mode_for_cache in {"backbone", "moe_concat", "moe_fused", "backbone_moe_fused"}:
        mode_for_cache = f"{base_mode}_late"
    return base_mode, pooling_timing, mode_for_cache


def _estimate_nbytes(value) -> int:
    if value is None:
        return 0
    if isinstance(value, np.ndarray):
        return int(value.nbytes)
    if isinstance(value, torch.Tensor):
        return int(value.numel() * value.element_size())
    return 0


def _release_encoder_after_embedding(embedder: Optional[MFMConformerEmbedder], device: torch.device, fold: int) -> None:
    if embedder is None:
        return
    encoder = getattr(embedder, "model", None)
    if encoder is not None:
        try:
            encoder.to("cpu")
        except Exception as exc:
            print(f"[Fold {fold}] Warning: failed to move encoder to CPU before head training: {exc}")
    try:
        embedder.model = None
    except Exception:
        pass
    del encoder
    gc.collect()
    if device.type == "cuda" and torch.cuda.is_available():
        torch.cuda.empty_cache()


def _cuda_memory_info(device: torch.device) -> Tuple[Optional[int], Optional[int]]:
    if device.type != "cuda" or not torch.cuda.is_available():
        return None, None
    try:
        free_bytes, total_bytes = torch.cuda.mem_get_info(device)
        return int(free_bytes), int(total_bytes)
    except TypeError:
        try:
            with torch.cuda.device(device):
                free_bytes, total_bytes = torch.cuda.mem_get_info()
            return int(free_bytes), int(total_bytes)
        except Exception:
            return None, None
    except Exception:
        return None, None


def _resolve_finetune_feature_device(
    args,
    device: torch.device,
    *,
    total_feature_bytes: int,
    free_cuda_bytes: Optional[int] = None,
    total_cuda_bytes: Optional[int] = None,
) -> Tuple[str, str]:
    requested = str(args.finetune_feature_device).lower()
    if device.type != "cuda":
        return "cpu", "model_device_is_cpu"
    if requested == "cpu":
        return "cpu", "requested_cpu"
    if requested == "cuda":
        return "cuda", "requested_cuda"
    limit_bytes = int(float(args.finetune_feature_device_limit_mb) * 1024 * 1024)
    if limit_bytes <= 0:
        return "cpu", "limit_disabled"
    if total_feature_bytes <= limit_bytes:
        return "cuda", f"within_limit_mb={limit_bytes / (1024 * 1024):.0f}"

    # Keep explicit user limits strict. Only the default limit is treated as a
    # conservative baseline that auto mode may relax on roomy GPUs.
    if not math.isclose(
        float(args.finetune_feature_device_limit_mb),
        DEFAULT_FINETUNE_FEATURE_DEVICE_LIMIT_MB,
        rel_tol=0.0,
        abs_tol=1e-6,
    ):
        return "cpu", f"exceeds_limit_mb={limit_bytes / (1024 * 1024):.0f}"

    if free_cuda_bytes is not None and total_cuda_bytes is not None:
        reserve_bytes = int(AUTO_FINETUNE_FEATURE_CUDA_HEADROOM_MB * 1024 * 1024)
        adaptive_budget = min(
            max(0, int(free_cuda_bytes) - reserve_bytes),
            int(float(total_cuda_bytes) * AUTO_FINETUNE_FEATURE_CUDA_MAX_FRACTION),
        )
        if total_feature_bytes <= adaptive_budget:
            return (
                "cuda",
                (
                    f"adaptive_free_mb={int(free_cuda_bytes / (1024 * 1024))}"
                    f"/budget_mb={int(adaptive_budget / (1024 * 1024))}"
                ),
            )
        return "cpu", f"adaptive_budget_mb={int(adaptive_budget / (1024 * 1024))}"

    return "cpu", f"exceeds_default_limit_mb={limit_bytes / (1024 * 1024):.0f}"


def _attach_embedder_cache_metadata(embedder: MFMConformerEmbedder, effective_pretrained_ckpt: str) -> None:
    embedder.checkpoint_fingerprint = _checkpoint_fingerprint(effective_pretrained_ckpt)


def _collect_fold_smiles_for_cache(args, fold: int, targets: List[str]) -> List[str]:
    raw_train = load_fold_split(args.data_dir, fold, "train")
    raw_test = load_fold_split(args.data_dir, fold, "test")
    train_df = prepare_task_df(raw_train, targets)
    test_df = prepare_task_df(raw_test, targets)
    train_df = _sample_df(train_df, args.max_train_rows, args.seed + fold * 11)
    test_df = _sample_df(test_df, args.max_test_rows, args.seed + fold * 13)
    smiles = train_df["smiles"].astype(str).tolist()
    smiles.extend(test_df["smiles"].astype(str).tolist())
    return smiles


def _collect_global_cache_smiles(args, folds: List[int], targets: List[str]) -> List[str]:
    unique_smiles: List[str] = []
    seen = set()
    for fold in folds:
        for smi in _collect_fold_smiles_for_cache(args, int(fold), targets):
            smi = str(smi)
            if smi in seen:
                continue
            seen.add(smi)
            unique_smiles.append(smi)
    return unique_smiles


def _warmup_shared_global_cache(
    *,
    args,
    folds: List[int],
    targets: List[str],
    effective_pretrained_ckpt: str,
    mode_for_cache: str,
) -> None:
    if str(args.cache_mode).lower() != "global":
        return
    if str(args.global_cache_scope).lower() != "shared":
        return

    _, pooling_timing, _ = _resolve_embedding_setup(args)
    use_late_pooling = pooling_timing == "late"
    cache_dir = _effective_cache_dir(args)
    global_cache = _shared_global_cache_path(cache_dir, use_late_pooling=use_late_pooling)
    all_smiles = _collect_global_cache_smiles(args, folds, targets)
    if not all_smiles:
        print("[cache-prewarm] No smiles found in selected folds; skipping warmup.")
        return

    chunk_size = max(128, int(args.embed_batch_size) * 8)
    n_chunks = int(math.ceil(len(all_smiles) / float(chunk_size)))
    print(
        f"[cache-prewarm] Start: unique_smiles={len(all_smiles)} folds={len(folds)} "
        f"cache_path={global_cache} chunk_size={chunk_size} chunks={n_chunks}"
    )

    device = resolve_device(args.device)
    pretrained_model, _, encoder_load_info = load_pretrained_mfm(
        effective_pretrained_ckpt,
        device,
        return_load_info=True,
    )
    embedder_cfg = EmbedderConfig(
        num_conformers=args.num_conformers,
        optimize_conformers=bool(args.optimize_conformers),
        max_opt_iters=args.max_opt_iters,
        add_hs=bool(args.add_hs),
        embedding_mode=str(mode_for_cache),
        xyz_pool_root=(None if args.xyz_pool_root is None else str(args.xyz_pool_root)),
        atom_index_offset=args.atom_index_offset,
    )
    embedder = MFMConformerEmbedder(pretrained_model, device, embedder_cfg)
    _attach_embedder_cache_metadata(embedder, effective_pretrained_ckpt)
    print("[cache-prewarm] Encoder load info:", encoder_load_info)

    valid_total = 0
    try:
        for idx, start in enumerate(range(0, len(all_smiles), chunk_size), start=1):
            end = min(len(all_smiles), start + chunk_size)
            batch_smiles = all_smiles[start:end]
            seed = int(args.seed) + int(start)
            if use_late_pooling:
                _, _, valid = get_atom_embeddings_with_global_cache(
                    embedder,
                    batch_smiles,
                    cache_path=global_cache,
                    seed=seed,
                    desc=f"global-warmup-{idx:03d}/{n_chunks:03d}",
                )
            else:
                _, valid = get_embeddings_with_global_cache(
                    embedder,
                    batch_smiles,
                    cache_path=global_cache,
                    seed=seed,
                    desc=f"global-warmup-{idx:03d}/{n_chunks:03d}",
                )
            valid_total += int(np.asarray(valid).astype(bool).sum())
            print(f"[cache-prewarm] chunk {idx}/{n_chunks}: cached_rows={end}/{len(all_smiles)}")
    finally:
        _release_encoder_after_embedding(embedder, device, fold=0)

    print(
        f"[cache-prewarm] Done: valid={valid_total}/{len(all_smiles)} "
        f"cache_path={global_cache}"
    )


@torch.no_grad()
def _predict_scaled(
    model: torch.nn.Module,
    x: torch.Tensor,
    *,
    device: torch.device,
    batch_size: int,
    atom_mask: Optional[np.ndarray] = None,
    conf_mask: Optional[np.ndarray] = None,
) -> np.ndarray:
    model.eval()
    preds: List[torch.Tensor] = []
    n_rows = int(x.shape[0])
    for start in range(0, n_rows, int(batch_size)):
        end = min(n_rows, start + int(batch_size))
        xb = x[start:end].to(device)
        if atom_mask is None and conf_mask is None:
            yb = model(xb)
        elif conf_mask is None:
            ab = torch.from_numpy(atom_mask[start:end]).bool().to(device)
            yb = model(xb, ab)
        else:
            ab = torch.from_numpy(atom_mask[start:end]).bool().to(device)
            cb = torch.from_numpy(conf_mask[start:end]).bool().to(device)
            yb = model(xb, ab, cb)
        preds.append(yb.detach().cpu())
    return torch.cat(preds, dim=0).numpy()


class WarmupCosineLRScheduler:
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        *,
        total_steps: int,
        warmup_steps: int,
        init_lr: float,
        max_lr: float,
        final_lr: float,
    ) -> None:
        self.optimizer = optimizer
        self.total_steps = max(1, int(total_steps))
        self.warmup_steps = max(0, min(int(warmup_steps), self.total_steps - 1))
        self.init_lr = float(init_lr)
        self.max_lr = float(max_lr)
        self.final_lr = float(final_lr)
        self.step_idx = 0
        self._last_lr = self.init_lr
        self._set_lr(self.init_lr)

    def _set_lr(self, lr: float) -> None:
        self._last_lr = float(lr)
        for group in self.optimizer.param_groups:
            group["lr"] = self._last_lr

    def step(self) -> None:
        self.step_idx += 1
        if self.warmup_steps > 0 and self.step_idx <= self.warmup_steps:
            alpha = float(self.step_idx) / float(self.warmup_steps)
            lr = self.init_lr + alpha * (self.max_lr - self.init_lr)
            self._set_lr(lr)
            return

        decay_steps = max(1, self.total_steps - self.warmup_steps)
        t = min(1.0, float(self.step_idx - self.warmup_steps) / float(decay_steps))
        cosine = 0.5 * (1.0 + math.cos(math.pi * t))
        lr = self.final_lr + (self.max_lr - self.final_lr) * cosine
        self._set_lr(lr)

    def get_last_lr(self) -> float:
        return float(self._last_lr)


def train_single_fold(
    args,
    fold: int,
    targets: List[str],
    embedder: MFMConformerEmbedder,
    encoder_load_info: Dict,
    effective_pretrained_ckpt: str,
    device: torch.device,
) -> Dict:
    base_embedding_mode, pooling_timing, _ = _resolve_embedding_setup(args)
    use_late_pooling = pooling_timing == "late"

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

    train_smiles = train_sub["smiles"].astype(str).tolist()
    val_smiles = val_sub["smiles"].astype(str).tolist()
    test_smiles = test_df["smiles"].astype(str).tolist()
    y_train = _np_targets(train_sub, targets)
    y_val = _np_targets(val_sub, targets)
    y_test = _np_targets(test_df, targets)
    mask_train = np.isfinite(y_train)
    mask_val = np.isfinite(y_val)
    mask_test = np.isfinite(y_test)
    feature_signature = _feature_signature(
        args=args,
        targets=targets,
        base_embedding_mode=base_embedding_mode,
        pooling_timing=pooling_timing,
        effective_pretrained_ckpt=effective_pretrained_ckpt,
    )

    train_cache = None
    val_cache = None
    test_cache = None
    global_cache = None
    effective_cache_dir = _effective_cache_dir(args)
    if effective_cache_dir:
        global_cache = _resolve_global_cache_path(
            effective_cache_dir,
            fold=fold,
            use_late_pooling=use_late_pooling,
            scope=args.global_cache_scope,
        )
        if args.cache_mode == "split":
            if use_late_pooling:
                train_cache = _fold_conf_atom_cache_path(effective_cache_dir, fold, "train")
                val_cache = _fold_conf_atom_cache_path(effective_cache_dir, fold, "val")
                test_cache = _fold_conf_atom_cache_path(effective_cache_dir, fold, "test")
            else:
                train_cache = _fold_cache_path(effective_cache_dir, fold, "train")
                val_cache = _fold_cache_path(effective_cache_dir, fold, "val")
                test_cache = _fold_cache_path(effective_cache_dir, fold, "test")
        if args.cache_mode == "global":
            print(
                f"[Fold {fold}] Embedding cache: mode=global scope={str(args.global_cache_scope).lower()} "
                f"path={global_cache}"
            )
        else:
            print(
                f"[Fold {fold}] Embedding cache: mode=split train={train_cache} val={val_cache} test={test_cache}"
            )

    loaded_features = None
    if args.reuse_saved_features:
        loaded_features = _try_load_saved_features(
            output_dir=args.output_dir,
            fold=fold,
            use_late_pooling=use_late_pooling,
            train_smiles=train_smiles,
            val_smiles=val_smiles,
            test_smiles=test_smiles,
            y_train=y_train,
            y_val=y_val,
            y_test=y_test,
            mask_train=mask_train,
            mask_val=mask_val,
            mask_test=mask_test,
            signature=feature_signature,
        )
        if loaded_features is not None:
            print(f"[Fold {fold}] Reusing saved feature tensors from {_feature_dir(args.output_dir, fold)}")

    if use_late_pooling:
        if loaded_features is not None:
            x_train_atoms_t = loaded_features["x_train_atoms_t"]
            x_val_atoms_t = loaded_features["x_val_atoms_t"]
            x_test_atoms_t = loaded_features["x_test_atoms_t"]
            atom_mask_train = loaded_features["atom_mask_train"]
            atom_mask_val = loaded_features["atom_mask_val"]
            atom_mask_test = loaded_features["atom_mask_test"]
            valid_train = loaded_features["valid_train"]
            valid_val = loaded_features["valid_val"]
            valid_test = loaded_features["valid_test"]
        elif args.cache_mode == "global":
            x_train_atoms_t, atom_mask_train, valid_train = get_atom_embeddings_with_global_cache(
                embedder,
                train_smiles,
                cache_path=global_cache,
                seed=args.seed + fold * 1000,
                desc=f"Fold{fold}-train-atom-embed",
            )
            x_val_atoms_t, atom_mask_val, valid_val = get_atom_embeddings_with_global_cache(
                embedder,
                val_smiles,
                cache_path=global_cache,
                seed=args.seed + fold * 1000 + 200_000,
                desc=f"Fold{fold}-val-atom-embed",
            )
            x_test_atoms_t, atom_mask_test, valid_test = get_atom_embeddings_with_global_cache(
                embedder,
                test_smiles,
                cache_path=global_cache,
                seed=args.seed + fold * 1000 + 400_000,
                desc=f"Fold{fold}-test-atom-embed",
            )
        else:
            x_train_atoms_t, atom_mask_train, valid_train = get_atom_embeddings_with_global_cache(
                embedder,
                train_smiles,
                cache_path=train_cache,
                seed=args.seed + fold * 1000,
                desc=f"Fold{fold}-train-atom-embed",
            )
            x_val_atoms_t, atom_mask_val, valid_val = get_atom_embeddings_with_global_cache(
                embedder,
                val_smiles,
                cache_path=val_cache,
                seed=args.seed + fold * 1000 + 200_000,
                desc=f"Fold{fold}-val-atom-embed",
            )
            x_test_atoms_t, atom_mask_test, valid_test = get_atom_embeddings_with_global_cache(
                embedder,
                test_smiles,
                cache_path=test_cache,
                seed=args.seed + fold * 1000 + 400_000,
                desc=f"Fold{fold}-test-atom-embed",
            )
    else:
        if loaded_features is not None:
            x_train_t = loaded_features["x_train_t"]
            x_val_t = loaded_features["x_val_t"]
            x_test_t = loaded_features["x_test_t"]
            valid_train = loaded_features["valid_train"]
            valid_val = loaded_features["valid_val"]
            valid_test = loaded_features["valid_test"]
        elif args.cache_mode == "global":
            x_train_t, valid_train = get_embeddings_with_global_cache(
                embedder,
                train_smiles,
                cache_path=global_cache,
                seed=args.seed + fold * 1000,
                desc=f"Fold{fold}-train-embed",
            )
            x_val_t, valid_val = get_embeddings_with_global_cache(
                embedder,
                val_smiles,
                cache_path=global_cache,
                seed=args.seed + fold * 1000 + 200_000,
                desc=f"Fold{fold}-val-embed",
            )
            x_test_t, valid_test = get_embeddings_with_global_cache(
                embedder,
                test_smiles,
                cache_path=global_cache,
                seed=args.seed + fold * 1000 + 400_000,
                desc=f"Fold{fold}-test-embed",
            )
        else:
            x_train_t, valid_train = get_embeddings_with_global_cache(
                embedder,
                train_smiles,
                cache_path=train_cache,
                seed=args.seed + fold * 1000,
                desc=f"Fold{fold}-train-embed",
            )
            x_val_t, valid_val = get_embeddings_with_global_cache(
                embedder,
                val_smiles,
                cache_path=val_cache,
                seed=args.seed + fold * 1000 + 200_000,
                desc=f"Fold{fold}-val-embed",
            )
            x_test_t, valid_test = get_embeddings_with_global_cache(
                embedder,
                test_smiles,
                cache_path=test_cache,
                seed=args.seed + fold * 1000 + 400_000,
                desc=f"Fold{fold}-test-embed",
            )
    embedding_transform: Optional[EmbeddingTransform] = None
    if use_late_pooling:
        x_train_atoms_save_t = x_train_atoms_t
        x_val_atoms_save_t = x_val_atoms_t
        x_test_atoms_save_t = x_test_atoms_t
        need_transform = bool(args.embedding_standardize) or int(args.embedding_pca_dim) > 0
        if need_transform:
            embedding_transform = _fit_embedding_transform_late_atomwise(
                x_train_atoms_t=x_train_atoms_t,
                atom_mask_train=atom_mask_train,
                valid_train=valid_train,
                pca_dim=int(args.embedding_pca_dim),
                max_fit_rows=int(args.embedding_pca_max_fit_rows),
                standardize=bool(args.embedding_standardize),
                eps=float(args.embedding_standardize_eps),
                seed=int(args.seed + fold * 101 + 17),
            )
            if embedding_transform is not None:
                x_train_atoms_t = embedding_transform.transform_torch(x_train_atoms_t).float()
                x_val_atoms_t = embedding_transform.transform_torch(x_val_atoms_t).float()
                x_test_atoms_t = embedding_transform.transform_torch(x_test_atoms_t).float()
        if embedding_transform is None:
            print(
                f"[Fold {fold}] Embedding transform: disabled "
                f"(standardize={bool(args.embedding_standardize)} pca_dim={int(args.embedding_pca_dim)})."
            )
        else:
            print(
                f"[Fold {fold}] Embedding transform: standardize={embedding_transform.standardize} "
                f"pca_applied={embedding_transform.pca_applied} "
                f"input_dim={embedding_transform.input_dim} output_dim={embedding_transform.output_dim} "
                f"fit_count={embedding_transform.fit_count}"
            )
    else:
        x_train_save = x_train_t.detach().cpu().numpy().astype(np.float32, copy=False)
        x_val_save = x_val_t.detach().cpu().numpy().astype(np.float32, copy=False)
        x_test_save = x_test_t.detach().cpu().numpy().astype(np.float32, copy=False)
        need_transform = bool(args.embedding_standardize) or int(args.embedding_pca_dim) > 0
        if need_transform:
            embedding_transform = _fit_embedding_transform_early(
                x_train_t=x_train_t,
                valid_train=valid_train,
                pca_dim=int(args.embedding_pca_dim),
                max_fit_rows=int(args.embedding_pca_max_fit_rows),
                standardize=bool(args.embedding_standardize),
                eps=float(args.embedding_standardize_eps),
                seed=int(args.seed + fold * 101 + 17),
            )
            if embedding_transform is not None:
                x_train_t = embedding_transform.transform_torch(x_train_t).float()
                x_val_t = embedding_transform.transform_torch(x_val_t).float()
                x_test_t = embedding_transform.transform_torch(x_test_t).float()
        if embedding_transform is None:
            print(
                f"[Fold {fold}] Embedding transform: disabled "
                f"(standardize={bool(args.embedding_standardize)} pca_dim={int(args.embedding_pca_dim)})."
            )
        else:
            print(
                f"[Fold {fold}] Embedding transform: standardize={embedding_transform.standardize} "
                f"pca_applied={embedding_transform.pca_applied} "
                f"input_dim={embedding_transform.input_dim} output_dim={embedding_transform.output_dim} "
                f"fit_count={embedding_transform.fit_count}"
            )
        x_train = x_train_t.detach().cpu().numpy().astype(np.float32, copy=False)
        x_val = x_val_t.detach().cpu().numpy().astype(np.float32, copy=False)
        x_test = x_test_t.detach().cpu().numpy().astype(np.float32, copy=False)

    scaler = LabelScaler.fit(y_train)
    y_train_scaled = scaler.transform(y_train)
    y_val_scaled = scaler.transform(y_val)

    total_feature_bytes = _estimate_nbytes(y_train_scaled) + _estimate_nbytes(y_val_scaled)
    total_feature_bytes += _estimate_nbytes(mask_train) + _estimate_nbytes(mask_val)
    if use_late_pooling:
        total_feature_bytes += _estimate_nbytes(x_train_atoms_t) + _estimate_nbytes(x_val_atoms_t)
        total_feature_bytes += _estimate_nbytes(atom_mask_train) + _estimate_nbytes(atom_mask_val)
    else:
        total_feature_bytes += _estimate_nbytes(x_train_t) + _estimate_nbytes(x_val_t)
    _release_encoder_after_embedding(embedder, device, fold)
    free_cuda_bytes, total_cuda_bytes = _cuda_memory_info(device)
    finetune_feature_device, finetune_feature_reason = _resolve_finetune_feature_device(
        args,
        device,
        total_feature_bytes=total_feature_bytes,
        free_cuda_bytes=free_cuda_bytes,
        total_cuda_bytes=total_cuda_bytes,
    )
    pin_memory = device.type == "cuda" and finetune_feature_device == "cpu"
    non_blocking = pin_memory

    cuda_mem_msg = ""
    if free_cuda_bytes is not None and total_cuda_bytes is not None:
        cuda_mem_msg = (
            f" free_cuda_mb={int(free_cuda_bytes / (1024 * 1024))}"
            f" total_cuda_mb={int(total_cuda_bytes / (1024 * 1024))}"
        )
    print(
        f"[Fold {fold}] Head training device pipeline: model_device={device} feature_device={finetune_feature_device} "
        f"pin_memory={pin_memory} approx_train_val_mb={total_feature_bytes / (1024 * 1024):.1f} "
        f"decision={finetune_feature_reason}{cuda_mem_msg}"
    )
    if device.type == "cuda" and finetune_feature_device == "cpu":
        print(
            f"[Fold {fold}] Warning: fine-tune features remain on CPU, so every batch will copy host tensors to {device}. "
            f"For large late-pooling runs, try --finetune_feature_device cuda or raise "
            f"--finetune_feature_device_limit_mb."
        )

    if use_late_pooling:
        train_x = x_train_atoms_t
        val_x = x_val_atoms_t
        train_atom_mask = atom_mask_train
        val_atom_mask = atom_mask_val
        train_y = y_train_scaled
        val_y = y_val_scaled
        train_mask = mask_train
        val_mask = mask_val
        if finetune_feature_device == "cuda":
            train_x = x_train_atoms_t.to(device)
            val_x = x_val_atoms_t.to(device)
            train_atom_mask = torch.as_tensor(atom_mask_train, dtype=torch.bool, device=device)
            val_atom_mask = torch.as_tensor(atom_mask_val, dtype=torch.bool, device=device)
            train_y = torch.as_tensor(y_train_scaled, dtype=torch.float32, device=device)
            val_y = torch.as_tensor(y_val_scaled, dtype=torch.float32, device=device)
            train_mask = torch.as_tensor(mask_train, dtype=torch.bool, device=device)
            val_mask = torch.as_tensor(mask_val, dtype=torch.bool, device=device)
        train_loader = build_atom_feature_loader(
            train_x,
            train_atom_mask,
            train_y,
            train_mask,
            batch_size=args.batch_size,
            shuffle=True,
            pin_memory=pin_memory,
        )
        val_loader = build_atom_feature_loader(
            val_x,
            val_atom_mask,
            val_y,
            val_mask,
            batch_size=args.batch_size,
            shuffle=False,
            pin_memory=pin_memory,
        )
        model = AtomwiseLatePoolRegressionHead(
            in_dim=int(x_train_atoms_t.shape[2]),
            out_dim=len(targets),
            hidden_dim=args.hidden_dim,
            atom_layers=args.atom_head_layers,
            readout_layers=args.head_layers,
            dropout=args.dropout,
        ).to(device)
        embedding_dim = int(x_train_atoms_t.shape[2])
    else:
        train_x = x_train
        val_x = x_val
        train_y = y_train_scaled
        val_y = y_val_scaled
        train_mask = mask_train
        val_mask = mask_val
        if finetune_feature_device == "cuda":
            train_x = x_train_t.to(device)
            val_x = x_val_t.to(device)
            train_y = torch.as_tensor(y_train_scaled, dtype=torch.float32, device=device)
            val_y = torch.as_tensor(y_val_scaled, dtype=torch.float32, device=device)
            train_mask = torch.as_tensor(mask_train, dtype=torch.bool, device=device)
            val_mask = torch.as_tensor(mask_val, dtype=torch.bool, device=device)
        train_loader = build_feature_loader(
            train_x,
            train_y,
            train_mask,
            batch_size=args.batch_size,
            shuffle=True,
            pin_memory=pin_memory,
        )
        val_loader = build_feature_loader(
            val_x,
            val_y,
            val_mask,
            batch_size=args.batch_size,
            shuffle=False,
            pin_memory=pin_memory,
        )
        model = RegressionHead(
            in_dim=x_train.shape[1],
            out_dim=len(targets),
            hidden_dim=args.hidden_dim,
            n_layers=args.head_layers,
            dropout=args.dropout,
        ).to(device)
        embedding_dim = int(x_train.shape[1])
    schedule_enabled = args.max_lr is not None
    if schedule_enabled:
        max_lr = float(args.max_lr)
        init_lr = float(args.init_lr if args.init_lr is not None else max_lr)
        final_lr = float(args.final_lr if args.final_lr is not None else max_lr)
        optimizer = torch.optim.AdamW(model.parameters(), lr=max_lr, weight_decay=args.weight_decay)
        lr_scheduler = WarmupCosineLRScheduler(
            optimizer,
            total_steps=max(1, args.epochs * len(train_loader)),
            warmup_steps=max(0, args.warmup_epochs * len(train_loader)),
            init_lr=init_lr,
            max_lr=max_lr,
            final_lr=final_lr,
        )
    else:
        optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
        lr_scheduler = None

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

    out_fold = Path(args.output_dir) / f"fold_{fold}" / "model_files"
    out_fold.mkdir(parents=True, exist_ok=True)

    best_val = float("inf")
    bad_epochs = 0
    best_payload = None
    for epoch in range(1, args.epochs + 1):
        tr_loss = run_epoch(
            model,
            train_loader,
            device=device,
            optimizer=optimizer,
            task_weights=task_weights_t,
            lr_scheduler=lr_scheduler,
            non_blocking=non_blocking,
        )
        va_loss = run_epoch(
            model,
            val_loader,
            device=device,
            optimizer=None,
            task_weights=task_weights_t,
            non_blocking=non_blocking,
        )
        curr_lr = float(optimizer.param_groups[0]["lr"])
        print(f"[Fold {fold}] Epoch {epoch:03d} train_loss={tr_loss:.6f} val_loss={va_loss:.6f} lr={curr_lr:.6g}")

        payload = {
            "head_state": model.state_dict(),
            "targets": targets,
            "mode": args.mode,
            "target_scaler": scaler.to_dict(),
            "embedding_dim": embedding_dim,
            "arch": str(args.arch),
            "head_cfg": {
                "hidden_dim": int(args.hidden_dim),
                "head_layers": int(args.head_layers),
                "dropout": float(args.dropout),
                "pooling_timing": str(pooling_timing),
                "atom_head_layers": int(args.atom_head_layers),
                "pooling_arch": "atomwise_v1" if use_late_pooling else "early_attn_v1",
            },
            "feature_cfg": {
                "num_conformers": args.num_conformers,
                "optimize_conformers": bool(args.optimize_conformers),
                "max_opt_iters": int(args.max_opt_iters),
                "add_hs": bool(args.add_hs),
                "embedding_mode": str(base_embedding_mode),
                "embedding_mode_arg": str(args.embedding_mode),
                "pooling_timing": str(pooling_timing),
                "atom_index_offset": int(args.atom_index_offset),
                "xyz_pool_root": None if args.xyz_pool_root is None else str(args.xyz_pool_root),
                "mp_hidden_size": int(args.mp_hidden_size),
                "mp_depth": int(args.mp_depth),
                "mp_dropout": float(args.mp_dropout),
                "embed_batch_size": int(args.embed_batch_size),
                "embed_num_workers": int(args.embed_num_workers),
                "finetune_feature_device": str(finetune_feature_device),
                "finetune_feature_device_limit_mb": float(args.finetune_feature_device_limit_mb),
                "mp_batch_norm": not bool(args.no_mp_batch_norm),
                "mp_warmup_epochs": int(args.mp_warmup_epochs),
                "mp_init_lr": float(args.mp_init_lr),
                "mp_max_lr": float(args.mp_max_lr),
                "mp_final_lr": float(args.mp_final_lr),
                "embedding_standardize": bool(args.embedding_standardize),
                "embedding_standardize_eps": float(args.embedding_standardize_eps),
                "embedding_pca_dim": int(args.embedding_pca_dim),
                "embedding_pca_max_fit_rows": int(args.embedding_pca_max_fit_rows),
            },
            "embedding_transform": None if embedding_transform is None else embedding_transform.to_dict(),
            "optim_cfg": {
                "lr": float(args.lr),
                "weight_decay": float(args.weight_decay),
                "warmup_epochs": int(args.warmup_epochs),
                "init_lr": None if args.init_lr is None else float(args.init_lr),
                "max_lr": None if args.max_lr is None else float(args.max_lr),
                "final_lr": None if args.final_lr is None else float(args.final_lr),
            },
            "pretrained_ckpt": effective_pretrained_ckpt,
            "encoder_load_info": dict(encoder_load_info),
            "epoch": int(epoch),
            "train_loss": float(tr_loss),
            "val_loss": float(va_loss),
            "lr": curr_lr,
        }
        torch.save(payload, out_fold / f"last.pt")

        if va_loss < best_val:
            best_val = va_loss
            bad_epochs = 0
            best_payload = payload
            torch.save(payload, out_fold / "best.pt")
            torch.save(payload, out_fold / f"best-epoch{epoch:03d}-val{va_loss:.5f}.pt")
        else:
            bad_epochs += 1
            if bad_epochs >= args.patience:
                print(f"[Fold {fold}] Early stopping at epoch {epoch}.")
                break

    if best_payload is None:
        best_ckpt = select_best_checkpoint(out_fold)
        best_payload = torch.load(best_ckpt, map_location="cpu")
    model.load_state_dict(best_payload["head_state"])
    model.eval()

    if use_late_pooling:
        y_train_pred_scaled = _predict_scaled(
            model,
            x_train_atoms_t,
            device=device,
            batch_size=args.batch_size,
            atom_mask=atom_mask_train,
        )
        y_val_pred_scaled = _predict_scaled(
            model,
            x_val_atoms_t,
            device=device,
            batch_size=args.batch_size,
            atom_mask=atom_mask_val,
        )
        y_pred_scaled = _predict_scaled(
            model,
            x_test_atoms_t,
            device=device,
            batch_size=args.batch_size,
            atom_mask=atom_mask_test,
        )
    else:
        with torch.no_grad():
            x_train_torch = torch.from_numpy(x_train).float().to(device)
            y_train_pred_scaled = model(x_train_torch).cpu().numpy()
            x_val_torch = torch.from_numpy(x_val).float().to(device)
            y_val_pred_scaled = model(x_val_torch).cpu().numpy()
            x_test_torch = torch.from_numpy(x_test).float().to(device)
            y_pred_scaled = model(x_test_torch).cpu().numpy()
    y_train_pred = scaler.inverse(y_train_pred_scaled)
    y_val_pred = scaler.inverse(y_val_pred_scaled)
    y_test_pred = scaler.inverse(y_pred_scaled)
    train_metrics = compute_metrics_table(y_train, y_train_pred, targets)
    val_metrics = compute_metrics_table(y_val, y_val_pred, targets)
    test_metrics = compute_metrics_table(y_test, y_test_pred, targets)
    print(f"[Fold {fold}] Train metrics")
    print_metrics(train_metrics)
    print(f"[Fold {fold}] Val metrics")
    print_metrics(val_metrics)
    print(f"[Fold {fold}] Test metrics")
    print_metrics(test_metrics)

    if args.save_feature_tensors or args.reuse_saved_features:
        feat_dir = Path(args.output_dir) / f"fold_{fold}" / "features"
        if use_late_pooling:
            _save_atom_feature_tensor(
                feat_dir / "train.pt",
                x_train_atoms_save_t,
                atom_mask_train,
                y_train,
                mask_train,
                smiles=train_smiles,
                valid=valid_train,
                feature_signature=feature_signature,
            )
            _save_atom_feature_tensor(
                feat_dir / "val.pt",
                x_val_atoms_save_t,
                atom_mask_val,
                y_val,
                mask_val,
                smiles=val_smiles,
                valid=valid_val,
                feature_signature=feature_signature,
            )
            _save_atom_feature_tensor(
                feat_dir / "test.pt",
                x_test_atoms_save_t,
                atom_mask_test,
                y_test,
                mask_test,
                smiles=test_smiles,
                valid=valid_test,
                feature_signature=feature_signature,
            )
        else:
            _save_feature_tensor(
                feat_dir / "train.pt",
                x_train_save,
                y_train,
                mask_train,
                smiles=train_smiles,
                valid=valid_train,
                feature_signature=feature_signature,
            )
            _save_feature_tensor(
                feat_dir / "val.pt",
                x_val_save,
                y_val,
                mask_val,
                smiles=val_smiles,
                valid=valid_val,
                feature_signature=feature_signature,
            )
            _save_feature_tensor(
                feat_dir / "test.pt",
                x_test_save,
                y_test,
                mask_test,
                smiles=test_smiles,
                valid=valid_test,
                feature_signature=feature_signature,
            )

    summary = {
        "fold": fold,
        "targets": targets,
        "arch": str(args.arch),
        "best_val_loss": float(best_val),
        "n_train": int(len(train_sub)),
        "n_val": int(len(val_sub)),
        "n_test": int(len(test_df)),
        "embed_valid_train": int(valid_train.sum()),
        "embed_valid_val": int(valid_val.sum()),
        "embed_valid_test": int(valid_test.sum()),
        "embedding_transform": {
            "enabled": embedding_transform is not None,
            "standardize": False if embedding_transform is None else bool(embedding_transform.standardize),
            "pca_applied": False if embedding_transform is None else bool(embedding_transform.pca_applied),
            "input_dim": None if embedding_transform is None else int(embedding_transform.input_dim),
            "output_dim": None if embedding_transform is None else int(embedding_transform.output_dim),
            "fit_count": None if embedding_transform is None else int(embedding_transform.fit_count),
            "pca_dim_arg": int(args.embedding_pca_dim),
        },
        "metrics_train": train_metrics,
        "metrics_val": val_metrics,
        "metrics_test": test_metrics,
        "metrics": test_metrics,
    }
    save_json(Path(args.output_dir) / f"fold_{fold}" / "summary.json", summary)
    return summary


def _train_fold_worker(args_dict: Dict, fold: int, targets: List[str]) -> Dict:
    args = argparse.Namespace(**args_dict)
    set_seed(args.seed + int(fold))
    device = resolve_device(args.device)
    effective_pretrained_ckpt = args.pretrained_ckpt or args.encoder_ckpt
    pretrained_model, _, encoder_load_info = load_pretrained_mfm(
        effective_pretrained_ckpt,
        device,
        return_load_info=True,
    )
    _, _, mode_for_cache = _resolve_embedding_setup(args)
    embedder_cfg = EmbedderConfig(
        num_conformers=args.num_conformers,
        optimize_conformers=bool(args.optimize_conformers),
        max_opt_iters=args.max_opt_iters,
        add_hs=bool(args.add_hs),
        embedding_mode=str(mode_for_cache),
        xyz_pool_root=(None if args.xyz_pool_root is None else str(args.xyz_pool_root)),
        atom_index_offset=args.atom_index_offset,
    )
    embedder = MFMConformerEmbedder(pretrained_model, device, embedder_cfg)
    _attach_embedder_cache_metadata(embedder, effective_pretrained_ckpt)
    print(f"[Fold {fold}] Encoder load info:", encoder_load_info)
    return train_single_fold(
        args=args,
        fold=fold,
        targets=targets,
        embedder=embedder,
        encoder_load_info=encoder_load_info,
        effective_pretrained_ckpt=effective_pretrained_ckpt,
        device=device,
    )


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("Train MFM ADMET head (single-task or multi-task)")
    add_shared_parser_args(p)
    p.add_argument("--arch", type=str, default="mfm")
    p.add_argument("--encoder_ckpt", type=str, default=None)
    p.add_argument("--strict_encoder_load", action="store_true")
    p.add_argument("--mp_hidden_size", type=int, default=300)
    p.add_argument("--mp_depth", type=int, default=3)
    p.add_argument("--mp_dropout", type=float, default=0.1)
    p.add_argument("--embed_batch_size", type=int, default=256)
    p.add_argument("--embed_num_workers", type=int, default=0)
    p.add_argument(
        "--fold_workers",
        type=int,
        default=0,
        help="How many folds to train concurrently. 0 means auto: at most one worker per visible GPU.",
    )
    p.add_argument(
        "--finetune_feature_device",
        type=str,
        choices=["auto", "cpu", "cuda"],
        default="auto",
        help="Where cached fine-tuning features live during head training. auto prefers the configured limit and, with the default limit, can still use free GPU memory after encoder release when the features fit comfortably.",
    )
    p.add_argument(
        "--finetune_feature_device_limit_mb",
        type=float,
        default=DEFAULT_FINETUNE_FEATURE_DEVICE_LIMIT_MB,
        help="Conservative auto-placement threshold in MB for train/val features. Custom values are treated as strict limits.",
    )
    p.add_argument("--no_mp_batch_norm", action="store_true")
    p.add_argument("--mp_warmup_epochs", type=int, default=5)
    p.add_argument("--mp_init_lr", type=float, default=1e-4)
    p.add_argument("--mp_max_lr", type=float, default=1e-3)
    p.add_argument("--mp_final_lr", type=float, default=1e-4)
    p.add_argument("--output_dir", type=str, required=True)
    p.add_argument("--val_frac", type=float, default=0.1)
    p.add_argument("--epochs", type=int, default=400)
    p.add_argument("--patience", type=int, default=40)
    p.add_argument("--batch_size", type=int, default=16)
    p.add_argument("--lr", type=float, default=5e-4)
    p.add_argument("--weight_decay", type=float, default=1e-4)
    p.add_argument("--hidden_dim", type=int, default=1024)
    p.add_argument("--head_layers", type=int, default=2)
    p.add_argument("--atom_head_layers", type=int, default=2)
    p.add_argument("--dropout", type=float, default=0.1)
    p.add_argument("--embedding_standardize", dest="embedding_standardize", action="store_true")
    p.add_argument("--no_embedding_standardize", dest="embedding_standardize", action="store_false")
    p.add_argument(
        "--embedding_standardize_eps",
        type=float,
        default=1e-6,
        help="Minimum std clamp when standardizing embeddings.",
    )
    p.add_argument(
        "--embedding_pca_dim",
        type=int,
        default=0,
        help="If >0, reduce embedding last-dimension to this PCA dimension (fit on train split only).",
    )
    p.add_argument(
        "--embedding_pca_max_fit_rows",
        type=int,
        default=200000,
        help="Max sampled training rows used to fit PCA/statistics for embedding transform.",
    )
    p.add_argument("--warmup_epochs", type=int, default=0)
    p.add_argument("--init_lr", type=float, default=None)
    p.add_argument("--max_lr", type=float, default=None)
    p.add_argument("--final_lr", type=float, default=None)
    p.add_argument(
        "--task_weights",
        type=str,
        default=None,
        help="Comma separated task weights for MT mode. Example: 1.0,1.0,2.0,...",
    )
    p.add_argument("--reuse_saved_features", dest="reuse_saved_features", action="store_true")
    p.add_argument("--no_reuse_saved_features", dest="reuse_saved_features", action="store_false")
    p.add_argument("--save_feature_tensors", action="store_true")
    p.add_argument(
        "--cache_mode",
        type=str,
        choices=["global", "split"],
        default="global",
        help="global: cache by smiles dictionary (scope controlled by --global_cache_scope); split: separate train/val/test cache files inside each fold directory.",
    )
    p.add_argument(
        "--global_cache_scope",
        type=str,
        choices=["shared", "fold"],
        default="shared",
        help="Only used when --cache_mode global. shared: one cache file reused by all folds; fold: keep per-fold global cache (legacy behavior).",
    )
    p.add_argument("--max_train_rows", type=int, default=0)
    p.add_argument("--max_val_rows", type=int, default=0)
    p.add_argument("--max_test_rows", type=int, default=0)
    p.set_defaults(reuse_saved_features=True, embedding_standardize=True)
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    set_seed(args.seed)
    if args.encoder_ckpt and args.pretrained_ckpt and args.encoder_ckpt != args.pretrained_ckpt:
        raise ValueError("--encoder_ckpt and --pretrained_ckpt are both set but not equal.")
    effective_pretrained_ckpt = args.pretrained_ckpt or args.encoder_ckpt
    if not effective_pretrained_ckpt:
        raise ValueError("train.py requires --pretrained_ckpt (or --encoder_ckpt).")
    print("Train args:", vars(args))

    targets = parse_targets_from_args(args.mode, args.target, args.targets)
    folds = parse_fold_spec(args.folds)
    all_summaries: List[Dict] = []

    _, _, mode_for_cache = _resolve_embedding_setup(args)
    _warmup_shared_global_cache(
        args=args,
        folds=folds,
        targets=targets,
        effective_pretrained_ckpt=effective_pretrained_ckpt,
        mode_for_cache=mode_for_cache,
    )
    if len(folds) == 1:
        device = resolve_device(args.device)
        pretrained_model, _, encoder_load_info = load_pretrained_mfm(
            effective_pretrained_ckpt,
            device,
            return_load_info=True,
        )
        embedder_cfg = EmbedderConfig(
            num_conformers=args.num_conformers,
            optimize_conformers=bool(args.optimize_conformers),
            max_opt_iters=args.max_opt_iters,
            add_hs=bool(args.add_hs),
            embedding_mode=str(mode_for_cache),
            xyz_pool_root=(None if args.xyz_pool_root is None else str(args.xyz_pool_root)),
            atom_index_offset=args.atom_index_offset,
        )
        embedder = MFMConformerEmbedder(pretrained_model, device, embedder_cfg)
        _attach_embedder_cache_metadata(embedder, effective_pretrained_ckpt)
        print("Encoder load info:", encoder_load_info)
        all_summaries.append(
            train_single_fold(
                args=args,
                fold=folds[0],
                targets=targets,
                embedder=embedder,
                encoder_load_info=encoder_load_info,
                effective_pretrained_ckpt=effective_pretrained_ckpt,
                device=device,
            )
        )
    else:
        base_args = vars(args).copy()
        futures = []
        requested_device = str(args.device).lower()
        use_cuda_pool = False
        cuda_device_pool: List[str] = []
        if requested_device == "auto":
            if torch.cuda.is_available():
                use_cuda_pool = True
                cuda_device_pool = [f"cuda:{i}" for i in range(torch.cuda.device_count())]
        elif requested_device == "cuda":
            if not torch.cuda.is_available() or torch.cuda.device_count() <= 0:
                raise RuntimeError("device=cuda was requested, but no CUDA device is available.")
            use_cuda_pool = True
            cuda_device_pool = [f"cuda:{i}" for i in range(torch.cuda.device_count())]
        elif requested_device.startswith("cuda:"):
            use_cuda_pool = True
            cuda_device_pool = [str(args.device)]

        requested_workers = int(args.fold_workers)
        if requested_workers < 0:
            raise ValueError("--fold_workers must be >= 0.")
        if requested_workers > 0:
            max_workers = min(len(folds), requested_workers)
        elif use_cuda_pool:
            max_workers = min(len(folds), len(cuda_device_pool))
        else:
            max_workers = min(len(folds), max(1, os.cpu_count() or 1))

        if use_cuda_pool:
            print(f"Parallel folds: workers={max_workers}, cuda_devices={cuda_device_pool}")
        else:
            print(f"Parallel folds: workers={max_workers}, device={args.device}")

        # Use spawn to avoid CUDA re-init failures caused by forking after CUDA is touched.
        mp_ctx = mp.get_context("spawn")
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=mp_ctx) as ex:
            for i, fold in enumerate(folds):
                fold_args = dict(base_args)
                if use_cuda_pool:
                    fold_args["device"] = cuda_device_pool[i % len(cuda_device_pool)]
                futures.append(ex.submit(_train_fold_worker, fold_args, int(fold), list(targets)))
            for fut in as_completed(futures):
                all_summaries.append(fut.result())
        all_summaries.sort(key=lambda x: int(x.get("fold", 0)))

    save_json(Path(args.output_dir) / "train_summary.json", {"folds": all_summaries})
    print("Training complete.")


if __name__ == "__main__":
    main()
