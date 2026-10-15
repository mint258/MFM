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
    MFMConformerEmbedder,
    RegressionHead,
    add_shared_parser_args,
    get_atom_embeddings_with_global_cache,
    get_conformer_atom_embeddings_with_global_cache,
    get_embeddings_with_global_cache,
    load_pretrained_mfm,
    parse_fold_spec,
    resolve_device,
    save_json,
    select_best_checkpoint,
    set_seed,
)


def _load_head_payload(path: Path, device: torch.device) -> Dict:
    payload = torch.load(path, map_location="cpu")
    targets = list(payload["targets"])
    head_cfg = payload.get("head_cfg", {})
    pooling_timing = str(head_cfg.get("pooling_timing", "early"))
    pooling_arch = str(head_cfg.get("pooling_arch", "atomwise_v1"))
    if pooling_timing == "late":
        if pooling_arch == "conf_attn_v1":
            model = ConformerAttentionLatePoolRegressionHead(
                in_dim=int(payload["embedding_dim"]),
                out_dim=len(targets),
                hidden_dim=int(head_cfg.get("hidden_dim", 512)),
                atom_layers=int(head_cfg.get("atom_head_layers", 2)),
                readout_layers=int(head_cfg.get("head_layers", 2)),
                dropout=float(head_cfg.get("dropout", 0.1)),
            ).to(device)
        else:
            model = AtomwiseLatePoolRegressionHead(
                in_dim=int(payload["embedding_dim"]),
                out_dim=len(targets),
                hidden_dim=int(head_cfg.get("hidden_dim", 512)),
                atom_layers=int(head_cfg.get("atom_head_layers", 2)),
                readout_layers=int(head_cfg.get("head_layers", 2)),
                dropout=float(head_cfg.get("dropout", 0.1)),
            ).to(device)
    else:
        model = RegressionHead(
            in_dim=int(payload["embedding_dim"]),
            out_dim=len(targets),
            hidden_dim=int(head_cfg.get("hidden_dim", 512)),
            n_layers=int(head_cfg.get("head_layers", 2)),
            dropout=float(head_cfg.get("dropout", 0.1)),
        ).to(device)
    model.load_state_dict(payload["head_state"])
    model.eval()
    payload["_pooling_timing"] = pooling_timing
    payload["_pooling_arch"] = pooling_arch
    payload["_embedding_transform"] = EmbeddingTransform.from_dict(payload.get("embedding_transform"))
    return payload, model


def _embed_cfg_from_payload(payload: Dict) -> EmbedderConfig:
    fcfg = payload.get("feature_cfg", {})
    return EmbedderConfig(
        num_conformers=int(fcfg.get("num_conformers", 8)),
        optimize_conformers=bool(fcfg.get("optimize_conformers", False)),
        max_opt_iters=int(fcfg.get("max_opt_iters", 200)),
        add_hs=bool(fcfg.get("add_hs", False)),
        embedding_mode=str(fcfg.get("embedding_mode", "backbone")),
        xyz_pool_root=fcfg.get("xyz_pool_root", None),
        atom_index_offset=int(fcfg.get("atom_index_offset", -1)),
    )


def _inverse_scale(pred_scaled: np.ndarray, scaler_dict: Dict) -> np.ndarray:
    mean = np.asarray(scaler_dict["mean"], dtype=np.float32)[None, :]
    std = np.asarray(scaler_dict["std"], dtype=np.float32)[None, :]
    return pred_scaled * std + mean


