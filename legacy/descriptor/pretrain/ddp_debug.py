from __future__ import annotations

from dataclasses import dataclass
import json
import logging
import os
from pathlib import Path
import socket
import threading
import time
from typing import Any

import torch
import torch.distributed as dist


LOGGER = logging.getLogger("multitask")


@dataclass
class DDPDebugConfig:
    enabled: bool = False
    interval_s: float = 15.0
    stall_threshold_s: float = 60.0
    log_dir: str | None = None
    grad_sample_size: int = 12


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)


def _read_proc_snapshot(pid: int) -> dict[str, Any]:
    proc_dir = Path("/proc") / str(pid)
    if not proc_dir.exists():
        return {}

    snapshot: dict[str, Any] = {}
    stat_path = proc_dir / "stat"
    try:
        text = stat_path.read_text(encoding="utf-8")
        _, rest = text.rsplit(")", 1)
        parts = rest.strip().split()
        if len(parts) >= 22:
            snapshot["state"] = parts[0]
            snapshot["ppid"] = int(parts[1])
            snapshot["num_threads"] = int(parts[17])
            snapshot["rss_pages"] = int(parts[21])
    except Exception:
        pass

    wchan_path = proc_dir / "wchan"
    try:
        snapshot["wchan"] = wchan_path.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return snapshot


def _cuda_snapshot(device: torch.device) -> dict[str, Any]:
    if device.type != "cuda" or not torch.cuda.is_available():
        return {}

    try:
        current_device = device.index if device.index is not None else torch.cuda.current_device()
        return {
            "cuda_device_index": int(current_device),
            "cuda_mem_allocated_mb": round(torch.cuda.memory_allocated(current_device) / (1024**2), 2),
            "cuda_mem_reserved_mb": round(torch.cuda.memory_reserved(current_device) / (1024**2), 2),
            "cuda_max_mem_allocated_mb": round(torch.cuda.max_memory_allocated(current_device) / (1024**2), 2),
        }
    except Exception:
        return {}


def _ddp_snapshot(model) -> dict[str, Any]:
    payload = {
        "dist_initialized": int(_is_dist_ready()),
        "torch_distributed_debug": os.environ.get("TORCH_DISTRIBUTED_DEBUG", ""),
        "nccl_debug": os.environ.get("NCCL_DEBUG", ""),
        "nccl_async_error_handling": os.environ.get("NCCL_ASYNC_ERROR_HANDLING", ""),
    }
    if _is_dist_ready():
        try:
            payload["backend"] = dist.get_backend()
        except Exception:
            pass
    if not hasattr(model, "module"):
        payload["wrapped_ddp"] = 0
        return payload
    payload.update(
        {
            "wrapped_ddp": 1,
            "require_backward_grad_sync": int(getattr(model, "require_backward_grad_sync", True)),
            "find_unused_parameters": int(bool(getattr(model, "find_unused_parameters", False))),
            "broadcast_buffers": int(bool(getattr(model, "broadcast_buffers", False))),
            "static_graph": int(bool(getattr(model, "static_graph", getattr(model, "_static_graph", False)))),
        }
    )
    return payload


def _is_dist_ready() -> bool:
    return dist.is_available() and dist.is_initialized()


