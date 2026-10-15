import argparse
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
import torch

from common import (
    AtomwiseLatePoolRegressionHead,
    ConformerAttentionLatePoolRegressionHead,
    EmbeddingTransform,
    EmbedderConfig,
    LabelScaler,
    MFMConformerEmbedder,
    RegressionHead,
    add_shared_parser_args,
    compute_metrics_table,
    get_atom_embeddings_with_global_cache,
    get_conformer_atom_embeddings_with_global_cache,
    get_embeddings_with_global_cache,
    get_structure_atom_embeddings_with_global_cache,
    get_structure_embeddings_with_global_cache,
    load_fold_split,
    load_pretrained_mfm,
    parse_fold_spec,
    prepare_task_df,
    print_metrics,
    resolve_device,
    save_json,
    select_best_checkpoint,
    set_seed,
)


def _load_head(ckpt_path: Path, device: torch.device) -> Dict:
    payload = torch.load(ckpt_path, map_location="cpu")
    head_cfg = payload.get("head_cfg", {})
    pooling_timing = str(head_cfg.get("pooling_timing", "early"))
    pooling_arch = str(head_cfg.get("pooling_arch", "atomwise_v1"))
    if pooling_timing == "late":
        if pooling_arch == "conf_attn_v1":
            model = ConformerAttentionLatePoolRegressionHead(
                in_dim=int(payload["embedding_dim"]),
                out_dim=len(payload["targets"]),
                hidden_dim=int(head_cfg.get("hidden_dim", 512)),
                atom_layers=int(head_cfg.get("atom_head_layers", 2)),
                readout_layers=int(head_cfg.get("head_layers", 2)),
                dropout=float(head_cfg.get("dropout", 0.1)),
            ).to(device)
        else:
            model = AtomwiseLatePoolRegressionHead(
                in_dim=int(payload["embedding_dim"]),
                out_dim=len(payload["targets"]),
                hidden_dim=int(head_cfg.get("hidden_dim", 512)),
                atom_layers=int(head_cfg.get("atom_head_layers", 2)),
                readout_layers=int(head_cfg.get("head_layers", 2)),
                dropout=float(head_cfg.get("dropout", 0.1)),
            ).to(device)
    else:
        model = RegressionHead(
            in_dim=int(payload["embedding_dim"]),
            out_dim=len(payload["targets"]),
            hidden_dim=int(head_cfg.get("hidden_dim", 512)),
            n_layers=int(head_cfg.get("head_layers", 2)),
            dropout=float(head_cfg.get("dropout", 0.1)),
        ).to(device)
    model.load_state_dict(payload["head_state"])
    model.eval()
    scaler = LabelScaler.from_dict(payload["target_scaler"])
    embedding_transform = EmbeddingTransform.from_dict(payload.get("embedding_transform"))
    return {
        "model": model,
        "targets": list(payload["targets"]),
        "mode": payload.get("mode", "mt"),
        "scaler": scaler,
        "feature_cfg": payload.get("feature_cfg", {}),
        "pretrained_ckpt": payload.get("pretrained_ckpt"),
        "pooling_timing": pooling_timing,
        "pooling_arch": pooling_arch,
        "embedding_transform": embedding_transform,
    }


def _feature_cfg_from_payload(feature_cfg: Dict) -> EmbedderConfig:
    data_type = str(feature_cfg.get("data_type", "graph")).strip().lower()
    return EmbedderConfig(
        data_type=data_type,
        structure_path_col=str(feature_cfg.get("structure_path_col", "xyz_path")),
        num_conformers=(1 if data_type == "structure" else int(feature_cfg.get("num_conformers", 8))),
        optimize_conformers=(False if data_type == "structure" else bool(feature_cfg.get("optimize_conformers", False))),
        max_opt_iters=int(feature_cfg.get("max_opt_iters", 200)),
        add_hs=(False if data_type == "structure" else bool(feature_cfg.get("add_hs", False))),
        embedding_mode=str(feature_cfg.get("embedding_mode", "backbone")),
        xyz_pool_root=(None if data_type == "structure" else feature_cfg.get("xyz_pool_root", None)),
        atom_index_offset=int(feature_cfg.get("atom_index_offset", -1)),
    )


def _cache_path(cache_dir: str, fold: int, pooling_timing: str) -> Path:
    if str(pooling_timing) == "late":
        return Path(cache_dir) / f"fold_{fold}" / "test_conf_atom_embeddings.pt"
    return Path(cache_dir) / f"fold_{fold}" / "test_embeddings.pt"


