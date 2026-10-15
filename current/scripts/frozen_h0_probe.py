#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.preprocessing import StandardScaler
from torch_geometric.data import Data
from torch_geometric.loader import DataLoader

from phychem_mfm.discovery.engine import file_sha256
from phychem_mfm.discovery.registry import ExperimentRegistry
from phychem_mfm.factory import build_model


def parse_args():
    parser = argparse.ArgumentParser("Frozen-H0 transfer screening")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--panel", choices=("expansionrx", "qm7", "qm9"), required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expansion-root", default="/share/home/zixiao/descriptor_analysis/data/OpenADMET_ExpansionRx_MLQSAR_paper_reproduction")
    parser.add_argument("--qm9-root", default="/share/home/zixiao/dataset/qm9")
    parser.add_argument("--qm7-root", default="/share/home/zixiao/dataset/qm7")
    parser.add_argument("--batch-size", type=int, default=96)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--max-atoms", type=int, default=196)
    parser.add_argument("--wandb-project", default="phychem-mfm-iclr2027-discovery")
    parser.add_argument("--wandb-mode", choices=("online", "offline", "disabled"), default="offline")
    parser.add_argument("--registry", default="registry/discovery_registry.json")
    return parser.parse_args()


@contextmanager
def cache_lock(path: Path):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as handle:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            handle.write(b"0")
            handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def load_frozen_model(checkpoint: str | Path, device: torch.device):
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    model_config = dict(payload["model_config"])
    config = {
        "architecture": {"task_route_per_task": dict(payload["task_route_per_task"])},
        "backbone": dict(model_config["backbone_config"]),
        "expert": dict(model_config["expert_config"]),
        "head": dict(model_config["head_config"]),
    }
    model = build_model(config)
    model.load_state_dict(payload["model_state"], strict=True)
    model.to(device).eval()
    for parameter in model.parameters():
        parameter.requires_grad = False
    return model, payload


def smiles_to_graph(smiles: str, *, seed: int, max_atoms: int) -> Data | None:
    from rdkit import Chem
    from rdkit.Chem import AllChem

    molecule = Chem.MolFromSmiles(str(smiles))
    if molecule is None:
        return None
    molecule = Chem.AddHs(molecule)
    if molecule.GetNumAtoms() > max_atoms:
        return None
    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed & 0x7FFFFFFF)
    params.useRandomCoords = True
    if AllChem.EmbedMolecule(molecule, params) != 0:
        return None
    try:
        AllChem.MMFFOptimizeMolecule(molecule, maxIters=100)
    except Exception:
        pass
    conformer = molecule.GetConformer()
    coordinates = np.asarray(conformer.GetPositions(), dtype=np.float32)
    atomic_numbers = np.asarray([atom.GetAtomicNum() for atom in molecule.GetAtoms()], dtype=np.int64)
    return Data(x=torch.from_numpy(atomic_numbers).view(-1, 1), pos=torch.from_numpy(coordinates))


