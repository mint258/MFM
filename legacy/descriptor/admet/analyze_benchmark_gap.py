import argparse
import re
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


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


def parse_cross_summary_blocks(nohup_path: Path) -> List[Tuple[int, Dict[str, float]]]:
    lines = nohup_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    idx = [i for i, line in enumerate(lines) if line.strip() == "Cross-fold summary"]
    blocks: List[Tuple[int, Dict[str, float]]] = []

    for i in idx:
        block: Dict[str, float] = {}
        task = None
        j = i + 1
        while j < len(lines):
            line = lines[j].strip()
            if not line or line.startswith("Saved CV predictions to:") or line.startswith("Traceback"):
                break

            task_match = re.match(r"^(Log\w.*)$", line)
            mae_match = re.match(r"^Test MAE:\s*([0-9eE+\-.]+)\s*\+/-\s*([0-9eE+\-.]+)$", line)
            if task_match:
                task = task_match.group(1)
            elif mae_match and task is not None:
                block[task] = float(mae_match.group(1))
            j += 1
        blocks.append((i + 1, block))
    return blocks


def pick_mt_and_st(blocks: List[Tuple[int, Dict[str, float]]]) -> Tuple[Tuple[int, Dict[str, float]], Dict[str, Tuple[int, float]]]:
    mt_block = None
    for line_no, metrics in blocks:
        if len(metrics) >= len(TASKS):
            mt_block = (line_no, metrics)
            break
    if mt_block is None:
        raise ValueError("Could not find a multi-task cross-fold summary in nohup log.")

    st: Dict[str, Tuple[int, float]] = {}
    for line_no, metrics in blocks:
        if len(metrics) == 1:
            task = next(iter(metrics.keys()))
            st[task] = (line_no, float(metrics[task]))
    return mt_block, st


def build_gap_table(
    ours: Dict[str, float], benchmark_row: pd.Series, benchmark_model_name: str
) -> pd.DataFrame:
    rows = []
    for task in TASKS:
        ours_mae = float(ours[task])
        bench_mae = float(benchmark_row[f"{task}_mae"])
        gap_pct = (ours_mae - bench_mae) / bench_mae * 100.0
        rows.append(
            {
                "task": task,
                "ours_mae": ours_mae,
                "benchmark_model": benchmark_model_name,
                "benchmark_mae": bench_mae,
                "gap_pct": gap_pct,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser("Analyze MFM vs benchmark gaps using nohup.out summaries.")
    parser.add_argument("--nohup", type=str, default="nohup.out")
    parser.add_argument("--benchmark_csv", type=str, default="chemprop_results/mae.csv")
    parser.add_argument("--mt_benchmark", type=str, default="Chemprop_MT_hpo")
    parser.add_argument("--st_benchmark", type=str, default="Chemprop_ST_hpo")
    args = parser.parse_args()

    nohup_path = Path(args.nohup)
    if not nohup_path.exists():
        raise FileNotFoundError(f"Missing nohup log: {nohup_path}")

    blocks = parse_cross_summary_blocks(nohup_path)
    mt_block, st_blocks = pick_mt_and_st(blocks)
    mt_line, mt_metrics = mt_block

    missing_st = [t for t in TASKS if t not in st_blocks]
    if missing_st:
        raise ValueError(f"Missing ST summaries in nohup for tasks: {missing_st}")
    st_metrics = {t: st_blocks[t][1] for t in TASKS}

    bench = pd.read_csv(args.benchmark_csv)
    mt_row = bench[bench["model"] == args.mt_benchmark]
    st_row = bench[bench["model"] == args.st_benchmark]
    if mt_row.empty:
        raise ValueError(f"Model not found in benchmark csv: {args.mt_benchmark}")
    if st_row.empty:
        raise ValueError(f"Model not found in benchmark csv: {args.st_benchmark}")
    mt_row = mt_row.iloc[0]
    st_row = st_row.iloc[0]

    mt_gap = build_gap_table(mt_metrics, mt_row, args.mt_benchmark)
    st_gap = build_gap_table(st_metrics, st_row, args.st_benchmark)

    print(f"Detected MT summary at nohup line: {mt_line}")
    print("\nMT gap table (sorted by gap_pct desc):")
    print(mt_gap.sort_values("gap_pct", ascending=False).to_string(index=False))
    print(
        f"\nMT mean gap vs {args.mt_benchmark}: {mt_gap['gap_pct'].mean():.2f}% "
        f"(median {mt_gap['gap_pct'].median():.2f}%)"
    )

    print("\nST gap table (sorted by gap_pct desc):")
    print(st_gap.sort_values("gap_pct", ascending=False).to_string(index=False))
    print(
        f"\nST mean gap vs {args.st_benchmark}: {st_gap['gap_pct'].mean():.2f}% "
        f"(median {st_gap['gap_pct'].median():.2f}%)"
    )

    text = nohup_path.read_text(encoding="utf-8", errors="ignore")
    hf_missing_count = text.count("ModuleNotFoundError: No module named 'huggingface_hub'")
    if hf_missing_count > 0:
        print(f"\nDetected huggingface_hub missing error count: {hf_missing_count}")


if __name__ == "__main__":
    main()
