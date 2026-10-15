#!/usr/bin/env python
"""Reproduce the ML_QSAR pre-model analyses on ExpansionRx.

This script ports the public notebook for "Deep Learning vs Classical
Methods in Potency & ADME Prediction" to the OpenADMET ExpansionRx data.
It intentionally keeps the paper implementation constants visible in one
place so downstream reports can audit them.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from rdkit.Chem.Scaffolds.MurckoScaffold import MurckoScaffoldSmilesFromSmiles
from scipy import sparse
from scipy.cluster.hierarchy import linkage
from scipy.sparse.csgraph import connected_components, minimum_spanning_tree
from scipy.spatial.distance import pdist
from scipy.stats import kendalltau, mannwhitneyu, pearsonr, spearmanr, ttest_ind, zscore
from sklearn.cluster import AgglomerativeClustering
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.neighbors import NearestNeighbors


TASKS = [
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

SET_PALETTE = {"Train": "#009e73", "Test": "#e69f00"}

RAW_TO_LOG = {
    "LogD": ("LogD", False, 1.0),
    "KSOL": ("LogS", True, 1e-6),
    "HLM CLint": ("Log_HLM_CLint", True, 1.0),
    "MLM CLint": ("Log_MLM_CLint", True, 1.0),
    "Caco-2 Permeability Papp A>B": ("Log_Caco_Papp_AB", True, 1e-6),
    "Caco-2 Permeability Efflux": ("Log_Caco_ER", True, 1.0),
    "MPPB": ("Log_Mouse_PPB", True, 1.0),
    "MBPB": ("Log_Mouse_BPB", True, 1.0),
    "MGMB": ("Log_Mouse_MPB", True, 1.0),
}

PAIR_PLOTS = [
    ("LogD", "LogS"),
    ("Log_HLM_CLint", "Log_MLM_CLint"),
    ("Log_Caco_Papp_AB", "Log_Caco_ER"),
    ("Log_Mouse_PPB", "Log_Mouse_BPB"),
    ("Log_Mouse_BPB", "Log_Mouse_MPB"),
]

PAPER_SEEDS = [42, 37, 83, 96, 101]


@dataclass(frozen=True)
class PaperConstants:
    morgan_radius: int = 2
    fp_size: int = 2048
    include_chirality: bool = True
    agglo_n_clusters: int = 500
    agglo_linkage: str = "complete"
    agglo_metric: str = "jaccard"
    sali_denominator_offset: float = 1.05
    cliff_z_threshold: float = 2.5
    cv_n_splits: int = 5
    cv_n_repeats: int = 5
    cv_seeds: tuple[int, ...] = tuple(PAPER_SEEDS)
    stratify_target: str = "LogD"


CONSTANTS = PaperConstants()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/OpenADMET + ExpansionRx Blind Challenge"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/OpenADMET_ExpansionRx_MLQSAR_paper_reproduction"),
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=Path("results/expansionrx_mlqsar_preanalysis"),
    )
    parser.add_argument("--max-train-rows", type=int, default=None)
    parser.add_argument("--max-test-rows", type=int, default=None)
    parser.add_argument("--agglo-clusters", type=int, default=CONSTANTS.agglo_n_clusters)
    parser.add_argument("--tmap-neighbors", type=int, default=12)
    parser.add_argument("--tmap-layout-iterations", type=int, default=120)
    parser.add_argument("--tmap-n-jobs", type=int, default=1)
    parser.add_argument("--skip-cliffs", action="store_true")
    parser.add_argument("--skip-tmap", action="store_true")
    parser.add_argument("--write-masked-folds", action="store_true", default=True)
    parser.add_argument("--figure-format", choices=["png", "svg", "both"], default="png")
    return parser.parse_args()


def ensure_dirs(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def transform_raw_expansionrx(df: pd.DataFrame) -> pd.DataFrame:
    out = df[["SMILES", "Molecule Name"]].copy()
    for raw_col, (log_col, log_scale, multiplier) in RAW_TO_LOG.items():
        values = pd.to_numeric(df[raw_col], errors="coerce")
        if log_scale:
            values = np.log10((values + 1.0) * multiplier)
        out[log_col] = values
    return out[["SMILES", "Molecule Name"] + TASKS]


def load_expansionrx(input_dir: Path, max_train: int | None, max_test: int | None) -> pd.DataFrame:
    train_path = input_dir / "log_train_data.csv"
    test_path = input_dir / "openadmet_full_test" / "expansion_data_test.csv"
    if not train_path.exists():
        raise FileNotFoundError(f"Missing transformed train file: {train_path}")
    if not test_path.exists():
        raise FileNotFoundError(f"Missing official test file: {test_path}")

    train_df = pd.read_csv(train_path)
    test_df = transform_raw_expansionrx(pd.read_csv(test_path))
    if max_train is not None:
        train_df = train_df.head(max_train).copy()
    if max_test is not None:
        test_df = test_df.head(max_test).copy()
    train_df["Set"] = "Train"
    test_df["Set"] = "Test"
    return pd.concat([train_df, test_df], ignore_index=True)


def mol_from_smiles(smiles: str) -> Chem.Mol:
    mol = Chem.MolFromSmiles(str(smiles))
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles}")
    return mol


def fingerprint_generator() -> rdFingerprintGenerator.FingerprintGenerator64:
    return rdFingerprintGenerator.GetMorganGenerator(
        radius=CONSTANTS.morgan_radius,
        fpSize=CONSTANTS.fp_size,
        includeChirality=CONSTANTS.include_chirality,
    )


def add_fingerprints(df: pd.DataFrame) -> tuple[pd.DataFrame, list[DataStructs.ExplicitBitVect], np.ndarray]:
    fg = fingerprint_generator()
    mols = [mol_from_smiles(smi) for smi in df["SMILES"]]
    bitvectors = [fg.GetFingerprint(mol) for mol in mols]
    bit_arrays = np.zeros((len(bitvectors), CONSTANTS.fp_size), dtype=np.uint8)
    for idx, fp in enumerate(bitvectors):
        arr = np.zeros((CONSTANTS.fp_size,), dtype=np.int8)
        DataStructs.ConvertToNumpyArray(fp, arr)
        bit_arrays[idx] = arr
    return df.copy(), bitvectors, bit_arrays


def max_tanimoto_to_other_split(
    df: pd.DataFrame, bitvectors: list[DataStructs.ExplicitBitVect]
) -> pd.DataFrame:
    out = df.copy()
    train_idx = out.index[out["Set"] == "Train"].to_numpy()
    test_idx = out.index[out["Set"] == "Test"].to_numpy()
    train_fps = [bitvectors[i] for i in train_idx]
    test_fps = [bitvectors[i] for i in test_idx]
    out["train_test_sim"] = np.nan
    for i in train_idx:
        sims = DataStructs.BulkTanimotoSimilarity(bitvectors[i], test_fps)
        out.at[i, "train_test_sim"] = float(np.max(sims)) if sims else np.nan
    for i in test_idx:
        sims = DataStructs.BulkTanimotoSimilarity(bitvectors[i], train_fps)
        out.at[i, "train_test_sim"] = float(np.max(sims)) if sims else np.nan
    return out


def add_scaffold_clusters(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    scaffolds = out["SMILES"].apply(lambda smi: MurckoScaffoldSmilesFromSmiles(str(smi)))
    out["murcko_scaffold"] = scaffolds
    out["scaffold_cluster"] = pd.factorize(scaffolds)[0]
    return out


def add_label_coverage(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["n_labeled_endpoints"] = out[TASKS].notna().sum(axis=1)
    coverage_bins = [-0.1, 1, 3, 6, len(TASKS)]
    coverage_labels = ["0-1 labels", "2-3 labels", "4-6 labels", "7-9 labels"]
    out["label_coverage_bin"] = pd.cut(
        out["n_labeled_endpoints"],
        bins=coverage_bins,
        labels=coverage_labels,
        include_lowest=True,
    ).astype(str)
    return out


def add_agglo_clusters(df: pd.DataFrame, bit_arrays: np.ndarray, n_clusters: int) -> pd.DataFrame:
    out = df.copy()
    n_clusters = int(min(n_clusters, max(1, len(out) - 1)))
    distances = pdist(bit_arrays != 0, metric=CONSTANTS.agglo_metric)
    try:
        clustering = AgglomerativeClustering(
            n_clusters=n_clusters,
            metric="precomputed",
            linkage=CONSTANTS.agglo_linkage,
            distance_threshold=None,
        )
    except TypeError:
        clustering = AgglomerativeClustering(
            n_clusters=n_clusters,
            affinity="precomputed",
            linkage=CONSTANTS.agglo_linkage,
            distance_threshold=None,
        )
    labels = clustering.fit_predict(square_distance(distances, len(out)))
    out["agglo_cluster"] = labels
    return out


def compute_tmap_style_layout(
    bit_arrays: np.ndarray,
    n_neighbors: int = 12,
    layout_iterations: int = 120,
    n_jobs: int = 1,
    seed: int = 42,
) -> pd.DataFrame:
    """Build a static TMAP-style layout from an ECFP4 kNN/MST graph.

    The paper reports TMAP using ECFP4 fingerprints. The Python package named
    `tmap` on PyPI is not the LSHForest/Faerun TMAP implementation used for
    chemical visualization, so this function implements the same visual idea
    as a reproducible static fallback: ECFP4 Jaccard kNN graph, minimum
    spanning tree, and deterministic force-directed tree layout.
    """

    n_samples = bit_arrays.shape[0]
    n_neighbors = int(min(max(2, n_neighbors), max(2, n_samples - 1)))
    bool_bits = bit_arrays.astype(bool)
    nn = NearestNeighbors(
        n_neighbors=n_neighbors + 1,
        metric="jaccard",
        algorithm="brute",
        n_jobs=n_jobs,
    )
    nn.fit(bool_bits)
    knn = nn.kneighbors_graph(bool_bits, mode="distance")
    knn = knn.maximum(knn.T).tocsr()

    n_components, labels = connected_components(knn, directed=False)
    mst_blocks = []
    for component in range(n_components):
        idx = np.where(labels == component)[0]
        subgraph = knn[idx][:, idx]
        if len(idx) == 1:
            continue
        mst_sub = minimum_spanning_tree(subgraph).tocoo()
        rows = idx[mst_sub.row]
        cols = idx[mst_sub.col]
        mst_blocks.append(sparse.coo_matrix((mst_sub.data, (rows, cols)), shape=(n_samples, n_samples)))
    if mst_blocks:
        mst = sum(mst_blocks).tocsr()
    else:
        mst = sparse.csr_matrix((n_samples, n_samples))

    import networkx as nx

    graph = nx.Graph()
    graph.add_nodes_from(range(n_samples))
    coo = mst.tocoo()
    for row, col, dist in zip(coo.row, coo.col, coo.data):
        graph.add_edge(int(row), int(col), distance=float(dist), weight=float(1.0 - dist))

    pos = nx.spring_layout(
        graph,
        seed=seed,
        weight="weight",
        iterations=layout_iterations,
        scale=1.0,
    )
    coords = np.asarray([pos[i] for i in range(n_samples)], dtype=float)
    layout = pd.DataFrame(
        {
            "tmap_x": coords[:, 0],
            "tmap_y": coords[:, 1],
            "tmap_component": labels,
            "tmap_degree": [graph.degree[i] for i in range(n_samples)],
        }
    )
    return layout


def square_distance(condensed: np.ndarray, n: int) -> np.ndarray:
    matrix = np.zeros((n, n), dtype=np.float32)
    tri = np.triu_indices(n, k=1)
    matrix[tri] = condensed.astype(np.float32)
    matrix[(tri[1], tri[0])] = matrix[tri]
    return matrix


def tanimoto_matrix_for_indices(
    indices: Iterable[int], bitvectors: list[DataStructs.ExplicitBitVect]
) -> tuple[list[int], np.ndarray]:
    idx = list(indices)
    mat = np.eye(len(idx), dtype=np.float32)
    for row, original_i in enumerate(idx):
        sims = DataStructs.BulkTanimotoSimilarity(bitvectors[original_i], [bitvectors[j] for j in idx])
        mat[row, :] = np.asarray(sims, dtype=np.float32)
    return idx, mat


def add_activity_cliffs(
    df: pd.DataFrame,
    bitvectors: list[DataStructs.ExplicitBitVect],
    tasks: list[str],
    z_threshold: float = CONSTANTS.cliff_z_threshold,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = df.copy()
    cliff_rows: list[dict[str, object]] = []
    for task in tasks:
        sali = np.full(len(out), np.nan, dtype=float)
        for _, cluster_df in out.groupby("agglo_cluster", sort=False):
            train_indices = cluster_df.index[cluster_df["Set"] == "Train"].tolist()
            valid_indices = [i for i in train_indices if not pd.isna(out.at[i, task])]
            if len(valid_indices) < 2:
                continue
            _, sim = tanimoto_matrix_for_indices(valid_indices, bitvectors)
            y = out.loc[valid_indices, task].astype(float).to_numpy()
            dy = np.abs(y[:, None] - y[None, :])
            vals = dy / (CONSTANTS.sali_denominator_offset - sim)
            np.fill_diagonal(vals, 0.0)
            sali[valid_indices] = np.nanmax(vals, axis=1)
        z = zscore(sali, nan_policy="omit")
        is_cliff = np.abs(z) > z_threshold
        out[f"SALI_{task}"] = sali
        out[f"z_SALI_{task}"] = z
        out[f"is_cliff_{task}"] = is_cliff
        for idx in np.where(is_cliff & ~np.isnan(sali))[0]:
            cliff_rows.append(
                {
                    "row_index": int(idx),
                    "Molecule Name": out.at[idx, "Molecule Name"],
                    "SMILES": out.at[idx, "SMILES"],
                    "task": task,
                    "SALI": float(sali[idx]),
                    "z_SALI": float(z[idx]),
                    "agglo_cluster": int(out.at[idx, "agglo_cluster"]),
                }
            )
    return out, pd.DataFrame(cliff_rows)


def add_paper_cv_splits(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    train_mask = out["Set"] == "Train"
    train = out.loc[train_mask]
    y = pd.to_numeric(train[CONSTANTS.stratify_target], errors="coerce")
    med = y.median()
    strat_y = (y.fillna(med) > med).to_numpy()
    groups = train["scaffold_cluster"].to_numpy()
    counter = 1
    for seed in PAPER_SEEDS:
        splitter = StratifiedGroupKFold(
            n_splits=CONSTANTS.cv_n_splits,
            shuffle=True,
            random_state=seed,
        )
        for _, val_pos in splitter.split(np.arange(len(train)), strat_y, groups):
            col = f"CV_val_{counter}"
            out[col] = False
            val_index = train.index[val_pos]
            out.loc[val_index, col] = True
            counter += 1
    return out


def pearson_safe(x: pd.Series, y: pd.Series) -> tuple[float, float]:
    mask = x.notna() & y.notna()
    if mask.sum() < 3:
        return np.nan, np.nan
    return pearsonr(x[mask], y[mask])


def correlation_tables(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for x in TASKS:
        for y in TASKS:
            mask = df[x].notna() & df[y].notna()
            if mask.sum() < 3:
                pearson_val = pearson_p = spearman_val = spearman_p = kendall_val = kendall_p = np.nan
            else:
                pearson_val, pearson_p = pearsonr(df.loc[mask, x], df.loc[mask, y])
                spearman_val, spearman_p = spearmanr(df.loc[mask, x], df.loc[mask, y])
                kendall_res = kendalltau(df.loc[mask, x], df.loc[mask, y])
                kendall_val, kendall_p = kendall_res.statistic, kendall_res.pvalue
            rows.append(
                {
                    "x": x,
                    "y": y,
                    "n_pair": int(mask.sum()),
                    "pearsonr": pearson_val,
                    "pearson_p": pearson_p,
                    "spearman_rho": spearman_val,
                    "spearman_p": spearman_p,
                    "kendall_tau": kendall_val,
                    "kendall_p": kendall_p,
                }
            )
    corr = pd.DataFrame(rows)
    pearson_matrix = corr.pivot(index="x", columns="y", values="pearsonr").loc[TASKS, TASKS]
    return corr, pearson_matrix


def endpoint_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for task in TASKS:
        for split, sub in df.groupby("Set"):
            vals = pd.to_numeric(sub[task], errors="coerce")
            rows.append(
                {
                    "task": task,
                    "Set": split,
                    "n_total": len(sub),
                    "n_labeled": int(vals.notna().sum()),
                    "missing_fraction": float(vals.isna().mean()),
                    "mean": vals.mean(),
                    "std": vals.std(),
                    "min": vals.min(),
                    "q25": vals.quantile(0.25),
                    "median": vals.median(),
                    "q75": vals.quantile(0.75),
                    "max": vals.max(),
                }
            )
    return pd.DataFrame(rows)


def shared_scaffold_summary(df: pd.DataFrame) -> pd.DataFrame:
    train_scaffolds = set(df.loc[df["Set"] == "Train", "murcko_scaffold"])
    test = df[df["Set"] == "Test"].copy()
    shared = test["murcko_scaffold"].isin(train_scaffolds)
    return pd.DataFrame(
        [
            {
                "n_test": int(len(test)),
                "n_test_shared_train_scaffold": int(shared.sum()),
                "fraction_test_shared_train_scaffold": float(shared.mean()),
                "percent_test_shared_train_scaffold": float(shared.mean() * 100.0),
            }
        ]
    )


def similarity_label_tests(df: pd.DataFrame) -> pd.DataFrame:
    test = df[df["Set"] == "Test"].copy()
    median_sim = test["train_test_sim"].median()
    test["similarity_group"] = np.where(test["train_test_sim"] > median_sim, "high", "low")
    rows = []
    raw_p_values = []
    for task in TASKS:
        high = test.loc[test["similarity_group"] == "high", task].dropna()
        low = test.loc[test["similarity_group"] == "low", task].dropna()
        if len(high) < 2 or len(low) < 2:
            mw_p = t_p = np.nan
            mw_stat = t_stat = np.nan
        else:
            mw = mannwhitneyu(high, low, alternative="two-sided")
            tt = ttest_ind(high, low, equal_var=False, nan_policy="omit")
            mw_stat, mw_p = mw.statistic, mw.pvalue
            t_stat, t_p = tt.statistic, tt.pvalue
        raw_p_values.append(t_p)
        rows.append(
            {
                "task": task,
                "median_test_similarity": median_sim,
                "n_high": int(len(high)),
                "n_low": int(len(low)),
                "mean_high": high.mean(),
                "mean_low": low.mean(),
                "mannwhitney_u": mw_stat,
                "mannwhitney_p": mw_p,
                "welch_t": t_stat,
                "welch_p": t_p,
            }
        )
    valid = [p for p in raw_p_values if not pd.isna(p)]
    corrected_values = [min(float(p) * len(valid), 1.0) for p in valid]
    corrected = iter(corrected_values)
    for row in rows:
        row["welch_p_bonferroni"] = np.nan if pd.isna(row["welch_p"]) else float(next(corrected))
    return pd.DataFrame(rows)


def cliff_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    train = df[df["Set"] == "Train"]
    for task in TASKS:
        labeled = train[task].notna()
        cliff_col = f"is_cliff_{task}"
        n_labeled = int(labeled.sum())
        n_cliff = int((labeled & train[cliff_col]).sum()) if cliff_col in train else 0
        rows.append(
            {
                "task": task,
                "n_labeled_train": n_labeled,
                "n_cliff": n_cliff,
                "fraction_cliff": n_cliff / n_labeled if n_labeled else np.nan,
                "percent_retained_after_masking": 100.0 * (1.0 - n_cliff / n_labeled) if n_labeled else np.nan,
            }
        )
    return pd.DataFrame(rows)


def cv_summary(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    train = df[df["Set"] == "Train"]
    for col in [c for c in df.columns if c.startswith("CV_val_")]:
        val = train[col].astype(bool)
        rows.append(
            {
                "CV": col.replace("_val", ""),
                "n_train": int((~val).sum()),
                "n_val": int(val.sum()),
                "val_fraction": float(val.mean()),
                "n_val_scaffolds": int(train.loc[val, "scaffold_cluster"].nunique()),
                "n_train_scaffolds": int(train.loc[~val, "scaffold_cluster"].nunique()),
                "median_LogD_val": train.loc[val, "LogD"].median(),
                "median_LogD_train": train.loc[~val, "LogD"].median(),
            }
        )
    return pd.DataFrame(rows)


def save_fig(fig: plt.Figure, figures_dir: Path, name: str, fmt: str) -> None:
    if fmt in {"png", "both"}:
        fig.savefig(figures_dir / f"{name}.png", dpi=220, bbox_inches="tight")
    if fmt in {"svg", "both"}:
        fig.savefig(figures_dir / f"{name}.svg", bbox_inches="tight")
    plt.close(fig)


def set_paper_style() -> None:
    sns.set_theme(style="ticks", context="notebook")
    plt.rcParams["figure.facecolor"] = "white"
    plt.rcParams["axes.facecolor"] = "white"
    plt.rcParams["savefig.facecolor"] = "white"


def plot_similarity_hist(df: pd.DataFrame, figures_dir: Path, fmt: str) -> None:
    set_paper_style()
    fig, ax = plt.subplots(figsize=(6, 3.4))
    sns.histplot(
        data=df,
        x="train_test_sim",
        hue="Set",
        hue_order=["Train", "Test"],
        palette=SET_PALETTE,
        stat="probability",
        common_norm=False,
        bins=20,
        alpha=0.8,
        element="bars",
        edgecolor="white",
        ax=ax,
    )
    ax.set_xlabel("Tanimoto similarity between train and test sets", fontsize=12)
    ax.set_ylabel("Probability", fontsize=12)
    sns.move_legend(ax, "best", title="Set")
    if "murcko_scaffold" in df:
        shared = shared_scaffold_summary(df)["percent_test_shared_train_scaffold"].iloc[0]
        ax.text(
            0.02,
            0.95,
            f"Test shared scaffold: {shared:.1f}%",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=10,
        )
    sns.despine(fig=fig)
    save_fig(fig, figures_dir, "fig2a_train_test_similarity_histogram", fmt)


def plot_tmap_chemical_space(df: pd.DataFrame, figures_dir: Path, fmt: str) -> None:
    if not {"tmap_x", "tmap_y"}.issubset(df.columns):
        return
    set_paper_style()
    fig, ax = plt.subplots(figsize=(6, 5.2))
    for split in ["Train", "Test"]:
        sub = df[df["Set"] == split]
        ax.scatter(
            sub["tmap_x"],
            sub["tmap_y"],
            s=6 if split == "Train" else 9,
            c=SET_PALETTE[split],
            alpha=0.62 if split == "Train" else 0.82,
            linewidths=0,
            label=split,
            rasterized=True,
        )
    ax.set_title("ExpansionRx", fontsize=16)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.legend(title="")
    sns.despine(fig=fig, left=True, bottom=True)
    save_fig(fig, figures_dir, "fig2b_tmap_chemical_space_train_test", fmt)

    fig, ax = plt.subplots(figsize=(6, 5.2))
    coverage_palette = {
        "0-1 labels": "#d9d9d9",
        "2-3 labels": "#a6cee3",
        "4-6 labels": "#1f78b4",
        "7-9 labels": "#08306b",
    }
    for group, color in coverage_palette.items():
        sub = df[df["label_coverage_bin"] == group]
        if sub.empty:
            continue
        ax.scatter(
            sub["tmap_x"],
            sub["tmap_y"],
            s=7,
            c=color,
            alpha=0.72,
            linewidths=0,
            label=group,
            rasterized=True,
        )
    ax.set_title("ExpansionRx label coverage", fontsize=16)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.legend(title="Endpoint labels", markerscale=2.2, fontsize=9)
    sns.despine(fig=fig, left=True, bottom=True)
    save_fig(fig, figures_dir, "fig2c_tmap_chemical_space_label_coverage", fmt)


def plot_joint_like(df: pd.DataFrame, figures_dir: Path, fmt: str) -> None:
    set_paper_style()
    for x_col, y_col in PAIR_PLOTS:
        plot_df = df.loc[df[x_col].notna() & df[y_col].notna(), [x_col, y_col, "Set"]].copy()
        if plot_df.empty:
            continue
        g = sns.jointplot(
            data=plot_df,
            x=x_col,
            y=y_col,
            hue="Set",
            hue_order=["Train", "Test"],
            marginal_kws={"common_norm": False},
            ratio=3,
            palette=SET_PALETTE,
            joint_kws={"alpha": 0.8, "s": 16, "linewidth": 0},
            height=5.5,
        )
        g.ax_joint.set_xlabel(x_col, fontsize=13)
        g.ax_joint.set_ylabel(y_col, fontsize=13)
        sns.despine(fig=g.fig)
        save_fig(g.fig, figures_dir, f"fig2_joint_{x_col}_vs_{y_col}", fmt)


def plot_correlation_heatmap(matrix: pd.DataFrame, figures_dir: Path, fmt: str) -> None:
    set_paper_style()
    fig, ax = plt.subplots(figsize=(8.2, 6.2))
    sns.heatmap(
        matrix,
        cmap="YlGn",
        annot=True,
        cbar_kws={"label": "Correlation (Pearson r)"},
        alpha=0.9,
        fmt=".2f",
        vmin=-1,
        vmax=1,
        linewidths=0.25,
        linecolor="white",
        ax=ax,
    )
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")
    ax.set_xlabel("")
    ax.set_ylabel("")
    save_fig(fig, figures_dir, "endpoint_pearson_correlation_heatmap", fmt)


def plot_endpoint_distributions(df: pd.DataFrame, figures_dir: Path, fmt: str) -> None:
    set_paper_style()
    fig, axes = plt.subplots(3, 3, figsize=(10, 8))
    axes = axes.ravel()
    for ax, task in zip(axes, TASKS):
        sns.histplot(
            data=df,
            x=task,
            hue="Set",
            hue_order=["Train", "Test"],
            palette=SET_PALETTE,
            common_norm=False,
            stat="density",
            bins=25,
            alpha=0.55,
            element="bars",
            edgecolor="white",
            legend=False,
            ax=ax,
        )
        ax.set_title(task, fontsize=9)
        ax.set_xlabel("")
    handles = [
        plt.Line2D([0], [0], color=SET_PALETTE["Train"], lw=8, alpha=0.7),
        plt.Line2D([0], [0], color=SET_PALETTE["Test"], lw=8, alpha=0.7),
    ]
    fig.legend(handles, ["Train", "Test"], loc="upper center", ncols=2)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    sns.despine(fig=fig)
    save_fig(fig, figures_dir, "endpoint_distribution_grid", fmt)


def plot_cliffs(df: pd.DataFrame, cliff_stats: pd.DataFrame, figures_dir: Path, fmt: str) -> None:
    set_paper_style()
    sali_rows = []
    for task in TASKS:
        col = f"z_SALI_{task}"
        if col not in df:
            continue
        sub = df.loc[df["Set"] == "Train", [col]].dropna()
        for val in sub[col].to_numpy():
            sali_rows.append({"task": task, "abs_z_SALI": abs(float(val))})
    sali_df = pd.DataFrame(sali_rows)
    if not sali_df.empty:
        fig, ax = plt.subplots(figsize=(7, 4))
        sns.boxplot(
            data=sali_df,
            x="abs_z_SALI",
            y="task",
            hue="task",
            order=TASKS,
            hue_order=TASKS,
            palette="tab10",
            flierprops={"marker": "x", "markersize": 0},
            legend=False,
            ax=ax,
        )
        sns.stripplot(
            data=sali_df,
            x="abs_z_SALI",
            y="task",
            hue="task",
            order=TASKS,
            hue_order=TASKS,
            size=2.4,
            palette="tab10",
            alpha=0.45,
            marker="o",
            legend=False,
            ax=ax,
        )
        ax.axvline(CONSTANTS.cliff_z_threshold, ls="--", lw=2, color="black")
        ax.axvspan(CONSTANTS.cliff_z_threshold, max(8, sali_df["abs_z_SALI"].max()), alpha=0.1, color="red")
        ax.set_xlabel("SALI |z-score|", fontsize=12)
        ax.set_ylabel("")
        ax.xaxis.grid(True)
        sns.despine(fig=fig)
        save_fig(fig, figures_dir, "sali_abs_zscore_cliff_zone", fmt)

    fig, ax = plt.subplots(figsize=(7, 4))
    sns.barplot(
        data=cliff_stats,
        x="percent_retained_after_masking",
        y="task",
        order=TASKS,
        color="#4c78a8",
        ax=ax,
    )
    ax.set_xlim(90, 100)
    ax.set_xlabel("% retained after cliff masking")
    ax.set_ylabel("")
    sns.despine(fig=fig)
    save_fig(fig, figures_dir, "cliff_masking_retention", fmt)


def plot_cv_summary(cv_stats: pd.DataFrame, figures_dir: Path, fmt: str) -> None:
    set_paper_style()
    fig, ax = plt.subplots(figsize=(6, 3.5))
    sns.boxplot(data=cv_stats, x="val_fraction", color="#009e73", width=0.35, ax=ax)
    sns.stripplot(data=cv_stats, x="val_fraction", color="#e69f00", size=5, alpha=0.85, ax=ax)
    ax.axvline(0.2, color="gray", ls="--")
    ax.set_xlabel("Validation fraction")
    ax.set_yticks([])
    sns.despine(fig=fig, left=True)
    save_fig(fig, figures_dir, "paper_5x5_scaffold_cv_val_fraction", fmt)


def write_fold_datasets(df: pd.DataFrame, output_dir: Path, masked: bool) -> pd.DataFrame:
    train = df[df["Set"] == "Train"].copy()
    cols = ["SMILES", "Molecule Name"] + TASKS
    fold_rows = []
    root = output_dir / "cliff_masked" if masked else output_dir
    ensure_dirs(root)
    for fold_no, cv_col in enumerate([c for c in df.columns if c.startswith("CV_val_")], start=1):
        fold_dir = root / f"fold_{fold_no}"
        ensure_dirs(fold_dir)
        train_part = train.loc[~train[cv_col].astype(bool), cols].copy()
        val_part = train.loc[train[cv_col].astype(bool), cols].copy()
        if masked:
            for task in TASKS:
                cliff_col = f"is_cliff_{task}"
                if cliff_col in train:
                    train_part.loc[train_part["Molecule Name"].isin(train.loc[train[cliff_col], "Molecule Name"]), task] = np.nan
        train_part.to_csv(fold_dir / "train.csv", index=False)
        val_part.to_csv(fold_dir / "test.csv", index=False)
        fold_rows.append(
            {
                "fold": fold_no,
                "cv_column": cv_col,
                "folder": str(fold_dir.as_posix()),
                "masked": masked,
                "n_train": len(train_part),
                "n_test": len(val_part),
            }
        )
    return pd.DataFrame(fold_rows)


def write_outputs(df: pd.DataFrame, output_dir: Path, results_dir: Path, figures_dir: Path, fmt: str) -> None:
    tables_dir = results_dir / "tables"
    ensure_dirs(output_dir, results_dir, figures_dir, tables_dir)

    combined_path = output_dir / "combined_with_mlqsar_analysis.csv"
    df.to_csv(combined_path, index=False)
    df.loc[df["Set"] == "Train", ["SMILES", "Molecule Name"] + TASKS].to_csv(output_dir / "log_train_data.csv", index=False)
    df.loc[df["Set"] == "Test", ["SMILES", "Molecule Name"] + TASKS].to_csv(output_dir / "official_test.csv", index=False)

    endpoint_stats = endpoint_summary(df)
    endpoint_stats.to_csv(tables_dir / "endpoint_distribution_summary.csv", index=False)
    corr_long, corr_matrix = correlation_tables(df)
    corr_long.to_csv(tables_dir / "endpoint_correlations_long.csv", index=False)
    corr_matrix.to_csv(tables_dir / "endpoint_pearson_matrix.csv")
    sim_tests = similarity_label_tests(df)
    sim_tests.to_csv(tables_dir / "test_similarity_high_low_label_tests.csv", index=False)
    cv_stats = cv_summary(df)
    cv_stats.to_csv(tables_dir / "paper_5x5_scaffold_cv_summary.csv", index=False)
    scaffold_stats = (
        df.groupby("Set")
        .agg(n_molecules=("SMILES", "size"), n_scaffolds=("murcko_scaffold", "nunique"), n_agglo_clusters=("agglo_cluster", "nunique"))
        .reset_index()
    )
    scaffold_stats.to_csv(tables_dir / "chemical_space_set_summary.csv", index=False)
    shared_scaffold_summary(df).to_csv(tables_dir / "shared_test_scaffold_summary.csv", index=False)
    if {"tmap_x", "tmap_y"}.issubset(df.columns):
        df[
            [
                "SMILES",
                "Molecule Name",
                "Set",
                "tmap_x",
                "tmap_y",
                "tmap_component",
                "tmap_degree",
                "n_labeled_endpoints",
                "label_coverage_bin",
                "train_test_sim",
                "murcko_scaffold",
            ]
        ].to_csv(tables_dir / "tmap_chemical_space_coordinates.csv", index=False)

    if any(c.startswith("is_cliff_") for c in df.columns):
        cliff_stats = cliff_summary(df)
        cliff_stats.to_csv(tables_dir / "activity_cliff_summary.csv", index=False)
        cliff_rows = []
        for task in TASKS:
            cliff_col = f"is_cliff_{task}"
            if cliff_col in df:
                sub = df.loc[df["Set"].eq("Train") & df[cliff_col], ["SMILES", "Molecule Name", task, f"SALI_{task}", f"z_SALI_{task}", "agglo_cluster"]].copy()
                sub["task"] = task
                sub = sub.rename(columns={task: "label", f"SALI_{task}": "SALI", f"z_SALI_{task}": "z_SALI"})
                cliff_rows.append(sub)
        if cliff_rows:
            pd.concat(cliff_rows, ignore_index=True).to_csv(tables_dir / "activity_cliff_molecules.csv", index=False)
        plot_cliffs(df, cliff_stats, figures_dir, fmt)

    fold_manifest = write_fold_datasets(df, output_dir, masked=False)
    masked_manifest = write_fold_datasets(df, output_dir, masked=True)
    pd.concat([fold_manifest, masked_manifest], ignore_index=True).to_csv(output_dir / "fold_manifest.csv", index=False)

    plot_similarity_hist(df, figures_dir, fmt)
    plot_tmap_chemical_space(df, figures_dir, fmt)
    plot_endpoint_distributions(df, figures_dir, fmt)
    plot_joint_like(df, figures_dir, fmt)
    plot_correlation_heatmap(corr_matrix, figures_dir, fmt)
    plot_cv_summary(cv_stats, figures_dir, fmt)


def write_manifest(args: argparse.Namespace, df: pd.DataFrame, elapsed: float) -> None:
    manifest = {
        "script": Path(__file__).name,
        "elapsed_seconds": elapsed,
        "input_dir": str(args.input_dir),
        "output_dir": str(args.output_dir),
        "results_dir": str(args.results_dir),
        "n_rows": int(len(df)),
        "n_train": int((df["Set"] == "Train").sum()),
        "n_test": int((df["Set"] == "Test").sum()),
        "tasks": TASKS,
        "paper_constants": asdict(CONSTANTS),
        "has_tmap_style_layout": bool({"tmap_x", "tmap_y"}.issubset(df.columns)),
        "adaptation_notes": [
            "ExpansionRx labels use the existing project log transforms from process.py so output folds match prior fine-tuning scripts.",
            "The paper's Potency/ADME split is replaced by ExpansionRx's nine ADMET endpoints.",
            "The paper's 5x5 scaffold CV is reproduced with LogD median stratification and Murcko scaffold groups.",
        ],
    }
    ensure_dirs(args.results_dir)
    (args.results_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    args = parse_args()
    start = time.time()
    figures_dir = args.results_dir / "figures"
    ensure_dirs(args.output_dir, args.results_dir, figures_dir)

    df = load_expansionrx(args.input_dir, args.max_train_rows, args.max_test_rows)
    df, bitvectors, bit_arrays = add_fingerprints(df)
    df = max_tanimoto_to_other_split(df, bitvectors)
    df = add_scaffold_clusters(df)
    df = add_label_coverage(df)
    df = add_agglo_clusters(df, bit_arrays, n_clusters=args.agglo_clusters)
    if not args.skip_cliffs:
        df, _ = add_activity_cliffs(df, bitvectors, TASKS)
    df = add_paper_cv_splits(df)
    if not args.skip_tmap:
        layout = compute_tmap_style_layout(
            bit_arrays,
            n_neighbors=args.tmap_neighbors,
            layout_iterations=args.tmap_layout_iterations,
            n_jobs=args.tmap_n_jobs,
        )
        df = pd.concat([df.reset_index(drop=True), layout.reset_index(drop=True)], axis=1)
    write_outputs(df, args.output_dir, args.results_dir, figures_dir, args.figure_format)
    write_manifest(args, df, elapsed=time.time() - start)
    print(f"Wrote processed dataset to {args.output_dir}")
    print(f"Wrote analysis results to {args.results_dir}")


if __name__ == "__main__":
    main()
