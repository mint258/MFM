import argparse
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_TASKS = [
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


def _read_text(path: Path) -> str:
    encodings = ["utf-8", "utf-8-sig", "gbk", "latin-1"]
    for enc in encodings:
        try:
            return path.read_text(encoding=enc)
        except Exception:
            continue
    # last resort
    return path.read_bytes().decode("utf-8", errors="ignore")


def _to_float(text: str) -> float:
    t = text.strip()
    if t.lower() in {"nan", "-nan", "+nan"}:
        return float("nan")
    if t.lower() in {"inf", "+inf"}:
        return float("inf")
    if t.lower() == "-inf":
        return float("-inf")
    return float(t)


def _parse_cross_fold_summary(lines: List[str]) -> Dict[str, Dict[str, Tuple[float, float]]]:
    """
    Parse blocks like:
      Cross-fold summary
      LogD
        Test MAE:  0.123 +/- 0.01
        Test RMSE: ...
        Test R2:   0.456 +/- 0.02
    """
    out: Dict[str, Dict[str, Tuple[float, float]]] = {}
    in_summary = False
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line == "Cross-fold summary":
            in_summary = True
            i += 1
            continue
        if not in_summary:
            i += 1
            continue
        # task line: non-empty, no colon, not starting with Fold/[
        if line and (":" not in line) and (not line.startswith("Fold")) and (not line.startswith("[")):
            task = line
            mae_mean = mae_std = r2_mean = r2_std = None
            j = i + 1
            while j < len(lines):
                s = lines[j].strip()
                if not s:
                    j += 1
                    continue
                if (":" not in s) and (not s.startswith("Test")):
                    break
                m_mae = re.search(r"Test\s+MAE:\s*([\-+0-9.eEinfnaINFNA]+)\s*\+/-\s*([\-+0-9.eEinfnaINFNA]+)", s)
                if m_mae:
                    mae_mean = _to_float(m_mae.group(1))
                    mae_std = _to_float(m_mae.group(2))
                m_r2 = re.search(r"Test\s+R2:\s*([\-+0-9.eEinfnaINFNA]+)\s*\+/-\s*([\-+0-9.eEinfnaINFNA]+)", s)
                if m_r2:
                    r2_mean = _to_float(m_r2.group(1))
                    r2_std = _to_float(m_r2.group(2))
                j += 1
            if mae_mean is not None or r2_mean is not None:
                out[task] = {
                    "mae": (float("nan") if mae_mean is None else mae_mean, float("nan") if mae_std is None else mae_std),
                    "r2": (float("nan") if r2_mean is None else r2_mean, float("nan") if r2_std is None else r2_std),
                }
            i = j
            continue
        i += 1
    return out


def _parse_fold_test_blocks(lines: List[str]) -> Dict[str, Dict[str, Tuple[float, float]]]:
    """
    Parse repeated fold blocks like:
      [Fold 2] Test metrics
      LogD
        MAE: 0.33
        RMSE: ...
        R2: 0.86
    and aggregate mean/std over folds.
    """
    block_heads = [
        re.compile(r"^\[Fold\s+\d+\]\s+Test\s+metrics\s*$"),
        re.compile(r"^Fold\s+\d+\s+metrics\s*$"),
    ]

    per_task_mae: Dict[str, List[float]] = {}
    per_task_r2: Dict[str, List[float]] = {}

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not any(pat.match(line) for pat in block_heads):
            i += 1
            continue

        i += 1
        while i < len(lines):
            task_line = lines[i].strip()
            if not task_line:
                i += 1
                continue
            if task_line.startswith("[") or re.match(r"^Fold\s+\d+", task_line) or task_line == "Training complete." or task_line == "Cross-fold summary":
                break
            if ":" in task_line:
                i += 1
                continue

            task = task_line
            mae_val: Optional[float] = None
            r2_val: Optional[float] = None
            j = i + 1
            while j < len(lines):
                s = lines[j].strip()
                if not s:
                    j += 1
                    continue
                # next task or new section
                if (":" not in s) and (not s.startswith("MAE")) and (not s.startswith("RMSE")) and (not s.startswith("R2")):
                    break
                m_mae = re.match(r"MAE:\s*([\-+0-9.eEinfnaINFNA]+)", s)
                if m_mae:
                    mae_val = _to_float(m_mae.group(1))
                m_r2 = re.match(r"R2:\s*([\-+0-9.eEinfnaINFNA]+)", s)
                if m_r2:
                    r2_val = _to_float(m_r2.group(1))
                j += 1

            if mae_val is not None:
                per_task_mae.setdefault(task, []).append(mae_val)
            if r2_val is not None:
                per_task_r2.setdefault(task, []).append(r2_val)
            i = j

    out: Dict[str, Dict[str, Tuple[float, float]]] = {}
    tasks = sorted(set(per_task_mae.keys()) | set(per_task_r2.keys()))
    for t in tasks:
        mae_vals = np.asarray(per_task_mae.get(t, [np.nan]), dtype=float)
        r2_vals = np.asarray(per_task_r2.get(t, [np.nan]), dtype=float)
        out[t] = {
            "mae": (float(np.nanmean(mae_vals)), float(np.nanstd(mae_vals))),
            "r2": (float(np.nanmean(r2_vals)), float(np.nanstd(r2_vals))),
        }
    return out


def parse_test_metrics_from_log(path: Path) -> Dict[str, Dict[str, Tuple[float, float]]]:
    text = _read_text(path)
    lines = text.splitlines()

    # Prefer explicit cross-fold summary if available.
    summary = _parse_cross_fold_summary(lines)
    if summary:
        return summary

    # Fallback to aggregating per-fold test blocks.
    fold_data = _parse_fold_test_blocks(lines)
    if fold_data:
        return fold_data

    raise ValueError(f"Failed to parse test metrics from log: {path}")


def _nature_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.linewidth": 1.0,
            "axes.facecolor": "white",
            "figure.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "grid.color": "#E6E6E6",
            "grid.linewidth": 0.8,
            "grid.linestyle": "-",
            "axes.grid": True,
            "axes.axisbelow": True,
        }
    )


