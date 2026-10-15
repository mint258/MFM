#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

from phychem_mfm.discovery.registry import ExperimentRegistry
from scripts.frozen_h0_probe import (
    build_expansion_cache,
    build_qm7_cache,
    build_qm9_cache,
    cache_lock,
    load_frozen_model,
)


PROTOCOL = "node_adapt_mixture_pool_v3.1"
HISTORICAL_EXPANSIONRX_TASK_WEIGHTS = np.asarray(
    [1.018, 1.000, 1.364, 1.134, 2.377, 2.373, 3.939, 5.259, 23.099],
    dtype=np.float32,
)


def parse_args():
    parser = argparse.ArgumentParser("Frozen H0 -> node adapter -> mean/max/std pooling -> downstream predictor")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--panel", choices=("expansionrx", "qm7", "qm9"), required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expansion-root", default="/share/home/zixiao/descriptor_analysis/data/OpenADMET_ExpansionRx_MLQSAR_paper_reproduction")
    parser.add_argument("--qm9-root", default="/share/home/zixiao/dataset/qm9")
    parser.add_argument("--qm7-root", default="/share/home/zixiao/dataset/qm7")
    parser.add_argument("--hidden-dim", type=int, default=1024)
    parser.add_argument("--atom-layers", type=int, default=2)
    parser.add_argument("--head-layers", type=int, default=2)
    parser.add_argument("--dropout", type=float, default=0.10)
    parser.add_argument("--lr", type=float, default=5e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--epochs", type=int, default=400)
    parser.add_argument("--patience", type=int, default=40)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--encoder-batch-size", type=int, default=96)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-atoms", type=int, default=196)
    parser.add_argument("--registry", default="registry/discovery_registry.json")
    parser.add_argument("--wandb-project", default="phychem-mfm-iclr2027-discovery")
    parser.add_argument("--wandb-mode", choices=("online", "offline", "disabled"), default="offline")
    parser.add_argument("--device", default="cuda")
    return parser.parse_args()


class NodeAdaptMixturePool(nn.Module):
    """Historical late atom adaptation with the v3-frozen mean/max/std readout."""

    def __init__(self, in_dim, out_dim, hidden_dim, atom_layers, head_layers, dropout):
        super().__init__()
        atom_modules = []
        current = int(in_dim)
        for _ in range(int(atom_layers)):
            atom_modules.extend([nn.Linear(current, hidden_dim), nn.ReLU(), nn.Dropout(dropout)])
            current = hidden_dim
        self.node_adapter = nn.Sequential(*atom_modules)
        readout = []
        current = hidden_dim * 3
        for _ in range(max(0, int(head_layers) - 1)):
            readout.extend([nn.Linear(current, hidden_dim), nn.ReLU(), nn.Dropout(dropout)])
            current = hidden_dim
        readout.append(nn.Linear(current, out_dim))
        self.predictor = nn.Sequential(*readout)

    def forward(self, nodes, mask):
        adapted = self.node_adapter(nodes)
        valid = mask.unsqueeze(-1)
        denominator = valid.sum(1).clamp_min(1)
        mean = (adapted * valid).sum(1) / denominator
        maximum = adapted.masked_fill(~valid, torch.finfo(adapted.dtype).min).max(1).values
        maximum = torch.where(torch.isfinite(maximum), maximum, torch.zeros_like(maximum))
        variance = ((adapted - mean.unsqueeze(1)).square() * valid).sum(1) / denominator
        std = torch.sqrt(variance.clamp_min(1e-12))
        return self.predictor(torch.cat((mean, maximum, std), dim=-1))


@torch.no_grad()
def encode_nodes(model, graphs, device, batch_size):
    from torch_geometric.loader import DataLoader

    result = []
    for batch in DataLoader(graphs, batch_size=batch_size, shuffle=False):
        batch = batch.to(device)
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
            atoms = model.encode_atoms(batch)
        ptr = batch.ptr.detach().cpu().tolist()
        atoms = atoms.float().cpu()
        result.extend(atoms[ptr[index]:ptr[index + 1]].contiguous() for index in range(len(ptr) - 1))
    return result


def padded_batch(features, indices, targets, device):
    selected = [features[int(index)] for index in indices]
    nmax = max(item.size(0) for item in selected)
    dim = selected[0].size(1)
    nodes = torch.zeros((len(selected), nmax, dim), device=device)
    mask = torch.zeros((len(selected), nmax), device=device, dtype=torch.bool)
    for row, item in enumerate(selected):
        nodes[row, :item.size(0)] = item.to(device)
        mask[row, :item.size(0)] = True
    return nodes, mask, torch.as_tensor(targets[indices], device=device, dtype=torch.float32)


