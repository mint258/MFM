"""Public-data approximation of the rced_nvx OpenADMET strategy.

The rank-7 rced_nvx report describes a weighted ensemble of public components:
Chemprop/CheMeleon embeddings, classical tree models, TabPFN, XGBoost,
LightGBM, ECFP/FCFP/Avalon fingerprints, RDKit/Mordred descriptors,
ADMET-AI, MiniMol and CLAMP embeddings.

The public report does not provide exact code, hyperparameters, external data
lists, trained models, or final predictions. This script therefore implements a
transparent local approximation using components available in this project:

- CheMeleon frozen embeddings
- Mordred2D
- RDKit2D
- ECFP4, FCFP4 and Avalon fingerprints
- Ridge, RandomForest, ExtraTrees and HistGradientBoosting
- Validation-MAE weighted ensemble

It is intended for local CV comparison and for producing a reproducible baseline
against the phase-1 Mordred/CheMeleon probe results.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from rdkit import Chem
from rdkit.Avalon import pyAvalonTools
from rdkit.Chem import rdFingerprintGenerator
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.feature_selection import VarianceThreshold
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from descriptastorus.descriptors import rdDescriptors

from phase1_chemeleon_official_eval import (
    OPENADMET_TASKS,
    build_feature_bank,
    canonicalize_smiles,
    load_or_compute_chemeleon_features,
    load_or_compute_mordred2d_features,
    write_json,
)


def collect_openadmet_smiles(fold_dirs: list[Path]) -> list[str]:
    smiles: list[str] = []
    for fold_dir in fold_dirs:
        for split in ["train.csv", "test.csv"]:
            path = fold_dir / split
            if path.exists():
                smiles.extend(pd.read_csv(path)["SMILES"].dropna().astype(str).tolist())
    return smiles


def smiles_hash(smiles: list[str]) -> str:
    import hashlib

    return hashlib.sha256("\n".join(smiles).encode("utf-8")).hexdigest()[:16]


def load_or_compute_rdkit2d(smiles: list[str], cache_dir: Path) -> tuple[np.ndarray, dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = smiles_hash(smiles)
    path = cache_dir / f"rdkit2d_{key}.npz"
    meta_path = cache_dir / f"rdkit2d_{key}.json"
    if path.exists() and meta_path.exists():
        return np.load(path)["X"], json.loads(meta_path.read_text(encoding="utf-8"))

    gen = rdDescriptors.RDKit2D()
    columns = [c[0] if isinstance(c, tuple) else str(c) for c in gen.GetColumns()]
    rows = []
    for smi in smiles:
        values = gen.process(smi)
        rows.append(values[1:])
    X = np.asarray(rows, dtype=np.float64)
    meta = {"kind": "rdkit2d_descriptastorus", "feature_dim": int(X.shape[1]), "columns": columns[1:]}
    np.savez_compressed(path, X=X)
    write_json(meta_path, meta)
    return X, meta


def bitvect_to_array(fp, n_bits: int) -> np.ndarray:
    arr = np.zeros((n_bits,), dtype=np.float32)
    Chem.DataStructs.ConvertToNumpyArray(fp, arr)
    return arr


def load_or_compute_fingerprints(
    smiles: list[str], cache_dir: Path, n_bits: int
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    key = smiles_hash(smiles)
    path = cache_dir / f"fingerprints_{n_bits}_{key}.npz"
    meta_path = cache_dir / f"fingerprints_{n_bits}_{key}.json"
    if path.exists() and meta_path.exists():
        loaded = np.load(path)
        return {k: loaded[k] for k in loaded.files}, json.loads(meta_path.read_text(encoding="utf-8"))

    morgan = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=n_bits)
    feature_morgan = rdFingerprintGenerator.GetMorganGenerator(
        radius=2, fpSize=n_bits, atomInvariantsGenerator=rdFingerprintGenerator.GetMorganFeatureAtomInvGen()
    )
    out = {"ecfp4": [], "fcfp4": [], "avalon": []}
    for smi in smiles:
        mol = Chem.MolFromSmiles(smi)
        out["ecfp4"].append(bitvect_to_array(morgan.GetFingerprint(mol), n_bits))
        out["fcfp4"].append(bitvect_to_array(feature_morgan.GetFingerprint(mol), n_bits))
        out["avalon"].append(bitvect_to_array(pyAvalonTools.GetAvalonFP(mol, nBits=n_bits), n_bits))
    arrays = {k: np.vstack(v).astype(np.float32) for k, v in out.items()}
    meta = {"kind": "rdkit_fingerprints", "n_bits": n_bits, "features": list(arrays)}
    np.savez_compressed(path, **arrays)
    write_json(meta_path, meta)
    return arrays, meta


def make_preprocess(scale: bool = True) -> Pipeline:
    steps = [
        ("impute", SimpleImputer(strategy="median", keep_empty_features=True)),
        ("variance", VarianceThreshold(threshold=0.0)),
    ]
    if scale:
        steps.append(("scale", StandardScaler()))
    return Pipeline(steps)


def metrics(y_true: np.ndarray, pred: np.ndarray, train_mean: float) -> dict[str, float]:
    mae = mean_absolute_error(y_true, pred)
    baseline = np.mean(np.abs(y_true - train_mean))
    return {
        "rmse": float(np.sqrt(mean_squared_error(y_true, pred))),
        "mae": float(mae),
        "rae": float(mae / baseline) if baseline > 0 else float("nan"),
        "r2": float(r2_score(y_true, pred)) if len(np.unique(y_true)) > 1 else float("nan"),
    }


def model_specs(seed: int, n_jobs: int, selected: set[str]) -> list[tuple[str, Any, bool]]:
    specs = [
        ("ridge", Ridge(alpha=10.0, random_state=seed), True),
        (
            "random_forest",
            RandomForestRegressor(
                n_estimators=300,
                max_features="sqrt",
                min_samples_leaf=2,
                random_state=seed,
                n_jobs=n_jobs,
            ),
            False,
        ),
        (
            "extra_trees",
            ExtraTreesRegressor(
                n_estimators=300,
                max_features="sqrt",
                min_samples_leaf=2,
                random_state=seed,
                n_jobs=n_jobs,
            ),
            False,
        ),
        (
            "gradient_boosting",
            GradientBoostingRegressor(
                n_estimators=300,
                learning_rate=0.05,
                max_depth=3,
                random_state=seed,
            ),
            False,
        ),
    ]
    return [spec for spec in specs if spec[0] in selected]


def fit_feature_model(
    feature_set: str,
    feature_name: str,
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    seed: int,
    model_n_jobs: int,
    selected_models: set[str],
) -> tuple[list[dict[str, Any]], np.ndarray]:
    idx = np.arange(len(y_train))
    tr_idx, val_idx = train_test_split(idx, test_size=0.15, random_state=seed)
    rows = []
    preds = []
    weights = []
    train_mean = float(np.mean(y_train))
    for model_name, model, scale in model_specs(seed, model_n_jobs, selected_models):
        prep = make_preprocess(scale=scale)
        x_tr = prep.fit_transform(X_train[tr_idx])
        x_val = prep.transform(X_train[val_idx])
        x_all = prep.fit_transform(X_train)
        x_te = prep.transform(X_test)

        model.fit(x_tr, y_train[tr_idx])
        val_pred = model.predict(x_val)
        val_mae = mean_absolute_error(y_train[val_idx], val_pred)

        model.fit(x_all, y_train)
        test_pred = model.predict(x_te)
        row = {
            "feature_set": feature_set,
            "feature": feature_name,
            "model": model_name,
            "val_mae": float(val_mae),
            **metrics(y_test, test_pred, train_mean),
        }
        rows.append(row)
        preds.append(test_pred)
        weights.append(1.0 / max(val_mae, 1e-8))

    weights_arr = np.asarray(weights, dtype=float)
    weights_arr = weights_arr / weights_arr.sum()
    ensemble_pred = np.average(np.vstack(preds), axis=0, weights=weights_arr)
    rows.append(
        {
            "feature_set": feature_set,
            "feature": feature_name,
            "model": "weighted_ensemble",
            "val_mae": float(np.average([r["val_mae"] for r in rows], weights=weights_arr)),
            **metrics(y_test, ensemble_pred, train_mean),
        }
    )
    return rows, ensemble_pred


def build_feature_sets(features: dict[str, np.ndarray], mode: str) -> dict[str, dict[str, np.ndarray]]:
    sets: dict[str, dict[str, np.ndarray]] = {}
    if mode in {"all", "chemeleon"}:
        sets["chemeleon_only"] = {"chemeleon": features["chemeleon_representation"]}
    if mode in {"all", "mordred"}:
        sets["mordred_only"] = {"mordred2d": features["mordred2d_full"]}
    if mode in {"all", "public_combo"}:
        sets["rced_public_combo"] = {
            "chemeleon": features["chemeleon_representation"],
            "mordred2d": features["mordred2d_full"],
            "rdkit2d": features["rdkit2d"],
            "ecfp4": features["ecfp4"],
            "fcfp4": features["fcfp4"],
            "avalon": features["avalon"],
        }
    return sets


def evaluate_fold_task(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    task: str,
    fold: str,
    features: dict[str, np.ndarray],
    smiles_to_index: dict[str, int],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    tr = train_df[["SMILES", task]].copy()
    te = test_df[["SMILES", task]].copy()
    tr["canonical_smiles"] = tr["SMILES"].map(canonicalize_smiles)
    te["canonical_smiles"] = te["SMILES"].map(canonicalize_smiles)
    tr = tr.dropna(subset=["canonical_smiles", task])
    te = te.dropna(subset=["canonical_smiles", task])
    tr = tr[tr["canonical_smiles"].isin(smiles_to_index)]
    te = te[te["canonical_smiles"].isin(smiles_to_index)]
    if len(tr) < args.min_train or len(te) < args.min_test:
        return []

    tr_idx = [smiles_to_index[s] for s in tr["canonical_smiles"]]
    te_idx = [smiles_to_index[s] for s in te["canonical_smiles"]]
    y_train = tr[task].astype(float).to_numpy()
    y_test = te[task].astype(float).to_numpy()

    rows = []
    for feature_set, members in build_feature_sets(features, args.feature_mode).items():
        member_preds = []
        member_weights = []
        for feature_name, X in members.items():
            X_train = X[tr_idx]
            X_test = X[te_idx]
            model_rows, pred = fit_feature_model(
                feature_set,
                feature_name,
                X_train,
                y_train,
                X_test,
                y_test,
                args.seed,
                args.model_n_jobs,
                set(args.models),
            )
            for row in model_rows:
                row.update({"fold": fold, "task": task, "n_train": len(y_train), "n_test": len(y_test)})
                rows.append(row)
            best_val = min(r["val_mae"] for r in model_rows if r["model"] != "weighted_ensemble")
            member_preds.append(pred)
            member_weights.append(1.0 / max(best_val, 1e-8))
        if len(member_preds) > 1:
            w = np.asarray(member_weights)
            w = w / w.sum()
            combo_pred = np.average(np.vstack(member_preds), axis=0, weights=w)
            row = {
                "feature_set": feature_set,
                "feature": "all_members",
                "model": "feature_weighted_ensemble",
                "val_mae": float("nan"),
                **metrics(y_test, combo_pred, float(np.mean(y_train))),
                "fold": fold,
                "task": task,
                "n_train": len(y_train),
                "n_test": len(y_test),
            }
            rows.append(row)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ckpt-path", type=Path, default=Path("ckpt/chemeleon_mp.pt"))
    parser.add_argument("--data-dir", type=Path, default=Path("data/OpenADMET + ExpansionRx Blind Challenge"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/openadmet_rced_public_approx"))
    parser.add_argument("--folds", nargs="+", type=int, default=None)
    parser.add_argument("--tasks", nargs="+", default=None)
    parser.add_argument("--feature-mode", choices=["all", "chemeleon", "mordred", "public_combo"], default="all")
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--mordred-batch-size", type=int, default=1024)
    parser.add_argument("--mordred-nproc", type=int, default=1)
    parser.add_argument("--num-workers", type=int, default=0)
    parser.add_argument("--fp-bits", type=int, default=2048)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-n-jobs", type=int, default=1)
    parser.add_argument(
        "--models",
        nargs="+",
        default=["ridge", "random_forest", "extra_trees", "gradient_boosting"],
        choices=["ridge", "random_forest", "extra_trees", "gradient_boosting"],
    )
    parser.add_argument("--min-train", type=int, default=40)
    parser.add_argument("--min-test", type=int, default=10)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fold_dirs = sorted(args.data_dir.glob("fold_*"), key=lambda p: int(p.name.split("_")[1]))
    if args.folds:
        wanted = {f"fold_{i}" for i in args.folds}
        fold_dirs = [p for p in fold_dirs if p.name in wanted]
    tasks = args.tasks or OPENADMET_TASKS

    all_smiles = collect_openadmet_smiles(fold_dirs)
    valid_smiles = []
    seen = set()
    for smi in all_smiles:
        can = canonicalize_smiles(smi)
        if can is not None and can not in seen:
            valid_smiles.append(can)
            seen.add(can)
    cache_dir = args.output_dir / "openadmet" / "feature_cache"
    features: dict[str, np.ndarray] = {}
    feature_meta: dict[str, Any] = {}
    if args.feature_mode in {"all", "chemeleon", "public_combo"}:
        X, meta = load_or_compute_chemeleon_features(
            valid_smiles, args.ckpt_path, cache_dir, args.batch_size, args.num_workers
        )
        features["chemeleon_representation"] = X
        feature_meta["chemeleon_representation"] = meta
    if args.feature_mode in {"all", "mordred", "public_combo"}:
        X, names, meta = load_or_compute_mordred2d_features(
            valid_smiles, cache_dir, args.mordred_batch_size, args.mordred_nproc
        )
        features["mordred2d_full"] = X
        feature_meta["mordred2d_full"] = meta | {"first_features": names[:10]}
    if args.feature_mode in {"all", "public_combo"}:
        rdkit2d, rdkit2d_meta = load_or_compute_rdkit2d(valid_smiles, cache_dir)
        fps, fp_meta = load_or_compute_fingerprints(valid_smiles, cache_dir, args.fp_bits)
        features.update({"rdkit2d": rdkit2d})
        features.update(fps)
        feature_meta["rdkit2d"] = rdkit2d_meta
        feature_meta["fingerprints"] = fp_meta
    write_json(
        args.output_dir / "feature_manifest.json",
        {
            "features": feature_meta,
            "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        },
    )
    smiles_to_index = {s: i for i, s in enumerate(valid_smiles)}

    rows = []
    for fold_dir in fold_dirs:
        train_df = pd.read_csv(fold_dir / "train.csv")
        test_df = pd.read_csv(fold_dir / "test.csv")
        for task in tasks:
            rows.extend(evaluate_fold_task(train_df, test_df, task, fold_dir.name, features, smiles_to_index, args))
            print(f"[done] {fold_dir.name} {task}", flush=True)

    result = pd.DataFrame(rows)
    result.to_csv(args.output_dir / "rced_public_approx_results.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    summary = (
        result.groupby(["feature_set", "task", "model"])[["rmse", "mae", "rae", "r2"]]
        .agg(["mean", "median", "std", "count"])
        .reset_index()
    )
    summary.to_csv(args.output_dir / "rced_public_approx_summary.csv", index=False)
    print(f"Wrote {args.output_dir / 'rced_public_approx_results.csv'}")


if __name__ == "__main__":
    main()