def _stable_seed(text: str, base_seed: int) -> int:
    digest = hashlib.sha256(f"{base_seed}|{text}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def build_expansion_cache(root: Path, cache_path: Path, *, seed: int, max_atoms: int):
    if cache_path.exists():
        return torch.load(cache_path, map_location="cpu", weights_only=False)
    frames = {}
    graphs = []
    split_ids = []
    row_ids = []
    targets = []
    target_names = None
    for split_name, filename in (("train", "fold_1/train.csv"), ("test", "fold_1/test.csv")):
        frame = pd.read_csv(root / filename)
        frames[split_name] = frame
        if target_names is None:
            target_names = [column for column in frame.columns if column not in {"SMILES", "Molecule Name"}]
        for row_index, row in frame.iterrows():
            smiles = str(row["SMILES"])
            graph = smiles_to_graph(smiles, seed=_stable_seed(smiles, seed), max_atoms=max_atoms)
            if graph is None:
                continue
            graphs.append(graph)
            split_ids.append(split_name)
            row_ids.append(int(row_index))
            targets.append([float(row[name]) if pd.notna(row[name]) else np.nan for name in target_names])
    payload = {
        "protocol": "ExpansionRx_fold1_ETKDGv3_MMFF_one_conformer_v1",
        "graphs": graphs,
        "split_ids": split_ids,
        "row_ids": row_ids,
        "targets": np.asarray(targets, dtype=np.float32),
        "target_names": target_names,
        "source_files": {
            name: {"path": str(root / filename), "size": (root / filename).stat().st_size}
            for name, filename in (("train", "fold_1/train.csv"), ("test", "fold_1/test.csv"))
        },
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, cache_path)
    return payload


def build_qm9_cache(root: Path, cache_path: Path, *, seed: int, max_atoms: int):
    if cache_path.exists():
        return torch.load(cache_path, map_location="cpu", weights_only=False)
    from torch_geometric.datasets import QM9

    dataset = QM9(str(root))
    rng = np.random.default_rng(seed)
    candidates = rng.permutation(len(dataset))
    graphs = []
    targets = []
    source_indices = []
    for index in candidates:
        item = dataset[int(index)]
        if int(item.z.numel()) > max_atoms:
            continue
        graphs.append(Data(x=item.z.long().view(-1, 1), pos=item.pos.float()))
        targets.append(item.y.view(-1).float().numpy())
        source_indices.append(int(index))
        if len(graphs) >= 12000:
            break
    if len(graphs) < 12000:
        raise RuntimeError(f"QM9 screening protocol requires 12000 valid molecules, found {len(graphs)}")
    payload = {
        "protocol": "QM9_fixed_seed0_10k_train_2k_test_v1",
        "graphs": graphs,
        "split_ids": ["train"] * 10000 + ["test"] * 2000,
        "row_ids": source_indices,
        "targets": np.asarray(targets, dtype=np.float32),
        "target_names": [f"qm9_target_{index}" for index in range(np.asarray(targets).shape[1])],
        "source_root": str(root.resolve()),
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, cache_path)
    return payload


def build_qm7_cache(root: Path, cache_path: Path, *, max_atoms: int):
    if cache_path.exists():
        return torch.load(cache_path, map_location="cpu", weights_only=False)
    from scipy.io import loadmat
    from urllib.request import urlretrieve

    root.mkdir(parents=True, exist_ok=True)
    source_path = root / "qm7.mat"
    source_url = "https://deepchemdata.s3-us-west-1.amazonaws.com/datasets/qm7.mat"
    if not source_path.exists():
        temporary = source_path.with_suffix(".mat.tmp")
        urlretrieve(source_url, temporary)
        os.replace(temporary, source_path)
    payload_mat = loadmat(source_path)
    required = {"T", "Z", "R", "P"}
    if not required.issubset(payload_mat):
        raise RuntimeError(f"QM7 mat file is missing keys: {sorted(required.difference(payload_mat))}")
    z_values = np.asarray(payload_mat["Z"])
    coordinates = np.asarray(payload_mat["R"])
    targets = np.asarray(payload_mat["T"], dtype=np.float32).reshape(-1, 1)
    folds = np.asarray(payload_mat["P"], dtype=np.int64)
    test_indices = set(int(value) for value in folds[0].reshape(-1))
    graphs = []
    split_ids = []
    row_ids = []
    selected_targets = []
    for index in range(len(z_values)):
        atoms = np.asarray(z_values[index]).reshape(-1)
        mask = atoms > 0
        if int(mask.sum()) == 0 or int(mask.sum()) > max_atoms:
            continue
        graphs.append(
            Data(
                x=torch.from_numpy(atoms[mask].astype(np.int64)).view(-1, 1),
                pos=torch.from_numpy(np.asarray(coordinates[index][mask], dtype=np.float32)),
            )
        )
        split_ids.append("test" if index in test_indices else "train")
        row_ids.append(index)
        selected_targets.append(targets[index])
    source_digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
    payload = {
        "protocol": "QM7_official_fold0_test_v1",
        "graphs": graphs,
        "split_ids": split_ids,
        "row_ids": row_ids,
        "targets": np.asarray(selected_targets, dtype=np.float32),
        "target_names": ["atomization_energy_kcal_per_mol"],
        "source_path": str(source_path.resolve()),
        "source_url": source_url,
        "source_sha256": source_digest,
    }
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, cache_path)
    return payload


@torch.no_grad()
def encode_graphs(model, graphs, *, device: torch.device, batch_size: int) -> np.ndarray:
    rows = []
    for batch in DataLoader(graphs, batch_size=batch_size, shuffle=False):
        batch = batch.to(device)
        with torch.autocast(device_type=device.type, dtype=torch.bfloat16, enabled=device.type == "cuda"):
            representation = model.encode_graph(batch, pooling="mean")
        rows.append(representation.float().cpu().numpy())
    return np.concatenate(rows, axis=0)


