"""Phase-1 evaluation for official CheMeleon message-passing weights.

This script compares frozen CheMeleon representations against full Mordred2D
descriptors on local benchmark splits. It intentionally keeps the downstream
probe simple and explicit:

- regression: Ridge, optional MLP/RF when linear performance is weak
- classification: LogisticRegression, optional MLP/RF when linear performance is weak

Outputs are written under ``results/phase1_chemeleon_official``.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import time
from typing import Any

from joblib import Parallel, delayed
import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Chem.Scaffolds import MurckoScaffold
from rdkit import RDLogger
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.exceptions import ConvergenceWarning
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier, MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
import torch
import warnings

from chemprop.cli.utils.parsing import make_dataset
from chemprop.data import LazyMoleculeDatapoint, build_dataloader
from chemprop.nn.agg import MeanAggregation
from chemprop.nn.message_passing import BondMessagePassing

from mordred import Calculator, descriptors


RDLogger.DisableLog("rdApp.warning")
warnings.filterwarnings("ignore", category=ConvergenceWarning)


OPENADMET_TASKS = [
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


MOLECULENET_TASKS = {
    "esol": {
        "path": "data/MoleculeNet/esol.csv",
        "smiles": "smiles",
        "targets": ["measured log solubility in mols per litre"],
        "task_type": "regression",
    },
    "freesolv": {
        "path": "data/MoleculeNet/freesolv.csv",
        "smiles": "smiles",
        "targets": ["expt"],
        "task_type": "regression",
    },
    "lipophilicity": {
        "path": "data/MoleculeNet/lipophilicity.csv",
        "smiles": "smiles",
        "targets": ["exp"],
        "task_type": "regression",
    },
    "bbbp": {
        "path": "data/MoleculeNet/bbbp.csv",
        "smiles": "smiles",
        "targets": ["p_np"],
        "task_type": "classification",
    },
    "bace": {
        "path": "data/MoleculeNet/bace.csv",
        "smiles": "mol",
        "targets": ["Class"],
        "task_type": "classification",
    },
    "clintox": {
        "path": "data/MoleculeNet/clintox.csv.gz",
        "smiles": "smiles",
        "targets": ["FDA_APPROVED", "CT_TOX"],
        "task_type": "classification",
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonicalize_smiles(smiles: str) -> str | None:
    if not isinstance(smiles, str) or not smiles.strip():
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol, canonical=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_or_compute_chemeleon_features(
    smiles: list[str], ckpt_path: Path, cache_dir: Path, batch_size: int, num_workers: int
) -> tuple[np.ndarray, dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    smiles_hash = hashlib.sha256("\n".join(smiles).encode("utf-8")).hexdigest()[:16]
    cache_path = cache_dir / f"chemeleon_mp_{smiles_hash}.npz"
    meta_path = cache_dir / f"chemeleon_mp_{smiles_hash}.json"
    if cache_path.exists() and meta_path.exists():
        arr = np.load(cache_path)["X"]
        return arr, json.loads(meta_path.read_text(encoding="utf-8"))

    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    mp = BondMessagePassing(**ckpt["hyper_parameters"])
    mp.load_state_dict(ckpt["state_dict"])
    mp.eval()
    agg = MeanAggregation()

    data = [
        LazyMoleculeDatapoint(smi, y=np.array([np.nan], dtype=float), name=smi)
        for smi in smiles
    ]
    dset = make_dataset(
        data,
        reaction_mode="REAC_DIFF",
        multi_hot_atom_featurizer_mode="V2",
        cuikmolmaker_featurization=False,
        n_workers=num_workers,
    )
    loader = build_dataloader(
        dset, batch_size=batch_size, num_workers=num_workers, shuffle=False, drop_last=False
    )

    features = []
    with torch.no_grad():
        for batch in loader:
            h_v = mp(batch.bmg, batch.V_d)
            h = agg(h_v, batch.bmg.batch)
            features.append(h.cpu().numpy())
    X = np.vstack(features).astype(np.float32)
    meta = {
        "kind": "chemeleon_official_message_passing_mean_aggregation",
        "source_checkpoint": str(ckpt_path),
        "checkpoint_sha256": sha256_file(ckpt_path),
        "feature_dim": int(X.shape[1]),
        "n_smiles": len(smiles),
        "chemprop_atom_featurizer": "V2",
        "aggregation": "mean",
        "hyper_parameters": {
            k: (v if isinstance(v, (str, int, float, bool, type(None))) else str(v))
            for k, v in ckpt["hyper_parameters"].items()
        },
    }
    np.savez_compressed(cache_path, X=X)
    write_json(meta_path, meta)
    return X, meta


def load_or_compute_mordred2d_features(
    smiles: list[str], cache_dir: Path, batch_size: int, nproc: int
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    smiles_hash = hashlib.sha256("\n".join(smiles).encode("utf-8")).hexdigest()[:16]
    cache_path = cache_dir / f"mordred2d_{smiles_hash}.npz"
    meta_path = cache_dir / f"mordred2d_{smiles_hash}.json"
    if cache_path.exists() and meta_path.exists():
        loaded = np.load(cache_path, allow_pickle=True)
        return loaded["X"], loaded["feature_names"].tolist(), json.loads(
            meta_path.read_text(encoding="utf-8")
        )

    calc = Calculator(descriptors, ignore_3D=True)
    feature_names = [str(d) for d in calc.descriptors]
    rows = []
    for start in range(0, len(smiles), batch_size):
        chunk = smiles[start : start + batch_size]
        mols = [Chem.MolFromSmiles(smi) for smi in chunk]
        df = calc.pandas(mols, nproc=nproc, quiet=True)
        df = df.apply(pd.to_numeric, errors="coerce")
        rows.append(df.to_numpy(dtype=np.float64))
    X = np.vstack(rows)
    meta = {
        "kind": "mordred2d_full",
        "package": "mordredcommunity",
        "ignore_3D": True,
        "feature_dim": int(X.shape[1]),
        "n_smiles": len(smiles),
        "descriptor_count": len(feature_names),
        "nproc": nproc,
        "matches_expected_chemeleon_label_count": len(feature_names) == 1613,
        "note": (
            "CheMeleon/Chemprop uses the official chemeleon_mp.pt message-passing weights; "
            "full Mordred2D is computed with mordredcommunity Calculator(descriptors, ignore_3D=True)."
        ),
    }
    np.savez_compressed(cache_path, X=X, feature_names=np.array(feature_names, dtype=object))
    write_json(meta_path, meta)
    return X, feature_names, meta


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    rmse = math.sqrt(mean_squared_error(y_true, y_pred))
    return {
        "rmse": rmse,
        "mae": mean_absolute_error(y_true, y_pred),
        "r2": r2_score(y_true, y_pred) if len(np.unique(y_true)) > 1 else float("nan"),
    }


def classification_metrics(y_true: np.ndarray, y_score: np.ndarray) -> dict[str, float]:
    y_pred = (y_score >= 0.5).astype(int)
    out = {"accuracy": accuracy_score(y_true, y_pred)}
    if len(np.unique(y_true)) == 2:
        out["roc_auc"] = roc_auc_score(y_true, y_score)
        out["pr_auc"] = average_precision_score(y_true, y_score)
    else:
        out["roc_auc"] = float("nan")
        out["pr_auc"] = float("nan")
    return out


def make_preprocess() -> Pipeline:
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
            ("variance", VarianceThreshold(threshold=0.0)),
            ("scale", StandardScaler()),
        ]
    )


def finite_feature_matrix(X: np.ndarray) -> np.ndarray:
    X = np.asarray(X, dtype=np.float64)
    X = np.where(np.isfinite(X), X, np.nan)
    return X


def fit_regression_probe(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    seed: int,
    advanced: bool,
    linear_r2_threshold: float,
    model_n_jobs: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    alphas = [1e-4, 1e-3, 1e-2, 1e-1, 1, 10, 100]
    idx = np.arange(len(y_train))
    if len(y_train) >= 20:
        train_idx, val_idx = train_test_split(idx, test_size=0.15, random_state=seed)
    else:
        train_idx, val_idx = idx, idx

    best_alpha = None
    best_rmse = float("inf")
    for alpha in alphas:
        prep = make_preprocess()
        x_tr = prep.fit_transform(X_train[train_idx])
        x_val = prep.transform(X_train[val_idx])
        model = Ridge(alpha=alpha, random_state=seed)
        model.fit(x_tr, y_train[train_idx])
        pred = model.predict(x_val)
        rmse = math.sqrt(mean_squared_error(y_train[val_idx], pred))
        if rmse < best_rmse:
            best_rmse = rmse
            best_alpha = alpha

    prep = make_preprocess()
    x_tr_all = prep.fit_transform(X_train)
    x_te = prep.transform(X_test)
    model = Ridge(alpha=best_alpha, random_state=seed)
    model.fit(x_tr_all, y_train)
    pred = model.predict(x_te)
    metrics = regression_metrics(y_test, pred)
    results.append(
        {
            "probe_model": "ridge",
            "best_param": f"alpha={best_alpha}",
            "val_rmse": best_rmse,
            **metrics,
        }
    )

    if advanced and (not np.isfinite(metrics["r2"]) or metrics["r2"] < linear_r2_threshold):
        rf = RandomForestRegressor(
            n_estimators=200,
            max_features="sqrt",
            min_samples_leaf=2,
            random_state=seed,
            n_jobs=model_n_jobs,
        )
        rf.fit(x_tr_all, y_train)
        results.append(
            {
                "probe_model": "random_forest",
                "best_param": "n_estimators=200,max_features=sqrt,min_samples_leaf=2",
                "val_rmse": float("nan"),
                **regression_metrics(y_test, rf.predict(x_te)),
            }
        )

        mlp = MLPRegressor(
            hidden_layer_sizes=(256,),
            alpha=1e-3,
            learning_rate_init=1e-3,
            max_iter=500,
            early_stopping=True,
            random_state=seed,
        )
        mlp.fit(x_tr_all, y_train)
        results.append(
            {
                "probe_model": "mlp",
                "best_param": "hidden=(256,),alpha=1e-3,early_stopping=True",
                "val_rmse": float("nan"),
                **regression_metrics(y_test, mlp.predict(x_te)),
            }
        )

    return results


def fit_classification_probe(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    seed: int,
    advanced: bool,
    linear_auc_threshold: float,
    model_n_jobs: int,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    Cs = [1e-3, 1e-2, 1e-1, 1, 10, 100]
    idx = np.arange(len(y_train))
    stratify = y_train if min(np.bincount(y_train.astype(int))) >= 2 else None
    if len(y_train) >= 30 and stratify is not None:
        train_idx, val_idx = train_test_split(
            idx, test_size=0.15, random_state=seed, stratify=stratify
        )
    else:
        train_idx, val_idx = idx, idx

    best_C = None
    best_auc = -float("inf")
    for C in Cs:
        prep = make_preprocess()
        x_tr = prep.fit_transform(X_train[train_idx])
        x_val = prep.transform(X_train[val_idx])
        model = LogisticRegression(C=C, max_iter=2000, class_weight="balanced", random_state=seed)
        model.fit(x_tr, y_train[train_idx])
        score = model.predict_proba(x_val)[:, 1]
        auc = roc_auc_score(y_train[val_idx], score) if len(np.unique(y_train[val_idx])) == 2 else 0
        if auc > best_auc:
            best_auc = auc
            best_C = C

    prep = make_preprocess()
    x_tr_all = prep.fit_transform(X_train)
    x_te = prep.transform(X_test)
    model = LogisticRegression(C=best_C, max_iter=2000, class_weight="balanced", random_state=seed)
    model.fit(x_tr_all, y_train)
    score = model.predict_proba(x_te)[:, 1]
    metrics = classification_metrics(y_test, score)
    results.append(
        {
            "probe_model": "logistic_regression",
            "best_param": f"C={best_C}",
            "val_roc_auc": best_auc,
            **metrics,
        }
    )

    if advanced and (
        not np.isfinite(metrics.get("roc_auc", float("nan")))
        or metrics.get("roc_auc", 0.0) < linear_auc_threshold
    ):
        rf = RandomForestClassifier(
            n_estimators=300,
            max_features="sqrt",
            min_samples_leaf=2,
            class_weight="balanced",
            random_state=seed,
            n_jobs=model_n_jobs,
        )
        rf.fit(x_tr_all, y_train)
        results.append(
            {
                "probe_model": "random_forest",
                "best_param": "n_estimators=300,max_features=sqrt,min_samples_leaf=2",
                "val_roc_auc": float("nan"),
                **classification_metrics(y_test, rf.predict_proba(x_te)[:, 1]),
            }
        )

        mlp = MLPClassifier(
            hidden_layer_sizes=(256,),
            alpha=1e-3,
            learning_rate_init=1e-3,
            max_iter=500,
            early_stopping=True,
            random_state=seed,
        )
        mlp.fit(x_tr_all, y_train)
        results.append(
            {
                "probe_model": "mlp",
                "best_param": "hidden=(256,),alpha=1e-3,early_stopping=True",
                "val_roc_auc": float("nan"),
                **classification_metrics(y_test, mlp.predict_proba(x_te)[:, 1]),
            }
        )

    return results


def evaluate_split(
    dataset_name: str,
    fold: str,
    task: str,
    task_type: str,
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    smiles_col: str,
    target_col: str,
    features: dict[str, np.ndarray],
    smiles_to_index: dict[str, int],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    tr = train_df[[smiles_col, target_col]].copy()
    te = test_df[[smiles_col, target_col]].copy()
    tr["canonical_smiles"] = tr[smiles_col].map(canonicalize_smiles)
    te["canonical_smiles"] = te[smiles_col].map(canonicalize_smiles)
    tr = tr.dropna(subset=["canonical_smiles", target_col])
    te = te.dropna(subset=["canonical_smiles", target_col])
    tr = tr[tr["canonical_smiles"].isin(smiles_to_index)]
    te = te[te["canonical_smiles"].isin(smiles_to_index)]
    if len(tr) < args.min_train or len(te) < args.min_test:
        return rows

    y_train = tr[target_col].astype(float).to_numpy()
    y_test = te[target_col].astype(float).to_numpy()
    if task_type == "classification":
        y_train = y_train.astype(int)
        y_test = y_test.astype(int)
        if len(np.unique(y_train)) < 2 or len(np.unique(y_test)) < 2:
            return rows

    tr_idx = [smiles_to_index[s] for s in tr["canonical_smiles"]]
    te_idx = [smiles_to_index[s] for s in te["canonical_smiles"]]

    for feature_name, X_all in features.items():
        X_train = finite_feature_matrix(X_all[tr_idx])
        X_test = finite_feature_matrix(X_all[te_idx])
        if task_type == "regression":
            probe_rows = fit_regression_probe(
                X_train,
                y_train,
                X_test,
                y_test,
                args.seed,
                args.advanced in {"always", "auto"},
                args.linear_r2_threshold,
                args.model_n_jobs,
            )
        else:
            probe_rows = fit_classification_probe(
                X_train,
                y_train,
                X_test,
                y_test,
                args.seed,
                args.advanced in {"always", "auto"},
                args.linear_auc_threshold,
                args.model_n_jobs,
            )

        for pr in probe_rows:
            pr.update(
                {
                    "dataset": dataset_name,
                    "fold": fold,
                    "task": task,
                    "task_type": task_type,
                    "target_col": target_col,
                    "feature": feature_name,
                    "n_train": int(len(y_train)),
                    "n_test": int(len(y_test)),
                    "feature_dim_raw": int(X_all.shape[1]),
                }
            )
            rows.append(pr)
    return rows


def build_feature_bank(
    all_smiles: list[str], args: argparse.Namespace, out_dir: Path
) -> tuple[dict[str, np.ndarray], dict[str, Any], list[str]]:
    valid_smiles = []
    seen = set()
    for smi in all_smiles:
        can = canonicalize_smiles(smi)
        if can is not None and can not in seen:
            valid_smiles.append(can)
            seen.add(can)

    cache_dir = out_dir / "feature_cache"
    chemeleon_X, chemeleon_meta = load_or_compute_chemeleon_features(
        valid_smiles, args.ckpt_path, cache_dir, args.batch_size, args.num_workers
    )
    mordred_X, mordred_names, mordred_meta = load_or_compute_mordred2d_features(
        valid_smiles, cache_dir, args.mordred_batch_size, args.mordred_nproc
    )
    meta = {
        "features": {
            "chemeleon_representation": chemeleon_meta,
            "mordred2d_full": mordred_meta | {"first_features": mordred_names[:10]},
        },
        "n_unique_valid_smiles": len(valid_smiles),
    }
    return {"chemeleon_representation": chemeleon_X, "mordred2d_full": mordred_X}, meta, valid_smiles


def collect_openadmet_smiles(fold_dirs: list[Path]) -> list[str]:
    smiles: list[str] = []
    for fold_dir in fold_dirs:
        for split in ["train.csv", "test.csv"]:
            path = fold_dir / split
            if path.exists():
                smiles.extend(pd.read_csv(path)["SMILES"].dropna().astype(str).tolist())
    return smiles


def run_probe_jobs(jobs: list[dict[str, Any]], args: argparse.Namespace, label: str) -> list[dict[str, Any]]:
    if not jobs:
        return []
    if args.probe_n_jobs == 1:
        rows: list[dict[str, Any]] = []
        for job in jobs:
            rows.extend(evaluate_split(**job))
            print(f"[{label}] {job['fold']} {job['task']}: done", flush=True)
        return rows

    def _run(job: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
        rows = evaluate_split(**job)
        return rows, f"[{label}] {job['fold']} {job['task']}: done"

    if args.probe_backend == "threading":
        out = []
        with ThreadPoolExecutor(max_workers=args.probe_n_jobs) as executor:
            future_to_job = {executor.submit(_run, job): job for job in jobs}
            for future in as_completed(future_to_job):
                out.append(future.result())
    else:
        out = Parallel(n_jobs=args.probe_n_jobs, backend=args.probe_backend)(
            delayed(_run)(job) for job in jobs
        )
    rows = []
    for job_rows, message in out:
        rows.extend(job_rows)
        print(message, flush=True)
    return rows


def run_openadmet(args: argparse.Namespace, out_dir: Path) -> list[dict[str, Any]]:
    root = args.openadmet_dir
    fold_dirs = sorted(root.glob("fold_*"), key=lambda p: int(p.name.split("_")[1]))
    if args.openadmet_folds:
        wanted = {f"fold_{i}" for i in args.openadmet_folds}
        fold_dirs = [p for p in fold_dirs if p.name in wanted]
    all_smiles = collect_openadmet_smiles(fold_dirs)
    features, feature_meta, valid_smiles = build_feature_bank(all_smiles, args, out_dir / "openadmet")
    write_json(out_dir / "openadmet" / "feature_manifest.json", feature_meta)
    smiles_to_index = {s: i for i, s in enumerate(valid_smiles)}

    jobs: list[dict[str, Any]] = []
    tasks = args.openadmet_tasks or OPENADMET_TASKS
    for fold_dir in fold_dirs:
        train_df = pd.read_csv(fold_dir / "train.csv")
        test_df = pd.read_csv(fold_dir / "test.csv")
        for task in tasks:
            jobs.append(
                {
                    "dataset_name": "OpenADMET_ExpansionRx",
                    "fold": fold_dir.name,
                    "task": task,
                    "task_type": "regression",
                    "train_df": train_df,
                    "test_df": test_df,
                    "smiles_col": "SMILES",
                    "target_col": task,
                    "features": features,
                    "smiles_to_index": smiles_to_index,
                    "args": args,
                }
            )
    return run_probe_jobs(jobs, args, "OpenADMET")


def split_moleculenet(
    df: pd.DataFrame, smiles_col: str, seed: int, split: str
) -> tuple[pd.DataFrame, pd.DataFrame, str]:
    if split == "random":
        train_df, test_df = train_test_split(df, test_size=0.2, random_state=seed)
        return train_df.reset_index(drop=True), test_df.reset_index(drop=True), f"random80_20_seed{seed}"

    scaffold_to_indices: dict[str, list[int]] = {}
    for i, smi in enumerate(df[smiles_col].astype(str)):
        mol = Chem.MolFromSmiles(smi)
        scaffold = "" if mol is None else MurckoScaffold.MurckoScaffoldSmiles(mol=mol)
        scaffold_to_indices.setdefault(scaffold, []).append(i)
    rng = np.random.default_rng(seed)
    groups = list(scaffold_to_indices.values())
    rng.shuffle(groups)
    groups.sort(key=len, reverse=True)
    test_target = int(round(0.2 * len(df)))
    train_idx: list[int] = []
    test_idx: list[int] = []
    for group in groups:
        if len(test_idx) < test_target:
            test_idx.extend(group)
        else:
            train_idx.extend(group)
    train_df = df.iloc[train_idx]
    test_df = df.iloc[test_idx]
    return train_df.reset_index(drop=True), test_df.reset_index(drop=True), f"scaffold80_20_seed{seed}"


def run_moleculenet(args: argparse.Namespace, out_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    available = []
    selected = set(args.moleculenet_datasets or MOLECULENET_TASKS.keys())
    for name, cfg in MOLECULENET_TASKS.items():
        if name not in selected:
            continue
        path = Path(cfg["path"])
        if path.exists():
            available.append((name, cfg, path))
        else:
            missing.append({"dataset": name, "expected_path": str(path), "status": "missing"})

    if not available:
        return rows, missing

    all_smiles = []
    dfs = {}
    for name, cfg, path in available:
        df = pd.read_csv(path)
        dfs[name] = df
        all_smiles.extend(df[cfg["smiles"]].dropna().astype(str).tolist())
    features, feature_meta, valid_smiles = build_feature_bank(all_smiles, args, out_dir / "moleculenet")
    write_json(out_dir / "moleculenet" / "feature_manifest.json", feature_meta)
    smiles_to_index = {s: i for i, s in enumerate(valid_smiles)}

    jobs: list[dict[str, Any]] = []
    for name, cfg, path in available:
        train_df, test_df, split_name = split_moleculenet(
            dfs[name], cfg["smiles"], args.seed, args.moleculenet_split
        )
        for target in cfg["targets"]:
            if target not in dfs[name].columns:
                missing.append(
                    {
                        "dataset": name,
                        "expected_path": str(path),
                        "missing_target": target,
                        "columns": list(dfs[name].columns),
                    }
                )
                continue
            jobs.append(
                {
                    "dataset_name": f"MoleculeNet_{name}",
                    "fold": split_name,
                    "task": target,
                    "task_type": cfg["task_type"],
                    "train_df": train_df,
                    "test_df": test_df,
                    "smiles_col": cfg["smiles"],
                    "target_col": target,
                    "features": features,
                    "smiles_to_index": smiles_to_index,
                    "args": args,
                }
            )
    rows.extend(run_probe_jobs(jobs, args, "MoleculeNet"))
    return rows, missing


def summarize_results(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results
    metric = np.where(results["task_type"].eq("classification"), "roc_auc", "r2")
    tmp = results.copy()
    tmp["primary_metric"] = [
        row[m] if m in tmp.columns else np.nan for _, row, m in zip(tmp.index, tmp.to_dict("records"), metric)
    ]
    group_cols = ["dataset", "task", "feature", "probe_model"]
    numeric = [
        c
        for c in ["rmse", "mae", "r2", "roc_auc", "pr_auc", "accuracy", "primary_metric"]
        if c in tmp.columns
    ]
    return tmp.groupby(group_cols, dropna=False)[numeric].agg(["mean", "std", "count"]).reset_index()


def environment_manifest(args: argparse.Namespace) -> dict[str, Any]:
    import chemprop
    import importlib.metadata as md
    import mordred
    import rdkit
    import sklearn

    def version(name: str) -> str:
        try:
            return md.version(name)
        except Exception:
            return "unknown"

    return {
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "packages": {
            "chemprop": getattr(chemprop, "__version__", version("chemprop")),
            "torch": torch.__version__,
            "rdkit": rdkit.__version__,
            "sklearn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "mordred_module": getattr(mordred, "__version__", "unknown"),
            "mordredcommunity": version("mordredcommunity"),
        },
        "arguments": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt-path", type=Path, default=Path("ckpt/chemeleon_mp.pt"))
    parser.add_argument(
        "--openadmet-dir",
        type=Path,
        default=Path("data/OpenADMET + ExpansionRx Blind Challenge"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("results/phase1_chemeleon_official"))
    parser.add_argument("--benchmarks", nargs="+", default=["openadmet", "moleculenet"])
    parser.add_argument("--openadmet-folds", nargs="+", type=int, default=None)
    parser.add_argument("--openadmet-tasks", nargs="+", default=None)
    parser.add_argument("--moleculenet-datasets", nargs="+", default=None)
    parser.add_argument("--moleculenet-split", choices=["scaffold", "random"], default="scaffold")
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--mordred-batch-size", type=int, default=256)
    parser.add_argument("--mordred-nproc", type=int, default=1)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--probe-n-jobs", type=int, default=1)
    parser.add_argument("--probe-backend", choices=["threading", "loky"], default="threading")
    parser.add_argument("--model-n-jobs", type=int, default=1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--advanced", choices=["off", "auto", "always"], default="auto")
    parser.add_argument("--linear-r2-threshold", type=float, default=0.30)
    parser.add_argument("--linear-auc-threshold", type=float, default=0.70)
    parser.add_argument("--min-train", type=int, default=40)
    parser.add_argument("--min-test", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_json(out_dir / "environment_manifest.json", environment_manifest(args))

    all_rows: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    if "openadmet" in args.benchmarks:
        all_rows.extend(run_openadmet(args, out_dir))
    if "moleculenet" in args.benchmarks:
        ml_rows, ml_missing = run_moleculenet(args, out_dir)
        all_rows.extend(ml_rows)
        missing.extend(ml_missing)

    results = pd.DataFrame(all_rows)
    results_path = out_dir / "phase1_probe_results.csv"
    results.to_csv(results_path, index=False, quoting=csv.QUOTE_MINIMAL)

    summary = summarize_results(results)
    summary.to_csv(out_dir / "phase1_probe_summary.csv", index=False)
    write_json(out_dir / "missing_or_skipped_datasets.json", missing)
    print(f"Wrote {results_path}")
    print(f"Wrote {out_dir / 'phase1_probe_summary.csv'}")
    if missing:
        print(f"MoleculeNet missing/skipped entries: {len(missing)}")


if __name__ == "__main__":
    main()
