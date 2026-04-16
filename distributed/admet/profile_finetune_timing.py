import argparse
import gc
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
import torch
from torch.profiler import ProfilerActivity, profile


THIS_DIR = Path(__file__).resolve().parent


def _load_common_module(module_root: Path):
    module_root = module_root.resolve()
    common_path = module_root / "admet" / "common.py"
    if not common_path.exists():
        raise FileNotFoundError(f"Missing common.py at {common_path}")
    sys.path.insert(0, str(common_path.parent))
    spec = importlib.util.spec_from_file_location(f"profile_common_{module_root.name}", common_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to import {common_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sample_df(df: pd.DataFrame, max_rows: int, seed: int) -> pd.DataFrame:
    if max_rows <= 0 or len(df) <= max_rows:
        return df.reset_index(drop=True)
    return df.sample(n=int(max_rows), random_state=int(seed)).reset_index(drop=True)


def _resolve_embedding_setup(common_mod, embedding_mode: str, pooling_timing: str) -> Tuple[str, str, str]:
    base_mode, timing = common_mod.resolve_embedding_and_pooling(embedding_mode, pooling_timing)
    mode_for_cache = str(embedding_mode)
    if timing == "late" and mode_for_cache in {"backbone", "moe_concat", "moe_fused", "backbone_moe_fused"}:
        mode_for_cache = f"{base_mode}_late"
    return str(base_mode), str(timing), str(mode_for_cache)


def _np_targets(df: pd.DataFrame, targets: Sequence[str]) -> np.ndarray:
    return df.loc[:, list(targets)].to_numpy(dtype=np.float32)


def _profile_epoch(common_mod, model, loader, device: torch.device, optimizer, task_weights=None) -> Dict[str, Any]:
    model.train(True)
    timings = {
        "fetch_s": 0.0,
        "to_device_s": 0.0,
        "forward_s": 0.0,
        "backward_s": 0.0,
        "optimizer_s": 0.0,
        "loss_s": 0.0,
        "batches": 0,
        "examples": 0,
    }
    total_loss = 0.0
    iterator = iter(loader)
    while True:
        t0 = time.perf_counter()
        try:
            batch = next(iterator)
        except StopIteration:
            break
        timings["fetch_s"] += time.perf_counter() - t0

        conf_mask_b = None
        if len(batch) == 3:
            xb, yb, mb = batch
            atom_mask_b = None
        elif len(batch) == 4:
            xb, atom_mask_b, yb, mb = batch
        elif len(batch) == 5:
            xb, atom_mask_b, conf_mask_b, yb, mb = batch
        else:
            raise ValueError(f"Unexpected batch size: {len(batch)}")

        t1 = time.perf_counter()
        xb = xb.to(device)
        yb = yb.to(device)
        mb = mb.to(device)
        if atom_mask_b is not None:
            atom_mask_b = atom_mask_b.to(device)
        if conf_mask_b is not None:
            conf_mask_b = conf_mask_b.to(device)
        timings["to_device_s"] += time.perf_counter() - t1

        optimizer.zero_grad(set_to_none=True)
        t2 = time.perf_counter()
        if atom_mask_b is None and conf_mask_b is None:
            pred = model(xb)
        elif conf_mask_b is None:
            pred = model(xb, atom_mask_b)
        else:
            pred = model(xb, atom_mask_b, conf_mask_b)
        timings["forward_s"] += time.perf_counter() - t2

        t3 = time.perf_counter()
        loss = common_mod.masked_weighted_mse(pred, yb, mb, task_weights)
        timings["loss_s"] += time.perf_counter() - t3

        t4 = time.perf_counter()
        loss.backward()
        timings["backward_s"] += time.perf_counter() - t4

        t5 = time.perf_counter()
        optimizer.step()
        timings["optimizer_s"] += time.perf_counter() - t5

        timings["batches"] += 1
        timings["examples"] += int(xb.shape[0])
        total_loss += float(loss.item())

    timings["avg_loss"] = total_loss / max(1, timings["batches"])
    return timings


def _profile_single_batch(common_mod, model, batch, device: torch.device, optimizer, task_weights=None) -> Dict[str, Any]:
    conf_mask_b = None
    if len(batch) == 3:
        xb, yb, mb = batch
        atom_mask_b = None
    elif len(batch) == 4:
        xb, atom_mask_b, yb, mb = batch
    elif len(batch) == 5:
        xb, atom_mask_b, conf_mask_b, yb, mb = batch
    else:
        raise ValueError(f"Unexpected batch size: {len(batch)}")

    xb = xb.to(device)
    yb = yb.to(device)
    mb = mb.to(device)
    if atom_mask_b is not None:
        atom_mask_b = atom_mask_b.to(device)
    if conf_mask_b is not None:
        conf_mask_b = conf_mask_b.to(device)

    optimizer.zero_grad(set_to_none=True)
    with profile(activities=[ProfilerActivity.CPU], record_shapes=True, profile_memory=True) as prof:
        if atom_mask_b is None and conf_mask_b is None:
            pred = model(xb)
        elif conf_mask_b is None:
            pred = model(xb, atom_mask_b)
        else:
            pred = model(xb, atom_mask_b, conf_mask_b)
        loss = common_mod.masked_weighted_mse(pred, yb, mb, task_weights)
        loss.backward()
        optimizer.step()
    return {
        "table": prof.key_averages().table(sort_by="cpu_time_total", row_limit=15),
        "loss": float(loss.item()),
    }


def _benchmark_repeated_batch(common_mod, model, batch, device: torch.device, optimizer, task_weights=None, steps: int = 40) -> Dict[str, Any]:
    conf_mask_b = None
    if len(batch) == 3:
        xb, yb, mb = batch
        atom_mask_b = None
    elif len(batch) == 4:
        xb, atom_mask_b, yb, mb = batch
    elif len(batch) == 5:
        xb, atom_mask_b, conf_mask_b, yb, mb = batch
    else:
        raise ValueError(f"Unexpected batch size: {len(batch)}")

    xb = xb.to(device)
    yb = yb.to(device)
    mb = mb.to(device)
    if atom_mask_b is not None:
        atom_mask_b = atom_mask_b.to(device)
    if conf_mask_b is not None:
        conf_mask_b = conf_mask_b.to(device)

    model.train(True)
    t0 = time.perf_counter()
    last_loss = float("nan")
    for _ in range(int(steps)):
        optimizer.zero_grad(set_to_none=True)
        if atom_mask_b is None and conf_mask_b is None:
            pred = model(xb)
        elif conf_mask_b is None:
            pred = model(xb, atom_mask_b)
        else:
            pred = model(xb, atom_mask_b, conf_mask_b)
        loss = common_mod.masked_weighted_mse(pred, yb, mb, task_weights)
        loss.backward()
        optimizer.step()
        last_loss = float(loss.item())
    elapsed = time.perf_counter() - t0
    return {
        "steps": int(steps),
        "total_s": elapsed,
        "avg_step_s": elapsed / max(1, int(steps)),
        "last_loss": last_loss,
    }


def _delete_pretrained_state(pretrained_model, embedder) -> None:
    try:
        if pretrained_model is not None:
            pretrained_model.to("cpu")
    except Exception:
        pass
    try:
        if embedder is not None and getattr(embedder, "model", None) is not None:
            embedder.model.to("cpu")
    except Exception:
        pass
    del pretrained_model
    del embedder
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def main() -> None:
    parser = argparse.ArgumentParser("Profile fine-tune timing for old/new MFM on one fold")
    parser.add_argument("--impl", type=str, choices=["old", "new"], required=True)
    parser.add_argument("--module_root", type=str, required=True)
    parser.add_argument("--pretrained_ckpt", type=str, required=True)
    parser.add_argument("--data_dir", type=str, required=True)
    parser.add_argument("--fold", type=int, default=1)
    parser.add_argument("--target", type=str, default="LogD")
    parser.add_argument("--num_conformers", type=int, default=8)
    parser.add_argument("--optimize_conformers", dest="optimize_conformers", action="store_true")
    parser.add_argument("--no_optimize_conformers", dest="optimize_conformers", action="store_false")
    parser.add_argument("--add_hs", dest="add_hs", action="store_true")
    parser.add_argument("--no_add_hs", dest="add_hs", action="store_false")
    parser.add_argument("--embedding_mode", type=str, default="backbone")
    parser.add_argument("--pooling_timing", type=str, default="late")
    parser.add_argument("--atom_index_offset", type=int, default=-1)
    parser.add_argument("--max_train_rows", type=int, default=128)
    parser.add_argument("--max_val_rows", type=int, default=32)
    parser.add_argument("--batch_size", type=int, default=32)
    parser.add_argument("--hidden_dim", type=int, default=1024)
    parser.add_argument("--head_layers", type=int, default=2)
    parser.add_argument("--atom_head_layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.1)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--cache_dir", type=str, default=None)
    parser.add_argument("--xyz_pool_root", type=str, default=None)
    parser.add_argument("--report_path", type=str, default=None)
    parser.set_defaults(optimize_conformers=False, add_hs=True)
    args = parser.parse_args()

    t_all0 = time.perf_counter()
    common_mod = _load_common_module(Path(args.module_root))
    common_mod.set_seed(int(args.seed))
    device = common_mod.resolve_device("cpu")
    base_mode, pooling_timing, mode_for_cache = _resolve_embedding_setup(common_mod, args.embedding_mode, args.pooling_timing)
    use_late_pooling = pooling_timing == "late"

    t0 = time.perf_counter()
    pretrained_model, _, load_info = common_mod.load_pretrained_mfm(args.pretrained_ckpt, device, return_load_info=True)
    t_load = time.perf_counter() - t0

    cfg_kwargs = dict(
        num_conformers=int(args.num_conformers),
        optimize_conformers=bool(args.optimize_conformers),
        max_opt_iters=200,
        add_hs=bool(args.add_hs),
        embedding_mode=str(mode_for_cache),
        atom_index_offset=int(args.atom_index_offset),
    )
    if "xyz_pool_root" in getattr(common_mod, "EmbedderConfig").__annotations__:
        cfg_kwargs["xyz_pool_root"] = None if args.xyz_pool_root is None else str(args.xyz_pool_root)

    t1 = time.perf_counter()
    embedder_cfg = common_mod.EmbedderConfig(**cfg_kwargs)
    embedder = common_mod.MFMConformerEmbedder(pretrained_model, device, embedder_cfg)
    t_embedder_init = time.perf_counter() - t1

    raw_train = common_mod.load_fold_split(args.data_dir, int(args.fold), "train")
    train_df = common_mod.prepare_task_df(raw_train, [args.target])
    tr_idx, va_idx = common_mod.split_train_val(len(train_df), 0.1, int(args.seed) + int(args.fold))
    train_sub = train_df.iloc[tr_idx].reset_index(drop=True)
    val_sub = train_df.iloc[va_idx].reset_index(drop=True)
    train_sub = _sample_df(train_sub, int(args.max_train_rows), int(args.seed) + 17)
    val_sub = _sample_df(val_sub, int(args.max_val_rows), int(args.seed) + 23)

    cache_base = Path(args.cache_dir) if args.cache_dir else (THIS_DIR.parent / "tmp_profile_cache")
    cache_base.mkdir(parents=True, exist_ok=True)
    cache_path = cache_base / f"{args.impl}_fold{args.fold}_{pooling_timing}_{base_mode}.pt"

    if use_late_pooling:
        t2 = time.perf_counter()
        x_train_t, atom_mask_train, valid_train = common_mod.get_atom_embeddings_with_global_cache(
            embedder,
            train_sub["smiles"].tolist(),
            cache_path=cache_path,
            seed=int(args.seed) + 1000,
            desc=f"profile-{args.impl}-train-atom",
        )
        t_embed_train = time.perf_counter() - t2

        t3 = time.perf_counter()
        x_val_t, atom_mask_val, valid_val = common_mod.get_atom_embeddings_with_global_cache(
            embedder,
            val_sub["smiles"].tolist(),
            cache_path=cache_path,
            seed=int(args.seed) + 2000,
            desc=f"profile-{args.impl}-val-atom",
        )
        t_embed_val = time.perf_counter() - t3

        y_train = _np_targets(train_sub, [args.target])
        y_val = _np_targets(val_sub, [args.target])
        mask_train = np.isfinite(y_train)
        mask_val = np.isfinite(y_val)
        scaler = common_mod.LabelScaler.fit(y_train)
        y_train_scaled = scaler.transform(y_train)
        y_val_scaled = scaler.transform(y_val)

        train_loader = common_mod.build_atom_feature_loader(
            x_train_t,
            atom_mask_train,
            y_train_scaled,
            mask_train,
            batch_size=int(args.batch_size),
            shuffle=True,
        )
        val_loader = common_mod.build_atom_feature_loader(
            x_val_t,
            atom_mask_val,
            y_val_scaled,
            mask_val,
            batch_size=int(args.batch_size),
            shuffle=False,
        )
        head = common_mod.AtomwiseLatePoolRegressionHead(
            in_dim=int(x_train_t.shape[2]),
            out_dim=1,
            hidden_dim=int(args.hidden_dim),
            atom_layers=int(args.atom_head_layers),
            readout_layers=int(args.head_layers),
            dropout=float(args.dropout),
        ).to(device)
        batch_shape = list(x_train_t.shape)
        avg_atoms = float(atom_mask_train.sum(axis=1).mean())
        max_atoms = int(atom_mask_train.sum(axis=1).max())
        batch_bytes = int(np.prod(batch_shape[1:]) * 4 * min(int(args.batch_size), batch_shape[0]))
    else:
        t2 = time.perf_counter()
        x_train_t, valid_train = common_mod.get_embeddings_with_global_cache(
            embedder,
            train_sub["smiles"].tolist(),
            cache_path=cache_path,
            seed=int(args.seed) + 1000,
            desc=f"profile-{args.impl}-train",
        )
        t_embed_train = time.perf_counter() - t2

        t3 = time.perf_counter()
        x_val_t, valid_val = common_mod.get_embeddings_with_global_cache(
            embedder,
            val_sub["smiles"].tolist(),
            cache_path=cache_path,
            seed=int(args.seed) + 2000,
            desc=f"profile-{args.impl}-val",
        )
        t_embed_val = time.perf_counter() - t3

        x_train = x_train_t.numpy()
        x_val = x_val_t.numpy()
        y_train = _np_targets(train_sub, [args.target])
        y_val = _np_targets(val_sub, [args.target])
        mask_train = np.isfinite(y_train)
        mask_val = np.isfinite(y_val)
        scaler = common_mod.LabelScaler.fit(y_train)
        y_train_scaled = scaler.transform(y_train)
        y_val_scaled = scaler.transform(y_val)
        train_loader = common_mod.build_feature_loader(x_train, y_train_scaled, mask_train, batch_size=int(args.batch_size), shuffle=True)
        val_loader = common_mod.build_feature_loader(x_val, y_val_scaled, mask_val, batch_size=int(args.batch_size), shuffle=False)
        head = common_mod.RegressionHead(
            in_dim=int(x_train.shape[1]),
            out_dim=1,
            hidden_dim=int(args.hidden_dim),
            n_layers=int(args.head_layers),
            dropout=float(args.dropout),
        ).to(device)
        batch_shape = list(x_train.shape)
        avg_atoms = float("nan")
        max_atoms = -1
        batch_bytes = int(np.prod(batch_shape[1:]) * 4 * min(int(args.batch_size), batch_shape[0]))

    head_params = int(sum(p.numel() for p in head.parameters()))
    opt = torch.optim.AdamW(head.parameters(), lr=float(args.lr), weight_decay=1e-4)

    first_batch = next(iter(train_loader))
    single_batch_profile = _profile_single_batch(common_mod, head, first_batch, device, opt)
    head_repeat = type(head)(**{
        "in_dim": int(batch_shape[2]) if use_late_pooling else int(batch_shape[1]),
        "out_dim": 1,
        "hidden_dim": int(args.hidden_dim),
        "atom_layers": int(args.atom_head_layers),
        "readout_layers": int(args.head_layers),
        "dropout": float(args.dropout),
    }).to(device) if use_late_pooling else common_mod.RegressionHead(
        in_dim=int(batch_shape[1]),
        out_dim=1,
        hidden_dim=int(args.hidden_dim),
        n_layers=int(args.head_layers),
        dropout=float(args.dropout),
    ).to(device)
    opt_repeat = torch.optim.AdamW(head_repeat.parameters(), lr=float(args.lr), weight_decay=1e-4)
    repeated_batch_benchmark = _benchmark_repeated_batch(common_mod, head_repeat, first_batch, device, opt_repeat, steps=40)

    head2 = type(head)(**{
        "in_dim": int(batch_shape[2]) if use_late_pooling else int(batch_shape[1]),
        "out_dim": 1,
        "hidden_dim": int(args.hidden_dim),
        "atom_layers": int(args.atom_head_layers),
        "readout_layers": int(args.head_layers),
        "dropout": float(args.dropout),
    }).to(device) if use_late_pooling else common_mod.RegressionHead(
        in_dim=int(batch_shape[1]),
        out_dim=1,
        hidden_dim=int(args.hidden_dim),
        n_layers=int(args.head_layers),
        dropout=float(args.dropout),
    ).to(device)
    opt2 = torch.optim.AdamW(head2.parameters(), lr=float(args.lr), weight_decay=1e-4)
    t4 = time.perf_counter()
    train_epoch_timing = _profile_epoch(common_mod, head2, train_loader, device, opt2)
    t_train_epoch = time.perf_counter() - t4

    head3 = type(head2)(**{
        "in_dim": int(batch_shape[2]) if use_late_pooling else int(batch_shape[1]),
        "out_dim": 1,
        "hidden_dim": int(args.hidden_dim),
        "atom_layers": int(args.atom_head_layers),
        "readout_layers": int(args.head_layers),
        "dropout": float(args.dropout),
    }).to(device) if use_late_pooling else common_mod.RegressionHead(
        in_dim=int(batch_shape[1]),
        out_dim=1,
        hidden_dim=int(args.hidden_dim),
        n_layers=int(args.head_layers),
        dropout=float(args.dropout),
    ).to(device)
    opt3 = torch.optim.AdamW(head3.parameters(), lr=float(args.lr), weight_decay=1e-4)
    _delete_pretrained_state(pretrained_model, embedder)
    t5 = time.perf_counter()
    train_epoch_after_release = _profile_epoch(common_mod, head3, train_loader, device, opt3)
    t_train_epoch_after_release = time.perf_counter() - t5

    val_batches = len(val_loader)
    report = {
        "impl": args.impl,
        "module_root": str(Path(args.module_root).resolve()),
        "checkpoint": str(Path(args.pretrained_ckpt).resolve()),
        "checkpoint_size_mb": float(Path(args.pretrained_ckpt).stat().st_size / (1024 * 1024)),
        "fold": int(args.fold),
        "target": str(args.target),
        "embedding_mode": str(args.embedding_mode),
        "pooling_timing": str(pooling_timing),
        "base_mode": str(base_mode),
        "load_info": load_info,
        "latent_dim": int(getattr(head, "atom_net", None)[0].in_features if use_late_pooling else batch_shape[1]),
        "head_params": int(head_params),
        "batch_shape": batch_shape,
        "avg_atoms": avg_atoms,
        "max_atoms": max_atoms,
        "approx_batch_input_mb": float(batch_bytes / (1024 * 1024)),
        "valid_train": int(valid_train.sum()),
        "valid_val": int(valid_val.sum()),
        "n_train": int(len(train_sub)),
        "n_val": int(len(val_sub)),
        "n_train_batches": int(len(train_loader)),
        "n_val_batches": int(val_batches),
        "timing_seconds": {
            "load_pretrained": t_load,
            "init_embedder": t_embedder_init,
            "embed_train": t_embed_train,
            "embed_val": t_embed_val,
            "train_epoch_keep_encoder": t_train_epoch,
            "train_epoch_after_release": t_train_epoch_after_release,
            "total": time.perf_counter() - t_all0,
        },
        "train_epoch_breakdown_keep_encoder": train_epoch_timing,
        "train_epoch_breakdown_after_release": train_epoch_after_release,
        "single_batch_profile": single_batch_profile,
        "repeated_batch_benchmark": repeated_batch_benchmark,
    }

    report_path = Path(args.report_path) if args.report_path else (cache_base / f"profile_{args.impl}_fold{args.fold}_{pooling_timing}_{base_mode}.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps({
        "impl": report["impl"],
        "checkpoint_size_mb": report["checkpoint_size_mb"],
        "latent_dim": report["latent_dim"],
        "batch_shape": report["batch_shape"],
        "approx_batch_input_mb": report["approx_batch_input_mb"],
        "timing_seconds": report["timing_seconds"],
        "train_epoch_breakdown_keep_encoder": train_epoch_timing,
        "train_epoch_breakdown_after_release": train_epoch_after_release,
        "repeated_batch_benchmark": repeated_batch_benchmark,
        "report_path": str(report_path),
    }, indent=2))
    print("\n[Single batch profiler]\n")
    print(single_batch_profile["table"])


if __name__ == "__main__":
    main()