def ridge_panel(features, targets, split_ids, target_names, *, label_fraction: float, seed: int):
    split_ids = np.asarray(split_ids)
    train_pool = np.flatnonzero(split_ids == "train")
    test_pool = np.flatnonzero(split_ids == "test")
    per_target = {}
    normalized_maes = []
    for target_index, target_name in enumerate(target_names):
        train_indices = train_pool[np.isfinite(targets[train_pool, target_index])]
        test_indices = test_pool[np.isfinite(targets[test_pool, target_index])]
        if label_fraction < 1.0:
            rng = np.random.default_rng(seed + target_index * 7919)
            keep = max(16, round(len(train_indices) * label_fraction))
            train_indices = np.sort(rng.choice(train_indices, size=min(keep, len(train_indices)), replace=False))
        if len(train_indices) < 16 or len(test_indices) < 8:
            continue
        scaler = StandardScaler().fit(features[train_indices])
        estimator = Ridge(alpha=1.0).fit(scaler.transform(features[train_indices]), targets[train_indices, target_index])
        prediction = estimator.predict(scaler.transform(features[test_indices]))
        mae = float(mean_absolute_error(targets[test_indices, target_index], prediction))
        target_std = float(np.std(targets[train_indices, target_index]))
        normalized_mae = mae / max(target_std, 1e-12)
        normalized_maes.append(normalized_mae)
        per_target[target_name] = {
            "mae": mae,
            "normalized_mae": normalized_mae,
            "train_labels": int(len(train_indices)),
            "test_labels": int(len(test_indices)),
        }
    if not normalized_maes:
        raise RuntimeError("No downstream targets had enough labels for the frozen probe")
    return {"macro_normalized_mae": float(np.mean(normalized_maes)), "per_target": per_target}


def main():
    args = parse_args()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_hash = file_sha256(args.checkpoint)
    if args.panel == "expansionrx":
        graph_cache_path = output_dir.parent / "cache" / "expansionrx_fold1_graphs.pt"
        with cache_lock(graph_cache_path):
            cache = build_expansion_cache(
                Path(args.expansion_root),
                graph_cache_path,
                seed=args.seed,
                max_atoms=args.max_atoms,
            )
    elif args.panel == "qm9":
        graph_cache_path = output_dir.parent / "cache" / "qm9_12k_graphs.pt"
        with cache_lock(graph_cache_path):
            cache = build_qm9_cache(
                Path(args.qm9_root),
                graph_cache_path,
                seed=args.seed,
                max_atoms=args.max_atoms,
            )
    else:
        graph_cache_path = output_dir.parent / "cache" / "qm7_graphs.pt"
        with cache_lock(graph_cache_path):
            cache = build_qm7_cache(
                Path(args.qm7_root),
                graph_cache_path,
                max_atoms=args.max_atoms,
            )
    model, checkpoint = load_frozen_model(args.checkpoint, device)
    representation_cache = output_dir.parent / "cache" / f"{args.panel}_{checkpoint_hash[:16]}_h0.npy"
    if representation_cache.exists():
        features = np.load(representation_cache)
    else:
        features = encode_graphs(model, cache["graphs"], device=device, batch_size=args.batch_size)
        np.save(representation_cache, features)
    full = ridge_panel(
        features,
        cache["targets"],
        cache["split_ids"],
        cache["target_names"],
        label_fraction=1.0,
        seed=args.seed,
    )
    result = {
        "protocol": cache["protocol"],
        "panel": args.panel,
        "checkpoint": str(Path(args.checkpoint).resolve()),
        "checkpoint_sha256": checkpoint_hash,
        "experiment_id": checkpoint.get("discovery", {}).get("experiment_id"),
        "recipe_hash": checkpoint.get("discovery", {}).get("recipe_hash"),
        "frozen_h0": True,
        "pooling": "mean",
        "probe": "StandardScaler + Ridge(alpha=1.0)",
        "full_label": full,
        "encoded_graph_count": int(features.shape[0]),
        "representation_dim": int(features.shape[1]),
    }
    if args.panel == "expansionrx":
        result["low_label_20pct"] = ridge_panel(
            features,
            cache["targets"],
            cache["split_ids"],
            cache["target_names"],
            label_fraction=0.2,
            seed=args.seed,
        )
    result_path = output_dir / f"{args.panel}_frozen_h0.json"
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    experiment_id = result.get("experiment_id")
    if experiment_id:
        registry = ExperimentRegistry(args.registry)
        registry.update_experiment(
            str(experiment_id),
            {
                "downstream_evaluated": True,
                "downstream_results": {args.panel: result},
                "result_paths": {f"frozen_h0_{args.panel}": str(result_path)},
            },
        )
    if args.wandb_mode != "disabled":
        import wandb

        run = wandb.init(
            project=args.wandb_project,
            name=f"frozen-h0-{args.panel}-{checkpoint_hash[:10]}",
            mode=args.wandb_mode,
            dir=str(output_dir),
            config={key: value for key, value in result.items() if key not in {"full_label", "low_label_20pct"}},
            tags=["iclr2027", "frozen-h0", args.panel],
        )
        metrics = {"probe/full_macro_normalized_mae": full["macro_normalized_mae"]}
        if "low_label_20pct" in result:
            metrics["probe/low20_macro_normalized_mae"] = result["low_label_20pct"]["macro_normalized_mae"]
        run.log(metrics)
        run.finish()
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
