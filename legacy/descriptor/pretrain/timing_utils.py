from __future__ import annotations

import json
from pathlib import Path
import socket
import time
from typing import Any

import numpy as np
import torch
import torch.distributed as dist


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)


class StepTimingLogger:
    def __init__(
        self,
        log_dir: str | None,
        *,
        rank: int,
        local_rank: int,
        world_size: int,
        enabled: bool = True,
        interval: int = 1,
        file_prefix: str = "train",
        sync_cuda: bool = False,
        collect_rank_skew: bool = False,
    ) -> None:
        self.enabled = bool(enabled) and int(interval) > 0 and bool(log_dir)
        self.rank = int(rank)
        self.local_rank = int(local_rank)
        self.world_size = int(world_size)
        self.interval = max(1, int(interval))
        self.sync_cuda = bool(sync_cuda)
        self.collect_rank_skew = bool(collect_rank_skew)
        self.host = socket.gethostname()
        self.path: Path | None = None
        if self.enabled:
            root = Path(str(log_dir)).resolve()
            root.mkdir(parents=True, exist_ok=True)
            self.path = root / f"rank{self.rank}_{file_prefix}_step_timing.jsonl"

    def sync(self, device: torch.device) -> None:
        if not self.enabled or not self.sync_cuda:
            return
        if device.type == "cuda" and torch.cuda.is_available():
            torch.cuda.synchronize(device)

    def duration_skew_ms(self, duration_s: float, device: torch.device) -> float | None:
        if not self.enabled or not self.collect_rank_skew:
            return None
        if not dist.is_available() or not dist.is_initialized():
            return 0.0
        payload = torch.tensor(
            [float(duration_s), float(duration_s)],
            device=device if device.type == "cuda" else torch.device("cpu"),
            dtype=torch.float64,
        )
        dist.all_reduce(payload[:1], op=dist.ReduceOp.MIN)
        dist.all_reduce(payload[1:], op=dist.ReduceOp.MAX)
        return float((payload[1] - payload[0]).item() * 1000.0)

    def log_step(self, payload: dict[str, Any], *, global_step: int) -> None:
        if not self.enabled or self.path is None:
            return
        if int(global_step) % self.interval != 0:
            return
        record = {
            "ts": round(time.time(), 3),
            "host": self.host,
            "rank": self.rank,
            "local_rank": self.local_rank,
            "world_size": self.world_size,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(_json_dumps(record) + "\n")

    def close(self) -> None:
        return None


def _metric_summary(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    arr = np.asarray(values, dtype=np.float64)
    return {
        "count": int(arr.size),
        "mean": float(arr.mean()),
        "median": float(np.median(arr)),
        "p90": float(np.percentile(arr, 90)),
        "p95": float(np.percentile(arr, 95)),
        "min": float(arr.min()),
        "max": float(arr.max()),
        "total": float(arr.sum()),
    }


def summarize_step_timing_logs(log_dir: str | None) -> dict[str, Any] | None:
    if not log_dir:
        return None

    root = Path(str(log_dir)).resolve()
    files = sorted(root.glob("rank*_train_step_timing.jsonl"))
    if not files:
        return None

    per_rank_records: dict[int, list[dict[str, Any]]] = {}
    all_records: list[dict[str, Any]] = []
    for path in files:
        records: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                record = json.loads(line)
                records.append(record)
                all_records.append(record)
        if records:
            per_rank_records[int(records[0]["rank"])] = records

    if not all_records:
        return None

    time_keys = [
        "fetch_s",
        "to_device_s",
        "model_forward_s",
        "loss_compute_s",
        "backward_s",
        "unscale_s",
        "grad_clip_s",
        "optimizer_step_s",
        "scheduler_s",
        "optimizer_s",
        "metrics_s",
        "process_total_s",
        "step_total_s",
    ]
    skew_keys = [
        "fetch_duration_skew_ms",
        "to_device_duration_skew_ms",
        "model_forward_duration_skew_ms",
        "loss_compute_duration_skew_ms",
        "backward_duration_skew_ms",
        "optimizer_duration_skew_ms",
        "step_total_duration_skew_ms",
    ]
    count_keys = [
        "num_graphs",
        "num_nodes",
        "graphs_per_s",
        "nodes_per_s",
        "cuda_mem_allocated_mb",
        "cuda_mem_reserved_mb",
        "cuda_max_mem_allocated_mb",
    ]

    def build_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "steps": int(len(records)),
            "global_step_min": int(min(int(item["global_step"]) for item in records)),
            "global_step_max": int(max(int(item["global_step"]) for item in records)),
            "metrics": {},
            "shares_vs_step_total": {},
        }
        for key in time_keys + skew_keys + count_keys:
            values = [float(item[key]) for item in records if item.get(key) is not None]
            metric = _metric_summary(values)
            if metric is not None:
                payload["metrics"][key] = metric

        share_keys = ["fetch_s", "to_device_s", "model_forward_s", "loss_compute_s", "backward_s", "optimizer_s", "metrics_s"]
        shares = {key: [] for key in share_keys}
        for item in records:
            step_total = float(item.get("step_total_s", 0.0))
            if step_total <= 0:
                continue
            for key in share_keys:
                shares[key].append(float(item.get(key, 0.0)) / step_total)
        for key, values in shares.items():
            metric = _metric_summary(values)
            if metric is not None:
                payload["shares_vs_step_total"][key] = metric
        return payload

    summary = {
        "generated_at": round(time.time(), 3),
        "log_dir": str(root),
        "files": [str(path) for path in files],
        "global": build_summary(all_records),
        "per_rank": {
            str(rank): build_summary(records)
            for rank, records in sorted(per_rank_records.items())
        },
    }

    summary_path = root / "train_step_timing_summary.json"
    summary_path.write_text(_json_dumps(summary) + "\n", encoding="utf-8")

    lines = [
        "# Train Step Timing Summary",
        "",
        f"- steps: {summary['global']['steps']}",
        f"- global_step_range: {summary['global']['global_step_min']} -> {summary['global']['global_step_max']}",
        "",
        "## Mean Time Per Step",
    ]
    for key in time_keys:
        metric = summary["global"]["metrics"].get(key)
        if metric is None:
            continue
        lines.append(f"- {key}: {metric['mean']:.6f}s")
    lines.extend(
        [
            "",
            "## Mean Share Of Step Total",
        ]
    )
    for key in ["fetch_s", "to_device_s", "model_forward_s", "loss_compute_s", "backward_s", "optimizer_s", "metrics_s"]:
        metric = summary["global"]["shares_vs_step_total"].get(key)
        if metric is None:
            continue
        lines.append(f"- {key}: {metric['mean'] * 100.0:.2f}%")
    markdown_path = root / "train_step_timing_summary.md"
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