def train_panel(features, targets, target_names, split_ids, *, label_fraction, args, device):
    rng = np.random.default_rng(args.seed + round(label_fraction * 1000))
    split_ids = np.asarray(split_ids)
    train_pool = np.flatnonzero(split_ids == "train")
    test_indices = np.flatnonzero(split_ids == "test")
    if label_fraction < 1.0:
        keep = max(32, round(len(train_pool) * label_fraction))
        train_pool = np.sort(rng.choice(train_pool, min(keep, len(train_pool)), replace=False))
    shuffled = rng.permutation(train_pool)
    val_count = max(16, round(len(shuffled) * 0.10))
    validation_indices = np.sort(shuffled[:val_count])
    train_indices = np.sort(shuffled[val_count:])
    target_mean = np.nanmean(targets[train_indices], axis=0)
    target_std = np.nanstd(targets[train_indices], axis=0)
    target_std = np.where(np.isfinite(target_std) & (target_std > 1e-12), target_std, 1.0)
    normalized = (targets - target_mean) / target_std
    task_weights = (
        HISTORICAL_EXPANSIONRX_TASK_WEIGHTS
        if args.panel == "expansionrx" and targets.shape[1] == len(HISTORICAL_EXPANSIONRX_TASK_WEIGHTS)
        else np.ones(targets.shape[1], dtype=np.float32)
    )
    task_weights_tensor = torch.as_tensor(task_weights, device=device)

    torch.manual_seed(args.seed)
    model = NodeAdaptMixturePool(
        features[0].size(1), targets.shape[1], args.hidden_dim, args.atom_layers,
        args.head_layers, args.dropout,
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=args.weight_decay)
    best_state = None
    best_value = math.inf
    epochs_without_improvement = 0
    history = []
    for epoch in range(1, args.epochs + 1):
        model.train()
        order = rng.permutation(train_indices)
        losses = []
        for start in range(0, len(order), args.batch_size):
            indices = order[start:start + args.batch_size]
            nodes, mask, target = padded_batch(features, indices, normalized, device)
            valid = torch.isfinite(target)
            prediction = model(nodes, mask)
            if not valid.any():
                continue
            valid_weights = valid.float() * task_weights_tensor.unsqueeze(0)
            residual = torch.where(valid, prediction - target, torch.zeros_like(prediction))
            loss = (residual.square() * valid_weights).sum() / valid_weights.sum().clamp_min(1.0)
            optimizer.zero_grad(set_to_none=True); loss.backward()
            optimizer.step(); losses.append(float(loss.detach()))
        validation = evaluate_indices(model, features, normalized, validation_indices, args.batch_size, device)
        validation_target = normalized[validation_indices]
        validation_mask = np.isfinite(validation_target)
        validation_weights = validation_mask * task_weights[None, :]
        validation_mse = float(
            (np.where(validation_mask, validation - validation_target, 0.0) ** 2 * validation_weights).sum()
            / max(1.0, validation_weights.sum())
        )
        history.append({"epoch": epoch, "train_loss": float(np.mean(losses)), "validation_weighted_mse": validation_mse})
        if validation_mse < best_value:
            best_value = validation_mse
            best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}
            epochs_without_improvement = 0
        else:
            epochs_without_improvement += 1
            if epochs_without_improvement >= args.patience:
                break
    model.load_state_dict(best_state)
    normalized_prediction = evaluate_indices(model, features, normalized, test_indices, args.batch_size, device)
    prediction = normalized_prediction * target_std + target_mean
    per_target = {}
    normalized_maes = []
    for target_index in range(targets.shape[1]):
        valid = np.isfinite(targets[test_indices, target_index]) & np.isfinite(prediction[:, target_index])
        if not valid.any():
            continue
        absolute = np.abs(prediction[valid, target_index] - targets[test_indices[valid], target_index])
        mae = float(absolute.mean())
        normalized_mae = mae / float(target_std[target_index])
        normalized_maes.append(normalized_mae)
        per_target[str(target_names[target_index])] = {
            "mae": mae, "normalized_mae": normalized_mae, "test_labels": int(valid.sum())
        }
    return {
        "macro_normalized_mae": float(np.mean(normalized_maes)),
        "per_target": per_target,
        "train_rows": int(len(train_indices)), "inner_validation_rows": int(len(validation_indices)),
        "test_rows": int(len(test_indices)), "best_validation_weighted_mse": best_value,
        "trained_epochs": len(history), "history": history,
        "target_scaling": {"mean": target_mean.tolist(), "std": target_std.tolist(), "fit_on": "train_only"},
        "task_weights": task_weights.tolist(),
    }


