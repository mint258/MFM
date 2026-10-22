"""Owned GPU selection and persistent diagnostics; accepted shared-GPU risk."""
from contextlib import contextmanager
import csv
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

from runtime import PROJECT, ROOT, assert_allocation, save


def query(args):
    return subprocess.check_output(args, stdin=subprocess.DEVNULL, text=True, timeout=30)


@contextmanager
def gpu_runtime(name):
    assert_allocation(gpu=True)
    applications = query(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory", "--format=csv,noheader,nounits"])
    busy = {line.split(",")[0].strip() for line in applications.splitlines() if line.strip()}
    rows = list(csv.reader(query(["nvidia-smi", "--query-gpu=uuid,name,memory.total,memory.free", "--format=csv,noheader,nounits"]).splitlines()))
    lock_root = PROJECT / "docs/phase1/evidence/stage46_shared_gpu_launch/.own_gpu_uuid_locks"
    lock_root.mkdir(exist_ok=True)
    lock = selected = None
    for row in rows:
        if row[0].strip() in busy or int(row[3]) < 0.95 * int(row[2]):
            continue
        trial = (lock_root / (row[0].strip() + ".lock")).open("a")
        try:
            fcntl.flock(trial, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            trial.close()
            continue
        lock, selected = trial, row
        break
    if selected is None:
        raise RuntimeError("No idle, own-unlocked GPU; no foreign tasks changed")
    os.environ["CUDA_VISIBLE_DEVICES"] = selected[0].strip()
    os.environ["WANDB_MODE"] = "offline"
    job = os.environ["SLURM_JOB_ID"]
    output = ROOT / "diagnostics" / name / ("job_" + job)
    output.mkdir(parents=True, exist_ok=False)
    status = {"status": "RUNNING", "job_id": job, "name": name, "node": socket.gethostname(),
              "gpu_uuid": selected[0].strip(), "gpu_model": selected[1].strip(),
              "gpu_protection": "USER_ACCEPTED_SHARED_GPU_RISK",
              "gpu_memory_total_MiB": int(selected[2]), "gpu_memory_reserve_MiB": 2048,
              "host_RSS_cap_GiB": 52, "run_output_cap_bytes": 2 << 30,
              "original_lmdb_written": False, "new_lmdb_created": False}
    save(output / "runtime.json", status)
    started = time.monotonic()
    try:
        yield output, status
        status["status"] = "COMPUTATION_RETURNED"
    except BaseException as exc:
        status["status"], status["error"] = "FAILED", repr(exc)
        raise
    finally:
        status["elapsed_seconds"] = time.monotonic() - started
        save(output / "runtime.json", status)
        lock.close()


def check_memory(torch, status):
    allocated = torch.cuda.memory_reserved()
    assert allocated < (status["gpu_memory_total_MiB"] - status["gpu_memory_reserve_MiB"]) * (1 << 20), "GPU_MEMORY_CAP"
    import psutil
    parent = psutil.Process()
    owned_pids = {parent.pid}
    total = parent.memory_info().rss
    for child in parent.children(recursive=True):
        try:
            total += child.memory_info().rss
            owned_pids.add(child.pid)
        except psutil.NoSuchProcess:
            pass
    assert total < 52 * (1 << 30), "HOST_RSS_CAP"
    apps = list(csv.reader(query(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory", "--format=csv,noheader,nounits"]).splitlines()))
    foreign = [row for row in apps if row[0].strip() == status["gpu_uuid"] and int(row[1]) not in owned_pids]
    return {"host_tree_RSS_bytes": total, "gpu_peak_allocated_bytes": torch.cuda.max_memory_allocated(),
            "gpu_peak_reserved_bytes": torch.cuda.max_memory_reserved(),
            "foreign_gpu_process_count": len(foreign)}
