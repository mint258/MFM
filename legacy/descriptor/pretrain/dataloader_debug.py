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


LOGGER = logging.getLogger("multitask")
_WORKER_DEBUG_ENV = "MFM_DATALOADER_DEBUG"
_WORKER_DEBUG_DIR_ENV = "MFM_DATALOADER_DEBUG_DIR"
_WORKER_DEBUG_RANK_ENV = "MFM_DATALOADER_DEBUG_RANK"
_WORKER_SLOW_THRESHOLD_ENV = "MFM_DATALOADER_SLOW_FETCH_S"


@dataclass
class DataLoaderDebugConfig:
    enabled: bool = False
    interval_s: float = 30.0
    stall_threshold_s: float = 120.0
    timeout_s: float = 0.0
    slow_fetch_threshold_s: float = 10.0
    log_dir: str | None = None


def _safe_qsize(queue_obj) -> int | None:
    if queue_obj is None or not hasattr(queue_obj, "qsize"):
        return None
    try:
        return int(queue_obj.qsize())
    except (NotImplementedError, OSError, AttributeError):
        return None


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


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)


def _debug_file_path(log_dir: str | None, *, rank: str, pid: int, suffix: str) -> Path | None:
    if not log_dir:
        return None
    root = Path(log_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root / f"rank{rank}_{suffix}_{pid}.jsonl"


def worker_debug_enabled() -> bool:
    return os.getenv(_WORKER_DEBUG_ENV, "0") == "1"


def worker_slow_threshold_s() -> float:
    try:
        return float(os.getenv(_WORKER_SLOW_THRESHOLD_ENV, "10.0"))
    except ValueError:
        return 10.0


def worker_debug_event(event: str, **fields) -> None:
    if not worker_debug_enabled():
        return

    log_dir = os.getenv(_WORKER_DEBUG_DIR_ENV)
    rank = os.getenv(_WORKER_DEBUG_RANK_ENV, "na")
    pid = os.getpid()
    payload = {
        "ts": round(time.time(), 3),
        "host": socket.gethostname(),
        "rank": rank,
        "pid": pid,
        "event": event,
        **fields,
    }
    path = _debug_file_path(log_dir, rank=rank, pid=pid, suffix="worker")
    if path is None:
        return
    with path.open("a", encoding="utf-8") as handle:
        handle.write(_json_dumps(payload) + "\n")


def configure_worker_debug_env(cfg: DataLoaderDebugConfig, *, rank: int) -> None:
    if not cfg.enabled:
        os.environ.pop(_WORKER_DEBUG_ENV, None)
        os.environ.pop(_WORKER_DEBUG_DIR_ENV, None)
        os.environ.pop(_WORKER_DEBUG_RANK_ENV, None)
        os.environ.pop(_WORKER_SLOW_THRESHOLD_ENV, None)
        return

    os.environ[_WORKER_DEBUG_ENV] = "1"
    if cfg.log_dir:
        Path(cfg.log_dir).resolve().mkdir(parents=True, exist_ok=True)
        os.environ[_WORKER_DEBUG_DIR_ENV] = str(Path(cfg.log_dir).resolve())
    os.environ[_WORKER_DEBUG_RANK_ENV] = str(rank)
    os.environ[_WORKER_SLOW_THRESHOLD_ENV] = str(float(cfg.slow_fetch_threshold_s))


class DataLoaderWatchdog:
    def __init__(
        self,
        iterator,
        *,
        cfg: DataLoaderDebugConfig,
        rank: int,
        desc: str,
        loader_name: str,
        is_main_process: bool,
    ) -> None:
        self.iterator = iterator
        self.cfg = cfg
        self.rank = int(rank)
        self.desc = desc
        self.loader_name = loader_name
        self.is_main_process = bool(is_main_process)
        self._state = {
            "phase": "init",
            "batch_index": 0,
            "global_step": 0,
            "optimizer_steps": 0,
            "last_batch_wait_s": None,
            "last_batch_process_s": None,
            "last_batch_graphs": None,
            "last_event_monotonic": time.monotonic(),
        }
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread = None
        self._log_path = None

        if not self.cfg.enabled:
            return

        if self.cfg.log_dir:
            root = Path(self.cfg.log_dir).resolve()
            root.mkdir(parents=True, exist_ok=True)
            self._log_path = root / f"rank{self.rank}_watchdog.jsonl"

        self._thread = threading.Thread(target=self._run, name=f"dataloader-watchdog-rank{self.rank}", daemon=True)
        self._thread.start()

    def _snapshot_iterator(self) -> dict[str, Any]:
        workers_payload = []
        workers = getattr(self.iterator, "_workers", None) or []
        for worker in workers:
            info = {
                "pid": int(getattr(worker, "pid", -1)),
                "alive": bool(worker.is_alive()) if hasattr(worker, "is_alive") else None,
                "exitcode": getattr(worker, "exitcode", None),
            }
            if info["pid"] and info["pid"] > 0:
                info.update(_read_proc_snapshot(info["pid"]))
            workers_payload.append(info)

        pin_thread = getattr(self.iterator, "_pin_memory_thread", None)
        return {
            "iterator_class": type(self.iterator).__name__,
            "tasks_outstanding": getattr(self.iterator, "_tasks_outstanding", None),
            "send_idx": getattr(self.iterator, "_send_idx", None),
            "rcvd_idx": getattr(self.iterator, "_rcvd_idx", None),
            "num_yielded": getattr(self.iterator, "_num_yielded", None),
            "data_queue_size": _safe_qsize(getattr(self.iterator, "_data_queue", None)),
            "worker_result_queue_size": _safe_qsize(getattr(self.iterator, "_worker_result_queue", None)),
            "index_queue_sizes": [_safe_qsize(q) for q in (getattr(self.iterator, "_index_queues", None) or [])],
            "workers_status": list(getattr(self.iterator, "_workers_status", [])) if hasattr(self.iterator, "_workers_status") else None,
            "pin_memory_thread_alive": pin_thread.is_alive() if pin_thread is not None and hasattr(pin_thread, "is_alive") else None,
            "workers": workers_payload,
        }

    def _emit(self, event: str, *, level: int = logging.INFO, extra: dict[str, Any] | None = None) -> None:
        with self._lock:
            state = dict(self._state)
        since_last = time.monotonic() - float(state["last_event_monotonic"])
        payload = {
            "event": event,
            "ts": round(time.time(), 3),
            "host": socket.gethostname(),
            "rank": self.rank,
            "loader_name": self.loader_name,
            "desc": self.desc,
            "phase": state["phase"],
            "batch_index": state["batch_index"],
            "global_step": state["global_step"],
            "optimizer_steps": state["optimizer_steps"],
            "seconds_since_last_event": round(since_last, 3),
            "last_batch_wait_s": state["last_batch_wait_s"],
            "last_batch_process_s": state["last_batch_process_s"],
            "last_batch_graphs": state["last_batch_graphs"],
            "iterator": self._snapshot_iterator(),
        }
        if extra:
            payload.update(extra)

        if self.is_main_process or level >= logging.WARNING:
            LOGGER.log(level, "[dataloader-debug] %s", _json_dumps(payload))
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

    def waiting_for_batch(self, *, batch_index: int, global_step: int, optimizer_steps: int) -> None:
        if not self.cfg.enabled:
            return
        with self._lock:
            self._state.update(
                {
                    "phase": "waiting_batch",
                    "batch_index": int(batch_index),
                    "global_step": int(global_step),
                    "optimizer_steps": int(optimizer_steps),
                    "last_event_monotonic": time.monotonic(),
                }
            )

    def batch_fetched(self, *, wait_s: float, batch_index: int, global_step: int, optimizer_steps: int, num_graphs: int | None) -> None:
        if not self.cfg.enabled:
            return
        with self._lock:
            self._state.update(
                {
                    "phase": "processing_batch",
                    "batch_index": int(batch_index),
                    "global_step": int(global_step),
                    "optimizer_steps": int(optimizer_steps),
                    "last_batch_wait_s": round(float(wait_s), 3),
                    "last_batch_graphs": None if num_graphs is None else int(num_graphs),
                    "last_event_monotonic": time.monotonic(),
                }
            )
        if wait_s >= float(self.cfg.slow_fetch_threshold_s):
            self._emit(
                "slow_batch_fetch",
                level=logging.WARNING,
                extra={"wait_s": round(float(wait_s), 3), "stall_detected": 0},
            )

    def batch_processed(self, *, process_s: float, batch_index: int, global_step: int, optimizer_steps: int) -> None:
        if not self.cfg.enabled:
            return
        with self._lock:
            self._state.update(
                {
                    "phase": "batch_complete",
                    "batch_index": int(batch_index),
                    "global_step": int(global_step),
                    "optimizer_steps": int(optimizer_steps),
                    "last_batch_process_s": round(float(process_s), 3),
                    "last_event_monotonic": time.monotonic(),
                }
            )

    def exception(self, *, event: str, exc: BaseException, batch_index: int, global_step: int, optimizer_steps: int) -> None:
        if not self.cfg.enabled:
            return
        with self._lock:
            self._state.update(
                {
                    "phase": "exception",
                    "batch_index": int(batch_index),
                    "global_step": int(global_step),
                    "optimizer_steps": int(optimizer_steps),
                    "last_event_monotonic": time.monotonic(),
                }
            )
        self._emit(event, level=logging.ERROR, extra={"exception": repr(exc)})

    def close(self) -> None:
        if self._thread is None:
            return
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        self._emit("watchdog_stop", level=logging.INFO)