def _ensemble_cache_path(cache_dir: str, pooling_timing: str, cache_mode: str) -> Path:
    scope_dir = Path(cache_dir) / "ensemble"
    if str(pooling_timing) == "late":
        cache_name = "global_conf_atom_embeddings.pt" if cache_mode == "global" else "ensemble_test_conf_atom_embeddings.pt"
    else:
        cache_name = "global_embeddings.pt" if cache_mode == "global" else "ensemble_test_embeddings.pt"
    return scope_dir / cache_name


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("Ensemble predictions across CV folds for MFM ADMET")
    add_shared_parser_args(p)
    p.add_argument("--model_dir", type=str, required=True)
    p.add_argument("--test_csv", type=str, default="hf://datasets/openadmet/openadmet-challenge-test-data-blinded/expansion_data_test_blinded.csv")
    p.add_argument("--output_csv", type=str, default=None)
    p.add_argument("--force_pretrained_ckpt", type=str, default=None)
    p.add_argument(
        "--cache_mode",
        type=str,
        choices=["global", "split"],
        default="global",
        help="global: one cache file under cache_dir/ensemble shared by this ensemble run; split: use a dedicated ensemble-test cache file.",
    )
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    set_seed(args.seed)

    folds = parse_fold_spec(args.folds)
    device = resolve_device(args.device)

    first_fold_ckpt = select_best_checkpoint(Path(args.model_dir) / f"fold_{folds[0]}" / "model_files")
    first_payload, _ = _load_head_payload(first_fold_ckpt, device)
    targets = list(first_payload["targets"])
    mode = first_payload.get("mode", "mt")
    pooling_timing = str(first_payload.get("_pooling_timing", "early"))
    pooling_arch = str(first_payload.get("_pooling_arch", "atomwise_v1"))

    if args.force_pretrained_ckpt:
        backbone_ckpt = args.force_pretrained_ckpt
    else:
        backbone_ckpt = first_payload.get("pretrained_ckpt") or args.pretrained_ckpt
    if not backbone_ckpt:
        raise ValueError("No pretrained backbone checkpoint found. Use --force_pretrained_ckpt or --pretrained_ckpt.")

    backbone_model, _ = load_pretrained_mfm(backbone_ckpt, device)
    embed_cfg = _embed_cfg_from_payload(first_payload)
    if args.xyz_pool_root is not None:
        embed_cfg.xyz_pool_root = str(args.xyz_pool_root)
    embedder = MFMConformerEmbedder(backbone_model, device, embed_cfg)

    try:
        df = pd.read_csv(args.test_csv)
    except ImportError as exc:
        if args.test_csv.startswith("hf://"):
            raise ImportError(
                "Failed to read hf:// test csv. Install huggingface_hub/fsspec support "
                "or pass a local --test_csv file path explicitly."
            ) from exc
        raise
    if "SMILES" not in df.columns or "Molecule Name" not in df.columns:
        raise ValueError("Input test_csv must contain 'SMILES' and 'Molecule Name' columns.")
    smiles = df["SMILES"].astype(str).tolist()

    if args.cache_dir:
        cache_path = _ensemble_cache_path(args.cache_dir, pooling_timing, args.cache_mode)
        print(f"[Ensemble] Embedding cache: mode={args.cache_mode} path={cache_path}")
    else:
        cache_path = None
    x_all = None
    atom_mask_all = None
    conf_mask_all = None
    if pooling_timing == "late":
        if pooling_arch == "conf_attn_v1":
            x_all, atom_mask_all, conf_mask_all, valid = get_conformer_atom_embeddings_with_global_cache(
                embedder,
                smiles,
                cache_path=cache_path,
                seed=args.seed + 999_999,
                desc="Ensemble-conf-atom-embed",
            )
            x_all = x_all.float().to(device)
            atom_mask_all = torch.from_numpy(atom_mask_all).bool().to(device)
            conf_mask_all = torch.from_numpy(conf_mask_all).bool().to(device)
        else:
            x_all, atom_mask_all, valid = get_atom_embeddings_with_global_cache(
                embedder,
                smiles,
                cache_path=cache_path,
                seed=args.seed + 999_999,
                desc="Ensemble-atom-embed",
            )
            x_all = x_all.float().to(device)
            atom_mask_all = torch.from_numpy(atom_mask_all).bool().to(device)
    else:
        x_all, valid = get_embeddings_with_global_cache(
            embedder,
            smiles,
            cache_path=cache_path,
            seed=args.seed + 999_999,
            desc="Ensemble-embed",
        )
        x_all = x_all.float().to(device)

    preds_by_fold: List[np.ndarray] = []
    fold_info = []
    for fold in folds:
        ckpt_path = select_best_checkpoint(Path(args.model_dir) / f"fold_{fold}" / "model_files")
        payload, head_model = _load_head_payload(ckpt_path, device)
        fold_pooling_timing = str(payload.get("_pooling_timing", "early"))
        fold_pooling_arch = str(payload.get("_pooling_arch", "atomwise_v1"))
        fold_embedding_transform = payload.get("_embedding_transform")
        if fold_embedding_transform is not None:
            x_eval = fold_embedding_transform.transform_torch(x_all).float()
        else:
            x_eval = x_all
        with torch.no_grad():
            if fold_pooling_timing == "late":
                if fold_pooling_arch == "conf_attn_v1":
                    y_scaled = head_model(x_eval, atom_mask_all, conf_mask_all).cpu().numpy()
                else:
                    y_scaled = head_model(x_eval, atom_mask_all).cpu().numpy()
            else:
                y_scaled = head_model(x_eval).cpu().numpy()
        y_pred = _inverse_scale(y_scaled, payload["target_scaler"])
        preds_by_fold.append(y_pred)
        fold_info.append({"fold": fold, "ckpt": str(ckpt_path)})

    avg_pred = np.mean(np.stack(preds_by_fold, axis=0), axis=0)
    out_df = pd.DataFrame({"SMILES": df["SMILES"], "Molecule Name": df["Molecule Name"]})
    if mode == "st":
        out_df[targets[0]] = avg_pred[:, 0]
    else:
        for i, t in enumerate(targets):
            out_df[t] = avg_pred[:, i]

    output_csv = Path(args.output_csv) if args.output_csv else Path(args.model_dir) / "test_ensemble_preds.csv"
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(output_csv, index=False)

    save_json(
        Path(args.model_dir) / "ensemble_summary.json",
        {
            "mode": mode,
            "targets": targets,
            "num_rows": int(len(out_df)),
            "valid_embeddings": int(valid.sum()),
            "folds": fold_info,
            "output_csv": str(output_csv),
        },
    )
    print(f"Saved ensemble predictions to: {output_csv}")


if __name__ == "__main__":
    main()
