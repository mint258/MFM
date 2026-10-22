"""Read-only, bounded observation inside one already-owned Slurm allocation."""
import argparse
import csv
import json
import os
from pathlib import Path
import socket
import subprocess

import psutil

parser = argparse.ArgumentParser()
parser.add_argument("--job", required=True)
args = parser.parse_args()
assert os.getuid() == 1278 and os.environ.get("SLURM_JOB_ID") == args.job
raw = subprocess.check_output(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,used_memory", "--format=csv,noheader,nounits"], text=True)
rows = list(csv.reader(raw.splitlines()))
observations = []
for row in rows:
    try:
        proc = psutil.Process(int(row[1]))
        if proc.uids().real != os.getuid():
            continue
        cgroup = Path(f"/proc/{proc.pid}/cgroup").read_text()
        if "job_" + args.job not in cgroup:
            continue
        descendants = [proc] + proc.children(recursive=True)
        values = []
        for child in descendants:
            try:
                io = child.io_counters()
                values.append({"pid": child.pid, "parent": child.ppid(), "status": child.status(),
                               "cpu_times": child.cpu_times()._asdict(), "rss": child.memory_info().rss,
                               "io": io._asdict(), "threads": child.num_threads(),
                               "wchan": Path(f"/proc/{child.pid}/wchan").read_text().strip()})
            except (psutil.NoSuchProcess, FileNotFoundError):
                pass
        observations.append({"gpu_uuid": row[0].strip(), "main_pid": proc.pid, "cgroup": cgroup, "processes": values})
    except (psutil.NoSuchProcess, FileNotFoundError):
        pass
gpu = subprocess.check_output(["nvidia-smi", "--query-gpu=uuid,utilization.gpu,memory.used,memory.free", "--format=csv,noheader,nounits"], text=True)
print(json.dumps({"node": socket.gethostname(), "job_id": args.job, "observations": observations, "actual_gpu": gpu}, indent=2), flush=True)