def _red_blue_palette(n: int) -> List[str]:
    red = np.array([220, 53, 69], dtype=float) / 255.0
    blue = np.array([33, 102, 172], dtype=float) / 255.0
    if n <= 1:
        return ["#DD3545"]
    if n == 2:
        return ["#DD3545", "#2166AC"]
    colors = []
    for i in range(n):
        alpha = i / (n - 1)
        rgb = (1 - alpha) * red + alpha * blue
        colors.append(tuple(rgb))
    return colors


def _plot_grouped_bar(
    metric_key: str,
    metric_label: str,
    tasks: List[str],
    labels: List[str],
    series_values: Dict[str, Dict[str, Dict[str, Tuple[float, float]]]],
    out_path: Path,
) -> None:
    _nature_style()
    n_tasks = len(tasks)
    n_series = len(labels)

    x = np.arange(n_tasks, dtype=float)
    total_width = 0.82
    bar_w = total_width / max(1, n_series)
    start = -total_width / 2 + bar_w / 2

    fig_w = max(12, 0.75 * n_tasks + 3)
    fig, ax = plt.subplots(figsize=(fig_w, 4.6), dpi=300)

    colors = _red_blue_palette(n_series)
    for i, label in enumerate(labels):
        means = []
        stds = []
        for task in tasks:
            val = series_values[label].get(task, {}).get(metric_key, (np.nan, np.nan))
            means.append(val[0])
            stds.append(val[1])

        xpos = x + start + i * bar_w
        ax.bar(
            xpos,
            means,
            width=bar_w * 0.95,
            color=colors[i],
            edgecolor="white",
            linewidth=0.5,
            label=label,
            zorder=3,
        )
        arr_std = np.asarray(stds, dtype=float)
        arr_mean = np.asarray(means, dtype=float)
        valid = np.isfinite(arr_mean) & np.isfinite(arr_std)
        if np.any(valid):
            ax.errorbar(
                xpos[valid],
                arr_mean[valid],
                yerr=arr_std[valid],
                fmt="none",
                ecolor="black",
                elinewidth=0.7,
                capsize=1.8,
                capthick=0.7,
                zorder=4,
            )

    ax.set_xticks(x)
    ax.set_xticklabels(tasks, rotation=35, ha="right")
    ax.set_ylabel(metric_label)
    ax.set_xlabel("Tasks")
    ax.legend(frameon=False, ncol=min(4, len(labels)), loc="upper left", bbox_to_anchor=(0.0, 1.02))

    if metric_key == "r2":
        ax.axhline(0.0, color="#999999", linewidth=0.8, zorder=1)
        ax.set_ylim(bottom=min(-0.2, float(np.nanmin([series_values[l].get(t, {}).get("r2", (np.nan, np.nan))[0] for l in labels for t in tasks])) - 0.05))

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    plt.close(fig)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser("Parse benchmark logs and plot test MAE/R2 in Nature style")
    p.add_argument("--logs", nargs="+", required=True, help="Input log file paths")
    p.add_argument("--labels", nargs="+", required=True, help="Manual names for each log (same order as --logs)")
    p.add_argument("--tasks", nargs="+", default=None, help="Task order. Default: tasks found in first log, fallback to ADMET default list")
    p.add_argument("--output_dir", type=str, default="logs/analysis_figs")
    p.add_argument("--prefix", type=str, default="benchmark_test")
    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    log_paths = [Path(x) for x in args.logs]
    labels = [str(x) for x in args.labels]
    if len(log_paths) != len(labels):
        raise ValueError("--logs and --labels must have the same length")

    metrics_by_label: Dict[str, Dict[str, Dict[str, Tuple[float, float]]]] = {}
    for label, path in zip(labels, log_paths):
        if not path.exists():
            raise FileNotFoundError(f"Log file not found: {path}")
        metrics_by_label[label] = parse_test_metrics_from_log(path)

    if args.tasks:
        tasks = list(args.tasks)
    else:
        first = metrics_by_label[labels[0]]
        if first:
            tasks = list(first.keys())
        else:
            tasks = list(DEFAULT_TASKS)

    # fill with default task order if first log lacks full set
    if set(DEFAULT_TASKS).issubset(set().union(*[set(v.keys()) for v in metrics_by_label.values()])):
        # Keep user-specified order if provided; otherwise prefer canonical ADMET order.
        if not args.tasks:
            tasks = [t for t in DEFAULT_TASKS if any(t in metrics_by_label[l] for l in labels)]

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    mae_png = out_dir / f"{args.prefix}_mae.png"
    r2_png = out_dir / f"{args.prefix}_r2.png"
    summary_csv = out_dir / f"{args.prefix}_summary.csv"

    _plot_grouped_bar("mae", "Test MAE", tasks, labels, metrics_by_label, mae_png)
    _plot_grouped_bar("r2", "Test R2", tasks, labels, metrics_by_label, r2_png)

    rows = []
    for label in labels:
        for task in tasks:
            mae_mean, mae_std = metrics_by_label[label].get(task, {}).get("mae", (np.nan, np.nan))
            r2_mean, r2_std = metrics_by_label[label].get(task, {}).get("r2", (np.nan, np.nan))
            rows.append(
                {
                    "label": label,
                    "task": task,
                    "test_mae_mean": mae_mean,
                    "test_mae_std": mae_std,
                    "test_r2_mean": r2_mean,
                    "test_r2_std": r2_std,
                }
            )
    pd.DataFrame(rows).to_csv(summary_csv, index=False)

    print(f"Saved MAE figure: {mae_png}")
    print(f"Saved R2 figure:  {r2_png}")
    print(f"Saved summary:    {summary_csv}")


if __name__ == "__main__":
    main()