def _global_cache_path(cache_dir: str, fold: int, pooling_timing: str) -> Path:
    if str(pooling_timing) == "late":
        return Path(cache_dir) / f"fold_{fold}" / "global_conf_atom_embeddings.pt"
    return Path(cache_dir) / f"fold_{fold}" / "global_embeddings.pt"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("Predict CV folds for MFM ADMET head")
    add_shared_parser_args(p)
    p.add_argument("--model_dir", type=str, required=True)
    p.add_argument("--output_csv", type=str, default=None)
    p.add_argument("--force_pretrained_ckpt", type=str, default=None)
    p.add_argument(
        "--cache_mode",
        type=str,
        choices=["global", "split"],
        default="global",
        help="global: reuse the fold-level shared cache written during training; split: reuse fold/test-specific cache files.",
    )
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    set_seed(args.seed)

    folds = parse_fold_spec(args.folds)
    device = resolve_device(args.device)
    all_preds = []
    per_fold_metrics: List[Dict] = []
    targets_ref: List[str] = []
    mode_ref = None
    embedder_cache: Dict = {}

    for fold in folds:
        fold_model_dir = Path(args.model_dir) / f"fold_{fold}" / "model_files"
        ckpt_path = select_best_checkpoint(fold_model_dir)
        head_bundle = _load_head(ckpt_path, device)
        targets = head_bundle["targets"]
        mode = head_bundle["mode"]
        scaler = head_bundle["scaler"]
        model = head_bundle["model"]
        pooling_timing = str(head_bundle.get("pooling_timing", "early"))
        pooling_arch = str(head_bundle.get("pooling_arch", "atomwise_v1"))
        embedding_transform = head_bundle.get("embedding_transform")
        targets_ref = targets
        mode_ref = mode

        if args.force_pretrained_ckpt:
            backbone_ckpt = args.force_pretrained_ckpt
        else:
            backbone_ckpt = head_bundle["pretrained_ckpt"] or args.pretrained_ckpt
        if not backbone_ckpt:
            raise ValueError(
                "No pretrained backbone checkpoint available. Provide --force_pretrained_ckpt or --pretrained_ckpt."
            )
        feature_cfg = _feature_cfg_from_payload(head_bundle["feature_cfg"])
        if args.xyz_pool_root is not None:
            feature_cfg.xyz_pool_root = str(args.xyz_pool_root)
        key = (
            str(backbone_ckpt),
            feature_cfg.data_type,
            feature_cfg.structure_path_col,
            feature_cfg.num_conformers,
            feature_cfg.optimize_conformers,
            feature_cfg.max_opt_iters,
            feature_cfg.add_hs,
            feature_cfg.embedding_mode,
            feature_cfg.xyz_pool_root,
            feature_cfg.atom_index_offset,
        )
        if key not in embedder_cache:
            backbone_model, _ = load_pretrained_mfm(backbone_ckpt, device)
            embedder_cache[key] = MFMConformerEmbedder(backbone_model, device, feature_cfg)
        embedder = embedder_cache[key]

        test_raw = load_fold_split(args.data_dir, fold, "test")
        test_df = prepare_task_df(test_raw, targets)
        data_type = str(feature_cfg.data_type).strip().lower()
        if data_type == "structure":
            path_col = str(feature_cfg.structure_path_col)
            if path_col not in test_df.columns:
                raise KeyError(
                    f"Missing structure path column '{path_col}' in test split. "
                    f"Available columns: {list(test_df.columns)}"
                )
            xyz_paths = test_df[path_col].astype(str).tolist()
            sample_keys = [str(Path(p).expanduser()) for p in xyz_paths]
        else:
            smiles = test_df["smiles"].tolist()

        if args.cache_dir:
            if args.cache_mode == "global":
                cache_path = _global_cache_path(args.cache_dir, fold, pooling_timing)
            else:
                cache_path = _cache_path(args.cache_dir, fold, pooling_timing)
            print(f"[Fold {fold}] Predict embedding cache: mode={args.cache_mode} path={cache_path}")
        else:
            cache_path = None
        if pooling_timing == "late":
            if pooling_arch == "conf_attn_v1":
                if data_type == "structure":
                    raise ValueError("pooling_arch=conf_attn_v1 is only supported for data_type=graph.")
                x_test_t, atom_mask_test, conf_mask_test, valid_test = get_conformer_atom_embeddings_with_global_cache(
                    embedder,
                    smiles,
                    cache_path=cache_path,
                    seed=args.seed + fold * 7000,
                    desc=f"Fold{fold}-predict-conf-atom-embed",
                )
                if embedding_transform is not None:
                    x_test_t = embedding_transform.transform_torch(x_test_t).float()
                with torch.no_grad():
                    y_pred_scaled = model(
                        x_test_t.float().to(device),
                        torch.from_numpy(atom_mask_test).bool().to(device),
                        torch.from_numpy(conf_mask_test).bool().to(device),
                    ).cpu().numpy()
            else:
                if data_type == "structure":
                    x_test_t, atom_mask_test, valid_test = get_structure_atom_embeddings_with_global_cache(
                        embedder,
                        sample_keys,
                        xyz_paths,
                        cache_path=cache_path,
                        seed=args.seed + fold * 7000,
                        desc=f"Fold{fold}-predict-atom-embed",
                    )
                else:
                    x_test_t, atom_mask_test, valid_test = get_atom_embeddings_with_global_cache(
                        embedder,
                        smiles,
                        cache_path=cache_path,
                        seed=args.seed + fold * 7000,
                        desc=f"Fold{fold}-predict-atom-embed",
                    )
                if embedding_transform is not None:
                    x_test_t = embedding_transform.transform_torch(x_test_t).float()
                with torch.no_grad():
                    y_pred_scaled = model(
                        x_test_t.float().to(device),
                        torch.from_numpy(atom_mask_test).bool().to(device),
                    ).cpu().numpy()
        else:
            if data_type == "structure":
                x_test_t, valid_test = get_structure_embeddings_with_global_cache(
                    embedder,
                    sample_keys,
                    xyz_paths,
                    cache_path=cache_path,
                    seed=args.seed + fold * 7000,
                    desc=f"Fold{fold}-predict-embed",
                )
            else:
                x_test_t, valid_test = get_embeddings_with_global_cache(
                    embedder,
                    smiles,
                    cache_path=cache_path,
                    seed=args.seed + fold * 7000,
                    desc=f"Fold{fold}-predict-embed",
                )
            if embedding_transform is not None:
                x_test_t = embedding_transform.transform_torch(x_test_t).float()
            with torch.no_grad():
                y_pred_scaled = model(x_test_t.float().to(device)).cpu().numpy()
        y_pred = scaler.inverse(y_pred_scaled)
        y_true = test_df.loc[:, targets].to_numpy(dtype=np.float32)
        metrics = compute_metrics_table(y_true, y_pred, targets)
        print(f"Fold {fold} metrics")
        print_metrics(metrics)
        per_fold_metrics.append({"fold": fold, "metrics": metrics, "valid_embed": int(valid_test.sum())})

        if mode == "st":
            target = targets[0]
            if data_type == "structure":
                out_df = pd.DataFrame({str(feature_cfg.structure_path_col): test_df[str(feature_cfg.structure_path_col)].values})
                if "smiles" in test_df.columns:
                    out_df["smiles"] = test_df["smiles"].values
                out_df[target] = test_df[target].values
                out_df[f"{target}_pred"] = y_pred[:, 0]
            else:
                out_df = pd.DataFrame(
                    {
                        "smiles": test_df["smiles"].values,
                        target: test_df[target].values,
                        f"{target}_pred": y_pred[:, 0],
                    }
                )
        else:
            if data_type == "structure":
                base_cols = [str(feature_cfg.structure_path_col)]
                if "smiles" in test_df.columns:
                    base_cols.append("smiles")
                out_df = test_df[base_cols + targets].copy()
            else:
                out_df = test_df[["smiles"] + targets].copy()
            for i, name in enumerate(targets):
                out_df[f"{name}_pred"] = y_pred[:, i]
        all_preds.append(out_df)

    pred_df = pd.concat(all_preds, axis=0).reset_index(drop=True)
    output_csv = Path(args.output_csv) if args.output_csv else Path(args.model_dir) / "cv_preds.csv"
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    pred_df.to_csv(output_csv, index=False)

    print("Cross-fold summary")
    for target in targets_ref:
        maes = []
        rmses = []
        r2s = []
        for item in per_fold_metrics:
            vals = item["metrics"][target]
            maes.append(vals["mae"])
            rmses.append(vals["rmse"])
            r2s.append(vals["r2"])
        print(target)
        print(f"  Test MAE:  {np.nanmean(maes)} +/- {np.nanstd(maes)}")
        print(f"  Test RMSE: {np.nanmean(rmses)} +/- {np.nanstd(rmses)}")
        print(f"  Test R2:   {np.nanmean(r2s)} +/- {np.nanstd(r2s)}")

    save_json(
        Path(args.model_dir) / "predict_cv_summary.json",
        {"mode": mode_ref, "targets": targets_ref, "fold_metrics": per_fold_metrics, "output_csv": str(output_csv)},
    )
    print(f"Saved CV predictions to: {output_csv}")


if __name__ == "__main__":
    main()