class DDPPhaseWatchdog:
    def __init__(
        self,
        *,
        cfg: DDPDebugConfig,
        rank: int,
        world_size: int,
        local_rank: int,
        device: torch.device,
        desc: str,
        model,
        is_main_process: bool,
    ) -> None:
        self.cfg = cfg
        self.rank = int(rank)
        self.world_size = int(world_size)
        self.local_rank = int(local_rank)
        self.device = device
        self.desc = desc
        self.model = model
        self.is_main_process = bool(is_main_process)
        self.pid = os.getpid()
        self.host = socket.gethostname()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._log_path = None
        self._state = {
            "phase": "init",
            "batch_index": 0,
            "global_step": 0,
            "optimizer_steps": 0,
            "epoch": None,
            "stage": None,
            "last_event_monotonic": time.monotonic(),
            "last_phase_duration_s": None,
            "last_loss_total": None,
            "last_num_graphs": None,
            "last_num_nodes": None,
        }

        if not self.cfg.enabled:
            return

        if self.cfg.log_dir:
            root = Path(self.cfg.log_dir).resolve()
            root.mkdir(parents=True, exist_ok=True)
            self._log_path = root / f"rank{self.rank}_ddp_phase.jsonl"

        self._thread = threading.Thread(target=self._run, name=f"ddp-phase-watchdog-rank{self.rank}", daemon=True)
        self._thread.start()
        self.mark("watchdog_start", emit=True)

    def _emit(self, event: str, *, level: int = logging.INFO, extra: dict[str, Any] | None = None) -> None:
        with self._lock:
            state = dict(self._state)
        payload = {
            "event": event,
            "ts": round(time.time(), 3),
            "host": self.host,
            "pid": self.pid,
            "rank": self.rank,
            "local_rank": self.local_rank,
            "world_size": self.world_size,
            "desc": self.desc,
            "phase": state["phase"],
            "batch_index": state["batch_index"],
            "global_step": state["global_step"],
            "optimizer_steps": state["optimizer_steps"],
            "epoch": state["epoch"],
            "stage": state["stage"],
            "seconds_since_last_event": round(time.monotonic() - float(state["last_event_monotonic"]), 3),
            "last_phase_duration_s": state["last_phase_duration_s"],
            "last_loss_total": state["last_loss_total"],
            "last_num_graphs": state["last_num_graphs"],
            "last_num_nodes": state["last_num_nodes"],
            "process": _read_proc_snapshot(self.pid),
            "ddp": _ddp_snapshot(self.model),
        }
        payload.update(_cuda_snapshot(self.device))
        if extra:
            payload.update(extra)

        if self.is_main_process or level >= logging.WARNING:
            LOGGER.log(level, "[ddp-debug] %s", _json_dumps(payload))
        if self._log_path is not None:
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(_json_dumps(payload) + "\n")

    def _run(self) -> None:
        while not self._stop_event.wait(max(1.0, float(self.cfg.interval_s))):
            with self._lock:
                since_last = time.monotonic() - float(self._state["last_event_monotonic"])
            stalled = since_last >= float(self.cfg.stall_threshold_s) > 0
            self._emit(
                "stall_watch" if stalled else "heartbeat",
                level=logging.WARNING if stalled else logging.INFO,
                extra={"stall_detected": int(stalled)},
            )

    def mark(
        self,
        phase: str,
        *,
        batch_index: int | None = None,
        global_step: int | None = None,
        optimizer_steps: int | None = None,
        epoch: int | None = None,
        stage: int | None = None,
        duration_s: float | None = None,
        loss_total: float | None = None,
        num_graphs: int | None = None,
        num_nodes: int | None = None,
        emit: bool = False,
        level: int = logging.INFO,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not self.cfg.enabled:
            return
        with self._lock:
            self._state["phase"] = str(phase)
            if batch_index is not None:
                self._state["batch_index"] = int(batch_index)
            if global_step is not None:
                self._state["global_step"] = int(global_step)
            if optimizer_steps is not None:
                self._state["optimizer_steps"] = int(optimizer_steps)
            if epoch is not None:
                self._state["epoch"] = int(epoch)
            if stage is not None:
                self._state["stage"] = int(stage)
            if duration_s is not None:
                self._state["last_phase_duration_s"] = round(float(duration_s), 4)
            if loss_total is not None:
                self._state["last_loss_total"] = float(loss_total)
            if num_graphs is not None:
                self._state["last_num_graphs"] = int(num_graphs)
            if num_nodes is not None:
                self._state["last_num_nodes"] = int(num_nodes)
            self._state["last_event_monotonic"] = time.monotonic()

        if emit:
            self._emit(
                "phase_transition",
                level=level,
                extra={"new_phase": str(phase), **(extra or {})},
            )

    def log_grad_summary(self, model, *, batch_index: int, global_step: int, optimizer_steps: int, epoch: int | None, stage: int | None) -> None:
        if not self.cfg.enabled:
            return

        missing = []
        total = 0
        with_grad = 0
        nan_grad = 0
        for name, param in model.named_parameters():
            if not param.requires_grad:
                continue
            total += 1
            grad = param.grad
            if grad is None:
                if len(missing) < int(self.cfg.grad_sample_size):
                    missing.append(name)
                continue
            with_grad += 1
            if not torch.isfinite(grad).all():
                nan_grad += 1

        self.mark(
            "grad_summary",
            batch_index=batch_index,
            global_step=global_step,
            optimizer_steps=optimizer_steps,
            epoch=epoch,
            stage=stage,
        )
        self._emit(
            "grad_summary",
            level=logging.INFO,
            extra={
                "total_trainable_params": total,
                "with_grad_params": with_grad,
                "missing_grad_params": total - with_grad,
                "nonfinite_grad_params": nan_grad,
                "missing_grad_names": missing,
            },
        )

    def exception(self, *, event: str, exc: BaseException, batch_index: int, global_step: int, optimizer_steps: int, epoch: int | None, stage: int | None) -> None:
        if not self.cfg.enabled:
            return
        self.mark(
            "exception",
            batch_index=batch_index,
            global_step=global_step,
            optimizer_steps=optimizer_steps,
            epoch=epoch,
            stage=stage,
        )
        self._emit(event, level=logging.ERROR, extra={"exception": repr(exc)})

    def close(self) -> None:
        if not self.cfg.enabled:
            return
        if self._thread is not None:
            self._stop_event.set()
            self._thread.join(timeout=2.0)
        self._emit("watchdog_stop", level=logging.INFO)