@torch.no_grad()
def evaluate_indices(model, features, targets, indices, batch_size, device):
    model.eval(); rows = []
    for start in range(0, len(indices), batch_size):
        selected = indices[start:start + batch_size]
        nodes, mask, _ = padded_batch(features, selected, targets, device)
        rows.append(model(nodes, mask).cpu().numpy())
    return np.concatenate(rows)


def main():
    args = parse_args()
    device = torch.device(args.device if torch.cuda.is_available() else "cpu")
    output_dir = Path(args.output_dir).resolve(); output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = Path(args.checkpoint).resolve()
    checkpoint_sha = hashlib.sha256(checkpoint_path.read_bytes()).hexdigest()
    graph_cache_path = output_dir.parent / "cache" / f"{args.panel}_graphs.pt"
    with cache_lock(graph_cache_path):
        if args.panel == "expansionrx":
            cache = build_expansion_cache(Path(args.expansion_root), graph_cache_path, seed=args.seed, max_atoms=args.max_atoms)
        elif args.panel == "qm7":
            cache = build_qm7_cache(Path(args.qm7_root), graph_cache_path, max_atoms=args.max_atoms)
        else:
            cache = build_qm9_cache(Path(args.qm9_root), graph_cache_path, seed=args.seed, max_atoms=args.max_atoms)
    frozen_model, checkpoint = load_frozen_model(checkpoint_path, device)
    node_cache = output_dir.parent / "cache" / f"{args.panel}_{checkpoint_sha[:16]}_h0_nodes.pt"
    if node_cache.exists():
        features = torch.load(node_cache, map_location="cpu", weights_only=False)
    else:
        features = encode_nodes(frozen_model, cache["graphs"], device, args.encoder_batch_size)
        torch.save(features, node_cache)
    full = train_panel(
        features, cache["targets"], cache["target_names"], cache["split_ids"],
        label_fraction=1.0, args=args, device=device,
    )
    result = {
        "protocol": PROTOCOL, "dataset_protocol": cache["protocol"], "panel": args.panel,
        "checkpoint": str(checkpoint_path), "checkpoint_sha256": checkpoint_sha,
        "experiment_id": checkpoint.get("discovery", {}).get("experiment_id"),
        "recipe_hash": checkpoint.get("discovery", {}).get("recipe_hash"),
        "backbone": "frozen SharedBackbone H0", "node_adapter": {
            "hidden_dim": args.hidden_dim, "layers": args.atom_layers, "activation": "ReLU", "dropout": args.dropout,
        },
        "pooling": "concat(mean(node), max(node), std(node))",
        "predictor_layers": args.head_layers, "optimizer": "AdamW", "lr": args.lr,
        "weight_decay": args.weight_decay, "early_stopping_patience": args.patience,
        "missing_labels": "finite-mask", "inner_validation": "deterministic 10% of train split",
        "full_label": full,
    }
    if args.panel == "expansionrx":
        result["low_label_20pct"] = train_panel(
            features, cache["targets"], cache["target_names"], cache["split_ids"],
            label_fraction=0.2, args=args, device=device,
        )
    result_path = output_dir / f"{args.panel}_node_adapt_mixture_pool_v3.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    if result.get("experiment_id"):
        registry = ExperimentRegistry(args.registry)
        registry.update_experiment(str(result["experiment_id"]), {
            "downstream_evaluated": True, "downstream_protocol_version": PROTOCOL,
            "downstream_results": {f"{args.panel}_v3": result},
            "result_paths": {f"{args.panel}_v3": str(result_path)},
        })
    if args.wandb_mode != "disabled":
        import wandb
        wandb_config = {
            "protocol": PROTOCOL, "panel": args.panel, "checkpoint_sha256": checkpoint_sha,
            "hidden_dim": args.hidden_dim, "atom_layers": args.atom_layers,
            "head_layers": args.head_layers, "dropout": args.dropout, "lr": args.lr,
            "weight_decay": args.weight_decay, "epochs": args.epochs, "patience": args.patience,
            "batch_size": args.batch_size, "seed": args.seed,
        }
        run = wandb.init(project=args.wandb_project, mode=args.wandb_mode, dir=str(output_dir),
                         name=f"v3-mixture-{args.panel}-{checkpoint_sha[:10]}", config=wandb_config,
                         tags=["iclr2027", "v3", "node-adapt", "mean-max-std", args.panel])
        metrics = {"probe/full_macro_normalized_mae": full["macro_normalized_mae"]}
        if "low_label_20pct" in result:
            metrics["probe/low20_macro_normalized_mae"] = result["low_label_20pct"]["macro_normalized_mae"]
        run.log(metrics); run.finish()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
